"""
Logging call detection for Java source code.

The _is_logging_call predicate is adapted from the replication package of Zeng et al. (2019),
logdetector/codetransform.py.

Differences from upstream:
- standalone module with no DB or config imports
- Gdx.app added to the caller whitelist for LibGDX games
- 'changelog', 'logfile', 'loggedon' added to the false-positive blacklist
- java.util.logging levels (config, finer, finest) and Arc's err added to the level whitelist
- Android patterns (Log.d, Timber) kept
- player-facing game message logs (SPD GLog) are tagged 'game_message', not formal logging
- the logging framework is inferred from the file imports
- bare calls through a static logger import (`import static arc.util.Log.*; info(..)`)
  and chained `getLogger(..).log(..)` calls are named after their logger before the predicate
- printf-style and entry-tracing level methods (tracef, debugf, traceEntry, ...) are accepted
"""

import re
from src.parsing.srcml_parser import (
    get_call_name, call_has_arguments, get_call_expressions
)

CALLER_WHITELIST = re.compile(
    r'.*?(log|logger|logging'
    r'|(system\.out)|(system\.err)'
    r'|timber'
    r'|(gdx\.app)'
    r').*',
    re.IGNORECASE
)

CALLER_BLACKLIST = re.compile(
    r'.*?(dialog|login|logout|loggedin|loggedout|loggedon'
    r'|catalog|logic|blog|logo'
    r'|changelog|logfile'
    r').*',
    re.IGNORECASE
)

LEVEL_WHITELIST = re.compile(
    r'^(w|e|v|i|d|wtf'
    r'|warn|warning|err|error|verbose|info|debug'
    r'|severe|fine|finer|finest|fatal|trace|config'
    r'|print|printf|println|log|logp'
    r'|tracef|debugf|infof|warnf|errorf|fatalf|traceentry|tracefentry|traceexit'
    r')$',
    re.IGNORECASE
)

# in-game message logs shown to the player (SPD utils/GLog: i/p/n/w/h post to the GameLog UI)
GAME_MESSAGE_CALLERS = {"GLog"}

# project logging wrappers whose names carry no 'log' token (configs/extraction.yaml):
# UCore.log / UCore.error was Mindustry's logging utility before arc's Log (2018)
PROJECT_LOGGER_CALLERS = {"UCore"}
GAME_MESSAGE_LEVELS = {"i", "p", "n", "w", "h"}


def split_call_name(call_name):
    if '.' in call_name:
        caller, level = call_name.rsplit('.', 1)
        return caller, level
    return call_name, None


def is_game_message(caller, level):
    return caller in GAME_MESSAGE_CALLERS and level in GAME_MESSAGE_LEVELS


def is_logging_call(call_xml, call_name=None):
    if not call_has_arguments(call_xml):
        return False
    if call_name is None:
        call_name = get_call_name(call_xml)
    return is_logging_name(call_name)


def is_logging_name(call_name):
    """Upstream caller/level predicate on a dotted call name (arguments checked by the caller)."""
    if not call_name:
        return False

    caller, level = split_call_name(call_name)

    if is_game_message(caller, level):
        return True

    if caller in PROJECT_LOGGER_CALLERS:
        return level is not None and LEVEL_WHITELIST.match(level) is not None

    if not CALLER_WHITELIST.match(caller):
        return False

    if CALLER_BLACKLIST.match(caller):
        return False

    if level is not None and not LEVEL_WHITELIST.match(level):
        return False

    return True


def static_log_names(imports):
    """Bare names usable as logging calls through static imports: {name: logger class}.

    `static arc.util.Log.*` makes every level method of Log callable as info(..), err(..);
    `static arc.util.Log.info` only info(..).
    """
    names = {}
    for imp in imports:
        if not imp.startswith("static"):
            continue
        body = imp[len("static"):].strip()
        parts = body.split(".")
        if len(parts) < 2:
            continue
        if parts[-1] == "*":
            owner = parts[-2]
            members = None
        else:
            owner, members = parts[-2], [parts[-1]]
        if not CALLER_WHITELIST.match(owner) or CALLER_BLACKLIST.match(owner):
            continue
        if owner.lower() in ("system.out", "system.err") or owner in ("Math", "Mathf", "StrictMath"):
            continue
        if members is None:
            for lvl in _STATIC_LEVEL_NAMES:
                names.setdefault(lvl, owner)
        else:
            for m in members:
                if LEVEL_WHITELIST.match(m) and m.lower() not in ("print", "printf", "println", "log", "logp"):
                    names.setdefault(m, owner)
    return names


_STATIC_LEVEL_NAMES = ["trace", "debug", "info", "warn", "warning", "err", "error", "fatal",
                       "severe", "fine", "finer", "finest", "config"]


def find_logging_calls_in_method(method_xml):
    calls = get_call_expressions(method_xml)
    return [c for c in calls if is_logging_call(c)]


_INFORMAL_CALLERS = {"system.out", "system.err"}

_FORMAL_CALLERS = re.compile(
    r'^(logger|log|LOG|LOGGER|Log|Timber'
    r'|Gdx\.app'
    r')$',
    re.IGNORECASE
)


def classify_logging_style(caller, level):
    if is_game_message(caller, level):
        return "game_message"

    if caller and caller.lower() in _INFORMAL_CALLERS:
        return "informal_print"

    if caller and _FORMAL_CALLERS.match(caller):
        return "formal"

    if level and LEVEL_WHITELIST.match(level):
        return "formal"

    return "unresolved_wrapper"


_IMPORT_FRAMEWORKS = [
    ("org.slf4j", "slf4j"),
    ("org.apache.logging.log4j", "log4j"),
    ("org.apache.log4j", "log4j"),
    ("org.apache.commons.logging", "jcl"),
    ("java.util.logging", "jul"),
    ("java.lang.System.Logger", "jdk_system"),
    ("com.riiablo.logger", "riiablo"),
    ("arc.util.Log", "arc"),
    ("arc.util.*", "arc"),
    ("android.util.Log", "android"),
]


def file_framework(imports):
    """Logging framework suggested by the file imports (first match in a fixed priority)."""
    for prefix, name in _IMPORT_FRAMEWORKS:
        for imp in imports:
            body = imp[len("static"):].strip() if imp.startswith("static") else imp.strip()
            if body.startswith(prefix):
                return name
    return "none"


def infer_framework(caller, style, imports_framework):
    if style == "informal_print":
        return "stdout"
    if style == "game_message":
        return "game_message"
    if style == "console_reply":
        return "console"
    if caller in PROJECT_LOGGER_CALLERS:
        return caller.lower()
    if caller and caller.lower().startswith("gdx.app"):
        return "gdx"
    if caller == "Log" and imports_framework in ("arc", "android"):
        return imports_framework
    if caller == "Timber":
        return "android"
    if imports_framework != "none":
        return imports_framework
    return "unknown"
