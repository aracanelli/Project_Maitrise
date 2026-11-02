"""
Rebuild the task view of an instance from the Git objects recorded at mining time.

The view is chosen by the instance's `view` field, never by the task name:
- "pre": the pre-state method (parent blob, class_path_pre, signature_pre, pre_ordinal),
  anchored on the target log statement when the instance has anchor_pre_idx
  (REMOVE_LOG / CHANGE_LEVEL) and not anchored otherwise (ADD_LOG, multiclass)
- "post_masked": the post-state method with every statement added in that commit masked
  out (the add_log_post sensitivity task)
- file-level context always comes from the pre-state file (parent commit)

Features and graphs are both computed from the view returned here, so the two
representations always describe the same code.
"""

import re
from collections import Counter, OrderedDict
from dataclasses import dataclass

import git
from lxml import etree

from src.common.config import repo_path
from src.parsing.srcml_parser import SRC, flatten_text, get_unit_body
from src.parsing.method_units import (
    parse_java_source, find_unit, collect_logs, body_hash, console_reply_context
)

_repos = {}
_blob_cache = OrderedDict()
_parse_cache = OrderedDict()
_BLOB_CACHE_SIZE = 256
_PARSE_CACHE_SIZE = 64


def _repo(repo_name):
    if repo_name not in _repos:
        _repos[repo_name] = git.Repo(str(repo_path(repo_name)))
    return _repos[repo_name]


def read_blob(repo_name, blob_sha):
    key = (repo_name, blob_sha)
    if key in _blob_cache:
        _blob_cache.move_to_end(key)
        return _blob_cache[key]
    data = _repo(repo_name).odb.stream(bytes.fromhex(blob_sha)).read()
    _blob_cache[key] = data
    if len(_blob_cache) > _BLOB_CACHE_SIZE:
        _blob_cache.popitem(last=False)
    return data


def parse_blob(repo_name, blob_sha):
    """Parse a blob; cached because many instances share the same file version.

    Callers that mutate the tree (masking) must parse their own copy.
    """
    key = (repo_name, blob_sha)
    if key in _parse_cache:
        _parse_cache.move_to_end(key)
        return _parse_cache[key]
    parsed = parse_java_source(read_blob(repo_name, blob_sha))
    _parse_cache[key] = parsed
    if len(_parse_cache) > _PARSE_CACHE_SIZE:
        _parse_cache.popitem(last=False)
    return parsed


def _remove_keep_tail(el):
    parent = el.getparent()
    if parent is None:
        return
    tail = el.tail or ""
    prev = el.getprevious()
    if prev is not None:
        prev.tail = (prev.tail or "") + tail
    else:
        parent.text = (parent.text or "") + tail
    parent.remove(el)


def _block_is_empty(block):
    if block is None:
        return True
    content = block.find(SRC + "block_content")
    target = content if content is not None else block
    for child in target:
        if child.tag != SRC + "comment":
            return False
    return True


_LEVEL_CHECK = re.compile(r'\bis(Trace|Debug|Info|Warn|Error)Enabled\s*\(|\bisLoggable\s*\(')
LOOP_TAGS = (SRC + "for", SRC + "while", SRC + "do")


def _attached(el, unit_element):
    while el is not None:
        if el is unit_element:
            return True
        el = el.getparent()
    return False


def _depth(el):
    d = 0
    while el is not None:
        d += 1
        el = el.getparent()
    return d


def _enclosing_statement(el, unit_element):
    stmt_tags = (SRC + "expr_stmt", SRC + "decl_stmt", SRC + "return")
    while el is not None and el is not unit_element:
        if el.tag in stmt_tags:
            return el
        el = el.getparent()
    return None


def _negate_condition(if_el):
    expr = if_el.find(SRC + "condition/" + SRC + "expr")
    if expr is None:
        return
    op = etree.Element(SRC + "operator")
    op.text = "!"
    op.tail = expr.text
    expr.text = ""
    expr.insert(0, op)


