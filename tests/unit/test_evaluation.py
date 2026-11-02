"""Tests for stage-8 evaluation: metrics, bootstrap statistics, table builders and figures.

Everything runs on a synthetic data tree in the pipeline's file formats (make_tree).
"""

import json
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from sklearn import metrics as skm

from src.common.config import ROOT
from src.evaluation import analysis as an
from src.evaluation import figures as fg
from src.evaluation import reporting as rp
from src.evaluation import stats as st
from src.evaluation.metrics import binary_metrics, average_precision, batch_ranking, multiclass_metrics, pr_curve

REPOS = ["OpenKeeper", "Mindustry", "shattered-pixel-dungeon", "OpenRTS", "SkyHussars"]
TASKS = ["add_log", "remove_log", "change_level"]
ALL_MODELS = ["naive_prior", "naive_size", "naive_rule", "lr", "rf", "hgb", "mlp_full", "mlp_hist",
              "gnn_rgcn", "gnn_ggnn", "hybrid_ggnn", "hybrid_ggnn_nohist"]
STRENGTH = {"naive_prior": 0.0, "naive_size": 0.4, "naive_rule": 0.6, "lr": 1.0, "rf": 1.2, "hgb": 1.3,
            "mlp_full": 1.3, "mlp_hist": 0.8, "gnn_rgcn": 1.1, "gnn_ggnn": 1.2, "hybrid_ggnn": 1.5,
            "hybrid_ggnn_nohist": 1.4, "lr_log1p": 1.1, "mlp_full_log1p": 1.35, "hybrid_ggnn_log1p": 1.6}
POSTHOC = ["lr_log1p", "mlp_full_log1p", "hybrid_ggnn_log1p"]
CATS = ["frame_update", "loop", "subsystem", "general"]


def _hex(rng, n=40):
    return "".join(rng.choice(list("0123456789abcdef"), n))


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def make_tree(root, n_pos=(40, 25, 12, 30, 6), models=ALL_MODELS, seeds=(0, 1), tasks=TASKS,
              settings=("R4",), seed=0):
    """Synthetic data/ tree: instances, folds, features, graphs, mining, events, predictions.

    add_log_post (sensitivity task) copies the add_log instances and context under its own
    prefix, as the dataset stage does; it must come after add_log in `tasks`."""
    rng = np.random.default_rng(seed)
    data = root
    folds = {}
    saved = {}
    for task in tasks:
        insts = []
        for r_i, repo in enumerate(REPOS if task != "add_log_post" else []):
            npos = n_pos[r_i % len(n_pos)]
            nneg = 10 * npos
            n = npos + nneg
            commits = [_hex(rng) for _ in range(max(3, n // 5))]
            labels = np.r_[np.ones(npos, int), np.zeros(nneg, int)]
            neg_rank = np.r_[-np.ones(npos, int), rng.permutation(nneg)]
            for i in range(n):
                c = commits[rng.integers(len(commits))]
                iid = f"{task}:{repo}:{c[:12]}:{i}" + ("" if task == "add_log" else ":0")
                row = {"instance_id": iid, "task": task, "repo": repo, "engine": "x", "size": "y", "commit_id": c,
                       "parent_commit_id": _hex(rng), "topo_index": int(i), "timestamp": "2020-01-01T00:00:00",
                       "author_id": _hex(rng, 12), "pre_path": f"src/{repo}/A{i % 7}.java",
                       "post_path": f"src/{repo}/A{i % 7}.java", "pre_blob": _hex(rng), "post_blob": _hex(rng),
                       "class_path": f"A{i % 7}", "method_name": f"m{i}", "signature_pre": f"m{i}()",
                       "signature_post": f"m{i}()", "kind": "method", "pre_ordinal": 0, "post_ordinal": 0,
                       "label": int(labels[i]), "sample_role": "positive" if labels[i] else "negative",
                       "neg_rank": int(neg_rank[i]), "in_R1": bool(labels[i] or neg_rank[i] < npos),
                       "in_R4": bool(labels[i] or neg_rank[i] < 4 * npos), "in_R10": True,
                       "neg_provenance": "modified_method"}
                if task == "add_log":
                    row.update({"view": "post_masked", "mask_post_idx": [0] if labels[i] else []})
                else:
                    row.update({"view": "pre", "anchor_pre_idx": 0, "anchor_level": "DEBUG", "match_ratio": 0.9,
                                "post_level": "INFO" if task == "change_level" else None})
                insts.append(row)
        if task == "add_log_post":
            insts = [dict(r, instance_id=r["instance_id"].replace("add_log:", "add_log_post:", 1), task=task)
                     for r in saved["add_log"][0]]
        _write_jsonl(data / "processed" / "instances" / f"{task}.jsonl", insts)
        pos_by_repo = {}
        for r in insts:
            pos_by_repo[r["repo"]] = pos_by_repo.get(r["repo"], 0) + r["label"]
        folds[task] = {"test_repos": sorted(k for k, v in pos_by_repo.items() if v >= 10),
                       "low_support": sorted(k for k, v in pos_by_repo.items() if 10 <= v < 30),
                       "excluded": {k: v for k, v in pos_by_repo.items() if v < 10}}

        # features (context columns) and failures
        feats = []
        for i, r in enumerate(insts):
            if task == "add_log_post":
                feats.append(dict(saved["add_log"][1][i], instance_id=r["instance_id"]))
                continue
            perf = int(rng.random() < 0.45)
            cat = CATS[rng.integers(3)] if perf else "general"
            feats.append({"instance_id": r["instance_id"], "h_prior": rng.random(), "d_is_perf_sensitive": perf,
                          "d_ctx_category": cat, "d_loop": int(cat == "loop"), "d_frame": int(cat == "frame_update"),
                          "d_input": int(cat == "subsystem" and i % 2 == 0),
                          "d_network": int(cat == "subsystem" and i % 2 == 1), "d_physics": int(perf and i % 7 == 0),
                          "f_fw_jul": int(r["repo"] == "OpenKeeper"), "f_fw_arc": int(r["repo"] == "Mindustry")})
        saved[task] = (insts, feats)
        fdir = data / "processed" / "features"
        fdir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(feats).to_csv(fdir / f"{task}.csv", index=False)
        _write_jsonl(fdir / f"{task}_failures.jsonl", [{"instance_id": f"{task}:OpenRTS:{'0' * 12}:999", "reason": "unit_not_found"}])

        gdir = data / "processed" / "graphs"
        gdir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"graph_pos": range(len(insts)), "instance_id": [r["instance_id"] for r in insts],
                      "n_nodes": rng.integers(5, 400, len(insts)), "n_edges": rng.integers(5, 1500, len(insts)),
                      "truncated": rng.random(len(insts)) < 0.01}).to_csv(gdir / f"{task}_index.csv", index=False)
        with open(gdir / f"{task}_meta.json", "w") as f:
            json.dump({"node_types": ["method", "block"], "edge_types": ["ast"], "n_graphs": len(insts),
                       "n_failures": 1, "failure_reasons": {"view": 1},
                       "stats": {"all": {"n_graphs": len(insts), "nodes": {"mean": 10}, "truncated": 3, "failures": 1},
                                 "per_repo": {}}}, f)
        _write_jsonl(gdir / f"{task}_failures.jsonl", [{"instance_id": f"{task}:OpenRTS:{'1' * 12}:998",
                                                        "repo": "OpenRTS", "reason": "view: unit not found"}])

        # predictions
        perf_of = {f_["instance_id"]: f_["d_is_perf_sensitive"] for f_ in feats}
        for setting in settings:
            sel = [r for r in insts if r[f"in_{setting}"]]
            test = [r for r in sel if r["repo"] in folds[task]["test_repos"]]
            y = np.array([r["label"] for r in test])
            perf = np.array([perf_of[r["instance_id"]] for r in test])
            for m in models:
                for s in seeds:
                    srng = np.random.default_rng(1000 * s + sum(map(ord, m)))
                    k = STRENGTH[m] + (0.8 * perf if m == "hybrid_ggnn" else 0)
                    z = k * (2 * y - 1) + srng.normal(0, 1, len(y))
                    score = 1 / (1 + np.exp(-z))
                    pdir = data / "results" / "predictions" / setting / task / m
                    pdir.mkdir(parents=True, exist_ok=True)
                    pd.DataFrame({"instance_id": [r["instance_id"] for r in test],
                                  "test_repo": [r["repo"] for r in test], "y_true": y, "score": score,
                                  "y_pred": (score > 0.5).astype(int), "threshold": 0.5}).to_csv(pdir / f"seed{s}.csv", index=False)
                    # post-hoc runs list their log1p columns per fold (src/models/train.py)
                    extra = {}
                    if m in POSTHOC:
                        cols = [f"x_{k}" for k in range(4)] + ["h_commit_index", "h_prior", "m_loc"]
                        extra = {"tabular_transform": "signed_log1p_nonbinary", "n_log1p_columns": len(cols),
                                 "log1p_columns_by_group": {"x": 4, "h": 2, "m": 1}, "log1p_columns": cols}
                    with open(pdir / f"seed{s}.json", "w") as f:
                        json.dump({"complete": True, "n_eval": len(test), "n_selected": len(sel),
                                   "dropped": {"no_features": 1, "no_graph": 0},
                                   "folds": [{"test_repo": r_, "fold_seconds": 2.0, "threshold": 0.5,
                                              "val": {"pr_auc": 0.7}, **extra} for r_ in folds[task]["test_repos"]]}, f)
        # scripts/run_experiments.py --importance layout
        imp_dir = data / "results" / "importance" / "R4" / task
        imp_dir.mkdir(parents=True, exist_ok=True)
        rows = [{"fold": rp_, "group": g, "mean_drop": rng.random() * 0.1, "std": 0.01}
                for rp_ in folds[task]["test_repos"] for g in ["h", "f", "m", "l", "d", "x"]]
        pd.DataFrame(rows).to_csv(imp_dir / "hgb_seed0_groups.csv", index=False)
        rows = [{"fold": rp_, "feature": f"m_feat{k}", "mean_drop": rng.random() * 0.05, "std": 0.01}
                for rp_ in folds[task]["test_repos"] for k in range(20)]
        pd.DataFrame(rows).to_csv(imp_dir / "hgb_seed0_features.csv", index=False)

    with open(data / "processed" / "instances" / "folds.json", "w") as f:
        json.dump(folds, f)

    # multiclass supplement
    mdir = data / "results" / "predictions" / "R4" / "multiclass" / "hgb_multiclass"
    mdir.mkdir(parents=True, exist_ok=True)
    for s in seeds:
        yt = rng.choice(an.MULTICLASS, 400, p=[0.7, 0.15, 0.1, 0.05])
        sc = rng.dirichlet(np.ones(4), 400)
        df = pd.DataFrame({"instance_id": [f"multiclass:R:{i}" for i in range(400)], "test_repo": "OpenKeeper",
                           "y_true": yt, "y_pred": np.array(an.MULTICLASS)[sc.argmax(1)]})
        for j, c in enumerate(an.MULTICLASS):
            df[f"score_{c}"] = sc[:, j]
        df.to_csv(mdir / f"seed{s}.csv", index=False)

    # mining outputs and events master
    events = []
    levels = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
    for repo in REPOS:
        mdir = data / "interim" / "mining" / repo
        commits = [{"repo": repo, "commit_id": _hex(rng), "is_merge": bool(i % 9 == 0), "is_bulk": i == 1,
                    "timestamp": f"{2015 + i % 5}-03-01T10:00:00+02:00"} for i in range(120)]
        _write_jsonl(mdir / "commits.jsonl", commits)
        _write_jsonl(mdir / "parse_failures.jsonl", [{"commit_id": "x", "path": "a.java", "side": "pre", "reason": "srcml"}])
        with open(mdir / "summary.json", "w") as f:
            json.dump({"files_parsed": 1000, "elapsed": 12.5, "labels": {"ADD_LOG": 3},
                       "parse_failures_by_reason": {"srcml": 1}}, f)
        for i in range(60):
            lab = ["ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"][i % 3]
            events.append({"event_id": f"{repo}:{i}", "repo": repo, "event_label": lab,
                           "timestamp": f"{2015 + i % 4}-06-01T12:00:00+00:00", "is_bulk": i % 5 == 2,
                           "validity_status": ["core", "core", "bulk", "relocated", "out_of_scope"][i % 5],
                           "scope": ["modified_method", "new_method", "new_file"][i % 3],
                           "logging_style": "formal", "framework": "jul" if repo == "OpenKeeper" else "arc",
                           "pre_level": levels[i % 5] if lab != "ADD_LOG" else None,
                           "post_level": levels[(i + 1) % 5] if lab != "REMOVE_LOG" else None})
    _write_jsonl(data / "processed" / "events_master.jsonl", events)
    # scripts/screen_corpus.py layout (with ALL/MODELING total rows and a top-30 caller table)
    rq1 = data / "results" / "rq1"
    rq1.mkdir(parents=True, exist_ok=True)
    lev = []
    for r in REPOS + ["ALL", "MODELING"]:
        row = {"repo": r, **{lv: int(rng.integers(0, 50)) for lv in levels}, "unknown": int(rng.integers(0, 5))}
        row["n_formal"] = sum(v for k, v in row.items() if k != "repo")
        lev.append(row)
    pd.DataFrame(lev).to_csv(rq1 / "level_distribution.csv", index=False)
    pd.DataFrame([{"repo": r, "modeling": True, "n_java_files": 100, "n_parse_failures": 0,
                   "n_files_misparsed": 2 if r == "Mindustry" else 0, "n_units_no_class": 7 if r == "Mindustry" else 0,
                   "n_formal": 10, "dominant_framework": "jul" if r == "OpenKeeper" else "arc"}
                  for r in REPOS + ["ALL"]]).to_csv(rq1 / "corpus_snapshot.csv", index=False)
    pd.DataFrame([{"repo": "Mindustry", "path": f"core/A{k}.java", "blob": "b" * 40, "top_level_tags": "function",
                   "n_units": 5, "n_units_no_class": 3 + k, "n_accepted_lost": 2, "n_formal_lost": 1,
                   "n_text_only_lost": 0, "n_rejected_loglike_lost": 0} for k in range(2)]).to_csv(
        rq1 / "structural_misparse.csv", index=False)
    vdir = data / "results" / "validation"
    vdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"event_id": f"OpenKeeper:{'a' * 12}:{k}", "repo": "OpenKeeper",
                   "commit_url": f"https://example.org/commit/{'%040d' % (k // 2)}", "event_label": lab,
                   "label_correct": ""} for k, lab in enumerate(["ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"] * 4)]).to_csv(
        vdir / "event_sample.csv", index=False)
    with open(data / "results" / "run_manifest.json", "w") as f:
        json.dump({"generated": "2026-10-03T10:00:00", "python": "3.10.6 (main)", "platform": "Windows-10",
                   "packages": {"numpy": "2.2.6", "torch": "2.6.0"}, "srcml": "srcml: 1.1.0\nlibsrcml: 1.1.0",
                   "git": "git version 2.45", "cuda": {"available": True, "device_name": "GPU X"},
                   "seeds": {"training": [0, 1]}, "corpus": [{"name": "A"}], "source_sha256": {"a.py": "x"}}, f)
    pd.DataFrame([{"repo": r, "rank": 1, "call_name": "x.y", "logging_style": "formal", "framework": "slf4j",
                   "verbosity": "INFO", "count": 3} for r in REPOS]).to_csv(rq1 / "caller_audit.csv", index=False)
    return data


