"""Tests for stage 4 (dataset assembly): labelling rules, sampling, ids, folds, summary."""

import hashlib
import json
import random
from collections import Counter

import pytest

from src.dataset.assemble import build_all, path_tag, core_check, attach_nonformal_adds
from src.dataset.folds import make_folds
from src.dataset.sampling import rank_negatives, sampling_key, sample_stats


def cid(k):
    return hashlib.sha1(str(k).encode()).hexdigest()


def mrow(repo, commit, ordinal=0, path="src/A.java", topo=1, **kw):
    row = {
        "repo": repo, "commit_id": commit, "parent_commit_id": cid("parent" + commit), "topo_index": topo,
        "timestamp": "2020-01-01T00:00:00+00:00", "author_id": "a1b2c3d4e5f6", "is_bulk": False,
        "pre_path": path, "post_path": path, "pre_blob": "1" * 40, "post_blob": "2" * 40, "change_type": "M",
        "class_path": "A", "method_name": f"m{ordinal}", "signature_pre": f"m{ordinal}()",
        "signature_post": f"m{ordinal}()", "kind": "method", "match_pass": 1,
        "pre_ordinal": ordinal, "post_ordinal": ordinal,
        "pre_start_line": 1, "pre_end_line": 9, "post_start_line": 1, "post_end_line": 9,
        "n_pre_formal": 0, "n_post_formal": 0, "n_pre_logs_all": 0, "n_post_logs_all": 0,
        "added_formal_post": [], "removed_formal_pre": [], "level_changed": [], "matched_formal": [],
        "pre_levels": [], "post_levels": [], "relocated_pre": [], "relocated_post": [],
        "other_log_change": False,
    }
    row.update(kw)
    return row


def event(repo, commit, n, label, validity="core", scope="modified_method", style="formal", topo=1, **kw):
    # all events.jsonl fields; the statement defaults to formal index 0 of m0() in src/A.java
    e = {"event_id": f"{repo}:{commit[:12]}:{n}", "repo": repo, "commit_id": commit,
         "parent_commit_id": cid("parent" + commit), "topo_index": topo,
         "timestamp": "2020-01-01T00:00:00+00:00", "author_id": "a1b2c3d4e5f6",
         "is_bulk": validity == "bulk", "scope": scope, "event_label": label, "logging_style": style,
         "framework": "slf4j" if style == "formal" else "stdout", "file_path": "src/A.java",
         "pre_path": "src/A.java", "post_path": "src/A.java", "class_path": "A", "method_signature": "m0()",
         "call_name": "log.info", "call_text": "log.info(\"x\")", "call_text_before": None,
         "pre_level": None if label == "ADD_LOG" else "INFO",
         "post_level": None if label == "REMOVE_LOG" else "INFO",
         "statement_continuity": "matched" if label == "CHANGE_LEVEL" else "none", "match_confidence": None,
         "pre_line": None, "post_line": 3,
         "pre_formal_index": None if label == "ADD_LOG" else 0,
         "post_formal_index": None if label == "REMOVE_LOG" else 0,
         "is_relocated": validity == "relocated", "validity_status": validity}
    if style != "formal":
        e["pre_formal_index"] = e["post_formal_index"] = None
    e.update(kw)
    return e


def write_mining(root, repo, rows, events=()):
    # commits and file_changes are not read by stage 4, only their row counts are checked
    d = root / "mining" / repo
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "methods_changed.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    with open(d / "events.jsonl", "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    (d / "commits.jsonl").write_text("")
    (d / "file_changes.jsonl").write_text("")
    summary = {"repo": repo, "n_commits": 0, "file_changes_rows": 0, "events": len(events),
               "methods_changed": len(rows)}
    (d / "summary.json").write_text(json.dumps(summary))


