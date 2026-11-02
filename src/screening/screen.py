"""
RQ1 snapshot screening (stage 2): logging practice at the pinned HEAD of every
corpus repository (proposal ch. 3, Table 3.2).

Files are read from Git objects at the pinned commit (git ls-tree + object database),
never from the working tree. Test and generated files are skipped (src.screening.corpus).
Detection, verbosity and framework come from src.parsing.method_units unchanged; this
module counts them and audits the detection rules (possible false positives, rejected
logger-like calls, a text cross-check). The audit names, accepts and styles calls exactly
as the units do (method_units.resolved_call_name and statement_style), so it lists only
what the detector misses. It reuses the caller/level whitelist and blacklist of
src.detection.log_detection.
"""

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import git

from src.common.config import load_config
from src.detection.log_detection import (
    CALLER_BLACKLIST, LEVEL_WHITELIST, is_logging_name, split_call_name, classify_logging_style
)
from src.detection.verbosity import LEVELS
from src.features.domain import domain_indicators
from src.features.lexical import subtokens
from src.parsing.method_units import parse_java_source, resolved_call_name, statement_style, console_reply_context
from src.parsing.srcml_parser import (
    SRC, TYPE_TAGS, get_statement_calls, get_call_name, get_call_text, call_has_arguments, get_lines,
    flatten_text
)
from src.screening.corpus import is_test_path, generated_reason

STYLES = ["formal", "informal_print", "game_message", "console_reply", "unresolved_wrapper"]
LEVEL_COLUMNS = LEVELS + ["unknown"]
CONTEXTS = ["method_top", "branch", "loop", "try_body", "catch", "finally", "lambda_anon"]
CONTEXT_LABELS = {
    "method_top": "method top level",
    "branch": "if / else / switch",
    "loop": "loop (for / while / do)",
    "try_body": "try body",
    "catch": "catch",
    "finally": "finally",
    "lambda_anon": "lambda / anonymous or local class",
}
FRAMEWORK_ORDER = ["jul", "slf4j", "log4j", "jcl", "jdk_system", "arc", "gdx", "riiablo", "android", "unknown"]

_CONTEXT_TAGS = {
    SRC + "catch": "catch",
    SRC + "finally": "finally",
    SRC + "try": "try_body",
    SRC + "for": "loop",
    SRC + "while": "loop",
    SRC + "do": "loop",
    SRC + "if": "branch",
    SRC + "else": "branch",
    SRC + "if_stmt": "branch",
    SRC + "switch": "branch",
    SRC + "case": "branch",
    SRC + "default": "branch",
    SRC + "lambda": "lambda_anon",
    SRC + "function": "lambda_anon",
    SRC + "constructor": "lambda_anon",
}
for _t in TYPE_TAGS:
    _CONTEXT_TAGS[_t] = "lambda_anon"

LOGGER_TOKENS = {"log", "logger", "logging", "logs"}
PRINTF_ENTRY_LEVELS = {"tracef", "debugf", "infof", "warnf", "errorf", "fatalf", "traceentry", "tracefentry",
                       "traceexit"}
LEVEL_WORDS = {"trace", "debug", "info", "warn", "warning", "err", "error", "severe", "fatal",
               "verbose", "fine", "finer", "finest", "log", "logp"} | PRINTF_ENTRY_LEVELS
PRINT_LEVELS = {"print", "println", "printf"}
# detection rules beyond the upstream predicate (src/parsing, src/detection); each is counted
# separately so the reports show how many statements depend on it
DETECTION_VERSION, DETECTION_DATE = "v2.2", "2026-10-01"
V21_RULES = ["static_import", "chained_logger", "switch_rule", "printf_entry"]
CHAIN_GETTERS = {"getlogger", "getlog"}
STANDARD_CALLERS = {"system.out", "system.err", "timber"}
# rejected categories that are not candidate missed logging (kept in the audit only as a check)
NOT_LOGGING = {"blacklisted_caller"}

# direct children of <unit> in a well-formed Java file; anything else means srcML lost the class structure
# (module-info.java comes out as a decl_stmt, see is_module_declaration)
TOP_LEVEL_TAGS = {SRC + t for t in ("package", "import", "comment", "class", "enum", "interface",
                                    "annotation_defn", "record", "empty_stmt", "annotation", "module")}

TEXT_MAX = 160

# optional Java 14 rule head before the call: `case X -> `, `default -> {`
_TEXT_RULE = r'^\s*((?:case\s[^;{}]*?|default)\s*->\s*\{?\s*)?'
# line starting with qualifier.method( ; the same caller/level predicate as is_logging_name
_TEXT_CALL = re.compile(_TEXT_RULE + r'((?:[A-Za-z_$][\w$]*\s*\.\s*)*[A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)'
                        r'\s*\((\s*\))?')
# line starting with an unqualified call with arguments, e.g. info("..") under import static arc.util.Log.*
_TEXT_BARE_CALL = re.compile(_TEXT_RULE + r'([A-Za-z_$][\w$]*)\s*\((?!\s*\))')


def short(text, n=TEXT_MAX):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 3] + "..."


def log_context(stmt, unit_element):
    """Innermost enclosing structure of a statement inside its method unit."""
    p = stmt.getparent()
    while p is not None and p is not unit_element:
        ctx = _CONTEXT_TAGS.get(p.tag)
        if ctx:
            return ctx
        p = p.getparent()
    return "method_top"


def v1_reachable(unit_element):
    """Whether the narrower XPath //class[specifier]/block/function reaches this unit."""
    if unit_element.tag != SRC + "function":
        return False
    block = unit_element.getparent()
    if block is None or block.tag != SRC + "block":
        return False
    cls = block.getparent()
    return cls is not None and cls.tag == SRC + "class" and cls.find(SRC + "specifier") is not None


def chained_tail(stmt, call):
    """Name of the last call of a chained statement a.b(..).c(..) the detector did not read through, else None.

    srcML keeps the chain as sibling <call> elements; the detector reads the trailing call only of
    a two-call getLogger(..).level(..) chain (srcml_parser.get_statement_calls), otherwise the first.
    """
    expr = stmt.find(SRC + "expr") if stmt.tag == SRC + "expr_stmt" else stmt
    if expr is None:
        return None
    calls = [c for c in expr if c.tag == SRC + "call"]
    if len(calls) < 2 or calls[-1] is call:
        return None
    dot = calls[-1].getprevious()
    if dot is None or dot.tag != SRC + "operator" or (dot.text or "").strip() != ".":
        return None
    return get_call_name(calls[-1])


def in_switch_rule(stmt):
    """Whether a statement is the body of a Java 14 rule `case X -> ..` (a direct statement of its block)."""
    p = stmt.getparent()
    if p is not None and p.tag == SRC + "block":
        p = p.getparent()
    return p is not None and p.tag == SRC + "expr" and p.getparent() is not None and p.getparent().tag == SRC + "case"


def v21_rules(log):
    """Which of the V21_RULES a detected statement needed ('+'-joined, '' for none)."""
    raw = get_call_name(log.call)
    rules = []
    if "." not in raw and "." in log.call_name and "()." not in log.call_name:
        rules.append("static_import")
    if "()." in log.call_name:
        rules.append("chained_logger")
    if in_switch_rule(log.element):
        rules.append("switch_rule")
    if (log.level_token or "").lower() in PRINTF_ENTRY_LEVELS:
        rules.append("printf_entry")
    return "+".join(rules)


def static_logger_import(imports):
    """First 'import static <...>.Log.*' style import of a class named like a logger, else None."""
    for imp in imports:
        if not imp.startswith("static"):
            continue
        parts = imp[len("static"):].strip().split(".")
        if len(parts) >= 2 and set(subtokens(parts[-2])) & LOGGER_TOKENS:
            return imp[len("static"):].strip()
    return None


