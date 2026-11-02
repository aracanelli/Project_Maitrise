"""
Method-level comparison of two versions of a Java file and logging event extraction.

Adapted from the replication package of Zeng et al. (2019), logdetector/detector.py:
compare_all_methods (three-pass method matching), handle_added_or_deleted_file and
save_logs_of_method_xml_str_if_needed (logs of added and deleted files and methods).
compare_logging_method_calls lives in src/matching/statement_matcher.py.

Differences from upstream:
- units come from src/parsing/method_units.py: methods and constructors of every named
  type, including package-private classes, enums and interfaces; logs of anonymous
  classes and lambdas belong to the enclosing unit
- pass 1 = same (class path, signature); pass 2 = same (class path, name) with other
  parameters, paired greedily in document order; pass 3 = identical normalised block
  (statements only, so a renamed method can match; empty blocks never match) among
  the rest. Upstream compared raw XML strings, so whitespace or comment edits made a
  method "modified"; here a pair is modified iff its body_hash (normalised unit text,
  comments and whitespace removed) differs. body_hash covers the whole unit, so a
  modifier, annotation, return-type or name edit alone also makes a pair modified;
  such rows carry block_changed = False (statement block identical) so that the
  dataset stage can tell them apart
- units with the same (class path, signature) get a positional suffix (run(), run()#2,
  ...: methods of several field-level anonymous classes or enum constant bodies).
  Pairing those by the suffixed signature breaks as soon as a body is inserted before
  the others, so pass 1 pairs such a group by the enclosing declaration (enum constant
  or field name) when that is unique, then by identical block, then order-preservingly
  by the Levenshtein ratio of the normalised blocks (first BLOCK_HEAD characters). With
  nothing inserted or deleted the last step is the positional pairing.
- every event keeps its scope (modified_method, new_method, deleted_method, new_file,
  deleted_file) instead of calling every log of new code ADD_LOG, and carries the real
  class path; an empty class path for modified methods only would leak the label
- REMOVE_LOG/ADD_LOG pairs that moved between methods are marked as relocations, and
  each event gets a validity status (core or the reason it is not). A relocation pair
  is tagged relocation_kind = same_signature when both statements sit in units with the
  same signature (constructors: same parameters), which is what a renamed class or a
  moved file looks like when its method also changed; different_signature otherwise
- each blob is parsed once into a compact summary (no XML is kept) and cached per worker
- blobs are sent to srcML in batches (one srcml call, one archive, split per file).
  On Windows a srcml process start costs more than parsing a typical file. Units are built with the same code
  as method_units.parse_java_source (build_units on the file's <unit>); if a batch fails,
  every file of it is parsed alone with parse_java_source so failures stay per file
"""

import copy
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from collections import OrderedDict

import Levenshtein

from src.detection.log_detection import file_framework
from src.parsing.method_units import parse_java_source, build_units
from src.parsing.srcml_parser import (
    SRC, _find_srcml, parse_xml, get_imports, get_unit_body, normalized_text, flatten_text
)
from src.matching.statement_matcher import (
    match_statements, normalized_call_text, payload_ratio, pair_conversions
)
from src.mining.git_walker import read_blob, has_generated_header

CACHE_SIZE = 3000
BATCH_FILES = 64
SRCML_JOBS = 1      # one thread per srcml call: the pool already uses the cores
BLOCK_HEAD = 1000   # characters of the normalised block kept to pair same-signature duplicates
_cache = OrderedDict()
cache_stats = {"parses": 0, "hits": 0, "parse_seconds": 0.0, "batch_fallbacks": 0}


def declaration_path(element):
    """Names of the declarations around a unit, outermost first ("" for an ordinary method).

    A method in an enum constant body gets the constant name, a method of an anonymous
    class in a field initializer gets the field name. The foundation class path is the
    same for all of them, which is why their signatures get the #N suffix.
    """
    names = []
    el = element.getparent()
    while el is not None:
        if el.tag == SRC + "decl":
            name = el.find(SRC + "name")
            names.append(flatten_text(name).strip() if name is not None else "")
        el = el.getparent()
    return "/".join(reversed(names))


