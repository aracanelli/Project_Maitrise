"""
Fold runner for every model id and the neural training loop.

Every binary model is fitted on the training part of a fold (training repositories minus the
grouped validation split). The validation split drives early stopping (neural models, HGB)
and the F1-maximising decision threshold, which is then frozen; the held-out repository is
only scored. Hyperparameters come from configs/experiment.yaml and are never tuned.

The post-hoc variants lr_log1p, mlp_full_log1p and hybrid_ggnn_log1p run the code of lr,
mlp_full and hybrid_ggnn with one flag: prepare_tabular(log1p=True). They are a post-hoc
sensitivity analysis, not part of the pre-specified model set.
"""

import logging
import queue
import random
import threading
import time

import numpy as np
import torch
from sklearn.metrics import accuracy_score, average_precision_score, f1_score
from torch import nn
from torch_geometric.loader import DataLoader

from src.models import baselines
from src.models.data import MULTICLASS_LABELS, nonbinary_columns, prepare_tabular, select_columns
from src.models.gnn import GraphNet, TabNet, node_num_stats

NAIVE = ["naive_prior", "naive_size", "naive_rule"]
CLASSICAL = ["lr", "rf", "hgb"]
NEURAL = ["mlp_full", "mlp_hist"]
GRAPH = ["gnn_rgcn", "gnn_ggnn", "hybrid_ggnn", "hybrid_ggnn_nohist"]
MULTICLASS = ["lr_multiclass", "hgb_multiclass"]
# post-hoc variants (configs/experiment.yaml posthoc): the base model with
# sign(x) * log1p(|x|) on the non-binary tabular columns; not in "all"
POSTHOC = {"lr_log1p": "lr", "mlp_full_log1p": "mlp_full", "hybrid_ggnn_log1p": "hybrid_ggnn"}
LOG1P_TRANSFORM = "signed_log1p_nonbinary"
MODEL_GROUPS = {
    "naive": NAIVE,
    "classical": CLASSICAL,
    "neural": NEURAL,
    "graph": GRAPH,
    "all": NAIVE + CLASSICAL + NEURAL + GRAPH,
    "multiclass": MULTICLASS,
    "posthoc": list(POSTHOC),
}

# tabular feature set of each model (None = no tabular input)
FEATURE_SET = {
    "naive_prior": None, "naive_size": None, "naive_rule": None,
    "lr": "all", "rf": "all", "hgb": "all",
    "mlp_full": "all", "mlp_hist": "history",
    "gnn_rgcn": None, "gnn_ggnn": None,
    "hybrid_ggnn": "all", "hybrid_ggnn_nohist": "static",
    "lr_multiclass": "all", "hgb_multiclass": "all",
    "lr_log1p": "all", "mlp_full_log1p": "all", "hybrid_ggnn_log1p": "all",
}
ENCODER = {"gnn_rgcn": "rgcn", "gnn_ggnn": "ggnn", "hybrid_ggnn": "ggnn", "hybrid_ggnn_nohist": "ggnn",
           "hybrid_ggnn_log1p": "ggnn"}
EVAL_BATCH_FACTOR = 4

log = logging.getLogger(__name__)


def default_device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def base_model(model_id):
    """The pre-specified model a post-hoc variant copies (the id itself otherwise)."""
    return POSTHOC.get(model_id, model_id)


def posthoc_spec(model_id, cfg):
    """configs/experiment.yaml posthoc entry of a variant, checked against what the code does."""
    p = cfg["posthoc"]
    if p["models"].get(model_id) != POSTHOC[model_id] or p["tabular_transform"] != LOG1P_TRANSFORM:
        raise ValueError(f"configs/experiment.yaml posthoc does not describe {model_id} as implemented "
                         f"({POSTHOC[model_id]} + {LOG1P_TRANSFORM})")
    return {"base": POSTHOC[model_id], "tabular_transform": LOG1P_TRANSFORM, "prespecified": False}


def model_config(model_id, cfg):
    """Hyperparameters that define a model id (recorded in the sidecar and in the run key)."""
    if model_id in POSTHOC:
        out = model_config(POSTHOC[model_id], cfg)
        out["posthoc"] = posthoc_spec(model_id, cfg)
        return out
    m = cfg["models"]
    base = model_id.replace("_multiclass", "")
    if base in CLASSICAL:
        return {base: m[base]}
    if model_id in NEURAL:
        return {"mlp": m["mlp"], "training": m["training"]}
    if model_id in GRAPH:
        out = {"gnn": m["gnn"], "training": m["training"]}
        if FEATURE_SET[model_id]:
            out["mlp"] = m["mlp"]
        return out
    return {}