@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    make_tree(root, settings=("R1", "R4", "R10"))
    return root


@pytest.fixture(scope="module")
def tds(tree):
    p = an.paths(tree)
    eco, _ = an.repo_ecosystems(p, an.load_events(p), TASKS)
    return {task: an.load_task("R4", task, p, B=60, ecosystems=eco) for task in TASKS}


# metrics

def test_binary_metrics_equal_sklearn():
    rng = np.random.default_rng(1)
    for _ in range(100):
        n = int(rng.integers(10, 400))
        y = rng.integers(0, 2, n)
        if y.min() == y.max():
            continue
        s = np.round(rng.random(n), int(rng.integers(1, 3))) + 0.3 * y * rng.random()
        yp = (s > np.quantile(s, rng.random())).astype(int)
        m = binary_metrics(y, s, yp)
        assert m["pr_auc"] == pytest.approx(skm.average_precision_score(y, s), abs=1e-12)
        assert m["roc_auc"] == pytest.approx(skm.roc_auc_score(y, s), abs=1e-12)
        assert m["f1"] == pytest.approx(skm.f1_score(y, yp, zero_division=0), abs=1e-12)
        assert m["precision"] == pytest.approx(skm.precision_score(y, yp, zero_division=0), abs=1e-12)
        assert m["recall"] == pytest.approx(skm.recall_score(y, yp), abs=1e-12)
        assert m["mcc"] == pytest.approx(skm.matthews_corrcoef(y, yp), abs=1e-12)
        assert m["balanced_accuracy"] == pytest.approx(skm.balanced_accuracy_score(y, yp), abs=1e-12)
        assert m["accuracy"] == pytest.approx(skm.accuracy_score(y, yp), abs=1e-12)
        assert m["n"] == n and m["n_pos"] == y.sum()


def test_metrics_nan_safe_when_a_class_is_absent():
    m = binary_metrics([0, 0, 0], [0.1, 0.5, 0.9], [0, 1, 1])
    assert np.isnan(m["pr_auc"]) and np.isnan(m["roc_auc"]) and np.isnan(m["recall"]) and np.isnan(m["f1"])
    assert m["precision"] == 0.0 and m["accuracy"] == pytest.approx(1 / 3)
    m = binary_metrics([1, 1], [0.2, 0.3], [0, 0])
    assert m["pr_auc"] == 1.0 and np.isnan(m["roc_auc"]) and m["precision"] == 0.0 and m["f1"] == 0.0
    m = binary_metrics([], [], [])
    assert m["n"] == 0 and np.isnan(m["pr_auc"])


def test_numpy_ap_equals_sklearn_with_ties_and_weights():
    rng = np.random.default_rng(2)
    for _ in range(50):
        n = int(rng.integers(20, 600))
        y = (rng.random(n) < 0.3).astype(int)
        if y.sum() == 0:
            continue
        s = rng.integers(0, 6, n) / 5.0
        assert average_precision(y, s) == pytest.approx(skm.average_precision_score(y, s), abs=1e-12)
        W = rng.poisson(1.0, (5, n)).astype(np.float32)
        ap, auc = batch_ranking(W, y, s)
        for b in range(5):
            if (W[b] * y).sum() == 0 or (W[b] * (1 - y)).sum() == 0:
                continue
            assert ap[b] == pytest.approx(skm.average_precision_score(y, s, sample_weight=W[b]), abs=1e-9)
            assert auc[b] == pytest.approx(skm.roc_auc_score(y, s, sample_weight=W[b]), abs=1e-9)


def test_cluster_bootstrap_ap_and_f1_equal_weighted_sklearn():
    rng = np.random.default_rng(3)
    n, K = 300, 40
    cl = rng.integers(0, K, n)
    y = (rng.random(n) < 0.25).astype(int)
    s = np.round(rng.random(n), 1)
    yp = (s > 0.5).astype(int)
    CT = st.resample_counts(rng.integers(0, 3, K), 30, seed=5)
    ap = st.boot_average_precision(CT, cl, st.prepare_ranking(y, s))
    f1 = st.boot_f1(CT, cl, y, yp)
    for b in range(30):
        w = CT[cl, b]
        assert ap[b] == pytest.approx(skm.average_precision_score(y, s, sample_weight=w), abs=1e-9)
        assert f1[b] == pytest.approx(skm.f1_score(y, yp, sample_weight=w, zero_division=0), abs=1e-9)


def test_resample_keeps_clusters_per_stratum():
    strata = np.array([0, 0, 0, 1, 1, 2])
    CT = st.resample_counts(strata, 200, seed=42)
    assert CT[:3].sum(axis=0).tolist() == [3] * 200
    assert CT[3:5].sum(axis=0).tolist() == [2] * 200
    assert CT[5].tolist() == [1] * 200
    assert np.array_equal(CT, st.resample_counts(strata, 200, seed=42))


