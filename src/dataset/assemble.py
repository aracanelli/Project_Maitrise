"""
Stage 4: task instances from the mining output.

Input:  data/interim/mining/<repo>/{methods_changed,events,commits,file_changes}.jsonl, summary.json
Output: data/processed/events_master.{jsonl,csv}
        data/processed/instances/{add_log,add_log_post,remove_log,change_level,multiclass}.jsonl
        data/processed/instances/{folds,summary}.json

Every instance comes from a modified method of a non-bulk commit whose body block changed
(block_changed; rows where only the header changed can never carry a logging change, so
they would only dilute the negatives). Labels follow the core
event semantics: relocated statements are neither positive nor negative, and a method is
a clean ADD_LOG (or NO_EVENT) negative only when nothing about its logging changed.

ADD_LOG instances use the pre-state view (the method before the commit, no masking, no
anchor), like REMOVE_LOG and CHANGE_LEVEL. The masked post-state leaves emptied catch
blocks in 14% of the positives against 0.6% of the negatives, a cue a model can learn
instead of the task. The masked post-state ("commit-time") view is kept as the sensitivity task
add_log_post: exactly the add_log instances (same labels, neg_rank, in_R flags, folds),
instance_id prefix add_log_post:, view post_masked, masking every statement added in the
commit, of any style (mask_post_all_idx, from the miner's added_all_post).

The ADD_LOG pools are asymmetric by design: a positive may also carry a non-formal
logging change (other_log_change), a clean negative never does. add_log instances also
carry two metadata fields, never features: other_log_change (copied from the row) and
n_nonformal_added (non-formal ADD_LOG events of the method, joined from events.jsonl),
and summary.json counts them per repository (add_log_split) for a sensitivity analysis.

Both Stage-3 files are checked against their expected field lists before use; a renamed
or dropped field would otherwise read as "no change" and silently make clean negatives.
Every mining table must also have the row count recorded in its summary.json: a mining
run interrupted while rewriting the tables leaves them truncated next to an older
summary (or none), and is refused instead of being assembled as a smaller history.

instance_id has a short hash of the file path before the ordinal, because ordinals are
per file and one commit usually modifies methods in several files. Only components 0-2
(task, repo, commit prefix) are meant to be parsed downstream.
"""

import copy
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

from src.common.config import DATA, load_config, corpus_repos
from src.dataset.folds import make_folds
from src.dataset.sampling import sampling_key, rank_negatives, mark_positives, sample_stats
from src.parsing.method_units import console_reply_context

TASKS = ["add_log", "remove_log", "change_level"]
# add_log_post mirrors add_log (built from its instances), so it must come after it
ALL_TASKS = ["add_log", "add_log_post", "remove_log", "change_level", "multiclass"]
EVENT_TYPES = ["ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]
MULTICLASS_PRIORITY = ["CHANGE_LEVEL", "REMOVE_LOG", "ADD_LOG"]

# copied from the methods_changed row, in this order (common fields + change_type, match_pass)
ROW_FIELDS = [
    "commit_id", "parent_commit_id", "topo_index", "timestamp", "author_id",
    "pre_path", "post_path", "pre_blob", "post_blob", "class_path", "method_name",
    "signature_pre", "signature_post", "kind", "pre_ordinal", "post_ordinal",
    "change_type", "match_pass",
]
EVENT_COUNT_FIELDS = ["validity_status", "scope", "logging_style", "event_label"]

# fields every Stage-3 row must have (src/mining/run.py writes more)
METHODS_CHANGED_FIELDS = [
    "repo", "commit_id", "parent_commit_id", "topo_index", "timestamp", "author_id", "is_bulk",
    "pre_path", "post_path", "pre_blob", "post_blob", "change_type",
    "class_path", "method_name", "signature_pre", "signature_post", "kind", "match_pass",
    "pre_ordinal", "post_ordinal", "pre_start_line", "pre_end_line", "post_start_line", "post_end_line",
    "n_pre_formal", "n_post_formal", "n_pre_logs_all", "n_post_logs_all",
    "added_formal_post", "removed_formal_pre", "level_changed", "matched_formal",
    "pre_levels", "post_levels", "relocated_pre", "relocated_post", "other_log_change",
]
EVENT_FIELDS = [
    "event_id", "repo", "commit_id", "parent_commit_id", "topo_index", "timestamp", "author_id",
    "is_bulk", "scope", "event_label", "logging_style", "framework", "file_path", "pre_path",
    "post_path", "class_path", "method_signature", "call_name", "call_text", "call_text_before",
    "pre_level", "post_level", "statement_continuity", "match_confidence", "pre_line", "post_line",
    "pre_formal_index", "post_formal_index", "is_relocated", "validity_status",
]
ROW_TYPES = {"is_bulk": bool, "other_log_change": bool,
             "added_formal_post": list, "removed_formal_pre": list, "level_changed": list,
             "matched_formal": list, "pre_levels": list, "post_levels": list,
             "relocated_pre": list, "relocated_post": list}
EVENT_TYPES_CHECK = {"is_bulk": bool, "is_relocated": bool}
EVENT_CHOICES = {"event_label": EVENT_TYPES,
                 "validity_status": ["core", "relocated", "bulk", "non_formal", "out_of_scope"]}

# per-repo counters of summary.json add_log_split, always all present
SPLIT_KEYS = [
    "positive", "clean_negative", "neither", "neither_only_other_log_change",
    "positive_with_other_log_change", "positive_with_nonformal_add", "positive_with_removal",
    "positive_with_level_change", "positive_with_relocation",
]

# mining table -> summary.json key holding its row count (src/mining/run.py); the
# features stage checks the same counts (src/features/history_features.py)
MINING_COUNTS = {
    "commits": "n_commits",
    "file_changes": "file_changes_rows",
    "events": "events",
    "methods_changed": "methods_changed",
}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path, rows):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, path)


