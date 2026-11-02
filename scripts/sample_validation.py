"""
Draw a stratified random sample of core events for manual validation of the extraction
(precision of the ADD_LOG, REMOVE_LOG and CHANGE_LEVEL labels, report section 7.6.3).

The sample is seeded and written with empty annotation columns for a human annotator.
Each event shows the pre- and post-state method with the logging statement marked, plus
a link to the commit.

Usage:
    python -m scripts.sample_validation [--per-label 40] [--seed 11] [--per-commit 2] [--data-dir DIR] [--out-dir DIR]

Seed 7 is the sample used to calibrate the statement-continuity threshold, so the
validation sample must use another seed (default 11) to stay independent of it. At most
--per-commit events come from one commit, because events of a commit are correlated.
A sheet that already has annotations is only overwritten with --overwrite.

Outputs:
    data/results/validation/event_sample.csv   (annotation sheet)
    data/results/validation/event_sample.md    (readable code excerpts)
"""

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from src.common.config import DATA, repo_info
from src.dataset.views import read_blob
from src.parsing.method_units import parse_java_source
from src.parsing.srcml_parser import flatten_text

WINDOW = 20   # lines shown on each side of the marked statement
ANNOTATION_COLUMNS = ["label_correct", "is_logging_statement", "level_correct", "notes"]
# allowed values of each annotation column
ANNOTATION_HELP = "`label_correct` (y/n/?), `is_logging_statement` (y/n), `level_correct` (y/n/na), `notes`"


def method_source(repo, blob, class_path, signature, mark_line):
    if not blob:
        return "(no file at this side)"
    parsed = parse_java_source(read_blob(repo, blob))
    if parsed is None:
        return "(parse failure)"
    for u in parsed.units:
        if u.class_path == class_path and u.signature == signature:
            text = flatten_text(u.element).splitlines()
            first = u.start_line or 1
            centre = (mark_line - first) if mark_line else 0
            lo, hi = max(0, centre - WINDOW), min(len(text), centre + WINDOW + 1)
            out = ["      ..."] if lo > 0 else []
            for i in range(lo, hi):
                n = first + i
                out.append(f"{n:5d}{' >>' if n == mark_line else '   '} {text[i]}")
            if hi < len(text):
                out.append("      ...")
            return "\n".join(out)
    return "(method not found)"


def statement_line(e):
    text = (e["call_text"] or "")[:200]
    if e["event_label"] == "ADD_LOG":
        return f"- added statement (post-state): `{text}`"
    if e["event_label"] == "REMOVE_LOG":
        return f"- removed statement (pre-state): `{text}`"
    return f"- statement: `{(e['call_text_before'] or '')[:200]}` -> `{text}`"


def is_annotated(path):
    """True when the sheet at path has any annotation filled in."""
    if not path.exists():
        return False
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if any((row.get(c) or "").strip() for c in ANNOTATION_COLUMNS):
                return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draw the seeded event sample for the manual validation of the extraction.")
    ap.add_argument("--per-label", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11, help="seed 7 was the development sample; do not reuse it")
    ap.add_argument("--per-commit", type=int, default=2, help="at most this many events of one commit")
    ap.add_argument("--data-dir", default=str(DATA), help="reads processed/events_master.jsonl and interim/mining/")
    ap.add_argument("--out-dir", default=None, help="default <data-dir>/results/validation")
    ap.add_argument("--overwrite", action="store_true", help="replace a sheet that already has annotations")
    args = ap.parse_args(argv)
    per_label, seed, per_commit = args.per_label, args.seed, args.per_commit
    data = Path(args.data_dir)
    out_dir = Path(args.out_dir) if args.out_dir else data / "results" / "validation"
    if is_annotated(out_dir / "event_sample.csv") and not args.overwrite:
        ap.error(f"{out_dir / 'event_sample.csv'} already has annotations; move it away or pass --overwrite")

    by_label = defaultdict(list)
    with open(data / "processed" / "events_master.jsonl", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e["validity_status"] == "core":
                by_label[e["event_label"]].append(e)

    rng = random.Random(seed)
    sample = []
    for label in ("ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL"):
        events = sorted(by_label[label], key=lambda e: e["event_id"])
        rng.shuffle(events)
        taken, per = [], {}
        for e in events:
            key = (e["repo"], e["commit_id"])
            if per.get(key, 0) >= per_commit:
                continue
            per[key] = per.get(key, 0) + 1
            taken.append(e)
            if len(taken) == per_label:
                break
        sample.extend(taken)

    out_dir.mkdir(parents=True, exist_ok=True)

    md = ["# Event extraction validation sample", "",
          f"Seed {seed}, up to {per_label} core events per label, at most {per_commit} per commit. Annotate `event_sample.csv`:",
          ANNOTATION_HELP,
          "(annotation rules in report section 7.6.3).", ""]
    # events carry no blob ids; take them from methods_changed rows of the same commit
    mining = data / "interim" / "mining"
    blobs = {}
    wanted = {(e["repo"], e["commit_id"]) for e in sample}
    for repo in {r for r, _ in wanted}:
        with open(mining / repo / "methods_changed.jsonl", encoding="utf-8") as f:
            for line in f:
                m = json.loads(line)
                if (repo, m["commit_id"]) in wanted:
                    sides = (m["pre_blob"], m["post_blob"], m.get("class_path_pre") or m["class_path"],
                             m["signature_pre"], m["class_path"], m["signature_post"])
                    blobs[(repo, m["commit_id"], m["class_path"], m["signature_post"])] = sides
                    blobs[(repo, m["commit_id"], m.get("class_path_pre") or m["class_path"], m["signature_pre"])] = sides

    with open(out_dir / "event_sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "repo", "commit_url", "file_path", "class_path", "method_signature",
                    "event_label", "pre_level", "post_level", "call_text_before", "call_text",
                    ] + ANNOTATION_COLUMNS)
        for e in sample:
            url = repo_info(e["repo"])["remote"].removesuffix(".git") + "/commit/" + e["commit_id"]
            w.writerow([e["event_id"], e["repo"], url, e["file_path"], e["class_path"], e["method_signature"],
                        e["event_label"], e["pre_level"], e["post_level"], e["call_text_before"], e["call_text"],
                        "", "", "", ""])
            key = (e["repo"], e["commit_id"], e["class_path"], e["method_signature"])
            pre_blob, post_blob, cls_pre, sig_pre, cls_post, sig_post = blobs.get(
                key, (None, None, e["class_path"], e["method_signature"], e["class_path"], e["method_signature"]))
            md += [f"## {e['event_id']} — {e['event_label']}", "",
                   f"- repo: {e['repo']}  commit: {url}",
                   f"- method: `{e['class_path']}.{e['method_signature']}` in `{e['file_path']}`",
                   statement_line(e),
                   f"- levels: {e['pre_level']} -> {e['post_level']}", "",
                   "Pre-state:", "```java", method_source(e["repo"], pre_blob, cls_pre, sig_pre, e.get("pre_line")), "```",
                   "Post-state:", "```java", method_source(e["repo"], post_blob, cls_post, sig_post, e.get("post_line")), "```", ""]

    (out_dir / "event_sample.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {len(sample)} events to {out_dir}")


if __name__ == "__main__":
    main()
