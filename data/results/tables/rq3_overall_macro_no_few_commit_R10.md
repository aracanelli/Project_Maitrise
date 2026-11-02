**Macro average over test repositories without the few-commit folds (folds_excluded; n = remaining test instances). Setting R10, leave-one-repository-out. n = instances in the row, n_pos = positives; mean ± sd over seeds; 95% CI: commit-cluster bootstrap within repositories (B=1000) of the seed mean; paired tests on B=10000 resamples.**

| task | model | folds_excluded | n | n_pos | PR-AUC | PR-AUC 95% CI | F1 | F1 95% CI | Precision | Precision 95% CI | Recall | Recall 95% CI | ROC-AUC | MCC | Balanced accuracy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| change_level | naive_prior | OpenKeeper | 979 | 89 | 0.106 ± 0.010 | [0.077, 0.165] | 0.061 ± 0.036 | [0.041, 0.075] | 0.068 ± 0.041 | [0.040, 0.099] | 0.056 ± 0.034 | [0.042, 0.078] | 0.522 ± 0.027 | -0.018 ± 0.039 | 0.493 ± 0.018 |
| change_level | naive_size | OpenKeeper | 979 | 89 | 0.081 ± 0.000 | [0.045, 0.149] | 0.161 ± 0.000 | [0.100, 0.224] | 0.088 ± 0.000 | [0.054, 0.127] | 0.955 ± 0.000 | [0.864, 1.000] | 0.339 ± 0.000 | -0.061 ± 0.000 | 0.481 ± 0.000 |
| change_level | naive_rule | OpenKeeper | 979 | 89 | 0.151 ± 0.000 | [0.103, 0.269] | 0.157 ± 0.000 | [0.093, 0.219] | 0.094 ± 0.000 | [0.053, 0.135] | 0.740 ± 0.000 | [0.686, 0.833] | 0.567 ± 0.000 | 0.005 ± 0.000 | 0.504 ± 0.000 |
| change_level | lr | OpenKeeper | 979 | 89 | 0.108 ± 0.000 | [0.070, 0.173] | 0.136 ± 0.000 | [0.074, 0.205] | 0.084 ± 0.000 | [0.045, 0.130] | 0.650 ± 0.000 | [0.556, 0.733] | 0.539 ± 0.000 | -0.009 ± 0.000 | 0.491 ± 0.000 |
| change_level | rf | OpenKeeper | 979 | 89 | 0.197 ± 0.013 | [0.120, 0.302] | 0.208 ± 0.020 | [0.130, 0.275] | 0.134 ± 0.034 | [0.077, 0.193] | 0.900 ± 0.119 | [0.864, 0.923] | 0.637 ± 0.021 | 0.132 ± 0.030 | 0.577 ± 0.025 |
| change_level | hgb | OpenKeeper | 979 | 89 | 0.181 ± 0.000 | [0.101, 0.319] | 0.177 ± 0.000 | [0.086, 0.256] | 0.110 ± 0.000 | [0.048, 0.170] | 0.606 ± 0.000 | [0.468, 0.782] | 0.550 ± 0.000 | 0.022 ± 0.000 | 0.513 ± 0.000 |
