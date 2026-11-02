**Top-15 single features by permutation importance (drop in average precision), mean ± sd over folds; x_ buckets belong to the lexical group; n_folds per row. 1 model(s), 3 task(s).**

| setting | task | model | feature | importance_mean | importance_sd | n_folds | rank | group_name |
|---|---|---|---|---|---|---|---|---|
| R4 | add_log | hgb | f_log_density | 0.070 | 0.072 | 6 | 1 | file |
| R4 | add_log | hgb | h_method_prior_log_events | 0.047 | 0.052 | 6 | 2 | history |
| R4 | add_log | hgb | l_log_density | 0.027 | 0.058 | 6 | 3 | logging context |
| R4 | add_log | hgb | h_repo_prior_log_event_rate | 0.026 | 0.048 | 6 | 4 | history |
| R4 | add_log | hgb | x_076 | 0.010 | 0.008 | 6 | 5 | lexical |
| R4 | add_log | hgb | h_author_prior_log_events | 0.007 | 0.007 | 6 | 6 | history |
| R4 | add_log | hgb | m_n_statements | 0.006 | 0.013 | 6 | 7 | method |
| R4 | add_log | hgb | h_file_prior_log_events | 0.005 | 0.010 | 6 | 8 | history |
| R4 | add_log | hgb | m_n_try | 0.004 | 0.015 | 6 | 9 | method |
| R4 | add_log | hgb | l_mean_level_ord | 0.004 | 0.009 | 6 | 10 | logging context |
| R4 | add_log | hgb | m_return_void | 0.003 | 0.007 | 6 | 11 | method |
| R4 | add_log | hgb | x_041 | 0.003 | 0.007 | 6 | 12 | lexical |
| R4 | add_log | hgb | h_file_prior_commits | 0.003 | 0.006 | 6 | 13 | history |
| R4 | add_log | hgb | h_days_since_file_change | 0.002 | 0.011 | 6 | 14 | history |
| R4 | add_log | hgb | f_n_imports | 0.002 | 0.010 | 6 | 15 | file |
| R4 | change_level | hgb | m_loc | 0.026 | 0.040 | 4 | 1 | method |
| R4 | change_level | hgb | x_122 | 0.025 | 0.051 | 4 | 2 | lexical |
| R4 | change_level | hgb | h_author_prior_commits | 0.021 | 0.030 | 4 | 3 | history |
| R4 | change_level | hgb | l_log_density | 0.018 | 0.031 | 4 | 4 | logging context |
| R4 | change_level | hgb | m_n_statements | 0.017 | 0.033 | 4 | 5 | method |
| R4 | change_level | hgb | h_author_prior_log_events | 0.017 | 0.022 | 4 | 6 | history |
| R4 | change_level | hgb | m_n_conditionals | 0.016 | 0.032 | 4 | 7 | method |
| R4 | change_level | hgb | m_n_if | 0.011 | 0.023 | 4 | 8 | method |
| R4 | change_level | hgb | l_mean_level_ord | 0.010 | 0.020 | 4 | 9 | logging context |
| R4 | change_level | hgb | f_n_formal_logs | 0.010 | 0.019 | 4 | 10 | file |
| R4 | change_level | hgb | f_n_imports | 0.009 | 0.018 | 4 | 11 | file |
| R4 | change_level | hgb | f_dominant_level_TRACE | 0.008 | 0.017 | 4 | 12 | file |
| R4 | change_level | hgb | s_rel_position | 0.005 | 0.007 | 4 | 13 | statement |
| R4 | change_level | hgb | h_repo_prior_log_event_rate | 0.004 | 0.008 | 4 | 14 | history |
| R4 | change_level | hgb | s_level_eq_file_dominant | 0.003 | 0.006 | 4 | 15 | statement |
| R4 | remove_log | hgb | h_author_prior_commits | 0.016 | 0.023 | 7 | 1 | history |
| R4 | remove_log | hgb | l_log_density | 0.011 | 0.011 | 7 | 2 | logging context |
| R4 | remove_log | hgb | x_028 | 0.010 | 0.016 | 7 | 3 | lexical |
| R4 | remove_log | hgb | f_log_density | 0.009 | 0.012 | 7 | 4 | file |
| R4 | remove_log | hgb | m_n_calls | 0.007 | 0.011 | 7 | 5 | method |
| R4 | remove_log | hgb | s_level_INFO | 0.007 | 0.012 | 7 | 6 | statement |
| R4 | remove_log | hgb | x_038 | 0.005 | 0.014 | 7 | 7 | lexical |
| R4 | remove_log | hgb | l_dominant_level_INFO | 0.005 | 0.013 | 7 | 8 | logging context |
| R4 | remove_log | hgb | x_102 | 0.004 | 0.008 | 7 | 9 | lexical |
| R4 | remove_log | hgb | x_016 | 0.004 | 0.008 | 7 | 10 | lexical |
| R4 | remove_log | hgb | x_018 | 0.004 | 0.007 | 7 | 11 | lexical |
| R4 | remove_log | hgb | s_depth | 0.003 | 0.007 | 7 | 12 | statement |
| R4 | remove_log | hgb | x_124 | 0.003 | 0.007 | 7 | 13 | lexical |
| R4 | remove_log | hgb | x_055 | 0.003 | 0.010 | 7 | 14 | lexical |
| R4 | remove_log | hgb | x_035 | 0.003 | 0.004 | 7 | 15 | lexical |