def write_json(path, obj):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def write_csv(path, rows):
    fields = []
    seen = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fields.append(k)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", errors="backslashreplace", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            out = {}
            for k in fields:
                v = r.get(k)
                if v is None:
                    v = ""
                elif isinstance(v, (list, dict)):
                    v = json.dumps(v)
                out[k] = v
            w.writerow(out)
    os.replace(tmp, path)


def file_sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def path_tag(path):
    return hashlib.sha1((path or "").replace("\\", "/").encode("utf-8")).hexdigest()[:8]


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def check_contract(rows, path, repo, fields, types, choices=None):
    """Raise ValueError when a Stage-3 file has missing fields, wrong types or another repo."""
    missing, wrong_type, unknown, wrong_repo = Counter(), Counter(), Counter(), []
    for r in rows:
        for k in fields:
            if k not in r:
                missing[k] += 1
        for k, t in types.items():
            if k in r and not isinstance(r[k], t):
                wrong_type[k] += 1
        for k, allowed in (choices or {}).items():
            if k in r and r[k] not in allowed:
                unknown[f"{k}={r[k]}"] += 1
        if r.get("repo") != repo:
            wrong_repo.append(r.get("repo"))
    if wrong_repo:
        raise ValueError(f"{path}: {len(wrong_repo)} rows with repo != {repo}, e.g. {wrong_repo[0]!r}")
    if missing or wrong_type or unknown:
        raise ValueError(f"{path} does not follow the Stage 3 contract: missing {dict(missing)}, "
                         f"wrong type {dict(wrong_type)}, unknown values {dict(unknown)}")


def count_lines(path):
    n = 0
    with open(path, "rb") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def check_mining_counts(d):
    """Raise ValueError unless every mining table of folder d has its summary.json row count."""
    path = d / "summary.json"
    if not path.exists():
        raise ValueError(f"{path} is missing: the mining of {d.name} did not finish")
    summary = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for table, key in MINING_COUNTS.items():
        f = d / f"{table}.jsonl"
        if key not in summary:
            problems.append(f"summary.json has no '{key}' count")
        elif not f.exists():
            problems.append(f"{f.name} is missing")
        else:
            n = count_lines(f)
            if n != summary[key]:
                problems.append(f"{f.name} has {n} rows but summary.json says {summary[key]}")
    if problems:
        raise ValueError(f"mining output of {d.name} is partial or stale ({d}): " + "; ".join(problems))


def _set(row, key):
    return set(row[key])


def _level(levels, i):
    if i is None or i < 0 or i >= len(levels):
        return None
    return levels[i]


