# Experiment report (R1)

Generated 2026-10-05T19:06:15-04:00. Paths are relative to `data/results/`. Protocol: leave-one-repository-out; metrics pooled over the test folds unless stated; mean ± sd over training seeds; 95% CI = percentile cluster bootstrap over commits within repositories (B = 1000, seed 42) of the seed mean; paired tests on B = 10000 resamples of the same clusters. Every table lists n (instances) and n_pos (positives). This report states measurements only. The primary analysis covers add_log (pre-state view), remove_log and change_level with the 12 pre-specified models; the commit-time view (add_log_post) and the post-hoc log1p models appear only in sections 9 and 10.

## Models available

- add_log: naive_prior, naive_size, naive_rule, lr, rf, hgb
- remove_log: naive_prior, naive_size, naive_rule, lr, rf, hgb
- change_level: naive_prior, naive_size, naive_rule, lr, rf, hgb

## 1. Summary by research question

Measured values only, primary tasks and primary models. Δ = A − B; 95% CI = commit-cluster bootstrap; p = paired bootstrap on the test resamples, Holm-adjusted within the family named. The sensitivity task add_log_post (section 9) and the post-hoc log1p models (section 10) are not used here.

**RQ1 – logging practices and their evolution.** Decisive: `tables/rq1_event_rates.csv`, `tables/rq1_events_per_year.csv`, `tables/rq1_transitions.csv`, `tables/dq_extraction_precision.csv`; figures `figures/rq1_core_events_*`, `figures/rq1_events_per_year_*`, `figures/rq1_change_level_heatmap_*`.

- Core events: ADD_LOG 1225, REMOVE_LOG 767, CHANGE_LEVEL 119 in 9 repositories (32588 non-merge commits); core events per 1,000 non-merge commits from 0.6 (shattered-pixel-dungeon) to 501.1 (OpenRTS).
- Most frequent CHANGE_LEVEL transitions (n = 119): INFO→DEBUG 39; TRACE→DEBUG 28; DEBUG→TRACE 22.
- Extraction precision (annotation, 120 of 120 sampled events; `?` excluded): 0.915, the label precisions weighted by their shares of the core events (bootstrap of commits within labels, 95% CI [0.857, 0.964]); with `?` counted as wrong 0.915. Per label (Wilson 95% CI): ADD_LOG 0.950 [0.835, 0.986] (n=40); REMOVE_LOG 0.850 [0.709, 0.929] (n=40); CHANGE_LEVEL 0.975 [0.871, 0.996] (n=40).

**RQ2 – can history and code structure model logging decisions?** Decisive: `tables/rq3_overall_pooled_R1.csv`, `tables/pairwise_R1.csv`, `tables/ablation_R1.csv`, `tables/rq2_importance_R1.csv`.

- add_log: highest pooled PR-AUC rf 0.703 ± 0.003 [0.665, 0.747] (prevalence 0.500; naive_rule 0.571 ± 0.000 [0.529, 0.618]).
- remove_log: highest pooled PR-AUC rf 0.604 ± 0.005 [0.554, 0.654] (prevalence 0.500; naive_rule 0.509 ± 0.000 [0.417, 0.601]).
- change_level: highest pooled PR-AUC rf 0.732 ± 0.008 [0.460, 0.884] (prevalence 0.500; naive_rule 0.593 ± 0.000 [0.493, 0.701]).

**RQ3 – graph-based models vs simpler baselines.** Decisive: `tables/pairwise_R1.csv`, `tables/rq3_overall_macro_R1.csv`, `tables/rq3_per_repo_R1.csv`; figures `figures/prauc_bars_R1_*`, `figures/prauc_heatmap_<task>_R1_*`.


**RQ4 – performance-sensitive code.** Decisive: `tables/rq4_did_R1.csv`, `tables/rq4_subset_R1.csv`; figure `figures/rq4_forest_pr_auc_R1_*`. Primary test: PR-AUC difference-in-differences (hybrid_ggnn − hgb, subset minus complement), Holm over the three tasks; a task with a part below the support floor (< 10 positives or positives from at most 2 commits) gets no p.

- not available.

## 2. Dataset quality

| task | n_repos | n_pos | n_neg_pool | n_neg_R1 | n_neg_R4 | n_neg_R10 | test_repos | low_support |
|---|---|---|---|---|---|---|---|---|
| add_log | 9 | 907 | 90072 | 907 | 3628 | 9070 | 6 | 1 |
| change_level | 6 | 119 | 13869 | 119 | 476 | 1190 | 4 | 2 |
| remove_log | 8 | 767 | 14134 | 767 | 3005 | 6805 | 7 | 2 |

Per repository: `tables/dq_instances.csv`.

LORO folds (fit / validation / test sizes and positives from the prediction sidecars; training = every other repository of the evaluation set; commit support of the test positives):

| task | test repo | training repos | fit n / n_pos | val n / n_pos | test n / n_pos | positive commits | max commit share | few-commit | low support |
|---|---|---|---|---|---|---|---|---|---|
| add_log | OpenKeeper | 8 | 1312 / 656 | 232 / 116 | 270 / 135 | 88 | 0.14 |  |  |
| add_log | Mindustry | 8 | 846 / 423 | 150 / 75 | 818 / 409 | 338 | 0.01 |  |  |
| add_log | subspace-infinity | 8 | 1388 / 693 | 246 / 124 | 180 / 90 | 49 | 0.09 |  |  |
| add_log | riiablo | 8 | 1225 / 612 | 217 / 109 | 372 / 186 | 121 | 0.05 |  |  |
| add_log | OpenRTS | 8 | 1441 / 716 | 255 / 132 | 118 / 59 | 41 | 0.08 |  |  |
| add_log | SkyHussars | 8 | 1513 / 757 | 269 / 134 | 32 / 16 | 14 | 0.12 |  | yes |
| remove_log | OpenKeeper | 7 | 1234 / 616 | 218 / 110 | 82 / 41 | 27 | 0.10 |  |  |
| remove_log | Mindustry | 7 | 751 / 374 | 133 / 68 | 650 / 325 | 229 | 0.04 |  |  |
| remove_log | subspace-infinity | 7 | 1149 / 574 | 203 / 102 | 182 / 91 | 39 | 0.10 |  |  |
| remove_log | riiablo | 7 | 1030 / 513 | 182 / 93 | 322 / 161 | 40 | 0.18 |  |  |
| remove_log | OpenRTS | 7 | 1130 / 564 | 200 / 101 | 204 / 102 | 39 | 0.25 |  |  |
| remove_log | SkyHussars | 7 | 1250 / 627 | 226 / 111 | 58 / 29 | 16 | 0.21 |  | yes |
| remove_log | jme3rpg | 7 | 1278 / 638 | 226 / 114 | 30 / 15 | 5 | 0.67 |  | yes |
| change_level | OpenKeeper | 5 | 154 / 76 | 28 / 15 | 56 / 28 | 2 | 0.96 | yes | yes |
| change_level | Mindustry | 5 | 146 / 62 | 28 / 25 | 64 / 32 | 14 | 0.28 |  |  |
| change_level | subspace-infinity | 5 | 164 / 69 | 30 / 28 | 44 / 22 | 9 | 0.36 |  | yes |
| change_level | riiablo | 5 | 142 / 65 | 26 / 19 | 70 / 35 | 12 | 0.43 |  |  |

