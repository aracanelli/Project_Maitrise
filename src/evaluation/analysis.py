"""
Stage-8 analysis: load predictions and their context, compute every evaluation table
(inputs are the outputs of stages 3 to 7).

One TaskData per (setting, task) holds the predictions of all models aligned on the same
instances, the instance context (repository, commit, engine, size, ecosystem, d_* columns)
and one set of commit-cluster bootstrap resamples. Point metrics and bootstrap matrices are
cached per (model, subset key), so a subset used by several tables (and paired tests between
models) is computed once on identical resamples.

All models of a task are evaluated on the same instances: the intersection of the
instances predicted by every model that covers at least 99% of the union. A model below that,
or one whose sidecar names another evaluation set (eval_set_sha1), is kept, flagged as
partial (marked in every table and the report), and its comparisons use the instances both
models predicted.

Two sets of resamples are drawn from the same clusters: B (CIs of single metrics) and
B_test (paired tests, ablation, difference-in-differences; evaluation.bootstrap_samples_tests).
A resample without a positive in the instances a metric needs is undefined; every CI and test
reports how many resamples it used (b_used). A macro value needs a positive in every repository
of the macro (macro_boot). Tests on a part below the support floor (below_floor: < 10 positives
or positives from at most 2 commits) are descriptive only: no p, not in a Holm family.
The post-hoc log1p models (labels.POSTHOC_MODELS) are never loaded with the primary models;
they get their own TaskData on the primary instances (ref=), so they cannot change the
evaluated instances or resamples of the primary analysis.
"""

import json
import os
import re
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import DATA, load_config, corpus_repos
from src.evaluation import stats as st
from src.evaluation.labels import (MODEL_ORDER, LEVELS, EVENT_LABELS, POSTHOC_MODELS, SUBSYSTEM_MARKERS,
                                   FEATURE_GROUPS, group_name)
from src.evaluation.metrics import binary_metrics, multiclass_metrics, confusion_metrics, BINARY_METRICS

ABLATION = [("full", "hybrid_ggnn"), ("no_history", "hybrid_ggnn_nohist"), ("no_graph", "mlp_full"),
            ("history_only", "mlp_hist"), ("graph_only", "gnn_ggnn")]
PAIRS = [("hybrid_ggnn", "hgb"), ("hybrid_ggnn", "rf"), ("hybrid_ggnn", "lr"), ("hybrid_ggnn", "mlp_full"),
         ("hybrid_ggnn", "naive_prior"), ("hybrid_ggnn", "naive_size"), ("hybrid_ggnn", "naive_rule"),
         ("gnn_ggnn", "hgb"), ("gnn_rgcn", "hgb"), ("gnn_ggnn", "gnn_rgcn")]
REFERENCE = "hgb"
CLASSICAL = ["lr", "rf", "hgb"]
FULL_MODEL = "hybrid_ggnn"
SENSITIVITY_MODELS = ["naive_prior", "naive_size", "naive_rule", "lr", "rf", "hgb"]
CURVE_MODELS = ["naive_rule", "lr", "hgb", "gnn_ggnn", "hybrid_ggnn"]
ERROR_MODELS = ["naive_rule", "lr", "rf", "hgb", "gnn_ggnn", "hybrid_ggnn"]
GROUP_MODELS = ["naive_prior", "hgb", "gnn_ggnn", "hybrid_ggnn"]
POSTHOC_PAIRS = [("lr_log1p", "lr"), ("mlp_full_log1p", "mlp_full"), ("hybrid_ggnn_log1p", "hybrid_ggnn"),
                 ("hybrid_ggnn_log1p", "hgb")]
