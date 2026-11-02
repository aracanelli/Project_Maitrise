"""
Anchor-statement features (s_) for the statement tasks REMOVE_LOG and CHANGE_LEVEL.

The anchor is a formal logging statement of the pre-state method. Only its current
form is described (level, position, message shape, enclosing context); the post-state
level and the direction of a level change are labels and are never features.
"""

import math
import re

from src.detection.verbosity import LEVELS, LEVEL_ORD
from src.features.lexical import subtokens
from src.features.method_features import (
    LOOP_TAGS, CONTROL_TAGS, STATEMENT_TAGS, NESTED_TAGS, ancestors
)
from src.parsing.srcml_parser import SRC, flatten_code, flatten_text, get_call_arguments

STATEMENT_FRAMEWORKS = ["jul", "jdk_system", "slf4j", "log4j", "jcl", "arc", "gdx", "riiablo", "android", "unknown"]
NEIGHBOR_WINDOW = 3

STATEMENT_COLUMNS = (
    [f"s_level_{lvl}" for lvl in LEVELS + ["UNKNOWN"]]
    + ["s_level_ord", "s_in_loop", "s_in_catch", "s_in_try_body", "s_in_if", "s_in_else",
       "s_in_switch", "s_in_synchronized", "s_in_lambda_or_anon", "s_depth", "s_rel_position",
       "s_n_args", "s_msg_len", "s_n_string_literals", "s_has_concat", "s_has_exception_arg",
       "s_is_guarded", "s_n_neighbor_logs", "s_neighbor_warn_error",
       "s_level_eq_method_dominant", "s_level_eq_file_dominant", "s_level_minus_file_mean"]
    + [f"s_framework_{fw}" for fw in STATEMENT_FRAMEWORKS]
    + ["s_n_tokens"]
)

_GUARD = re.compile(r"is(Debug|Trace|Info|Warn)Enabled|isLoggable|\bDEBUG\b|\bdebug\b")


def literal_body(text):
    if text.startswith('"""') and text.endswith('"""') and len(text) >= 6:
        return text[3:-3]
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def catch_parameter_names(anc):
    names = set()
    for a in anc:
        if a.tag != SRC + "catch":
            continue
        for name in a.iterfind(SRC + "parameter_list/" + SRC + "parameter/" + SRC + "decl/" + SRC + "name"):
            if name.text:
                names.add(name.text)
    return names


def enclosing_statement(el, unit_el):
    if el.tag in STATEMENT_TAGS:
        return el
    for a in ancestors(el, unit_el):
        if a.tag in STATEMENT_TAGS:
            return a
    return None


def neighbor_logs(unit, anchor):
    """Formal logs (other than the anchor) inside the +-3 sibling statements of the anchor."""
    el = anchor.element
    parent = el.getparent()
    if parent is None:
        return 0, 0
    siblings = [c for c in parent if c.tag in STATEMENT_TAGS or c is el]
    pos = siblings.index(el)
    window = siblings[max(pos - NEIGHBOR_WINDOW, 0):pos] + siblings[pos + 1:pos + 1 + NEIGHBOR_WINDOW]
    window_ids = {id(s) for s in window}
    n = 0
    n_high = 0
    for log in unit.formal_logs:
        if log.element is el:
            continue
        node = log.element
        while node is not None and node is not parent:
            if id(node) in window_ids:
                n += 1
                n_high += int(log.verbosity in ("WARN", "ERROR"))
                break
            node = node.getparent()
    return n, n_high


def statement_features(unit, anchor, method_dominant, file_dominant, file_mean):
    unit_el = unit.element
    el = anchor.element
    anc = ancestors(el, unit_el)
    tags = [a.tag for a in anc]
    lvl = anchor.verbosity
    s = {}
    for name in LEVELS + ["UNKNOWN"]:
        s[f"s_level_{name}"] = int((lvl or "UNKNOWN") == name)
    s["s_level_ord"] = LEVEL_ORD.get(lvl, 0)

    s["s_in_loop"] = int(any(t in LOOP_TAGS for t in tags))
    s["s_in_catch"] = int(SRC + "catch" in tags)
    s["s_in_try_body"] = int(any(
        a.tag == SRC + "block" and a.getparent() is not None and a.getparent().tag == SRC + "try"
        for a in anc
    ))
    s["s_in_if"] = int(SRC + "if" in tags)
    s["s_in_else"] = int(SRC + "else" in tags)
    s["s_in_switch"] = int(SRC + "switch" in tags)
    s["s_in_synchronized"] = int(SRC + "synchronized" in tags)
    s["s_in_lambda_or_anon"] = int(any(t in NESTED_TAGS for t in tags))
    s["s_depth"] = sum(1 for t in tags if t in CONTROL_TAGS)

    statements = [e for e in unit_el.iter(*STATEMENT_TAGS)]
    own = enclosing_statement(el, unit_el)
    if own is not None and statements:
        rank = next(i for i, e in enumerate(statements) if e is own)
        s["s_rel_position"] = (rank + 1) / len(statements)
    else:
        s["s_rel_position"] = math.nan

    args = get_call_arguments(anchor.call)
    s["s_n_args"] = len(args)
    msg_len = 0
    n_lit = 0
    concat = 0
    for arg in args:
        lits = [lit for lit in arg.iter(SRC + "literal") if lit.get("type") == "string"]
        n_lit += len(lits)
        msg_len += sum(len(literal_body(flatten_text(lit))) for lit in lits)
        plus = any((op.text or "").strip() == "+" for op in arg.iter(SRC + "operator"))
        if lits and plus:
            concat = 1
    s["s_msg_len"] = msg_len
    s["s_n_string_literals"] = n_lit
    s["s_has_concat"] = concat

    catch_names = catch_parameter_names(anc)
    exc = 0
    for arg in args:
        expr = arg.find(SRC + "expr")
        if expr is not None and len(expr) == 1 and expr[0].tag == SRC + "name" and expr[0].text in catch_names:
            exc = 1
    s["s_has_exception_arg"] = exc

    guarded = 0
    for a in anc:
        if a.tag != SRC + "if":
            continue
        cond = a.find(SRC + "condition")
        if cond is not None and _GUARD.search(flatten_code(cond)):
            guarded = 1
    s["s_is_guarded"] = guarded

    n_near, n_high = neighbor_logs(unit, anchor)
    s["s_n_neighbor_logs"] = n_near
    s["s_neighbor_warn_error"] = int(n_high > 0)

    known = lvl in LEVEL_ORD
    s["s_level_eq_method_dominant"] = int(known and lvl == method_dominant)
    s["s_level_eq_file_dominant"] = int(known and lvl == file_dominant)
    if known and not math.isnan(file_mean):
        s["s_level_minus_file_mean"] = LEVEL_ORD[lvl] - file_mean
    else:
        s["s_level_minus_file_mean"] = math.nan

    fw = anchor.framework if anchor.framework in STATEMENT_FRAMEWORKS else "unknown"
    for name in STATEMENT_FRAMEWORKS:
        s[f"s_framework_{name}"] = int(fw == name)
    s["s_n_tokens"] = len(subtokens(anchor.call_text))
    return s
