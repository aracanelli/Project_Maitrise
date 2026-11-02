**Extraction precision per event label from the annotation of validation/event_sample.csv (docs/16 rule), '?' excluded and counted as wrong; Wilson and commit-clustered bootstrap 95% CIs. ALL = label precisions weighted by the labels' shares of the core events (the sample is stratified by label); 'ALL (sample, unweighted)' is not a corpus estimate. n = 120 annotated events (n_annotated per row).**

| event_label | estimator | n_annotated | n_correct | n_wrong | n_unclear | n_commits | precision | wilson_ci_lo | wilson_ci_hi | cluster_ci_lo | cluster_ci_hi | b_used | precision_unclear_wrong | unclear_wrong_wilson_ci_lo | unclear_wrong_wilson_ci_hi | unclear_wrong_cluster_ci_lo | unclear_wrong_cluster_ci_hi | core_events | weight |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ADD_LOG | label | 40 | 38 | 2 | 0 | 37 | 0.950 | 0.835 | 0.986 | 0.875 | 1.000 | 1000 | 0.950 | 0.835 | 0.986 | 0.875 | 1.000 | 1225.000 | 0.580 |
| REMOVE_LOG | label | 40 | 34 | 6 | 0 | 37 | 0.850 | 0.709 | 0.929 | 0.737 | 0.951 | 1000 | 0.850 | 0.709 | 0.929 | 0.737 | 0.951 | 767.000 | 0.363 |
| CHANGE_LEVEL | label | 40 | 39 | 1 | 0 | 29 | 0.975 | 0.871 | 0.996 | 0.919 | 1.000 | 1000 | 0.975 | 0.871 | 0.996 | 0.919 | 1.000 | 119.000 | 0.056 |
| ALL | stratified: label precisions weighted by their share of the core events | 120 | 111 | 9 | 0 | 103 | 0.915 | – | – | 0.857 | 0.964 | 1000 | 0.915 | – | – | 0.857 | 0.964 | 2111.000 | 1.000 |
| ALL (sample, unweighted) | pooled share of the label-stratified sample, not a corpus estimate | 120 | 111 | 9 | 0 | 103 | 0.925 | 0.864 | 0.960 | 0.877 | 0.967 | 1000 | 0.925 | 0.864 | 0.960 | 0.877 | 0.967 | – | – |