Commit support source: folds.json (dataset stage: positives from at most 2 commits). A few-commit fold measures the model on very few independent logging decisions. Training repositories per fold: `tables/dq_folds_R1.csv`.

Evaluated instances (predictions aligned across models):

| task | n_models | n_union | n_evaluated_min | n_evaluated_max | n_partial | n_eval_set_mismatch |
|---|---|---|---|---|---|---|
| add_log | 6 | 1790 | 1790 | 1790 | 0 | 0 |
| change_level | 6 | 234 | 234 | 234 | 0 | 0 |
| remove_log | 6 | 1528 | 1528 | 1528 | 0 | 0 |

Per model and seed: `tables/dq_coverage_R1.csv`.

Training runs (prediction sidecars; instances in the setting, evaluated, dropped for missing features or graph; number of distinct evaluation sets, eval_set_sha1, over the models):

| task | models | seeds | n_selected | n_eval | dropped no features | dropped no graph | eval sets | incomplete runs |
|---|---|---|---|---|---|---|---|---|
| add_log | 6 | 5-5 | 1814 | 1814 | 0 | 0 | 1 | none |
| remove_log | 6 | 5-5 | 1534 | 1534 | 0 | 0 | 1 | none |
| change_level | 6 | 5-5 | 238 | 238 | 0 | 0 | 1 | none |

Per model (seeds, seconds, epochs, thresholds): `tables/dq_training_R1.csv`.

Imbalance handling (negative sampling 1 negatives per positive per repository (seeded, nested); class weighting and threshold rule from the sidecars; threshold mean over tasks, folds and seeds):

| model | class_weighting | threshold_rule | threshold_mean |
|---|---|---|---|
| naive_prior | none (no training) | score < threshold (training prevalence) | 0.483 |
| naive_size | none (no training) | score >= threshold (F1-max on validation) | 17.524 |
| naive_rule | none (no training) | score >= threshold (F1-max on validation) | 0.041 |
| lr | class_weight=balanced | score >= threshold (F1-max on validation) | 0.130 |
| rf | class_weight=balanced_subsample | score >= threshold (F1-max on validation) | 0.289 |
| hgb | none (unweighted loss) | score >= threshold (F1-max on validation) | 0.350 |

Per task: `tables/dq_imbalance_R1.csv`. Hyperparameters (fixed a priori, except the `posthoc` section: post-hoc variants added on 2026-10-03, `prespecified` = False): `tables/config_hyperparameters.csv`. Hardware and software: `tables/env_manifest.csv`.

View, feature and graph failures (graphs are built only for the instances of the primary setting, which the neural models use; `n_graph_not_built_outside_R4` counts the other instances of the instance file, `n_graph_missing_in_R4` real gaps):

| task | n_instances | n_view_failures | n_with_features | n_with_graph | n_graph_not_built_outside_R4 | n_graph_missing_in_R4 | n_graph_truncated | n_graph_failures |
|---|---|---|---|---|---|---|---|---|
| add_log | 9977 | 0 | 9977 | 4535 | 5442 | 0 | 55 | 0 |
| change_level | 1309 | 0 | 1309 | 595 | 714 | 0 | 0 | 0 |
| remove_log | 7572 | 0 | 7572 | 3772 | 3800 | 0 | 0 | 0 |

Per repository and reason: `tables/dq_failures.csv`.

Graph sizes:

| task | n_graphs | n_nodes_mean | n_nodes_median | n_nodes_p95 | n_nodes_max | n_edges_mean | n_edges_median | n_truncated |
|---|---|---|---|---|---|---|---|---|
| add_log | 4535 | 106.2 | 39.0 | 345.2 | 2000.0 | 403.7 | 144.0 | 55 |
| remove_log | 3772 | 157.3 | 96.0 | 470.4 | 1233.0 | 668.8 | 394.0 | 0 |
| change_level | 595 | 166.8 | 82.0 | 535.0 | 1231.0 | 741.8 | 346.0 | 0 |

Full: `tables/dq_graph_stats.csv`.

Mining (commits and srcML parse failures over the history):

| repo | n_commits | n_non_merge | n_bulk | parse_failures | parse_failures_pre | parse_failures_post |
|---|---|---|---|---|---|---|
| Archer-Game-Template2 | 473 | 464 | 1 | 0 | 0 | 0 |
| Mindustry | 20299 | 17260 | 26 | 0 | 0 | 0 |
| OpenKeeper | 2780 | 2458 | 7 | 0 | 0 | 0 |
| OpenRTS | 477 | 439 | 8 | 0 | 0 | 0 |
| SkyHussars | 439 | 430 | 2 | 0 | 0 | 0 |
| jme3rpg | 315 | 295 | 2 | 0 | 0 | 0 |
| riiablo | 1951 | 1942 | 5 | 0 | 0 | 0 |
| shattered-pixel-dungeon | 8745 | 8732 | 24 | 0 | 0 | 0 |
| subspace-infinity | 607 | 568 | 12 | 0 | 0 | 0 |

parse_failures = 0 only means that srcML returned a tree for every file; it does not show that the tree is structurally correct (see the HEAD misparse counts below). With the mining summary counts: `tables/dq_parse_failures.csv`.

HEAD snapshot, structural misparses (rq1 screening): a misparsed file has statements or members directly under `<unit>`; its method units lose their class (`n_units_no_class`) and statements outside any unit are not detected (`n_formal_outside_units_misparse` formal logging statements, `n_statements_outside_units_misparse` of any style); `n_formal` = formal statements detected at HEAD:

| repo | n_java_files | n_parse_failures | n_files_misparsed | pct_files_misparsed | n_units_no_class | n_formal_outside_units_misparse | n_statements_outside_units_misparse | n_formal |
|---|---|---|---|---|---|---|---|---|
| OpenKeeper | 698 | 0 | 5 | 0.7 | 13 | 0 | 0 | 358 |
| Mindustry | 809 | 0 | 81 | 10.0 | 1108 | 102 | 107 | 306 |
| shattered-pixel-dungeon | 1289 | 0 | 4 | 0.3 | 10 | 0 | 0 | 2 |
| subspace-infinity | 310 | 0 | 0 | 0.0 | 0 | 0 | 0 | 275 |
| riiablo | 862 | 0 | 3 | 0.3 | 35 | 5 | 5 | 1462 |
| OpenRTS | 236 | 0 | 1 | 0.4 | 6 | 0 | 1 | 93 |
| SkyHussars | 134 | 0 | 1 | 0.7 | 1 | 0 | 0 | 19 |
| Archer-Game-Template2 | 78 | 0 | 0 | 0.0 | 0 | 0 | 0 | 27 |
| jme3rpg | 126 | 0 | 0 | 0.0 | 0 | 0 | 0 | 20 |

All screened repositories: `tables/dq_head_misparse.csv`; per file: `rq1/structural_misparse.csv`.

Extraction precision from the annotation (120 of 120 sampled events annotated). An event is correct when `is_logging_statement`, `label_correct` and, for CHANGE_LEVEL, `level_correct` are y (docs/16); precision with `?` excluded and with `?` counted as wrong; Wilson 95% CI and a bootstrap 95% CI over commits:

