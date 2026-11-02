"""Tests for the stage-5 tabular features (method, file, statement, history, orchestration).

Blobs are served from a dict instead of git so the tests stay fast; views.load_view is
otherwise used exactly as in the pipeline.
"""

import hashlib
import json
import math

import pandas as pd
import pytest

from src.dataset import views
from src.features import extract
from src.features.extract import view_features, feature_columns, extract_task, STATEMENT_TASKS
from src.features.file_features import file_features
from src.features.history_features import build_history_index, history_features, HISTORY_COLUMNS
from src.features.method_features import method_features, log_context_features, dominant_level
from src.features.statement_features import statement_features
from src.parsing.method_units import parse_java_source

BLOBS = {}


@pytest.fixture(autouse=True)
def fake_blobs(monkeypatch):
    monkeypatch.setattr(views, "read_blob", lambda repo, sha: BLOBS[sha].encode("utf-8"))
    views._parse_cache.clear()
    yield
    views._parse_cache.clear()


def put(sha, text):
    BLOBS[sha] = text
    return sha


def base_instance(task, iid, pre_blob, post_blob, sig, cls, **extra):
    inst = {
        "instance_id": iid, "task": task, "repo": "synthetic", "commit_id": "c" * 40,
        "parent_commit_id": "p" * 40, "topo_index": 3, "timestamp": "2020-01-04T00:00:00+00:00",
        "author_id": "a1", "pre_path": "core/src/game/world/World.java",
        "post_path": "core/src/game/world/World.java", "pre_blob": pre_blob, "post_blob": post_blob,
        "class_path": cls, "method_name": sig.split("(")[0], "signature_pre": sig, "signature_post": sig,
        "kind": "method", "pre_ordinal": None, "post_ordinal": None, "label": 1,
    }
    inst.update(extra)
    return inst


def post_masked(iid, pre_blob, post_blob, sig, cls, mask):
    return base_instance("add_log_post", iid, pre_blob, post_blob, sig, cls, view="post_masked", mask_post_idx=mask)


def add_log_pre(iid, pre_blob, post_blob, sig, cls):
    # primary ADD_LOG view: the method before the commit, no mask, no anchor
    return base_instance("add_log", iid, pre_blob, post_blob, sig, cls, view="pre")


def pre_view(iid, pre_blob, sig, cls, anchor=None):
    extra = {"view": "pre"}
    if anchor is not None:
        extra["anchor_pre_idx"] = anchor
    return base_instance("remove_log", iid, pre_blob, pre_blob, sig, cls, **extra)


def code_columns(feats, prefixes=("m_", "l_", "d_", "x_", "f_")):
    return {k: v for k, v in feats.items() if k.startswith(prefixes)}


def same(a, b):
    assert a.keys() == b.keys()
    diff = {}
    for k in a:
        va, vb = a[k], b[k]
        if isinstance(va, float) and isinstance(vb, float) and math.isnan(va) and math.isnan(vb):
            continue
        if va != vb:
            diff[k] = (va, vb)
    return diff


# leakage: the masked ADD_LOG view must look exactly like the code without the logs

JUL_PRE = '''package game.world;
import java.util.logging.Logger;
import java.util.logging.Level;
import java.util.List;
public class World {
    private static final Logger LOG = Logger.getLogger(World.class.getName());
    private final List<Entity> entities = new ArrayList<>();

    public int update(float tpf, int budget) {
        LOG.fine("update start");
        int done = 0;
        for (Entity e : entities) {
            if (e.isDead()) {
                continue;
            }
            try {
                e.step(tpf);
                done++;
            } catch (IllegalStateException ex) {
                e.reset();
            } catch (RuntimeException io) {
            }
        }
        return done;
    }
}
'''

JUL_POST = '''package game.world;
import java.util.logging.Logger;
import java.util.logging.Level;
import java.util.List;
public class World {
    private static final Logger LOG = Logger.getLogger(World.class.getName());
    private final List<Entity> entities = new ArrayList<>();

    public int update(float tpf, int budget) {
        LOG.fine("update start");
        int done = 0;
        for (Entity e : entities) {
            if (e.isDead()) {
                LOG.info("skipping dead entity " + e.getId());
                continue;
            }
            try {
                e.step(tpf);
                done++;
            } catch (IllegalStateException ex) {
                LOG.log(Level.WARNING, "step failed", ex);
                e.reset();
            } catch (RuntimeException io) {
                LOG.severe("runtime");
            }
        }
        if (LOG.isLoggable(Level.FINE)) {
            LOG.fine("done " + done);
        }
        return done;
    }
}
'''

# slf4j variant: the logger field and import are added in the same commit, the log is
# wrapped in an isDebugEnabled() guard and sits inside a lambda
SLF_PRE = '''package game.net;
import java.util.Map;
class Lobby {
    private Map<String, Player> players;
    void join(Player p) {
        players.put(p.name(), p);
        p.send("welcome");
        players.values().forEach(o -> o.notify(p));
    }
}
'''

SLF_POST = '''package game.net;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
class Lobby {
    private static final Logger log = LoggerFactory.getLogger(Lobby.class);
    private Map<String, Player> players;
    void join(Player p) {
        if (log.isDebugEnabled()) {
            log.debug("join {}", p.name());
        }
        players.put(p.name(), p);
        p.send("welcome");
        players.values().forEach(o -> {
            o.notify(p);
            log.trace("notified {}", o);
        });
    }
}
'''

SLF_PRE_LAMBDA_BLOCK = SLF_PRE.replace("forEach(o -> o.notify(p));", "forEach(o -> {\n            o.notify(p);\n        });")

# JUL_POST adds a log to the catch block that was empty in JUL_PRE; complete masking drops a
# catch it empties, so the masked view is the code written without that catch
JUL_PLAIN = JUL_PRE.replace(" catch (RuntimeException io) {\n            }", "")


