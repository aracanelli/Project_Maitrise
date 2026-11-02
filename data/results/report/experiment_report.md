# Experiment report (R4)

Generated 2026-10-05T19:12:22-04:00. Paths are relative to `data/results/`. Protocol: leave-one-repository-out; metrics pooled over the test folds unless stated; mean ± sd over training seeds; 95% CI = percentile cluster bootstrap over commits within repositories (B = 1000, seed 42) of the seed mean; paired tests on B = 10000 resamples of the same clusters. Every table lists n (instances) and n_pos (positives). This report states measurements only. The primary analysis covers add_log (pre-state view), remove_log and change_level with the 12 pre-specified models; the commit-time view (add_log_post) and the post-hoc log1p models appear only in sections 9 and 10.

## Models available

- add_log: naive_prior, naive_size, naive_rule, lr, rf, hgb, mlp_hist, mlp_full, gnn_rgcn, gnn_ggnn, hybrid_ggnn_nohist, hybrid_ggnn
- remove_log: naive_prior, naive_size, naive_rule, lr, rf, hgb, mlp_hist, mlp_full, gnn_rgcn, gnn_ggnn, hybrid_ggnn_nohist, hybrid_ggnn
- change_level: naive_prior, naive_size, naive_rule, lr, rf, hgb, mlp_hist, mlp_full, gnn_rgcn, gnn_ggnn, hybrid_ggnn_nohist, hybrid_ggnn
- sensitivity add_log_post: naive_prior, naive_size, naive_rule, lr, rf, hgb, mlp_hist, mlp_full, gnn_rgcn, gnn_ggnn, hybrid_ggnn_nohist, hybrid_ggnn
- post-hoc (add_log): hybrid_ggnn_log1p, lr_log1p, mlp_full_log1p
- post-hoc (remove_log): hybrid_ggnn_log1p, lr_log1p, mlp_full_log1p
- post-hoc (change_level): hybrid_ggnn_log1p, lr_log1p, mlp_full_log1p

## 1. Summary by research question

Measured values only, primary tasks and primary models. Δ = A − B; 95% CI = commit-cluster bootstrap; p = paired bootstrap on the test resamples, Holm-adjusted within the family named. The sensitivity task add_log_post (section 9) and the post-hoc log1p models (section 10) are not used here.

**RQ1 – logging practices and their evolution.** Decisive: `tables/rq1_event_rates.csv`, `tables/rq1_events_per_year.csv`, `tables/rq1_transitions.csv`, `tables/dq_extraction_precision.csv`; figures `figures/rq1_core_events_*`, `figures/rq1_events_per_year_*`, `figures/rq1_change_level_heatmap_*`.

- Core events: ADD_LOG 1225, REMOVE_LOG 767, CHANGE_LEVEL 119 in 9 repositories (32588 non-merge commits); core events per 1,000 non-merge commits from 0.6 (shattered-pixel-dungeon) to 501.1 (OpenRTS).
- Most frequent CHANGE_LEVEL transitions (n = 119): INFO→DEBUG 39; TRACE→DEBUG 28; DEBUG→TRACE 22.
- Extraction precision (annotation, 120 of 120 sampled events; `?` excluded): 0.915, the label precisions weighted by their shares of the core events (bootstrap of commits within labels, 95% CI [0.857, 0.964]); with `?` counted as wrong 0.915. Per label (Wilson 95% CI): ADD_LOG 0.950 [0.835, 0.986] (n=40); REMOVE_LOG 0.850 [0.709, 0.929] (n=40); CHANGE_LEVEL 0.975 [0.871, 0.996] (n=40).

**RQ2 – can history and code structure model logging decisions?** Decisive: `tables/rq3_overall_pooled.csv`, `tables/pairwise.csv`, `tables/ablation.csv`, `tables/rq2_importance.csv`.

- add_log: highest pooled PR-AUC hgb 0.404 ± 0.000 [0.366, 0.453] (prevalence 0.200; naive_rule 0.246 ± 0.000 [0.221, 0.279]); hybrid_ggnn − naive_rule Δ PR-AUC +0.085 [+0.055, +0.115], p Holm 0.002; no-history − full Δ PR-AUC +0.005 [-0.008, +0.018], p Holm 1.000; history-only − full Δ PR-AUC +0.054 [+0.024, +0.085], p Holm 0.002; top feature group (hgb) history 0.093 ± 0.077.
- remove_log: highest pooled PR-AUC rf 0.293 ± 0.004 [0.250, 0.341] (prevalence 0.203; naive_rule 0.208 ± 0.000 [0.151, 0.292]); hybrid_ggnn − naive_rule Δ PR-AUC +0.063 [-0.026, +0.129], p Holm 1.000; no-history − full Δ PR-AUC -0.010 [-0.054, +0.030], p Holm 1.000; history-only − full Δ PR-AUC -0.045 [-0.092, -0.002], p Holm 0.251; top feature group (hgb) lexical 0.022 ± 0.033.
- change_level: highest pooled PR-AUC hybrid_ggnn_nohist 0.432 ± 0.106 [0.235, 0.600] (prevalence 0.200; naive_rule 0.249 ± 0.000 [0.174, 0.355]); hybrid_ggnn − naive_rule Δ PR-AUC +0.103 [-0.033, +0.197], p Holm 0.809; no-history − full Δ PR-AUC +0.080 [-0.003, +0.137], p Holm 0.573; history-only − full Δ PR-AUC -0.084 [-0.181, +0.055], p Holm 1.000; top feature group (hgb) method 0.040 ± 0.066.

**RQ3 – graph-based models vs simpler baselines.** Decisive: `tables/pairwise.csv`, `tables/rq3_overall_macro.csv`, `tables/rq3_per_repo.csv`; figures `figures/prauc_bars_*`, `figures/prauc_heatmap_<task>_*`.

- add_log: hybrid_ggnn − hgb pooled Δ PR-AUC -0.073 [-0.099, -0.049] (p Holm 0.002), macro Δ -0.086 [-0.118, -0.043] (p Holm 0.002), Wilcoxon p 0.094 (n=6); gnn_ggnn − hgb pooled Δ PR-AUC -0.037 [-0.065, -0.011] (p Holm 0.014), macro Δ -0.069 [-0.104, -0.023] (p Holm 0.012), Wilcoxon p 0.156 (n=6).
- remove_log: hybrid_ggnn − hgb pooled Δ PR-AUC -0.001 [-0.048, +0.049] (p Holm 1.000), macro Δ +0.022 [-0.030, +0.066] (p Holm 1.000; 9972 of 10000 resamples with a positive in every repository), Wilcoxon p 0.469 (n=7); gnn_ggnn − hgb pooled Δ PR-AUC -0.023 [-0.072, +0.024] (p Holm 1.000), macro Δ -0.006 [-0.063, +0.031] (p Holm 1.000; 9972 of 10000 resamples with a positive in every repository), Wilcoxon p 0.938 (n=7).
- change_level: hybrid_ggnn − hgb pooled Δ PR-AUC +0.058 [-0.083, +0.162] (p Holm 1.000), macro Δ +0.131 [+0.020, +0.192] (p Holm 0.093; 8704 of 10000 resamples with a positive in every repository), macro Δ without the few-commit folds (OpenKeeper) +0.024 [-0.040, +0.110] (p Holm 1.000), Wilcoxon p 0.375 (n=4); gnn_ggnn − hgb pooled Δ PR-AUC +0.058 [-0.129, +0.204] (p Holm 1.000), macro Δ +0.054 [-0.018, +0.113] (p Holm 0.895; 8704 of 10000 resamples with a positive in every repository), macro Δ without the few-commit folds (OpenKeeper) +0.027 [-0.051, +0.108] (p Holm 1.000), Wilcoxon p 0.625 (n=4).

**RQ4 – performance-sensitive code.** Decisive: `tables/rq4_did.csv`, `tables/rq4_subset.csv`; figure `figures/rq4_forest_pr_auc_*`. Primary test: PR-AUC difference-in-differences (hybrid_ggnn − hgb, subset minus complement), Holm over the three tasks; a task with a part below the support floor (< 10 positives or positives from at most 2 commits) gets no p.

- add_log: PR-AUC DiD +0.016 [-0.039, +0.072], p 0.567, p Holm 1.000 (n_pos subset 673, complement 222); F1 DiD +0.055 [-0.001, +0.110], p Holm 0.109.
- remove_log: PR-AUC DiD +0.042 [-0.052, +0.135], p 0.366, p Holm 1.000 (n_pos subset 634, complement 130); F1 DiD +0.055 [-0.003, +0.111], p Holm 0.109.
- change_level: PR-AUC DiD +0.044 [-0.221, +0.305], p 0.756, p Holm 1.000 (n_pos subset 100, complement 17); F1 DiD -0.273 [-0.439, -0.065], p Holm 0.047 – exploratory, < 30 positives in the complement.

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
| add_log | OpenKeeper | 8 | 3281 / 656 | 579 / 116 | 675 / 135 | 88 | 0.14 |  |  |
| add_log | Mindustry | 8 | 2115 / 423 | 375 / 75 | 2045 / 409 | 338 | 0.01 |  |  |
| add_log | subspace-infinity | 8 | 3472 / 694 | 613 / 123 | 450 / 90 | 49 | 0.09 |  |  |
| add_log | riiablo | 8 | 3064 / 612 | 541 / 109 | 930 / 186 | 121 | 0.05 |  |  |
| add_log | OpenRTS | 8 | 3604 / 719 | 636 / 129 | 295 / 59 | 41 | 0.08 |  |  |
| add_log | SkyHussars | 8 | 3785 / 745 | 670 / 146 | 80 / 16 | 14 | 0.12 |  | yes |
| remove_log | OpenKeeper | 7 | 3030 / 600 | 537 / 126 | 205 / 41 | 27 | 0.10 |  |  |
| remove_log | Mindustry | 7 | 1824 / 359 | 323 / 83 | 1625 / 325 | 229 | 0.04 |  |  |
| remove_log | subspace-infinity | 7 | 2817 / 574 | 500 / 102 | 455 / 91 | 39 | 0.10 |  |  |
| remove_log | riiablo | 7 | 2521 / 515 | 446 / 91 | 805 / 161 | 40 | 0.18 |  |  |
| remove_log | OpenRTS | 7 | 2772 / 564 | 490 / 101 | 510 / 102 | 39 | 0.25 |  |  |
| remove_log | SkyHussars | 7 | 3114 / 627 | 553 / 111 | 105 / 29 | 16 | 0.21 |  | yes |
| remove_log | jme3rpg | 7 | 3154 / 639 | 557 / 113 | 61 / 15 | 5 | 0.67 |  | yes |
| change_level | OpenKeeper | 5 | 386 / 75 | 69 / 16 | 140 / 28 | 2 | 0.96 | yes | yes |
| change_level | Mindustry | 5 | 369 / 73 | 66 / 14 | 160 / 32 | 14 | 0.28 |  |  |
| change_level | subspace-infinity | 5 | 412 / 82 | 73 / 15 | 110 / 22 | 9 | 0.36 |  | yes |
| change_level | riiablo | 5 | 357 / 71 | 63 / 13 | 175 / 35 | 12 | 0.43 |  |  |

Commit support source: folds.json (dataset stage: positives from at most 2 commits). A few-commit fold measures the model on very few independent logging decisions. Training repositories per fold: `tables/dq_folds.csv`.

Evaluated instances (predictions aligned across models):

| task | n_models | n_union | n_evaluated_min | n_evaluated_max | n_partial | n_eval_set_mismatch |
|---|---|---|---|---|---|---|
| add_log | 12 | 4475 | 4475 | 4475 | 0 | 0 |
| change_level | 12 | 585 | 585 | 585 | 0 | 0 |
| remove_log | 12 | 3766 | 3766 | 3766 | 0 | 0 |

Per model and seed: `tables/dq_coverage.csv`.

Training runs (prediction sidecars; instances in the setting, evaluated, dropped for missing features or graph; number of distinct evaluation sets, eval_set_sha1, over the models):

| task | models | seeds | n_selected | n_eval | dropped no features | dropped no graph | eval sets | incomplete runs |
|---|---|---|---|---|---|---|---|---|
| add_log | 12 | 5-5 | 4535 | 4535 | 0 | 0 | 1 | none |
| remove_log | 12 | 5-5 | 3772 | 3772 | 0 | 0 | 1 | none |
| change_level | 12 | 5-5 | 595 | 595 | 0 | 0 | 1 | none |
| multiclass | 2 | 5-5 | 7185 | 7185 | 0 | 0 | 1 | none |

Per model (seeds, seconds, epochs, thresholds): `tables/dq_training.csv`.

Imbalance handling (negative sampling 4 negatives per positive per repository (seeded, nested); class weighting and threshold rule from the sidecars; threshold mean over tasks, folds and seeds):

| model | class_weighting | threshold_rule | threshold_mean |
|---|---|---|---|
| naive_prior | none (no training) | score < threshold (training prevalence) | 0.199 |
| naive_size | none (no training) | score >= threshold (F1-max on validation) | 8.516 |
| naive_rule | none (no training) | score >= threshold (F1-max on validation) | 0.544 |
| lr | class_weight=balanced | score >= threshold (F1-max on validation) | 0.299 |
| rf | class_weight=balanced_subsample | score >= threshold (F1-max on validation) | 0.219 |
| hgb | none (unweighted loss) | score >= threshold (F1-max on validation) | 0.175 |
| mlp_hist | pos_weight=balanced (n_neg/n_pos of the fit part) | score >= threshold (F1-max on validation) | 0.491 |
| mlp_full | pos_weight=balanced (n_neg/n_pos of the fit part) | score >= threshold (F1-max on validation) | 0.479 |
| gnn_rgcn | pos_weight=balanced (n_neg/n_pos of the fit part) | score >= threshold (F1-max on validation) | 0.447 |
| gnn_ggnn | pos_weight=balanced (n_neg/n_pos of the fit part) | score >= threshold (F1-max on validation) | 0.499 |
| hybrid_ggnn_nohist | pos_weight=balanced (n_neg/n_pos of the fit part) | score >= threshold (F1-max on validation) | 0.475 |
| hybrid_ggnn | pos_weight=balanced (n_neg/n_pos of the fit part) | score >= threshold (F1-max on validation) | 0.457 |

Per task: `tables/dq_imbalance.csv`. Hyperparameters (fixed a priori, except the `posthoc` section: post-hoc variants added on 2026-10-03, `prespecified` = False): `tables/config_hyperparameters.csv`. Hardware and software: `tables/env_manifest.csv`.

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
| naive_prior | 0.206 ± 0.004 [0.190, 0.226] | 0.202 ± 0.001 [0.177, 0.231] | 0.217 ± 0.015 [0.134, 0.326] |
| naive_size | 0.212 ± 0.000 [0.192, 0.238] | 0.163 ± 0.000 [0.135, 0.204] | 0.150 ± 0.000 [0.080, 0.259] |
| naive_rule | 0.246 ± 0.000 [0.221, 0.279] | 0.208 ± 0.000 [0.151, 0.292] | 0.249 ± 0.000 [0.174, 0.355] |
| hgb | 0.404 ± 0.000 [0.366, 0.453] | 0.273 ± 0.000 [0.231, 0.322] | 0.295 ± 0.000 [0.164, 0.449] |
| mlp_hist | 0.385 ± 0.009 [0.346, 0.431] | 0.227 ± 0.005 [0.197, 0.262] | 0.268 ± 0.026 [0.172, 0.419] |
| gnn_ggnn | 0.367 ± 0.018 [0.337, 0.405] | 0.250 ± 0.016 [0.209, 0.302] | 0.353 ± 0.039 [0.203, 0.526] |
| hybrid_ggnn | 0.331 ± 0.046 [0.301, 0.367] | 0.272 ± 0.016 [0.221, 0.338] | 0.352 ± 0.043 [0.225, 0.493] |

