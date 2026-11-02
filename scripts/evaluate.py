"""
Stage 8: evaluation tables, figures, error analysis and the experiment report.

Builds everything the available predictions allow. Missing models, tasks or inputs are
skipped with a notice that the report repeats under "Limitations of evidence". A table or
figure that raises an error is reported, and the script then exits with 1.

The primary analysis covers --tasks (add_log, remove_log, change_level) and the 12 primary
models. The sensitivity task add_log_post (--sens-tasks) and the post-hoc log1p models
(labels.POSTHOC_MODELS) are evaluated separately and only written to tables/sens_<task>_*
and tables/posthoc_log1p_* and to their own report sections.

Usage:
    python -m scripts.evaluate [--setting R4] [--lang en|fr|both] [--tasks add_log,remove_log,change_level]
                               [--sens-tasks add_log_post] [--data-dir DIR] [--results-dir DIR]
                               [--bootstrap B] [--bootstrap-tests B] [--examples 15]

Inputs come from <data-dir> (processed/, interim/, results/predictions, results/rq1, ...).
Outputs go to --results-dir (default <data-dir>/results): tables/*.csv|md|tex (plus *_fr.md|tex
for the main tables), figures/*_<lang>.png|pdf, error_analysis/* and report/experiment_report.md.
With a non-primary --setting (R1, R10) every setting-dependent file gets an _<setting> suffix,
so the primary outputs are never overwritten. The dataset-quality and RQ1 tables do not depend
on the setting.
"""

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common.config import DATA, load_config
from src.evaluation import analysis as an
from src.evaluation import figures as fg
from src.evaluation import reporting as rp
from src.evaluation.labels import MODEL_ORDER, TASK_ORDER, SENSITIVITY_TASKS, POSTHOC_MODELS, POSTHOC_BASE

FAILED = []
# tables whose content does not depend on --setting (rq1_* too); every other output of a
# non-primary run carries the _<setting> suffix
SETTING_FREE = {"dq_instances", "dq_failures", "dq_graph_stats", "dq_parse_failures", "dq_head_misparse",
                "dq_extraction_precision", "config_hyperparameters", "env_manifest"}

CAP = {
    "rq3_overall_pooled": "Overall metrics, test folds pooled.",
    "rq3_overall_macro": "Overall metrics, macro average over test repositories (n = all test instances).",
    "rq3_overall_macro_no_few_commit": "Macro average over test repositories without the few-commit folds "
                                       "(folds_excluded; n = remaining test instances).",
    "rq3_per_repo": "Metrics per test repository (low support: < 30 positives).",
    "rq3_per_engine": "Metrics pooled per game engine; lift = PR-AUC / prevalence.",
    "rq3_per_size": "Metrics pooled per repository size class; lift = PR-AUC / prevalence.",
    "rq3_per_ecosystem": "Metrics pooled per logging ecosystem (dominant formal framework of the repository); "
                         "lift = PR-AUC / prevalence.",
    "rq4_subset": "Metrics on the performance-sensitive subset (d_is_perf_sensitive = 1) and its complement; "
                  "lift = PR-AUC / prevalence.",
    "rq4_ctx_category": "Metrics per context category (d_ctx_category); lift = PR-AUC / prevalence.",
    "rq4_subsystem_markers": "Descriptive: metrics on the methods carrying each subsystem marker (markers overlap); "
                             "lift = PR-AUC / prevalence.",
    "ablation": "Ablation variants on the full test set and the performance-sensitive subset.",
}
CAP_FR = {
    "rq3_overall_pooled": "Métriques globales, plis de test agrégés.",
    "rq3_overall_macro": "Métriques globales, moyenne macro sur les référentiels de test (n = toutes les instances "
                         "de test).",
    "rq3_per_repo": "Métriques par référentiel de test (faible effectif : < 30 positifs).",
    "rq3_per_engine": "Métriques agrégées par moteur de jeu ; gain = PR-AUC / prévalence.",
    "rq3_per_size": "Métriques agrégées par classe de taille du référentiel ; gain = PR-AUC / prévalence.",
    "rq3_per_ecosystem": "Métriques agrégées par écosystème de journalisation ; gain = PR-AUC / prévalence.",
    "rq4_subset": "Métriques sur le sous-ensemble sensible aux performances et son complément ; "
                  "gain = PR-AUC / prévalence.",
    "rq4_ctx_category": "Métriques par catégorie de contexte ; gain = PR-AUC / prévalence.",
    "ablation": "Variantes d'ablation sur l'ensemble de test complet et le sous-ensemble sensible aux performances.",
    "rq4_subset_gap": "Sous-ensemble moins complément par modèle, sur des rééchantillons identiques ; une partie "
                      "sous le seuil de support (moins de 10 positifs ou positifs issus d'au plus 2 commits) est "
                      "descriptive (sans p).",
    "pairwise": "Comparaisons de modèles par paires (A − B, agrégé et macro) ; Holm par tâche et par métrique ; "
                "Wilcoxon sur les référentiels de test ; delta de Cliff.",
    "rq4_did": "QR4, différence des différences : (hybrid_ggnn − hgb) sur le sous-ensemble moins sur le complément ; "
               "hgb fixé a priori ; Holm sur les tâches par métrique ; le F1 des parties à faible effectif est "
               "exploratoire ; une partie sous le seuil de support (moins de 10 positifs ou positifs issus d'au plus "
               "2 commits) est descriptive (sans p, hors famille de Holm).",
}
DID_PREFIXES = [(f"{m}_{part}", f"{lab} {name}") for m, lab in (("pr_auc", "PR-AUC"), ("f1", "F1"))
                for part, name in (("subset", "subset"), ("complement", "complement"), ("did", "DiD"))]
