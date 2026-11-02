"""
Graph and neural tabular models.

- Stage-6 graphs (<task>.npz, <task>_index.csv, <task>_meta.json) are loaded once per task
  into PyG Data objects and reused across folds and seeds.
- Node embedding: concat(type embedding, Linear(standardised x_num), mean of the node's
  token embeddings) -> Linear -> hidden. Tokens share the 128-bucket space of the x_ features.
- R-GCN (Schlichtkrull et al. 2018): stacked RGCNConv layers with basis decomposition,
  residual + LayerNorm + ReLU + dropout.
- Relational GGNN (Li et al. 2016; Allamanis et al. 2018): one shared relational message
  module (RGCNConv, per-relation mean aggregation) applied for `ggnn_steps` steps, each
  followed by a GRUCell update.
- FusedRGCNConv keeps the parameters and maths of torch_geometric's RGCNConv but computes
  the per-relation neighbour means as one sparse product instead of its Python loop over
  relations (used when pyg_lib is absent); tests check outputs and gradients against RGCNConv.
- Determinism: every sum of floats over a variable set of rows (neighbour means, mean
  pooling and their gradients) is a segment sum added in a fixed order (SpMM below);
  token means and embedding gradients are dense products. No float atomic additions
  (scatter-add, the backward of x[index] with repeated indices, cuSPARSE CSR products with
  long rows), so a run is bitwise reproducible on the GPU for a given seed.
"""

import json
import warnings

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.data import Data
from torch_geometric.nn import RGCNConv, global_max_pool

from src.models.data import processed_dir

N_TOKENS = 128

# torch_geometric falls back to torch.scatter_reduce for the max readout (same result)
warnings.filterwarnings("ignore", message=".*can be accelerated via the 'torch-scatter' package")


class MethodGraph(Data):
    def __inc__(self, key, value, *args, **kwargs):
        if key in ("tok_node", "anchor", "target"):
            return self.num_nodes
        if key == "gidx":
            return 0
        return super().__inc__(key, value, *args, **kwargs)


def load_graph_arrays(task, data_dir=None):
    base = processed_dir(data_dir) / "graphs"
    with np.load(base / f"{task}.npz") as z:
        arrays = {k: z[k] for k in z.files}
    meta = {}
    if (base / f"{task}_meta.json").exists():
        with open(base / f"{task}_meta.json", encoding="utf-8") as f:
            meta = json.load(f)
    return arrays, meta


def _vocab_size(meta, names):
    for name in names:
        v = meta.get(name)
        if isinstance(v, (list, dict)):
            return len(v)
    return 0


def check_arrays(a):
    """Contract checks on the npz; raises on any inconsistency."""
    G = len(a["node_ptr"]) - 1
    N = int(a["node_ptr"][-1])
    ok = (len(a["edge_ptr"]) == G + 1 and len(a["anchor_local"]) == G and len(a["target_local"]) == G
          and len(a["node_type"]) == N and a["node_num"].shape[0] == N and len(a["tok_ptr"]) == N + 1
          and int(a["tok_ptr"][-1]) == len(a["tok_ids"])
          and a["edge_index"].shape[1] == int(a["edge_ptr"][-1]) == len(a["edge_type"]))
    if not ok:
        raise ValueError("graph npz arrays have inconsistent lengths")
    n_nodes = np.diff(a["node_ptr"])
    per_edge = np.repeat(n_nodes, np.diff(a["edge_ptr"]))
    ei = a["edge_index"].astype(np.int64)
    if ei.size and ((ei < 0).any() or (ei >= per_edge[None, :]).any()):
        raise ValueError("edge_index has graph-local indices outside their graph")
    if len(a["tok_ids"]) and (a["tok_ids"].min() < 0):
        raise ValueError("negative token id")