def no_formal_change(row):
    """No formal log added, removed, relocated or re-levelled in this method."""
    for key in ("added_formal_post", "removed_formal_pre", "level_changed", "relocated_pre", "relocated_post"):
        if row[key]:
            return False
    return not any(a != b for _, _, _, a, b in known_level_pairs(row))


def is_clean(row):
    """No logging change of any kind: the ADD_LOG / NO_EVENT negative pool."""
    return no_formal_change(row) and not row["other_log_change"] and not row["n_nonformal_added"]


def genuine_added(row):
    return sorted(_set(row, "added_formal_post") - _set(row, "relocated_post"))


def genuine_removed(row):
    return sorted(_set(row, "removed_formal_pre") - _set(row, "relocated_pre"))


def uncertain_pairs(row):
    """Matched formal pairs whose statement identity is unsure (payload below the continuity threshold)."""
    return {(p, q) for p, q in row.get("uncertain_formal", [])}


def known_level_pairs(row):
    """Confident matched formal pairs whose two levels are known: (pre_fi, post_fi, ratio, pre_level, post_level)."""
    unsure = uncertain_pairs(row)
    out = []
    for pre_fi, post_fi, ratio in row["matched_formal"]:
        if (pre_fi, post_fi) in unsure:
            continue
        a = _level(row["pre_levels"], pre_fi)
        b = _level(row["post_levels"], post_fi)
        if a is not None and b is not None:
            out.append((pre_fi, post_fi, ratio, a, b))
    return out


def event_types(row):
    present = []
    if genuine_added(row):
        present.append("ADD_LOG")
    if genuine_removed(row):
        present.append("REMOVE_LOG")
    if any(a != b for _, _, _, a, b in known_level_pairs(row)):
        present.append("CHANGE_LEVEL")
    return present


def row_problems(row):
    """Internal-consistency checks on a methods_changed row (counted, never fatal).

    Relocated indices may be kept inside added/removed or apart from them (the miner keeps
    them apart); both read the same, so only overlap with matched statements is a problem.
    """
    problems = []
    n_pre = row["n_pre_formal"]
    n_post = row["n_post_formal"]
    if len(row["pre_levels"]) != n_pre or len(row["post_levels"]) != n_post:
        problems.append("levels_length_mismatch")
    matched = row["matched_formal"]
    matched_pre = {m[0] for m in matched}
    matched_post = {m[1] for m in matched}
    removed = _set(row, "removed_formal_pre")
    added = _set(row, "added_formal_post")
    reloc_pre = _set(row, "relocated_pre")
    reloc_post = _set(row, "relocated_post")
    if any(i < 0 or i >= n_pre for i in removed | matched_pre | reloc_pre):
        problems.append("pre_index_out_of_range")
    if any(i < 0 or i >= n_post for i in added | matched_post | reloc_post):
        problems.append("post_index_out_of_range")
    if removed & matched_pre or added & matched_post:
        problems.append("removed_or_added_also_matched")
    if reloc_pre & matched_pre or reloc_post & matched_post:
        problems.append("relocated_also_matched")
    if len(matched_pre) != len(matched) or len(matched_post) != len(matched):
        problems.append("matched_not_one_to_one")
    if set(range(n_pre)) - removed - matched_pre - reloc_pre:
        problems.append("pre_statement_unaccounted")
    if set(range(n_post)) - added - matched_post - reloc_post:
        problems.append("post_statement_unaccounted")
    computed = sorted((p, q) for p, q, _, a, b in known_level_pairs(row) if a != b)
    listed = sorted((x[0], x[1]) for x in row["level_changed"])
    if computed != listed:
        problems.append("level_changed_mismatch")
    if row["n_nonformal_added"] and not row["other_log_change"]:
        problems.append("nonformal_add_without_other_log_change")
    return problems