DID_EXTRA = ["n_subset", "n_pos_subset", "n_pos_commits_subset", "n_complement", "n_pos_complement",
             "n_pos_commits_complement", "low_support_subset", "low_support_complement", "f1_exploratory",
             "descriptive_only"]
FLOOR = (f"Parts with < {load_config('experiment')['protocol']['min_test_positives']} positives or positives from at "
         f"most {an.FEW_COMMITS} commits are descriptive only (no p, not in the Holm family); B used = resamples "
         "with the positives the value needs.")
PAIRS_LIKE = {
    "rq4_subset_gap": ("Subset minus complement per model, paired bootstrap on identical test resamples; lift = "
                       "PR-AUC / prevalence (the prevalence differs between the parts). " + FLOOR,
                       [("pr_auc", "PR-AUC"), ("pr_auc_lift", "lift"), ("roc_auc", "ROC-AUC"), ("f1", "F1")],
                       ["task", "model"],
                       ["n_subset", "n_pos_subset", "n_pos_commits_subset", "prevalence_subset", "n_complement",
                        "n_pos_complement", "n_pos_commits_complement", "prevalence_complement", "low_support",
                        "descriptive_only"]),
    "pairwise": ("Pairwise model comparisons (A - B; pooled and macro over test repositories; macro resamples need a "
                 "positive in every repository); Holm within task per metric; Wilcoxon over test repositories; "
                 "Cliff's delta over (repository, seed) values.",
                 [("pr_auc", "PR-AUC"), ("macro_pr_auc", "macro PR-AUC"),
                  ("macro_no_few_commit_pr_auc", "macro PR-AUC without few-commit folds"), ("f1", "F1")],
                 ["task", "model_a", "model_b"],
                 ["n", "n_pos", "pr_auc_wilcoxon_p", "pr_auc_cliffs_delta", "pr_auc_cliffs_magnitude",
                  "few_commit_folds_excluded"]),
}
DID_TEXT = {
    "rq4_did": "RQ4 difference-in-differences: (hybrid_ggnn - hgb) on the subset minus on the complement; hgb fixed a "
               "priori; Holm over tasks per metric; PR-AUC is the primary test, F1 of low-support parts is "
               "exploratory. " + FLOOR,
    "rq4_did_bestval": "RQ4 sensitivity: difference-in-differences against the classical model with the highest "
                       "validation PR-AUC (model_b); Holm over tasks per metric. " + FLOOR,
    "rq4_did_frame_update": "RQ4 sensitivity: difference-in-differences with the stricter subset frame_update only "
                            "(complement = every other method); Holm over tasks per metric. " + FLOOR,
}


METRIC_SUFFIXES = {"_pooled": "rq3_overall_pooled", "_macro": "rq3_overall_macro", "_per_repo": "rq3_per_repo",
                   "_subset": "rq4_subset"}


def is_metric_table(name):
    """Tables of summary_row metrics (formatted with metric_display)."""
    if name in CAP:
        return True
    return name.startswith(("sens_", "posthoc_log1p_")) and name.endswith(tuple(METRIC_SUFFIXES))


def metric_caption(name):
    if name in CAP:
        return CAP[name]
    for suffix, key in METRIC_SUFFIXES.items():
        if name.endswith(suffix):
            return CAP[key]
    return name


def step(name, fn, *args, **kwargs):
    t0 = time.time()
    try:
        out = fn(*args, **kwargs)
    except Exception as e:
        traceback.print_exc()
        FAILED.append(name)
        an.notice(f"FAILED: {name} ({type(e).__name__}: {e})")
        return None
    print(f"  {name}: {time.time() - t0:.1f}s", flush=True)
    return out


