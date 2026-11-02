"""
Evaluation instance sets, LORO folds, grouped validation splits and tabular matrices for
the model stage.

- R4: in_R4 and features available and graph available. Every R4 model (naive, classical,
  neural, graph) uses this same set, so all comparisons are paired.
- R1 / R10: in_Rk and features available (classical and naive models only).
- Validation: 15% of the training repositories' instances, grouped by (repo, commit),
  stratified by label as far as the grouping allows. It depends only on the fold, never on
  the model or the training seed.
- add_log_post (masked post-state sensitivity view of add_log, same instances) is read from
  its own instance, feature and graph files like any binary task, and must end up with the
  add_log evaluation set and folds (check_paired_view, task_folds).
"""

import hashlib
import json
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import DATA, load_config

log = logging.getLogger(__name__)

GROUPS = ["h", "f", "m", "l", "s", "d", "x"]
FEATURE_SETS = {
    "all": ["h", "f", "m", "l", "s", "d", "x"],
    "static": ["f", "m", "l", "s", "d", "x"],
    "history": ["h"],
}
CTX_COLUMN = "d_ctx_category"
MULTICLASS_LABELS = ["NO_EVENT", "ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]


def processed_dir(data_dir=None):
    return Path(data_dir) if data_dir else DATA / "processed"


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_folds(data_dir=None):
    with open(processed_dir(data_dir) / "instances" / "folds.json", encoding="utf-8") as f:
        return json.load(f)


def task_folds(folds, task):
    """folds.json entry of a task. add_log_post has the instances of add_log (only the view
    differs), so its entry must be the add_log one; without its own entry it takes it."""
    if task in folds:
        if task == "add_log_post" and "add_log" in folds and folds[task] != folds["add_log"]:
            raise ValueError(f"folds.json: the add_log_post entry differs from the add_log one "
                             f"({folds[task]} vs {folds['add_log']}); both views must share the folds")
        return folds[task]
    if task == "add_log_post" and "add_log" in folds:
        log.warning("folds.json has no add_log_post entry: using the add_log folds (same instances)")
        return folds["add_log"]
    raise KeyError(f"folds.json has no entry for task {task}")


def ctx_categories():
    return list(load_config("perf_sensitive")["category_priority"])


def load_features(task, data_dir=None):
    """Read features/<task>.csv.

    Returns (ids, X, columns, groups, failed): X is float64 with NaN for missing values,
    d_ctx_category is one-hot encoded (one column per category, group d), and `failed`
    is the set of instance ids listed in <task>_failures.jsonl.
    """
    base = processed_dir(data_dir) / "features"
    df = pd.read_csv(base / f"{task}.csv", dtype={"instance_id": str, CTX_COLUMN: str}, low_memory=False)

    failed = set()
    fpath = base / f"{task}_failures.jsonl"
    if fpath.exists():
        for row in read_jsonl(fpath):
            failed.add(row["instance_id"])

    # the groups file must agree with the prefixes; prefixes are what we use
    gpath = base / f"{task}_groups.json"
    if gpath.exists():
        with open(gpath, encoding="utf-8") as f:
            declared = json.load(f)
        if isinstance(declared, dict):
            for col, g in declared.items():
                if isinstance(g, str) and g in GROUPS and col.split("_", 1)[0] != g and not col.startswith(CTX_COLUMN):
                    log.warning("%s: column %s declared in group %s but has another prefix", task, col, g)

    columns, groups, blocks, skipped = [], [], [], []
    for col in df.columns:
        if col == "instance_id":
            continue
        prefix = col.split("_", 1)[0]
        if prefix not in GROUPS:
            skipped.append(col)
            continue
        if col == CTX_COLUMN:
            cats = df[col].fillna("").astype(str).values
            for cat in ctx_categories():
                columns.append(f"{CTX_COLUMN}={cat}")
                groups.append("d")
                blocks.append((cats == cat).astype(np.float64))
            continue
        values = df[col]
        if values.dtype == object:
            converted = pd.to_numeric(values, errors="coerce")
            if converted.notna().sum() < values.notna().sum():
                skipped.append(col)
                continue
            values = converted
        columns.append(col)
        groups.append(prefix)
        blocks.append(values.astype(np.float64).values)
    if skipped:
        log.warning("%s: %d non-feature columns ignored: %s", task, len(skipped), skipped[:10])

    X = np.column_stack(blocks) if blocks else np.zeros((len(df), 0))
    ids = df["instance_id"].astype(str).tolist()
    return ids, X, columns, groups, failed


def load_graph_index(task, data_dir=None):
    """{instance_id: graph_pos} for graphs with at least one node."""
    path = processed_dir(data_dir) / "graphs" / f"{task}_index.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: the R4 instance set needs the graphs (stage 6)")
    meta_path = path.with_name(f"{task}_meta.json")
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        # truncated, limited or message-word builds would change the R4 instance set
        if meta.get("setting", "R4") != "R4" or meta.get("limit") is not None or meta.get("log_message_words"):
            raise ValueError(f"{meta_path}: not the primary graph build (setting={meta.get('setting')}, "
                             f"limit={meta.get('limit')}, log_message_words={meta.get('log_message_words')})")
    df = pd.read_csv(path, dtype={"instance_id": str})
    df = df[df["n_nodes"] > 0]
    return dict(zip(df["instance_id"], df["graph_pos"].astype(int)))