def split_keys(row):
    """add_log_split counters of one row: its pool, and for positives what else changed.

    neither_only_other_log_change: excluded from the negatives by a non-formal or
    auxiliary change alone (the rows the asymmetric pool definition leaves out).
    """
    if not genuine_added(row):
        if is_clean(row):
            return ["clean_negative"]
        if no_formal_change(row):
            return ["neither", "neither_only_other_log_change"]
        return ["neither"]
    keys = ["positive"]
    if row["other_log_change"]:
        keys.append("positive_with_other_log_change")
    if row["n_nonformal_added"]:
        keys.append("positive_with_nonformal_add")
    if genuine_removed(row):
        keys.append("positive_with_removal")
    if any(a != b for _, _, _, a, b in known_level_pairs(row)):
        keys.append("positive_with_level_change")
    if row["relocated_pre"] or row["relocated_post"]:
        keys.append("positive_with_relocation")
    return keys


def base_instance(row, task, info, instance_id, label, role, provenance, ratios):
    inst = {"instance_id": instance_id, "task": task, "repo": row["repo"],
            "engine": info["engine"], "size": info["size"]}
    for k in ROW_FIELDS:
        inst[k] = row[k]
    # pre-state class path (differs from class_path for methods moved between classes)
    inst["class_path_pre"] = row.get("class_path_pre") or row["class_path"]
    inst["label"] = label
    inst["sample_role"] = role
    inst["neg_rank"] = None
    for r in ratios:
        inst[f"in_R{r}"] = False
    inst["neg_provenance"] = provenance
    return inst


def add_log_id(row):
    return f"add_log:{row['repo']}:{row['commit_id'][:12]}:{path_tag(row['post_path'])}:{row['post_ordinal']}"


def add_log_instance(row, info, ratios):
    if genuine_added(row):
        label, role, prov = 1, "positive", ""
    elif is_clean(row):
        label, role, prov = 0, "negative", "modified_method_no_log_change"
    else:
        return None
    inst = base_instance(row, "add_log", info, add_log_id(row), label, role, prov, ratios)
    # the method as it was before the commit: nothing to mask, no anchor
    inst["view"] = "pre"
    # metadata for the sensitivity analysis, not features (always False / 0 for negatives)
    inst["other_log_change"] = row["other_log_change"]
    inst["n_nonformal_added"] = row["n_nonformal_added"]
    return inst


def post_mask(row):
    """mask fields of the post_masked view of a row (add_log_post)."""
    # every log added in this commit is masked, relocated ones included, so the view is
    # the post-state without any statement that did not exist before the commit
    # statements of unsure identity may be new as well, so they are masked too
    mask = {"mask_post_idx": sorted(_set(row, "added_formal_post") | _set(row, "relocated_post")
                                    | {q for _, q in uncertain_pairs(row)})}
    if "added_all_post" in row:
        mask["mask_post_all_idx"] = sorted(set(row["added_all_post"]) | set(row.get("uncertain_post_all", [])))
    return mask


def add_log_post_instances(add_log_kept, rows):
    """The add_log_post twin of every kept add_log instance: same unit, label, neg_rank,
    in_R flags and metadata; only the id prefix, the task and the view differ."""
    masks = {}
    for row in rows:
        if genuine_added(row) or is_clean(row):
            masks[add_log_id(row)] = post_mask(row)
    out = []
    for inst in add_log_kept:
        twin = {}
        for k, v in inst.items():
            twin[k] = v
            if k == "view":
                twin["view"] = "post_masked"
                twin.update(masks[inst["instance_id"]])
        twin["instance_id"] = "add_log_post:" + inst["instance_id"][len("add_log:"):]
        twin["task"] = "add_log_post"
        out.append(twin)
    return out


def statement_instance(row, task, info, i, label, prov, ratios):
    iid = f"{task}:{row['repo']}:{row['commit_id'][:12]}:{path_tag(row['pre_path'])}:{row['pre_ordinal']}:{i}"
    role = "positive" if label else "negative"
    inst = base_instance(row, task, info, iid, label, role, prov, ratios)
    inst["view"] = "pre"
    inst["anchor_pre_idx"] = i
    inst["anchor_level"] = _level(row["pre_levels"], i)
    return inst