| label | annotated (correct / wrong / ?) | precision | Wilson CI | commit bootstrap CI | precision (? wrong) | Wilson CI (? wrong) | core events | weight |
|---|---|---|---|---|---|---|---|---|
| ADD_LOG | 40 (38 / 2 / 0) | 0.950 | [0.835, 0.986] | [0.875, 1.000] | 0.950 | [0.835, 0.986] | 1225.000 | 0.580 |
| REMOVE_LOG | 40 (34 / 6 / 0) | 0.850 | [0.709, 0.929] | [0.737, 0.951] | 0.850 | [0.709, 0.929] | 767.000 | 0.363 |
| CHANGE_LEVEL | 40 (39 / 1 / 0) | 0.975 | [0.871, 0.996] | [0.919, 1.000] | 0.975 | [0.871, 0.996] | 119.000 | 0.056 |
| ALL | 120 (111 / 9 / 0) | 0.915 | – | [0.857, 0.964] | 0.915 | – | 2111.000 | 1.000 |
| ALL (sample, unweighted) | 120 (111 / 9 / 0) | 0.925 | [0.864, 0.960] | [0.877, 0.967] | 0.925 | [0.864, 0.960] | – | – |

The sample is stratified by label (up to 40 core events each), so it over-represents rare labels. `ALL` is the stratified estimate Σ W_l·p_l with W_l = the label's share of the core events of the master table; its CI is a bootstrap of commits within each label (no Wilson interval). `ALL (sample, unweighted)` is the pooled share of the sample and is not an estimate for the corpus. Wilson intervals are optimistic because errors cluster by commit; a label whose annotated events are all correct adds no bootstrap variance. Table: `tables/dq_extraction_precision.csv`.

## 3. RQ1 - logging practices and their evolution

Logging events per repository:

| repo | n_non_merge | core_ADD_LOG | core_REMOVE_LOG | core_CHANGE_LEVEL | core_total | core_total_per_1k | n_formal_nonbulk | formal_nonbulk_per_1k |
|---|---|---|---|---|---|---|---|---|
| Archer-Game-Template2 | 464 | 5 | 0 | 0 | 5 | 10.8 | 41 | 88.4 |
| Mindustry | 17260 | 510 | 325 | 32 | 867 | 50.2 | 1554 | 90.0 |
| OpenKeeper | 2458 | 149 | 41 | 28 | 218 | 88.7 | 717 | 291.7 |
| OpenRTS | 439 | 117 | 102 | 1 | 220 | 501.1 | 469 | 1068.3 |
| SkyHussars | 430 | 23 | 29 | 1 | 53 | 123.3 | 126 | 293.0 |
| jme3rpg | 295 | 14 | 15 | 0 | 29 | 98.3 | 87 | 294.9 |
| riiablo | 1942 | 276 | 161 | 35 | 472 | 243.0 | 2769 | 1425.8 |
| shattered-pixel-dungeon | 8732 | 2 | 3 | 0 | 5 | 0.6 | 8 | 0.9 |
| subspace-infinity | 568 | 129 | 91 | 22 | 242 | 426.1 | 1004 | 1767.6 |

Columns: `n_non_merge` = non-merge commits reachable from the pinned HEAD (bulk commits included); `core_<label>` = core events (formal logging style, inside a method that exists before and after the commit, not relocated, not in a bulk commit); `core_total_per_1k` = core_total / n_non_merge × 1000; `n_formal_nonbulk` = formal events outside bulk commits in any scope (new/deleted methods and files, relocations included); `formal_nonbulk_per_1k` = n_formal_nonbulk / n_non_merge × 1000. The CSV also has `n_events_all` / `all_per_1k`: every event of the master table (all styles, scopes, bulk and relocated events), which counts code creation and deletion, not logging decisions.

Total core events: ADD_LOG 1225, REMOVE_LOG 767, CHANGE_LEVEL 119.

Core events per commit year, all repositories (per repository and label: `tables/rq1_events_per_year.csv`; figure `figures/rq1_events_per_year_*`):

| year | n_non_merge | ADD_LOG | REMOVE_LOG | CHANGE_LEVEL | total | total_per_1k |
|---|---|---|---|---|---|---|
| 2014 | 882 | 90 | 28 | 0 | 118 | 133.8 |
| 2015 | 1689 | 87 | 82 | 1 | 170 | 100.7 |
| 2016 | 1519 | 58 | 25 | 5 | 88 | 57.9 |
| 2017 | 1504 | 61 | 43 | 0 | 104 | 69.1 |
| 2018 | 3119 | 181 | 128 | 2 | 311 | 99.7 |
| 2019 | 3939 | 225 | 129 | 21 | 375 | 95.2 |
| 2020 | 5800 | 316 | 157 | 56 | 529 | 91.2 |
| 2021 | 3540 | 55 | 74 | 3 | 132 | 37.3 |
| 2022 | 3339 | 37 | 16 | 0 | 53 | 15.9 |
| 2023 | 2622 | 40 | 43 | 30 | 113 | 43.1 |
| 2024 | 1930 | 27 | 19 | 0 | 46 | 23.8 |
| 2025 | 2184 | 43 | 22 | 1 | 66 | 30.2 |
| 2026 | 521 | 5 | 1 | 0 | 6 | 11.5 |

Most frequent CHANGE_LEVEL transitions (core, n = 119): INFO→DEBUG 39; TRACE→DEBUG 28; DEBUG→TRACE 22; DEBUG→INFO 9; ERROR→WARN 5; INFO→ERROR 3.

Context categories of positives vs negatives (R4 instances):

| task | category | n_pos | share_pos | n_neg | share_neg | enrichment |
|---|---|---|---|---|---|---|
| add_log | frame_update | 94 | 0.104 | 591 | 0.163 | 0.636 |
| add_log | loop | 325 | 0.358 | 936 | 0.258 | 1.389 |
| add_log | subsystem | 263 | 0.290 | 776 | 0.214 | 1.356 |
| add_log | general | 225 | 0.248 | 1325 | 0.365 | 0.679 |
| add_log | perf_sensitive_any | 682 | 0.752 | 2303 | 0.635 | 1.185 |
| remove_log | frame_update | 113 | 0.147 | 206 | 0.069 | 2.149 |
| remove_log | loop | 309 | 0.403 | 1567 | 0.521 | 0.773 |
| remove_log | subsystem | 214 | 0.279 | 806 | 0.268 | 1.040 |
| remove_log | general | 131 | 0.171 | 426 | 0.142 | 1.205 |
| remove_log | perf_sensitive_any | 636 | 0.829 | 2579 | 0.858 | 0.966 |
| change_level | frame_update | 4 | 0.034 | 28 | 0.059 | 0.571 |
| change_level | loop | 50 | 0.420 | 256 | 0.538 | 0.781 |
| change_level | subsystem | 47 | 0.395 | 123 | 0.258 | 1.528 |
| change_level | general | 18 | 0.151 | 69 | 0.145 | 1.043 |
| change_level | perf_sensitive_any | 101 | 0.849 | 407 | 0.855 | 0.993 |

