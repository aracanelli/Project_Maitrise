"""
Stage 5: one row of tabular features per instance of data/processed/instances/<task>.jsonl.

Views are rebuilt with src.dataset.views.load_view, so features and graphs describe the
same code and share the masking of post_masked views (add_log_post). Which code a feature
sees depends on the instance's view, not on the task name; only the s_ columns are tied
to the statement tasks. History features are computed in the main process from the
mining tables; the code features run in worker processes, with the instances that share
a file version sent to the same worker so views.py can reuse the parsed file. Outputs, per
task, in data/processed/features/: <task>.csv (instance_id plus feature columns),
<task>_groups.json (column to group prefix), <task>_failures.jsonl and <task>_summary.json.

No feature reads the label fields of an instance (label, sample_role, neg_rank, in_R*).
The summary records the sha1 of the instances file and of every mining table read, and
for post_masked views how often a view has more empty bodies or unreferenced locals than
its pre-state method, for masked and unmasked views (masking_traces). That count is a
diagnostic of the views.py masking and never a feature.
"""

import json
import multiprocessing as mp
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from src.common.config import DATA
from src.dataset import views
from src.features.domain import domain_indicators
from src.features.file_features import FILE_COLUMNS, file_features, dominant_from_columns
from src.features.history_features import HISTORY_COLUMNS, build_history_index, history_features, read_table
from src.features.method_features import (
    METHOD_COLUMNS, LOG_COLUMNS, LEXICAL_COLUMNS,
    method_features, log_context_features, lexical_features, dominant_level, block_is_empty,
)
from src.features.statement_features import STATEMENT_COLUMNS, statement_features
from src.parsing.method_units import find_unit
from src.parsing.srcml_parser import SRC

TASKS = ("add_log", "add_log_post", "remove_log", "change_level", "multiclass")
STATEMENT_TASKS = ("remove_log", "change_level")
DOMAIN_COLUMNS = list(domain_indicators(None, "", "", "").keys())
TRACE_BODY_TAGS = (SRC + "for", SRC + "while", SRC + "do", SRC + "lambda", SRC + "synchronized",
                   SRC + "try", SRC + "catch", SRC + "finally")

INSTANCES_DIR = DATA / "processed" / "instances"
MINING_DIR = DATA / "interim" / "mining"
FEATURES_DIR = DATA / "processed" / "features"


def feature_columns(task):
    cols = HISTORY_COLUMNS + FILE_COLUMNS + METHOD_COLUMNS + LOG_COLUMNS
    if task in STATEMENT_TASKS:
        cols = cols + STATEMENT_COLUMNS
    return cols + DOMAIN_COLUMNS + LEXICAL_COLUMNS


def column_groups(columns):
    return {c: c.split("_", 1)[0] for c in columns}


def view_features(view, task, file_cache=None):
    inst = view.instance
    unit = view.unit
    key = (inst["repo"], inst["pre_blob"])
    f = file_cache.get(key) if file_cache is not None else None
    if f is None:
        f = file_features(view.file_pre)
        if file_cache is not None:
            file_cache[key] = f

    m = method_features(unit)
    feats = {}
    feats.update(f)
    feats.update(m)
    feats.update(log_context_features(unit, m["m_loc"]))
    if task in STATEMENT_TASKS:
        if view.anchor is None:
            raise ValueError("statement task instance without anchor")
        feats.update(statement_features(
            unit, view.anchor, dominant_level(unit.formal_logs),
            dominant_from_columns(f, "f"), f["f_mean_level_ord"],
        ))
    if inst.get("view") == "post_masked":
        path = inst.get("post_path")
    else:
        path = inst.get("pre_path")
    feats.update(domain_indicators(unit.element, unit.name, unit.class_path, path or ""))
    feats.update(lexical_features(unit.element))
    return feats


def masking_traces(unit_el):
    """(empty bodies, unreferenced locals) of a unit: a diagnostic, not a feature.

    Empty bodies are those of loops, lambdas, synchronized, try, catch and finally blocks
    and then-branches before an else; views.py removes every such body that masking
    empties, so a masked view should not have more of them than its pre-state method.
    The method's own body is not counted (masking keeps it, see mask_residue of stage 6).
    """
    empty = 0
    for el in unit_el.iter(*TRACE_BODY_TAGS):
        block = el.find(SRC + "block")
        if block is not None and block_is_empty(block):
            empty += 1
    for if_stmt in unit_el.iter(SRC + "if_stmt"):
        branches = [c for c in if_stmt if c.tag in (SRC + "if", SRC + "else")]
        if len(branches) > 1 and block_is_empty(branches[0].find(SRC + "block")):
            empty += 1
    uses = Counter(n.text for n in unit_el.iter(SRC + "name") if n.text)
    unreferenced = 0
    for stmt in unit_el.iter(SRC + "decl_stmt"):
        for decl in stmt.findall(SRC + "decl"):
            name = decl.find(SRC + "name")
            if name is not None and name.text and uses[name.text] <= 1:
                unreferenced += 1
    return empty, unreferenced


