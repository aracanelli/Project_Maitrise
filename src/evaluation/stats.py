"""
Uncertainty and significance tests for the evaluation.

- cluster bootstrap: commits are the clusters, resampled with replacement inside each
  repository (stratum), so every resample keeps the number of commits per repository.
  A resample is stored as cluster counts CT (K clusters x B resamples); an instance's
  weight in resample b is the count of its commit. Any subset of instances (one repo, the
  performance-sensitive subset, ...) reuses the same resamples, which keeps paired
  comparisons and the difference-in-differences on identical resamples.
- multi-seed models: in every resample the metric is computed for each seed and the seeds
  are averaged, so the interval is for the seed mean.
- paired bootstrap p-value: two-sided, p = min(1, 2 min(P(d <= 0), P(d >= 0))) with +1 smoothing,
  reported with its Monte-Carlo standard error (binomial error of the tail share).
- Wilcoxon signed-rank over repositories, Holm step-down correction, Cliff's delta,
  Wilson interval for a proportion.
"""

import numpy as np
from scipy import stats as sps


def resample_counts(strata, B, seed=42):
    """Cluster counts (K x B): within each stratum draw as many clusters as it has.

    Stored as uint8 (a cluster drawn more than 255 times in one resample never happens in
    practice; int32 is used if it does), which keeps the bootstrap gathers small.
    """
    strata = np.asarray(strata)
    rng = np.random.default_rng(seed)
    CT = np.zeros((len(strata), B), dtype=np.int32)
    for s in sorted(set(strata.tolist())):
        members = np.flatnonzero(strata == s)
        k = len(members)
        draws = rng.integers(0, k, size=(B, k))
        flat = (draws + np.arange(B)[:, None] * k).ravel()
        counts = np.bincount(flat, minlength=B * k).reshape(B, k)
        CT[members] = counts.T
    return CT.astype(np.uint8) if CT.size == 0 or CT.max() < 256 else CT


def prepare_ranking(y, score):
    """Precompute, for one score vector, everything AP needs except the weights.

    Positive-containing tied groups are the only thresholds where recall moves, so AP only
    needs the cumulative weight at those groups (segment sums instead of a full cumsum).
    """
    y = np.asarray(y).astype(bool)
    score = np.asarray(score, dtype=np.float64)
    order = np.argsort(-score, kind="mergesort")
    s = score[order]
    ys = y[order]
    new_group = np.r_[True, s[1:] != s[:-1]] if len(s) else np.array([], dtype=bool)
    gid = np.cumsum(new_group) - 1
    pos_sorted = np.flatnonzero(ys)
    if len(pos_sorted) == 0:
        return {"order": order, "n_pos": 0}
    pos_groups, pos_group_start = np.unique(gid[pos_sorted], return_index=True)
    # last sorted position of every positive-containing group
    group_end = np.r_[np.flatnonzero(new_group)[1:] - 1, len(s) - 1]
    seg_end = group_end[pos_groups]
    seg_start = np.r_[0, seg_end[:-1] + 1]
    return {
        "order": order,
        "n_pos": len(pos_sorted),
        "prefix": order[:seg_end[-1] + 1],
        "seg_start": seg_start,
        "pos_idx": order[pos_sorted],
        "pos_start": pos_group_start,
    }


