"""
Binary and multiclass metrics.

Everything is written for a weight matrix W (B x n): row b gives how many times each
instance is present in bootstrap resample b. The point estimate is the same code with a
single row of ones, so the bootstrap and the reported value can never disagree on how a
metric is computed (ties, empty classes, zero division).

Conventions (NaN-safe):
- no positive instance: recall, F1, PR-AUC, ROC-AUC, MCC, balanced accuracy are NaN
- no negative instance: ROC-AUC, MCC, balanced accuracy are NaN
- no predicted positive while positives exist: precision = 0 (sklearn zero_division=0)
- MCC with an empty predicted class: 0 (sklearn convention)

average_precision follows sklearn's non-interpolated definition
AP = sum_k (R_k - R_{k-1}) P_k over distinct score thresholds (tied scores form one step).
"""

import numpy as np

BINARY_METRICS = ["pr_auc", "f1", "precision", "recall", "roc_auc", "mcc",
                  "balanced_accuracy", "accuracy"]


def sort_inputs(score):
    """Descending order of the scores and the last position of each distinct value."""
    score = np.asarray(score, dtype=np.float64)
    order = np.argsort(-score, kind="mergesort")
    s = score[order]
    ends = np.r_[np.flatnonzero(np.diff(s)), len(s) - 1] if len(s) else np.array([], dtype=int)
    return order, ends


def _ranking_counts(W, y, order, ends):
    """Cumulative weighted tp and fp at every distinct threshold, each (B x T)."""
    Ws = W[:, order]
    ys = y[order].astype(Ws.dtype)
    tp = np.cumsum(Ws * ys, axis=1)[:, ends].astype(np.float64)
    tot = np.cumsum(Ws, axis=1)[:, ends].astype(np.float64)
    return tp, tot - tp


def batch_ranking(W, y, score, order=None, ends=None):
    """(pr_auc, roc_auc) arrays of length B for every row of W."""
    W = np.atleast_2d(W)
    y = np.asarray(y)
    if order is None:
        order, ends = sort_inputs(score)
    if len(order) == 0:
        nan = np.full(W.shape[0], np.nan)
        return nan, nan.copy()
    tp, fp = _ranking_counts(W, y, order, ends)
    P = tp[:, -1]
    N = fp[:, -1]
    ps = tp + fp
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(ps > 0, tp / np.where(ps > 0, ps, 1), 0.0)
        dtp = np.diff(tp, axis=1, prepend=0.0)
        ap = (dtp * precision).sum(axis=1) / P
        dfp = np.diff(fp, axis=1, prepend=0.0)
        tp_prev = np.concatenate([np.zeros((tp.shape[0], 1)), tp[:, :-1]], axis=1)
        auc = (dfp * (tp + tp_prev) / 2.0).sum(axis=1) / (P * N)
    ap = np.where(P > 0, ap, np.nan)
    auc = np.where((P > 0) & (N > 0), auc, np.nan)
    return ap, auc


def batch_confusion(W, y, y_pred):
    """Weighted (tp, fp, fn, tn), each of length B."""
    W = np.atleast_2d(W)
    y = np.asarray(y).astype(bool)
    yp = np.asarray(y_pred).astype(bool)
    M = np.stack([y & yp, ~y & yp, y & ~yp, ~y & ~yp], axis=1).astype(W.dtype)
    C = (W @ M).astype(np.float64)
    return C[:, 0], C[:, 1], C[:, 2], C[:, 3]


def confusion_metrics(tp, fp, fn, tn):
    tp, fp, fn, tn = (np.asarray(a, dtype=np.float64) for a in (tp, fp, fn, tn))
    P = tp + fn
    N = fp + tn
    n = P + N
    with np.errstate(divide="ignore", invalid="ignore"):
        pp = tp + fp
        precision = np.where(pp > 0, tp / np.where(pp > 0, pp, 1), np.where(P > 0, 0.0, np.nan))
        recall = np.where(P > 0, tp / np.where(P > 0, P, 1), np.nan)
        f1 = np.where(P > 0, 2 * tp / (2 * tp + fp + fn), np.nan)
        tnr = np.where(N > 0, tn / np.where(N > 0, N, 1), np.nan)
        bacc = np.where((P > 0) & (N > 0), (recall + tnr) / 2, np.nan)
        denom = np.sqrt(pp * P * N * (tn + fn))
        mcc = np.where(denom > 0, (tp * tn - fp * fn) / np.where(denom > 0, denom, 1), 0.0)
        mcc = np.where((P > 0) & (N > 0), mcc, np.nan)
        acc = np.where(n > 0, (tp + tn) / np.where(n > 0, n, 1), np.nan)
    return {"f1": f1, "precision": precision, "recall": recall, "mcc": mcc,
            "balanced_accuracy": bacc, "accuracy": acc}