def _clean_if(if_stmt, touched):
    """Rewrite an if statement whose branches were emptied by masking. True if changed."""
    branches = [c for c in if_stmt if c.tag in (SRC + "if", SRC + "else")]
    if not branches:
        return False
    first = branches[0]
    cond = first.find(SRC + "condition")
    is_guard = cond is not None and _LEVEL_CHECK.search(flatten_text(cond)) is not None
    for br in branches[1:]:
        if br in touched and _block_is_empty(br.find(SRC + "block")):
            _remove_keep_tail(br)
            return True
    if first not in touched:
        return False
    if not _block_is_empty(first.find(SRC + "block")):
        if is_guard and len(branches) == 1 and not collect_logs(first, "none", {}):
            # logger level-check guard left holding only log-preparation code
            _remove_keep_tail(if_stmt)
            return True
        return False
    if len(branches) == 1:
        _remove_keep_tail(if_stmt)
        return True
    nxt = branches[1]
    if nxt.tag == SRC + "if":
        # if (a) {} else if (b) {B} ...  ->  if (b) {B} ...
        nxt.attrib.pop("type", None)
        nxt.text = "if "
        _remove_keep_tail(first)
        return True
    # if (c) {} else {B}  ->  if (!c) {B}
    else_block = nxt.find(SRC + "block")
    empty_block = first.find(SRC + "block")
    _negate_condition(first)
    if empty_block is not None and else_block is not None:
        nxt.remove(else_block)
        else_block.tail = empty_block.tail
        first.replace(empty_block, else_block)
    _remove_keep_tail(nxt)
    return True


def _unwrap(el):
    """Replace `el` by the statements of its block; they keep their own text and tails."""
    block = el.find(SRC + "block")
    content = block.find(SRC + "block_content") if block is not None else None
    parent = el.getparent()
    i = parent.index(el)
    for kid in list(content) if content is not None else []:
        parent.insert(i, kid)
        i += 1
    _remove_keep_tail(el)


def _clean_try(try_el, touched):
    """Remove or unwrap a try statement that masking left without purpose. True if changed."""
    block = try_el.find(SRC + "block")
    if block is not None and block in touched and _block_is_empty(block):
        # try { log(..); } catch (..) { .. }: the whole statement existed for the log
        _remove_keep_tail(try_el)
        return True
    handlers = [c for c in try_el if c.tag in (SRC + "catch", SRC + "finally")]
    if not handlers and try_el.find(SRC + "init") is None:
        # its only catch or finally was emptied and removed: try { a(); }  ->  a();
        _unwrap(try_el)
        return True
    return False


def _is_anonymous_class(el):
    return el.tag == SRC + "class" and el.find(SRC + "name") is None


def _anonymous_class_emptied(cls, touched):
    """An anonymous class whose single member is a method whose body masking emptied."""
    body = cls.find(SRC + "block")
    if body is None:
        return False
    content = body.find(SRC + "block_content")
    members = [c for c in (content if content is not None else body) if c.tag != SRC + "comment"]
    if len(members) != 1 or members[0].tag != SRC + "function":
        return False
    method_body = members[0].find(SRC + "block")
    return method_body is not None and method_body in touched and _block_is_empty(method_body)


CASE_TAGS = (SRC + "case", SRC + "default")
# structures removed for an emptied body whose header (condition, loop header, selector)
# only existed for it
HEADER_TAGS = (SRC + "if_stmt", SRC + "switch", SRC + "synchronized") + LOOP_TAGS + CASE_TAGS


def _switch_content(el):
    """The block_content of the switch that `el` is a direct statement of, else None."""
    content = el.getparent()
    if content is None or content.tag != SRC + "block_content":
        return None
    block = content.getparent()
    if block is None or block.getparent() is None or block.getparent().tag != SRC + "switch":
        return None
    return content


def _is_colon_label(el):
    # arrow rules (case X -> ..) are parsed differently by srcML and are left alone
    return el.tag in CASE_TAGS and flatten_text(el).rstrip().endswith(":")


def _case_label(el):
    """The colon-style case/default label whose statements include `el`, else None."""
    if _switch_content(el) is None:
        return None
    prev = el.getprevious()
    while prev is not None and prev.tag not in CASE_TAGS:
        prev = prev.getprevious()
    if prev is None or not _is_colon_label(prev):
        return None
    return prev