@pytest.mark.parametrize("plain_src,post_src,sig,cls,n_added", [
    (JUL_PLAIN, JUL_POST, "update(float,int)", "World", 4),
    (SLF_PRE_LAMBDA_BLOCK, SLF_POST, "join(Player)", "Lobby", 2),
])
def test_masked_add_log_view_equals_code_without_logs(plain_src, post_src, sig, cls, n_added):
    pre = put(f"pre-{cls}", plain_src)
    post = put(f"post-{cls}", post_src)
    post_unit = [u for u in parse_java_source(post_src).units if u.signature == sig][0]
    pre_unit = [u for u in parse_java_source(plain_src).units if u.signature == sig][0]
    pre_texts = {l.call_text for l in pre_unit.formal_logs}
    added = [l.formal_index for l in post_unit.formal_logs if l.call_text not in pre_texts]
    assert len(added) == n_added

    v_add = views.load_view(post_masked("add:1", pre, post, sig, cls, added))
    v_pre = views.load_view(pre_view("pre:1", pre, sig, cls))
    assert v_add is not None and v_pre is not None
    f_add = code_columns(view_features(v_add, "add_log_post"))
    f_pre = code_columns(view_features(v_pre, "multiclass"))
    assert same(f_add, f_pre) == {}
    # the features are not trivially empty
    assert f_add["m_n_statements"] > 3 and sum(v for k, v in f_add.items() if k.startswith("x_")) > 0


def test_masked_view_keeps_existing_logs_and_uses_pre_file():
    pre = put("pre-World2", JUL_PRE)
    post = put("post-World2", JUL_POST)
    post_unit = [u for u in parse_java_source(JUL_POST).units if u.signature == "update(float,int)"][0]
    added = [l.formal_index for l in post_unit.formal_logs][1:]
    view = views.load_view(post_masked("add:2", pre, post, "update(float,int)", "World", added))
    feats = view_features(view, "add_log_post")
    assert feats["l_n_formal"] == 1 and feats["l_dominant_level_DEBUG"] == 1
    # the catch that held only the added log is gone, the other catch keeps e.reset()
    assert feats["m_n_catch"] == 1 and feats["m_n_empty_catch"] == 0 and feats["m_n_catch_without_log"] == 1
    assert feats["m_n_if"] == 1                     # the isLoggable guard is gone

    pre2 = put("pre-Lobby2", SLF_PRE_LAMBDA_BLOCK)
    post2 = put("post-Lobby2", SLF_POST)
    feats2 = view_features(views.load_view(post_masked("add:3", pre2, post2, "join(Player)", "Lobby", [0, 1])),
                           "add_log_post")
    # logger field and slf4j import were added in the same commit: not visible
    assert feats2["f_has_logger_field"] == 0 and feats2["f_framework_none"] == 1
    assert feats2["m_n_if"] == 0 and feats2["l_n_formal"] == 0


def test_add_log_pre_view_is_the_method_before_the_commit():
    pre = put("pre-World3", JUL_PRE)
    post = put("post-World3", JUL_POST)
    inst = add_log_pre("add_log:pre:1", pre, post, "update(float,int)", "World")
    view = views.load_view(inst)
    assert view is not None and view.anchor is None and view.masked == 0
    f_add = code_columns(view_features(view, "add_log"))
    f_pre = code_columns(view_features(views.load_view(pre_view("pre:3", pre, "update(float,int)", "World")),
                                       "multiclass"))
    assert same(f_add, f_pre) == {}
    # the empty catch the developer later logged in is part of the pre-state view
    assert f_add["m_n_empty_catch"] == 1 and f_add["l_n_formal"] == 1
    assert not any(k.startswith("s_") for k in view_features(view, "add_log"))

    # the pre view of a method moved to another class is found through class_path_pre
    moved = dict(inst, instance_id="add_log:pre:2", class_path="Elsewhere", class_path_pre="World")
    assert views.load_view(moved) is not None


def test_domain_path_follows_the_view():
    # the commit moved the file into a network module: the pre view uses the old path
    pre = put("pre-path", JUL_PRE)
    post = put("post-path", JUL_POST)
    paths = {"pre_path": "core/src/game/world/World.java", "post_path": "core/src/net/World.java"}
    a = dict(add_log_pre("add_log:path", pre, post, "update(float,int)", "World"), **paths)
    p = dict(post_masked("add_log_post:path", pre, post, "update(float,int)", "World", []), **paths)
    assert view_features(views.load_view(a), "add_log")["d_network"] == 0
    assert view_features(views.load_view(p), "add_log_post")["d_network"] == 1


def shape_file(body):
    return ("import org.slf4j.Logger;\nclass S {\n    static final Logger log = null;\n"
            "    void f(java.util.List<String> items, boolean c) {\n        " + body + "\n    }\n}\n")


SHAPE_SIG = "f(java.util.List<String>,boolean)"