def rejected_category(call_name, has_args, tail=None, static_logger=None):
    """Audit category of a statement call the detector rejected, None if not log-like (or accepted).

    `call_name` is the resolved name (method_units.resolved_call_name); a bare level-named call
    still unresolved in a file with a static logger import is `static_import_call`.
    """
    caller, level = split_call_name(call_name)
    if level == "printStackTrace" or (has_args and is_logging_name(call_name)):
        return None
    if tail and "log" in call_name.lower() and LEVEL_WHITELIST.match(tail.split(".")[-1]):
        return "chained_logger_call", f"chain ends in .{tail}(..)"
    if level is None and static_logger and has_args and caller.lower() in LEVEL_WORDS:
        return "static_import_call", f"import static {static_logger}"
    if "log" in caller.lower():
        if CALLER_BLACKLIST.match(caller):
            return "blacklisted_caller", "caller blacklisted"
        if not has_args:
            return "logger_caller_rejected", "no arguments"
        return "logger_caller_rejected", "level token not whitelisted"
    if not has_args:
        return None
    if level is not None and level.lower() in LEVEL_WORDS:
        return "level_method_non_logger_caller", "caller not whitelisted"
    method = level if level is not None else caller
    if method.lower() in LEVEL_WORDS or set(subtokens(method)) & {"log", "logger", "logging"}:
        return "log_named_helper", "caller not whitelisted"
    return None


def suspect_category(call_name, caller, level, style):
    """Audit category of an accepted call that may not be a diagnostic log, else None."""
    if style in ("game_message", "console_reply") or level == "printStackTrace":
        return None
    low = caller.lower()
    if low in STANDARD_CALLERS or low.startswith("gdx.app"):
        return None
    if "." not in call_name:
        return "bare_call"
    if caller.endswith("()"):
        # chained x.getLogger(..).level(..): the head call yields the logger
        caller = caller[:-2]
        if caller.split(".")[-1].lower() in CHAIN_GETTERS:
            return None
    if level is not None and level.lower() in PRINT_LEVELS:
        return "print_on_non_system"
    toks = set(subtokens(caller.split(".")[-1]))
    if not toks & LOGGER_TOKENS:
        return "substring_match"
    if toks - LOGGER_TOKENS:
        return "compound_name"
    if style == "unresolved_wrapper":
        return "unresolved_wrapper"
    return None


def text_log_lines(text, static_names=None, static_logger=None):
    """{line: {"text", "style", "call_name", "rule"}} of lines starting with a call the detector accepts.

    Same predicate and naming as the units (method_units.statement_style: x.printStackTrace(..) is an
    informal print with or without arguments); a bare call (info(..)) is resolved through the file's
    static logger imports (`static_names`, ParsedFile.static_log_names). With a static logger import
    (`static_logger`), a bare level-named call it does not resolve is returned with style
    "static_import_call" (same rule as rejected_category). `rule` is set when the call follows a
    Java 14 rule head (`case X ->`, `default ->`) on the same line.
    Lines are split on "\\n" only, as srcML numbers them (str.splitlines also breaks on \\f, \\v, ...).
    """
    static_names = static_names or {}
    hits = {}
    for i, line in enumerate(text.split("\n"), start=1):
        m = _TEXT_CALL.match(line)
        if not m:
            b = _TEXT_BARE_CALL.match(line)
            if b is None:
                continue
            name = b.group(2)
            if name in static_names:
                owner = static_names[name]
                hits[i] = {"text": short(line), "style": classify_logging_style(owner, name),
                           "call_name": owner + "." + name, "rule": bool(b.group(1))}
            elif static_logger and name.lower() in LEVEL_WORDS:
                hits[i] = {"text": short(line), "style": "static_import_call", "call_name": name,
                           "rule": bool(b.group(1))}
            continue
        caller = re.sub(r'\s+', '', m.group(2))
        name = caller + "." + m.group(3)
        if m.group(3) == "printStackTrace":
            style = "informal_print"
        elif m.group(4) or not is_logging_name(name):
            continue
        else:
            style = classify_logging_style(caller, m.group(3))
        hits[i] = {"text": short(line), "style": style, "call_name": name, "rule": bool(m.group(1))}
    return hits


def text_only_cause(root, unit_spans, line, rule=False):
    """Why srcML exposes no statement at a text cross-check line.

    'outside_units': the line is in no method unit (srcML lost the class structure);
    'switch_rule': in a Java 14 switch rule the switch_rule detection reads no statement from: a `default -> ..`
    that srcML emits as a separate expression statement (after a rule block holding a `return`, or as the
    only rule), or a statement nested in (or right after) an if/for/try inside a `case X -> {..}` block;
    'unexposed': inside a unit, but srcML did not produce a statement for it.
    """
    if not any(s <= line <= e for s, e in unit_spans):
        return "outside_units"
    if rule:
        return "switch_rule"
    for el in root.iter():
        if isinstance(el.tag, str) and get_lines(el)[0] == line:
            if any(True for _ in el.iterancestors(SRC + "case")):
                return "switch_rule"
            break
    return "unexposed"


def is_module_declaration(el):
    """srcML 1.1 has no <module> for Java: `[open] module a.b {..}` is a top-level decl_stmt or decl."""
    decl = el.find(SRC + "decl") if el.tag == SRC + "decl_stmt" else el
    if decl is None or decl.tag != SRC + "decl":
        return False
    typ = decl.find(SRC + "type")
    if typ is None:
        return False
    return [n.text for n in typ.findall(SRC + "name")] in (["module"], ["open", "module"])


def misparsed_top_tags(root):
    """Tags of the direct children of <unit> that a well-formed Java file does not have."""
    tags = set()
    for c in root:
        if not isinstance(c.tag, str) or c.tag in TOP_LEVEL_TAGS or is_module_declaration(c):
            continue
        tags.add(c.tag.split("}")[-1])
    return sorted(tags)


def commented_lines(root):
    lines = set()
    for c in root.iter(SRC + "comment"):
        s, e = get_lines(c)
        if s is not None and e is not None:
            lines.update(range(s + 1, e + 1))
    return lines


def _inside_unit(el):
    for _ in el.iterancestors(SRC + "function", SRC + "constructor"):
        return True
    return False


def statement_location(stmt):
    """'unit', 'initializer_or_field' (in a type but no method unit) or 'misparse' (in no type)."""
    if _inside_unit(stmt):
        return "unit"
    if any(True for _ in stmt.iterancestors(*TYPE_TAGS)):
        return "initializer_or_field"
    return "misparse"


def screen_source(path, source):
    """Per-file summary (plain types only, so it can come back from a worker process)."""
    try:
        parsed = parse_java_source(source, path)
    except Exception as e:
        return {"path": path, "ok": False, "reason": f"{type(e).__name__}: {short(str(e), 200)}"}
    if parsed is None:
        return {"path": path, "ok": False, "reason": "srcml_failed"}

    units, logs, rejected = [], [], []
    static_names = parsed.static_log_names
    static_logger = static_logger_import(parsed.imports)
    for unit in parsed.units:
        d = domain_indicators(unit.element, unit.name, unit.class_path, path)
        reach = v1_reachable(unit.element)
        units.append({
            "ordinal": unit.ordinal,
            "kind": unit.kind,
            "ctx": d["d_ctx_category"],
            "n_formal": len(unit.formal_logs),
            "n_logs": len(unit.logs),
            "lines": unit.end_line - unit.start_line + 1 if unit.start_line and unit.end_line else 0,
            "v1_reachable": reach,
        })
        for log in unit.logs:
            logs.append({
                "unit": unit.ordinal,
                "class_path": unit.class_path,
                "signature": unit.signature,
                "call_name": log.call_name,
                "caller": log.caller,
                "level_token": log.level_token,
                "style": log.logging_style,
                "framework": log.framework,
                "verbosity": log.verbosity,
                "context": log_context(log.element, unit.element),
                "ctx_category": d["d_ctx_category"],
                "lambda_body": log.element.tag == SRC + "expr" and not in_switch_rule(log.element),
                "rule": v21_rules(log),
                "v1_reachable": reach,
                "line": log.line,
                "text": short(log.call_text),
            })

    # one pass over every statement call of the file, named and accepted exactly as in the units,
    # so calls srcML left outside any unit (misparsed regions, initialisers) are audited too
    outside = []
    detected_lines = {l["line"] for l in logs}
    for stmt, call in get_statement_calls(parsed.root):
        name = resolved_call_name(call, static_names)
        found = statement_style(call, name)
        if found is not None:
            where = statement_location(stmt)
            if where == "unit":
                continue
            line = get_lines(stmt)[0]
            detected_lines.add(line)
            outside.append({"call_name": name, "style": found[0], "where": where,
                            "line": line, "text": short(get_call_text(call))})
            continue
        if not name:
            continue
        cat = rejected_category(name, call_has_arguments(call), chained_tail(stmt, call), static_logger)
        if cat is None:
            continue
        rejected.append({"category": cat[0], "reason": cat[1], "call_name": name,
                         "where": statement_location(stmt), "line": get_lines(stmt)[0],
                         "text": short(flatten_text(stmt))})

    if isinstance(source, bytes):
        text = source.decode("utf-8", errors="replace")
    else:
        text = source
    skip = commented_lines(parsed.root)
    spans = [(u.start_line, u.end_line) for u in parsed.units if u.start_line and u.end_line]
    console = [(u.start_line, u.end_line) for u in parsed.units
               if u.start_line and u.end_line and console_reply_context(u.class_path, u.name)]
    text_only = []
    seen_lines = detected_lines | {r["line"] for r in rejected if r["category"] == "static_import_call"}
    for line, hit in sorted(text_log_lines(text, static_names, static_logger).items()):
        if line in seen_lines or line in skip:
            continue
        cause = text_only_cause(parsed.root, spans, line, hit["rule"])
        if hit["style"] == "static_import_call":
            # a bare level-named call the static imports do not resolve, with no statement: still rejected
            rejected.append({"category": "static_import_call", "reason": f"import static {static_logger}",
                             "call_name": hit["call_name"],
                             "where": "misparse" if cause == "outside_units" else "unit", "line": line,
                             "text": hit["text"]})
            continue
        style = hit["style"]
        if style == "formal" and any(s <= line <= e for s, e in console):
            style = "console_reply"
        text_only.append({"line": line, "call_name": hit["call_name"], "text": hit["text"], "style": style,
                          "cause": cause})

    return {
        "path": path,
        "ok": True,
        "sloc": parsed.sloc,
        "comment_lines": parsed.comment_lines,
        "file_framework": parsed.file_framework,
        "units": units,
        "logs": logs,
        "rejected": rejected,
        "outside": outside,
        "text_only": text_only,
        "n_print_stack_trace": sum(1 for l in logs if l["level_token"] == "printStackTrace"),
        "misparsed_top": misparsed_top_tags(parsed.root),
        "n_units_no_class": sum(1 for u in parsed.units if not u.class_path),
    }