def build_graphs(arrays, positions, labels, meta=None):
    """Data objects for the graphs at `positions`; gidx = position in that list.

    Returns (graphs, info) where info holds the vocabulary sizes needed by the model.
    """
    a = arrays
    check_arrays(a)
    meta = meta or {}
    node_ptr, edge_ptr, tok_ptr = a["node_ptr"], a["edge_ptr"], a["tok_ptr"]
    node_type = torch.from_numpy(a["node_type"].astype(np.int64))
    node_num = torch.from_numpy(np.ascontiguousarray(a["node_num"], dtype=np.float32))
    if node_num.dim() == 1:
        node_num = node_num.view(-1, 1)
    tok_ids = torch.from_numpy(a["tok_ids"].astype(np.int64))
    tok_owner = torch.from_numpy(np.repeat(np.arange(len(node_type), dtype=np.int64), np.diff(tok_ptr)))
    edge_index = torch.from_numpy(a["edge_index"].astype(np.int64))
    edge_type = torch.from_numpy(a["edge_type"].astype(np.int64))

    graphs = []
    fixed = 0
    for k, g in enumerate(positions):
        n0, n1 = int(node_ptr[g]), int(node_ptr[g + 1])
        e0, e1 = int(edge_ptr[g]), int(edge_ptr[g + 1])
        t0, t1 = int(tok_ptr[n0]), int(tok_ptr[n1])
        n = n1 - n0
        anchor = int(a["anchor_local"][g])
        target = int(a["target_local"][g])
        if not 0 <= anchor < n:
            anchor = 0
            fixed += 1
        if not 0 <= target < n:
            target = anchor
            fixed += 1
        d = MethodGraph(
            node_type=node_type[n0:n1],
            x_num=node_num[n0:n1],
            tok_ids=tok_ids[t0:t1],
            tok_node=tok_owner[t0:t1] - n0,
            edge_index=edge_index[:, e0:e1],
            edge_type=edge_type[e0:e1],
            anchor=torch.tensor([anchor]),
            target=torch.tensor([target]),
            y=torch.tensor([float(labels[k])]),
            gidx=torch.tensor([k]),
        )
        d.num_nodes = n
        graphs.append(d)

    info = {
        "n_node_types": max(_vocab_size(meta, ["node_types", "node_type_vocab", "node_vocab"]),
                            int(node_type.max()) + 1 if len(node_type) else 1),
        "n_relations": max(_vocab_size(meta, ["edge_types", "edge_type_vocab", "edge_vocab"]),
                           int(edge_type.max()) + 1 if len(edge_type) else 1),
        "n_num": int(node_num.shape[1]),
        "n_tokens": max(N_TOKENS, int(tok_ids.max()) + 1 if len(tok_ids) else 0),
        "anchor_target_fixed": fixed,
    }
    return graphs, info


def node_num_stats(graphs, idx):
    """Mean / std of node numeric features over the graphs at idx (training part of a fold)."""
    x = torch.cat([graphs[i].x_num for i in idx], dim=0)
    mean = x.mean(dim=0)
    std = x.std(dim=0, unbiased=False)
    std[~(std > 0)] = 1.0
    return mean, std


def _segments(keys, n):
    """Stable order of the entries by key and the offsets of the n key segments."""
    order = torch.argsort(keys, stable=True)
    offsets = torch.zeros(n + 1, dtype=torch.long, device=keys.device)
    offsets[1:] = torch.cumsum(torch.bincount(keys, minlength=n), 0)
    return order, offsets


def sparse_operator(rows, cols, vals, n_rows, n_cols):
    """Sparse matrix A (n_rows x n_cols) from COO entries, as two sorted entry lists:
    (column, value, row offsets) for A @ x and (row, value, column offsets) for A^T @ g."""
    by_row, row_off = _segments(rows, n_rows)
    by_col, col_off = _segments(cols, n_cols)
    return (cols[by_row], vals[by_row], row_off), (rows[by_col], vals[by_col], col_off)


def _segment_product(index, vals, offsets, x):
    # out[i] = sum of vals[k] * x[index[k]] over the entries k of segment i
    return torch.segment_reduce(x[index] * vals.unsqueeze(1), "sum", offsets=offsets)


