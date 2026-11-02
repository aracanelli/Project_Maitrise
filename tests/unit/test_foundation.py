"""Tests for method units, verbosity, masking, lexical and domain helpers."""

import pytest

from src.detection.verbosity import classify_verbosity, level_from_argument
from src.features.lexical import subtokens, bucket
from src.parsing.method_units import parse_java_source
from src.dataset.views import mask_statements
from src.features.domain import domain_indicators
from src.parsing.srcml_parser import SRC, normalized_text

JAVA = '''
package a.b;
import java.util.logging.Logger;
import java.util.logging.Level;
class Pkg {
    private static final Logger LOG = Logger.getLogger(Pkg.class.getName());
    Pkg(int x) { LOG.info("ctor " + x); }
    void update(float tpf) {
        for (int i = 0; i < 3; i++) {
            try { run(i); } catch (Exception e) { LOG.log(Level.WARNING, "fail", e); }
        }
        Runnable r = new Runnable() { public void run() { LOG.fine("anon"); } };
        list.forEach(x -> LOG.info("lam"));
        System.out.println("print");
    }
    enum E { A; void f() { LOG.severe("e"); } }
    interface I { default void g() { LOG.finest("i"); } }
}
'''


@pytest.fixture(scope="module")
def parsed():
    return parse_java_source(JAVA)


def test_units_cover_ctor_enum_interface_package_private(parsed):
    sigs = [(u.class_path, u.signature, u.kind) for u in parsed.units]
    assert ("Pkg", "Pkg(int)", "constructor") in sigs
    assert ("Pkg", "update(float)", "method") in sigs
    assert ("Pkg.E", "f()", "method") in sigs
    assert ("Pkg.I", "g()", "method") in sigs
    # the anonymous-class run() belongs to update, not a unit of its own
    assert not any(s[1] == "run()" for s in sigs)


def test_logs_in_anonymous_class_and_lambda_belong_to_enclosing_unit(parsed):
    update = [u for u in parsed.units if u.signature == "update(float)"][0]
    names = [(l.call_name, l.verbosity, l.logging_style) for l in update.logs]
    assert names == [
        ("LOG.log", "WARN", "formal"),
        ("LOG.fine", "DEBUG", "formal"),
        ("LOG.info", "INFO", "formal"),
        ("System.out.println", "INFO", "informal_print"),
    ]
    assert [l.formal_index for l in update.logs] == [0, 1, 2, None]
    assert all(l.framework == "jul" for l in update.formal_logs)
    assert update.logs[0].line == 10


def test_imports_and_framework(parsed):
    assert "java.util.logging.Level" in parsed.imports
    assert parsed.file_framework == "jul"
    assert parsed.sloc > 10


def test_verbosity_reads_level_argument():
    assert classify_verbosity("logger", "log", "Level.SEVERE") == "ERROR"
    assert classify_verbosity("logger", "log", "java.util.logging.Level.FINE") == "DEBUG"
    assert classify_verbosity("Log", "log", "LogLevel.warn") == "WARN"
    assert classify_verbosity("logger", "log", "level") is None
    assert classify_verbosity("Gdx.app", "log", "TAG") == "INFO"
    assert classify_verbosity("Gdx.app", "error", "TAG") == "ERROR"
    assert classify_verbosity("Log", "err", None) == "ERROR"
    assert level_from_argument("Level.WARNING") == "WARN"
    assert level_from_argument('"text"') is None


def test_game_message_is_not_formal():
    pf = parse_java_source('class A { void f(){ GLog.w("hungry"); GLog.p("ok"); Log.info("x"); } }')
    styles = [(l.call_name, l.logging_style, l.verbosity) for l in pf.units[0].logs]
    assert styles == [("GLog.w", "game_message", None), ("GLog.p", "game_message", None), ("Log.info", "formal", "INFO")]


def test_level_change_detected_through_level_argument():
    a = parse_java_source('class A { void f(){ logger.log(Level.INFO, "x"); } }')
    b = parse_java_source('class A { void f(){ logger.log(Level.FINE, "x"); } }')
    c = parse_java_source('class A { void f(){ logger.info("x"); } }')
    va = a.units[0].logs[0].verbosity
    assert va == "INFO" and b.units[0].logs[0].verbosity == "DEBUG"
    assert c.units[0].logs[0].verbosity == va


def test_body_hash_ignores_comments_and_whitespace():
    a = parse_java_source('class A { void f(){ x(); } }')
    b = parse_java_source('class A {\n  void f() {\n    // note\n    x();\n  }\n}')
    c = parse_java_source('class A { void f(){ y(); } }')
    assert a.units[0].body_hash == b.units[0].body_hash
    assert a.units[0].body_hash != c.units[0].body_hash


