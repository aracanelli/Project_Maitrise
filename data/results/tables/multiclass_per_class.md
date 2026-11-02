**Multiclass supplement (NO_EVENT/ADD_LOG/REMOVE_LOG/CHANGE_LEVEL), pooled over LORO folds; mean ± sd over seeds; balanced accuracy = macro recall; majority_class = always the most frequent class; n = instances (n_class per class).**

| setting | model | class | n_class | f1_mean | f1_sd | pr_auc_mean | pr_auc_sd |
|---|---|---|---|---|---|---|---|
| R4 | hgb_multiclass | NO_EVENT | 5720 | 0.895 | 0.000 | 0.921 | 0.000 |
| R4 | hgb_multiclass | ADD_LOG | 857 | 0.061 | 0.000 | 0.200 | 0.000 |
| R4 | hgb_multiclass | REMOVE_LOG | 493 | 0.375 | 0.000 | 0.363 | 0.000 |
| R4 | hgb_multiclass | CHANGE_LEVEL | 80 | 0.025 | 0.000 | 0.086 | 0.000 |
| R4 | lr_multiclass | NO_EVENT | 5720 | 0.745 | 0.000 | 0.867 | 0.000 |
| R4 | lr_multiclass | ADD_LOG | 857 | 0.204 | 0.000 | 0.143 | 0.000 |
| R4 | lr_multiclass | REMOVE_LOG | 493 | 0.345 | 0.000 | 0.200 | 0.000 |
| R4 | lr_multiclass | CHANGE_LEVEL | 80 | 0.050 | 0.000 | 0.029 | 0.000 |
