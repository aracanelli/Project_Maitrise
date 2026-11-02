"""
Method (m_), logging-context (l_) and lexical (x_) features of a method unit.

All three are computed on the task view of the unit: the pre-state method for ADD_LOG, REMOVE_LOG and CHANGE_LEVEL, and for the add_log_post
sensitivity task the post-state method after the added logs were masked, so the
statements the developer added never reach the features. Counts include code inside
lambdas and anonymous classes because those statements belong to the enclosing unit.

The catch-block indicators (empty catch, catch without log) follow the "Logged" and
"EmptyBlock" catch features from LogAdvisor (Zhu et al., 2015), recomputed on srcML
instead of Roslyn.
"""

import math

from src.detection.verbosity import LEVELS, LEVEL_ORD
from src.features.lexical import N_BUCKETS, subtokens, bucket_counts
from src.parsing.srcml_parser import SRC, TYPE_TAGS, flatten_code, get_unit_body

LOOP_TAGS = {SRC + "for", SRC + "while", SRC + "do"}
# a catch/finally clause belongs to its try statement, so `try` counts one level
CONTROL_TAGS = LOOP_TAGS | {SRC + "if_stmt", SRC + "switch", SRC + "try", SRC + "synchronized"}
STATEMENT_TAGS = CONTROL_TAGS | {
    SRC + "expr_stmt", SRC + "decl_stmt", SRC + "return", SRC + "throw",
    SRC + "break", SRC + "continue", SRC + "assert",
}
NESTED_TAGS = {SRC + "lambda", SRC + "class", SRC + "function", SRC + "constructor"}

PRIMITIVES = {"boolean", "byte", "char", "short", "int", "long", "float", "double"}
# java.util collections plus libGDX Array/IntArray/ObjectMap and Arc Seq/IntSeq
COLLECTION_SUFFIXES = ("List", "Set", "Map", "Collection", "Array", "Queue", "Deque", "Iterable", "Seq")

RETURN_KINDS = ["void", "primitive", "object", "collection", "array", "none"]
VISIBILITIES = ["public", "protected", "private", "package"]
DOMINANT_KINDS = ["NONE"] + LEVELS

METHOD_COLUMNS = (
    ["m_loc", "m_n_params"]
    + [f"m_return_{k}" for k in RETURN_KINDS]
    + ["m_is_constructor", "m_is_static"]
    + [f"m_visibility_{v}" for v in VISIBILITIES]
    + ["m_max_nesting", "m_n_if", "m_n_switch", "m_n_ternary", "m_n_conditionals",
       "m_n_loops", "m_n_try", "m_n_catch", "m_n_throw", "m_n_return", "m_n_calls",
       "m_n_var_decls", "m_has_early_exit", "m_n_statements", "m_n_empty_catch",
       "m_n_catch_without_log", "m_n_lambdas", "m_n_anon_classes", "m_n_string_literals",
       "m_has_synchronized"]
)

LOG_COLUMNS = (
    ["l_n_formal", "l_n_informal", "l_has_formal", "l_log_density"]
    + [f"l_dominant_level_{k}" for k in DOMINANT_KINDS]
    + ["l_mean_level_ord", "l_n_logs_in_catch", "l_n_logs_in_loop", "l_frac_catch_with_log"]
)

LEXICAL_COLUMNS = [f"x_{i:03d}" for i in range(N_BUCKETS)]


def ancestors(el, stop):
    """Ancestors of el up to (not including) stop, innermost first."""
    out = []
    parent = el.getparent()
    while parent is not None and parent is not stop:
        out.append(parent)
        parent = parent.getparent()
    return out


def is_inside(el, container, stop):
    parent = el.getparent()
    while parent is not None and parent is not stop:
        if parent is container:
            return True
        parent = parent.getparent()
    return False


def strip_generics(text):
    out = []
    depth = 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(depth - 1, 0)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def type_text(name_el):
    """'java.util.List<String>[]' -> 'java.util.List[]'"""
    return strip_generics("".join(flatten_code(name_el).split()))


