"""Tests for graph construction (src/graphs/builder.py), storage and the stage script."""

import json

import numpy as np
import pytest

from src.dataset import views
from src.detection.verbosity import LEVEL_ORD
from src.features.lexical import bucket
from src.graphs.builder import (
    NODE_TYPES, EDGE_TYPES, NUMERIC_FEATURES, MAX_TOKENS, build_graph, build_instance_graph, empty_blocks
)
from src.graphs.serialize import pack_graphs, unpack_graph, save_graphs, load_graphs
from src.parsing.method_units import parse_java_source
from src.parsing.srcml_parser import flatten_code

F = len(NUMERIC_FEATURES)


def unit_of(src, sig):
    pf = parse_java_source(src)
    return [u for u in pf.units if u.signature == sig][0]


def types(g):
    return [NODE_TYPES[t] for t in g["node_type"].tolist()]


def edges(g, name):
    k = EDGE_TYPES.index(name)
    ei = g["edge_index"]
    return [(int(s), int(d)) for s, d, t in zip(ei[0], ei[1], g["edge_type"]) if t == k]


def text(g, i):
    el = g["elements"][i]
    if isinstance(el, str):
        return el
    return " ".join(flatten_code(el).split()) if el is not None else ""


def find(g, ntype, contains=""):
    return [i for i, t in enumerate(types(g)) if t == ntype and contains in text(g, i)]


def var_node(g, name):
    hits = [i for i, t in enumerate(types(g)) if t == "VARIABLE" and g["elements"][i] == name]
    assert len(hits) <= 1
    return hits[0] if hits else None


def tokens(g, i):
    return g["tok_ids"][g["tok_ptr"][i]:g["tok_ptr"][i + 1]].tolist()


CONSTRUCTS = '''
import java.util.logging.Logger;
class A {
  private static final Logger LOG = Logger.getLogger("A");
  int f(int x, String s) throws Exception {
    int y = x + 1;
    if (x > 0) { y = g(x, h(y)); } else if (x < 0) y--; else { return 0; }
    for (int i = 0; i < y; i++) { count += i; continue; }
    while (y > 0) y--;
    do { y++; } while (y < 3);
    switch (x) { case 1: y = 2; break; default: y = 3; }
    try { r.read(); } catch (IOException e) { LOG.warning("fail " + e); throw new RuntimeException(e); } finally { close(); }
    synchronized (this) { count++; }
    outer: for (;;) { break outer; }
    ;
    Runnable q = () -> System.out.println("hi");
    Object o = new Object() { public String toString() { LOG.fine("anon"); return "x"; } };
    class Local { void m() {} }
    assert x > 0;
    return s.length();
  }
}
'''


@pytest.fixture(scope="module")
def constructs():
    u = unit_of(CONSTRUCTS, "f(int,String)")
    return u, build_graph(u, keep_elements=True)


def test_node_types_of_constructs(constructs):
    u, g = constructs
    t = types(g)
    for expected in NODE_TYPES:
        if expected in ("ANON_CLASS", "LOCAL_CLASS"):
            continue
        assert expected in t, expected
    assert "ANON_CLASS" in t and "LOCAL_CLASS" in t
    assert t[0] == "METHOD" and t[-1] == "ANCHOR" and t.count("ANCHOR") == 1
    assert t.count("PARAM") == 2
    assert t.count("LOG_STMT") == len(u.formal_logs) == 2
    assert t.count("PRINT_STMT") == 1
    assert g["node_num"].shape == (len(t), F)
    assert g["node_num"].dtype == np.float32


def test_every_log_statement_is_one_node(constructs):
    u, g = constructs
    log_nodes = [i for i, x in enumerate(types(g)) if x in ("LOG_STMT", "PRINT_STMT")]
    assert sorted(id(g["elements"][i]) for i in log_nodes) == sorted(id(l.element) for l in u.logs)
    # the log call itself is not repeated as a CALL node
    assert not find(g, "CALL", "LOG.warning")
    assert find(g, "CALL", "close()")


def test_next_follows_statement_order():
    u = unit_of('class A { void f(){ a(); int x = 1; b(x); return; } }', "f()")
    g = build_graph(u, keep_elements=True)
    block = types(g).index("BLOCK")
    stmts = [d for s, d in edges(g, "AST_CHILD") if s == block]
    assert [types(g)[i] for i in stmts] == ["EXPR_STMT", "DECL_STMT", "EXPR_STMT", "RETURN"]
    nxt = edges(g, "NEXT")
    assert nxt == list(zip(stmts, stmts[1:]))
    assert sorted(edges(g, "PREV")) == sorted((d, s) for s, d in nxt)


