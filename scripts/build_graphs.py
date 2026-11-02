"""
Stage 6: build one typed graph per instance.

Reads data/processed/instances/<task>.jsonl, keeps the instances of one sample setting
(in_R4 by default: the graph models only run on the primary setting), rebuilds each view
with src.dataset.views.load_view and writes to data/processed/graphs/:
    <task>.npz, <task>_index.csv, <task>_meta.json, <task>_failures.jsonl

Instances that share a file version go to the same worker, as in the features stage, so
views.py parses each pre-state file once. Results are sorted by instance_id, so the
outputs do not depend on the number of workers. A run is skipped when the existing
outputs came from the same instances file, settings and graph code (--overwrite forces it).

data/processed/graphs/ only holds the primary build (R4, no --limit, no message words)
that the model stage reads. Any other run goes to a subfolder named after its settings
(graphs/R1/, graphs/R4_limit100/, ...) unless --out-dir is given.

Graphs are anchored on the instance's anchor statement when it has one (REMOVE_LOG,
CHANGE_LEVEL) and on the METHOD node otherwise (ADD_LOG, add_log_post). For post_masked
views (add_log_post) the meta also lists the positives where masking emptied a body that
is not empty in the unmasked method, since such an empty block would reveal the label.

Usage:
    python -m scripts.build_graphs --task add_log [--setting R4] [--workers 16] [--limit N]
    python -m scripts.build_graphs --task all [--overwrite] [--message-words]
"""

import argparse
import hashlib
import json
import multiprocessing as mp
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from src.common.config import DATA, ROOT, load_config
from src.dataset import views
from src.features.lexical import N_BUCKETS
from src.graphs.builder import (
    NODE_TYPES, EDGE_TYPES, REVERSE, NUMERIC_FEATURES, MAX_TOKENS, build_instance_graph, empty_blocks
)
from src.graphs.serialize import GRAPH_DIR, paths, save_graphs
from src.parsing.method_units import find_unit

TASKS = ("add_log", "add_log_post", "remove_log", "change_level")
SETTINGS = ("R1", "R4", "R10")
INSTANCES_DIR = DATA / "processed" / "instances"
# everything that decides graph content: detection decides LOG_STMT / PRINT_STMT and levels
CODE_FILES = ["src/graphs/builder.py", "src/graphs/serialize.py", "scripts/build_graphs.py",
              "src/dataset/views.py", "src/parsing/method_units.py", "src/parsing/srcml_parser.py",
              "src/detection/log_detection.py", "src/detection/verbosity.py", "src/features/lexical.py"]


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_sha1():
    h = hashlib.sha1()
    for rel in CODE_FILES:
        h.update(rel.encode())
        h.update(sha1_file(ROOT / rel).encode())
    return h.hexdigest()


def load_instances(path, setting):
    instances = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                inst = json.loads(line)
                if inst.get(f"in_{setting}"):
                    instances.append(inst)
    instances.sort(key=lambda r: r["instance_id"])
    ids = [r["instance_id"] for r in instances]
    if len(ids) != len(set(ids)):
        dup = [k for k, n in Counter(ids).items() if n > 1][:5]
        raise ValueError(f"duplicate instance_id in {path}: {dup}")
    return instances


# same grouping as the features stage (src/features/extract.py)
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


def failure_reason(inst):
    """Why load_view returned None (same checks, same wording as the features stage)."""
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
        missing = sorted(set(inst.get("mask_post_idx") or []) - {l.formal_index for l in unit.formal_logs})
        if missing:
            return f"mask_post_idx not in unit: {missing}"
        missing = sorted(set(inst.get("mask_post_all_idx") or []) - {l.index for l in unit.logs})
        if missing:
            return f"mask_post_all_idx not in unit: {missing}"
        return "unknown"
    class_pre = inst.get("class_path_pre") or inst["class_path"]
    unit = find_unit(pre, inst.get("pre_ordinal"), inst["signature_pre"], class_pre)
    if unit is None:
        return "pre unit not found"
    idx = inst.get("anchor_pre_idx")
    if idx is not None and idx not in {l.formal_index for l in unit.formal_logs}:
        return f"anchor_pre_idx not in unit: {idx}"
    return "unknown"