def batch_metrics(W, y, score, y_pred, order=None, ends=None, ranking=True):
    """All binary metrics for every row of W, as a dict of arrays of length B."""
    W = np.atleast_2d(W)
    out = confusion_metrics(*batch_confusion(W, y, y_pred))
    if ranking:
        out["pr_auc"], out["roc_auc"] = batch_ranking(W, y, score, order, ends)
    return out


def binary_metrics(y_true, score, y_pred):
    """Point metrics of one prediction vector, plus n, n_pos and prevalence."""
    y = np.asarray(y_true).astype(np.int8)
    W = np.ones((1, len(y)), dtype=np.float64)
    m = batch_metrics(W, y, np.asarray(score, dtype=np.float64), y_pred)
    out = {k: float(m[k][0]) for k in BINARY_METRICS}
    out["n"] = int(len(y))
    out["n_pos"] = int(y.sum())
    out["prevalence"] = float(y.mean()) if len(y) else float("nan")
    return out


def average_precision(y_true, score):
    y = np.asarray(y_true).astype(np.int8)
    ap, _ = batch_ranking(np.ones((1, len(y))), y, np.asarray(score, dtype=np.float64))
    return float(ap[0])


def roc_auc(y_true, score):
    y = np.asarray(y_true).astype(np.int8)
    _, auc = batch_ranking(np.ones((1, len(y))), y, np.asarray(score, dtype=np.float64))
    return float(auc[0])


def pr_curve(y_true, score):
    """(precision, recall) at every distinct threshold, highest threshold first, (1, 0) prepended."""
    y = np.asarray(y_true).astype(np.int8)
    order, ends = sort_inputs(score)
    tp, fp = _ranking_counts(np.ones((1, len(y))), y, order, ends)
    tp, fp = tp[0], fp[0]
    P = tp[-1] if len(tp) else 0
    precision = np.where(tp + fp > 0, tp / np.maximum(tp + fp, 1), 1.0)
    recall = tp / P if P > 0 else np.zeros_like(tp)
    return np.r_[1.0, precision], np.r_[0.0, recall]


def multiclass_metrics(y_true, y_pred, scores=None, classes=None):
    """Macro F1/precision/recall, balanced accuracy, MCC, per-class F1 and macro one-vs-rest
    PR-AUC over the classes present in y_true.

    Balanced accuracy is the macro recall over the present classes; MCC is the multiclass
    (Gorodkin) form used by sklearn. Accuracy is kept but is not a headline metric.
    scores: dict class -> score array (optional).
    """
    y_true = np.asarray(y_true).astype(str)
    y_pred = np.asarray(y_pred).astype(str)
    if classes is None:
        classes = sorted(set(y_true))
    present = [c for c in classes if (y_true == c).any()]
    out = {"n": int(len(y_true)), "accuracy": float((y_true == y_pred).mean()) if len(y_true) else np.nan}
    f1s, precs, recs, aps = [], [], [], []
    for c in classes:
        yt = (y_true == c).astype(np.int8)
        yp = (y_pred == c).astype(np.int8)
        tp = float((yt & yp).sum())
        fp = float(((1 - yt) & yp).sum())
        fn = float((yt & (1 - yp)).sum())
        f1 = 2 * tp / (2 * tp + fp + fn) if yt.sum() > 0 else np.nan
        out[f"f1_{c}"] = f1
        out[f"n_{c}"] = int(yt.sum())
        if c in present:
            f1s.append(f1)
            precs.append(tp / (tp + fp) if tp + fp > 0 else 0.0)
            recs.append(tp / (tp + fn))
        if scores is not None and c in scores and c in present:
            ap = average_precision(yt, scores[c])
            out[f"pr_auc_{c}"] = ap
            aps.append(ap)
    out["macro_f1"] = float(np.mean(f1s)) if f1s else np.nan
    out["macro_precision"] = float(np.mean(precs)) if precs else np.nan
    out["macro_recall"] = float(np.mean(recs)) if recs else np.nan
    out["balanced_accuracy"] = out["macro_recall"]
    out["mcc"] = multiclass_mcc(y_true, y_pred, classes)
    out["macro_pr_auc"] = float(np.mean(aps)) if aps else np.nan
    return out


def multiclass_mcc(y_true, y_pred, classes):
    labels = list(classes) + sorted(set(y_true) | set(y_pred) - set(classes))
    idx = {c: i for i, c in enumerate(labels)}
    C = np.zeros((len(labels), len(labels)))
    for a, b in zip(y_true, y_pred):
        C[idx[a], idx[b]] += 1
    t_k = C.sum(axis=1)
    p_k = C.sum(axis=0)
    c = np.trace(C)
    s = C.sum()
    denom = np.sqrt((s ** 2 - (p_k ** 2).sum()) * (s ** 2 - (t_k ** 2).sum()))
    return float((c * s - (t_k * p_k).sum()) / denom) if denom > 0 else 0.0
