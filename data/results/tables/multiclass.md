**Multiclass supplement (NO_EVENT/ADD_LOG/REMOVE_LOG/CHANGE_LEVEL), pooled over LORO folds; mean ± sd over seeds; balanced accuracy = macro recall; majority_class = always the most frequent class; n = instances (n_class per class).**

| setting | model | n | n_seeds | macro_f1_mean | macro_f1_sd | balanced_accuracy_mean | balanced_accuracy_sd | mcc_mean | mcc_sd | macro_precision_mean | macro_precision_sd | macro_recall_mean | macro_recall_sd | macro_pr_auc_mean | macro_pr_auc_sd | accuracy_mean | accuracy_sd | predicts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R4 | hgb_multiclass | 7150 | 5 | 0.339 | 0.000 | 0.344 | 0.000 | 0.254 | 0.000 | 0.630 | 0.000 | 0.344 | 0.000 | 0.392 | 0.000 | 0.800 | 0.000 | – |
| R4 | lr_multiclass | 7150 | 5 | 0.336 | 0.000 | 0.399 | 0.000 | 0.186 | 0.000 | 0.330 | 0.000 | 0.399 | 0.000 | 0.310 | 0.000 | 0.591 | 0.000 | – |
| R4 | majority_class | 7150 | 1 | 0.222 | – | 0.250 | – | 0.000 | – | 0.200 | – | 0.250 | – | – | – | 0.800 | – | NO_EVENT |
