**Group-level permutation importance (drop in average precision when the group's columns are permuted jointly on the test repository), mean ± sd over folds; group_name spells out the prefix; n_folds per row. 1 model(s), 3 task(s).**

| setting | task | model | group | importance_mean | importance_sd | n_folds | rank | group_name |
|---|---|---|---|---|---|---|---|---|
| R4 | add_log | hgb | h | 0.093 | 0.077 | 6 | 1 | history |
| R4 | add_log | hgb | f | 0.074 | 0.099 | 6 | 2 | file |
| R4 | add_log | hgb | l | 0.038 | 0.073 | 6 | 3 | logging context |
| R4 | add_log | hgb | m | 0.020 | 0.019 | 6 | 4 | method |
| R4 | add_log | hgb | d | 0.004 | 0.004 | 6 | 5 | domain |
| R4 | add_log | hgb | x | -0.001 | 0.024 | 6 | 6 | lexical |
| R4 | change_level | hgb | m | 0.040 | 0.066 | 4 | 1 | method |
| R4 | change_level | hgb | f | 0.031 | 0.025 | 4 | 2 | file |
| R4 | change_level | hgb | l | 0.030 | 0.055 | 4 | 3 | logging context |
| R4 | change_level | hgb | x | 0.026 | 0.055 | 4 | 4 | lexical |
| R4 | change_level | hgb | s | 0.009 | 0.012 | 4 | 5 | statement |
| R4 | change_level | hgb | d | -0.002 | 0.003 | 4 | 6 | domain |
| R4 | change_level | hgb | h | -0.002 | 0.071 | 4 | 7 | history |
| R4 | remove_log | hgb | x | 0.022 | 0.033 | 7 | 1 | lexical |
| R4 | remove_log | hgb | l | 0.012 | 0.015 | 7 | 2 | logging context |
| R4 | remove_log | hgb | m | 0.011 | 0.022 | 7 | 3 | method |
| R4 | remove_log | hgb | f | 0.010 | 0.020 | 7 | 4 | file |
| R4 | remove_log | hgb | s | 0.007 | 0.032 | 7 | 5 | statement |
| R4 | remove_log | hgb | d | 0.002 | 0.009 | 7 | 6 | domain |
| R4 | remove_log | hgb | h | -0.006 | 0.040 | 7 | 7 | history |
