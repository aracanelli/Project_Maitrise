"""
Stage 3: mine the Git history of corpus repositories.

Reads the pinned HEAD from configs/corpus.yaml and writes
data/interim/mining/<repo>/{commits,file_changes,methods_changed,events,aux_changes,
parse_failures}.jsonl and summary.json.

Exits with status 1 when a commit could not be mined (commit_errors > 0 in summary.json;
the failed commits carry mining_error in commits.jsonl), unless --allow-errors is given.

Files are written into <out>.tmp, which replaces <out> only once every file is complete.
An interrupted run keeps the previous output and leaves <out>.tmp behind for the next run
to delete.

--max-commits is for smoke tests. It needs an --out outside data/interim/mining, so a
truncated history never replaces the complete one that the dataset stage reads.

Usage:
    python -m scripts.mine_history --repo NAME [NAME ...] [--workers 16] [--max-commits N] [--out DIR]
"""

import argparse
import sys
from pathlib import Path

from src.common.config import DATA, repo_info, repo_path
from src.mining.run import mine_repo


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mine the Git history of corpus repositories (stage 3).")
    ap.add_argument("--repo", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-commits", type=int, default=None,
                    help="only the first N commits in topo order (smoke tests, needs --out)")
    ap.add_argument("--chunk-size", type=int, default=150)
    ap.add_argument("--out", default=None, help="output directory (default data/interim/mining/<repo>)")
    ap.add_argument("--allow-errors", action="store_true", help="exit 0 even if some commits failed to mine")
    args = ap.parse_args(argv)
    mining_dir = (DATA / "interim" / "mining").resolve()
    if args.max_commits and (not args.out or Path(args.out).resolve().is_relative_to(mining_dir)):
        ap.error("--max-commits is for smoke tests: pass an --out outside data/interim/mining so the "
                 "complete mining output is never replaced by a truncated one")

    failed = []
    for name in args.repo:
        info = repo_info(name)
        out = Path(args.out) if args.out else DATA / "interim" / "mining" / name
        if args.out and len(args.repo) > 1:
            out = out / name
        s = mine_repo(name, repo_path(name), info["head"], out, workers=args.workers,
                      max_commits=args.max_commits, chunk_size=args.chunk_size)
        print(f"{name}: commits={s['n_commits']} non_merge={s['n_non_merge']} bulk={s['n_bulk']} "
              f"java_changes={s['java_file_changes']} mined={s['java_files_mined']} "
              f"parses={s['blob_parses']} parse_failures={s['parse_failures']} "
              f"commit_errors={s['commit_errors']} mismatches={s['file_change_mismatch_commits']}")
        for key, n in s["events_by_label_validity"].items():
            print(f"  {key:<32} {n}")
        print(f"  -> {out}")
        if s["commit_errors"]:
            failed.append(name)
            for err in s["commit_error_examples"]:
                print(f"  commit error {err['commit_id'][:12]}: {err['error']}", file=sys.stderr)
        if s["file_change_mismatch_commits"]:
            print(f"  warning: {s['file_change_mismatch_commits']} commits differ between the numstat log "
                  f"and the mined diffs", file=sys.stderr)

    if failed and not args.allow_errors:
        print(f"commits failed to mine in: {', '.join(failed)} (see commits.jsonl mining_error)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
