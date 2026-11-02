"""
Create data/raw/repos/<repo> for every corpus repository and verify the pinned HEAD.

Clones from the local `source` in configs/corpus.yaml (full history, no network). If
`source` is unset, missing on disk, or is the destination itself (a clone made in place),
clones the `remote` URL instead. Existing clones are left as they are, and mining always
reads from the pinned SHA.

Usage:
    python -m scripts.setup_corpus [--modeling-only]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from src.common.config import ROOT, corpus_repos, repo_path


def git(args, cwd=None):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def same_path(a, b):
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def clone_source(r, dest):
    """(where, is_local): the local `source` copy, or the `remote` URL when `source` is
    missing, absent from disk, or resolves to dest itself. where is None when neither works."""
    if r.get("source"):
        src = (ROOT / r["source"]).resolve()
        if src.exists() and not same_path(src, dest):
            return str(src), True
    return r.get("remote"), False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Clone the corpus repositories into data/raw/repos and "
                                             "verify the pinned heads of configs/corpus.yaml.")
    ap.add_argument("--modeling-only", action="store_true", help="only the 9 modelling repositories")
    args = ap.parse_args(argv)

    ok = True
    for r in corpus_repos(args.modeling_only):
        dest = repo_path(r["name"])
        if not dest.exists():
            src, local = clone_source(r, dest)
            if not src:
                print(f"{r['name']}: no usable source or remote in configs/corpus.yaml")
                ok = False
                continue
            print(f"cloning {r['name']} from {src}")
            res = git(["clone", "--no-hardlinks", src, str(dest)] if local else ["clone", src, str(dest)])
            if res.returncode != 0:
                print(res.stderr)
                ok = False
                continue
        has = git(["cat-file", "-t", r["head"]], cwd=dest)
        shallow = git(["rev-parse", "--is-shallow-repository"], cwd=dest).stdout.strip()
        n = git(["rev-list", "--count", r["head"]], cwd=dest).stdout.strip()
        status = "ok" if has.stdout.strip() == "commit" and shallow == "false" else "PROBLEM"
        if status != "ok":
            ok = False
        print(f"{r['name']:<26} head={r['head'][:10]} commits={n:<6} shallow={shallow} {status}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