def test_control_edges_of_loop_body():
    src = 'class A { void f(){ for (int i = 0; i < n; i++) { a(); if (c) { b(); } } done(); } }'
    g = build_graph(unit_of(src, "f()"), keep_elements=True)
    loop = find(g, "FOR")[0]
    if_node = find(g, "IF")[0]
    a_stmt = find(g, "EXPR_STMT", "a()")[0]
    b_stmt = find(g, "EXPR_STMT", "b()")[0]
    done = find(g, "EXPR_STMT", "done()")[0]
    ctrl = edges(g, "CONTROL")
    assert sorted(d for s, d in ctrl if s == loop) == sorted([a_stmt, if_node])
    assert (if_node, b_stmt) in ctrl
    assert all(d != done for s, d in ctrl)
    assert all(d != b_stmt for s, d in ctrl if s == loop)
    nf = NUMERIC_FEATURES.index("in_loop")
    assert g["node_num"][a_stmt, nf] == 1 and g["node_num"][b_stmt, nf] == 1
    assert g["node_num"][done, nf] == 0 and g["node_num"][loop, nf] == 0


def test_uses_and_declares_local_variable():
    src = 'class A { void f(int base){ int total = base + 1; use(total); } }'
    g = build_graph(unit_of(src, "f(int)"), keep_elements=True)
    decl = find(g, "DECL_STMT")[0]
    call_stmt = find(g, "EXPR_STMT", "use(total)")[0]
    param = find(g, "PARAM")[0]
    total, base = var_node(g, "total"), var_node(g, "base")
    assert (decl, total) in edges(g, "DECLARES")
    assert (total, decl) in edges(g, "DECLARED_BY")
    assert (param, base) in edges(g, "DECLARES")
    assert (decl, base) in edges(g, "USES")
    assert (call_stmt, total) in edges(g, "USES")
    assert (decl, total) not in edges(g, "USES")
    isf = NUMERIC_FEATURES.index("is_field")
    assert g["node_num"][total, isf] == 0 and g["node_num"][base, isf] == 0
    assert tokens(g, total) == [bucket("total"), bucket("int")]
    # the call node hangs off the statement that owns it
    call = find(g, "CALL", "use(total)")[0]
    assert (call_stmt, call) in edges(g, "CALLS")


def test_field_flag_and_no_type_or_method_variables():
    src = '''class A { void f(int[] arr){
        count++;
        this.speed = 2;
        int m = Util.max(left, right);
        java.util.Arrays.sort(arr);
        Foo cast = (Foo) obj;
        Runnable r = Integer::parseInt;
        LOG.info("x");
        foo(bar).baz();
        java.util.List<String> l = new java.util.ArrayList<>();
        Object v = new com.jme3.math.Vector3f(1, 2, 3);
        player.Update();
        throw new java.lang.IllegalStateException("x");
    } }'''
    g = build_graph(unit_of(src, "f(int[])"), keep_elements=True)
    names = {g["elements"][i] for i, t in enumerate(types(g)) if t == "VARIABLE"}
    assert names == {"arr", "count", "speed", "m", "left", "right", "cast", "obj", "r", "LOG", "bar",
                     "l", "v", "player"}
    isf = NUMERIC_FEATURES.index("is_field")
    for name in ("count", "speed", "left", "right", "obj", "LOG", "bar", "player"):
        assert g["node_num"][var_node(g, name), isf] == 1, name
    for name in ("arr", "m", "cast", "r", "l", "v"):
        assert g["node_num"][var_node(g, name), isf] == 0, name
    nested = find(g, "EXPR_STMT", "foo(bar)")[0]
    assert len([d for s, d in edges(g, "CALLS") if s == nested]) == 2


