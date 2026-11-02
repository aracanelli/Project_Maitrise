**Training runs per model: seeds, completeness, evaluated instances (n_eval) and instances dropped for missing features or graphs, from the seed<k>.json sidecars. n_eval = evaluated instances and n_selected = instances of the setting, per model.**

| setting | task | model | n_seeds | eval_set_sha1 | code_sha1 | all_complete | n_folds_total | n_eval | n_selected | dropped_no_features | dropped_no_graph | fold_seconds_mean | seconds_per_seed | epochs_mean | threshold_mean | val_pr_auc_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | add_log | naive_prior | 5 | 8509ea580b44b6ecea954932f96c42b3a8593b49 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 1814 | 1814 | 0 | 0 | 0.009 | 0.052 | – | 0.499 | 0.503 |
| R1 | add_log | naive_size | 5 | 8509ea580b44b6ecea954932f96c42b3a8593b49 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 1814 | 1814 | 0 | 0 | 0.009 | 0.054 | – | 3.500 | 0.554 |
| R1 | add_log | naive_rule | 5 | 8509ea580b44b6ecea954932f96c42b3a8593b49 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 1814 | 1814 | 0 | 0 | 0.010 | 0.062 | – | 0.004 | 0.606 |
| R1 | add_log | lr | 5 | 8509ea580b44b6ecea954932f96c42b3a8593b49 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 1814 | 1814 | 0 | 0 | 0.085 | 0.508 | – | 0.199 | 0.739 |
| R1 | add_log | rf | 5 | 8509ea580b44b6ecea954932f96c42b3a8593b49 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 1814 | 1814 | 0 | 0 | 1.248 | 7.488 | – | 0.394 | 0.787 |
| R1 | add_log | hgb | 5 | 8509ea580b44b6ecea954932f96c42b3a8593b49 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 1814 | 1814 | 0 | 0 | 2.388 | 14.330 | – | 0.412 | 0.795 |
| R1 | remove_log | naive_prior | 5 | a7debc9de56b44eacf528fc6114c980f6a083db1 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 1534 | 1534 | 0 | 0 | 0.003 | 0.018 | – | 0.499 | 0.520 |
| R1 | remove_log | naive_size | 5 | a7debc9de56b44eacf528fc6114c980f6a083db1 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 1534 | 1534 | 0 | 0 | 0.006 | 0.044 | – | 4.571 | 0.460 |
| R1 | remove_log | naive_rule | 5 | a7debc9de56b44eacf528fc6114c980f6a083db1 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 1534 | 1534 | 0 | 0 | 0.003 | 0.024 | – | 0.005 | 0.458 |
| R1 | remove_log | lr | 5 | a7debc9de56b44eacf528fc6114c980f6a083db1 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 1534 | 1534 | 0 | 0 | 0.060 | 0.422 | – | 0.013 | 0.644 |
| R1 | remove_log | rf | 5 | a7debc9de56b44eacf528fc6114c980f6a083db1 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 1534 | 1534 | 0 | 0 | 1.016 | 7.114 | – | 0.215 | 0.665 |
| R1 | remove_log | hgb | 5 | a7debc9de56b44eacf528fc6114c980f6a083db1 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 1534 | 1534 | 0 | 0 | 1.077 | 7.538 | – | 0.271 | 0.663 |
| R1 | change_level | naive_prior | 5 | f8c6cd9671f8182bc5015f3f973be08891b9362e | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 238 | 238 | 0 | 0 | 0.008 | 0.032 | – | 0.449 | 0.806 |
| R1 | change_level | naive_size | 5 | f8c6cd9671f8182bc5015f3f973be08891b9362e | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 238 | 238 | 0 | 0 | 0.012 | 0.048 | – | 44.500 | 0.851 |
| R1 | change_level | naive_rule | 5 | f8c6cd9671f8182bc5015f3f973be08891b9362e | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 238 | 238 | 0 | 0 | 0.010 | 0.038 | – | 0.116 | 0.807 |
| R1 | change_level | lr | 5 | f8c6cd9671f8182bc5015f3f973be08891b9362e | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 238 | 238 | 0 | 0 | 0.029 | 0.114 | – | 0.179 | 0.795 |
| R1 | change_level | rf | 5 | f8c6cd9671f8182bc5015f3f973be08891b9362e | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 238 | 238 | 0 | 0 | 1.216 | 4.862 | – | 0.258 | 0.806 |
| R1 | change_level | hgb | 5 | f8c6cd9671f8182bc5015f3f973be08891b9362e | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 238 | 238 | 0 | 0 | 0.213 | 0.852 | – | 0.367 | 0.813 |
