"""
Method-centred typed graphs for the graph models.

A graph is built from the same srcML element as the tabular features: the task view of
src.dataset.views.load_view (pre-state method for ADD_LOG, REMOVE_LOG and CHANGE_LEVEL,
masked post-state method for the add_log_post sensitivity task). Nodes are the method, its
parameters, blocks, statements, control-structure conditions, invocations and variables,
plus one virtual anchor node. Every edge type has its own reverse type.

The edge set follows the program-graph idea of Allamanis et al. (2018), "Learning to
Represent Programs with Graphs": a syntax backbone plus statement order, control, data
(use / declaration) and invocation relations. It is implemented here on top of the
srcML helpers of src/parsing.
"""

import math
from collections import Counter, deque

import numpy as np

from src.detection.verbosity import LEVEL_ORD
from src.features.lexical import subtokens, bucket
from src.parsing.srcml_parser import (
    SRC, get_call_name, get_call_arguments, get_unit_name, flatten_code
)

NODE_TYPES = [
    "METHOD", "PARAM", "BLOCK", "EXPR_STMT", "DECL_STMT", "RETURN", "THROW", "IF", "ELSE",
    "FOR", "WHILE", "DO", "SWITCH", "CASE", "TRY", "CATCH", "FINALLY", "BREAK", "CONTINUE",
    "SYNCHRONIZED", "LABEL", "EMPTY", "LAMBDA", "ANON_CLASS", "LOCAL_CLASS", "OTHER_STMT",
    "LOG_STMT", "PRINT_STMT", "CONDITION", "CALL", "VARIABLE", "ANCHOR",
]
NODE_ID = {t: i for i, t in enumerate(NODE_TYPES)}

# forward type at an even id, its reverse right after it
EDGE_TYPES = [
    "AST_CHILD", "AST_PARENT", "NEXT", "PREV", "CONTROL", "CONTROLLED_BY",
    "USES", "USED_BY", "DECLARES", "DECLARED_BY", "CALLS", "CALLED_BY", "ANCHOR", "ANCHORED_BY",
]
EDGE_ID = {t: i for i, t in enumerate(EDGE_TYPES)}
REVERSE = {EDGE_TYPES[i]: EDGE_TYPES[i + 1] for i in range(0, len(EDGE_TYPES), 2)}

NUMERIC_FEATURES = [
    "depth_norm", "log_n_tokens", "has_string_literal", "n_args_norm",
    "in_loop", "in_catch", "level_ord_norm", "is_field",
]
MAX_TOKENS = 16

NAME = SRC + "name"

STATEMENT_TAGS = {
    "expr_stmt": "EXPR_STMT", "decl_stmt": "DECL_STMT", "return": "RETURN", "throw": "THROW",
    "if_stmt": "IF", "for": "FOR", "foreach": "FOR", "while": "WHILE", "do": "DO",
    "switch": "SWITCH", "case": "CASE", "default": "CASE", "try": "TRY", "break": "BREAK",
    "continue": "CONTINUE", "synchronized": "SYNCHRONIZED", "label": "LABEL", "empty_stmt": "EMPTY",
}
TYPE_DECL_TAGS = {"class", "enum", "interface", "record", "annotation_defn"}
# a <block> is a code block only under these; elsewhere it is an array initializer or a class body
BLOCK_PARENTS = {"function", "constructor", "if", "then", "else", "for", "foreach", "while", "do",
                 "try", "catch", "finally", "synchronized", "switch", "lambda", "block_content"}
CONDITION_PARENTS = {"if", "while", "do", "switch", "control"}
SKIP_TAGS = {"comment", "type", "specifier", "annotation", "super", "throws"}

LOOP_TYPES = {"FOR", "WHILE", "DO"}
CONTROL_TYPES = {"IF", "ELSE", "FOR", "WHILE", "DO", "SWITCH", "TRY", "CATCH", "FINALLY", "SYNCHRONIZED"}
# nodes that own the names and calls of the expressions written directly in them
NOT_OWNERS = {"METHOD", "PARAM", "BLOCK", "LAMBDA", "ANON_CLASS", "LOCAL_CLASS", "CALL", "VARIABLE", "ANCHOR"}

