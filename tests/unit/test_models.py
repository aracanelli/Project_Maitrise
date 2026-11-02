"""Tests for stage 7 (src/models/*, scripts/run_experiments.py) on synthetic contract-format data."""

import json
import shutil

import numpy as np
import pandas as pd
import pytest
import torch
from torch_geometric.data import Batch
from torch_geometric.loader import DataLoader

from scripts import run_experiments
from src.common.config import load_config
from src.models import baselines, gnn, train
from src.models.data import (build_eval_set, check_paired_view, load_folds, loro_folds, nonbinary_columns,
                             prepare_tabular, select_columns, task_folds, validation_split)

TASKS = ["add_log", "remove_log", "change_level"]
REPOS = {"A": 64, "B": 56, "C": 48, "D": 24}      # D is below the test threshold: training only
CTX = ["frame_update", "loop", "subsystem", "general"]
MC = ["NO_EVENT", "ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def synth_instances(task, rng):
    rows = []
    for repo, n in REPOS.items():
        labels = (rng.random(n) < 0.25).astype(int)
        labels[:3] = 1
        n_pos = int(labels.sum())
        ranks = rng.permutation(n - n_pos)
        k = 0
        for i in range(n):
            commit = f"{repo.lower()}{i // 4:03d}" + "0" * 30
            pos = labels[i] == 1
            rank = -1 if pos else int(ranks[k])
            k += 0 if pos else 1
            rows.append({
                "instance_id": f"{task}:{repo}:{commit[:12]}:{i}", "task": task, "repo": repo,
                "commit_id": commit, "label": int(labels[i]),
                "sample_role": "positive" if pos else "negative", "neg_rank": rank,
                "in_R1": bool(pos or rank < n_pos), "in_R4": bool(pos or rank < 4 * n_pos), "in_R10": True,
            })
    return rows


def synth_features(rows, rng, labels):
    n = len(rows)
    y = np.asarray(labels, dtype=float)
    df = pd.DataFrame({"instance_id": [r["instance_id"] for r in rows]})
    df["h_prior_events"] = rng.poisson(1 + 3 * y).astype(float)
    df.loc[rng.random(n) < 0.15, "h_prior_events"] = np.nan
    df["h_author_exp"] = rng.normal(size=n)
    df["f_sloc"] = rng.poisson(200, n)
    df["f_has_logger"] = rng.integers(0, 2, n)
    df["m_loc"] = rng.poisson(15 + 25 * y)
    df["m_n_catch_without_log"] = rng.poisson(0.2 + 1.5 * y)
    df["l_n_logs"] = rng.poisson(1, n)
    df["s_level_ord"] = rng.integers(1, 6, n).astype(float)
    df["s_in_loop"] = rng.integers(0, 2, n)
    df["s_level_minus_file_mean"] = rng.normal(size=n) + y
    df.loc[rng.random(n) < 0.1, "s_level_minus_file_mean"] = np.nan
    df["s_level_eq_file_dominant"] = (rng.random(n) < 0.7 - 0.4 * y).astype(float)
    df["d_ctx_category"] = rng.choice(CTX, n)
    df["d_loop"] = (df["d_ctx_category"] == "loop").astype(int)
    df["d_is_perf_sensitive"] = (df["d_ctx_category"] != "general").astype(int)
    for b in range(6):
        df[f"x_tok_{b}"] = rng.poisson(1, n)
    return df


def synth_graph_arrays(n_graphs, rng, labels=None, n_types=7, n_rel=4, n_num=3):
    node_ptr, edge_ptr, tok_ptr = [0], [0], [0]
    node_type, node_num, tok_ids, edges, etypes, anchor, target = [], [], [], [], [], [], []
    for g in range(n_graphs):
        n = int(rng.integers(3, 9))
        types = rng.integers(0, n_types - 1, n)
        if labels is not None and labels[g]:
            types[0] = n_types - 1
        node_type.extend(types)
        node_num.append(rng.normal(size=(n, n_num)) * 5 + 3)
        for _ in range(n):
            t = int(rng.integers(0, 3))
            tok_ids.extend(rng.integers(0, 128, t))
            tok_ptr.append(tok_ptr[-1] + t)
        e = int(rng.integers(1, 3 * n))
        edges.append(rng.integers(0, n, (2, e)))
        etypes.extend(rng.integers(0, n_rel, e))
        anchor.append(n - 1)
        target.append(int(rng.integers(0, n)))
        node_ptr.append(node_ptr[-1] + n)
        edge_ptr.append(edge_ptr[-1] + e)
    return {
        "node_ptr": np.array(node_ptr, dtype=np.int64), "edge_ptr": np.array(edge_ptr, dtype=np.int64),
        "tok_ptr": np.array(tok_ptr, dtype=np.int64), "node_type": np.array(node_type, dtype=np.int16),
        "node_num": np.concatenate(node_num).astype(np.float32), "tok_ids": np.array(tok_ids, dtype=np.int16),
        "edge_index": np.concatenate(edges, axis=1).astype(np.int32), "edge_type": np.array(etypes, dtype=np.int8),
        "anchor_local": np.array(anchor, dtype=np.int32), "target_local": np.array(target, dtype=np.int32),
    }


def write_binary_task(root, task, rows, rng):
    """Instances, features (two failures) and graphs (one missing) of a binary task."""
    inst_dir, feat_dir, graph_dir = root / "instances", root / "features", root / "graphs"
    write_jsonl(inst_dir / f"{task}.jsonl", rows)
    labels = [r["label"] for r in rows]
    df = synth_features(rows, rng, labels)
    no_feat = rows[5]["instance_id"]          # failed and absent from the csv
    failed_present = rows[6]["instance_id"]   # failed but still in the csv
    df = df[df["instance_id"] != no_feat]
    df.to_csv(feat_dir / f"{task}.csv", index=False)
    groups = {c: c.split("_", 1)[0] for c in df.columns if c != "instance_id"}
    with open(feat_dir / f"{task}_groups.json", "w") as f:
        json.dump(groups, f)
    write_jsonl(feat_dir / f"{task}_failures.jsonl",
                [{"instance_id": no_feat, "reason": "unit_not_found"},
                 {"instance_id": failed_present, "reason": "mask_mismatch"}])

    no_graph = rows[7]["instance_id"]
    with_graph = [r for r in rows if r["instance_id"] != no_graph]
    perm = rng.permutation(len(with_graph))   # graph order differs from instance order
    ordered = [with_graph[p] for p in perm]
    arrays = synth_graph_arrays(len(ordered), rng, [r["label"] for r in ordered])
    np.savez(graph_dir / f"{task}.npz", **arrays)
    idx = pd.DataFrame({
        "graph_pos": np.arange(len(ordered)), "instance_id": [r["instance_id"] for r in ordered],
        "n_nodes": np.diff(arrays["node_ptr"]), "n_edges": np.diff(arrays["edge_ptr"]), "truncated": 0,
    })
    idx.to_csv(graph_dir / f"{task}_index.csv", index=False)
    with open(graph_dir / f"{task}_meta.json", "w") as f:
        json.dump({"node_types": [f"t{i}" for i in range(7)], "edge_types": [f"e{i}" for i in range(4)],
                   "numeric_features": ["a", "b", "c"]}, f)
    return {"no_feat": no_feat, "failed_present": failed_present, "no_graph": no_graph, "rows": rows}


def make_dataset(root):
    rng = np.random.default_rng(0)
    inst_dir, feat_dir, graph_dir = root / "instances", root / "features", root / "graphs"
    for d in (inst_dir, feat_dir, graph_dir):
        d.mkdir(parents=True)
    folds = {}
    info = {}
    for task in TASKS:
        rows = synth_instances(task, rng)
        info[task] = write_binary_task(root, task, rows, rng)
        folds[task] = {"test_repos": ["A", "B", "C"], "low_support": ["C"], "excluded": {"D": 6}}

    # multiclass supplement (method level, string labels)
    rows = []
    for repo, n in REPOS.items():
        for i in range(n):
            commit = f"{repo.lower()}{i // 4:03d}" + "0" * 30
            lab = MC[int(rng.choice(4, p=[0.6, 0.2, 0.12, 0.08]))]
            if i < 4:
                lab = MC[i]
            rows.append({"instance_id": f"multiclass:{repo}:{commit[:12]}:{i}", "task": "multiclass",
                         "repo": repo, "commit_id": commit, "label": lab})
    write_jsonl(inst_dir / "multiclass.jsonl", rows)
    df = synth_features(rows, rng, [int(r["label"] != "NO_EVENT") for r in rows])
    df = df[[c for c in df.columns if not c.startswith("s_")]]
    df.to_csv(feat_dir / "multiclass.csv", index=False)
    folds["multiclass"] = {"test_repos": ["A", "B", "C"], "low_support": [], "excluded": {}}

    # add_log_post: the add_log instances (same labels, flags and folds) in another view,
    # so other feature values and graphs; its own generator keeps the data above unchanged
    rows = [dict(r, instance_id="add_log_post:" + r["instance_id"].split(":", 1)[1], task="add_log_post")
            for r in info["add_log"]["rows"]]
    info["add_log_post"] = write_binary_task(root, "add_log_post", rows, np.random.default_rng(1))
    folds["add_log_post"] = dict(folds["add_log"])
    with open(inst_dir / "folds.json", "w") as f:
        json.dump(folds, f)
    return info


@pytest.fixture(scope="module", autouse=True)
def few_threads():
    # HGB's OpenMP pool degrades badly when other jobs share the CPUs
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=4):
        yield


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    root = tmp_path_factory.mktemp("processed")
    info = make_dataset(root)
    return root, info