def return_category(unit_el):
    if unit_el.tag == SRC + "constructor":
        return "none"
    type_el = unit_el.find(SRC + "type")
    if type_el is None:
        return "none"
    name_el = type_el.find(SRC + "name")
    if name_el is None:
        return "object"
    text = type_text(name_el)
    if text.endswith("]"):
        return "array"
    base = text.split(".")[-1]
    if base == "void":
        return "void"
    if base in PRIMITIVES:
        return "primitive"
    if base.endswith(COLLECTION_SUFFIXES):
        return "collection"
    return "object"


def unit_specifiers(unit_el):
    specs = [s.text for s in unit_el.findall(SRC + "specifier")]
    type_el = unit_el.find(SRC + "type")
    if type_el is not None:
        specs += [s.text for s in type_el.findall(SRC + "specifier")]
    return {s for s in specs if s}


def visibility(unit_el, specs):
    for v in ("public", "protected", "private"):
        if v in specs:
            return v
    # interface and annotation members are implicitly public
    block = unit_el.getparent()
    owner = block.getparent() if block is not None else None
    if owner is not None and owner.tag in (SRC + "interface", SRC + "annotation_defn"):
        return "public"
    return "package"


def is_object_creation(call):
    prev = call.getprevious()
    return prev is not None and prev.tag == SRC + "operator" and (prev.text or "").strip() == "new"


def max_nesting(unit_el):
    deepest = 0
    for el in unit_el.iter(*CONTROL_TAGS):
        depth = 1 + sum(1 for a in ancestors(el, unit_el) if a.tag in CONTROL_TAGS)
        deepest = max(deepest, depth)
    return deepest


def block_is_empty(block):
    if block is None:
        return True
    content = block.find(SRC + "block_content")
    target = content if content is not None else block
    return all(child.tag == SRC + "comment" for child in target)


def has_early_exit(unit_el):
    body = get_unit_body(unit_el)
    if body is None:
        return 0
    top = [c for c in body if c.tag in STATEMENT_TAGS]
    last = top[-1] if top else None
    for el in body.iter(SRC + "return", SRC + "throw"):
        # returns of lambdas or anonymous-class methods do not leave this method
        if any(a.tag in NESTED_TAGS for a in ancestors(el, unit_el)):
            continue
        if el is not last:
            return 1
    return 0


def count_local_decls(unit_el):
    n = 0
    for decl in unit_el.iter(SRC + "decl"):
        parent = decl.getparent()
        # method, catch and lambda parameters are not local variables
        if parent is not None and parent.tag == SRC + "parameter":
            continue
        n += 1
    return n


def method_features(unit):
    el = unit.element
    m = {}
    m["m_loc"] = sum(1 for line in flatten_code(el).splitlines() if line.strip())
    params = el.find(SRC + "parameter_list")
    m["m_n_params"] = len(params.findall(SRC + "parameter")) if params is not None else 0

    ret = return_category(el)
    for k in RETURN_KINDS:
        m[f"m_return_{k}"] = int(ret == k)

    specs = unit_specifiers(el)
    m["m_is_constructor"] = int(unit.kind == "constructor")
    m["m_is_static"] = int("static" in specs)
    vis = visibility(el, specs)
    for v in VISIBILITIES:
        m[f"m_visibility_{v}"] = int(vis == v)

    m["m_max_nesting"] = max_nesting(el)
    m["m_n_if"] = sum(1 for _ in el.iter(SRC + "if"))
    m["m_n_switch"] = sum(1 for _ in el.iter(SRC + "switch"))
    m["m_n_ternary"] = sum(1 for _ in el.iter(SRC + "ternary"))
    m["m_n_conditionals"] = m["m_n_if"] + m["m_n_switch"] + m["m_n_ternary"]
    m["m_n_loops"] = sum(1 for _ in el.iter(*LOOP_TAGS))
    m["m_n_try"] = sum(1 for _ in el.iter(SRC + "try"))
    catches = list(el.iter(SRC + "catch"))
    m["m_n_catch"] = len(catches)
    m["m_n_throw"] = sum(1 for _ in el.iter(SRC + "throw"))
    m["m_n_return"] = sum(1 for _ in el.iter(SRC + "return"))
    m["m_n_calls"] = sum(1 for c in el.iter(SRC + "call") if not is_object_creation(c))
    m["m_n_var_decls"] = count_local_decls(el)
    m["m_has_early_exit"] = has_early_exit(el)
    m["m_n_statements"] = sum(1 for _ in el.iter(*STATEMENT_TAGS))

    formal = unit.formal_logs
    n_empty = 0
    n_without_log = 0
    for c in catches:
        if block_is_empty(c.find(SRC + "block")):
            n_empty += 1
        if not any(is_inside(log.element, c, el) for log in formal):
            n_without_log += 1
    m["m_n_empty_catch"] = n_empty
    m["m_n_catch_without_log"] = n_without_log

    m["m_n_lambdas"] = sum(1 for _ in el.iter(SRC + "lambda"))
    m["m_n_anon_classes"] = sum(1 for c in el.iter(SRC + "class") if c.find(SRC + "name") is None)
    m["m_n_string_literals"] = sum(1 for lit in el.iter(SRC + "literal") if lit.get("type") == "string")
    m["m_has_synchronized"] = int("synchronized" in specs or el.find(".//" + SRC + "synchronized") is not None)
    return m