# statement shapes around an added log: (code with the log, the same code written without it)
MASK_SHAPES = [
    pytest.param('if (log.isDebugEnabled()) { log.debug("d"); }\n        use();', "use();", id="guard"),
    pytest.param('for (String s : items) {\n            use();\n            if (log.isTraceEnabled()) '
                 '{ log.trace("s {}", s); }\n        }', "for (String s : items) {\n            use();\n        }",
                 id="guard_in_loop"),
    pytest.param('if (c) { use(); } else if (items.isEmpty()) { log.warn("empty"); }', "if (c) { use(); }",
                 id="else_if_branch"),
    pytest.param('for (String s : items) { log.debug("x {}", s); }\n        use();', "use();", id="loop_body"),
    pytest.param('items.forEach(s -> log.debug("x {}", s));\n        use();', "use();", id="lambda_body"),
    pytest.param('String msg = "v=" + c;\n        log.info(msg);\n        use();', "use();", id="local_for_log"),
    pytest.param('if (c) { log.warn("c"); } else { use(); }', "if (!c) { use(); }", id="then_branch"),
    pytest.param('if (log.isDebugEnabled()) { String m = "v" + c; log.debug(m); }\n        use();', "use();",
                 id="guard_with_local"),
    # complete masking of try/catch and anonymous classes
    pytest.param('try { use(); } catch (RuntimeException e) { log.error("x", e); }', "use();", id="catch_body"),
    pytest.param('try {\n            use();\n            items.clear();\n        } catch (RuntimeException e) {\n'
                 '            log.error("x", e);\n        }', "use();\n        items.clear();", id="catch_body_multiline"),
    pytest.param('try { use(); } catch (IllegalStateException e) { log.warn("s"); } '
                 'catch (RuntimeException e) { items.clear(); }',
                 "try { use(); } catch (RuntimeException e) { items.clear(); }", id="catch_one_of_two"),
    pytest.param('try { log.info("start"); } catch (RuntimeException e) { items.clear(); }\n        use();', "use();",
                 id="try_body"),
    pytest.param('try { use(); } finally { log.info("done"); }', "use();", id="finally_body"),
    pytest.param('try (java.io.Closeable r = open()) { use(r); } catch (java.io.IOException e) { log.warn("io"); }',
                 "try (java.io.Closeable r = open()) { use(r); }", id="resources_kept"),
    pytest.param('items.forEach(new java.util.function.Consumer<String>() {\n'
                 '            public void accept(String s) { log.debug("x {}", s); }\n        });\n        use();',
                 "use();", id="anon_class"),
    pytest.param('try { use(); log.info("ok"); } catch (RuntimeException e) { }',
                 "try { use(); } catch (RuntimeException e) { }", id="pre_existing_empty_catch_kept"),
    # colon-style switch groups, and locals that only a removed guard or loop header used
    pytest.param('switch (items.size()) { case 0: log.info("none"); break; case 1: use(); break; }',
                 "switch (items.size()) { case 1: use(); break; }", id="case_group"),
    pytest.param('switch (items.size()) { case 0: use(); break; default: log.warn("many"); }',
                 "switch (items.size()) { case 0: use(); break; }", id="default_group"),
    pytest.param('switch (items.size()) { case 0: case 1: log.info("few"); break; case 2: use(); }',
                 "switch (items.size()) { case 2: use(); }", id="case_labels_together"),
    pytest.param('switch (items.size()) { case 0: log.info("none"); break; }\n        use();', "use();",
                 id="switch_body"),
    pytest.param('switch (items.size()) { case 0: log.info("none"); break; case 1: use(); break; '
                 'default: items.clear(); }',
                 "switch (items.size()) { case 0: break; case 1: use(); break; default: items.clear(); }",
                 id="case_kept_when_default"),
    pytest.param('switch (items.size()) { case 0: log.info("none"); case 1: use(); }',
                 "switch (items.size()) { case 0: case 1: use(); }", id="case_fall_through_kept"),
    pytest.param('long n = items.size();\n        if (items.hashCode() != n) { log.warn("x"); }\n        use();',
                 "use();", id="local_for_guard"),
    pytest.param('int n = items.size();\n        for (int i = 0; i < n; i++) { log.debug("i"); }\n        use();',
                 "use();", id="local_for_loop_header"),
]


def masked_and_plain(name, with_log, without):
    pre = put(f"shape-pre-{name}", shape_file(without))
    post = put(f"shape-post-{name}", shape_file(with_log))
    post_unit = [u for u in parse_java_source(shape_file(with_log)).units if u.signature == SHAPE_SIG][0]
    mask = [l.formal_index for l in post_unit.formal_logs]
    v_add = views.load_view(post_masked(f"add:{name}", pre, post, SHAPE_SIG, "S", mask))
    v_pre = views.load_view(pre_view(f"pre:{name}", pre, SHAPE_SIG, "S"))
    return v_add, v_pre


@pytest.mark.parametrize("with_log,without", MASK_SHAPES)
def test_masked_shapes_equal_code_without_log(request, with_log, without):
    import numpy as np
    from scripts.build_graphs import mask_residue
    from src.graphs.builder import build_instance_graph

    v_add, v_pre = masked_and_plain(request.node.callspec.id, with_log, without)
    assert v_add.masked > 0 and not v_add.unit.formal_logs
    f_add = code_columns(view_features(v_add, "add_log_post"), ("m_", "l_", "d_", "x_"))
    f_pre = code_columns(view_features(v_pre, "multiclass"), ("m_", "l_", "d_", "x_"))
    assert same(f_add, f_pre) == {}
    # the graph keeps no emptied container either, and is the graph of the plain code
    assert mask_residue(v_add.instance, v_add) == []
    g_add, g_pre = build_instance_graph(v_add), build_instance_graph(v_pre)
    for k in ("node_type", "node_num", "tok_ptr", "tok_ids", "edge_index", "edge_type"):
        assert np.array_equal(g_add[k], g_pre[k]), k


def test_masking_keeps_the_emptied_method_body():
    v_add, v_pre = masked_and_plain("method_body", 'log.info("only");', "")
    from scripts.build_graphs import mask_residue
    assert mask_residue(v_add.instance, v_add) == ["METHOD"]
    f_add = code_columns(view_features(v_add, "add_log_post"), ("m_", "l_", "d_", "x_"))
    f_pre = code_columns(view_features(v_pre, "multiclass"), ("m_", "l_", "d_", "x_"))
    assert same(f_add, f_pre) == {}


def test_masking_traces_flag_what_masking_leaves():
    shapes = {
        "guard": ('if (log.isDebugEnabled()) { log.debug("d"); }\n        use();', "use();", (False, False)),
        "loop_body": ('for (String s : items) { log.debug("x {}", s); }\n        use();', "use();", (False, False)),
        "lambda_body": ('items.forEach(s -> log.debug("x {}", s));\n        use();', "use();", (False, False)),
        "then_branch": ('if (c) { log.warn("c"); } else { use(); }', "if (!c) { use(); }", (False, False)),
        "local_for_log": ('String msg = "v=" + c;\n        log.info(msg);\n        use();', "use();", (False, False)),
        "local_for_guard": ('long n = items.size();\n        if (items.hashCode() != n) { log.warn("x"); }\n'
                            '        use();', "use();", (False, False)),
    }
    traces = []
    for name, (with_log, without, expected) in shapes.items():
        v_add, v_pre = masked_and_plain("trace-" + name, with_log, without)
        rec = extract.trace_record(v_add)
        assert (rec["more_empty_bodies"], rec["more_unreferenced_locals"]) == expected, name
        assert rec["masked"]
        traces.append(rec)
        # written by hand, an empty lambda or loop body is not a masking trace by itself
        plain = extract.trace_record(views.load_view(post_masked(f"plain:{name}", v_pre.instance["pre_blob"],
                                                                 v_pre.instance["pre_blob"], SHAPE_SIG, "S", [])))
        assert not plain["masked"] and not plain["more_empty_bodies"] and not plain["more_unreferenced_locals"]
        traces.append(plain)
    summary = extract.trace_summary(traces)
    # masking removes everything that existed only for the added log
    assert summary == {"synthetic": {"masked": {"n": 6, "more_empty_bodies": 0, "more_unreferenced_locals": 0},
                                     "unmasked": {"n": 6, "more_empty_bodies": 0, "more_unreferenced_locals": 0}}}
    # an empty if written by the developer is left alone: only ancestors of masked statements change
    dev = put("shape-dev-empty-if", shape_file("if (c) { }\n        use();"))
    v = views.load_view(post_masked("plain:dev", dev, dev, SHAPE_SIG, "S", []))
    assert v.masked == 0 and extract.trace_record(v)["masked"] is False


