"""
Per-repository mining run (stage 3): commits -> Java file diffs -> method pairs -> events.

Writes data/interim/mining/<repo>/{commits,file_changes,methods_changed,events,
aux_changes,parse_failures}.jsonl and summary.json.

The replication package of Zeng et al. (2019), logdetector/detector.py (detect_project),
walks the commits one by one and writes to PostgreSQL. Here the non-merge commits are cut into chunks that are
contiguous in topo order (so a worker's blob cache sees the next version of the same
files), mined in a multiprocessing pool, and merged back in topo order. The output does
not depend on the number of workers or the chunk size.

A commit whose mining raises (git or parser error) contributes no rows; its commits.jsonl
row gets mining_error and summary.json counts it under commit_errors, so a partial run
is never mistaken for a complete one (scripts/mine_history.py exits non-zero).

All files are written into <out>.tmp (summary.json last) and that directory replaces <out>
only once it is complete. An interrupted run leaves the previous <out> untouched next to
an incomplete <out>.tmp, which the next run deletes. If the swap itself fails, the previous
<out> is moved back before the error is raised. Only a folder that is a mining output of
the same repository (the six tables and summary.json, nothing else) is ever replaced.
"""

import git
import json
import os
import shutil
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from pathlib import Path

from src.common.config import load_config
from src.mining import method_differ
from src.mining.git_walker import (
    open_repo, list_commits, java_changes, is_java, is_test_path, is_generated_path
)
from src.mining.history import commit_records, file_changes
from src.mining.method_differ import (
    load_blobs, diff_file, mark_relocations, validity_status, method_row
)

EVENT_FIELDS = [
    "event_id", "repo", "commit_id", "parent_commit_id", "topo_index", "timestamp",
    "author_id", "is_bulk", "scope", "event_label", "logging_style", "framework",
    "file_path", "pre_path", "post_path", "class_path", "method_signature",
    "call_name", "call_text", "call_text_before", "pre_level", "post_level",
    "statement_continuity", "match_confidence", "pre_line", "post_line",
    "pre_formal_index", "post_formal_index", "is_relocated", "validity_status",
    "pre_ordinal", "post_ordinal", "relocation_kind",
]
COMMIT_FIELDS = ["repo", "commit_id", "parent_commit_id", "topo_index", "timestamp", "author_id", "is_bulk"]
TABLES = ["commits", "file_changes", "methods_changed", "events", "aux_changes", "parse_failures"]
OUTPUT_FILES = {f"{t}.jsonl" for t in TABLES} | {"summary.json"}
PREFETCH_BLOBS = 256   # blobs parsed together before the commits that need them are mined

_repos = {}


def _repo(repo_dir):
    if repo_dir not in _repos:
        _repos[repo_dir] = open_repo(repo_dir)
    return _repos[repo_dir]


def _mining_side(change):
    """(kind, pre_path, post_path, pre_blob, post_blob) as mined.

    A rename between a .java and a non-Java path is mined as a deletion / addition of
    the Java side.
    """
    ct = change["change_type"]
    old, new = change["old_path"], change["new_path"]
    if ct == "R" and not is_java(new):
        ct, new = "D", None
    elif ct == "R" and not is_java(old):
        ct, old = "A", None
    return (ct, old, new,
            change["old_blob"] if old else None,
            change["new_blob"] if new else None)


def _to_mine(change, params):
    """Mining side of a change, or None when the file is a test or generated (by path)."""
    side = _mining_side(change)
    kind, pre_path, post_path = side[:3]
    if is_test_path(post_path or pre_path):
        return None
    segments = params["generated_path_segments"]
    if is_generated_path(pre_path, segments) or is_generated_path(post_path, segments):
        return None
    return side


def blobs_needed(changes, params):
    shas = []
    for change in changes:
        side = _to_mine(change, params)
        if side is None:
            continue
        kind, _, _, pre_blob, post_blob = side
        if kind in ("M", "R") and pre_blob == post_blob:
            continue
        shas.extend(b for b in (pre_blob, post_blob) if b)
    return shas


