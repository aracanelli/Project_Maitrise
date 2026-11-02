"""
File-level features (f_) computed on the pre-state file of an instance.

Every task uses the pre-state, so a logger field or import added in the same commit as
an ADD_LOG cannot leak into the features.
Logs are counted over the whole file, including field initialisers and static blocks.
"""

import re

from src.parsing.method_units import collect_logs
from src.parsing.srcml_parser import SRC, flatten_code
from src.features.method_features import DOMINANT_KINDS, level_columns, type_text, is_type_member

FILE_FRAMEWORKS = ["jul", "jdk_system", "slf4j", "log4j", "jcl", "arc", "gdx", "riiablo", "android", "none"]

FILE_COLUMNS = (
    ["f_sloc", "f_n_methods", "f_n_formal_logs", "f_log_density", "f_comment_density",
     "f_n_imports", "f_import_diversity", "f_has_logger_field", "f_n_informal"]
    + [f"f_dominant_level_{k}" for k in DOMINANT_KINDS]
    + ["f_mean_level_ord"]
    + [f"f_framework_{fw}" for fw in FILE_FRAMEWORKS]
)

_LOGGER_TYPE = re.compile(r"^(Log|\w*Logger)$")
_LOGGER_INIT = re.compile(r"getLogger|LogManager|LoggerFactory")


def import_prefix(imp):
    body = imp[len("static"):] if imp.startswith("static") else imp
    return ".".join(body.split(".")[:2])


def has_logger_field(root):
    for stmt in root.iter(SRC + "decl_stmt"):
        if not is_type_member(stmt):
            continue
        for decl in stmt.findall(SRC + "decl"):
            type_el = decl.find(SRC + "type")
            name_el = type_el.find(SRC + "name") if type_el is not None else None
            if name_el is not None and _LOGGER_TYPE.match(type_text(name_el).split(".")[-1]):
                return 1
            init = decl.find(SRC + "init")
            if init is not None and _LOGGER_INIT.search(flatten_code(init)):
                return 1
    return 0


def file_features(parsed):
    logs = collect_logs(parsed.root, parsed.file_framework)
    # console command replies (configs/extraction.yaml) are not logging, as in the units
    console = {l.element for u in parsed.units for l in u.logs if l.logging_style == "console_reply"}
    logs = [log for log in logs if log.element not in console]
    formal = [log for log in logs if log.logging_style == "formal"]
    sloc = parsed.sloc
    f = {}
    f["f_sloc"] = sloc
    f["f_n_methods"] = len(parsed.units)
    f["f_n_formal_logs"] = len(formal)
    f["f_log_density"] = 1000.0 * len(formal) / max(sloc, 1)
    f["f_comment_density"] = parsed.comment_lines / max(sloc, 1)
    f["f_n_imports"] = len(parsed.imports)
    f["f_import_diversity"] = len({import_prefix(imp) for imp in parsed.imports})
    f["f_has_logger_field"] = has_logger_field(parsed.root)
    f["f_n_informal"] = sum(1 for log in logs if log.logging_style == "informal_print")
    f.update(level_columns(formal, "f"))
    for fw in FILE_FRAMEWORKS:
        f[f"f_framework_{fw}"] = int(parsed.file_framework == fw)
    return f


def dominant_from_columns(feats, prefix):
    for k in DOMINANT_KINDS:
        if feats.get(f"{prefix}_dominant_level_{k}"):
            return k
    return "NONE"