def dominant_level(logs):
    """Most frequent known level; ties go to the lower ordinal; NONE without known levels."""
    counts = {lvl: 0 for lvl in LEVELS}
    for log in logs:
        if log.verbosity in counts:
            counts[log.verbosity] += 1
    if sum(counts.values()) == 0:
        return "NONE"
    return max(LEVELS, key=lambda lvl: (counts[lvl], -LEVEL_ORD[lvl]))


def mean_level_ord(logs):
    ords = [LEVEL_ORD[log.verbosity] for log in logs if log.verbosity in LEVEL_ORD]
    if not ords:
        return math.nan
    return sum(ords) / len(ords)


def level_columns(logs, prefix):
    dom = dominant_level(logs)
    out = {f"{prefix}_dominant_level_{k}": int(dom == k) for k in DOMINANT_KINDS}
    out[f"{prefix}_mean_level_ord"] = mean_level_ord(logs)
    return out


def log_context_features(unit, m_loc):
    el = unit.element
    formal = unit.formal_logs
    l = {}
    l["l_n_formal"] = len(formal)
    l["l_n_informal"] = sum(1 for log in unit.logs if log.logging_style == "informal_print")
    l["l_has_formal"] = int(len(formal) > 0)
    l["l_log_density"] = len(formal) / max(m_loc, 1)
    l.update(level_columns(formal, "l"))

    in_catch = 0
    in_loop = 0
    for log in formal:
        tags = {a.tag for a in ancestors(log.element, el)}
        in_catch += int(SRC + "catch" in tags)
        in_loop += int(bool(tags & LOOP_TAGS))
    l["l_n_logs_in_catch"] = in_catch
    l["l_n_logs_in_loop"] = in_loop

    catches = list(el.iter(SRC + "catch"))
    if catches:
        with_log = sum(1 for c in catches if any(is_inside(log.element, c, el) for log in formal))
        l["l_frac_catch_with_log"] = with_log / len(catches)
    else:
        l["l_frac_catch_with_log"] = math.nan
    return l


def lexical_features(unit_el):
    """log1p bucket counts of identifier subtokens (no string literals, no comments).

    Each srcML <name> carries only its own identifier as direct text; qualified
    names are split into child <name> elements, so every identifier is seen once.
    """
    toks = []
    for name in unit_el.iter(SRC + "name"):
        if name.text:
            toks.extend(subtokens(name.text))
    counts = bucket_counts(toks)
    return {f"x_{i:03d}": math.log1p(c) for i, c in enumerate(counts)}


def is_type_member(el):
    """True for declarations placed directly in a class/enum/interface body."""
    block = el.getparent()
    return block is not None and block.tag == SRC + "block" and block.getparent() is not None \
        and block.getparent().tag in TYPE_TAGS
