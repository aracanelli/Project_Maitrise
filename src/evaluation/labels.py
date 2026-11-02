"""
Display labels for tables and figures, in English and French (the thesis is written in French).

Event labels (ADD_LOG, REMOVE_LOG, CHANGE_LEVEL), model ids and level names are identifiers
and are never translated; only their display names are.
"""

MODEL_ORDER = ["naive_prior", "naive_size", "naive_rule", "lr", "rf", "hgb",
               "mlp_hist", "mlp_full", "gnn_rgcn", "gnn_ggnn", "hybrid_ggnn_nohist", "hybrid_ggnn"]

TASK_ORDER = ["add_log", "remove_log", "change_level"]

# sensitivity analysis only: never part of the primary tables, figures or Holm families
SENSITIVITY_TASKS = ["add_log_post"]
POSTHOC_BASE = {"lr_log1p": "lr", "mlp_full_log1p": "mlp_full", "hybrid_ggnn_log1p": "hybrid_ggnn"}
POSTHOC_MODELS = list(POSTHOC_BASE)

FEATURE_GROUPS = {"h": "history", "f": "file", "m": "method", "l": "logging context", "s": "statement",
                  "d": "domain", "x": "lexical"}

SUBSYSTEM_MARKERS = ["d_input", "d_network", "d_physics", "d_collision", "d_animation", "d_resource"]

LEVELS = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]

EVENT_LABELS = ["ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"]

TEXT = {
    "en": {
        "precision": "Precision",
        "recall": "Recall",
        "f1": "F1",
        "pr_auc": "PR-AUC",
        "roc_auc": "ROC-AUC",
        "mcc": "MCC",
        "balanced_accuracy": "Balanced accuracy",
        "accuracy": "Accuracy",
        "prevalence": "Prevalence",
        "model": "Model",
        "task": "Task",
        "repo": "Repository",
        "engine": "Engine",
        "size": "Size",
        "ecosystem": "Logging ecosystem",
        "subset": "Performance-sensitive subset",
        "complement": "Complement",
        "full_test": "Full test set",
        "context": "Context category",
        "variant": "Ablation variant",
        "level_before": "Level before",
        "level_after": "Level after",
        "events": "Events",
        "statements": "Formal logging statements",
        "share": "Share",
        "core_events": "Core events",
        "delta_vs_hgb": "Difference (hybrid GGNN - HGB)",
        "delta": "Difference",
        "did": "Difference-in-differences",
        "pr_curves": "precision-recall curves (pooled test folds, seed 0)",
        "prauc_bars": "PR-AUC by model (pooled, 95% CI)",
        "heatmap": "PR-AUC per test repository (mean over seeds)",
        "ablation": "Ablation: PR-AUC on the full test set and on the performance-sensitive subset",
        "forest": "RQ4: hybrid GGNN - HGB, subset vs complement (95% CI)",
        "levels_title": "Formal logging level distribution per repository (snapshot)",
        "core_title": "Core logging events per repository",
        "transition_title": "CHANGE_LEVEL transitions (core events)",
        "low_support": "low support",
        "hollow_low_support": "hollow marker: < 30 positives (low support); F1 there is exploratory",
        "partial": "partial: evaluated on fewer instances",
        "chance": "prevalence",
        "prev_short": "prev.",
        "unknown_level": "unknown level",
        "lift": "Lift (PR-AUC / prevalence)",
        "ctx_title": "PR-AUC per context category (pooled, 95% CI; black tick = prevalence)",
        "per_year_title": "Core logging events per year (all repositories)",
        "year": "Year",
        "setting_line": "setting {s}: {r} negatives per positive per repository",
    },
    "fr": {
        "precision": "Précision",
        "recall": "Rappel",
        "f1": "F1",
        "pr_auc": "PR-AUC",
        "roc_auc": "ROC-AUC",
        "mcc": "MCC",
        "balanced_accuracy": "Exactitude équilibrée",
        "accuracy": "Exactitude",
        "prevalence": "Prévalence",
        "model": "Modèle",
        "task": "Tâche",
        "repo": "Référentiel",
        "engine": "Moteur",
        "size": "Taille",
        "ecosystem": "Écosystème de journalisation",
        "subset": "Sous-ensemble sensible aux performances",
        "complement": "Complément",
        "full_test": "Ensemble de test complet",
        "context": "Catégorie de contexte",
        "variant": "Variante d'ablation",
        "level_before": "Niveau avant",
        "level_after": "Niveau après",
        "events": "Événements",
        "statements": "Instructions de journalisation formelles",
        "share": "Proportion",
        "core_events": "Événements du noyau",
        "delta_vs_hgb": "Différence (GGNN hybride - HGB)",
        "delta": "Différence",
        "did": "Différence des différences",
        "pr_curves": "courbes précision-rappel (plis de test agrégés, graine 0)",
        "prauc_bars": "PR-AUC par modèle (agrégé, IC à 95 %)",
        "heatmap": "PR-AUC par référentiel de test (moyenne sur les graines)",
        "ablation": "Ablation : PR-AUC sur l'ensemble de test complet et sur le sous-ensemble sensible aux performances",
        "forest": "QR4 : GGNN hybride - HGB, sous-ensemble et complément (IC à 95 %)",
        "levels_title": "Distribution des niveaux de journalisation formelle par référentiel (instantané)",
        "core_title": "Événements de journalisation du noyau par référentiel",
        "transition_title": "Transitions CHANGE_LEVEL (événements du noyau)",
        "low_support": "faible effectif",
        "hollow_low_support": "marqueur creux : moins de 30 positifs (faible effectif) ; le F1 y est exploratoire",
        "partial": "partiel : évalué sur moins d'instances",
        "chance": "prévalence",
        "prev_short": "prév.",
        "unknown_level": "niveau inconnu",
        "lift": "Gain (PR-AUC / prévalence)",
        "ctx_title": "PR-AUC par catégorie de contexte (agrégé, IC à 95 % ; trait noir = prévalence)",
        "per_year_title": "Événements de journalisation du noyau par année (tous les référentiels)",
        "year": "Année",
        "setting_line": "réglage {s} : {r} négatifs par positif et par référentiel",
    },
}