def test_nested_calls_and_features():
    src = '''class A { void loadAll(){
        try { run(load("a.txt"), 3); } catch (IOException | IllegalStateException ex) { LOG.error("cannot load {}", name, ex); }
    } }'''
    g = build_graph(unit_of(src, "loadAll()"), keep_elements=True)
    stmt = find(g, "EXPR_STMT", "run(")[0]
    outer = find(g, "CALL", "run(")[0]
    inner = [i for i in find(g, "CALL", "load(") if text(g, i).startswith("load")][0]
    assert {d for s, d in edges(g, "CALLS") if s == stmt} == {outer, inner}
    assert (outer, inner) in edges(g, "AST_CHILD")
    col = {n: NUMERIC_FEATURES.index(n) for n in NUMERIC_FEATURES}
    assert g["node_num"][outer, col["n_args_norm"]] == pytest.approx(0.4)
    assert g["node_num"][inner, col["has_string_literal"]] == 1
    assert g["node_num"][outer, col["has_string_literal"]] == 1
    log = find(g, "LOG_STMT")[0]
    assert g["node_num"][log, col["in_catch"]] == 1 and g["node_num"][stmt, col["in_catch"]] == 0
    assert g["node_num"][log, col["level_ord_norm"]] == pytest.approx(LEVEL_ORD["ERROR"] / 5)
    assert g["node_num"][log, col["n_args_norm"]] == pytest.approx(0.6)
    # message words are an ablation only (x_ does not see string literals)
    assert tokens(g, log) == [bucket("log"), bucket("error")]
    words = build_graph(unit_of(src, "loadAll()"), message_words=True)
    assert tokens(words, log) == [bucket(t) for t in ["log", "error", "cannot", "load"]]
    catch = find(g, "CATCH")[0]
    assert tokens(g, catch) == [bucket(t) for t in ["io", "exception", "illegal", "state"]]
    assert tokens(g, 0) == [bucket("load"), bucket("all")]
    assert all(0 <= t < 128 for t in g["tok_ids"].tolist())
    assert max(np.diff(g["tok_ptr"])) <= MAX_TOKENS
    assert (g["node_num"] >= 0).all()


def test_reverse_edges_pair_up(constructs):
    _, g = constructs
    for k in range(0, len(EDGE_TYPES), 2):
        fwd = sorted(edges(g, EDGE_TYPES[k]))
        rev = sorted((d, s) for s, d in edges(g, EDGE_TYPES[k + 1]))
        assert fwd == rev, EDGE_TYPES[k]
    assert g["edge_index"].dtype == np.int32 and g["edge_type"].dtype == np.int8
    assert g["edge_index"].max() < len(g["node_type"])


def test_lambda_and_anonymous_class_logs():
    src = '''class A { void f(java.util.List<String> items){
        items.forEach(it -> LOG.debug("item " + it));
        new Thread(new Runnable() { public void run() { LOG.info("run"); } }).start();
    } }'''
    u = parse_java_source(src).units[0]
    g = build_graph(u, keep_elements=True)
    logs = find(g, "LOG_STMT")
    assert len(logs) == len(u.formal_logs) == 2
    parent = {d: s for s, d in edges(g, "AST_CHILD")}

    def ancestors(i):
        out = []
        while i in parent:
            i = parent[i]
            out.append(types(g)[i])
        return out
    assert "LAMBDA" in ancestors(logs[0])
    assert "ANON_CLASS" in ancestors(logs[1])
    lam = find(g, "LAMBDA")[0]
    assert (lam, var_node(g, "it")) in edges(g, "DECLARES")


def test_anchor_targets_log_statement(constructs):
    u, _ = constructs
    anchor = u.formal_logs[0]
    g = build_graph(u, anchor, keep_elements=True)
    assert types(g)[g["target"]] == "LOG_STMT"
    assert g["elements"][g["target"]] is anchor.element
    assert types(g)[g["anchor"]] == "ANCHOR"
    assert edges(g, "ANCHOR") == [(g["anchor"], g["target"])]
    assert edges(g, "ANCHORED_BY") == [(g["target"], g["anchor"])]
    g0 = build_graph(u)
    assert g0["target"] == 0 and types(g0)[0] == "METHOD"


PRE = '''import org.slf4j.Logger;
class Game {
  void tick(float tpf) {
    if (LOG.isDebugEnabled()) { LOG.debug("tick " + tpf); }
    step(tpf);
  }
}
'''
POST = '''import org.slf4j.Logger;
class Game {
  void tick(float tpf) {
    if (LOG.isDebugEnabled()) { LOG.debug("tick " + tpf); }
    try { step(tpf); } catch (Exception e) { LOG.error("step failed", e); }
    if (LOG.isTraceEnabled()) { LOG.trace("after step"); }
  }
}
'''


