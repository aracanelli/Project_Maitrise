"""
Method units and their logging statements.

A method unit is a function or constructor that is not nested in another one
(see srcml_parser.extract_method_units). This is the method-level context used by
mining, features and graphs.
"""

import hashlib
from dataclasses import dataclass, field

from src.parsing.srcml_parser import (
    SRC, source_to_root, extract_method_units, get_unit_name, get_unit_signature,
    get_class_path, get_lines, get_imports, get_statement_calls, get_call_name,
    get_call_text, get_call_arguments, flatten_text, flatten_code, normalized_text
)
from src.detection.log_detection import (
    is_logging_name, split_call_name, classify_logging_style, file_framework, infer_framework,
    static_log_names
)
from src.parsing.srcml_parser import call_has_arguments
from src.detection.verbosity import classify_verbosity


@dataclass
class LogStatement:
    index: int
    formal_index: object
    element: object
    call: object
    call_name: str
    caller: str
    level_token: object
    call_text: str
    verbosity: object
    logging_style: str
    framework: str
    line: object


@dataclass
class MethodUnit:
    element: object
    ordinal: int
    class_path: str
    name: str
    signature: str
    kind: str
    start_line: object
    end_line: object
    body_hash: str
    logs: list = field(default_factory=list)

    @property
    def formal_logs(self):
        return [l for l in self.logs if l.logging_style == "formal"]


@dataclass
class ParsedFile:
    root: object
    imports: list
    units: list
    file_framework: str
    sloc: int
    comment_lines: int
    static_log_names: dict = field(default_factory=dict)


def _nearest_unit(el):
    while el is not None and el.tag != SRC + "unit":
        el = el.getparent()
    return el


def resolved_call_name(call, static_names):
    """Dotted call name with chained-logger prefixes and static-import owners filled in."""
    name = get_call_name(call)
    prev = call.getprevious()
    if prev is not None and prev.tag == SRC + "operator" and (prev.text or "").strip() == ".":
        head = prev.getprevious()
        if head is not None and head.tag == SRC + "call":
            return get_call_name(head) + "()." + name
    if "." not in name and name in static_names:
        return static_names[name] + "." + name
    return name


def statement_style(call, call_name):
    """(style, verbosity) of a statement call, or None when it is not a logging statement.

    Besides the upstream predicate, `x.printStackTrace(..)` counts as an informal print
    since it writes the stack trace to stderr, like a System.err call.
    """
    caller, level = split_call_name(call_name)
    if level == "printStackTrace":
        return "informal_print", "ERROR"
    if not call_has_arguments(call) or not is_logging_name(call_name):
        return None
    args = get_call_arguments(call)
    first_arg = flatten_text(args[0]) if args else None
    style = classify_logging_style(caller, level)
    verbosity = classify_verbosity(caller, level, first_arg)
    if style == "game_message":
        verbosity = None
    return style, verbosity


_console_contexts = None


def console_reply_context(class_path, unit_name):
    """True for units whose logger calls answer operator console commands (configs/extraction.yaml)."""
    global _console_contexts
    if _console_contexts is None:
        from src.common.config import load_config
        _console_contexts = {(c["class"], m) for c in load_config("extraction").get("console_reply_contexts", [])
                             for m in c["methods"]}
    return (class_path.split(".")[-1] if class_path else "", unit_name) in _console_contexts


def collect_logs(unit_element, imports_framework, static_names=None, console_reply=False):
    if static_names is None:
        unit_root = _nearest_unit(unit_element)
        static_names = static_log_names(get_imports(unit_root)) if unit_root is not None else {}
    logs = []
    formal_count = 0
    for stmt, call in get_statement_calls(unit_element):
        call_name = resolved_call_name(call, static_names)
        found = statement_style(call, call_name)
        if found is None:
            continue
        style, verbosity = found
        caller, level = split_call_name(call_name)
        if console_reply and style == "formal":
            style, verbosity = "console_reply", verbosity
        formal_index = None
        if style == "formal":
            formal_index = formal_count
            formal_count += 1
        line, _ = get_lines(stmt)
        logs.append(LogStatement(
            index=len(logs),
            formal_index=formal_index,
            element=stmt,
            call=call,
            call_name=call_name,
            caller=caller,
            level_token=level,
            call_text=get_call_text(call),
            verbosity=verbosity,
            logging_style=style,
            framework=infer_framework(caller, style, imports_framework),
            line=line,
        ))
    return logs


def body_hash(unit_element):
    return hashlib.sha1(normalized_text(unit_element).encode("utf-8")).hexdigest()


def count_code_lines(root):
    """(sloc, comment_lines): non-blank lines without comments, and lines covered by comments."""
    code = flatten_code(root)
    sloc = sum(1 for line in code.splitlines() if line.strip())
    comment_lines = 0
    for c in root.iter(SRC + "comment"):
        text = flatten_text(c)
        comment_lines += text.count("\n") + 1
    return sloc, comment_lines


def build_units(root, imports_framework, static_names=None):
    if static_names is None:
        static_names = static_log_names(get_imports(root))
    units = []
    seen = {}
    for el in extract_method_units(root):
        class_path = get_class_path(el)
        signature = get_unit_signature(el)
        key = (class_path, signature)
        # overloads that collapse to the same signature (e.g. erased generics) get a suffix
        if key in seen:
            seen[key] += 1
            signature = f"{signature}#{seen[key]}"
        else:
            seen[key] = 1
        start, end = get_lines(el)
        units.append(MethodUnit(
            element=el,
            ordinal=len(units),
            class_path=class_path,
            name=get_unit_name(el),
            signature=signature,
            kind="constructor" if el.tag == SRC + "constructor" else "method",
            start_line=start,
            end_line=end,
            body_hash=body_hash(el),
            logs=collect_logs(el, imports_framework, static_names,
                              console_reply_context(class_path, get_unit_name(el))),
        ))
    return units


def parse_java_source(source, path_hint=""):
    root = source_to_root(source, position=True)
    if root is None:
        return None
    imports = get_imports(root)
    fw = file_framework(imports)
    static_names = static_log_names(imports)
    sloc, comment_lines = count_code_lines(root)
    return ParsedFile(
        root=root,
        imports=imports,
        units=build_units(root, fw, static_names),
        file_framework=fw,
        sloc=sloc,
        comment_lines=comment_lines,
        static_log_names=static_names,
    )


def find_unit(parsed, ordinal, signature, class_path):
    """Locate a unit by ordinal, checking identity; fall back to (class_path, signature)."""
    if parsed is None:
        return None
    if ordinal is not None and 0 <= ordinal < len(parsed.units):
        u = parsed.units[ordinal]
        if u.signature == signature and u.class_path == class_path:
            return u
    for u in parsed.units:
        if u.signature == signature and u.class_path == class_path:
            return u
    return None