def _screen_task(task):
    path, source = task
    return screen_source(path, source)


def list_java_blobs(repo, head):
    """(path, blob_sha) of every regular .java file in the tree of `head`."""
    out = repo.git.ls_tree("-r", "-z", head)
    files = []
    for entry in out.split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind == "blob" and mode != "120000" and path.endswith(".java"):
            files.append((path, sha))
    return files


def history_stats(repo, head):
    """Commit counts, first/last author date and number of distinct author e-mails.

    E-mails are only counted (and kept in memory as a set for corpus totals), never written.
    """
    out = repo.git.log("--no-merges", "--format=%at%x09%ae", head)
    stamps, emails = [], set()
    for line in out.splitlines():
        if not line.strip():
            continue
        stamp, email = line.split("\t", 1)
        stamps.append(int(stamp))
        emails.add(email.strip().lower())
    n_all = int(repo.git.rev_list("--count", head))

    def day(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    return {
        "n_commits_all": n_all,
        "n_nonmerge_commits": len(stamps),
        "first_commit_date": day(min(stamps)) if stamps else "",
        "last_commit_date": day(max(stamps)) if stamps else "",
        "n_authors": len(emails),
        "_emails": emails,
    }


def screen_repo(name, path, head, pool=None):
    """Screen one repository at `head`. `pool` is an optional multiprocessing pool."""
    repo = git.Repo(str(path))
    try:
        files = list_java_blobs(repo, head)
        tasks, skipped, skipped_tasks = [], [], []
        for p, sha in files:
            data = repo.odb.stream(bytes.fromhex(sha)).read()
            reason = "test" if is_test_path(p) else generated_reason(p, data)
            if reason:
                skipped.append({"path": p, "reason": reason if reason == "test" else "generated:" + reason})
                skipped_tasks.append((p, data))
            else:
                tasks.append((p, data))
        # skipped files are parsed too, only to report how many statements the exclusion removes
        if pool is None:
            results = [_screen_task(t) for t in tasks + skipped_tasks]
        else:
            results = pool.map(_screen_task, tasks + skipped_tasks, chunksize=4)
        results, skipped_results = results[:len(tasks)], results[len(tasks):]
        for s, r in zip(skipped, skipped_results):
            styles = Counter(l["style"] for l in r["logs"]) if r["ok"] else Counter()
            for st in STYLES:
                s["n_" + st] = styles[st]
        blob_of = dict(files)
        for r in results:
            r["blob"] = blob_of[r["path"]]
        history = history_stats(repo, head)
    finally:
        repo.close()
    return {"name": name, "head": head, "n_java_total": len(files), "skipped": skipped,
            "files": results, "history": history}


def _dominant(counter):
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _pct(a, b, nd=2):
    return round(100.0 * a / b, nd) if b else None


def repo_logs(sr, style=None):
    for f in sr["files"]:
        if not f["ok"]:
            continue
        for log in f["logs"]:
            if style is None or log["style"] == style:
                yield f["path"], log


def snapshot_row(meta, sr):
    h = sr["history"]
    ok = [f for f in sr["files"] if f["ok"]]
    n_units = sum(len(f["units"]) for f in ok)
    with_formal = sum(1 for f in ok for u in f["units"] if u["n_formal"] > 0)
    styles = Counter(log["style"] for _, log in repo_logs(sr))
    formal = [log for _, log in repo_logs(sr, "formal")]
    sloc = sum(f["sloc"] for f in ok)
    skipped = Counter(s["reason"].split(":")[0] for s in sr["skipped"])
    return {
        "repo": sr["name"],
        "engine": meta.get("engine", ""),
        "size": meta.get("size", ""),
        "selection": meta.get("selection", ""),
        "modeling": bool(meta.get("modeling", False)),
        "head": sr["head"],
        "n_commits_all": h["n_commits_all"],
        "n_nonmerge_commits": h["n_nonmerge_commits"],
        "first_commit_date": h["first_commit_date"],
        "last_commit_date": h["last_commit_date"],
        "n_authors": h["n_authors"],
        "n_java_files_total": sr["n_java_total"],
        "n_test_files": skipped["test"],
        "n_generated_files": skipped["generated"],
        "n_java_files": len(sr["files"]),
        "n_parse_failures": len(sr["files"]) - len(ok),
        "n_files_misparsed": sum(1 for f in ok if f["misparsed_top"]),
        "n_units_no_class": sum(f["n_units_no_class"] for f in ok),
        "sloc": sloc,
        "comment_lines": sum(f["comment_lines"] for f in ok),
        "n_method_units": n_units,
        "n_formal": styles["formal"],
        "n_informal_print": styles["informal_print"],
        "n_game_message": styles["game_message"],
        "n_console_reply": styles["console_reply"],
        "n_unresolved_wrapper": styles["unresolved_wrapper"],
        "n_formal_unknown_level": sum(1 for l in formal if l["verbosity"] is None),
        "n_logs_outside_units": sum(len(f["outside"]) for f in ok),
        "n_print_stack_trace": sum(f["n_print_stack_trace"] for f in ok),
        "formal_per_kloc": round(1000.0 * styles["formal"] / sloc, 3) if sloc else None,
        "pct_methods_with_formal_log": _pct(with_formal, n_units),
        "dominant_framework": _dominant(Counter(l["framework"] for l in formal)),
    }


def total_row(label, rows, srs):
    """Corpus total over several repositories (distinct authors over the union of e-mails)."""
    out = {k: "" for k in rows[0]}
    out["repo"] = label
    sums = ["n_commits_all", "n_nonmerge_commits", "n_java_files_total", "n_test_files",
            "n_generated_files", "n_java_files", "n_parse_failures", "n_files_misparsed",
            "n_units_no_class", "sloc", "comment_lines",
            "n_method_units", "n_formal", "n_informal_print", "n_game_message", "n_console_reply",
            "n_unresolved_wrapper", "n_formal_unknown_level", "n_logs_outside_units",
            "n_print_stack_trace"]
    for k in sums:
        out[k] = sum(r[k] for r in rows)
    dates = [r["first_commit_date"] for r in rows if r["first_commit_date"]]
    out["first_commit_date"] = min(dates) if dates else ""
    dates = [r["last_commit_date"] for r in rows if r["last_commit_date"]]
    out["last_commit_date"] = max(dates) if dates else ""
    emails = set()
    for sr in srs:
        emails |= sr["history"]["_emails"]
    out["n_authors"] = len(emails)
    out["formal_per_kloc"] = round(1000.0 * out["n_formal"] / out["sloc"], 3) if out["sloc"] else None
    n_units = out["n_method_units"]
    with_formal = sum(1 for sr in srs for f in sr["files"] if f["ok"] for u in f["units"] if u["n_formal"] > 0)
    out["pct_methods_with_formal_log"] = _pct(with_formal, n_units)
    fw = Counter(l["framework"] for sr in srs for _, l in repo_logs(sr, "formal"))
    out["dominant_framework"] = _dominant(fw)
    return out


def level_row(label, srs):
    c = Counter()
    for sr in srs:
        for _, l in repo_logs(sr, "formal"):
            c[l["verbosity"] or "unknown"] += 1
    row = {"repo": label, "n_formal": sum(c.values())}
    for lv in LEVEL_COLUMNS:
        row[lv] = c[lv]
    return row


def framework_row(label, srs, columns):
    c = Counter()
    for sr in srs:
        for _, l in repo_logs(sr, "formal"):
            c[l["framework"]] += 1
    row = {"repo": label, "n_formal": sum(c.values())}
    for fw in columns:
        row[fw] = c[fw]
    return row


def framework_columns(srs):
    seen = Counter(l["framework"] for sr in srs for _, l in repo_logs(sr, "formal"))
    cols = [fw for fw in FRAMEWORK_ORDER if fw in seen]
    cols += sorted(fw for fw in seen if fw not in FRAMEWORK_ORDER)
    return cols


def context_row(label, srs):
    c = Counter()
    for sr in srs:
        for _, l in repo_logs(sr, "formal"):
            c[l["context"]] += 1
    row = {"repo": label, "n_formal": sum(c.values())}
    for ctx in CONTEXTS:
        row[ctx] = c[ctx]
    return row


def perf_rows(label, srs):
    cats = load_config("perf_sensitive")["category_priority"]
    units, with_formal, formal, lines = Counter(), Counter(), Counter(), Counter()
    for sr in srs:
        for f in sr["files"]:
            if not f["ok"]:
                continue
            for u in f["units"]:
                units[u["ctx"]] += 1
                formal[u["ctx"]] += u["n_formal"]
                lines[u["ctx"]] += u["lines"]
                if u["n_formal"] > 0:
                    with_formal[u["ctx"]] += 1
    tot_units = sum(units.values())
    tot_formal = sum(formal.values())
    rows = []
    for cat in cats:
        share_u = units[cat] / tot_units if tot_units else None
        share_f = formal[cat] / tot_formal if tot_formal else None
        enrich = round(share_f / share_u, 3) if share_u and share_f is not None else None
        rows.append({
            "repo": label,
            "d_ctx_category": cat,
            "n_units": units[cat],
            "n_units_with_formal": with_formal[cat],
            "n_formal": formal[cat],
            "pct_units_with_formal": _pct(with_formal[cat], units[cat]),
            "share_units": round(share_u, 4) if share_u is not None else None,
            "share_formal": round(share_f, 4) if share_f is not None else None,
            "enrichment": enrich,
            "mean_unit_lines": round(lines[cat] / units[cat], 1) if units[cat] else None,
            "formal_per_kline": round(1000.0 * formal[cat] / lines[cat], 2) if lines[cat] else None,
        })
    return rows


def caller_rows(sr, top=30):
    counts = Counter()
    style, fw, verb, example = {}, defaultdict(Counter), defaultdict(Counter), {}
    for path, l in repo_logs(sr):
        name = l["call_name"]
        counts[name] += 1
        style[name] = l["style"]
        fw[name][l["framework"]] += 1
        verb[name][l["verbosity"] or "unknown"] += 1
        example.setdefault(name, f"{path}:{l['line']}")
    total = sum(counts.values())
    rows = []
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    for rank, (name, n) in enumerate(ranked, start=1):
        rows.append({
            "repo": sr["name"],
            "rank": rank,
            "call_name": name,
            "logging_style": style[name],
            "main_framework_of_call": _dominant(fw[name]),
            "main_verbosity_of_call": _dominant(verb[name]),
            "count": n,
            "share": round(n / total, 4) if total else None,
            "example": example[name],
        })
    return rows


def failure_rows(sr):
    rows = []
    for f in sr["files"]:
        if not f["ok"]:
            rows.append({"repo": sr["name"], "path": f["path"], "blob": f.get("blob", ""), "reason": f["reason"]})
    return rows


MISPARSE_COLUMNS = ["repo", "path", "blob", "top_level_tags", "n_units", "n_units_no_class", "n_accepted_lost",
                    "n_formal_lost", "n_text_only_lost", "n_rejected_loglike_lost"]


def misparse_rows(sr):
    """Files srcML parsed but whose class structure it lost (members at the top level of the unit).

    The *_lost columns count statements in code srcML placed outside any type: accepted by the
    detector (all styles / formal only; static-import info(..) calls included),
    text cross-check lines in no unit, and rejected log-like calls (residual chained calls, local
    helpers such as warn(..), ...), which the detector would miss anyway.
    """
    rows = []
    for f in sr["files"]:
        if f["ok"] and (f["misparsed_top"] or f["n_units_no_class"]):
            lost = [o for o in f["outside"] if o["where"] == "misparse"]
            rows.append({"repo": sr["name"], "path": f["path"], "blob": f.get("blob", ""),
                         "top_level_tags": " ".join(f["misparsed_top"]), "n_units": len(f["units"]),
                         "n_units_no_class": f["n_units_no_class"],
                         "n_accepted_lost": len(lost),
                         "n_formal_lost": sum(1 for o in lost if o["style"] == "formal"),
                         "n_text_only_lost": sum(1 for t in f["text_only"] if t["cause"] == "outside_units"),
                         "n_rejected_loglike_lost": sum(1 for r in f["rejected"] if r["where"] == "misparse"
                                                        and r["category"] not in NOT_LOGGING)})
    return rows


def log_rows(sr):
    """Every detected statement at the snapshot, for traceability and manual validation."""
    rows = []
    for f in sr["files"]:
        if not f["ok"]:
            continue
        for l in f["logs"]:
            rows.append({
                "repo": sr["name"], "path": f["path"], "line": l["line"], "class_path": l["class_path"],
                "signature": l["signature"], "call_name": l["call_name"], "logging_style": l["style"],
                "framework": l["framework"], "verbosity": l["verbosity"] or "", "context": l["context"],
                "d_ctx_category": l["ctx_category"], "lambda_body": int(l["lambda_body"]),
                "v1_reachable": int(l["v1_reachable"]), "detection_rule": l["rule"], "call_text": l["text"],
            })
    return rows


def _with_rule(logs, rule):
    return sum(1 for l in logs if rule in l["rule"].split("+"))


def difference_row(sr, game):
    """Measured factors behind the gap between our counts and the Game List."""
    formal = [l for _, l in repo_logs(sr, "formal")]
    styles = Counter(l["style"] for _, l in repo_logs(sr))
    ok = [f for f in sr["files"] if f["ok"]]
    level_arg = sum(1 for l in formal if (l["level_token"] or "").lower() in ("log", "logp")
                    and not l["caller"].lower().startswith("gdx.app"))
    tests = [s for s in sr["skipped"] if s["reason"] == "test"]
    gen = [s for s in sr["skipped"] if s["reason"].startswith("generated")]
    outside = [o for f in ok for o in f["outside"]]
    misparse = [o for o in outside if o["where"] == "misparse"]
    rejected = [r for f in ok for r in f["rejected"]]
    text_only = [t for f in ok for t in f["text_only"]]
    return {
        "repo": sr["name"],
        "game_list_loc": game.get("loc"),
        "game_list_formal": game.get("formal"),
        "game_list_informal": game.get("informal"),
        "n_formal": styles["formal"],
        "n_game_message": styles["game_message"],
        "n_console_reply": styles["console_reply"],
        "n_unresolved_wrapper": styles["unresolved_wrapper"],
        "formal_v1_unreachable": sum(1 for l in formal if not l["v1_reachable"]),
        "formal_lambda_body": sum(1 for l in formal if l["lambda_body"]),
        "formal_level_argument": level_arg,
        "formal_static_import": _with_rule(formal, "static_import"),
        "formal_chained_logger": _with_rule(formal, "chained_logger"),
        "formal_switch_rule": _with_rule(formal, "switch_rule"),
        "formal_printf_entry": _with_rule(formal, "printf_entry"),
        "informal_switch_rule": _with_rule([l for _, l in repo_logs(sr, "informal_print")], "switch_rule"),
        "n_informal_print": styles["informal_print"],
        "n_print_stack_trace": sum(f["n_print_stack_trace"] for f in ok),
        "n_test_files": len(tests),
        "n_generated_files": len(gen),
        "formal_in_test_files": sum(s.get("n_formal", 0) for s in tests),
        "informal_in_test_files": sum(s.get("n_informal_print", 0) for s in tests),
        "formal_in_generated_files": sum(s.get("n_formal", 0) for s in gen),
        "n_logs_outside_units": len(outside),
        "outside_initializer": sum(1 for o in outside if o["where"] == "initializer_or_field"),
        "formal_outside_misparse": sum(1 for o in misparse if o["style"] == "formal"),
        "informal_outside_misparse": sum(1 for o in misparse if o["style"] == "informal_print"),
        "other_outside_misparse": sum(1 for o in misparse if o["style"] not in ("formal", "informal_print")),
        "chained_logger_calls": sum(1 for r in rejected if r["category"] == "chained_logger_call"),
        "static_import_calls": sum(1 for r in rejected if r["category"] == "static_import_call"),
        "static_import_outside_units": sum(1 for r in rejected if r["category"] == "static_import_call"
                                           and r["where"] != "unit"),
        "text_only_formal": sum(1 for t in text_only if t["style"] == "formal"),
        "text_only_informal": sum(1 for t in text_only if t["style"] == "informal_print"),
        "text_only_other": sum(1 for t in text_only if t["style"] not in ("formal", "informal_print")),
        "text_only_switch_rule": sum(1 for t in text_only if t["cause"] == "switch_rule"),
        "text_only_outside_units": sum(1 for t in text_only if t["cause"] == "outside_units"),
        "text_only_unexposed": sum(1 for t in text_only if t["cause"] == "unexposed"),
    }


def audit(sr, top=10):
    """Detection audit of one repository: suspicious accepted calls and rejected log-like calls."""
    suspects = defaultdict(lambda: {"count": 0, "example": None, "style": None})
    for path, l in repo_logs(sr):
        cat = suspect_category(l["call_name"], l["caller"], l["level_token"], l["style"])
        if cat is None:
            continue
        s = suspects[(cat, l["call_name"])]
        s["count"] += 1
        s["style"] = l["style"]
        if s["example"] is None:
            s["example"] = f"{path}:{l['line']} `{l['text']}`"

    missed = defaultdict(lambda: {"count": 0, "outside_units": 0, "example": None, "reason": None})
    text_only, outside = [], []
    for f in sr["files"]:
        if not f["ok"]:
            continue
        for r in f["rejected"]:
            m = missed[(r["category"], r["call_name"])]
            m["count"] += 1
            m["outside_units"] += r["where"] != "unit"
            m["reason"] = r["reason"]
            if m["example"] is None:
                m["example"] = f"{f['path']}:{r['line']} `{r['text']}`"
        for t in f["text_only"]:
            text_only.append((t["style"], t["cause"], f"{f['path']}:{t['line']} `{t['text']}`"))
        for o in f["outside"]:
            outside.append((o["style"] + "/" + o["where"], f"{f['path']}:{o['line']} `{o['text']}`"))

    def ranked(d):
        by_cat = defaultdict(list)
        for (cat, name), v in d.items():
            by_cat[cat].append(dict(v, call_name=name))
        out = {}
        for cat, items in by_cat.items():
            items.sort(key=lambda v: (-v["count"], v["call_name"]))
            out[cat] = {"n_calls": sum(v["count"] for v in items), "n_names": len(items), "top": items[:top],
                        "n_outside_units": sum(v.get("outside_units", 0) for v in items)}
        return out

    detected = [l for _, l in repo_logs(sr)]
    return {
        "repo": sr["name"],
        "suspects": ranked(suspects),
        "missed": ranked(missed),
        "text_only": text_only,
        "outside": outside,
        "v21": {rule: _with_rule(detected, rule) for rule in V21_RULES},
        "n_logs": len(detected),
        "n_misparsed": sum(1 for f in sr["files"] if f["ok"] and f["misparsed_top"]),
    }


def write_csv(path, rows, columns=None):
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if r.get(k) is None else r.get(k) for k in columns})


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v).replace("|", "\\|")