def load(root, task):
    with open(root / "out" / "instances" / f"{task}.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def build(root, repos):
    return build_all(root / "mining", root / "out", repos)


def by_id(rows):
    return {r["instance_id"]: r for r in rows}


# labelling rules

def test_add_log_rules_relocation_bulk_and_neither(tmp_path):
    repo = "OpenKeeper"
    c = cid(1)
    rows = [
        # genuine add at 0, relocated add at 1: positive, both masked
        mrow(repo, c, 0, n_post_formal=2, post_levels=["INFO", "INFO"], added_formal_post=[0, 1], relocated_post=[1]),
        # only a relocated add: neither positive nor clean
        mrow(repo, c, 1, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0], relocated_post=[0]),
        # only a removal: neither
        mrow(repo, c, 2, n_pre_formal=1, pre_levels=["DEBUG"], removed_formal_pre=[0]),
        # print / text change only: neither
        mrow(repo, c, 3, other_log_change=True),
        # clean, no logs
        mrow(repo, c, 4),
        # clean, with an unchanged log
        mrow(repo, c, 5, n_pre_formal=1, n_post_formal=1, pre_levels=["INFO"], post_levels=["INFO"],
             matched_formal=[[0, 0, 1.0]]),
        # bulk commit: never an instance
        mrow(repo, cid(2), 0, topo=2, is_bulk=True, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0]),
        mrow(repo, cid(2), 1, topo=2, is_bulk=True),
    ]
    write_mining(tmp_path, repo, rows)
    summary = build(tmp_path, [repo])
    inst = load(tmp_path, "add_log")
    tag = path_tag("src/A.java")

    pos = [i for i in inst if i["label"] == 1]
    neg = [i for i in inst if i["label"] == 0]
    assert len(pos) == 1 and len(neg) == 2
    p = pos[0]
    assert p["instance_id"] == f"add_log:{repo}:{c[:12]}:{tag}:0"
    # primary view: the method before the commit, nothing masked, no anchor
    assert p["view"] == "pre" and "mask_post_idx" not in p and "anchor_pre_idx" not in p
    assert p["sample_role"] == "positive" and p["neg_rank"] == -1
    assert p["engine"] == "jME" and p["size"] == "Large"
    assert sorted(n["post_ordinal"] for n in neg) == [4, 5]
    assert all(n["view"] == "pre" and "mask_post_idx" not in n for n in neg)
    assert all(n["neg_provenance"] == "modified_method_no_log_change" for n in neg)
    # sensitivity view: the same instances, masked post-state
    post = by_id(load(tmp_path, "add_log_post"))
    assert sorted(post) == sorted("add_log_post:" + i["instance_id"][len("add_log:"):] for i in inst)
    pp = post[f"add_log_post:{repo}:{c[:12]}:{tag}:0"]
    assert pp["view"] == "post_masked" and pp["mask_post_idx"] == [0, 1] and pp["task"] == "add_log_post"
    assert all(i["mask_post_idx"] == [] for i in post.values() if i["label"] == 0)
    assert all(i["commit_id"] == c for i in inst)
    assert all(i["other_log_change"] is False and i["n_nonformal_added"] == 0 for i in inst)
    split = summary["per_repo"][repo]["add_log_split"]
    assert split == {"positive": 1, "clean_negative": 2, "neither": 3, "neither_only_other_log_change": 1,
                     "positive_with_other_log_change": 0, "positive_with_nonformal_add": 0,
                     "positive_with_removal": 0, "positive_with_level_change": 0, "positive_with_relocation": 1}
    assert summary["per_repo"][repo]["bulk_rows"] == 2


def test_remove_log_statement_rules(tmp_path):
    repo = "OpenKeeper"
    c = cid(1)
    row = mrow(repo, c, 3, n_pre_formal=4, n_post_formal=2,
               pre_levels=["DEBUG", "INFO", "WARN", None], post_levels=["INFO", None],
               removed_formal_pre=[0, 2], relocated_pre=[2], matched_formal=[[1, 0, 0.8], [3, 1, 1.0]])
    write_mining(tmp_path, repo, [row])
    build(tmp_path, [repo])
    inst = by_id(load(tmp_path, "remove_log"))
    base = f"remove_log:{repo}:{c[:12]}:{path_tag('src/A.java')}:3"
    assert sorted(inst) == [f"{base}:0", f"{base}:1", f"{base}:3"]  # 2 is relocated
    p = inst[f"{base}:0"]
    assert p["label"] == 1 and p["anchor_pre_idx"] == 0 and p["anchor_level"] == "DEBUG"
    assert p["view"] == "pre" and p["match_ratio"] is None
    n1 = inst[f"{base}:1"]
    assert n1["label"] == 0 and n1["neg_provenance"] == "retained_statement"
    assert n1["anchor_level"] == "INFO" and n1["match_ratio"] == 0.8 and n1["anchor_post_idx"] == 0
    assert inst[f"{base}:3"]["anchor_level"] is None


def test_change_level_rules(tmp_path):
    repo = "OpenKeeper"
    c = cid(1)
    row = mrow(repo, c, 0, n_pre_formal=3, n_post_formal=3,
               pre_levels=["DEBUG", "INFO", None], post_levels=["INFO", "INFO", "WARN"],
               matched_formal=[[0, 0, 0.9], [1, 1, 0.7], [2, 2, 0.6]], level_changed=[[0, 0]])
    write_mining(tmp_path, repo, [row])
    summary = build(tmp_path, [repo])
    inst = by_id(load(tmp_path, "change_level"))
    base = f"change_level:{repo}:{c[:12]}:{path_tag('src/A.java')}:0"
    assert sorted(inst) == [f"{base}:0", f"{base}:1"]  # 2 has an unknown pre level
    p = inst[f"{base}:0"]
    assert (p["label"], p["anchor_level"], p["post_level"], p["match_ratio"]) == (1, "DEBUG", "INFO", 0.9)
    n = inst[f"{base}:1"]
    assert (n["label"], n["anchor_level"], n["post_level"], n["neg_provenance"]) == (0, "INFO", "INFO", "same_level_statement")
    assert summary["per_repo"][repo]["row_problems"] == {}
    # the matched statements are negatives of remove_log too
    assert len(load(tmp_path, "remove_log")) == 0  # n_pos == 0 -> no negatives kept
    assert summary["tasks"]["remove_log"][repo]["n_neg_pool"] == 3


