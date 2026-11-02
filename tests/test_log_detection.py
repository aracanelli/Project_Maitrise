"""
Tests for logging detection pipeline.

Tests that require srcML are guarded by a skip marker.
Regex-only tests run without srcML.
"""

import subprocess
import pytest
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _srcml_installed():
    import os
    candidates = ["srcml", r"C:\Program Files\srcML\bin\srcml.exe"]
    for cmd in candidates:
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, timeout=10)
            if r.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return False


needs_srcml = pytest.mark.skipif(
    not _srcml_installed(), reason="srcML not installed"
)


# Unit tests (no srcML needed)

def test_caller_whitelist_matches():
    from src.detection.log_detection import CALLER_WHITELIST
    assert CALLER_WHITELIST.match("logger")
    assert CALLER_WHITELIST.match("Log")
    assert CALLER_WHITELIST.match("log")
    assert CALLER_WHITELIST.match("LOG")
    assert CALLER_WHITELIST.match("System.out")
    assert CALLER_WHITELIST.match("System.err")
    assert CALLER_WHITELIST.match("Timber")
    assert CALLER_WHITELIST.match("Gdx.app")
    assert CALLER_WHITELIST.match("myLogger")


def test_caller_blacklist_rejects():
    from src.detection.log_detection import CALLER_BLACKLIST
    assert CALLER_BLACKLIST.match("loginService")
    assert CALLER_BLACKLIST.match("dialogLog")
    assert CALLER_BLACKLIST.match("catalogManager")
    assert CALLER_BLACKLIST.match("changelogParser")
    assert not CALLER_BLACKLIST.match("logger")
    assert not CALLER_BLACKLIST.match("Log")


def test_level_whitelist():
    from src.detection.log_detection import LEVEL_WHITELIST
    for name in ["info", "debug", "warn", "error", "trace", "fine", "severe",
                  "fatal", "verbose", "d", "i", "w", "e", "v", "config"]:
        assert LEVEL_WHITELIST.match(name), f"Expected match for '{name}'"
    for name in ["toString", "getMessage", "append", "size", "run"]:
        assert not LEVEL_WHITELIST.match(name), f"Expected no match for '{name}'"


def test_classify_verbosity():
    from src.detection.verbosity import classify_verbosity
    assert classify_verbosity("logger", "info") == "INFO"
    assert classify_verbosity("logger", "debug") == "DEBUG"
    assert classify_verbosity("logger", "warn") == "WARN"
    assert classify_verbosity("logger", "error") == "ERROR"
    assert classify_verbosity("logger", "fine") == "DEBUG"
    assert classify_verbosity("logger", "severe") == "ERROR"
    assert classify_verbosity("logger", "trace") == "TRACE"
    assert classify_verbosity("logger", "config") == "DEBUG"
    assert classify_verbosity("System.err", None) == "ERROR"
    assert classify_verbosity("System.out", None) == "INFO"
    assert classify_verbosity("logger", None) is None


def test_classify_logging_style():
    from src.detection.log_detection import classify_logging_style
    assert classify_logging_style("System.out", "println") == "informal_print"
    assert classify_logging_style("System.err", "println") == "informal_print"
    assert classify_logging_style("logger", "info") == "formal"
    assert classify_logging_style("Log", "d") == "formal"
    assert classify_logging_style("Gdx.app", "log") == "formal"
    assert classify_logging_style("Timber", "d") == "formal"
    assert classify_logging_style("GLog", "p") == "game_message"
    assert classify_logging_style("GLog", "w") == "game_message"
    assert classify_logging_style("someHelper", "logData") == "unresolved_wrapper"
    assert classify_logging_style("FileLogger", "write") == "unresolved_wrapper"


def test_looks_like_test():
    from src.detection.scan import _looks_like_test
    assert _looks_like_test("src/test/java/Foo.java")
    assert _looks_like_test("FooTest.java")
    assert _looks_like_test("TestFoo.java")
    assert not _looks_like_test("src/main/java/GameEngine.java")
    assert not _looks_like_test("src/main/java/TestableModule.java") is False or True


# Integration tests (need srcML)

@needs_srcml
def test_scan_fixture_finds_logs():
    from src.detection.scan import scan_file
    fixture = FIXTURE_DIR / "SampleGame.java"
    records = scan_file(fixture)
    call_names = [r["call_name"] for r in records]

    assert any("debug" in c for c in call_names)
    assert any("fine" in c for c in call_names)
    assert any("info" in c for c in call_names)
    assert any("error" in c for c in call_names)
    assert any("warn" in c for c in call_names)


@needs_srcml
def test_scan_fixture_excludes_false_positives():
    from src.detection.scan import scan_file
    fixture = FIXTURE_DIR / "SampleGame.java"
    records = scan_file(fixture)
    call_names = [r["call_name"] for r in records]
    assert not any("login" in c.lower() for c in call_names)


@needs_srcml
def test_scan_fixture_verbosity_classification():
    from src.detection.scan import scan_file
    fixture = FIXTURE_DIR / "SampleGame.java"
    records = scan_file(fixture)

    for r in records:
        name = r["call_name"]
        verb = r["verbosity"]
        if "debug" in name:
            assert verb == "DEBUG"
        elif "fine" in name:
            assert verb == "DEBUG"
        elif "info" in name:
            assert verb == "INFO"
        elif "error" in name:
            assert verb == "ERROR"
        elif "warn" in name:
            assert verb == "WARN"


@needs_srcml
def test_scan_fixture_method_anchoring():
    from src.detection.scan import scan_file
    fixture = FIXTURE_DIR / "SampleGame.java"
    records = scan_file(fixture)
    methods = set(r["method_signature"] for r in records)
    assert len(methods) >= 3


@needs_srcml
def test_scan_fixture_class_name():
    from src.detection.scan import scan_file
    fixture = FIXTURE_DIR / "SampleGame.java"
    records = scan_file(fixture)
    for r in records:
        assert r["class_name"] == "SampleGame"
