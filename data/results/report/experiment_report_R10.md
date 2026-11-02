# Experiment report (R10)

Generated 2026-10-05T19:08:02-04:00. Paths are relative to `data/results/`. Protocol: leave-one-repository-out; metrics pooled over the test folds unless stated; mean ± sd over training seeds; 95% CI = percentile cluster bootstrap over commits within repositories (B = 1000, seed 42) of the seed mean; paired tests on B = 10000 resamples of the same clusters. Every table lists n (instances) and n_pos (positives). This report states measurements only. The primary analysis covers add_log (pre-state view), remove_log and change_level with the 12 pre-specified models; the commit-time view (add_log_post) and the post-hoc log1p models appear only in sections 9 and 10.

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

**RQ2 – can history and code structure model logging decisions?** Decisive: `tables/rq3_overall_pooled_R10.csv`, `tables/pairwise_R10.csv`, `tables/ablation_R10.csv`, `tables/rq2_importance_R10.csv`.

- add_log: highest pooled PR-AUC rf 0.197 ± 0.004 [0.173, 0.224] (prevalence 0.091; naive_rule 0.118 ± 0.000 [0.103, 0.138]).
- remove_log: highest pooled PR-AUC rf 0.182 ± 0.005 [0.153, 0.221] (prevalence 0.101; naive_rule 0.102 ± 0.000 [0.071, 0.164]).
- change_level: highest pooled PR-AUC rf 0.188 ± 0.007 [0.101, 0.304] (prevalence 0.091; naive_rule 0.112 ± 0.000 [0.073, 0.178]).

**RQ3 – graph-based models vs simpler baselines.** Decisive: `tables/pairwise_R10.csv`, `tables/rq3_overall_macro_R10.csv`, `tables/rq3_per_repo_R10.csv`; figures `figures/prauc_bars_R10_*`, `figures/prauc_heatmap_<task>_R10_*`.


**RQ4 – performance-sensitive code.** Decisive: `tables/rq4_did_R10.csv`, `tables/rq4_subset_R10.csv`; figure `figures/rq4_forest_pr_auc_R10_*`. Primary test: PR-AUC difference-in-differences (hybrid_ggnn − hgb, subset minus complement), Holm over the three tasks; a task with a part below the support floor (< 10 positives or positives from at most 2 commits) gets no p.

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
| add_log | OpenKeeper | 8 | 7218 / 656 | 1274 / 116 | 1485 / 135 | 88 | 0.14 |  |  |
| add_log | Mindustry | 8 | 4654 / 420 | 824 / 78 | 4499 / 409 | 338 | 0.01 |  |  |
| add_log | subspace-infinity | 8 | 7637 / 694 | 1350 / 123 | 990 / 90 | 49 | 0.09 |  |  |
| add_log | riiablo | 8 | 6741 / 607 | 1190 / 114 | 2046 / 186 | 121 | 0.05 |  |  |
| add_log | OpenRTS | 8 | 7928 / 720 | 1400 / 128 | 649 / 59 | 41 | 0.08 |  |  |
| add_log | SkyHussars | 8 | 8330 / 750 | 1471 / 141 | 176 / 16 | 14 | 0.12 |  | yes |
| remove_log | OpenKeeper | 7 | 6040 / 617 | 1081 / 109 | 451 / 41 | 27 | 0.10 |  |  |
| remove_log | Mindustry | 7 | 3395 / 375 | 602 / 67 | 3575 / 325 | 229 | 0.04 |  |  |
| remove_log | subspace-infinity | 7 | 5810 / 574 | 1028 / 102 | 734 / 91 | 39 | 0.10 |  |  |
| remove_log | riiablo | 7 | 4930 / 515 | 871 / 91 | 1771 / 161 | 40 | 0.18 |  |  |
| remove_log | OpenRTS | 7 | 5697 / 565 | 1006 / 100 | 869 / 102 | 39 | 0.25 |  |  |
| remove_log | SkyHussars | 7 | 6346 / 625 | 1121 / 113 | 105 / 29 | 16 | 0.21 |  | yes |
| remove_log | jme3rpg | 7 | 6381 / 628 | 1130 / 124 | 61 / 15 | 5 | 0.67 |  | yes |
| change_level | OpenKeeper | 5 | 850 / 77 | 151 / 14 | 308 / 28 | 2 | 0.96 | yes | yes |
| change_level | Mindustry | 5 | 805 / 73 | 152 / 14 | 352 / 32 | 14 | 0.28 |  |  |
| change_level | subspace-infinity | 5 | 904 / 61 | 163 / 36 | 242 / 22 | 9 | 0.36 |  | yes |
| change_level | riiablo | 5 | 783 / 46 | 141 / 38 | 385 / 35 | 12 | 0.43 |  |  |