def remove_log_instances(row, info, ratios):
    removed = _set(row, "removed_formal_pre")
    # relocated statements and statements of unsure identity are neither positive nor negative
    relocated = _set(row, "relocated_pre") | {p for p, _ in uncertain_pairs(row)}
    matched = {}
    for pre_fi, post_fi, ratio in row["matched_formal"]:
        matched[pre_fi] = (post_fi, ratio)
    out = []
    for i in range(row["n_pre_formal"]):
        if i in relocated:
            continue
        if i in removed:
            inst = statement_instance(row, "remove_log", info, i, 1, "", ratios)
            inst["anchor_post_idx"] = None
            inst["match_ratio"] = None
        elif i in matched:
            inst = statement_instance(row, "remove_log", info, i, 0, "retained_statement", ratios)
            inst["anchor_post_idx"] = matched[i][0]
            inst["match_ratio"] = matched[i][1]
        else:
            continue
        out.append(inst)
    return out


def change_level_instances(row, info, ratios):
    relocated = _set(row, "relocated_pre")
    out = []
    for pre_fi, post_fi, ratio, a, b in known_level_pairs(row):
        if pre_fi in relocated:
            continue
        label = int(a != b)
        prov = "" if label else "same_level_statement"
        inst = statement_instance(row, "change_level", info, pre_fi, label, prov, ratios)
        inst["anchor_post_idx"] = post_fi
        inst["post_level"] = b
        inst["match_ratio"] = ratio
        out.append(inst)
    return out


def multiclass_instance(row, info, ratios):
    present = event_types(row)
    if present:
        label = [t for t in MULTICLASS_PRIORITY if t in present][0]
        role, prov = "positive", ""
    elif is_clean(row):
        label, role, prov = "NO_EVENT", "negative", "modified_method_no_log_change"
    else:
        return None
    iid = f"multiclass:{row['repo']}:{row['commit_id'][:12]}:{path_tag(row['pre_path'])}:{row['pre_ordinal']}"
    inst = base_instance(row, "multiclass", info, iid, label, role, prov, ratios)
    inst["view"] = "pre"
    inst["labels_multi"] = present
    inst["other_log_change"] = row["other_log_change"]  # metadata, as for add_log
    return inst


def task_instances(task, row, info, ratios):
    if task == "add_log":
        inst = add_log_instance(row, info, ratios)
        return [inst] if inst else []
    if task == "remove_log":
        return remove_log_instances(row, info, ratios)
    if task == "change_level":
        return change_level_instances(row, info, ratios)
    inst = multiclass_instance(row, info, ratios)
    return [inst] if inst else []


# keyed on the unit the model sees, i.e. on the view: the pre-state unit for "pre" views
# (add_log included), the post-state unit for post_masked views
def unit_key(inst):
    if inst.get("view") == "post_masked":
        return (inst["repo"], inst["commit_id"], inst["post_path"], inst["post_ordinal"])
    return (inst["repo"], inst["commit_id"], inst["pre_path"], inst["pre_ordinal"], inst.get("anchor_pre_idx"))


def signature_key(inst):
    if inst.get("view") == "post_masked":
        return (inst["repo"], inst["commit_id"], inst["post_path"], inst["class_path"], inst["signature_post"])
    return (inst["repo"], inst["commit_id"], inst["pre_path"], inst["class_path_pre"], inst["signature_pre"],
            inst.get("anchor_pre_idx"))


def check_instances(positives, negatives):
    """Hard checks before sampling: unique ids and no unit that is both positive and negative.

    The unit is the one of the instance's view (unit_key): for add_log, a pre-state method
    that two post-state methods come from cannot be labelled both ways.
    Returns the number of (file, class, signature) keys shared by a positive and a negative,
    which can legitimately happen for same-named methods of two anonymous classes.
    """
    counts = Counter(i["instance_id"] for i in positives + negatives)
    dup = [k for k, n in counts.items() if n > 1]
    assert not dup, f"duplicate instance_ids ({len(dup)}), e.g. {dup[:3]}"
    pos_keys = {unit_key(i) for i in positives}
    both = [unit_key(i) for i in negatives if unit_key(i) in pos_keys]
    assert not both, f"units both positive and negative ({len(both)}), e.g. {both[:3]}"
    pos_sig = {signature_key(i) for i in positives}
    return sum(1 for i in negatives if signature_key(i) in pos_sig)


