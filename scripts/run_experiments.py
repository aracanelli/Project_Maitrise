"""
Stage 7: train and score the models with leave-one-repository-out.

    python -m scripts.run_experiments --setting R4 --task add_log --models naive,classical --seeds 0,1,2,3,4 --importance
    python -m scripts.run_experiments --setting R4 --task add_log --models neural,graph
    python -m scripts.run_experiments --setting R1 --task remove_log --models naive,classical
    python -m scripts.run_experiments --setting R4 --task multiclass --models lr_multiclass,hgb_multiclass
    python -m scripts.run_experiments --setting R4 --task add_log_post --models all
    python -m scripts.run_experiments --setting R4 --task remove_log --models posthoc
    python -m scripts.run_experiments --benchmark

Model groups: naive, classical, neural (mlp_*), graph (gnn_* and hybrid_*), all (the
pre-specified models) and posthoc (lr_log1p, mlp_full_log1p, hybrid_ggnn_log1p; R4 and the
tasks listed under posthoc in configs/experiment.yaml only). add_log_post is the masked
post-state view of add_log. It only runs when its evaluation set matches the add_log one
of the same data dir (same instances in the same order, same repos, commits and labels),
and stops with an error before training otherwise.

Writes data/results/predictions/<setting>/<task>/<model_id>/seed<k>.csv and seed<k>.json.
The sidecar is rewritten after every fold, so an interrupted run resumes at the next fold.
An existing output is reused only under the same run key (config, protocol, folds of
folds.json, evaluation-set content, graph files, epochs override, device kind) and the
same code. Otherwise nothing runs and the exit code is 2; --overwrite recomputes the
selected folds. Logs go to data/results/logs/. --max-epochs (smoke tests) needs a
--results-dir other than data/results.
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import torch
import torch_geometric
from threadpoolctl import threadpool_limits

from src.common.config import DATA, ROOT, load_config
from src.models import train as T
from src.models.data import (MULTICLASS_LABELS, build_eval_set, check_paired_view, load_folds, loro_folds,
                             processed_dir, task_folds)
from src.models.gnn import build_graphs, load_graph_arrays
from src.models.importance import N_REPEATS, hgb_importance

log = logging.getLogger("run_experiments")

BINARY_TASKS = ["add_log", "remove_log", "change_level", "add_log_post"]
SETTINGS = ["R4", "R1", "R10"]
# folds.json fields that are part of the run key: the folds depend on test_repos and
# low_support; excluded is not read, but removing it would invalidate every existing key
KEY_FOLD_FIELDS = ("test_repos", "low_support", "excluded")


def is_neural(model_id):
    return T.base_model(model_id) in T.NEURAL + T.GRAPH


def uses_graphs(model_id):
    return T.base_model(model_id) in T.GRAPH


def expand_models(spec, setting, task):
    out = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        if part == "all" and task == "multiclass":
            names = T.MULTICLASS
        elif part == "all" and setting != "R4":
            names = T.NAIVE + T.CLASSICAL
            log.info("--models all in %s expands to naive + classical only", setting)
        elif part in T.MODEL_GROUPS:
            names = T.MODEL_GROUPS[part]
        else:
            names = [part]
        for n in names:
            if n not in out:
                out.append(n)
    known = set(T.FEATURE_SET)
    for n in out:
        if n not in known:
            raise SystemExit(f"unknown model id {n}")
        if task == "multiclass" and n not in T.MULTICLASS:
            raise SystemExit(f"{n} is not a multiclass model (use lr_multiclass, hgb_multiclass)")
        if task != "multiclass" and n in T.MULTICLASS:
            raise SystemExit(f"{n} only runs with --task multiclass")
        if setting != "R4" and is_neural(n):
            raise SystemExit(f"{n} refused for {setting}: R1/R10 are a sensitivity analysis for "
                             f"naive and classical models only")
        if n in T.POSTHOC:
            tasks = load_config("experiment")["posthoc"]["tasks"]
            if setting != "R4" or task not in tasks:
                raise SystemExit(f"{n} is a post-hoc variant: R4 and tasks {tasks} only "
                                 f"(configs/experiment.yaml posthoc)")
    return out


class RunConflict(RuntimeError):
    pass


def code_sha1():
    h = hashlib.sha1()
    for p in sorted((ROOT / "src" / "models").glob("*.py")) + [Path(__file__)]:
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def file_sha1(*paths):
    h = hashlib.sha1()
    for p in paths:
        if not p.exists():
            h.update(b"missing")
            continue
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(1 << 22), b""):
                h.update(block)
    return h.hexdigest()


def graph_inputs_sha1(task, data_dir, graph_pos):
    """Graph files plus the evaluation-row -> graph mapping (graph models only)."""
    base = processed_dir(data_dir) / "graphs"
    h = hashlib.sha1(file_sha1(base / f"{task}.npz", base / f"{task}_index.csv",
                               base / f"{task}_meta.json").encode("ascii"))
    h.update(np.ascontiguousarray(graph_pos, dtype=np.int64).tobytes())
    return h.hexdigest()


def device_kind(device):
    return "cuda" if str(device).startswith("cuda") else "cpu"


def run_key(model_id, cfg, ev, args, inputs):
    """Everything a (model, seed) result depends on, as (sha1, payload).

    The key covers the model configuration, protocol, folds of the folds.json entry,
    evaluation-set content (ids, labels, repos, commits, feature values), graph files (graph
    models), epochs override and device kind (neural models, whose floats differ between CPU
    and GPU). Only parsed configuration values are hashed, so comments in
    configs/experiment.yaml do not change it; a post-hoc variant's transform is part of its
    "config". Only KEY_FOLD_FIELDS of the folds.json entry are hashed, so informational
    fields such as per_repo or few_commit_folds leave the key unchanged.
    """
    neural = is_neural(model_id)
    payload = {
        "model": model_id,
        "config": T.model_config(model_id, cfg),
        "protocol": {k: v for k, v in cfg["protocol"].items() if k != "seeds"},
        "sampling_seed": cfg["sampling"]["seed"],
        "folds": {k: v for k, v in inputs["folds"].items() if k in KEY_FOLD_FIELDS},
        "max_epochs_override": args.max_epochs if neural else None,
        "device": device_kind(args.device) if neural else None,
        "eval_set_sha1": ev["eval_set_sha1"],
        "content_sha1": ev["content_sha1"],
        "graph_inputs_sha1": inputs.get("graph_inputs_sha1") if uses_graphs(model_id) else None,
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest(), payload


def importance_key(hgb_key):
    payload = {"hgb_run_key": hgb_key, "seed": 0, "n_repeats": N_REPEATS, "scoring": "average_precision"}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest(), payload


def write_atomic(path, text, tries=6, wait=0.5):
    """Write via a .tmp file and os.replace. On Windows the replace fails while another
    program (a reader, Excel, a sync client) has the file open, so retry for ~15 s."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    for k in range(tries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if k == tries - 1:
                raise
            log.warning("%s is locked by another program; retrying in %.1fs", path, wait * 2 ** k)
            time.sleep(wait * 2 ** k)