def test_multiclass_priority_and_exclusions(tmp_path):
    repo = "OpenKeeper"
    c = cid(1)
    rows = [
        mrow(repo, c, 0, n_pre_formal=2, n_post_formal=2, pre_levels=["DEBUG", "INFO"], post_levels=["INFO", "WARN"],
             removed_formal_pre=[1], added_formal_post=[1], matched_formal=[[0, 0, 0.9]], level_changed=[[0, 0]]),
        mrow(repo, c, 1, n_pre_formal=1, n_post_formal=1, pre_levels=["INFO"], post_levels=["INFO"],
             removed_formal_pre=[0], added_formal_post=[0]),
        mrow(repo, c, 2, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0]),
        mrow(repo, c, 3, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0], relocated_post=[0]),
        mrow(repo, c, 4),
        mrow(repo, c, 5, other_log_change=True),
    ]
    write_mining(tmp_path, repo, rows)
    summary = build(tmp_path, [repo])
    inst = {i["pre_ordinal"]: i for i in load(tmp_path, "multiclass")}
    assert sorted(inst) == [0, 1, 2, 4]
    assert inst[0]["label"] == "CHANGE_LEVEL" and inst[0]["labels_multi"] == ["ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]
    assert inst[1]["label"] == "REMOVE_LOG" and inst[1]["labels_multi"] == ["ADD_LOG", "REMOVE_LOG"]
    assert inst[2]["label"] == "ADD_LOG"
    assert inst[4]["label"] == "NO_EVENT" and inst[4]["sample_role"] == "negative" and inst[4]["labels_multi"] == []
    assert all(i["view"] == "pre" for i in inst.values())
    assert inst[0]["instance_id"] == f"multiclass:{repo}:{c[:12]}:{path_tag('src/A.java')}:0"
    s = summary["tasks"]["multiclass"][repo]
    assert s["n_pos"] == 3 and s["by_label"] == {"ADD_LOG": 1, "CHANGE_LEVEL": 1, "REMOVE_LOG": 1}
    assert set(s["n_neg"]) == {"R1", "R4"}  # only settings up to the primary ratio


# sampling

def test_nested_sampling(tmp_path):
    repo = "Mindustry"
    rows = [mrow(repo, cid(k), 0, topo=k, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0])
            for k in range(3)]
    rows += [mrow(repo, cid(100 + k), 0, topo=100 + k) for k in range(50)]
    write_mining(tmp_path, repo, rows)
    summary = build(tmp_path, [repo])
    inst = load(tmp_path, "add_log")
    pos = [i for i in inst if i["label"] == 1]
    neg = [i for i in inst if i["label"] == 0]
    assert len(pos) == 3 and len(neg) == 30
    assert all(p["neg_rank"] == -1 and p["in_R1"] and p["in_R4"] and p["in_R10"] for p in pos)
    assert sorted(n["neg_rank"] for n in neg) == list(range(30))
    r1 = {n["instance_id"] for n in neg if n["in_R1"]}
    r4 = {n["instance_id"] for n in neg if n["in_R4"]}
    r10 = {n["instance_id"] for n in neg if n["in_R10"]}
    assert len(r1) == 3 and len(r4) == 12 and len(r10) == 30
    assert r1 < r4 < r10
    s = summary["tasks"]["add_log"][repo]
    assert s["n_pos"] == 3 and s["n_neg_pool"] == 50
    assert s["n_neg"] == {"R1": 3, "R4": 12, "R10": 30}
    assert s["ratio"] == {"R1": 1.0, "R4": 4.0, "R10": 10.0}
    # written rows are in chronological order
    assert [i["topo_index"] for i in inst] == sorted(i["topo_index"] for i in inst)


def test_small_pool_and_zero_positives(tmp_path):
    rows_a = [mrow("OpenKeeper", cid(k), 0, topo=k, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0])
              for k in range(3)]
    rows_a += [mrow("OpenKeeper", cid(100 + k), 0, topo=100 + k) for k in range(5)]
    rows_b = [mrow("OpenRTS", cid(200 + k), 0, topo=k) for k in range(5)]
    write_mining(tmp_path, "OpenKeeper", rows_a)
    write_mining(tmp_path, "OpenRTS", rows_b)
    summary = build(tmp_path, ["OpenKeeper", "OpenRTS"])
    a = summary["tasks"]["add_log"]["OpenKeeper"]
    assert a["n_neg"] == {"R1": 3, "R4": 5, "R10": 5} and a["ratio"]["R4"] == round(5 / 3, 4)
    b = summary["tasks"]["add_log"]["OpenRTS"]
    assert b["n_pos"] == 0 and b["n_neg_pool"] == 5 and b["n_neg"]["R10"] == 0 and b["ratio"]["R4"] is None
    assert not [i for i in load(tmp_path, "add_log") if i["repo"] == "OpenRTS"]


def test_rank_negatives_is_seeded_and_nested():
    negs = [{"instance_id": f"x:{k:03d}"} for k in range(40)]
    shuffled = list(negs)
    random.Random(7).shuffle(shuffled)
    a = rank_negatives([dict(n) for n in negs], 2, [1, 4, 10], sampling_key(42, "add_log", "R"))
    b = rank_negatives([dict(n) for n in shuffled], 2, [1, 4, 10], sampling_key(42, "add_log", "R"))
    assert [n["instance_id"] for n in a] == [n["instance_id"] for n in b]
    c = rank_negatives([dict(n) for n in negs], 2, [1, 4, 10], sampling_key(42, "add_log", "S"))
    assert [n["instance_id"] for n in a] != [n["instance_id"] for n in c]
    assert sum(n["in_R1"] for n in a) == 2 and sum(n["in_R10"] for n in a) == 20
    assert all(n["in_R10"] for n in a if n["in_R4"]) and all(n["in_R4"] for n in a if n["in_R1"])
    assert sample_stats(0, 5, [1]) == ({"R1": 0}, {"R1": None})