def fake_instances(tag):
    common = {"repo": f"fake_{tag}", "commit_id": "c" * 40, "class_path": "Game", "label": 1,
              "in_R1": True, "in_R4": True, "in_R10": True, "pre_blob": f"{tag}01" * 5, "post_blob": f"{tag}02" * 5,
              "signature_pre": "tick(float)", "signature_post": "tick(float)", "pre_ordinal": 0, "post_ordinal": 0}
    add = dict(common, instance_id=f"add_log_post:fake_{tag}:c:0", task="add_log_post", view="post_masked",
               mask_post_idx=[1, 2])
    rem = dict(common, instance_id=f"remove_log:fake_{tag}:c:0:0", task="remove_log", view="pre", anchor_pre_idx=0)
    bad = dict(common, instance_id=f"remove_log:fake_{tag}:c:0:5", task="remove_log", view="pre", anchor_pre_idx=5)
    blobs = {(common["repo"], common["pre_blob"]): PRE.encode(), (common["repo"], common["post_blob"]): POST.encode()}
    return add, rem, bad, blobs


def add_log_pre(add):
    # the primary ADD_LOG instance of the same unit: pre-state view, no mask, no anchor
    inst = {k: v for k, v in add.items() if k != "mask_post_idx"}
    inst.update(instance_id="add_log:" + add["instance_id"].split(":", 1)[1], task="add_log", view="pre")
    return inst


def patch_blobs(monkeypatch, blobs):
    monkeypatch.setattr(views, "read_blob", lambda repo, sha: blobs[(repo, sha)])


def test_add_log_masked_view_has_no_masked_logs(monkeypatch):
    add, rem, bad, blobs = fake_instances("aa")
    patch_blobs(monkeypatch, blobs)
    view = views.load_view(add)
    assert view is not None and view.anchor is None
    g = build_instance_graph(view, keep_elements=True)
    log_text = [text(g, i) for i in find(g, "LOG_STMT")]
    assert log_text == ['LOG.debug("tick " + tpf);']
    assert not any("step failed" in text(g, i) or "after step" in text(g, i) for i in range(len(g["node_type"])))
    # the emptied isTraceEnabled guard is gone too, and the try whose only catch held the
    # added log is unwrapped: step(tpf) is a plain statement of the method body
    assert len(find(g, "IF")) == 1
    assert not find(g, "CATCH") and not find(g, "TRY")
    assert g["target"] == 0
    # ... which is the graph of the pre-state method, the primary ADD_LOG view
    pre_view = views.load_view(add_log_pre(add))
    assert pre_view.anchor is None and pre_view.masked == 0
    g_pre = build_instance_graph(pre_view)
    assert g_pre["target"] == 0 and types(g_pre)[g_pre["target"]] == "METHOD"
    for k in ("node_type", "node_num", "tok_ids", "edge_index", "edge_type"):
        assert np.array_equal(g[k], g_pre[k]), k

    view = views.load_view(rem)
    g = build_instance_graph(view, keep_elements=True)
    assert types(g)[g["target"]] == "LOG_STMT"
    assert text(g, g["target"]) == 'LOG.debug("tick " + tpf);'
    assert views.load_view(bad) is None


def big_method(n):
    body = "\n".join(f"    int v{i} = w{i} + call{i}(v{i - 1 if i else 0});" for i in range(n))
    return f'class A {{ void big() {{\n{body}\n    LOG.warn("middle");\n{body.replace("int v", "v")}\n  }} }}'


def test_truncation_keeps_anchor_and_target():
    u = parse_java_source(big_method(150)).units[0]
    anchor = u.formal_logs[0]
    full = build_graph(u, anchor, keep_elements=True)
    g = build_graph(u, anchor, max_nodes=60, keep_elements=True)
    assert len(full["node_type"]) > 60
    assert len(g["node_type"]) == 60 and g["truncated"] == 1 and g["n_nodes_full"] == len(full["node_type"])
    assert types(g)[g["target"]] == "LOG_STMT" and g["elements"][g["target"]] is anchor.element
    assert types(g)[g["anchor"]] == "ANCHOR"
    assert g["edge_index"].max() < 60
    # the kept statements are the ones next to the log
    t = full["target"]
    neighbours = {d for s, d in edges(full, "NEXT") + edges(full, "PREV") if s == t}
    kept = {id(e) for e in g["elements"] if not isinstance(e, str)}
    assert all(id(full["elements"][i]) in kept for i in neighbours)
    # induced subgraph: no edge lost between kept nodes
    pos = {id(e) if not isinstance(e, str) else e: i for i, e in enumerate(g["elements"])}
    induced = 0
    for s, d in zip(full["edge_index"][0], full["edge_index"][1]):
        ks = full["elements"][s]
        kd = full["elements"][d]
        ks = ks if isinstance(ks, str) else id(ks)
        kd = kd if isinstance(kd, str) else id(kd)
        if ks in pos and kd in pos:
            induced += 1
    assert induced == g["edge_index"].shape[1]
    small = build_graph(u, anchor, max_nodes=10_000)
    assert small["truncated"] == 0