def test_masking_removes_log_and_empty_guard():
    src = '''class A { void f(){
        if (LOG.isDebugEnabled()) { LOG.debug("a"); }
        try { z(); } catch (E e) { LOG.error("c", e); }
        if (x) LOG.info("b"); else y();
        keep();
    } }'''
    pf = parse_java_source(src)
    u = pf.units[0]
    targets = [l.element for l in u.formal_logs]
    mask_statements(u.element, targets)
    text = normalized_text(u.element)
    assert "LOG.debug" not in text and "LOG.error" not in text and "LOG.info" not in text
    assert "isDebugEnabled" not in text          # empty guard removed
    # the catch emptied by masking is removed and the try left without a handler unwrapped
    assert "catch" not in text and "try" not in text and "z();" in text
    assert "if(!x)y();" in text and "else" not in text   # if (x) log; else y();  ->  if (!x) y();
    assert "keep()" in text


def test_masking_keeps_catch_blocks_it_did_not_empty():
    src = '''class A { void f(){
        try { z(); LOG.info("z"); } catch (E e) { }
        try { w(); } catch (E e) { LOG.warn("w", e); } catch (F g) { g(); }
        try { v(); } catch (E e) { LOG.warn("v", e); } finally { done(); }
        try (R r = open()) { u(); } catch (E e) { LOG.warn("u", e); }
    } }'''
    pf = parse_java_source(src)
    u = pf.units[0]
    mask_statements(u.element, [l.element for l in u.formal_logs])
    text = normalized_text(u.element)
    # an empty catch the developer wrote stays; other clauses keep their try
    assert "try{z();}catch(Ee){}" in text
    assert "try{w();}catch(Fg){g();}" in text
    assert "try{v();}finally{done();}" in text
    assert "try(Rr=open()){u();}" in text and "LOG" not in text


def test_masking_switch_groups_and_guard_locals():
    src = '''class A { void f(int x){
        switch (x) { case 1: LOG.info("one"); break; case 2: two(); break; }
        switch (x) { case 1: LOG.info("one"); break; case 2: two(); break; default: other(); }
        switch (x) { case 3: LOG.info("three"); case 4: four(); }
        switch (x) { case 5: five(); break; default: LOG.warn("x"); }
        switch (x) { case 6 -> LOG.info("six"); case 7 -> seven(); }
        long offset = size();
        if (hash() != offset) { LOG.warn("mismatch"); }
        keep();
    } }'''
    u = parse_java_source(src).units[0]
    mask_statements(u.element, [l.element for l in u.formal_logs])
    text = normalized_text(u.element)
    assert "switch(x){case2:two();break;}" in text
    # with a default, case 1 must stay to keep x == 1 out of it
    assert "switch(x){case1:break;case2:two();break;default:other();}" in text
    assert "switch(x){case3:case4:four();}" in text          # fall-through kept
    assert "switch(x){case5:five();break;}" in text
    assert "case6->;" in text                                # arrow rules are left as they are
    assert "offset" not in text and "size()" not in text and "keep();" in text


def test_masking_dead_locals_follow_logs_and_removed_headers_only():
    src = '''class A { void f(){
        Runnable r = make();
        run(r, () -> LOG.info("done"));
        int n = size();
        while (n-- > 0) { LOG.debug("tick"); }
        keep();
    } }'''
    u = parse_java_source(src).units[0]
    mask_statements(u.element, [l.element for l in u.formal_logs])
    text = normalized_text(u.element)
    # the loop header only counted for the log; the lambda rule takes run(..) with it,
    # so its other arguments are not followed (known limitation)
    assert "size()" not in text and "while" not in text
    assert "run(" not in text and "Runnabler=make();" in text and "keep();" in text


def test_subtokens_and_bucket_stable():
    assert subtokens("updateHUDText_now") == ["update", "hud", "text", "now"]
    assert subtokens("tpf") == ["tpf"]
    assert bucket("update") == bucket("update")
    assert 0 <= bucket("render") < 128


def test_domain_indicators(parsed):
    update = [u for u in parsed.units if u.signature == "update(float)"][0]
    d = domain_indicators(update.element, update.name, update.class_path, "core/src/game/Pkg.java")
    assert d["d_loop"] == 1 and d["d_frame"] == 1 and d["d_frame_param"] == 1
    assert d["d_ctx_category"] == "frame_update" and d["d_is_perf_sensitive"] == 1
    ctor = [u for u in parsed.units if u.kind == "constructor"][0]
    d2 = domain_indicators(ctor.element, ctor.name, ctor.class_path, "core/src/game/Pkg.java")
    assert d2["d_ctx_category"] == "general" and d2["d_is_perf_sensitive"] == 0
    d3 = domain_indicators(ctor.element, "loadTexture", "AssetManager", "core/src/Assets.java")
    assert d3["d_resource"] == 1 and d3["d_ctx_category"] == "subsystem"