def mine_commit(meta, params, changes, entries):
    """Mine one non-merge commit from its Java changes and the parsed blobs (load_blobs).

    Returns a dict with the rows of every output file.
    """
    is_bulk = (meta["is_root"] and params["root_commit_is_bulk"]) \
        or len(changes) > params["bulk_commit_java_files"]

    events, pairs, failures = [], [], []
    n_mined = 0
    for file_idx, change in enumerate(changes):
        side = _to_mine(change, params)
        if side is None:
            continue
        kind, pre_path, post_path, pre_blob, post_blob = side
        if kind in ("M", "R") and pre_blob == post_blob:
            n_mined += 1  # pure rename or mode change: nothing to compare
            continue

        pre = entries[pre_blob] if pre_blob else None
        post = entries[post_blob] if post_blob else None
        if (pre and pre["generated"]) or (post and post["generated"]):
            continue
        failed = False
        for which, entry, path, blob in (("pre", pre, pre_path, pre_blob), ("post", post, post_path, post_blob)):
            if entry is not None and entry["failure"]:
                failures.append({"repo": meta["repo"], "commit_id": meta["commit_id"], "path": path,
                                 "side": which, "reason": entry["failure"], "blob": blob})
                failed = True
        if failed:
            continue

        n_mined += 1
        file_events, file_pairs = diff_file(
            kind, pre_path, post_path,
            pre["units"] if pre else None, post["units"] if post else None,
            params["levenshtein_threshold"], params.get("payload_continuity_threshold", 0.7),
        )
        for e in file_events:
            e["_file"] = file_idx
        for p in file_pairs:
            p["file"] = {"pre_path": pre_path, "post_path": post_path, "pre_blob": pre_blob,
                         "post_blob": post_blob, "change_type": kind}
        events.extend(file_events)
        pairs.extend(file_pairs)

    mark_relocations(events, params.get("payload_continuity_threshold", 0.7))

    base = {k: meta[k] for k in COMMIT_FIELDS}
    base["is_bulk"] = is_bulk
    event_rows = []
    for n, e in enumerate(events):
        e["validity_status"] = validity_status(e, is_bulk)
        row = dict(base)
        row["event_id"] = f"{meta['repo']}:{meta['commit_id'][:12]}:{n}"
        row.update({k: v for k, v in e.items() if not k.startswith("_")})
        event_rows.append({k: row[k] for k in EVENT_FIELDS})

    method_rows, aux_rows = [], []
    for p in pairs:
        row = dict(base)
        row.update(p["file"])
        row.update(method_row(p))
        method_rows.append(row)
        for a in p["aux"]:
            aux = dict(base)
            aux.update(a)
            aux_rows.append(aux)

    return {
        "commit_id": meta["commit_id"],
        "n_java_files": len(changes),
        "n_java_mined": n_mined,
        "is_bulk": is_bulk,
        "diff": [(c["change_type"], c["old_path"], c["new_path"]) for c in changes],
        "events": event_rows,
        "methods": method_rows,
        "aux": aux_rows,
        "failures": failures,
    }


def _retry(fn, *args, attempts=3):
    """Call fn, retrying transient process failures (Windows can fail to start a git/srcML
    child under load, e.g. exit code 0xC0000142). Other errors are raised at once."""
    for k in range(attempts):
        try:
            return fn(*args)
        except (git.GitCommandError, OSError) as e:
            if k == attempts - 1:
                raise
            time.sleep(1 + 2 * k)


def _mine_chunk(args):
    repo_dir, metas, params = args
    repo = _repo(repo_dir)
    before = dict(method_differ.cache_stats)

    diffs = []
    for meta in metas:
        try:
            diffs.append(_retry(java_changes, repo, meta["commit_id"], meta["parent_commit_id"]))
        except Exception as e:
            diffs.append(e)

    results = []
    group = []
    group_shas = []
    for k, meta in enumerate(metas):
        if not isinstance(diffs[k], Exception):
            group_shas.extend(blobs_needed(diffs[k], params))
        group.append(k)
        if len(group_shas) < PREFETCH_BLOBS and k < len(metas) - 1:
            continue
        # parse the blobs of the whole group at once (srcML batches), then mine it
        try:
            entries = _retry(load_blobs, repo, group_shas, params["generated_header_markers"],
                             params["srcml_timeout_seconds"])
        except Exception as e:
            entries = e
        for i in group:
            meta = metas[i]
            try:
                if isinstance(diffs[i], Exception):
                    raise diffs[i]
                if isinstance(entries, Exception):
                    raise entries
                results.append(mine_commit(meta, params, diffs[i], entries))
            except Exception as e:
                # recorded and counted; the commit contributes no rows
                results.append({"commit_id": meta["commit_id"], "error": f"{type(e).__name__}: {e}"})
        group, group_shas = [], []

    stats = {k: method_differ.cache_stats[k] - before[k] for k in before}
    return results, stats


def _write(f, row):
    f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rename(src, dst, attempts=5):
    # on Windows OneDrive, an antivirus or the indexer can hold a fresh file for a moment
    for k in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if k == attempts - 1:
                raise
            time.sleep(1 + k)


