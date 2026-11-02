**Mean validation PR-AUC (over folds and seeds, from the sidecars) of the classical models; selected = reference of the RQ4 sensitivity check. n_val_folds = validation values (folds x seeds) averaged per row.**

| setting | task | model | val_pr_auc_mean | n_val_folds | selected |
|---|---|---|---|---|---|
| R1 | add_log | lr | 0.739 | 30 |  |
| R1 | add_log | rf | 0.787 | 30 |  |
| R1 | add_log | hgb | 0.795 | 30 | yes |
| R1 | remove_log | lr | 0.644 | 35 |  |
| R1 | remove_log | rf | 0.665 | 35 | yes |
| R1 | remove_log | hgb | 0.663 | 35 |  |
| R1 | change_level | lr | 0.795 | 20 |  |
| R1 | change_level | rf | 0.806 | 20 |  |
| R1 | change_level | hgb | 0.813 | 20 | yes |