def _clean_case(label):
    """Drop a case group that masking reduced to nothing or a lone `break`. True if changed.

    Only when this does not change which code runs: `case 1: log.info(..); break;` goes if
    the switch has no default (else value 1 would now run the default), a default goes
    whatever the other labels. A group left empty that falls through into the next one
    stays (`case 1: case 2: a();`); labels written together (`case 0: case 1:`) go together.
    """
    content = _switch_content(label)
    if content is None or not _is_colon_label(label):
        return False
    labels = [label]
    prev = label.getprevious()
    while prev is not None and (prev.tag in CASE_TAGS or prev.tag == SRC + "comment"):
        if prev.tag in CASE_TAGS:
            labels.insert(0, prev)
        prev = prev.getprevious()
    rest = []
    nxt = label.getnext()
    while nxt is not None and nxt.tag not in CASE_TAGS:
        if nxt.tag != SRC + "comment":
            rest.append(nxt)
        nxt = nxt.getnext()
    lone_break = len(rest) == 1 and rest[0].tag == SRC + "break" and rest[0].find(SRC + "name") is None
    if not lone_break and (rest or nxt is not None):
        return False
    has_default = any(c.tag == SRC + "default" for c in content)
    if has_default and not any(l.tag == SRC + "default" for l in labels):
        return False
    for el in labels + rest:
        _remove_keep_tail(el)
    return True


def _structure_emptied(el, unit_element, touched):
    """Remove `el` (an ancestor of a masked statement) if masking left it without purpose."""
    if el.tag == SRC + "if_stmt":
        return _clean_if(el, touched)
    if el.tag == SRC + "try":
        return _clean_try(el, touched)
    if el.tag in CASE_TAGS:
        return _clean_case(el)
    if el.tag in LOOP_TAGS or el.tag in (SRC + "synchronized", SRC + "finally", SRC + "catch", SRC + "switch"):
        if _block_is_empty(el.find(SRC + "block")):
            _remove_keep_tail(el)
            return True
    elif el.tag == SRC + "lambda" or _is_anonymous_class(el):
        if el.tag == SRC + "lambda":
            emptied = _block_is_empty(el.find(SRC + "block"))
        else:
            emptied = _anonymous_class_emptied(el, touched)
        if emptied:
            stmt = _enclosing_statement(el, unit_element)
            if stmt is not None:
                _remove_keep_tail(stmt)
                return True
    return False


def _name_counts(unit_element):
    return Counter(n.text for n in unit_element.iter(SRC + "name") if not len(n) and n.text)


def _referenced_names(unit_element):
    names = set()
    for n in unit_element.iter(SRC + "name"):
        if len(n) or not n.text:
            continue
        parent = n.getparent()
        if parent is not None and parent.tag == SRC + "decl":
            continue          # the declared name itself
        names.add(n.text)
    return names


def _remove_dead_locals(unit_element, candidates):
    """Drop local declarations whose variables were only used by masked statements."""
    body = get_unit_body(unit_element)
    if body is None:
        return 0
    removed = 0
    changed = True
    while changed:
        changed = False
        refs = _referenced_names(unit_element)
        for decl_stmt in list(body.iter(SRC + "decl_stmt")):
            declared = [d.find(SRC + "name") for d in decl_stmt.findall(SRC + "decl")]
            declared = [d.text for d in declared if d is not None and d.text]
            if not declared or not all(v in candidates and v not in refs for v in declared):
                continue
            for n in decl_stmt.iter(SRC + "name"):
                if not len(n) and n.text:
                    candidates.add(n.text)
            _remove_keep_tail(decl_stmt)
            removed += 1
            changed = True
            break
    return removed