@pytest.fixture(scope="module")
def cfg():
    return load_config("experiment")


def test_eval_sets_and_drop_counts(dataset):
    root, info = dataset
    ev4 = build_eval_set("add_log", "R4", root)
    i = info["add_log"]
    for iid in (i["no_feat"], i["failed_present"], i["no_graph"]):
        assert iid not in ev4["ids"]
    in_r4 = [r for r in i["rows"] if r["in_R4"]]
    assert ev4["n_selected"] == len(in_r4)
    assert ev4["n_selected"] - len(ev4["ids"]) == sum(ev4["dropped"].values())
    assert len(ev4["graph_pos"]) == len(ev4["ids"]) == len(ev4["y"]) == ev4["X"].shape[0]

    ev1 = build_eval_set("add_log", "R1", root)
    assert ev1["graph_pos"] is None and ev1["dropped"]["no_graph"] == 0
    in_r1 = {r["instance_id"] for r in i["rows"] if r["in_R1"]}
    assert set(ev1["ids"]) <= in_r1
    if i["no_graph"] in in_r1:
        assert i["no_graph"] in ev1["ids"]

    # rows of X are the csv rows of the same instance; ctx is one-hot
    df = pd.read_csv(root / "features" / "add_log.csv").set_index("instance_id")
    k = 10
    j = ev4["columns"].index("m_loc")
    assert ev4["X"][k, j] == df.loc[ev4["ids"][k], "m_loc"]
    ctx = [c for c in ev4["columns"] if c.startswith("d_ctx_category=")]
    assert len(ctx) == 4
    cj = [ev4["columns"].index(c) for c in ctx]
    assert np.all(ev4["X"][:, cj].sum(axis=1) == 1)
    cat = df.loc[ev4["ids"][k], "d_ctx_category"]
    assert ev4["X"][k, ev4["columns"].index(f"d_ctx_category={cat}")] == 1
    assert ev4["groups"][cj[0]] == "d"


def test_loro_split_invariants(dataset):
    root, _ = dataset
    ev = build_eval_set("add_log", "R4", root)
    fcfg = load_folds(root)["add_log"]
    folds = loro_folds(ev, fcfg)
    assert [f["test_repo"] for f in folds] == ["A", "B", "C"]
    for f in folds:
        test_repos = set(ev["repos"][f["test_idx"]])
        train = np.concatenate([f["fit_idx"], f["val_idx"]])
        assert test_repos == {f["test_repo"]}
        assert not test_repos & set(ev["repos"][train])
        assert "D" in set(ev["repos"][train])
        assert len(set(f["fit_idx"]) & set(f["val_idx"])) == 0
        assert len(train) + len(f["test_idx"]) == len(ev["ids"])
        fit_c = set(zip(ev["repos"][f["fit_idx"]], ev["commits"][f["fit_idx"]]))
        val_c = set(zip(ev["repos"][f["val_idx"]], ev["commits"][f["val_idx"]]))
        assert not fit_c & val_c
        yv = ev["y"][f["val_idx"]]
        assert yv.sum() >= 1 and (1 - yv).sum() >= 1
        assert 0.08 < len(f["val_idx"]) / len(train) < 0.3
        n_pos = int(ev["y"][f["test_idx"]].sum())
        assert n_pos >= 10 and f["low_support"] == (f["test_repo"] == "C" or n_pos < 30)

    # thresholds are re-checked on the evaluated instances: D (< 10 positives) is not tested
    # even if listed, but it still trains every other fold
    with_d = dict(fcfg, test_repos=["A", "D", "B"], low_support=[])
    names = [f["test_repo"] for f in loro_folds(ev, with_d)]
    assert int(ev["y"][ev["repos"] == "D"].sum()) < 10 and names == ["A", "B"]

    again = loro_folds(ev, fcfg)
    only_b = loro_folds(ev, fcfg, only={"B"})
    for a, b in zip(folds, again):
        assert np.array_equal(a["val_idx"], b["val_idx"]) and a["val_seed"] == b["val_seed"]
    assert np.array_equal(only_b[0]["val_idx"], folds[1]["val_idx"])
    assert folds[0]["val_seed"] == load_config("experiment")["sampling"]["seed"]


def test_validation_split_needs_both_classes():
    repos = np.array(["A"] * 10, dtype=object)
    commits = np.array([f"c{i}" for i in range(10)], dtype=object)
    with pytest.raises(RuntimeError):
        validation_split(np.arange(10), repos, commits, np.zeros(10, dtype=int), 0.15, 42)
    y = np.zeros(10, dtype=int)
    y[3] = 1
    val, seed = validation_split(np.arange(10), repos, commits, y, 0.15, 42)
    assert 3 in val and len(val) >= 2


def test_prepare_tabular_fits_on_training_rows_only():
    X = np.array([[1.0, np.nan], [3.0, 2.0], [np.nan, 4.0], [100.0, np.nan]])
    fit = np.array([0, 1, 2])
    out = prepare_tabular(X, fit, impute=True, scale=False)
    assert out[2, 0] == 2.0 and out[0, 1] == 3.0 and out[3, 1] == 3.0
    sc = prepare_tabular(X, fit, impute=True, scale=True)
    assert np.allclose(sc[fit].mean(axis=0), 0) and np.allclose(sc[fit].std(axis=0), 1)
    allnan = prepare_tabular(np.array([[np.nan], [np.nan]]), np.array([0]), True, True)
    assert np.all(allnan == 0)


def test_log1p_flag_transforms_the_nonbinary_fit_columns_only():
    nan = np.nan
    X = np.array([
        # 0/1, two values, signed continuous, binary in the fit rows only, constant, NaN + 3 values, NaN + 2 values
        [0, 3, -5.0, 0, 7, nan, nan],
        [1, 100, 0.5, 1, 7, 2.0, 4.0],
        [0, 3, 10.0, 0, 7, nan, 9.0],
        [1, 100, 2.0, 1, 7, 5.0, nan],
        [1, 3, -0.2, 0, 7, nan, 4.0],
        [0, 3, 30.0, 1, 7, 9.0, 9.0],
        [5, 50, 4.0, 9, 2, 1.0, 1.0],          # rows 6, 7 are not in the fit part
        [nan, 3, -1.0, 4, 5, nan, 20.0],
    ])
    fit = np.arange(6)
    assert nonbinary_columns(X, fit).tolist() == [False, False, True, False, False, True, False]
    assert nonbinary_columns(X, np.arange(8))[[0, 1, 3, 4, 6]].all()    # the other rows would change it
    Z = X.copy()
    Z[6:] = Z[6:] * 1000 + 3
    assert nonbinary_columns(Z, fit).tolist() == nonbinary_columns(X, fit).tolist()

    out = prepare_tabular(X, fit, impute=False, scale=False, log1p=True)
    signed = np.sign(X) * np.log1p(np.abs(X))
    for j in range(X.shape[1]):
        expect = signed[:, j] if j in (2, 5) else X[:, j]
        assert np.array_equal(out[:, j], expect, equal_nan=True), j
    assert out[0, 2] < 0 and out[4, 2] < 0
    # transform first, then the usual median imputation and standardisation on the fit rows
    full = prepare_tabular(X, fit, impute=True, scale=True, log1p=True)
    assert np.array_equal(full, prepare_tabular(out, fit, impute=True, scale=True))
    assert np.allclose(full[fit].mean(axis=0), 0)


