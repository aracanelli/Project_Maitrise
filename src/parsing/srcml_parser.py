"""
srcML-based Java source parsing.

Adapted from the replication package of Zeng et al. (2019), logdetector/codetransform.py.

Differences from upstream:
- temp files instead of FIFO pipes (os.mkfifo), which Windows does not have
- no Peewee/PostgreSQL dependency
- extra helpers for class paths, line positions, imports and normalised text
- method units include constructors and methods of package-private classes, enums and
  interfaces (the upstream XPath only keeps classes with a specifier)
"""

import subprocess
import tempfile
import os
import shutil
from lxml import etree

NS = {"src": "http://www.srcML.org/srcML/src"}
SRC = "{http://www.srcML.org/srcML/src}"
POS = "{http://www.srcML.org/srcML/position}"

TYPE_TAGS = {SRC + "class", SRC + "enum", SRC + "interface", SRC + "annotation_defn", SRC + "record"}
UNIT_TAGS = {SRC + "function", SRC + "constructor"}

_SRCML_KNOWN_PATHS = [
    r"C:\Program Files\srcML\bin\srcml.exe",
    r"C:\Program Files (x86)\srcML\bin\srcml.exe",
]

_srcml_cmd = None


def _find_srcml():
    global _srcml_cmd
    if _srcml_cmd is not None:
        return _srcml_cmd

    found = shutil.which("srcml")
    if found:
        _srcml_cmd = found
        return _srcml_cmd

    for p in _SRCML_KNOWN_PATHS:
        if os.path.isfile(p):
            _srcml_cmd = p
            return _srcml_cmd

    raise RuntimeError(
        "srcml not found. Install from https://www.srcml.org/downloads.html"
    )


def java_file_to_xml(java_path, position=False):
    srcml = _find_srcml()
    cmd = [srcml, str(java_path)]
    if position:
        cmd.append("--position")
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def java_source_to_xml(source, position=True, timeout=60):
    """Run srcML on Java source through a temp file (srcML ignores piped stdin on Windows)."""
    if isinstance(source, str):
        source = source.encode("utf-8")
    srcml = _find_srcml()
    fd, tmp_path = tempfile.mkstemp(suffix=".java")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(source)
        cmd = [srcml, tmp_path]
        if position:
            cmd.append("--position")
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def parse_xml(xml_bytes):
    if not xml_bytes:
        return None
    parser = etree.XMLParser(huge_tree=True)
    try:
        return etree.fromstring(xml_bytes, parser=parser)
    except etree.XMLSyntaxError:
        return None


def source_to_root(source, position=True):
    return parse_xml(java_source_to_xml(source, position=position))


def extract_methods(xml_root):
    """Upstream XPath, kept for reference: functions inside classes with specifiers."""
    return xml_root.xpath(
        '//src:unit//src:class[src:specifier]/src:block/src:function',
        namespaces=NS
    )


def extract_method_units(xml_root):
    """Functions and constructors that are not nested inside another function/constructor.

    Methods of anonymous classes and lambdas declared inside a method body belong to
    the enclosing unit, so each statement is owned by exactly one unit.
    """
    return xml_root.xpath(
        '//*[(self::src:function or self::src:constructor)'
        ' and not(ancestor::src:function or ancestor::src:constructor)]',
        namespaces=NS
    )


def wrap_method(method_el):
    """Wrap a method element in a <root> tag for standalone XPath queries."""
    raw = etree.tostring(method_el, with_tail=False)
    return etree.fromstring(b'<root>' + raw + b'</root>')


def get_method_name(method_xml):
    els = method_xml.xpath('//src:function/src:name', namespaces=NS)
    if els and els[0].text:
        return els[0].text
    return ""


def get_method_params_str(method_xml):
    param_types = method_xml.xpath(
        '//src:function/src:parameter_list/src:parameter/src:decl/src:type/src:name',
        namespaces=NS
    )
    parts = []
    for p in param_types:
        t = p.text if p.text else flatten_text(p)
        parts.append(t)
    return "(" + ",".join(parts) + ")"


def get_method_signature(method_xml):
    return get_method_name(method_xml) + get_method_params_str(method_xml)


def get_unit_name(unit_el):
    name_el = unit_el.find(SRC + "name")
    if name_el is None:
        return ""
    return flatten_text(name_el).strip()


def get_unit_param_types(unit_el):
    params = unit_el.find(SRC + "parameter_list")
    if params is None:
        return []
    types = []
    for p in params.findall(SRC + "parameter"):
        type_name = p.find(SRC + "decl/" + SRC + "type/" + SRC + "name")
        if type_name is None:
            types.append("")
            continue
        text = type_name.text if type_name.text else flatten_text(type_name)
        types.append("".join(text.split()))
    return types


def get_unit_signature(unit_el):
    return get_unit_name(unit_el) + "(" + ",".join(get_unit_param_types(unit_el)) + ")"


def get_class_path(el):
    """Dotted path of enclosing named types, outermost first. Anonymous types give '$anon'."""
    names = []
    parent = el.getparent()
    while parent is not None:
        if parent.tag in TYPE_TAGS:
            name_el = parent.find(SRC + "name")
            if name_el is not None and flatten_text(name_el).strip():
                name = flatten_text(name_el).strip()
                names.append(name.split("<")[0].strip())
            else:
                names.append("$anon")
        parent = parent.getparent()
    return ".".join(reversed(names))


def get_lines(el):
    start = el.get(POS + "start")
    end = el.get(POS + "end")
    s = int(start.split(":")[0]) if start else None
    e = int(end.split(":")[0]) if end else None
    return s, e