def _replaceable(d, repo_name):
    """True when d is missing or is a mining output of repo_name: only the six tables and
    summary.json, whose repo (when the summary is there) is repo_name. Nothing else is
    ever deleted."""
    if not d.exists():
        return True
    if not d.is_dir() or not all(f.is_file() and f.name in OUTPUT_FILES for f in d.iterdir()):
        return False
    summary = d / "summary.json"
    if not summary.exists():
        return True
    try:
        return json.loads(summary.read_text(encoding="utf-8")).get("repo") == repo_name
    except (OSError, ValueError, AttributeError):
        return False


def _remove(d, log, attempts=3):
    """Delete the previous output; failing that, warn and leave it (the new output is complete)."""
    for k in range(attempts):
        try:
            shutil.rmtree(d)
            return True
        except OSError as e:
            if k == attempts - 1:
                log(f"warning: could not delete {d} ({e}); the new output is complete, delete it by hand")
                return False
            time.sleep(1 + k)


def _replace_dir(tmp_dir, out_dir, log=print):
    """Move the finished tmp_dir to out_dir; the previous out_dir is deleted only afterwards,
    and moved back if tmp_dir cannot take its place."""
    old_dir = out_dir.with_name(out_dir.name + ".old")
    if old_dir.exists():
        shutil.rmtree(old_dir)
    if out_dir.exists():
        _rename(out_dir, old_dir)
    try:
        _rename(tmp_dir, out_dir)
    except BaseException:
        if old_dir.exists() and not out_dir.exists():
            _rename(old_dir, out_dir)
        raise
    if old_dir.exists():
        _remove(old_dir, log)


def _nested_counts(counter):
    out = {}
    for (label, scope, style, validity), n in sorted(counter.items()):
        out.setdefault(label, {}).setdefault(scope, {}).setdefault(style, {})[validity] = n
    return out