def _two_repo_rows():
    # one positive per task and per repo, pools larger than the kept sample
    rows = {}
    for repo, off in (("OpenKeeper", 0), ("OpenRTS", 1000)):
        rr = []
        for k in range(6):
            c = cid(off + k)
            pre = ["DEBUG" if k == 0 else "INFO", "INFO", "INFO", "INFO"]
            rr.append(mrow(repo, c, 0, topo=k, n_pre_formal=4, n_post_formal=4, pre_levels=pre,
                           post_levels=["INFO"] * 4, matched_formal=[[i, i, 0.9] for i in range(4)],
                           level_changed=[[0, 0]] if k == 0 else []))
            if k == 0:
                rr.append(mrow(repo, c, 1, topo=k, n_pre_formal=1, n_post_formal=1, pre_levels=["WARN"],
                               post_levels=["INFO"], removed_formal_pre=[0], added_formal_post=[0]))
            for j in range(2, 12):
                rr.append(mrow(repo, c, j, topo=k))
        rows[repo] = rr
    return rows


def test_determinism_independent_of_repo_and_row_order(tmp_path):
    rows = _two_repo_rows()
    for name in ("ab", "ba", "a", "shuffled"):
        root = tmp_path / name
        a_rows = list(rows["OpenKeeper"])
        if name == "shuffled":
            random.Random(3).shuffle(a_rows)
        write_mining(root, "OpenKeeper", a_rows)
        write_mining(root, "OpenRTS", rows["OpenRTS"])
    summary = build(tmp_path / "ab", ["OpenKeeper", "OpenRTS"])
    for task in ("add_log", "remove_log", "change_level"):
        s = summary["tasks"][task]["OpenKeeper"]
        assert s["n_pos"] == 1 and s["n_neg_pool"] > s["n_neg"]["R10"] == 10
    build(tmp_path / "ba", ["OpenRTS", "OpenKeeper"])
    build(tmp_path / "a", ["OpenKeeper"])
    build(tmp_path / "shuffled", ["OpenKeeper", "OpenRTS"])
    for task in ("add_log", "add_log_post", "remove_log", "change_level", "multiclass"):
        ref = [i for i in load(tmp_path / "ab", task) if i["repo"] == "OpenKeeper"]
        assert ref
        for name in ("ba", "a", "shuffled"):
            other = [i for i in load(tmp_path / name, task) if i["repo"] == "OpenKeeper"]
            assert other == ref, (task, name)
    assert (tmp_path / "ab" / "out" / "instances" / "add_log.jsonl").read_bytes() == \
        (tmp_path / "ba" / "out" / "instances" / "add_log.jsonl").read_bytes()


def test_rebuild_is_idempotent(tmp_path):
    rows = _two_repo_rows()
    write_mining(tmp_path, "OpenKeeper", rows["OpenKeeper"], [event("OpenKeeper", cid(0), 0, "ADD_LOG")])
    build(tmp_path, ["OpenKeeper"])
    out = tmp_path / "out"
    files = sorted(p for p in out.rglob("*") if p.is_file())
    first = {p: p.read_bytes() for p in files}
    build(tmp_path, ["OpenKeeper"])
    assert {p: p.read_bytes() for p in files} == first
    assert not list(out.rglob("*.tmp"))


# ids, folds, summary

def test_ids_unique_when_ordinals_repeat_across_files(tmp_path):
    repo = "OpenKeeper"
    c = cid(1)
    rows = [mrow(repo, c, 0, path=p, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0])
            for p in ("src/A.java", "src/B.java")]
    write_mining(tmp_path, repo, rows)
    build(tmp_path, [repo])
    ids = [i["instance_id"] for i in load(tmp_path, "add_log")]
    assert len(ids) == 2 and len(set(ids)) == 2

    write_mining(tmp_path, repo, rows + [rows[0]])
    with pytest.raises(AssertionError, match="duplicate instance_ids"):
        build(tmp_path, [repo])


def test_add_log_unit_check_uses_the_pre_state_unit():
    from src.common.config import load_config
    from src.dataset.assemble import unit_key, signature_key, build_task

    repo = "OpenKeeper"
    c = cid(1)
    sampling = load_config("experiment")["sampling"]
    info = {"engine": "jME", "size": "Large"}
    # one pre-state method split into two post-state methods, one of them with an added log:
    # distinct post units, but the same add_log input (the pre view) with both labels
    rows = [mrow(repo, c, 0, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0], n_nonformal_added=0),
            mrow(repo, c, 1, pre_ordinal=0, signature_pre="m0()", n_nonformal_added=0)]
    with pytest.raises(AssertionError, match="units both positive and negative"):
        build_task("add_log", repo, rows, info, sampling)
    rows[1]["pre_ordinal"] = 1
    kept, stats = build_task("add_log", repo, rows, info, sampling)
    assert stats["n_pos"] == 1 and stats["n_neg_pool"] == 1

    inst = {"repo": repo, "commit_id": c, "pre_path": "a", "post_path": "b", "pre_ordinal": 1, "post_ordinal": 2,
            "class_path": "B", "class_path_pre": "A", "signature_pre": "f()", "signature_post": "g()"}
    assert unit_key(dict(inst, view="pre")) == (repo, c, "a", 1, None)
    assert unit_key(dict(inst, view="post_masked")) == (repo, c, "b", 2)
    assert signature_key(dict(inst, view="pre")) == (repo, c, "a", "A", "f()", None)
    assert signature_key(dict(inst, view="post_masked")) == (repo, c, "b", "B", "g()")


