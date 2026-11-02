**Mean validation PR-AUC (over folds and seeds, from the sidecars) of the classical models; selected = reference of the RQ4 sensitivity check. n_val_folds = validation values (folds x seeds) averaged per row.**

| setting | task | model | val_pr_auc_mean | n_val_folds | selected |
|---|---|---|---|---|---|
| R10 | add_log | lr | 0.277 | 30 |  |
| R10 | add_log | rf | 0.347 | 30 | yes |
| R10 | add_log | hgb | 0.341 | 30 |  |
| R10 | remove_log | lr | 0.221 | 35 |  |
| R10 | remove_log | rf | 0.222 | 35 |  |
| R10 | remove_log | hgb | 0.250 | 35 | yes |
| R10 | change_level | lr | 0.222 | 20 |  |
| R10 | change_level | rf | 0.299 | 20 | yes |
| R10 | change_level | hgb | 0.272 | 20 |  |