def trace_record(view):
    """Compare a post-state view with its pre-state method (None if that is not found)."""
    inst = view.instance
    class_pre = inst.get("class_path_pre") or inst["class_path"]
    pre_unit = find_unit(view.file_pre, inst.get("pre_ordinal"), inst["signature_pre"], class_pre)
    if pre_unit is None:
        return None
    a = masking_traces(view.unit.element)
    b = masking_traces(pre_unit.element)
    # by the mask fields: positives are masked, negatives (empty masks) never are
    masked = bool(inst.get("mask_post_idx") or inst.get("mask_post_all_idx"))
    return {"repo": inst["repo"], "masked": masked,
            "more_empty_bodies": a[0] > b[0], "more_unreferenced_locals": a[1] > b[1]}


def trace_summary(traces):
    out = {}
    for t in traces:
        repo = out.setdefault(t["repo"], {})
        side = repo.setdefault("masked" if t["masked"] else "unmasked",
                               {"n": 0, "more_empty_bodies": 0, "more_unreferenced_locals": 0})
        side["n"] += 1
        side["more_empty_bodies"] += int(t["more_empty_bodies"])
        side["more_unreferenced_locals"] += int(t["more_unreferenced_locals"])
    return dict(sorted(out.items()))


def failure_reason(inst):
    """Re-run the checks of load_view to say why a view could not be rebuilt."""
    repo = inst["repo"]
    try:
        pre = views.parse_blob(repo, inst["pre_blob"])
    except Exception as e:
        return f"pre_blob unreadable: {type(e).__name__}"
    if pre is None:
        return "pre_blob parse failed"
    if inst.get("view") == "post_masked":
        try:
            post = views.parse_blob(repo, inst["post_blob"])
        except Exception as e:
            return f"post_blob unreadable: {type(e).__name__}"
        if post is None:
            return "post_blob parse failed"
        unit = find_unit(post, inst.get("post_ordinal"), inst["signature_post"], inst["class_path"])
        if unit is None:
            return "post unit not found"
        have = {log.formal_index for log in unit.formal_logs}
        missing = sorted(set(inst.get("mask_post_idx") or []) - have)
        if missing:
            return f"mask_post_idx not in unit: {missing}"
        missing = sorted(set(inst.get("mask_post_all_idx") or []) - {log.index for log in unit.logs})
        if missing:
            return f"mask_post_all_idx not in unit: {missing}"
        return "unknown"
    class_pre = inst.get("class_path_pre") or inst["class_path"]
    unit = find_unit(pre, inst.get("pre_ordinal"), inst["signature_pre"], class_pre)
    if unit is None:
        return "pre unit not found"
    idx = inst.get("anchor_pre_idx")
    if idx is not None and idx not in {log.formal_index for log in unit.formal_logs}:
        return f"anchor_pre_idx not in unit: {idx}"
    return "unknown"


def failure_record(inst, reason):
    return {
        "instance_id": inst["instance_id"],
        "repo": inst.get("repo"),
        "commit_id": inst.get("commit_id"),
        "label": inst.get("label"),
        "reason": reason,
    }


def extract_chunk(job):
    task, instances = job
    rows = []
    failures = []
    traces = []
    file_cache = {}
    last_group = None
    for inst in instances:
        # chunks hold whole groups in order, so only the current group's parse is reused;
        # dropping the rest bounds memory (a parsed tree is ~150x its source)
        if group_key(inst) != last_group:
            last_group = group_key(inst)
            views._parse_cache.clear()
            file_cache.clear()
        view = None
        reason = None
        try:
            view = views.load_view(inst)
        except Exception as e:
            reason = f"load_view error: {type(e).__name__}: {e}"
        if view is None:
            failures.append(failure_record(inst, reason or failure_reason(inst)))
            continue
        try:
            feats = view_features(view, task, file_cache)
        except Exception as e:
            failures.append(failure_record(inst, f"feature error: {type(e).__name__}: {e}"))
            continue
        feats["instance_id"] = inst["instance_id"]
        rows.append(feats)
        if inst.get("view") == "post_masked":
            rec = trace_record(view)
            if rec is not None:
                traces.append(rec)
    return rows, failures, traces


def group_key(inst):
    blob = inst.get("post_blob") if inst.get("view") == "post_masked" else inst.get("pre_blob")
    return inst["repo"], blob or "", inst.get("pre_blob") or ""