# 'var' is only reserved as a type name, so it stays a valid variable name (Mindustry uses it)
KEYWORDS = {"this", "super", "null", "true", "false", "class", "new", "yield", "instanceof",
            "int", "long", "short", "byte", "char", "boolean", "float", "double", "void"}


def _local(tag):
    if not isinstance(tag, str):
        return ""
    return tag[len(SRC):] if tag.startswith(SRC) else tag


def _simple(name_el):
    if name_el.text and name_el.text.strip():
        return name_el.text.strip()
    for c in name_el:
        if c.tag == NAME:
            return _simple(c)
    return ""


def _segments(name_el):
    """'a.b.c' -> ['a', 'b', 'c'] for a srcML <name>, simple or compound."""
    kids = [c for c in name_el if c.tag == NAME]
    if not kids:
        return [name_el.text.strip()] if name_el.text and name_el.text.strip() else []
    return [_simple(c) for c in kids]


def _index_parts(name_el):
    """<index> elements of a compound name (array accesses), not those nested in other indexes."""
    out = []
    for c in name_el:
        if c.tag == SRC + "index":
            out.append(c)
        elif c.tag == NAME:
            out.extend(_index_parts(c))
    return out


def _looks_like_type(s):
    return bool(s) and s[0].isupper() and (len(s) == 1 or any(ch.islower() for ch in s))


def _is_package_chain(segs):
    # java.util.Arrays, com.jme3.math.Vector3f: lowercase segments followed by a type name
    for j in range(1, len(segs)):
        if _looks_like_type(segs[j]):
            return all(p and p == p.lower() for p in segs[:j])
        if any(ch.isupper() for ch in segs[j]):
            return False
    return False


def root_variable(segs, declared):
    """Variable referenced by an access chain, or None (type names, packages, keywords).

    Only the root of a chain is a variable: in 'player.pos.x' it is 'player'; 'this.count'
    gives 'count'. Names not declared in the unit are taken as fields or constants.
    """
    if not segs:
        return None
    first = segs[0]
    if first in ("this", "super"):
        if len(segs) >= 2 and segs[1] not in KEYWORDS and not _looks_like_type(segs[1]):
            return segs[1] or None
        return None
    if not first or first in KEYWORDS or not (first[0].isalpha() or first[0] in "_$"):
        return None
    if first in declared:
        return first
    if _looks_like_type(first) or _is_package_chain(segs):
        return None
    return first


def _type_text(decl_el):
    names = []
    for t in decl_el.findall(SRC + "type"):
        for n in t.iter(NAME):
            if n.text and n.text.strip():
                names.append(n.text.strip())
    return " ".join(names)


def declared_names(unit_el):
    """Every simple name declared anywhere in the unit (locals, parameters, catch, lambda, for, resources)."""
    names = set()
    for d in unit_el.iter(SRC + "decl"):
        n = d.find(NAME)
        if n is not None and _simple(n):
            names.add(_simple(n))
    # pattern bindings: 'o instanceof Foo f'
    for op in unit_el.iter(SRC + "operator"):
        if (op.text or "").strip() == "instanceof":
            t = op.getnext()
            b = t.getnext() if t is not None else None
            if t is not None and b is not None and t.tag == NAME and b.tag == NAME and _simple(b):
                names.add(_simple(b))
    return names


def _clip_tokens(tokens):
    out = []
    for t in tokens:
        if t not in out:
            out.append(t)
        if len(out) == MAX_TOKENS:
            break
    return out


def _log_tokens(log, message_words=False):
    toks = subtokens(log.caller) + subtokens(log.level_token or "")
    if message_words:
        for lit in log.call.iter(SRC + "literal"):
            if lit.get("type") == "string":
                toks.extend(subtokens(lit.text or ""))
    return toks