def test_multiclass_metrics_equal_sklearn():
    rng = np.random.default_rng(4)
    classes = ["NO_EVENT", "ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]
    yt = rng.choice(classes, 300)
    sc = rng.dirichlet(np.ones(4), 300)
    yp = np.array(classes)[sc.argmax(1)]
    m = multiclass_metrics(yt, yp, {c: sc[:, j] for j, c in enumerate(classes)}, classes)
    assert m["macro_f1"] == pytest.approx(skm.f1_score(yt, yp, average="macro", labels=classes))
    aps = [skm.average_precision_score(yt == c, sc[:, j]) for j, c in enumerate(classes)]
    assert m["macro_pr_auc"] == pytest.approx(np.mean(aps))


def test_pr_curve_matches_sklearn():
    rng = np.random.default_rng(5)
    y = rng.integers(0, 2, 200)
    s = np.round(rng.random(200), 2)
    prec, rec = pr_curve(y, s)
    p_ref, r_ref, _ = skm.precision_recall_curve(y, s)
    assert np.allclose(prec[1:], p_ref[::-1][1:]) and np.allclose(rec[1:], r_ref[::-1][1:])


def _area(x, v):
    """Area under a drawn polyline (exact for the horizontal/vertical segments of a step curve)."""
    return float(np.sum(np.diff(x) * (v[1:] + v[:-1]) / 2))


def test_pr_figure_area_equals_average_precision(tmp_path, monkeypatch):
    # the drawn curve, not only the pr_curve arrays: a 'post' step would draw the first
    # interval at precision 1 and inflate tied/binary scores (0.77 drawn vs AP 0.32)
    from src.evaluation.labels import model_name
    rng = np.random.default_rng(8)
    n = 1000
    y = (rng.random(n) < 0.2).astype(int)
    rule = np.where(y == 1, rng.random(n) < 0.6, rng.random(n) < 0.22).astype(float)
    coarse = np.round(np.clip(0.3 * y + rng.random(n), 0, 1), 1)
    fine = 0.5 * y + rng.random(n)
    scores = {"naive_rule": rule, "lr": coarse, "hgb": fine}
    drawn = []

    def keep(fig, *args, **kwargs):
        drawn.append(fig)
        return []

    monkeypatch.setattr(fg, "save", keep)
    fg.fig_pr_curves({m: pr_curve(y, s) for m, s in scores.items()}, y.mean(), "add_log", tmp_path)
    lines = {line.get_label(): line for line in drawn[0].axes[0].lines}
    for m, s in scores.items():
        line = lines[model_name(m, "en")]
        assert line.get_drawstyle() == "default"
        x, v = line.get_xydata().T
        assert np.all(np.diff(x) >= 0)
        assert _area(x, v) == pytest.approx(skm.average_precision_score(y, s), abs=1e-12)
    for _ in range(20):
        m = int(rng.integers(5, 300))
        yy = rng.integers(0, 2, m)
        if yy.sum() == 0:
            continue
        ss = rng.integers(0, 4, m).astype(float)
        assert _area(*fg.pr_step(*pr_curve(yy, ss))) == pytest.approx(average_precision(yy, ss), abs=1e-12)
    import matplotlib.pyplot as plt
    plt.close(drawn[0])


# statistics

def test_bootstrap_ci_contains_point_estimate(tds):
    td = tds["add_log"]
    an.ensure(td, {"all": an.all_mask(td)})
    for m in td.models:
        row = an.summary_row(td, m, "all")
        for metric in ("pr_auc", "f1"):
            assert row[f"{metric}_ci_lo"] <= row[f"{metric}_mean"] <= row[f"{metric}_ci_hi"]


def test_identical_models_give_zero_delta_and_p_one():
    rng = np.random.default_rng(6)
    boot = rng.random((500, 3))
    pt = rng.random(3)
    res = st.paired_test(boot, boot.copy(), pt, pt.copy())
    assert res["delta"] == 0.0 and res["ci_lo"] == 0.0 and res["ci_hi"] == 0.0 and res["p"] == 1.0
    w = st.wilcoxon_paired([0.3, 0.5, 0.7], [0.3, 0.5, 0.7])
    assert w["p"] == 1.0 and w["n"] == 3


def test_identical_models_on_task_data(tds):
    td = tds["remove_log"]
    td.models["hgb_copy"] = dict(td.models["hgb"])
    try:
        res = an.paired(td, "hgb_copy", "hgb", "all", an.all_mask(td), "pr_auc")
        assert res["delta"] == 0.0 and res["p"] == 1.0
    finally:
        del td.models["hgb_copy"]


def test_bootstrap_p_detects_clear_difference():
    d = np.full(999, 0.05)
    assert st.bootstrap_p(d) == pytest.approx(2 / 1000)
    assert st.bootstrap_p(-d) == pytest.approx(2 / 1000)


def test_holm_known_example():
    adj = st.holm([0.01, 0.04, 0.03, 0.005])
    assert np.allclose(adj, [0.03, 0.06, 0.06, 0.02])
    adj = st.holm([0.2, np.nan, 0.01])
    assert np.isnan(adj[1]) and np.allclose(adj[[0, 2]], [0.2, 0.02])
    assert np.allclose(st.holm([0.5, 0.9]), [1.0, 1.0])


def test_cliffs_delta_known_values():
    assert st.cliffs_delta([1, 2, 3], [1, 2, 3]) == 0.0
    assert st.cliffs_delta([4, 5, 6], [1, 2, 3]) == 1.0
    assert st.cliffs_delta([1, 2, 3], [4, 5, 6]) == -1.0
    # 9 pairs: x>y in 5, x<y in 3, one tie -> 2/9
    assert st.cliffs_delta([2, 3, 5], [1, 3, 4]) == pytest.approx(2 / 9)
    assert st.cliffs_delta([1, 3, 5], [2, 3, 4]) == 0.0
    assert st.cliffs_magnitude(0.1) == "negligible" and st.cliffs_magnitude(-0.5) == "large"


def test_did_sign_on_constructed_case():
    rng = np.random.default_rng(7)
    n = 4000
    y = (rng.random(n) < 0.2).astype(int)
    sub = rng.random(n) < 0.5
    cl = np.arange(n) // 4
    CT = st.resample_counts(np.zeros(cl.max() + 1, int), 200, seed=42)
    noise = rng.normal(0, 1, n)
    good = 1 / (1 + np.exp(-(2.5 * (2 * y - 1) + noise)))
    plain = 1 / (1 + np.exp(-(1.0 * (2 * y - 1) + noise)))
    a = np.where(sub, good, plain)        # model A better than B only on the subset
    b = plain
    boots, points = {}, {}
    for name, score, mask in (("a_sub", a, sub), ("b_sub", b, sub), ("a_comp", a, ~sub), ("b_comp", b, ~sub)):
        idx = np.flatnonzero(mask)
        boots[name] = st.boot_seed_metrics(CT, cl[idx], y[idx], score[None, idx], (score[None, idx] > 0.5))["pr_auc"]
        points[name] = np.array([binary_metrics(y[idx], score[idx], score[idx] > 0.5)["pr_auc"]])
    res = st.did_test(boots, points)
    assert res["delta"] > 0.1 and res["ci_lo"] > 0 and res["p"] < 0.05
    flipped = st.did_test({"a_sub": boots["b_sub"], "b_sub": boots["a_sub"], "a_comp": boots["a_comp"],
                           "b_comp": boots["b_comp"]},
                          {"a_sub": points["b_sub"], "b_sub": points["a_sub"], "a_comp": points["a_comp"],
                           "b_comp": points["b_comp"]})
    assert flipped["delta"] < 0


# tables

METRIC_COLS = [f"{m}_{s}" for m in ("pr_auc", "f1", "precision", "recall", "roc_auc", "mcc", "balanced_accuracy")
               for s in ("mean", "sd")] + ["pr_auc_ci_lo", "pr_auc_ci_hi", "f1_ci_lo", "f1_ci_hi", "n", "n_pos",
                                            "low_support"]


def test_task_data_alignment(tds):
    td = tds["add_log"]
    assert set(td.models) == set(ALL_MODELS)
    assert td.CT.shape[1] == 60
    assert set(td.test_repos) == {"OpenKeeper", "Mindustry", "shattered-pixel-dungeon", "OpenRTS"}
    assert td.meta["engine"].isin(["jME", "libGDX"]).all()
    assert set(td.meta["perf_part"].unique()) == {"subset", "complement"}
    assert td.meta.loc[td.meta["repo"] == "OpenKeeper", "ecosystem"].iloc[0] == "jul"
    assert (td.y == td.meta["label"].astype(int)).all()


def test_overall_and_group_tables(tree, tds):
    pooled = an.table_overall_pooled(tds)
    assert set(METRIC_COLS) <= set(pooled.columns)
    assert len(pooled) == 3 * len(ALL_MODELS)
    hy = pooled[(pooled.task == "add_log") & (pooled.model == "hybrid_ggnn")].iloc[0]
    pr = pooled[(pooled.task == "add_log") & (pooled.model == "naive_prior")].iloc[0]
    assert hy["pr_auc_mean"] > pr["pr_auc_mean"]
    macro = an.table_overall_macro(tds)
    assert {"n_test_repos", "pr_auc_mean", "pr_auc_ci_lo", "n_low_support_repos"} <= set(macro.columns)
    per_repo = an.table_per_repo(tds, an.load_folds(an.paths(tree)))
    assert set(METRIC_COLS) | {"test_repo", "engine", "size", "ecosystem"} <= set(per_repo.columns)
    low = per_repo[per_repo.test_repo == "shattered-pixel-dungeon"]["low_support"]
    assert low.all()
    for col, label in (("engine", "engine"), ("size", "size"), ("ecosystem", "ecosystem"), ("d_ctx_category", "ctx")):
        df = an.table_by(tds, col, label)
        assert set(METRIC_COLS) | {label, "n_repos"} <= set(df.columns)
        n_all = pooled.set_index(["task", "model"])["n"]
        n_groups = df.groupby(["task", "model"])["n"].sum()
        assert (n_groups == n_all.reindex(n_groups.index)).all()


def test_rq4_tables(tree, tds):
    sub = an.table_subset(tds)
    assert set(sub["part"]) == {"subset", "complement"}
    gap = an.table_subset_gap(tds)
    assert {"pr_auc_delta", "pr_auc_ci_lo", "pr_auc_p", "f1_delta", "n_subset"} <= set(gap.columns)
    did = an.table_did(tds)
    assert len(did) == 3
    assert {"pr_auc_subset_delta", "pr_auc_complement_delta", "pr_auc_did_delta", "pr_auc_did_ci_lo",
            "pr_auc_did_p", "pr_auc_did_p_holm", "f1_did_delta"} <= set(did.columns)
    # synthetic hybrid is built stronger on the subset only
    assert (did["pr_auc_did_delta"] > 0).all()
    # per-task reference ('best classical' sensitivity); hgb rows equal the primary table
    alt = an.table_did(tds, b={"add_log": "rf", "remove_log": "hgb"})
    assert alt.set_index("task")["model_b"].to_dict() == {"add_log": "rf", "remove_log": "hgb"}
    same = did.set_index("task").loc["remove_log", "pr_auc_did_delta"]
    assert alt.set_index("task").loc["remove_log", "pr_auc_did_delta"] == same
    # all synthetic sidecars have the same validation PR-AUC: a tie keeps the a priori reference
    best, val = an.best_classical_by_validation(an.paths(tree), "R4", TASKS)
    assert best == {task: "hgb" for task in TASKS}
    assert np.allclose(val["val_pr_auc_mean"], 0.7) and val.loc[val["selected"], "model"].eq("hgb").all()


def test_macro_ci_equals_per_repository_reference(tds):
    td = tds["add_log"]
    m = "hgb"
    md = td.models[m]
    macro = an.table_overall_macro({"add_log": td}).set_index("model").loc[m]
    repo_idx = [np.flatnonzero((td.meta["test_repo"] == r).to_numpy() & md["cover"]) for r in td.test_repos]
    ref = []
    for b in range(td.CT.shape[1]):
        per_seed = []
        for j in range(len(md["seeds"])):
            vals = []
            for idx in repo_idx:
                w = td.CT[td.rows[idx], b].astype(float)
                vals.append(skm.average_precision_score(td.y[idx], md["score"][j, idx], sample_weight=w)
                            if (w * td.y[idx]).sum() > 0 else np.nan)
            # a resample in which a repository has no positive does not define the macro
            per_seed.append(np.mean(vals))
        ref.append(np.mean(per_seed))
    ref = np.array(ref)
    lo, hi = np.quantile(ref[np.isfinite(ref)], [0.025, 0.975])
    assert macro["pr_auc_ci_lo"] == pytest.approx(lo, abs=1e-12)
    assert macro["pr_auc_ci_hi"] == pytest.approx(hi, abs=1e-12)
    assert macro["n_test_repos"] == len(td.test_repos) and macro["b_used"] == np.isfinite(ref).sum()


def test_ablation_and_pairwise(tds):
    ab = an.table_ablation(tds)
    assert set(ab["variant"]) == {"full", "no_history", "no_graph", "history_only", "graph_only"}
    assert set(ab["scope"]) == {"full_test", "subset"}
    assert {"pr_auc_vs_full_delta", "pr_auc_vs_full_p", "pr_auc_vs_full_p_holm", "f1_vs_full_ci_hi"} <= set(ab.columns)
    assert ab.loc[ab.variant == "full", "pr_auc_vs_full_delta"].isna().all()
    pw = an.table_pairwise(tds)
    assert len(pw) == 3 * len(an.PAIRS)
    assert {"pr_auc_delta", "pr_auc_ci_lo", "pr_auc_p", "pr_auc_p_holm", "pr_auc_wilcoxon_n", "pr_auc_wilcoxon_p",
            "pr_auc_cliffs_delta", "f1_delta", "f1_p_holm"} <= set(pw.columns)
    assert (pw["pr_auc_wilcoxon_n"] == 4).all()


def test_sensitivity_multiclass_importance(tree, tds):
    p = an.paths(tree)
    sens = an.table_sensitivity(p, ["add_log"], 40, {"add_log": tds["add_log"]})
    assert set(sens["setting"]) == {"R1", "R4", "R10"}
    assert set(sens["model"]) == set(an.SENSITIVITY_MODELS)
    prev = sens.groupby("setting")["prevalence"].first()
    assert prev["R1"] > prev["R4"] > prev["R10"]
    mc, per_class = an.table_multiclass(p, "R4")
    assert {"macro_f1_mean", "macro_pr_auc_mean", "accuracy_mean"} <= set(mc.columns)
    assert set(per_class["class"]) == set(an.MULTICLASS)
    imp = an.table_importance(p, "R4")
    assert {"task", "model", "group", "importance_mean", "importance_sd", "n_folds", "rank"} <= set(imp.columns)
    assert (imp["model"] == "hgb").all() and (imp["n_folds"] == 4).all() and len(imp) == 3 * 6
    feats = an.table_importance(p, "R4", "feature", top=15)
    assert "feature" in feats and feats.groupby("task").size().max() <= 15
    tr = an.table_training(p, "R4", TASKS)
    assert {"n_seeds", "all_complete", "n_eval", "dropped_no_features", "seconds_per_seed"} <= set(tr.columns)
    assert tr["all_complete"].all() and (tr["n_seeds"] == 2).all()


def test_importance_unchanged_after_its_tables_are_written(tree):
    # scripts/evaluate.py writes tables/rq2_importance*.csv; a second run must not read them back
    p = an.paths(tree)
    groups = an.table_importance(p, "R4")
    feats = an.table_importance(p, "R4", "feature", top=15)
    rp.write_table(groups, "rq2_importance", p["results"] / "tables", "caption")
    rp.write_table(feats, "rq2_importance_features", p["results"] / "tables", "caption")
    pd.testing.assert_frame_equal(an.table_importance(p, "R4"), groups)
    pd.testing.assert_frame_equal(an.table_importance(p, "R4", "feature", top=15), feats)
    assert (groups["n_folds"] == 4).all()
    assert all("tables" not in f.parts for f in an._importance_files(p) + an._importance_files(p, "feature"))


def _small_tree(root, models):
    return make_tree(root, n_pos=(12, 10, 15), models=models, seeds=(0, 1), tasks=["add_log"])


def test_partial_model_missing_a_fold(tmp_path):
    root = _small_tree(tmp_path, ["lr", "hgb", "gnn_ggnn", "hybrid_ggnn"])
    pdir = root / "results" / "predictions" / "R4" / "add_log"
    for s in (0, 1):
        f = pdir / "gnn_ggnn" / f"seed{s}.csv"
        df = pd.read_csv(f)
        df[df.test_repo != "OpenRTS"].to_csv(f, index=False)
        f = pdir / "hybrid_ggnn" / f"seed{s}.csv"    # 2 instances without a graph: still complete
        pd.read_csv(f).iloc[2:].to_csv(f, index=False)
    an.NOTICES.clear()
    td = an.load_task("R4", "add_log", an.paths(root), B=40)
    gnn, hy = td.models["gnn_ggnn"], td.models["hybrid_ggnn"]
    assert gnn["partial"] and not hy["partial"] and not td.models["hgb"]["partial"]
    n_all = len(pd.read_csv(pdir / "lr" / "seed0.csv"))
    # evaluated instances: intersection of the complete models (lr, hgb, hybrid)
    assert td.n_union == n_all and len(td.ids) == n_all - 2 and hy["cover"].all()
    in_fold = (td.meta["test_repo"] == "OpenRTS").to_numpy()
    assert not gnn["cover"][in_fold].any() and gnn["cover"][~in_fold].all()
    assert any("gnn_ggnn" in m and "partial" in m for m in an.NOTICES)
    # paired comparisons use the instances both models predicted
    res = an.paired(td, "gnn_ggnn", "hgb", "all", an.all_mask(td), "pr_auc")
    assert res["n"] == int(gnn["cover"].sum()) < len(td.ids)
    # macro over the repositories the partial model was evaluated on
    macro = an.table_overall_macro({"add_log": td}).set_index("model")
    assert macro.loc["gnn_ggnn", "n_test_repos"] == len(td.test_repos) - 1 == 4
    assert macro.loc["hgb", "n_test_repos"] == 5 and macro.loc["gnn_ggnn", "n_low_support_repos"] == 4
    per_repo = an.table_per_repo({"add_log": td})
    g = per_repo[(per_repo.model == "gnn_ggnn") & (per_repo.n > 0)]
    assert len(g) == 4 and macro.loc["gnn_ggnn", "pr_auc_mean"] == pytest.approx(g["pr_auc_mean"].mean())
    # the formatted tables and the report pivots mark it
    pooled = an.table_overall_pooled({"add_log": td})
    assert pooled.set_index("model")["n_test_repos"].to_dict() == {"lr": 5, "hgb": 5, "gnn_ggnn": 4, "hybrid_ggnn": 5}
    disp = rp.metric_display(pooled, ["task", "model"])
    assert disp["partial"].tolist() == ["yes" if m == "gnn_ggnn" else "" for m in pooled["model"]]
    piv = rp.pivot_metric(pooled, "pr_auc").set_index("model")["add_log"]
    assert piv["gnn_ggnn"].endswith("†") and not piv["hgb"].endswith("†")
    note = rp.partial_note(pooled)
    assert f"add_log/gnn_ggnn n={int(gnn['cover'].sum())}" in note and "hgb" not in note
    # grouped pivots keep the partial model on the row of the complete models (its n in the footnote)
    by_engine = rp.keyed(an.table_by({"add_log": td}, "engine", "engine"), "engine")
    piv = rp.pivot_metric(by_engine, "pr_auc", row="key", col="model")
    assert len(piv) == by_engine["engine"].nunique() and piv["gnn_ggnn"].str.endswith("†").all()
    hgb_n = by_engine[by_engine.model == "hgb"].set_index("engine")["n"]
    assert set(piv["key"]) == {f"add_log / {e} (n={n})" for e, n in hgb_n.items()}


def test_stale_evaluation_set_is_flagged(tmp_path):
    root = _small_tree(tmp_path, ["lr", "rf", "hgb"])
    p = an.paths(root)
    pdir = root / "results" / "predictions" / "R4" / "add_log"
    for m in ("lr", "rf", "hgb"):
        for s in (0, 1):
            f = pdir / m / f"seed{s}.json"
            side = json.loads(f.read_text())
            side["eval_set_sha1"] = ("b" if m == "rf" else "a") * 40
            side["code_sha1"] = "c" * 40
            side["run_key"] = f"{m}{s}" if m == "lr" else m      # lr seeds: two configurations
            if m == "rf":
                side["folds"] = [dict(fo, val={"pr_auc": 0.9}) for fo in side["folds"]]
            f.write_text(json.dumps(side))
    an.NOTICES.clear()
    td = an.load_task("R4", "add_log", p, B=20)
    assert td.models["rf"]["stale"] and td.models["rf"]["partial"]
    assert not td.models["hgb"]["partial"] and not td.models["lr"]["stale"]
    assert any("rf" in msg and "eval_set_sha1" in msg for msg in an.NOTICES)
    assert [msg for msg in an.NOTICES if "run_key" in msg] == ["R4/add_log/lr: seeds were trained with 2 different "
                                                                "configurations (run_key)"]
    cov = an.table_coverage({"R4": {"add_log": td}}).set_index("model")
    assert cov.loc["rf", "eval_set_mismatch"] and not cov.loc["hgb", "eval_set_mismatch"]
    assert cov.loc["hgb", "eval_set_sha1"] == "a" * 40
    tr = an.table_training(p, "R4", ["add_log"]).set_index("model")
    assert tr.loc["rf", "eval_set_sha1"] == "b" * 40 and tr.loc["lr", "code_sha1"] == "c" * 40
    # the 'best classical' reference is chosen on validation PR-AUC only
    best, val = an.best_classical_by_validation(p, "R4", ["add_log"])
    assert best == {"add_log": "rf"} and val.loc[val["selected"], "model"].tolist() == ["rf"]
    # three models on three sets: no majority, so none of them can be trusted to be current
    for s in (0, 1):
        f = pdir / "hgb" / f"seed{s}.json"
        f.write_text(json.dumps(dict(json.loads(f.read_text()), eval_set_sha1="d" * 40)))
    an.NOTICES.clear()
    td = an.load_task("R4", "add_log", p, B=5)
    assert all(md["stale"] and md["partial"] for md in td.models.values())
    assert any("no majority evaluation set" in msg for msg in an.NOTICES)


def test_dataset_quality_and_rq1(tree, tds):
    p = an.paths(tree)
    folds = an.load_folds(p)
    inst = an.table_instances(p, folds, TASKS)
    assert {"n_pos", "n_neg_pool", "n_neg_R1", "n_neg_R4", "n_neg_R10", "fold_role", "low_support"} <= set(inst.columns)
    r = inst[(inst.task == "add_log") & (inst.repo == "OpenKeeper")].iloc[0]
    assert r["n_neg_R4"] == 4 * r["n_pos"] and r["n_neg_R1"] == r["n_pos"]
    fail = an.table_failures(p, TASKS)
    assert fail["n_view_failures"].sum() == 3 and {"n_with_graph", "n_graph_truncated"} <= set(fail.columns)
    assert fail["n_graph_failures"].sum() == 3
    gs = an.table_graph_stats(p, TASKS)
    assert len(gs) == 3 and (gs["build_n_failures"] == 1).all() and (gs["build_truncated"] == 3).all()
    pf = an.table_parse_failures(p)
    assert {"n_commits", "n_non_merge", "parse_failures_pre", "summary_files_parsed"} <= set(pf.columns)
    assert len(an.table_coverage({"R4": tds})) == 3 * len(ALL_MODELS)
    ev = an.load_events(p)
    assert an.table_events(ev)["n"].sum() == len(ev)
    assert "core" in an.pivot_events(ev, "validity_status").columns
    rates = an.table_event_rates(ev, an.commit_counts(p))
    assert {"core_ADD_LOG", "core_total_per_1k", "all_per_1k"} <= set(rates.columns)
    tr = an.table_transitions(ev)
    assert list(tr["pre_level"]) == ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
    enr = an.table_enrichment(p, TASKS)
    assert {"category", "share_pos", "share_neg", "enrichment"} <= set(enr.columns)
    lv = an.snapshot_levels(p)
    assert list(lv.columns) == ["repo", "n_formal", "TRACE", "DEBUG", "INFO", "WARN", "ERROR", "unknown"]
    assert set(lv["repo"]) == set(REPOS)
    assert (lv["n_formal"] == lv[["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "unknown"]].sum(axis=1)).all()
    eco, source = an.repo_ecosystems(p, ev, TASKS)
    assert source == "rq1 snapshot" and eco["OpenKeeper"] == "jul" and "ALL" not in eco


def test_error_analysis_and_examples(tds, tmp_path):
    td = tds["change_level"]
    res = an.error_analysis(td, tmp_path, view_loader=lambda inst: None, n_examples=3)
    assert {"tp", "fp", "fn", "tn", "fp_rate", "fn_rate", "grouping"} <= set(res["confusion"].columns)
    assert set(res["confusion"]["grouping"]) == {"d_ctx_category", "perf_part"}
    only = pd.read_csv(tmp_path / "change_level_only_hybrid_ggnn_correct.csv")
    assert {"repo", "commit_id", "pre_path", "class_path", "method_name", "label", "score_hybrid_ggnn",
            "score_hgb", "d_ctx_category", "anchor_level"} <= set(only.columns)
    assert len(only) == res["summary"]["only_hybrid_ggnn_correct"]
    text = (tmp_path / "change_level_examples.md").read_text(encoding="utf-8")
    assert "Only hybrid_ggnn correct" in text and "view could not be rebuilt" in text


def test_method_source_marks_anchor():
    from src.parsing.method_units import parse_java_source
    from src.dataset.views import InstanceView
    java = ("import org.slf4j.Logger;\nclass A {\n  Logger log;\n  @Override\n  void run(int x) {\n"
            "    log.info(\"start\");\n    for (int i = 0; i < x; i++) {\n      log.debug(\"step {}\", i);\n"
            "    }\n  }\n}\n")
    parsed = parse_java_source(java)
    unit = parsed.units[0]
    view = InstanceView({}, unit, parsed, unit.formal_logs[1], 0)
    src = an.method_source(view)
    marked = [line for line in src.splitlines() if "<<< anchor" in line]
    assert len(marked) == 1 and 'log.debug("step {}", i);' in marked[0]
    short = an.method_source(view, max_lines=4).splitlines()
    assert len(short) <= 4 and any("<<< anchor" in line for line in short)


# reporting and figures

def test_reporting_writers(tmp_path, tds):
    pooled = an.table_overall_pooled(tds)
    disp = rp.metric_display(pooled, ["task", "model"])
    assert "PR-AUC 95% CI" in disp.columns and "±" in disp["PR-AUC"].iloc[0]
    rp.write_table(pooled, "x", tmp_path, "Caption with n.", disp)
    assert (tmp_path / "x.csv").exists() and (tmp_path / "x.md").exists()
    tex = (tmp_path / "x.tex").read_text(encoding="utf-8")
    assert "\\toprule" in tex and "\\bottomrule" in tex and "$\\pm$" in tex and "hybrid\\_ggnn" in tex
    assert rp.tex_escape("a_b & 50%") == "a\\_b \\& 50\\%"
    assert rp.fmt_p(0.0001) == "<0.001" and rp.fmt_mean_sd(0.5, np.nan) == "0.500"


def test_figures_run_headless(tmp_path, tree, tds):
    import matplotlib
    assert matplotlib.get_backend().lower() == "agg"
    pooled = an.table_overall_pooled(tds)
    per_repo = an.table_per_repo(tds)
    ab = an.table_ablation(tds)
    did = an.table_did(tds)
    p = an.paths(tree)
    ev = an.load_events(p)
    # English here; the end-to-end test draws every figure in French
    lang = "en"
    files = fg.fig_pr_curves(an.pr_curve_data(tds["add_log"]), 0.2, "add_log", tmp_path, lang)
    files += fg.fig_prauc_bars(pooled, tmp_path, lang)
    files += fg.fig_repo_heatmap(per_repo, "remove_log", tmp_path, lang)
    files += fg.fig_ablation(ab, tmp_path, lang)
    files += fg.fig_forest(did, tmp_path, lang)
    files += fg.fig_levels(an.snapshot_levels(p), tmp_path, lang)
    files += fg.fig_core_events(an.table_event_rates(ev, an.commit_counts(p)), tmp_path, lang)
    files += fg.fig_transitions(an.table_transitions(ev), tmp_path, lang)
    assert len(files) == 16 and all(f.exists() and f.stat().st_size > 0 for f in files)
    assert fg.fig_prauc_bars(pooled, tmp_path, lang, sfx="_R1")[0].name == "prauc_bars_R1_en.png"


def test_french_labels():
    from src.evaluation.labels import t, model_name, context_name
    assert t("precision", "fr") == "Précision" and t("recall", "fr") == "Rappel"
    assert t("subset", "fr") == "Sous-ensemble sensible aux performances"
    assert t("repo", "fr") == "Référentiel" and t("engine", "fr") == "Moteur" and t("size", "fr") == "Taille"
    assert context_name("frame_update", "fr") == "Mise à jour de trame"
    assert model_name("lr", "fr") == "Régression logistique"


def _evaluate(root, *extra, monkeypatch=None):
    """scripts.evaluate as a subprocess (the real CLI), or in this process when monkeypatch is given."""
    args = ["--data-dir", str(root), "--bootstrap", "10", "--bootstrap-tests", "20", "--tasks", "add_log,remove_log",
            "--lang", "fr", "--examples", "2", *extra]
    if monkeypatch is None:
        res = subprocess.run([sys.executable, "-m", "scripts.evaluate", *args], cwd=ROOT, capture_output=True,
                             text=True)
        assert res.returncode == 0, res.stdout[-3000:] + res.stderr[-3000:]
        return
    import scripts.evaluate as ev
    monkeypatch.setattr(sys, "argv", ["evaluate", *args])
    an.NOTICES.clear()
    ev.FAILED.clear()
    ev.main()
    assert not ev.FAILED


def _snapshot(results):
    """Bytes of every deterministic output (PDFs carry a creation date, the report a timestamp)."""
    return {f.relative_to(results).as_posix(): f.read_bytes() for f in results.rglob("*")
            if f.is_file() and f.suffix in (".csv", ".md", ".tex", ".png") and f.parent.name != "report"}


def test_evaluate_script_end_to_end(tmp_path, monkeypatch):
    root = make_tree(tmp_path, n_pos=(20, 12, 4), models=["naive_rule", "lr", "hgb", "gnn_ggnn", "hybrid_ggnn"],
                     seeds=(0,), tasks=["add_log", "remove_log"], settings=("R4", "R1"))
    results = root / "results"
    _evaluate(root)
    report = (results / "report" / "experiment_report.md").read_text(encoding="utf-8")
    for section in ("Summary by research question", "Dataset quality", "RQ1", "RQ2", "RQ3", "RQ4", "Ablations",
                    "Statistical tests", "Sensitivity analysis", "Post-hoc analysis", "Limitations of evidence"):
        assert section in report
    assert "the annotation of `validation/event_sample.csv` is pending" in report
    assert "No predictions for add_log_post" in report and "No predictions for the post-hoc models" in report
    assert "no predictions for" in report and "fixed a priori" in report
    # synthetic sidecars tie on validation PR-AUC, so the 'best classical' check is hgb itself
    assert "The validation choice is hgb for every task" in report
    tables = results / "tables"
    for name in ("rq3_overall_pooled", "rq3_per_repo", "rq4_did", "rq4_did_reference_validation", "pairwise", "ablation",
                 "dq_instances", "dq_coverage", "rq1_event_rates", "rq1_levels", "rq2_importance", "dq_folds",
                 "dq_imbalance", "config_hyperparameters", "env_manifest", "dq_head_misparse", "rq1_events_per_year",
                 "rq4_did_frame_update", "rq4_subsystem_markers"):
        assert (tables / f"{name}.csv").exists() and (tables / f"{name}.tex").exists(), name
    # French variants of the main tables (--lang fr): decimal comma, French headers
    for name in ("rq3_overall_pooled", "rq3_per_repo", "rq4_did", "pairwise", "ablation", "rq4_subset"):
        fr = (tables / f"{name}_fr.md").read_text(encoding="utf-8")
        assert "Réglage R4" in fr and "IC 95 %" in fr and "n = " in fr.splitlines()[0], name
    assert re.search(r"\d,\d{3}", (tables / "rq3_overall_pooled_fr.md").read_text(encoding="utf-8"))
    assert (results / "figures" / "rq4_ctx_category_fr.png").exists()
    assert (results / "figures" / "rq1_events_per_year_fr.png").exists()
    assert (results / "error_analysis" / "error_rate_gap.csv").exists()
    # every table states its n
    for f in tables.glob("*.md"):
        cap = f.read_text(encoding="utf-8").splitlines()[0]
        assert re.search(r"\bn(_\w+)? =|n_folds per row|n per task", cap), (f.name, cap)
    assert "n = " in (tables / "rq1_levels.md").read_text(encoding="utf-8").splitlines()[0]
    assert (results / "figures" / "prauc_bars_fr.png").exists()
    assert (results / "error_analysis" / "add_log_examples.md").exists()
    first = _snapshot(results)

    # a non-primary setting writes suffixed files and leaves every R4 output untouched
    _evaluate(root, "--setting", "R1", monkeypatch=monkeypatch)
    after = _snapshot(results)
    assert {k: v for k, v in after.items() if k in first} == first
    new = set(after) - set(first)
    for name in ("figures/prauc_bars_R1_fr.png", "figures/pr_curves_add_log_R1_fr.png", "tables/dq_coverage_R1.csv",
                 "tables/rq3_overall_pooled_R1.csv", "tables/sensitivity_ratio_R1.csv",
                 "error_analysis/add_log_examples_R1.md", "error_analysis/add_log_only_hybrid_ggnn_correct_R1.csv"):
        assert name in new, name
    assert all("R1" in k for k in new), sorted(k for k in new if "R1" not in k)
    assert (results / "report" / "experiment_report_R1.md").exists()

    # a second primary run reproduces the first byte for byte (importance not read back, seeded bootstrap)
    _evaluate(root, monkeypatch=monkeypatch)
    assert {k: v for k, v in _snapshot(results).items() if k in first} == first


def test_manifest_contents(tmp_path, monkeypatch):
    import scripts.write_manifest as wm
    f = tmp_path / "a.txt"
    f.write_bytes(b"abc")
    assert wm.sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    # importing torch is the slow part; srcML, git and the hashes run for real
    monkeypatch.setattr(wm, "cuda_info", lambda: {"available": False, "stub": True})
    m = wm.build_manifest(tmp_path)
    assert {"python", "packages", "srcml", "cuda", "corpus", "source_sha256", "generated"} <= set(m)
    assert "src/evaluation/stats.py" in m["source_sha256"] and "configs/experiment.yaml" in m["source_sha256"]
    assert {"torch", "torch_geometric", "scikit-learn", "numpy", "scipy", "pandas", "lxml", "GitPython"} <= set(m["packages"])
    assert len(m["corpus"]) == 16 and all("pinned_head" in r for r in m["corpus"])
    assert m["packages"]["torch"] is not None and m["srcml"]


def test_lock_file_names_the_pytorch_index():
    from scripts.write_manifest import index_lines
    frozen = "numpy==2.1.3\ntorch==2.6.0+cu124\ntorchvision==0.21.0+cu124\ntorch-geometric==2.8.0.post1\n"
    assert index_lines(frozen) == ["--extra-index-url https://download.pytorch.org/whl/cu124"]
    assert index_lines("numpy==2.1.3\ntorch==2.6.0\n") == []
    lock = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
    assert set(index_lines(lock)) <= set(lock.splitlines())


# further statistics and report cases

def test_boot_roc_auc_prevalence_and_p_mcse():
    rng = np.random.default_rng(11)
    n, K = 400, 50
    cl = rng.integers(0, K, n)
    y = (rng.random(n) < 0.3).astype(int)
    s = np.round(rng.random(n) + 0.2 * y, 1)
    CT = st.resample_counts(rng.integers(0, 3, K), 40, seed=3)
    auc = st.boot_roc_auc(CT, cl, y, s, chunk=7)
    prev = st.boot_prevalence(CT, cl, y)
    for b in range(40):
        w = CT[cl, b]
        assert auc[b] == pytest.approx(skm.roc_auc_score(y, s, sample_weight=w), abs=1e-9)
        assert prev[b] == pytest.approx(np.average(y, weights=w), abs=1e-12)
    assert np.isnan(st.boot_roc_auc(CT, cl, np.zeros(n, int), s)).all()
    # Monte-Carlo SE of a bootstrap p: 2 sqrt(q (1-q) / B) for the smaller tail share q
    d = np.r_[np.full(900, 0.1), np.full(100, -0.1)]
    q = 101 / 1001
    assert st.bootstrap_p_mcse(d) == pytest.approx(2 * np.sqrt(q * (1 - q) / 1000))
    floor = st.bootstrap_p_mcse(np.full(999, 0.1))
    assert floor == pytest.approx(2 * np.sqrt((1 / 1000) * (999 / 1000) / 999)) and floor > 0
    assert st.delta_test(0.1, d)["p_mcse"] == pytest.approx(st.bootstrap_p_mcse(d))
    lo, hi = st.wilson_ci(8, 10)
    assert (lo, hi) == (pytest.approx(0.4902, abs=1e-4), pytest.approx(0.9433, abs=1e-4))
    assert np.isnan(st.wilson_ci(0, 0)[0])


def test_multiclass_secondary_metrics_and_majority_row(tree):
    rng = np.random.default_rng(12)
    classes = ["NO_EVENT", "ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]
    yt = rng.choice(classes, 500, p=[0.6, 0.2, 0.15, 0.05])
    yp = rng.choice(classes, 500)
    m = multiclass_metrics(yt, yp, None, classes)
    assert m["balanced_accuracy"] == pytest.approx(skm.balanced_accuracy_score(yt, yp))
    assert m["mcc"] == pytest.approx(skm.matthews_corrcoef(yt, yp))
    assert m["macro_precision"] == pytest.approx(skm.precision_score(yt, yp, average="macro", labels=classes,
                                                                     zero_division=0))
    assert m["macro_recall"] == pytest.approx(skm.recall_score(yt, yp, average="macro", labels=classes))
    mc, _ = an.table_multiclass(an.paths(tree), "R4")
    assert {"balanced_accuracy_mean", "mcc_mean", "macro_precision_mean", "macro_recall_mean"} <= set(mc.columns)
    maj = mc.set_index("model").loc["majority_class"]
    assert maj["predicts"] == "NO_EVENT" and maj["mcc_mean"] == 0.0
    assert maj["balanced_accuracy_mean"] == pytest.approx(0.25)
    assert list(mc["model"])[-1] == "majority_class"


def test_group_tables_report_prevalence_lift_roc_and_precision_ci(tds):
    pooled = an.table_overall_pooled(tds)
    for metric in ("precision", "recall", "pr_auc_lift"):
        assert {f"{metric}_ci_lo", f"{metric}_ci_hi"} <= set(pooled.columns)
    assert (pooled["precision_ci_lo"] <= pooled["precision_ci_hi"]).all()
    r = pooled.iloc[0]
    td = tds[r["task"]]
    pt = td.point[(r["model"], "all")]
    assert r["pr_auc_lift_mean"] == pytest.approx((pt["pr_auc"] / pt["prevalence"]).mean())
    macro = an.table_overall_macro(tds)
    assert {"precision_ci_lo", "recall_ci_hi"} <= set(macro.columns)
    for col, label in (("engine", "engine"), ("d_ctx_category", "ctx_category"), ("perf_part", "part")):
        df = an.table_by(tds, col, label)
        assert {"n_pos", "prevalence", "pr_auc_lift_mean", "pr_auc_lift_ci_lo", "roc_auc_mean", "share_of_test"} <= set(df)
        prior = df[df["model"] == "naive_prior"]
        assert len(prior) == len(df[df["model"] == "hgb"])
        assert prior.groupby("task")["share_of_test"].sum().round(9).eq(1).all()
    disp = rp.group_display(an.table_by(tds, "engine", "engine"), "engine")
    assert {"n_pos", "prevalence", "naive_prior PR-AUC", "hgb PR-AUC [CI] ×lift", "hgb ROC-AUC"} <= set(disp.columns)
    assert disp["hgb PR-AUC [CI] ×lift"].str.contains("×").all()
    md = rp.metric_display(pooled, ["task", "model"])
    assert {"prevalence", "Precision 95% CI", "Recall 95% CI", "lift", "lift 95% CI"} <= set(md.columns)


def test_markers_frame_part_and_subset_gap_lift_roc(tds):
    mk = an.table_markers(tds)
    assert set(mk["marker"]) <= {"input", "network", "physics", "collision", "animation", "resource"}
    assert {"input", "network"} <= set(mk["marker"]) and set(mk["model"]) == set(an.GROUP_MODELS)
    td = tds["add_log"]
    sel = (td.meta["d_input"] > 0).to_numpy()
    row = mk[(mk.task == "add_log") & (mk.marker == "input") & (mk.model == "hgb")].iloc[0]
    assert row["n"] == sel.sum() and row["n_pos"] == td.y[sel].sum()
    assert set(td.meta["frame_part"].dropna()) == {"subset", "complement"}
    assert ((td.meta["frame_part"] == "subset") == (td.meta["d_ctx_category"] == "frame_update")).all()
    gap = an.table_subset_gap(tds)
    for metric in ("pr_auc", "pr_auc_lift", "roc_auc", "f1"):
        assert {f"{metric}_delta", f"{metric}_ci_lo", f"{metric}_p", f"{metric}_p_mcse"} <= set(gap.columns)
    sub = an.table_subset(tds).set_index(["task", "part", "model"])
    g = gap.set_index(["task", "model"]).loc[("remove_log", "hgb")]
    assert g["roc_auc_delta"] == pytest.approx(sub.loc[("remove_log", "subset", "hgb"), "roc_auc_mean"]
                                               - sub.loc[("remove_log", "complement", "hgb"), "roc_auc_mean"])
    assert g["pr_auc_lift_delta"] == pytest.approx(sub.loc[("remove_log", "subset", "hgb"), "pr_auc_lift_mean"]
                                                   - sub.loc[("remove_log", "complement", "hgb"), "pr_auc_lift_mean"])
    assert g["prevalence_subset"] == pytest.approx(sub.loc[("remove_log", "subset", "hgb"), "prevalence"])


def test_tests_use_their_own_resamples_and_flag_low_support(tree):
    p = an.paths(tree)
    td = an.load_task("R4", "change_level", p, B=30, B_test=70)
    assert td.CT.shape[1] == 30 and td.CT_test.shape[1] == 70 and td.CT.shape[0] == td.CT_test.shape[0]
    did = an.table_did({"change_level": td})
    r = did.iloc[0]
    assert td.boot_test[("hybrid_ggnn", "perf_part=subset")]["pr_auc"].shape == (70, 2)
    assert {"pr_auc_did_p_mcse", "f1_did_p_mcse", "low_support_subset", "low_support_complement",
            "f1_exploratory"} <= set(did.columns)
    assert r["low_support_subset"] == (r["n_pos_subset"] < 30)
    assert r["low_support_complement"] == (r["n_pos_complement"] < 30)
    assert r["f1_exploratory"] == (r["low_support_subset"] or r["low_support_complement"])
    assert r["pr_auc_did_p"] >= 2 / 71
    # summaries keep the CI resamples
    an.ensure(td, {"all": an.all_mask(td)})
    assert td.boot[("hgb", "all")]["precision"].shape == (30, 2)
    fu = an.table_did({"change_level": td}, part="frame_part")
    assert fu["split"].iloc[0] == "frame_part"
    assert fu["n_subset"].iloc[0] == int(((td.meta["d_ctx_category"] == "frame_update").to_numpy()).sum())
    ab = an.table_ablation({"change_level": td})
    assert "pr_auc_vs_full_p_mcse" in ab


def test_macro_paired_bootstrap(tds):
    td = tds["remove_log"]
    pw = an.table_pairwise({"remove_log": td}, [("hybrid_ggnn", "hgb"), ("gnn_ggnn", "hgb")])
    macro = an.table_overall_macro({"remove_log": td}).set_index("model")["pr_auc_mean"]
    row = pw.set_index("model_a").loc["hybrid_ggnn"]
    assert row["macro_pr_auc_delta"] == pytest.approx(macro["hybrid_ggnn"] - macro["hgb"])
    assert row["macro_pr_auc_ci_lo"] <= row["macro_pr_auc_delta"] <= row["macro_pr_auc_ci_hi"]
    assert {"macro_pr_auc_p", "macro_pr_auc_p_holm", "macro_pr_auc_p_mcse", "pr_auc_p_mcse"} <= set(pw.columns)
    td.models["hgb_copy"] = dict(td.models["hgb"])
    try:
        res = an.macro_paired(td, "hgb_copy", "hgb")
        assert res["delta"] == 0.0 and res["p"] == 1.0 and res["n_repos"] == len(td.test_repos)
    finally:
        del td.models["hgb_copy"]


def test_agreement_error_rate_gap_and_stratified_examples(tds, tmp_path):
    td = tds["remove_log"]
    ag = an.agreement(td)
    for m in ("hybrid_ggnn", "hgb"):
        assert ag[f"only_{m}_correct_pos"] + ag[f"only_{m}_correct_neg"] == ag[f"only_{m}_correct"]
        yp = an.majority(td.models[m]["pred"])
        assert ag[f"{m}_vote_f1"] == pytest.approx(skm.f1_score(td.y, yp))
        assert ag[f"{m}_vote_precision"] == pytest.approx(skm.precision_score(td.y, yp))
    assert ag["topk_k"] == td.y.sum() and 0 <= ag["topk_overlap"] <= ag["topk_k"]
    assert ag["topk_pos_both"] + ag["topk_pos_only_hgb"] == ag["topk_pos_hgb"]
    same = an.agreement(td, "hgb", "hgb")
    assert same["topk_overlap_share"] == 1.0 and same["only_hgb_correct"] == 0
    gap = an.error_rate_gap(td, ["hgb", "naive_rule"])
    conf = an.confusion_by(td, ["hgb"], ["perf_part"]).set_index("group")
    g = gap.set_index("model").loc["hgb"]
    assert g["fp_rate_delta"] == pytest.approx(conf.loc["subset", "fp_rate"] - conf.loc["complement", "fp_rate"])
    assert g["fn_rate_ci_lo"] <= g["fn_rate_delta"] <= g["fn_rate_ci_hi"]
    res = an.error_analysis(td, tmp_path, view_loader=lambda inst: None, n_examples=4)
    assert set(res["confusion"]["model"]) == set(an.ERROR_MODELS)
    assert {"only_hybrid_ggnn_correct_pos", "topk_overlap", "hgb_vote_recall"} <= set(res["summary"])
    only = pd.read_csv(tmp_path / "remove_log_only_hybrid_ggnn_correct.csv")
    assert (only["wrong_error"] == np.where(only["label"] == 1, "FN", "FP")).all()
    rng = np.random.default_rng(0)
    pick = an.stratified_pick(only, ["perf_part", "wrong_error"], 4, rng)
    strata = only.groupby(["perf_part", "wrong_error"]).ngroups
    assert len(pick) == min(4, len(only))
    assert only.loc[pick].groupby(["perf_part", "wrong_error"]).ngroups == min(4, strata)
    text = (tmp_path / "remove_log_examples.md").read_text(encoding="utf-8")
    assert "Strata:" in text and "wrong model's error" in text


def test_fold_commit_support_and_macro_without_few_commit_folds(tree, tds, tmp_path):
    p = an.paths(tree)
    folds = an.load_folds(p)
    sup, source = an.fold_commit_support(p, folds, "add_log")
    inst = [r for r in an.load_instances(p, "add_log") if r["label"] == 1 and r["repo"] == "OpenKeeper"]
    commits = pd.Series([r["commit_id"] for r in inst]).value_counts()
    n_pos, npc, share, few = sup["OpenKeeper"]
    assert (n_pos, npc) == (len(inst), len(commits)) and share == pytest.approx(commits.iloc[0] / len(inst))
    assert source.startswith("computed") and few == (npc <= an.FEW_COMMITS)
    # values written by the dataset stage (folds.json per_repo, few_commit_folds) take precedence
    folds2 = json.loads(json.dumps(folds))
    folds2["add_log"].update({"per_repo": {"OpenKeeper": {"n_pos": 40, "n_pos_commits": 1, "max_commit_share": 0.96}},
                              "few_commit_folds": ["OpenKeeper"]})
    sup2, source2 = an.fold_commit_support(p, folds2, "add_log")
    assert source2.startswith("folds.json") and sup2["OpenKeeper"][1:] == (1, 0.96, True)
    assert not sup2["Mindustry"][3] and sup2["Mindustry"][1] > 0
    few, _ = an.few_commit_folds(p, folds2, ["add_log"])
    assert few == {"add_log": ["OpenKeeper"]}
    macro = an.table_overall_macro({"add_log": tds["add_log"]}, few).set_index("model")
    assert (macro["folds_excluded"] == "OpenKeeper").all()
    assert macro.loc["hgb", "n_test_repos"] == len(tds["add_log"].test_repos) - 1
    per_repo = an.table_per_repo({"add_log": tds["add_log"]})
    ref = per_repo[(per_repo.model == "hgb") & (per_repo.test_repo != "OpenKeeper")]["pr_auc_mean"].mean()
    assert macro.loc["hgb", "pr_auc_mean"] == pytest.approx(ref)
    ft = an.table_folds(p, folds2, ["add_log"], "R4")
    r = ft.set_index("test_repo").loc["OpenKeeper"]
    assert r["few_commit_fold"] and "OpenKeeper" not in r["training_repos"].split(";")
    assert r["n_training_repos"] == len(REPOS) - 1 and r["n_test_pos"] is None  # synthetic sidecars have no sizes


def test_imbalance_hyperparameter_environment_tables(tree, tmp_path):
    p = an.paths(tree)
    side = p["predictions"] / "R4" / "add_log"
    for m, cfg, extra in (("lr", {"lr": {"C": 1.0, "class_weight": "balanced"}}, {}),
                          ("hgb", {"hgb": {"learning_rate": 0.05}}, {}),
                          ("mlp_full", {"mlp": {"hidden": 8}, "training": {"pos_weight": "balanced"}}, {"pos_weight": 4.0})):
        for s in (0, 1):
            f = side / m / f"seed{s}.json"
            d = json.loads(f.read_text())
            d["config"] = cfg
            d["folds"] = [dict(fo, decision="score >= threshold (F1-max on validation)", **extra) for fo in d["folds"]]
            f.write_text(json.dumps(d))
    imb = an.table_imbalance(p, "R4", ["add_log"]).set_index("model")
    assert imb.loc["lr", "class_weighting"] == "class_weight=balanced"
    assert imb.loc["hgb", "class_weighting"] == "none (unweighted loss)"
    assert imb.loc["mlp_full", "class_weighting"].startswith("pos_weight=balanced")
    assert imb.loc["mlp_full", "pos_weight_mean"] == 4.0
    assert imb.loc["naive_prior", "class_weighting"] == "none (no training)"
    assert imb.loc["lr", "negative_sampling"].startswith("4 negatives per positive")
    assert imb.loc["lr", "threshold_rule"] == "score >= threshold (F1-max on validation)"
    hp = an.table_hyperparameters({"sampling": {"seed": 42}, "models": {"lr": {"C": 1.0}}, "evaluation": {"ci": 0.95}})
    assert set(zip(hp["section"], hp["key"], hp["value"])) == {("sampling", "seed", "42"), ("models", "lr.C", "1.0"),
                                                             ("evaluation", "ci", "0.95")}
    # the posthoc section is not pre-specified
    hp = an.table_hyperparameters({"models": {"lr": {"C": 1.0}}, "posthoc": {"models": {"lr_log1p": "lr"}}})
    assert dict(zip(hp["key"], hp["prespecified"])) == {"lr.C": True, "models.lr_log1p": False}
    assert not an.table_hyperparameters().query("section == 'posthoc'")["prespecified"].any()
    env = an.table_environment(p).set_index("item")["value"]
    assert env["python"] == "3.10.6" and env["srcml"] == "srcml: 1.1.0" and env["cuda device_name"] == "GPU X"
    assert env["package numpy"] == "2.2.6" and env["seeds training"] == "0, 1"
    assert an.table_environment(an.paths(tmp_path)) is None
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "run_manifest.json").write_text(json.dumps(
        {"hardware": {"cpu": "CPU Y", "logical_cores": 22, "ram_gb": 16.0},
         "evaluation": {"bootstrap_samples": 1000, "bootstrap_seed": 42, "ci": 0.95}}))
    env = an.table_environment(an.paths(tmp_path)).set_index("item")["value"]
    assert env["hardware logical_cores"] == "22" and env["evaluation bootstrap_seed"] == "42"
    assert "evaluation ci" not in env
    # B for tests and the resampling seed default when configs/experiment.yaml does not set them
    assert an.bootstrap_sizes({"evaluation": {"bootstrap_samples": 1000}}) == (1000, 10000, 42)
    assert an.bootstrap_sizes({"evaluation": {"bootstrap_samples": 500, "bootstrap_samples_tests": 2000,
                                              "bootstrap_seed": 7}}) == (500, 2000, 7)


def test_head_misparse_and_extraction_precision(tree, tmp_path):
    p = an.paths(tree)
    hm = an.table_head_misparse(p).set_index("repo")
    assert hm.loc["Mindustry", "n_files_misparsed"] == 2 and hm.loc["Mindustry", "n_units_no_class"] == 7
    assert hm.loc["Mindustry", "n_formal_outside_units_misparse"] == 2
    assert hm.loc["Mindustry", "n_statements_outside_units_misparse"] == 4
    assert hm.loc["OpenKeeper", "n_formal_outside_units_misparse"] == 0 and "ALL" not in hm.index
    assert hm.loc["Mindustry", "pct_files_misparsed"] == pytest.approx(2.0)
    # the synthetic sample is not annotated yet
    ep, n_ann, n_rows, problems = an.table_extraction_precision(p)
    assert ep is None and n_ann == 0 and n_rows == 12 and problems == []
    root = tmp_path / "v"
    rows = []
    for k in range(10):
        rows.append(_sample_row(k, "ADD_LOG", ["yes", "1", "Y", "true", "ok", "ok", "1.0", "yes", "no", "0"][k]))
    rows += [_sample_row(20, "REMOVE_LOG", "?"),                     # unclear
             _sample_row(21, "REMOVE_LOG", "y", logging="n"),        # not a logging statement: wrong
             _sample_row(22, "CHANGE_LEVEL", "y", level="n"),        # level wrong: wrong
             _sample_row(23, "CHANGE_LEVEL", "y", level="y"),
             _sample_row(24, "CHANGE_LEVEL", "", logging="", level="")]   # not annotated yet
    _write_sample(root, rows)
    ep, n_ann, n_rows, problems = an.table_extraction_precision(an.paths(root), B=200)
    assert (n_ann, n_rows, problems) == (14, 15, [])
    e = ep.set_index("event_label")
    a = e.loc["ADD_LOG"]
    assert a["n_correct"] == 8 and a["precision"] == 0.8 and a["n_commits"] == 5
    assert a["wilson_ci_lo"] == pytest.approx(0.4902, abs=1e-4) and a["wilson_ci_hi"] == pytest.approx(0.9433, abs=1e-4)
    assert 0.0 <= a["cluster_ci_lo"] <= 0.8 <= a["cluster_ci_hi"] <= 1.0
    # '?' excluded or counted as wrong; correct needs is_logging_statement and (CHANGE_LEVEL) level_correct
    assert (e.loc["REMOVE_LOG", ["n_correct", "n_wrong", "n_unclear"]] == [0, 1, 1]).all()
    assert e.loc["REMOVE_LOG", "precision"] == 0 and e.loc["REMOVE_LOG", "precision_unclear_wrong"] == 0
    assert e.loc["CHANGE_LEVEL", "precision"] == 0.5 and e.loc["CHANGE_LEVEL", "n_annotated"] == 2
    # without core-event counts there is no overall estimate, only the unweighted sample share
    assert set(ep["event_label"]) == {"ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL", "ALL (sample, unweighted)"}
    u = e.loc["ALL (sample, unweighted)"]
    assert u["precision"] == pytest.approx(9 / 13) and u["precision_unclear_wrong"] == pytest.approx(9 / 14)


def _sample_row(k, label, correct, logging="y", level="na"):
    return {"event_id": f"R:{k // 2:012d}:{k}", "repo": "R", "commit_url": f"https://x/commit/{label}{k // 2:036d}",
            "event_label": label, "label_correct": correct, "is_logging_statement": logging,
            "level_correct": level, "notes": ""}


def _write_sample(root, rows):
    vdir = root / "results" / "validation"
    vdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(vdir / "event_sample.csv", index=False)
    return an.paths(root)


def test_extraction_precision_is_weighted_by_core_event_shares(tmp_path):
    # ADD_LOG all correct, CHANGE_LEVEL half correct; equal sample sizes, unequal populations
    rows = [_sample_row(k, "ADD_LOG", "y") for k in range(10)]
    rows += [_sample_row(k, "CHANGE_LEVEL", "y" if k < 5 else "n", level="y") for k in range(10)]
    p = _write_sample(tmp_path, rows)
    ep, n_ann, _, _ = an.table_extraction_precision(p, B=300, core_counts={"ADD_LOG": 900, "CHANGE_LEVEL": 100})
    e = ep.set_index("event_label")
    assert e.loc["ALL", "precision"] == pytest.approx(0.9 * 1.0 + 0.1 * 0.5)
    assert e.loc["ALL (sample, unweighted)", "precision"] == pytest.approx(15 / 20)
    assert e.loc["ADD_LOG", "weight"] == pytest.approx(0.9) and e.loc["ALL", "core_events"] == 1000
    assert np.isnan(e.loc["ALL", "wilson_ci_lo"]) and e.loc["ALL", "b_used"] == 300
    # stratified bootstrap: ADD_LOG is 1 in every resample, so ALL = 0.9 + 0.1 * CHANGE_LEVEL resample
    for c in ("cluster_ci_lo", "cluster_ci_hi"):
        assert e.loc["ALL", c] == pytest.approx(0.9 + 0.1 * e.loc["CHANGE_LEVEL", c])
    # the report headlines the weighted value, never the pooled sample share
    ctx = {"sfx": "", "setting": "R4", "extraction": (n_ann, 20, [])}
    line = rp._extraction_line(ep, ctx)
    assert line.startswith("- Extraction precision (annotation, 20 of 20 sampled events") and "0.950" in line
    assert "0.750" not in line and "weighted by their shares of the core events" in line
    text = "\n".join(rp._section_quality({"dq_extraction_precision": ep}, ctx))
    assert "| ALL (sample, unweighted) |" in text and "not an estimate for the corpus" in text
    # a label with core events but no annotated event: no overall value
    an.NOTICES.clear()
    ep, _, _, _ = an.table_extraction_precision(p, B=50, core_counts={"ADD_LOG": 900, "REMOVE_LOG": 50,
                                                                      "CHANGE_LEVEL": 100})
    assert "ALL" not in set(ep["event_label"]) and any("REMOVE_LOG" in n for n in an.NOTICES)


def test_unrecognised_or_incomplete_annotations_stop_the_precision(tmp_path):
    rows = [_sample_row(k, "ADD_LOG", v) for k, v in enumerate(["yes"] * 6 + ["no - relocation", "x", "wrong label"])]
    p = _write_sample(tmp_path / "a", rows)
    an.NOTICES.clear()
    ep, n_ann, n_rows, problems = an.table_extraction_precision(p)
    assert ep is None and (n_ann, n_rows) == (9, 9)
    assert problems == ["label_correct='no - relocation' (1x)", "label_correct='wrong label' (1x)",
                        "label_correct='x' (1x)"]
    assert any("not computed" in n for n in an.NOTICES)
    rows = [_sample_row(0, "ADD_LOG", "y"), _sample_row(1, "ADD_LOG", "y", logging="")]
    ep, n_ann, _, problems = an.table_extraction_precision(_write_sample(tmp_path / "b", rows))
    assert ep is None and n_ann == 2 and problems[0].startswith("1 started rows with a required cell empty")
    lines = rp._section_quality({}, {"sfx": "", "setting": "R4", "extraction": (2, 2, problems)})
    assert any("not computed" in line and "required cell empty" in line for line in lines)
    assert "not computed" in rp._extraction_line(None, {"extraction": (2, 2, problems)})


def test_rq1_rates_per_year_failures_and_importance_names(tree):
    p = an.paths(tree)
    ev = an.load_events(p)
    rates = an.table_event_rates(ev, an.commit_counts(p)).set_index("repo")
    fnb = ev[(ev["logging_style"] == "formal") & ~ev["is_bulk"]]
    assert rates.loc["OpenKeeper", "n_formal_nonbulk"] == int((fnb["repo"] == "OpenKeeper").sum())
    r = rates.loc["OpenKeeper"]
    assert r["formal_nonbulk_per_1k"] == pytest.approx(r["n_formal_nonbulk"] / r["n_non_merge"] * 1000)
    py_ = an.commits_per_year(p)
    assert sum(v for (repo, _), v in py_.items() if repo == "OpenKeeper") == an.commit_counts(p)["OpenKeeper"][1]
    per_year = an.table_events_per_year(ev, py_)
    core = ev[ev["validity_status"] == "core"]
    allrows = per_year[per_year["repo"] == "ALL"]
    assert allrows["total"].sum() == len(core) and per_year[per_year["repo"] != "ALL"]["total"].sum() == len(core)
    y = allrows.set_index("year").loc[2015]
    assert y["n_non_merge"] == sum(v for (_, yr), v in py_.items() if yr == 2015)
    assert y["total_per_1k"] == pytest.approx(y["total"] / y["n_non_merge"] * 1000)
    assert list(per_year["repo"])[-1] == "ALL"
    fail = an.table_failures(p, ["add_log"])
    assert {"n_graph_not_built_outside_R4", "n_graph_missing_in_R4"} <= set(fail.columns) and "n_graph_missing" not in fail
    # synthetic graphs exist for every instance
    assert fail["n_graph_not_built_outside_R4"].sum() == 0 and fail["n_graph_missing_in_R4"].sum() == 0
    imp = an.table_importance(p, "R4", tasks=TASKS)
    assert set(imp["group_name"]) == {"history", "file", "method", "logging context", "domain", "lexical"}
    feats = an.table_importance(p, "R4", "feature", top=15, tasks=["add_log"])
    assert set(feats["task"]) == {"add_log"} and (feats["group_name"] == "method").all()


def test_french_tables_and_figure_text(tmp_path, tds):
    disp = pd.DataFrame({"task": ["add_log"], "PR-AUC 95% CI": ["[0.495, 0.598]"], "p": ["<0.001"],
                         "low support": ["yes"], "Precision": ["0.500 ± 0.010"]})
    fr = rp.to_french(disp)
    assert list(fr.columns) == ["tâche", "PR-AUC IC 95 %", "p", "faible effectif", "Précision"]
    assert fr.iloc[0].tolist() == ["add_log", "[0,495 ; 0,598]", "<0,001", "oui", "0,500 ± 0,010"]
    # categorical cells get their French display names; model ids stay identifiers
    cat = rp.to_french(pd.DataFrame({"task": ["add_log"] * 3, "part": ["subset", "complement", "subset"],
                                     "ctx_category": ["frame_update", "general", "loop"],
                                     "scope": ["full_test", "subset", "full_test"],
                                     "variant": ["no_history", "full", "graph_only"],
                                     "marker": ["input", "network", "resource"], "model": ["hgb"] * 3}))
    assert cat.iloc[0].tolist() == ["add_log", "Sous-ensemble", "Mise à jour de trame", "Ensemble de test complet",
                                    "Sans historique", "Entrée", "hgb"]
    assert cat.iloc[1, 1:6].tolist() == ["Complément", "Général", "Sous-ensemble sensible aux performances",
                                         "Complet", "Réseau"]
    rp.write_table(pd.DataFrame({"a": [0.5]}), "t", tmp_path, "Caption n = 1.", fr_caption="Légende n = 1.")
    assert (tmp_path / "t_fr.md").read_text(encoding="utf-8").startswith("**Légende n = 1.**")
    assert "0,500" in (tmp_path / "t_fr.tex").read_text(encoding="utf-8")
    from src.evaluation.labels import t, model_name, num, colon, task_name
    assert model_name("hgb", "fr") == "Boosting de gradient (HGB)" and t("low_support", "fr") == "faible effectif"
    assert "agrégés" in t("pr_curves", "fr") and "graine 0" in t("pr_curves", "fr") and "seed 0" in t("pr_curves", "en")
    assert num(0.256, 2, "fr") == "0,26" and num(0.256, 2, "en") == "0.26" and colon("fr") == " : "
    assert "commit" in task_name("add_log_post", "fr") and model_name("lr_log1p", "en").endswith("(post-hoc)")


def test_figures_setting_titles_hollow_markers_and_french_numbers(tmp_path, tds, monkeypatch):
    drawn = []
    monkeypatch.setattr(fg, "save", lambda fig, *a, **k: drawn.append(fig) or [])
    did = an.table_did(tds)
    did.loc[did["task"] == "change_level", "low_support_complement"] = True
    did.loc[did["task"] == "remove_log", "below_floor_subset"] = True
    fg.fig_forest(did, tmp_path, "fr", "f1")
    ax = drawn[-1].axes[0]
    assert "R4" in ax.get_title() and "réglage R4" in ax.get_title()
    markers = [line for line in ax.lines if line.get_marker() == "o"]
    hollow = [line for line in markers if line.get_markerfacecolor() == "white"]
    # change_level: complement and DiD rows hollow; remove_log: subset (below the support floor) and DiD rows
    assert len(markers) == 3 * len(did) and len(hollow) == 4
    assert "faible effectif" in ax.get_xlabel()
    per_repo = an.table_per_repo(tds)
    fg.fig_repo_heatmap(per_repo, "remove_log", tmp_path, "fr")
    ax = drawn[-1].axes[0]
    labels = [lab.get_text() for lab in ax.get_xticklabels()]
    assert all("prév. 0," in lab for lab in labels)
    assert all("." not in txt.get_text() for txt in ax.texts)
    fg.fig_prauc_bars(an.table_overall_pooled(tds), tmp_path, "fr")
    fig = drawn[-1]
    assert "R4" in fig._suptitle.get_text()
    assert any(txt.get_text() == "prévalence\n0,20" for a in fig.axes for txt in a.texts)
    fg.fig_pr_curves(an.pr_curve_data(tds["add_log"]), 0.2, "add_log", tmp_path, "fr", setting="R4")
    title = drawn[-1].axes[0].get_title()
    assert title.startswith("ADD_LOG : ") and "graine 0" in title and "R4" in title
    import matplotlib.pyplot as plt
    for f in drawn:
        plt.close(f)


def test_new_figures_written(tmp_path, tree, tds):
    ctx = an.table_by(tds, "d_ctx_category", "ctx_category")
    files = fg.fig_ctx_category(ctx, tmp_path, "en")
    ev = an.load_events(an.paths(tree))
    files += fg.fig_events_per_year(an.table_events_per_year(ev, an.commits_per_year(an.paths(tree))), tmp_path, "fr")
    assert [f.name for f in files] == ["rq4_ctx_category_en.png", "rq4_ctx_category_en.pdf",
                                       "rq1_events_per_year_fr.png", "rq1_events_per_year_fr.pdf"]
    assert all(f.stat().st_size > 0 for f in files)


@pytest.fixture(scope="module")
def ph_tree(tmp_path_factory):
    root = tmp_path_factory.mktemp("ph")
    models = ["naive_prior", "naive_rule", "lr", "hgb", "mlp_full", "gnn_ggnn", "hybrid_ggnn", "lr_log1p",
              "mlp_full_log1p", "hybrid_ggnn_log1p"]
    return make_tree(root, n_pos=(20, 12, 15), models=models, seeds=(0, 1), tasks=["add_log", "remove_log",
                                                                                   "add_log_post"])


def test_posthoc_models_never_enter_the_primary_analysis(ph_tree):
    p = an.paths(ph_tree)
    pdir = p["predictions"] / "R4" / "add_log"
    for s in (0, 1):
        f = pdir / "lr_log1p" / f"seed{s}.csv"
        pd.read_csv(f).iloc[3:].to_csv(f, index=False)   # 3 instances missing (>= 99% coverage)
    an.NOTICES.clear()
    td = an.load_task("R4", "add_log", p, B=20, B_test=30)
    assert not set(td.models) & set(POSTHOC)
    n_all = len(pd.read_csv(pdir / "lr" / "seed0.csv"))
    assert len(td.ids) == n_all
    ph = an.load_task("R4", "add_log", p, B=20, B_test=30, models=["lr_log1p", "lr", "hybrid_ggnn_log1p",
                                                                   "hybrid_ggnn", "hgb"], ref=td, exclude=())
    assert (ph.ids == td.ids).all() and np.array_equal(ph.CT, td.CT) and np.array_equal(ph.CT_test, td.CT_test)
    assert (ph.y == td.y).all() and not ph.models["lr_log1p"]["cover"].all()
    # the base models have the same values in both TaskData (same instances and resamples)
    a = an.table_overall_pooled({"add_log": td}).set_index("model")
    b = an.table_overall_pooled({"add_log": ph}).set_index("model")
    for c in ("pr_auc_mean", "pr_auc_ci_lo", "f1_ci_hi"):
        assert a.loc["lr", c] == b.loc["lr", c]
    pw = an.table_pairwise({"add_log": ph}, an.POSTHOC_PAIRS)
    assert set(zip(pw["model_a"], pw["model_b"])) == {("lr_log1p", "lr"), ("hybrid_ggnn_log1p", "hybrid_ggnn"),
                                                      ("hybrid_ggnn_log1p", "hgb")}
    assert pw.set_index("model_a").loc["lr_log1p", "n"] == n_all - 3
    tr = an.table_training(p, "R4", ["add_log"])
    assert not set(tr["model"]) & set(POSTHOC) and "n_log1p_columns_mean" not in tr
    ph_tr = an.table_training(p, "R4", ["add_log"], models=POSTHOC, multiclass=False).set_index("model")
    assert set(ph_tr.index) == set(POSTHOC)
    # the double log1p (x_ buckets, h_commit_index) is surfaced from the sidecars
    r = ph_tr.loc["mlp_full_log1p"]
    assert r["n_log1p_columns_mean"] == 7 and r["log1p_columns_by_group"] == "h=2; m=1; x=4"
    assert r["n_log1p_twice_mean"] == 5 and r["tabular_transform"] == "signed_log1p_nonbinary"
    assert not set(an.table_imbalance(p, "R4", ["add_log"])["model"]) & set(POSTHOC)
    ph_all = an.load_task("R4", "add_log", p, B=20, B_test=30, models=POSTHOC + ["lr", "mlp_full", "hybrid_ggnn", "hgb"],
                          ref=td, exclude=())
    pw = an.table_pairwise({"add_log": ph_all}, an.POSTHOC_PAIRS)
    assert set(zip(pw["model_a"], pw["model_b"])) == set(an.POSTHOC_PAIRS)
    assert (pw["pr_auc_b_used"] == 30).all() and (pw["macro_pr_auc_b_used"] <= 30).all()


def test_commit_time_view_is_a_separate_paired_sensitivity(ph_tree):
    p = an.paths(ph_tree)
    pre = an.load_task("R4", "add_log", p, B=20, B_test=40)
    post = an.load_task("R4", "add_log_post", p, B=20, B_test=40)
    assert all(i.startswith("add_log_post:") for i in post.ids)
    assert np.array_equal(pre.clusters, post.clusters) and np.array_equal(pre.CT_test, post.CT_test)
    comp = an.table_view_comparison(pre, post)
    assert comp["paired"].all() and set(comp["model"]) == set(pre.models) & set(post.models)
    r = comp.set_index("model").loc["hgb"]
    pp = an.table_overall_pooled({"add_log": pre}).set_index("model").loc["hgb", "pr_auc_mean"]
    pq = an.table_overall_pooled({"add_log_post": post}).set_index("model").loc["hgb", "pr_auc_mean"]
    assert r["pr_auc_delta"] == pytest.approx(pq - pp) and r["pr_auc_ci_lo"] <= r["pr_auc_delta"] <= r["pr_auc_ci_hi"]
    assert "pr_auc_p_holm" in comp and (comp["pr_auc_b_used"] == 40).all()
    same = an.table_view_comparison(pre, pre)
    assert (same["pr_auc_delta"] == 0).all() and (same["pr_auc_p"] == 1).all()


def test_commit_time_view_uses_the_pre_state_split(ph_tree):
    p = an.paths(ph_tree)
    pre = an.load_task("R4", "add_log", p, B=20, B_test=40)
    post = an.load_task("R4", "add_log_post", p, B=20, B_test=40)
    # the masked view flags some methods differently (as src/features/domain.py can on the masked unit)
    flip = post.meta.index[:6]
    post.meta.loc[flip, "perf_part"] = np.where(post.meta.loc[flip, "perf_part"] == "subset", "complement", "subset")
    post.meta.loc[flip[:2], "d_ctx_category"] = "frame_update_x"
    split = an.align_view_split(post, pre)
    assert split["source"] == "pre-state view (add_log)" and split["n"] == len(pre.ids)
    assert split["n_perf_changed"] == 6 and split["n_perf_changed_pos"] == int((post.y[:6] == 1).sum())
    assert split["n_category_changed"] == 2
    assert (post.meta["perf_part"].to_numpy() == pre.meta["perf_part"].to_numpy()).all()
    assert (post.meta["d_ctx_category"].to_numpy() == pre.meta["d_ctx_category"].to_numpy()).all()
    # the DiD of the commit-time view runs on the add_log split
    did = an.table_did({"add_log_post": post})
    assert did["n_pos_subset"].iloc[0] == int(((pre.meta["perf_part"] == "subset") & (pre.y == 1)).sum())


def test_view_comparison_without_aligned_instances(ph_tree, tmp_path):
    import shutil
    root = tmp_path / "copy"
    shutil.copytree(ph_tree, root)
    pdir = root / "results" / "predictions" / "R4" / "add_log_post"
    dropped = pd.read_csv(pdir / "hgb" / "seed0.csv")["instance_id"].iloc[0]
    for f in pdir.glob("*/seed*.csv"):
        df = pd.read_csv(f)
        df[df["instance_id"] != dropped].to_csv(f, index=False)
    p = an.paths(root)
    pre = an.load_task("R4", "add_log", p, B=20, B_test=40)
    post = an.load_task("R4", "add_log_post", p, B=20, B_test=40)
    an.NOTICES.clear()
    comp = an.table_view_comparison(pre, post)
    assert not comp["paired"].any() and comp["pr_auc_p"].isna().all() and comp["pr_auc_p_holm"].isna().all()
    assert np.isfinite(comp["pr_auc_delta"]).all() and (comp["pr_auc_b_used"] == 0).all()
    assert any("without paired bootstrap" in n for n in an.NOTICES)
    # every add_log_post instance is still in add_log, so the split is still the pre-state one
    assert an.align_view_split(post, pre)["source"].startswith("pre-state")
    # the other way round an instance is missing: the masked split stays, with a notice
    split = an.align_view_split(pre, post)
    assert split["source"] == "masked view" and split["n"] == len(post.ids)
    lines = rp._section_sensitivity({"sens_add_log_post_pooled": an.table_overall_pooled({"add_log_post": post}),
                                     "sens_add_log_post_vs_add_log": comp},
                                    {"sfx": "", "view_split": split})
    text = "\n".join(lines)
    assert "without a paired test" in text and "computed on the masked method" in text
    assert "exactly the instances" not in text


def test_macro_and_did_need_positives_and_support(tmp_path):
    """A repository whose positives all come from one commit: many resamples draw none of them."""
    root = make_tree(tmp_path, n_pos=(12, 10, 15), models=["lr", "hgb", "mlp_full", "mlp_hist", "gnn_ggnn",
                                                         "hybrid_ggnn", "hybrid_ggnn_nohist"],
                     seeds=(0, 1), tasks=["add_log"])
    f = root / "processed" / "instances" / "add_log.jsonl"
    rows = an.read_jsonl(f)
    one = next(r["commit_id"] for r in rows if r["repo"] == "Mindustry" and r["label"] == 1)
    for r in rows:
        if r["repo"] == "Mindustry" and r["label"] == 1:
            r["commit_id"] = one
    _write_jsonl(f, rows)
    td = an.load_task("R4", "add_log", an.paths(root), B=200, B_test=300)
    # macro CIs: only resamples in which every repository has a positive
    macro = an.table_overall_macro({"add_log": td}).set_index("model")
    an.ensure(td, an.repo_masks(td), ["hgb"])
    keys = [f"repo={r}" for r in td.test_repos]
    ok = np.all([td.boot[("hgb", k)]["prev"] > 0 for k in keys], axis=0)
    assert 0 < ok.sum() < 200 and macro.loc["hgb", "b_used"] == ok.sum()
    ref = np.mean([st.seed_mean(td.boot[("hgb", k)]["pr_auc"]) for k in keys], axis=0)[ok]
    lo, hi = np.quantile(ref, [0.025, 0.975])
    assert macro.loc["hgb", "pr_auc_ci_lo"] == pytest.approx(lo) and macro.loc["hgb", "pr_auc_ci_hi"] == pytest.approx(hi)
    # the macro paired test uses the same rule on the test resamples
    res = an.macro_paired(td, "hybrid_ggnn", "hgb")
    ok_t = np.all([an.boot_of(td, "hgb", k, "test")["prev"] > 0 for k in keys], axis=0)
    assert res["b_used"] == ok_t.sum() < 300 and res["n_repos"] == len(keys)
    pw = an.table_pairwise({"add_log": td}, [("hybrid_ggnn", "hgb")], {"add_log": ["Mindustry"]}).iloc[0]
    assert pw["macro_pr_auc_b_used"] == res["b_used"] and pw["macro_no_few_commit_pr_auc_b_used"] == 300
    assert pw["few_commit_folds_excluded"] == "Mindustry" and pw["pr_auc_b_used"] == 300
    # support floor: a part with 3 positives from 1 commit gets no p and stays out of Holm
    assert an.below_floor(9, 5) and an.below_floor(40, 2) and not an.below_floor(10, 3)
    sel = ((td.meta["repo"] == "Mindustry") & (td.y == 1)).to_numpy()
    sel[np.flatnonzero(sel)[3:]] = False
    sel |= ((td.meta["repo"] == "OpenRTS") & (td.y == 0)).to_numpy()
    td.meta["perf_part"] = np.where(sel, "subset", "complement")
    did = an.table_did({"add_log": td})
    r = did.iloc[0]
    assert r["descriptive_only"] and r["below_floor_subset"] and not r["below_floor_complement"]
    assert (r["n_pos_subset"], r["n_pos_commits_subset"]) == (3, 1)
    assert np.isnan(r["pr_auc_did_p"]) and np.isnan(r["pr_auc_did_p_holm"]) and np.isnan(r["f1_subset_p"])
    assert np.isfinite(r["pr_auc_did_delta"]) and np.isfinite(r["pr_auc_complement_p"])
    in_sub = an.boot_of(td, "hgb", "perf_part=subset", "test")["prev"] > 0
    assert r["pr_auc_did_b_used"] == in_sub.sum() < 300
    gap = an.table_subset_gap({"add_log": td})
    assert gap["descriptive_only"].all() and gap["pr_auc_p"].isna().all() and (gap["pr_auc_b_used"] < 300).all()
    ab = an.table_ablation({"add_log": td}).set_index(["scope", "variant"])
    assert ab.loc[("subset", "no_history"), "descriptive_only"] and np.isnan(ab.loc[("subset", "no_history"),
                                                                                      "pr_auc_vs_full_p"])
    assert not ab.loc[("full_test", "no_history"), "descriptive_only"]
    rg = an.error_rate_gap(td, ["hgb"]).iloc[0]
    assert rg["fn_rate_descriptive_only"] and np.isnan(rg["fn_rate_p"]) and not rg["fp_rate_descriptive_only"]
    # report and forest plot
    disp = rp._did_display(did)
    assert disp["flags"].str.contains("descriptive only, no p \\(subset 3 pos / 1 commits\\)").all()
    assert (disp["p Holm"] == "–").all()
    lines = rp._section_summary({"rq4_did": did}, {"sfx": "", "tasks": ["add_log"]})
    assert any("descriptive only, no p" in line for line in lines)
    limits = rp._section_limits({"rq4_did": did, "rq4_subset_gap": gap},
                                {"B": 200, "B_test": 300, "tasks": [], "models_by_task": {}, "model_order": [],
                                 "notices": []})
    assert any("Descriptive only in this run" in line and "rq4_did add_log" in line for line in limits)


def test_evaluate_with_sensitivity_and_posthoc(ph_tree, tmp_path):
    out = tmp_path / "out"
    args = [sys.executable, "-m", "scripts.evaluate", "--data-dir", str(ph_tree), "--results-dir", str(out),
            "--bootstrap", "10", "--bootstrap-tests", "20", "--tasks", "add_log,remove_log", "--lang", "en",
            "--examples", "1"]
    res = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-3000:] + res.stderr[-3000:]
    assert not (ph_tree / "results" / "tables").exists() and not (ph_tree / "results" / "report").exists()
    tables = out / "tables"
    for name in ("sens_add_log_post_pooled", "sens_add_log_post_vs_add_log", "sens_add_log_post_did",
                 "sens_add_log_post_pairwise", "posthoc_log1p_pooled", "posthoc_log1p_pairwise",
                 "posthoc_log1p_training"):
        assert (tables / f"{name}.csv").exists(), name
    assert "SENSITIVITY" in (tables / "sens_add_log_post_pooled.md").read_text(encoding="utf-8").splitlines()[0]
    assert "POST-HOC" in (tables / "posthoc_log1p_pairwise.md").read_text(encoding="utf-8").splitlines()[0]
    # primary tables, Holm families and figures hold neither the post-hoc models nor add_log_post
    for name in ("rq3_overall_pooled", "rq3_overall_macro", "rq3_per_repo", "pairwise", "ablation", "rq4_did",
                 "rq4_subset", "rq4_subset_gap", "dq_training", "dq_coverage", "dq_imbalance", "sensitivity_ratio"):
        df = pd.read_csv(tables / f"{name}.csv")
        for col in ("model", "model_a", "model_b"):
            if col in df:
                assert not set(df[col]) & set(POSTHOC), (name, col)
        if "task" in df:
            assert "add_log_post" not in set(df["task"]), name
    assert not any("add_log_post" in f.name or "log1p" in f.name for f in (out / "figures").iterdir())
    report = (out / "report" / "experiment_report.md").read_text(encoding="utf-8")
    head, rest = report.split("## 9. Sensitivity analysis", 1)
    summary = head.split("## 1. Summary by research question", 1)[1].split("## 2.", 1)[0]
    assert not any(m in summary for m in POSTHOC) and "- add_log_post" not in summary
    assert "POST-HOC" in rest and "commit-time" in rest
    assert "hybrid_ggnn_log1p" not in head.split("## Models available", 1)[1].split("- post-hoc", 1)[0]
    sens, post = rest.split("## 10. Post-hoc analysis", 1)
    assert "compared pairwise" in sens and "pre-state view, so both views are compared on the same split" in sens
    assert "transformed twice" in post and "- mlp_full_log1p / add_log: 7 columns (h=2; m=1; x=4); 5 of them" in post
    tr = pd.read_csv(tables / "posthoc_log1p_training.csv")
    assert set(tr["model"]) == set(POSTHOC) and (tr["n_log1p_twice_mean"] == 5).all()
    assert "except the posthoc section" in (tables / "config_hyperparameters.md").read_text(encoding="utf-8")
    hp = pd.read_csv(tables / "config_hyperparameters.csv")
    assert not hp.loc[hp["section"] == "posthoc", "prespecified"].any() and hp.loc[hp["section"] != "posthoc",
                                                                                   "prespecified"].all()
    # B used next to every bootstrap p
    pw = pd.read_csv(tables / "pairwise.csv")
    assert {"pr_auc_b_used", "f1_b_used", "macro_pr_auc_b_used"} <= set(pw.columns)
    assert "B used PR-AUC" in (tables / "pairwise.md").read_text(encoding="utf-8")
    assert {"pr_auc_did_b_used", "descriptive_only", "n_pos_commits_subset"} <= set(
        pd.read_csv(tables / "rq4_did.csv").columns)
    assert "pr_auc_vs_full_b_used" in pd.read_csv(tables / "ablation.csv")