def test_feature_sets(dataset):
    root, _ = dataset
    ev = build_eval_set("add_log", "R4", root)
    g = ev["groups"]
    assert {g[j] for j in select_columns(g, "history")} == {"h"}
    assert "h" not in {g[j] for j in select_columns(g, "static")}
    assert len(select_columns(g, "all")) == len(g)


def test_threshold_and_naive_rules():
    y = np.array([0, 0, 1, 1, 0, 1])
    s = np.array([0.1, 0.4, 0.35, 0.8, 0.2, 0.9])
    t = baselines.f1_threshold(y, s)
    pred = (s >= t).astype(int)
    assert t == 0.35 and baselines.binary_metrics(y, s, pred)["f1"] == pytest.approx(6 / 7)

    cols = ["m_loc", "m_n_catch_without_log", "s_level_ord", "s_in_loop", "s_level_minus_file_mean",
            "s_level_eq_file_dominant"]
    X = np.array([[10, 2, 1, 1, -1.5, 0], [20, np.nan, 3, 0, np.nan, np.nan], [0, 0, 2, 0, 0.5, 1]])
    assert np.allclose(baselines.naive_rule_scores("add_log", X, cols), [2.01, 0.02, 0])
    assert np.allclose(baselines.naive_rule_scores("remove_log", X, cols), [3.01, 0.02, 2.0])
    assert np.allclose(baselines.naive_rule_scores("change_level", X, cols), [2.5, 0, 0.5])
    assert np.allclose(baselines.naive_size_scores(X, cols), [10, 20, 0])
    a = baselines.naive_prior_scores(5, 0, 1)
    assert np.array_equal(a, baselines.naive_prior_scores(5, 0, 1))
    assert not np.array_equal(a, baselines.naive_prior_scores(5, 1, 1))


@pytest.mark.parametrize("model_id", ["lr", "rf", "hgb"])
def test_classical_deterministic_given_seed(dataset, cfg, model_id):
    root, _ = dataset
    ev = build_eval_set("add_log", "R4", root)
    fold = loro_folds(ev, load_folds(root)["add_log"])[0]
    a = train.run_fold(model_id, ev, fold, 0, cfg)
    b = train.run_fold(model_id, ev, fold, 0, cfg)
    assert np.array_equal(a["scores"], b["scores"]) and a["threshold"] == b["threshold"]
    assert len(a["scores"]) == len(fold["test_idx"])


def _small_graphs():
    rng = np.random.default_rng(3)
    arrays = synth_graph_arrays(5, rng)
    arrays["node_type"] = np.arange(int(arrays["node_ptr"][-1]), dtype=np.int16)   # node type = global id
    return arrays


def test_batching_keeps_indices_inside_each_graph():
    arrays = _small_graphs()
    positions = [3, 0, 4, 1]
    graphs, info = gnn.build_graphs(arrays, positions, [1, 0, 1, 0])
    assert info["n_relations"] == int(arrays["edge_type"].max()) + 1
    batch = next(iter(DataLoader(graphs, batch_size=4, shuffle=False)))
    nptr, tptr, eptr = arrays["node_ptr"], arrays["tok_ptr"], arrays["edge_ptr"]
    exp_tok_owner, exp_edges = [], []
    for i, g in enumerate(positions):
        n0 = nptr[g]
        a, t = int(batch.anchor[i]), int(batch.target[i])
        assert int(batch.batch[a]) == i and int(batch.batch[t]) == i
        assert int(batch.node_type[a]) == n0 + arrays["anchor_local"][g]
        assert int(batch.node_type[t]) == n0 + arrays["target_local"][g]
        for node in range(n0, nptr[g + 1]):
            exp_tok_owner.extend([node] * int(tptr[node + 1] - tptr[node]))
        exp_edges.append(arrays["edge_index"][:, eptr[g]:eptr[g + 1]] + n0)
    assert batch.node_type[batch.tok_node].tolist() == exp_tok_owner
    assert np.array_equal(batch.node_type[batch.edge_index].numpy(), np.concatenate(exp_edges, axis=1))
    assert batch.gidx.tolist() == [0, 1, 2, 3]
    assert batch.y.tolist() == [1, 0, 1, 0]


@pytest.mark.parametrize("bases,root", [(4, True), (4, False), (None, True)])
def test_fused_rgcn_matches_pyg_rgcnconv(bases, root):
    from torch_geometric.nn import RGCNConv
    torch.manual_seed(0)
    n, e, r, d = 300, 1500, 14, 32
    x = torch.randn(n, d, requires_grad=True)
    ei = torch.randint(0, n, (2, e))
    et = torch.randint(0, r, (e,))
    ref = RGCNConv(d, 16, r, num_bases=bases, root_weight=root)
    fused = gnn.FusedRGCNConv(d, 16, r, num_bases=bases, root_weight=root)
    fused.load_state_dict(ref.state_dict())
    a, b = ref(x, ei, et), fused(x, ei, et)
    assert torch.allclose(a, b, atol=1e-5)
    ga = torch.autograd.grad(a.square().sum(), [x] + list(ref.parameters()))
    gb = torch.autograd.grad(b.square().sum(), [x] + list(fused.parameters()))
    for u, v in zip(ga, gb):
        assert torch.allclose(u, v, rtol=1e-4, atol=1e-4)


def test_node_encoder_and_mean_pool_match_reference(cfg):
    from torch_geometric.nn import global_mean_pool
    from torch_geometric.utils import scatter
    arrays = synth_graph_arrays(6, np.random.default_rng(4))
    graphs, info = gnn.build_graphs(arrays, [0, 1, 2, 3, 4, 5], [0] * 6)
    batch = Batch.from_data_list(graphs)
    enc = gnn.NodeEncoder(info["n_node_types"], info["n_num"], info["n_tokens"], 16, 8, 8)
    with torch.no_grad():
        parts = [enc.type_emb(batch.node_type), enc.num_lin(batch.x_num),
                 scatter(enc.tok_emb(batch.tok_ids), batch.tok_node, 0, dim_size=batch.num_nodes, reduce="mean")]
        ref = torch.relu(enc.proj(torch.cat(parts, dim=1)))
        assert torch.allclose(enc(batch), ref, atol=1e-6)
        h = torch.randn(batch.num_nodes, 5)
        pool = gnn.mean_pool_operator(batch.batch, batch.num_graphs)
        assert torch.allclose(gnn.SpMM.apply(pool, h), global_mean_pool(h, batch.batch), atol=1e-6)


DEVICES = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])


@pytest.mark.parametrize("device", DEVICES)
def test_spmm_matches_dense_product_and_gradient(device):
    g = torch.Generator().manual_seed(0)
    n_rows, n_cols, nnz = 40, 30, 300
    rows = torch.randint(0, n_rows - 5, (nnz,), generator=g)      # last rows and columns stay empty
    cols = torch.randint(0, n_cols - 3, (nnz,), generator=g)
    vals = torch.rand(nnz, generator=g)
    dense = torch.zeros(n_rows, n_cols).index_put_((rows, cols), vals, accumulate=True)
    op = gnn.sparse_operator(rows.to(device), cols.to(device), vals.to(device), n_rows, n_cols)
    x = torch.randn(n_cols, 7, generator=g).to(device).requires_grad_(True)
    up = torch.randn(n_rows, 7, generator=g).to(device)
    out = gnn.SpMM.apply(op, x)
    (out * up).sum().backward()
    d = dense.to(device)
    assert torch.allclose(out, d @ x.detach(), atol=1e-5)
    assert torch.allclose(x.grad, d.t() @ up, atol=1e-5)
    empty = gnn.sparse_operator(*(t[:0].to(device) for t in (rows, cols, vals)), n_rows, n_cols)
    assert torch.equal(gnn.SpMM.apply(empty, x.detach()), torch.zeros(n_rows, 7, device=device))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_spmm_is_bitwise_repeatable_on_long_rows_on_gpu():
    # cuSPARSE CSR products stop repeating bitwise at >= 64 non-zeros per row
    g = torch.Generator().manual_seed(1)
    n, per_row = 2000, 150
    rows = torch.arange(n).repeat_interleave(per_row).cuda()
    cols = torch.randint(0, n, (n * per_row,), generator=g).cuda()
    op = gnn.sparse_operator(rows, cols, torch.rand(n * per_row, generator=g).cuda(), n, n)
    x = torch.randn(n, 128, generator=g).cuda()
    up = torch.randn(n, 128, generator=g).cuda()
    ref_out, ref_grad = None, None
    for _ in range(10):
        xi = x.clone().requires_grad_(True)
        out = gnn.SpMM.apply(op, xi)
        (out * up).sum().backward()
        if ref_out is None:
            ref_out, ref_grad = out.detach(), xi.grad
        assert torch.equal(out, ref_out) and torch.equal(xi.grad, ref_grad)