def test_folds_eligibility(tmp_path):
    counts = {"OpenKeeper": 35, "Mindustry": 12, "OpenRTS": 3}
    off = 0
    for repo, n in counts.items():
        rows = [mrow(repo, cid(off + k), 0, topo=k, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0])
                for k in range(n)]
        rows += [mrow(repo, cid(off + 500 + k), 0, topo=500 + k) for k in range(5)]
        write_mining(tmp_path, repo, rows)
        off += 1000
    build(tmp_path, ["OpenRTS", "OpenKeeper", "Mindustry"])
    folds = json.loads((tmp_path / "out" / "instances" / "folds.json").read_text())
    assert set(folds) == {"add_log", "add_log_post", "remove_log", "change_level", "multiclass"}
    assert folds["add_log"] == {
        "test_repos": ["OpenKeeper", "Mindustry"], "low_support": ["Mindustry"], "excluded": {"OpenRTS": 3},
        "per_repo": {"OpenKeeper": {"n_pos": 35, "n_pos_commits": 35, "max_commit_share": 0.0286},
                     "Mindustry": {"n_pos": 12, "n_pos_commits": 12, "max_commit_share": 0.0833},
                     "OpenRTS": {"n_pos": 3, "n_pos_commits": 3, "max_commit_share": 0.3333}},
        "few_commit_folds": []}
    assert folds["add_log_post"] == folds["add_log"]
    # multiclass counts event rows (here the same ADD_LOG rows)
    assert folds["multiclass"]["test_repos"] == ["OpenKeeper", "Mindustry"]
    assert folds["remove_log"]["test_repos"] == [] and folds["remove_log"]["excluded"]["OpenKeeper"] == 0


def test_make_folds_thresholds():
    f = make_folds({"t": {"A": 10, "B": 9, "C": 30}}, ["C", "B", "A"], 10, 30)
    assert f["t"] == {"test_repos": ["C", "A"], "low_support": ["A"], "excluded": {"B": 9}}


def test_folds_commit_concentration(tmp_path):
    commits = {"t": {"A": Counter({"c1": 9, "c2": 3}), "B": Counter({"c3": 4, "c4": 4, "c5": 4}),
                     "C": Counter({"c6": 5}), "D": Counter()}}
    f = make_folds({"t": {"A": 12, "B": 12, "C": 5, "D": 0}}, ["A", "B", "C", "D"], 10, 30, commits)["t"]
    assert f["test_repos"] == ["A", "B"] and f["low_support"] == ["A", "B"]
    assert f["per_repo"]["A"] == {"n_pos": 12, "n_pos_commits": 2, "max_commit_share": 0.75}
    assert f["per_repo"]["B"] == {"n_pos": 12, "n_pos_commits": 3, "max_commit_share": 0.3333}
    assert f["per_repo"]["D"] == {"n_pos": 0, "n_pos_commits": 0, "max_commit_share": None}
    # only test repositories are listed: C has a single commit but is not a fold
    assert f["few_commit_folds"] == ["A"]

    # the same numbers from assembled positives: 9 methods of one commit, 3 of another
    repo = "OpenKeeper"
    rows = [mrow(repo, cid(1) if k < 9 else cid(2), k, topo=1 if k < 9 else 2, n_post_formal=1,
                 post_levels=["INFO"], added_formal_post=[0]) for k in range(12)]
    rows += [mrow(repo, cid(100 + k), 0, topo=100 + k) for k in range(5)]
    write_mining(tmp_path, repo, rows)
    build(tmp_path, [repo])
    folds = json.loads((tmp_path / "out" / "instances" / "folds.json").read_text())
    assert folds["add_log"]["per_repo"][repo] == {"n_pos": 12, "n_pos_commits": 2, "max_commit_share": 0.75}
    assert folds["add_log"]["few_commit_folds"] == [repo] and folds["add_log_post"] == folds["add_log"]
    assert folds["remove_log"]["per_repo"][repo]["max_commit_share"] is None


def test_add_log_post_mirrors_add_log(tmp_path):
    rows = _two_repo_rows()
    for repo in rows:
        write_mining(tmp_path, repo, rows[repo])
    summary = build(tmp_path, ["OpenKeeper", "OpenRTS"])
    add = load(tmp_path, "add_log")
    post = load(tmp_path, "add_log_post")
    assert len(add) == len(post) > 0 and any(i["label"] == 1 for i in add)
    for a, p in zip(add, post):
        assert p["instance_id"] == "add_log_post:" + a["instance_id"][len("add_log:"):]
        assert (a["task"], a["view"], p["task"], p["view"]) == ("add_log", "pre", "add_log_post", "post_masked")
        rest = {k: v for k, v in p.items() if k not in ("instance_id", "task", "view", "mask_post_idx")}
        assert rest == {k: v for k, v in a.items() if k not in ("instance_id", "task", "view")}
        assert p["mask_post_idx"] == ([0] if a["label"] else [])
    assert summary["tasks"]["add_log_post"] == summary["tasks"]["add_log"]
    assert summary["task_totals"]["add_log_post"] == summary["task_totals"]["add_log"]


