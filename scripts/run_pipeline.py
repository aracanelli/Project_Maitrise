"""
Run the pipeline stages in order, from cloning the corpus to the run manifest.

Each stage is a separate script that can also run on its own. Datasets and features are
always rebuilt; graphs are rebuilt when their instances or code changed. The model stages
(scripts/run_experiments.py) reuse predictions made under the same run key and stop with
exit 2 when existing predictions came from other inputs or code, for example after the
instances were rebuilt. --overwrite is passed on to every run_experiments command, which
then recomputes all its predictions; combine it with --from/--to to limit it to the
stages that need it.

Usage:
    python -m scripts.run_pipeline [--from STAGE] [--to STAGE] [--workers 16] [--overwrite] [--dry-run]

Stages: corpus, screen, mine, datasets, features, graphs, classical, neural, posthoc,
        sensitivity, multiclass, evaluate, manifest

Primary tasks come from configs/experiment.yaml (add_log, remove_log, change_level).
add_log_post is the commit-time (masked post-state) sensitivity view of add_log: it gets
features, graphs, the R4 classical and neural/graph runs, but no post-hoc or R1/R10 runs.
The posthoc stage runs the log1p variants of lr, mlp_full and hybrid_ggnn, which are
reported separately as post-hoc models.
"""

import argparse
import subprocess
import sys
import time

from src.common.config import ROOT, corpus_repos, load_config

PY = sys.executable

STAGES = ["corpus", "screen", "mine", "datasets", "features", "graphs", "classical", "neural",
          "posthoc", "sensitivity", "multiclass", "evaluate", "manifest"]
SENSITIVITY_TASKS = ["add_log_post"]
POSTHOC_MODELS = "lr_log1p,mlp_full_log1p,hybrid_ggnn_log1p"


def stage_commands(stage, tasks, seeds, workers, overwrite=False):
    """`python -m` argument lists of one stage; tasks are the primary binary tasks."""
    cmds = _commands(stage, tasks, seeds, workers)
    if overwrite:
        cmds = [c + ["--overwrite"] if c[0] == "scripts.run_experiments" else c for c in cmds]
    return cmds


def _commands(stage, tasks, seeds, workers):
    view_tasks = []   # add_log, add_log_post, remove_log, change_level
    for t in tasks:
        view_tasks.append(t)
        if t == "add_log":
            view_tasks += SENSITIVITY_TASKS
    if stage == "corpus":
        return [["scripts.setup_corpus"]]
    if stage == "screen":
        return [["scripts.screen_corpus", "--workers", workers]]
    if stage == "mine":
        return [["scripts.mine_history", "--repo", r["name"], "--workers", workers]
                for r in corpus_repos(modeling_only=True)]
    if stage == "datasets":
        return [["scripts.build_datasets"]]
    if stage == "features":
        return [["scripts.extract_features", "--task", t, "--workers", workers]
                for t in view_tasks + ["multiclass"]]
    if stage == "graphs":
        return [["scripts.build_graphs", "--task", t, "--workers", workers] for t in view_tasks]
    if stage == "classical":
        return [["scripts.run_experiments", "--setting", "R4", "--task", t,
                 "--models", "naive,classical", "--seeds", seeds, "--importance"] for t in view_tasks]
    if stage == "neural":
        return [["scripts.run_experiments", "--setting", "R4", "--task", t,
                 "--models", "neural,graph", "--seeds", seeds] for t in view_tasks]
    if stage == "posthoc":
        return [["scripts.run_experiments", "--setting", "R4", "--task", t,
                 "--models", POSTHOC_MODELS, "--seeds", seeds] for t in tasks]
    if stage == "sensitivity":
        return [["scripts.run_experiments", "--setting", setting, "--task", t,
                 "--models", "naive,classical", "--seeds", seeds]
                for setting in ("R1", "R10") for t in tasks]
    if stage == "multiclass":
        return [["scripts.run_experiments", "--setting", "R4", "--task", "multiclass",
                 "--models", "lr_multiclass,hgb_multiclass", "--seeds", seeds]]
    if stage == "evaluate":
        return [["scripts.evaluate", "--setting", setting, "--lang", "both"] for setting in ("R4", "R1", "R10")]
    if stage == "manifest":
        return [["scripts.write_manifest"]]
    raise ValueError(stage)


def run(args):
    print("\n$ " + " ".join(args), flush=True)
    t0 = time.time()
    res = subprocess.run([PY, "-m"] + args, cwd=ROOT)
    print(f"  -> exit {res.returncode} in {time.time() - t0:.0f}s", flush=True)
    if res.returncode != 0:
        sys.exit(res.returncode)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the pipeline stages in order. "
                                             "Stages: " + ", ".join(STAGES) + ".")
    ap.add_argument("--from", dest="start", choices=STAGES, default=STAGES[0], metavar="STAGE",
                    help=f"first stage to run (default {STAGES[0]})")
    ap.add_argument("--to", dest="stop", choices=STAGES, default=STAGES[-1], metavar="STAGE",
                    help=f"last stage to run (default {STAGES[-1]})")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--overwrite", action="store_true",
                    help="pass --overwrite to every run_experiments command (recomputes all their predictions)")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = ap.parse_args(argv)
    if STAGES.index(args.start) > STAGES.index(args.stop):
        ap.error(f"--from {args.start} comes after --to {args.stop}")

    exp = load_config("experiment")
    tasks = [t for t in exp["tasks"] if t not in SENSITIVITY_TASKS]
    seeds = ",".join(str(s) for s in exp["protocol"]["seeds"])
    todo = STAGES[STAGES.index(args.start):STAGES.index(args.stop) + 1]

    for stage in todo:
        for cmd in stage_commands(stage, tasks, seeds, str(args.workers), args.overwrite):
            if args.dry_run:
                print("python -m " + " ".join(cmd))
            else:
                run(cmd)


if __name__ == "__main__":
    main()