def hub_graph_arrays(n_graphs, seed=0):
    """Graphs shaped like the real ones (~150 nodes, ~600 edges, 14 relations) whose node 0
    also has 100 incoming edges of relation 0 and 100 outgoing edges of relation 1, so the
    relation and pooling sums have rows and columns of more than 64 entries."""
    a = run_experiments.synthetic_graph_arrays(n_graphs, 150, 600, 14, 32, 8, seed)
    edges, types = [], []
    for g in range(n_graphs):
        n = int(a["node_ptr"][g + 1] - a["node_ptr"][g])
        e0, e1 = int(a["edge_ptr"][g]), int(a["edge_ptr"][g + 1])
        k = np.arange(1, min(100, n - 1) + 1)
        z = np.zeros_like(k)
        edges.append(np.concatenate([a["edge_index"][:, e0:e1], np.stack([k, z]), np.stack([z, k])], axis=1))
        types.append(np.concatenate([a["edge_type"][e0:e1], np.zeros(len(k)), np.ones(len(k))]))
    a["edge_index"] = np.concatenate(edges, axis=1).astype(np.int32)
    a["edge_type"] = np.concatenate(types).astype(np.int8)
    a["edge_ptr"] = np.concatenate([[0], np.cumsum([e.shape[1] for e in edges])]).astype(np.int64)
    return a


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_graph_training_is_bitwise_reproducible_on_realistic_graphs(cfg):
    G = 300
    arrays = hub_graph_arrays(G)
    y = (np.random.default_rng(1).random(G) < 0.25).astype(np.int64)
    graphs, info = gnn.build_graphs(arrays, np.arange(G), y)
    assert info["n_relations"] == 14 and np.diff(arrays["node_ptr"]).min() >= 100
    ev = {"task": "add_log", "y": y, "X": np.random.default_rng(2).normal(size=(G, 12)),
          "groups": ["h"] * 4 + ["m"] * 8, "columns": [f"c{j}" for j in range(12)]}
    idx = np.arange(G)
    fold = {"test_repo": "t", "fold_index": 0, "val_seed": 0, "low_support": False,
            "fit_idx": idx[:200], "val_idx": idx[200:250], "test_idx": idx[250:]}
    for model_id in ("gnn_rgcn", "gnn_ggnn", "hybrid_ggnn"):
        a = train.run_fold(model_id, ev, fold, 0, cfg, graphs, info, "cuda", max_epochs=2)
        b = train.run_fold(model_id, ev, fold, 0, cfg, graphs, info, "cuda", max_epochs=2)
        assert np.array_equal(a["scores"], b["scores"]), model_id
        assert np.array_equal(a["val_scores"], b["val_scores"]) and a["threshold"] == b["threshold"]
        assert a["info"]["history"] == b["info"]["history"]


@pytest.mark.parametrize("device", DEVICES)
def test_graph_training_is_bitwise_reproducible(dataset, cfg, device):
    root, _ = dataset
    ev = build_eval_set("add_log", "R4", root)
    fold = loro_folds(ev, load_folds(root)["add_log"])[0]
    arrays, meta = gnn.load_graph_arrays("add_log", root)
    graphs, info = gnn.build_graphs(arrays, ev["graph_pos"], ev["y"], meta)
    for model_id in ("gnn_rgcn", "hybrid_ggnn"):
        a = train.run_fold(model_id, ev, fold, 0, cfg, graphs, info, device, max_epochs=3)
        b = train.run_fold(model_id, ev, fold, 0, cfg, graphs, info, device, max_epochs=3)
        c = train.run_fold(model_id, ev, fold, 1, cfg, graphs, info, device, max_epochs=3)
        assert np.array_equal(a["scores"], b["scores"]) and a["threshold"] == b["threshold"]
        assert not np.array_equal(a["scores"], c["scores"])


def test_hybrid_reads_tabular_row_by_gidx(cfg):
    arrays = _small_graphs()
    graphs, info = gnn.build_graphs(arrays, [3, 0, 4], [1, 0, 1])
    model = gnn.GraphNet("ggnn", info, cfg["models"]["gnn"], 2, n_tab=4)
    table = torch.arange(12, dtype=torch.float32).view(3, 4)
    model.set_tab_table(table)
    seen = []
    model.tab.register_forward_hook(lambda m, inp, out: seen.append(inp[0].clone()))
    model.eval()
    out = model(Batch.from_data_list([graphs[2], graphs[0]]))
    assert out.shape == (2,)
    assert torch.equal(seen[0], table[[2, 0]])


def test_hybrid_table_is_standardised_per_fold(dataset, cfg, monkeypatch):
    root, _ = dataset
    ev = build_eval_set("add_log", "R4", root)
    folds = loro_folds(ev, load_folds(root)["add_log"])
    arrays, meta = gnn.load_graph_arrays("add_log", root)
    graphs, info = gnn.build_graphs(arrays, ev["graph_pos"], ev["y"], meta)
    # graph k is the graph of instance k (gidx = position in the evaluation set)
    idx = pd.read_csv(root / "graphs" / "add_log_index.csv").set_index("graph_pos")
    for k in (0, 17, len(graphs) - 1):
        assert idx.loc[int(ev["graph_pos"][k]), "instance_id"] == ev["ids"][k]
        assert int(graphs[k].gidx) == k and int(graphs[k].y) == ev["y"][k]
    tables = []
    monkeypatch.setattr(gnn.GraphNet, "set_tab_table", lambda self, t: (tables.append(t.cpu()),
                                                                          setattr(self, "tab_table", t)))
    cols = select_columns(ev["groups"], "static")
    for f in folds[:2]:
        train.run_fold("hybrid_ggnn_nohist", ev, f, 0, cfg, graphs, info, max_epochs=1)
        expect = prepare_tabular(ev["X"][:, cols], f["fit_idx"], True, True)
        assert np.allclose(tables[-1].numpy(), expect, atol=1e-5)
        assert np.allclose(tables[-1][f["fit_idx"]].mean(0).numpy(), 0, atol=1e-5)
    assert not torch.allclose(tables[0], tables[1])


