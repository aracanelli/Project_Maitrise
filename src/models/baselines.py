"""
Naive and classical baselines, and the decision rule shared by every binary model: the
F1-maximising threshold on validation scores, frozen and applied to the test repository.

Naive scores are computed from raw feature columns (no imputation); missing values count as 0.
"""

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score)


def f1_threshold(y, scores):
    """Threshold t maximising F1 of (score >= t) on (y, scores); the lowest t among ties."""
    y = np.asarray(y)
    scores = np.nan_to_num(np.asarray(scores, dtype=np.float64))
    p, r, t = precision_recall_curve(y, scores)
    p, r = p[:-1], r[:-1]
    denom = p + r
    f1 = np.where(denom > 0, 2 * p * r / np.where(denom > 0, denom, 1), 0.0)
    return float(t[int(np.argmax(f1))])


def binary_metrics(y, scores, y_pred):
    y = np.asarray(y)
    scores = np.nan_to_num(np.asarray(scores, dtype=np.float64))
    out = {"n": int(len(y)), "n_pos": int(y.sum())}
    both = 0 < y.sum() < len(y)
    out["pr_auc"] = float(average_precision_score(y, scores)) if y.sum() else None
    out["roc_auc"] = float(roc_auc_score(y, scores)) if both else None
    out["f1"] = float(f1_score(y, y_pred, zero_division=0))
    out["precision"] = float(precision_score(y, y_pred, zero_division=0))
    out["recall"] = float(recall_score(y, y_pred, zero_division=0))
    return out


def _col(X, columns, name):
    if name not in columns:
        raise KeyError(f"naive baseline needs feature column {name}")
    return np.nan_to_num(X[:, columns.index(name)].astype(np.float64))


def naive_prior_scores(n, seed, fold_index):
    """Stratified random baseline: U(0,1) scores; y_pred = score < training prevalence."""
    rng = np.random.default_rng([seed, fold_index])
    return rng.random(n)


def naive_size_scores(X, columns):
    return _col(X, columns, "m_loc")


def naive_rule_scores(task, X, columns):
    """Hand-written rule per task; 1e-3 * LOC only breaks ties between equal rule values.

    add_log:      catch blocks without a log (same rule for the add_log_post view)
    remove_log:   TRACE/DEBUG statement (s_level_ord 1..2), more so inside a loop
    change_level: level differs from the file's mean / dominant level
    """
    loc = _col(X, columns, "m_loc")
    if task in ("add_log", "add_log_post"):
        return _col(X, columns, "m_n_catch_without_log") + 1e-3 * loc
    if task == "remove_log":
        lvl = _col(X, columns, "s_level_ord")
        low = ((lvl >= 1) & (lvl <= 2)).astype(np.float64)
        return 2 * low + _col(X, columns, "s_in_loop") + 1e-3 * loc
    if task == "change_level":
        diff = np.abs(_col(X, columns, "s_level_minus_file_mean"))
        eq = X[:, columns.index("s_level_eq_file_dominant")].astype(np.float64)
        eq = np.where(np.isnan(eq), 1.0, eq)   # unknown dominant level: no evidence of a mismatch
        return diff + (1 - eq)
    raise ValueError(task)


def make_classifier(name, seed, cfg):
    p = dict(cfg)
    if name == "lr":
        return LogisticRegression(C=p["C"], max_iter=p["max_iter"], class_weight=p.get("class_weight"),
                                  random_state=seed)
    if name == "rf":
        return RandomForestClassifier(n_estimators=p["n_estimators"], min_samples_leaf=p["min_samples_leaf"],
                                      class_weight=p.get("class_weight"), n_jobs=p.get("n_jobs", 1),
                                      random_state=seed)
    if name == "hgb":
        return HistGradientBoostingClassifier(learning_rate=p["learning_rate"], max_iter=p["max_iter"],
                                              max_leaf_nodes=p["max_leaf_nodes"],
                                              l2_regularization=p["l2_regularization"],
                                              early_stopping=p.get("early_stopping", True),
                                              random_state=seed)
    raise ValueError(name)


def fit_classifier(name, model, X_fit, y_fit, X_val=None, y_val=None):
    """HGB early-stops on the grouped validation split (same split as the neural models)."""
    if name == "hgb" and model.early_stopping and X_val is not None:
        model.fit(X_fit, y_fit, X_val=X_val, y_val=y_val)
    else:
        model.fit(X_fit, y_fit)
    if name == "rf":
        # parallel predict_proba sums the trees in thread order (last-bit differences);
        # predicting serially keeps scores bit-reproducible for a given seed
        model.set_params(n_jobs=1)
    return model


def positive_scores(model, X):
    return model.predict_proba(X)[:, list(model.classes_).index(1)]
