"""
Static indicators of performance-sensitive game code.

Indicators come from subtokens of the method name, class path and file path, plus loop
structure in the method AST. The keyword lists live in configs/perf_sensitive.yaml so the
definition of the performance-sensitive subset is explicit and reproducible.
"""

from src.common.config import load_config
from src.features.lexical import subtokens
from src.parsing.srcml_parser import SRC, get_unit_body

LOOP_TAGS = (SRC + "for", SRC + "while", SRC + "do")


def _cfg():
    return load_config("perf_sensitive")


def path_tokens(file_path):
    toks = []
    for seg in (file_path or "").replace("\\", "/").split("/"):
        if seg.endswith(".java"):
            seg = seg[:-5]
        toks.extend(subtokens(seg))
    return toks


def param_names(unit_el):
    names = []
    params = unit_el.find(SRC + "parameter_list")
    if params is None:
        return names
    for p in params.findall(SRC + "parameter"):
        n = p.find(SRC + "decl/" + SRC + "name")
        if n is not None and n.text:
            names.append(n.text.lower())
    return names


def loop_stats(unit_el):
    """(n_loops, max_loop_nesting) inside the unit body."""
    body = get_unit_body(unit_el)
    if body is None:
        return 0, 0
    n = 0
    max_nest = 0
    for el in body.iter(*LOOP_TAGS):
        n += 1
        depth = 1
        parent = el.getparent()
        while parent is not None and parent is not unit_el:
            if parent.tag in LOOP_TAGS:
                depth += 1
            parent = parent.getparent()
        max_nest = max(max_nest, depth)
    return n, max_nest


def domain_indicators(unit_el, method_name, class_path, file_path):
    cfg = _cfg()
    name_toks = set(subtokens(method_name))
    sources = {
        "method_name": name_toks,
        "class_path": set(subtokens(class_path)),
        "file_path": set(path_tokens(file_path)),
    }
    pool = set()
    for src in cfg["subsystem_sources"]:
        pool |= sources[src]

    n_loops, max_nest = loop_stats(unit_el) if unit_el is not None else (0, 0)
    params = set(param_names(unit_el)) if unit_el is not None else set()

    d = {
        "d_loop": int(n_loops > 0),
        "d_n_loops": n_loops,
        "d_nested_loop": int(max_nest >= 2),
        "d_frame_name": int(bool(name_toks & set(cfg["frame_method_tokens"]))),
        "d_frame_param": int(bool(params & set(cfg["frame_param_names"]))),
    }
    d["d_frame"] = int(d["d_frame_name"] or d["d_frame_param"])

    any_subsystem = 0
    for sub, words in cfg["subsystems"].items():
        hit = int(bool(pool & set(words)))
        d[f"d_{sub}"] = hit
        any_subsystem |= hit
    d["d_subsystem"] = any_subsystem

    d["d_is_perf_sensitive"] = int(d["d_loop"] or d["d_frame"] or d["d_subsystem"])

    if d["d_frame"]:
        cat = "frame_update"
    elif d["d_loop"]:
        cat = "loop"
    elif d["d_subsystem"]:
        cat = "subsystem"
    else:
        cat = "general"
    d["d_ctx_category"] = cat
    return d