def get_imports(xml_root):
    imports = []
    for imp in xml_root.iter(SRC + "import"):
        text = "".join(flatten_text(imp).split())
        if text.startswith("import"):
            text = text[len("import"):]
        imports.append(text.rstrip(";"))
    return imports


def get_call_expressions(method_xml):
    """Call elements that start an expression statement in a method body."""
    candidates = method_xml.xpath('//src:expr_stmt/src:expr/*[1]', namespaces=NS)
    calls = []
    for el in candidates:
        if el.tag == SRC + "call":
            calls.append(el)
    return calls


_CHAIN_HEADS = ("getlogger", "getlog", "logger", "log")


def _chained_logger_call(expr):
    """`Logger.getLogger(..).log(..)`: return the trailing call when the head call yields a logger."""
    if len(expr) != 3 or expr[0].tag != SRC + "call" or expr[2].tag != SRC + "call":
        return None
    if expr[1].tag != SRC + "operator" or (expr[1].text or "").strip() != ".":
        return None
    head = get_call_name(expr[0]).rsplit(".", 1)[-1].lower()
    if head not in _CHAIN_HEADS:
        return None
    return expr[2]


def get_statement_calls(unit_el):
    """(statement_element, call_element) pairs for statements whose expression is a call.

    Covers expression statements, expression-bodied lambdas and Java 14 arrow-switch rules
    (srcML 1.1 puts a rule body after a '->' operator inside the <case> expression), in
    document order. For a chained `getLogger(..).level(..)` the trailing call is returned.
    """
    pairs = []
    for el in unit_el.iter(SRC + "expr_stmt", SRC + "lambda", SRC + "operator"):
        if el.tag == SRC + "expr_stmt":
            # same rule as upstream '//expr_stmt/expr/*[1]' being a call
            expr = el.find(SRC + "expr")
            if expr is not None and len(expr) and expr[0].tag == SRC + "call":
                chained = _chained_logger_call(expr)
                pairs.append((el, chained if chained is not None else expr[0]))
        elif el.tag == SRC + "lambda":
            block = el.find(SRC + "block")
            if block is None or block.get("type") != "pseudo":
                continue
            content = block.find(SRC + "block_content")
            if content is None:
                continue
            expr = content.find(SRC + "expr")
            if expr is not None and len(expr) and expr[0].tag == SRC + "call":
                pairs.append((expr, expr[0]))
        else:
            if (el.text or "").strip() != "->":
                continue
            parent = el.getparent()
            if parent is None or parent.tag != SRC + "expr" or parent.getparent() is None                     or parent.getparent().tag != SRC + "case":
                continue
            nxt = el.getnext()
            if nxt is None:
                continue
            if nxt.tag == SRC + "call":
                pairs.append((nxt, nxt))
            elif nxt.tag == SRC + "block":
                for child in nxt:
                    if child.tag == SRC + "expr" and len(child) and child[0].tag == SRC + "call":
                        pairs.append((child, child[0]))
    return pairs


def get_call_name(call_xml):
    """Full dotted call name, e.g. 'logger.info' or 'Log.d'."""
    parts = call_xml.xpath('src:name//*', namespaces=NS)
    if not parts:
        parts = call_xml.xpath('src:name', namespaces=NS)
    name = ""
    for item in parts:
        if item.text is not None:
            name += item.text
    return name


def call_has_arguments(call_xml):
    args = call_xml.xpath('./src:argument_list/src:argument', namespaces=NS)
    return len(args) > 0


def get_call_arguments(call_xml):
    return call_xml.xpath('./src:argument_list/src:argument', namespaces=NS)


def get_call_text(call_xml):
    return flatten_text(call_xml)


def flatten_text(el):
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        parts.append(flatten_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def flatten_code(el):
    """Like flatten_text but drops comments."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        if child.tag != SRC + "comment":
            parts.append(flatten_code(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def normalized_text(el):
    """Code text without comments and whitespace, used for change detection."""
    return "".join(flatten_code(el).split())


def get_method_block_content(method_xml):
    """Return the block_content element of a method (the body inside braces).
    Adapted from upstream codetransform.get_method_block_content."""
    blocks = method_xml.xpath('//src:function/src:block/src:block_content', namespaces=NS)
    if blocks:
        return blocks[0]
    blocks = method_xml.xpath('//src:function/src:block', namespaces=NS)
    if blocks:
        return blocks[0]
    return None


def get_unit_body(unit_el):
    block = unit_el.find(SRC + "block")
    if block is None:
        return None
    content = block.find(SRC + "block_content")
    return content if content is not None else block


def compare_method_signature(method_xml_a, method_xml_b):
    """Compare two methods by name and parameter types.
    Adapted from upstream codetransform.compare_method_signature."""
    name_a = get_method_name(method_xml_a)
    name_b = get_method_name(method_xml_b)
    params_a = get_method_params_str(method_xml_a)
    params_b = get_method_params_str(method_xml_b)
    return name_a == name_b, params_a == params_b


def get_enclosing_class_name(method_el):
    """Name of the innermost named type around a method element, "" if none."""
    parent = method_el.getparent()
    while parent is not None:
        if parent.tag in TYPE_TAGS:
            name_el = parent.find(SRC + "name")
            if name_el is not None and name_el.text:
                return name_el.text
        parent = parent.getparent()
    return ""


def tag_name(el):
    t = el.tag
    if isinstance(t, str) and t.startswith("{"):
        return t.split("}", 1)[1]
    return t
