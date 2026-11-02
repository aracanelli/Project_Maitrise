"""
History features (h_) from the mining tables of data/interim/mining/<repo>/.

"Prior" means a strictly smaller topo_index, so nothing from the instance's own commit
is used. Every history is stored as sorted
topo_index arrays and counted with bisect, which keeps the cost per instance at
O(log n) once a repository is indexed.

Files are tracked through renames: the R rows of file_changes.jsonl move a file's
lineage to its new path, so a renamed file keeps the history of its old path. When a
parallel branch still changes the old path after the rename (in topo order), that
change continues the same lineage. A file deleted and added again (or a rename hidden
in a merge) starts a new lineage.

Methods are followed the same way: a method key is (file lineage, class_path,
signature) and each methods_changed row moves the method lineage of its pre-state key
to its post-state key, so a method keeps its history when its signature or class
changes; as for files, a key moved away on a parallel branch keeps its lineage. Formal
events join the lineage of their method (modified-method events through their row,
whatever side their label records). An instance uses the lineage of its own
methods_changed row.

The mining output is checked before use: all four tables and summary.json must exist
and the row counts must match the summary, so a partial or stale run fails loudly.
"""

import hashlib
import json
import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HISTORY_COLUMNS = [
    "h_repo_age_days", "h_commit_index", "h_file_prior_commits", "h_file_prior_churn",
    "h_days_since_file_change", "h_file_prior_log_events", "h_method_prior_log_events",
    "h_method_prior_changes", "h_author_prior_commits", "h_author_prior_log_events",
    "h_repo_prior_log_event_rate",
]

# mining table -> summary.json key holding its row count (src/mining/run.py)
TABLE_COUNTS = {
    "commits": "n_commits",
    "file_changes": "file_changes_rows",
    "events": "events",
    "methods_changed": "methods_changed",
}

DAY = 86400.0