def save_outputs(files):
    """Write [(path, text), ...] in order; False (and logged) if a file stays locked."""
    for path, text in files:
        try:
            write_atomic(path, text)
        except PermissionError as e:
            log.error("could not write %s (%s); kept in memory, retried after the next fold", path, e)
            return False
    return True


def read_sidecar(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def keep_listed(df, side, column, counts):
    """Rows of the folds the sidecar lists, with the expected row count per fold.

    A crash between the csv and the sidecar write leaves rows of an unlisted fold in the
    csv; those rows are dropped and the fold is recomputed. A listed fold whose row count
    is wrong is dropped from both.
    """
    listed = {f["test_repo"]: counts(f) for f in side["folds"] if not f.get("skipped")}
    df = df[df[column].isin(listed)]
    have = df[column].value_counts()
    bad = [r for r, n in listed.items() if int(have.get(r, 0)) != n]
    if bad:
        log.warning("%s: rows of folds %s do not match the sidecar; they are recomputed", column, bad)
        side["folds"] = [f for f in side["folds"] if f["test_repo"] not in bad]
        df = df[~df[column].isin(bad)]
    return df


def load_existing(csv_path, json_path):
    side = read_sidecar(json_path)
    if side is None or not csv_path.exists():
        return None, None
    # round_trip: the floats of the kept folds are written back unchanged
    df = pd.read_csv(csv_path, dtype={"instance_id": str, "test_repo": str}, float_precision="round_trip")
    return side, keep_listed(df, side, "test_repo", lambda f: f["n_test"])


def plan_folds(side, key, code, selected, overwrite):
    """(folds kept from an existing output, folds to compute, conflict message or None).

    One output file never mixes run keys or code versions. A different key is a conflict
    unless --overwrite, which recomputes everything. Adding folds next to folds made by
    other code is a conflict unless --overwrite, which drops the old folds. With --overwrite
    and a matching key and code, only the selected folds are recomputed.
    """
    if side is None:
        return [], list(selected), None
    done = [f["test_repo"] for f in side["folds"]]
    if side.get("run_key") != key:
        if not overwrite:
            return done, [], "was produced with another configuration or other inputs"
        return [], list(selected), None
    keep = [r for r in done if not (overwrite and r in selected)]
    todo = [r for r in selected if r not in keep]
    if todo and keep and side.get("code_sha1") != code:
        if not overwrite:
            return keep, [], (f"has folds {keep} from another version of src/models; resuming would "
                              f"mix code versions in one file")
        return [], list(selected), None
    return keep, todo, None


def key_difference(side, payload):
    old = side.get("key_inputs") or {}
    return sorted(k for k in set(old) | set(payload) if old.get(k) != payload.get(k)) or ["run_key"]


def environment():
    return {
        "python": platform.python_version(), "torch": torch.__version__,
        "torch_geometric": torch_geometric.__version__, "sklearn": sklearn.__version__,
        "numpy": np.__version__, "cuda": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def prediction_paths(results_dir, setting, task, model_id, seed):
    d = results_dir / "predictions" / setting / task / model_id
    return d / f"seed{seed}.csv", d / f"seed{seed}.json"


def check_outputs(models, seeds, ev, folds, cfg, results_dir, args, inputs, code):
    """Conflicts of the requested runs with existing outputs, before anything is trained."""
    selected = [f["test_repo"] for f in folds]
    problems = []
    for model_id in models:
        key, payload = run_key(model_id, cfg, ev, args, inputs)
        for seed in seeds:
            csv_path, json_path = prediction_paths(results_dir, ev["setting"], ev["task"], model_id, seed)
            side = read_sidecar(json_path) if csv_path.exists() else None
            _, _, problem = plan_folds(side, key, code, selected, args.overwrite)
            if problem:
                if side.get("run_key") != key:
                    problem += f" (differs in: {', '.join(key_difference(side, payload))})"
                problems.append(f"{json_path}: {problem}")
    if args.importance and ev["task"] != "multiclass":
        key, _ = importance_key(run_key("hgb", cfg, ev, args, inputs)[0])
        f_path, g_path, path = importance_paths(results_dir, ev["setting"], ev["task"])
        side = read_sidecar(path) if f_path.exists() and g_path.exists() else None
        _, _, problem = plan_folds(side, key, code, selected, args.overwrite)
        if problem:
            problems.append(f"{path}: {problem}")
    return problems


def run_model_seed(model_id, seed, ev, folds, all_folds, cfg, results_dir, args, inputs, code,
                   graphs=None, graph_info=None):
    multiclass = model_id in T.MULTICLASS
    csv_path, json_path = prediction_paths(results_dir, ev["setting"], ev["task"], model_id, seed)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    key, payload = run_key(model_id, cfg, ev, args, inputs)

    side, prev = load_existing(csv_path, json_path)
    keep, todo, problem = plan_folds(side, key, code, [f["test_repo"] for f in folds], args.overwrite)
    if problem:
        raise RunConflict(f"{json_path}: {problem}")
    if not todo:
        if side is not None and side.get("code_sha1") != code:
            log.warning("%s seed %d: outputs exist but were computed by another version of src/models "
                        "(kept; --overwrite recomputes them)", model_id, seed)
        log.info("skip %s seed %d: outputs exist", model_id, seed)
        return
    if keep:
        side["folds"] = [f for f in side["folds"] if f["test_repo"] in keep]
        prev = prev[prev["test_repo"].isin(keep)]
        log.info("%s seed %d: keeping folds %s, computing %s", model_id, seed, keep, todo)
    else:
        if side is not None:
            log.info("%s seed %d: existing output replaced", model_id, seed)
        side = {
            "setting": ev["setting"], "task": ev["task"], "model": model_id, "seed": seed,
            "run_key": key, "key_inputs": payload, "eval_set_sha1": ev["eval_set_sha1"],
            "content_sha1": ev["content_sha1"], "n_eval": len(ev["ids"]),
            "n_selected": ev["n_selected"], "dropped": ev["dropped"],
            "feature_set": T.FEATURE_SET[model_id], "config": T.model_config(model_id, cfg),
            "max_epochs_override": payload["max_epochs_override"], "folds_entry": inputs["folds"],
            "folds": [],
        }
        if "paired_with" in inputs:
            side["paired_with"] = inputs["paired_with"]
        prev = None
    frames = [prev] if prev is not None else []
    env = environment()
    device = args.device if is_neural(model_id) else None
    saved = True

    for fold in [f for f in folds if f["test_repo"] in todo]:
        log.info("%s %s %s seed %d fold %s: train %d (pos %d) val %d (pos %d) test %d (pos %d)",
                 ev["setting"], ev["task"], model_id, seed, fold["test_repo"], len(fold["fit_idx"]),
                 int((ev["y"][fold["fit_idx"]] > 0).sum()), len(fold["val_idx"]),
                 int((ev["y"][fold["val_idx"]] > 0).sum()), len(fold["test_idx"]),
                 int((ev["y"][fold["test_idx"]] > 0).sum()))
        test = fold["test_idx"]
        ids = [ev["ids"][i] for i in test]
        if multiclass:
            res = T.run_multiclass_fold(model_id, ev, fold, seed, cfg)
            df = pd.DataFrame({
                "instance_id": ids, "test_repo": fold["test_repo"],
                "y_true": [MULTICLASS_LABELS[c] for c in ev["y"][test]],
                "y_pred": [MULTICLASS_LABELS[c] for c in res["y_pred"]],
            })
            for c, name in enumerate(MULTICLASS_LABELS):
                df[f"score_{name}"] = res["proba"][:, c]
            log.info("  val macro-F1 %.3f", res["info"]["val"]["macro_f1"])
        else:
            res = T.run_fold(model_id, ev, fold, seed, cfg, graphs, graph_info, args.device, args.max_epochs)
            df = pd.DataFrame({
                "instance_id": ids, "test_repo": fold["test_repo"], "y_true": ev["y"][test],
                "score": res["scores"], "y_pred": res["y_pred"].astype(int), "threshold": res["threshold"],
            })
            v = res["info"]["val"]
            log.info("  threshold %.4g | val PR-AUC %s F1 %.3f | %s epochs | %.1fs", res["threshold"],
                     None if v["pr_auc"] is None else round(v["pr_auc"], 3), v["f1"],
                     res["info"].get("epochs", "-"), res["info"]["fold_seconds"])
        res["info"].update(code_sha1=code, environment=env, device=device)
        frames.append(df)
        side["folds"].append(res["info"])
        side["folds"].sort(key=lambda f: f["fold_index"])
        out = pd.concat(frames, ignore_index=True)
        order = {f["test_repo"]: f["fold_index"] for f in side["folds"]}
        out = out.sort_values("test_repo", key=lambda s: s.map(order), kind="stable")
        frames = [out]
        side["complete"] = {f["test_repo"] for f in side["folds"]} >= {f["test_repo"] for f in all_folds}
        side["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        side["code_sha1"] = code
        side["environment"] = env
        side["device"] = device
        # csv first: rows of a fold the sidecar does not list yet are dropped on resume
        saved = save_outputs([(csv_path, out.to_csv(index=False)), (json_path, json.dumps(side, indent=1))])
    if not saved and not save_outputs([(csv_path, frames[0].to_csv(index=False)),
                                       (json_path, json.dumps(side, indent=1))]):
        raise OSError(f"could not write {csv_path} / {json_path}: the results are in the .tmp files next "
                      f"to them (close the program holding the file and rename them)")
    log.info("wrote %s (%d rows, complete=%s)", csv_path, len(frames[0]), side["complete"])


def append_rows(df, rows, order):
    if rows:
        new = pd.DataFrame(rows, columns=df.columns)
        df = new if df.empty else pd.concat([df, new], ignore_index=True)
    return df.sort_values("fold", key=lambda s: s.map(order), kind="stable")


def importance_paths(results_dir, setting, task):
    d = results_dir / "importance" / setting / task
    return d / "hgb_seed0_features.csv", d / "hgb_seed0_groups.csv", d / "hgb_seed0.json"


def run_importance(ev, folds, all_folds, cfg, results_dir, args, inputs, code):
    """Permutation importance of hgb seed 0, per fold, resumable like the predictions.

    The sidecar hgb_seed0.json records the key and the folds covered, so running folds in
    chunks fills in the missing folds and a change of inputs is caught.
    """
    f_path, g_path, s_path = importance_paths(results_dir, ev["setting"], ev["task"])
    f_path.parent.mkdir(parents=True, exist_ok=True)
    key, payload = importance_key(run_key("hgb", cfg, ev, args, inputs)[0])
    side = read_sidecar(s_path)
    feats = groups = None
    if side is not None and f_path.exists() and g_path.exists():
        feats = keep_listed(pd.read_csv(f_path, dtype={"fold": str}, float_precision="round_trip"),
                            side, "fold", lambda f: f["n_features"])
        groups = keep_listed(pd.read_csv(g_path, dtype={"fold": str}, float_precision="round_trip"),
                             side, "fold", lambda f: f["n_groups"])
        listed = [f["test_repo"] for f in side["folds"]]
        feats = feats[feats["fold"].isin(listed)]
    elif side is not None:
        side = None
    keep, todo, problem = plan_folds(side, key, code, [f["test_repo"] for f in folds], args.overwrite)
    if problem:
        raise RunConflict(f"{s_path}: {problem}")
    if not todo:
        log.info("skip importance: %s covers the requested folds", f_path)
        return
    if keep:
        side["folds"] = [f for f in side["folds"] if f["test_repo"] in keep]
        feats, groups = feats[feats["fold"].isin(keep)], groups[groups["fold"].isin(keep)]
    else:
        side = {"setting": ev["setting"], "task": ev["task"], "model": "hgb", "seed": 0,
                "run_key": key, "key_inputs": payload, "n_repeats": N_REPEATS, "folds": []}
        feats = pd.DataFrame(columns=["fold", "feature", "mean_drop", "std"])
        groups = pd.DataFrame(columns=["fold", "group", "mean_drop", "std"])
    env = environment()
    saved = True
    for fold in [f for f in folds if f["test_repo"] in todo]:
        t0 = time.time()
        fr, gr = hgb_importance(ev, [fold], cfg, seed=0)
        side["folds"].append({"test_repo": fold["test_repo"], "fold_index": fold["fold_index"],
                              "n_test": int(len(fold["test_idx"])), "n_features": len(fr), "n_groups": len(gr),
                              "skipped": not fr, "seconds": round(time.time() - t0, 2), "code_sha1": code})
        side["folds"].sort(key=lambda f: f["fold_index"])
        order = {f["test_repo"]: f["fold_index"] for f in side["folds"]}
        feats = append_rows(feats, fr, order)
        groups = append_rows(groups, gr, order)
        side["complete"] = {f["test_repo"] for f in side["folds"]} >= {f["test_repo"] for f in all_folds}
        side["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        side["code_sha1"] = code
        side["environment"] = env
        log.info("importance fold %s: %d features, %d groups in %.0fs%s", fold["test_repo"], len(fr), len(gr),
                 time.time() - t0, " (skipped: single-class test fold)" if not fr else "")
        saved = save_outputs([(f_path, feats.to_csv(index=False)), (g_path, groups.to_csv(index=False)),
                              (s_path, json.dumps(side, indent=1))])
    if not saved and not save_outputs([(f_path, feats.to_csv(index=False)), (g_path, groups.to_csv(index=False)),
                                       (s_path, json.dumps(side, indent=1))]):
        raise OSError(f"could not write the importance files in {f_path.parent} (see the .tmp files)")
    log.info("importance written to %s (folds %s)", f_path.parent, [f["test_repo"] for f in side["folds"]])


def setup_logging(results_dir, name):
    log_dir = results_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{name}_{time.strftime('%Y%m%d-%H%M%S')}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers = [logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler(sys.stdout)]
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    return handlers, path


def synthetic_graph_arrays(n_graphs, nodes, edges, n_rel, n_types, n_num, seed=0):
    """Random arrays in the Stage-6 npz layout (benchmark only)."""
    rng = np.random.default_rng(seed)
    n_nodes = np.clip(rng.poisson(nodes, n_graphs), 10, None)
    n_edges = np.clip(rng.poisson(edges, n_graphs), 1, None)
    node_ptr = np.concatenate([[0], np.cumsum(n_nodes)]).astype(np.int64)
    edge_ptr = np.concatenate([[0], np.cumsum(n_edges)]).astype(np.int64)
    N, E = int(node_ptr[-1]), int(edge_ptr[-1])
    toks = rng.poisson(1.5, N)
    tok_ptr = np.concatenate([[0], np.cumsum(toks)]).astype(np.int64)
    per_edge = np.repeat(n_nodes, n_edges)
    return {
        "node_ptr": node_ptr, "edge_ptr": edge_ptr, "tok_ptr": tok_ptr,
        "node_type": rng.integers(0, n_types, N).astype(np.int16),
        "node_num": rng.normal(size=(N, n_num)).astype(np.float32),
        "tok_ids": rng.integers(0, 128, int(tok_ptr[-1])).astype(np.int16),
        "edge_index": (rng.random((2, E)) * per_edge).astype(np.int32),
        "edge_type": rng.integers(0, n_rel, E).astype(np.int8),
        "anchor_local": (n_nodes - 1).astype(np.int32),
        "target_local": rng.integers(0, n_nodes).astype(np.int32),
    }


def benchmark(args, cfg):
    """Seconds per epoch and peak GPU memory on a synthetic dataset shaped like the real one."""
    G = args.bench_graphs
    t0 = time.time()
    arrays = synthetic_graph_arrays(G, 150, 600, 14, 32, 8)
    y = (np.random.default_rng(1).random(G) < 0.2).astype(np.int64)
    graphs, info = build_graphs(arrays, np.arange(G), y)
    log.info("benchmark: built %d graphs (%d nodes, %d edges) in %.1fs; info %s", G,
             int(arrays["node_ptr"][-1]), int(arrays["edge_ptr"][-1]), time.time() - t0, info)
    n_tab = 190
    rng = np.random.default_rng(2)
    ev = {"task": "bench", "y": y, "X": rng.normal(size=(G, n_tab)),
          "groups": (["h"] * 10 + ["m"] * 52 + ["x"] * 128), "columns": [f"c{j}" for j in range(n_tab)]}
    test = np.arange(G - G // 10, G)
    train = np.arange(0, G - G // 10)
    val = train[: int(0.15 * len(train))]
    fit = train[int(0.15 * len(train)):]
    fold = {"test_repo": "bench", "fold_index": 0, "val_seed": 0, "low_support": False,
            "fit_idx": fit, "val_idx": val, "test_idx": test}
    bench_cfg = json.loads(json.dumps(cfg))
    bench_cfg["models"]["training"]["patience"] = 10 ** 6
    results = {}
    for model_id in ["gnn_rgcn", "gnn_ggnn", "hybrid_ggnn"]:
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        t1 = time.time()
        res = T.run_fold(model_id, ev, fold, 0, bench_cfg, graphs, info, args.device, args.bench_epochs)
        wall = time.time() - t1
        per_epoch = res["info"]["train_seconds"] / res["info"]["epochs"]
        peak = torch.cuda.max_memory_allocated() / 2 ** 20 if torch.cuda.is_available() else None
        results[model_id] = {"sec_per_epoch": round(per_epoch, 2), "fold_wall_seconds": round(wall, 1),
                             "peak_gpu_mb": None if peak is None else round(peak), "n_params": res["info"]["n_params"]}
        log.info("benchmark %s: %.2f s/epoch (train %d + val %d graphs), fold wall %.1fs, peak GPU %s MB",
                 model_id, per_epoch, len(fit), len(val), wall, results[model_id]["peak_gpu_mb"])
    runs = 3 * 9 * 5
    per_epoch_4 = (results["gnn_rgcn"]["sec_per_epoch"] + results["gnn_ggnn"]["sec_per_epoch"]
                   + 2 * results["hybrid_ggnn"]["sec_per_epoch"])
    for epochs in (20, 30, cfg["models"]["training"]["max_epochs"]):
        hours = runs * per_epoch_4 * epochs / 3600
        log.info("estimate: 3 tasks x 9 folds x 5 seeds x 4 graph models at %d epochs/run = %.1f h "
                 "(for %d graphs per task)", epochs, hours, G)
    results["estimate_hours"] = {e: round(runs * per_epoch_4 * e / 3600, 1) for e in (20, 30, 60)}
    print(json.dumps(results, indent=1))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--setting", choices=SETTINGS, default="R4")
    ap.add_argument("--task", choices=BINARY_TASKS + ["multiclass"])
    ap.add_argument("--models", default="all")
    ap.add_argument("--seeds", default=None, help="comma list, default configs/experiment.yaml protocol.seeds")
    ap.add_argument("--folds", default=None, help="comma list of test repositories (default: all folds)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--importance", action="store_true", help="permutation importance of hgb seed 0")
    ap.add_argument("--max-epochs", type=int, default=None, help="override for smoke tests (recorded)")
    ap.add_argument("--device", default=None)
    ap.add_argument("--threads", type=int, default=None,
                    help="cap OpenMP/BLAS and torch CPU threads (when other jobs share the machine)")
    ap.add_argument("--data-dir", default=None, help="default data/processed")
    ap.add_argument("--results-dir", default=None, help="default data/results")
    ap.add_argument("--benchmark", action="store_true")
    ap.add_argument("--bench-graphs", type=int, default=20000)
    ap.add_argument("--bench-epochs", type=int, default=2)
    args = ap.parse_args(argv)
    args.device = args.device or T.default_device()

    cfg = load_config("experiment")
    results_dir = Path(args.results_dir) if args.results_dir else DATA / "results"
    if args.max_epochs and results_dir.resolve() == (DATA / "results").resolve():
        ap.error("--max-epochs is for smoke tests: pass a --results-dir outside data/results so the "
                 "protocol outputs are never mixed with them")
    name = "benchmark" if args.benchmark else f"run_{args.setting}_{args.task}"
    handlers, log_path = setup_logging(results_dir, name)
    limits = None
    if args.threads:
        limits = threadpool_limits(limits=args.threads)
        torch.set_num_threads(args.threads)
    try:
        if args.benchmark:
            benchmark(args, cfg)
            return 0
        if not args.task:
            ap.error("--task is required")
        if args.task == "multiclass" and args.setting != "R4":
            ap.error("the multiclass supplement is only run in R4")
        models = expand_models(args.models, args.setting, args.task)
        seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else list(cfg["protocol"]["seeds"])
        log.info("setting %s task %s models %s seeds %s device %s (log %s)", args.setting, args.task,
                 models, seeds, args.device, log_path)
        if args.max_epochs:
            log.warning("max_epochs overridden to %d: not the configured protocol", args.max_epochs)

        ev = build_eval_set(args.task, args.setting, args.data_dir)
        paired = None
        if args.task == "add_log_post":
            ref = build_eval_set("add_log", args.setting, args.data_dir)
            check_paired_view(ev, ref)
            paired = {"task": "add_log", "eval_set_sha1": ref["eval_set_sha1"], "n_eval": len(ref["ids"])}
            del ref
        folds_cfg = task_folds(load_folds(args.data_dir), args.task)
        all_folds = loro_folds(ev, folds_cfg)
        only = set(args.folds.split(",")) if args.folds else None
        folds = [f for f in all_folds if not only or f["test_repo"] in only]
        if only and len(folds) != len(only):
            log.warning("unknown or empty folds requested: %s", sorted(only - {f["test_repo"] for f in folds}))
        for f in folds:
            log.info("fold %d %s: fit %d val %d (seed %d) test %d%s", f["fold_index"], f["test_repo"],
                     len(f["fit_idx"]), len(f["val_idx"]), f["val_seed"], len(f["test_idx"]),
                     " [low support]" if f["low_support"] else "")

        use_graphs = any(uses_graphs(m) for m in models)
        code = code_sha1()
        inputs = {"folds": folds_cfg}
        if paired:
            inputs["paired_with"] = paired
        if use_graphs:
            inputs["graph_inputs_sha1"] = graph_inputs_sha1(args.task, args.data_dir, ev["graph_pos"])
        problems = check_outputs(models, seeds, ev, folds, cfg, results_dir, args, inputs, code)
        if problems:
            for p in problems:
                log.error("conflict: %s", p)
            log.error("nothing was run. Re-run with --overwrite to recompute these outputs, or restore "
                      "the inputs / code they were produced with.")
            return 2

        graphs = graph_info = None
        if use_graphs:
            t0 = time.time()
            arrays, meta = load_graph_arrays(args.task, args.data_dir)
            graphs, graph_info = build_graphs(arrays, ev["graph_pos"], ev["y"], meta)
            del arrays
            log.info("loaded %d graphs in %.1fs: %s", len(graphs), time.time() - t0, graph_info)

        try:
            for model_id in models:
                for seed in seeds:
                    run_model_seed(model_id, seed, ev, folds, all_folds, cfg, results_dir, args, inputs, code,
                                   graphs, graph_info)
            if args.importance and args.task != "multiclass":
                run_importance(ev, folds, all_folds, cfg, results_dir, args, inputs, code)
        except RunConflict as e:
            log.error("conflict: %s (use --overwrite)", e)
            return 2
        return 0
    finally:
        if limits is not None:
            limits.restore_original_limits()
        root = logging.getLogger()
        for h in handlers:
            root.removeHandler(h)
            h.close()


if __name__ == "__main__":
    sys.exit(main())
