**Macro average over test repositories without the few-commit folds (folds_excluded; n = remaining test instances). Setting R1, leave-one-repository-out. n = instances in the row, n_pos = positives; mean ± sd over seeds; 95% CI: commit-cluster bootstrap within repositories (B=1000) of the seed mean; paired tests on B=10000 resamples.**

| task | model | folds_excluded | n | n_pos | PR-AUC | PR-AUC 95% CI | F1 | F1 95% CI | Precision | Precision 95% CI | Recall | Recall 95% CI | ROC-AUC | MCC | Balanced accuracy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| change_level | naive_prior | OpenKeeper | 178 | 89 | 0.536 ± 0.024 | [0.409, 0.651] | 0.464 ± 0.021 | [0.367, 0.509] | 0.506 ± 0.016 | [0.356, 0.608] | 0.432 ± 0.031 | [0.382, 0.489] | 0.503 ± 0.019 | 0.012 ± 0.033 | 0.506 ± 0.017 |
| change_level | naive_size | OpenKeeper | 178 | 89 | 0.443 ± 0.000 | [0.293, 0.585] | 0.648 ± 0.000 | [0.489, 0.736] | 0.493 ± 0.000 | [0.344, 0.601] | 0.945 ± 0.000 | [0.847, 1.000] | 0.320 ± 0.000 | -0.064 ± 0.000 | 0.488 ± 0.000 |
| change_level | naive_rule | OpenKeeper | 178 | 89 | 0.663 ± 0.000 | [0.557, 0.775] | 0.667 ± 0.000 | [0.516, 0.751] | 0.500 ± 0.000 | [0.357, 0.602] | 1.000 ± 0.000 | [1.000, 1.000] | 0.632 ± 0.000 | 0.000 ± 0.000 | 0.500 ± 0.000 |
| change_level | lr | OpenKeeper | 178 | 89 | 0.646 ± 0.000 | [0.514, 0.772] | 0.683 ± 0.000 | [0.502, 0.772] | 0.553 ± 0.000 | [0.377, 0.664] | 0.899 ± 0.000 | [0.756, 0.984] | 0.667 ± 0.000 | 0.208 ± 0.000 | 0.583 ± 0.000 |
| change_level | rf | OpenKeeper | 178 | 89 | 0.686 ± 0.009 | [0.547, 0.802] | 0.676 ± 0.007 | [0.513, 0.756] | 0.538 ± 0.005 | [0.379, 0.641] | 0.933 ± 0.029 | [0.837, 0.995] | 0.691 ± 0.008 | 0.115 ± 0.022 | 0.552 ± 0.007 |
| change_level | hgb | OpenKeeper | 178 | 89 | 0.630 ± 0.000 | [0.484, 0.760] | 0.667 ± 0.000 | [0.495, 0.753] | 0.538 ± 0.000 | [0.369, 0.644] | 0.909 ± 0.000 | [0.788, 0.978] | 0.615 ± 0.000 | 0.092 ± 0.000 | 0.545 ± 0.000 |