def build_task(task, repo, rows, info, sampling):
    """All instances of one task for one repository, sampled. Returns (kept, stats)."""
    ratios = list(sampling["ratios"])
    top = max(ratios)
    if task == "multiclass":
        top = sampling["primary_ratio"]
        ratios = [r for r in ratios if r <= top]

    positives, negatives = [], []
    for row in rows:
        for inst in task_instances(task, row, info, ratios):
            if inst["sample_role"] == "positive":
                positives.append(inst)
            else:
                negatives.append(inst)
    sig_overlap = check_instances(positives, negatives)

    n_pos = len(positives)
    mark_positives(positives, ratios)
    ranked = rank_negatives(negatives, n_pos, ratios, sampling_key(sampling["seed"], task, repo))
    kept = positives + [i for i in ranked if i[f"in_R{top}"]]
    kept.sort(key=lambda i: (i["topo_index"], i["instance_id"]))

    n_neg, achieved = sample_stats(n_pos, len(negatives), ratios)
    stats = {"n_pos": n_pos, "n_neg_pool": len(negatives), "n_neg": n_neg, "ratio": achieved,
             "n_written": len(kept), "signature_key_overlap": sig_overlap}
    if task == "multiclass":
        stats["by_label"] = dict(sorted(Counter(i["label"] for i in positives).items()))
    return kept, stats


def _event_order(ev):
    n = str(ev.get("event_id", "")).rsplit(":", 1)[-1]
    return (ev.get("topo_index") or 0, int(n) if n.isdigit() else 0)


def master_events(path, repo, info):
    """events.jsonl plus engine/size, in (topo_index, event number) order."""
    events = list(read_jsonl(path))
    check_contract(events, path, repo, EVENT_FIELDS, EVENT_TYPES_CHECK, EVENT_CHOICES)
    out = []
    for ev in events:
        row = {}
        for k, v in ev.items():
            row[k] = v
            if k == "repo":
                row["engine"] = info["engine"]
                row["size"] = info["size"]
        row.setdefault("engine", info["engine"])
        row.setdefault("size", info["size"])
        out.append(row)
    out.sort(key=_event_order)
    return out


def crosstab(events, a, b):
    table = {}
    for e in events:
        table.setdefault(str(e.get(a)), Counter())[str(e.get(b))] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(table.items())}


def event_counts(events):
    c = {"total": len(events)}
    for field in EVENT_COUNT_FIELDS:
        c[field] = dict(sorted(Counter(str(e.get(field)) for e in events).items()))
    c["label_by_validity"] = crosstab(events, "event_label", "validity_status")
    c["label_by_scope"] = crosstab(events, "event_label", "scope")
    c["label_by_style"] = crosstab(events, "event_label", "logging_style")
    return c


def attach_nonformal_adds(rows, events):
    """Set row["n_nonformal_added"]: non-formal ADD_LOG events of that modified method.

    Joined on (commit, post_path, class_path, signature), which is unique within a file.
    Returns (number of such events, number that matched no row).
    """
    adds = Counter()
    for e in events:
        if (e["event_label"] == "ADD_LOG" and e["scope"] == "modified_method"
                and e["logging_style"] != "formal" and not e["is_bulk"]):
            adds[(e["commit_id"], e["post_path"], e["class_path"], e["method_signature"])] += 1
    used = set()
    for r in rows:
        key = (r["commit_id"], r["post_path"], r["class_path"], r["signature_post"])
        r["n_nonformal_added"] = adds.get(key, 0)
        if key in adds:
            used.add(key)
    return sum(adds.values()), sum(n for k, n in adds.items() if k not in used)


def core_keys_from_rows(rows):
    """Statement keys of the core events implied by methods_changed.

    class_path is left out: methods_changed has only the post-state one, while a
    REMOVE_LOG event names the pre-state class. CHANGE_LEVEL is keyed on both paths and
    indices so it does not depend on which side's signature the event carries.
    """
    keys = {t: Counter() for t in EVENT_TYPES}
    for r in rows:
        c = r["commit_id"]
        for i in genuine_added(r):
            keys["ADD_LOG"][(c, r["post_path"], r["signature_post"], i, _level(r["post_levels"], i))] += 1
        for i in genuine_removed(r):
            keys["REMOVE_LOG"][(c, r["pre_path"], r["signature_pre"], i, _level(r["pre_levels"], i))] += 1
        for p, q, _, a, b in known_level_pairs(r):
            if a != b:
                keys["CHANGE_LEVEL"][(c, r["pre_path"], r["post_path"], p, q, a, b)] += 1
    return keys


