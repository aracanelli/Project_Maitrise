"""Mining rules: statement continuity on the payload,
style conversions, edited moves, printStackTrace and operator console replies."""

from collections import OrderedDict

import git
import pytest

from src.matching.statement_matcher import payload_ratio, pair_conversions
from src.mining import method_differ
from tests.unit.test_mining import _commit, mine_outputs

GAME = '''package game;

import com.badlogic.gdx.Gdx;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

class Game {
    private static final Logger LOG = LoggerFactory.getLogger(Game.class);
    private static final String TAG = "Game";

    void decode(int salt) {
        int k = salt * 2;
        Gdx.app.debug(TAG, "salt: " + salt);
    }

    void setLevel(int n) {
        LOG.info("level set to " + n);
        n++;
    }

    void boot() {
        int a = 1;
        System.out.println("booting engine " + a);
    }

    void save() {
        try { write(); } catch (Exception e) { e.printStackTrace(); }
    }

    void loadAll() {
        int count = 3;
        LOG.debug("loading all resources, count=" + count);
        count--;
    }

    void write() { }
}
'''

SERVER = '''package game;

import static arc.util.Log.*;

class ServerControl {
    ServerControl() {
        info("Server loaded.");
    }

    void registerCommands() {
        handler.register("ban", "<ip>", arg -> {
            info("Banned.");
        });
    }
}
'''


def build(path):
    repo = git.Repo.init(path)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test Dev")
        cw.set_value("user", "email", "dev@example.com")
        cw.set_value("commit", "gpgsign", "false")
        cw.set_value("core", "autocrlf", "false")
    _commit(repo, "root", {"g/Game.java": GAME, "g/ServerControl.java": SERVER})
    game = GAME
    # unrelated statement sharing the Gdx.app prefix, with another level -> not CHANGE_LEVEL
    game = game.replace('Gdx.app.debug(TAG, "salt: " + salt);',
                        'Gdx.app.log(TAG, "cofAlphas: " + java.util.Arrays.toString(alphas));')
    # same statement, level changed -> CHANGE_LEVEL
    game = game.replace('LOG.info("level set to " + n);', 'LOG.warn("level set to " + n);')
    # print -> logger conversion, printStackTrace -> logger conversion
    game = game.replace('System.out.println("booting engine " + a);', 'LOG.info("booting engine " + a);')
    game = game.replace('e.printStackTrace();', 'LOG.error("save failed", e);')
    # extract method: the log moves to a new method with an edited message
    game = game.replace('''        LOG.debug("loading all resources, count=" + count);
        count--;''', '''        count--;
        report(count);''')
    game = game.replace("    void write() { }", '''    void report(int count) {
        LOG.debug("loading all resources: count=" + count);
    }

    void write() { }''')
    server = SERVER.replace('info("Banned.");', 'info("Banned IP.");\n            err("Not found.");')
    head = _commit(repo, "c1", {"g/Game.java": game, "g/ServerControl.java": server})
    return repo, head


@pytest.fixture(scope="module")
def mined(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("v22")
    method_differ._cache = OrderedDict()
    repo, head = build(tmp / "toy")
    summary, rows = mine_outputs(repo, head, tmp / "out")
    return summary, rows


def ev(rows, method):
    # events of the second commit only (the root commit adds every file: new_file scope)
    return [e for e in rows["events"] if e["topo_index"] == 1 and e["method_signature"].startswith(method)]


def test_unrelated_statements_are_not_a_level_change(mined):
    _, rows = mined
    assert not [e for e in rows["events"] if e["event_label"] == "CHANGE_LEVEL" and "decode" in e["method_signature"]]
    row = [r for r in rows["methods_changed"] if r["method_name"] == "decode"][0]
    assert row["uncertain_formal"] == [[0, 0]] and row["uncertain_post_all"] == [0]
    assert row["other_log_change"] is True
    assert any(a.get("uncertain") for a in rows["aux_changes"] if a["signature_pre"].startswith("decode"))


def test_real_level_change_is_kept(mined):
    _, rows = mined
    cl = [e for e in ev(rows, "setLevel") if e["event_label"] == "CHANGE_LEVEL"]
    assert len(cl) == 1 and (cl[0]["pre_level"], cl[0]["post_level"]) == ("INFO", "WARN")
    assert cl[0]["validity_status"] == "core"


def test_style_conversions_are_not_core(mined):
    _, rows = mined
    for method in ("boot", "save"):
        es = ev(rows, method)
        assert {e["event_label"] for e in es} == {"ADD_LOG", "REMOVE_LOG"}, method
        assert all(e["is_relocated"] and e["relocation_kind"] == "style_conversion" for e in es), method
        assert not [e for e in es if e["validity_status"] == "core"], method
    save = [e for e in ev(rows, "save") if e["event_label"] == "REMOVE_LOG"][0]
    assert save["logging_style"] == "informal_print" and save["call_name"] == "e.printStackTrace"


def test_edited_move_is_a_relocation(mined):
    _, rows = mined
    moved = ev(rows, "loadAll") + ev(rows, "report")
    assert {e["event_label"] for e in moved} == {"REMOVE_LOG", "ADD_LOG"}
    assert all(e["is_relocated"] and e["relocation_kind"] == "edited_move" for e in moved)


def test_console_replies_are_not_formal(mined):
    _, rows = mined
    replies = ev(rows, "registerCommands")
    assert replies and all(e["logging_style"] == "console_reply" for e in replies)
    assert all(e["validity_status"] == "non_formal" for e in replies)
    row = [r for r in rows["methods_changed"] if r["method_name"] == "registerCommands"][0]
    assert row["n_pre_formal"] == 0 and row["n_post_formal"] == 0


def test_payload_helpers():
    assert payload_ratio('logger.log(Level.TRACE, "x {0}", s)', 'logger.log(Level.DEBUG, "x {0}", s)') == 1.0
    assert payload_ratio('Gdx.app.debug(TAG, "salt: " + salt)', 'Gdx.app.log(TAG, "cofAlphas: " + a)') < 0.7
    pre = [{"logging_style": "informal_print", "call_name": "System.out.println", "call_text": 'System.out.println("go " + a)'},
           {"logging_style": "formal", "call_name": "LOG.info", "call_text": 'LOG.info("x")'}]
    post = [{"logging_style": "formal", "call_name": "LOG.info", "call_text": 'LOG.info("go " + a)'}]
    assert pair_conversions(pre, post, [0, 1], [0], 0.7) == [(0, 0, 1.0)]


def test_ucore_is_a_project_logger_and_its_migration_is_not_an_addition():
    from src.parsing.method_units import parse_java_source
    from src.matching.statement_matcher import match_statements
    pre = parse_java_source('class A { void f(){ UCore.log("Loading map " + name); UCore.setPrivate(true); } }').units[0]
    post = parse_java_source('class A { void f(){ Log.info("Loading map " + name); } }').units[0]
    assert [(l.call_name, l.logging_style, l.verbosity) for l in pre.logs] == [("UCore.log", "formal", "INFO")]
    as_dicts = lambda u: [{"call_text": l.call_text, "logging_style": l.logging_style} for l in u.logs]
    pairs, removed, added = match_statements(as_dicts(pre), as_dicts(post))
    assert len(pairs) == 1 and not removed and not added
    assert payload_ratio(pre.logs[0].call_text, post.logs[0].call_text) == 1.0