def test_posthoc_variants_are_their_base_models_plus_the_transform(dataset, cfg, monkeypatch):
    root, _ = dataset
    ev = build_eval_set("add_log", "R4", root)
    fold = loro_folds(ev, load_folds(root)["add_log"])[0]
    arrays, meta = gnn.load_graph_arrays("add_log", root)
    graphs, info = gnn.build_graphs(arrays, ev["graph_pos"], ev["y"], meta)
    cols = select_columns(ev["groups"], "all")
    fit = fold["fit_idx"]
    n_log1p = int(nonbinary_columns(ev["X"][:, cols], fit).sum())
    assert 0 < n_log1p < len(cols)

    calls, tables = [], []
    real_prepare = train.prepare_tabular
    monkeypatch.setattr(train, "prepare_tabular", lambda *a, **k: (calls.append(k.get("log1p", False)),
                                                                  real_prepare(*a, **k))[1])
    monkeypatch.setattr(gnn.GraphNet, "set_tab_table", lambda self, t: (tables.append(t.cpu()),
                                                                          setattr(self, "tab_table", t)))

    def run(model_id):
        calls.clear()
        res = train.run_fold(model_id, ev, fold, 0, cfg, graphs, info, "cpu", max_epochs=2)
        return res, list(calls)

    runs = {}
    for base in ("lr", "mlp_full", "hybrid_ggnn"):
        runs[base], flags = run(base)
        assert flags == [False] and "n_log1p_columns" not in runs[base]["info"], base
    base_table = tables[-1]
    assert np.allclose(base_table.numpy(), prepare_tabular(ev["X"][:, cols], fit, True, True), atol=1e-6)
    moved = [ev["columns"][j] for j, m in zip(cols, nonbinary_columns(ev["X"][:, cols], fit)) if m]
    assert "f_has_logger" not in moved and "x_tok_0" in moved and "h_prior_events" in moved
    for variant, base in train.POSTHOC.items():
        runs[variant], flags = run(variant)
        assert flags == [True], variant
        fi = runs[variant]["info"]
        assert fi["n_log1p_columns"] == n_log1p and fi["log1p_columns"] == moved
        assert sum(fi["log1p_columns_by_group"].values()) == n_log1p
        assert fi["log1p_columns_by_group"]["x"] == sum(c.startswith("x_") for c in moved)
        assert fi["tabular_transform"] == "signed_log1p_nonbinary"
        assert not np.array_equal(runs[variant]["scores"], runs[base]["scores"]), variant
    expect = prepare_tabular(ev["X"][:, cols], fit, True, True, log1p=True)
    assert np.allclose(tables[-1].numpy(), expect, atol=1e-6) and not torch.allclose(tables[-1], base_table)

    # with no column to transform, each variant is its base model bit for bit (same code path)
    monkeypatch.setattr("src.models.data.nonbinary_columns", lambda X, fit_idx: np.zeros(X.shape[1], dtype=bool))
    for variant, base in train.POSTHOC.items():
        res, _ = run(variant)
        assert np.array_equal(res["scores"], runs[base]["scores"]), variant
        assert np.array_equal(res["val_scores"], runs[base]["val_scores"]) and res["threshold"] == runs[base]["threshold"]


def test_test_repository_cannot_influence_training(dataset, cfg):
    # LORO invariant: perturbing the held-out repository's features, labels and graphs must
    # leave everything learned (imputation, scaling, node statistics, early stopping,
    # threshold) unchanged, so the threshold and the validation scores are identical
    root, _ = dataset
    ev = build_eval_set("add_log", "R4", root)
    fold = loro_folds(ev, load_folds(root)["add_log"])[0]
    arrays, meta = gnn.load_graph_arrays("add_log", root)
    graphs, info = gnn.build_graphs(arrays, ev["graph_pos"], ev["y"], meta)
    test = fold["test_idx"]
    bad = dict(ev, X=ev["X"].copy(), y=ev["y"].copy())
    bad["X"][test] = bad["X"][test] * 1000 + 77
    bad["X"][test[::3]] = np.nan
    bad["y"][test] = 1 - bad["y"][test]
    bad_graphs = list(graphs)
    for i in test:
        g = graphs[i].clone()
        g.x_num = g.x_num * 1000 + 5
        g.node_type = torch.full_like(g.node_type, info["n_node_types"] - 1)
        g.y = 1 - g.y
        bad_graphs[i] = g
    for model_id in train.MODEL_GROUPS["all"] + train.MODEL_GROUPS["posthoc"]:
        a = train.run_fold(model_id, ev, fold, 0, cfg, graphs, info, "cpu", max_epochs=2)
        b = train.run_fold(model_id, bad, fold, 0, cfg, bad_graphs, info, "cpu", max_epochs=2)
        assert a["threshold"] == b["threshold"], model_id
        assert a["info"]["val"] == b["info"]["val"], model_id
        assert np.array_equal(a["val_scores"], b["val_scores"]), model_id
        assert a["info"].get("history") == b["info"].get("history"), model_id
        assert a["info"].get("n_log1p_columns") == b["info"].get("n_log1p_columns"), model_id
        assert a["info"].get("log1p_columns") == b["info"].get("log1p_columns"), model_id
        if model_id != "naive_prior":     # the perturbation does reach the test scores
            assert not np.array_equal(a["scores"], b["scores"]), model_id

    ev = build_eval_set("multiclass", "R4", root)
    fold = loro_folds(ev, load_folds(root)["multiclass"])[0]
    test = fold["test_idx"]
    bad = dict(ev, X=ev["X"].copy(), y=ev["y"].copy())
    bad["X"][test] = bad["X"][test] * 1000 + 77
    bad["y"][test] = (bad["y"][test] + 1) % 4
    for model_id in train.MULTICLASS:
        a = train.run_multiclass_fold(model_id, ev, fold, 0, cfg)
        b = train.run_multiclass_fold(model_id, bad, fold, 0, cfg)
        assert a["info"]["val"] == b["info"]["val"] and np.array_equal(a["val_proba"], b["val_proba"])


def test_r1_refuses_neural_models():
    with pytest.raises(SystemExit):
        run_experiments.expand_models("gnn_ggnn", "R1", "add_log")
    with pytest.raises(SystemExit):
        run_experiments.expand_models("neural", "R10", "add_log")
    assert run_experiments.expand_models("all", "R1", "add_log") == train.NAIVE + train.CLASSICAL
    assert run_experiments.expand_models("naive,lr", "R4", "add_log") == train.NAIVE + ["lr"]
    assert run_experiments.expand_models("all", "R4", "multiclass") == train.MULTICLASS


def test_posthoc_group_is_separate_and_scoped():
    for task in ("add_log", "remove_log", "change_level"):
        assert run_experiments.expand_models("posthoc", "R4", task) == list(train.POSTHOC)
    assert not set(train.POSTHOC) & set(run_experiments.expand_models("all", "R4", "add_log"))
    assert run_experiments.expand_models("all", "R4", "add_log_post") == train.MODEL_GROUPS["all"]
    for setting, task in (("R1", "add_log"), ("R10", "remove_log"), ("R4", "add_log_post"), ("R4", "multiclass")):
        with pytest.raises(SystemExit):
            run_experiments.expand_models("lr_log1p", setting, task)


# run keys of every pre-specified model for fixed evaluation-set hashes, computed with the code
# and configs/experiment.yaml that produced the official predictions. A difference means the official outputs would be refused as "other configuration".
PINNED_RUN_KEYS = {
    "naive_prior": "26b405711e1316b0af4883bb83c8cde7b8700366",
    "naive_size": "3415d753f536a0f787822688c70d93390f40ac46",
    "naive_rule": "0e3b63e8d9c9dceb1dff13ba3ce78885ca6588a6",
    "lr": "79f766c74855f4890b32270382a8f3b2c7e1c86d",
    "rf": "fd534c088f532595a2f6d5196bb7c0c1fdd633bf",
    "hgb": "9c8da861cb4b0b538905ebf8a56dc89c92bfe57e",
    "mlp_full": "1bfbee7a07d29a560e5a1a9cce89b15187a56818",
    "mlp_hist": "640c0b423b4fb5a3a82ed9e47fe685276397e607",
    "gnn_rgcn": "9520f128cdaea3f2f2f3f3c38874d4e46aaff1ff",
    "gnn_ggnn": "36d131a741d8a9c3c08d4582925a7b078db51b62",
    "hybrid_ggnn": "b6f5d3cdd558dc60f0fc983bae8e6ed0b7eef73d",
    "hybrid_ggnn_nohist": "111b99a824a10845b12043fa52cf79647265774c",
    "lr_multiclass": "1f6e886c7bfe014fb200f2b864e18341ea044b84",
    "hgb_multiclass": "984d6e8f11d98eb154387ec7c3d512b62e394159",
}


PINNED_FOLDS = {"test_repos": ["A", "B"], "low_support": [], "excluded": {}}


def _keys(cfg, models, folds=PINNED_FOLDS):
    import argparse
    ev = {"eval_set_sha1": "e" * 40, "content_sha1": "c" * 40}
    inputs = {"folds": folds, "graph_inputs_sha1": "g" * 40}
    args = argparse.Namespace(max_epochs=None, device="cuda")
    return {m: run_experiments.run_key(m, cfg, ev, args, inputs)[0] for m in models}


