**Imbalance handling per task and model: negative sampling, class weighting and decision-threshold rule (prediction sidecars). n = 36 rows.**

| setting | task | model | negative_sampling | class_weighting | pos_weight_mean | threshold_rule | threshold_mean | threshold_min | threshold_max |
|---|---|---|---|---|---|---|---|---|---|
| R4 | add_log | naive_prior | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score < threshold (training prevalence) | 0.199 | 0.197 | 0.200 |
| R4 | add_log | naive_size | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 12.833 | 9.000 | 19.000 |
| R4 | add_log | naive_rule | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 0.013 | 0.009 | 0.019 |
| R4 | add_log | lr | 4 negatives per positive per repository (seeded, nested) | class_weight=balanced | – | score >= threshold (F1-max on validation) | 0.666 | 0.573 | 0.792 |
| R4 | add_log | rf | 4 negatives per positive per repository (seeded, nested) | class_weight=balanced_subsample | – | score >= threshold (F1-max on validation) | 0.303 | 0.145 | 0.416 |
| R4 | add_log | hgb | 4 negatives per positive per repository (seeded, nested) | none (unweighted loss) | – | score >= threshold (F1-max on validation) | 0.223 | 0.132 | 0.308 |
| R4 | add_log | mlp_hist | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.017 | score >= threshold (F1-max on validation) | 0.610 | 0.472 | 0.756 |
| R4 | add_log | mlp_full | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.017 | score >= threshold (F1-max on validation) | 0.617 | 0.404 | 0.790 |
| R4 | add_log | gnn_rgcn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.017 | score >= threshold (F1-max on validation) | 0.568 | 0.298 | 0.824 |
| R4 | add_log | gnn_ggnn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.017 | score >= threshold (F1-max on validation) | 0.562 | 0.332 | 0.783 |
| R4 | add_log | hybrid_ggnn_nohist | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.017 | score >= threshold (F1-max on validation) | 0.563 | 0.096 | 0.805 |
| R4 | add_log | hybrid_ggnn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.017 | score >= threshold (F1-max on validation) | 0.614 | 0.129 | 0.860 |
| R4 | remove_log | naive_prior | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score < threshold (training prevalence) | 0.201 | 0.197 | 0.204 |
| R4 | remove_log | naive_size | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 6.714 | 3.000 | 16.000 |
| R4 | remove_log | naive_rule | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 0.455 | 0.003 | 2.025 |
| R4 | remove_log | lr | 4 negatives per positive per repository (seeded, nested) | class_weight=balanced | – | score >= threshold (F1-max on validation) | 0.224 | 0.008 | 0.526 |
| R4 | remove_log | rf | 4 negatives per positive per repository (seeded, nested) | class_weight=balanced_subsample | – | score >= threshold (F1-max on validation) | 0.224 | 0.115 | 0.283 |
| R4 | remove_log | hgb | 4 negatives per positive per repository (seeded, nested) | none (unweighted loss) | – | score >= threshold (F1-max on validation) | 0.175 | 0.133 | 0.210 |
| R4 | remove_log | mlp_hist | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 3.964 | score >= threshold (F1-max on validation) | 0.513 | 0.350 | 0.640 |
| R4 | remove_log | mlp_full | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 3.964 | score >= threshold (F1-max on validation) | 0.494 | 0.021 | 0.865 |
| R4 | remove_log | gnn_rgcn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 3.964 | score >= threshold (F1-max on validation) | 0.458 | 0.026 | 0.797 |
| R4 | remove_log | gnn_ggnn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 3.964 | score >= threshold (F1-max on validation) | 0.509 | 0.020 | 0.920 |
| R4 | remove_log | hybrid_ggnn_nohist | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 3.964 | score >= threshold (F1-max on validation) | 0.453 | 0.000 | 0.913 |
| R4 | remove_log | hybrid_ggnn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 3.964 | score >= threshold (F1-max on validation) | 0.484 | 0.061 | 0.850 |
| R4 | change_level | naive_prior | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score < threshold (training prevalence) | 0.198 | 0.194 | 0.199 |
| R4 | change_level | naive_size | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 6.000 | 4.000 | 9.000 |
| R4 | change_level | naive_rule | 4 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 1.163 | 0.500 | 2.000 |
| R4 | change_level | lr | 4 negatives per positive per repository (seeded, nested) | class_weight=balanced | – | score >= threshold (F1-max on validation) | 0.006 | 0.000 | 0.012 |
| R4 | change_level | rf | 4 negatives per positive per repository (seeded, nested) | class_weight=balanced_subsample | – | score >= threshold (F1-max on validation) | 0.131 | 0.031 | 0.222 |
| R4 | change_level | hgb | 4 negatives per positive per repository (seeded, nested) | none (unweighted loss) | – | score >= threshold (F1-max on validation) | 0.127 | 0.074 | 0.186 |
| R4 | change_level | mlp_hist | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.064 | score >= threshold (F1-max on validation) | 0.351 | 0.056 | 0.692 |
| R4 | change_level | mlp_full | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.064 | score >= threshold (F1-max on validation) | 0.326 | 0.000 | 0.604 |
| R4 | change_level | gnn_rgcn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.064 | score >= threshold (F1-max on validation) | 0.316 | 0.040 | 0.736 |
| R4 | change_level | gnn_ggnn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.064 | score >= threshold (F1-max on validation) | 0.427 | 0.001 | 0.892 |
| R4 | change_level | hybrid_ggnn_nohist | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.064 | score >= threshold (F1-max on validation) | 0.410 | 0.008 | 0.814 |
| R4 | change_level | hybrid_ggnn | 4 negatives per positive per repository (seeded, nested) | pos_weight=balanced (n_neg/n_pos of the fit part) | 4.064 | score >= threshold (F1-max on validation) | 0.272 | 0.001 | 0.796 |