def boot_average_precision(CT, rows, prep):
    """AP for every resample (length B). rows: CT row (cluster) of each instance."""
    B = CT.shape[1]
    if prep["n_pos"] == 0:
        return np.full(B, np.nan)
    tot = np.add.reduceat(CT[rows[prep["prefix"]]], prep["seg_start"], axis=0, dtype=np.int32)
    tp = np.add.reduceat(CT[rows[prep["pos_idx"]]], prep["pos_start"], axis=0, dtype=np.int32)
    TP = np.cumsum(tp, axis=0, dtype=np.float64)
    TOT = np.cumsum(tot, axis=0, dtype=np.float64)
    P = TP[-1].copy()
    # precision in place; where TOT == 0 also TP == 0, so the term is 0
    np.divide(TP, TOT, out=TP, where=TOT > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ap = (tp * TP).sum(axis=0) / P
    return np.where(P > 0, ap, np.nan)


def boot_confusion(CT, rows, y, y_pred):
    """(tp, fp, fn, tn) per resample, from per-cluster confusion counts."""
    y = np.asarray(y).astype(bool)
    yp = np.asarray(y_pred).astype(bool)
    K = CT.shape[0]
    cells = [y & yp, ~y & yp, y & ~yp, ~y & ~yp]
    counts = np.stack([np.bincount(rows[c], minlength=K) for c in cells], axis=1).astype(np.float32)
    C = (counts.T @ CT).T.astype(np.float64)
    return C[:, 0], C[:, 1], C[:, 2], C[:, 3]


def boot_prevalence(CT, rows, y):
    """Share of positives in every resample (length B)."""
    y = np.asarray(y).astype(bool)
    K = CT.shape[0]
    counts = np.stack([np.bincount(rows[y], minlength=K), np.bincount(rows, minlength=K)]).astype(np.float32)
    P, n = (counts @ CT).astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(n > 0, P / n, np.nan)


def boot_roc_auc(CT, rows, y, score, chunk=500):
    """ROC-AUC (ties count 1/2) for every resample, computed in blocks of resamples."""
    y = np.asarray(y).astype(bool)
    score = np.asarray(score, dtype=np.float64)
    B = CT.shape[1]
    if not y.any() or y.all():
        return np.full(B, np.nan)
    order = np.argsort(score, kind="mergesort")
    s = score[order]
    gid = np.cumsum(np.r_[True, s[1:] != s[:-1]]) - 1
    G = int(gid[-1]) + 1
    parts = []
    for cls in (True, False):
        sel = y[order] == cls
        g = gid[sel]
        groups, start = np.unique(g, return_index=True)
        parts.append((rows[order[sel]], groups, start))
    out = np.empty(B)
    for b0 in range(0, B, chunk):
        C = CT[:, b0:b0 + chunk]
        w = []
        for r, groups, start in parts:
            full = np.zeros((G, C.shape[1]))
            full[groups] = np.add.reduceat(C[r], start, axis=0, dtype=np.int32)
            w.append(full)
        wp, wn = w
        below = np.cumsum(wn, axis=0) - wn
        num = (wp * (below + 0.5 * wn)).sum(axis=0)
        P, N = wp.sum(axis=0), wn.sum(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[b0:b0 + chunk] = np.where((P > 0) & (N > 0), num / (P * N), np.nan)
    return out


def boot_f1(CT, rows, y, y_pred):
    tp, fp, fn, tn = boot_confusion(CT, rows, y, y_pred)
    P = tp + fn
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(P > 0, 2 * tp / (2 * tp + fp + fn), np.nan)


def boot_seed_metrics(CT, rows, y, scores, preds):
    """{'pr_auc': (B x S), 'f1': (B x S)} for S seeds on the same instances."""
    B = CT.shape[1]
    S = len(scores)
    out = {"pr_auc": np.full((B, S), np.nan), "f1": np.full((B, S), np.nan)}
    for j in range(S):
        out["pr_auc"][:, j] = boot_average_precision(CT, rows, prepare_ranking(y, scores[j]))
        out["f1"][:, j] = boot_f1(CT, rows, y, preds[j])
    return out


def seed_mean(boot):
    """Average over seeds inside each resample (B x S -> B)."""
    boot = np.asarray(boot, dtype=np.float64)
    if boot.ndim == 1:
        return boot
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(boot).any(axis=1)
        out = np.full(boot.shape[0], np.nan)
        out[ok] = np.nanmean(boot[ok], axis=1)
    return out


def percentile_ci(values, ci=0.95):
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.nan, np.nan
    a = (1 - ci) / 2
    return float(np.quantile(v, a)), float(np.quantile(v, 1 - a))


def bootstrap_p(deltas):
    """Two-sided bootstrap p-value of H0: delta = 0, with +1 smoothing."""
    d = np.asarray(deltas, dtype=np.float64)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return np.nan
    le = (1 + np.sum(d <= 0)) / (len(d) + 1)
    ge = (1 + np.sum(d >= 0)) / (len(d) + 1)
    return float(min(1.0, 2 * min(le, ge)))


def bootstrap_p_mcse(deltas):
    """Monte-Carlo standard error of bootstrap_p: 2 sqrt(q (1 - q) / B) for the smaller tail share q,
    smoothed like the p-value, so a p at its floor 2/(B+1) does not get a zero error."""
    d = np.asarray(deltas, dtype=np.float64)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return np.nan
    q = min((1 + np.sum(d <= 0)) / (len(d) + 1), (1 + np.sum(d >= 0)) / (len(d) + 1))
    q = min(q, 0.5)
    return float(min(1.0, 2 * np.sqrt(q * (1 - q) / len(d))))


def delta_test(point_delta, boot_deltas, ci=0.95):
    lo, hi = percentile_ci(boot_deltas, ci)
    n_ok = int(np.isfinite(np.asarray(boot_deltas, dtype=np.float64)).sum())
    return {"delta": float(point_delta), "ci_lo": lo, "ci_hi": hi,
            "p": bootstrap_p(boot_deltas), "p_mcse": bootstrap_p_mcse(boot_deltas), "b_used": n_ok}


def paired_test(boot_a, boot_b, point_a, point_b, ci=0.95):
    """Paired bootstrap of mean_seed(A) - mean_seed(B) on identical resamples."""
    point = np.nanmean(point_a) - np.nanmean(point_b)
    return delta_test(point, seed_mean(boot_a) - seed_mean(boot_b), ci)


def did_test(boots, points, ci=0.95):
    """Difference-in-differences (A - B on subset) - (A - B on complement).

    boots/points: dicts with keys a_sub, b_sub, a_comp, b_comp.
    """
    point = ((np.nanmean(points["a_sub"]) - np.nanmean(points["b_sub"]))
             - (np.nanmean(points["a_comp"]) - np.nanmean(points["b_comp"])))
    d = ((seed_mean(boots["a_sub"]) - seed_mean(boots["b_sub"]))
         - (seed_mean(boots["a_comp"]) - seed_mean(boots["b_comp"])))
    return delta_test(point, d, ci)


def wilcoxon_paired(a, b):
    """Two-sided Wilcoxon signed-rank test over paired values (e.g. per-repository metrics)."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = int(len(a))
    out = {"n": n, "stat": np.nan, "p": np.nan, "min_p": 2.0 / 2 ** n if n else np.nan}
    if n == 0:
        return out
    if np.all(a - b == 0):
        out["p"] = 1.0
        return out
    try:
        res = sps.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
        out["stat"] = float(res.statistic)
        out["p"] = float(res.pvalue)
    except ValueError:
        pass
    return out


def holm(pvals):
    """Holm step-down adjusted p-values; NaNs are left out of the family and stay NaN."""
    p = np.asarray(pvals, dtype=np.float64)
    out = np.full(len(p), np.nan)
    idx = np.flatnonzero(np.isfinite(p))
    m = len(idx)
    if m == 0:
        return out
    order = idx[np.argsort(p[idx], kind="mergesort")]
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        out[i] = running
    return out


def cliffs_delta(x, y):
    """P(X > Y) - P(X < Y) over all pairs of finite values."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if len(x) == 0 or len(y) == 0:
        return np.nan
    return float(np.sign(x[:, None] - y[None, :]).mean())


def wilson_ci(k, n, ci=0.95):
    """Wilson score interval of a proportion k/n."""
    if not n:
        return np.nan, np.nan
    z = sps.norm.ppf(1 - (1 - ci) / 2)
    ph = k / n
    centre = (ph + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def cliffs_magnitude(d):
    """Romano et al. (2006) thresholds."""
    if d is None or not np.isfinite(d):
        return ""
    d = abs(d)
    if d < 0.147:
        return "negligible"
    if d < 0.33:
        return "small"
    if d < 0.474:
        return "medium"
    return "large"
