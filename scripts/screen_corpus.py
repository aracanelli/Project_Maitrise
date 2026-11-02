"""
Stage 2 (RQ1): screen the pinned snapshot of the corpus repositories.

Reads every Java file at the HEAD pinned in configs/corpus.yaml from Git objects, parses
it with srcML (multiprocessing) and writes the RQ1 tables to data/results/rq1/.

Usage:
    .venv/Scripts/python.exe -m scripts.screen_corpus [--repos a,b] [--workers 16] [--out data/results/rq1]

A --repos subset never writes to data/results/rq1 itself, which holds the full-corpus
tables. It defaults to data/results/rq1/subset_<names>/ and its total row is SUBSET.
"""

import argparse
import hashlib
import multiprocessing as mp
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.common.config import ROOT, CONFIGS, DATA, corpus_repos, repo_path
from src.screening.corpus import read_game_list
from src.screening.screen import screen_repo, write_outputs

GAME_LIST = ROOT / "docs" / "user_docs" / "Game List.xlsx"
DEFAULT_OUT = DATA / "results" / "rq1"


def sha1_file(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def srcml_version():
    try:
        out = subprocess.run(["srcml", "--version"], capture_output=True, text=True).stdout
        return out.splitlines()[0].strip() if out else ""
    except OSError:
        return ""


def output_target(wanted, out_arg, all_names, default=DEFAULT_OUT):
    """(output directory, total-row label) for a run over `wanted` (empty = whole corpus).

    Raises ValueError when a subset would overwrite the full-corpus outputs.
    """
    out = Path(out_arg) if out_arg else default
    if not wanted or set(wanted) == set(all_names):
        return out, "ALL"
    if not out_arg:
        return default / ("subset_" + "+".join(sorted(set(wanted)))), "SUBSET"
    if out.resolve() == Path(default).resolve():
        raise ValueError(f"--repos subset would overwrite the full-corpus outputs in {out}; choose another --out")
    return out, "SUBSET"


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--repos", default="", help="comma-separated subset of configs/corpus.yaml names")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default="", help=f"output directory (default {DEFAULT_OUT.relative_to(ROOT)})")
    args = ap.parse_args()

    repos = corpus_repos()
    names = [r["name"] for r in repos]
    wanted = [n.strip() for n in args.repos.split(",") if n.strip()]
    unknown = set(wanted) - set(names)
    if unknown:
        sys.exit(f"unknown repositories: {sorted(unknown)}")
    try:
        out, total_label = output_target(wanted, args.out, names)
    except ValueError as e:
        sys.exit(str(e))
    if wanted:
        repos = [r for r in repos if r["name"] in wanted]
    missing = [r["name"] for r in repos if not repo_path(r["name"]).exists()]
    if missing:
        sys.exit(f"missing clones (run scripts/setup_corpus.py): {missing}")

    game_list = read_game_list(GAME_LIST) if GAME_LIST.exists() else {}
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t_start = time.time()
    timings = {}
    srs = []
    pool = mp.Pool(args.workers) if args.workers > 1 else None
    try:
        for r in repos:
            t0 = time.time()
            sr = screen_repo(r["name"], repo_path(r["name"]), r["head"], pool)
            sr["meta"] = r
            srs.append(sr)
            timings[r["name"]] = round(time.time() - t0, 1)
            ok = [f for f in sr["files"] if f["ok"]]
            n_formal = sum(1 for f in ok for l in f["logs"] if l["style"] == "formal")
            print(f"{r['name']:<26} files={len(sr['files']):5d} failed={len(sr['files']) - len(ok):3d} "
                  f"skipped={len(sr['skipped']):4d} formal={n_formal:5d} {timings[r['name']]:7.1f}s", flush=True)
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    run_info = {
        "started": started,
        "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "elapsed_seconds": round(time.time() - t_start, 1),
        "seconds_per_repo": timings,
        "workers": args.workers,
        "python": platform.python_version(),
        "srcml": srcml_version(),
        "heads": {r["name"]: r["head"] for r in repos},
        "configs_sha1": {n: sha1_file(CONFIGS / f"{n}.yaml") for n in ("corpus", "extraction", "perf_sensitive")},
        "game_list_sha1": sha1_file(GAME_LIST) if GAME_LIST.exists() else "",
        "sources_sha1": {p: sha1_file(ROOT / p) for p in (
            "src/screening/screen.py", "src/screening/corpus.py", "src/parsing/method_units.py",
            "src/parsing/srcml_parser.py", "src/detection/log_detection.py", "src/detection/verbosity.py",
            "src/features/domain.py", "src/mining/git_walker.py")},
        "total_label": total_label,
    }
    write_outputs(srs, out, game_list, run_info, total_label)
    print(f"wrote {out} in {run_info['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