HEAD snapshot tables from `scripts/screen_corpus.py`: `rq1/caller_audit.md`, `rq1/corpus_snapshot.md`, `rq1/detection_audit.md`, `rq1/framework_distribution.md`, `rq1/level_distribution.md`, `rq1/log_context_distribution.md`, `rq1/parse_failures.md`, `rq1/perf_context_distribution.md`.

Tables: `tables/rq1_events.csv`, `tables/rq1_events_validity.csv`, `tables/rq1_events_scope.csv`, `tables/rq1_event_rates.csv`, `tables/rq1_events_per_year.csv`, `tables/rq1_transitions.csv`, `tables/rq1_transitions_by_repo.csv`, `tables/rq1_enrichment.csv`, `tables/rq1_levels.csv`. Figures (not setting-dependent): `figures/rq1_core_events_*`, `figures/rq1_events_per_year_*`, `figures/rq1_change_level_heatmap_*`, `figures/rq1_levels_*`.

## 4. RQ2 - can history and code structure model logging decisions?

Pooled PR-AUC (the prevalence is the expected PR-AUC of a random ranking):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.504 ± 0.007 [0.473, 0.536] | 0.506 ± 0.016 [0.465, 0.549] | 0.513 ± 0.022 [0.356, 0.655] |
| naive_size | 0.516 ± 0.000 [0.475, 0.560] | 0.437 ± 0.000 [0.379, 0.512] | 0.415 ± 0.000 [0.247, 0.589] |
| naive_rule | 0.571 ± 0.000 [0.529, 0.618] | 0.509 ± 0.000 [0.417, 0.601] | 0.593 ± 0.000 [0.493, 0.701] |
| hgb | 0.689 ± 0.000 [0.652, 0.731] | 0.540 ± 0.000 [0.484, 0.596] | 0.712 ± 0.000 [0.452, 0.876] |

Prevalence per task: add_log 0.500; change_level 0.500; remove_log 0.500.

Permutation importance: not available.

## 5. RQ3 - graph-based models vs simpler baselines

Pooled PR-AUC, all models:

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.504 ± 0.007 [0.473, 0.536] | 0.506 ± 0.016 [0.465, 0.549] | 0.513 ± 0.022 [0.356, 0.655] |
| naive_size | 0.516 ± 0.000 [0.475, 0.560] | 0.437 ± 0.000 [0.379, 0.512] | 0.415 ± 0.000 [0.247, 0.589] |
| naive_rule | 0.571 ± 0.000 [0.529, 0.618] | 0.509 ± 0.000 [0.417, 0.601] | 0.593 ± 0.000 [0.493, 0.701] |
| lr | 0.586 ± 0.000 [0.550, 0.625] | 0.553 ± 0.000 [0.488, 0.627] | 0.626 ± 0.000 [0.414, 0.788] |
| rf | 0.703 ± 0.003 [0.665, 0.747] | 0.604 ± 0.005 [0.554, 0.654] | 0.732 ± 0.008 [0.460, 0.884] |
| hgb | 0.689 ± 0.000 [0.652, 0.731] | 0.540 ± 0.000 [0.484, 0.596] | 0.712 ± 0.000 [0.452, 0.876] |