def test_determinism():
    a = build_graph(unit_of(CONSTRUCTS, "f(int,String)"))
    b = build_graph(unit_of(CONSTRUCTS, "f(int,String)"))
    for k in ("node_type", "node_num", "tok_ptr", "tok_ids", "edge_index", "edge_type"):
        assert np.array_equal(a[k], b[k]), k
    assert (a["anchor"], a["target"]) == (b["anchor"], b["target"])


def test_npz_round_trip(tmp_path, constructs):
    u, _ = constructs
    graphs = [build_graph(u), build_graph(u, u.formal_logs[1]), build_graph(unit_of(big_method(30), "big()"), max_nodes=40)]
    ids = ["t:a", "t:b", "t:c"]
    save_graphs("t", graphs, ids, {"task": "t"}, F, tmp_path)
    arrays, index, meta = load_graphs("t", tmp_path)
    assert meta == {"task": "t"}
    assert [r["instance_id"] for r in index] == ids
    assert [r["truncated"] for r in index] == [0, 0, 1]
    assert arrays["node_ptr"].tolist()[-1] == sum(len(g["node_type"]) for g in graphs)
    assert arrays["tok_ptr"].shape == (arrays["node_ptr"][-1] + 1,)
    assert arrays["node_type"].dtype == np.int16 and arrays["tok_ids"].dtype == np.int16
    assert arrays["anchor_local"].dtype == np.int32 and arrays["edge_ptr"].dtype == np.int64
    for pos, g in enumerate(graphs):
        back = unpack_graph(arrays, pos)
        assert index[pos]["n_nodes"] == len(g["node_type"]) and index[pos]["n_edges"] == g["edge_index"].shape[1]
        for k in ("node_type", "node_num", "tok_ptr", "tok_ids", "edge_index", "edge_type"):
            assert np.array_equal(back[k], g[k]), k
        assert (back["anchor"], back["target"]) == (g["anchor"], g["target"])
    empty = pack_graphs([], F)
    assert empty["node_ptr"].tolist() == [0] and empty["edge_index"].shape == (2, 0)