def mine_repo(repo_name, repo_dir, head, out_dir, workers=16, max_commits=None,
              chunk_size=150, config=None, log=print):
    """Mine the history of one repository and write the stage-3 files. Returns the summary dict."""
    t0 = time.time()
    cfg = dict(load_config("extraction"))
    if config:
        cfg.update(config)
    params = {k: cfg[k] for k in ("bulk_commit_java_files", "root_commit_is_bulk", "levenshtein_threshold",
                                  "srcml_timeout_seconds", "generated_path_segments",
                                  "generated_header_markers")}
    params["payload_continuity_threshold"] = cfg.get("payload_continuity_threshold", 0.7)
    repo_dir = str(Path(repo_dir).resolve())
    final_dir = Path(out_dir).resolve()
    out_dir = final_dir.with_name(final_dir.name + ".tmp")
    for d in (final_dir, out_dir, final_dir.with_name(final_dir.name + ".old")):
        if not _replaceable(d, repo_name):
            raise ValueError(f"{d} is not a mining output of {repo_name} (the six tables and summary.json), "
                             f"it is not replaced: check --out, or delete it by hand")
    if out_dir.exists():
        shutil.rmtree(out_dir)   # left by an interrupted run
    out_dir.mkdir(parents=True)

    commits = list_commits(repo_dir, head)
    if max_commits:
        commits = commits[:max_commits]
    records = commit_records(repo_name, commits)
    by_sha = {r["commit_id"]: r for r in records}
    todo = [r for r in records if not r["is_merge"]]
    # about four chunks per worker so small repositories still use every worker
    chunk_size = min(chunk_size, max(10, -(-len(todo) // (max(workers, 1) * 4))))
    chunks = [todo[i:i + chunk_size] for i in range(0, len(todo), chunk_size)]
    tasks = [(repo_dir, chunk, params) for chunk in chunks]
    log(f"[{repo_name}] {len(records)} commits ({len(todo)} non-merge) in {len(chunks)} chunks, "
        f"{workers} workers")

    counts = Counter()
    by_pass = Counter()
    header_only = Counter()
    relocated = Counter()
    fail_reasons = Counter()
    errors = []
    perf = Counter()
    n_events = n_methods = n_aux = n_failures = 0
    mined_diffs = {}
    done = 0
    next_report = 500

    # the numstat log of the whole history runs in the background while the pool mines
    topo_index = {r["commit_id"]: r["topo_index"] for r in todo}
    background = ThreadPoolExecutor(max_workers=1)
    fc_future = background.submit(file_changes, repo_dir, repo_name, head, topo_index,
                                  params["generated_path_segments"])

    files = {name: open(out_dir / f"{name}.jsonl", "w", encoding="utf-8", errors="replace", newline="\n")
             for name in ("events", "methods_changed", "aux_changes", "parse_failures")}
    pool = Pool(workers) if workers > 1 else None
    try:
        results = pool.imap(_mine_chunk, tasks) if pool else map(_mine_chunk, tasks)
        for chunk_results, stats in results:
            perf.update(stats)
            for res in chunk_results:
                rec = by_sha[res["commit_id"]]
                if "error" in res:
                    errors.append({"commit_id": res["commit_id"], "error": res["error"]})
                    rec["mining_error"] = res["error"]
                    continue
                rec["n_java_files"] = res["n_java_files"]
                rec["n_java_mined"] = res["n_java_mined"]
                rec["is_bulk"] = res["is_bulk"]
                mined_diffs[res["commit_id"]] = res["diff"]
                for e in res["events"]:
                    _write(files["events"], e)
                    counts[(e["event_label"], e["scope"], e["logging_style"], e["validity_status"])] += 1
                    if e["is_relocated"]:
                        relocated[f"{e['logging_style']}|{e['relocation_kind']}"] += 1
                for m in res["methods"]:
                    _write(files["methods_changed"], m)
                    by_pass[m["match_pass"]] += 1
                    if not m["block_changed"]:
                        header_only[m["match_pass"]] += 1
                for a in res["aux"]:
                    _write(files["aux_changes"], a)
                for fl in res["failures"]:
                    _write(files["parse_failures"], fl)
                    fail_reasons[fl["reason"]] += 1
                n_events += len(res["events"])
                n_methods += len(res["methods"])
                n_aux += len(res["aux"])
                n_failures += len(res["failures"])
            done += len(chunk_results)
            if done >= next_report or done == len(todo):
                log(f"[{repo_name}] {done}/{len(todo)} commits, {n_events} events, "
                    f"{time.time() - t0:.0f}s")
                while next_report <= done:
                    next_report += 500
    finally:
        if pool:
            pool.close()
            pool.join()
        for f in files.values():
            f.close()

    with open(out_dir / "commits.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            _write(f, r)

    fc_rows = fc_future.result()
    background.shutdown()
    with open(out_dir / "file_changes.jsonl", "w", encoding="utf-8", errors="replace", newline="\n") as f:
        for r in fc_rows:
            _write(f, r)

    # the numstat log and the per-commit diffs must describe the same Java file changes
    from_log = {}
    for r in fc_rows:
        from_log.setdefault(r["commit_id"], []).append((r["change_type"], r["old_path"], r["new_path"]))
    mismatches = [sha for sha in mined_diffs
                  if sorted(mined_diffs[sha], key=str) != sorted(from_log.get(sha, []), key=str)]

    core = Counter()
    by_validity = Counter()
    for (label, scope, style, validity), n in counts.items():
        by_validity[(label, validity)] += n
        if validity == "core":
            core[label] += n
    summary = {
        "repo": repo_name,
        "head": head,
        "max_commits": max_commits,
        "n_commits": len(records),
        "n_merge": sum(r["is_merge"] for r in records),
        "n_non_merge": len(todo),
        "n_root": sum(r["is_root"] for r in records),
        "n_bulk": sum(bool(r["is_bulk"]) for r in records),
        "java_file_changes": sum(r["n_java_files"] or 0 for r in records),
        "java_files_mined": sum(r["n_java_mined"] or 0 for r in records),
        "file_changes_rows": len(fc_rows),
        "file_change_mismatch_commits": len(mismatches),
        "file_change_mismatch_examples": mismatches[:5],
        "blob_parses": perf["parses"],
        "blob_cache_hits": perf["hits"],
        "parse_seconds": round(perf["parse_seconds"], 1),
        "srcml_batch_fallbacks": perf["batch_fallbacks"],
        "parse_failures": n_failures,
        "parse_failures_by_reason": dict(fail_reasons),
        "commit_errors": len(errors),
        "commit_error_examples": errors[:5],
        "methods_changed": n_methods,
        "methods_changed_by_pass": {str(k): v for k, v in sorted(by_pass.items())},
        "methods_changed_block_unchanged_by_pass": {str(k): v for k, v in sorted(header_only.items())},
        "aux_changes": n_aux,
        "events": n_events,
        "core_events": dict(sorted(core.items())),
        "events_by_label_validity": {f"{l}|{v}": n for (l, v), n in sorted(by_validity.items())},
        "relocated_events_by_style_kind": dict(sorted(relocated.items())),
        "counts": _nested_counts(counts),
        "workers": workers,
        "chunk_size": chunk_size,
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2)
    _replace_dir(out_dir, final_dir, log)
    log(f"[{repo_name}] done in {summary['elapsed_seconds']}s: {n_events} events "
        f"(core {dict(core)}), {n_methods} modified methods, {n_failures} parse failures, "
        f"{len(errors)} commit errors")
    return summary
