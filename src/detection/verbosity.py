"""
Verbosity (log level) classification.

get_verbosity_type and its level tables are adapted from the replication package of
Zeng et al. (2019), logdetector/metrics.py.

Differences from upstream:
- standalone function, no DB or model imports
- VERBOSE is folded into TRACE
- java.util.logging levels CONFIG, FINE, FINER, FINEST are mapped
- Android shorthand aliases (v, d, i, w, e) are kept
- log(Level.X, ...) / logp(Level.X, ...) take the level from the first argument
  (java.util.logging and Log4j 2); upstream mapped every log(...) to INFO
"""

import re

LEVELS = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
LEVEL_ORD = {lvl: i + 1 for i, lvl in enumerate(LEVELS)}

# Level.WARNING, java.util.logging.Level.FINE, LogLevel.info (Arc)
_LEVEL_ARG = re.compile(r'^(?:[\w.]*\.)?\w*Level\.([A-Za-z]+)$')

_NAME_MAP = {
    'v': 'TRACE', 'verbose': 'TRACE', 'trace': 'TRACE', 'finest': 'TRACE', 'finer': 'TRACE', 'all': 'TRACE',
    'tracef': 'TRACE', 'traceentry': 'TRACE', 'tracefentry': 'TRACE', 'traceexit': 'TRACE',
    'd': 'DEBUG', 'debug': 'DEBUG', 'fine': 'DEBUG', 'config': 'DEBUG', 'debugf': 'DEBUG',
    'i': 'INFO', 'info': 'INFO', 'log': 'INFO', 'print': 'INFO', 'printf': 'INFO', 'println': 'INFO', 'infof': 'INFO',
    'w': 'WARN', 'warn': 'WARN', 'warning': 'WARN', 'warnf': 'WARN',
    'e': 'ERROR', 'err': 'ERROR', 'error': 'ERROR', 'severe': 'ERROR', 'fatal': 'ERROR', 'wtf': 'ERROR',
    'errorf': 'ERROR', 'fatalf': 'ERROR',
}

_LEVEL_ARG_METHODS = {'log', 'logp', 'logrb'}


def level_from_argument(arg_text):
    """Return the normalised level of a 'Level.X' argument, None if it is not a literal level."""
    if arg_text is None:
        return None
    m = _LEVEL_ARG.match("".join(arg_text.split()))
    if not m:
        return None
    return _NAME_MAP.get(m.group(1).lower())


def classify_verbosity(caller, level_name, first_arg=None):
    if caller:
        low_caller = caller.lower()
        if low_caller == 'system.err':
            return 'ERROR'
        if low_caller == 'system.out':
            return 'INFO'

    if level_name is None:
        return None

    low = level_name.lower()

    if low in _LEVEL_ARG_METHODS and not (caller and caller.lower().startswith('gdx.app')):
        from_arg = level_from_argument(first_arg)
        if from_arg is not None:
            return from_arg
        if first_arg is not None:
            flat = "".join(first_arg.split())
            # a level passed through a variable cannot be resolved statically
            if 'level' in flat.lower() or flat.startswith('Level.'):
                return None

    return _NAME_MAP.get(low)