def tensor_batches(X, y, batch_size, shuffle=False, seed=0):
    gen = torch.Generator().manual_seed(seed)

    def batches():
        n = len(y)
        order = torch.randperm(n, generator=gen) if shuffle else torch.arange(n)
        order = order.to(X.device)
        for s in range(0, n, batch_size):
            idx = order[s:s + batch_size]
            yield X[idx], y[idx]
    return batches


def background(iterable, size=3):
    """Run a generator in a thread (PyG collation is CPU work that overlaps the GPU step)."""
    q = queue.Queue(maxsize=size)
    done = object()

    def work():
        try:
            for item in iterable:
                q.put(item)
        except BaseException as e:
            q.put(e)
            return
        q.put(done)

    threading.Thread(target=work, daemon=True).start()
    while True:
        item = q.get()
        if item is done:
            return
        if isinstance(item, BaseException):
            raise item
        yield item


def graph_batches(graph_list, batch_size, device, shuffle=False, seed=0, cache=False):
    """Batches of PyG graphs; cache=True collates once and keeps the batches on the device."""
    # an explicit generator also for unshuffled loaders: otherwise the DataLoader draws its
    # base seed from the global RNG, from the collation thread
    gen = torch.Generator().manual_seed(seed)
    loader = DataLoader(graph_list, batch_size=batch_size, shuffle=shuffle, generator=gen)
    cuda = str(device).startswith("cuda")

    def collated():
        for b in loader:
            yield b.pin_memory() if cuda else b

    def batches():
        for b in background(collated()):
            b = b.to(device, non_blocking=cuda)
            yield b, b.y

    if cache:
        kept = list(batches())
        return lambda: iter(kept)
    return batches


@torch.no_grad()
def predict(model, batches):
    model.eval()
    scores, ys = [], []
    for inputs, y in batches():
        scores.append(torch.sigmoid(model(inputs)).float().cpu())
        ys.append(y.float().cpu())
    if not scores:
        return np.zeros(0), np.zeros(0)
    return torch.cat(scores).numpy().astype(np.float64), torch.cat(ys).numpy()


def train_neural(model, train_batches, val_batches, pos_weight, tcfg, device, max_epochs=None):
    """AdamW + weighted BCE; early stopping on validation PR-AUC; best weights restored."""
    max_epochs = max_epochs or tcfg["max_epochs"]
    # fused=True is the single-kernel CUDA AdamW (same update rule)
    opt = torch.optim.AdamW(model.parameters(), lr=tcfg["lr"], weight_decay=tcfg["weight_decay"],
                            fused=str(device).startswith("cuda"))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, dtype=torch.float32, device=device))
    best_ap, best_epoch, best_state, bad = -1.0, 0, None, 0
    history = []
    t0 = time.time()
    for epoch in range(1, max_epochs + 1):
        model.train()
        total = torch.zeros((), device=device)
        n = 0
        for inputs, y in train_batches():
            opt.zero_grad()
            loss = loss_fn(model(inputs), y)
            loss.backward()
            opt.step()
            total += loss.detach() * len(y)
            n += len(y)
        vs, vy = predict(model, val_batches)
        ap = float(average_precision_score(vy, np.nan_to_num(vs)))
        history.append({"epoch": epoch, "loss": round(float(total) / max(n, 1), 5), "val_pr_auc": round(ap, 5)})
        log.info("    epoch %d loss %.4f val PR-AUC %.4f (%.0fs)", epoch, history[-1]["loss"], ap, time.time() - t0)
        if ap > best_ap:
            best_ap, best_epoch, bad = ap, epoch, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= tcfg["patience"]:
                break
    model.load_state_dict(best_state)
    return {"epochs": len(history), "best_epoch": best_epoch, "best_val_pr_auc": best_ap,
            "train_seconds": round(time.time() - t0, 2), "history": history}


def fit_classical(name, ev, fold, seed, cfg):
    """Fit lr/rf/hgb (or lr_log1p) on the fold's training part. Returns (model, X of all rows, column idx)."""
    cols = select_columns(ev["groups"], FEATURE_SET[name])
    X = ev["X"][:, cols]
    fit, val = fold["fit_idx"], fold["val_idx"]
    base = base_model(name)
    if base == "lr":
        X = prepare_tabular(X, fit, impute=True, scale=True, log1p=name in POSTHOC)
    elif base == "rf":
        X = prepare_tabular(X, fit, impute=True, scale=False)
    y = ev["y"]
    model = baselines.make_classifier(base, seed, cfg["models"][base])
    baselines.fit_classifier(base, model, X[fit], y[fit], X[val], y[val])
    return model, X, cols