def test_partial_mining_output_is_refused(tmp_path, monkeypatch, capsys):
    from scripts import build_datasets

    repo = "OpenKeeper"
    rows = [mrow(repo, cid(1), 0, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0]),
            mrow(repo, cid(2), 0, topo=2)]
    d = tmp_path / "mining" / repo
    # an interrupted run: methods_changed cut short next to the summary of a complete run
    write_mining(tmp_path, repo, rows)
    (d / "methods_changed.jsonl").write_text(json.dumps(rows[0]) + "\n")
    with pytest.raises(ValueError, match="methods_changed.jsonl has 1 rows but summary.json says 2"):
        build(tmp_path, [repo])
    assert not (tmp_path / "out").exists()

    write_mining(tmp_path, repo, rows)
    (d / "commits.jsonl").write_text('{"commit_id": "x"}\n')
    with pytest.raises(ValueError, match="commits.jsonl has 1 rows but summary.json says 0"):
        build(tmp_path, [repo])
    write_mining(tmp_path, repo, rows)
    (d / "file_changes.jsonl").unlink()
    with pytest.raises(ValueError, match="file_changes.jsonl is missing"):
        build(tmp_path, [repo])
    write_mining(tmp_path, repo, rows)
    (d / "summary.json").write_text(json.dumps({"n_commits": 0, "file_changes_rows": 0, "methods_changed": 2}))
    with pytest.raises(ValueError, match="no 'events' count"):
        build(tmp_path, [repo])
    (d / "summary.json").unlink()
    with pytest.raises(ValueError, match="summary.json is missing"):
        build(tmp_path, [repo])

    write_mining(tmp_path, repo, rows)
    (d / "methods_changed.jsonl").write_text(json.dumps(rows[0]) + "\n")
    monkeypatch.setattr("sys.argv", ["build_datasets", "--repos", repo, "--mining-dir", str(tmp_path / "mining"),
                                     "--out", str(tmp_path / "out")])
    with pytest.raises(SystemExit) as exit_info:
        build_datasets.main()
    assert exit_info.value.code == 1 and "partial or stale" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()

    write_mining(tmp_path, repo, rows)
    assert build(tmp_path, [repo])["repos"] == [repo]