class _Builder:
    def __init__(self, unit, message_words=False):
        self.unit_el = unit.element
        self.message_words = message_words
        self.logs = {log.element: log for log in unit.logs}
        self.skip_calls = {log.call for log in unit.logs}
        self.declared = declared_names(unit.element)
        self.nodes = []        # dicts: type, el, parent, depth, tokens, has_str, n_args, level, in_loop, in_catch, children
        self.edges = []        # forward edges (src, dst, type)
        self.var_info = {}     # name -> declared type text (first declaration wins)
        self.var_order = []
        self.var_edges = []    # (node, var name, edge type)
        self._var_seen = set()
        self.last_decl_type = ""

    def add_node(self, ntype, el, parent, tokens=()):
        idx = len(self.nodes)
        node = {"type": ntype, "el": el, "parent": parent, "depth": 0, "tokens": list(tokens),
                "has_str": 0, "n_args": 0, "level": 0, "in_loop": 0, "in_catch": 0, "children": []}
        if parent is not None:
            p = self.nodes[parent]
            node["depth"] = p["depth"] + 1
            node["in_loop"] = int(p["in_loop"] or p["type"] in LOOP_TYPES)
            node["in_catch"] = int(p["in_catch"] or p["type"] == "CATCH")
            p["children"].append(idx)
            self.edges.append((parent, idx, "AST_CHILD"))
        self.nodes.append(node)
        return idx

    def var_ref(self, node, name, etype, type_text=None):
        if name not in self.var_info:
            self.var_info[name] = type_text or ""
            self.var_order.append(name)
        elif type_text and not self.var_info[name]:
            self.var_info[name] = type_text
        key = (node, name, etype)
        if key not in self._var_seen:
            self._var_seen.add(key)
            self.var_edges.append(key)

    def node_kind(self, el, tag):
        parent = el.getparent()
        ptag = _local(parent.tag) if parent is not None else ""
        log = self.logs.get(el)
        if log is not None:
            # any detected logging statement: expr_stmt, lambda body, arrow-switch rule
            return "LOG_STMT" if log.logging_style == "formal" else "PRINT_STMT"
        if tag == "expr_stmt" or (tag == "expr" and ptag == "block_content"):
            log = self.logs.get(el)
            if log is not None:
                return "LOG_STMT" if log.logging_style == "formal" else "PRINT_STMT"
            return "EXPR_STMT"
        if tag in STATEMENT_TAGS:
            return STATEMENT_TAGS[tag]
        if tag in TYPE_DECL_TAGS:
            return "LOCAL_CLASS" if el.find(NAME) is not None else "ANON_CLASS"
        # catch/finally normally sit in a <try>, but srcML parse errors can leave them in a block
        if tag == "catch":
            return "CATCH"
        if tag == "finally":
            return "FINALLY"
        if tag == "lambda":
            return "LAMBDA"
        if ptag == "block_content":
            if tag == "block":
                return "BLOCK"
            if tag == "if":
                return "IF"
            if tag in ("comment", "operator"):
                return None     # stray punctuation left by a srcML parse error
            return "OTHER_STMT"
        if tag == "block":
            return "BLOCK" if ptag in BLOCK_PARENTS else None
        if tag == "if":
            # the first <if> of an if_stmt is folded into the IF node of the statement
            return "IF" if ptag != "if_stmt" or el.get("type") == "elseif" else None
        if tag == "else":
            return "ELSE" if ptag in ("if_stmt", "if") else None
        if tag == "condition":
            # 'for (;;)' has an empty condition: no node
            return "CONDITION" if ptag in CONDITION_PARENTS and len(el) else None
        if tag == "parameter" and parent is not None and parent.getparent() is self.unit_el:
            return "PARAM"
        return None

    def mark_string(self, parent, owner):
        n = parent
        while n is not None and self.nodes[n]["type"] == "CALL":
            self.nodes[n]["has_str"] = 1
            n = self.nodes[n]["parent"]
        if owner is not None:
            self.nodes[owner]["has_str"] = 1

    def handle_name(self, el, parent, owner, stack):
        for idx_el in reversed(_index_parts(el)):
            stack.append((idx_el, parent, owner))
        if owner is None:
            return
        prev = el.getprevious()
        if prev is not None and prev.tag == SRC + "operator":
            op = (prev.text or "").strip()
            if op in (".", "::", "new", "instanceof"):
                return      # member / method reference / created or tested type
        if prev is not None and prev.tag == NAME:
            before = prev.getprevious()
            if before is not None and before.tag == SRC + "operator" and (before.text or "").strip() == "instanceof":
                name = _simple(el)
                if name:
                    self.var_ref(owner, name, "DECLARES", _simple(prev))
                return
        var = root_variable(_segments(el), self.declared)
        if var:
            self.var_ref(owner, var, "USES")

    def handle_callee(self, call_el, owner, parent, stack):
        name_el = call_el.find(NAME)
        if name_el is None:
            return
        for idx_el in reversed(_index_parts(name_el)):
            stack.append((idx_el, parent, owner))
        if owner is None:
            return
        segs = _segments(name_el)
        # 'new java.util.ArrayList<>()': the last segment is the type, so the qualifier is a package
        prev = call_el.getprevious()
        if (prev is not None and prev.tag == SRC + "operator" and (prev.text or "").strip() == "new"
                and segs and segs[0] not in self.declared and _is_package_chain(segs)):
            return
        var = root_variable(segs[:-1], self.declared)
        if var:
            self.var_ref(owner, var, "USES")

    def handle_decl(self, el, parent, owner, stack):
        declarer = parent
        if self.nodes[parent]["type"] == "CALL" and owner is not None:
            declarer = owner
        type_el = el.find(SRC + "type")
        if type_el is not None and type_el.get("ref") == "prev":
            type_text = self.last_decl_type
        else:
            type_text = _type_text(el)
        self.last_decl_type = type_text
        name_el = el.find(NAME)
        rest = []
        for c in el:
            if c.tag == SRC + "type" or c is name_el:
                continue
            rest.append(c)
        if name_el is not None:
            rest = _index_parts(name_el) + rest
            name = _simple(name_el)
            if name:
                self.var_ref(declarer, name, "DECLARES", type_text)
        for c in reversed(rest):
            stack.append((c, parent, owner))

    def walk(self):
        root = self.add_node("METHOD", self.unit_el, None, subtokens(get_unit_name(self.unit_el)))
        stack = [(c, root, None) for c in reversed(list(self.unit_el))]
        while stack:
            el, parent, owner = stack.pop()
            tag = _local(el.tag)
            if not tag or tag in SKIP_TAGS:
                continue
            if tag == "argument_list" and el.get("type") == "generic":
                continue
            if tag == "name":
                self.handle_name(el, parent, owner, stack)
                continue
            if tag == "literal":
                if el.get("type") == "string":
                    self.mark_string(parent, owner)
                continue
            if tag == "decl":
                self.handle_decl(el, parent, owner, stack)
                continue
            if tag == "call" and el not in self.logs:
                node = parent
                if el not in self.skip_calls:
                    node = self.add_node("CALL", el, parent, subtokens(get_call_name(el)))
                    self.nodes[node]["n_args"] = len(get_call_arguments(el))
                    if owner is not None:
                        self.edges.append((owner, node, "CALLS"))
                self.handle_callee(el, owner, node, stack)
                rest = [c for c in el if c.tag != NAME]
                for c in reversed(rest):
                    stack.append((c, node, owner))
                continue

            kind = self.node_kind(el, tag)
            if kind is None:
                for c in reversed(list(el)):
                    stack.append((c, parent, owner))
                continue

            node = self.add_node(kind, el, parent)
            n = self.nodes[node]
            if kind in ("LOG_STMT", "PRINT_STMT"):
                log = self.logs[el]
                n["tokens"] = _log_tokens(log, self.message_words)
                n["n_args"] = len(get_call_arguments(log.call))
                if kind == "LOG_STMT":
                    n["level"] = LEVEL_ORD.get(log.verbosity, 0)
            elif kind == "CATCH":
                decl = el.find(SRC + "parameter_list/" + SRC + "parameter/" + SRC + "decl")
                if decl is not None:
                    n["tokens"] = subtokens(_type_text(decl))

            if kind in ("LABEL", "BREAK", "CONTINUE"):
                continue            # only label names inside
            new_owner = None if kind in NOT_OWNERS else node
            for c in reversed(list(el)):
                if kind == "ANON_CLASS" and c.tag == SRC + "argument_list":
                    stack.append((c, node, owner))    # constructor arguments belong to the statement
                else:
                    stack.append((c, node, new_owner))

    def finish(self, anchor):
        n_struct = len(self.nodes)
        var_index = {}
        for name in self.var_order:
            idx = self.add_node("VARIABLE", None, None, subtokens(name) + subtokens(self.var_info[name]))
            self.nodes[idx]["name"] = name
            self.nodes[idx]["is_field"] = int(name not in self.declared)
            var_index[name] = idx
        for node, name, etype in self.var_edges:
            self.edges.append((node, var_index[name], etype))

        for i in range(n_struct):
            node = self.nodes[i]
            if node["type"] != "BLOCK":
                continue
            kids = node["children"]
            for a, b in zip(kids, kids[1:]):
                self.edges.append((a, b, "NEXT"))
            ctrl = node["parent"]
            if ctrl is not None and self.nodes[ctrl]["type"] in CONTROL_TYPES:
                for k in kids:
                    self.edges.append((ctrl, k, "CONTROL"))

        target = 0
        if anchor is not None:
            target = None
            for i in range(n_struct):
                if self.nodes[i]["el"] is anchor.element:
                    target = i
                    break
            if target is None or self.nodes[target]["type"] != "LOG_STMT":
                raise ValueError("anchor statement is not a LOG_STMT node of the graph")
        anchor_idx = self.add_node("ANCHOR", None, None)
        self.edges.append((anchor_idx, target, "ANCHOR"))
        return anchor_idx, target

    def features(self, i):
        node = self.nodes[i]
        t = node["type"]
        if t == "VARIABLE":
            n_sub = len(subtokens(node["name"]))
        elif node["el"] is not None:
            n_sub = len(subtokens(flatten_code(node["el"])))
        else:
            n_sub = 0
        return [
            min(node["depth"] / 20.0, 1.0),
            math.log1p(n_sub) / 5.0,
            float(node["has_str"]),
            min(node["n_args"] / 5.0, 1.0) if t in ("CALL", "LOG_STMT", "PRINT_STMT") else 0.0,
            float(node["in_loop"]),
            float(node["in_catch"]),
            node["level"] / 5.0 if t == "LOG_STMT" else 0.0,
            float(node.get("is_field", 0)),
        ]