def core_keys_from_events(events):
    keys = {t: Counter() for t in EVENT_TYPES}
    for e in events:
        if e["validity_status"] != "core":
            continue
        c = e["commit_id"]
        if e["event_label"] == "ADD_LOG":
            k = (c, e["post_path"], e["method_signature"], e["post_formal_index"], e["post_level"])
        elif e["event_label"] == "REMOVE_LOG":
            k = (c, e["pre_path"], e["method_signature"], e["pre_formal_index"], e["pre_level"])
        else:
            k = (c, e["pre_path"], e["post_path"], e["pre_formal_index"], e["post_formal_index"],
                 e["pre_level"], e["post_level"])
        keys[e["event_label"]][k] += 1
    return keys


def core_check(events, rows):
    """Core events must be exactly the statement-level positives of methods_changed (as multisets of keys)."""
    from_events = core_keys_from_events(events)
    from_rows = core_keys_from_rows(rows)
    out = {}
    for label in EVENT_TYPES:
        only_events = from_events[label] - from_rows[label]
        only_rows = from_rows[label] - from_events[label]
        out[label] = {
            "core_events": sum(from_events[label].values()),
            "from_methods_changed": sum(from_rows[label].values()),
            "n_only_events": sum(only_events.values()),
            "n_only_rows": sum(only_rows.values()),
            "match": not only_events and not only_rows,
            "examples_only_events": [list(k) for k in sorted(only_events, key=repr)[:3]],
            "examples_only_rows": [list(k) for k in sorted(only_rows, key=repr)[:3]],
        }
    return out


def select_repos(repos=None):
    all_names = [r["name"] for r in corpus_repos()]
    if not repos:
        return [r["name"] for r in corpus_repos(modeling_only=True)]
    unknown = [r for r in repos if r not in all_names]
    if unknown:
        raise ValueError(f"repositories not in configs/corpus.yaml: {unknown}")
    # corpus order, whatever order they were given in
    return [n for n in all_names if n in repos]


