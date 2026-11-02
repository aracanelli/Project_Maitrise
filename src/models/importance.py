"""
Permutation importance of the HGB model (seed 0) on each held-out repository.

Drop in average precision when one feature, or all columns of one group (h, f, m, l, s, d,
x) jointly, are permuted across the test rows. Permuting a group with a single row
permutation keeps the within-group correlations, so group drops are not sums of feature
drops. Semantics follow sklearn.inspection.permutation_importance (scoring
"average_precision", n_repeats), extended to column groups.
"""

import numpy as np
from sklearn.metrics import average_precision_score

from src.models import baselines
from src.models.data import GROUPS
from src.models.train import fit_classical

N_REPEATS = 5


def permutation_drops(score_fn, X, y, column_sets, n_repeats=N_REPEATS, seed=0):
    """(base AP, [(mean drop, std drop)] for each list of column indices in column_sets)."""
    X = np.array(X, dtype=np.float64, copy=True)
    base = average_precision_score(y, score_fn(X))
    rng = np.random.RandomState(seed)
    out = []
    for cols in column_sets:
        original = X[:, cols].copy()
        drops = []
        for _ in range(n_repeats):
            perm = rng.permutation(len(y))
            X[:, cols] = original[perm]
            drops.append(base - average_precision_score(y, score_fn(X)))
        X[:, cols] = original
        out.append((float(np.mean(drops)), float(np.std(drops))))
    return base, out


def hgb_importance(ev, folds, cfg, n_repeats=N_REPEATS, seed=0):
    """Per-fold feature and group importance rows for hgb trained with `seed`."""
    feature_rows, group_rows = [], []
    for fold in folds:
        test = fold["test_idx"]
        y = ev["y"][test]
        if y.sum() == 0 or y.sum() == len(y):
            continue
        model, X, cols = fit_classical("hgb", ev, fold, seed, cfg)
        names = [ev["columns"][j] for j in cols]
        groups = [ev["groups"][j] for j in cols]

        def score_fn(Z):
            return baselines.positive_scores(model, Z)

        Xt = X[test]
        _, feats = permutation_drops(score_fn, Xt, y, [[j] for j in range(len(names))], n_repeats,
                                     seed + fold["fold_index"])
        for name, (mean, std) in zip(names, feats):
            feature_rows.append({"fold": fold["test_repo"], "feature": name, "mean_drop": mean, "std": std})

        present = [g for g in GROUPS if g in groups]
        sets = [[j for j, g in enumerate(groups) if g == grp] for grp in present]
        _, grp = permutation_drops(score_fn, Xt, y, sets, n_repeats, seed + fold["fold_index"])
        for name, (mean, std) in zip(present, grp):
            group_rows.append({"fold": fold["test_repo"], "group": name, "mean_drop": mean, "std": std})
    return feature_rows, group_rows