# method / file / statement features on hand-checked code

FEATURE_SRC = '''package a.b;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.badlogic.gdx.utils.Array;
import static java.lang.Math.max;
public class Units {
    private static final Logger log = LoggerFactory.getLogger(Units.class);
    // a comment line
    public static synchronized int[] load(String path, int n) throws IOException {
        int x = n > 0 ? 1 : 2, y;
        if (path == null) {
            return null;
        } else if (n < 0) {
            throw new IllegalArgumentException("n");
        }
        for (int i = 0; i < n; i++) {
            while (x > 0) {
                x--;
                log.debug("x=" + x, i);
            }
        }
        try {
            read(path);
            log.info("read {}", path);
        } catch (IOException e) {
            log.warn("failed", e);
            log.error("again");
        } catch (RuntimeException r) {
        }
        if (log.isDebugEnabled()) {
            log.debug("done");
        }
        Runnable job = new Runnable() { public void run() { helper(); } };
        return new int[n];
    }
    private Array<String> names() { return null; }
    Units() { this(1); }
    void plain() { System.out.println("p"); }
}
'''


@pytest.fixture(scope="module")
def feature_file():
    return parse_java_source(FEATURE_SRC)


def test_method_features(feature_file):
    load = feature_file.units[0]
    m = method_features(load)
    assert m["m_n_params"] == 2 and m["m_return_array"] == 1 and m["m_is_static"] == 1
    assert m["m_visibility_public"] == 1 and m["m_has_synchronized"] == 1
    assert m["m_n_if"] == 3 and m["m_n_ternary"] == 1 and m["m_n_conditionals"] == 4
    assert m["m_n_loops"] == 2 and m["m_max_nesting"] == 2
    assert m["m_n_try"] == 1 and m["m_n_catch"] == 2 and m["m_n_empty_catch"] == 1
    assert m["m_n_catch_without_log"] == 1
    assert m["m_n_throw"] == 1 and m["m_n_return"] == 2 and m["m_has_early_exit"] == 1
    assert m["m_n_anon_classes"] == 1 and m["m_n_lambdas"] == 0
    # x, y, i, job (catch parameters are not local variables)
    assert m["m_n_var_decls"] == 4
    # read, 5 logs, isDebugEnabled, helper (object creations excluded)
    assert m["m_n_calls"] == 8

    names, ctor, plain = feature_file.units[1:]
    assert method_features(names)["m_return_collection"] == 1
    assert method_features(names)["m_visibility_private"] == 1
    mc = method_features(ctor)
    assert mc["m_return_none"] == 1 and mc["m_is_constructor"] == 1 and mc["m_visibility_package"] == 1
    mp = method_features(plain)
    assert mp["m_return_void"] == 1 and mp["m_has_early_exit"] == 0


def test_log_context_features(feature_file):
    load = feature_file.units[0]
    m = method_features(load)
    l = log_context_features(load, m["m_loc"])
    assert l["l_n_formal"] == 5 and l["l_n_informal"] == 0 and l["l_has_formal"] == 1
    assert l["l_dominant_level_DEBUG"] == 1 and l["l_mean_level_ord"] == pytest.approx((2 + 3 + 4 + 5 + 2) / 5)
    assert l["l_n_logs_in_catch"] == 2 and l["l_n_logs_in_loop"] == 1
    assert l["l_frac_catch_with_log"] == 0.5
    plain = feature_file.units[3]
    lp = log_context_features(plain, 1)
    assert lp["l_n_informal"] == 1 and lp["l_dominant_level_NONE"] == 1
    assert math.isnan(lp["l_mean_level_ord"]) and math.isnan(lp["l_frac_catch_with_log"])


def test_dominant_level_ties_go_to_lower_ordinal():
    pf = parse_java_source('class A { void f(){ log.warn("a"); log.info("b"); log.warn("c"); log.info("d"); } }')
    assert dominant_level(pf.units[0].formal_logs) == "INFO"


def test_file_features(feature_file):
    f = file_features(feature_file)
    assert f["f_n_methods"] == 4 and f["f_n_formal_logs"] == 5 and f["f_n_informal"] == 1
    assert f["f_n_imports"] == 4 and f["f_import_diversity"] == 3   # org.slf4j, com.badlogic, java.lang
    assert f["f_has_logger_field"] == 1 and f["f_framework_slf4j"] == 1
    assert f["f_dominant_level_DEBUG"] == 1
    assert f["f_log_density"] == pytest.approx(5000 / feature_file.sloc)
    assert f["f_comment_density"] == pytest.approx(1 / feature_file.sloc)
    bare = file_features(parse_java_source('class B { int log; void f(){ } }'))
    assert bare["f_has_logger_field"] == 0 and bare["f_framework_none"] == 1 and math.isnan(bare["f_mean_level_ord"])


def test_statement_features(feature_file):
    load = feature_file.units[0]
    f = file_features(feature_file)
    logs = {l.call_text.split("(")[0] + str(l.formal_index): l for l in load.formal_logs}
    dom = dominant_level(load.formal_logs)

    def s_of(key):
        return statement_features(load, logs[key], dom, "DEBUG", f["f_mean_level_ord"])

    s = s_of("log.warn2")
    assert s["s_level_WARN"] == 1 and s["s_level_ord"] == 4
    assert s["s_in_catch"] == 1 and s["s_in_try_body"] == 0 and s["s_in_loop"] == 0
    assert s["s_has_exception_arg"] == 1 and s["s_n_args"] == 2 and s["s_msg_len"] == len("failed")
    assert s["s_n_neighbor_logs"] == 1 and s["s_neighbor_warn_error"] == 1
    assert s["s_level_eq_method_dominant"] == 0 and s["s_framework_slf4j"] == 1
    assert s["s_level_minus_file_mean"] == pytest.approx(4 - f["f_mean_level_ord"])

    s = s_of("log.debug0")
    assert s["s_in_loop"] == 1 and s["s_depth"] == 2 and s["s_has_concat"] == 1
    assert s["s_level_eq_method_dominant"] == 1 and s["s_level_eq_file_dominant"] == 1
    assert s["s_is_guarded"] == 0

    s = s_of("log.info1")
    assert s["s_in_try_body"] == 1 and s["s_in_catch"] == 0 and s["s_has_exception_arg"] == 0

    s = s_of("log.debug4")
    assert s["s_is_guarded"] == 1 and s["s_in_if"] == 1 and s["s_in_else"] == 0
    assert 0 < s["s_rel_position"] <= 1