def read_table(path):
    """Rows of a jsonl file and the sha1 of the bytes they were parsed from."""
    data = Path(path).read_bytes()
    rows = []
    for line in data.decode("utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows, hashlib.sha1(data).hexdigest()


def load_mining_tables(repo, mining_dir):
    """The four stage-3 tables of a repository, checked against its summary.json.

    Returns ({table: rows}, {file name: sha1}).
    """
    d = Path(mining_dir) / repo
    names = [f"{t}.jsonl" for t in TABLE_COUNTS] + ["summary.json"]
    missing = [n for n in names if not (d / n).exists()]
    if missing:
        raise FileNotFoundError(f"mining output for {repo} is incomplete ({d}): missing {missing}")
    summary_bytes = (d / "summary.json").read_bytes()
    summary = json.loads(summary_bytes)
    tables = {}
    sha1 = {"summary.json": hashlib.sha1(summary_bytes).hexdigest()}
    for table, key in TABLE_COUNTS.items():
        rows, sha1[f"{table}.jsonl"] = read_table(d / f"{table}.jsonl")
        if key not in summary:
            raise ValueError(f"{d / 'summary.json'} has no '{key}' count")
        if summary[key] != len(rows):
            raise ValueError(f"{d / table}.jsonl has {len(rows)} rows but summary.json says {summary[key]}: "
                             "partial or stale mining output")
        tables[table] = rows
    if (d / "summary.json").read_bytes() != summary_bytes:
        raise ValueError(f"mining output for {repo} changed while it was read")
    return tables, sha1


def to_epoch(ts):
    if ts is None or ts == "":
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def last_lineage(history, key):
    """Most recent lineage recorded for a path (or method key), None if there is none."""
    for _, lid in reversed(history.get(key, ())):
        if lid is not None:
            return lid
    return None


def build_lineages(file_changes):
    """Assign a lineage id to every file_changes row, following renames in topo order.

    Returns (row_lineage, path_history, lineage_of_row, n_reused): {(commit_id, path):
    lineage} for the old and new path of each row, {path: [(topo_index, lineage or None),
    ...]}, the lineage of each row in input order and how many rows reused the lineage of
    a path moved away earlier.
    """
    # renames and deletions free their old path before additions in the same commit
    order = sorted(
        range(len(file_changes)),
        key=lambda i: (file_changes[i]["topo_index"], 0 if file_changes[i]["change_type"][:1] in ("R", "D") else 1, i),
    )
    current = {}
    path_history = defaultdict(list)
    row_lineage = {}
    lineage_of_row = [None] * len(file_changes)
    next_id = 0
    n_reused = 0
    for i in order:
        row = file_changes[i]
        ct = row["change_type"][:1]   # tolerate git-style "R100"
        t = row["topo_index"]
        old, new = row.get("old_path"), row.get("new_path")
        if ct == "A":
            lid = next_id
            next_id += 1
            current[new] = lid
            path_history[new].append((t, lid))
            lineage_of_row[i] = lid
            row_lineage[(row["commit_id"], new)] = lid
            continue
        path = old if ct in ("R", "D") else (new or old)
        lid = current.get(path)
        if lid is None:
            # the path was renamed or deleted earlier in topo order, on a parallel branch
            lid = last_lineage(path_history, path)
            n_reused += lid is not None
        if lid is None:
            lid = next_id
            next_id += 1
        if ct in ("R", "D"):
            current.pop(path, None)
            path_history[path].append((t, None))
            if ct == "R":
                current[new] = lid
                path_history[new].append((t, lid))
        elif current.get(path) != lid:
            current[path] = lid
            path_history[path].append((t, lid))
        lineage_of_row[i] = lid
        if old:
            row_lineage[(row["commit_id"], old)] = lid
        if new:
            row_lineage[(row["commit_id"], new)] = lid
    return row_lineage, dict(path_history), lineage_of_row, n_reused


def build_method_lineages(rows, events, file_lineage):
    """Follow method identities through the methods_changed rows, in topo order.

    A method key is (file lineage, class_path, signature). Each row moves the lineage of
    its pre-state key to its post-state key. Events of a modified method take the lineage
    of their row (a REMOVE_LOG names the pre-state method, the others the post-state one);
    events of deleted methods resolve their key before the commit, events of new methods
    after it. file_lineage(record) gives the file lineage of a row or event (or None).

    Returns (row_mid, event_mid, key_history, n_reused): the method lineage of each row
    and each event, in input order (None without a file lineage), {key: [(topo_index,
    mid or None), ...]} and how many rows and events reused the lineage of a moved key.
    """
    row_pre, row_post = [], []
    by_pre, by_post = {}, {}
    rows_at = defaultdict(list)
    for i, m in enumerate(rows):
        lid = file_lineage(m)
        row_pre.append((lid, m.get("class_path_pre") or m.get("class_path"), m.get("signature_pre")))
        row_post.append((lid, m.get("class_path"), m.get("signature_post")))
        if lid is None:
            continue
        by_pre.setdefault((m["commit_id"],) + row_pre[i], i)
        by_post.setdefault((m["commit_id"],) + row_post[i], i)
        rows_at[m["topo_index"]].append(i)

    event_key, event_row = [], []
    before_at, after_at = defaultdict(list), defaultdict(list)
    for k, e in enumerate(events):
        lid = file_lineage(e)
        key = (lid, e.get("class_path"), e.get("method_signature"))
        event_key.append(key)
        event_row.append(None)
        if lid is None:
            continue
        scope = e.get("scope")
        if scope == "modified_method":
            side = by_pre if e.get("event_label") == "REMOVE_LOG" else by_post
            event_row[k] = side.get((e["commit_id"],) + key)
        if scope in ("deleted_method", "deleted_file"):
            before_at[e["topo_index"]].append(k)
        else:
            after_at[e["topo_index"]].append(k)

    row_mid = [None] * len(rows)
    event_mid = [None] * len(events)
    current = {}
    key_history = defaultdict(list)
    next_id = 0
    n_reused = 0
    for t in sorted(set(rows_at) | set(before_at) | set(after_at)):
        # pre-state keys resolve against the methods as they were before the commit; a key
        # moved away earlier in topo order (on a parallel branch) keeps its last lineage
        for i in rows_at[t]:
            mid = current.get(row_pre[i])
            if mid is None:
                mid = last_lineage(key_history, row_pre[i])
                n_reused += mid is not None
            if mid is None:
                mid = next_id
                next_id += 1
            row_mid[i] = mid
        for k in before_at[t]:
            mid = current.get(event_key[k])
            if mid is None:
                mid = last_lineage(key_history, event_key[k])
                n_reused += mid is not None
            if mid is None:
                mid = next_id
                next_id += 1
            event_mid[k] = mid
        # then the commit moves renamed methods and frees deleted ones
        freed = [(row_pre[i], row_mid[i]) for i in rows_at[t] if row_pre[i] != row_post[i]]
        freed += [(event_key[k], event_mid[k]) for k in before_at[t]]
        for key, mid in freed:
            if current.get(key) == mid:
                del current[key]
                key_history[key].append((t, None))
        for i in rows_at[t]:
            if current.get(row_post[i]) != row_mid[i]:
                current[row_post[i]] = row_mid[i]
                key_history[row_post[i]].append((t, row_mid[i]))
        # events of new methods (and any event without its row) use the post-state key
        for k in after_at[t]:
            if event_row[k] is not None:
                event_mid[k] = row_mid[event_row[k]]
                continue
            key = event_key[k]
            mid = current.get(key)
            if mid is None:
                mid = next_id
                next_id += 1
                current[key] = mid
                key_history[key].append((t, mid))
            event_mid[k] = mid
    return row_mid, event_mid, dict(key_history), n_reused


def lineage_before(path_history, path, topo):
    """Lineage that `path` pointed to just before commit `topo`."""
    hist = path_history.get(path)
    if not hist:
        return None
    pos = bisect_left([t for t, _ in hist], topo) - 1
    if pos < 0:
        return None
    return hist[pos][1]


def build_history_index(repo, mining_dir):
    tables, sha1 = load_mining_tables(repo, mining_dir)
    commits = tables["commits"]
    file_changes = tables["file_changes"]
    events = tables["events"]
    methods_changed = tables["methods_changed"]

    commits.sort(key=lambda c: c["topo_index"])
    commit_ts = {}
    topos = []
    min_ts = []
    lowest = math.inf
    nonmerge = []
    author_commits = defaultdict(list)
    for c in commits:
        ts = to_epoch(c.get("timestamp"))
        commit_ts[c["commit_id"]] = ts
        if ts is not None:
            lowest = min(lowest, ts)
        topos.append(c["topo_index"])
        min_ts.append(lowest)
        if not c.get("is_merge"):
            nonmerge.append(c["topo_index"])
            author_commits[c.get("author_id")].append(c["topo_index"])

    row_lineage, path_history, lineage_of_row, file_reused = build_lineages(file_changes)
    per_file = defaultdict(list)
    for i, row in enumerate(file_changes):
        churn = (row.get("lines_added") or 0) + (row.get("lines_deleted") or 0)
        per_file[lineage_of_row[i]].append((row["topo_index"], churn, commit_ts.get(row["commit_id"])))
    file_topos, file_churn, file_ts = {}, {}, {}
    for lid, items in per_file.items():
        items.sort(key=lambda x: x[0])
        file_topos[lid] = [x[0] for x in items]
        cum = []
        total = 0
        for x in items:
            total += x[1]
            cum.append(total)
        file_churn[lid] = cum
        file_ts[lid] = [x[2] for x in items]

    def row_lid(commit_id, topo, *paths):
        for p in paths:
            if p and (commit_id, p) in row_lineage:
                return row_lineage[(commit_id, p)]
        for p in paths:
            if p:
                lid = lineage_before(path_history, p, topo)
                if lid is not None:
                    return lid
        return None

    def file_lineage(r):
        return row_lid(r["commit_id"], r["topo_index"], r.get("post_path"), r.get("pre_path"), r.get("file_path"))

    formal = [e for e in events if e.get("logging_style") == "formal"]
    row_mid, event_mid, method_history, method_reused = build_method_lineages(methods_changed, formal, file_lineage)

    event_topos = []
    file_events = defaultdict(list)
    method_events = defaultdict(list)
    author_events = defaultdict(list)
    for e, mid in zip(formal, event_mid):
        t = e["topo_index"]
        event_topos.append(t)
        lid = file_lineage(e)
        if lid is not None:
            file_events[lid].append(t)
        if mid is not None:
            method_events[mid].append(t)
        author_events[e.get("author_id")].append(t)

    # instances are built from methods_changed rows: each finds its method lineage here
    method_changes = defaultdict(list)
    own_row_mid = {}
    for m, mid in zip(methods_changed, row_mid):
        if mid is None:
            continue
        method_changes[mid].append(m["topo_index"])
        own_row_mid[(m["commit_id"], m.get("pre_path"), m.get("pre_ordinal"), m.get("signature_pre"))] = mid

    for table in (author_commits, file_events, method_events, author_events, method_changes):
        for v in table.values():
            v.sort()
    event_topos.sort()

    return {
        "repo": repo,
        "inputs_sha1": sha1,
        "lineage_reuse": {"file_rows": file_reused, "method_records": method_reused},
        "commit_ts": commit_ts,
        "topos": topos,
        "min_ts": min_ts,
        "max_topo": topos[-1] if topos else 0,
        "nonmerge": nonmerge,
        "author_commits": dict(author_commits),
        "row_lineage": row_lineage,
        "path_history": path_history,
        "file_topos": file_topos,
        "file_churn": file_churn,
        "file_ts": file_ts,
        "event_topos": event_topos,
        "file_events": dict(file_events),
        "method_events": dict(method_events),
        "author_events": dict(author_events),
        "method_changes": dict(method_changes),
        "method_history": method_history,
        "own_row_mid": own_row_mid,
    }


def n_before(sorted_list, t):
    if not sorted_list:
        return 0
    return bisect_left(sorted_list, t)


def instance_lineage(idx, inst):
    path = inst.get("pre_path") or inst.get("post_path")
    key = (inst["commit_id"], path)
    if key in idx["row_lineage"]:
        return idx["row_lineage"][key]
    return lineage_before(idx["path_history"], path, inst["topo_index"])


def history_features(idx, inst):
    t = inst["topo_index"]
    ts = to_epoch(inst.get("timestamp"))
    if ts is None:
        ts = idx["commit_ts"].get(inst["commit_id"])
    h = {}

    pos = bisect_right(idx["topos"], t) - 1
    start = idx["min_ts"][pos] if pos >= 0 else ts
    if ts is None or start is None or math.isinf(start):
        h["h_repo_age_days"] = math.nan
    else:
        h["h_repo_age_days"] = max(ts - start, 0.0) / DAY
    # position in history from prior commits only (a ratio to the final history length
    # would use commits that happen after the instance)
    prior_commits = n_before(idx["nonmerge"], t)
    h["h_commit_index"] = math.log1p(prior_commits)

    lid = instance_lineage(idx, inst)
    topos = idx["file_topos"].get(lid, [])
    k = n_before(topos, t)
    h["h_file_prior_commits"] = k
    h["h_file_prior_churn"] = math.log1p(idx["file_churn"][lid][k - 1]) if k else 0.0
    last_ts = idx["file_ts"][lid][k - 1] if k else None
    if last_ts is None or ts is None:
        h["h_days_since_file_change"] = math.nan
    else:
        h["h_days_since_file_change"] = max(ts - last_ts, 0.0) / DAY

    h["h_file_prior_log_events"] = n_before(idx["file_events"].get(lid), t)
    # the instance's own row gives its method lineage even when this commit renames the
    # class; without a row, the method the pre-state key pointed to before this commit
    own_row = (inst["commit_id"], inst.get("pre_path"), inst.get("pre_ordinal"), inst.get("signature_pre"))
    mid = idx["own_row_mid"].get(own_row)
    if mid is None:
        mid = lineage_before(idx["method_history"], (lid, inst.get("class_path"), inst.get("signature_pre")), t)
    h["h_method_prior_log_events"] = n_before(idx["method_events"].get(mid), t)
    h["h_method_prior_changes"] = n_before(idx["method_changes"].get(mid), t)

    author = inst.get("author_id")
    h["h_author_prior_commits"] = n_before(idx["author_commits"].get(author), t)
    h["h_author_prior_log_events"] = n_before(idx["author_events"].get(author), t)
    h["h_repo_prior_log_event_rate"] = n_before(idx["event_topos"], t) / max(prior_commits, 1)
    return h