def run_fold(model_id, ev, fold, seed, cfg, graphs=None, graph_info=None, device=None, max_epochs=None):
    """Train one model on one LORO fold. Returns test scores, predictions, threshold and info."""
    device = device or default_device()
    y = ev["y"]
    fit, val, test = fold["fit_idx"], fold["val_idx"], fold["test_idx"]
    info = {
        "test_repo": fold["test_repo"], "fold_index": fold["fold_index"], "val_seed": fold["val_seed"],
        "low_support": fold["low_support"],
        "n_train": int(len(fit)), "n_val": int(len(val)), "n_test": int(len(test)),
        "n_train_pos": int(y[fit].sum()), "n_val_pos": int(y[val].sum()), "n_test_pos": int(y[test].sum()),
    }
    t0 = time.time()

    if model_id == "naive_prior":
        prevalence = float(y[fit].mean())
        n = len(y)
        scores_all = baselines.naive_prior_scores(n, seed, fold["fold_index"])
        vs, ts = scores_all[val], scores_all[test]
        threshold = prevalence
        val_pred = (vs < threshold).astype(int)
        test_pred = (ts < threshold).astype(int)
        info["decision"] = "score < threshold (training prevalence)"
    else:
        if model_id == "naive_size":
            s = baselines.naive_size_scores(ev["X"], ev["columns"])
            vs, ts = s[val], s[test]
        elif model_id == "naive_rule":
            s = baselines.naive_rule_scores(ev["task"], ev["X"], ev["columns"])
            vs, ts = s[val], s[test]
        elif base_model(model_id) in CLASSICAL:
            model, X, cols = fit_classical(model_id, ev, fold, seed, cfg)
            vs = baselines.positive_scores(model, X[val])
            ts = baselines.positive_scores(model, X[test])
            info["n_features"] = len(cols)
            if model_id == "hgb":
                info["n_iter"] = int(model.n_iter_)
        elif base_model(model_id) in NEURAL or base_model(model_id) in GRAPH:
            vs, ts, extra = _run_neural(model_id, ev, fold, seed, cfg, graphs, graph_info, device, max_epochs)
            info.update(extra)
        else:
            raise ValueError(f"unknown model {model_id}")
        if model_id in POSTHOC:
            # recorded because the x_ buckets, h_commit_index and h_file_prior_churn are already
            # log1p counts (src/features), so these columns get log1p twice
            cols = select_columns(ev["groups"], FEATURE_SET[model_id])
            moved = [j for j, m in zip(cols, nonbinary_columns(ev["X"][:, cols], fit)) if m]
            by_group = {}
            for j in moved:
                by_group[ev["groups"][j]] = by_group.get(ev["groups"][j], 0) + 1
            info["tabular_transform"] = LOG1P_TRANSFORM
            info["n_log1p_columns"] = len(moved)
            info["log1p_columns_by_group"] = by_group
            info["log1p_columns"] = [ev["columns"][j] for j in moved]
        threshold = baselines.f1_threshold(y[val], vs)
        val_pred = (np.nan_to_num(vs) >= threshold).astype(int)
        test_pred = (np.nan_to_num(ts) >= threshold).astype(int)
        info["decision"] = "score >= threshold (F1-max on validation)"

    info["threshold"] = float(threshold)
    info["val"] = baselines.binary_metrics(y[val], vs, val_pred)
    info.setdefault("train_seconds", round(time.time() - t0, 2))
    info["fold_seconds"] = round(time.time() - t0, 2)
    return {"scores": np.asarray(ts, dtype=np.float64), "y_pred": test_pred, "threshold": float(threshold),
            "val_scores": np.asarray(vs, dtype=np.float64), "info": info}