def summarize_units(method_units):
    """Compact, picklable summary of a list of MethodUnit (src/parsing/method_units.py)."""
    units = []
    for u in method_units:
        body = get_unit_body(u.element)
        block = normalized_text(body) if body is not None else ""
        units.append({
            "ordinal": u.ordinal,
            "class_path": u.class_path,
            "container": declaration_path(u.element),
            "name": u.name,
            "signature": u.signature,
            "kind": u.kind,
            "start_line": u.start_line,
            "end_line": u.end_line,
            "body_hash": u.body_hash,
            "block_hash": hashlib.sha1(block.encode("utf-8")).hexdigest() if block else None,
            "block_head": block[:BLOCK_HEAD],
            "logs": [{
                "index": l.index,
                "formal_index": l.formal_index,
                "call_name": l.call_name,
                "call_text": l.call_text,
                "verbosity": l.verbosity,
                "logging_style": l.logging_style,
                "framework": l.framework,
                "line": l.line,
            } for l in u.logs],
        })
    return units


def parse_single(data, timeout=60):
    """Entry for one source parsed with the foundation entry point parse_java_source."""
    entry = {"generated": False, "units": None, "failure": None}
    start = time.time()
    try:
        parsed = parse_java_source(data)
    except Exception as e:
        parsed = None
        entry["failure"] = f"error:{type(e).__name__}"
    elapsed = time.time() - start
    if parsed is not None:
        entry["units"] = summarize_units(parsed.units)
    elif entry["failure"] is None:
        entry["failure"] = "timeout" if elapsed >= timeout - 1 else "srcml_failed"
    return entry