class SpMM(torch.autograd.Function):
    """A @ x for a sparse_operator A, with the backward A^T @ grad.

    Both products gather the rows they need and add each output row with segment_reduce,
    which sums a segment sequentially in a fixed order. cuSPARSE CSR products (rows with
    64 or more non-zeros), scatter-add and the backward of x[index] use atomic additions on
    the GPU, whose order, and so the float result, changes between runs.
    """

    @staticmethod
    def forward(ctx, op, x):
        ctx.op_t = op[1]
        return _segment_product(*op[0], x)

    @staticmethod
    def backward(ctx, grad):
        return None, _segment_product(*ctx.op_t, grad.contiguous())


def relation_operator(edge_index, edge_type, n_nodes, n_relations):
    """Sparse R-GCN mean aggregation: row i * R + r averages the r-neighbours of node i,
    i.e. weight 1 / |N_r(i)| on each incoming edge of type r."""
    rows = edge_index[1] * n_relations + edge_type
    deg = torch.bincount(rows, minlength=n_nodes * n_relations).float()
    return sparse_operator(rows, edge_index[0], 1.0 / deg[rows], n_nodes * n_relations, n_nodes)


def mean_pool_operator(batch, n_graphs):
    n = batch.size(0)
    count = torch.bincount(batch, minlength=n_graphs).float()
    return sparse_operator(batch, torch.arange(n, device=batch.device), 1.0 / count[batch], n_graphs, n)


class FusedRGCNConv(RGCNConv):
    """RGCNConv (aggr="mean") computed without the loop over relations.

    out_i = root^T x_i + bias + sum_r sum_{j in N_r(i)} (1 / |N_r(i)|) W_r^T x_j, with
    W_r = sum_b comp[r, b] V_b. The neighbour means of all relations come out of one sparse
    product as an [N, R * d] matrix, which is multiplied by the stacked [R * d, out] weights.
    `rel` is relation_operator(...) of the batch, shared by all layers / steps.
    """

    def forward(self, x, edge_index, edge_type, rel=None):
        n, r, d = x.size(0), self.num_relations, self.in_channels_l
        if rel is None:
            rel = relation_operator(edge_index, edge_type, n, r)
        agg = SpMM.apply(rel, x)
        w = self.weight
        if self.num_bases is not None:
            w = self.comp @ w.view(self.num_bases, -1)
        out = agg.view(n, r * d) @ w.reshape(r * d, self.out_channels)
        if self.root is not None:
            out = out + x @ self.root
        if self.bias is not None:
            out = out + self.bias
        return out


def tab_mlp(n_in, hidden, layers, dropout):
    mods = []
    d = n_in
    for _ in range(layers):
        mods += [nn.Linear(d, hidden), nn.ReLU(), nn.Dropout(dropout)]
        d = hidden
    return nn.Sequential(*mods)


class NodeEncoder(nn.Module):
    def __init__(self, n_types, n_num, n_tokens, hidden, type_dim, token_dim):
        super().__init__()
        self.type_emb = nn.Embedding(n_types, type_dim)
        self.tok_emb = nn.Embedding(n_tokens, token_dim)
        self.num_lin = nn.Linear(n_num, type_dim) if n_num else None
        in_dim = type_dim + token_dim + (type_dim if n_num else 0)
        self.proj = nn.Linear(in_dim, hidden)
        self.register_buffer("num_mean", torch.zeros(n_num))
        self.register_buffer("num_std", torch.ones(n_num))

    def forward(self, data):
        n = data.num_nodes
        dev = data.node_type.device
        # embedding lookups written as products with one-hot / count matrices (deterministic
        # gradients); same values as type_emb(node_type) and the scatter mean of tok_emb(tok_ids)
        onehot = torch.zeros(n, self.type_emb.num_embeddings, device=dev)
        onehot.scatter_(1, data.node_type.unsqueeze(1), 1.0)
        parts = [onehot @ self.type_emb.weight]
        if self.num_lin is not None:
            parts.append(self.num_lin((data.x_num - self.num_mean) / self.num_std))
        counts = torch.zeros(n, self.tok_emb.num_embeddings, device=dev)
        counts.index_put_((data.tok_node, data.tok_ids), torch.ones(data.tok_ids.size(0), device=dev),
                          accumulate=True)
        parts.append((counts / counts.sum(1, keepdim=True).clamp(min=1)) @ self.tok_emb.weight)
        return F.relu(self.proj(torch.cat(parts, dim=1)))


