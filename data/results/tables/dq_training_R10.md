**Training runs per model: seeds, completeness, evaluated instances (n_eval) and instances dropped for missing features or graphs, from the seed<k>.json sidecars. n_eval = evaluated instances and n_selected = instances of the setting, per model.**

| setting | task | model | n_seeds | eval_set_sha1 | code_sha1 | all_complete | n_folds_total | n_eval | n_selected | dropped_no_features | dropped_no_graph | fold_seconds_mean | seconds_per_seed | epochs_mean | threshold_mean | val_pr_auc_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R10 | add_log | naive_prior | 5 | 5c0ceb717b450e73e89563b7842e7666839a19c8 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 9977 | 9977 | 0 | 0 | 0.009 | 0.054 | – | 0.090 | 0.098 |
| R10 | add_log | naive_size | 5 | 5c0ceb717b450e73e89563b7842e7666839a19c8 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 9977 | 9977 | 0 | 0 | 0.010 | 0.062 | – | 10.500 | 0.100 |
| R10 | add_log | naive_rule | 5 | 5c0ceb717b450e73e89563b7842e7666839a19c8 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 9977 | 9977 | 0 | 0 | 0.009 | 0.052 | – | 0.012 | 0.109 |
| R10 | add_log | lr | 5 | 5c0ceb717b450e73e89563b7842e7666839a19c8 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 9977 | 9977 | 0 | 0 | 0.436 | 2.618 | – | 0.719 | 0.277 |
| R10 | add_log | rf | 5 | 5c0ceb717b450e73e89563b7842e7666839a19c8 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 9977 | 9977 | 0 | 0 | 2.533 | 15.200 | – | 0.226 | 0.347 |
| R10 | add_log | hgb | 5 | 5c0ceb717b450e73e89563b7842e7666839a19c8 | 17cda31f1809a54e15f9a3e050d65546232234f6 | yes | 30 | 9977 | 9977 | 0 | 0 | 4.411 | 26.464 | – | 0.171 | 0.341 |
| R10 | remove_log | naive_prior | 5 | cce83475293f643af0ecf927d0a4d6ad5d9009f8 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 7572 | 7572 | 0 | 0 | 0.007 | 0.052 | – | 0.102 | 0.113 |
| R10 | remove_log | naive_size | 5 | cce83475293f643af0ecf927d0a4d6ad5d9009f8 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 7572 | 7572 | 0 | 0 | 0.008 | 0.056 | – | 48.143 | 0.112 |
| R10 | remove_log | naive_rule | 5 | cce83475293f643af0ecf927d0a4d6ad5d9009f8 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 7572 | 7572 | 0 | 0 | 0.009 | 0.064 | – | 0.809 | 0.123 |
| R10 | remove_log | lr | 5 | cce83475293f643af0ecf927d0a4d6ad5d9009f8 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 7572 | 7572 | 0 | 0 | 0.319 | 2.232 | – | 0.547 | 0.221 |
| R10 | remove_log | rf | 5 | cce83475293f643af0ecf927d0a4d6ad5d9009f8 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 7572 | 7572 | 0 | 0 | 2.253 | 15.772 | – | 0.137 | 0.222 |
| R10 | remove_log | hgb | 5 | cce83475293f643af0ecf927d0a4d6ad5d9009f8 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 35 | 7572 | 7572 | 0 | 0 | 2.449 | 17.140 | – | 0.139 | 0.250 |
| R10 | change_level | naive_prior | 5 | 1e61a45e89990394eb4ea983a3847b10afe08f92 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 1309 | 1309 | 0 | 0 | 0.011 | 0.046 | – | 0.077 | 0.202 |
| R10 | change_level | naive_size | 5 | 1e61a45e89990394eb4ea983a3847b10afe08f92 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 1309 | 1309 | 0 | 0 | 0.010 | 0.038 | – | 4.250 | 0.115 |
| R10 | change_level | naive_rule | 5 | 1e61a45e89990394eb4ea983a3847b10afe08f92 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 1309 | 1309 | 0 | 0 | 0.008 | 0.032 | – | 1.200 | 0.272 |
| R10 | change_level | lr | 5 | 1e61a45e89990394eb4ea983a3847b10afe08f92 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 1309 | 1309 | 0 | 0 | 0.079 | 0.316 | – | 0.238 | 0.222 |
| R10 | change_level | rf | 5 | 1e61a45e89990394eb4ea983a3847b10afe08f92 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 1309 | 1309 | 0 | 0 | 1.506 | 6.022 | – | 0.081 | 0.299 |
| R10 | change_level | hgb | 5 | 1e61a45e89990394eb4ea983a3847b10afe08f92 | bced518ae228914cefe00b69fe8067d3737d98c7 | yes | 20 | 1309 | 1309 | 0 | 0 | 0.535 | 2.140 | – | 0.075 | 0.272 |