Commit support source: folds.json (dataset stage: positives from at most 2 commits). A few-commit fold measures the model on very few independent logging decisions. Training repositories per fold: `tables/dq_folds_R10.csv`.

Evaluated instances (predictions aligned across models):

| task | n_models | n_union | n_evaluated_min | n_evaluated_max | n_partial | n_eval_set_mismatch |
|---|---|---|---|---|---|---|
| add_log | 6 | 9845 | 9845 | 9845 | 0 | 0 |
| change_level | 6 | 1287 | 1287 | 1287 | 0 | 0 |
| remove_log | 6 | 7566 | 7566 | 7566 | 0 | 0 |

Per model and seed: `tables/dq_coverage_R10.csv`.

Training runs (prediction sidecars; instances in the setting, evaluated, dropped for missing features or graph; number of distinct evaluation sets, eval_set_sha1, over the models):

| task | models | seeds | n_selected | n_eval | dropped no features | dropped no graph | eval sets | incomplete runs |
|---|---|---|---|---|---|---|---|---|
| add_log | 6 | 5-5 | 9977 | 9977 | 0 | 0 | 1 | none |
| remove_log | 6 | 5-5 | 7572 | 7572 | 0 | 0 | 1 | none |
| change_level | 6 | 5-5 | 1309 | 1309 | 0 | 0 | 1 | none |

Per model (seeds, seconds, epochs, thresholds): `tables/dq_training_R10.csv`.

Imbalance handling (negative sampling 10 negatives per positive per repository (seeded, nested); class weighting and threshold rule from the sidecars; threshold mean over tasks, folds and seeds):

| model | class_weighting | threshold_rule | threshold_mean |
|---|---|---|---|
| naive_prior | none (no training) | score < threshold (training prevalence) | 0.090 |
| naive_size | none (no training) | score >= threshold (F1-max on validation) | 20.964 |
| naive_rule | none (no training) | score >= threshold (F1-max on validation) | 0.673 |
| lr | class_weight=balanced | score >= threshold (F1-max on validation) | 0.501 |
| rf | class_weight=balanced_subsample | score >= threshold (F1-max on validation) | 0.148 |
| hgb | none (unweighted loss) | score >= threshold (F1-max on validation) | 0.128 |

Per task: `tables/dq_imbalance_R10.csv`. Hyperparameters (fixed a priori, except the `posthoc` section: post-hoc variants added on 2026-10-03, `prespecified` = False): `tables/config_hyperparameters.csv`. Hardware and software: `tables/env_manifest.csv`.

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
| naive_prior | 0.092 ± 0.002 [0.084, 0.102] | 0.101 ± 0.004 [0.087, 0.119] | 0.097 ± 0.003 [0.053, 0.154] |
| naive_size | 0.098 ± 0.000 [0.088, 0.112] | 0.076 ± 0.000 [0.062, 0.097] | 0.067 ± 0.000 [0.034, 0.131] |
| naive_rule | 0.118 ± 0.000 [0.103, 0.138] | 0.102 ± 0.000 [0.071, 0.164] | 0.112 ± 0.000 [0.073, 0.178] |
| hgb | 0.193 ± 0.000 [0.168, 0.220] | 0.150 ± 0.000 [0.119, 0.188] | 0.120 ± 0.000 [0.064, 0.213] |

Prevalence per task: add_log 0.091; change_level 0.091; remove_log 0.101.

Permutation importance: not available.

## 5. RQ3 - graph-based models vs simpler baselines

Pooled PR-AUC, all models:

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.092 ± 0.002 [0.084, 0.102] | 0.101 ± 0.004 [0.087, 0.119] | 0.097 ± 0.003 [0.053, 0.154] |
| naive_size | 0.098 ± 0.000 [0.088, 0.112] | 0.076 ± 0.000 [0.062, 0.097] | 0.067 ± 0.000 [0.034, 0.131] |
| naive_rule | 0.118 ± 0.000 [0.103, 0.138] | 0.102 ± 0.000 [0.071, 0.164] | 0.112 ± 0.000 [0.073, 0.178] |
| lr | 0.131 ± 0.000 [0.114, 0.151] | 0.125 ± 0.000 [0.097, 0.170] | 0.113 ± 0.000 [0.063, 0.187] |
| rf | 0.197 ± 0.004 [0.173, 0.224] | 0.182 ± 0.005 [0.153, 0.221] | 0.188 ± 0.007 [0.101, 0.304] |
| hgb | 0.193 ± 0.000 [0.168, 0.220] | 0.150 ± 0.000 [0.119, 0.188] | 0.120 ± 0.000 [0.064, 0.213] |