def build_all(mining_dir=None, out_dir=None, repos=None):
    exp = load_config("experiment")
    sampling = exp["sampling"]
    protocol = exp["protocol"]
    infos = {r["name"]: r for r in corpus_repos()}
    mining_dir = Path(mining_dir) if mining_dir else DATA / "interim" / "mining"
    out_dir = Path(out_dir) if out_dir else DATA / "processed"
    inst_dir = out_dir / "instances"

    wanted = select_repos(repos)
    present, missing = [], {}
    for repo in wanted:
        d = mining_dir / repo
        lacking = [n for n in ("methods_changed.jsonl", "events.jsonl") if not (d / n).exists()]
        if lacking:
            warn(f"{repo}: skipped, missing {', '.join(lacking)} in {d}")
            missing[repo] = lacking
            continue
        # a truncated table (interrupted mining run) stops the build before anything is written
        check_mining_counts(d)
        present.append(repo)
    if not present:
        # do not overwrite an earlier build with empty files (e.g. wrong --mining-dir)
        warn(f"no mining output under {mining_dir}, nothing written")
        return {"repos": [], "missing_repos": missing}

    kept = {t: [] for t in ALL_TASKS}
    stats = {t: {} for t in ALL_TASKS}
    events_all = []
    per_repo = {}
    inputs = {}
    for repo in present:
        info = infos[repo]
        d = mining_dir / repo
        inputs[repo] = {n: file_sha1(d / n) for n in ("methods_changed.jsonl", "events.jsonl")}

        all_rows = list(read_jsonl(d / "methods_changed.jsonl"))
        check_contract(all_rows, d / "methods_changed.jsonl", repo, METHODS_CHANGED_FIELDS, ROW_TYPES)
        events = master_events(d / "events.jsonl", repo, info)
        events_all.extend(events)

        rows = [r for r in all_rows if not r["is_bulk"]]
        n_header_only = sum(1 for r in rows if not r.get("block_changed", True))
        rows = [r for r in rows if r.get("block_changed", True)]
        # operator console command replies (configs/extraction.yaml console_reply_contexts)
        n_console = sum(1 for r in rows if console_reply_context(r["class_path"], r["method_name"]))
        rows = [r for r in rows if not console_reply_context(r["class_path"], r["method_name"])]
        n_nonformal, n_unattributed = attach_nonformal_adds(rows, events)
        if n_unattributed:
            warn(f"{repo}: {n_unattributed} of {n_nonformal} non-formal ADD_LOG events in modified methods match no methods_changed row")
        problems = Counter()
        split = Counter({k: 0 for k in SPLIT_KEYS})
        for r in rows:
            problems.update(row_problems(r))
            split.update(split_keys(r))
        if split["positive_with_nonformal_add"] and not all("added_all_post" in r for r in rows):
            warn(f"{repo}: {split['positive_with_nonformal_add']} of {split['positive']} add_log positives "
                 f"keep a non-formal log added in the same commit (unmasked)")

        for task in ALL_TASKS:
            if task == "add_log_post":
                instances = add_log_post_instances(add_log_kept, rows)
                s = copy.deepcopy(stats["add_log"][repo])
            else:
                instances, s = build_task(task, repo, rows, info, sampling)
                if task == "add_log":
                    add_log_kept = instances
                if s["signature_key_overlap"]:
                    warn(f"{repo}/{task}: {s['signature_key_overlap']} negatives share (file, class, signature) with a positive")
            kept[task].extend(instances)
            stats[task][repo] = s

        check = core_check(events, rows)
        for label, c in check.items():
            if not c["match"]:
                warn(f"{repo}: core {label} events and methods_changed disagree: {c['n_only_events']} only in "
                     f"events, {c['n_only_rows']} only in methods_changed")
        per_repo[repo] = {
            "methods_changed_rows": len(all_rows),
            "bulk_rows": len(all_rows) - len(rows),
            "non_bulk_rows": len(rows) + n_header_only + n_console,
            "header_only_rows": n_header_only,
            "console_context_rows": n_console,
            "instance_rows": len(rows),
            "add_log_split": {k: split[k] for k in SPLIT_KEYS},
            "nonformal_adds": {"events": n_nonformal, "unattributed": n_unattributed},
            "row_problems": dict(sorted(problems.items())),
            "core_check": check,
            "events": event_counts(events),
        }
        del all_rows, rows

    inst_dir.mkdir(parents=True, exist_ok=True)
    for task in ALL_TASKS:
        write_jsonl(inst_dir / f"{task}.jsonl", kept[task])
    write_jsonl(out_dir / "events_master.jsonl", events_all)
    write_csv(out_dir / "events_master.csv", events_all)

    pos_counts = {t: {repo: stats[t][repo]["n_pos"] for repo in present} for t in ALL_TASKS}
    pos_commits = {t: {repo: Counter() for repo in present} for t in ALL_TASKS}
    for task in ALL_TASKS:
        for inst in kept[task]:
            if inst["sample_role"] == "positive":
                pos_commits[task][inst["repo"]][inst["commit_id"]] += 1
    folds = make_folds(pos_counts, present, protocol["min_test_positives"], protocol["low_support_positives"],
                       pos_commits)
    write_json(inst_dir / "folds.json", folds)

    totals = {}
    for task in ALL_TASKS:
        t = {"n_pos": 0, "n_neg_pool": 0, "n_written": 0, "n_neg": Counter()}
        for s in stats[task].values():
            t["n_pos"] += s["n_pos"]
            t["n_neg_pool"] += s["n_neg_pool"]
            t["n_written"] += s["n_written"]
            t["n_neg"].update(s["n_neg"])
        t["n_neg"] = dict(t["n_neg"])
        totals[task] = t

    summary = {
        "config": {"seed": sampling["seed"], "ratios": sampling["ratios"], "primary_ratio": sampling["primary_ratio"],
                   "min_test_positives": protocol["min_test_positives"],
                   "low_support_positives": protocol["low_support_positives"]},
        "repos": present,
        "missing_repos": missing,
        "inputs_sha1": inputs,
        "tasks": stats,
        "task_totals": totals,
        "per_repo": per_repo,
        "events_total": event_counts(events_all),
    }
    write_json(inst_dir / "summary.json", summary)
    return summary