def test_run_keys_of_the_prespecified_models_are_unchanged(cfg):
    assert _keys(cfg, PINNED_RUN_KEYS) == PINNED_RUN_KEYS


def test_run_keys_ignore_yaml_comments_and_other_sections(cfg):
    import copy
    import re

    import yaml
    from src.common.config import CONFIGS
    models = list(PINNED_RUN_KEYS) + list(train.POSTHOC)
    text = (CONFIGS / "experiment.yaml").read_text(encoding="utf-8")
    assert "#" in text
    stripped = "\n".join(re.sub(r"\s+#.*$", "", line) for line in text.splitlines() if not line.lstrip().startswith("#"))
    noisy = "\n".join(line + ("   # another comment" if line.strip() else "") for line in text.splitlines())
    keys = _keys(cfg, models)
    for variant in (stripped, "# header\n" + noisy):
        parsed = yaml.safe_load(variant)
        assert parsed == cfg
        assert _keys(parsed, models) == keys

    # sections no model reads do not key the pre-specified models
    other = copy.deepcopy(cfg)
    del other["posthoc"], other["evaluation"], other["features"]
    assert _keys(other, PINNED_RUN_KEYS) == PINNED_RUN_KEYS

    # the transform is part of a post-hoc variant's key and of its recorded config
    for variant, base in train.POSTHOC.items():
        conf = train.model_config(variant, cfg)
        assert conf["posthoc"] == {"base": base, "tabular_transform": "signed_log1p_nonbinary", "prespecified": False}
        assert {k: v for k, v in conf.items() if k != "posthoc"} == train.model_config(base, cfg)
        assert keys[variant] != keys[base]
    changed = copy.deepcopy(cfg)
    changed["posthoc"]["tabular_transform"] = "log1p_all"
    with pytest.raises(ValueError):
        _keys(changed, ["lr_log1p"])


def test_documentation_only_values_are_keyed_as_their_comment_says(cfg):
    # a value marked "documentation only" is either inert or, if its comment says so, part of
    # the run keys (editing it invalidates the predictions): check every such comment
    import copy
    import re

    from src.common.config import CONFIGS
    models = list(PINNED_RUN_KEYS) + list(train.POSTHOC)
    keys = _keys(cfg, models)
    stack, seen = [], []
    for line in (CONFIGS / "experiment.yaml").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^( *)(\w+):(.*)$", line)
        if not m:
            continue
        indent = len(m.group(1))
        stack = [(i, k) for i, k in stack if i < indent] + [(indent, m.group(2))]
        comment = m.group(3)
        if "documentation only" not in comment:
            continue
        edited = copy.deepcopy(cfg)
        node = edited
        for _, k in stack[:-1]:
            node = node[k]
        node[stack[-1][1]] = "edited"
        new = _keys(edited, models)
        changed = {x for x in models if new[x] != keys[x]}
        if "every run key" in comment:
            expect = set(models)
        elif "run key of the neural and graph models" in comment:
            expect = {x for x in models if run_experiments.is_neural(x)}
        else:
            assert "run key" not in comment
            expect = set()
        path = ".".join(k for _, k in stack)
        assert changed == expect, path
        seen.append(path)
    assert len(seen) == 10 and "protocol.scheme" in seen and "models.training.pos_weight" in seen


def test_run_keys_ignore_informational_folds_fields(cfg):
    # the dataset rebuild adds per_repo and few_commit_folds to every folds.json entry; they
    # change no fold, so the outputs of unchanged tasks must keep their keys
    models = list(PINNED_RUN_KEYS) + list(train.POSTHOC)
    keys = _keys(cfg, models)
    extra = dict(PINNED_FOLDS, per_repo={"A": {"n_pos": 12, "n_pos_commits": 3, "max_commit_share": 0.5}},
                 few_commit_folds=["B"])
    assert _keys(cfg, models, extra) == keys
    assert {m: keys[m] for m in PINNED_RUN_KEYS} == PINNED_RUN_KEYS
    for field, value in (("test_repos", ["A"]), ("low_support", ["B"]), ("excluded", {"C": 3})):
        changed = _keys(cfg, models, dict(extra, **{field: value}))
        assert all(changed[m] != keys[m] for m in models), field


def _main(root, out, *extra):
    argv = ["--data-dir", str(root), "--results-dir", str(out), "--seeds", "0", "--device",
            "cuda" if torch.cuda.is_available() else "cpu"] + list(extra)
    return run_experiments.main(argv)


def _run(root, out, *extra):
    assert _main(root, out, *extra) == 0


def _pred(out, model, setting="R4", task="add_log", ext="csv"):
    return out / "predictions" / setting / task / model / f"seed0.{ext}"


def test_end_to_end_every_model(dataset, tmp_path):
    root, _ = dataset
    _run(root, tmp_path, "--setting", "R4", "--task", "add_log", "--models", "all", "--folds", "A",
         "--max-epochs", "2", "--importance")
    ev = build_eval_set("add_log", "R4", root)
    n_test = int((ev["repos"] == "A").sum())
    for model_id in train.MODEL_GROUPS["all"]:
        d = tmp_path / "predictions" / "R4" / "add_log" / model_id
        df = pd.read_csv(d / "seed0.csv")
        assert list(df.columns) == ["instance_id", "test_repo", "y_true", "score", "y_pred", "threshold"]
        assert len(df) == n_test and set(df["test_repo"]) == {"A"}
        assert set(df["y_pred"]) <= {0, 1} and df["threshold"].nunique() == 1
        assert df["score"].notna().all()
        if model_id == "naive_prior":
            assert (df["y_pred"] == (df["score"] < df["threshold"])).all()
        else:
            assert (df["y_pred"] == (df["score"] >= df["threshold"])).all()
        side = json.loads((d / "seed0.json").read_text())
        assert side["complete"] is False and len(side["folds"]) == 1
        f = side["folds"][0]
        for key in ("threshold", "val", "train_seconds", "n_train", "n_val", "n_test", "test_repo"):
            assert key in f
        assert f["n_test"] == n_test and side["dropped"] == ev["dropped"]
        if model_id in train.NEURAL + train.GRAPH:
            assert f["epochs"] == 2 and side["max_epochs_override"] == 2
    imp = tmp_path / "importance" / "R4" / "add_log"
    feats = pd.read_csv(imp / "hgb_seed0_features.csv")
    groups = pd.read_csv(imp / "hgb_seed0_groups.csv")
    assert list(feats.columns) == ["fold", "feature", "mean_drop", "std"]
    assert list(groups.columns) == ["fold", "group", "mean_drop", "std"]
    assert set(groups["group"]) == {"h", "f", "m", "l", "s", "d", "x"}
    assert len(feats) == len(ev["columns"])


def test_naive_rules_for_statement_tasks(dataset, tmp_path):
    root, _ = dataset
    for task in ("remove_log", "change_level"):
        _run(root, tmp_path, "--setting", "R4", "--task", task, "--models", "naive_rule,hgb")
        df = pd.read_csv(tmp_path / "predictions" / "R4" / task / "naive_rule" / "seed0.csv")
        assert set(df["test_repo"]) == {"A", "B", "C"}
        side = json.loads((tmp_path / "predictions" / "R4" / task / "hgb" / "seed0.json").read_text())
        assert side["complete"] is True and [f["test_repo"] for f in side["folds"]] == ["A", "B", "C"]


def test_resume_and_skip(dataset, tmp_path):
    root, _ = dataset
    full = tmp_path / "full"
    part = tmp_path / "part"
    _run(root, full, "--setting", "R1", "--task", "add_log", "--models", "lr,hgb,naive_size")
    _run(root, part, "--setting", "R1", "--task", "add_log", "--models", "lr,hgb,naive_size", "--folds", "B")
    p = _pred(part, "lr", "R1")
    assert json.loads(p.with_suffix(".json").read_text())["complete"] is False
    _run(root, part, "--setting", "R1", "--task", "add_log", "--models", "lr,hgb,naive_size")
    for m in ("lr", "hgb", "naive_size"):
        # the folds read back on resume keep every bit of their scores
        assert _pred(full, m, "R1").read_bytes() == _pred(part, m, "R1").read_bytes(), m
    side = json.loads(p.with_suffix(".json").read_text())
    assert side["complete"] is True and [f["test_repo"] for f in side["folds"]] == ["A", "B", "C"]
    assert all(f["code_sha1"] == side["code_sha1"] and "environment" in f for f in side["folds"])
    before = p.stat().st_mtime_ns
    _run(root, part, "--setting", "R1", "--task", "add_log", "--models", "lr")
    assert p.stat().st_mtime_ns == before


