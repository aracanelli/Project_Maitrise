**Mean validation PR-AUC (over folds and seeds, from the sidecars) of the classical models; selected = reference of the RQ4 sensitivity check. n_val_folds = validation values (folds x seeds) averaged per row.**

| setting | task | model | val_pr_auc_mean | n_val_folds | selected |
|---|---|---|---|---|---|
| R4 | add_log | lr | 0.484 | 30 |  |
| R4 | add_log | rf | 0.519 | 30 |  |
| R4 | add_log | hgb | 0.526 | 30 | yes |
| R4 | remove_log | lr | 0.349 | 35 |  |
| R4 | remove_log | rf | 0.366 | 35 |  |
| R4 | remove_log | hgb | 0.384 | 35 | yes |
| R4 | change_level | lr | 0.375 | 20 |  |
| R4 | change_level | rf | 0.380 | 20 | yes |
| R4 | change_level | hgb | 0.340 | 20 |  |