def multiclass_label(inst):
    lab = inst["label"]
    if isinstance(lab, str):
        return MULTICLASS_LABELS.index(lab)
    return int(lab)


def content_sha1(ids, repos, commits, y, X, columns, groups):
    """sha1 of everything a model reads from the evaluation set (ids, repos, commits, labels,
    feature values and names), so outputs can be tied to the inputs they were computed from."""
    h = hashlib.sha1()
    for part in (list(ids), [str(r) for r in repos], [str(c) for c in commits], list(columns), list(groups)):
        h.update(json.dumps(part).encode("utf-8"))
    h.update(np.ascontiguousarray(y, dtype=np.int64).tobytes())
    X = np.asarray(X, dtype=np.float64)
    h.update(np.ascontiguousarray(np.where(np.isnan(X), np.nan, X)).tobytes())   # one NaN bit pattern
    return h.hexdigest()


def build_eval_set(task, setting, data_dir=None, need_graph=None):
    """Instances evaluated for (task, setting) with their aligned feature matrix.

    need_graph defaults to True for R4 binary tasks so that all R4 models share one set.
    """
    multiclass = task == "multiclass"
    if need_graph is None:
        need_graph = setting == "R4" and not multiclass

    instances = read_jsonl(processed_dir(data_dir) / "instances" / f"{task}.jsonl")
    flag = f"in_{setting}"
    if multiclass and not any(flag in r for r in instances):
        selected = instances
    else:
        selected = [r for r in instances if r.get(flag)]

    ids, X_all, columns, groups, failed = load_features(task, data_dir)
    feat_pos = {iid: k for k, iid in enumerate(ids)}
    graph_pos = load_graph_index(task, data_dir) if need_graph else None

    keep, rows, gpos = [], [], []
    dropped = {"no_features": 0, "no_graph": 0}
    for r in selected:
        iid = r["instance_id"]
        if iid in failed or iid not in feat_pos:
            dropped["no_features"] += 1
            continue
        if graph_pos is not None and iid not in graph_pos:
            dropped["no_graph"] += 1
            continue
        keep.append(r)
        rows.append(feat_pos[iid])
        if graph_pos is not None:
            gpos.append(graph_pos[iid])

    if multiclass:
        y = np.array([multiclass_label(r) for r in keep], dtype=np.int64)
    else:
        y = np.array([int(r["label"]) for r in keep], dtype=np.int64)
    inst_ids = [r["instance_id"] for r in keep]
    repos = np.array([r["repo"] for r in keep], dtype=object)
    commits = np.array([r["commit_id"] for r in keep], dtype=object)
    X = X_all[rows] if rows else np.zeros((0, X_all.shape[1]))
    ev = {
        "task": task,
        "setting": setting,
        "ids": inst_ids,
        "repos": repos,
        "commits": commits,
        "y": y,
        "X": X,
        "columns": columns,
        "groups": groups,
        "graph_pos": np.array(gpos, dtype=np.int64) if graph_pos is not None else None,
        "n_selected": len(selected),
        "dropped": dropped,
        "eval_set_sha1": hashlib.sha1("\n".join(sorted(inst_ids)).encode("utf-8")).hexdigest(),
        "content_sha1": content_sha1(inst_ids, repos, commits, y, X, columns, groups),
    }
    log.info("%s %s: %d instances in setting, %d kept, dropped %s",
             task, setting, len(selected), len(keep), dropped)
    return ev


def check_paired_view(ev, ref):
    """Raise unless ev (add_log_post) is evaluated on the instances of ref (add_log).

    Both views must keep the same instances in the same order with the same repos, commits
    and labels: then loro_folds gives them the same fit/val/test splits and post minus pre is
    a paired difference. A feature or graph failure in one view only breaks this (one
    dropped commit reshuffles a whole validation split), so it is an error, not a warning.
    """
    a = [i.split(":", 1)[1] for i in ev["ids"]]
    b = [i.split(":", 1)[1] for i in ref["ids"]]
    if (a == b and np.array_equal(ev["y"], ref["y"]) and list(ev["repos"]) == list(ref["repos"])
            and list(ev["commits"]) == list(ref["commits"])):
        return
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    raise ValueError(
        f"{ev['task']} {ev['setting']} is not evaluated on the {ref['task']} instances: "
        f"{len(only_a)} only in {ev['task']} {only_a[:3]}, {len(only_b)} only in {ref['task']} {only_b[:3]} "
        f"(dropped {ev['dropped']} vs {ref['dropped']})"
        + ("" if only_a or only_b else "; same ids but another order, repo, commit or label")
        + ". Fix the view-specific failures (features/<task>_failures.jsonl, graphs/<task>_index.csv)")