def test_crash_between_csv_and_sidecar_write(dataset, tmp_path):
    root, _ = dataset
    _run(root, tmp_path / "full", "--task", "add_log", "--models", "lr")
    out = tmp_path / "crash"
    _run(root, out, "--task", "add_log", "--models", "lr", "--folds", "A,B")
    # killed after the csv (folds A, B) was replaced but before the sidecar listed B
    s = _pred(out, "lr", ext="json")
    side = json.loads(s.read_text())
    side["folds"] = [f for f in side["folds"] if f["test_repo"] != "B"]
    s.write_text(json.dumps(side))
    _run(root, out, "--task", "add_log", "--models", "lr")
    df = pd.read_csv(_pred(out, "lr"))
    assert not df["instance_id"].duplicated().any()
    assert _pred(out, "lr").read_bytes() == _pred(tmp_path / "full", "lr").read_bytes()


def test_smoke_runs_need_their_own_results_dir(dataset):
    root, _ = dataset
    with pytest.raises(SystemExit):
        run_experiments.main(["--data-dir", str(root), "--task", "add_log", "--models", "mlp_hist",
                              "--max-epochs", "2"])


def test_configuration_mismatch_is_an_error(dataset, tmp_path):
    root, _ = dataset
    _run(root, tmp_path, "--task", "add_log", "--models", "mlp_hist", "--max-epochs", "2", "--device", "cpu")
    p = _pred(tmp_path, "mlp_hist")
    before = p.read_bytes()
    # the protocol run must not silently keep the smoke-run output
    assert _main(root, tmp_path, "--task", "add_log", "--models", "mlp_hist", "--device", "cpu") == 2
    assert p.read_bytes() == before
    _run(root, tmp_path, "--task", "add_log", "--models", "mlp_hist", "--device", "cpu", "--overwrite")
    side = json.loads(p.with_suffix(".json").read_text())
    assert side["max_epochs_override"] is None and side["complete"] is True
    assert any(f["epochs"] > 2 for f in side["folds"])


def test_changed_inputs_are_detected(dataset, tmp_path):
    root = tmp_path / "processed"
    shutil.copytree(dataset[0], root)
    out = tmp_path / "out"
    _run(root, out, "--task", "add_log", "--models", "lr,gnn_rgcn", "--folds", "A", "--max-epochs", "1")

    # graph files key the graph models only
    with np.load(root / "graphs" / "add_log.npz") as z:
        arrays = {k: z[k] for k in z.files}
    arrays["node_num"] = arrays["node_num"] * 2
    np.savez(root / "graphs" / "add_log.npz", **arrays)
    assert _main(root, out, "--task", "add_log", "--models", "gnn_rgcn", "--max-epochs", "1") == 2
    _run(root, out, "--task", "add_log", "--models", "lr", "--folds", "A,B")

    # a rebuilt feature table must not be joined with folds made from the old one
    df = pd.read_csv(root / "features" / "add_log.csv")
    df["m_loc"] = 0
    df["m_new_feature"] = 1.0
    df.to_csv(root / "features" / "add_log.csv", index=False)
    assert _main(root, out, "--task", "add_log", "--models", "lr") == 2
    _run(root, out, "--task", "add_log", "--models", "lr", "--overwrite")
    side = json.loads(_pred(out, "lr", ext="json").read_text())
    assert side["complete"] and len({f["n_features"] for f in side["folds"]}) == 1


def test_resume_never_mixes_code_versions(dataset, tmp_path, monkeypatch):
    root, _ = dataset
    real = run_experiments.code_sha1()
    monkeypatch.setattr(run_experiments, "code_sha1", lambda: "older-code")
    _run(root, tmp_path, "--task", "add_log", "--models", "lr", "--folds", "A")
    _run(root, tmp_path, "--task", "add_log", "--models", "naive_size")
    monkeypatch.setattr(run_experiments, "code_sha1", lambda: real)
    assert _main(root, tmp_path, "--task", "add_log", "--models", "lr") == 2
    # a complete output made by other code is kept (and warned about), never extended
    before = _pred(tmp_path, "naive_size").stat().st_mtime_ns
    _run(root, tmp_path, "--task", "add_log", "--models", "naive_size")
    assert _pred(tmp_path, "naive_size").stat().st_mtime_ns == before
    _run(root, tmp_path, "--task", "add_log", "--models", "lr", "--overwrite")
    side = json.loads(_pred(tmp_path, "lr", ext="json").read_text())
    assert {f["code_sha1"] for f in side["folds"]} == {real} and side["complete"]


def test_importance_is_tracked_per_fold(dataset, tmp_path):
    root = tmp_path / "processed"
    shutil.copytree(dataset[0], root)
    imp = lambda out, name: out / "importance" / "R4" / "add_log" / f"hgb_seed0_{name}"
    _run(root, tmp_path / "once", "--task", "add_log", "--models", "hgb", "--importance")
    out = tmp_path / "chunks"
    _run(root, out, "--task", "add_log", "--models", "hgb", "--importance", "--folds", "A")
    assert set(pd.read_csv(imp(out, "groups.csv"))["fold"]) == {"A"}
    _run(root, out, "--task", "add_log", "--models", "hgb", "--importance")
    for name in ("features.csv", "groups.csv"):
        assert imp(out, name).read_bytes() == imp(tmp_path / "once", name).read_bytes()
    side = json.loads((out / "importance" / "R4" / "add_log" / "hgb_seed0.json").read_text())
    assert side["complete"] and [f["test_repo"] for f in side["folds"]] == ["A", "B", "C"]

    # --overwrite --folds B recomputes B only and keeps A and C
    _run(root, out, "--task", "add_log", "--models", "hgb", "--importance", "--folds", "B", "--overwrite")
    assert set(pd.read_csv(imp(out, "groups.csv"))["fold"]) == {"A", "B", "C"}
    assert imp(out, "features.csv").read_bytes() == imp(tmp_path / "once", "features.csv").read_bytes()

    df = pd.read_csv(root / "features" / "add_log.csv")
    df["m_loc"] = df["m_loc"] + 1
    df.to_csv(root / "features" / "add_log.csv", index=False)
    assert _main(root, out, "--task", "add_log", "--models", "lr", "--importance") == 2


def test_write_retries_while_the_file_is_open(tmp_path):
    import threading
    p = tmp_path / "seed0.csv"
    p.write_text("old\n")
    fh = open(p)    # on Windows os.replace fails while a reader holds the file
    threading.Timer(1.0, fh.close).start()
    run_experiments.write_atomic(p, "new\n")
    assert p.read_text() == "new\n"


def test_locked_output_is_written_after_the_next_fold(dataset, tmp_path, monkeypatch):
    root, _ = dataset
    _run(root, tmp_path / "ref", "--task", "add_log", "--models", "lr")
    real = run_experiments.write_atomic
    calls = []

    def flaky(path, text):
        calls.append(path.name)
        if len(calls) == 1:
            raise PermissionError("locked")
        real(path, text)

    monkeypatch.setattr(run_experiments, "write_atomic", flaky)
    _run(root, tmp_path / "out", "--task", "add_log", "--models", "lr")
    assert calls[0] == "seed0.csv"
    assert _pred(tmp_path / "out", "lr").read_bytes() == _pred(tmp_path / "ref", "lr").read_bytes()
    assert json.loads(_pred(tmp_path / "out", "lr", ext="json").read_text())["complete"] is True


def test_multiclass_supplement(dataset, tmp_path):
    root, _ = dataset
    _run(root, tmp_path, "--setting", "R4", "--task", "multiclass", "--models", "lr_multiclass,hgb_multiclass")
    for m in train.MULTICLASS:
        df = pd.read_csv(tmp_path / "predictions" / "R4" / "multiclass" / m / "seed0.csv")
        score_cols = [f"score_{c}" for c in MC]
        assert list(df.columns) == ["instance_id", "test_repo", "y_true", "y_pred"] + score_cols
        assert set(df["y_true"]) <= set(MC) and set(df["y_pred"]) <= set(MC)
        assert np.allclose(df[score_cols].sum(axis=1), 1)
        assert (df[score_cols].values.argmax(1) == df["y_pred"].map(MC.index).values).all()
        assert set(df["test_repo"]) == {"A", "B", "C"}