class RGCNEncoder(nn.Module):
    def __init__(self, hidden, n_relations, num_bases, layers, dropout):
        super().__init__()
        self.convs = nn.ModuleList([FusedRGCNConv(hidden, hidden, n_relations, num_bases=num_bases)
                                    for _ in range(layers)])
        self.norms = nn.ModuleList([nn.LayerNorm(hidden) for _ in range(layers)])
        self.dropout = dropout

    def forward(self, h, edge_index, edge_type, rel=None):
        for conv, norm in zip(self.convs, self.norms):
            out = F.relu(norm(conv(h, edge_index, edge_type, rel)))
            h = h + F.dropout(out, self.dropout, self.training)
        return h


class GGNNEncoder(nn.Module):
    def __init__(self, hidden, n_relations, num_bases, steps):
        super().__init__()
        # the GRU carries the node's own state, so the message has no root term
        self.message = FusedRGCNConv(hidden, hidden, n_relations, num_bases=num_bases, root_weight=False)
        self.gru = nn.GRUCell(hidden, hidden)
        self.steps = steps

    def forward(self, h, edge_index, edge_type, rel=None):
        for _ in range(self.steps):
            h = self.gru(self.message(h, edge_index, edge_type, rel), h)
        return h


class GraphNet(nn.Module):
    """Graph-only model (n_tab = 0) or hybrid graph + tabular model."""

    def __init__(self, encoder, info, gnn_cfg, mlp_layers=2, n_tab=0):
        super().__init__()
        h = gnn_cfg["hidden"]
        drop = gnn_cfg["dropout"]
        self.nodes = NodeEncoder(info["n_node_types"], info["n_num"], info["n_tokens"], h,
                                 gnn_cfg["type_dim"], gnn_cfg["token_dim"])
        if encoder == "rgcn":
            self.encoder = RGCNEncoder(h, info["n_relations"], gnn_cfg["num_bases"], gnn_cfg["layers"], drop)
        elif encoder == "ggnn":
            self.encoder = GGNNEncoder(h, info["n_relations"], gnn_cfg["num_bases"], gnn_cfg["ggnn_steps"])
        else:
            raise ValueError(encoder)
        self.tab = tab_mlp(n_tab, h, mlp_layers, drop) if n_tab else None
        in_dim = 4 * h + (h if n_tab else 0)
        self.head = nn.Sequential(nn.Linear(in_dim, h), nn.ReLU(), nn.Dropout(drop), nn.Linear(h, 1))
        self.tab_table = None
        self.n_relations = info["n_relations"]

    def set_node_stats(self, mean, std):
        self.nodes.num_mean.copy_(mean)
        self.nodes.num_std.copy_(std)

    def set_tab_table(self, table):
        self.tab_table = table

    def forward(self, data):
        h = self.nodes(data)
        rel = relation_operator(data.edge_index, data.edge_type, h.size(0), self.n_relations)
        h = self.encoder(h, data.edge_index, data.edge_type, rel)
        size = data.num_graphs
        pool = mean_pool_operator(data.batch, size)
        parts = [SpMM.apply(pool, h), global_max_pool(h, data.batch, size),
                 h[data.anchor], h[data.target]]
        if self.tab is not None:
            parts.append(self.tab(self.tab_table[data.gidx]))
        return self.head(torch.cat(parts, dim=1)).squeeze(-1)


class TabNet(nn.Module):
    """Tabular MLP used by mlp_full / mlp_hist."""

    def __init__(self, n_tab, hidden, layers, dropout):
        super().__init__()
        self.body = tab_mlp(n_tab, hidden, layers, dropout)
        self.out = nn.Linear(hidden, 1)

    def forward(self, x):
        return self.out(self.body(x)).squeeze(-1)