def mask_statements(unit_element, elements):
    """Remove the given statements, then whatever existed only for them.

    Removed afterwards: if guards and branches left empty (`if (c) {} else {B}` becomes
    `if (!c) {B}`), logger level-check guards left without a log, loops, synchronized,
    switch, finally and catch blocks left empty, statements whose lambda body was the masked
    log, statements whose anonymous class had a single method and masking emptied its body,
    colon-style case groups left with nothing or a lone `break` (when the switch runs the
    same code without them, see _clean_case), and local variables only used by the masked
    statements or by the condition, header or selector of a removed if, loop or switch.
    A try whose own block was emptied is removed with its catch and finally clauses; a try
    left with no catch, no finally and no resources is replaced by the statements of its
    block (`try { a(); } catch (E e) { log(..); }` becomes `a();`). Only the method body
    itself stays even when emptied.

    Only ancestors of masked statements change (plus the clauses of a removed try and the
    labels of a removed case group), so an empty catch block that was already there and
    is not around a masked statement stays. A catch that the commit filled with the log
    (empty before, or whose old content, such as a throw, a printStackTrace or another
    log, the commit replaced by the log) is emptied by masking and goes with its try, so in a few
    positives the masked view has no try/catch where the pre-state method had one.
    """
    touched = []
    candidates = set()
    for el in elements:
        for n in el.iter(SRC + "name"):
            if not len(n) and n.text:
                candidates.add(n.text)
        node = el
        while node is not None and node is not unit_element:
            label = _case_label(node)
            if label is not None and label not in touched:
                touched.append(label)
            node = node.getparent()
            if node is not None and node is not unit_element and node not in touched:
                touched.append(node)

    n = 0
    for el in elements:
        if el.getparent() is not None:
            _remove_keep_tail(el)
            n += 1

    touched_set = set(touched)
    changed = True
    while changed:
        changed = False
        n += _remove_dead_locals(unit_element, candidates)
        before = _name_counts(unit_element)
        for el in sorted(touched, key=_depth, reverse=True):
            if not _attached(el, unit_element):
                continue
            tag = el.tag
            if _structure_emptied(el, unit_element, touched_set):
                if tag in HEADER_TAGS:
                    # a removed guard condition, loop header or switch selector may leave a dead
                    # local; not for the lambda / anonymous class / try rules, which can take
                    # other code with them
                    after = _name_counts(unit_element)
                    candidates.update(k for k, v in before.items() if after[k] < v)
                n += 1
                changed = True
                break
    return n


@dataclass
class InstanceView:
    instance: dict
    unit: object
    file_pre: object
    anchor: object
    masked: int


def load_view(instance):
    repo = instance["repo"]
    try:
        file_pre = parse_blob(repo, instance["pre_blob"])
    except Exception:
        return None
    if file_pre is None:
        return None

    if instance.get("view") == "post_masked":
        # fresh parse: masking mutates the tree
        try:
            post = parse_java_source(read_blob(repo, instance["post_blob"]))
        except Exception:
            return None
        unit = find_unit(post, instance.get("post_ordinal"), instance["signature_post"], instance["class_path"])
        if unit is None:
            return None
        wanted = set(instance.get("mask_post_idx") or [])
        wanted_all = instance.get("mask_post_all_idx")
        if wanted_all is not None:
            # every statement added in the commit, any logging style
            wanted_all = set(wanted_all)
            targets = [log.element for log in unit.logs if log.index in wanted_all]
            formal_hit = {log.formal_index for log in unit.logs
                          if log.index in wanted_all and log.formal_index is not None}
            if len(targets) != len(wanted_all) or not wanted <= formal_hit:
                return None
        else:
            targets = [log.element for log in unit.formal_logs if log.formal_index in wanted]
            if len(targets) != len(wanted):
                return None
        masked = mask_statements(unit.element, targets)
        unit.logs = collect_logs(unit.element, post.file_framework, post.static_log_names,
                                 console_reply_context(unit.class_path, unit.name))
        unit.body_hash = body_hash(unit.element)
        return InstanceView(instance, unit, file_pre, None, masked)

    class_pre = instance.get("class_path_pre") or instance["class_path"]
    unit = find_unit(file_pre, instance.get("pre_ordinal"), instance["signature_pre"], class_pre)
    if unit is None:
        return None
    anchor = None
    idx = instance.get("anchor_pre_idx")
    if idx is not None:
        for log in unit.formal_logs:
            if log.formal_index == idx:
                anchor = log
                break
        if anchor is None:
            return None
    return InstanceView(instance, unit, file_pre, anchor, 0)
