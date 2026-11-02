"""
Stage 4: build the task instances, folds and dataset summary from the mining output.

Reads data/interim/mining/<repo>/ for the modelling repositories (modeling: true in
configs/corpus.yaml) and skips repositories with no mining output. Every run rewrites the
outputs from scratch. The run stops with exit code 1, before writing anything, when a
mining table disagrees with its summary.json (a truncated table from an interrupted run)
or lacks required columns.

Usage:
    python -m scripts.build_datasets [--repos A B ...] [--mining-dir DIR] [--out DIR]
"""

import argparse
import sys
import time

from src.dataset.assemble import build_all, ALL_TASKS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="+", default=None)
    ap.add_argument("--mining-dir", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    try:
        summary = build_all(args.mining_dir, args.out, args.repos)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    if not summary["repos"]:
        sys.exit(1)

    print(f"{'task':<13} {'repo':<26} {'n_pos':>6} {'pool':>8} {'R1':>6} {'R4':>6} {'R10':>6} {'R4 ratio':>9}")
    for task in ALL_TASKS:
        for repo, s in summary["tasks"][task].items():
            n = s["n_neg"]
            print(f"{task:<13} {repo:<26} {s['n_pos']:>6} {s['n_neg_pool']:>8} {n.get('R1', ''):>6} "
                  f"{n.get('R4', ''):>6} {n.get('R10', '-'):>6} {str(s['ratio'].get('R4')):>9}")
    for repo, r in summary["per_repo"].items():
        mism = [k for k, c in r["core_check"].items() if not c["match"]]
        split = r["add_log_split"]
        print(f"{repo:<26} rows={r['methods_changed_rows']} bulk={r['bulk_rows']} "
              f"events={r['events']['total']} problems={r['row_problems'] or '-'} core_mismatch={mism or '-'} "
              f"add_log_pos_other_change={split['positive_with_other_log_change']}/{split['positive']} "
              f"nonformal_add={split['positive_with_nonformal_add']}")
    if summary["missing_repos"]:
        print(f"missing: {', '.join(summary['missing_repos'])}")
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