def test_events_master_and_summary(tmp_path):
    repo = "shattered-pixel-dungeon"
    c1, c2 = cid(1), cid(2)
    rows = [mrow(repo, c1, 0, n_pre_formal=1, n_post_formal=1, pre_levels=["DEBUG"], post_levels=["INFO"],
                 added_formal_post=[0], removed_formal_pre=[0])]
    events = [
        event(repo, c2, 0, "ADD_LOG", validity="bulk", scope="new_file", topo=2),
        event(repo, c1, 1, "REMOVE_LOG", pre_level="DEBUG"),
        event(repo, c1, 0, "ADD_LOG"),
        event(repo, c1, 2, "ADD_LOG", validity="non_formal", style="game_message", method_signature="other()"),
    ]
    write_mining(tmp_path, repo, rows, events)
    summary = build(tmp_path, [repo])
    out = tmp_path / "out"
    with open(out / "events_master.jsonl", encoding="utf-8") as f:
        master = [json.loads(l) for l in f]
    assert [e["event_id"].rsplit(":", 1)[1] for e in master] == ["0", "1", "2", "0"]
    assert list(master[0])[:4] == ["event_id", "repo", "engine", "size"]
    assert master[0]["engine"] == "libGDX" and master[0]["size"] == "Large"
    header = (out / "events_master.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("event_id,repo,engine,size,")
    ev = summary["per_repo"][repo]["events"]
    assert ev["total"] == 4
    assert ev["validity_status"] == {"bulk": 1, "core": 2, "non_formal": 1}
    assert ev["logging_style"] == {"formal": 3, "game_message": 1}
    assert ev["label_by_validity"]["ADD_LOG"] == {"bulk": 1, "core": 1, "non_formal": 1}
    check = summary["per_repo"][repo]["core_check"]
    assert check["ADD_LOG"]["match"] and check["REMOVE_LOG"]["match"] and check["CHANGE_LEVEL"]["match"]
    assert check["ADD_LOG"]["core_events"] == check["ADD_LOG"]["from_methods_changed"] == 1
    assert summary["inputs_sha1"][repo]["events.jsonl"]
    # the game_message add names a method that has no methods_changed row: unattributed
    assert summary["per_repo"][repo]["nonformal_adds"] == {"events": 1, "unattributed": 1}


def test_missing_repo_is_skipped_with_warning(tmp_path, capsys):
    write_mining(tmp_path, "OpenKeeper", [mrow("OpenKeeper", cid(1), 0)])
    summary = build(tmp_path, ["OpenKeeper", "riiablo"])
    assert summary["repos"] == ["OpenKeeper"]
    assert "riiablo" in summary["missing_repos"]
    assert "riiablo: skipped" in capsys.readouterr().err
    with pytest.raises(ValueError):
        build(tmp_path, ["NotARepo"])
    # nothing present: an earlier build is left untouched
    before = (tmp_path / "out" / "instances" / "summary.json").read_bytes()
    assert build(tmp_path, ["riiablo"])["repos"] == []
    assert (tmp_path / "out" / "instances" / "summary.json").read_bytes() == before


def test_row_consistency_problems_are_counted(tmp_path):
    repo = "OpenKeeper"
    # level differs but level_changed is empty, and post statement 1 is unaccounted
    row = mrow(repo, cid(1), 0, n_pre_formal=1, n_post_formal=2, pre_levels=["DEBUG"], post_levels=["INFO", "INFO"],
               matched_formal=[[0, 0, 0.9]])
    write_mining(tmp_path, repo, [row])
    summary = build(tmp_path, [repo])
    assert summary["per_repo"][repo]["row_problems"] == {"level_changed_mismatch": 1, "post_statement_unaccounted": 1}


# further labelling cases

def test_other_log_change_asymmetry_is_recorded(tmp_path, capsys):
    repo = "OpenKeeper"
    c = cid(1)
    rows = [
        # formal log and a System.out added together: positive, the print stays visible after masking
        mrow(repo, c, 0, n_post_formal=1, n_post_logs_all=2, post_levels=["INFO"], added_formal_post=[0],
             other_log_change=True),
        mrow(repo, c, 1, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0]),
        # add + removal + level change in one method
        mrow(repo, c, 2, n_pre_formal=2, n_post_formal=2, pre_levels=["INFO", "DEBUG"], post_levels=["INFO", "WARN"],
             removed_formal_pre=[0], added_formal_post=[1], matched_formal=[[1, 0, 0.9]], level_changed=[[1, 0]]),
        mrow(repo, c, 3, other_log_change=True),
        mrow(repo, c, 4),
        mrow(repo, c, 5),
        # events show a print added here but the row says nothing changed: not a negative, flagged
        mrow(repo, c, 6),
    ]
    events = [
        event(repo, c, 0, "ADD_LOG", validity="non_formal", style="informal_print", method_signature="m0()"),
        event(repo, c, 1, "ADD_LOG", validity="non_formal", style="informal_print", method_signature="m6()"),
        event(repo, c, 2, "ADD_LOG", validity="non_formal", style="informal_print", method_signature="gone()"),
    ]
    write_mining(tmp_path, repo, rows, events)
    summary = build(tmp_path, [repo])
    r = summary["per_repo"][repo]
    assert r["add_log_split"] == {"positive": 3, "clean_negative": 2, "neither": 2, "neither_only_other_log_change": 2,
                                  "positive_with_other_log_change": 1, "positive_with_nonformal_add": 1,
                                  "positive_with_removal": 1, "positive_with_level_change": 1,
                                  "positive_with_relocation": 0}
    assert r["nonformal_adds"] == {"events": 3, "unattributed": 1}
    assert r["row_problems"] == {"nonformal_add_without_other_log_change": 1}
    inst = {i["post_ordinal"]: i for i in load(tmp_path, "add_log")}
    assert sorted(inst) == [0, 1, 2, 4, 5]
    assert (inst[0]["other_log_change"], inst[0]["n_nonformal_added"]) == (True, 1)
    assert (inst[1]["other_log_change"], inst[1]["n_nonformal_added"]) == (False, 0)
    assert all(not inst[k]["other_log_change"] and inst[k]["n_nonformal_added"] == 0 for k in (4, 5))
    multi = {i["pre_ordinal"]: i for i in load(tmp_path, "multiclass")}
    assert multi[0]["other_log_change"] is True and 6 not in multi
    err = capsys.readouterr().err
    assert "1 of 3 non-formal ADD_LOG events" in err and "1 of 3 add_log positives" in err


def test_attach_nonformal_adds_ignores_formal_bulk_and_other_scopes():
    c = cid(1)
    rows = [mrow("OpenKeeper", c, 0)]
    events = [
        event("OpenKeeper", c, 0, "ADD_LOG"),  # formal
        event("OpenKeeper", c, 1, "ADD_LOG", validity="non_formal", style="informal_print", scope="new_method"),
        event("OpenKeeper", c, 2, "REMOVE_LOG", validity="non_formal", style="informal_print"),
        event("OpenKeeper", c, 3, "ADD_LOG", validity="non_formal", style="game_message"),
        event("OpenKeeper", c, 4, "ADD_LOG", validity="non_formal", style="game_message", is_bulk=True),
    ]
    assert attach_nonformal_adds(rows, events) == (1, 0)
    assert rows[0]["n_nonformal_added"] == 1


def test_contract_drift_fails_loudly(tmp_path):
    repo = "OpenKeeper"
    good = [mrow(repo, cid(1), 0, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0]),
            mrow(repo, cid(2), 0, topo=2)]

    renamed = [dict(r) for r in good]
    renamed[1]["other_log_changed"] = renamed[1].pop("other_log_change")
    write_mining(tmp_path / "a", repo, renamed)
    with pytest.raises(ValueError, match="missing .*other_log_change"):
        build(tmp_path / "a", [repo])
    assert not (tmp_path / "a" / "out").exists()

    wrong_type = [dict(r) for r in good]
    wrong_type[1]["relocated_post"] = None
    write_mining(tmp_path / "b", repo, wrong_type)
    with pytest.raises(ValueError, match="wrong type .*relocated_post"):
        build(tmp_path / "b", [repo])

    ev = event(repo, cid(1), 0, "ADD_LOG")
    del ev["method_signature"]
    write_mining(tmp_path / "c", repo, good, [ev])
    with pytest.raises(ValueError, match="missing .*method_signature"):
        build(tmp_path / "c", [repo])

    write_mining(tmp_path / "d", repo, good, [event(repo, cid(1), 0, "ADD")])
    with pytest.raises(ValueError, match="event_label=ADD"):
        build(tmp_path / "d", [repo])