def mask_residue(inst, view):
    """Parent types of the empty BLOCKs that masking added to a post_masked view.

    The masked view is compared with the same post-state unit before masking, so a body
    that was already empty in the developer's code is not counted. Only positives are
    masked, so negatives have no residue; pre views are never masked.
    """
    if not view.masked:
        return []
    post = views.parse_blob(inst["repo"], inst["post_blob"])
    unit = find_unit(post, inst.get("post_ordinal"), inst["signature_post"], inst["class_path"])
    after = empty_blocks(view.unit)
    before = empty_blocks(unit) if unit is not None else {}
    out = []
    for kind in sorted(after):
        out.extend([kind] * max(after[kind] - before.get(kind, 0), 0))
    return out


def build_chunk(job):
    max_nodes, message_words, instances = job
    out = []
    for inst in instances:
        graph, reason, extra = None, None, None
        try:
            view = views.load_view(inst)
        except Exception as e:
            view = None
            reason = f"load_view error: {type(e).__name__}: {e}"
        if view is None:
            reason = reason or failure_reason(inst)
        else:
            try:
                graph = build_instance_graph(view, max_nodes, message_words=message_words)
                if inst.get("view") == "post_masked":
                    extra = {"empty": sorted(empty_blocks(view.unit)), "residue": mask_residue(inst, view)}
            except Exception as e:
                graph = None
                reason = f"graph error: {type(e).__name__}: {e}"
        out.append((inst["instance_id"], graph, reason, extra))
    return out


def describe(values):
    if not values:
        return {"mean": None, "median": None, "p95": None, "max": None}
    a = np.array(values, dtype=np.float64)
    return {"mean": round(float(a.mean()), 2), "median": float(np.median(a)),
            "p95": round(float(np.percentile(a, 95)), 2), "max": int(a.max())}


def group_stats(rows, n_failures):
    nodes = [r["n_nodes"] for r in rows]
    edges = [r["n_edges"] for r in rows]
    return {
        "n_graphs": len(rows),
        "n_pos": sum(1 for r in rows if r["label"] == 1),
        "nodes": describe(nodes),
        "edges": describe(edges),
        "nodes_before_truncation_max": max((r["n_nodes_full"] for r in rows), default=None),
        "truncated": sum(r["truncated"] for r in rows),
        "failures": n_failures,
    }


def build_stats(instances, graphs, ids, failures):
    by_id = {inst["instance_id"]: inst for inst in instances}
    rows = defaultdict(list)
    for iid, g in zip(ids, graphs):
        rows[by_id[iid]["repo"]].append({
            "label": by_id[iid].get("label"), "n_nodes": len(g["node_type"]),
            "n_edges": g["edge_index"].shape[1], "n_nodes_full": g["n_nodes_full"], "truncated": g["truncated"],
        })
    fails = Counter(rec["repo"] for rec in failures)
    per_repo = {}
    for repo in sorted(set(rows) | set(fails)):
        per_repo[repo] = group_stats(rows.get(repo, []), fails.get(repo, 0))
    every = [r for repo in sorted(rows) for r in rows[repo]]
    return {"all": group_stats(every, len(failures)), "per_repo": per_repo}


def type_counts(graphs):
    nodes = Counter()
    edges = Counter()
    for g in graphs:
        nodes.update(g["node_type"].tolist())
        edges.update(g["edge_type"].tolist())
    return ({NODE_TYPES[k]: nodes[k] for k in sorted(nodes)},
            {EDGE_TYPES[k]: edges[k] for k in sorted(edges)})