Pooled F1 (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.494 ± 0.009 [0.475, 0.512] | 0.502 ± 0.022 [0.472, 0.531] | 0.457 ± 0.028 [0.373, 0.509] |
| naive_size | 0.653 ± 0.000 [0.625, 0.678] | 0.653 ± 0.000 [0.610, 0.692] | 0.584 ± 0.000 [0.421, 0.717] |
| naive_rule | 0.653 ± 0.000 [0.625, 0.678] | 0.653 ± 0.000 [0.611, 0.693] | 0.607 ± 0.000 [0.478, 0.717] |
| lr | 0.606 ± 0.000 [0.577, 0.633] | 0.648 ± 0.000 [0.606, 0.690] | 0.727 ± 0.000 [0.558, 0.824] |
| rf | 0.687 ± 0.004 [0.656, 0.713] | 0.667 ± 0.000 [0.627, 0.705] | 0.719 ± 0.004 [0.563, 0.809] |
| hgb | 0.646 ± 0.000 [0.614, 0.680] | 0.661 ± 0.000 [0.619, 0.700] | 0.712 ± 0.000 [0.557, 0.806] |

Pooled precision (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.498 ± 0.007 [0.465, 0.528] | 0.500 ± 0.021 [0.452, 0.549] | 0.496 ± 0.031 [0.334, 0.626] |
| naive_size | 0.496 ± 0.000 [0.466, 0.525] | 0.492 ± 0.000 [0.448, 0.538] | 0.489 ± 0.000 [0.352, 0.603] |
| naive_rule | 0.496 ± 0.000 [0.466, 0.525] | 0.493 ± 0.000 [0.448, 0.538] | 0.485 ± 0.000 [0.358, 0.595] |
| lr | 0.515 ± 0.000 [0.483, 0.547] | 0.512 ± 0.000 [0.467, 0.559] | 0.600 ± 0.000 [0.415, 0.722] |
| rf | 0.602 ± 0.011 [0.567, 0.634] | 0.500 ± 0.000 [0.457, 0.545] | 0.576 ± 0.006 [0.403, 0.697] |
| hgb | 0.619 ± 0.000 [0.583, 0.657] | 0.503 ± 0.000 [0.459, 0.548] | 0.573 ± 0.000 [0.401, 0.697] |

Pooled recall (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.491 ± 0.014 [0.476, 0.504] | 0.504 ± 0.025 [0.487, 0.521] | 0.426 ± 0.034 [0.392, 0.464] |
| naive_size | 0.956 ± 0.000 [0.936, 0.974] | 0.967 ± 0.000 [0.952, 0.980] | 0.726 ± 0.000 [0.456, 0.980] |
| naive_rule | 0.956 ± 0.000 [0.936, 0.974] | 0.969 ± 0.000 [0.953, 0.981] | 0.812 ± 0.000 [0.582, 1.000] |
| lr | 0.735 ± 0.000 [0.697, 0.770] | 0.884 ± 0.000 [0.836, 0.928] | 0.923 ± 0.000 [0.797, 0.986] |
| rf | 0.800 ± 0.020 [0.761, 0.833] | 1.000 ± 0.000 [1.000, 1.000] | 0.956 ± 0.016 [0.895, 0.989] |
| hgb | 0.675 ± 0.000 [0.636, 0.713] | 0.962 ± 0.000 [0.925, 0.986] | 0.940 ± 0.000 [0.864, 0.983] |

Pooled ROC-AUC (mean ± sd over seeds):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.500 ± 0.006 | 0.503 ± 0.023 | 0.512 ± 0.018 |
| naive_size | 0.547 ± 0.000 | 0.386 ± 0.000 | 0.266 ± 0.000 |
| naive_rule | 0.569 ± 0.000 | 0.443 ± 0.000 | 0.548 ± 0.000 |
| lr | 0.568 ± 0.000 | 0.585 ± 0.000 | 0.668 ± 0.000 |
| rf | 0.722 ± 0.003 | 0.612 ± 0.008 | 0.712 ± 0.006 |
| hgb | 0.697 ± 0.000 | 0.540 ± 0.000 | 0.708 ± 0.000 |

n per task: add_log n=1790, n_pos=895; change_level n=234, n_pos=117; remove_log n=1528, n_pos=764.

Macro PR-AUC (mean over the test repositories each model was evaluated on):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.516 ± 0.017 [0.478, 0.564] | 0.526 ± 0.019 [0.466, 0.593] | 0.532 ± 0.023 [0.370, 0.658] |
| naive_size | 0.560 ± 0.000 [0.509, 0.619] | 0.483 ± 0.000 [0.407, 0.569] | 0.423 ± 0.000 [0.269, 0.561] |
| naive_rule | 0.576 ± 0.000 [0.527, 0.638] | 0.524 ± 0.000 [0.432, 0.596] | 0.620 ± 0.000 [0.560, 0.809] |
| lr | 0.633 ± 0.000 [0.588, 0.687] | 0.588 ± 0.000 [0.504, 0.668] | 0.672 ± 0.000 [0.490, 0.790] |
| rf | 0.706 ± 0.002 [0.653, 0.762] | 0.613 ± 0.005 [0.544, 0.676] | 0.748 ± 0.010 [0.632, 0.840] |
| hgb | 0.688 ± 0.000 [0.641, 0.742] | 0.571 ± 0.000 [0.451, 0.640] | 0.691 ± 0.000 [0.530, 0.799] |

Macro CIs use only the resamples in which every repository of the macro has a positive (of B = 1000): add_log 1000; change_level 878; remove_log 998.

Macro PR-AUC with and without the few-commit folds (change_level: OpenKeeper):

| model | change_level all folds | change_level without few-commit folds |
|---|---|---|
| naive_prior | 0.532 ± 0.023 [0.370, 0.658] | 0.536 ± 0.024 [0.409, 0.651] |
| naive_size | 0.423 ± 0.000 [0.269, 0.561] | 0.443 ± 0.000 [0.293, 0.585] |
| naive_rule | 0.620 ± 0.000 [0.560, 0.809] | 0.663 ± 0.000 [0.557, 0.775] |
| lr | 0.672 ± 0.000 [0.490, 0.790] | 0.646 ± 0.000 [0.514, 0.772] |
| rf | 0.748 ± 0.010 [0.632, 0.840] | 0.686 ± 0.009 [0.547, 0.802] |
| hgb | 0.691 ± 0.000 [0.530, 0.799] | 0.630 ± 0.000 [0.484, 0.760] |

Table: `tables/rq3_overall_macro_no_few_commit_R1.csv`.

Pooled metrics per engine (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | engine | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | jME | 600 | 300 | 0.500 | 0.502 | 0.641 ± 0.000 [0.556, 0.731] ×1.28 | 0.631 ± 0.000 |
| add_log | libGDX | 1190 | 595 | 0.500 | 0.506 | 0.711 ± 0.000 [0.668, 0.753] ×1.42 | 0.725 ± 0.000 |
| remove_log | jME | 556 | 278 | 0.500 | 0.512 | 0.534 ± 0.000 [0.414, 0.664] ×1.07 | 0.533 ± 0.000 |
| remove_log | libGDX | 972 | 486 | 0.500 | 0.505 | 0.550 ± 0.000 [0.499, 0.609] ×1.10 | 0.549 ± 0.000 |
| change_level | jME | 100 | 50 | 0.500 | 0.517 | 0.804 ± 0.000 [0.301, 0.960] ×1.61 | 0.830 ± 0.000 |
| change_level | libGDX | 134 | 67 | 0.500 | 0.522 | 0.628 ± 0.000 [0.442, 0.776] ×1.26 | 0.608 ± 0.000 |

Pooled metrics per size (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | size | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | Large | 1640 | 820 | 0.500 | 0.503 | 0.690 ± 0.000 [0.650, 0.733] ×1.38 | 0.701 ± 0.000 |
| add_log | Medium | 150 | 75 | 0.500 | 0.523 | 0.686 ± 0.000 [0.562, 0.814] ×1.37 | 0.649 ± 0.000 |
| remove_log | Large | 1236 | 618 | 0.500 | 0.505 | 0.530 ± 0.000 [0.481, 0.582] ×1.06 | 0.528 ± 0.000 |
| remove_log | Medium | 292 | 146 | 0.500 | 0.518 | 0.619 ± 0.000 [0.421, 0.777] ×1.24 | 0.617 ± 0.000 |
| change_level | Large | 234 | 117 | 0.500 | 0.513 | 0.712 ± 0.000 [0.452, 0.876] ×1.42 | 0.708 ± 0.000 |

Pooled metrics per ecosystem (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | ecosystem | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | arc | 818 | 409 | 0.500 | 0.507 | 0.742 ± 0.000 [0.693, 0.792] ×1.48 | 0.754 ± 0.000 |
| add_log | gdx | 372 | 186 | 0.500 | 0.511 | 0.730 ± 0.000 [0.657, 0.804] ×1.46 | 0.725 ± 0.000 |
| add_log | jdk_system | 270 | 135 | 0.500 | 0.516 | 0.689 ± 0.000 [0.571, 0.803] ×1.38 | 0.719 ± 0.000 |
| add_log | jul | 118 | 59 | 0.500 | 0.538 | 0.657 ± 0.000 [0.506, 0.805] ×1.31 | 0.626 ± 0.000 |
| add_log | slf4j | 212 | 106 | 0.500 | 0.492 | 0.564 ± 0.000 [0.460, 0.674] ×1.13 | 0.519 ± 0.000 |
| remove_log | arc | 650 | 325 | 0.500 | 0.514 | 0.557 ± 0.000 [0.502, 0.623] ×1.11 | 0.529 ± 0.000 |
| remove_log | gdx | 322 | 161 | 0.500 | 0.499 | 0.571 ± 0.000 [0.460, 0.675] ×1.14 | 0.589 ± 0.000 |
| remove_log | jdk_system | 82 | 41 | 0.500 | 0.544 | 0.468 ± 0.000 [0.339, 0.634] ×0.94 | 0.445 ± 0.000 |
| remove_log | jul | 234 | 117 | 0.500 | 0.519 | 0.709 ± 0.000 [0.414, 0.867] ×1.42 | 0.650 ± 0.000 |
| remove_log | slf4j | 240 | 120 | 0.500 | 0.511 | 0.483 ± 0.000 [0.378, 0.611] ×0.97 | 0.466 ± 0.000 |
| change_level | arc | 64 | 32 | 0.500 | 0.505 | 0.599 ± 0.000 [0.324, 0.785] ×1.20 | 0.561 ± 0.000 |
| change_level | gdx | 70 | 35 | 0.500 | 0.559 | 0.643 ± 0.000 [0.369, 0.866] ×1.29 | 0.627 ± 0.000 |
| change_level | jdk_system | 56 | 28 | 0.500 | 0.521 | 0.873 ± 0.000 [0.333, 1.000] ×1.75 | 0.916 ± 0.000 |
| change_level | slf4j | 44 | 22 | 0.500 | 0.544 | 0.647 ± 0.000 [0.403, 0.853] ×1.29 | 0.656 ± 0.000 |

PR-AUC depends on the prevalence, which differs between groups (engines, sizes, ecosystems, subsets, categories): compare groups through the lift and ROC-AUC, not through raw PR-AUC.

Ecosystem = dominant formal logging framework per repository; source: rq1 snapshot.

Tables: `tables/rq3_overall_pooled_R1.csv`, `tables/rq3_overall_macro_R1.csv`, `tables/rq3_per_repo_R1.csv`, `tables/rq3_per_engine_R1.csv`, `tables/rq3_per_size_R1.csv`, `tables/rq3_per_ecosystem_R1.csv` (with French variants `*_fr.md`/`*_fr.tex` of the main tables). Figures: `figures/pr_curves_<task>_R1_*` (seed 0), `figures/prauc_bars_R1_*`, `figures/prauc_heatmap_<task>_R1_*`.

## 6. RQ4 - performance-sensitive code

Difference-in-differences: not available (needs hybrid_ggnn, hgb and d_is_perf_sensitive).

Sensitivity to the reference model: the primary reference is hgb, fixed a priori; as a check, the reference is also chosen without test information, as the classical model (lr, rf, hgb) with the highest mean validation PR-AUC over folds and seeds: add_log hgb (0.795); remove_log rf (0.665); change_level hgb (0.813).

Validation PR-AUC per classical model: `tables/rq4_did_reference_validation_R1.csv`.

Subset coverage (share of the test instances in the performance-sensitive subset): add_log 68.8% of the instances, 75.2% of the positives; remove_log 85.1% of the instances, 83.0% of the positives; change_level 86.3% of the instances, 85.5% of the positives.

Subset and complement (pooled; prevalence differs between the parts, so compare lift and ROC-AUC):

| task | part | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | complement | 559 | 222 | 0.397 | 0.398 | 0.567 ± 0.000 [0.492, 0.646] ×1.43 | 0.646 ± 0.000 |
| add_log | subset | 1231 | 673 | 0.547 | 0.553 | 0.721 ± 0.000 [0.680, 0.763] ×1.32 | 0.699 ± 0.000 |
| remove_log | complement | 228 | 130 | 0.570 | 0.597 | 0.591 ± 0.000 [0.492, 0.698] ×1.04 | 0.497 ± 0.000 |
| remove_log | subset | 1300 | 634 | 0.488 | 0.490 | 0.528 ± 0.000 [0.465, 0.593] ×1.08 | 0.542 ± 0.000 |
| change_level | complement | 32 | 17 | 0.531 | 0.525 | 0.845 ± 0.000 [0.505, 0.988] ×1.59 | 0.853 ± 0.000 |
| change_level | subset | 202 | 100 | 0.495 | 0.516 | 0.688 ± 0.000 [0.382, 0.869] ×1.39 | 0.680 ± 0.000 |

Subset minus complement per model (same test resamples):

| task | model | Δ PR-AUC [CI] | Δ lift [CI] | Δ ROC-AUC [CI] | Δ F1 [CI] | prevalence subset / complement | flags |
|---|---|---|---|---|---|---|---|
| add_log | naive_prior | +0.155 [+0.093, +0.212] | +0.009 [-0.051, +0.053] | +0.011 [-0.015, +0.039] | +0.066 [+0.028, +0.108] | 0.547 / 0.397 |  |
| add_log | hgb | +0.154 [+0.072, +0.233] | -0.109 [-0.299, +0.052] | +0.053 [-0.005, +0.113] | +0.191 [+0.122, +0.265] | 0.547 / 0.397 |  |
| remove_log | naive_prior | -0.107 [-0.201, -0.016] | -0.042 [-0.112, +0.010] | -0.024 [-0.057, +0.012] | -0.023 [-0.075, +0.034] | 0.488 / 0.570 |  |
| remove_log | hgb | -0.063 [-0.182, +0.056] | +0.046 [-0.127, +0.207] | +0.044 [-0.059, +0.147] | -0.075 [-0.148, +0.007] | 0.488 / 0.570 |  |
| change_level | naive_prior | -0.009 [-0.285, +0.235] | +0.054 [-0.335, +0.152] | +0.092 [+0.001, +0.183] | -0.046 [-0.185, +0.192] | 0.495 / 0.531 |  |
| change_level | hgb | -0.157 [-0.533, +0.234] | -0.201 [-1.432, +0.242] | -0.173 [-0.412, +0.068] | -0.051 [-0.266, +0.244] | 0.495 / 0.531 |  |

All models with p values, MC SE and B used: `tables/rq4_subset_gap_R1.csv`.

Context categories (mutually exclusive; pooled):

| task | ctx_category | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | frame_update | 228 | 92 | 0.404 | 0.425 | 0.533 ± 0.000 [0.436, 0.640] ×1.32 | 0.626 ± 0.000 |
| add_log | general | 559 | 222 | 0.397 | 0.398 | 0.567 ± 0.000 [0.492, 0.646] ×1.43 | 0.646 ± 0.000 |
| add_log | loop | 557 | 321 | 0.576 | 0.587 | 0.738 ± 0.000 [0.675, 0.799] ×1.28 | 0.714 ± 0.000 |
| add_log | subsystem | 446 | 260 | 0.583 | 0.583 | 0.741 ± 0.000 [0.681, 0.803] ×1.27 | 0.678 ± 0.000 |
| remove_log | frame_update | 182 | 113 | 0.621 | 0.627 | 0.569 ± 0.000 [0.474, 0.682] ×0.92 | 0.431 ± 0.000 |
| remove_log | general | 228 | 130 | 0.570 | 0.597 | 0.591 ± 0.000 [0.492, 0.698] ×1.04 | 0.497 ± 0.000 |
| remove_log | loop | 713 | 309 | 0.433 | 0.439 | 0.449 ± 0.000 [0.384, 0.520] ×1.04 | 0.514 ± 0.000 |
| remove_log | subsystem | 405 | 212 | 0.523 | 0.525 | 0.666 ± 0.000 [0.521, 0.780] ×1.27 | 0.618 ± 0.000 |
| change_level | frame_update | 6 | 3 | 0.500 | 0.693 | 0.411 ± 0.000 [0.200, 1.000] ×0.82 | 0.167 ± 0.000 |
| change_level | general | 32 | 17 | 0.531 | 0.525 | 0.845 ± 0.000 [0.505, 0.988] ×1.59 | 0.853 ± 0.000 |
| change_level | loop | 122 | 50 | 0.410 | 0.423 | 0.551 ± 0.000 [0.350, 0.737] ×1.34 | 0.649 ± 0.000 |
| change_level | subsystem | 74 | 47 | 0.635 | 0.679 | 0.839 ± 0.000 [0.315, 0.964] ×1.32 | 0.719 ± 0.000 |

Figure: `figures/rq4_ctx_category_R1_*`.

Subsystem markers, each on its own (descriptive; a method can carry several markers; markers with few positives give wide intervals):

| task | marker | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | input | 120 | 41 | 0.342 | 0.362 | 0.617 ± 0.000 [0.449, 0.784] ×1.80 | 0.733 ± 0.000 |
| add_log | network | 366 | 272 | 0.743 | 0.737 | 0.810 ± 0.000 [0.756, 0.863] ×1.09 | 0.609 ± 0.000 |
| add_log | physics | 43 | 19 | 0.442 | 0.510 | 0.558 ± 0.000 [0.353, 0.831] ×1.26 | 0.526 ± 0.000 |
| add_log | collision | 12 | 10 | 0.833 | 0.867 | 0.906 ± 0.000 [0.679, 1.000] ×1.09 | 0.650 ± 0.000 |
| add_log | animation | 19 | 10 | 0.526 | 0.622 | 0.878 ± 0.000 [0.658, 1.000] ×1.67 | 0.789 ± 0.000 |
| add_log | resource | 214 | 124 | 0.579 | 0.616 | 0.707 ± 0.000 [0.615, 0.794] ×1.22 | 0.622 ± 0.000 |
| remove_log | input | 69 | 38 | 0.551 | 0.575 | 0.839 ± 0.000 [0.383, 0.975] ×1.52 | 0.812 ± 0.000 |
| remove_log | network | 575 | 227 | 0.395 | 0.398 | 0.416 ± 0.000 [0.349, 0.500] ×1.05 | 0.541 ± 0.000 |
| remove_log | physics | 50 | 33 | 0.660 | 0.715 | 0.730 ± 0.000 [0.475, 0.919] ×1.11 | 0.529 ± 0.000 |
| remove_log | collision | 24 | 17 | 0.708 | 0.741 | 0.931 ± 0.000 [0.767, 0.995] ×1.31 | 0.828 ± 0.000 |
| remove_log | animation | 2 | 0 | 0.000 | – | – | – |
| remove_log | resource | 217 | 107 | 0.493 | 0.493 | 0.561 ± 0.000 [0.442, 0.681] ×1.14 | 0.541 ± 0.000 |
| change_level | input | 7 | 1 | 0.143 | 0.533 | 1.000 ± 0.000 [1.000, 1.000] ×7.00 | 1.000 ± 0.000 |
| change_level | network | 102 | 56 | 0.549 | 0.561 | 0.772 ± 0.000 [0.299, 0.943] ×1.41 | 0.717 ± 0.000 |
| change_level | physics | 2 | 2 | 1.000 | 1.000 | 1.000 ± 0.000 [1.000, 1.000] ×1.00 | – |
| change_level | collision | 4 | 2 | 0.500 | 0.783 | 0.500 ± 0.000 [0.286, 1.000] ×1.00 | 0.000 ± 0.000 |
| change_level | animation | 6 | 2 | 0.333 | 0.590 | 1.000 ± 0.000 [1.000, 1.000] ×3.00 | 1.000 ± 0.000 |
| change_level | resource | 49 | 28 | 0.571 | 0.613 | 0.635 ± 0.000 [0.195, 0.812] ×1.11 | 0.527 ± 0.000 |

Tables: `tables/rq4_subset_R1.csv`, `tables/rq4_subset_gap_R1.csv`, `tables/rq4_did_R1.csv`, `tables/rq4_did_frame_update_R1.csv`, `tables/rq4_ctx_category_R1.csv`, `tables/rq4_subsystem_markers_R1.csv`; error analysis in `error_analysis/` (confusion, disagreement sets, examples stratified by part and error `<task>_examples_R1.md`). Figures: `figures/rq4_forest_pr_auc_R1_*`, `figures/rq4_forest_f1_R1_*` (hollow markers: < 30 positives).

## 7. Ablations

Ablation models not available.

## 8. Statistical tests

Negative-ratio sensitivity, pooled PR-AUC (the prevalence differs by setting, so values are not comparable across columns without it; see `prevalence` in the table):

| key | R1 | R4 | R10 |
|---|---|---|---|
| add_log / naive_prior | 0.504 ± 0.007 [0.473, 0.536] | 0.206 ± 0.004 [0.190, 0.226] | 0.092 ± 0.002 [0.084, 0.102] |
| add_log / naive_size | 0.516 ± 0.000 [0.475, 0.560] | 0.212 ± 0.000 [0.192, 0.238] | 0.098 ± 0.000 [0.088, 0.112] |
| add_log / naive_rule | 0.571 ± 0.000 [0.529, 0.618] | 0.246 ± 0.000 [0.221, 0.279] | 0.118 ± 0.000 [0.103, 0.138] |
| add_log / lr | 0.586 ± 0.000 [0.550, 0.625] | 0.273 ± 0.000 [0.245, 0.306] | 0.131 ± 0.000 [0.114, 0.151] |
| add_log / rf | 0.703 ± 0.003 [0.665, 0.747] | 0.398 ± 0.005 [0.362, 0.443] | 0.197 ± 0.004 [0.173, 0.224] |
| add_log / hgb | 0.689 ± 0.000 [0.652, 0.731] | 0.404 ± 0.000 [0.366, 0.453] | 0.193 ± 0.000 [0.168, 0.220] |
| remove_log / naive_prior | 0.506 ± 0.016 [0.465, 0.549] | 0.202 ± 0.001 [0.177, 0.231] | 0.101 ± 0.004 [0.087, 0.119] |
| remove_log / naive_size | 0.437 ± 0.000 [0.379, 0.512] | 0.163 ± 0.000 [0.135, 0.204] | 0.076 ± 0.000 [0.062, 0.097] |
| remove_log / naive_rule | 0.509 ± 0.000 [0.417, 0.601] | 0.208 ± 0.000 [0.151, 0.292] | 0.102 ± 0.000 [0.071, 0.164] |
| remove_log / lr | 0.553 ± 0.000 [0.488, 0.627] | 0.252 ± 0.000 [0.198, 0.322] | 0.125 ± 0.000 [0.097, 0.170] |
| remove_log / rf | 0.604 ± 0.005 [0.554, 0.654] | 0.293 ± 0.004 [0.250, 0.341] | 0.182 ± 0.005 [0.153, 0.221] |
| remove_log / hgb | 0.540 ± 0.000 [0.484, 0.596] | 0.273 ± 0.000 [0.231, 0.322] | 0.150 ± 0.000 [0.119, 0.188] |
| change_level / naive_prior | 0.513 ± 0.022 [0.356, 0.655] | 0.217 ± 0.015 [0.134, 0.326] | 0.097 ± 0.003 [0.053, 0.154] |
| change_level / naive_size | 0.415 ± 0.000 [0.247, 0.589] | 0.150 ± 0.000 [0.080, 0.259] | 0.067 ± 0.000 [0.034, 0.131] |
| change_level / naive_rule | 0.593 ± 0.000 [0.493, 0.701] | 0.249 ± 0.000 [0.174, 0.355] | 0.112 ± 0.000 [0.073, 0.178] |
| change_level / lr | 0.626 ± 0.000 [0.414, 0.788] | 0.268 ± 0.000 [0.173, 0.380] | 0.113 ± 0.000 [0.063, 0.187] |
| change_level / rf | 0.732 ± 0.008 [0.460, 0.884] | 0.351 ± 0.007 [0.216, 0.500] | 0.188 ± 0.007 [0.101, 0.304] |
| change_level / hgb | 0.712 ± 0.000 [0.452, 0.876] | 0.295 ± 0.000 [0.164, 0.449] | 0.120 ± 0.000 [0.064, 0.213] |

Full table: `tables/sensitivity_ratio_R1.csv`.

## 9. Sensitivity analysis: ADD_LOG commit-time view (add_log_post)

No predictions for add_log_post; the sensitivity analysis was not run.

## 10. Post-hoc analysis: log1p preprocessing of tabular features (not pre-specified)

No predictions for the post-hoc models (lr_log1p, mlp_full_log1p, hybrid_ggnn_log1p).

## 11. Limitations of evidence

- Confidence intervals of single metrics use B = 1000 resamples, paired tests (pairwise, ablation, difference-in-differences, subset gaps) B = 10000. Bootstrap p-values cannot be smaller than 2/(B+1) = 0.00020; Holm-adjusted values are bounded below by that floor times the family size. The Monte-Carlo standard error of each p is reported next to it.
- RQ4 reference model: the difference-in-differences uses hgb as reference, fixed a priori, because choosing the best classical model on the test folds would be a post-hoc selection on test data. A reference chosen on validation PR-AUC is reported as a sensitivity check (section 6).
- PR-AUC depends on the prevalence; group comparisons (subset/complement, categories, engines, sizes, ecosystems, repositories) differ in prevalence and are read through lift and ROC-AUC.
- Pooled ranking metrics concatenate fold-specific models whose scores are not calibrated across folds; the macro values and the macro paired bootstrap are reported next to them.
- A bootstrap resample without a positive in the instances a value needs leaves that value undefined; such resamples are left out and every CI and test reports how many it used (b_used, B used). A macro value (CI, macro paired test, macro without few-commit folds) is defined only in the resamples in which every repository of the macro has a positive, so all its resamples estimate the same mean over the same repositories; the resamples left out are those in which a repository with positives from few commits drew none of them.
- Support floor: a comparison on a part with < 10 positives or positives from at most 2 commits (the few-commit rule of the folds) is descriptive only: Δ and CI are shown, without p, and it is not counted in its Holm family.
- add_log: test repositories OpenKeeper, Mindustry, subspace-infinity, riiablo, OpenRTS, SkyHussars; low-support folds (< 30 positives): SkyHussars; not a test fold (< 10 positives): shattered-pixel-dungeon (1), Archer-Game-Template2 (4), jme3rpg (7); few-commit folds: none.
- remove_log: test repositories OpenKeeper, Mindustry, subspace-infinity, riiablo, OpenRTS, SkyHussars, jme3rpg; low-support folds (< 30 positives): SkyHussars, jme3rpg; not a test fold (< 10 positives): shattered-pixel-dungeon (3), Archer-Game-Template2 (0); few-commit folds: none.
- change_level: test repositories OpenKeeper, Mindustry, subspace-infinity, riiablo; low-support folds (< 30 positives): OpenKeeper, subspace-infinity; not a test fold (< 10 positives): shattered-pixel-dungeon (0), OpenRTS (1), SkyHussars (1), Archer-Game-Template2 (0), jme3rpg (0); few-commit folds: OpenKeeper.
- add_log: evaluated repositories with < 30 positives: SkyHussars.
- change_level: evaluated repositories with < 30 positives: OpenKeeper, subspace-infinity.
- remove_log: evaluated repositories with < 30 positives: SkyHussars, jme3rpg.
- add_log: Wilcoxon over 6 test repositories; smallest attainable two-sided p = 0.0312.
- change_level: Wilcoxon over 4 test repositories; smallest attainable two-sided p = 0.1250.
- remove_log: Wilcoxon over 7 test repositories; smallest attainable two-sided p = 0.0156.
- add_log: no predictions for mlp_hist, mlp_full, gnn_rgcn, gnn_ggnn, hybrid_ggnn_nohist, hybrid_ggnn.
- remove_log: no predictions for mlp_hist, mlp_full, gnn_rgcn, gnn_ggnn, hybrid_ggnn_nohist, hybrid_ggnn.
- change_level: no predictions for mlp_hist, mlp_full, gnn_rgcn, gnn_ggnn, hybrid_ggnn_nohist, hybrid_ggnn.

Notices raised during evaluation:

- R1/add_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/remove_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/change_level: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/add_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/remove_log: RQ4 DiD needs hybrid_ggnn and rf, skipped
- R1/change_level: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/add_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/remove_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/change_level: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R1/add_log: hybrid_ggnn missing, ablation skipped
- R1/remove_log: hybrid_ggnn missing, ablation skipped
- R1/change_level: hybrid_ggnn missing, ablation skipped
- R1/add_log: comparison hybrid_ggnn vs hgb skipped (model missing)
- R1/add_log: comparison hybrid_ggnn vs rf skipped (model missing)
- R1/add_log: comparison hybrid_ggnn vs lr skipped (model missing)
- R1/add_log: comparison hybrid_ggnn vs mlp_full skipped (model missing)
- R1/add_log: comparison hybrid_ggnn vs naive_prior skipped (model missing)
- R1/add_log: comparison hybrid_ggnn vs naive_size skipped (model missing)
- R1/add_log: comparison hybrid_ggnn vs naive_rule skipped (model missing)
- R1/add_log: comparison gnn_ggnn vs hgb skipped (model missing)
- R1/add_log: comparison gnn_rgcn vs hgb skipped (model missing)
- R1/add_log: comparison gnn_ggnn vs gnn_rgcn skipped (model missing)
- R1/remove_log: comparison hybrid_ggnn vs hgb skipped (model missing)
- R1/remove_log: comparison hybrid_ggnn vs rf skipped (model missing)
- R1/remove_log: comparison hybrid_ggnn vs lr skipped (model missing)
- R1/remove_log: comparison hybrid_ggnn vs mlp_full skipped (model missing)
- R1/remove_log: comparison hybrid_ggnn vs naive_prior skipped (model missing)
- R1/remove_log: comparison hybrid_ggnn vs naive_size skipped (model missing)
- R1/remove_log: comparison hybrid_ggnn vs naive_rule skipped (model missing)
- R1/remove_log: comparison gnn_ggnn vs hgb skipped (model missing)
- R1/remove_log: comparison gnn_rgcn vs hgb skipped (model missing)
- R1/remove_log: comparison gnn_ggnn vs gnn_rgcn skipped (model missing)
- R1/change_level: comparison hybrid_ggnn vs hgb skipped (model missing)
- R1/change_level: comparison hybrid_ggnn vs rf skipped (model missing)
- R1/change_level: comparison hybrid_ggnn vs lr skipped (model missing)
- R1/change_level: comparison hybrid_ggnn vs mlp_full skipped (model missing)
- R1/change_level: comparison hybrid_ggnn vs naive_prior skipped (model missing)
- R1/change_level: comparison hybrid_ggnn vs naive_size skipped (model missing)
- R1/change_level: comparison hybrid_ggnn vs naive_rule skipped (model missing)
- R1/change_level: comparison gnn_ggnn vs hgb skipped (model missing)
- R1/change_level: comparison gnn_rgcn vs hgb skipped (model missing)
- R1/change_level: comparison gnn_ggnn vs gnn_rgcn skipped (model missing)
- R1/multiclass: no predictions, supplement skipped
- no permutation-importance CSVs (group level) for R1, table skipped
- no permutation-importance CSVs (feature level) for R1, table skipped
- R1/add_log_post: no predictions, sensitivity analysis skipped
- R1/add_log: error analysis needs hybrid_ggnn and hgb, skipped
- R1/remove_log: error analysis needs hybrid_ggnn and hgb, skipped
- R1/change_level: error analysis needs hybrid_ggnn and hgb, skipped