def md_table(rows, columns, labels=None):
    labels = labels or columns
    numeric = []
    for c in columns:
        v = rows[0].get(c) if rows else None
        numeric.append(isinstance(v, (int, float)) and not isinstance(v, bool))
    lines = ["| " + " | ".join(labels) + " |",
             "|" + "|".join("---:" if n else "---" for n in numeric) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(fmt(r.get(c)) for c in columns) + " |")
    return "\n".join(lines)


def with_pct(rows, columns, total_key):
    """Copy of rows where each count column reads 'n (p%)' of row[total_key]."""
    out = []
    for r in rows:
        nr = dict(r)
        for c in columns:
            nr[c] = f"{r[c]} ({100.0 * r[c] / r[total_key]:.1f}%)" if r[total_key] else "0"
        out.append(nr)
    return out


def _code(text):
    return (text or "").replace("`", "'")


def _groups(srs, label="ALL"):
    """Total rows: `label` over every screened repository, plus its modelling-corpus subset."""
    groups = [(label, srs)]
    modeling = [sr for sr in srs if sr["meta"].get("modeling")]
    if modeling and len(modeling) < len(srs):
        groups.append(("MODELING" if label == "ALL" else label + "_MODELING", modeling))
    return groups


SNAPSHOT_COLUMNS = [
    "repo", "engine", "size", "selection", "modeling", "head", "n_commits_all", "n_nonmerge_commits",
    "first_commit_date", "last_commit_date", "n_authors", "n_java_files_total", "n_test_files",
    "n_generated_files", "n_java_files", "n_parse_failures", "n_files_misparsed", "n_units_no_class",
    "sloc", "comment_lines", "n_method_units", "n_formal", "n_informal_print", "n_game_message", "n_console_reply", "n_unresolved_wrapper",
    "n_formal_unknown_level",
    "n_logs_outside_units", "n_print_stack_trace", "formal_per_kloc", "pct_methods_with_formal_log",
    "dominant_framework",
]