def test_build_task_script(tmp_path, monkeypatch):
    from scripts import build_graphs

    add, rem, bad, blobs = fake_instances("bb")
    patch_blobs(monkeypatch, blobs)
    out = tmp_path / "graphs"
    with open(tmp_path / "remove_log.jsonl", "w", encoding="utf-8") as f:
        for inst in (bad, rem, dict(rem, instance_id=rem["instance_id"] + "x", in_R4=False)):
            f.write(json.dumps(inst) + "\n")
    meta = build_graphs.build_task("remove_log", "R4", workers=1, instances_dir=tmp_path, out_dir=out, verbose=False)
    assert meta["n_candidates"] == 2 and meta["n_graphs"] == 1 and meta["n_failures"] == 1
    assert meta["node_types"] == NODE_TYPES and meta["numeric_features"] == NUMERIC_FEATURES
    assert meta["stats"]["per_repo"]["fake_bb"]["failures"] == 1
    arrays, index, _ = load_graphs("remove_log", out)
    assert [r["instance_id"] for r in index] == [rem["instance_id"]]
    fails = [json.loads(l) for l in open(out / "remove_log_failures.jsonl", encoding="utf-8")]
    assert fails[0]["instance_id"] == bad["instance_id"] and fails[0]["reason"].startswith("anchor_pre_idx not in unit")
    assert build_graphs.build_task("remove_log", "R4", workers=1, instances_dir=tmp_path, out_dir=out,
                                   verbose=False) is None
    # a missing failures file (interrupted run) is not 'up to date'
    (out / "remove_log_failures.jsonl").unlink()
    assert build_graphs.build_task("remove_log", "R4", workers=1, instances_dir=tmp_path, out_dir=out,
                                   verbose=False) is not None
    for rel in ("src/detection/log_detection.py", "src/detection/verbosity.py", "scripts/build_graphs.py"):
        assert rel in build_graphs.CODE_FILES

    with open(tmp_path / "add_log_post.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(add) + "\n")
        f.write(json.dumps(dict(add, instance_id=add["instance_id"] + "n", label=0, mask_post_idx=[])) + "\n")
    meta = build_graphs.build_task("add_log_post", "R4", workers=1, instances_dir=tmp_path, out_dir=out,
                                   verbose=False)
    res = meta["mask_residue"]
    # the catch emptied by masking is removed with its try: nothing is left behind
    assert res["instances"] == {} and res["n_instances"] == 0
    assert res["graphs_with_empty_block_by_label"] == {}
    assert meta["log_message_words"] is False and meta["anchor_target"] == "METHOD"
    assert meta["n_graphs"] == 2 and meta["n_failures"] == 0

    # the primary ADD_LOG view is the pre-state method: nothing masked, METHOD target
    with open(tmp_path / "add_log.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(add_log_pre(add)) + "\n")
    meta = build_graphs.build_task("add_log", "R4", workers=1, instances_dir=tmp_path, out_dir=out, verbose=False)
    assert meta["n_graphs"] == 1 and meta["mask_residue"] is None and meta["anchor_target"] == "METHOD"
    arrays, index, _ = load_graphs("add_log", out)
    assert arrays["target_local"].tolist() == [0]
    rem_meta = json.loads((out / "remove_log_meta.json").read_text(encoding="utf-8"))
    assert rem_meta["anchor_target"] == "LOG_STMT of anchor_pre_idx" and rem_meta["mask_residue"] is None


RESIDUE = '''import org.slf4j.Logger;
class R {
  void f(java.util.List<String> xs, int x) {
    Events.on(Foo.class, e -> LOG.info("loaded"));
    for (String s : xs) LOG.debug(s);
    while (busy()) LOG.warn("busy");
    if (x > 0) { LOG.debug("pos"); } else { neg(); }
    try { run(); } catch (Exception e) { LOG.error("fail", e); } finally { LOG.info("done"); }
    synchronized (this) { LOG.trace("in lock"); }
    if (LOG.isDebugEnabled()) { LOG.debug("guarded"); }
    try { other(); } catch (RuntimeException ignored) { }
    try { LOG.info("start"); } catch (Exception e) { reset(); }
    try { more(); } catch (IllegalStateException e) { LOG.warn("state"); } catch (Exception e) { reset(); }
    exec(new Runnable() { public void run() { LOG.debug("task"); } });
    switch (x) { case 1: LOG.info("one"); break; case 2: two(); break; }
    switch (x) { default: LOG.warn("any"); }
    step();
  }
}
'''


def residue_instance(monkeypatch, tag, src, label=1):
    pf = parse_java_source(src)
    mask = [l.formal_index for l in pf.units[0].formal_logs] if label else []
    inst = {"instance_id": f"add_log_post:fake_{tag}:c:0", "task": "add_log_post", "repo": f"fake_{tag}",
            "commit_id": "c" * 40,
            "class_path": "R", "label": label, "in_R4": True, "view": "post_masked", "mask_post_idx": mask,
            "pre_blob": f"{tag}01" * 5, "post_blob": f"{tag}02" * 5, "signature_pre": pf.units[0].signature,
            "signature_post": pf.units[0].signature, "pre_ordinal": 0, "post_ordinal": 0}
    blobs = {(inst["repo"], inst["pre_blob"]): src.encode(), (inst["repo"], inst["post_blob"]): src.encode()}
    patch_blobs(monkeypatch, blobs)
    return inst


def test_mask_residue_is_measured(monkeypatch):
    from scripts.build_graphs import mask_residue

    inst = residue_instance(monkeypatch, "rr", RESIDUE)
    view = views.load_view(inst)
    assert view is not None and not view.unit.formal_logs
    # complete masking: loops, lambdas, finally/synchronized blocks, if branches, catch clauses,
    # try statements and single-method anonymous classes emptied by it are all gone
    assert mask_residue(inst, view) == []
    g = build_instance_graph(view, keep_elements=True)
    assert len(find(g, "TRY")) == 2 and len(find(g, "CATCH")) == 2   # other() and more() keep theirs
    assert not find(g, "ANON_CLASS") and not find(g, "FINALLY") and not find(g, "LAMBDA")
    # the case group of the masked log goes, and the switch that only held a log
    assert len(find(g, "SWITCH")) == 1 and len(find(g, "CASE")) == 1

    neg = residue_instance(monkeypatch, "rn", RESIDUE, label=0)
    view = views.load_view(neg)
    assert view.masked == 0 and mask_residue(neg, view) == []
    assert empty_blocks(view.unit) == {"CATCH": 1}

    # the method body itself is kept even when masking empties it: the one residue left
    only = residue_instance(monkeypatch, "rm", "class R {\n  void f() {\n    LOG.info(\"a\");\n  }\n}\n")
    view = views.load_view(only)
    assert mask_residue(only, view) == ["METHOD"]


def test_masking_leaves_no_emptied_body(monkeypatch):
    view = views.load_view(residue_instance(monkeypatch, "rx", RESIDUE))
    # only the empty catch the developer wrote is left
    assert empty_blocks(view.unit) == {"CATCH": 1}


def test_graph_tokens_stay_within_tabular_lexical_buckets(constructs):
    from src.features.method_features import lexical_features

    src = '''class A { void loadAll(){
        try { run(load("a.txt"), 3); } catch (IOException ex) { LOG.error("cannot open {}", name, ex); }
    } }'''
    u, _ = constructs
    cases = [(u, None), (u, u.formal_logs[0]), (unit_of(src, "loadAll()"), None)]
    for unit, anchor in cases:
        x = lexical_features(unit.element)
        nonzero = {i for i in range(128) if x[f"x_{i:03d}"] > 0}
        g = build_graph(unit, anchor)
        assert set(g["tok_ids"].tolist()) <= nonzero
    # with message words the graph sees buckets that x_ never sees
    unit = unit_of(src, "loadAll()")
    x = lexical_features(unit.element)
    nonzero = {i for i in range(128) if x[f"x_{i:03d}"] > 0}
    assert set(build_graph(unit, message_words=True)["tok_ids"].tolist()) - nonzero


def deep_method(n):
    stmts = "\n".join(f'    LOG.info("s{i}" + a{i} + b{i}); v{i}.x = w{i};' for i in range(n))
    return (f'class A {{ void big() {{\n{stmts}\n'
            f'    run(() -> {{ go(() -> {{ if (c) {{ while (d) {{ LOG.warn("deep"); }} }} }}); }});\n  }} }}')


def test_truncation_keeps_method_and_path_to_target():
    u = parse_java_source(deep_method(150)).units[0]
    anchor = [l for l in u.formal_logs if "deep" in l.call_text][0]
    g = build_graph(u, anchor, max_nodes=100, keep_elements=True)
    assert g["truncated"] == 1 and len(g["node_type"]) == 100
    t = types(g)
    assert t[0] == "METHOD" and g["elements"][0] is u.element
    assert t[g["target"]] == "LOG_STMT" and g["elements"][g["target"]] is anchor.element
    # the target still reaches METHOD through AST_PARENT edges
    up = dict(edges(g, "AST_PARENT"))
    i, steps = g["target"], 0
    while i != 0 and i in up and steps < 100:
        i, steps = up[i], steps + 1
    assert i == 0


def test_truncation_of_add_log_graph():
    u = parse_java_source(big_method(150)).units[0]
    full = build_graph(u)
    g = build_graph(u, max_nodes=60)
    assert len(full["node_type"]) > 60
    assert len(g["node_type"]) == 60 and g["truncated"] == 1
    assert g["target"] == 0 and types(g)[0] == "METHOD"
    assert types(g)[g["anchor"]] == "ANCHOR" and edges(g, "ANCHOR") == [(g["anchor"], 0)]
    assert any(s == 0 for s, d in edges(g, "AST_CHILD"))


def test_task_all_builds_every_instances_file(tmp_path, monkeypatch):
    from scripts import build_graphs

    for task in ("add_log", "add_log_post", "change_level"):
        (tmp_path / f"{task}.jsonl").write_text("")
    calls = []
    monkeypatch.setattr(build_graphs, "build_task", lambda task, *a, **kw: calls.append(task))
    monkeypatch.setattr("sys.argv", ["build_graphs", "--task", "all", "--instances-dir", str(tmp_path)])
    build_graphs.main()
    assert calls == ["add_log", "add_log_post", "change_level"]


def test_non_primary_runs_keep_out_of_the_primary_folder(tmp_path, monkeypatch):
    from scripts import build_graphs

    add, rem, bad, blobs = fake_instances("cc")
    patch_blobs(monkeypatch, blobs)
    primary = tmp_path / "graphs"
    monkeypatch.setattr(build_graphs, "GRAPH_DIR", primary)
    with open(tmp_path / "remove_log.jsonl", "w", encoding="utf-8") as f:
        for inst in (rem, dict(rem, instance_id=rem["instance_id"] + "x", in_R1=False)):
            f.write(json.dumps(inst) + "\n")
    build_graphs.build_task("remove_log", "R4", workers=1, instances_dir=tmp_path, verbose=False)
    names = ["remove_log.npz", "remove_log_index.csv", "remove_log_meta.json", "remove_log_failures.jsonl"]
    before = {n: (primary / n).read_bytes() for n in names}

    r1 = build_graphs.build_task("remove_log", "R1", workers=1, instances_dir=tmp_path, verbose=False)
    lim = build_graphs.build_task("remove_log", "R4", workers=1, limit=1, instances_dir=tmp_path, verbose=False)
    msg = build_graphs.build_task("remove_log", "R4", workers=1, instances_dir=tmp_path, message_words=True,
                                  verbose=False)
    assert (r1["n_graphs"], lim["n_graphs"], msg["n_graphs"]) == (1, 1, 2)
    for sub in ("R1", "R4_limit1", "R4_msgwords"):
        assert (primary / sub / "remove_log_meta.json").exists()
    assert {n: (primary / n).read_bytes() for n in names} == before
    with pytest.raises(ValueError):
        build_graphs.build_task("remove_log", "R1", workers=1, instances_dir=tmp_path, out_dir=primary, verbose=False)


# real git objects: files with formal logs at the pinned jme3rpg HEAD (configs/corpus.yaml)
JME_FILES = [
    "Common/src/main/java/ru/arifolth/anjrpg/weather/WeatherManager.java",
    "Common/src/main/java/ru/arifolth/anjrpg/interfaces/core/ThreadExecutorProvider.java",
    "Modules/Models/src/main/java/ru/arifolth/anjrpg/models/NonPlayerCharacter.java",
    "Modules/Models/src/main/java/ru/arifolth/anjrpg/models/PlayerCharacter.java",
    "Modules/Sky/src/main/java/com/idflood/sky/utils/SunSystem.java",
]


def jme_instances():
    import git
    from src.common.config import load_config, repo_path

    path = repo_path("jme3rpg")
    if not (path / ".git").exists():
        pytest.skip("jme3rpg clone not available")
    head = {r["name"]: r for r in load_config("corpus")["repos"]}["jme3rpg"]["head"]
    commit = git.Repo(str(path)).commit(head)
    out = []
    for rel in JME_FILES:
        blob = commit.tree / rel
        pf = parse_java_source(blob.data_stream.read())
        n_neg = 0
        for u in pf.units:
            if not u.formal_logs and n_neg >= 3:
                continue
            n_neg += not u.formal_logs
            out.append({
                "instance_id": f"add_log_post:jme3rpg:{head[:12]}:{blob.hexsha[:8]}:{u.ordinal}",
                "task": "add_log_post",
                "repo": "jme3rpg", "commit_id": head, "pre_path": rel, "post_path": rel,
                "pre_blob": blob.hexsha, "post_blob": blob.hexsha, "class_path": u.class_path,
                "method_name": u.name, "signature_pre": u.signature, "signature_post": u.signature,
                "kind": u.kind, "pre_ordinal": u.ordinal, "post_ordinal": u.ordinal,
                "label": int(bool(u.formal_logs)), "in_R1": True, "in_R4": True, "in_R10": True,
                "view": "post_masked", "mask_post_idx": [l.formal_index for l in u.formal_logs],
            })
    return out


def test_workers_do_not_change_outputs_on_real_blobs(tmp_path):
    from scripts import build_graphs

    instances = jme_instances()
    assert sum(r["label"] for r in instances) >= 5 and len(build_graphs.make_chunks(instances, 2)) >= 2
    with open(tmp_path / "add_log_post.jsonl", "w", encoding="utf-8") as f:
        for inst in instances:
            f.write(json.dumps(inst) + "\n")
    m1 = build_graphs.build_task("add_log_post", workers=1, instances_dir=tmp_path, out_dir=tmp_path / "w1",
                                 verbose=False)
    m2 = build_graphs.build_task("add_log_post", workers=2, instances_dir=tmp_path, out_dir=tmp_path / "w2",
                                 verbose=False)
    assert m1["n_graphs"] == len(instances) and m1["n_failures"] == 0
    m1.pop("elapsed_seconds"), m2.pop("elapsed_seconds")
    assert m1 == m2
    a1, i1, _ = load_graphs("add_log_post", tmp_path / "w1")
    a2, i2, _ = load_graphs("add_log_post", tmp_path / "w2")
    assert i1 == i2 and [r["instance_id"] for r in i1] == sorted(r["instance_id"] for r in instances)
    for k in a1:
        assert np.array_equal(a1[k], a2[k]), k
    for name in ("add_log_post_index.csv", "add_log_post_failures.jsonl"):
        assert (tmp_path / "w1" / name).read_bytes() == (tmp_path / "w2" / name).read_bytes()