def n_note(name, df):
    """The n statement of a table that has no per-row n and n_pos columns."""
    def total(col, d=df):
        return int(pd.to_numeric(d[col], errors="coerce").fillna(0).sum()) if col in d else 0

    if name in ("rq2_importance", "rq2_importance_features"):
        return f"{df['model'].nunique()} model(s), {df['task'].nunique()} task(s)."
    if name == "dq_training" or name.startswith("posthoc_log1p_training"):
        return "n_eval = evaluated instances and n_selected = instances of the setting, per model."
    if name == "dq_instances":
        return (f"n = {total('n_pos')} positives and {total('n_neg_pool')} pooled negatives "
                f"over {len(df)} task-repository rows.")
    if name == "dq_failures":
        return f"n = {total('n_instances')} instances over {len(df)} task-repository rows."
    if name == "dq_graph_stats":
        return f"n = {total('n_graphs')} graphs."
    if name == "dq_parse_failures":
        return (f"n = {total('n_commits')} commits ({total('n_non_merge')} non-merge) and "
                f"{total('parse_failures')} parse failures over {len(df)} repositories.")
    if name == "dq_head_misparse":
        return f"n = {total('n_java_files')} Java files over {len(df)} repositories."
    if name == "dq_extraction_precision":
        return f"n = {total('n_annotated', df[df['estimator'] == 'label'])} annotated events (n_annotated per row)."
    if name == "dq_folds":
        return f"n = {total('n_test')} test instances over {len(df)} folds."
    if name == "dq_coverage":
        return "n_union = instances predicted by any model, n_evaluated = instances scored for the model."
    if name == "rq1_events":
        return f"n = {total('n')} events."
    if name in ("rq1_events_validity", "rq1_events_scope"):
        return f"n = {total('total')} events."
    if name == "rq1_event_rates":
        return (f"n = {total('n_events_all')} events ({total('core_total')} core) and "
                f"{total('n_non_merge')} non-merge commits.")
    if name == "rq1_events_per_year":
        return f"n = {total('total', df[df['repo'] != 'ALL'])} core events (ALL rows = every repository)."
    if name == "rq1_transitions":
        return f"n = {total('total')} core CHANGE_LEVEL events."
    if name == "rq1_transitions_by_repo":
        return f"n = {total('n')} core CHANGE_LEVEL events."
    if name == "rq1_enrichment":
        per = df.groupby("task")[["total_pos", "total_neg"]].first()
        return "n per task: " + "; ".join(f"{task} {int(r.total_pos)} positives, {int(r.total_neg)} negatives"
                                          for task, r in per.iterrows()) + "."
    if name == "rq1_levels":
        return f"n = {total('n_formal')} formal statements over {len(df)} repositories (n_formal per row)."
    if name.startswith("rq4_did_reference_validation"):
        return "n_val_folds = validation values (folds x seeds) averaged per row."
    return f"n = {len(df)} rows."


def caption(text, setting, B, B_test=None):
    tests = f"; paired tests on B={B_test} resamples" if B_test and B_test != B else ""
    return (f"{text} Setting {setting}, leave-one-repository-out. n = instances in the row, n_pos = positives; "
            f"mean ± sd over seeds; 95% CI: commit-cluster bootstrap within repositories (B={B}) of the seed mean"
            f"{tests}.")