def make_chunks(instances, workers):
    groups = defaultdict(list)
    for inst in instances:
        groups[group_key(inst)].append(inst)
    target = max(10, len(instances) // max(workers * 8, 1))
    chunks = []
    current = []
    for key in sorted(groups):
        current.extend(groups[key])
        if len(current) >= target:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def load_instances(task, instances_dir):
    path = Path(instances_dir) / f"{task}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"instances not found: {path}")
    instances, sha1 = read_table(path)
    instances.sort(key=lambda r: r["instance_id"])
    ids = [r["instance_id"] for r in instances]
    if len(ids) != len(set(ids)):
        dup = [k for k, n in Counter(ids).items() if n > 1][:5]
        raise ValueError(f"duplicate instance_id in {path}: {dup}")
    return instances, sha1


def output_dir(out_dir=None, limit=None):
    """data/processed/features/ only holds full runs (the model stage reads it); a --limit
    run goes to features/limit<N>/ unless another folder is given."""
    if out_dir is None:
        return Path(FEATURES_DIR) / f"limit{limit}" if limit else Path(FEATURES_DIR)
    out_dir = Path(out_dir)
    if limit and out_dir.resolve() == Path(FEATURES_DIR).resolve():
        raise ValueError(f"{FEATURES_DIR} holds only full runs; got limit={limit}")
    return out_dir


def extract_task(task, workers=16, limit=None, instances_dir=INSTANCES_DIR,
                 mining_dir=MINING_DIR, out_dir=None, verbose=True):
    if task not in TASKS:
        raise ValueError(f"unknown task {task}")
    out_dir = output_dir(out_dir, limit)
    t0 = time.time()
    instances, instances_sha1 = load_instances(task, instances_dir)
    if limit:
        instances = instances[:limit]

    inputs = {f"instances/{task}.jsonl": instances_sha1}
    lineage_reuse = {}
    hist = {}
    for repo in sorted({inst["repo"] for inst in instances}):
        idx = build_history_index(repo, mining_dir)
        for name, sha in idx["inputs_sha1"].items():
            inputs[f"mining/{repo}/{name}"] = sha
        lineage_reuse[repo] = idx["lineage_reuse"]
        for inst in instances:
            if inst["repo"] == repo:
                hist[inst["instance_id"]] = history_features(idx, inst)
        del idx
    if verbose:
        print(f"[{task}] {len(instances)} instances, history done in {time.time() - t0:.1f}s")

    chunks = make_chunks(instances, workers)
    rows = []
    failures = []
    traces = []
    if workers <= 1:
        for ch in chunks:
            r, f, tr = extract_chunk((task, ch))
            rows.extend(r)
            failures.extend(f)
            traces.extend(tr)
    else:
        ctx = mp.get_context("spawn")
        done = 0
        step = max(len(chunks) // 20, 1)
        with ctx.Pool(workers) as pool:
            for i, (r, f, tr) in enumerate(pool.imap_unordered(extract_chunk, [(task, ch) for ch in chunks])):
                rows.extend(r)
                failures.extend(f)
                traces.extend(tr)
                done += len(r) + len(f)
                if verbose and (i + 1) % step == 0:
                    print(f"[{task}] {done}/{len(instances)} ({time.time() - t0:.0f}s, {len(failures)} failures)")

    columns = feature_columns(task)
    allowed = set(columns) | {"instance_id"}
    for row in rows:
        row.update(hist[row["instance_id"]])
        extra = set(row) - allowed
        if extra:
            raise RuntimeError(f"feature keys missing from the column list: {sorted(extra)}")
    rows.sort(key=lambda r: r["instance_id"])
    failures.sort(key=lambda r: r["instance_id"])

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["instance_id"] + columns)
    df.to_csv(out_dir / f"{task}.csv", index=False)
    with open(out_dir / f"{task}_groups.json", "w", encoding="utf-8") as f:
        json.dump(column_groups(columns), f, indent=1)
    with open(out_dir / f"{task}_failures.jsonl", "w", encoding="utf-8") as f:
        for rec in failures:
            f.write(json.dumps(rec) + "\n")

    per_repo = defaultdict(lambda: {"rows": 0, "failures": 0})
    repo_of = {inst["instance_id"]: inst["repo"] for inst in instances}
    for row in rows:
        per_repo[repo_of[row["instance_id"]]]["rows"] += 1
    for rec in failures:
        per_repo[rec["repo"]]["failures"] += 1
    nan_cols = {c: int(df[c].isna().sum()) for c in columns if df[c].isna().any()}
    summary = {
        "task": task,
        "n_instances": len(instances),
        "n_rows": len(rows),
        "n_failures": len(failures),
        "failure_reasons": dict(Counter(rec["reason"].split(":")[0] for rec in failures)),
        "per_repo": dict(sorted(per_repo.items())),
        "n_feature_columns": len(columns),
        "nan_counts": nan_cols,
        "inputs_sha1": inputs,
        "history_lineage_reuse": lineage_reuse,
        "workers": workers,
        "limit": limit,
        "elapsed_s": round(time.time() - t0, 1),
    }
    if any(inst.get("view") == "post_masked" for inst in instances):
        summary["masking_traces"] = trace_summary(traces)
    with open(out_dir / f"{task}_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    if verbose:
        print(f"[{task}] wrote {len(rows)} rows, {len(failures)} failures in {summary['elapsed_s']}s -> {out_dir}")
    return df, failures, summary