def build_graph(unit, anchor=None, max_nodes=None, keep_elements=False, message_words=False):
    """Typed graph of a method unit.

    unit: MethodUnit of the task view (after masking for a post_masked view).
    anchor: LogStatement the task is about (REMOVE_LOG / CHANGE_LEVEL), or None to anchor
            on the METHOD node (ADD_LOG, add_log_post).
    Returns a dict of numpy arrays (node_type, node_num, tok_ptr, tok_ids, edge_index,
    edge_type) and ints (anchor, target, truncated, n_nodes_full). With keep_elements the
    srcML element (or variable name) of each node is returned under 'elements'.
    message_words=True adds the words of string literals to LOG_STMT / PRINT_STMT tokens.
    It is off by default because the tabular x_ features do not see string literals, and
    both representations should get the same lexical information; it is only an ablation.
    """
    b = _Builder(unit, message_words)
    b.walk()
    anchor_idx, target = b.finish(anchor)

    node_type = np.array([NODE_ID[n["type"]] for n in b.nodes], dtype=np.int16)
    node_num = np.array([b.features(i) for i in range(len(b.nodes))], dtype=np.float32).reshape(-1, len(NUMERIC_FEATURES))
    tok_ptr = [0]
    tok_ids = []
    for n in b.nodes:
        for t in _clip_tokens(n["tokens"]):
            tok_ids.append(bucket(t))
        tok_ptr.append(len(tok_ids))

    src, dst, et = [], [], []
    for s, d, t in b.edges:
        src.append(s)
        dst.append(d)
        et.append(EDGE_ID[t])
    for s, d, t in b.edges:
        src.append(d)
        dst.append(s)
        et.append(EDGE_ID[REVERSE[t]])

    g = {
        "node_type": node_type,
        "node_num": node_num,
        "tok_ptr": np.array(tok_ptr, dtype=np.int64),
        "tok_ids": np.array(tok_ids, dtype=np.int16),
        "edge_index": np.array([src, dst], dtype=np.int32).reshape(2, -1),
        "edge_type": np.array(et, dtype=np.int8),
        "anchor": anchor_idx,
        "target": target,
        "truncated": 0,
        "n_nodes_full": len(b.nodes),
    }
    if keep_elements:
        g["elements"] = [n.get("name", n["el"]) for n in b.nodes]
    if max_nodes is not None and len(b.nodes) > max_nodes:
        g = truncate(g, max_nodes)
    return g