MODEL_NAMES = {
    "en": {
        "naive_prior": "Naive: prior rate",
        "naive_size": "Naive: method size",
        "naive_rule": "Naive: task rule",
        "lr": "Logistic regression",
        "rf": "Random forest",
        "hgb": "Gradient boosting (HGB)",
        "mlp_full": "MLP (all tabular)",
        "mlp_hist": "MLP (history only)",
        "gnn_rgcn": "R-GCN (graph only)",
        "gnn_ggnn": "GGNN (graph only)",
        "hybrid_ggnn": "Hybrid GGNN + tabular",
        "hybrid_ggnn_nohist": "Hybrid GGNN, no history",
        "hgb_multiclass": "HGB (multiclass)",
        "lr_multiclass": "Logistic regression (multiclass)",
        "lr_log1p": "Logistic regression, log1p (post-hoc)",
        "mlp_full_log1p": "MLP (all tabular), log1p (post-hoc)",
        "hybrid_ggnn_log1p": "Hybrid GGNN + tabular, log1p (post-hoc)",
    },
    "fr": {
        "naive_prior": "Naïf : taux a priori",
        "naive_size": "Naïf : taille de la méthode",
        "naive_rule": "Naïf : règle de la tâche",
        "lr": "Régression logistique",
        "rf": "Forêt aléatoire",
        "hgb": "Boosting de gradient (HGB)",
        "mlp_full": "MLP (tabulaire complet)",
        "mlp_hist": "MLP (historique seul)",
        "gnn_rgcn": "R-GCN (graphe seul)",
        "gnn_ggnn": "GGNN (graphe seul)",
        "hybrid_ggnn": "GGNN hybride + tabulaire",
        "hybrid_ggnn_nohist": "GGNN hybride, sans historique",
        "hgb_multiclass": "HGB (multiclasse)",
        "lr_multiclass": "Régression logistique (multiclasse)",
        "lr_log1p": "Régression logistique, log1p (post hoc)",
        "mlp_full_log1p": "MLP (tabulaire complet), log1p (post hoc)",
        "hybrid_ggnn_log1p": "GGNN hybride + tabulaire, log1p (post hoc)",
    },
}

VARIANT_NAMES = {
    "en": {"full": "Full", "no_history": "No history", "no_graph": "No graph",
           "history_only": "History only", "graph_only": "Graph only"},
    "fr": {"full": "Complet", "no_history": "Sans historique", "no_graph": "Sans graphe",
           "history_only": "Historique seul", "graph_only": "Graphe seul"},
}

CONTEXT_NAMES = {
    "en": {"frame_update": "Frame update", "loop": "Loop", "subsystem": "Subsystem", "general": "General"},
    "fr": {"frame_update": "Mise à jour de trame", "loop": "Boucle", "subsystem": "Sous-système",
           "general": "Général"},
}


PART_NAMES = {
    "en": {"subset": "Subset", "complement": "Complement"},
    "fr": {"subset": "Sous-ensemble", "complement": "Complément"},
}

MARKER_NAMES = {
    "en": {"input": "Input", "network": "Network", "physics": "Physics", "collision": "Collision",
           "animation": "Animation", "resource": "Resource loading"},
    "fr": {"input": "Entrée", "network": "Réseau", "physics": "Physique", "collision": "Collision",
           "animation": "Animation", "resource": "Chargement de ressources"},
}


def t(key, lang="en"):
    return TEXT.get(lang, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def model_name(model_id, lang="en"):
    return MODEL_NAMES.get(lang, MODEL_NAMES["en"]).get(model_id, model_id)


def variant_name(variant, lang="en"):
    return VARIANT_NAMES.get(lang, VARIANT_NAMES["en"]).get(variant, variant)


def context_name(cat, lang="en"):
    return CONTEXT_NAMES.get(lang, CONTEXT_NAMES["en"]).get(cat, cat)


def task_name(task, lang="en"):
    # event labels stay as identifiers in both languages
    if task == "add_log_post":
        return "ADD_LOG (commit-time view)" if lang == "en" else "ADD_LOG (vue au moment du commit)"
    return {"add_log": "ADD_LOG", "remove_log": "REMOVE_LOG", "change_level": "CHANGE_LEVEL"}.get(task, task)


def group_name(g):
    return FEATURE_GROUPS.get(g, g)


def category_name(column, value, lang="en"):
    """Display name of a categorical table cell (part, ctx_category, scope, variant, marker); other
    columns and unknown values are returned unchanged."""
    if column == "ctx_category":
        return context_name(value, lang)
    if column == "variant":
        return variant_name(value, lang)
    if column == "part":
        return PART_NAMES.get(lang, PART_NAMES["en"]).get(value, value)
    if column == "marker":
        return MARKER_NAMES.get(lang, MARKER_NAMES["en"]).get(value, value)
    if column == "scope" and value in ("full_test", "subset"):
        return t(value, lang)
    return value


def colon(lang="en"):
    """French typography puts a space before ':'."""
    return " : " if lang == "fr" else ": "


def num(v, digits=2, lang="en"):
    """A number for figure text; French uses the decimal comma."""
    s = f"{v:.{digits}f}"
    return s.replace(".", ",") if lang == "fr" else s