Prevalence per task: add_log 0.200; change_level 0.200; remove_log 0.203.

Feature groups: `h_` history, `f_` file, `m_` method, `l_` logging context, `s_` statement, `d_` domain, `x_` lexical (the 128 `x_` buckets are hashed identifier subtokens and are read as one lexical group). Top-3 groups by permutation importance (drop in average precision when the group is permuted jointly; mean ± sd over folds):

- add_log / hgb: history 0.093 ± 0.077 (folds=6); file 0.074 ± 0.099 (folds=6); logging context 0.038 ± 0.073 (folds=6)
- change_level / hgb: method 0.040 ± 0.066 (folds=4); file 0.031 ± 0.025 (folds=4); logging context 0.030 ± 0.055 (folds=4)
- remove_log / hgb: lexical 0.022 ± 0.033 (folds=7); logging context 0.012 ± 0.015 (folds=7); method 0.011 ± 0.022 (folds=7)

Full table: `tables/rq2_importance.csv`.

Top-5 non-lexical single features by permutation importance; the lexical buckets are summarised as one group (their single-bucket drops are not interpretable one by one):

- add_log / hgb: f_log_density (file) 0.070 ± 0.072; h_method_prior_log_events (history) 0.047 ± 0.052; l_log_density (logging context) 0.027 ± 0.058; h_repo_prior_log_event_rate (history) 0.026 ± 0.048; h_author_prior_log_events (history) 0.007 ± 0.007; lexical group: 2 of the top 15 single features are `x_` buckets (best rank 5), group drop -0.001 ± 0.024
- change_level / hgb: m_loc (method) 0.026 ± 0.040; h_author_prior_commits (history) 0.021 ± 0.030; l_log_density (logging context) 0.018 ± 0.031; m_n_statements (method) 0.017 ± 0.033; h_author_prior_log_events (history) 0.017 ± 0.022; lexical group: 1 of the top 15 single features are `x_` buckets (best rank 2), group drop 0.026 ± 0.055
- remove_log / hgb: h_author_prior_commits (history) 0.016 ± 0.023; l_log_density (logging context) 0.011 ± 0.011; f_log_density (file) 0.009 ± 0.012; m_n_calls (method) 0.007 ± 0.011; s_level_INFO (statement) 0.007 ± 0.012; lexical group: 8 of the top 15 single features are `x_` buckets (best rank 3), group drop 0.022 ± 0.033

Top 15: `tables/rq2_importance_features.csv`.

## 5. RQ3 - graph-based models vs simpler baselines

Pooled PR-AUC, all models:

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.206 ± 0.004 [0.190, 0.226] | 0.202 ± 0.001 [0.177, 0.231] | 0.217 ± 0.015 [0.134, 0.326] |
| naive_size | 0.212 ± 0.000 [0.192, 0.238] | 0.163 ± 0.000 [0.135, 0.204] | 0.150 ± 0.000 [0.080, 0.259] |
| naive_rule | 0.246 ± 0.000 [0.221, 0.279] | 0.208 ± 0.000 [0.151, 0.292] | 0.249 ± 0.000 [0.174, 0.355] |
| lr | 0.273 ± 0.000 [0.245, 0.306] | 0.252 ± 0.000 [0.198, 0.322] | 0.268 ± 0.000 [0.173, 0.380] |
| rf | 0.398 ± 0.005 [0.362, 0.443] | 0.293 ± 0.004 [0.250, 0.341] | 0.351 ± 0.007 [0.216, 0.500] |
| hgb | 0.404 ± 0.000 [0.366, 0.453] | 0.273 ± 0.000 [0.231, 0.322] | 0.295 ± 0.000 [0.164, 0.449] |
| mlp_hist | 0.385 ± 0.009 [0.346, 0.431] | 0.227 ± 0.005 [0.197, 0.262] | 0.268 ± 0.026 [0.172, 0.419] |
| mlp_full | 0.331 ± 0.012 [0.300, 0.369] | 0.268 ± 0.009 [0.222, 0.326] | 0.311 ± 0.033 [0.194, 0.450] |
| gnn_rgcn | 0.363 ± 0.031 [0.333, 0.399] | 0.239 ± 0.008 [0.204, 0.279] | 0.288 ± 0.016 [0.181, 0.418] |
| gnn_ggnn | 0.367 ± 0.018 [0.337, 0.405] | 0.250 ± 0.016 [0.209, 0.302] | 0.353 ± 0.039 [0.203, 0.526] |
| hybrid_ggnn_nohist | 0.336 ± 0.035 [0.308, 0.369] | 0.262 ± 0.013 [0.213, 0.334] | 0.432 ± 0.106 [0.235, 0.600] |
| hybrid_ggnn | 0.331 ± 0.046 [0.301, 0.367] | 0.272 ± 0.016 [0.221, 0.338] | 0.352 ± 0.043 [0.225, 0.493] |