def truncate(g, max_nodes):
    """Keep the max_nodes nodes nearest to the target (undirected BFS).

    Anchor, target and the target's AST ancestors up to METHOD always stay, so METHOD is
    still node 0 and the kept graph stays connected.
    """
    n = len(g["node_type"])
    if n <= max_nodes:
        return g
    target, anchor = g["target"], g["anchor"]
    adj = [[] for _ in range(n)]
    parent = {}
    child_type = EDGE_ID["AST_CHILD"]
    for s, d, t in zip(g["edge_index"][0].tolist(), g["edge_index"][1].tolist(), g["edge_type"].tolist()):
        adj[s].append(d)
        if t == child_type:
            parent[d] = s
    keep = {target, anchor}
    u = target
    while u in parent:
        u = parent[u]
        keep.add(u)
    seen = {target}
    queue = deque([target])
    while queue and len(keep) < max_nodes:
        u = queue.popleft()
        for v in sorted(set(adj[u])):
            if v in seen:
                continue
            seen.add(v)
            queue.append(v)
            if v not in keep:
                keep.add(v)
                if len(keep) >= max_nodes:
                    break
    kept = sorted(keep)
    remap = {old: new for new, old in enumerate(kept)}

    src, dst, et = [], [], []
    for s, d, t in zip(g["edge_index"][0].tolist(), g["edge_index"][1].tolist(), g["edge_type"].tolist()):
        if s in remap and d in remap:
            src.append(remap[s])
            dst.append(remap[d])
            et.append(t)
    tok_ptr = [0]
    tok_ids = []
    for old in kept:
        tok_ids.extend(g["tok_ids"][g["tok_ptr"][old]:g["tok_ptr"][old + 1]].tolist())
        tok_ptr.append(len(tok_ids))

    out = dict(g)
    out["node_type"] = g["node_type"][kept]
    out["node_num"] = g["node_num"][kept]
    out["tok_ptr"] = np.array(tok_ptr, dtype=np.int64)
    out["tok_ids"] = np.array(tok_ids, dtype=np.int16)
    out["edge_index"] = np.array([src, dst], dtype=np.int32).reshape(2, -1)
    out["edge_type"] = np.array(et, dtype=np.int8)
    out["anchor"] = remap[anchor]
    out["target"] = remap[target]
    out["truncated"] = 1
    if "elements" in g:
        out["elements"] = [g["elements"][i] for i in kept]
    return out


def build_instance_graph(view, max_nodes=None, keep_elements=False, message_words=False):
    """Graph of an InstanceView: anchored on view.anchor when the instance names one
    (anchor_pre_idx: REMOVE_LOG, CHANGE_LEVEL), on the METHOD node otherwise."""
    if view.anchor is None and view.instance.get("anchor_pre_idx") is not None:
        raise ValueError("statement task without anchor statement")
    return build_graph(view.unit, view.anchor, max_nodes, keep_elements, message_words)


def empty_blocks(unit):
    """Counter of parent node types over the BLOCK nodes of a unit that hold no statement.

    Used to measure what the masking of post_masked views leaves behind, such as an
    emptied method body.
    """
    b = _Builder(unit)
    b.walk()
    out = Counter()
    for node in b.nodes:
        if node["type"] == "BLOCK" and not node["children"] and node["parent"] is not None:
            out[b.nodes[node["parent"]]["type"]] += 1
    return out
