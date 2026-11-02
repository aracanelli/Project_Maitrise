# Learning logging decisions in Java games from Git history

Code and results for the ÉTS master's project *A GNN and Git-mining framework for logging optimization in Java-based games* (Anthony Racanelli, 2026).

The pipeline mines the Git history of open-source Java game repositories, finds three kinds of logging decisions at the method level and learns to predict them:

- `ADD_LOG`: a logging statement is added to an existing method;
- `REMOVE_LOG`: a logging statement is removed;
- `CHANGE_LEVEL`: a logging statement keeps its message but changes level.

Each instance gets two representations of the same pre-change method, a tabular feature vector and a typed graph. Twelve models are compared under leave-one-repository-out evaluation: naive baselines, logistic regression, random forest, histogram-based gradient boosting (HGB), MLPs, R-GCN, GGNN and hybrid GGNNs. A static performance-sensitive subset (loops, frame-update methods, game subsystems) tests whether the models help more where logging costs the most.

## Main results (R4 setting, pooled PR-AUC, prevalence 0.20)

| Task | Best model | PR-AUC [95% CI] | HGB | Hybrid GGNN |
|---|---|---:|---:|---:|
| ADD_LOG | HGB | 0.404 [0.366, 0.453] | 0.404 | 0.331 |
| REMOVE_LOG | Random forest | 0.293 [0.250, 0.341] | 0.273 | 0.272 |
| CHANGE_LEVEL | Hybrid GGNN, no history | 0.432 [0.235, 0.600] | 0.295 | 0.352 |

No GNN model significantly beats HGB. HGB beats the hybrid GGNN on ADD_LOG (−0.073, Holm-adjusted p = 0.002). The difference-in-differences test shows no extra advantage in the performance-sensitive subset. All tables, figures and the generated reports are in `data/results/`.

## Layout

| Path | Content |
|---|---|
| `src/parsing`, `src/detection` | srcML parsing, method units, logging-statement detection and level normalisation |
| `src/screening` | snapshot of the 16 screened repositories (RQ1) |
| `src/mining`, `src/matching` | Git history walk, method and statement matching, event labelling |
| `src/dataset` | task instances, negative sampling, input views, LORO folds |
| `src/features`, `src/graphs` | tabular features (7 groups) and typed method graphs |
| `src/models` | baselines, classical models, MLPs, GNNs, permutation importance |
| `src/evaluation` | metrics, cluster bootstrap, paired tests, tables, figures, reports |
| `scripts/` | one command-line entry point per pipeline stage, plus `run_pipeline.py` |
| `configs/` | corpus with pinned commits, extraction rules, performance-sensitive keywords, experiment settings |
| `tests/` | unit tests (about 320) |
| `data/results/` | published outputs: tables (CSV, Markdown, LaTeX), figures, reports, validation sheet, run manifest |

## Requirements

- Python 3.10 and [srcML](https://www.srcml.org) 1.1.0 on the `PATH`.
- Git.
- A CUDA GPU is optional. The reported runs used an RTX 4060 with CUDA 12.4; CPU runs work but are slower and get their own run keys.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
```

On Linux or macOS, use `.venv/bin/python`. The lock file pins the exact versions used for the report, including the PyTorch CUDA wheel index. `pyproject.toml` lists the unpinned dependencies.

## Checking the published numbers

The tables behind every number in the report are in `data/results/tables/`. For example, `rq3_overall_pooled.csv` holds the pooled metrics of the twelve models and `pairwise.csv` the paired comparisons. `data/results/report/experiment_report.md` reads them together.

Run the tests:

```bash
.venv/Scripts/python.exe -m pytest -q tests
```

## Reproducing the experiment

Every script prints its options with `--help`. Run commands from the repository root:

```bash
.venv/Scripts/python.exe -m scripts.run_pipeline --dry-run    # print the commands
.venv/Scripts/python.exe -m scripts.run_pipeline              # run every stage
.venv/Scripts/python.exe -m scripts.run_pipeline --from classical --to evaluate
```

| Stage | Script | Output |
|---|---|---|
| corpus | `setup_corpus` | `data/raw/repos/`: the 16 repositories cloned at the commits pinned in `configs/corpus.yaml` |
| screen | `screen_corpus` | `data/results/rq1/` |
| mine | `mine_history --repo <name>` | `data/interim/mining/<repo>/` |
| datasets | `build_datasets` | `data/processed/instances/` and folds |
| features | `extract_features --task <task>` | `data/processed/features/` |
| graphs | `build_graphs --task <task>` | `data/processed/graphs/` |
| classical, neural, posthoc, sensitivity, multiclass | `run_experiments` | `data/results/predictions/`, `data/results/importance/` |
| evaluate | `evaluate --setting R4 --lang both` (also R1, R10) | `data/results/tables`, `figures`, `report` |
| manifest | `write_manifest` | `data/results/run_manifest.json` |

Tasks: `add_log`, `remove_log` and `change_level` are the primary tasks. `add_log_post` is the commit-time view of `add_log`, used as a sensitivity analysis. `multiclass` is a four-class supplement. Settings: `R4` (four negatives per positive) is primary; `R1` and `R10` run the naive and classical models only.

Cost: mining, features and graphs take well under an hour on 16 cores; the naive and classical models take under half an hour in total. The neural and graph models are the expensive part: those of the ADD_LOG task alone took about 100 GPU hours on an RTX 4060. Predictions are cached under a run key that hashes the configuration, inputs and code. `run_experiments` refuses to mix predictions made from different inputs; add `--overwrite` to recompute.

## Extraction validation sheet

`data/results/validation/event_sample.csv` holds the 120 core events (40 per label) used to estimate extraction precision, with the judgment columns `label_correct`, `is_logging_statement`, `level_correct` and `notes`. `event_sample.md` shows the code excerpt and commit link of each event. Section 7.6.3 of the report describes how the sheet was produced. `scripts/sample_validation.py` draws a new sample.

## Reused code

Detection, srcML handling, the commit walk and the method and statement matching are adapted from the replication package of Zeng et al., *Studying the characteristics of logging practices in mobile apps: a case study on F-Droid* (Empirical Software Engineering, 2019). See `THIRD_PARTY_NOTICES.md`.

## Citation

> A. Racanelli, *Un cadre utilisant des GNN et l'analyse de l'historique Git pour l'optimisation des logs dans les jeux en Java*, master's project report, École de technologie supérieure, Montréal, 2026.

## Licence

MIT for the code written for this project (see `LICENSE`). The adapted parts listed in `THIRD_PARTY_NOTICES.md` keep their authors' credit. The mined repositories are not redistributed; `setup_corpus` clones them from their public remotes.