Pooled F1 (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.188 ± 0.014 [0.175, 0.202] | 0.201 ± 0.014 [0.182, 0.218] | 0.192 ± 0.054 [0.138, 0.230] |
| naive_size | 0.324 ± 0.000 [0.298, 0.353] | 0.314 ± 0.000 [0.275, 0.352] | 0.313 ± 0.000 [0.191, 0.430] |
| naive_rule | 0.330 ± 0.000 [0.304, 0.358] | 0.279 ± 0.000 [0.229, 0.328] | 0.246 ± 0.000 [0.156, 0.339] |
| lr | 0.288 ± 0.000 [0.256, 0.320] | 0.358 ± 0.000 [0.311, 0.411] | 0.453 ± 0.000 [0.291, 0.579] |
| rf | 0.442 ± 0.038 [0.412, 0.471] | 0.361 ± 0.009 [0.321, 0.400] | 0.372 ± 0.016 [0.207, 0.523] |
| hgb | 0.398 ± 0.000 [0.366, 0.431] | 0.357 ± 0.000 [0.319, 0.396] | 0.383 ± 0.000 [0.234, 0.524] |
| mlp_hist | 0.404 ± 0.019 [0.363, 0.444] | 0.247 ± 0.054 [0.209, 0.282] | 0.288 ± 0.044 [0.181, 0.402] |
| mlp_full | 0.367 ± 0.037 [0.339, 0.397] | 0.359 ± 0.011 [0.315, 0.407] | 0.439 ± 0.055 [0.258, 0.604] |
| gnn_rgcn | 0.462 ± 0.013 [0.431, 0.491] | 0.346 ± 0.016 [0.313, 0.381] | 0.366 ± 0.038 [0.245, 0.457] |
| gnn_ggnn | 0.447 ± 0.029 [0.421, 0.476] | 0.346 ± 0.017 [0.309, 0.384] | 0.333 ± 0.086 [0.202, 0.443] |
| hybrid_ggnn_nohist | 0.395 ± 0.033 [0.369, 0.420] | 0.327 ± 0.027 [0.282, 0.375] | 0.432 ± 0.077 [0.253, 0.573] |
| hybrid_ggnn | 0.384 ± 0.037 [0.354, 0.417] | 0.358 ± 0.020 [0.315, 0.406] | 0.384 ± 0.089 [0.238, 0.490] |

Pooled precision (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.188 ± 0.013 [0.169, 0.208] | 0.204 ± 0.011 [0.175, 0.236] | 0.195 ± 0.050 [0.110, 0.288] |
| naive_size | 0.217 ± 0.000 [0.197, 0.240] | 0.191 ± 0.000 [0.163, 0.219] | 0.189 ± 0.000 [0.107, 0.284] |
| naive_rule | 0.221 ± 0.000 [0.200, 0.243] | 0.187 ± 0.000 [0.150, 0.225] | 0.224 ± 0.000 [0.124, 0.327] |
| lr | 0.297 ± 0.000 [0.262, 0.335] | 0.244 ± 0.000 [0.207, 0.287] | 0.303 ± 0.000 [0.175, 0.428] |
| rf | 0.357 ± 0.070 [0.328, 0.385] | 0.225 ± 0.007 [0.195, 0.255] | 0.241 ± 0.009 [0.121, 0.372] |
| hgb | 0.294 ± 0.000 [0.266, 0.323] | 0.235 ± 0.000 [0.206, 0.267] | 0.239 ± 0.000 [0.134, 0.360] |
| mlp_hist | 0.430 ± 0.044 [0.386, 0.476] | 0.225 ± 0.019 [0.183, 0.262] | 0.243 ± 0.024 [0.142, 0.343] |
| mlp_full | 0.377 ± 0.032 [0.342, 0.417] | 0.284 ± 0.011 [0.240, 0.331] | 0.350 ± 0.045 [0.179, 0.515] |
| gnn_rgcn | 0.432 ± 0.020 [0.401, 0.467] | 0.234 ± 0.009 [0.204, 0.266] | 0.329 ± 0.018 [0.185, 0.462] |
| gnn_ggnn | 0.420 ± 0.013 [0.390, 0.454] | 0.237 ± 0.009 [0.205, 0.272] | 0.302 ± 0.045 [0.158, 0.439] |
| hybrid_ggnn_nohist | 0.353 ± 0.041 [0.324, 0.384] | 0.261 ± 0.022 [0.219, 0.307] | 0.427 ± 0.050 [0.220, 0.596] |
| hybrid_ggnn | 0.361 ± 0.037 [0.327, 0.399] | 0.272 ± 0.011 [0.230, 0.317] | 0.362 ± 0.074 [0.193, 0.507] |

Pooled recall (threshold frozen on validation):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.188 ± 0.015 [0.176, 0.200] | 0.198 ± 0.016 [0.185, 0.210] | 0.190 ± 0.059 [0.162, 0.227] |
| naive_size | 0.642 ± 0.000 [0.599, 0.686] | 0.897 ± 0.000 [0.868, 0.921] | 0.915 ± 0.000 [0.850, 0.990] |
| naive_rule | 0.653 ± 0.000 [0.609, 0.694] | 0.551 ± 0.000 [0.473, 0.624] | 0.274 ± 0.000 [0.177, 0.444] |
| lr | 0.279 ± 0.000 [0.246, 0.315] | 0.669 ± 0.000 [0.591, 0.744] | 0.897 ± 0.000 [0.836, 0.961] |
| rf | 0.610 ± 0.076 [0.570, 0.648] | 0.922 ± 0.031 [0.901, 0.942] | 0.819 ± 0.079 [0.663, 0.918] |
| hgb | 0.616 ± 0.000 [0.568, 0.660] | 0.742 ± 0.000 [0.668, 0.819] | 0.966 ± 0.000 [0.906, 1.000] |
| mlp_hist | 0.389 ± 0.059 [0.346, 0.431] | 0.295 ± 0.138 [0.253, 0.339] | 0.362 ± 0.095 [0.218, 0.595] |
| mlp_full | 0.359 ± 0.046 [0.326, 0.391] | 0.495 ± 0.052 [0.433, 0.557] | 0.615 ± 0.145 [0.448, 0.770] |
| gnn_rgcn | 0.498 ± 0.033 [0.462, 0.529] | 0.669 ± 0.050 [0.632, 0.708] | 0.427 ± 0.095 [0.347, 0.512] |
| gnn_ggnn | 0.479 ± 0.049 [0.447, 0.509] | 0.644 ± 0.056 [0.613, 0.677] | 0.436 ± 0.176 [0.312, 0.540] |
| hybrid_ggnn_nohist | 0.453 ± 0.042 [0.420, 0.486] | 0.439 ± 0.048 [0.373, 0.510] | 0.441 ± 0.107 [0.268, 0.577] |
| hybrid_ggnn | 0.414 ± 0.057 [0.380, 0.451] | 0.536 ± 0.089 [0.474, 0.598] | 0.441 ± 0.167 [0.309, 0.554] |

Pooled ROC-AUC (mean ± sd over seeds):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.507 ± 0.010 | 0.497 ± 0.006 | 0.505 ± 0.040 |
| naive_size | 0.544 ± 0.000 | 0.387 ± 0.000 | 0.288 ± 0.000 |
| naive_rule | 0.565 ± 0.000 | 0.443 ± 0.000 | 0.525 ± 0.000 |
| lr | 0.556 ± 0.000 | 0.581 ± 0.000 | 0.678 ± 0.000 |
| rf | 0.712 ± 0.003 | 0.633 ± 0.010 | 0.731 ± 0.003 |
| hgb | 0.694 ± 0.000 | 0.619 ± 0.000 | 0.598 ± 0.000 |
| mlp_hist | 0.680 ± 0.009 | 0.553 ± 0.007 | 0.563 ± 0.034 |
| mlp_full | 0.648 ± 0.025 | 0.607 ± 0.008 | 0.675 ± 0.043 |
| gnn_rgcn | 0.675 ± 0.013 | 0.563 ± 0.019 | 0.649 ± 0.018 |
| gnn_ggnn | 0.680 ± 0.009 | 0.574 ± 0.020 | 0.670 ± 0.040 |
| hybrid_ggnn_nohist | 0.653 ± 0.022 | 0.576 ± 0.017 | 0.731 ± 0.064 |
| hybrid_ggnn | 0.646 ± 0.039 | 0.609 ± 0.009 | 0.692 ± 0.040 |

n per task: add_log n=4475, n_pos=895; change_level n=585, n_pos=117; remove_log n=3766, n_pos=764.

Macro PR-AUC (mean over the test repositories each model was evaluated on):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| naive_prior | 0.217 ± 0.006 [0.198, 0.254] | 0.229 ± 0.004 [0.190, 0.284] | 0.234 ± 0.014 [0.158, 0.338] |
| naive_size | 0.255 ± 0.000 [0.223, 0.309] | 0.203 ± 0.000 [0.161, 0.281] | 0.166 ± 0.000 [0.096, 0.264] |
| naive_rule | 0.254 ± 0.000 [0.223, 0.311] | 0.247 ± 0.000 [0.185, 0.324] | 0.302 ± 0.000 [0.247, 0.582] |
| lr | 0.315 ± 0.000 [0.279, 0.370] | 0.315 ± 0.000 [0.259, 0.399] | 0.359 ± 0.000 [0.189, 0.480] |
| rf | 0.428 ± 0.005 [0.381, 0.493] | 0.296 ± 0.006 [0.251, 0.372] | 0.388 ± 0.006 [0.246, 0.525] |
| hgb | 0.450 ± 0.000 [0.395, 0.506] | 0.298 ± 0.000 [0.248, 0.377] | 0.324 ± 0.000 [0.198, 0.463] |
| mlp_hist | 0.381 ± 0.003 [0.337, 0.449] | 0.296 ± 0.018 [0.246, 0.359] | 0.245 ± 0.032 [0.168, 0.355] |
| mlp_full | 0.360 ± 0.015 [0.323, 0.413] | 0.303 ± 0.015 [0.258, 0.373] | 0.475 ± 0.029 [0.255, 0.577] |
| gnn_rgcn | 0.392 ± 0.011 [0.348, 0.451] | 0.289 ± 0.021 [0.232, 0.360] | 0.362 ± 0.027 [0.213, 0.497] |
| gnn_ggnn | 0.381 ± 0.014 [0.345, 0.440] | 0.292 ± 0.014 [0.239, 0.354] | 0.379 ± 0.043 [0.237, 0.496] |
| hybrid_ggnn_nohist | 0.358 ± 0.017 [0.322, 0.412] | 0.317 ± 0.023 [0.257, 0.384] | 0.507 ± 0.039 [0.290, 0.617] |
| hybrid_ggnn | 0.364 ± 0.017 [0.329, 0.421] | 0.319 ± 0.010 [0.260, 0.395] | 0.455 ± 0.035 [0.277, 0.565] |

Macro CIs use only the resamples in which every repository of the macro has a positive (of B = 1000): add_log 1000; change_level 869; remove_log 996.

Macro PR-AUC with and without the few-commit folds (change_level: OpenKeeper):

| model | change_level all folds | change_level without few-commit folds |
|---|---|---|
| naive_prior | 0.234 ± 0.014 [0.158, 0.338] | 0.236 ± 0.026 [0.172, 0.333] |
| naive_size | 0.166 ± 0.000 [0.096, 0.264] | 0.175 ± 0.000 [0.102, 0.289] |
| naive_rule | 0.302 ± 0.000 [0.247, 0.582] | 0.328 ± 0.000 [0.238, 0.474] |
| lr | 0.359 ± 0.000 [0.189, 0.480] | 0.262 ± 0.000 [0.177, 0.381] |
| rf | 0.388 ± 0.006 [0.246, 0.525] | 0.366 ± 0.008 [0.248, 0.515] |
| hgb | 0.324 ± 0.000 [0.198, 0.463] | 0.319 ± 0.000 [0.208, 0.470] |
| mlp_hist | 0.245 ± 0.032 [0.168, 0.355] | 0.257 ± 0.019 [0.182, 0.368] |
| mlp_full | 0.475 ± 0.029 [0.255, 0.577] | 0.334 ± 0.025 [0.260, 0.461] |
| gnn_rgcn | 0.362 ± 0.027 [0.213, 0.497] | 0.335 ± 0.013 [0.236, 0.469] |
| gnn_ggnn | 0.379 ± 0.043 [0.237, 0.496] | 0.347 ± 0.021 [0.264, 0.465] |
| hybrid_ggnn_nohist | 0.507 ± 0.039 [0.290, 0.617] | 0.377 ± 0.058 [0.265, 0.518] |
| hybrid_ggnn | 0.455 ± 0.035 [0.277, 0.565] | 0.343 ± 0.020 [0.256, 0.475] |

Table: `tables/rq3_overall_macro_no_few_commit.csv`.

Per-repository prevalence differs from 1/(1+R) = 0.200 where a repository's negative pool is smaller than R × its positives: remove_log SkyHussars 0.276; remove_log jme3rpg 0.246. Per-repository PR-AUC values (heatmaps, macro averages) are relative to these prevalences; the heatmap column labels give them.

Pooled metrics per engine (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | engine | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC | gnn_ggnn PR-AUC [CI] ×lift | gnn_ggnn ROC-AUC | hybrid_ggnn PR-AUC [CI] ×lift | hybrid_ggnn ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | jME | 1500 | 300 | 0.200 | 0.212 | 0.350 ± 0.000 [0.281, 0.431] ×1.75 | 0.666 ± 0.000 | 0.302 ± 0.009 [0.256, 0.356] ×1.51 | 0.613 ± 0.012 | 0.326 ± 0.013 [0.270, 0.394] ×1.63 | 0.637 ± 0.006 |
| add_log | libGDX | 2975 | 595 | 0.200 | 0.204 | 0.457 ± 0.000 [0.410, 0.510] ×2.29 | 0.710 ± 0.000 | 0.443 ± 0.019 [0.403, 0.488] ×2.21 | 0.729 ± 0.006 | 0.349 ± 0.079 [0.315, 0.389] ×1.75 | 0.655 ± 0.061 |
| remove_log | jME | 1336 | 278 | 0.208 | 0.205 | 0.297 ± 0.000 [0.217, 0.411] ×1.43 | 0.626 ± 0.000 | 0.252 ± 0.010 [0.205, 0.317] ×1.21 | 0.563 ± 0.023 | 0.348 ± 0.038 [0.247, 0.472] ×1.67 | 0.641 ± 0.007 |
| remove_log | libGDX | 2430 | 486 | 0.200 | 0.201 | 0.265 ± 0.000 [0.221, 0.324] ×1.33 | 0.617 ± 0.000 | 0.258 ± 0.028 [0.192, 0.341] ×1.29 | 0.583 ± 0.030 | 0.248 ± 0.016 [0.198, 0.330] ×1.24 | 0.600 ± 0.014 |
| change_level | jME | 250 | 50 | 0.200 | 0.218 | 0.236 ± 0.000 [0.069, 0.455] ×1.18 | 0.579 ± 0.000 | 0.407 ± 0.110 [0.118, 0.631] ×2.03 | 0.736 ± 0.051 | 0.469 ± 0.092 [0.190, 0.668] ×2.35 | 0.811 ± 0.048 |
| change_level | libGDX | 335 | 67 | 0.200 | 0.230 | 0.340 ± 0.000 [0.158, 0.540] ×1.70 | 0.635 ± 0.000 | 0.328 ± 0.051 [0.228, 0.454] ×1.64 | 0.641 ± 0.053 | 0.317 ± 0.036 [0.207, 0.473] ×1.59 | 0.639 ± 0.027 |

Pooled metrics per size (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | size | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC | gnn_ggnn PR-AUC [CI] ×lift | gnn_ggnn ROC-AUC | hybrid_ggnn PR-AUC [CI] ×lift | hybrid_ggnn ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | Large | 4100 | 820 | 0.200 | 0.206 | 0.402 ± 0.000 [0.363, 0.453] ×2.01 | 0.700 ± 0.000 | 0.373 ± 0.020 [0.340, 0.410] ×1.86 | 0.689 ± 0.010 | 0.335 ± 0.051 [0.303, 0.373] ×1.67 | 0.653 ± 0.047 |
| add_log | Medium | 375 | 75 | 0.200 | 0.212 | 0.441 ± 0.000 [0.315, 0.578] ×2.21 | 0.637 ± 0.000 | 0.329 ± 0.023 [0.238, 0.441] ×1.65 | 0.599 ± 0.030 | 0.332 ± 0.037 [0.247, 0.440] ×1.66 | 0.605 ± 0.012 |
| remove_log | Large | 3090 | 618 | 0.200 | 0.199 | 0.262 ± 0.000 [0.223, 0.313] ×1.31 | 0.610 ± 0.000 | 0.254 ± 0.024 [0.204, 0.312] ×1.27 | 0.579 ± 0.024 | 0.255 ± 0.017 [0.209, 0.319] ×1.27 | 0.596 ± 0.015 |
| remove_log | Medium | 676 | 146 | 0.216 | 0.222 | 0.336 ± 0.000 [0.216, 0.496] ×1.55 | 0.673 ± 0.000 | 0.258 ± 0.027 [0.191, 0.352] ×1.19 | 0.551 ± 0.018 | 0.406 ± 0.048 [0.238, 0.586] ×1.88 | 0.679 ± 0.014 |
| change_level | Large | 585 | 117 | 0.200 | 0.217 | 0.295 ± 0.000 [0.164, 0.449] ×1.47 | 0.598 ± 0.000 | 0.353 ± 0.039 [0.203, 0.526] ×1.77 | 0.670 ± 0.040 | 0.352 ± 0.043 [0.225, 0.493] ×1.76 | 0.692 ± 0.040 |

Pooled metrics per ecosystem (n_pos and prevalence of the group; naive_prior = chance reference; ×lift = PR-AUC / prevalence):

| task | ecosystem | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC | gnn_ggnn PR-AUC [CI] ×lift | gnn_ggnn ROC-AUC | hybrid_ggnn PR-AUC [CI] ×lift | hybrid_ggnn ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | arc | 2045 | 409 | 0.200 | 0.204 | 0.484 ± 0.000 [0.433, 0.538] ×2.42 | 0.712 ± 0.000 | 0.524 ± 0.008 [0.475, 0.574] ×2.62 | 0.735 ± 0.006 | 0.339 ± 0.099 [0.304, 0.378] ×1.70 | 0.663 ± 0.072 |
| add_log | gdx | 930 | 186 | 0.200 | 0.209 | 0.552 ± 0.000 [0.467, 0.639] ×2.76 | 0.752 ± 0.000 | 0.444 ± 0.045 [0.375, 0.522] ×2.22 | 0.737 ± 0.011 | 0.477 ± 0.023 [0.399, 0.565] ×2.38 | 0.703 ± 0.046 |
| add_log | jdk_system | 675 | 135 | 0.200 | 0.223 | 0.378 ± 0.000 [0.282, 0.490] ×1.89 | 0.745 ± 0.000 | 0.321 ± 0.026 [0.245, 0.407] ×1.60 | 0.659 ± 0.017 | 0.367 ± 0.012 [0.277, 0.474] ×1.83 | 0.715 ± 0.009 |
| add_log | jul | 295 | 59 | 0.200 | 0.215 | 0.411 ± 0.000 [0.276, 0.557] ×2.05 | 0.613 ± 0.000 | 0.335 ± 0.020 [0.232, 0.465] ×1.67 | 0.592 ± 0.036 | 0.349 ± 0.026 [0.250, 0.469] ×1.74 | 0.614 ± 0.009 |
| add_log | slf4j | 530 | 106 | 0.200 | 0.214 | 0.314 ± 0.000 [0.234, 0.424] ×1.57 | 0.591 ± 0.000 | 0.288 ± 0.025 [0.222, 0.376] ×1.44 | 0.564 ± 0.041 | 0.288 ± 0.017 [0.221, 0.375] ×1.44 | 0.579 ± 0.010 |
| remove_log | arc | 1625 | 325 | 0.200 | 0.203 | 0.326 ± 0.000 [0.276, 0.384] ×1.63 | 0.682 ± 0.000 | 0.243 ± 0.027 [0.207, 0.286] ×1.22 | 0.575 ± 0.026 | 0.321 ± 0.038 [0.276, 0.376] ×1.61 | 0.679 ± 0.017 |
| remove_log | gdx | 805 | 161 | 0.200 | 0.202 | 0.246 ± 0.000 [0.163, 0.371] ×1.23 | 0.510 ± 0.000 | 0.288 ± 0.060 [0.148, 0.426] ×1.44 | 0.602 ± 0.056 | 0.216 ± 0.030 [0.125, 0.355] ×1.08 | 0.512 ± 0.032 |
| remove_log | jdk_system | 205 | 41 | 0.200 | 0.194 | 0.218 ± 0.000 [0.136, 0.365] ×1.09 | 0.536 ± 0.000 | 0.263 ± 0.029 [0.179, 0.385] ×1.31 | 0.611 ± 0.050 | 0.245 ± 0.039 [0.148, 0.389] ×1.23 | 0.528 ± 0.033 |
| remove_log | jul | 571 | 117 | 0.205 | 0.214 | 0.337 ± 0.000 [0.199, 0.512] ×1.65 | 0.686 ± 0.000 | 0.234 ± 0.026 [0.159, 0.345] ×1.14 | 0.536 ± 0.021 | 0.430 ± 0.061 [0.240, 0.620] ×2.10 | 0.704 ± 0.019 |
| remove_log | slf4j | 560 | 120 | 0.214 | 0.215 | 0.304 ± 0.000 [0.212, 0.427] ×1.42 | 0.624 ± 0.000 | 0.279 ± 0.026 [0.218, 0.374] ×1.30 | 0.579 ± 0.038 | 0.360 ± 0.038 [0.250, 0.486] ×1.68 | 0.642 ± 0.028 |
| change_level | arc | 160 | 32 | 0.200 | 0.236 | 0.384 ± 0.000 [0.103, 0.629] ×1.92 | 0.659 ± 0.000 | 0.354 ± 0.087 [0.189, 0.518] ×1.77 | 0.644 ± 0.048 | 0.404 ± 0.017 [0.215, 0.601] ×2.02 | 0.732 ± 0.023 |
| change_level | gdx | 175 | 35 | 0.200 | 0.238 | 0.358 ± 0.000 [0.188, 0.618] ×1.79 | 0.665 ± 0.000 | 0.336 ± 0.093 [0.190, 0.506] ×1.68 | 0.675 ± 0.095 | 0.294 ± 0.059 [0.137, 0.514] ×1.47 | 0.595 ± 0.067 |
| change_level | jdk_system | 140 | 28 | 0.200 | 0.227 | 0.339 ± 0.000 [0.036, 0.638] ×1.70 | 0.701 ± 0.000 | 0.475 ± 0.173 [0.049, 0.731] ×2.38 | 0.771 ± 0.081 | 0.791 ± 0.137 [0.102, 0.954] ×3.95 | 0.954 ± 0.032 |
| change_level | slf4j | 110 | 22 | 0.200 | 0.235 | 0.215 ± 0.000 [0.091, 0.397] ×1.08 | 0.495 ± 0.000 | 0.349 ± 0.031 [0.168, 0.578] ×1.75 | 0.715 ± 0.057 | 0.332 ± 0.060 [0.178, 0.536] ×1.66 | 0.703 ± 0.069 |

PR-AUC depends on the prevalence, which differs between groups (engines, sizes, ecosystems, subsets, categories): compare groups through the lift and ROC-AUC, not through raw PR-AUC.

Ecosystem = dominant formal logging framework per repository; source: rq1 snapshot.

Tables: `tables/rq3_overall_pooled.csv`, `tables/rq3_overall_macro.csv`, `tables/rq3_per_repo.csv`, `tables/rq3_per_engine.csv`, `tables/rq3_per_size.csv`, `tables/rq3_per_ecosystem.csv` (with French variants `*_fr.md`/`*_fr.tex` of the main tables). Figures: `figures/pr_curves_<task>_*` (seed 0), `figures/prauc_bars_*`, `figures/prauc_heatmap_<task>_*`.

## 6. RQ4 - performance-sensitive code

Primary RQ4 test: PR-AUC difference-in-differences of hybrid_ggnn - hgb (hgb fixed a priori as the reference classical model), Holm over the three tasks; paired cluster bootstrap on the test resamples (B = 10000); p with its Monte-Carlo standard error and the number of resamples used (those with a positive in both parts). A row with a part below the support floor (< 10 positives or positives from at most 2 commits) is descriptive only: Δ and CI, no p, not in the Holm family:

| task | difference | metric | Δ subset [CI] | Δ complement [CI] | DiD [CI] | p (MC SE; B used) | p Holm | subset n / n_pos / commits | complement n / n_pos / commits | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| add_log | hybrid_ggnn - hgb | pr_auc | -0.071 [-0.101, -0.044] | -0.087 [-0.137, -0.042] | +0.016 [-0.039, +0.072] | 0.567 (±0.0090; B 10000) | 1.000 | 2952 / 673 / 509 | 1523 / 222 / 178 |  |
| remove_log | hybrid_ggnn - hgb | pr_auc | +0.007 [-0.047, +0.065] | -0.035 [-0.107, +0.041] | +0.042 [-0.052, +0.135] | 0.366 (±0.0077; B 10000) | 1.000 | 3213 / 634 / 322 | 553 / 130 / 87 |  |
| change_level | hybrid_ggnn - hgb | pr_auc | +0.055 [-0.097, +0.165] | +0.011 [-0.226, +0.218] | +0.044 [-0.221, +0.305] | 0.756 (±0.0097; B 9999) | 1.000 | 499 / 100 / 32 | 86 / 17 / 9 | complement < 30 pos |

Secondary (threshold-dependent) F1 difference-in-differences, Holm over the tasks; rows with < 30 positives in the subset or the complement are exploratory:

| task | difference | metric | Δ subset [CI] | Δ complement [CI] | DiD [CI] | p (MC SE; B used) | p Holm | subset n / n_pos / commits | complement n / n_pos / commits | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| add_log | hybrid_ggnn - hgb | f1 | -0.009 [-0.037, +0.018] | -0.064 [-0.115, -0.012] | +0.055 [-0.001, +0.110] | 0.055 (±0.0033; B 10000) | 0.109 | 2952 / 673 / 509 | 1523 / 222 / 178 |  |
| remove_log | hybrid_ggnn - hgb | f1 | +0.011 [-0.032, +0.053] | -0.044 [-0.082, -0.006] | +0.055 [-0.003, +0.111] | 0.063 (±0.0035; B 10000) | 0.109 | 3213 / 634 / 322 | 553 / 130 / 87 |  |
| change_level | hybrid_ggnn - hgb | f1 | -0.048 [-0.168, +0.044] | +0.225 [+0.046, +0.336] | -0.273 [-0.439, -0.065] | 0.016 (±0.0018; B 9999) | 0.047 | 499 / 100 / 32 | 86 / 17 / 9 | complement < 30 pos, exploratory |

Sensitivity to the reference model: the primary reference is hgb, fixed a priori; as a check, the reference is also chosen without test information, as the classical model (lr, rf, hgb) with the highest mean validation PR-AUC over folds and seeds: add_log hgb (0.526); remove_log hgb (0.384); change_level rf (0.380).

Difference-in-differences against the validation-selected classical model (its own Holm family over tasks):

| task | difference | metric | Δ subset [CI] | Δ complement [CI] | DiD [CI] | p (MC SE; B used) | p Holm | subset n / n_pos / commits | complement n / n_pos / commits | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| add_log | hybrid_ggnn - hgb | pr_auc | -0.071 [-0.101, -0.044] | -0.087 [-0.137, -0.042] | +0.016 [-0.039, +0.072] | 0.567 (±0.0090; B 10000) | 1.000 | 2952 / 673 / 509 | 1523 / 222 / 178 |  |
| add_log | hybrid_ggnn - hgb | f1 | -0.009 [-0.037, +0.018] | -0.064 [-0.115, -0.012] | +0.055 [-0.001, +0.110] | 0.055 (±0.0033; B 10000) | 0.118 | 2952 / 673 / 509 | 1523 / 222 / 178 |  |
| remove_log | hybrid_ggnn - hgb | pr_auc | +0.007 [-0.047, +0.065] | -0.035 [-0.107, +0.041] | +0.042 [-0.052, +0.135] | 0.366 (±0.0077; B 10000) | 1.000 | 3213 / 634 / 322 | 553 / 130 / 87 |  |
| remove_log | hybrid_ggnn - hgb | f1 | +0.011 [-0.032, +0.053] | -0.044 [-0.082, -0.006] | +0.055 [-0.003, +0.111] | 0.063 (±0.0035; B 10000) | 0.118 | 3213 / 634 / 322 | 553 / 130 / 87 |  |
| change_level | hybrid_ggnn - rf | pr_auc | -0.011 [-0.094, +0.066] | +0.069 [-0.186, +0.220] | -0.080 [-0.250, +0.181] | 0.512 (±0.0087; B 9999) | 1.000 | 499 / 100 / 32 | 86 / 17 / 9 | complement < 30 pos |
| change_level | hybrid_ggnn - rf | f1 | -0.027 [-0.138, +0.067] | +0.179 [+0.010, +0.290] | -0.206 [-0.358, -0.014] | 0.039 (±0.0028; B 9999) | 0.118 | 499 / 100 / 32 | 86 / 17 / 9 | complement < 30 pos, exploratory |

Validation PR-AUC per classical model: `tables/rq4_did_reference_validation.csv`.

Stricter-subset sensitivity: subset = frame_update methods only, complement = every other method (hybrid_ggnn - hgb; its own Holm family over the tasks above the support floor; rows below it are descriptive only):

| task | difference | metric | Δ subset [CI] | Δ complement [CI] | DiD [CI] | p (MC SE; B used) | p Holm | subset n / n_pos / commits | complement n / n_pos / commits | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| add_log | hybrid_ggnn - hgb | pr_auc | +0.036 [-0.026, +0.089] | -0.086 [-0.114, -0.061] | +0.122 [+0.057, +0.180] | <0.001 (±0.0004; B 10000) | 0.002 | 676 / 92 / 86 | 3799 / 803 / 595 |  |
| add_log | hybrid_ggnn - hgb | f1 | +0.056 [-0.012, +0.124] | -0.032 [-0.059, -0.006] | +0.089 [+0.017, +0.160] | 0.013 (±0.0016; B 10000) | 0.027 | 676 / 92 / 86 | 3799 / 803 / 595 |  |
| remove_log | hybrid_ggnn - hgb | pr_auc | +0.079 [-0.027, +0.168] | -0.014 [-0.062, +0.034] | +0.093 [-0.011, +0.179] | 0.083 (±0.0040; B 10000) | 0.083 | 319 / 113 / 84 | 3447 / 651 / 324 |  |
| remove_log | hybrid_ggnn - hgb | f1 | +0.015 [-0.056, +0.090] | -0.010 [-0.047, +0.027] | +0.025 [-0.050, +0.101] | 0.538 (±0.0089; B 10000) | 0.538 | 319 / 113 / 84 | 3447 / 651 / 324 |  |
| change_level | hybrid_ggnn - hgb | pr_auc | +0.251 [+0.125, +0.441] | +0.052 [-0.090, +0.160] | +0.199 [+0.048, +0.437] | – (B 8680) | – | 28 / 3 / 2 | 557 / 114 / 37 | subset < 30 pos, descriptive only, no p (subset 3 pos / 2 commits) |
| change_level | hybrid_ggnn - hgb | f1 | -0.062 [-0.228, +0.014] | +0.002 [-0.104, +0.101] | -0.064 [-0.236, +0.064] | – (B 8680) | – | 28 / 3 / 2 | 557 / 114 / 37 | subset < 30 pos, descriptive only, no p (subset 3 pos / 2 commits) |

Subset coverage (share of the test instances in the performance-sensitive subset): add_log 66.0% of the instances, 75.2% of the positives; remove_log 85.3% of the instances, 83.0% of the positives; change_level 85.3% of the instances, 85.5% of the positives.

Subset and complement (pooled; prevalence differs between the parts, so compare lift and ROC-AUC):

| task | part | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC | gnn_ggnn PR-AUC [CI] ×lift | gnn_ggnn ROC-AUC | hybrid_ggnn PR-AUC [CI] ×lift | hybrid_ggnn ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | complement | 1523 | 222 | 0.146 | 0.150 | 0.323 ± 0.000 [0.260, 0.399] ×2.22 | 0.671 ± 0.000 | 0.252 ± 0.018 [0.208, 0.306] ×1.73 | 0.628 ± 0.009 | 0.236 ± 0.019 [0.193, 0.293] ×1.62 | 0.585 ± 0.037 |
| add_log | subset | 2952 | 673 | 0.228 | 0.236 | 0.431 ± 0.000 [0.387, 0.485] ×1.89 | 0.693 ± 0.000 | 0.408 ± 0.019 [0.371, 0.451] ×1.79 | 0.691 ± 0.013 | 0.360 ± 0.053 [0.325, 0.399] ×1.58 | 0.652 ± 0.043 |
| remove_log | complement | 553 | 130 | 0.235 | 0.250 | 0.296 ± 0.000 [0.234, 0.386] ×1.26 | 0.598 ± 0.000 | 0.234 ± 0.020 [0.184, 0.300] ×1.00 | 0.512 ± 0.030 | 0.261 ± 0.015 [0.197, 0.352] ×1.11 | 0.532 ± 0.027 |
| remove_log | subset | 3213 | 634 | 0.197 | 0.194 | 0.268 ± 0.000 [0.220, 0.326] ×1.36 | 0.620 ± 0.000 | 0.256 ± 0.020 [0.207, 0.316] ×1.30 | 0.582 ± 0.022 | 0.275 ± 0.017 [0.217, 0.351] ×1.39 | 0.618 ± 0.008 |
| change_level | complement | 86 | 17 | 0.198 | 0.250 | 0.533 ± 0.000 [0.270, 0.801] ×2.70 | 0.865 ± 0.000 | 0.421 ± 0.150 [0.221, 0.585] ×2.13 | 0.682 ± 0.079 | 0.544 ± 0.058 [0.306, 0.790] ×2.75 | 0.858 ± 0.026 |
| change_level | subset | 499 | 100 | 0.200 | 0.217 | 0.268 ± 0.000 [0.127, 0.432] ×1.34 | 0.557 ± 0.000 | 0.344 ± 0.028 [0.180, 0.535] ×1.72 | 0.667 ± 0.036 | 0.323 ± 0.052 [0.172, 0.480] ×1.61 | 0.665 ± 0.046 |

Subset minus complement per model (same test resamples):

| task | model | Δ PR-AUC [CI] | Δ lift [CI] | Δ ROC-AUC [CI] | Δ F1 [CI] | prevalence subset / complement | flags |
|---|---|---|---|---|---|---|---|
| add_log | naive_prior | +0.086 [+0.053, +0.115] | +0.005 [-0.091, +0.067] | +0.021 [-0.002, +0.044] | +0.020 [-0.008, +0.048] | 0.228 / 0.146 |  |
| add_log | hgb | +0.108 [+0.022, +0.187] | -0.325 [-0.867, +0.102] | +0.021 [-0.033, +0.078] | +0.115 [+0.058, +0.174] | 0.228 / 0.146 |  |
| add_log | gnn_ggnn | +0.156 [+0.092, +0.213] | +0.058 [-0.291, +0.330] | +0.064 [+0.016, +0.112] | +0.170 [+0.114, +0.226] | 0.228 / 0.146 |  |
| add_log | hybrid_ggnn | +0.124 [+0.063, +0.179] | -0.042 [-0.393, +0.242] | +0.067 [+0.017, +0.120] | +0.169 [+0.114, +0.227] | 0.228 / 0.146 |  |
| remove_log | naive_prior | -0.056 [-0.122, +0.000] | -0.080 [-0.199, -0.014] | -0.010 [-0.038, +0.017] | -0.016 [-0.054, +0.026] | 0.197 / 0.235 |  |
| remove_log | hgb | -0.028 [-0.128, +0.057] | +0.097 [-0.282, +0.397] | +0.022 [-0.054, +0.098] | -0.071 [-0.151, +0.014] | 0.197 / 0.235 |  |
| remove_log | gnn_ggnn | +0.022 [-0.059, +0.096] | +0.302 [+0.102, +0.474] | +0.070 [+0.016, +0.125] | -0.043 [-0.118, +0.036] | 0.197 / 0.235 |  |
| remove_log | hybrid_ggnn | +0.014 [-0.095, +0.110] | +0.284 [-0.106, +0.590] | +0.086 [-0.004, +0.172] | -0.016 [-0.099, +0.069] | 0.197 / 0.235 |  |
| change_level | naive_prior | -0.033 [-0.217, +0.103] | -0.181 [-1.322, +0.038] | -0.036 [-0.119, +0.020] | +0.033 [-0.046, +0.142] | 0.200 / 0.198 |  |
| change_level | hgb | -0.265 [-0.561, +0.040] | -1.360 [-5.975, -0.070] | -0.308 [-0.437, -0.172] | +0.001 [-0.249, +0.257] | 0.200 / 0.198 |  |
| change_level | gnn_ggnn | -0.077 [-0.320, +0.187] | -0.415 [-2.777, +0.268] | -0.014 [-0.141, +0.078] | -0.030 [-0.243, +0.223] | 0.200 / 0.198 |  |
| change_level | hybrid_ggnn | -0.222 [-0.512, +0.076] | -1.143 [-4.727, -0.134] | -0.193 [-0.351, -0.055] | -0.272 [-0.530, +0.100] | 0.200 / 0.198 |  |

All models with p values, MC SE and B used: `tables/rq4_subset_gap.csv`.

Context categories (mutually exclusive; pooled):

| task | ctx_category | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC | gnn_ggnn PR-AUC [CI] ×lift | gnn_ggnn ROC-AUC | hybrid_ggnn PR-AUC [CI] ×lift | hybrid_ggnn ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | frame_update | 676 | 92 | 0.136 | 0.146 | 0.191 ± 0.000 [0.134, 0.275] ×1.41 | 0.486 ± 0.000 | 0.212 ± 0.017 [0.161, 0.289] ×1.56 | 0.559 ± 0.045 | 0.227 ± 0.008 [0.163, 0.308] ×1.67 | 0.568 ± 0.015 |
| add_log | general | 1523 | 222 | 0.146 | 0.150 | 0.323 ± 0.000 [0.260, 0.399] ×2.22 | 0.671 ± 0.000 | 0.252 ± 0.018 [0.208, 0.306] ×1.73 | 0.628 ± 0.009 | 0.236 ± 0.019 [0.193, 0.293] ×1.62 | 0.585 ± 0.037 |
| add_log | loop | 1254 | 321 | 0.256 | 0.264 | 0.475 ± 0.000 [0.410, 0.552] ×1.86 | 0.726 ± 0.000 | 0.456 ± 0.012 [0.402, 0.515] ×1.78 | 0.723 ± 0.016 | 0.375 ± 0.061 [0.325, 0.434] ×1.46 | 0.664 ± 0.048 |
| add_log | subsystem | 1022 | 260 | 0.254 | 0.272 | 0.471 ± 0.000 [0.405, 0.548] ×1.85 | 0.702 ± 0.000 | 0.422 ± 0.035 [0.369, 0.490] ×1.66 | 0.680 ± 0.017 | 0.412 ± 0.046 [0.359, 0.477] ×1.62 | 0.632 ± 0.060 |
| remove_log | frame_update | 319 | 113 | 0.354 | 0.349 | 0.359 ± 0.000 [0.282, 0.473] ×1.01 | 0.532 ± 0.000 | 0.404 ± 0.050 [0.310, 0.516] ×1.14 | 0.532 ± 0.065 | 0.438 ± 0.022 [0.315, 0.566] ×1.24 | 0.545 ± 0.035 |
| remove_log | general | 553 | 130 | 0.235 | 0.250 | 0.296 ± 0.000 [0.234, 0.386] ×1.26 | 0.598 ± 0.000 | 0.234 ± 0.020 [0.184, 0.300] ×1.00 | 0.512 ± 0.030 | 0.261 ± 0.015 [0.197, 0.352] ×1.11 | 0.532 ± 0.027 |
| remove_log | loop | 1876 | 309 | 0.165 | 0.166 | 0.234 ± 0.000 [0.177, 0.313] ×1.42 | 0.628 ± 0.000 | 0.226 ± 0.023 [0.159, 0.309] ×1.37 | 0.587 ± 0.026 | 0.199 ± 0.017 [0.152, 0.278] ×1.21 | 0.568 ± 0.021 |
| remove_log | subsystem | 1018 | 212 | 0.208 | 0.206 | 0.301 ± 0.000 [0.213, 0.420] ×1.45 | 0.615 ± 0.000 | 0.242 ± 0.012 [0.188, 0.312] ×1.16 | 0.547 ± 0.031 | 0.342 ± 0.029 [0.223, 0.483] ×1.64 | 0.650 ± 0.017 |
| change_level | frame_update | 28 | 3 | 0.107 | 0.186 | 0.111 ± 0.000 [0.031, 0.309] ×1.04 | 0.220 ± 0.000 | 0.366 ± 0.140 [0.170, 0.714] ×3.42 | 0.835 ± 0.081 | 0.362 ± 0.256 [0.163, 0.662] ×3.38 | 0.779 ± 0.134 |
| change_level | general | 86 | 17 | 0.198 | 0.250 | 0.533 ± 0.000 [0.270, 0.801] ×2.70 | 0.865 ± 0.000 | 0.421 ± 0.150 [0.221, 0.585] ×2.13 | 0.682 ± 0.079 | 0.544 ± 0.058 [0.306, 0.790] ×2.75 | 0.858 ± 0.026 |
| change_level | loop | 304 | 50 | 0.164 | 0.184 | 0.309 ± 0.000 [0.102, 0.546] ×1.88 | 0.598 ± 0.000 | 0.271 ± 0.059 [0.184, 0.400] ×1.65 | 0.631 ± 0.084 | 0.289 ± 0.021 [0.156, 0.489] ×1.76 | 0.660 ± 0.068 |
| change_level | subsystem | 167 | 47 | 0.281 | 0.313 | 0.274 ± 0.000 [0.093, 0.501] ×0.97 | 0.446 ± 0.000 | 0.476 ± 0.065 [0.164, 0.713] ×1.69 | 0.682 ± 0.037 | 0.382 ± 0.087 [0.174, 0.586] ×1.36 | 0.622 ± 0.098 |

Figure: `figures/rq4_ctx_category_*`.

Subsystem markers, each on its own (descriptive; a method can carry several markers; markers with few positives give wide intervals):

| task | marker | n | n_pos | prevalence | naive_prior PR-AUC | hgb PR-AUC [CI] ×lift | hgb ROC-AUC | gnn_ggnn PR-AUC [CI] ×lift | gnn_ggnn ROC-AUC | hybrid_ggnn PR-AUC [CI] ×lift | hybrid_ggnn ROC-AUC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | input | 329 | 41 | 0.125 | 0.140 | 0.390 ± 0.000 [0.257, 0.575] ×3.13 | 0.726 ± 0.000 | 0.296 ± 0.028 [0.197, 0.432] ×2.37 | 0.671 ± 0.033 | 0.358 ± 0.031 [0.236, 0.503] ×2.87 | 0.721 ± 0.016 |
| add_log | network | 680 | 272 | 0.400 | 0.417 | 0.553 ± 0.000 [0.494, 0.630] ×1.38 | 0.650 ± 0.000 | 0.530 ± 0.031 [0.471, 0.594] ×1.32 | 0.658 ± 0.015 | 0.504 ± 0.055 [0.447, 0.571] ×1.26 | 0.546 ± 0.075 |
| add_log | physics | 122 | 19 | 0.156 | 0.212 | 0.396 ± 0.000 [0.193, 0.744] ×2.54 | 0.610 ± 0.000 | 0.289 ± 0.052 [0.109, 0.565] ×1.86 | 0.510 ± 0.076 | 0.291 ± 0.059 [0.150, 0.517] ×1.87 | 0.617 ± 0.065 |
| add_log | collision | 32 | 10 | 0.312 | 0.385 | 0.596 ± 0.000 [0.341, 0.834] ×1.91 | 0.609 ± 0.000 | 0.553 ± 0.034 [0.296, 0.782] ×1.77 | 0.520 ± 0.050 | 0.557 ± 0.095 [0.314, 0.782] ×1.78 | 0.595 ± 0.123 |
| add_log | animation | 79 | 10 | 0.127 | 0.196 | 0.285 ± 0.000 [0.107, 0.611] ×2.25 | 0.707 ± 0.000 | 0.341 ± 0.096 [0.164, 0.612] ×2.69 | 0.745 ± 0.076 | 0.288 ± 0.046 [0.094, 0.589] ×2.28 | 0.633 ± 0.024 |
| add_log | resource | 525 | 124 | 0.236 | 0.256 | 0.462 ± 0.000 [0.374, 0.556] ×1.96 | 0.696 ± 0.000 | 0.468 ± 0.020 [0.388, 0.563] ×1.98 | 0.747 ± 0.008 | 0.314 ± 0.092 [0.260, 0.378] ×1.33 | 0.624 ± 0.077 |
| remove_log | input | 156 | 38 | 0.244 | 0.234 | 0.509 ± 0.000 [0.217, 0.749] ×2.09 | 0.736 ± 0.000 | 0.340 ± 0.081 [0.147, 0.549] ×1.39 | 0.635 ± 0.078 | 0.712 ± 0.079 [0.153, 0.905] ×2.92 | 0.815 ± 0.016 |
| remove_log | network | 1591 | 227 | 0.143 | 0.142 | 0.238 ± 0.000 [0.163, 0.336] ×1.67 | 0.660 ± 0.000 | 0.181 ± 0.015 [0.138, 0.238] ×1.27 | 0.557 ± 0.014 | 0.210 ± 0.012 [0.155, 0.282] ×1.47 | 0.624 ± 0.006 |
| remove_log | physics | 82 | 33 | 0.402 | 0.444 | 0.537 ± 0.000 [0.255, 0.770] ×1.33 | 0.520 ± 0.000 | 0.506 ± 0.084 [0.321, 0.688] ×1.26 | 0.550 ± 0.132 | 0.628 ± 0.073 [0.350, 0.820] ×1.56 | 0.685 ± 0.077 |
| remove_log | collision | 49 | 17 | 0.347 | 0.349 | 0.569 ± 0.000 [0.307, 0.800] ×1.64 | 0.651 ± 0.000 | 0.451 ± 0.075 [0.292, 0.676] ×1.30 | 0.554 ± 0.068 | 0.438 ± 0.044 [0.225, 0.654] ×1.26 | 0.544 ± 0.025 |
| remove_log | animation | 20 | 0 | 0.000 | – | – | – | – | – | – | – |
| remove_log | resource | 547 | 107 | 0.196 | 0.206 | 0.211 ± 0.000 [0.146, 0.299] ×1.08 | 0.548 ± 0.000 | 0.216 ± 0.020 [0.136, 0.327] ×1.10 | 0.501 ± 0.048 | 0.240 ± 0.016 [0.166, 0.350] ×1.23 | 0.516 ± 0.016 |
| change_level | input | 22 | 1 | 0.045 | 0.144 | 0.083 ± 0.000 [0.056, 0.333] ×1.83 | 0.476 ± 0.000 | 0.314 ± 0.191 [0.212, 0.717] ×6.91 | 0.819 ± 0.163 | 0.218 ± 0.111 [0.143, 0.645] ×4.80 | 0.771 ± 0.148 |
| change_level | network | 259 | 56 | 0.216 | 0.231 | 0.267 ± 0.000 [0.109, 0.482] ×1.23 | 0.586 ± 0.000 | 0.462 ± 0.074 [0.139, 0.681] ×2.13 | 0.704 ± 0.025 | 0.348 ± 0.091 [0.169, 0.531] ×1.61 | 0.653 ± 0.118 |
| change_level | physics | 3 | 2 | 0.667 | 0.733 | 0.667 ± 0.000 [0.400, 1.000] ×1.00 | 0.000 ± 0.000 | 0.833 ± 0.228 [0.730, 1.000] ×1.25 | 0.600 ± 0.548 | 0.967 ± 0.075 [0.940, 1.000] ×1.45 | 0.900 ± 0.224 |
| change_level | collision | 7 | 2 | 0.286 | 0.434 | 0.286 ± 0.000 [0.182, 0.750] ×1.00 | 0.000 ± 0.000 | 0.377 ± 0.101 [0.243, 0.855] ×1.32 | 0.420 ± 0.228 | 0.283 ± 0.095 [0.194, 0.743] ×0.99 | 0.180 ± 0.249 |
| change_level | animation | 6 | 2 | 0.333 | 0.740 | 1.000 ± 0.000 [1.000, 1.000] ×3.00 | 1.000 ± 0.000 | 0.525 ± 0.176 [0.365, 0.917] ×1.57 | 0.575 ± 0.274 | 1.000 ± 0.000 [1.000, 1.000] ×3.00 | 1.000 ± 0.000 |
| change_level | resource | 99 | 28 | 0.283 | 0.319 | 0.448 ± 0.000 [0.063, 0.716] ×1.58 | 0.569 ± 0.000 | 0.384 ± 0.170 [0.203, 0.567] ×1.36 | 0.592 ± 0.184 | 0.381 ± 0.018 [0.166, 0.702] ×1.35 | 0.556 ± 0.141 |

Agreement of hybrid_ggnn and hgb (majority vote over seeds). Gains on positives = TP of one model where the other has a FN; gains on negatives = TN against FP. Top-k: the k = n_pos highest seed-mean scores of each model (threshold-free):

| task | n | n_pos | TP gains hybrid / hgb | TN gains hybrid / hgb | hybrid P / R / F1 | hgb P / R / F1 | top-k overlap / k (share) | positives in top-k hybrid / hgb |
|---|---|---|---|---|---|---|---|---|
| add_log | 4475 | 895 | 63 / 247 | 909 / 194 | 0.378 / 0.410 / 0.393 | 0.294 / 0.616 / 0.398 | 548 / 895 (0.612) | 341 / 391 |
| remove_log | 3766 | 764 | 79 / 214 | 1054 / 301 | 0.283 / 0.565 / 0.377 | 0.235 / 0.742 / 0.357 | 272 / 764 (0.356) | 218 / 220 |
| change_level | 585 | 117 | 1 / 66 | 288 / 6 | 0.381 / 0.410 / 0.395 | 0.239 / 0.966 / 0.383 | 52 / 117 (0.444) | 48 / 34 |

All counts: `error_analysis/disagreement.csv`.

Error rates of the majority vote, subset vs complement (Δ = subset − complement, cluster bootstrap CI; p with MC SE and B used, no p below the support floor):

| task | model | FP rate sub / comp | Δ FP rate [CI] | p FP | FN rate sub / comp | Δ FN rate [CI] | p FN | n_pos sub / comp | flags |
|---|---|---|---|---|---|---|---|---|---|
| add_log | naive_rule | 0.706 / 0.350 | +0.356 [+0.321, +0.390] | <0.001 (±0.0002; B 10000) | 0.276 / 0.563 | -0.287 [-0.366, -0.207] | <0.001 (±0.0002; B 10000) | 673 / 222 |  |
| add_log | lr | 0.197 / 0.110 | +0.087 [+0.063, +0.111] | <0.001 (±0.0002; B 10000) | 0.697 / 0.793 | -0.096 [-0.168, -0.022] | 0.012 (±0.0016; B 10000) | 673 / 222 |  |
| add_log | rf | 0.326 / 0.109 | +0.216 [+0.190, +0.243] | <0.001 (±0.0002; B 10000) | 0.339 / 0.568 | -0.229 [-0.315, -0.143] | <0.001 (±0.0002; B 10000) | 673 / 222 |  |
| add_log | hgb | 0.425 / 0.271 | +0.154 [+0.120, +0.188] | <0.001 (±0.0002; B 10000) | 0.339 / 0.523 | -0.184 [-0.275, -0.090] | <0.001 (±0.0003; B 10000) | 673 / 222 |  |
| add_log | gnn_ggnn | 0.172 / 0.104 | +0.068 [+0.045, +0.090] | <0.001 (±0.0002; B 10000) | 0.447 / 0.676 | -0.228 [-0.303, -0.153] | <0.001 (±0.0002; B 10000) | 673 / 222 |  |
| add_log | hybrid_ggnn | 0.226 / 0.069 | +0.157 [+0.133, +0.181] | <0.001 (±0.0002; B 10000) | 0.520 / 0.802 | -0.282 [-0.348, -0.213] | <0.001 (±0.0002; B 10000) | 673 / 222 |  |
| remove_log | naive_rule | 0.626 / 0.518 | +0.108 [+0.040, +0.177] | 0.002 (±0.0006; B 10000) | 0.399 / 0.692 | -0.293 [-0.430, -0.150] | <0.001 (±0.0003; B 10000) | 634 / 130 |  |
| remove_log | lr | 0.498 / 0.695 | -0.197 [-0.255, -0.135] | <0.001 (±0.0002; B 10000) | 0.360 / 0.192 | +0.167 [+0.047, +0.283] | 0.006 (±0.0011; B 10000) | 634 / 130 |  |
| remove_log | rf | 0.808 / 0.929 | -0.121 [-0.159, -0.083] | <0.001 (±0.0002; B 10000) | 0.055 / 0.038 | +0.017 [-0.033, +0.061] | 0.454 (±0.0084; B 10000) | 634 / 130 |  |
| remove_log | hgb | 0.601 / 0.702 | -0.101 [-0.159, -0.039] | 0.001 (±0.0005; B 10000) | 0.282 / 0.138 | +0.144 [+0.028, +0.258] | 0.015 (±0.0017; B 10000) | 634 / 130 |  |
| remove_log | gnn_ggnn | 0.515 / 0.591 | -0.076 [-0.135, -0.014] | 0.017 (±0.0018; B 10000) | 0.317 / 0.262 | +0.055 [-0.051, +0.158] | 0.283 (±0.0070; B 10000) | 634 / 130 |  |
| remove_log | hybrid_ggnn | 0.342 / 0.504 | -0.162 [-0.224, -0.099] | <0.001 (±0.0002; B 10000) | 0.450 / 0.362 | +0.088 [-0.054, +0.227] | 0.208 (±0.0061; B 10000) | 634 / 130 |  |
| change_level | naive_rule | 0.251 / 0.159 | +0.091 [-0.008, +0.188] | 0.070 (±0.0037; B 10000) | 0.700 / 0.882 | -0.182 [-0.452, +0.118] | 0.205 (±0.0061; B 9999) | 100 / 17 |  |
| change_level | lr | 0.499 / 0.623 | -0.124 [-0.252, +0.008] | 0.065 (±0.0036; B 10000) | 0.120 / 0.000 | +0.120 [+0.051, +0.208] | <0.001 (±0.0004; B 9999) | 100 / 17 |  |
| change_level | rf | 0.659 / 0.652 | +0.007 [-0.119, +0.144] | 0.918 (±0.0100; B 10000) | 0.180 / 0.000 | +0.180 [+0.070, +0.404] | <0.001 (±0.0003; B 9999) | 100 / 17 |  |
| change_level | hgb | 0.764 / 0.797 | -0.033 [-0.144, +0.095] | 0.597 (±0.0092; B 10000) | 0.040 / 0.000 | +0.040 [+0.000, +0.111] | 0.098 (±0.0043; B 9999) | 100 / 17 |  |
| change_level | gnn_ggnn | 0.273 / 0.159 | +0.114 [+0.018, +0.204] | 0.024 (±0.0022; B 10000) | 0.550 / 0.647 | -0.097 [-0.403, +0.320] | 0.717 (±0.0096; B 9999) | 100 / 17 |  |
| change_level | hybrid_ggnn | 0.168 / 0.159 | +0.008 [-0.090, +0.101] | 0.826 (±0.0098; B 10000) | 0.650 / 0.235 | +0.415 [-0.068, +0.734] | 0.086 (±0.0041; B 9999) | 100 / 17 |  |

Table: `error_analysis/error_rate_gap.csv`; confusion by context and part for naive_rule, lr, rf, hgb, gnn_ggnn, hybrid_ggnn: `error_analysis/confusion.csv`.

Tables: `tables/rq4_subset.csv`, `tables/rq4_subset_gap.csv`, `tables/rq4_did.csv`, `tables/rq4_did_bestval.csv`, `tables/rq4_did_frame_update.csv`, `tables/rq4_ctx_category.csv`, `tables/rq4_subsystem_markers.csv`; error analysis in `error_analysis/` (confusion, disagreement sets, examples stratified by part and error `<task>_examples.md`). Figures: `figures/rq4_forest_pr_auc_*`, `figures/rq4_forest_f1_*` (hollow markers: < 30 positives).

## 7. Ablations

PR-AUC and paired difference vs full (test resamples B = 10000; Holm within task, over variants and scopes):

| task | scope | variant | model | n | n_pos | PR-AUC [CI] | Δ vs full [CI] |
|---|---|---|---|---|---|---|---|
| add_log | full_test | full | hybrid_ggnn | 4475 | 895 | 0.331 ± 0.046 [0.301, 0.367] |  |
| add_log | full_test | no_history | hybrid_ggnn_nohist | 4475 | 895 | 0.336 ± 0.035 [0.308, 0.369] | +0.005 [-0.008, +0.018] (p=0.442 (±0.0083; B 10000), Holm 1.000) |
| add_log | full_test | no_graph | mlp_full | 4475 | 895 | 0.331 ± 0.012 [0.300, 0.369] | -0.001 [-0.011, +0.010] (p=0.922 (±0.0100; B 10000), Holm 1.000) |
| add_log | full_test | history_only | mlp_hist | 4475 | 895 | 0.385 ± 0.009 [0.346, 0.431] | +0.054 [+0.024, +0.085] (p=<0.001 (±0.0003; B 10000), Holm 0.002) |
| add_log | full_test | graph_only | gnn_ggnn | 4475 | 895 | 0.367 ± 0.018 [0.337, 0.405] | +0.036 [+0.017, +0.055] (p=<0.001 (±0.0003; B 10000), Holm 0.003) |
| add_log | subset | full | hybrid_ggnn | 2952 | 673 | 0.360 ± 0.053 [0.325, 0.399] |  |
| add_log | subset | no_history | hybrid_ggnn_nohist | 2952 | 673 | 0.366 ± 0.044 [0.335, 0.400] | +0.006 [-0.010, +0.021] (p=0.446 (±0.0083; B 10000), Holm 1.000) |
| add_log | subset | no_graph | mlp_full | 2952 | 673 | 0.364 ± 0.010 [0.330, 0.404] | +0.004 [-0.009, +0.017] (p=0.522 (±0.0088; B 10000), Holm 1.000) |
| add_log | subset | history_only | mlp_hist | 2952 | 673 | 0.442 ± 0.009 [0.398, 0.495] | +0.083 [+0.050, +0.118] (p=<0.001 (±0.0002; B 10000), Holm 0.002) |
| add_log | subset | graph_only | gnn_ggnn | 2952 | 673 | 0.408 ± 0.019 [0.371, 0.451] | +0.048 [+0.026, +0.070] (p=<0.001 (±0.0002; B 10000), Holm 0.002) |
| remove_log | full_test | full | hybrid_ggnn | 3766 | 764 | 0.272 ± 0.016 [0.221, 0.338] |  |
| remove_log | full_test | no_history | hybrid_ggnn_nohist | 3766 | 764 | 0.262 ± 0.013 [0.213, 0.334] | -0.010 [-0.054, +0.030] (p=0.695 (±0.0095; B 10000), Holm 1.000) |
| remove_log | full_test | no_graph | mlp_full | 3766 | 764 | 0.268 ± 0.009 [0.222, 0.326] | -0.004 [-0.020, +0.011] (p=0.666 (±0.0094; B 10000), Holm 1.000) |
| remove_log | full_test | history_only | mlp_hist | 3766 | 764 | 0.227 ± 0.005 [0.197, 0.262] | -0.045 [-0.092, -0.002] (p=0.035 (±0.0026; B 10000), Holm 0.251) |
| remove_log | full_test | graph_only | gnn_ggnn | 3766 | 764 | 0.250 ± 0.016 [0.209, 0.302] | -0.022 [-0.064, +0.017] (p=0.275 (±0.0069; B 10000), Holm 1.000) |
| remove_log | subset | full | hybrid_ggnn | 3213 | 634 | 0.275 ± 0.017 [0.217, 0.351] |  |
| remove_log | subset | no_history | hybrid_ggnn_nohist | 3213 | 634 | 0.263 ± 0.014 [0.207, 0.346] | -0.011 [-0.066, +0.037] (p=0.688 (±0.0095; B 10000), Holm 1.000) |
| remove_log | subset | no_graph | mlp_full | 3213 | 634 | 0.266 ± 0.008 [0.214, 0.333] | -0.009 [-0.027, +0.007] (p=0.279 (±0.0069; B 10000), Holm 1.000) |
| remove_log | subset | history_only | mlp_hist | 3213 | 634 | 0.221 ± 0.004 [0.188, 0.260] | -0.054 [-0.109, -0.004] (p=0.031 (±0.0025; B 10000), Holm 0.251) |
| remove_log | subset | graph_only | gnn_ggnn | 3213 | 634 | 0.256 ± 0.020 [0.207, 0.316] | -0.019 [-0.071, +0.028] (p=0.438 (±0.0083; B 10000), Holm 1.000) |
| change_level | full_test | full | hybrid_ggnn | 585 | 117 | 0.352 ± 0.043 [0.225, 0.493] |  |
| change_level | full_test | no_history | hybrid_ggnn_nohist | 585 | 117 | 0.432 ± 0.106 [0.235, 0.600] | +0.080 [-0.003, +0.137] (p=0.072 (±0.0037; B 10000), Holm 0.573) |
| change_level | full_test | no_graph | mlp_full | 585 | 117 | 0.311 ± 0.033 [0.194, 0.450] | -0.042 [-0.098, +0.005] (p=0.082 (±0.0040; B 10000), Holm 0.574) |
| change_level | full_test | history_only | mlp_hist | 585 | 117 | 0.268 ± 0.026 [0.172, 0.419] | -0.084 [-0.181, +0.055] (p=0.233 (±0.0064; B 10000), Holm 1.000) |
| change_level | full_test | graph_only | gnn_ggnn | 585 | 117 | 0.353 ± 0.039 [0.203, 0.526] | +0.001 [-0.087, +0.072] (p=0.951 (±0.0100; B 10000), Holm 1.000) |
| change_level | subset | full | hybrid_ggnn | 499 | 100 | 0.323 ± 0.052 [0.172, 0.480] |  |
| change_level | subset | no_history | hybrid_ggnn_nohist | 499 | 100 | 0.405 ± 0.126 [0.184, 0.595] | +0.082 [-0.014, +0.140] (p=0.187 (±0.0058; B 10000), Holm 1.000) |
| change_level | subset | no_graph | mlp_full | 499 | 100 | 0.304 ± 0.046 [0.171, 0.468] | -0.019 [-0.063, +0.026] (p=0.435 (±0.0083; B 10000), Holm 1.000) |
| change_level | subset | history_only | mlp_hist | 499 | 100 | 0.252 ± 0.026 [0.139, 0.417] | -0.071 [-0.174, +0.083] (p=0.377 (±0.0078; B 10000), Holm 1.000) |
| change_level | subset | graph_only | gnn_ggnn | 499 | 100 | 0.344 ± 0.028 [0.180, 0.535] | +0.021 [-0.071, +0.087] (p=0.640 (±0.0093; B 10000), Holm 1.000) |

With F1 and every metric: `tables/ablation.csv`. Figure: `figures/ablation_*`.

## 8. Statistical tests

Paired cluster bootstrap (B = 10000) of the pooled difference A - B (primary) and of the macro difference (mean over test repositories of the per-repository PR-AUC), Holm within task per metric; Wilcoxon signed-rank over test repositories on seed-mean PR-AUC; Cliff's delta over per-(repository, seed) PR-AUC:

| task | comparison | n | Δ PR-AUC pooled [CI] | p (MC SE; B used) | p Holm | Δ PR-AUC macro [CI] | p macro (MC SE; B used) | p Holm (macro) | Wilcoxon p | Cliff's δ | Δ F1 [CI] | p Holm (F1) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | hybrid_ggnn vs hgb | 4475 | -0.073 [-0.099, -0.049] | <0.001 (±0.0002; B 10000) | 0.002 | -0.086 [-0.118, -0.043] | <0.001 (±0.0002; B 10000) | 0.002 | 0.094 (n=6) | -0.43 medium | -0.014 [-0.040, +0.011] | 0.278 |
| add_log | hybrid_ggnn vs rf | 4475 | -0.066 [-0.086, -0.048] | <0.001 (±0.0002; B 10000) | 0.002 | -0.064 [-0.103, -0.029] | <0.001 (±0.0004; B 10000) | 0.005 | 0.844 (n=6) | -0.33 small | -0.057 [-0.080, -0.035] | 0.002 |
| add_log | hybrid_ggnn vs lr | 4475 | +0.059 [+0.034, +0.084] | <0.001 (±0.0002; B 10000) | 0.002 | +0.049 [+0.020, +0.078] | 0.002 (±0.0007; B 10000) | 0.012 | 0.094 (n=6) | +0.33 medium | +0.096 [+0.066, +0.129] | 0.002 |
| add_log | hybrid_ggnn vs mlp_full | 4475 | +0.001 [-0.010, +0.011] | 0.922 (±0.0100; B 10000) | 1.000 | +0.004 [-0.009, +0.022] | 0.446 (±0.0083; B 10000) | 0.564 | 0.688 (n=6) | +0.01 negligible | +0.017 [+0.001, +0.034] | 0.063 |
| add_log | hybrid_ggnn vs naive_prior | 4475 | +0.126 [+0.100, +0.153] | <0.001 (±0.0002; B 10000) | 0.002 | +0.147 [+0.106, +0.192] | <0.001 (±0.0002; B 10000) | 0.002 | 0.031 (n=6) | +0.97 large | +0.196 [+0.164, +0.229] | 0.002 |
| add_log | hybrid_ggnn vs naive_size | 4475 | +0.120 [+0.095, +0.146] | <0.001 (±0.0002; B 10000) | 0.002 | +0.109 [+0.065, +0.158] | <0.001 (±0.0002; B 10000) | 0.002 | 0.062 (n=6) | +0.74 large | +0.060 [+0.031, +0.088] | 0.002 |
| add_log | hybrid_ggnn vs naive_rule | 4475 | +0.085 [+0.055, +0.115] | <0.001 (±0.0002; B 10000) | 0.002 | +0.110 [+0.063, +0.156] | <0.001 (±0.0002; B 10000) | 0.002 | 0.031 (n=6) | +0.82 large | +0.055 [+0.026, +0.081] | 0.002 |
| add_log | gnn_ggnn vs hgb | 4475 | -0.037 [-0.065, -0.011] | 0.005 (±0.0010; B 10000) | 0.014 | -0.069 [-0.104, -0.023] | 0.003 (±0.0007; B 10000) | 0.012 | 0.156 (n=6) | -0.36 medium | +0.049 [+0.020, +0.077] | 0.004 |
| add_log | gnn_rgcn vs hgb | 4475 | -0.041 [-0.070, -0.015] | 0.003 (±0.0008; B 10000) | 0.012 | -0.058 [-0.096, -0.014] | 0.010 (±0.0014; B 10000) | 0.030 | 0.219 (n=6) | -0.32 small | +0.064 [+0.038, +0.090] | 0.002 |
| add_log | gnn_ggnn vs gnn_rgcn | 4475 | +0.004 [-0.008, +0.016] | 0.531 (±0.0088; B 10000) | 1.000 | -0.011 [-0.026, +0.007] | 0.282 (±0.0070; B 10000) | 0.564 | 0.688 (n=6) | -0.08 negligible | -0.015 [-0.028, -0.002] | 0.057 |
| remove_log | hybrid_ggnn vs hgb | 3766 | -0.001 [-0.048, +0.049] | 0.944 (±0.0100; B 10000) | 1.000 | +0.022 [-0.030, +0.066] | 0.491 (±0.0086; B 9972) | 1.000 | 0.469 (n=7) | +0.13 negligible | +0.002 [-0.033, +0.037] | 1.000 |
| remove_log | hybrid_ggnn vs rf | 3766 | -0.021 [-0.059, +0.023] | 0.317 (±0.0073; B 10000) | 1.000 | +0.024 [-0.024, +0.060] | 0.372 (±0.0078; B 9972) | 1.000 | 0.375 (n=7) | +0.15 small | -0.003 [-0.040, +0.031] | 1.000 |
| remove_log | hybrid_ggnn vs lr | 3766 | +0.019 [-0.009, +0.044] | 0.164 (±0.0055; B 10000) | 1.000 | +0.004 [-0.063, +0.058] | 0.958 (±0.0100; B 9972) | 1.000 | 1.000 (n=7) | -0.03 negligible | +0.000 [-0.024, +0.023] | 1.000 |
| remove_log | hybrid_ggnn vs mlp_full | 3766 | +0.004 [-0.011, +0.020] | 0.666 (±0.0094; B 10000) | 1.000 | +0.017 [-0.015, +0.038] | 0.360 (±0.0077; B 9972) | 1.000 | 0.469 (n=7) | +0.08 negligible | -0.001 [-0.016, +0.013] | 1.000 |
| remove_log | hybrid_ggnn vs naive_prior | 3766 | +0.070 [+0.033, +0.116] | <0.001 (±0.0002; B 10000) | 0.002 | +0.091 [+0.052, +0.134] | <0.001 (±0.0002; B 9972) | 0.002 | 0.016 (n=7) | +0.66 large | +0.158 [+0.121, +0.197] | 0.002 |
| remove_log | hybrid_ggnn vs naive_size | 3766 | +0.109 [+0.056, +0.160] | <0.001 (±0.0003; B 10000) | 0.004 | +0.116 [+0.024, +0.164] | 0.019 (±0.0020; B 9972) | 0.173 | 0.016 (n=7) | +0.83 large | +0.044 [+0.004, +0.082] | 0.275 |
| remove_log | hybrid_ggnn vs naive_rule | 3766 | +0.063 [-0.026, +0.129] | 0.149 (±0.0053; B 10000) | 1.000 | +0.073 [-0.020, +0.145] | 0.113 (±0.0046; B 9972) | 0.903 | 0.219 (n=7) | +0.44 medium | +0.079 [+0.018, +0.144] | 0.094 |
| remove_log | gnn_ggnn vs hgb | 3766 | -0.023 [-0.072, +0.024] | 0.338 (±0.0075; B 10000) | 1.000 | -0.006 [-0.063, +0.031] | 0.587 (±0.0091; B 9972) | 1.000 | 0.938 (n=7) | -0.11 negligible | -0.011 [-0.047, +0.029] | 1.000 |
| remove_log | gnn_rgcn vs hgb | 3766 | -0.034 [-0.076, +0.002] | 0.065 (±0.0035; B 10000) | 0.517 | -0.009 [-0.061, +0.028] | 0.468 (±0.0085; B 9972) | 1.000 | 0.688 (n=7) | -0.21 small | -0.010 [-0.041, +0.021] | 1.000 |
| remove_log | gnn_ggnn vs gnn_rgcn | 3766 | +0.011 [-0.009, +0.036] | 0.338 (±0.0075; B 10000) | 1.000 | +0.003 [-0.023, +0.027] | 0.858 (±0.0099; B 9972) | 1.000 | 0.812 (n=7) | +0.05 negligible | -0.000 [-0.018, +0.019] | 1.000 |
| change_level | hybrid_ggnn vs hgb | 585 | +0.058 [-0.083, +0.162] | 0.396 (±0.0080; B 10000) | 1.000 | +0.131 [+0.020, +0.192] | 0.013 (±0.0017; B 8704) | 0.093 | 0.375 (n=4) | +0.42 medium | +0.001 [-0.102, +0.096] | 1.000 |
| change_level | hybrid_ggnn vs rf | 585 | +0.001 [-0.077, +0.075] | 0.950 (±0.0100; B 10000) | 1.000 | +0.067 [-0.040, +0.128] | 0.237 (±0.0069; B 8704) | 1.000 | 0.875 (n=4) | -0.01 negligible | +0.012 [-0.087, +0.109] | 1.000 |
| change_level | hybrid_ggnn vs lr | 585 | +0.084 [-0.016, +0.170] | 0.096 (±0.0043; B 10000) | 0.675 | +0.096 [+0.026, +0.161] | 0.006 (±0.0012; B 8704) | 0.050 | 0.125 (n=4) | +0.40 medium | -0.069 [-0.180, +0.035] | 1.000 |
| change_level | hybrid_ggnn vs mlp_full | 585 | +0.042 [-0.005, +0.098] | 0.082 (±0.0040; B 10000) | 0.656 | -0.020 [-0.068, +0.062] | 0.839 (±0.0106; B 8704) | 1.000 | 0.875 (n=4) | +0.06 negligible | -0.055 [-0.136, +0.041] | 1.000 |
| change_level | hybrid_ggnn vs naive_prior | 585 | +0.135 [+0.050, +0.220] | <0.001 (±0.0004; B 10000) | 0.010 | +0.221 [+0.082, +0.289] | <0.001 (±0.0002; B 8704) | 0.002 | 0.125 (n=4) | +0.86 large | +0.192 [+0.064, +0.295] | 0.010 |
| change_level | hybrid_ggnn vs naive_size | 585 | +0.202 [+0.046, +0.312] | 0.015 (±0.0017; B 10000) | 0.131 | +0.289 [+0.124, +0.381] | <0.001 (±0.0002; B 8704) | 0.002 | 0.125 (n=4) | +1.00 large | +0.071 [-0.039, +0.162] | 1.000 |
| change_level | hybrid_ggnn vs naive_rule | 585 | +0.103 [-0.033, +0.197] | 0.135 (±0.0050; B 10000) | 0.809 | +0.153 [-0.253, +0.233] | 0.530 (±0.0095; B 8704) | 1.000 | 0.625 (n=4) | +0.53 large | +0.138 [-0.012, +0.256] | 0.652 |
| change_level | gnn_ggnn vs hgb | 585 | +0.058 [-0.129, +0.204] | 0.563 (±0.0090; B 10000) | 1.000 | +0.054 [-0.018, +0.113] | 0.149 (±0.0056; B 8704) | 0.895 | 0.625 (n=4) | +0.20 small | -0.050 [-0.127, +0.011] | 0.938 |
| change_level | gnn_rgcn vs hgb | 585 | -0.006 [-0.138, +0.101] | 0.938 (±0.0100; B 10000) | 1.000 | +0.038 [-0.043, +0.110] | 0.398 (±0.0086; B 8704) | 1.000 | 0.625 (n=4) | +0.12 negligible | -0.017 [-0.100, +0.064] | 1.000 |
| change_level | gnn_ggnn vs gnn_rgcn | 585 | +0.065 [-0.027, +0.148] | 0.235 (±0.0064; B 10000) | 1.000 | +0.016 [-0.024, +0.056] | 0.446 (±0.0089; B 8704) | 1.000 | 0.375 (n=4) | +0.03 negligible | -0.033 [-0.096, +0.029] | 1.000 |

Pooled PR-AUC ranks the concatenated scores of fold-specific models; scores of different folds are not calibrated to a common scale (cross-fold calibration), so the pooled value mixes ranking quality within folds with score shifts between folds. The macro value ranks within each fold only; its bootstrap uses only the resamples in which every test repository has a positive (B used).

Macro PR-AUC difference with and without the few-commit folds (positives from at most 2 commits; Holm within task over the pairs, separately for each column):

| task | comparison | folds left out | Δ macro [CI] | p (MC SE; B used) | p Holm | Δ macro without them [CI] | p without (MC SE; B used) | p Holm without |
|---|---|---|---|---|---|---|---|---|
| change_level | hybrid_ggnn vs hgb | OpenKeeper | +0.131 [+0.020, +0.192] | 0.013 (±0.0017; B 8704) | 0.093 | +0.024 [-0.040, +0.110] | 0.404 (±0.0080; B 9999) | 1.000 |
| change_level | hybrid_ggnn vs rf | OpenKeeper | +0.067 [-0.040, +0.128] | 0.237 (±0.0069; B 8704) | 1.000 | -0.023 [-0.101, +0.061] | 0.700 (±0.0095; B 9999) | 1.000 |
| change_level | hybrid_ggnn vs lr | OpenKeeper | +0.096 [+0.026, +0.161] | 0.006 (±0.0012; B 8704) | 0.050 | +0.082 [+0.012, +0.172] | 0.022 (±0.0021; B 9999) | 0.178 |
| change_level | hybrid_ggnn vs mlp_full | OpenKeeper | -0.020 [-0.068, +0.062] | 0.839 (±0.0106; B 8704) | 1.000 | +0.010 [-0.064, +0.066] | 0.765 (±0.0097; B 9999) | 1.000 |
| change_level | hybrid_ggnn vs naive_prior | OpenKeeper | +0.221 [+0.082, +0.289] | <0.001 (±0.0002; B 8704) | 0.002 | +0.107 [+0.036, +0.204] | 0.002 (±0.0007; B 9999) | 0.024 |
| change_level | hybrid_ggnn vs naive_size | OpenKeeper | +0.289 [+0.124, +0.381] | <0.001 (±0.0002; B 8704) | 0.002 | +0.168 [+0.062, +0.294] | 0.003 (±0.0007; B 9999) | 0.025 |
| change_level | hybrid_ggnn vs naive_rule | OpenKeeper | +0.153 [-0.253, +0.233] | 0.530 (±0.0095; B 8704) | 1.000 | +0.016 [-0.128, +0.128] | 0.840 (±0.0099; B 9999) | 1.000 |
| change_level | gnn_ggnn vs hgb | OpenKeeper | +0.054 [-0.018, +0.113] | 0.149 (±0.0056; B 8704) | 0.895 | +0.027 [-0.051, +0.108] | 0.457 (±0.0084; B 9999) | 1.000 |
| change_level | gnn_rgcn vs hgb | OpenKeeper | +0.038 [-0.043, +0.110] | 0.398 (±0.0086; B 8704) | 1.000 | +0.016 [-0.076, +0.109] | 0.729 (±0.0096; B 9999) | 1.000 |
| change_level | gnn_ggnn vs gnn_rgcn | OpenKeeper | +0.016 [-0.024, +0.056] | 0.446 (±0.0089; B 8704) | 1.000 | +0.011 [-0.036, +0.062] | 0.608 (±0.0092; B 9999) | 1.000 |

Full table (F1 tests, Wilcoxon Holm, statistics): `tables/pairwise.csv`.

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

Full table: `tables/sensitivity_ratio.csv`.

Multiclass supplement (method level, pooled over folds; mean ± sd over seeds). The majority_class row always predicts NO_EVENT; accuracy is listed last because the majority class alone reaches most of it:

| model | n | macro_f1 | balanced_accuracy | mcc | macro_precision | macro_recall | macro_pr_auc | accuracy |
|---|---|---|---|---|---|---|---|---|
| hgb_multiclass | 7150 | 0.339 ± 0.000 | 0.344 ± 0.000 | 0.254 ± 0.000 | 0.630 ± 0.000 | 0.344 ± 0.000 | 0.392 ± 0.000 | 0.800 ± 0.000 |
| lr_multiclass | 7150 | 0.336 ± 0.000 | 0.399 ± 0.000 | 0.186 ± 0.000 | 0.330 ± 0.000 | 0.399 ± 0.000 | 0.310 ± 0.000 | 0.591 ± 0.000 |
| majority_class | 7150 | 0.222 | 0.250 | 0.000 | 0.200 | 0.250 | – | 0.800 |

Per class: `tables/multiclass_per_class.csv`.

## 9. Sensitivity analysis: ADD_LOG commit-time view (add_log_post)

Not part of the primary analysis (author decision 2026-10-03). add_log_post is the ADD_LOG task in the masked post-state ('commit-time') view: every statement added in the commit is removed, with complete masking. The primary add_log view is the pre-state method. Every Holm family below is separate from the primary families.

The evaluated instances (positives, negatives, folds) and the commit-cluster resamples are those of add_log, so the two views are compared pairwise.

The subset/complement split and the context categories of the tables below are those of the pre-state view, so both views are compared on the same split; computed on the masked method, the performance-sensitive flag differs for 57 of 4475 instances (20 positives) and the context category for 98 (44 positives).

Pooled PR-AUC and F1 per model in both views; Δ = commit-time − pre-state, paired cluster bootstrap on identical resamples, Holm over the models per metric:

| model | n | PR-AUC pre-state | PR-AUC commit-time | Δ PR-AUC [CI] | p Holm | F1 pre-state | F1 commit-time | Δ F1 [CI] | p Holm (F1) |
|---|---|---|---|---|---|---|---|---|---|
| naive_prior | 4475 | 0.206 | 0.206 | +0.000 [+0.000, +0.000] | 1.000 | 0.188 | 0.188 | +0.000 [+0.000, +0.000] | 1.000 |
| naive_size | 4475 | 0.212 | 0.228 | +0.016 [+0.012, +0.020] | 0.002 | 0.324 | 0.357 | +0.033 [+0.023, +0.044] | 0.002 |
| naive_rule | 4475 | 0.246 | 0.273 | +0.026 [+0.011, +0.039] | 0.022 | 0.330 | 0.342 | +0.012 [-0.003, +0.026] | 0.455 |
| lr | 4475 | 0.273 | 0.303 | +0.030 [+0.008, +0.054] | 0.062 | 0.288 | 0.367 | +0.079 [+0.050, +0.108] | 0.002 |
| rf | 4475 | 0.398 | 0.409 | +0.012 [+0.000, +0.022] | 0.200 | 0.442 | 0.456 | +0.015 [+0.004, +0.026] | 0.064 |
| hgb | 4475 | 0.404 | 0.425 | +0.021 [+0.002, +0.039] | 0.178 | 0.398 | 0.448 | +0.049 [+0.033, +0.066] | 0.002 |
| mlp_hist | 4475 | 0.385 | 0.385 | +0.000 [+0.000, +0.000] | 1.000 | 0.404 | 0.404 | +0.000 [+0.000, +0.000] | 1.000 |
| mlp_full | 4475 | 0.331 | 0.336 | +0.005 [-0.015, +0.025] | 1.000 | 0.367 | 0.405 | +0.037 [+0.015, +0.060] | 0.006 |
| gnn_rgcn | 4475 | 0.363 | 0.321 | -0.042 [-0.058, -0.027] | 0.002 | 0.462 | 0.407 | -0.055 [-0.074, -0.038] | 0.002 |
| gnn_ggnn | 4475 | 0.367 | 0.311 | -0.056 [-0.075, -0.037] | 0.002 | 0.447 | 0.414 | -0.034 [-0.052, -0.015] | 0.005 |
| hybrid_ggnn_nohist | 4475 | 0.336 | 0.299 | -0.037 [-0.054, -0.021] | 0.002 | 0.395 | 0.398 | +0.002 [-0.017, +0.021] | 1.000 |
| hybrid_ggnn | 4475 | 0.331 | 0.329 | -0.002 [-0.021, +0.017] | 1.000 | 0.384 | 0.404 | +0.020 [+0.001, +0.039] | 0.173 |

Key comparisons in the commit-time view (Holm within this family):

| task | comparison | n | Δ PR-AUC pooled [CI] | p (MC SE; B used) | p Holm | Δ PR-AUC macro [CI] | p macro (MC SE; B used) | p Holm (macro) | Wilcoxon p | Cliff's δ | Δ F1 [CI] | p Holm (F1) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log_post | hybrid_ggnn vs hgb | 4475 | -0.096 [-0.128, -0.066] | <0.001 (±0.0002; B 10000) | <0.001 | -0.075 [-0.112, -0.032] | <0.001 (±0.0003; B 10000) | 0.001 | 0.062 (n=6) | -0.49 large | -0.044 [-0.069, -0.018] | <0.001 |
| add_log_post | gnn_ggnn vs hgb | 4475 | -0.114 [-0.147, -0.082] | <0.001 (±0.0002; B 10000) | <0.001 | -0.088 [-0.135, -0.031] | 0.002 (±0.0006; B 10000) | 0.002 | 0.031 (n=6) | -0.47 medium | -0.034 [-0.063, -0.008] | 0.008 |
| add_log_post | hybrid_ggnn vs naive_rule | 4475 | +0.057 [+0.034, +0.080] | <0.001 (±0.0002; B 10000) | <0.001 | +0.078 [+0.033, +0.118] | <0.001 (±0.0003; B 10000) | 0.001 | 0.031 (n=6) | +0.60 large | +0.063 [+0.035, +0.088] | <0.001 |

RQ4 difference-in-differences in the commit-time view (hybrid_ggnn - hgb):

| task | difference | metric | Δ subset [CI] | Δ complement [CI] | DiD [CI] | p (MC SE; B used) | p Holm | subset n / n_pos / commits | complement n / n_pos / commits | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| add_log_post | hybrid_ggnn - hgb | pr_auc | -0.091 [-0.125, -0.059] | -0.117 [-0.182, -0.054] | +0.026 [-0.044, +0.095] | 0.496 (±0.0086; B 10000) | 0.496 | 2952 / 673 / 509 | 1523 / 222 / 178 |  |
| add_log_post | hybrid_ggnn - hgb | f1 | -0.027 [-0.054, -0.001] | -0.113 [-0.170, -0.058] | +0.087 [+0.027, +0.147] | 0.004 (±0.0009; B 10000) | 0.004 | 2952 / 673 / 509 | 1523 / 222 / 178 |  |

Tables: `tables/sens_add_log_post_pooled.csv`, `tables/sens_add_log_post_macro.csv`, `tables/sens_add_log_post_per_repo.csv`, `tables/sens_add_log_post_vs_add_log.csv`, `tables/sens_add_log_post_pairwise.csv`, `tables/sens_add_log_post_subset.csv`, `tables/sens_add_log_post_did.csv`.

## 10. Post-hoc analysis: log1p preprocessing of tabular features (not pre-specified)

POST-HOC, added after the primary results were seen (author decision 2026-10-03), not tuned. lr_log1p, mlp_full_log1p and hybrid_ggnn_log1p equal lr, mlp_full and hybrid_ggnn except that every non-binary tabular column (more than 2 distinct values in the fit part) is transformed x → sign(x)·log1p(|x|) before imputation and standardisation. The primary models keep the pre-specified preprocessing; these results answer no research question on their own and are not part of any primary table, figure or Holm family. They are evaluated on the primary instances and resamples.

The transform also hits columns that the feature build already stores as log1p counts (the 128 `x_` lexical buckets, `h_commit_index`, `h_file_prior_churn`): those that are non-binary in the fit part are transformed twice.

Transformed columns per fold, from the sidecars (mean over folds and seeds; per group; of them already log1p counts):

- hybrid_ggnn_log1p / add_log: 175.8 columns (h=11; f=9; m=19.8; l=7; d=1; x=128); 130 of them transformed twice.
- lr_log1p / add_log: 175.8 columns (h=11; f=9; m=19.8; l=7; d=1; x=128); 130 of them transformed twice.
- mlp_full_log1p / add_log: 175.8 columns (h=11; f=9; m=19.8; l=7; d=1; x=128); 130 of them transformed twice.
- hybrid_ggnn_log1p / remove_log: 184.9 columns (h=11; f=9; m=19.9; l=7; s=9; d=1; x=128); 130 of them transformed twice.
- lr_log1p / remove_log: 184.9 columns (h=11; f=9; m=19.9; l=7; s=9; d=1; x=128); 130 of them transformed twice.
- mlp_full_log1p / remove_log: 184.9 columns (h=11; f=9; m=19.9; l=7; s=9; d=1; x=128); 130 of them transformed twice.
- hybrid_ggnn_log1p / change_level: 184.8 columns (h=11; f=9; m=19.8; l=7; s=9; d=1; x=128); 130 of them transformed twice.
- lr_log1p / change_level: 184.8 columns (h=11; f=9; m=19.8; l=7; s=9; d=1; x=128); 130 of them transformed twice.
- mlp_full_log1p / change_level: 184.8 columns (h=11; f=9; m=19.8; l=7; s=9; d=1; x=128); 130 of them transformed twice.

Pooled PR-AUC (post-hoc models next to their pre-specified versions and hgb):

| model | add_log | remove_log | change_level |
|---|---|---|---|
| lr | 0.273 ± 0.000 [0.245, 0.306] | 0.252 ± 0.000 [0.198, 0.322] | 0.268 ± 0.000 [0.173, 0.380] |
| lr_log1p | 0.298 ± 0.000 [0.268, 0.331] | 0.260 ± 0.000 [0.212, 0.320] | 0.272 ± 0.000 [0.177, 0.387] |
| mlp_full | 0.331 ± 0.012 [0.300, 0.369] | 0.268 ± 0.009 [0.222, 0.326] | 0.311 ± 0.033 [0.194, 0.450] |
| mlp_full_log1p | 0.370 ± 0.021 [0.336, 0.410] | 0.307 ± 0.020 [0.249, 0.384] | 0.309 ± 0.032 [0.194, 0.454] |
| hybrid_ggnn | 0.331 ± 0.046 [0.301, 0.367] | 0.272 ± 0.016 [0.221, 0.338] | 0.352 ± 0.043 [0.225, 0.493] |
| hybrid_ggnn_log1p | 0.384 ± 0.018 [0.350, 0.423] | 0.286 ± 0.026 [0.236, 0.353] | 0.370 ± 0.043 [0.239, 0.510] |
| hgb | 0.404 ± 0.000 [0.366, 0.453] | 0.273 ± 0.000 [0.231, 0.322] | 0.295 ± 0.000 [0.164, 0.449] |

Pooled F1:

| model | add_log | remove_log | change_level |
|---|---|---|---|
| lr | 0.288 ± 0.000 [0.256, 0.320] | 0.358 ± 0.000 [0.311, 0.411] | 0.453 ± 0.000 [0.291, 0.579] |
| lr_log1p | 0.319 ± 0.000 [0.288, 0.352] | 0.341 ± 0.000 [0.304, 0.379] | 0.433 ± 0.000 [0.268, 0.564] |
| mlp_full | 0.367 ± 0.037 [0.339, 0.397] | 0.359 ± 0.011 [0.315, 0.407] | 0.439 ± 0.055 [0.258, 0.604] |
| mlp_full_log1p | 0.400 ± 0.027 [0.371, 0.430] | 0.371 ± 0.011 [0.326, 0.416] | 0.446 ± 0.043 [0.246, 0.621] |
| hybrid_ggnn | 0.384 ± 0.037 [0.354, 0.417] | 0.358 ± 0.020 [0.315, 0.406] | 0.384 ± 0.089 [0.238, 0.490] |
| hybrid_ggnn_log1p | 0.419 ± 0.016 [0.389, 0.449] | 0.364 ± 0.012 [0.322, 0.406] | 0.384 ± 0.093 [0.240, 0.496] |
| hgb | 0.398 ± 0.000 [0.366, 0.431] | 0.357 ± 0.000 [0.319, 0.396] | 0.383 ± 0.000 [0.234, 0.524] |

Paired comparisons (Holm within task over these post-hoc comparisons only):

| task | comparison | n | Δ PR-AUC pooled [CI] | p (MC SE; B used) | p Holm | Δ PR-AUC macro [CI] | p macro (MC SE; B used) | p Holm (macro) | Wilcoxon p | Cliff's δ | Δ F1 [CI] | p Holm (F1) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| add_log | lr_log1p vs lr | 4475 | +0.025 [+0.014, +0.035] | <0.001 (±0.0002; B 10000) | <0.001 | +0.004 [-0.016, +0.025] | 0.544 (±0.0089; B 10000) | 0.544 | 0.688 (n=6) | +0.06 negligible | +0.031 [+0.010, +0.052] | 0.008 |
| add_log | mlp_full_log1p vs mlp_full | 4475 | +0.040 [+0.030, +0.049] | <0.001 (±0.0002; B 10000) | <0.001 | +0.020 [+0.012, +0.033] | <0.001 (±0.0002; B 10000) | <0.001 | 0.312 (n=6) | +0.14 negligible | +0.033 [+0.022, +0.044] | <0.001 |
| add_log | hybrid_ggnn_log1p vs hybrid_ggnn | 4475 | +0.053 [+0.041, +0.066] | <0.001 (±0.0002; B 10000) | <0.001 | +0.027 [+0.013, +0.039] | <0.001 (±0.0002; B 10000) | <0.001 | 0.219 (n=6) | +0.20 small | +0.034 [+0.022, +0.047] | <0.001 |
| add_log | hybrid_ggnn_log1p vs hgb | 4475 | -0.020 [-0.046, +0.005] | 0.114 (±0.0046; B 10000) | 0.114 | -0.059 [-0.090, -0.020] | 0.004 (±0.0008; B 10000) | 0.007 | 0.156 (n=6) | -0.31 small | +0.020 [-0.006, +0.046] | 0.132 |
| remove_log | lr_log1p vs lr | 3766 | +0.008 [-0.027, +0.036] | 0.584 (±0.0091; B 10000) | 1.000 | -0.004 [-0.046, +0.030] | 0.863 (±0.0099; B 9972) | 1.000 | 0.812 (n=7) | -0.06 negligible | -0.017 [-0.043, +0.008] | 0.767 |
| remove_log | mlp_full_log1p vs mlp_full | 3766 | +0.039 [-0.005, +0.084] | 0.079 (±0.0039; B 10000) | 0.317 | +0.045 [+0.013, +0.071] | 0.005 (±0.0010; B 9972) | 0.018 | 0.016 (n=7) | +0.27 small | +0.011 [-0.014, +0.032] | 1.000 |
| remove_log | hybrid_ggnn_log1p vs hybrid_ggnn | 3766 | +0.014 [-0.029, +0.050] | 0.455 (±0.0084; B 10000) | 1.000 | +0.005 [-0.013, +0.024] | 0.562 (±0.0090; B 9972) | 1.000 | 0.688 (n=7) | -0.03 negligible | +0.006 [-0.022, +0.029] | 1.000 |
| remove_log | hybrid_ggnn_log1p vs hgb | 3766 | +0.013 [-0.028, +0.055] | 0.546 (±0.0089; B 10000) | 1.000 | +0.027 [-0.021, +0.067] | 0.315 (±0.0073; B 9972) | 0.944 | 0.578 (n=7) | +0.08 negligible | +0.007 [-0.025, +0.039] | 1.000 |
| change_level | lr_log1p vs lr | 585 | +0.004 [-0.036, +0.056] | 0.818 (±0.0098; B 10000) | 1.000 | -0.023 [-0.056, +0.054] | 0.799 (±0.0105; B 8704) | 1.000 | 0.875 (n=4) | +0.00 negligible | -0.019 [-0.062, +0.012] | 1.000 |
| change_level | mlp_full_log1p vs mlp_full | 585 | -0.002 [-0.022, +0.024] | 0.917 (±0.0100; B 10000) | 1.000 | -0.007 [-0.033, +0.038] | 0.990 (±0.0107; B 8704) | 1.000 | 0.625 (n=4) | +0.01 negligible | +0.007 [-0.045, +0.046] | 1.000 |
| change_level | hybrid_ggnn_log1p vs hybrid_ggnn | 585 | +0.018 [-0.006, +0.043] | 0.175 (±0.0057; B 10000) | 0.701 | +0.000 [-0.015, +0.026] | 0.684 (±0.0102; B 8704) | 1.000 | 1.000 (n=4) | +0.05 negligible | -0.000 [-0.020, +0.022] | 1.000 |
| change_level | hybrid_ggnn_log1p vs hgb | 585 | +0.076 [-0.063, +0.172] | 0.271 (±0.0068; B 10000) | 0.813 | +0.131 [+0.036, +0.194] | 0.006 (±0.0011; B 8704) | 0.023 | 0.375 (n=4) | +0.47 large | +0.001 [-0.104, +0.100] | 1.000 |

Tables: `tables/posthoc_log1p_pooled.csv`, `tables/posthoc_log1p_macro.csv`, `tables/posthoc_log1p_pairwise.csv`, `tables/posthoc_log1p_training.csv`.

## 11. Limitations of evidence

- Confidence intervals of single metrics use B = 1000 resamples, paired tests (pairwise, ablation, difference-in-differences, subset gaps) B = 10000. Bootstrap p-values cannot be smaller than 2/(B+1) = 0.00020; Holm-adjusted values are bounded below by that floor times the family size. The Monte-Carlo standard error of each p is reported next to it.
- RQ4 reference model: the difference-in-differences uses hgb as reference, fixed a priori, because choosing the best classical model on the test folds would be a post-hoc selection on test data. A reference chosen on validation PR-AUC is reported as a sensitivity check (section 6).
- PR-AUC depends on the prevalence; group comparisons (subset/complement, categories, engines, sizes, ecosystems, repositories) differ in prevalence and are read through lift and ROC-AUC.
- Pooled ranking metrics concatenate fold-specific models whose scores are not calibrated across folds; the macro values and the macro paired bootstrap are reported next to them.
- A bootstrap resample without a positive in the instances a value needs leaves that value undefined; such resamples are left out and every CI and test reports how many it used (b_used, B used). A macro value (CI, macro paired test, macro without few-commit folds) is defined only in the resamples in which every repository of the macro has a positive, so all its resamples estimate the same mean over the same repositories; the resamples left out are those in which a repository with positives from few commits drew none of them.
- Support floor: a comparison on a part with < 10 positives or positives from at most 2 commits (the few-commit rule of the folds) is descriptive only: Δ and CI are shown, without p, and it is not counted in its Holm family.
- Descriptive only in this run (below the support floor): rq4_did_frame_update change_level (subset 3 pos / 2 commits).
- add_log: test repositories OpenKeeper, Mindustry, subspace-infinity, riiablo, OpenRTS, SkyHussars; low-support folds (< 30 positives): SkyHussars; not a test fold (< 10 positives): shattered-pixel-dungeon (1), Archer-Game-Template2 (4), jme3rpg (7); few-commit folds: none.
- remove_log: test repositories OpenKeeper, Mindustry, subspace-infinity, riiablo, OpenRTS, SkyHussars, jme3rpg; low-support folds (< 30 positives): SkyHussars, jme3rpg; not a test fold (< 10 positives): shattered-pixel-dungeon (3), Archer-Game-Template2 (0); few-commit folds: none.
- change_level: test repositories OpenKeeper, Mindustry, subspace-infinity, riiablo; low-support folds (< 30 positives): OpenKeeper, subspace-infinity; not a test fold (< 10 positives): shattered-pixel-dungeon (0), OpenRTS (1), SkyHussars (1), Archer-Game-Template2 (0), jme3rpg (0); few-commit folds: OpenKeeper.
- add_log: evaluated repositories with < 30 positives: SkyHussars.
- change_level: evaluated repositories with < 30 positives: OpenKeeper, subspace-infinity.
- remove_log: evaluated repositories with < 30 positives: SkyHussars, jme3rpg.
- add_log: Wilcoxon over 6 test repositories; smallest attainable two-sided p = 0.0312.
- change_level: Wilcoxon over 4 test repositories; smallest attainable two-sided p = 0.1250.
- remove_log: Wilcoxon over 7 test repositories; smallest attainable two-sided p = 0.0156.
