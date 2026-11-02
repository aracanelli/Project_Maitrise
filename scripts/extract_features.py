"""
Stage 5: extract the tabular features of one task.

Reads data/processed/instances/<task>.jsonl and data/interim/mining/<repo>/, writes
data/processed/features/<task>.csv, <task>_groups.json, <task>_failures.jsonl and
<task>_summary.json.

Tasks are add_log, add_log_post (sensitivity view of add_log), remove_log, change_level
and multiclass; 'all' runs every task whose instances file exists. Only full runs write
to data/processed/features/. A --limit run goes to features/limit<N>/, or to another
--out-dir (the default folder is refused).

Usage:
    python -m scripts.extract_features --task add_log [--workers 16]
    python -m scripts.extract_features --task add_log --limit N [--out-dir DIR]
    python -m scripts.extract_features --task all
"""

import argparse
from pathlib import Path

from src.features.extract import TASKS, INSTANCES_DIR, MINING_DIR, extract_task


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=list(TASKS) + ["all"])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--instances-dir", default=str(INSTANCES_DIR))
    ap.add_argument("--mining-dir", default=str(MINING_DIR))
    ap.add_argument("--out-dir", default=None,
                    help="default: data/processed/features/, or features/limit<N>/ with --limit")
    args = ap.parse_args()

    tasks = TASKS if args.task == "all" else [args.task]
    for task in tasks:
        if args.task == "all" and not (Path(args.instances_dir) / f"{task}.jsonl").exists():
            print(f"[{task}] no instances file, skipped")
            continue
        extract_task(task, workers=args.workers, limit=args.limit, instances_dir=args.instances_dir,
                     mining_dir=args.mining_dir, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