def residue_stats(by_id, extras):
    """Masking residue of post_masked views: positives whose view has an emptied body that
    the unmasked method does not have, and how many graphs of each label hold an empty
    block at all. A METHOD entry is a method body emptied by masking, which views.py keeps."""
    instances = {}
    by_container = Counter()
    per_repo = Counter()
    empty_by_label = defaultdict(Counter)
    for iid in sorted(extras):
        inst = by_id[iid]
        for kind in extras[iid]["empty"]:
            empty_by_label[str(inst.get("label"))][kind] += 1
        residue = extras[iid]["residue"]
        if residue:
            instances[iid] = residue
            per_repo[inst["repo"]] += 1
            by_container.update(sorted(set(residue)))
    return {
        "definition": "BLOCK nodes without statements added by masking, by parent node type "
                      "(view vs. the same unit before masking)",
        "n_instances": len(instances),
        "n_instances_non_catch": sum(1 for kinds in instances.values() if any(k != "CATCH" for k in kinds)),
        "n_instances_non_method": sum(1 for kinds in instances.values() if any(k != "METHOD" for k in kinds)),
        "instances_by_container": dict(sorted(by_container.items())),
        "per_repo": dict(sorted(per_repo.items())),
        "graphs_with_empty_block_by_label": {lab: dict(sorted(c.items())) for lab, c in sorted(empty_by_label.items())},
        "instances": instances,
    }


def anchor_target(instances):
    anchored = {inst.get("anchor_pre_idx") is not None for inst in instances}
    if anchored == {True}:
        return "LOG_STMT of anchor_pre_idx"
    if anchored == {False}:
        return "METHOD"
    return "LOG_STMT of anchor_pre_idx, METHOD for instances without one"


def output_dir(out_dir=None, setting="R4", limit=None, message_words=False):
    """data/processed/graphs/ is reserved for the primary build that the model stage reads."""
    primary = setting == "R4" and not limit and not message_words
    if out_dir is None:
        if primary:
            return Path(GRAPH_DIR)
        name = setting + (f"_limit{limit}" if limit else "") + ("_msgwords" if message_words else "")
        return Path(GRAPH_DIR) / name
    out_dir = Path(out_dir)
    if not primary and out_dir.resolve() == Path(GRAPH_DIR).resolve():
        raise ValueError(f"{GRAPH_DIR} holds only the primary build (R4, no limit, no message words); "
                         f"got setting={setting}, limit={limit}, message_words={message_words}")
    return out_dir