def caption_fr(text, setting, B, B_test=None):
    tests = f" ; tests appariés sur B = {B_test} rééchantillons" if B_test and B_test != B else ""
    return (f"{text} Réglage {setting}, validation croisée en laissant un référentiel de côté. n = instances de la "
            f"ligne, n_pos = positifs ; moyenne ± écart-type sur les graines ; IC à 95 % : bootstrap par grappes de "
            f"commits dans chaque référentiel (B = {B}) de la moyenne des graines{tests}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setting", default=None)
    ap.add_argument("--lang", default="both", choices=["en", "fr", "both"])
    ap.add_argument("--tasks", default=",".join(TASK_ORDER))
    ap.add_argument("--sens-tasks", default=",".join(SENSITIVITY_TASKS))
    ap.add_argument("--data-dir", default=str(DATA))
    ap.add_argument("--results-dir", default=None, help="output directory (default <data-dir>/results)")
    ap.add_argument("--bootstrap", type=int, default=None)
    ap.add_argument("--bootstrap-tests", type=int, default=None)
    ap.add_argument("--examples", type=int, default=15)
    args = ap.parse_args()

    cfg = load_config("experiment")
    primary = f"R{cfg['sampling']['primary_ratio']}"
    setting = args.setting or primary
    B_cfg, Bt_cfg, seed = an.bootstrap_sizes(cfg)
    B = args.bootstrap or B_cfg
    B_test = args.bootstrap_tests or Bt_cfg
    tasks = [x for x in args.tasks.split(",") if x]
    sens_tasks = [x for x in args.sens_tasks.split(",") if x]
    langs = ["en", "fr"] if args.lang == "both" else [args.lang]
    sfx = "" if setting == primary else f"_{setting}"
    ratio = int(setting[1:]) if setting[1:].isdigit() else None

    p = an.paths(Path(args.data_dir))
    out = Path(args.results_dir) if args.results_dir else p["results"]
    tdir, fdir, edir = out / "tables", out / "figures", out / "error_analysis"
    t_start = time.time()
    print(f"evaluate: setting={setting} tasks={tasks} sens={sens_tasks} B={B} B_test={B_test} data={p['data']} "
          f"out={out}", flush=True)

    folds = an.load_folds(p)
    if not folds:
        an.notice("instances/folds.json not found")
    events = an.load_events(p)
    if events is None:
        an.notice("events_master.jsonl not found, RQ1 event tables skipped")
    ecosystems, eco_source = an.repo_ecosystems(p, events, tasks)
    if not ecosystems:
        an.notice("no source for the logging ecosystem per repository; ecosystem = unknown")

    tds = {}
    for task in tasks:
        td = step(f"load {setting}/{task}", an.load_task, setting, task, p, B, seed, ecosystems=ecosystems,
                  B_test=B_test)
        if td is not None:
            tds[task] = td
    models_by_task = {task: (list(tds[task].models) if task in tds else []) for task in tasks}
    few, few_sources = an.few_commit_folds(p, folds, tasks) if folds else ({}, {})

    T = {}
    T["rq3_overall_pooled"] = step("overall pooled", an.table_overall_pooled, tds) if tds else None
    T["rq3_overall_macro"] = step("overall macro", an.table_overall_macro, tds) if tds else None
    if tds and any(few.get(task) for task in tds):
        T["rq3_overall_macro_no_few_commit"] = step("overall macro without few-commit folds", an.table_overall_macro,
                                                    {k: v for k, v in tds.items() if few.get(k)}, few)
    T["rq3_per_repo"] = step("per repo", an.table_per_repo, tds, folds) if tds else None
    T["rq3_per_engine"] = step("per engine", an.table_by, tds, "engine", "engine") if tds else None
    T["rq3_per_size"] = step("per size", an.table_by, tds, "size", "size") if tds else None
    T["rq3_per_ecosystem"] = step("per ecosystem", an.table_by, tds, "ecosystem", "ecosystem") if tds else None
    T["rq4_subset"] = step("perf subset", an.table_subset, tds) if tds else None
    T["rq4_subset_gap"] = step("perf subset gap", an.table_subset_gap, tds) if tds else None
    T["rq4_did"] = step("RQ4 DiD", an.table_did, tds) if tds else None
    best_val = step("RQ4 reference by validation", an.best_classical_by_validation, p, setting, list(tds))
    did_validation = None
    if best_val is not None:
        best, did_validation = best_val
        T["rq4_did_reference_validation"] = did_validation
        # with hgb chosen for every task the check is the primary table itself
        if any(m != an.REFERENCE for m in best.values()):
            T["rq4_did_bestval"] = step("RQ4 DiD (validation-selected reference)", an.table_did, tds,
                                        an.FULL_MODEL, best)
    T["rq4_did_frame_update"] = step("RQ4 DiD (frame_update subset)", an.table_did, tds, part="frame_part") \
        if tds else None
    T["rq4_ctx_category"] = step("context category", an.table_by, tds, "d_ctx_category", "ctx_category") if tds else None
    T["rq4_subsystem_markers"] = step("subsystem markers", an.table_markers, tds) if tds else None
    T["ablation"] = step("ablation", an.table_ablation, tds) if tds else None
    T["pairwise"] = step("pairwise", an.table_pairwise, tds, an.PAIRS, few) if tds else None
    T["sensitivity_ratio"] = step("R1/R4/R10 sensitivity", an.table_sensitivity, p, tasks, B,
                                  tds if setting == primary else {}, primary, ecosystems=ecosystems, seed=seed)
    mc = step("multiclass", an.table_multiclass, p, setting)
    T["multiclass"], T["multiclass_per_class"] = mc if mc else (None, None)
    T["rq2_importance"] = step("importance (groups)", an.table_importance, p, setting, "group", tasks=tasks)
    T["rq2_importance_features"] = step("importance (features)", an.table_importance, p, setting, "feature", 15,
                                        tasks=tasks)

    T["dq_instances"] = step("dq instances", an.table_instances, p, folds, tasks)
    T["dq_folds"] = step("dq folds", an.table_folds, p, folds, tasks, setting)
    T["dq_failures"] = step("dq failures", an.table_failures, p, tasks, primary)
    T["dq_graph_stats"] = step("dq graph stats", an.table_graph_stats, p, tasks)
    T["dq_parse_failures"] = step("dq parse failures", an.table_parse_failures, p)
    T["dq_head_misparse"] = step("dq HEAD misparse", an.table_head_misparse, p)
    # the validation sample is stratified by label: the overall precision weights the labels by their
    # share of the core events (the population the sample was drawn from, scripts/sample_validation.py)
    core_counts = None
    if events is not None and len(events) and "validity_status" in events:
        core_counts = events.loc[events["validity_status"] == "core", "event_label"].value_counts().to_dict()
    ep = step("dq extraction precision", an.table_extraction_precision, p, B, seed, core_counts)
    T["dq_extraction_precision"], n_ann, n_rows, ann_problems = ep if ep else (None, 0, 0, [])
    T["dq_coverage"] = step("dq coverage", an.table_coverage, {setting: tds})
    T["dq_training"] = step("dq training", an.table_training, p, setting, tasks)
    T["dq_imbalance"] = step("dq imbalance", an.table_imbalance, p, setting, tasks)
    T["config_hyperparameters"] = step("hyperparameters", an.table_hyperparameters, cfg)
    T["env_manifest"] = step("environment", an.table_environment, p)

    if events is not None and len(events):
        T["rq1_events"] = step("rq1 events", an.table_events, events)
        T["rq1_events_validity"] = step("rq1 validity", an.pivot_events, events, "validity_status")
        T["rq1_events_scope"] = step("rq1 scope", an.pivot_events, events, "scope")
        T["rq1_event_rates"] = step("rq1 rates", an.table_event_rates, events, an.commit_counts(p))
        T["rq1_events_per_year"] = step("rq1 events per year", an.table_events_per_year, events,
                                        an.commits_per_year(p))
        T["rq1_transitions"] = step("rq1 transitions", an.table_transitions, events)
        T["rq1_transitions_by_repo"] = step("rq1 transitions by repo", an.table_transitions, events, True)
    T["rq1_enrichment"] = step("rq1 enrichment", an.table_enrichment, p, tasks, primary)
    T["rq1_levels"] = step("rq1 snapshot levels", an.snapshot_levels, p)
    if T["rq1_levels"] is None:
        an.notice("no RQ1 snapshot level table under results/rq1, level-distribution figure skipped")

    # sensitivity task (commit-time ADD_LOG view): separate tables and Holm families
    sens_models, view_split = {}, None
    for task in sens_tasks:
        if not (p["predictions"] / setting / task).exists():
            an.notice(f"{setting}/{task}: no predictions, sensitivity analysis skipped")
            continue
        td_s = step(f"load {setting}/{task}", an.load_task, setting, task, p, B, seed, ecosystems=ecosystems,
                    B_test=B_test)
        if td_s is None:
            continue
        base = task.replace("_post", "")
        if base in tds:
            # the subset split of the pre-state view, so both views are compared on the same split
            view_split = step(f"{task} split from {base}", an.align_view_split, td_s, tds[base])
        sens_models[task] = list(td_s.models)
        one = {task: td_s}
        pre = f"sens_{task}"
        few_s = an.few_commit_folds(p, folds, [task])[0] if folds else {}
        T[f"{pre}_pooled"] = step(f"{task} pooled", an.table_overall_pooled, one)
        T[f"{pre}_macro"] = step(f"{task} macro", an.table_overall_macro, one)
        T[f"{pre}_per_repo"] = step(f"{task} per repo", an.table_per_repo, one, folds)
        T[f"{pre}_subset"] = step(f"{task} subset", an.table_subset, one)
        T[f"{pre}_did"] = step(f"{task} DiD", an.table_did, one)
        T[f"{pre}_pairwise"] = step(f"{task} pairwise", an.table_pairwise, one,
                                    [("hybrid_ggnn", "hgb"), ("gnn_ggnn", "hgb"), ("hybrid_ggnn", "naive_rule")], few_s)
        if base in tds:
            T[f"{pre}_vs_{base}"] = step(f"{task} vs {base}", an.table_view_comparison, tds[base], td_s)

    # post-hoc log1p models: primary instances and resamples, separate tables and Holm families
    tds_ph, posthoc_models = {}, {}
    for task, td in tds.items():
        avail = [m for m in POSTHOC_MODELS if (p["predictions"] / setting / task / m).is_dir()]
        if not avail:
            continue
        wanted = avail + [POSTHOC_BASE[m] for m in avail] + [an.REFERENCE]
        td_ph = step(f"load post-hoc {setting}/{task}", an.load_task, setting, task, p, B, seed, ecosystems=ecosystems,
                     B_test=B_test, models=wanted, ref=td, exclude=())
        if td_ph is not None:
            tds_ph[task] = td_ph
            posthoc_models[task] = [m for m in td_ph.models if m in POSTHOC_MODELS]
    if tds_ph:
        T["posthoc_log1p_pooled"] = step("post-hoc pooled", an.table_overall_pooled, tds_ph)
        T["posthoc_log1p_macro"] = step("post-hoc macro", an.table_overall_macro, tds_ph)
        T["posthoc_log1p_pairwise"] = step("post-hoc pairwise", an.table_pairwise, tds_ph, an.POSTHOC_PAIRS)
        T["posthoc_log1p_training"] = step("post-hoc training", an.table_training, p, setting, list(tds_ph),
                                           models=POSTHOC_MODELS, multiclass=False)

    fr = "fr" in langs
    for name, df in T.items():
        if df is None or not isinstance(df, pd.DataFrame) or not len(df):
            continue
        # a non-primary run never overwrites primary outputs; only the tables that do not depend
        # on --setting keep their name
        fname = name if name in SETTING_FREE or name.startswith("rq1_") else name + sfx
        tag = ""
        if name.startswith("sens_"):
            tag = "SENSITIVITY (commit-time ADD_LOG view, not primary). "
        elif name.startswith("posthoc_"):
            tag = "POST-HOC (log1p preprocessing, not pre-specified). "
        fr_cap = caption_fr(CAP_FR[name], setting, B, B_test) if fr and name in CAP_FR else None
        if is_metric_table(name):
            ids = [c for c in ["task", "test_repo", "engine", "size", "ecosystem", "part", "ctx_category", "marker",
                               "scope", "variant", "model", "folds_excluded"] if c in df]
            disp = rp.metric_display(df, ids)
            if name == "ablation" and "pr_auc_vs_full_delta" in df:
                extra = rp.delta_display(df, [], [("pr_auc_vs_full", "PR-AUC vs full"), ("f1_vs_full", "F1 vs full")],
                                         ["n_pos_commits", "descriptive_only"])
                disp = pd.concat([disp, extra], axis=1)
            step(f"write {fname}", rp.write_table, df, fname, tdir,
                 caption(tag + metric_caption(name), setting, B, B_test), disp, fr_cap)
        elif name in PAIRS_LIKE or name.endswith("_pairwise"):
            text, prefixes, ids, extra = PAIRS_LIKE.get(name, PAIRS_LIKE["pairwise"])
            disp = rp.delta_display(df, ids, prefixes, extra)
            step(f"write {fname}", rp.write_table, df, fname, tdir, caption(tag + text, setting, B, B_test), disp,
                 fr_cap)
        elif name in DID_TEXT or name.endswith("_did"):
            disp = rp.delta_display(df, ["task", "model_a", "model_b"], DID_PREFIXES, DID_EXTRA)
            text = DID_TEXT.get(name, DID_TEXT["rq4_did"])
            step(f"write {fname}", rp.write_table, df, fname, tdir, caption(tag + text, setting, B, B_test), disp,
                 fr_cap)
        elif name.endswith("_vs_add_log"):
            disp = rp.delta_display(df, ["model"], [("pr_auc", "PR-AUC (post - pre)"), ("f1", "F1 (post - pre)")],
                                    ["n", "n_pos", "pr_auc_pre", "pr_auc_post", "f1_pre", "f1_post", "paired"])
            step(f"write {fname}", rp.write_table, df, fname, tdir, caption(
                tag + "Each model in the pre-state view (add_log) and the commit-time view (add_log_post) on the same "
                "instances; paired bootstrap on identical resamples; Holm over the models per metric.", setting, B,
                B_test), disp)
        elif name == "sensitivity_ratio":
            disp = rp.metric_display(df, ["setting", "task", "model"], extra=("n", "n_pos", "prevalence"))
            step(f"write {fname}", rp.write_table, df, fname, tdir, caption(
                "Negative-sampling ratio sensitivity (R1, R4, R10) for naive and classical models, pooled; "
                "prevalence differs by setting.", "R1/R4/R10", B), disp)
        elif name in ("multiclass", "multiclass_per_class"):
            step(f"write {fname}", rp.write_table, df, fname, tdir,
                 "Multiclass supplement (NO_EVENT/ADD_LOG/REMOVE_LOG/CHANGE_LEVEL), pooled over LORO folds; "
                 "mean ± sd over seeds; balanced accuracy = macro recall; majority_class = always the most frequent "
                 "class; n = instances (n_class per class).")
        else:
            text = {
                "rq2_importance": "Group-level permutation importance (drop in average precision when the group's "
                                  "columns are permuted jointly on the test repository), mean ± sd over folds; "
                                  "group_name spells out the prefix; n_folds per row.",
                "rq2_importance_features": "Top-15 single features by permutation importance (drop in average "
                                           "precision), mean ± sd over folds; x_ buckets belong to the lexical group; "
                                           "n_folds per row.",
                "dq_training": "Training runs per model: seeds, completeness, evaluated instances (n_eval) and "
                               "instances dropped for missing features or graphs, from the seed<k>.json sidecars.",
                "posthoc_log1p_training": "POST-HOC models: training runs from the seed<k>.json sidecars, with the "
                                          "log1p-transformed columns per fold (mean over folds and seeds, per "
                                          "group; n_log1p_twice_mean = columns that are already log1p counts: x_ "
                                          "buckets, h_commit_index, h_file_prior_churn).",
                "dq_instances": "Instances per task and repository (positives; negatives in the pool and in R1/R4/R10).",
                "dq_folds": "LORO folds: training repositories, fit/validation/test sizes and positives (prediction "
                            "sidecars) and the commit support of the test positives (few_commit_fold).",
                "dq_imbalance": "Imbalance handling per task and model: negative sampling, class weighting and "
                                "decision-threshold rule (prediction sidecars).",
                "config_hyperparameters": "Hyperparameters and protocol, configs/experiment.yaml: fixed a priori, "
                                          "except the posthoc section (post-hoc log1p variants; "
                                          "prespecified = False).",
                "env_manifest": "Hardware and software, data/results/run_manifest.json.",
                "dq_failures": "Instances whose view, features or graph could not be built, per task and repository; "
                               "graphs are built only for the primary-setting instances.",
                "dq_graph_stats": "Graph size statistics per task (n_graphs graphs).",
                "dq_parse_failures": "Mining: commits, bulk commits and srcML parse failures per repository "
                                     "(0 = srcML returned a tree, not that it is structurally correct).",
                "dq_head_misparse": "HEAD snapshot: srcML parse failures and structural misparses per repository "
                                    "(files misparsed, method units without class, statements outside units).",
                "dq_extraction_precision": "Extraction precision per event label from the annotation of "
                                           "validation/event_sample.csv, '?' excluded and counted as "
                                           "wrong; Wilson and commit-clustered bootstrap 95% CIs. ALL = label "
                                           "precisions weighted by the labels' shares of the core events (the "
                                           "sample is stratified by label); 'ALL (sample, unweighted)' is not a "
                                           "corpus estimate.",
                "dq_coverage": "Prediction coverage per model (n_evaluated of n_union predicted instances).",
                "rq1_events": "Logging events per repository, label, validity status and scope.",
                "rq1_events_validity": "Logging events per repository and label by validity status.",
                "rq1_events_scope": "Logging events per repository and label by scope.",
                "rq1_event_rates": "Core events (formal, modified method, not relocated, not bulk), formal non-bulk "
                                   "events and all events per repository, absolute and per 1,000 non-merge commits.",
                "rq1_events_per_year": "Core events per repository, commit year and label; total_per_1k per 1,000 "
                                       "non-merge commits of that year.",
                "rq1_transitions": "CHANGE_LEVEL transitions between normalised levels (core events, rows = before).",
                "rq1_transitions_by_repo": "CHANGE_LEVEL transitions per repository (core events).",
                "rq1_enrichment": "Context category of positives vs negatives (R4 instances); enrichment = share_pos / share_neg.",
                "rq1_levels": "Formal logging statements per level and repository (HEAD snapshot).",
                "rq4_did_reference_validation": "Mean validation PR-AUC (over folds and seeds, from the sidecars) "
                                                "of the classical models; selected = reference of the RQ4 "
                                                "sensitivity check.",
            }.get(name, name)
            step(f"write {fname}", rp.write_table, df, fname, tdir, text + " " + n_note(name, df))

    conf_frames, summaries, gaps = [], [], []
    for task, td in tds.items():
        res = step(f"error analysis {task}", an.error_analysis, td, edir, n_examples=args.examples, sfx=sfx)
        if res:
            conf_frames.append(res["confusion"])
            summaries.append(res["summary"])
            if res["rate_gap"] is not None and len(res["rate_gap"]):
                gaps.append(res["rate_gap"])
    error_summary = pd.DataFrame(summaries) if summaries else None
    rate_gap = pd.concat(gaps, ignore_index=True) if gaps else None
    if conf_frames:
        conf = pd.concat(conf_frames, ignore_index=True)
        step("write confusion", rp.write_table, conf, f"confusion{sfx}", edir,
             "Confusion counts of the majority vote over seeds by context category and performance subset; "
             "fp_rate = fp/(fp+tn), fn_rate = fn/(fn+tp); n per row.")
        step("write disagreement", rp.write_table, error_summary, f"disagreement{sfx}", edir,
             "Agreement of hybrid_ggnn and hgb (majority vote over seeds), split by true label (_pos, _neg), with "
             "the precision/recall/F1 of each vote and the overlap of the top-k ranked instances (k = n_pos); "
             "n instances per task.")
    if rate_gap is not None:
        step("write error rate gap", rp.write_table, rate_gap, f"error_rate_gap{sfx}", edir,
             caption("FP and FN rates of the majority vote, subset minus complement, with cluster-bootstrap CIs.",
                     setting, B, B_test),
             rp.delta_display(rate_gap, ["task", "model"], [("fp_rate", "FP rate"), ("fn_rate", "FN rate")],
                              ["n_subset", "n_pos_subset", "n_complement", "n_pos_complement",
                               "fp_rate_descriptive_only", "fn_rate_descriptive_only"]))

    # figures cover the primary tasks and models only
    for lang in langs:
        for task, td in tds.items():
            curves = an.pr_curve_data(td)
            if curves:
                step(f"fig pr {task} {lang}", fg.fig_pr_curves, curves, float(td.y.mean()), task, fdir, lang, sfx,
                     setting)
            if T.get("rq3_per_repo") is not None:
                step(f"fig heatmap {task} {lang}", fg.fig_repo_heatmap, T["rq3_per_repo"], task, fdir, lang, sfx)
        if T.get("rq3_overall_pooled") is not None:
            step(f"fig bars {lang}", fg.fig_prauc_bars, T["rq3_overall_pooled"], fdir, lang, sfx)
        if T.get("ablation") is not None and len(T["ablation"]):
            step(f"fig ablation {lang}", fg.fig_ablation, T["ablation"], fdir, lang, sfx)
        if T.get("rq4_did") is not None and len(T["rq4_did"]):
            step(f"fig forest pr_auc {lang}", fg.fig_forest, T["rq4_did"], fdir, lang, "pr_auc", sfx)
            step(f"fig forest f1 {lang}", fg.fig_forest, T["rq4_did"], fdir, lang, "f1", sfx)
        if T.get("rq4_ctx_category") is not None and len(T["rq4_ctx_category"]):
            step(f"fig context categories {lang}", fg.fig_ctx_category, T["rq4_ctx_category"], fdir, lang, sfx)
        if T.get("rq1_levels") is not None:
            step(f"fig levels {lang}", fg.fig_levels, T["rq1_levels"], fdir, lang)
        if T.get("rq1_event_rates") is not None:
            step(f"fig core events {lang}", fg.fig_core_events, T["rq1_event_rates"], fdir, lang)
        if T.get("rq1_events_per_year") is not None:
            step(f"fig events per year {lang}", fg.fig_events_per_year, T["rq1_events_per_year"], fdir, lang)
        if T.get("rq1_transitions") is not None:
            step(f"fig transitions {lang}", fg.fig_transitions, T["rq1_transitions"], fdir, lang)

    ctx = {"setting": setting, "sfx": sfx, "B": B, "B_test": B_test, "seed": seed, "ratio": ratio, "tasks": tasks, "tables": T,
           "folds": folds, "few_commit": few, "few_commit_sources": few_sources,
           "generated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "notices": list(an.NOTICES), "ecosystem_source": eco_source, "models_by_task": models_by_task,
           "model_order": MODEL_ORDER, "error_summary": error_summary, "rate_gap": rate_gap,
           "did_validation": did_validation, "extraction": (n_ann, n_rows, ann_problems), "sens_models": sens_models,
           "posthoc_models": posthoc_models, "view_split": view_split,
           "min_test_positives": an.min_test_positives(), "few_commits": an.FEW_COMMITS,
           "rq1_snapshot_files": sorted(x.name for x in p["rq1"].glob("*.md")) if p["rq1"].exists() else []}
    lines = step("report", rp.experiment_report, ctx)
    if lines is None:
        lines = ["# Experiment report", "", "Report assembly failed; see the console output.", ""]
    name = "experiment_report.md" if setting == primary else f"experiment_report_{setting}.md"
    rp.write_report(lines, out / "report" / name)
    print(f"done in {time.time() - t_start:.0f}s; report: {out / 'report' / name}", flush=True)
    if FAILED:
        print(f"{len(FAILED)} steps failed: {FAILED}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