def _run_neural(model_id, ev, fold, seed, cfg, graphs, graph_info, device, max_epochs):
    m = cfg["models"]
    tcfg = m["training"]
    y = ev["y"]
    fit, val, test = fold["fit_idx"], fold["val_idx"], fold["test_idx"]
    bs = tcfg["batch_size"]
    n_pos = max(int(y[fit].sum()), 1)
    pos_weight = (len(fit) - n_pos) / n_pos

    table = None
    fs = FEATURE_SET[model_id]
    if fs:
        # hybrid models read their row of this table by gidx, so every row is transformed alike
        cols = select_columns(ev["groups"], fs)
        Xt = prepare_tabular(ev["X"][:, cols], fit, impute=True, scale=True, log1p=model_id in POSTHOC)
        table = torch.tensor(Xt, dtype=torch.float32, device=device)

    set_seed(seed)
    if base_model(model_id) in NEURAL:
        model = TabNet(table.shape[1], m["mlp"]["hidden"], m["mlp"]["layers"], m["mlp"]["dropout"]).to(device)
        yt = torch.tensor(y, dtype=torch.float32, device=device)
        idx = {k: torch.tensor(v, dtype=torch.long, device=device) for k, v in
               (("fit", fit), ("val", val), ("test", test))}
        train_b = tensor_batches(table[idx["fit"]], yt[idx["fit"]], bs, shuffle=True, seed=seed)
        val_b = tensor_batches(table[idx["val"]], yt[idx["val"]], bs * EVAL_BATCH_FACTOR)
        test_b = tensor_batches(table[idx["test"]], yt[idx["test"]], bs * EVAL_BATCH_FACTOR)
    else:
        if graphs is None:
            raise ValueError(f"{model_id} needs graphs")
        n_tab = table.shape[1] if table is not None else 0
        model = GraphNet(ENCODER[model_id], graph_info, m["gnn"], m["mlp"]["layers"], n_tab=n_tab).to(device)
        mean, std = node_num_stats(graphs, fit)
        model.set_node_stats(mean.to(device), std.to(device))
        if table is not None:
            model.set_tab_table(table)
        train_b = graph_batches([graphs[i] for i in fit], bs, device, shuffle=True, seed=seed)
        val_b = graph_batches([graphs[i] for i in val], bs * EVAL_BATCH_FACTOR, device, cache=True)
        test_b = graph_batches([graphs[i] for i in test], bs * EVAL_BATCH_FACTOR, device)

    extra = train_neural(model, train_b, val_b, pos_weight, tcfg, device, max_epochs)
    extra["pos_weight"] = round(pos_weight, 5)
    extra["n_params"] = int(sum(p.numel() for p in model.parameters()))
    if table is not None:
        extra["n_features"] = int(table.shape[1])
    vs, _ = predict(model, val_b)
    ts, _ = predict(model, test_b)
    del model, table
    if str(device).startswith("cuda"):
        torch.cuda.empty_cache()
    return vs, ts, extra


def run_multiclass_fold(model_id, ev, fold, seed, cfg):
    """lr_multiclass / hgb_multiclass on the method-level multiclass view (supplementary)."""
    name = model_id.replace("_multiclass", "")
    y = ev["y"]
    fit, val, test = fold["fit_idx"], fold["val_idx"], fold["test_idx"]
    t0 = time.time()
    cols = select_columns(ev["groups"], FEATURE_SET[model_id])
    X = ev["X"][:, cols]
    if name == "lr":
        X = prepare_tabular(X, fit, impute=True, scale=True)
    model = baselines.make_classifier(name, seed, cfg["models"][name])
    if set(y[val]) <= set(y[fit]):
        baselines.fit_classifier(name, model, X[fit], y[fit], X[val], y[val])
    else:
        baselines.fit_classifier(name, model, X[fit], y[fit])

    def proba(rows):
        out = np.zeros((len(rows), len(MULTICLASS_LABELS)))
        out[:, list(model.classes_)] = model.predict_proba(X[rows])
        return out

    pv, pt = proba(val), proba(test)
    info = {
        "test_repo": fold["test_repo"], "fold_index": fold["fold_index"], "val_seed": fold["val_seed"],
        "low_support": fold["low_support"],
        "n_train": int(len(fit)), "n_val": int(len(val)), "n_test": int(len(test)),
        "train_class_counts": {MULTICLASS_LABELS[c]: int((y[fit] == c).sum()) for c in range(len(MULTICLASS_LABELS))},
        "test_class_counts": {MULTICLASS_LABELS[c]: int((y[test] == c).sum()) for c in range(len(MULTICLASS_LABELS))},
        "val": {"macro_f1": float(f1_score(y[val], pv.argmax(1), average="macro", zero_division=0)),
                "accuracy": float(accuracy_score(y[val], pv.argmax(1)))},
        "n_features": len(cols),
        "train_seconds": round(time.time() - t0, 2),
    }
    return {"proba": pt, "y_pred": pt.argmax(1), "val_proba": pv, "info": info}