def up_to_date(p, expected):
    if not all(p[k].exists() for k in ("npz", "index", "meta", "failures")):
        return False
    try:
        with open(p["meta"], encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return False
    return all(meta.get(k) == v for k, v in expected.items())


def build_task(task, setting="R4", workers=16, limit=None, instances_dir=INSTANCES_DIR,
               out_dir=None, overwrite=False, message_words=False, verbose=True):
    t0 = time.time()
    inst_path = Path(instances_dir) / f"{task}.jsonl"
    if not inst_path.exists():
        raise FileNotFoundError(f"instances not found: {inst_path}")
    max_nodes = load_config("experiment")["models"]["gnn"]["max_nodes"]
    out_dir = output_dir(out_dir, setting, limit, message_words)
    p = paths(task, out_dir)
    expected = {"task": task, "setting": setting, "limit": limit, "max_nodes": max_nodes,
                "log_message_words": message_words,
                "instances_sha1": sha1_file(inst_path), "code_sha1": code_sha1()}
    if not overwrite and up_to_date(p, expected):
        if verbose:
            print(f"[{task}] graphs up to date ({p['npz']}), skipped")
        return None

    instances = load_instances(inst_path, setting)
    n_candidates = len(instances)
    if limit:
        instances = instances[:limit]
    if verbose:
        print(f"[{task}] {len(instances)} instances in {setting} (of {n_candidates}), max_nodes={max_nodes} -> {out_dir}")

    chunks = make_chunks(instances, workers)
    results = []
    if workers <= 1 or len(chunks) <= 1:
        for ch in chunks:
            results.extend(build_chunk((max_nodes, message_words, ch)))
    else:
        ctx = mp.get_context("spawn")
        step = max(len(chunks) // 20, 1)
        with ctx.Pool(min(workers, len(chunks))) as pool:
            for i, res in enumerate(pool.imap_unordered(build_chunk, [(max_nodes, message_words, ch) for ch in chunks])):
                results.extend(res)
                if verbose and (i + 1) % step == 0:
                    n_fail = sum(1 for r in results if r[1] is None)
                    print(f"[{task}] {len(results)}/{len(instances)} ({time.time() - t0:.0f}s, {n_fail} failures)")
    results.sort(key=lambda r: r[0])

    by_id = {inst["instance_id"]: inst for inst in instances}
    masked_view = any(inst.get("view") == "post_masked" for inst in instances)
    ids, graphs, failures, extras = [], [], [], {}
    for iid, g, reason, extra in results:
        if g is None:
            inst = by_id[iid]
            failures.append({"instance_id": iid, "repo": inst.get("repo"), "commit_id": inst.get("commit_id"),
                             "label": inst.get("label"), "reason": reason})
        else:
            ids.append(iid)
            graphs.append(g)
            if extra is not None:
                extras[iid] = extra

    node_counts, edge_counts = type_counts(graphs)
    meta = dict(expected)
    meta.update({
        "instances_file": (inst_path.relative_to(ROOT) if inst_path.is_relative_to(ROOT) else inst_path).as_posix(),
        "n_candidates": n_candidates,
        "n_instances": len(instances),
        "n_graphs": len(graphs),
        "n_failures": len(failures),
        "node_types": NODE_TYPES,
        "edge_types": EDGE_TYPES,
        "reverse_edge_types": REVERSE,
        "numeric_features": NUMERIC_FEATURES,
        "n_token_buckets": N_BUCKETS,
        "max_tokens_per_node": MAX_TOKENS,
        "anchor_target": anchor_target(instances),
        "edges_counted": "n_edges and edge stats include the reverse edges",
        "stats": build_stats(instances, graphs, ids, failures),
        "node_type_counts": node_counts,
        "edge_type_counts": edge_counts,
        "failure_reasons": dict(Counter(rec["reason"].split(":")[0] for rec in failures)),
        "mask_residue": residue_stats(by_id, extras) if masked_view else None,
        "elapsed_seconds": round(time.time() - t0, 1),
    })
    # old meta removed first and new meta written last: an interrupted run is never up to date
    p["meta"].unlink(missing_ok=True)
    p["failures"].parent.mkdir(parents=True, exist_ok=True)
    with open(p["failures"], "w", encoding="utf-8") as f:
        for rec in failures:
            f.write(json.dumps(rec) + "\n")
    save_graphs(task, graphs, ids, meta, len(NUMERIC_FEATURES), out_dir)

    if verbose:
        s = meta["stats"]["all"]
        print(f"[{task}] {len(graphs)} graphs, {len(failures)} failures, nodes mean={s['nodes']['mean']} "
              f"p95={s['nodes']['p95']} max={s['nodes']['max']}, truncated={s['truncated']}, "
              f"{meta['elapsed_seconds']}s -> {p['npz']}")
        if meta["mask_residue"] is not None:
            r = meta["mask_residue"]
            print(f"[{task}] masking left an empty body in {r['n_instances']} graphs "
                  f"({r['n_instances_non_method']} other than the method body): {r['instances_by_container']}")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=list(TASKS) + ["all"])
    ap.add_argument("--setting", default="R4", choices=SETTINGS)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--instances-dir", default=str(INSTANCES_DIR))
    ap.add_argument("--out-dir", default=None,
                    help="default: data/processed/graphs/ for the primary build, else a subfolder named after the settings")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--message-words", action="store_true",
                    help="ablation: add string-literal words to LOG_STMT / PRINT_STMT tokens (x_ does not see them)")
    args = ap.parse_args()

    tasks = TASKS if args.task == "all" else [args.task]
    for task in tasks:
        if args.task == "all" and not (Path(args.instances_dir) / f"{task}.jsonl").exists():
            print(f"[{task}] no instances file, skipped")
            continue
        build_task(task, args.setting, args.workers, args.limit, args.instances_dir, args.out_dir,
                   args.overwrite, message_words=args.message_words)


if __name__ == "__main__":
    main()
