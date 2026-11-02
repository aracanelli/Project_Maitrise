"""
Scan a Java repository for logging statements.

Parses every Java file of a local checkout with srcML and returns one record per
detected logging call, anchored to its method and class (method units from
src/parsing/method_units.py). Detection uses the predicate adapted from the
replication package of Zeng et al. (2019).
"""

import json
from pathlib import Path

from src.parsing.method_units import parse_java_source


def find_java_files(repo_path):
    return sorted(Path(repo_path).rglob("*.java"))


def scan_file(java_path):
    with open(java_path, "rb") as f:
        parsed = parse_java_source(f.read())
    if parsed is None:
        return []

    records = []
    for unit in parsed.units:
        for log in unit.logs:
            records.append({
                "file_path": str(java_path),
                "class_name": unit.class_path.split(".")[-1] if unit.class_path else "",
                "class_path": unit.class_path,
                "method_signature": unit.signature,
                "call_name": log.call_name,
                "call_text": log.call_text,
                "verbosity": log.verbosity,
                "logging_style": log.logging_style,
                "framework": log.framework,
                "line": log.line,
            })
    return records


def scan_repo(repo_path, exclude_tests=True):
    java_files = find_java_files(repo_path)
    all_records = []
    errors = []

    for java_path in java_files:
        rel = str(java_path.relative_to(repo_path))
        if exclude_tests and _looks_like_test(rel):
            continue
        try:
            file_records = scan_file(java_path)
            all_records.extend(file_records)
        except Exception as e:
            errors.append({"file": rel, "error": str(e)})

    return all_records, errors


def _looks_like_test(rel_path):
    parts = rel_path.replace("\\", "/").lower()
    name = parts.split("/")[-1].replace(".java", "")
    if "/test/" in parts or "/tests/" in parts:
        return True
    if name.startswith("test") or name.endswith("test") or name.endswith("tests"):
        return True
    return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.detection.scan <repo_path> [output.json]")
        sys.exit(1)

    repo_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    records, errors = scan_repo(repo_path)
    print(f"Found {len(records)} logging calls")
    if errors:
        print(f"Encountered {len(errors)} parse errors")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"records": records, "errors": errors}, f, indent=2)
        print(f"Written to {output_path}")
    else:
        for r in records[:10]:
            print(f"  {r['class_name']}.{r['method_signature']}: "
                  f"{r['call_name']} -> {r['verbosity']}")
        if len(records) > 10:
            print(f"  ... and {len(records) - 10} more")
