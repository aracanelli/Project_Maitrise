"""
Packed storage of the graphs of one task (stage 6 output).

All graphs of a task go into one .npz with CSR-style pointers, so the model stage can
load everything at once and slice graph g without per-graph files:

    node_ptr  int64 [G+1]   edge_ptr int64 [G+1]   tok_ptr int64 [N+1]
    node_type int16 [N]     node_num float32 [N, F]  tok_ids int16 [T]
    edge_index int32 [2, E] (graph-local)   edge_type int8 [E]
    anchor_local int32 [G]  target_local int32 [G]

plus <task>_index.csv (graph_pos, instance_id, n_nodes, n_edges, truncated) and
<task>_meta.json (vocabularies, feature names, build stats).
"""

import csv
import json
from pathlib import Path

import numpy as np

from src.common.config import DATA

GRAPH_DIR = DATA / "processed" / "graphs"
INDEX_COLUMNS = ["graph_pos", "instance_id", "n_nodes", "n_edges", "truncated"]


def pack_graphs(graphs, n_features):
    """Concatenate per-graph dicts from builder.build_graph into the npz arrays."""
    node_ptr = [0]
    edge_ptr = [0]
    tok_ptr = [0]
    node_type, node_num, tok_ids, edge_index, edge_type = [], [], [], [], []
    anchors, targets = [], []
    for g in graphs:
        n = len(g["node_type"])
        node_type.append(g["node_type"])
        node_num.append(g["node_num"])
        edge_index.append(g["edge_index"])
        edge_type.append(g["edge_type"])
        tok_ids.append(g["tok_ids"])
        tok_ptr.extend((g["tok_ptr"][1:] + tok_ptr[-1]).tolist())
        node_ptr.append(node_ptr[-1] + n)
        edge_ptr.append(edge_ptr[-1] + g["edge_index"].shape[1])
        anchors.append(g["anchor"])
        targets.append(g["target"])

    if not graphs:
        node_type, node_num = [np.zeros(0)], [np.zeros((0, n_features))]
        tok_ids, edge_index, edge_type = [np.zeros(0)], [np.zeros((2, 0))], [np.zeros(0)]

    return {
        "node_ptr": np.array(node_ptr, dtype=np.int64),
        "edge_ptr": np.array(edge_ptr, dtype=np.int64),
        "tok_ptr": np.array(tok_ptr, dtype=np.int64),
        "node_type": np.concatenate(node_type).astype(np.int16),
        "node_num": np.concatenate(node_num, axis=0).astype(np.float32),
        "tok_ids": np.concatenate(tok_ids).astype(np.int16),
        "edge_index": np.concatenate(edge_index, axis=1).astype(np.int32),
        "edge_type": np.concatenate(edge_type).astype(np.int8),
        "anchor_local": np.array(anchors, dtype=np.int32),
        "target_local": np.array(targets, dtype=np.int32),
    }


def unpack_graph(arrays, pos):
    """Graph `pos` of a packed store, in the same dict form build_graph returns."""
    n0, n1 = int(arrays["node_ptr"][pos]), int(arrays["node_ptr"][pos + 1])
    e0, e1 = int(arrays["edge_ptr"][pos]), int(arrays["edge_ptr"][pos + 1])
    tp = arrays["tok_ptr"][n0:n1 + 1]
    return {
        "node_type": arrays["node_type"][n0:n1],
        "node_num": arrays["node_num"][n0:n1],
        "tok_ptr": tp - tp[0],
        "tok_ids": arrays["tok_ids"][tp[0]:tp[-1]],
        "edge_index": arrays["edge_index"][:, e0:e1],
        "edge_type": arrays["edge_type"][e0:e1],
        "anchor": int(arrays["anchor_local"][pos]),
        "target": int(arrays["target_local"][pos]),
    }


def paths(task, out_dir=None):
    out = Path(out_dir) if out_dir is not None else GRAPH_DIR
    return {
        "npz": out / f"{task}.npz",
        "index": out / f"{task}_index.csv",
        "meta": out / f"{task}_meta.json",
        "failures": out / f"{task}_failures.jsonl",
    }


def save_graphs(task, graphs, instance_ids, meta, n_features, out_dir=None):
    p = paths(task, out_dir)
    p["npz"].parent.mkdir(parents=True, exist_ok=True)
    arrays = pack_graphs(graphs, n_features)
    np.savez_compressed(p["npz"], **arrays)
    with open(p["index"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(INDEX_COLUMNS)
        for pos, (iid, g) in enumerate(zip(instance_ids, graphs)):
            w.writerow([pos, iid, len(g["node_type"]), g["edge_index"].shape[1], g["truncated"]])
    with open(p["meta"], "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return p


def load_graphs(task, out_dir=None):
    """(arrays, index rows, meta) for a task; index rows are dicts with int fields converted."""
    p = paths(task, out_dir)
    with np.load(p["npz"]) as z:
        arrays = {k: z[k] for k in z.files}
    index = []
    with open(p["index"], newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            index.append({
                "graph_pos": int(row["graph_pos"]),
                "instance_id": row["instance_id"],
                "n_nodes": int(row["n_nodes"]),
                "n_edges": int(row["n_edges"]),
                "truncated": int(row["truncated"]),
            })
    with open(p["meta"], encoding="utf-8") as f:
        meta = json.load(f)
    return arrays, index, meta