def explain_differences(diffs):
    tot = Counter()
    for d in diffs:
        for k, v in d.items():
            if isinstance(v, int) and not isinstance(v, bool):
                tot[k] += v
    gm = ", ".join(f"{d['repo']} {d['n_game_message']}" for d in diffs if d["n_game_message"]) or "none"
    cr = ", ".join(f"{d['repo']} {d['n_console_reply']}" for d in diffs if d["n_console_reply"]) or "none"
    n_misparse = tot["formal_outside_misparse"] + tot["informal_outside_misparse"] + tot["other_outside_misparse"]
    other_text = f" and {tot['text_only_other']} other" if tot["text_only_other"] else ""
    lines = [
        "Measured factors (corpus totals over the screened repositories):",
        "",
        f"1. **Player- and operator-facing output.** `GLog.*` calls ({gm}) post localised text to the in-game "
        "message log; they are now `game_message`, not formal logs. "
        "A count that treats them as logging is higher by up to that amount. "
        f"Likewise, **operator console replies** ({cr}): logger calls in the units listed in "
        "`configs/extraction.yaml` `console_reply_contexts` (Mindustry `ServerControl.registerCommands` / "
        "`readCommands`, e.g. `info(\"Banned.\")`) answer commands typed in the server console. They are "
        "interactive operator output, not records of execution state (proposal §1.1, §4.2), so since detection "
        f"{DETECTION_VERSION} ({DETECTION_DATE}) they are `console_reply` (column `n_console_reply`) and excluded "
        "from the core like `game_message`.",
        f"2. **Method-unit scope.** Constructors and methods of package-private classes, enums and "
        f"interfaces are now analysed: {tot['formal_v1_unreachable']} of {tot['n_formal']} formal statements "
        "are in units that the v1 XPath `//class[specifier]/block/function` did not visit "
        "(column `formal_v1_unreachable`).",
        f"3. **Lambda expression bodies** (`x -> log.info(..)`) count as statements: "
        f"{tot['formal_lambda_body']} formal statements (column `formal_lambda_body`).",
        f"4. **`log(Level.X, ..)` / `logp(..)`.** The level is read from the first argument "
        f"({tot['formal_level_argument']} statements, column `formal_level_argument`). This changes the "
        "level distribution (no blanket INFO), not the number of statements.",
        f"5. **Exclusions.** {tot['n_test_files']} test files and {tot['n_generated_files']} generated files "
        "are skipped, and every file is read from the pinned HEAD (Git objects), not from a working copy. "
        f"The skipped test files hold {tot['formal_in_test_files']} formal and {tot['informal_in_test_files']} "
        f"informal statements, the generated files {tot['formal_in_generated_files']} formal statements "
        "(columns `formal_in_test_files`, `informal_in_test_files`).",
        f"6. **Outside method units.** {tot['n_logs_outside_units']} accepted logging statements belong to no "
        f"method unit and are not counted (column `n_logs_outside_units`): {tot['outside_initializer']} in "
        f"initialiser blocks or field-level lambdas, and {n_misparse} in code that srcML placed outside any type "
        f"after a structural misparse ({tot['formal_outside_misparse']} formal, "
        f"{tot['informal_outside_misparse']} informal, {tot['other_outside_misparse']} other; columns "
        "`formal_outside_misparse`, `informal_outside_misparse`).",
        f"7. **Detection v2.1 ({DETECTION_DATE}).** Four kinds of statement that the earlier "
        "rules missed are now detected and counted: bare calls through a static logger import "
        "(`import static arc.util.Log.*; info(..)`, named `Log.info`): "
        f"{tot['formal_static_import']} formal statements (column `formal_static_import`); chained "
        "`Logger.getLogger(..).log(Level.X, ..)` calls (read through to the trailing call, named "
        f"`Logger.getLogger().log`): {tot['formal_chained_logger']} (column `formal_chained_logger`); the bodies "
        "of Java 14 arrow-switch rules (`case X -> log.info(..)` and the direct statements of "
        f"`case X -> {{..}}`): {tot['formal_switch_rule']} formal and {tot['informal_switch_rule']} informal "
        "(columns `formal_switch_rule`, `informal_switch_rule`); and the printf/entry level methods "
        f"(`tracef`, `debugf`, ..., `traceEntry`, `traceExit`): {tot['formal_printf_entry']} (column "
        "`formal_printf_entry`). A statement can need more than one of these rules.",
        "8. **Residual detection gaps** (see detection_audit.md). Chained calls the v2.1 rule does not read "
        "through (head other than `getLogger`/`getLog`/`logger`/`log`, e.g. `Logger.getGlobal().info(..)`, or "
        f"chains of more than two calls): {tot['chained_logger_calls']} (column `chained_logger_calls`). Bare "
        "level-named calls in a file with a static logger import that the import does not cover: "
        f"{tot['static_import_calls']} (column `static_import_calls`), {tot['static_import_outside_units']} of "
        "them outside method units (column `static_import_outside_units`). Source lines that the detector's "
        "predicate (with the same static-import resolution) accepts but where srcML exposes no statement (text "
        f"cross-check): {tot['text_only_formal']} formal and {tot['text_only_informal']} informal"
        f"{other_text} (columns `text_only_formal`, `text_only_informal`); by cause, "
        f"{tot['text_only_switch_rule']} in switch rules the v2.1 rule reads no statement from (a "
        "`default -> ..` rule that srcML emits as a separate expression statement, e.g. after a rule block "
        "holding a `return`, or a statement nested in an if/for/try inside a `case X -> {..}` block), "
        f"{tot['text_only_outside_units']} in misparsed code outside method units and "
        f"{tot['text_only_unexposed']} elsewhere inside units. None of these are counted.",
        f"9. **Informal output.** `informal_print` ({tot['n_informal_print']}) = `System.out/err` print calls "
        f"with arguments plus, since detection {DETECTION_VERSION} ({DETECTION_DATE}), `x.printStackTrace(..)` "
        f"with or without arguments (a stack trace on stderr, verbosity ERROR): {tot['n_print_stack_trace']} of "
        "them (column `n_print_stack_trace`), as the Game List column \"Informal (sysout/trace)\" also "
        "counted them. The upstream rule rejected `printStackTrace` (Throwable method, caller not whitelisted).",
        "10. **Size.** SLOC counts non-blank, non-comment lines of the analysed (non-test, non-generated) "
        "files; the definition of the Game List \"Java LOC\" is not recorded.",
        "",
        "The procedure behind the Game List counts is not recorded in the repository, so these are "
        "rule-level explanations of the gap, not a file-by-file reconciliation.",
    ]
    return "\n".join(lines)