def srcml_batch(datas, timeout=120):
    """srcML <unit> roots of several sources from one srcml call, None if the call failed.

    Each root is deep-copied into its own document because the foundation XPaths
    ('//src:function ...') start at the document root.
    """
    tmp = tempfile.mkdtemp(prefix="srcml_batch_")
    try:
        paths = []
        for i, data in enumerate(datas):
            path = os.path.join(tmp, f"{i}.java")
            with open(path, "wb") as f:
                f.write(data)
            paths.append(path)
        try:
            res = subprocess.run([_find_srcml(), "--archive", "--position", "-j", str(SRCML_JOBS)] + paths,
                                 capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        if res.returncode != 0 or not res.stdout:
            return None
        archive = parse_xml(res.stdout)
        if archive is None:
            return None
        by_name = {}
        for unit in archive.findall(SRC + "unit"):
            by_name[os.path.basename(unit.get("filename", ""))] = unit
        roots = []
        for path in paths:
            unit = by_name.get(os.path.basename(path))
            if unit is None:
                return None
            roots.append(copy.deepcopy(unit))
        return roots
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def load_blobs(repo, blob_shas, markers, timeout=60):
    """{sha: {"generated", "units", "failure"}} for the given blobs.

    Cached per worker by (repository, blob sha). Generated blobs (header marker) are
    not parsed. failure is None, "timeout", "srcml_failed" or "error:<exception>".
    """
    entries = {}
    todo = []
    for sha in dict.fromkeys(blob_shas):
        key = (repo.git_dir, sha)
        if key in _cache:
            _cache.move_to_end(key)
            cache_stats["hits"] += 1
            entries[sha] = _cache[key]
            continue
        data = read_blob(repo, sha)
        if has_generated_header(data, markers):
            entries[sha] = {"generated": True, "units": None, "failure": None}
        else:
            todo.append((sha, data))

    for start in range(0, len(todo), BATCH_FILES):
        batch = todo[start:start + BATCH_FILES]
        t0 = time.time()
        roots = srcml_batch([data for _, data in batch], timeout=2 * timeout) if len(batch) > 1 else None
        if roots is None and len(batch) > 1:
            cache_stats["batch_fallbacks"] += 1
        for k, (sha, data) in enumerate(batch):
            if roots is None:
                entries[sha] = parse_single(data, timeout)
                continue
            try:
                units = build_units(roots[k], file_framework(get_imports(roots[k])))
                entries[sha] = {"generated": False, "units": summarize_units(units), "failure": None}
            except Exception:
                entries[sha] = parse_single(data, timeout)
        cache_stats["parses"] += len(batch)
        cache_stats["parse_seconds"] += time.time() - t0

    for sha, entry in entries.items():
        _cache[(repo.git_dir, sha)] = entry
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return entries


def base_signature(signature):
    """Signature without the foundation's duplicate suffix ("run()#2" -> "run()")."""
    return signature.split("#")[0]


def ordered_pairs(scores):
    """Order-preserving pairing of the rows and columns of an n x m score matrix.

    min(n, m) pairs, none crossing, with the largest total score (dynamic programming,
    as in a line diff). On ties the last rows / columns stay unpaired, so equal counts
    give the positional pairing. Returns [(row, col)] in order.
    """
    n = len(scores)
    m = len(scores[0]) if n else 0
    if n == 0 or m == 0:
        return []
    if n > m:
        return [(r, c) for c, r in ordered_pairs([list(col) for col in zip(*scores)])]

    best = [[float("-inf")] * (m + 1) for _ in range(n + 1)]
    best[0] = [0.0] * (m + 1)
    for k in range(1, n + 1):
        for l in range(k, m + 1):
            take = best[k - 1][l - 1] + scores[k - 1][l - 1]
            best[k][l] = max(take, best[k][l - 1])

    pairs = []
    k, l = n, m
    while k > 0:
        if l > k and best[k][l] == best[k][l - 1]:
            l -= 1
        else:
            pairs.append((k - 1, l - 1))
            k -= 1
            l -= 1
    return pairs[::-1]


def pair_duplicates(pre_units, post_units, pre_idx, post_idx):
    """Pair a pass-1 group whose (class path, signature) occurs more than once on a side.

    1. same container (enum constant / field name), when it is unique in the group on
       both sides; 2. identical blocks, in document order (this also covers reordered
       members); 3. the others keep their relative order: min(n, m) of them are paired
       without crossing, the inserted or deleted ones chosen so that the summed
       Levenshtein ratio of the block heads is largest. Returns [(i, j)].
    """
    pairs = []
    used_post = set()
    pre_containers = [pre_units[i]["container"] for i in pre_idx]
    post_containers = [post_units[j]["container"] for j in post_idx]
    left = []
    for i in pre_idx:
        c = pre_units[i]["container"]
        if pre_containers.count(c) == 1 and post_containers.count(c) == 1:
            j = post_idx[post_containers.index(c)]
            pairs.append((i, j))
            used_post.add(j)
        else:
            left.append(i)

    rest_pre = []
    for i in left:
        found = None
        for j in post_idx:
            if j not in used_post and pre_units[i]["block_hash"] == post_units[j]["block_hash"]:
                found = j
                break
        if found is None:
            rest_pre.append(i)
        else:
            pairs.append((i, found))
            used_post.add(found)

    rest_post = [j for j in post_idx if j not in used_post]
    scores = [[Levenshtein.ratio(pre_units[i]["block_head"], post_units[j]["block_head"]) for j in rest_post]
              for i in rest_pre]
    for r, c in ordered_pairs(scores):
        pairs.append((rest_pre[r], rest_post[c]))
    return pairs


def match_methods(pre_units, post_units):
    """Three-pass matching. Returns (pairs [(pre_pos, post_pos, pass)], unmatched_pre, unmatched_post)."""
    pairs = []
    used_post = set()

    pre_groups, post_groups = {}, {}
    for i, u in enumerate(pre_units):
        pre_groups.setdefault((u["class_path"], base_signature(u["signature"])), []).append(i)
    for j, v in enumerate(post_units):
        post_groups.setdefault((v["class_path"], base_signature(v["signature"])), []).append(j)
    used_pre = set()
    for key, pre_idx in pre_groups.items():
        post_idx = post_groups.get(key, [])
        if len(pre_idx) == 1 and len(post_idx) == 1:
            found = [(pre_idx[0], post_idx[0])]
        else:
            found = pair_duplicates(pre_units, post_units, pre_idx, post_idx)
        for i, j in found:
            pairs.append((i, j, 1))
            used_pre.add(i)
            used_post.add(j)
    rest = [i for i in range(len(pre_units)) if i not in used_pre]

    by_name = {}
    for j, v in enumerate(post_units):
        if j not in used_post:
            by_name.setdefault((v["class_path"], v["name"]), []).append(j)
    rest2 = []
    for i in rest:
        u = pre_units[i]
        found = None
        for j in by_name.get((u["class_path"], u["name"]), []):
            if j not in used_post:
                found = j
                break
        if found is None:
            rest2.append(i)
        else:
            pairs.append((i, found, 2))
            used_post.add(found)

    by_block = {}
    for j, v in enumerate(post_units):
        if j not in used_post and v["block_hash"]:
            by_block.setdefault(v["block_hash"], []).append(j)
    unmatched_pre = []
    for i in rest2:
        found = None
        for j in by_block.get(pre_units[i]["block_hash"], []) if pre_units[i]["block_hash"] else []:
            if j not in used_post:
                found = j
                break
        if found is None:
            unmatched_pre.append(i)
        else:
            pairs.append((i, found, 3))
            used_post.add(found)

    pairs.sort()
    unmatched_post = [j for j in range(len(post_units)) if j not in used_post]
    return pairs, unmatched_pre, unmatched_post


def _identity(unit):
    # what stays the same when only the enclosing class is renamed
    signature = base_signature(unit["signature"])
    if unit["kind"] == "constructor":
        return ("constructor", signature[signature.index("("):])
    return ("method", signature)


def _event(label, scope, pre_path, post_path, pre_unit=None, pre_log=None,
           post_unit=None, post_log=None, ratio=None):
    # the "subject" side: the removed statement for REMOVE_LOG, the post statement otherwise
    unit, log = (pre_unit, pre_log) if label == "REMOVE_LOG" else (post_unit, post_log)
    return {
        "scope": scope,
        "event_label": label,
        "logging_style": log["logging_style"],
        "framework": log["framework"],
        "file_path": pre_path if label == "REMOVE_LOG" else post_path,
        "pre_path": pre_path,
        "post_path": post_path,
        "class_path": unit["class_path"],
        "method_signature": unit["signature"],
        "call_name": log["call_name"],
        "call_text": log["call_text"],
        "call_text_before": pre_log["call_text"] if label == "CHANGE_LEVEL" else None,
        "pre_level": pre_log["verbosity"] if pre_log else None,
        "post_level": post_log["verbosity"] if post_log else None,
        "statement_continuity": "matched" if label == "CHANGE_LEVEL" else "none",
        "match_confidence": round(ratio, 4) if ratio is not None else None,
        "pre_line": pre_log["line"] if pre_log else None,
        "post_line": post_log["line"] if post_log else None,
        "pre_formal_index": pre_log["formal_index"] if pre_log else None,
        "post_formal_index": post_log["formal_index"] if post_log else None,
        "pre_ordinal": pre_unit["ordinal"] if pre_unit else None,
        "post_ordinal": post_unit["ordinal"] if post_unit else None,
        "is_relocated": False,
        "relocation_kind": None,
        "_ident": _identity(unit),
        "_norm": normalized_call_text(log["call_text"]),
        "_doc": (unit["ordinal"], log["index"]),
    }


def diff_file(change_type, pre_path, post_path, pre_units, post_units, threshold=0.5, continuity=0.7):
    """Events, modified method pairs and auxiliary text changes of one file change.

    change_type is A, D, M or R (R/M need both summaries). Events carry two private
    keys used at commit level: _mkey (method identity, for relocation) and _norm.
    """
    events = []
    pairs = []

    if change_type == "A":
        for v in post_units:
            for log in v["logs"]:
                e = _event("ADD_LOG", "new_file", None, post_path, post_unit=v, post_log=log)
                e["_mkey"] = ("post", post_path, v["ordinal"])
                events.append(e)
        return events, pairs
    if change_type == "D":
        for u in pre_units:
            for log in u["logs"]:
                e = _event("REMOVE_LOG", "deleted_file", pre_path, None, pre_unit=u, pre_log=log)
                e["_mkey"] = ("pre", pre_path, u["ordinal"])
                events.append(e)
        return events, pairs

    matched, gone, new = match_methods(pre_units, post_units)
    for i, j, match_pass in matched:
        u, v = pre_units[i], post_units[j]
        if u["body_hash"] == v["body_hash"]:
            continue
        mkey = ("pair", pre_path, post_path, u["ordinal"], v["ordinal"])
        st_pairs, removed, added = match_statements(u["logs"], v["logs"], threshold)
        pair = {"pre": u, "post": v, "match_pass": match_pass, "matched": [],
                "events": [], "aux": [], "uncertain": []}

        for a in removed:
            pair["events"].append(_event("REMOVE_LOG", "modified_method", pre_path, post_path,
                                         pre_unit=u, pre_log=u["logs"][a], post_unit=v))
        for a, b, ratio in st_pairs:
            pl, ql = u["logs"][a], v["logs"][b]
            pair["matched"].append((pl, ql, ratio))
            if payload_ratio(pl["call_text"], ql["call_text"]) < continuity:
                # paired by the upstream ratio but the messages differ: identity unsure,
                # so no CHANGE_LEVEL; the dataset stage keeps such pairs out of every pool
                pair["uncertain"].append((pl, ql))
                aux = _aux_row(pre_path, post_path, u, v, pl, ql, ratio)
                aux["uncertain"] = True
                pair["aux"].append(aux)
            elif pl["verbosity"] and ql["verbosity"] and pl["verbosity"] != ql["verbosity"]:
                pair["events"].append(_event("CHANGE_LEVEL", "modified_method", pre_path, post_path,
                                             pre_unit=u, pre_log=pl, post_unit=v, post_log=ql,
                                             ratio=ratio))
            elif normalized_call_text(pl["call_text"]) != normalized_call_text(ql["call_text"]):
                pair["aux"].append(_aux_row(pre_path, post_path, u, v, pl, ql, ratio))
        for b in added:
            pair["events"].append(_event("ADD_LOG", "modified_method", pre_path, post_path,
                                         pre_unit=u, post_unit=v, post_log=v["logs"][b]))
        # a statement rewritten in another logging style (System.out -> logger, printStackTrace
        # -> logger.error(.., e)) was not added or removed: tag both sides like a relocation
        removed_ev = {e["_doc"][1]: e for e in pair["events"] if e["event_label"] == "REMOVE_LOG"}
        added_ev = {e["_doc"][1]: e for e in pair["events"] if e["event_label"] == "ADD_LOG"}
        for a, b, _ in pair_conversions(u["logs"], v["logs"], removed, added, continuity):
            for e in (removed_ev.get(u["logs"][a]["index"]), added_ev.get(v["logs"][b]["index"])):
                if e is not None:
                    e["is_relocated"] = True
                    e["relocation_kind"] = "style_conversion"
        for e in pair["events"]:
            e["_mkey"] = mkey
        events.extend(pair["events"])
        pairs.append(pair)

    for i in gone:
        u = pre_units[i]
        for log in u["logs"]:
            e = _event("REMOVE_LOG", "deleted_method", pre_path, post_path, pre_unit=u, pre_log=log)
            e["_mkey"] = ("pre", pre_path, u["ordinal"])
            events.append(e)
    for j in new:
        v = post_units[j]
        for log in v["logs"]:
            e = _event("ADD_LOG", "new_method", pre_path, post_path, post_unit=v, post_log=log)
            e["_mkey"] = ("post", post_path, v["ordinal"])
            events.append(e)
    return events, pairs


def _aux_row(pre_path, post_path, u, v, pl, ql, ratio):
    return {
        "pre_path": pre_path,
        "post_path": post_path,
        "class_path": v["class_path"],
        "signature_pre": u["signature"],
        "signature_post": v["signature"],
        "pre_ordinal": u["ordinal"],
        "post_ordinal": v["ordinal"],
        "logging_style": ql["logging_style"],
        "call_name_before": pl["call_name"],
        "call_name": ql["call_name"],
        "call_text_before": pl["call_text"],
        "call_text": ql["call_text"],
        "pre_level": pl["verbosity"],
        "post_level": ql["verbosity"],
        "match_confidence": round(ratio, 4),
        "pre_line": pl["line"],
        "post_line": ql["line"],
        "pre_index": pl["index"],
        "post_index": ql["index"],
        "pre_formal_index": pl["formal_index"],
        "post_formal_index": ql["formal_index"],
    }


def mark_relocations(events, continuity=0.7):
    """Pair REMOVE_LOG/ADD_LOG events of one commit that moved between methods or files.

    Same normalised call text, same level and same style, different method; one-to-one,
    greedy in document order (file order of the diff, then unit ordinal, then statement
    index). events must carry "_file" (position of the file in the commit diff).
    Both events of a pair get relocation_kind: same_signature when the two units have the
    same signature (constructors: same parameters), e.g. a renamed class whose method
    also changed, so the statement itself probably never moved; different_signature otherwise.
    """
    adds = {}
    for e in sorted((e for e in events if e["event_label"] == "ADD_LOG"),
                    key=lambda e: (e["_file"], e["_doc"])):
        adds.setdefault((e["_norm"], e["post_level"], e["logging_style"]), []).append(e)

    removes = sorted((e for e in events if e["event_label"] == "REMOVE_LOG"),
                     key=lambda e: (e["_file"], e["_doc"]))
    for r in removes:
        if r["is_relocated"]:
            continue
        for a in adds.get((r["_norm"], r["pre_level"], r["logging_style"]), []):
            if a["is_relocated"] or a["_mkey"] == r["_mkey"]:
                continue
            kind = "same_signature" if a["_ident"] == r["_ident"] else "different_signature"
            for e in (a, r):
                e["is_relocated"] = True
                e["relocation_kind"] = kind
            break

    # second pass: moves whose text was edited on the way (extract method, ...): same style,
    # different method, payload similarity >= continuity; level may differ
    left_adds = [e for e in events if e["event_label"] == "ADD_LOG" and not e["is_relocated"]]
    left_adds.sort(key=lambda e: (e["_file"], e["_doc"]))
    candidates = []
    for r in removes:
        if r["is_relocated"]:
            continue
        for a in left_adds:
            if a["_mkey"] == r["_mkey"] or a["logging_style"] != r["logging_style"]:
                continue
            ratio = payload_ratio(r["call_text"], a["call_text"])
            if ratio >= continuity:
                candidates.append((-ratio, r["_file"], r["_doc"], a["_file"], a["_doc"], id(r), id(a), r, a))
    candidates.sort(key=lambda c: c[:5])
    for c in candidates:
        r, a = c[7], c[8]
        if r["is_relocated"] or a["is_relocated"]:
            continue
        for e in (r, a):
            e["is_relocated"] = True
            e["relocation_kind"] = "edited_move"


def validity_status(event, is_bulk):
    """core iff formal, modified_method, not relocated, not bulk (priority non_formal > bulk > relocated > out_of_scope)."""
    if event["logging_style"] != "formal":
        return "non_formal"
    if is_bulk:
        return "bulk"
    if event["is_relocated"]:
        return "relocated"
    if event["scope"] != "modified_method":
        return "out_of_scope"
    return "core"


def method_row(pair):
    """methods_changed.jsonl fields of one modified pair (file and commit fields are added by the caller).

    Every pre formal_index ends up in exactly one of removed_formal_pre, relocated_pre or
    the pre side of matched_formal (same for the post side). Call after mark_relocations.
    Besides the common fields: class_path_pre (class_path is the post-state one; they
    differ for pass-3 moves between classes) and block_changed (False when only the unit
    header changed: modifiers, annotations, return type, name or parameters) and
    added_all_post (post-state `index`, all styles, of every statement added in this
    commit, relocated ones included; the ADD_LOG view masks all of them),
    uncertain_formal ([pre_fi, post_fi] of matched formal pairs whose payload similarity is
    below the continuity threshold; a subset of matched_formal, kept out of every pool) and
    uncertain_post_all (post `index` of those pairs, masked in ADD_LOG views).
    """
    u, v = pair["pre"], pair["post"]
    added_all = sorted(e["_doc"][1] for e in pair["events"] if e["event_label"] == "ADD_LOG")
    uncertain_formal = sorted([pl["formal_index"], ql["formal_index"]] for pl, ql in pair.get("uncertain", [])
                              if pl["logging_style"] == "formal")
    uncertain_post_all = sorted(ql["index"] for pl, ql in pair.get("uncertain", []))
    added, removed, relocated_pre, relocated_post, level_changed = [], [], [], [], []
    other = bool(pair["aux"])
    for e in pair["events"]:
        if e["logging_style"] != "formal":
            other = True
            continue
        if e["event_label"] == "ADD_LOG":
            (relocated_post if e["is_relocated"] else added).append(e["post_formal_index"])
        elif e["event_label"] == "REMOVE_LOG":
            (relocated_pre if e["is_relocated"] else removed).append(e["pre_formal_index"])
        else:
            level_changed.append([e["pre_formal_index"], e["post_formal_index"]])

    matched_formal = [[pl["formal_index"], ql["formal_index"], round(ratio, 4)]
                      for pl, ql, ratio in pair["matched"] if pl["logging_style"] == "formal"]
    pre_formal = [l for l in u["logs"] if l["logging_style"] == "formal"]
    post_formal = [l for l in v["logs"] if l["logging_style"] == "formal"]
    return {
        "class_path": v["class_path"],
        "class_path_pre": u["class_path"],
        "method_name": v["name"],
        "signature_pre": u["signature"],
        "signature_post": v["signature"],
        "kind": v["kind"],
        "match_pass": pair["match_pass"],
        "pre_ordinal": u["ordinal"],
        "post_ordinal": v["ordinal"],
        "pre_start_line": u["start_line"],
        "pre_end_line": u["end_line"],
        "post_start_line": v["start_line"],
        "post_end_line": v["end_line"],
        "n_pre_formal": len(pre_formal),
        "n_post_formal": len(post_formal),
        "n_pre_logs_all": len(u["logs"]),
        "n_post_logs_all": len(v["logs"]),
        "added_formal_post": sorted(added),
        "removed_formal_pre": sorted(removed),
        "level_changed": sorted(level_changed),
        "matched_formal": sorted(matched_formal),
        "pre_levels": [l["verbosity"] for l in pre_formal],
        "post_levels": [l["verbosity"] for l in post_formal],
        "relocated_pre": sorted(relocated_pre),
        "relocated_post": sorted(relocated_post),
        "other_log_change": other,
        "block_changed": u["block_hash"] != v["block_hash"],
        "added_all_post": added_all,
        "uncertain_formal": uncertain_formal,
        "uncertain_post_all": uncertain_post_all,
    }