def test_add_log_post_end_to_end(dataset, tmp_path):
    root, info = dataset
    _run(root, tmp_path, "--task", "add_log_post", "--models", "all", "--folds", "A", "--max-epochs", "1",
         "--importance")
    ev = build_eval_set("add_log_post", "R4", root)
    ev_add = build_eval_set("add_log", "R4", root)
    # same instances as add_log in another view: the same evaluation rows, folds and splits
    assert [i.split(":", 1)[1] for i in ev["ids"]] == [i.split(":", 1)[1] for i in ev_add["ids"]]
    assert np.array_equal(ev["y"], ev_add["y"]) and not np.array_equal(ev["X"], ev_add["X"], equal_nan=True)
    folds = load_folds(root)
    for a, b in zip(loro_folds(ev, task_folds(folds, "add_log_post")), loro_folds(ev_add, folds["add_log"])):
        for k in ("fit_idx", "val_idx", "test_idx"):
            assert np.array_equal(a[k], b[k])
    n_test = int((ev["repos"] == "A").sum())
    for model_id in train.MODEL_GROUPS["all"]:
        df = pd.read_csv(_pred(tmp_path, model_id, task="add_log_post"))
        assert len(df) == n_test and df["instance_id"].str.startswith("add_log_post:").all(), model_id
        assert df["score"].notna().all()
        side = json.loads(_pred(tmp_path, model_id, task="add_log_post", ext="json").read_text())
        assert side["task"] == "add_log_post" and side["content_sha1"] == ev["content_sha1"]
        assert side["paired_with"] == {"task": "add_log", "eval_set_sha1": ev_add["eval_set_sha1"],
                                       "n_eval": len(ev_add["ids"])}
    assert (tmp_path / "importance" / "R4" / "add_log_post" / "hgb_seed0_groups.csv").exists()
    # the post-hoc variants are kept to the primary tasks
    with pytest.raises(SystemExit):
        _main(root, tmp_path, "--task", "add_log_post", "--models", "posthoc")


def test_add_log_post_takes_the_add_log_folds_without_its_own_entry(dataset, tmp_path):
    root = tmp_path / "processed"
    shutil.copytree(dataset[0], root)
    folds = load_folds(root)
    del folds["add_log_post"]
    (root / "instances" / "folds.json").write_text(json.dumps(folds))
    assert task_folds(folds, "add_log_post") == folds["add_log"]
    with pytest.raises(KeyError):
        task_folds(folds, "remove_log_post")
    _run(root, tmp_path / "out", "--task", "add_log_post", "--models", "naive_size,lr")
    side = json.loads(_pred(tmp_path / "out", "lr", task="add_log_post", ext="json").read_text())
    assert side["key_inputs"]["folds"] == folds["add_log"] and side["complete"]


def test_posthoc_outputs_record_the_transform(dataset, tmp_path):
    root, _ = dataset
    _run(root, tmp_path, "--task", "remove_log", "--models", "posthoc,lr", "--folds", "A", "--max-epochs", "1")
    base = json.loads(_pred(tmp_path, "lr", task="remove_log", ext="json").read_text())
    assert "posthoc" not in base["config"] and "n_log1p_columns" not in base["folds"][0]
    for variant, name in train.POSTHOC.items():
        side = json.loads(_pred(tmp_path, variant, task="remove_log", ext="json").read_text())
        assert side["config"]["posthoc"]["tabular_transform"] == "signed_log1p_nonbinary"
        assert side["config"]["posthoc"]["base"] == name and side["config"]["posthoc"]["prespecified"] is False
        assert side["key_inputs"]["config"] == side["config"] and side["feature_set"] == "all"
        assert side["folds"][0]["n_log1p_columns"] > 0
        assert side["run_key"] != base["run_key"]
        if variant != "lr_log1p":
            assert side["max_epochs_override"] == 1 and side["device"] is not None


def test_informational_folds_fields_keep_existing_outputs(dataset, tmp_path):
    root = tmp_path / "processed"
    shutil.copytree(dataset[0], root)
    out = tmp_path / "out"
    _run(root, out, "--task", "remove_log", "--models", "lr,hgb", "--importance")
    paths = [_pred(out, m, task="remove_log", ext=e) for m in ("lr", "hgb") for e in ("csv", "json")]
    paths.append(out / "importance" / "R4" / "remove_log" / "hgb_seed0.json")
    before = [p.read_bytes() for p in paths]
    folds = load_folds(root)
    assert json.loads(before[1])["folds_entry"] == folds["remove_log"]
    # what the dataset rebuild adds to every entry (dataset stage): nothing is recomputed
    for entry in folds.values():
        entry["per_repo"] = {r: {"n_pos": 3, "n_pos_commits": 1, "max_commit_share": 1.0} for r in REPOS}
        entry["few_commit_folds"] = ["C"]
    (root / "instances" / "folds.json").write_text(json.dumps(folds))
    _run(root, out, "--task", "remove_log", "--models", "lr,hgb", "--importance")
    assert [p.read_bytes() for p in paths] == before
    # a field the folds depend on still invalidates them
    folds["remove_log"]["low_support"] = []
    (root / "instances" / "folds.json").write_text(json.dumps(folds))
    assert _main(root, out, "--task", "remove_log", "--models", "lr") == 2
    _run(root, out, "--task", "remove_log", "--models", "lr", "--overwrite")
    side = json.loads(_pred(out, "lr", task="remove_log", ext="json").read_text())
    assert side["folds_entry"] == folds["remove_log"] and side["key_inputs"]["folds"]["low_support"] == []
    assert "per_repo" not in side["key_inputs"]["folds"]


def test_add_log_post_must_keep_the_add_log_instances(dataset, tmp_path):
    root = tmp_path / "processed"
    shutil.copytree(dataset[0], root)
    out = tmp_path / "out"
    ev = build_eval_set("add_log_post", "R4", root)
    ref = build_eval_set("add_log", "R4", root)
    check_paired_view(ev, ref)
    flipped = dict(ev, ids=ev["ids"][::-1], y=ev["y"][::-1], repos=ev["repos"][::-1], commits=ev["commits"][::-1])
    with pytest.raises(ValueError, match="another order"):
        check_paired_view(flipped, ref)
    relabelled = dict(ev, y=1 - ev["y"])
    with pytest.raises(ValueError, match="label"):
        check_paired_view(relabelled, ref)

    # a failure of the post view only (e.g. masking) would shift the validation splits
    extra = ev["ids"][40]
    with open(root / "features" / "add_log_post_failures.jsonl", "a") as f:
        f.write(json.dumps({"instance_id": extra, "reason": "mask_mismatch"}) + "\n")
    with pytest.raises(ValueError, match=r"0 only in add_log_post \[\], 1 only in add_log \["):
        _main(root, out, "--task", "add_log_post", "--models", "lr")
    assert not (out / "predictions").exists()

    # a graph failure of the pre view only: R4 is refused, R1 (no graphs) is still paired
    shutil.copy(dataset[0] / "features" / "add_log_post_failures.jsonl", root / "features")
    idx = pd.read_csv(root / "graphs" / "add_log_index.csv")
    idx.loc[idx["instance_id"] == "add_log:" + extra.split(":", 1)[1], "n_nodes"] = 0
    idx.to_csv(root / "graphs" / "add_log_index.csv", index=False)
    with pytest.raises(ValueError, match=r"1 only in add_log_post \["):
        _main(root, out, "--task", "add_log_post", "--models", "lr")
    _run(root, out, "--setting", "R1", "--task", "add_log_post", "--models", "lr")

    # the folds.json entries of the two views must agree
    folds = load_folds(root)
    folds["add_log_post"] = dict(folds["add_log"], low_support=[])
    (root / "instances" / "folds.json").write_text(json.dumps(folds))
    with pytest.raises(ValueError, match="folds.json"):
        _main(root, out, "--setting", "R1", "--task", "add_log_post", "--models", "lr", "--overwrite")
