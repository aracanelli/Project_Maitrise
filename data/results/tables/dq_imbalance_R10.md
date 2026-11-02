**Imbalance handling per task and model: negative sampling, class weighting and decision-threshold rule (prediction sidecars). n = 18 rows.**

| setting | task | model | negative_sampling | class_weighting | pos_weight_mean | threshold_rule | threshold_mean | threshold_min | threshold_max |
|---|---|---|---|---|---|---|---|---|---|
| R10 | add_log | naive_prior | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score < threshold (training prevalence) | 0.090 | 0.090 | 0.091 |
| R10 | add_log | naive_size | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 10.500 | 2.000 | 21.000 |
| R10 | add_log | naive_rule | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 0.012 | 0.002 | 0.021 |
| R10 | add_log | lr | 10 negatives per positive per repository (seeded, nested) | class_weight=balanced | – | score >= threshold (F1-max on validation) | 0.719 | 0.612 | 0.838 |
| R10 | add_log | rf | 10 negatives per positive per repository (seeded, nested) | class_weight=balanced_subsample | – | score >= threshold (F1-max on validation) | 0.226 | 0.129 | 0.318 |
| R10 | add_log | hgb | 10 negatives per positive per repository (seeded, nested) | none (unweighted loss) | – | score >= threshold (F1-max on validation) | 0.171 | 0.120 | 0.289 |
| R10 | remove_log | naive_prior | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score < threshold (training prevalence) | 0.102 | 0.098 | 0.110 |
| R10 | remove_log | naive_size | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 48.143 | 3.000 | 245.000 |
| R10 | remove_log | naive_rule | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 0.809 | 0.003 | 3.018 |
| R10 | remove_log | lr | 10 negatives per positive per repository (seeded, nested) | class_weight=balanced | – | score >= threshold (F1-max on validation) | 0.547 | 0.048 | 0.838 |
| R10 | remove_log | rf | 10 negatives per positive per repository (seeded, nested) | class_weight=balanced_subsample | – | score >= threshold (F1-max on validation) | 0.137 | 0.080 | 0.238 |
| R10 | remove_log | hgb | 10 negatives per positive per repository (seeded, nested) | none (unweighted loss) | – | score >= threshold (F1-max on validation) | 0.139 | 0.080 | 0.235 |
| R10 | change_level | naive_prior | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score < threshold (training prevalence) | 0.077 | 0.059 | 0.091 |
| R10 | change_level | naive_size | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 4.250 | 4.000 | 5.000 |
| R10 | change_level | naive_rule | 10 negatives per positive per repository (seeded, nested) | none (no training) | – | score >= threshold (F1-max on validation) | 1.200 | 0.000 | 3.167 |
| R10 | change_level | lr | 10 negatives per positive per repository (seeded, nested) | class_weight=balanced | – | score >= threshold (F1-max on validation) | 0.238 | 0.000 | 0.884 |
| R10 | change_level | rf | 10 negatives per positive per repository (seeded, nested) | class_weight=balanced_subsample | – | score >= threshold (F1-max on validation) | 0.081 | 0.020 | 0.231 |
| R10 | change_level | hgb | 10 negatives per positive per repository (seeded, nested) | none (unweighted loss) | – | score >= threshold (F1-max on validation) | 0.075 | 0.036 | 0.117 |
