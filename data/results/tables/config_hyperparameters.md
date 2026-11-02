**Hyperparameters and protocol, configs/experiment.yaml: fixed a priori, except the posthoc section (post-hoc log1p variants added on 2026-10-03; prespecified = False). n = 52 rows.**

| section | key | value | prespecified |
|---|---|---|---|
| sampling | seed | 42 | yes |
| sampling | ratios | 1, 4, 10 | yes |
| sampling | primary_ratio | 4 | yes |
| protocol | scheme | leave_one_repo_out | yes |
| protocol | min_test_positives | 10 | yes |
| protocol | low_support_positives | 30 | yes |
| protocol | val_fraction | 0.15 | yes |
| protocol | threshold | f1_on_validation | yes |
| protocol | seeds | 0, 1, 2, 3, 4 | yes |
| features | lexical_buckets | 128 | yes |
| models | lr.C | 1.0 | yes |
| models | lr.max_iter | 3000 | yes |
| models | lr.class_weight | balanced | yes |
| models | rf.n_estimators | 500 | yes |
| models | rf.min_samples_leaf | 2 | yes |
| models | rf.class_weight | balanced_subsample | yes |
| models | rf.n_jobs | 16 | yes |
| models | hgb.learning_rate | 0.05 | yes |
| models | hgb.max_iter | 400 | yes |
| models | hgb.max_leaf_nodes | 31 | yes |
| models | hgb.l2_regularization | 1.0 | yes |
| models | hgb.early_stopping | True | yes |
| models | mlp.hidden | 128 | yes |
| models | mlp.layers | 2 | yes |
| models | mlp.dropout | 0.2 | yes |
| models | gnn.hidden | 128 | yes |
| models | gnn.layers | 3 | yes |
| models | gnn.ggnn_steps | 6 | yes |
| models | gnn.num_bases | 4 | yes |
| models | gnn.token_dim | 32 | yes |
| models | gnn.type_dim | 32 | yes |
| models | gnn.dropout | 0.2 | yes |
| models | gnn.max_nodes | 2000 | yes |
| models | training.optimizer | adamw | yes |
| models | training.lr | 0.001 | yes |
| models | training.weight_decay | 0.0001 | yes |
| models | training.batch_size | 64 | yes |
| models | training.max_epochs | 60 | yes |
| models | training.patience | 8 | yes |
| models | training.early_stop_metric | pr_auc | yes |
| models | training.pos_weight | balanced | yes |
| posthoc | tabular_transform | signed_log1p_nonbinary |  |
| posthoc | models.lr_log1p | lr |  |
| posthoc | models.mlp_full_log1p | mlp_full |  |
| posthoc | models.hybrid_ggnn_log1p | hybrid_ggnn |  |
| posthoc | tasks | add_log, remove_log, change_level |  |
| evaluation | bootstrap_samples | 1000 | yes |
| evaluation | bootstrap_samples_tests | 10000 | yes |
| evaluation | bootstrap_cluster | commit | yes |
| evaluation | ci | 0.95 | yes |
| evaluation | alpha | 0.05 | yes |
| evaluation | correction | holm | yes |