def validation_split(train_idx, repos, commits, y, frac, seed, max_tries=100):
    """Grouped (repo, commit) validation split of the training indices.

    Groups are shuffled with the seed; groups containing a positive are taken first until
    the validation set holds `frac` of the positives, then positive-free groups until it
    holds `frac` of the instances. If the result lacks a positive or a negative the next
    seed is tried. Returns (val_idx sorted, seed used).
    """
    train_idx = np.asarray(train_idx)
    groups = {}
    for i in train_idx:
        groups.setdefault((repos[i], commits[i]), []).append(i)
    keys = sorted(groups)
    pos_in = {k: int((y[groups[k]] > 0).sum()) for k in keys}
    n_total = len(train_idx)
    n_pos_total = int((y[train_idx] > 0).sum())

    for attempt in range(max_tries):
        s = seed + attempt
        rng = np.random.RandomState(s)
        order = [keys[k] for k in rng.permutation(len(keys))]
        val = []
        n_pos = 0
        for key in order:
            if pos_in[key] == 0:
                continue
            if n_pos >= frac * n_pos_total:
                break
            val.extend(groups[key])
            n_pos += pos_in[key]
        for key in order:
            if pos_in[key] > 0:
                continue
            if len(val) >= frac * n_total:
                break
            val.extend(groups[key])
        val = np.array(sorted(val), dtype=np.int64)
        yv = y[val] > 0
        if len(val) and yv.any() and (~yv).any():
            return val, s
    raise RuntimeError("could not draw a validation split with both classes")


def loro_folds(ev, folds_cfg, val_fraction=None, base_seed=None, only=None):
    """Leave-one-repository-out folds over folds_cfg["test_repos"].

    Training = every other repository of the evaluation set (including repositories below
    the test threshold). folds.json counts positives before view/feature/graph failures, so
    the test threshold and the low-support flag are re-checked on the evaluated instances;
    a repository that falls below the threshold is not tested but still trains the others.
    `only` restricts to some test repos but keeps the fold index of the full list, so the
    validation split of a fold never depends on the selection.
    """
    exp = load_config("experiment")
    proto = exp["protocol"]
    if val_fraction is None:
        val_fraction = proto["val_fraction"]
    if base_seed is None:
        base_seed = exp["sampling"]["seed"]
    repos, commits, y = ev["repos"], ev["commits"], ev["y"]
    low = set(folds_cfg.get("low_support", []))
    folds = []
    for k, repo in enumerate(folds_cfg["test_repos"]):
        if only and repo not in only:
            continue
        test = np.where(repos == repo)[0]
        train = np.where(repos != repo)[0]
        n_pos = int((y[test] > 0).sum())
        if n_pos < proto["min_test_positives"] or len(train) == 0:
            log.warning("fold %s skipped: %d evaluated positives (< %d) or no training data",
                        repo, n_pos, proto["min_test_positives"])
            continue
        val, used = validation_split(train, repos, commits, y, val_fraction, base_seed + k)
        fit = np.setdiff1d(train, val)
        folds.append({
            "test_repo": repo,
            "fold_index": k,
            "fit_idx": fit,
            "val_idx": val,
            "test_idx": test,
            "val_seed": used,
            "low_support": repo in low or n_pos < proto["low_support_positives"],
        })
    return folds


def select_columns(groups, feature_set):
    wanted = FEATURE_SETS[feature_set]
    return [j for j, g in enumerate(groups) if g in wanted]


def nonbinary_columns(X, fit_idx):
    """Columns with more than two distinct non-missing values in the training part."""
    X = np.asarray(X, dtype=np.float64)
    out = np.zeros(X.shape[1], dtype=bool)
    for j in range(X.shape[1]):
        v = X[fit_idx, j]
        out[j] = len(np.unique(v[~np.isnan(v)])) > 2
    return out


def prepare_tabular(X, fit_idx, impute=True, scale=True, log1p=False):
    """Train-part imputation (median) and standardisation applied to all rows.

    Columns that are entirely missing in the training part are filled with 0.
    log1p=True (post-hoc variants only): the non-binary columns of the training part are first
    mapped to sign(x) * log1p(|x|) in every row; missing values stay missing until imputation.
    """
    X = np.array(X, dtype=np.float64, copy=True)
    if log1p:
        cols = nonbinary_columns(X, fit_idx)
        X[:, cols] = np.sign(X[:, cols]) * np.log1p(np.abs(X[:, cols]))
    if impute:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(X[fit_idx], axis=0) if len(fit_idx) else np.zeros(X.shape[1])
        med = np.where(np.isnan(med), 0.0, med)
        r, c = np.where(np.isnan(X))
        X[r, c] = med[c]
    if scale:
        mu = X[fit_idx].mean(axis=0)
        sd = X[fit_idx].std(axis=0)
        sd[~(sd > 0)] = 1.0
        X = (X - mu) / sd
    return X
