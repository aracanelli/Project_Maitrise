"""
Repository-level history tables: commits.jsonl and file_changes.jsonl.

commits.jsonl lists every commit of `rev-list --topo-order --reverse <head>`; the
mining stats (n_java_files, n_java_mined, is_bulk, and mining_error for a commit whose
mining failed) are filled in by src/mining/run.py.
file_changes.jsonl comes from one `git log --no-merges --numstat --summary -M` call,
so the line counts do not need one subprocess per commit.

Author identity is a hash of the lower-cased e-mail; raw e-mails are never written.
"""

import hashlib

from src.mining.git_walker import run_git, is_java, is_test_path, is_generated_path

COMMIT_MARK = "\x01"


def author_id(email):
    return hashlib.sha1((email or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def commit_records(repo_name, commits):
    """commits.jsonl rows (without mining stats) from git_walker.list_commits output."""
    rows = []
    for i, (sha, parents, date, email) in enumerate(commits):
        rows.append({
            "repo": repo_name,
            "commit_id": sha,
            "parent_commit_id": parents[0] if parents else None,
            "topo_index": i,
            "timestamp": date,
            "author_id": author_id(email),
            "is_merge": len(parents) > 1,
            "is_root": len(parents) == 0,
            "n_java_files": None,
            "n_java_mined": None,
            "is_bulk": False,
            "mining_error": None,
        })
    return rows


def _unquote(path):
    # with core.quotepath=off git only quotes paths with ", \ or control characters
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        path = path[1:-1].replace('\\"', '"').replace("\\t", "\t").replace("\\\\", "\\")
    return path


def split_rename(path):
    """Old and new path of a numstat rename entry, None if the entry is not a rename.

    Handles "old => new" and the compressed form "dir/{a => b}/file" (either side of
    the braces may be empty).
    """
    if " => " not in path:
        return None
    if "{" in path and "}" in path:
        before, rest = path.split("{", 1)
        middle, after = rest.split("}", 1)
        a, b = middle.split(" => ", 1)
        old = before + a + after
        new = before + b + after
    else:
        old, new = path.split(" => ", 1)
    old = old.replace("//", "/").lstrip("/")
    new = new.replace("//", "/").lstrip("/")
    return _unquote(old), _unquote(new)


def parse_numstat_log(text):
    """Parse `git log --numstat --summary --format=<mark>%H` output.

    Returns {sha: [(change_type, old_path, new_path, added, deleted), ...]} with the
    entries in git's order. Binary files ("-" counts) get None counts.
    """
    result = {}
    sha = None
    stats, creates, deletes = [], set(), set()

    def flush():
        if sha is None:
            return
        rows = []
        for added, deleted, path in stats:
            ren = split_rename(path)
            if ren is not None:
                rows.append(("R", ren[0], ren[1], added, deleted))
                continue
            path = _unquote(path)
            if path in creates:
                rows.append(("A", None, path, added, deleted))
            elif path in deletes:
                rows.append(("D", path, None, added, deleted))
            else:
                rows.append(("M", path, path, added, deleted))
        result[sha] = rows

    for line in text.splitlines():
        if line.startswith(COMMIT_MARK):
            flush()
            sha = line[1:].strip()
            stats, creates, deletes = [], set(), set()
        elif "\t" in line and not line.startswith(" "):
            added, deleted, path = line.split("\t", 2)
            stats.append((
                int(added) if added.isdigit() else None,
                int(deleted) if deleted.isdigit() else None,
                path,
            ))
        elif line.startswith(" create mode "):
            creates.add(_unquote(line.strip().split(" ", 3)[3]))
        elif line.startswith(" delete mode "):
            deletes.add(_unquote(line.strip().split(" ", 3)[3]))
    flush()
    return result


def file_changes(repo_dir, repo_name, head, topo_index, generated_segments):
    """file_changes.jsonl rows for the Java files of non-merge commits, in topo order.

    topo_index maps commit sha -> position; commits not in it are skipped (--max-commits).
    is_test / is_generated are path-based here (header markers need the blob).
    """
    text = run_git(repo_dir, [
        "-c", "core.quotepath=off", "-c", "log.showSignature=false",
        "log", "--no-merges", "--root", "--no-color", "--numstat", "--summary", "-M",
        f"--format={COMMIT_MARK}%H", head,
    ])
    per_commit = parse_numstat_log(text)

    rows = []
    for sha, entries in per_commit.items():
        if sha not in topo_index:
            continue
        for ct, old_path, new_path, added, deleted in entries:
            if not (is_java(old_path) or is_java(new_path)):
                continue
            path = new_path or old_path
            rows.append({
                "repo": repo_name,
                "commit_id": sha,
                "topo_index": topo_index[sha],
                "change_type": ct,
                "old_path": old_path,
                "new_path": new_path,
                "lines_added": added,
                "lines_deleted": deleted,
                "is_test": is_test_path(path),
                "is_generated": is_generated_path(old_path, generated_segments)
                                or is_generated_path(new_path, generated_segments),
            })
    rows.sort(key=lambda r: r["topo_index"])  # stable: keeps git's order inside a commit
    return rows