Pooled F1 (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.093 ± 0.011 [0.083, 0.102] | 0.105 ± 0.009 [0.092, 0.117] | 0.073 ± 0.035 [0.042, 0.100] |
| naive_size | 0.169 ± 0.000 [0.153, 0.187] | 0.146 ± 0.000 [0.120, 0.176] | 0.163 ± 0.000 [0.087, 0.245] |
| naive_rule | 0.168 ± 0.000 [0.152, 0.186] | 0.167 ± 0.000 [0.124, 0.217] | 0.160 ± 0.000 [0.086, 0.237] |
| lr | 0.183 ± 0.000 [0.157, 0.208] | 0.218 ± 0.000 [0.180, 0.259] | 0.155 ± 0.000 [0.082, 0.237] |
| rf | 0.308 ± 0.014 [0.282, 0.332] | 0.187 ± 0.003 [0.165, 0.210] | 0.198 ± 0.018 [0.127, 0.271] |
| hgb | 0.248 ± 0.000 [0.221, 0.276] | 0.238 ± 0.000 [0.205, 0.273] | 0.158 ± 0.000 [0.078, 0.247] |

Pooled precision (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.094 ± 0.011 [0.082, 0.106] | 0.102 ± 0.007 [0.084, 0.120] | 0.082 ± 0.036 [0.036, 0.137] |
| naive_size | 0.097 ± 0.000 [0.087, 0.108] | 0.086 ± 0.000 [0.070, 0.106] | 0.089 ± 0.000 [0.045, 0.140] |
| naive_rule | 0.097 ± 0.000 [0.087, 0.109] | 0.112 ± 0.000 [0.080, 0.149] | 0.093 ± 0.000 [0.049, 0.143] |
| lr | 0.142 ± 0.000 [0.120, 0.164] | 0.136 ± 0.000 [0.110, 0.166] | 0.092 ± 0.000 [0.047, 0.148] |
| rf | 0.244 ± 0.024 [0.221, 0.266] | 0.105 ± 0.002 [0.091, 0.119] | 0.114 ± 0.010 [0.069, 0.164] |
| hgb | 0.174 ± 0.000 [0.153, 0.197] | 0.169 ± 0.000 [0.142, 0.199] | 0.094 ± 0.000 [0.045, 0.153] |

Pooled recall (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.093 ± 0.011 [0.083, 0.102] | 0.108 ± 0.010 [0.098, 0.118] | 0.067 ± 0.034 [0.047, 0.084] |
| naive_size | 0.661 ± 0.000 [0.622, 0.704] | 0.475 ± 0.000 [0.396, 0.555] | 0.974 ± 0.000 [0.917, 1.000] |
| naive_rule | 0.627 ± 0.000 [0.581, 0.668] | 0.335 ± 0.000 [0.258, 0.418] | 0.556 ± 0.000 [0.302, 0.867] |
| lr | 0.257 ± 0.000 [0.222, 0.292] | 0.550 ± 0.000 [0.480, 0.615] | 0.504 ± 0.000 [0.298, 0.782] |
| rf | 0.427 ± 0.040 [0.390, 0.466] | 0.863 ± 0.058 [0.800, 0.920] | 0.754 ± 0.126 [0.573, 0.937] |
| hgb | 0.431 ± 0.000 [0.387, 0.472] | 0.402 ± 0.000 [0.338, 0.472] | 0.496 ± 0.000 [0.240, 0.770] |

Pooled ROC-AUC (mean ± sd over seeds):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.501 ± 0.013 | 0.502 ± 0.013 | 0.519 ± 0.013 |
| naive_size | 0.546 ± 0.000 | 0.366 ± 0.000 | 0.293 ± 0.000 |
| naive_rule | 0.566 ± 0.000 | 0.430 ± 0.000 | 0.514 ± 0.000 |
| lr | 0.556 ± 0.000 | 0.596 ± 0.000 | 0.600 ± 0.000 |
| rf | 0.707 ± 0.004 | 0.657 ± 0.009 | 0.688 ± 0.028 |
| hgb | 0.666 ± 0.000 | 0.633 ± 0.000 | 0.556 ± 0.000 |

n per task: add_log n=9845, n_pos=895; change_level n=1287, n_pos=117; remove_log n=7566, n_pos=764.

Macro PR-AUC (mean over the test repositories each model was evaluated on):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.102 ± 0.012 [0.092, 0.123] | 0.159 ± 0.017 [0.132, 0.211] | 0.105 ± 0.005 [0.069, 0.168] |
| naive_size | 0.128 ± 0.000 [0.109, 0.164] | 0.140 ± 0.000 [0.104, 0.217] | 0.076 ± 0.000 [0.042, 0.135] |
| naive_rule | 0.132 ± 0.000 [0.112, 0.172] | 0.177 ± 0.000 [0.121, 0.252] | 0.147 ± 0.000 [0.116, 0.437] |
| lr | 0.184 ± 0.000 [0.149, 0.234] | 0.190 ± 0.000 [0.137, 0.274] | 0.137 ± 0.000 [0.086, 0.223] |
| rf | 0.210 ± 0.005 [0.184, 0.259] | 0.222 ± 0.004 [0.182, 0.297] | 0.207 ± 0.007 [0.131, 0.309] |
| hgb | 0.213 ± 0.000 [0.184, 0.268] | 0.221 ± 0.000 [0.159, 0.294] | 0.163 ± 0.000 [0.091, 0.276] |

Macro CIs use only the resamples in which every repository of the macro has a positive (of B = 1000): add_log 1000; change_level 866; remove_log 995.

Macro PR-AUC with and without the few-commit folds (change_level: OpenKeeper):

| model | change_level all folds | change_level without few-commit folds |
|---|---|---|
| naive_prior | 0.105 ± 0.005 [0.069, 0.168] | 0.106 ± 0.010 [0.077, 0.165] |
| naive_size | 0.076 ± 0.000 [0.042, 0.135] | 0.081 ± 0.000 [0.045, 0.149] |
| naive_rule | 0.147 ± 0.000 [0.116, 0.437] | 0.151 ± 0.000 [0.103, 0.269] |
| lr | 0.137 ± 0.000 [0.086, 0.223] | 0.108 ± 0.000 [0.070, 0.173] |
| rf | 0.207 ± 0.007 [0.131, 0.309] | 0.197 ± 0.013 [0.120, 0.302] |
| hgb | 0.163 ± 0.000 [0.091, 0.276] | 0.181 ± 0.000 [0.101, 0.319] |

Table: `tables/rq3_overall_macro_no_few_commit_R10.csv`.

Per-repository prevalence differs from 1/(1+R) = 0.091 where a repository's negative pool is smaller than R × its positives: remove_log OpenRTS 0.117; remove_log SkyHussars 0.276; remove_log jme3rpg 0.246; remove_log subspace-infinity 0.124. Per-repository PR-AUC values (heatmaps, macro averages) are relative to these prevalences; the heatmap column labels give them.

Pooled metrics per engine (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | engine | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | jME | 3300 | 300 | 0.091 | 0.096 | 0.175 ± 0.000 [0.133, 0.224] ×1.92 | 0.657 ± 0.000 |
| add_log | libGDX | 6545 | 595 | 0.091 | 0.091 | 0.209 ± 0.000 [0.177, 0.247] ×2.30 | 0.674 ± 0.000 |
| remove_log | jME | 2220 | 278 | 0.125 | 0.130 | 0.192 ± 0.000 [0.133, 0.289] ×1.53 | 0.637 ± 0.000 |
| remove_log | libGDX | 5346 | 486 | 0.091 | 0.091 | 0.135 ± 0.000 [0.101, 0.185] ×1.49 | 0.628 ± 0.000 |
| change_level | jME | 550 | 50 | 0.091 | 0.101 | 0.112 ± 0.000 [0.027, 0.247] ×1.23 | 0.562 ± 0.000 |
| change_level | libGDX | 737 | 67 | 0.091 | 0.098 | 0.139 ± 0.000 [0.064, 0.261] ×1.53 | 0.588 ± 0.000 |

Pooled metrics per size (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | size | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | Large | 9020 | 820 | 0.091 | 0.092 | 0.192 ± 0.000 [0.167, 0.222] ×2.11 | 0.669 ± 0.000 |
| add_log | Medium | 825 | 75 | 0.091 | 0.099 | 0.241 ± 0.000 [0.153, 0.370] ×2.65 | 0.640 ± 0.000 |
| remove_log | Large | 6531 | 618 | 0.095 | 0.095 | 0.136 ± 0.000 [0.108, 0.178] ×1.44 | 0.617 ± 0.000 |
| remove_log | Medium | 1035 | 146 | 0.141 | 0.148 | 0.229 ± 0.000 [0.133, 0.379] ×1.62 | 0.695 ± 0.000 |
| change_level | Large | 1287 | 117 | 0.091 | 0.097 | 0.120 ± 0.000 [0.064, 0.213] ×1.32 | 0.556 ± 0.000 |

Pooled metrics per ecosystem (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | ecosystem | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | arc | 4499 | 409 | 0.091 | 0.091 | 0.197 ± 0.000 [0.164, 0.237] ×2.17 | 0.669 ± 0.000 |
| add_log | gdx | 2046 | 186 | 0.091 | 0.094 | 0.272 ± 0.000 [0.205, 0.351] ×2.99 | 0.721 ± 0.000 |
| add_log | jdk_system | 1485 | 135 | 0.091 | 0.102 | 0.196 ± 0.000 [0.141, 0.266] ×2.15 | 0.721 ± 0.000 |
| add_log | jul | 649 | 59 | 0.091 | 0.097 | 0.245 ± 0.000 [0.150, 0.392] ×2.69 | 0.626 ± 0.000 |
| add_log | slf4j | 1166 | 106 | 0.091 | 0.098 | 0.133 ± 0.000 [0.095, 0.192] ×1.47 | 0.607 ± 0.000 |
| remove_log | arc | 3575 | 325 | 0.091 | 0.092 | 0.174 ± 0.000 [0.140, 0.222] ×1.91 | 0.681 ± 0.000 |
| remove_log | gdx | 1771 | 161 | 0.091 | 0.091 | 0.138 ± 0.000 [0.073, 0.256] ×1.52 | 0.571 ± 0.000 |
| remove_log | jdk_system | 451 | 41 | 0.091 | 0.108 | 0.090 ± 0.000 [0.054, 0.161] ×0.99 | 0.483 ± 0.000 |
| remove_log | jul | 930 | 117 | 0.126 | 0.138 | 0.226 ± 0.000 [0.118, 0.397] ×1.80 | 0.712 ± 0.000 |
| remove_log | slf4j | 839 | 120 | 0.143 | 0.145 | 0.220 ± 0.000 [0.153, 0.320] ×1.54 | 0.615 ± 0.000 |
| change_level | arc | 352 | 32 | 0.091 | 0.113 | 0.152 ± 0.000 [0.051, 0.309] ×1.68 | 0.672 ± 0.000 |
| change_level | gdx | 385 | 35 | 0.091 | 0.096 | 0.149 ± 0.000 [0.047, 0.365] ×1.64 | 0.526 ± 0.000 |
| change_level | jdk_system | 308 | 28 | 0.091 | 0.102 | 0.110 ± 0.000 [0.009, 0.293] ×1.21 | 0.600 ± 0.000 |
| change_level | slf4j | 242 | 22 | 0.091 | 0.109 | 0.240 ± 0.000 [0.048, 0.568] ×2.64 | 0.452 ± 0.000 |

PR-AUC depends on the prevalence, which differs between groups (engines, sizes, ecosystems, subsets, categories): compare groups through the lift and ROC-AUC, not through raw PR-AUC.

Ecosystem = dominant formal logging framework per repository; source: rq1 snapshot.

Tables: `tables/rq3_overall_pooled_R10.csv`, `tables/rq3_overall_macro_R10.csv`, `tables/rq3_per_repo_R10.csv`, `tables/rq3_per_engine_R10.csv`, `tables/rq3_per_size_R10.csv`, `tables/rq3_per_ecosystem_R10.csv` (with French variants `*_fr.md`/`*_fr.tex` of the main tables). Figures: `figures/pr_curves_<task>_R10_*` (seed 0), `figures/prauc_bars_R10_*`, `figures/prauc_heatmap_<task>_R10_*`.

## 6. RQ4 - performance-sensitive code

Difference-in-differences: not available (needs hybrid_ggnn, hgb and d_is_perf_sensitive).

Sensitivity to the reference model: the primary reference is hgb, fixed a priori; as a check, the reference is also chosen without test information, as the classical model (lr, rf, hgb) with the highest mean validation PR-AUC over folds and seeds: add_log rf (0.347); remove_log hgb (0.250); change_level rf (0.299).

Validation PR-AUC per classical model: `tables/rq4_did_reference_validation_R10.csv`.

Subset coverage (share of the test instances in the performance-sensitive subset): add_log 64.1% of the instances, 75.2% of the positives; remove_log 85.9% of the instances, 83.0% of the positives; change_level 84.8% of the instances, 85.5% of the positives.

Subset and complement (pooled; prevalence differs between the parts, so compare lift and ROC-AUC):

| task | part | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | complement | 3537 | 222 | 0.063 | 0.065 | 0.159 ± 0.000 [0.119, 0.219] ×2.54 | 0.657 ± 0.000 |
| add_log | subset | 6308 | 673 | 0.107 | 0.108 | 0.205 ± 0.000 [0.176, 0.235] ×1.92 | 0.654 ± 0.000 |
| remove_log | complement | 1070 | 130 | 0.121 | 0.129 | 0.146 ± 0.000 [0.109, 0.199] ×1.21 | 0.591 ± 0.000 |
| remove_log | subset | 6496 | 634 | 0.098 | 0.098 | 0.151 ± 0.000 [0.114, 0.197] ×1.54 | 0.636 ± 0.000 |
| change_level | complement | 196 | 17 | 0.087 | 0.110 | 0.254 ± 0.000 [0.062, 0.518] ×2.93 | 0.749 ± 0.000 |
| change_level | subset | 1091 | 100 | 0.092 | 0.099 | 0.104 ± 0.000 [0.054, 0.193] ×1.14 | 0.523 ± 0.000 |

Subset minus complement per model (same test resamples):

| task | model | Δ PR-AUC [CI] | Δ lift [CI] | Δ ROC-AUC [CI] | Δ F1 [CI] | prevalence subset / complement | flags |
|---|---|---|---|---|---|---|---|
| add_log | naive_prior | +0.043 [+0.027, +0.057] | -0.029 [-0.141, +0.041] | +0.005 [-0.017, +0.026] | +0.021 [+0.004, +0.040] | 0.107 / 0.063 |  |
| add_log | hgb | +0.045 [-0.014, +0.095] | -0.622 [-1.520, +0.015] | -0.003 [-0.058, +0.053] | +0.057 [+0.004, +0.110] | 0.107 / 0.063 |  |
| remove_log | naive_prior | -0.032 [-0.070, -0.001] | -0.064 [-0.218, +0.017] | -0.013 [-0.043, +0.016] | -0.013 [-0.042, +0.017] | 0.098 / 0.121 |  |
| remove_log | hgb | +0.004 [-0.057, +0.062] | +0.336 [-0.102, +0.759] | +0.045 [-0.042, +0.130] | -0.050 [-0.125, +0.025] | 0.098 / 0.121 |  |
| change_level | naive_prior | -0.011 [-0.110, +0.063] | -0.188 [-1.716, +0.041] | +0.007 [-0.070, +0.069] | +0.044 [-0.003, +0.095] | 0.092 / 0.087 |  |
| change_level | hgb | -0.150 [-0.424, +0.062] | -1.790 [-4.693, -0.169] | -0.226 [-0.389, +0.094] | -0.080 [-0.269, +0.089] | 0.092 / 0.087 |  |

All models with p values, MC SE and B used: `tables/rq4_subset_gap_R10.csv`.

Context categories (mutually exclusive; pooled):

| task | ctx_category | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | frame_update | 1563 | 92 | 0.059 | 0.064 | 0.089 ± 0.000 [0.060, 0.149] ×1.52 | 0.524 ± 0.000 |
| add_log | general | 3537 | 222 | 0.063 | 0.065 | 0.159 ± 0.000 [0.119, 0.219] ×2.54 | 0.657 ± 0.000 |
| add_log | loop | 2676 | 321 | 0.120 | 0.120 | 0.233 ± 0.000 [0.194, 0.283] ×1.94 | 0.679 ± 0.000 |
| add_log | subsystem | 2069 | 260 | 0.126 | 0.131 | 0.223 ± 0.000 [0.181, 0.278] ×1.78 | 0.653 ± 0.000 |
| remove_log | frame_update | 477 | 113 | 0.237 | 0.257 | 0.243 ± 0.000 [0.189, 0.317] ×1.03 | 0.553 ± 0.000 |
| remove_log | general | 1070 | 130 | 0.121 | 0.129 | 0.146 ± 0.000 [0.109, 0.199] ×1.21 | 0.591 ± 0.000 |
| remove_log | loop | 4042 | 309 | 0.076 | 0.075 | 0.131 ± 0.000 [0.085, 0.201] ×1.71 | 0.619 ± 0.000 |
| remove_log | subsystem | 1977 | 212 | 0.107 | 0.112 | 0.149 ± 0.000 [0.097, 0.224] ×1.39 | 0.601 ± 0.000 |
| change_level | frame_update | 67 | 3 | 0.045 | 0.206 | 0.053 ± 0.000 [0.016, 0.135] ×1.18 | 0.195 ± 0.000 |
| change_level | general | 196 | 17 | 0.087 | 0.110 | 0.254 ± 0.000 [0.062, 0.518] ×2.93 | 0.749 ± 0.000 |
| change_level | loop | 650 | 50 | 0.077 | 0.084 | 0.126 ± 0.000 [0.056, 0.285] ×1.64 | 0.571 ± 0.000 |
| change_level | subsystem | 374 | 47 | 0.126 | 0.143 | 0.120 ± 0.000 [0.039, 0.237] ×0.95 | 0.492 ± 0.000 |

Figure: `figures/rq4_ctx_category_R10_*`.

Subsystem markers, each on its own (descriptive; a method can carry several markers; markers with few positives give wide intervals):

| task | marker | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC |
|---|---|---|---|---|---|---|---|
| add_log | input | 718 | 41 | 0.057 | 0.061 | 0.206 ± 0.000 [0.109, 0.349] ×3.61 | 0.714 ± 0.000 |
| add_log | network | 1216 | 272 | 0.224 | 0.230 | 0.305 ± 0.000 [0.255, 0.366] ×1.36 | 0.622 ± 0.000 |
| add_log | physics | 267 | 19 | 0.071 | 0.075 | 0.123 ± 0.000 [0.056, 0.292] ×1.73 | 0.566 ± 0.000 |
| add_log | collision | 73 | 10 | 0.137 | 0.155 | 0.256 ± 0.000 [0.077, 0.537] ×1.87 | 0.454 ± 0.000 |
| add_log | animation | 196 | 10 | 0.051 | 0.088 | 0.173 ± 0.000 [0.037, 0.441] ×3.39 | 0.640 ± 0.000 |
| add_log | resource | 1112 | 124 | 0.112 | 0.116 | 0.199 ± 0.000 [0.151, 0.266] ×1.79 | 0.636 ± 0.000 |
| remove_log | input | 294 | 38 | 0.129 | 0.149 | 0.291 ± 0.000 [0.103, 0.536] ×2.25 | 0.763 ± 0.000 |
| remove_log | network | 3380 | 227 | 0.067 | 0.069 | 0.134 ± 0.000 [0.077, 0.221] ×2.00 | 0.644 ± 0.000 |
| remove_log | physics | 89 | 33 | 0.371 | 0.409 | 0.392 ± 0.000 [0.255, 0.584] ×1.06 | 0.508 ± 0.000 |
| remove_log | collision | 78 | 17 | 0.218 | 0.262 | 0.432 ± 0.000 [0.144, 0.778] ×1.98 | 0.590 ± 0.000 |
| remove_log | animation | 47 | 0 | 0.000 | – | – | – |
| remove_log | resource | 1084 | 107 | 0.099 | 0.108 | 0.110 ± 0.000 [0.079, 0.166] ×1.11 | 0.487 ± 0.000 |
| change_level | input | 56 | 1 | 0.018 | 0.083 | 0.029 ± 0.000 [0.020, 0.113] ×1.65 | 0.400 ± 0.000 |
| change_level | network | 556 | 56 | 0.101 | 0.114 | 0.103 ± 0.000 [0.039, 0.219] ×1.02 | 0.477 ± 0.000 |
| change_level | physics | 6 | 2 | 0.333 | 0.555 | 0.333 ± 0.000 [0.167, 1.000] ×1.00 | 0.000 ± 0.000 |
| change_level | collision | 14 | 2 | 0.143 | 0.284 | 0.750 ± 0.000 [0.625, 1.000] ×5.25 | 0.938 ± 0.000 |
| change_level | animation | 16 | 2 | 0.125 | 0.320 | 0.333 ± 0.000 [0.200, 0.800] ×2.67 | 0.714 ± 0.000 |
| change_level | resource | 195 | 28 | 0.144 | 0.165 | 0.202 ± 0.000 [0.042, 0.446] ×1.41 | 0.558 ± 0.000 |

Tables: `tables/rq4_subset_R10.csv`, `tables/rq4_subset_gap_R10.csv`, `tables/rq4_did_R10.csv`, `tables/rq4_did_frame_update_R10.csv`, `tables/rq4_ctx_category_R10.csv`, `tables/rq4_subsystem_markers_R10.csv`; error analysis in `error_analysis/` (confusion, disagreement sets, examples stratified by part and error `<task>_examples_R10.md`). Figures: `figures/rq4_forest_pr_auc_R10_*`, `figures/rq4_forest_f1_R10_*` (hollow markers: < 30 positives).

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

Full table: `tables/sensitivity_ratio_R10.csv`.

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

- R10/add_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R10/remove_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R10/change_level: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R10/add_log: RQ4 DiD needs hybrid_ggnn and rf, skipped
- R10/remove_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R10/change_level: RQ4 DiD needs hybrid_ggnn and rf, skipped
- R10/add_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R10/remove_log: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R10/change_level: RQ4 DiD needs hybrid_ggnn and hgb, skipped
- R10/add_log: hybrid_ggnn missing, ablation skipped
- R10/remove_log: hybrid_ggnn missing, ablation skipped
- R10/change_level: hybrid_ggnn missing, ablation skipped
- R10/add_log: comparison hybrid_ggnn vs hgb skipped (model missing)
- R10/add_log: comparison hybrid_ggnn vs rf skipped (model missing)
- R10/add_log: comparison hybrid_ggnn vs lr skipped (model missing)
- R10/add_log: comparison hybrid_ggnn vs mlp_full skipped (model missing)
- R10/add_log: comparison hybrid_ggnn vs naive_prior skipped (model missing)
- R10/add_log: comparison hybrid_ggnn vs naive_size skipped (model missing)
- R10/add_log: comparison hybrid_ggnn vs naive_rule skipped (model missing)
- R10/add_log: comparison gnn_ggnn vs hgb skipped (model missing)
- R10/add_log: comparison gnn_rgcn vs hgb skipped (model missing)
- R10/add_log: comparison gnn_ggnn vs gnn_rgcn skipped (model missing)
- R10/remove_log: comparison hybrid_ggnn vs hgb skipped (model missing)
- R10/remove_log: comparison hybrid_ggnn vs rf skipped (model missing)
- R10/remove_log: comparison hybrid_ggnn vs lr skipped (model missing)
- R10/remove_log: comparison hybrid_ggnn vs mlp_full skipped (model missing)
- R10/remove_log: comparison hybrid_ggnn vs naive_prior skipped (model missing)
- R10/remove_log: comparison hybrid_ggnn vs naive_size skipped (model missing)
- R10/remove_log: comparison hybrid_ggnn vs naive_rule skipped (model missing)
- R10/remove_log: comparison gnn_ggnn vs hgb skipped (model missing)
- R10/remove_log: comparison gnn_rgcn vs hgb skipped (model missing)
- R10/remove_log: comparison gnn_ggnn vs gnn_rgcn skipped (model missing)
- R10/change_level: comparison hybrid_ggnn vs hgb skipped (model missing)
- R10/change_level: comparison hybrid_ggnn vs rf skipped (model missing)
- R10/change_level: comparison hybrid_ggnn vs lr skipped (model missing)
- R10/change_level: comparison hybrid_ggnn vs mlp_full skipped (model missing)
- R10/change_level: comparison hybrid_ggnn vs naive_prior skipped (model missing)
- R10/change_level: comparison hybrid_ggnn vs naive_size skipped (model missing)
- R10/change_level: comparison hybrid_ggnn vs naive_rule skipped (model missing)
- R10/change_level: comparison gnn_ggnn vs hgb skipped (model missing)
- R10/change_level: comparison gnn_rgcn vs hgb skipped (model missing)
- R10/change_level: comparison gnn_ggnn vs gnn_rgcn skipped (model missing)
- R10/multiclass: no predictions, supplement skipped
- no permutation-importance CSVs (group level) for R10, table skipped
- no permutation-importance CSVs (feature level) for R10, table skipped
- R10/add_log_post: no predictions, sensitivity analysis skipped
- R10/add_log: error analysis needs hybrid_ggnn and hgb, skipped
- R10/remove_log: error analysis needs hybrid_ggnn and hgb, skipped
- R10/change_level: error analysis needs hybrid_ggnn and hgb, skipped