def write_outputs(srs, out_dir, game_list=None, run_info=None, total_label="ALL"):
    """Write every RQ1 table (CSV + Markdown) for the screened repositories `srs`.

    Each element of `srs` is a screen_repo() result with an extra "meta" entry
    (its configs/corpus.yaml record). `total_label` names the total row ("SUBSET" when
    only part of the corpus was screened).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = _groups(srs, total_label)
    stamp = (run_info or {}).get("finished", "")
    note = ("Pinned HEADs from `configs/corpus.yaml`; files read from Git objects at that commit; test and "
            "generated files excluded; method units and detection from `src/parsing/method_units.py` "
            f"(detection {DETECTION_VERSION}, {DETECTION_DATE}). Generated by `scripts/screen_corpus.py` {stamp}.")

    rows = [snapshot_row(sr["meta"], sr) for sr in srs]
    totals = []
    for label, members in groups:
        names = {sr["name"] for sr in members}
        totals.append(total_row(label, [r for r in rows if r["repo"] in names], members))
    write_csv(out_dir / "corpus_snapshot.csv", rows + totals, SNAPSHOT_COLUMNS)

    game_list = game_list or {}
    sloc_of = {r["repo"]: r["sloc"] for r in rows}
    diffs = []
    for sr in srs:
        d = difference_row(sr, game_list.get(sr["name"], {}))
        d["sloc"] = sloc_of[sr["name"]]
        diffs.append(d)
    write_csv(out_dir / "game_list_comparison.csv", diffs)
    profile_cols = ["repo", "engine", "size", "selection", "modeling", "n_nonmerge_commits", "first_commit_date",
                    "last_commit_date", "n_authors", "n_java_files", "n_test_files", "n_generated_files",
                    "n_parse_failures", "n_files_misparsed", "sloc", "comment_lines", "n_method_units"]
    logging_cols = ["repo", "n_formal", "n_informal_print", "n_game_message", "n_console_reply",
                    "n_unresolved_wrapper",
                    "formal_per_kloc", "pct_methods_with_formal_log", "dominant_framework",
                    "n_formal_unknown_level", "n_logs_outside_units", "n_print_stack_trace"]
    diff_cols = ["repo", "game_list_loc", "sloc", "game_list_formal", "n_formal", "n_game_message", "n_console_reply",
                 "formal_in_test_files", "formal_v1_unreachable", "formal_lambda_body", "formal_level_argument",
                 "formal_static_import", "formal_chained_logger", "formal_switch_rule", "formal_printf_entry",
                 "chained_logger_calls", "static_import_calls", "formal_outside_misparse", "text_only_formal",
                 "game_list_informal", "n_informal_print", "informal_in_test_files", "informal_outside_misparse",
                 "text_only_informal", "n_print_stack_trace"]
    total_note = ", ".join(f"`{label}` = {'every screened repository' if m is srs else 'its modelling-corpus members'}"
                           for label, m in groups)
    md = ["# RQ1 corpus snapshot", "", note, "",
          f"Totals: {total_note}. "
          "`n_authors` counts distinct author e-mails (the e-mails are never written); dates are author dates "
          "(UTC) of the non-merge commits reachable from HEAD.", "",
          "## Repository profile", "", md_table(rows + totals, profile_cols), "",
          "## Logging profile", "",
          "`formal_per_kloc` = formal statements per 1,000 SLOC; `pct_methods_with_formal_log` = share of "
          "method units with at least one formal statement; `n_logs_outside_units` = accepted logging statements "
          "in no method unit (initialiser blocks, field-level lambdas, or statements srcML placed outside any "
          "method, see parse_failures.md); they are not counted in the other columns. `n_informal_print` "
          "includes the `printStackTrace(..)` statements (`n_print_stack_trace`); `n_game_message` (SPD `GLog`) "
          "and `n_console_reply` (operator console replies) are player/operator-facing output, outside the core "
          "(see the comparison notes below).", "",
          md_table(rows + totals, logging_cols), "",
          "## Comparison with the Game List counts", "",
          "`game_list_*` columns are the author's earlier counts used for proposal Table 3.2 "
          "(game_list_formal = \"Formal Log Stmts\", game_list_informal = \"Informal (sysout/trace)\"). "
          "All columns are explained below; game_list_comparison.csv also splits the text cross-check lines "
          "by cause (`text_only_switch_rule`, `text_only_outside_units`, `text_only_unexposed`).", "",
          md_table(diffs, diff_cols), "",
          "### Why the counts differ", "", explain_differences(diffs), ""]
    (out_dir / "corpus_snapshot.md").write_text("\n".join(md), encoding="utf-8")

    level = [level_row(sr["name"], [sr]) for sr in srs] + [level_row(label, m) for label, m in groups]
    write_csv(out_dir / "level_distribution.csv", level, ["repo", "n_formal"] + LEVEL_COLUMNS)
    md = ["# Level distribution of formal statements", "", note, "",
          "Normalised scale TRACE < DEBUG < INFO < WARN < ERROR; `unknown` = level passed "
          "through a variable, or a call without level semantics.", "",
          md_table(with_pct(level, LEVEL_COLUMNS, "n_formal"), ["repo", "n_formal"] + LEVEL_COLUMNS), ""]
    (out_dir / "level_distribution.md").write_text("\n".join(md), encoding="utf-8")

    fw_cols = framework_columns(srs)
    fws = [framework_row(sr["name"], [sr], fw_cols) for sr in srs] + [framework_row(l, m, fw_cols) for l, m in groups]
    write_csv(out_dir / "framework_distribution.csv", fws, ["repo", "n_formal"] + fw_cols)
    md = ["# Framework distribution of formal statements", "", note, "",
          "Framework inferred from the file imports (`src/detection/log_detection.py`); `gdx` = `Gdx.app.*`; "
          "`unknown` = no logging import recognised in the file.", "",
          md_table(with_pct(fws, fw_cols, "n_formal"), ["repo", "n_formal"] + fw_cols), ""]
    (out_dir / "framework_distribution.md").write_text("\n".join(md), encoding="utf-8")

    ctx = [context_row(sr["name"], [sr]) for sr in srs] + [context_row(l, m) for l, m in groups]
    write_csv(out_dir / "log_context_distribution.csv", ctx, ["repo", "n_formal"] + CONTEXTS)
    md = ["# Logging context of formal statements", "", note, "",
          "Innermost enclosing structure of the statement inside its method unit:", ""]
    md += [f"- `{c}`: {CONTEXT_LABELS[c]}" for c in CONTEXTS]
    md += ["", "`synchronized`, labelled and bare blocks are transparent. Methods of anonymous and local classes "
           "belong to the enclosing unit, so a statement directly inside them is `lambda_anon`.", "",
           md_table(with_pct(ctx, CONTEXTS, "n_formal"), ["repo", "n_formal"] + CONTEXTS), ""]
    (out_dir / "log_context_distribution.md").write_text("\n".join(md), encoding="utf-8")

    perf = []
    for sr in srs:
        perf += perf_rows(sr["name"], [sr])
    for label, m in groups:
        perf += perf_rows(label, m)
    write_csv(out_dir / "perf_context_distribution.csv", perf)
    md = ["# Formal logging by performance-sensitive context", "", note, "",
          "`d_ctx_category` from `src/features/domain.py` (configs/perf_sensitive.yaml; priority "
          "frame_update > loop > subsystem > general) on every method unit. `enrichment` = share of formal "
          "statements in the category / share of units in the category (> 1: logging over-represented). "
          "It is not size-adjusted: `mean_unit_lines` is the mean physical length of the units and "
          "`formal_per_kline` the number of formal statements per 1,000 unit lines.", "",
          md_table(perf, list(perf[0].keys()) if perf else []), ""]
    (out_dir / "perf_context_distribution.md").write_text("\n".join(md), encoding="utf-8")

    callers = []
    for sr in srs:
        callers += caller_rows(sr)
    caller_cols = ["repo", "rank", "call_name", "logging_style", "main_framework_of_call", "main_verbosity_of_call",
                   "count", "share", "example"]
    write_csv(out_dir / "caller_audit.csv", callers, caller_cols)
    md = ["# Most frequent logging call names (top 30 per repository)", "", note, "",
          "All detected statements (every style); `share` = share of the repository's detected statements; "
          "`main_verbosity_of_call` and `main_framework_of_call` = most frequent value for that call name (not a "
          "per-statement distribution: use level_distribution.csv and framework_distribution.csv for that).", ""]
    for sr in srs:
        mine = [c for c in callers if c["repo"] == sr["name"]]
        md += [f"## {sr['name']}", "", md_table(mine, caller_cols[1:]) if mine else "No logging statements.", ""]
    (out_dir / "caller_audit.md").write_text("\n".join(md), encoding="utf-8")

    failures = []
    for sr in srs:
        failures += failure_rows(sr)
    write_csv(out_dir / "parse_failures.csv", failures, ["repo", "path", "blob", "reason"])
    misparsed = []
    for sr in srs:
        misparsed += misparse_rows(sr)
    write_csv(out_dir / "structural_misparse.csv", misparsed, MISPARSE_COLUMNS)
    summary = [{"repo": r["repo"], "n_java_files": r["n_java_files"], "n_parse_failures": r["n_parse_failures"],
                "pct_failed": _pct(r["n_parse_failures"], r["n_java_files"]),
                "n_files_misparsed": r["n_files_misparsed"],
                "pct_misparsed": _pct(r["n_files_misparsed"], r["n_java_files"]),
                "n_units_no_class": r["n_units_no_class"]} for r in rows]
    md = ["# Parse failures", "", note, "",
          "`n_parse_failures`: srcML returned no tree. `n_files_misparsed`: srcML returned a tree but placed "
          "statements or members directly under `<unit>` (class structure lost after some construct it does not "
          "handle); method units are still found, but units outside any class get an empty `class_path` "
          "(`n_units_no_class`) and statements outside any unit are not counted. A `module-info.java` "
          "declaration, which srcML 1.1 emits as a top-level `decl_stmt`, is not a misparse.", "",
          md_table(summary, list(summary[0].keys()) if summary else []), "", "## Failed files", "",
          md_table(failures, ["repo", "path", "reason"]) if failures else "No parse failures.", "",
          "## Structurally misparsed files", "",
          "Statements in code srcML placed outside any type, so in no method unit: `n_accepted_lost` = accepted "
          "by the detector (any style; `n_formal_lost` of them formal); `n_text_only_lost` = text cross-check "
          "lines with no statement element; `n_rejected_loglike_lost` = log-like calls the detector rejects "
          "anyway (residual chained calls, local helpers such as `warn(..)`, ..., see detection_audit.md). Since "
          f"detection v2.1 ({DETECTION_DATE}) a static-import `info(..)` in such code is an "
          "accepted call (`n_accepted_lost`).", "",
          md_table(misparsed, MISPARSE_COLUMNS[:2] + MISPARSE_COLUMNS[3:]) if misparsed else "None.", ""]
    (out_dir / "parse_failures.md").write_text("\n".join(md), encoding="utf-8")

    skipped = [dict(s, repo=sr["name"]) for sr in srs for s in sr["skipped"]]
    write_csv(out_dir / "skipped_files.csv", skipped, ["repo", "path", "reason"] + ["n_" + st for st in STYLES])

    logs = []
    for sr in srs:
        logs += log_rows(sr)
    write_csv(out_dir / "snapshot_logs.csv", logs, LOG_COLUMNS)

    write_detection_audit(out_dir / "detection_audit.md", [audit(sr) for sr in srs], note)

    if run_info is not None:
        with open(out_dir / "run_info.json", "w", encoding="utf-8") as f:
            json.dump(run_info, f, indent=2)


LOG_COLUMNS = ["repo", "path", "line", "class_path", "signature", "call_name", "logging_style", "framework",
               "verbosity", "context", "d_ctx_category", "lambda_body", "v1_reachable", "detection_rule", "call_text"]

SUSPECT_HELP = {
    "substring_match": "accepted because the caller contains 'log' inside another word (no log/logger token)",
    "compound_name": "caller is a compound name with a log token (gameLog, LogUtil, logWindow, ...): "
                     "may be a UI/game log or a project wrapper",
    "print_on_non_system": "print/println/printf on a caller other than System.out/err (a writer or stream?)",
    "bare_call": "unqualified call such as log(..): a local helper method, level unknown",
    "unresolved_wrapper": "accepted, but neither the caller nor the method name gives level semantics",
}
MISSED_HELP = {
    "chained_logger_call": "chained statement whose first call names a logger and whose last call is a level method "
                           "(.log(..), .info(..)), but which the v2.1 chain rule does not read through: the head is "
                           "not getLogger/getLog/logger/log (Logger.getGlobal(), Gdx.app.getApplicationLogger()) or "
                           "the chain has more than two calls; the detector only reads the first call",
    "logger_caller_rejected": "caller contains 'log' but the call was rejected (method name not in the level "
                              "whitelist, or no arguments)",
    "level_method_non_logger_caller": "level-named method (info, error, log, ...) on a caller without 'log' in its name",
    "log_named_helper": "method whose name has a log token (logError, logDebug, ...) or is a bare level word (debug(..))",
    "blacklisted_caller": "caller rejected by the false-positive blacklist (dialog, catalog, logic, ...); listed "
                          "to confirm the blacklist only removes non-logging APIs",
    "static_import_call": "bare level-named call in a file with a static import of a logger class that does "
                          "not cover it (e.g. only import static x.Log.info, then warn(..)): a local helper or a "
                          "missed formal log; covered names (info(..) under import static arc.util.Log.*) are accepted",
}


def write_detection_audit(path, audits, note):
    md = ["# Detection audit (RQ1 snapshot)", "", note, "",
          "This report does **not** change any detection rule; it lists candidates for review.", "",
          f"Since detection v2.1 ({DETECTION_DATE}) the units also accept bare calls through a static "
          "logger import (`import static arc.util.Log.*; info(..)`, named `Log.info`), chained "
          "`Logger.getLogger(..).log(..)` calls (named `Logger.getLogger().log`), the bodies of Java 14 arrow-switch "
          "rules (`case X -> log.info(..)`, direct statements of `case X -> {..}`) and the printf/entry level "
          "methods (tracef, debugf, infof, warnf, errorf, fatalf, traceEntry, tracefEntry, traceExit). The audit "
          "names and accepts every call exactly as the units do, so these are no longer listed as rejected or "
          "text-only; overview columns `acc_<rule>` count the detected statements (any style) that needed each "
          "rule. The rejected categories and the text cross-check below are what is still missed.", "",
          f"Since detection {DETECTION_VERSION} ({DETECTION_DATE}) `x.printStackTrace(..)` is an `informal_print` "
          "statement (so no longer a rejected call), and logger calls in `console_reply_contexts` units "
          "(configs/extraction.yaml) are `console_reply`; neither is listed as a possible false positive.", "",
          "**Accepted calls that may be false positives**", ""]
    md += [f"- `{k}`: {v}" for k, v in SUSPECT_HELP.items()]
    md += ["", "**Rejected statement calls that may be missed logging** (expression statements anywhere in the "
           "file, including code srcML placed outside method units; `outside_units` counts those, and the overview "
           "column `rej_outside_units` sums them over every category except `blacklisted_caller`)", ""]
    md += [f"- `{k}`: {v}" for k, v in MISSED_HELP.items()]
    md += ["", "**Text cross-check**: source lines that start with `caller.method(` accepted by the same "
           "caller/level predicate (bare calls resolved through the static logger imports, a leading "
           "`case X ->` / `default ->` allowed), outside comments, where no detected statement starts. "
           "Each line is tagged with the style the call would get and a cause: `switch_rule` (a switch rule the "
           "v2.1 rule reads no statement from: a `default -> ..` rule that srcML emits as a separate expression "
           "statement instead of part of the `case` expression (e.g. after a rule block holding a `return`, or "
           "when it is the only rule), or a statement nested in, or right after, an if/for/try inside a "
           "`case X -> {..}` block, which srcML keeps as one expression), `outside_units` (misparsed code in no "
           "method unit) or `unexposed` (inside a unit, no statement element).", "",
           "**Outside units**: accepted logging statements in no method unit, so not counted in the snapshot: "
           "`initializer_or_field` (static/instance initialiser, field-level lambda) or `misparse` (srcML lost "
           "the class structure, see parse_failures.md).", ""]

    over = []
    for a in audits:
        row = {"repo": a["repo"], "detected": a["n_logs"]}
        for k in V21_RULES:
            row["acc_" + k] = a["v21"][k]
        for k in SUSPECT_HELP:
            row[k] = a["suspects"].get(k, {}).get("n_calls", 0)
        for k in MISSED_HELP:
            row["rej_" + k] = a["missed"].get(k, {}).get("n_calls", 0)
        row["rej_outside_units"] = sum(v["n_outside_units"] for k, v in a["missed"].items() if k not in NOT_LOGGING)
        row["text_only"] = len(a["text_only"])
        row["outside_units"] = len(a["outside"])
        row["misparsed_files"] = a["n_misparsed"]
        over.append(row)
    md += ["## Overview (number of calls)", "", md_table(over, list(over[0].keys()) if over else []), ""]

    biggest = []
    for a in audits:
        for kind, d in (("suspect", a["suspects"]), ("missed", a["missed"])):
            for cat, v in d.items():
                if cat in NOT_LOGGING:
                    continue
                for item in v["top"]:
                    biggest.append({"repo": a["repo"], "kind": kind, "category": cat, "call_name": item["call_name"],
                                    "count": item["count"], "outside_units": item.get("outside_units", ""),
                                    "example": _code(item["example"])})
    biggest.sort(key=lambda r: (-r["count"], r["repo"], r["call_name"]))
    md += ["## Largest candidates (corpus-wide, top 25)", "",
           md_table(biggest[:25], ["repo", "kind", "category", "call_name", "count", "outside_units", "example"])
           if biggest else "None.", ""]

    for a in audits:
        md += [f"## {a['repo']}", "", f"Detected statements: {a['n_logs']}.", ""]
        rows = []
        for cat in SUSPECT_HELP:
            for item in a["suspects"].get(cat, {}).get("top", []):
                rows.append({"category": cat, "call_name": item["call_name"], "style": item["style"],
                             "count": item["count"], "example": _code(item["example"])})
        md += ["### Possible false positives (accepted)", "",
               md_table(rows, ["category", "call_name", "style", "count", "example"]) if rows else "None.", ""]
        rows = []
        for cat in MISSED_HELP:
            for item in a["missed"].get(cat, {}).get("top", []):
                rows.append({"category": cat, "call_name": item["call_name"], "reason": item["reason"],
                             "count": item["count"], "outside_units": item["outside_units"],
                             "example": _code(item["example"])})
        md += ["### Possible missed logging / wrappers (rejected)", "",
               md_table(rows, ["category", "call_name", "reason", "count", "outside_units", "example"])
               if rows else "None.", ""]
        md += [f"### Text cross-check ({len(a['text_only'])} lines)", ""]
        md += [f"- {style}, {cause}: {_code(t)}" for style, cause, t in a["text_only"][:10]] or ["None."]
        if len(a["text_only"]) > 10:
            md.append(f"- ... {len(a['text_only']) - 10} more")
        by_style = Counter(s for s, _ in a["outside"])
        styles = ", ".join(f"{k} {v}" for k, v in sorted(by_style.items())) or "none"
        md += ["", f"### Outside method units ({len(a['outside'])} statements: {styles})", ""]
        md += [f"- {_code(e)}" for _, e in a["outside"][:5]]
        md.append("")
    Path(path).write_text("\n".join(md), encoding="utf-8")