def test_statement_in_else_lambda_and_unknown_level():
    pf = parse_java_source('''class A { void f(){
        if (a) { x(); } else { logger.log(level, "v"); }
        list.forEach(o -> LOG.info("lam"));
    } }''')
    u = pf.units[0]
    s0 = statement_features(u, u.formal_logs[0], "NONE", "NONE", math.nan)
    assert s0["s_in_else"] == 1 and s0["s_in_if"] == 0
    assert s0["s_level_UNKNOWN"] == 1 and s0["s_level_ord"] == 0
    assert math.isnan(s0["s_level_minus_file_mean"]) and s0["s_level_eq_file_dominant"] == 0
    s1 = statement_features(u, u.formal_logs[1], "INFO", "INFO", 3.0)
    assert s1["s_in_lambda_or_anon"] == 1 and s1["s_n_neighbor_logs"] == 0


# history: strictly prior commits, renames followed

def day(d):
    return f"2020-01-{d + 1:02d}T00:00:00+00:00"


def write_mining(root, repo, commits, file_changes, events, methods_changed):
    d = root / repo
    d.mkdir(parents=True, exist_ok=True)
    for name, rows in (("commits", commits), ("file_changes", file_changes),
                       ("events", events), ("methods_changed", methods_changed)):
        with open(d / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    summary = {"repo": repo, "n_commits": len(commits), "file_changes_rows": len(file_changes),
               "events": len(events), "methods_changed": len(methods_changed)}
    with open(d / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f)


def synthetic_history(tmp_path):
    authors = {0: "A", 1: "A", 2: "B", 3: "A", 4: "B", 5: "A", 6: "A"}
    commits = [{"repo": "hist", "commit_id": f"c{t}", "topo_index": t, "timestamp": day(t),
                "author_id": authors[t], "is_merge": t == 3} for t in range(7)]

    def fc(t, ct, old, new, a, d):
        return {"repo": "hist", "commit_id": f"c{t}", "topo_index": t, "change_type": ct,
                "old_path": old, "new_path": new, "lines_added": a, "lines_deleted": d}

    file_changes = [
        fc(0, "A", None, "src/Old.java", 10, 0),
        fc(0, "A", None, "src/Gone.java", 4, 0),
        fc(1, "M", "src/Old.java", "src/Old.java", 5, 2),
        fc(1, "A", None, "src/Other.java", 3, 0),
        fc(2, "R", "src/Old.java", "src/New.java", 1, 1),
        fc(2, "D", "src/Gone.java", None, 0, 4),
        fc(4, "M", "src/New.java", "src/New.java", 3, 3),
        fc(4, "A", None, "src/Gone.java", 2, 0),
        fc(5, "M", "src/New.java", "src/New.java", 1, 0),
        fc(6, "M", "src/Gone.java", "src/Gone.java", 1, 0),
    ]

    def ev(t, path, author, style="formal", sig="bar()"):
        return {"repo": "hist", "commit_id": f"c{t}", "topo_index": t, "author_id": author,
                "logging_style": style, "file_path": path, "pre_path": path, "post_path": path,
                "class_path": "Foo", "method_signature": sig, "event_label": "ADD_LOG"}

    events = [
        ev(1, "src/Old.java", "A"),
        ev(1, "src/Old.java", "A", style="informal_print"),
        ev(1, "src/Other.java", "A"),
        ev(4, "src/New.java", "B"),
        ev(5, "src/New.java", "A"),           # same commit as the instance: excluded
    ]

    def mc(t, path):
        return {"repo": "hist", "commit_id": f"c{t}", "topo_index": t, "pre_path": path, "post_path": path,
                "class_path": "Foo", "signature_pre": "bar()", "signature_post": "bar()"}

    methods_changed = [mc(1, "src/Old.java"), mc(4, "src/New.java"), mc(5, "src/New.java")]
    write_mining(tmp_path, "hist", commits, file_changes, events, methods_changed)
    return build_history_index("hist", tmp_path)


def hist_instance(t, path, author="A"):
    return {"instance_id": f"i{t}", "repo": "hist", "commit_id": f"c{t}", "topo_index": t,
            "timestamp": day(t), "author_id": author, "pre_path": path, "post_path": path,
            "class_path": "Foo", "signature_pre": "bar()", "signature_post": "bar()"}


def test_history_strictly_prior_and_follows_rename(tmp_path):
    idx = synthetic_history(tmp_path)
    h = history_features(idx, hist_instance(5, "src/New.java"))
    assert list(h) == HISTORY_COLUMNS
    assert h["h_repo_age_days"] == pytest.approx(5.0)
    assert h["h_commit_index"] == pytest.approx(math.log1p(4))   # c0, c1, c2, c4 (c3 merge, c5 itself)
    assert h["h_file_prior_commits"] == 4                      # c0, c1 (as Old.java), c2, c4
    assert h["h_file_prior_churn"] == pytest.approx(math.log1p(10 + 7 + 2 + 6))
    assert h["h_days_since_file_change"] == pytest.approx(1.0)
    assert h["h_file_prior_log_events"] == 2                   # c1 on Old.java + c4; c5 excluded
    assert h["h_method_prior_log_events"] == 2
    assert h["h_method_prior_changes"] == 2                    # c5 row excluded
    assert h["h_author_prior_commits"] == 2                    # c0, c1 (c3 is a merge)
    assert h["h_author_prior_log_events"] == 2                 # c1 Old + c1 Other
    assert h["h_repo_prior_log_event_rate"] == pytest.approx(3 / 4)


def test_history_at_rename_commit_and_readded_file(tmp_path):
    idx = synthetic_history(tmp_path)
    # instance in the renaming commit, keyed by the old path
    h = history_features(idx, hist_instance(2, "src/Old.java", author="B"))
    assert h["h_file_prior_commits"] == 2 and h["h_file_prior_log_events"] == 1
    assert h["h_author_prior_commits"] == 0
    # Gone.java was deleted at c2 and added again at c4: a new lineage
    h = history_features(idx, hist_instance(6, "src/Gone.java"))
    assert h["h_file_prior_commits"] == 1 and h["h_file_prior_churn"] == pytest.approx(math.log1p(2))
    # no history at all for the first commit
    h = history_features(idx, hist_instance(0, "src/Old.java"))
    assert h["h_file_prior_commits"] == 0 and math.isnan(h["h_days_since_file_change"])
    assert h["h_repo_prior_log_event_rate"] == 0 and h["h_repo_age_days"] == 0


def linear_commits(repo, n):
    return [{"repo": repo, "commit_id": f"c{t}", "topo_index": t, "timestamp": day(t),
             "author_id": "A", "is_merge": False} for t in range(n)]


def change(repo, t, ct, old, new, added=1, deleted=0):
    return {"repo": repo, "commit_id": f"c{t}", "topo_index": t, "change_type": ct,
            "old_path": old, "new_path": new, "lines_added": added, "lines_deleted": deleted}


def method_row(repo, t, path, cls_pre, cls, sig_pre, sig_post):
    return {"repo": repo, "commit_id": f"c{t}", "topo_index": t, "pre_path": path, "post_path": path,
            "class_path_pre": cls_pre, "class_path": cls, "signature_pre": sig_pre,
            "signature_post": sig_post, "pre_ordinal": 0, "post_ordinal": 0}


def formal_event(repo, t, label, path, cls, sig, scope="modified_method"):
    return {"repo": repo, "commit_id": f"c{t}", "topo_index": t, "author_id": "A",
            "logging_style": "formal", "scope": scope, "event_label": label, "file_path": path,
            "pre_path": None if scope == "new_file" else path, "post_path": path,
            "class_path": cls, "method_signature": sig}


def wp4_instance(repo, t, path, cls, sig):
    # what the mining stage writes: the post-state class_path only, no class_path_pre
    return {"instance_id": f"i{t}", "repo": repo, "commit_id": f"c{t}", "topo_index": t,
            "timestamp": day(t), "author_id": "A", "pre_path": path, "post_path": path,
            "class_path": cls, "signature_pre": sig, "signature_post": sig, "pre_ordinal": 0}


def test_method_history_follows_class_and_signature_changes(tmp_path):
    path = "src/Foo.java"
    file_changes = [change("mh", 0, "A", None, path)] + [change("mh", t, "M", path, path) for t in range(1, 6)]
    methods_changed = [
        method_row("mh", 1, path, "Foo", "Foo", "bar()", "bar()"),
        method_row("mh", 2, path, "Foo", "Baz", "bar()", "bar()"),        # class renamed
        method_row("mh", 3, path, "Baz", "Baz", "bar()", "bar(int)"),     # signature changed
        method_row("mh", 4, path, "Baz", "Baz", "bar(int)", "bar(int)"),
        method_row("mh", 5, path, "Baz", "Baz", "bar(int)", "bar(int)"),
    ]
    events = [
        formal_event("mh", 0, "ADD_LOG", path, "Foo", "bar()", scope="new_file"),
        formal_event("mh", 1, "ADD_LOG", path, "Foo", "bar()"),
        # recorded under the pre-state signature, unlike the ADD_LOG of the same commit
        formal_event("mh", 3, "REMOVE_LOG", path, "Baz", "bar()"),
        formal_event("mh", 3, "ADD_LOG", path, "Baz", "bar(int)"),
        formal_event("mh", 4, "ADD_LOG", path, "Baz", "other()", scope="new_method"),
    ]
    write_mining(tmp_path, "mh", linear_commits("mh", 6), file_changes, events, methods_changed)
    idx = build_history_index("mh", tmp_path)

    # the class is renamed in the instance commit: the instance only knows "Baz"
    h = history_features(idx, wp4_instance("mh", 2, path, "Baz", "bar()"))
    assert h["h_method_prior_changes"] == 1 and h["h_method_prior_log_events"] == 2
    # after the class and signature changes: c1-c3 rows, both events of c3 count
    h = history_features(idx, wp4_instance("mh", 4, path, "Baz", "bar(int)"))
    assert h["h_method_prior_changes"] == 3 and h["h_method_prior_log_events"] == 4
    h = history_features(idx, wp4_instance("mh", 5, path, "Baz", "bar(int)"))
    assert h["h_method_prior_changes"] == 4 and h["h_method_prior_log_events"] == 4
    # an instance without its own row falls back to the key's method before the commit
    h = history_features(idx, dict(wp4_instance("mh", 5, path, "Baz", "bar(int)"), pre_ordinal=7))
    assert h["h_method_prior_changes"] == 4 and h["h_method_prior_log_events"] == 4


def test_file_lineage_survives_rename_on_parallel_branch(tmp_path):
    # c2 renames Lib.java on one branch; c3, after it in topo order, changes Lib.java on another
    file_changes = [
        change("pb", 0, "A", None, "src/Lib.java", 10),
        change("pb", 1, "M", "src/Lib.java", "src/Lib.java", 2, 1),
        change("pb", 2, "R", "src/Lib.java", "src/Mgr.java", 0, 0),
        change("pb", 3, "M", "src/Lib.java", "src/Lib.java", 4),
        change("pb", 4, "M", "src/Mgr.java", "src/Mgr.java", 1, 1),
    ]
    methods_changed = [method_row("pb", 1, "src/Lib.java", "Lib", "Lib", "f()", "f()"),
                       dict(method_row("pb", 2, "src/Lib.java", "Lib", "Mgr", "f()", "f()"), post_path="src/Mgr.java"),
                       method_row("pb", 3, "src/Lib.java", "Lib", "Lib", "f()", "f()"),
                       method_row("pb", 4, "src/Mgr.java", "Mgr", "Mgr", "f()", "f()")]
    events = [formal_event("pb", 1, "ADD_LOG", "src/Lib.java", "Lib", "f()")]
    write_mining(tmp_path, "pb", linear_commits("pb", 5), file_changes, events, methods_changed)
    idx = build_history_index("pb", tmp_path)
    h = history_features(idx, wp4_instance("pb", 3, "src/Lib.java", "Lib", "f()"))
    # topo order: the rename on the other branch counts as prior, like any parallel commit
    assert h["h_file_prior_commits"] == 3
    assert h["h_file_prior_churn"] == pytest.approx(math.log1p(13))
    # the class was renamed on the other branch too; the old key keeps its method lineage
    assert h["h_method_prior_changes"] == 2 and h["h_method_prior_log_events"] == 1
    h = history_features(idx, wp4_instance("pb", 4, "src/Mgr.java", "Mgr", "f()"))
    assert h["h_file_prior_commits"] == 4 and h["h_method_prior_changes"] == 3


def test_history_requires_complete_mining_output(tmp_path):
    idx = synthetic_history(tmp_path)
    d = tmp_path / "hist"
    assert set(idx["inputs_sha1"]) == {"commits.jsonl", "file_changes.jsonl", "events.jsonl",
                                       "methods_changed.jsonl", "summary.json"}
    assert idx["inputs_sha1"]["events.jsonl"] == hashlib.sha1((d / "events.jsonl").read_bytes()).hexdigest()

    full = (d / "events.jsonl").read_text(encoding="utf-8")
    # a table cut short while the miner rewrites it, or left empty
    (d / "events.jsonl").write_text("".join(full.splitlines(keepends=True)[:-1]), encoding="utf-8")
    with pytest.raises(ValueError, match="partial or stale"):
        build_history_index("hist", tmp_path)
    (d / "events.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="partial or stale"):
        build_history_index("hist", tmp_path)
    (d / "events.jsonl").write_text(full, encoding="utf-8")
    build_history_index("hist", tmp_path)

    (d / "methods_changed.jsonl").unlink()
    with pytest.raises(FileNotFoundError, match="methods_changed"):
        build_history_index("hist", tmp_path)
    write_mining(tmp_path, "hist2", [], [], [], [])
    (tmp_path / "hist2" / "summary.json").unlink()
    with pytest.raises(FileNotFoundError, match="summary"):
        build_history_index("hist2", tmp_path)


# orchestration and label independence on a synthetic balanced set

TEMPLATES = [
    ("void a{i}(int n) {{\n        int s = 0;\n        for (int k = 0; k < n; k++) {{\n            s += k;\n{log}        }}\n        use(s);\n    }}", "a{i}(int)"),
    ("int b{i}(String p) {{\n        if (p == null) {{\n{log}            return -1;\n        }}\n        return p.length();\n    }}", "b{i}(String)"),
    ("void c{i}() {{\n        try {{\n            open();\n        }} catch (Exception e) {{\n{log}            close();\n        }}\n    }}", "c{i}()"),
    ("public Object d{i}(Map<String, Object> m, String k) {{\n        Object v = m.get(k);\n{log}        return v;\n    }}", "d{i}(Map<String,Object>,String)"),
]


def template_file(body):
    return ('package g;\nimport java.util.logging.Logger;\nclass G {\n'
            '    static final Logger LOG = Logger.getLogger("g");\n'
            '    void other() { LOG.info("o"); }\n'
            f'    {body}\n'
            '    void tail() { LOG.warning("t"); }\n}\n')


def synthetic_set(tmp_path, task):
    """Balanced instances: positives and negatives built from the same code templates."""
    instances = []
    n = 0
    for i in range(3):
        for tpl, sig_t in TEMPLATES:
            sig = sig_t.format(i=i)
            log_line = f'            LOG.info("event {i}");\n'
            no_log = template_file(tpl.format(i=i, log=""))
            with_log = template_file(tpl.format(i=i, log=log_line))
            for label in (1, 0):
                n += 1
                iid = f"{task}:synthetic:{n:04d}"
                if task == "add_log_post":
                    pre = put(f"{task}-pre-{n}", no_log)
                    post = put(f"{task}-post-{n}", with_log if label else no_log)
                    inst = post_masked(iid, pre, post, sig, "G", [0] if label else [])
                elif task == "add_log":
                    pre = put(f"{task}-pre-{n}", no_log)
                    post = put(f"{task}-post-{n}", with_log if label else no_log)
                    inst = add_log_pre(iid, pre, post, sig, "G")
                else:
                    pre = put(f"{task}-pre-{n}", with_log)
                    inst = pre_view(iid, pre, sig, "G", anchor=0)
                inst.update({"instance_id": iid, "task": task, "label": label, "topo_index": n % 7,
                             "commit_id": f"c{n % 7}", "timestamp": day(n % 7)})
                instances.append(inst)
    inst_dir = tmp_path / "instances"
    inst_dir.mkdir(exist_ok=True)
    with open(inst_dir / f"{task}.jsonl", "w", encoding="utf-8") as f:
        for inst in reversed(instances):
            f.write(json.dumps(inst) + "\n")
    commits = [{"repo": "synthetic", "commit_id": f"c{t}", "topo_index": t, "timestamp": day(t),
                "author_id": "a1", "is_merge": False} for t in range(7)]
    write_mining(tmp_path / "mining", "synthetic", commits, [], [], [])
    return instances


@pytest.mark.parametrize("task", ["add_log", "add_log_post", "remove_log"])
def test_no_feature_is_constant_by_label(tmp_path, task):
    instances = synthetic_set(tmp_path, task)
    df, failures, summary = extract_task(task, workers=1, instances_dir=tmp_path / "instances",
                                         mining_dir=tmp_path / "mining", out_dir=tmp_path / "out", verbose=False)
    assert failures == [] and len(df) == len(instances)
    labels = df["instance_id"].map({i["instance_id"]: i["label"] for i in instances})
    pos, neg = df[labels == 1], df[labels == 0]
    assert len(pos) == len(neg)
    for col in feature_columns(task):
        p, q = pos[col].dropna().unique(), neg[col].dropna().unique()
        assert not (len(p) == 1 and len(q) == 1 and p[0] != q[0]), col
    if task in ("add_log", "add_log_post"):
        # the pre-state (or masked) positive is the negative's code: every code feature matches pairwise
        code = [c for c in feature_columns(task) if not c.startswith("h_")]
        a = pos[code].reset_index(drop=True)
        b = neg[code].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
    if task == "add_log_post":
        # no masked view kept a trace of its log (the templates hold other statements too)
        assert summary["masking_traces"] == {"synthetic": {
            "masked": {"n": len(pos), "more_empty_bodies": 0, "more_unreferenced_locals": 0},
            "unmasked": {"n": len(neg), "more_empty_bodies": 0, "more_unreferenced_locals": 0}}}
    else:
        assert "masking_traces" not in summary


def test_extract_task_outputs(tmp_path):
    instances = synthetic_set(tmp_path, "remove_log")
    broken = dict(instances[0], instance_id="remove_log:synthetic:9999", signature_pre="missing()")
    bad_anchor = dict(instances[1], instance_id="remove_log:synthetic:9998", anchor_pre_idx=7)
    with open(tmp_path / "instances" / "remove_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(broken) + "\n")
        f.write(json.dumps(bad_anchor) + "\n")
    out = tmp_path / "out"
    extract_task("remove_log", workers=1, instances_dir=tmp_path / "instances",
                 mining_dir=tmp_path / "mining", out_dir=out, verbose=False)

    df = pd.read_csv(out / "remove_log.csv")
    cols = feature_columns("remove_log")
    assert list(df.columns) == ["instance_id"] + cols
    assert list(df["instance_id"]) == sorted(i["instance_id"] for i in instances)
    assert df["d_ctx_category"].dtype == object
    assert set(cols) == set(json.load(open(out / "remove_log_groups.json")))
    groups = json.load(open(out / "remove_log_groups.json"))
    assert set(groups.values()) == {"h", "f", "m", "l", "s", "d", "x"}
    fails = [json.loads(line) for line in open(out / "remove_log_failures.jsonl")]
    reasons = {r["instance_id"]: r["reason"] for r in fails}
    assert reasons == {"remove_log:synthetic:9998": "anchor_pre_idx not in unit: 7",
                       "remove_log:synthetic:9999": "pre unit not found"}
    summary = json.load(open(out / "remove_log_summary.json"))
    assert summary["n_rows"] == len(instances) and summary["n_failures"] == 2
    # the inputs are identified by hash, so a run on stale or partial inputs can be detected
    inputs = summary["inputs_sha1"]
    raw = (tmp_path / "instances" / "remove_log.jsonl").read_bytes()
    assert inputs["instances/remove_log.jsonl"] == hashlib.sha1(raw).hexdigest()
    assert {k for k in inputs if k.startswith("mining/synthetic/")} == {
        f"mining/synthetic/{n}" for n in ("commits.jsonl", "file_changes.jsonl", "events.jsonl",
                                          "methods_changed.jsonl", "summary.json")}

    # booleans are 0/1 and the add_log table has no statement columns
    assert set(df["s_in_catch"].unique()) <= {0, 1}
    assert not any(c.startswith("s_") for c in feature_columns("add_log"))
    assert feature_columns("add_log_post") == feature_columns("add_log")
    assert set(STATEMENT_TASKS) == {"remove_log", "change_level"}


def test_limit_runs_keep_out_of_the_features_folder(tmp_path, monkeypatch):
    official = tmp_path / "features"
    monkeypatch.setattr(extract, "FEATURES_DIR", official)
    assert extract.output_dir() == official and extract.output_dir(None, 5) == official / "limit5"
    assert extract.output_dir(tmp_path / "scratch", 5) == tmp_path / "scratch"
    with pytest.raises(ValueError):
        extract.output_dir(official, 5)

    synthetic_set(tmp_path, "remove_log")
    kw = dict(workers=1, instances_dir=tmp_path / "instances", mining_dir=tmp_path / "mining", verbose=False)
    df, _, summary = extract_task("remove_log", limit=3, **kw)
    assert len(df) == 3 and summary["limit"] == 3
    assert (official / "limit3" / "remove_log.csv").exists() and not (official / "remove_log.csv").exists()
    with pytest.raises(ValueError):
        extract_task("remove_log", limit=3, out_dir=official, **kw)
    assert not (official / "remove_log.csv").exists()


def test_task_all_runs_every_instances_file(tmp_path, monkeypatch):
    from scripts import extract_features

    for task in ("add_log", "add_log_post", "remove_log"):
        (tmp_path / f"{task}.jsonl").write_text("")
    calls = []
    monkeypatch.setattr(extract_features, "extract_task", lambda task, **kw: calls.append((task, kw["out_dir"])))
    monkeypatch.setattr("sys.argv", ["extract_features", "--task", "all", "--instances-dir", str(tmp_path)])
    extract_features.main()
    assert calls == [("add_log", None), ("add_log_post", None), ("remove_log", None)]


def test_failure_reason_names_missing_masked_statements():
    from scripts import build_graphs

    src = put("fail-all-idx", shape_file('use();\n        log.info("a");'))
    inst = dict(post_masked("add_log_post:fail", src, src, SHAPE_SIG, "S", [0]), mask_post_all_idx=[0, 5])
    assert views.load_view(inst) is None
    assert extract.failure_reason(inst) == "mask_post_all_idx not in unit: [5]"
    assert build_graphs.failure_reason(inst) == "mask_post_all_idx not in unit: [5]"
    # formal indices are checked first
    inst = dict(inst, mask_post_idx=[0, 2])
    assert extract.failure_reason(inst) == build_graphs.failure_reason(inst) == "mask_post_idx not in unit: [2]"
    assert views.load_view(dict(inst, mask_post_idx=[0], mask_post_all_idx=[0])) is not None


def test_extract_chunk_parses_each_file_version_once_and_keeps_one(monkeypatch):
    a = put("chunk-a", FEATURE_SRC)
    b = put("chunk-b", JUL_PRE)
    chunk = [pre_view(f"remove_log:chunk:a{i}", a, "load(String,int)", "Units", anchor=i) for i in range(5)]
    chunk += [pre_view(f"remove_log:chunk:b{i}", b, "update(float,int)", "World", anchor=0) for i in range(2)]
    parses = []
    real = views.parse_java_source
    monkeypatch.setattr(views, "parse_java_source", lambda src: parses.append(1) or real(src))
    rows, failures, _ = extract.extract_chunk(("remove_log", chunk))
    assert failures == [] and len(rows) == 7
    assert len(parses) == 2
    # parsed trees of earlier groups are dropped: memory stays at one parsed file per worker
    assert list(views._parse_cache) == [("synthetic", "chunk-b")]


def test_features_ignore_label_fields(tmp_path):
    instances = synthetic_set(tmp_path, "remove_log")
    a = view_features(views.load_view(instances[0]), "remove_log")
    flipped = dict(instances[0], label=1 - instances[0]["label"], sample_role="negative", neg_rank=3)
    b = view_features(views.load_view(flipped), "remove_log")
    assert same(a, b) == {}