# fallback when folds.json has no few_commit_folds: same rule as the dataset stage
# (src/dataset/folds.py), the test positives come from at most FEW_COMMITS distinct commits
FEW_COMMITS = 2
MULTICLASS = ["NO_EVENT", "ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]
CONTEXT_CATEGORIES = ["frame_update", "loop", "subsystem", "general"]
COVERAGE_MIN = 0.99
# numpy releases the GIL in the gathers/reductions of the bootstrap, so threads scale
BOOT_THREADS = max(1, min(8, (os.cpu_count() or 2) // 2))

NOTICES = []


def notice(msg):
    print(f"[evaluate] {msg}", flush=True)
    NOTICES.append(msg)


def paths(data_dir=DATA):
    d = Path(data_dir)
    return {
        "data": d,
        "predictions": d / "results" / "predictions",
        "instances": d / "processed" / "instances",
        "features": d / "processed" / "features",
        "graphs": d / "processed" / "graphs",
        "mining": d / "interim" / "mining",
        "rq1": d / "results" / "rq1",
        "events": d / "processed" / "events_master.jsonl",
        "results": d / "results",
    }


def low_support_threshold():
    return load_config("experiment")["protocol"]["low_support_positives"]


def min_test_positives():
    return load_config("experiment")["protocol"]["min_test_positives"]


def below_floor(n_pos, n_commits):
    """Support floor of a test: fewer positives than a test fold needs (protocol.min_test_positives)
    or positives from at most FEW_COMMITS commits. Such a comparison is reported without a p-value
    (descriptive only) and stays out of its Holm family."""
    return n_pos < min_test_positives() or n_commits <= FEW_COMMITS


def part_support(td, mask, label=1):
    """(instances of class `label` in mask, distinct commits among them)."""
    sel = np.asarray(mask, dtype=bool) & (td.y == label)
    return int(sel.sum()), int(td.meta.loc[sel, "commit_id"].nunique())


def bootstrap_sizes(cfg=None):
    """(B for confidence intervals, B for tests, resampling seed) from configs/experiment.yaml;
    bootstrap_samples_tests defaults to 10000 and bootstrap_seed to 42 (load_task's default)."""
    ev = (cfg or load_config("experiment"))["evaluation"]
    return (int(ev["bootstrap_samples"]), int(ev.get("bootstrap_samples_tests", 10000)),
            int(ev.get("bootstrap_seed", 42)))


def model_sort_key(m):
    return (MODEL_ORDER.index(m) if m in MODEL_ORDER else len(MODEL_ORDER), m)


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def corpus_frame():
    return pd.DataFrame([{"repo": r["name"], "engine": r.get("engine"), "size": r.get("size"),
                          "selection": r.get("selection"), "modeling": bool(r.get("modeling"))}
                         for r in corpus_repos()])


# inputs

def load_folds(p):
    f = p["instances"] / "folds.json"
    if not f.exists():
        return {}
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def load_instances(p, task):
    f = p["instances"] / f"{task}.jsonl"
    if not f.exists():
        return None
    return read_jsonl(f)


def load_context(p, task):
    """instance_id plus the d_* context columns (and framework one-hots for the ecosystem fallback)."""
    f = p["features"] / f"{task}.csv"
    if not f.exists():
        return None
    fw = re.compile(r"^[fls]_(framework|fw)_")
    return pd.read_csv(f, usecols=lambda c: c == "instance_id" or c.startswith("d_") or bool(fw.match(c)),
                       dtype={"instance_id": str, "d_ctx_category": str})


def load_events(p):
    if p["events"].exists():
        return pd.DataFrame(read_jsonl(p["events"]))
    csv = p["events"].with_suffix(".csv")
    if csv.exists():
        return pd.read_csv(csv)
    # before stage 4 has run, the master table is the concatenation of the mining event files
    rows = []
    for repo in mining_repos(p):
        f = p["mining"] / repo / "events.jsonl"
        if f.exists():
            rows += read_jsonl(f)
    if rows:
        notice("events_master.jsonl not found; RQ1 event tables built from data/interim/mining/*/events.jsonl")
        return pd.DataFrame(rows)
    return None


def read_prediction_file(path):
    df = pd.read_csv(path, dtype={"instance_id": str, "test_repo": str})
    missing = {"instance_id", "test_repo", "y_true", "score", "y_pred"} - set(df.columns)
    if missing:
        notice(f"{path}: missing columns {sorted(missing)}, file ignored")
        return None
    if df["instance_id"].duplicated().any():
        notice(f"{path}: {int(df['instance_id'].duplicated().sum())} duplicated instance ids, first kept")
        df = df.drop_duplicates("instance_id")
    return df


SIDECAR_KEYS = ("eval_set_sha1", "run_key", "code_sha1", "complete")


def load_predictions(p, setting, task, models=None, exclude=()):
    """{model_id: [(seed, DataFrame, sidecar), ...]} for
    data/results/predictions/<setting>/<task>/<model>/seed<k>.csv; sidecar holds SIDECAR_KEYS of seed<k>.json.

    models: only these ids; otherwise every model directory except `exclude`."""
    base = p["predictions"] / setting / task
    out = {}
    if not base.exists():
        return out
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        if models is not None and d.name not in models:
            continue
        if models is None and d.name in exclude:
            continue
        seeds = []
        for f in d.glob("seed*.csv"):
            m = re.fullmatch(r"seed(\d+)\.csv", f.name)
            if m:
                seeds.append((int(m.group(1)), f))
        runs = []
        for s, f in sorted(seeds):
            df = read_prediction_file(f)
            side = {}
            sf = f.with_suffix(".json")
            if sf.exists():
                try:
                    with open(sf, encoding="utf-8") as fh:
                        full = json.load(fh)
                    side = {k: full.get(k) for k in SIDECAR_KEYS}
                except (OSError, ValueError):
                    notice(f"{sf}: unreadable sidecar")
            else:
                notice(f"{f}: no sidecar, evaluation set and code version cannot be checked")
            if side.get("complete") is False:
                notice(f"{f}: sidecar says the run is incomplete (folds missing)")
            if df is not None:
                runs.append((s, df, side))
        if runs:
            out[d.name] = runs
    return dict(sorted(out.items(), key=lambda kv: model_sort_key(kv[0])))


def check_sidecars(setting, task, preds):
    """eval_set_sha1 per model and the models whose predictions come from another evaluation set.

    All models of a (setting, task) are trained on one evaluation set (src/models/data.py),
    so the reference is the eval_set_sha1 shared by most models. A model run on another set
    is likely stale (an older dataset or feature build with the same deterministic instance
    ids): it does not define the evaluated instances and is flagged partial. Without a strict
    majority the current set cannot be told apart, and every model with a sidecar is flagged.
    """
    shas = {}
    for m, runs in preds.items():
        vals = sorted({side.get("eval_set_sha1") for _, _, side in runs} - {None})
        codes = {side.get("code_sha1") for _, _, side in runs} - {None}
        keys = {side.get("run_key") for _, _, side in runs} - {None}
        if len(vals) > 1:
            notice(f"{setting}/{task}/{m}: seeds come from {len(vals)} different evaluation sets (eval_set_sha1)")
        if len(codes) > 1:
            notice(f"{setting}/{task}/{m}: seeds were trained with {len(codes)} different code versions (code_sha1)")
        if len(keys) > 1:
            # run_key covers the model configuration and protocol, not the seed
            notice(f"{setting}/{task}/{m}: seeds were trained with {len(keys)} different configurations (run_key)")
        shas[m] = vals
    counts = {}
    for m in preds:
        for v in shas[m]:
            counts[v] = counts.get(v, 0) + 1
    if len(counts) <= 1:
        return shas, set()
    top = max(counts.values())
    if sum(c == top for c in counts.values()) > 1:
        stale = {m for m in preds if shas[m]}
        notice(f"{setting}/{task}: no majority evaluation set ("
               + "; ".join(f"{m} {','.join(v[:12] for v in shas[m])}" for m in preds if shas[m])
               + "); every model evaluated as partial")
        return shas, stale
    ref = max(counts, key=lambda v: counts[v])
    stale = {m for m in preds if shas[m] and shas[m] != [ref]}
    for m in sorted(stale, key=model_sort_key):
        notice(f"{setting}/{task}/{m}: eval_set_sha1 {', '.join(v[:12] for v in shas[m])} differs from "
               f"{ref[:12]} (used by {counts[ref]} of {len(preds)} models); possibly stale predictions, "
               "evaluated as partial")
    return shas, stale


def _flex_col(df, names):
    for n in names:
        if n in df.columns:
            return n
    return None


def snapshot_frameworks(p):
    """Dominant formal framework per repository from the RQ1 snapshot CSVs, if they provide it."""
    d = p["rq1"]
    if not d.exists():
        return {}
    files = sorted(d.glob("*.csv"))
    files.sort(key=lambda f: f.name != "corpus_snapshot.csv")
    repos = set(corpus_frame()["repo"])
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        rc = _flex_col(df, ["repo", "repository", "name"])
        if rc is None:
            continue
        df = df[df[rc].isin(repos)]
        dom = _flex_col(df, ["dominant_framework", "ecosystem", "main_framework", "framework_dominant"])
        if dom is not None:
            return {str(r): str(v) for r, v in zip(df[rc], df[dom]) if isinstance(v, str) and v}
        fc = _flex_col(df, ["framework"])
        cc = _flex_col(df, ["n", "count", "n_statements", "statements"])
        if fc is not None and cc is not None:
            if "logging_style" in df:
                df = df[df["logging_style"] == "formal"]
            g = df.groupby([rc, fc])[cc].sum().reset_index()
            g = g.sort_values([rc, cc, fc], ascending=[True, False, True])
            return {str(r): str(v) for r, v in g.groupby(rc)[fc].first().items()}
    return {}


def repo_ecosystems(p, events=None, tasks=None):
    """repo -> dominant formal logging framework (RQ1 snapshot, else events, else feature one-hots)."""
    eco = snapshot_frameworks(p)
    if eco:
        return eco, "rq1 snapshot"
    if events is not None and len(events) and "framework" in events:
        ev = events[events["logging_style"] == "formal"] if "logging_style" in events else events
        if len(ev):
            g = ev.groupby(["repo", "framework"]).size().reset_index(name="n")
            g = g.sort_values(["repo", "n", "framework"], ascending=[True, False, True])
            return {str(r): str(v) for r, v in g.groupby("repo")["framework"].first().items()}, "events master (formal events)"
    totals = {}
    fw = re.compile(r"^[fls]_(?:framework|fw)_([a-z0-9_]+)$")
    for task in tasks or []:
        ctx = load_context(p, task)
        if ctx is None:
            continue
        cols = [c for c in ctx.columns if fw.match(c)]
        if not cols:
            continue
        ctx["repo"] = ctx["instance_id"].str.split(":").str[1]
        for c in cols:
            name = fw.match(c).group(1)
            for r, v in ctx.groupby("repo")[c].sum().items():
                totals.setdefault(r, {}).setdefault(name, 0.0)
                totals[r][name] += float(v)
    if totals:
        return {r: sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for r, d in totals.items()}, "feature columns"
    return {}, "unavailable"


# task data

@dataclass
class TaskData:
    setting: str
    task: str
    ids: np.ndarray
    y: np.ndarray
    meta: pd.DataFrame
    models: dict
    rows: np.ndarray
    CT: np.ndarray
    CT_test: np.ndarray = None
    clusters: np.ndarray = None
    instances: dict = field(default_factory=dict)
    point: dict = field(default_factory=dict)
    boot: dict = field(default_factory=dict)
    boot_test: dict = field(default_factory=dict)
    n_union: int = 0
    test_repos: list = field(default_factory=list)

    def __post_init__(self):
        if self.CT_test is None:
            self.CT_test = self.CT


def load_task(setting, task, p, B, seed=42, models=None, ecosystems=None, with_context=True, B_test=None,
              ref=None, exclude=tuple(POSTHOC_MODELS)):
    """TaskData of (setting, task). ref: another TaskData whose instances are reused as they are
    (same ids, labels and resamples; models covering < 99% of them are partial)."""
    preds = load_predictions(p, setting, task, models, exclude)
    if not preds:
        notice(f"{setting}/{task}: no predictions found, task skipped")
        return None

    shas, stale = check_sidecars(setting, task, preds)
    cover = {}
    union = set()
    for m, runs in preds.items():
        ids = None
        for s, df, _ in runs:
            ok = set(df.loc[np.isfinite(df["score"].astype(float)) & df["y_pred"].notna(), "instance_id"])
            ids = ok if ids is None else ids & ok
        cover[m] = ids
        union |= ids
    if ref is not None:
        universe = set(ref.ids)
        complete = [m for m in preds if len(cover[m] & universe) >= COVERAGE_MIN * len(universe) and m not in stale]
        for m in preds:
            if m not in complete and m not in stale:
                notice(f"{setting}/{task}/{m}: predictions cover {len(cover[m] & universe)}/{len(universe)} of the "
                       "primary instances, evaluated as partial")
    else:
        complete = [m for m in preds if len(cover[m]) >= COVERAGE_MIN * len(union) and m not in stale]
        universe = set.intersection(*[cover[m] for m in complete]) if complete else set(union)
        for m in preds:
            if m not in complete and m not in stale:
                notice(f"{setting}/{task}/{m}: predictions cover {len(cover[m])}/{len(union)} instances, evaluated as partial")
        if len(universe) < len(union):
            notice(f"{setting}/{task}: {len(union) - len(universe)} instances not predicted by every complete model were left out")

    ids = np.array(sorted(universe), dtype=object)
    n = len(ids)
    pos = pd.Series(np.arange(n), index=ids)

    y = np.full(n, -1, dtype=np.int8)
    test_repo = np.empty(n, dtype=object)
    if ref is not None:
        y[:] = ref.y
        test_repo[:] = ref.meta["test_repo"].to_numpy()
    mdata = {}
    for m, runs in preds.items():
        S = len(runs)
        score = np.full((S, n), np.nan)
        pred = np.zeros((S, n), dtype=np.int8)
        for j, (s, df, _) in enumerate(runs):
            d = df[df["instance_id"].isin(universe) & np.isfinite(df["score"].astype(float)) & df["y_pred"].notna()]
            idx = pos[d["instance_id"]].to_numpy()
            score[j, idx] = d["score"].astype(float).to_numpy()
            pred[j, idx] = d["y_pred"].astype(int).to_numpy()
            yt = d["y_true"].astype(int).to_numpy()
            known = y[idx] >= 0
            if (y[idx][known] != yt[known]).any():
                notice(f"{setting}/{task}/{m}/seed{s}: y_true disagrees with other models on "
                       f"{int((y[idx][known] != yt[known]).sum())} instances (first value kept)")
            fresh = idx[~known]
            y[fresh] = yt[~known]
            test_repo[fresh] = d["test_repo"].to_numpy()[~known]
        mdata[m] = {"seeds": [s for s, _, _ in runs], "score": score, "pred": pred,
                    "cover": np.isfinite(score).all(axis=0), "partial": m not in complete,
                    "eval_set_sha1": ";".join(shas[m]), "stale": m in stale}

    meta = pd.DataFrame({"instance_id": ids, "test_repo": test_repo, "y": y})
    inst_rows = load_instances(p, task)
    instances = {}
    if inst_rows is not None:
        instances = {r["instance_id"]: r for r in inst_rows if r["instance_id"] in universe}
        keep = ["instance_id", "repo", "commit_id", "pre_path", "post_path", "class_path", "method_name",
                "label", "anchor_level", "neg_provenance"]
        idf = pd.DataFrame([{k: r.get(k) for k in keep} for r in instances.values()], columns=keep)
        dup = len(inst_rows) - len({r["instance_id"] for r in inst_rows})
        if dup:
            notice(f"{task}: instances/{task}.jsonl has {dup} duplicated instance ids (last kept)")
        meta = meta.merge(idf, on="instance_id", how="left")
        missing = int(meta["repo"].isna().sum())
        if missing:
            notice(f"{setting}/{task}: {missing} predicted instances are not in instances/{task}.jsonl")
        bad = meta["label"].notna() & (meta["label"].fillna(-1).astype(int) != meta["y"])
        if bad.any():
            notice(f"{setting}/{task}: y_true differs from the instance label for {int(bad.sum())} instances")
    else:
        notice(f"{task}: instances/{task}.jsonl not found, repo and commit taken from the instance ids")
        for c in ["repo", "commit_id", "pre_path", "post_path", "class_path", "method_name", "label", "anchor_level"]:
            meta[c] = None
    parts = meta["instance_id"].str.split(":")
    meta["repo"] = meta["repo"].fillna(meta["test_repo"])
    meta["commit_id"] = meta["commit_id"].fillna(parts.str[2])
    if (meta["repo"] != meta["test_repo"]).any():
        notice(f"{setting}/{task}: {int((meta['repo'] != meta['test_repo']).sum())} instances have test_repo != repo")

    corpus = corpus_frame().set_index("repo")
    meta["engine"] = meta["repo"].map(corpus["engine"]).fillna("unknown")
    meta["size"] = meta["repo"].map(corpus["size"]).fillna("unknown")
    meta["ecosystem"] = meta["repo"].map(ecosystems or {}).fillna("unknown")

    if with_context:
        ctx = load_context(p, task)
        if ctx is None:
            notice(f"{task}: features/{task}.csv not found, context tables (RQ4, categories) skipped")
        else:
            dcols = [c for c in ctx.columns if c.startswith("d_")]
            if ctx["instance_id"].duplicated().any():
                notice(f"{task}: features/{task}.csv has duplicated instance ids (first kept)")
                ctx = ctx.drop_duplicates("instance_id")
            meta = meta.merge(ctx[["instance_id"] + dcols], on="instance_id", how="left")
            if "d_is_perf_sensitive" in meta:
                v = meta["d_is_perf_sensitive"]
                meta["perf_part"] = np.where(v.isna(), None, np.where(v.fillna(0).astype(float) > 0, "subset", "complement"))
                if v.isna().any():
                    notice(f"{setting}/{task}: {int(v.isna().sum())} instances without context features")
            if "d_ctx_category" in meta:
                # stricter subset (sensitivity): frame_update methods only, complement = all others
                c = meta["d_ctx_category"]
                meta["frame_part"] = np.where(c.isna(), None, np.where(c == "frame_update", "subset", "complement"))

    assert len(meta) == n and (meta["instance_id"].to_numpy() == ids).all()

    # commit clusters, repositories as strata
    # (pandas hashing truncates strings at NUL, so the separator must be a printable character)
    key = meta["repo"].astype(str) + "|" + meta["commit_id"].astype(str)
    rows, uniq = pd.factorize(key, sort=True)
    strata = pd.Series(uniq).str.split("|", regex=False).str[0].to_numpy()
    CT = st.resample_counts(strata, B, seed)
    CT_test = st.resample_counts(strata, B_test, seed) if B_test and B_test != B else CT

    return TaskData(setting=setting, task=task, ids=ids, y=y, meta=meta, models=mdata,
                    rows=rows.astype(np.int64), CT=CT, CT_test=CT_test, clusters=np.asarray(uniq, dtype=object),
                    instances=instances, n_union=len(union),
                    test_repos=sorted(meta["test_repo"].dropna().unique().tolist()))


def all_mask(td):
    return np.ones(len(td.ids), dtype=bool)


def masks_by(td, column, prefix=None, values=None):
    out = {}
    if column not in td.meta:
        return out
    col = td.meta[column]
    if values is None:
        values = sorted(col.dropna().unique().tolist(), key=str)
    for v in values:
        out[f"{prefix or column}={v}"] = (col == v).to_numpy()
    return out


CI_METRICS = ["pr_auc", "f1", "precision", "recall"]


def _boot_job(CT, y, rows, score, pred, full):
    pr = st.boot_average_precision(CT, rows, st.prepare_ranking(y, score))
    cm = confusion_metrics(*st.boot_confusion(CT, rows, y, pred))
    out = {"pr_auc": pr, "f1": cm["f1"]}
    if full:
        out["precision"], out["recall"] = cm["precision"], cm["recall"]
    return out


def _resamples(td, kind):
    """(CT, cache, full) of the CI ('ci') or test ('test') resamples. With B_test == B the
    test kind shares the CI cache."""
    if kind == "test" and td.CT_test is not td.CT:
        return td.CT_test, td.boot_test, False
    return td.CT, td.boot, True


def ensure(td, masks, models=None, kind="ci"):
    """Fill the point/bootstrap caches for every (model, key); seeds run in a thread pool.

    kind 'ci' keeps PR-AUC, F1, precision and recall on the B resamples, kind 'test' PR-AUC
    and F1 on the B_test resamples; both keep the resampled prevalence ('prev')."""
    models = list(td.models) if models is None else models
    CT, cache, full = _resamples(td, kind)
    names = CI_METRICS if full else ["pr_auc", "f1"]
    jobs = []
    for key, mask in masks.items():
        for m in models:
            md = td.models[m]
            idx = np.flatnonzero(mask & md["cover"])
            y = td.y[idx]
            if (m, key) not in td.point:
                pts = [binary_metrics(y, md["score"][j, idx], md["pred"][j, idx]) for j in range(len(md["seeds"]))]
                td.point[(m, key)] = pd.DataFrame(pts, index=md["seeds"])
            if (m, key) in cache:
                continue
            S, B = len(md["seeds"]), CT.shape[1]
            cache[(m, key)] = {k: np.full((B, S), np.nan) for k in names}
            cache[(m, key)]["prev"] = st.boot_prevalence(CT, td.rows[idx], y)
            jobs += [(m, key, idx, j) for j in range(S)]
    if not jobs:
        return

    def run(job):
        m, _, idx, j = job
        md = td.models[m]
        return _boot_job(CT, td.y[idx], td.rows[idx], md["score"][j, idx], md["pred"][j, idx], full)

    with ThreadPoolExecutor(BOOT_THREADS) as ex:
        results = list(ex.map(run, jobs))
    for (m, key, idx, j), res in zip(jobs, results):
        for k, v in res.items():
            cache[(m, key)][k][:, j] = v


def boot_of(td, m, key, kind="ci"):
    return _resamples(td, kind)[1][(m, key)]


def lift_points(pt):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (pt["pr_auc"] / pt["prevalence"]).to_numpy(dtype=float)


def lift_boot(bt):
    """Resampled lift (PR-AUC / prevalence of the same resample), B x S."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return bt["pr_auc"] / bt["prev"][:, None]


def summary_row(td, m, key):
    pt = td.point[(m, key)]
    bt = td.boot[(m, key)]
    row = {"n": int(pt["n"].iloc[0]), "n_pos": int(pt["n_pos"].iloc[0]),
           "prevalence": float(pt["prevalence"].iloc[0]), "n_seeds": len(pt)}
    for metric in BINARY_METRICS:
        row[f"{metric}_mean"] = float(pt[metric].mean())
        row[f"{metric}_sd"] = float(pt[metric].std(ddof=1)) if len(pt) > 1 else np.nan
    for metric in CI_METRICS:
        row[f"{metric}_ci_lo"], row[f"{metric}_ci_hi"] = st.percentile_ci(st.seed_mean(bt[metric]))
    lift = lift_points(pt)
    row["pr_auc_lift_mean"] = float(np.mean(lift)) if len(lift) else np.nan
    row["pr_auc_lift_sd"] = float(np.std(lift, ddof=1)) if len(lift) > 1 else np.nan
    row["pr_auc_lift_ci_lo"], row["pr_auc_lift_ci_hi"] = st.percentile_ci(st.seed_mean(lift_boot(bt)))
    # resamples with a positive (a defined PR-AUC); the others cannot enter the CI
    row["b_used"] = int(np.isfinite(st.seed_mean(bt["pr_auc"])).sum())
    row["low_support"] = row["n_pos"] < low_support_threshold()
    row["partial"] = bool(td.models[m]["partial"])
    return row


def pair_arrays(td, a, b, key, mask, kind="test"):
    """Point and bootstrap caches of models a and b on the instances both predicted."""
    joint = td.models[a]["cover"] & td.models[b]["cover"]
    k = key if joint.all() else f"{key}|{a}&{b}"
    ensure(td, {k: mask & joint}, [a, b], kind)
    return td.point[(a, k)], td.point[(b, k)], boot_of(td, a, k, kind), boot_of(td, b, k, kind)


def _test_values(pt, bt, metric):
    """Per-seed points and B x S resampled values of a metric ('pr_auc_lift' = PR-AUC / prevalence)."""
    if metric == "pr_auc_lift":
        return lift_points(pt), lift_boot(bt)
    return pt[metric].to_numpy(dtype=float), bt[metric]


def paired(td, a, b, key, mask, metric, kind="test"):
    pa, pb, ba, bb = pair_arrays(td, a, b, key, mask, kind)
    va, wa = _test_values(pa, ba, metric)
    vb, wb = _test_values(pb, bb, metric)
    res = st.paired_test(wa, wb, va, vb)
    res["n"] = int(pa["n"].iloc[0])
    res["n_pos"] = int(pa["n_pos"].iloc[0])
    return res


def macro_boot(values, prevs):
    """Macro (mean over repositories) of a metric in every resample, B x S.

    values: one B x S array per repository, prevs: the resampled prevalence of each. A resample
    in which some repository has no positive is undefined (NaN): averaging over the remaining
    repositories would estimate another quantity (a mean over fewer folds). Undefined resamples
    are left out of CIs and tests and counted in b_used."""
    ok = np.all(np.stack(prevs) > 0, axis=0)
    out = np.mean(np.stack(values), axis=0)
    out[~ok] = np.nan
    return out


def macro_paired(td, a, b, metric="pr_auc", kind="test", exclude=()):
    """Paired bootstrap of the macro (mean over test repositories) difference a - b.

    Repositories: those where both models have evaluated positives (minus `exclude`). Per
    resample: per-seed metric of each repository, mean over repositories (macro_boot), mean over seeds."""
    pts_a, pts_b, boots_a, boots_b, prevs = [], [], [], [], []
    for k, mask in repo_masks(td).items():
        if k.split("=", 1)[1] in exclude:
            continue
        pa, pb, ba, bb = pair_arrays(td, a, b, k, mask, kind)
        if pa["n_pos"].iloc[0] == 0:
            continue
        pts_a.append(pa[metric].to_numpy(dtype=float))
        pts_b.append(pb[metric].to_numpy(dtype=float))
        boots_a.append(ba[metric])
        boots_b.append(bb[metric])
        prevs.append(ba["prev"])
    if not pts_a:
        return {"delta": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "p": np.nan, "p_mcse": np.nan, "b_used": 0,
                "n_repos": 0}
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        point = np.nanmean(np.nanmean(np.stack(pts_a), axis=0)) - np.nanmean(np.nanmean(np.stack(pts_b), axis=0))
        da = st.seed_mean(macro_boot(boots_a, prevs))
        db = st.seed_mean(macro_boot(boots_b, prevs))
    res = st.delta_test(point, da - db)
    res["n_repos"] = len(pts_a)
    return res


# RQ2/RQ3 tables

def table_overall_pooled(tds, models=None):
    rows = []
    for task, td in tds.items():
        ms = [m for m in td.models if models is None or m in models]
        ensure(td, {"all": all_mask(td)}, ms)
        for m in ms:
            n_repos = td.meta.loc[td.models[m]["cover"], "test_repo"].nunique()
            rows.append({"setting": td.setting, "task": task, "model": m, "n_test_repos": int(n_repos),
                         **summary_row(td, m, "all")})
    return pd.DataFrame(rows)


def repo_masks(td):
    return masks_by(td, "test_repo", "repo", td.test_repos)


def table_overall_macro(tds, exclude=None, models=None):
    """Macro average over test repositories; exclude = {task: [repos]} leaves those folds out.

    CIs follow macro_boot: a resample counts only when every repository of the macro has a
    positive in it (b_used of the B resamples)."""
    exclude = exclude or {}
    rows = []
    for task, td in tds.items():
        dropped = [r for r in exclude.get(task, []) if r in td.test_repos]
        rm = {k: v for k, v in repo_masks(td).items() if k.split("=", 1)[1] not in dropped}
        if not rm:
            continue
        ms = [m for m in td.models if models is None or m in models]
        ensure(td, rm, ms)
        for m in ms:
            # a partial model missing a fold is averaged over the repositories it was evaluated on
            keys = [k for k in rm if td.point[(m, k)]["n_pos"].iloc[0] > 0]
            pts = [td.point[(m, k)] for k in keys]
            row = {"setting": td.setting, "task": task, "model": m, "n_test_repos": len(keys),
                   "n": int(sum(p_["n"].iloc[0] for p_ in pts)), "n_pos": int(sum(p_["n_pos"].iloc[0] for p_ in pts)),
                   "n_seeds": len(td.models[m]["seeds"]), "folds_excluded": ";".join(dropped)}
            for metric in BINARY_METRICS:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    per_seed = (np.nanmean(np.stack([p_[metric].to_numpy() for p_ in pts]), axis=0) if pts
                                else np.full(len(td.models[m]["seeds"]), np.nan))
                row[f"{metric}_mean"] = float(np.mean(per_seed))
                row[f"{metric}_sd"] = float(np.std(per_seed, ddof=1)) if len(per_seed) > 1 else np.nan
            prevs = [td.boot[(m, k)]["prev"] for k in keys]
            row["b_used"] = 0
            for metric in CI_METRICS:
                if not keys:
                    row[f"{metric}_ci_lo"] = row[f"{metric}_ci_hi"] = np.nan
                    continue
                with np.errstate(invalid="ignore"):
                    macro = st.seed_mean(macro_boot([td.boot[(m, k)][metric] for k in keys], prevs))
                row[f"{metric}_ci_lo"], row[f"{metric}_ci_hi"] = st.percentile_ci(macro)
                if metric == "pr_auc":
                    row["b_used"] = int(np.isfinite(macro).sum())
            row["n_low_support_repos"] = int(sum(p_["n_pos"].iloc[0] < low_support_threshold() for p_ in pts))
            row["partial"] = bool(td.models[m]["partial"])
            rows.append(row)
    return pd.DataFrame(rows)


def table_per_repo(tds, folds=None):
    folds = folds or {}
    rows = []
    for task, td in tds.items():
        rm = repo_masks(td)
        ensure(td, rm)
        fold_low = set(folds.get(task, {}).get("low_support", []))
        for k in rm:
            repo = k.split("=", 1)[1]
            sub = td.meta[td.meta["test_repo"] == repo]
            for m in td.models:
                rows.append({"setting": td.setting, "task": task, "test_repo": repo,
                             "engine": sub["engine"].iloc[0], "size": sub["size"].iloc[0],
                             "ecosystem": sub["ecosystem"].iloc[0], "model": m,
                             "fold_low_support": repo in fold_low, **summary_row(td, m, k)})
    return pd.DataFrame(rows)


def _group_rows(td, task, masks, label, models=None):
    ensure(td, masks, models)
    rows = []
    n_all = len(td.ids)
    for k, mask in masks.items():
        value = k.split("=", 1)[1]
        repos = sorted(td.meta.loc[mask, "test_repo"].unique().tolist())
        for m in (models or td.models):
            rows.append({"setting": td.setting, "task": task, label: value, "model": m,
                         "n_repos": len(repos), "repos": ";".join(repos),
                         "share_of_test": float(mask.sum() / n_all) if n_all else np.nan, **summary_row(td, m, k)})
    return rows


def table_by(tds, column, label, models=None):
    """Pooled metrics per value of a meta column (engine, size, ecosystem, d_ctx_category, perf_part),
    with prevalence, PR-AUC lift (PR-AUC / prevalence) and ROC-AUC; naive_prior is the chance reference."""
    rows = []
    for task, td in tds.items():
        ms = masks_by(td, column)
        if not ms:
            continue
        rows += _group_rows(td, task, ms, label, [m for m in td.models if models is None or m in models])
    return pd.DataFrame(rows)


def table_markers(tds, markers=SUBSYSTEM_MARKERS, models=GROUP_MODELS):
    """Descriptive: each subsystem marker separately (instances with marker = 1; markers overlap)."""
    rows = []
    for task, td in tds.items():
        masks = {}
        for mk in markers:
            if mk in td.meta:
                mask = (pd.to_numeric(td.meta[mk], errors="coerce").fillna(0) > 0).to_numpy()
                if mask.any():
                    masks[f"{mk}={mk[2:]}"] = mask
        if masks:
            rows += _group_rows(td, task, masks, "marker", [m for m in models if m in td.models])
    return pd.DataFrame(rows)


# RQ4

def table_subset(tds):
    return table_by(tds, "perf_part", "part")


def _ensure_roc(td, masks, models):
    """Resampled ROC-AUC (B_test x S) of each (model, key), stored next to the test bootstrap."""
    CT, cache, _ = _resamples(td, "test")
    jobs = []
    for key, mask in masks.items():
        for m in models:
            ensure(td, {key: mask}, [m], "test")
            if "roc_auc" in cache[(m, key)]:
                continue
            md = td.models[m]
            idx = np.flatnonzero(mask & md["cover"])
            cache[(m, key)]["roc_auc"] = np.full((CT.shape[1], len(md["seeds"])), np.nan)
            jobs += [(m, key, idx, j) for j in range(len(md["seeds"]))]
    if not jobs:
        return

    def run(job):
        m, _, idx, j = job
        return st.boot_roc_auc(CT, td.rows[idx], td.y[idx], td.models[m]["score"][j, idx])

    with ThreadPoolExecutor(BOOT_THREADS) as ex:
        results = list(ex.map(run, jobs))
    for (m, key, _, j), v in zip(jobs, results):
        cache[(m, key)]["roc_auc"][:, j] = v


def table_subset_gap(tds):
    """Per model: metric on the subset minus metric on the complement (same test resamples):
    PR-AUC, PR-AUC lift (the prevalence differs between the parts), ROC-AUC and F1. Below the
    support floor (below_floor) in either part the gap is descriptive only (no p)."""
    rows = []
    for task, td in tds.items():
        ms = masks_by(td, "perf_part", values=["subset", "complement"])
        if not ms or not all(m.any() for m in ms.values()):
            continue
        _ensure_roc(td, ms, list(td.models))
        for m in td.models:
            row = {"setting": td.setting, "task": task, "model": m}
            ps, pc = td.point[(m, "perf_part=subset")], td.point[(m, "perf_part=complement")]
            bs, bc = boot_of(td, m, "perf_part=subset", "test"), boot_of(td, m, "perf_part=complement", "test")
            cover = td.models[m]["cover"]
            sup = {part: part_support(td, ms[f"perf_part={part}"] & cover) for part in ("subset", "complement")}
            floor = any(below_floor(*v) for v in sup.values())
            for metric in ("pr_auc", "pr_auc_lift", "roc_auc", "f1"):
                vs, ws = _test_values(ps, bs, metric)
                vc, wc = _test_values(pc, bc, metric)
                res = st.paired_test(ws, wc, vs, vc)
                if floor:
                    res["p"] = res["p_mcse"] = np.nan
                for k_, v in res.items():
                    row[f"{metric}_{k_}"] = v
            row["n_subset"] = int(ps["n"].iloc[0])
            row["n_pos_subset"] = int(ps["n_pos"].iloc[0])
            row["n_pos_commits_subset"] = sup["subset"][1]
            row["prevalence_subset"] = float(ps["prevalence"].iloc[0])
            row["n_complement"] = int(pc["n"].iloc[0])
            row["n_pos_complement"] = int(pc["n_pos"].iloc[0])
            row["n_pos_commits_complement"] = sup["complement"][1]
            row["prevalence_complement"] = float(pc["prevalence"].iloc[0])
            row["low_support"] = min(row["n_pos_subset"], row["n_pos_complement"]) < low_support_threshold()
            row["descriptive_only"] = floor
            rows.append(row)
    return pd.DataFrame(rows)


def table_did(tds, a=FULL_MODEL, b=REFERENCE, part="perf_part"):
    """RQ4: (a - b on the subset) - (a - b on the complement), bootstrap CI and p on the test
    resamples; Holm over tasks per metric. b is one model id or {task: model id}; part is the
    meta column splitting subset/complement (perf_part, or frame_part for the stricter subset).
    """
    rows = []
    for task, td in tds.items():
        b_task = b.get(task) if isinstance(b, dict) else b
        if b_task is None:
            notice(f"{td.setting}/{task}: no reference model for the RQ4 DiD, skipped")
            continue
        row = did_row(td, a, b_task, part)
        if row is not None:
            rows.append(row)
    df = pd.DataFrame(rows)
    for metric in ("pr_auc", "f1"):
        if len(df):
            df[f"{metric}_did_p_holm"] = st.holm(df[f"{metric}_did_p"].to_numpy())
    return df


def did_row(td, a, b, part="perf_part"):
    """One RQ4 row for task data td, or None when a model or a part is missing.

    low_support_<part>: fewer than 30 positives in that part; F1 results of such rows are
    exploratory (threshold-dependent on few positives). below_floor_<part>: the part is below the
    support floor (below_floor); its paired test and the DiD then have no p (descriptive_only).
    b_used: resamples in which every part involved has a positive."""
    if a not in td.models or b not in td.models:
        notice(f"{td.setting}/{td.task}: RQ4 DiD needs {a} and {b}, skipped")
        return None
    ms = masks_by(td, part, values=["subset", "complement"])
    if not ms or not all(m.any() for m in ms.values()):
        notice(f"{td.setting}/{td.task}: no {part} subset/complement, DiD skipped")
        return None
    row = {"setting": td.setting, "task": td.task, "model_a": a, "model_b": b, "split": part}
    joint = td.models[a]["cover"] & td.models[b]["cover"]
    floor = {}
    for side in ("subset", "complement"):
        n_pos, n_commits = part_support(td, ms[f"{part}={side}"] & joint)
        row[f"n_pos_commits_{side}"] = n_commits
        floor[side] = below_floor(n_pos, n_commits)
    for metric in ("pr_auc", "f1"):
        got = {}
        for side in ("subset", "complement"):
            k = f"{part}={side}"
            pa, pb, ba, bb = pair_arrays(td, a, b, k, ms[k])
            got[side] = (pa, pb, ba, bb)
            res = st.paired_test(ba[metric], bb[metric], pa[metric].to_numpy(), pb[metric].to_numpy())
            if floor[side]:
                res["p"] = res["p_mcse"] = np.nan
            for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
                row[f"{metric}_{side}_{k_}"] = res[k_]
            row[f"n_{side}"] = int(pa["n"].iloc[0])
            row[f"n_pos_{side}"] = int(pa["n_pos"].iloc[0])
        (pas, pbs, bas, bbs), (pac, pbc, bac, bbc) = got["subset"], got["complement"]
        res = st.did_test({"a_sub": bas[metric], "b_sub": bbs[metric], "a_comp": bac[metric], "b_comp": bbc[metric]},
                          {"a_sub": pas[metric].to_numpy(), "b_sub": pbs[metric].to_numpy(),
                           "a_comp": pac[metric].to_numpy(), "b_comp": pbc[metric].to_numpy()})
        if floor["subset"] or floor["complement"]:
            res["p"] = res["p_mcse"] = np.nan
        for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
            row[f"{metric}_did_{k_}"] = res[k_]
    lim = low_support_threshold()
    row["low_support_subset"] = row["n_pos_subset"] < lim
    row["low_support_complement"] = row["n_pos_complement"] < lim
    row["low_support"] = row["low_support_subset"] or row["low_support_complement"]
    row["f1_exploratory"] = row["low_support"]
    row["below_floor_subset"] = floor["subset"]
    row["below_floor_complement"] = floor["complement"]
    row["descriptive_only"] = floor["subset"] or floor["complement"]
    return row


# ablation and comparisons

def table_ablation(tds):
    """Ablation variants on the full test set and on the subset; paired deltas vs full on the
    test resamples, Holm per (task, metric)."""
    rows = []
    for task, td in tds.items():
        if FULL_MODEL not in td.models:
            notice(f"{td.setting}/{task}: {FULL_MODEL} missing, ablation skipped")
            continue
        scopes = [("full_test", "all", all_mask(td))]
        pm = masks_by(td, "perf_part", values=["subset"])
        if pm and pm["perf_part=subset"].any():
            scopes.append(("subset", "perf_part=subset", pm["perf_part=subset"]))
        for scope, key, mask in scopes:
            ensure(td, {key: mask})
            for variant, m in ABLATION:
                if m not in td.models:
                    notice(f"{td.setting}/{task}: ablation variant {variant} ({m}) missing")
                    continue
                row = {"setting": td.setting, "task": task, "scope": scope, "variant": variant, "model": m,
                       **summary_row(td, m, key)}
                n_pos, n_commits = part_support(td, mask & td.models[m]["cover"] & td.models[FULL_MODEL]["cover"])
                row["n_pos_commits"] = n_commits
                row["descriptive_only"] = below_floor(n_pos, n_commits)
                for metric in ("pr_auc", "f1"):
                    if m == FULL_MODEL:
                        continue
                    res = paired(td, m, FULL_MODEL, key, mask, metric)
                    if row["descriptive_only"]:
                        res["p"] = res["p_mcse"] = np.nan
                    for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
                        row[f"{metric}_vs_full_{k_}"] = res[k_]
                rows.append(row)
    df = pd.DataFrame(rows)
    for metric in ("pr_auc", "f1"):
        col = f"{metric}_vs_full_p"
        if col not in df:
            continue
        df[f"{metric}_vs_full_p_holm"] = np.nan
        for task in df["task"].unique():
            sel = (df["task"] == task).to_numpy()
            df.loc[sel, f"{metric}_vs_full_p_holm"] = st.holm(df.loc[sel, col].to_numpy())
    return df


def per_repo_seed_values(td, a, b, metric):
    """Per test repository: seed-mean values of a and b, and the per-(repo, seed) values."""
    va, vb, ra, rb = [], [], [], []
    for k, mask in repo_masks(td).items():
        pa, pb, _, _ = pair_arrays(td, a, b, k, mask)
        va.append(np.nanmean(pa[metric].to_numpy()))
        vb.append(np.nanmean(pb[metric].to_numpy()))
        ra.extend(pa[metric].tolist())
        rb.extend(pb[metric].tolist())
    return np.array(va), np.array(vb), np.array(ra), np.array(rb)


def table_pairwise(tds, pairs=PAIRS, exclude=None):
    """Pooled paired bootstrap (primary), macro paired bootstrap of PR-AUC, Wilcoxon over test
    repositories and Cliff's delta; Holm within task per metric over the pairs. exclude =
    {task: [repos]} (the few-commit folds) adds the macro test without those folds."""
    exclude = exclude or {}
    rows = []
    for task, td in tds.items():
        for a, b in pairs:
            if a not in td.models or b not in td.models:
                notice(f"{td.setting}/{task}: comparison {a} vs {b} skipped (model missing)")
                continue
            row = {"setting": td.setting, "task": task, "model_a": a, "model_b": b}
            for metric in ("pr_auc", "f1"):
                res = paired(td, a, b, "all", all_mask(td), metric)
                row["n"], row["n_pos"] = res["n"], res["n_pos"]
                for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
                    row[f"{metric}_{k_}"] = res[k_]
                va, vb, ra, rb = per_repo_seed_values(td, a, b, metric)
                w = st.wilcoxon_paired(va, vb)
                row[f"{metric}_wilcoxon_n"] = w["n"]
                row[f"{metric}_wilcoxon_stat"] = w["stat"]
                row[f"{metric}_wilcoxon_p"] = w["p"]
                row[f"{metric}_wilcoxon_min_p"] = w["min_p"]
                d = st.cliffs_delta(ra, rb)
                row[f"{metric}_cliffs_delta"] = d
                row[f"{metric}_cliffs_magnitude"] = st.cliffs_magnitude(d)
            res = macro_paired(td, a, b, "pr_auc")
            for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
                row[f"macro_pr_auc_{k_}"] = res[k_]
            dropped = [r for r in exclude.get(task, []) if r in td.test_repos]
            if dropped:
                res = macro_paired(td, a, b, "pr_auc", exclude=dropped)
                for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
                    row[f"macro_no_few_commit_pr_auc_{k_}"] = res[k_]
                row["few_commit_folds_excluded"] = ";".join(dropped)
            rows.append(row)
    df = pd.DataFrame(rows)
    for col in ("pr_auc_p", "pr_auc_wilcoxon_p", "f1_p", "f1_wilcoxon_p", "macro_pr_auc_p",
                "macro_no_few_commit_pr_auc_p"):
        if col not in df:
            continue
        df[f"{col}_holm"] = np.nan
        for task in df["task"].unique():
            sel = (df["task"] == task).to_numpy()
            df.loc[sel, f"{col}_holm"] = st.holm(df.loc[sel, col].to_numpy())
    return df


def table_view_comparison(td_pre, td_post, models=None):
    """Sensitivity: each model on the add_log instances in the pre-state view (td_pre) and the
    commit-time view (td_post, same instances under the 'add_log_post:' prefix); post - pre.

    The paired bootstrap needs the same instances and commit clusters, which give identical
    test resamples; otherwise only the point values are reported."""
    def suffix(ids):
        return np.array([i.split(":", 1)[1] for i in ids], dtype=object)

    aligned = (len(td_pre.ids) == len(td_post.ids) and (suffix(td_pre.ids) == suffix(td_post.ids)).all()
               and np.array_equal(td_pre.clusters, td_post.clusters)
               and td_pre.CT_test.shape == td_post.CT_test.shape and np.array_equal(td_pre.CT_test, td_post.CT_test))
    if not aligned:
        notice(f"{td_post.setting}/{td_post.task}: instances differ from {td_pre.task}; view comparison "
               "without paired bootstrap")
    rows = []
    for m in [m for m in td_post.models if m in td_pre.models and (models is None or m in models)]:
        row = {"setting": td_post.setting, "model": m, "paired": aligned}
        if aligned:
            joint = td_pre.models[m]["cover"] & td_post.models[m]["cover"]
            key = "all" if joint.all() else "all|views"
            mask = all_mask(td_pre) & joint
        else:
            key, mask = "all", None
        for metric in ("pr_auc", "f1"):
            got = []
            for td in (td_pre, td_post):
                ensure(td, {key: mask if mask is not None else all_mask(td)}, [m], "test")
                got.append((td.point[(m, key)], boot_of(td, m, key, "test")))
            (pp, bp), (pq, bq) = got
            row["n"], row["n_pos"] = int(pp["n"].iloc[0]), int(pp["n_pos"].iloc[0])
            row[f"{metric}_pre"] = float(pp[metric].mean())
            row[f"{metric}_post"] = float(pq[metric].mean())
            if aligned:
                res = st.paired_test(bq[metric], bp[metric], pq[metric].to_numpy(), pp[metric].to_numpy())
            else:
                res = {"delta": row[f"{metric}_post"] - row[f"{metric}_pre"], "ci_lo": np.nan, "ci_hi": np.nan,
                       "p": np.nan, "p_mcse": np.nan, "b_used": 0}
            for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
                row[f"{metric}_{k_}"] = res[k_]
        row["partial"] = bool(td_pre.models[m]["partial"] or td_post.models[m]["partial"])
        rows.append(row)
    df = pd.DataFrame(rows)
    for metric in ("pr_auc", "f1"):
        if len(df):
            df[f"{metric}_p_holm"] = st.holm(df[f"{metric}_p"].to_numpy())
    return df


CONTEXT_COLUMNS = ["perf_part", "frame_part"]


def align_view_split(td_post, td_pre):
    """Gives the commit-time view (td_post) the context columns (d_*, perf_part, frame_part) of the
    pre-state view (td_pre), so both views are compared on the same subset/complement split.

    The d_* flags of add_log_post are computed on the masked post-state method and can differ.
    Replaced only when every td_post instance is in td_pre (same id after the task prefix); call
    it before any table of td_post. Returns the source of the split and how many instances
    (positives) change membership between the two views."""
    def suffix(ids):
        return pd.Index([i.split(":", 1)[1] for i in ids])

    out = {"source": "masked view", "n": 0, "n_perf_changed": 0, "n_perf_changed_pos": 0,
           "n_category_changed": 0, "n_category_changed_pos": 0}
    if "perf_part" not in td_post.meta or "perf_part" not in td_pre.meta:
        return out
    pre = td_pre.meta.set_index(suffix(td_pre.meta["instance_id"]))
    keys = suffix(td_post.meta["instance_id"])
    common = keys.isin(pre.index)
    out["n"] = int(common.sum())
    pos = td_post.y[common] == 1
    for col, name in (("perf_part", "perf"), ("d_ctx_category", "category")):
        if col not in td_post.meta or col not in pre:
            continue
        a = td_post.meta.loc[common, col].astype(str).to_numpy()
        b = pre.loc[keys[common], col].astype(str).to_numpy()
        out[f"n_{name}_changed"] = int((a != b).sum())
        out[f"n_{name}_changed_pos"] = int(((a != b) & pos).sum())
    if common.all():
        cols = [c for c in pre.columns if c.startswith("d_") or c in CONTEXT_COLUMNS]
        for c in cols:
            td_post.meta[c] = pre.loc[keys, c].to_numpy()
        out["source"] = f"pre-state view ({td_pre.task})"
    else:
        notice(f"{td_post.setting}/{td_post.task}: {int((~common).sum())} instances are not in {td_pre.task}; "
               "subset split taken from the masked view")
    return out


def table_sensitivity(p, tasks, B, primary, primary_setting="R4", settings=("R1", "R4", "R10"),
                      models=SENSITIVITY_MODELS, ecosystems=None, seed=42):
    rows = []
    for setting in settings:
        for task in tasks:
            if setting == primary_setting and task in primary:
                td = primary[task]
            else:
                td = load_task(setting, task, p, B, seed, models=models, ecosystems=ecosystems, with_context=False)
            if td is None:
                continue
            ms = [m for m in models if m in td.models]
            ensure(td, {"all": all_mask(td)}, ms)
            for m in ms:
                rows.append({"setting": setting, "task": task, "model": m, **summary_row(td, m, "all")})
    return pd.DataFrame(rows)


# multiclass supplement

def _class_of(v):
    if isinstance(v, (int, np.integer)) or (isinstance(v, str) and v.isdigit()):
        i = int(v)
        return MULTICLASS[i] if 0 <= i < len(MULTICLASS) else str(i)
    if isinstance(v, float) and float(v).is_integer():
        return MULTICLASS[int(v)]
    return str(v)


MULTICLASS_METRICS = ["macro_f1", "balanced_accuracy", "mcc", "macro_precision", "macro_recall", "macro_pr_auc",
                      "accuracy"]


def table_multiclass(p, setting):
    """Multiclass supplement. Accuracy is listed last: with ~80% NO_EVENT it mostly measures the
    majority class (see the majority_class row, which always predicts the most frequent class)."""
    base = p["predictions"] / setting / "multiclass"
    if not base.exists():
        notice(f"{setting}/multiclass: no predictions, supplement skipped")
        return None, None
    summary, per_class = [], []
    majority_row = None
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        res = []
        for f in sorted(d.glob("seed*.csv")):
            df = pd.read_csv(f)
            if not {"y_true", "y_pred"} <= set(df.columns):
                notice(f"{f}: multiclass file without y_true/y_pred, ignored")
                continue
            yt = [_class_of(v) for v in df["y_true"]]
            yp = [_class_of(v) for v in df["y_pred"]]
            scores = {}
            for c in df.columns:
                mm = re.fullmatch(r"(?:score|p|prob|proba)_(.+)", c)
                if mm:
                    scores[_class_of(mm.group(1))] = df[c].to_numpy(dtype=float)
            res.append(multiclass_metrics(yt, yp, scores or None, MULTICLASS))
            if majority_row is None:
                top = pd.Series(yt).value_counts().sort_index().idxmax()
                mm_ = multiclass_metrics(yt, [top] * len(yt), None, MULTICLASS)
                majority_row = {"setting": setting, "model": "majority_class", "n": mm_["n"], "n_seeds": 1,
                                "predicts": top, **{f"{k}_mean": mm_[k] for k in MULTICLASS_METRICS}}
        if not res:
            continue
        r = pd.DataFrame(res)
        row = {"setting": setting, "model": d.name, "n": int(r["n"].iloc[0]), "n_seeds": len(r)}
        for metric in MULTICLASS_METRICS:
            row[f"{metric}_mean"] = float(r[metric].mean())
            row[f"{metric}_sd"] = float(r[metric].std(ddof=1)) if len(r) > 1 else np.nan
        summary.append(row)
        for c in MULTICLASS:
            prow = {"setting": setting, "model": d.name, "class": c, "n_class": int(r[f"n_{c}"].iloc[0])}
            for metric in ("f1", "pr_auc"):
                col = f"{metric}_{c}"
                vals = r[col] if col in r else pd.Series([np.nan])
                prow[f"{metric}_mean"] = float(vals.mean())
                prow[f"{metric}_sd"] = float(vals.std(ddof=1)) if len(vals) > 1 else np.nan
            per_class.append(prow)
    if not summary:
        return None, None
    if majority_row is not None:
        summary.append(majority_row)
    return pd.DataFrame(summary), pd.DataFrame(per_class)


# RQ2 importance

def _importance_files(p, level="group"):
    """results/importance/<setting>/<task>/<model>_seed<k>_{groups,features}.csv, the layout written by
    scripts/run_experiments.py --importance. Nothing else is read: the evaluation's own
    tables/rq2_importance*.csv must never come back in as an extra fold."""
    kind = "groups" if level == "group" else "features"
    files = p["results"].glob(f"importance/*/*/*_seed*_{kind}.csv")
    return sorted(f for f in files if f.is_file() and re.fullmatch(rf".+_seed\d+_{kind}", f.stem))


def read_importance(p, setting, level="group", tasks=None, exclude_models=tuple(POSTHOC_MODELS)):
    """Rows (setting, task, model, name, fold, seed, importance) from the files of one setting.

    Setting and task come from the directory, model and seed from the file name; the
    columns are those written by scripts/run_experiments.py: fold, group|feature, mean_drop, std.
    """
    name_col = "group" if level == "group" else "feature"
    frames = []
    for f in _importance_files(p, level):
        sett, task = f.parent.parent.name, f.parent.name
        if sett != setting or (tasks is not None and task not in tasks):
            continue
        m = re.fullmatch(r"(.+)_seed(\d+)_(groups|features)", f.stem)
        if m.group(1) in exclude_models:
            continue
        try:
            df = pd.read_csv(f)
        except Exception as e:
            notice(f"{f}: unreadable importance file ({type(e).__name__}), ignored")
            continue
        if not {"fold", name_col, "mean_drop"} <= set(df.columns):
            notice(f"{f}: expected columns fold, {name_col}, mean_drop; file ignored")
            continue
        frames.append(pd.DataFrame({"setting": sett, "task": task, "model": m.group(1), "name": df[name_col],
                                    "fold": df["fold"], "seed": int(m.group(2)),
                                    "importance": df["mean_drop"].astype(float)}))
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def table_importance(p, setting, level="group", top=None, tasks=None):
    """Permutation importance (drop in AP): mean ± sd over folds of the seed-averaged drop.
    Group rows carry the spelled-out group name; feature rows their group (x_ buckets = lexical)."""
    imp = read_importance(p, setting, level, tasks)
    if imp is None:
        notice(f"no permutation-importance CSVs ({level} level) for {setting}, table skipped")
        return None
    per_fold = imp.groupby(["task", "model", "name", "fold"])["importance"].mean().reset_index()
    agg = per_fold.groupby(["task", "model", "name"])["importance"].agg(["mean", "std", "count"]).reset_index()
    agg = agg.rename(columns={"name": level, "mean": "importance_mean", "std": "importance_sd", "count": "n_folds"})
    agg["rank"] = agg.groupby(["task", "model"])["importance_mean"].rank(ascending=False, method="min").astype(int)
    agg.insert(0, "setting", setting)
    if level == "group":
        agg["group_name"] = agg["group"].map(group_name)
    else:
        agg["group_name"] = agg["feature"].astype(str).str.split("_").str[0].map(group_name)
    agg = agg.sort_values(["task", "model", "rank"]).reset_index(drop=True)
    if top:
        agg = agg[agg["rank"] <= top].reset_index(drop=True)
    return agg


def validation_pr_auc(p, setting, task, model):
    """(mean validation PR-AUC over folds and seeds from the sidecars, number of values); NaN if none.

    Uses no test information.
    """
    vals = []
    for f in sorted((p["predictions"] / setting / task / model).glob("seed*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                side = json.load(fh)
        except (OSError, ValueError):
            continue
        for fo in side.get("folds", []):
            v = fo.get("val", {}).get("pr_auc") if isinstance(fo.get("val"), dict) else None
            if isinstance(v, (int, float)) and np.isfinite(v):
                vals.append(float(v))
    return (float(np.mean(vals)) if vals else np.nan), len(vals)


def best_classical_by_validation(p, setting, tasks, models=CLASSICAL):
    """{task: classical model with the highest mean validation PR-AUC} and the table of those values.

    The RQ4 reference is the 'best classical' model; choosing it on the
    test folds would be post-hoc, so this sensitivity check chooses on validation only.
    """
    rows, best = [], {}
    for task in tasks:
        got = {m: validation_pr_auc(p, setting, task, m) for m in models}
        vals = {m: v for m, (v, _) in got.items()}
        ok = {m: v for m, v in vals.items() if np.isfinite(v)}
        if ok:
            # a tie keeps the a priori reference
            best[task] = max(ok, key=lambda m: (ok[m], m == REFERENCE))
        for m, v in vals.items():
            rows.append({"setting": setting, "task": task, "model": m, "val_pr_auc_mean": v,
                         "n_val_folds": got[m][1], "selected": best.get(task) == m})
    return best, pd.DataFrame(rows)


def table_training(p, setting, tasks, models=None, exclude=tuple(POSTHOC_MODELS), multiclass=True):
    """Per task and model: seeds, completeness and training effort, from the seed<k>.json sidecars."""
    rows = []
    for task in list(tasks) + (["multiclass"] if multiclass else []):
        base = p["predictions"] / setting / task
        if not base.exists():
            continue
        for d in sorted((x for x in base.iterdir() if x.is_dir()), key=lambda x: model_sort_key(x.name)):
            if (models is not None and d.name not in models) or (models is None and d.name in exclude):
                continue
            sides = []
            for f in sorted(d.glob("seed*.json")):
                try:
                    with open(f, encoding="utf-8") as fh:
                        sides.append(json.load(fh))
                except (OSError, ValueError):
                    notice(f"{f}: unreadable sidecar")
            if not sides:
                continue
            folds = [fo for sd in sides for fo in sd.get("folds", [])]
            secs = [float(fo["fold_seconds"]) for fo in folds if isinstance(fo.get("fold_seconds"), (int, float))]
            epochs = [fo["epochs"] for fo in folds if isinstance(fo.get("epochs"), (int, float))]
            val = [fo.get("val", {}).get("pr_auc") for fo in folds if isinstance(fo.get("val"), dict)]
            val = [v for v in val if isinstance(v, (int, float))]
            thr = [fo["threshold"] for fo in folds if isinstance(fo.get("threshold"), (int, float))]
            dropped = sides[0].get("dropped") or {}
            eval_sets = sorted({sd["eval_set_sha1"] for sd in sides if sd.get("eval_set_sha1")})
            codes = sorted({sd["code_sha1"] for sd in sides if sd.get("code_sha1")})
            row = {"setting": setting, "task": task, "model": d.name, "n_seeds": len(sides),
                   "eval_set_sha1": ";".join(eval_sets), "code_sha1": ";".join(codes),
                   "all_complete": all(sd.get("complete", True) for sd in sides),
                   "n_folds_total": len(folds), "n_eval": sides[0].get("n_eval"),
                   "n_selected": sides[0].get("n_selected"),
                   "dropped_no_features": dropped.get("no_features"), "dropped_no_graph": dropped.get("no_graph"),
                   "fold_seconds_mean": float(np.nanmean(secs)) if secs else np.nan,
                   "seconds_per_seed": float(np.nansum(secs)) / len(sides) if secs else np.nan,
                   "epochs_mean": float(np.mean(epochs)) if epochs else np.nan,
                   "threshold_mean": float(np.mean(thr)) if thr else np.nan,
                   "val_pr_auc_mean": float(np.mean(val)) if val else np.nan}
            row.update(log1p_columns(folds))
            rows.append(row)
    return pd.DataFrame(rows)


# columns that src/features already writes as log1p counts (with the x_ lexical buckets)
LOG1P_FEATURES = ("h_commit_index", "h_file_prior_churn")


def log1p_columns(folds):
    """Post-hoc log1p models: the transformed columns recorded per fold in the sidecars, as means over
    folds and seeds (per feature group, and those already log1p counts, transformed twice); {} otherwise."""
    trans = [fo for fo in folds if isinstance(fo.get("n_log1p_columns"), (int, float))]
    if not trans:
        return {}
    groups = {}
    for fo in trans:
        for g, v in (fo.get("log1p_columns_by_group") or {}).items():
            groups[g] = groups.get(g, 0) + v
    order = list(FEATURE_GROUPS)
    by_group = sorted(groups.items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else len(order), kv[0]))
    twice = [sum(1 for c in fo["log1p_columns"] if str(c).startswith("x_") or c in LOG1P_FEATURES)
             for fo in trans if isinstance(fo.get("log1p_columns"), list)]
    return {"tabular_transform": ";".join(sorted({str(fo.get("tabular_transform")) for fo in trans})),
            "n_log1p_columns_mean": float(np.mean([fo["n_log1p_columns"] for fo in trans])),
            "log1p_columns_by_group": "; ".join(f"{g}={round(v / len(trans), 1):g}" for g, v in by_group),
            "n_log1p_twice_mean": float(np.mean(twice)) if twice else np.nan,
            "n_folds_log1p": len(trans)}


# dataset quality

def table_instances(p, folds, tasks):
    # the negative pool size is only known at assembly time (instances/ keeps the R10 sample)
    summary_path = p["instances"] / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    rows = []
    for task in tasks:
        inst = load_instances(p, task)
        if inst is None:
            notice(f"instances/{task}.jsonl not found, instance counts skipped")
            continue
        df = pd.DataFrame([{k: r.get(k) for k in ("repo", "label", "in_R1", "in_R4", "in_R10")} for r in inst])
        f = folds.get(task, {})
        for repo, g in df.groupby("repo"):
            neg = g[g["label"] == 0]
            role = "test" if repo in f.get("test_repos", []) else "train_only"
            pool = summary.get("tasks", {}).get(task, {}).get(repo, {}).get("n_neg_pool")
            rows.append({"task": task, "repo": repo, "n_pos": int((g["label"] == 1).sum()),
                         "n_neg_pool": pool, "n_neg_written": len(neg), "n_neg_R1": int(neg["in_R1"].fillna(False).astype(bool).sum()),
                         "n_neg_R4": int(neg["in_R4"].fillna(False).astype(bool).sum()),
                         "n_neg_R10": int(neg["in_R10"].fillna(False).astype(bool).sum()),
                         "fold_role": role, "low_support": repo in f.get("low_support", []),
                         "excluded_n_pos": f.get("excluded", {}).get(repo)})
    return pd.DataFrame(rows)


def _repo_from_id(instance_id):
    parts = str(instance_id).split(":")
    return parts[1] if len(parts) > 2 else None


def table_failures(p, tasks, primary="R4"):
    """View/feature failures and graph failures per task and repository.

    Graphs are built for the instances of the primary setting only (neural models run there),
    so instances outside it have no graph by design (n_graph_not_built_outside_<primary>);
    n_graph_missing_in_<primary> counts real gaps."""
    rows = []
    for task in tasks:
        inst = load_instances(p, task)
        repo_of = {r["instance_id"]: r["repo"] for r in inst} if inst else {}
        in_primary = {r["instance_id"] for r in inst or [] if r.get("label") == 1 or r.get(f"in_{primary}")}
        ff = p["features"] / f"{task}_failures.jsonl"
        fails = read_jsonl(ff) if ff.exists() else []
        feats = p["features"] / f"{task}.csv"
        feat_ids = set(pd.read_csv(feats, usecols=["instance_id"], dtype=str)["instance_id"]) if feats.exists() else None
        gi = p["graphs"] / f"{task}_index.csv"
        gidx = pd.read_csv(gi, dtype={"instance_id": str}) if gi.exists() else None
        gf = p["graphs"] / f"{task}_failures.jsonl"
        gfails = read_jsonl(gf) if gf.exists() else None
        for r in fails:
            r["_repo"] = r.get("repo") or repo_of.get(r.get("instance_id")) or _repo_from_id(r.get("instance_id"))
        repos = sorted(set(repo_of.values()) | {r["_repo"] for r in fails if r["_repo"]})
        for repo in repos:
            ids = {i for i, v in repo_of.items() if v == repo}
            fr = [r for r in fails if r["_repo"] == repo]
            reasons = {}
            for r in fr:
                key = str(r.get("reason", "unknown"))
                reasons[key] = reasons.get(key, 0) + 1
            row = {"task": task, "repo": repo, "n_instances": len(ids), "n_view_failures": len(fr),
                   "failure_reasons": "; ".join(f"{k}={v}" for k, v in sorted(reasons.items()))}
            if feat_ids is not None:
                row["n_with_features"] = len(ids & feat_ids)
            if gidx is not None:
                g = gidx[gidx["instance_id"].isin(ids)]
                row["n_with_graph"] = int(g["instance_id"].nunique())
                if feat_ids is not None:
                    no_graph = (ids & feat_ids) - set(g["instance_id"])
                    row[f"n_graph_not_built_outside_{primary}"] = len(no_graph - in_primary)
                    row[f"n_graph_missing_in_{primary}"] = len(no_graph & in_primary)
                row["n_graph_truncated"] = int(g["truncated"].fillna(0).astype(bool).sum()) if "truncated" in g else 0
            if gfails is not None:
                gr = [r for r in gfails if (r.get("repo") or _repo_from_id(r.get("instance_id"))) == repo]
                row["n_graph_failures"] = len(gr)
                reasons = {}
                for r in gr:
                    key = str(r.get("reason", "unknown")).split(":")[0]
                    reasons[key] = reasons.get(key, 0) + 1
                row["graph_failure_reasons"] = "; ".join(f"{k}={v}" for k, v in sorted(reasons.items()))
            rows.append(row)
    return pd.DataFrame(rows)


def table_graph_stats(p, tasks):
    rows = []
    for task in tasks:
        gi = p["graphs"] / f"{task}_index.csv"
        if not gi.exists():
            notice(f"graphs/{task}_index.csv not found, graph statistics skipped")
            continue
        g = pd.read_csv(gi)
        row = {"task": task, "n_graphs": len(g)}
        for c in ("n_nodes", "n_edges"):
            v = g[c].astype(float)
            row.update({f"{c}_mean": v.mean(), f"{c}_median": v.median(), f"{c}_p95": v.quantile(0.95),
                        f"{c}_max": v.max()})
        row["n_truncated"] = int(g["truncated"].fillna(0).astype(bool).sum()) if "truncated" in g else 0
        mf = p["graphs"] / f"{task}_meta.json"
        if mf.exists():
            with open(mf, encoding="utf-8") as f:
                meta = json.load(f)
            for k in ("n_candidates", "n_instances", "n_graphs", "n_failures", "elapsed_seconds"):
                if isinstance(meta.get(k), (int, float)) and not isinstance(meta.get(k), bool):
                    row[f"build_{k}"] = meta[k]
            stats = meta.get("stats", meta.get("build_stats", {}))
            stats = stats.get("all", stats) if isinstance(stats, dict) else {}
            for k, v in stats.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    row[f"build_{k}"] = v
            if isinstance(meta.get("failure_reasons"), dict):
                row["build_failure_reasons"] = "; ".join(f"{k}={v}" for k, v in sorted(meta["failure_reasons"].items()))
            for k in ("node_types", "edge_types"):
                if isinstance(meta.get(k), (list, dict)):
                    row[f"n_{k}"] = len(meta[k])
        rows.append(row)
    return pd.DataFrame(rows)


def mining_repos(p):
    if not p["mining"].exists():
        return []
    # <repo>.tmp (interrupted run) and <repo>.old (previous output not deleted) are not repositories
    return sorted(d.name for d in p["mining"].iterdir()
                  if d.is_dir() and not d.name.endswith((".tmp", ".old")))


def commit_counts(p):
    """repo -> (n_commits, n_non_merge, n_bulk) from the mining commits.jsonl."""
    out = {}
    for repo in mining_repos(p):
        f = p["mining"] / repo / "commits.jsonl"
        if not f.exists():
            continue
        n = nm = nb = 0
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                c = json.loads(line)
                n += 1
                if not c.get("is_merge"):
                    nm += 1
                    nb += int(bool(c.get("is_bulk")))
        out[repo] = (n, nm, nb)
    return out


def table_parse_failures(p):
    rows = []
    counts = commit_counts(p)
    for repo in mining_repos(p):
        d = p["mining"] / repo
        row = {"repo": repo}
        if repo in counts:
            row["n_commits"], row["n_non_merge"], row["n_bulk"] = counts[repo]
        pf = d / "parse_failures.jsonl"
        fails = read_jsonl(pf) if pf.exists() else []
        row["parse_failures"] = len(fails)
        row["parse_failures_pre"] = sum(1 for r in fails if r.get("side") == "pre")
        row["parse_failures_post"] = sum(1 for r in fails if r.get("side") == "post")
        sf = d / "summary.json"
        if sf.exists():
            with open(sf, encoding="utf-8") as f:
                summ = json.load(f)
            for k, v in summ.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in row:
                    row[f"summary_{k}"] = v
            if isinstance(summ.get("parse_failures_by_reason"), dict):
                row["parse_failure_reasons"] = "; ".join(
                    f"{k}={v}" for k, v in sorted(summ["parse_failures_by_reason"].items()))
        rows.append(row)
    if not rows:
        notice("no mining outputs under data/interim/mining, parse-failure table skipped")
    return pd.DataFrame(rows)


def table_coverage(tds_by_setting):
    rows = []
    for setting, tds in tds_by_setting.items():
        for task, td in tds.items():
            for m, md in td.models.items():
                rows.append({"setting": setting, "task": task, "model": m, "n_seeds": len(md["seeds"]),
                             "seeds": ",".join(str(s) for s in md["seeds"]), "n_union": td.n_union,
                             "n_evaluated": int(md["cover"].sum()), "partial": md["partial"],
                             "eval_set_mismatch": md["stale"], "eval_set_sha1": md["eval_set_sha1"]})
    return pd.DataFrame(rows)


def fold_commit_support(p, folds, task, inst=None):
    """{test_repo: (n_pos, n_pos_commits, max_commit_share, few_commit)} and the source.

    folds.json `per_repo` and `few_commit_folds` (written by the dataset stage) are
    used when present; otherwise the values are computed from the positives of
    instances/<task>.jsonl with the dataset stage's rule (at most FEW_COMMITS commits)."""
    f = folds.get(task, {})
    if inst is None:
        inst = load_instances(p, task) or []
    by_repo = {}
    for r in inst:
        if r.get("label") == 1:
            by_repo.setdefault(r["repo"], []).append(r.get("commit_id"))
    per = f.get("per_repo") or {}
    few_listed = f.get("few_commit_folds")
    out = {}
    for repo in f.get("test_repos", []):
        commits = by_repo.get(repo, [])
        counts = pd.Series(commits).value_counts() if commits else pd.Series(dtype=int)
        stored = per.get(repo) or {}
        n_pos = stored.get("n_pos", len(commits))
        npc = stored.get("n_pos_commits")
        share = stored.get("max_commit_share")
        if npc is None:
            npc = int(len(counts))
        if share is None:
            share = float(counts.iloc[0] / len(commits)) if commits else np.nan
        few = repo in few_listed if few_listed is not None else npc <= FEW_COMMITS
        out[repo] = (int(n_pos), int(npc), float(share), bool(few))
    if per and few_listed is not None:
        source = "folds.json (dataset stage: positives from at most 2 commits)"
    else:
        source = f"computed from the instances (positives from at most {FEW_COMMITS} commits)"
    return out, source


def few_commit_folds(p, folds, tasks):
    out, sources = {}, {}
    for task in tasks:
        sup, src = fold_commit_support(p, folds, task)
        out[task] = [r for r, v in sup.items() if v[3]]
        sources[task] = src
    return out, sources


def _first_sidecar(p, setting, task, prefer=("hgb", "lr", "rf")):
    base = p["predictions"] / setting / task
    if not base.exists():
        return None
    dirs = [base / m for m in prefer if (base / m).is_dir()] + sorted(x for x in base.iterdir() if x.is_dir())
    for d in dirs:
        for f in sorted(d.glob("seed*.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                continue
    return None


def table_folds(p, folds, tasks, setting):
    """One row per LORO fold: training repositories, sizes and positives of the fit, validation
    and test parts (prediction sidecars), and the commit support of the test positives."""
    flag = f"in_{setting}"
    rows = []
    for task in tasks:
        f = folds.get(task)
        if not f:
            continue
        inst = load_instances(p, task) or []
        repos = sorted({r["repo"] for r in inst if r.get("label") == 1 or r.get(flag)})
        sup, source = fold_commit_support(p, folds, task, inst)
        side = _first_sidecar(p, setting, task) or {}
        by_fold = {fo.get("test_repo"): fo for fo in side.get("folds", [])}
        for repo in f.get("test_repos", []):
            fo = by_fold.get(repo, {})
            n_pos, npc, share, few = sup.get(repo, (np.nan, np.nan, np.nan, False))
            rows.append({"setting": setting, "task": task, "test_repo": repo,
                         "training_repos": ";".join(r for r in repos if r != repo),
                         "n_training_repos": len([r for r in repos if r != repo]),
                         "n_fit": fo.get("n_train"), "n_fit_pos": fo.get("n_train_pos"),
                         "n_val": fo.get("n_val"), "n_val_pos": fo.get("n_val_pos"),
                         "n_test": fo.get("n_test"), "n_test_pos": fo.get("n_test_pos"),
                         "val_seed": fo.get("val_seed"), "low_support": repo in f.get("low_support", []),
                         "n_pos_all": n_pos, "n_pos_commits": npc, "max_commit_share": share,
                         "few_commit_fold": few, "commit_support_source": source,
                         "evaluated": bool(fo)})
    return pd.DataFrame(rows)


def _find_key(d, key):
    if isinstance(d, dict):
        if key in d:
            return d[key]
        for v in d.values():
            got = _find_key(v, key)
            if got is not None:
                return got
    return None


def _weighting(cfg, model):
    if model.startswith("naive"):
        return "none (no training)"
    cw = _find_key(cfg, "class_weight")
    if cw is not None:
        return f"class_weight={cw}"
    pw = _find_key(cfg, "pos_weight")
    if pw is not None:
        return f"pos_weight={pw} (n_neg/n_pos of the fit part)"
    return "none (unweighted loss)"


def table_imbalance(p, setting, tasks, models=None, exclude=tuple(POSTHOC_MODELS)):
    """Imbalance handling per task and model: negative sampling of the setting, class weighting
    (sidecar configuration) and the decision-threshold rule, from the prediction sidecars."""
    ratio = setting[1:] if setting.startswith("R") else setting
    rows = []
    for task in tasks:
        base = p["predictions"] / setting / task
        if not base.exists():
            continue
        for d in sorted((x for x in base.iterdir() if x.is_dir()), key=lambda x: model_sort_key(x.name)):
            if (models is not None and d.name not in models) or (models is None and d.name in exclude):
                continue
            sides = []
            for f in sorted(d.glob("seed*.json")):
                try:
                    with open(f, encoding="utf-8") as fh:
                        sides.append(json.load(fh))
                except (OSError, ValueError):
                    continue
            if not sides:
                continue
            cfg = sides[0].get("config") or {}
            folds_ = [fo for sd in sides for fo in sd.get("folds", [])]
            rules = sorted({str(fo.get("decision")) for fo in folds_ if fo.get("decision")})
            thr = [fo["threshold"] for fo in folds_ if isinstance(fo.get("threshold"), (int, float))]
            pw = [fo["pos_weight"] for fo in folds_ if isinstance(fo.get("pos_weight"), (int, float))]
            rows.append({"setting": setting, "task": task, "model": d.name,
                         "negative_sampling": f"{ratio} negatives per positive per repository (seeded, nested)",
                         "class_weighting": _weighting(cfg, d.name),
                         "pos_weight_mean": float(np.mean(pw)) if pw else np.nan,
                         "threshold_rule": "; ".join(rules),
                         "threshold_mean": float(np.mean(thr)) if thr else np.nan,
                         "threshold_min": float(np.min(thr)) if thr else np.nan,
                         "threshold_max": float(np.max(thr)) if thr else np.nan})
    return pd.DataFrame(rows)


def _flatten(prefix, value, out):
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    else:
        out.append((prefix, value if not isinstance(value, list) else ", ".join(str(x) for x in value)))


def table_hyperparameters(cfg=None):
    """configs/experiment.yaml flattened: fixed a priori, except the posthoc section,
    which holds the post-hoc log1p variants (prespecified = False)."""
    cfg = cfg or load_config("experiment")
    rows = []
    for section in ("sampling", "protocol", "features", "models", "posthoc", "evaluation"):
        items = []
        _flatten("", cfg.get(section, {}), items)
        rows += [{"section": section, "key": k, "value": str(v), "prespecified": section != "posthoc"}
                 for k, v in items]
    return pd.DataFrame(rows)


def table_environment(p):
    """Hardware and software from data/results/run_manifest.json (scripts/write_manifest.py)."""
    f = p["results"] / "run_manifest.json"
    if not f.exists():
        notice("results/run_manifest.json not found, environment table skipped")
        return None
    with open(f, encoding="utf-8") as fh:
        m = json.load(fh)
    rows = [("generated", m.get("generated")), ("python", str(m.get("python", "")).split(" ")[0]),
            ("platform", m.get("platform"))]
    for k, v in (m.get("packages") or {}).items():
        rows.append((f"package {k}", v))
    rows.append(("srcml", str(m.get("srcml") or "").splitlines()[0] if m.get("srcml") else None))
    rows.append(("git", m.get("git")))
    cuda = m.get("cuda") or {}
    for k in ("device_name", "torch_cuda", "cudnn", "available"):
        if k in cuda:
            rows.append((f"cuda {k}", cuda[k]))
    for k, v in (m.get("seeds") or {}).items():
        rows.append((f"seeds {k}", ", ".join(map(str, v)) if isinstance(v, list) else v))
    for k, v in (m.get("hardware") or {}).items():
        rows.append((f"hardware {k}", v))
    for k in ("bootstrap_samples", "bootstrap_samples_tests", "bootstrap_seed"):
        if k in (m.get("evaluation") or {}):
            rows.append((f"evaluation {k}", m["evaluation"][k]))
    rows.append(("pinned repositories", len(m.get("corpus") or [])))
    rows.append(("hashed source files", len(m.get("source_sha256") or {})))
    return pd.DataFrame([{"item": k, "value": "" if v is None else str(v)} for k, v in rows])


def table_head_misparse(p):
    """HEAD snapshot (RQ1 screening) per repository: srcML failures and structural misparses.

    parse_failures = 0 only means srcML returned a tree; a misparsed file has statements or
    members directly under <unit> (class structure lost), so units there have no class and
    statements outside any unit are not detected."""
    d = p["rq1"]
    snap = d / "corpus_snapshot.csv"
    if not snap.exists():
        notice("rq1/corpus_snapshot.csv not found, HEAD misparse table skipped")
        return None
    s = pd.read_csv(snap)
    cols = [c for c in ["repo", "modeling", "n_java_files", "n_parse_failures", "n_files_misparsed", "n_units_no_class",
                        "n_method_units", "n_formal", "n_logs_outside_units"] if c in s]
    out = s[cols].copy()
    out = out[out["repo"].isin(set(corpus_frame()["repo"]))]
    if "n_files_misparsed" in out and "n_java_files" in out:
        out["pct_files_misparsed"] = 100 * out["n_files_misparsed"] / out["n_java_files"].replace(0, np.nan)
    mp = d / "structural_misparse.csv"
    if mp.exists():
        m = pd.read_csv(mp)
        agg = m.groupby("repo")[[c for c in ("n_accepted_lost", "n_formal_lost") if c in m]].sum()
        agg = agg.rename(columns={"n_accepted_lost": "n_statements_outside_units_misparse",
                                  "n_formal_lost": "n_formal_outside_units_misparse"})
        out = out.merge(agg, left_on="repo", right_index=True, how="left")
        for c in agg.columns:
            out[c] = out[c].fillna(0).astype(int)
    return out.reset_index(drop=True)


YES = {"1", "yes", "y", "true", "t", "correct", "ok"}
NO = {"0", "no", "n", "false", "f", "incorrect", "wrong"}
# allowed cells of the manual annotation sheet
ANNOTATION_VALUES = {"label_correct": YES | NO | {"?"}, "is_logging_statement": YES | NO,
                     "level_correct": YES | NO | {"na", "n/a"}}


def _norm(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    s = str(v).strip().lower()
    return s[:-2] if s.endswith(".0") else s


def _annotation(v):
    """1 (yes), 0 (no) or None (empty or anything else)."""
    s = _norm(v)
    return 1 if s in YES else 0 if s in NO else None


def event_outcome(label, lc, il, lv):
    """Reporting rule on normalised cells (label_correct, is_logging_statement, level_correct):
    wrong when any of them is n (level only for CHANGE_LEVEL), else unclear when label_correct is '?',
    correct when all required cells are y, otherwise incomplete."""
    level = label == "CHANGE_LEVEL"
    if lc in NO or il in NO or (level and lv in NO):
        return "wrong"
    if lc == "?":
        return "unclear"
    if lc in YES and il in YES and (not level or lv in YES):
        return "correct"
    return "incomplete"


def table_extraction_precision(p, B=1000, seed=42, core_counts=None):
    """Extraction precision from the annotation of validation/event_sample.csv.

    Per label: precision with '?' excluded (Wilson and commit-clustered bootstrap 95% CIs) and with
    '?' counted as wrong. The sample is stratified by label (up to 40 core events each), so the
    overall value (row ALL) is the stratified estimate sum_l W_l p_l, W_l = the label's share of the
    core events (core_counts), with a bootstrap of commit clusters within each label. The pooled
    share of the sample is kept as 'ALL (sample, unweighted)'; it over-represents rare labels and is
    not an estimate for the corpus. A non-empty cell that is not an allowed value, or a started row
    with a required cell empty, stops the computation (listed in problems).
    Returns (table or None, n_annotated, n_rows, problems)."""
    f = p["results"] / "validation" / "event_sample.csv"
    if not f.exists():
        return None, 0, 0, []
    df = pd.read_csv(f, dtype=str, keep_default_na=False)
    if "label_correct" not in df:
        return None, 0, len(df), []
    present = [c for c in ANNOTATION_VALUES if c in df]
    cells = {c: (df[c].map(_norm) if c in df else pd.Series("y", index=df.index)) for c in ANNOTATION_VALUES}
    started = np.zeros(len(df), dtype=bool)
    for c in present:
        started |= (cells[c] != "").to_numpy()
    problems = []
    for c in present:
        bad = cells[c][started & (cells[c] != "") & ~cells[c].isin(ANNOTATION_VALUES[c])]
        problems += [f"{c}={v!r} ({k}x)" for v, k in bad.value_counts().sort_index().items()]
    outcome = pd.Series([event_outcome(*r) for r in zip(df["event_label"], cells["label_correct"],
                                                         cells["is_logging_statement"], cells["level_correct"])],
                        index=df.index)
    incomplete = started & (outcome == "incomplete").to_numpy()
    if incomplete.any() and not problems:
        ids = df.loc[incomplete, "event_id"].head(3).tolist() if "event_id" in df else []
        problems.append(f"{int(incomplete.sum())} started rows with a required cell empty (e.g. {', '.join(ids)})")
    n_ann = int(started.sum())
    if problems:
        notice("validation/event_sample.csv: extraction precision not computed, annotation cells not recognised "
               "or incomplete: " + "; ".join(problems))
        return None, n_ann, len(df), problems
    if not n_ann:
        return None, 0, len(df), []
    missing = [c for c in ANNOTATION_VALUES if c not in df]
    if missing:
        notice(f"validation/event_sample.csv has no {', '.join(missing)} column; precision from the other columns")

    ann = df[started].copy()
    ann["outcome"] = outcome[started].to_numpy()
    commit = ann["commit_url"].str.rsplit("/", n=1).str[-1] if "commit_url" in ann else None
    if commit is None or (commit == "").any():
        commit = ann["event_id"].str.split(":").str[1]
    # clusters = commits within a label: the sample is drawn per label
    ann["cluster"] = ann["event_label"] + "|" + ann["repo"].astype(str) + "|" + commit.astype(str)
    rows_, uniq = pd.factorize(ann["cluster"], sort=True)
    K = len(uniq)
    strata = pd.Series(uniq).str.split("|", regex=False).str[0].to_numpy()
    CT = st.resample_counts(strata, B, seed).astype(np.float64)
    per_cluster = {o: np.bincount(rows_, weights=(ann["outcome"] == o).to_numpy(dtype=float), minlength=K)
                   for o in ("correct", "wrong", "unclear")}

    def boot(sel):
        c, w, u = ((per_cluster[o] * sel) @ CT for o in ("correct", "wrong", "unclear"))
        with np.errstate(divide="ignore", invalid="ignore"):
            return c / (c + w), c / (c + w + u)

    def stats_row(label, estimator, g, b1, b2, wilson=True):
        c, w, u = (int((g["outcome"] == o).sum()) for o in ("correct", "wrong", "unclear"))
        r = {"event_label": label, "estimator": estimator, "n_annotated": len(g), "n_correct": c, "n_wrong": w,
             "n_unclear": u, "n_commits": int(g["cluster"].nunique()),
             "precision": c / (c + w) if c + w else np.nan}
        r["wilson_ci_lo"], r["wilson_ci_hi"] = st.wilson_ci(c, c + w) if wilson else (np.nan, np.nan)
        r["cluster_ci_lo"], r["cluster_ci_hi"] = st.percentile_ci(b1)
        r["b_used"] = int(np.isfinite(b1).sum())
        r["precision_unclear_wrong"] = c / (c + w + u) if c + w + u else np.nan
        r["unclear_wrong_wilson_ci_lo"], r["unclear_wrong_wilson_ci_hi"] = (
            st.wilson_ci(c, c + w + u) if wilson else (np.nan, np.nan))
        r["unclear_wrong_cluster_ci_lo"], r["unclear_wrong_cluster_ci_hi"] = st.percentile_ci(b2)
        return r

    core_counts = {k: int(v) for k, v in (core_counts or {}).items() if k in EVENT_LABELS}
    total = sum(core_counts.values())
    labels = [x for x in EVENT_LABELS if x in set(ann["event_label"])]
    labels += sorted(set(ann["event_label"]) - set(EVENT_LABELS))
    rows, boots = [], {}
    for lab in labels:
        b1, b2 = boot((strata == lab).astype(float))
        boots[lab] = (b1, b2)
        r = stats_row(lab, "label", ann[ann["event_label"] == lab], b1, b2)
        r["core_events"] = core_counts.get(lab, np.nan)
        r["weight"] = core_counts[lab] / total if total and lab in core_counts else np.nan
        rows.append(r)
    weights = {lab: n / total for lab, n in core_counts.items() if n} if total else {}
    if weights and set(weights) <= set(labels):
        b1 = sum(w * boots[lab][0] for lab, w in weights.items())
        b2 = sum(w * boots[lab][1] for lab, w in weights.items())
        r = stats_row("ALL", "stratified: label precisions weighted by their share of the core events",
                      ann[ann["event_label"].isin(list(weights))], b1, b2, wilson=False)
        by = {x["event_label"]: x for x in rows}
        r["precision"] = sum(w * by[lab]["precision"] for lab, w in weights.items())
        r["precision_unclear_wrong"] = sum(w * by[lab]["precision_unclear_wrong"] for lab, w in weights.items())
        r["core_events"], r["weight"] = total, 1.0
        rows.append(r)
    elif weights:
        notice("extraction precision: labels " + ", ".join(sorted(set(weights) - set(labels)))
               + " have core events but no annotated sample event; no overall (weighted) precision")
    b1, b2 = boot(np.ones(K))
    r = stats_row("ALL (sample, unweighted)", "pooled share of the label-stratified sample, not a corpus estimate",
                  ann, b1, b2)
    r["core_events"], r["weight"] = np.nan, np.nan
    rows.append(r)
    return pd.DataFrame(rows), n_ann, len(df), []


# RQ1

def table_events(events):
    g = events.groupby(["repo", "event_label", "validity_status", "scope"]).size().reset_index(name="n")
    return g.sort_values(["repo", "event_label", "validity_status", "scope"]).reset_index(drop=True)


def pivot_events(events, column):
    g = events.groupby(["repo", "event_label", column]).size().unstack(column, fill_value=0)
    g["total"] = g.sum(axis=1)
    return g.reset_index()


def _formal_nonbulk(events):
    formal = events["logging_style"] == "formal" if "logging_style" in events else pd.Series(True, index=events.index)
    if "is_bulk" in events:
        bulk = events["is_bulk"].fillna(False).astype(bool)
    else:
        bulk = events["validity_status"] == "bulk"
    return formal & ~bulk


def table_event_rates(events, counts):
    """Per repository: core events (formal, modified method, not relocated, not bulk), formal
    non-bulk events of any scope (relocations included) and all events of the master table
    (every style, scope, bulk and relocated event), absolute and per 1,000 non-merge commits."""
    rows = []
    core = events[events["validity_status"] == "core"]
    fnb = _formal_nonbulk(events)
    for repo in sorted(set(events["repo"]) | set(counts)):
        n_commits, n_nm, n_bulk = counts.get(repo, (np.nan, np.nan, np.nan))
        row = {"repo": repo, "n_commits": n_commits, "n_non_merge": n_nm, "n_bulk": n_bulk,
               "n_events_all": int((events["repo"] == repo).sum()),
               "n_formal_nonbulk": int(((events["repo"] == repo) & fnb).sum())}
        for lab in EVENT_LABELS:
            row[f"core_{lab}"] = int(((core["repo"] == repo) & (core["event_label"] == lab)).sum())
        row["core_total"] = sum(row[f"core_{lab}"] for lab in EVENT_LABELS)
        for lab in EVENT_LABELS + ["total"]:
            row[f"core_{lab}_per_1k"] = row[f"core_{lab}"] / n_nm * 1000 if n_nm and n_nm == n_nm else np.nan
        row["formal_nonbulk_per_1k"] = row["n_formal_nonbulk"] / n_nm * 1000 if n_nm and n_nm == n_nm else np.nan
        row["all_per_1k"] = row["n_events_all"] / n_nm * 1000 if n_nm and n_nm == n_nm else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def commits_per_year(p):
    """(repo, year) -> non-merge commits, from the mining commits.jsonl timestamps."""
    out = {}
    for repo in mining_repos(p):
        f = p["mining"] / repo / "commits.jsonl"
        if not f.exists():
            continue
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                c = json.loads(line)
                ts = str(c.get("timestamp") or "")
                if c.get("is_merge") or len(ts) < 4 or not ts[:4].isdigit():
                    continue
                key = (repo, int(ts[:4]))
                out[key] = out.get(key, 0) + 1
    return out


def table_events_per_year(events, per_year=None):
    """Core events per repository, commit year (timestamp of the commit) and label; ALL = every repository.
    per_1k = core events per 1,000 non-merge commits of that year (when commit timestamps are available)."""
    core = events[events["validity_status"] == "core"].copy()
    if "timestamp" not in core or not len(core):
        return None
    core["year"] = pd.to_numeric(core["timestamp"].astype(str).str[:4], errors="coerce")
    core = core.dropna(subset=["year"])
    core["year"] = core["year"].astype(int)
    per_year = per_year or {}
    rows = []
    for repo, g in list(core.groupby("repo")) + [("ALL", core)]:
        for year, gy in g.groupby("year"):
            row = {"repo": repo, "year": int(year)}
            for lab in EVENT_LABELS:
                row[lab] = int((gy["event_label"] == lab).sum())
            row["total"] = sum(row[lab] for lab in EVENT_LABELS)
            if per_year:
                n = (sum(v for (r, y), v in per_year.items() if y == year) if repo == "ALL"
                     else per_year.get((repo, year), 0))
                row["n_non_merge"] = n
                row["total_per_1k"] = row["total"] / n * 1000 if n else np.nan
            rows.append(row)
    # groupby keeps repositories and years sorted; ALL comes last
    return pd.DataFrame(rows)


def table_transitions(events, by_repo=False):
    """CHANGE_LEVEL core events: counts per (pre_level, post_level)."""
    ev = events[(events["event_label"] == "CHANGE_LEVEL") & (events["validity_status"] == "core")]
    if by_repo:
        g = ev.groupby(["repo", "pre_level", "post_level"]).size().reset_index(name="n")
        return g.sort_values(["repo", "pre_level", "post_level"]).reset_index(drop=True)
    mat = pd.crosstab(ev["pre_level"], ev["post_level"]).reindex(index=LEVELS, columns=LEVELS, fill_value=0)
    mat.index.name = "pre_level"
    mat["total"] = mat.sum(axis=1)
    return mat.reset_index()


def table_enrichment(p, tasks, setting="R4"):
    """Share of positives and negatives per context category (instances of the given setting)."""
    rows = []
    for task in tasks:
        inst = load_instances(p, task)
        ctx = load_context(p, task)
        if inst is None or ctx is None or "d_ctx_category" not in ctx:
            continue
        flag = f"in_{setting}"
        df = pd.DataFrame([{"instance_id": r["instance_id"], "label": r["label"], "inset": bool(r.get(flag)) or r["label"] == 1}
                           for r in inst])
        df = df[df["inset"]].merge(ctx, on="instance_id", how="inner")
        npos = int((df["label"] == 1).sum())
        nneg = int((df["label"] == 0).sum())
        cats = CONTEXT_CATEGORIES + sorted(set(df["d_ctx_category"].dropna()) - set(CONTEXT_CATEGORIES))
        groups = [(c, df["d_ctx_category"] == c) for c in cats]
        if "d_is_perf_sensitive" in df:
            groups.append(("perf_sensitive_any", df["d_is_perf_sensitive"].fillna(0).astype(float) > 0))
        for c, sel in groups:
            a = int((sel & (df["label"] == 1)).sum())
            b = int((sel & (df["label"] == 0)).sum())
            sp = a / npos if npos else np.nan
            sn = b / nneg if nneg else np.nan
            rows.append({"setting": setting, "task": task, "category": c, "n_pos": a, "share_pos": sp,
                         "n_neg": b, "share_neg": sn, "enrichment": sp / sn if sn else np.nan,
                         "total_pos": npos, "total_neg": nneg})
    return pd.DataFrame(rows)


def snapshot_levels(p):
    """Formal statements per repo and level (plus 'unknown') from the RQ1 snapshot, if available;
    n_formal = the row total."""
    d = p["rq1"]
    if not d.exists():
        return None
    files = sorted(d.glob("*.csv"))
    files.sort(key=lambda f: f.name != "level_distribution.csv")
    repos = set(corpus_frame()["repo"])
    for f in files:
        if f.name == "caller_audit.csv":
            continue
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        rc = _flex_col(df, ["repo", "repository", "name"])
        if rc is None:
            continue
        df = df[df[rc].isin(repos)]
        if all(lv in df.columns for lv in LEVELS):
            cols = LEVELS + (["unknown"] if "unknown" in df.columns else [])
            out = df[[rc] + cols].rename(columns={rc: "repo"}).reset_index(drop=True)
        else:
            lc = _flex_col(df, ["verbosity", "level", "normalized_level"])
            if lc is None:
                continue
            if "logging_style" in df:
                df = df[df["logging_style"] == "formal"]
            cc = _flex_col(df, ["n", "count", "n_statements", "statements"])
            g = df.groupby([rc, lc])[cc].sum() if cc else df.groupby([rc, lc]).size()
            out = g.unstack(lc, fill_value=0).reindex(columns=LEVELS, fill_value=0).reset_index()
            out = out.rename(columns={rc: "repo"})
            cols = LEVELS
        out.insert(1, "n_formal", out[cols].sum(axis=1).astype(int))
        return out
    return None


# error analysis

def majority(pred):
    """Majority vote over seeds (S x n); a tie counts as negative."""
    return (pred.mean(axis=0) > 0.5).astype(np.int8)


def confusion_by(td, models, columns):
    rows = []
    y = td.y
    for m in models:
        md = td.models[m]
        yp = majority(md["pred"])
        for col in columns:
            if col not in td.meta:
                continue
            for v in sorted(td.meta[col].dropna().unique().tolist(), key=str):
                sel = (td.meta[col] == v).to_numpy() & md["cover"]
                tp = int(((y == 1) & (yp == 1) & sel).sum())
                fp = int(((y == 0) & (yp == 1) & sel).sum())
                fn = int(((y == 1) & (yp == 0) & sel).sum())
                tn = int(((y == 0) & (yp == 0) & sel).sum())
                rows.append({"setting": td.setting, "task": td.task, "model": m, "grouping": col, "group": v,
                             "n": int(sel.sum()), "n_pos": tp + fn, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                             "fp_rate": fp / (fp + tn) if fp + tn else np.nan,
                             "fn_rate": fn / (fn + tp) if fn + tp else np.nan,
                             "precision": tp / (tp + fp) if tp + fp else np.nan,
                             "recall": tp / (tp + fn) if tp + fn else np.nan})
    return pd.DataFrame(rows)


def error_rate_gap(td, models):
    """Per model (majority vote): FP and FN rates on the subset minus the complement, with a
    cluster-bootstrap CI and p on the test resamples. The FN rate needs the positives and the FP
    rate the negatives of both parts above the support floor (below_floor), else no p."""
    ms = masks_by(td, "perf_part", values=["subset", "complement"])
    if not ms or not all(m.any() for m in ms.values()):
        return pd.DataFrame()
    CT = td.CT_test
    rows = []
    for m in models:
        md = td.models[m]
        yp = majority(md["pred"])
        rates = {}
        for part in ("subset", "complement"):
            mask = ms[f"perf_part={part}"] & md["cover"]
            idx = np.flatnonzero(mask)
            y, p_ = td.y[idx], yp[idx]
            tp, fp, fn, tn = st.boot_confusion(CT, td.rows[idx], y, p_)
            point = [float(((y == a) & (p_ == b)).sum()) for a, b in ((1, 1), (0, 1), (1, 0), (0, 0))]
            with np.errstate(divide="ignore", invalid="ignore"):
                rates[part] = {"fp_rate": (point[1] / (point[1] + point[3]) if point[1] + point[3] else np.nan,
                                           fp / (fp + tn)),
                               "fn_rate": (point[2] / (point[2] + point[0]) if point[2] + point[0] else np.nan,
                                           fn / (fn + tp)),
                               "n": len(idx), "n_pos": int(y.sum()),
                               "floor": {"fn_rate": below_floor(*part_support(td, mask, 1)),
                                         "fp_rate": below_floor(*part_support(td, mask, 0))}}
        row = {"setting": td.setting, "task": td.task, "model": m,
               "n_subset": rates["subset"]["n"], "n_pos_subset": rates["subset"]["n_pos"],
               "n_complement": rates["complement"]["n"], "n_pos_complement": rates["complement"]["n_pos"]}
        for r in ("fp_rate", "fn_rate"):
            (ps, bs), (pc, bc) = rates["subset"][r], rates["complement"][r]
            res = st.delta_test(ps - pc, bs - bc)
            floor = rates["subset"]["floor"][r] or rates["complement"]["floor"][r]
            if floor:
                res["p"] = res["p_mcse"] = np.nan
            row[f"{r}_subset"], row[f"{r}_complement"] = ps, pc
            for k_ in ("delta", "ci_lo", "ci_hi", "p", "p_mcse", "b_used"):
                row[f"{r}_{k_}"] = res[k_]
            row[f"{r}_descriptive_only"] = floor
        rows.append(row)
    return pd.DataFrame(rows)


def agreement(td, a=FULL_MODEL, b=REFERENCE):
    """Agreement of the majority votes of a and b, split by the true label (gains on positives
    are TP of one model where the other has a FN; on negatives TN against FP), the precision,
    recall and F1 of each vote, and a threshold-free agreement: overlap of the top-k instances
    of the seed-mean scores, k = number of positives."""
    ma, mb = td.models[a], td.models[b]
    sel = ma["cover"] & mb["cover"]
    y = td.y
    ya, yb = majority(ma["pred"]), majority(mb["pred"])
    ca, cb = (ya == y) & sel, (yb == y) & sel
    out = {"n": int(sel.sum()), "n_pos": int((sel & (y == 1)).sum()),
           "both_correct": int((ca & cb).sum()), "both_wrong": int((~ca & ~cb & sel).sum()),
           f"only_{a}_correct": int((ca & ~cb).sum()), f"only_{b}_correct": int((~ca & cb).sum())}
    for lab, cls in (("pos", y == 1), ("neg", y == 0)):
        out[f"both_correct_{lab}"] = int((ca & cb & cls).sum())
        out[f"both_wrong_{lab}"] = int((~ca & ~cb & sel & cls).sum())
        out[f"only_{a}_correct_{lab}"] = int((ca & ~cb & cls).sum())
        out[f"only_{b}_correct_{lab}"] = int((~ca & cb & cls).sum())
    for m, yp in ((a, ya), (b, yb)):
        cm = confusion_metrics(*[float(((y == t_) & (yp == p_) & sel).sum()) for t_, p_ in ((1, 1), (0, 1), (1, 0), (0, 0))])
        for k in ("precision", "recall", "f1"):
            out[f"{m}_vote_{k}"] = float(cm[k])
    idx = np.flatnonzero(sel)
    k = int(y[idx].sum())
    tops = {}
    for m, md in ((a, ma), (b, mb)):
        s = np.nanmean(md["score"][:, idx], axis=0)
        tops[m] = set(idx[np.argsort(-s, kind="mergesort")[:k]].tolist())
    both = tops[a] & tops[b]
    out["topk_k"] = k
    out["topk_overlap"] = len(both)
    out["topk_overlap_share"] = len(both) / k if k else np.nan
    out["topk_jaccard"] = len(both) / len(tops[a] | tops[b]) if k else np.nan
    for m in (a, b):
        out[f"topk_pos_{m}"] = int(y[list(tops[m])].sum()) if k else 0
    out["topk_pos_both"] = int(y[list(both)].sum()) if both else 0
    out[f"topk_pos_only_{a}"] = int(y[list(tops[a] - tops[b])].sum()) if tops[a] - tops[b] else 0
    out[f"topk_pos_only_{b}"] = int(y[list(tops[b] - tops[a])].sum()) if tops[b] - tops[a] else 0
    return out


def disagreement_sets(td, a=FULL_MODEL, b=REFERENCE):
    ma, mb = td.models[a], td.models[b]
    sel = ma["cover"] & mb["cover"]
    ya, yb = majority(ma["pred"]), majority(mb["pred"])
    ca, cb = (ya == td.y) & sel, (yb == td.y) & sel
    cols = ["instance_id", "repo", "commit_id", "pre_path", "post_path", "class_path", "method_name"]
    base = td.meta[[c for c in cols if c in td.meta]].copy()
    base["label"] = td.y
    base[f"score_{a}"] = np.nanmean(ma["score"], axis=0)
    base[f"score_{b}"] = np.nanmean(mb["score"], axis=0)
    base[f"pred_{a}"] = ya
    base[f"pred_{b}"] = yb
    # the error of the model that is wrong (exactly one is wrong in each set)
    base["wrong_error"] = np.where(td.y == 1, "FN", "FP")
    for c in ("d_ctx_category", "d_is_perf_sensitive", "perf_part", "anchor_level"):
        if c in td.meta:
            base[c] = td.meta[c].to_numpy()
    summary = {"both_correct": int((ca & cb).sum()), "both_wrong": int((~ca & ~cb & sel).sum()),
               f"only_{a}_correct": int((ca & ~cb).sum()), f"only_{b}_correct": int((~ca & cb).sum()),
               "n": int(sel.sum())}
    return base[ca & ~cb].reset_index(drop=True), base[~ca & cb].reset_index(drop=True), summary


def method_source(view, max_lines=60):
    """Source of the task view's method, with the anchor statement marked '// <<< anchor'."""
    from src.parsing.srcml_parser import flatten_text
    lines = flatten_text(view.unit.element).splitlines()
    mark = None
    if view.anchor is not None and view.anchor.line and view.unit.start_line:
        mark = view.anchor.line - view.unit.start_line
        if 0 <= mark < len(lines):
            lines[mark] = lines[mark] + "  // <<< anchor"
        else:
            mark = None
    if len(lines) > max_lines:
        if mark is None:
            lines = lines[:max_lines - 1] + ["    // ... (truncated)"]
        else:
            body = max_lines - 2
            start = max(0, min(mark - body // 2, len(lines) - body))
            end = start + body
            lines = (["    // ..."] if start > 0 else []) + lines[start:end] + (["    // ..."] if end < len(lines) else [])
    return "\n".join(lines)


def masked_statements(instance):
    """Added statements that a masked post-state view removes (shown next to the example, not in the view)."""
    from src.dataset.views import read_blob
    from src.parsing.method_units import parse_java_source, find_unit
    try:
        post = parse_java_source(read_blob(instance["repo"], instance["post_blob"]))
        unit = find_unit(post, instance.get("post_ordinal"), instance["signature_post"], instance["class_path"])
    except Exception:
        return []
    if unit is None:
        return []
    wanted = set(instance.get("mask_post_idx") or [])
    return [(l.line, l.call_text) for l in unit.formal_logs if l.formal_index in wanted]


def stratified_pick(df, keys, n, rng):
    """Up to n rows spread evenly over the strata of `keys` (sorted), then filled from the largest."""
    if not len(df):
        return []
    groups = [g.index.to_numpy() for _, g in df.groupby(keys, sort=True, dropna=False)]
    picks = []
    quota = max(1, n // len(groups))
    rest = []
    for g in groups:
        take = min(quota, len(g))
        chosen = rng.choice(g, size=take, replace=False)
        picks += chosen.tolist()
        rest += [i for i in g if i not in set(chosen.tolist())]
    if len(picks) < n and rest:
        picks += rng.choice(np.array(rest), size=min(n - len(picks), len(rest)), replace=False).tolist()
    return sorted(picks[:n])


def examples_markdown(td, sets, view_loader=None, n_examples=15, seed=42):
    """Examples of each disagreement set, stratified by performance part (subset/complement) and
    by the error (FP/FN) of the model that is wrong."""
    if view_loader is None:
        from src.dataset.views import load_view as view_loader
    lines = [f"# Error analysis examples: {td.task} ({td.setting})", "",
             "Majority vote over seeds; up to "
             f"{n_examples} examples per set, spread over the strata performance part (subset/complement) x error of "
             f"the wrong model (FP/FN), sampled with seed {seed}. Code is the task view the models received "
             "(pre-state method for add_log, remove_log and change_level; for add_log_post the post-state with "
             "the added statements masked).", ""]
    rng = np.random.default_rng(seed)
    for title, df in sets:
        lines += [f"## {title} ({len(df)} instances)", ""]
        if not len(df):
            lines += ["(none)", ""]
            continue
        df = df.sort_values("instance_id").reset_index(drop=True)
        keys = [c for c in ("perf_part", "wrong_error") if c in df]
        if keys:
            counts = df.groupby(keys, dropna=False).size()
            lines += ["Strata: " + "; ".join(f"{' / '.join(map(str, k if isinstance(k, tuple) else (k,)))} {v}"
                                             for k, v in counts.items()), ""]
        pick = stratified_pick(df, keys, n_examples, rng) if keys else sorted(
            rng.choice(len(df), size=min(n_examples, len(df)), replace=False).tolist())
        for i in pick:
            r = df.iloc[i]
            inst = td.instances.get(r["instance_id"])
            score_cols = [c for c in df.columns if c.startswith("score_")]
            lines.append(f"### {r['instance_id']}")
            lines.append("")
            lines.append(f"- repo `{r.get('repo')}`, commit `{str(r.get('commit_id'))[:12]}`, "
                         f"file `{r.get('pre_path') or r.get('post_path')}`")
            lines.append(f"- method `{r.get('class_path')}.{r.get('method_name')}`, label {int(r['label'])}, "
                         + ", ".join(f"{c[6:]} score {r[c]:.3f}" for c in score_cols))
            lines.append(f"- stratum `{r.get('perf_part')}` / wrong model's error `{r.get('wrong_error')}`, context "
                         f"`{r.get('d_ctx_category')}`, anchor level `{r.get('anchor_level')}`")
            view = None
            if inst is not None:
                try:
                    view = view_loader(inst)
                except Exception:
                    view = None
            if view is None:
                lines += ["", "(view could not be rebuilt)", ""]
                continue
            if inst.get("view") == "post_masked":
                for line_no, text in masked_statements(inst):
                    lines.append(f"- masked (added in this commit), line {line_no}: `{text}`")
            lines += ["", "```java", method_source(view), "```", ""]
    return "\n".join(lines) + "\n"


def error_analysis(td, out_dir, view_loader=None, n_examples=15, a=FULL_MODEL, b=REFERENCE, sfx=""):
    """Confusion counts (ERROR_MODELS), FP/FN-rate gaps subset - complement, agreement and
    disagreement sets (CSV) and stratified examples (Markdown) of a vs b for one task.

    sfx is the setting suffix of a non-primary run, so it never overwrites the primary files.
    """
    if a not in td.models or b not in td.models:
        notice(f"{td.setting}/{td.task}: error analysis needs {a} and {b}, skipped")
        return None
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    models = [m for m in ERROR_MODELS if m in td.models]
    conf = confusion_by(td, models, ["d_ctx_category", "perf_part"])
    gap = error_rate_gap(td, models)
    only_a, only_b, _ = disagreement_sets(td, a, b)
    only_a.to_csv(out_dir / f"{td.task}_only_{a}_correct{sfx}.csv", index=False)
    only_b.to_csv(out_dir / f"{td.task}_only_{b}_correct{sfx}.csv", index=False)
    md = examples_markdown(td, [(f"Only {a} correct", only_a), (f"Only {b} correct", only_b)],
                           view_loader, n_examples)
    with open(out_dir / f"{td.task}_examples{sfx}.md", "w", encoding="utf-8") as f:
        f.write(md)
    summary = {"setting": td.setting, "task": td.task, **agreement(td, a, b)}
    if "perf_part" in td.meta:
        for part in ("subset", "complement"):
            sel = (td.meta["perf_part"] == part).to_numpy()
            summary[f"only_{a}_correct_{part}"] = int(only_a["instance_id"].isin(td.ids[sel]).sum())
            summary[f"only_{b}_correct_{part}"] = int(only_b["instance_id"].isin(td.ids[sel]).sum())
    return {"confusion": conf, "summary": summary, "rate_gap": gap}


# figure data

def pr_curve_data(td, models=CURVE_MODELS):
    from src.evaluation.metrics import pr_curve
    out = {}
    for m in models:
        if m not in td.models:
            continue
        md = td.models[m]
        j = md["seeds"].index(0) if 0 in md["seeds"] else 0
        sel = md["cover"]
        prec, rec = pr_curve(td.y[sel], md["score"][j, sel])
        out[m] = (prec, rec)
    return out