def test_rows_and_events_of_another_repo_are_rejected(tmp_path):
    rows = [mrow("OpenKeeper", cid(1), 0)]
    write_mining(tmp_path / "a", "OpenKeeper", rows, [event("Mindustry", cid(5), 0, "ADD_LOG")])
    with pytest.raises(ValueError, match="events.jsonl: 1 rows with repo != OpenKeeper"):
        build(tmp_path / "a", ["OpenKeeper"])
    write_mining(tmp_path / "b", "OpenKeeper", rows + [mrow("Mindustry", cid(2), 0)])
    with pytest.raises(ValueError, match="methods_changed.jsonl: 1 rows with repo != OpenKeeper"):
        build(tmp_path / "b", ["OpenKeeper"])


def test_core_check_compares_statement_keys(tmp_path, capsys):
    repo = "OpenKeeper"
    c = cid(1)
    rows = [
        mrow(repo, c, 0, n_post_formal=1, post_levels=["INFO"], added_formal_post=[0]),
        mrow(repo, c, 1, n_pre_formal=1, n_post_formal=1, pre_levels=["DEBUG"], post_levels=["WARN"],
             matched_formal=[[0, 0, 0.9]], level_changed=[[0, 0]]),
    ]
    level = event(repo, c, 1, "CHANGE_LEVEL", pre_level="DEBUG", post_level="WARN", method_signature="m1()")
    ok = core_check([event(repo, c, 0, "ADD_LOG"), level], rows)
    assert all(ok[t]["match"] for t in ok) and ok["CHANGE_LEVEL"]["core_events"] == 1

    # equal counts, different statements: one missing event, one extra in an unrelated commit
    moved = core_check([event(repo, cid(999), 0, "ADD_LOG"), level], rows)["ADD_LOG"]
    assert (moved["core_events"], moved["from_methods_changed"]) == (1, 1)
    assert not moved["match"] and moved["n_only_events"] == 1 and moved["n_only_rows"] == 1
    assert moved["examples_only_events"] == [[cid(999), "src/A.java", "m0()", 0, "INFO"]]
    assert moved["examples_only_rows"] == [[c, "src/A.java", "m0()", 0, "INFO"]]
    # same statement, different level
    assert not core_check([event(repo, c, 0, "ADD_LOG", post_level="WARN"), level], rows)["ADD_LOG"]["match"]
    # non-core events are not compared
    bulk = event(repo, c, 0, "ADD_LOG", validity="bulk")
    assert core_check([bulk, level], rows)["ADD_LOG"]["n_only_rows"] == 1

    write_mining(tmp_path, repo, rows, [event(repo, cid(999), 0, "ADD_LOG"), level])
    summary = build(tmp_path, [repo])
    assert not summary["per_repo"][repo]["core_check"]["ADD_LOG"]["match"]
    assert "core ADD_LOG events and methods_changed disagree: 1 only in events, 1 only in methods_changed" \
        in capsys.readouterr().err


def test_relocations_kept_apart_from_added_and_removed(tmp_path):
    # the miner lists relocated indices apart from added/removed; both conventions must read the same
    repo = "OpenKeeper"
    c = cid(1)
    rows = [
        mrow(repo, c, 0, n_post_formal=2, post_levels=["INFO", "INFO"], added_formal_post=[0], relocated_post=[1]),
        mrow(repo, c, 1, n_post_formal=1, post_levels=["INFO"], relocated_post=[0]),
        mrow(repo, c, 2, n_pre_formal=2, n_post_formal=1, pre_levels=["INFO", "WARN"], post_levels=["INFO"],
             removed_formal_pre=[0], relocated_pre=[1], added_formal_post=[0]),
        mrow(repo, c, 3, n_pre_formal=1, n_post_formal=1, pre_levels=["INFO"], post_levels=["INFO"],
             matched_formal=[[0, 0, 1.0]]),
    ]
    write_mining(tmp_path, repo, rows)
    summary = build(tmp_path, [repo])
    assert summary["per_repo"][repo]["row_problems"] == {}
    add = {i["post_ordinal"]: i for i in load(tmp_path, "add_log_post")}
    assert add[0]["label"] == 1 and add[0]["mask_post_idx"] == [0, 1]
    assert add[2]["label"] == 1 and add[2]["mask_post_idx"] == [0]
    assert 1 not in add
    rem = {(i["pre_ordinal"], i["anchor_pre_idx"]): i["label"] for i in load(tmp_path, "remove_log")}
    assert rem == {(2, 0): 1, (3, 0): 0}

    bad = mrow(repo, c, 0, n_pre_formal=1, n_post_formal=1, pre_levels=["INFO"], post_levels=["INFO"],
               matched_formal=[[0, 0, 1.0]], relocated_pre=[0])
    write_mining(tmp_path, repo, [bad])
    assert build(tmp_path, [repo])["per_repo"][repo]["row_problems"] == {"relocated_also_matched": 1}
