"""
Write evaluation tables as CSV (raw numbers), Markdown and LaTeX booktabs (formatted), and
assemble the experiment report.

CSV files keep every raw column so numbers in the thesis can be traced back. The Markdown
and LaTeX versions show mean ± sd over seeds and the 95% bootstrap CI of PR-AUC, F1,
precision and recall. French variants (<name>_fr.md/.tex) translate headers and captions and
use the decimal comma.
"""

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation.labels import t, group_name, category_name, POSTHOC_BASE

METRIC_COLS = ["pr_auc", "pr_auc_lift", "f1", "precision", "recall", "roc_auc", "mcc", "balanced_accuracy"]
CI_METRICS = ["pr_auc", "pr_auc_lift", "f1", "precision", "recall"]
METRIC_LABELS = {"pr_auc_lift": "lift"}


def _isnan(x):
    try:
        return x is None or (isinstance(x, float) and math.isnan(x)) or (isinstance(x, np.floating) and np.isnan(x))
    except TypeError:
        return False


def fmt(x, digits=3):
    if _isnan(x):
        return "–"
    if isinstance(x, (bool, np.bool_)):
        return "yes" if x else ""
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        return f"{x:.{digits}f}"
    return str(x)


def fmt_signed(x, digits=3):
    if _isnan(x):
        return "–"
    return f"{x:+.{digits}f}"


def fmt_p(p):
    if _isnan(p):
        return "–"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def fmt_mean_sd(mean, sd, digits=3):
    if _isnan(mean):
        return "–"
    if _isnan(sd):
        return f"{mean:.{digits}f}"
    return f"{mean:.{digits}f} ± {sd:.{digits}f}"


def fmt_ci(lo, hi, digits=3, signed=False):
    if _isnan(lo) or _isnan(hi):
        return "–"
    f = fmt_signed if signed else fmt
    return f"[{f(lo, digits)}, {f(hi, digits)}]"


def metric_label(m, lang="en"):
    return METRIC_LABELS.get(m) or t(m, lang)


def metric_display(df, id_cols, metrics=METRIC_COLS, ci_metrics=CI_METRICS, extra=("n", "n_pos", "prevalence"),
                   lang="en"):
    """Formatted copy: id columns, n/n_pos/prevalence, then 'mean ± sd' per metric and a CI column
    for PR-AUC, lift (PR-AUC / prevalence), F1, precision and recall."""
    out = pd.DataFrame(index=df.index)
    for c in id_cols:
        out[c] = df[c].map(fmt) if c in df else ""
    for c in extra:
        if c in df:
            out[c] = df[c].map(fmt)
    for m in metrics:
        if f"{m}_mean" not in df:
            continue
        name = metric_label(m, lang)
        sd = df[f"{m}_sd"] if f"{m}_sd" in df else [np.nan] * len(df)
        digits = 2 if m == "pr_auc_lift" else 3
        out[name] = [fmt_mean_sd(a, b, digits) for a, b in zip(df[f"{m}_mean"], sd)]
        if m in ci_metrics and f"{m}_ci_lo" in df:
            out[f"{name} 95% CI"] = [fmt_ci(a, b, digits) for a, b in zip(df[f"{m}_ci_lo"], df[f"{m}_ci_hi"])]
    if "low_support" in df:
        out["low support"] = df["low_support"].map(lambda v: "yes" if bool(v) else "")
    if "partial" in df and df["partial"].astype(bool).any():
        # coverage < 99% or another evaluation set: scored on other instances than the rest
        out["partial"] = df["partial"].map(lambda v: "yes" if bool(v) else "")
    return out.reset_index(drop=True)


def delta_display(df, id_cols, prefixes, extra=()):
    """Formatted copy for comparison tables: for each prefix, 'Δ [CI]', p, its Monte-Carlo SE, the
    resamples used (B used) and Holm p."""
    out = pd.DataFrame(index=df.index)
    for c in id_cols:
        out[c] = df[c].map(fmt) if c in df else ""
    for c in extra:
        if c in df:
            out[c] = df[c].map(fmt)
    for pre, label in prefixes:
        if f"{pre}_delta" not in df:
            continue
        out[f"Δ {label}"] = df[f"{pre}_delta"].map(fmt_signed)
        out[f"Δ {label} 95% CI"] = [fmt_ci(a, b, signed=True) for a, b in zip(df[f"{pre}_ci_lo"], df[f"{pre}_ci_hi"])]
        out[f"p {label}"] = df[f"{pre}_p"].map(fmt_p)
        if f"{pre}_p_mcse" in df:
            out[f"MC SE p {label}"] = df[f"{pre}_p_mcse"].map(lambda v: fmt(v, 4))
        if f"{pre}_b_used" in df:
            out[f"B used {label}"] = df[f"{pre}_b_used"].map(lambda v: "–" if _isnan(v) else str(int(v)))
        if f"{pre}_p_holm" in df:
            out[f"p Holm {label}"] = df[f"{pre}_p_holm"].map(fmt_p)
    return out.reset_index(drop=True)


def plain_display(df, digits=3):
    out = df.copy()
    for c in out.columns:
        if c.startswith("p_") or c.endswith("_p") or "_p_" in c:
            out[c] = out[c].map(fmt_p)
        else:
            out[c] = out[c].map(lambda v: fmt(v, digits))
    return out.reset_index(drop=True)


def to_markdown(df):
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        cells = [str(v).replace("|", "\\|").replace("\n", " ") for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


_TEX_SPECIAL = [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")]
_TEX_SYMBOLS = [("±", r"$\pm$"), ("Δ", r"$\Delta$"), ("δ", r"$\delta$"), ("≥", r"$\geq$"), ("≤", r"$\leq$"),
                ("–", "--"), ("→", r"$\rightarrow$"), ("<0.001", r"$<$0.001"), ("<0,001", r"$<$0,001"),
                ("×", r"$\times$")]


def tex_escape(s):
    s = str(s)
    out = []
    for ch in s:
        rep = ch
        for a, b in _TEX_SPECIAL:
            if ch == a:
                rep = b
                break
        out.append(rep)
    s = "".join(out)
    for a, b in _TEX_SYMBOLS:
        s = s.replace(a, b)
    return s


def _numeric_like(values):
    vals = [str(v) for v in values if str(v) not in ("", "–")]
    if not vals:
        return True
    return all(v[0].isdigit() or v[0] in "-+<[." for v in vals)


def to_latex(df, caption, label):
    align = "".join("r" if _numeric_like(df[c]) else "l" for c in df.columns)
    header = " & ".join(tex_escape(c) for c in df.columns) + r" \\"
    body = [" & ".join(tex_escape(v) for v in row) + r" \\" for row in df.itertuples(index=False)]
    long = len(df) > 40
    wide = len(df.columns) > 8
    lines = ["% requires \\usepackage{booktabs}" + (" and \\usepackage{longtable}" if long else "")
             + (" and \\usepackage{graphicx}" if wide and not long else "")]
    if long:
        lines += ["{\\scriptsize" if wide else "{\\small", f"\\begin{{longtable}}{{{align}}}",
                  f"\\caption{{{tex_escape(caption)}}}\\label{{{label}}}\\\\",
                  "\\toprule", header, "\\midrule", "\\endfirsthead",
                  "\\toprule", header, "\\midrule", "\\endhead",
                  "\\bottomrule", "\\endfoot"]
        lines += body
        lines += ["\\end{longtable}", "}"]
    else:
        lines += ["\\begin{table}[htbp]", "\\centering", "\\small",
                  f"\\caption{{{tex_escape(caption)}}}", f"\\label{{{label}}}"]
        if wide:
            lines.append("\\resizebox{\\textwidth}{!}{%")
        lines += [f"\\begin{{tabular}}{{{align}}}", "\\toprule", header, "\\midrule"]
        lines += body
        lines += ["\\bottomrule", "\\end{tabular}" + ("}" if wide else ""), "\\end{table}"]
    return "\n".join(lines) + "\n"


FR_HEADERS = {
    "task": "tâche", "model": "modèle", "model_a": "modèle A", "model_b": "modèle B", "test_repo": "référentiel de test",
    "engine": "moteur", "size": "taille", "ecosystem": "écosystème", "part": "partie",
    "ctx_category": "catégorie de contexte", "scope": "portée", "variant": "variante", "marker": "marqueur",
    "setting": "réglage", "n_subset": "n sous-ensemble", "n_pos_subset": "n_pos sous-ensemble",
    "n_complement": "n complément", "n_pos_complement": "n_pos complément", "prevalence": "prévalence",
    "prevalence_subset": "prévalence sous-ensemble", "prevalence_complement": "prévalence complément",
    "low_support_subset": "faible effectif sous-ensemble", "low_support_complement": "faible effectif complément",
    "f1_exploratory": "F1 exploratoire", "pr_auc_wilcoxon_p": "p Wilcoxon PR-AUC",
    "pr_auc_cliffs_delta": "delta de Cliff PR-AUC", "pr_auc_cliffs_magnitude": "ampleur (Cliff)",
}
FR_WORDS = [("95% CI", "IC 95 %"), ("Balanced accuracy", "Exactitude équilibrée"), ("Precision", "Précision"),
            ("Recall", "Rappel"), ("low support", "faible effectif"), ("partial", "partiel"),
            ("prevalence", "prévalence"), ("subset", "sous-ensemble"), ("complement", "complément"),
            ("vs full", "vs complet"), ("MC SE", "ET MC"), ("lift", "gain"), ("exploratory", "exploratoire")]


def fr_header(c):
    c = str(c)
    if c in FR_HEADERS:
        return FR_HEADERS[c]
    for a, b in FR_WORDS:
        c = c.replace(a, b)
    return c


def fr_cell(v):
    s = str(v)
    if s == "yes":
        return "oui"
    if s.startswith("[") and s.endswith("]"):
        s = s.replace(", ", " ; ")
    return re.sub(r"(?<=\d)\.(?=\d)", ",", s)


CATEGORY_COLUMNS = ("part", "ctx_category", "scope", "variant", "marker")


def to_french(display):
    """French headers and cells: categorical columns get their French display names (labels.py),
    numbers the decimal comma; model ids and event labels stay identifiers."""
    out = display.copy()
    for c in CATEGORY_COLUMNS:
        if c in out:
            out[c] = out[c].map(lambda v, c=c: category_name(c, v, "fr"))
    out.columns = [fr_header(c) for c in display.columns]
    for c in out.columns:
        out[c] = out[c].map(fr_cell)
    return out.reset_index(drop=True)


def write_table(raw, name, out_dir, caption, display=None, fr_caption=None):
    """raw -> <name>.csv; display (or raw) -> <name>.md and <name>.tex; with fr_caption also
    <name>_fr.md and <name>_fr.tex (French headers, decimal comma). Returns the csv path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(out_dir / f"{name}.csv", index=False)
    shown = display if display is not None else plain_display(raw)
    with open(out_dir / f"{name}.md", "w", encoding="utf-8") as f:
        f.write(f"**{caption}**\n\n")
        f.write(to_markdown(shown) + "\n")
    with open(out_dir / f"{name}.tex", "w", encoding="utf-8") as f:
        f.write(to_latex(shown, caption, f"tab:{name}"))
    if fr_caption:
        fr = to_french(shown)
        with open(out_dir / f"{name}_fr.md", "w", encoding="utf-8") as f:
            f.write(f"**{fr_caption}**\n\n")
            f.write(to_markdown(fr) + "\n")
        with open(out_dir / f"{name}_fr.tex", "w", encoding="utf-8") as f:
            f.write(to_latex(fr, fr_caption, f"tab:{name}_fr"))
    return out_dir / f"{name}.csv"


def write_report(lines, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return path


def _cell(r, m):
    digits = 2 if m == "pr_auc_lift" else 3
    s = fmt_mean_sd(r.get(f"{m}_mean"), r.get(f"{m}_sd"), digits)
    if not _isnan(r.get(f"{m}_ci_lo")):
        s += " " + fmt_ci(r[f"{m}_ci_lo"], r[f"{m}_ci_hi"], digits)
    return s


PARTIAL_MARK = " †"


def pivot_metric(df, metric, row="model", col="task", order=None):
    """Formatted 'mean ± sd [CI]' with one row per `row` value and one column per `col` value.

    A cell of a partial model (see partial_note) ends with '†'.
    """
    out = {}
    cols = []
    for _, r in df.iterrows():
        cell = _cell(r, metric)
        if bool(r.get("partial", False)):
            cell += PARTIAL_MARK
        out.setdefault(r[row], {})[r[col]] = cell
        if r[col] not in cols:
            cols.append(r[col])
    rows = order if order is not None else list(out)
    data = [[k] + [out.get(k, {}).get(c, "–") for c in cols] for k in rows if k in out]
    return pd.DataFrame(data, columns=[row] + cols)


def partial_note(df, group=None):
    """Footnote for the '†' cells of pivot_metric, with the n of every partial model (per group), or ''."""
    if df is None or "partial" not in df or not df["partial"].astype(bool).any():
        return ""
    d = df[df["partial"].astype(bool)]
    items = []
    for r in d.itertuples():
        where = f"{r.task}/{r.model}" if hasattr(r, "task") else str(r.model)
        if group:
            where += f" ({getattr(r, group)})"
        extra = f", {r.n_test_repos} test repositories" if hasattr(r, "n_test_repos") else ""
        items.append(f"{where} n={r.n}, n_pos={r.n_pos}{extra}")
    return ("† partial: predictions cover < 99% of the instances or come from another evaluation set, so the "
            "model is scored on other instances than the rest; " + "; ".join(items) + ".")


def _pivot_lines(df, metric, group=None, **kw):
    """Markdown pivot table followed by the partial-model footnote when there is one."""
    L = [to_markdown(pivot_metric(df, metric, **kw)), ""]
    note = partial_note(df, group)
    return L + ([note, ""] if note else [])


def keyed(df, col):
    """Adds key = 'task / value (n=...)' with the n of the complete models of that row, so a partial
    model (other n, given in the footnote) stays on the same row."""
    d = df.copy()
    partial = d["partial"].astype(bool) if "partial" in d else pd.Series(False, index=d.index)
    ref = d[~partial].groupby(["task", col])["n"].first().to_dict()
    n = [ref.get((task, v), n_) for task, v, n_ in zip(d["task"], d[col], d["n"])]
    d["key"] = [f"{task} / {v} (n={int(n_)})" for task, v, n_ in zip(d["task"], d[col], n)]
    return d


def group_display(df, col, models=("naive_prior", "hgb", "gnn_ggnn", "hybrid_ggnn")):
    """One row per (task, group): n, n_pos and prevalence of the group, naive_prior's PR-AUC as the
    chance reference, then per model PR-AUC [CI] with its lift (×, PR-AUC / prevalence) and ROC-AUC."""
    models = [m for m in models if m in set(df["model"])]
    rows = []
    for (task, value), g in df.groupby(["task", col], sort=False):
        partial = g["partial"].astype(bool) if "partial" in g else pd.Series(False, index=g.index)
        ref = g[~partial].iloc[0] if (~partial).any() else g.iloc[0]
        row = [task, value, fmt(ref["n"]), fmt(ref["n_pos"]), fmt(ref["prevalence"])]
        for m in models:
            r = g[g["model"] == m]
            if not len(r):
                row += ["–"] if m == "naive_prior" else ["–", "–"]
                continue
            r = r.iloc[0]
            mark = PARTIAL_MARK if bool(r.get("partial", False)) else ""
            if m == "naive_prior":
                row.append(fmt(r["pr_auc_mean"]) + mark)
                continue
            lift = "" if _isnan(r.get("pr_auc_lift_mean")) else f" ×{r['pr_auc_lift_mean']:.2f}"
            row += [_cell(r, "pr_auc") + lift + mark, fmt_mean_sd(r.get("roc_auc_mean"), r.get("roc_auc_sd"))]
        rows.append(row)
    cols = ["task", col, "n", "n_pos", "prevalence"]
    for m in models:
        cols += [f"{m} PR-AUC"] if m == "naive_prior" else [f"{m} PR-AUC [CI] ×lift", f"{m} ROC-AUC"]
    return pd.DataFrame(rows, columns=cols)


def _files(*names):
    return ", ".join(f"`{n}`" for n in names)


def _tbl(name, sfx=""):
    return f"tables/{name}{sfx}.csv"


def _floor_text(ctx):
    return (f"< {ctx.get('min_test_positives', 10)} positives or positives from at most "
            f"{ctx.get('few_commits', 2)} commits")


def _b_note(g, pre, ctx):
    """'; b of B resamples ...' when some test resamples were undefined, else ''."""
    b, B = g.get(f"{pre}_b_used"), ctx.get("B_test")
    if _isnan(b) or not B or int(b) >= B:
        return ""
    return f"; {int(b)} of {B} resamples with a positive in every repository"


def _delta_ci(g, pre):
    return f"{fmt_signed(g.get(f'{pre}_delta'))} {fmt_ci(g.get(f'{pre}_ci_lo'), g.get(f'{pre}_ci_hi'), signed=True)}"


def _p_se(g, pre):
    """'p (±MC SE; B used)'."""
    s = fmt_p(g.get(f"{pre}_p"))
    extra = []
    if not _isnan(g.get(f"{pre}_p_mcse")):
        extra.append(f"±{g[f'{pre}_p_mcse']:.4f}")
    if not _isnan(g.get(f"{pre}_b_used")):
        extra.append(f"B {int(g[f'{pre}_b_used'])}")
    return s + (f" ({'; '.join(extra)})" if extra else "")


def _support_note(g, sides=("subset", "complement")):
    """'subset 3 pos / 2 commits' for the parts of a row below the support floor."""
    return ", ".join(f"{s} {g.get(f'n_pos_{s}')} pos / {g.get(f'n_pos_commits_{s}')} commits" for s in sides
                     if bool(g.get(f"below_floor_{s}", False)))


def _get(df, **kw):
    if df is None or not len(df):
        return None
    sel = pd.Series(True, index=df.index)
    for k, v in kw.items():
        if k not in df:
            return None
        sel &= df[k] == v
    d = df[sel]
    return d.iloc[0] if len(d) else None


def _extraction(ctx):
    """(n annotated, n rows, problems) of the extraction-precision step."""
    ext = tuple(ctx.get("extraction") or (0, 0))
    return ext[0], ext[1], (list(ext[2]) if len(ext) > 2 else [])


def _extraction_line(ep, ctx):
    n_ann, n_rows, problems = _extraction(ctx)
    if ep is None or not len(ep):
        if problems:
            return ("- Extraction precision: not computed; the annotation of `validation/event_sample.csv` has cells "
                    "that are not allowed values or incomplete rows (section 2).")
        return "- Extraction precision: the annotation of `validation/event_sample.csv` is pending."
    labels = ep[ep["estimator"] == "label"]
    per = "; ".join(f"{r.event_label} {fmt(r.precision)} {fmt_ci(r.wilson_ci_lo, r.wilson_ci_hi)} "
                    f"(n={r.n_correct + r.n_wrong})" for r in labels.itertuples())
    a = _get(ep, event_label="ALL")
    if a is None:
        return (f"- Extraction precision per label (annotation, {n_ann} of {n_rows} sampled events; `?` "
                f"excluded; Wilson 95% CI): {per}. No overall value: the core-event shares that weight the "
                "label-stratified sample are not available for every label.")
    return (f"- Extraction precision (annotation, {n_ann} of {n_rows} sampled events; `?` excluded): "
            f"{a['precision']:.3f}, the label precisions weighted by their shares of the core events (bootstrap "
            f"of commits within labels, 95% CI {fmt_ci(a['cluster_ci_lo'], a['cluster_ci_hi'])}); with `?` counted "
            f"as wrong {fmt(a['precision_unclear_wrong'])}. Per label (Wilson 95% CI): {per}.")


def _section_summary(T, ctx):
    sfx = ctx["sfx"]
    tasks = ctx["tasks"]
    L = ["## 1. Summary by research question", "",
         "Measured values only, primary tasks and primary models. Δ = A − B; 95% CI = commit-cluster bootstrap; "
         "p = paired bootstrap on the test resamples, Holm-adjusted within the family named. The sensitivity task "
         "add_log_post (section 9) and the post-hoc log1p models (section 10) are not used here.", ""]

    L += ["**RQ1 – logging practices and their evolution.** Decisive: "
          + _files(_tbl("rq1_event_rates"), _tbl("rq1_events_per_year"), _tbl("rq1_transitions"),
                   _tbl("dq_extraction_precision"))
          + "; figures `figures/rq1_core_events_*`, `figures/rq1_events_per_year_*`, "
            "`figures/rq1_change_level_heatmap_*`.", ""]
    rates = T.get("rq1_event_rates")
    if rates is not None and len(rates):
        tot = {x: int(rates[f"core_{x}"].sum()) for x in ("ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL")}
        r = rates[pd.to_numeric(rates["n_non_merge"], errors="coerce") > 0]
        line = (f"- Core events: ADD_LOG {tot['ADD_LOG']}, REMOVE_LOG {tot['REMOVE_LOG']}, CHANGE_LEVEL "
                f"{tot['CHANGE_LEVEL']} in {len(rates)} repositories ({fmt(int(r['n_non_merge'].sum()))} non-merge commits)")
        if len(r):
            lo, hi = r.loc[r["core_total_per_1k"].idxmin()], r.loc[r["core_total_per_1k"].idxmax()]
            line += (f"; core events per 1,000 non-merge commits from {lo['core_total_per_1k']:.1f} ({lo['repo']}) "
                     f"to {hi['core_total_per_1k']:.1f} ({hi['repo']})")
        L.append(line + ".")
    tr = T.get("rq1_transitions")
    if tr is not None and len(tr):
        value_cols = [c for c in tr.columns if c not in ("pre_level", "total")]
        long = tr.melt(id_vars="pre_level", value_vars=value_cols, var_name="post_level", value_name="n")
        long = long[long["n"] > 0].sort_values(["n", "pre_level", "post_level"], ascending=[False, True, True]).head(3)
        L.append(f"- Most frequent CHANGE_LEVEL transitions (n = {int(tr['total'].sum())}): "
                 + "; ".join(f"{a}→{b} {int(n)}" for a, b, n in zip(long["pre_level"], long["post_level"], long["n"]))
                 + ".")
    L.append(_extraction_line(T.get("dq_extraction_precision"), ctx))
    L.append("")

    pooled, pw, ab = T.get("rq3_overall_pooled"), T.get("pairwise"), T.get("ablation")
    L += ["**RQ2 – can history and code structure model logging decisions?** Decisive: "
          + _files(_tbl("rq3_overall_pooled", sfx), _tbl("pairwise", sfx), _tbl("ablation", sfx),
                   _tbl("rq2_importance", sfx)) + ".", ""]
    imp = T.get("rq2_importance")
    for task in tasks:
        if pooled is None or not len(pooled) or task not in set(pooled["task"]):
            continue
        d = pooled[pooled["task"] == task]
        best = d.loc[d["pr_auc_mean"].idxmax()]
        rule = _get(d, model="naive_rule")
        line = (f"- {task}: highest pooled PR-AUC {best['model']} {_cell(best, 'pr_auc')} (prevalence "
                f"{best['prevalence']:.3f}")
        if rule is not None:
            line += f"; naive_rule {_cell(rule, 'pr_auc')}"
        line += ")"
        g = _get(pw, task=task, model_a="hybrid_ggnn", model_b="naive_rule")
        if g is not None:
            line += f"; hybrid_ggnn − naive_rule Δ PR-AUC {_delta_ci(g, 'pr_auc')}, p Holm {fmt_p(g['pr_auc_p_holm'])}"
        for variant, lab in (("no_history", "no-history − full"), ("history_only", "history-only − full")):
            a = _get(ab, task=task, scope="full_test", variant=variant)
            if a is not None and not _isnan(a.get("pr_auc_vs_full_delta")):
                line += (f"; {lab} Δ PR-AUC {_delta_ci(a, 'pr_auc_vs_full')}, p Holm "
                         f"{fmt_p(a.get('pr_auc_vs_full_p_holm'))}")
        if imp is not None and len(imp):
            top = imp[(imp["task"] == task) & (imp["rank"] == 1)]
            if len(top):
                r = top.iloc[0]
                line += f"; top feature group ({r['model']}) {group_name(r['group'])} {fmt_mean_sd(r['importance_mean'], r['importance_sd'])}"
        L.append(line + ".")
    L.append("")

    L += ["**RQ3 – graph-based models vs simpler baselines.** Decisive: "
          + _files(_tbl("pairwise", sfx), _tbl("rq3_overall_macro", sfx), _tbl("rq3_per_repo", sfx))
          + f"; figures `figures/prauc_bars{sfx}_*`, `figures/prauc_heatmap_<task>{sfx}_*`.", ""]
    for task in tasks:
        parts = []
        for a, b in (("hybrid_ggnn", "hgb"), ("gnn_ggnn", "hgb")):
            g = _get(pw, task=task, model_a=a, model_b=b)
            if g is None:
                continue
            s = (f"{a} − {b} pooled Δ PR-AUC {_delta_ci(g, 'pr_auc')} (p Holm {fmt_p(g['pr_auc_p_holm'])}), "
                 f"macro Δ {_delta_ci(g, 'macro_pr_auc')} (p Holm {fmt_p(g.get('macro_pr_auc_p_holm'))}"
                 + _b_note(g, "macro_pr_auc", ctx) + ")")
            if not _isnan(g.get("macro_no_few_commit_pr_auc_delta")):
                s += (f", macro Δ without the few-commit folds ({g['few_commit_folds_excluded']}) "
                      f"{_delta_ci(g, 'macro_no_few_commit_pr_auc')} (p Holm "
                      f"{fmt_p(g.get('macro_no_few_commit_pr_auc_p_holm'))})")
            parts.append(s + f", Wilcoxon p {fmt_p(g['pr_auc_wilcoxon_p'])} (n={g['pr_auc_wilcoxon_n']})")
        if parts:
            L.append(f"- {task}: " + "; ".join(parts) + ".")
    L.append("")

    did = T.get("rq4_did")
    L += ["**RQ4 – performance-sensitive code.** Decisive: " + _files(_tbl("rq4_did", sfx), _tbl("rq4_subset", sfx))
          + f"; figure `figures/rq4_forest_pr_auc{sfx}_*`. Primary test: PR-AUC difference-in-differences "
            "(hybrid_ggnn − hgb, subset minus complement), Holm over the three tasks; a task with a part below the "
            f"support floor ({_floor_text(ctx)}) gets no p.", ""]
    if did is not None and len(did):
        for _, g in did.iterrows():
            low = []
            if g.get("low_support_subset"):
                low.append("subset")
            if g.get("low_support_complement"):
                low.append("complement")
            support = (f"n_pos subset {g['n_pos_subset']}, complement {g['n_pos_complement']}")
            if bool(g.get("descriptive_only", False)):
                L.append(f"- {g['task']}: PR-AUC DiD {_delta_ci(g, 'pr_auc_did')}, F1 DiD {_delta_ci(g, 'f1_did')} – "
                         f"descriptive only, no p (below the support floor: {_support_note(g)}).")
                continue
            line = (f"- {g['task']}: PR-AUC DiD {_delta_ci(g, 'pr_auc_did')}, p {fmt_p(g['pr_auc_did_p'])}, "
                    f"p Holm {fmt_p(g['pr_auc_did_p_holm'])} ({support})")
            line += (f"; F1 DiD {_delta_ci(g, 'f1_did')}, p Holm {fmt_p(g['f1_did_p_holm'])}"
                     + (f" – exploratory, < 30 positives in the {' and '.join(low)}" if low else ""))
            L.append(line + ".")
    else:
        L.append("- not available.")
    L.append("")
    return L


def _section_quality(T, ctx):
    L = ["## 2. Dataset quality", ""]
    inst = T.get("dq_instances")
    if inst is not None and len(inst):
        g = inst.groupby("task").agg(n_repos=("repo", "count"), n_pos=("n_pos", "sum"), n_neg_pool=("n_neg_pool", "sum"),
                                     n_neg_R1=("n_neg_R1", "sum"), n_neg_R4=("n_neg_R4", "sum"),
                                     n_neg_R10=("n_neg_R10", "sum")).reset_index()
        g["test_repos"] = [int(((inst["task"] == x) & (inst["fold_role"] == "test")).sum()) for x in g["task"]]
        g["low_support"] = [int(((inst["task"] == x) & inst["low_support"].astype(bool)).sum()) for x in g["task"]]
        L += [to_markdown(plain_display(g)), "", f"Per repository: {_files(_tbl('dq_instances'))}.", ""]
    else:
        L += ["Instance files not available.", ""]
    fo = T.get("dq_folds")
    if fo is not None and len(fo):
        d = fo.copy()
        rows = [[r.task, r.test_repo, r.n_training_repos, f"{fmt(r.n_fit)} / {fmt(r.n_fit_pos)}",
                 f"{fmt(r.n_val)} / {fmt(r.n_val_pos)}", f"{fmt(r.n_test)} / {fmt(r.n_test_pos)}",
                 fmt(r.n_pos_commits), fmt(r.max_commit_share, 2), "yes" if r.few_commit_fold else "",
                 "yes" if r.low_support else ""] for r in d.itertuples()]
        L += ["LORO folds (fit / validation / test sizes and positives from the prediction sidecars; training = every "
              "other repository of the evaluation set; commit support of the test positives):", "",
              to_markdown(pd.DataFrame(rows, columns=["task", "test repo", "training repos", "fit n / n_pos",
                                                      "val n / n_pos", "test n / n_pos", "positive commits",
                                                      "max commit share", "few-commit", "low support"])), "",
              f"Commit support source: {'; '.join(sorted(set(d['commit_support_source'])))}. A few-commit fold "
              "measures the model on very few independent logging decisions. Training repositories per fold: "
              f"{_files(_tbl('dq_folds', ctx['sfx']))}.", ""]
    cov = T.get("dq_coverage")
    if cov is not None and len(cov):
        c = cov[cov["setting"] == ctx["setting"]].groupby("task").agg(
            n_models=("model", "count"), n_union=("n_union", "first"), n_evaluated_min=("n_evaluated", "min"),
            n_evaluated_max=("n_evaluated", "max"), n_partial=("partial", "sum"),
            n_eval_set_mismatch=("eval_set_mismatch", "sum")).reset_index()
        L += ["Evaluated instances (predictions aligned across models):", "", to_markdown(plain_display(c)), "",
              f"Per model and seed: {_files(_tbl('dq_coverage', ctx['sfx']))}.", ""]
    tr = T.get("dq_training")
    if tr is not None and len(tr):
        rows = []
        for task, g in tr.groupby("task", sort=False):
            incomplete = g.loc[~g["all_complete"].astype(bool), "model"].tolist()
            sets = {v for x in g["eval_set_sha1"].fillna("") for v in str(x).split(";") if v}
            rows.append([task, len(g), f"{int(g['n_seeds'].min())}-{int(g['n_seeds'].max())}",
                         fmt(g["n_selected"].iloc[0]), fmt(g["n_eval"].iloc[0]),
                         fmt(g["dropped_no_features"].iloc[0]), fmt(g["dropped_no_graph"].iloc[0]),
                         len(sets) or "–", ", ".join(incomplete) or "none"])
        L += ["Training runs (prediction sidecars; instances in the setting, evaluated, dropped for missing "
              "features or graph; number of distinct evaluation sets, eval_set_sha1, over the models):", "",
              to_markdown(pd.DataFrame(rows, columns=["task", "models", "seeds", "n_selected", "n_eval",
                                                      "dropped no features", "dropped no graph", "eval sets",
                                                      "incomplete runs"])), "",
              f"Per model (seeds, seconds, epochs, thresholds): {_files(_tbl('dq_training', ctx['sfx']))}.", ""]
    imb = T.get("dq_imbalance")
    if imb is not None and len(imb):
        d = imb.groupby("model", sort=False).agg(class_weighting=("class_weighting", "first"),
                                                threshold_rule=("threshold_rule", "first"),
                                                threshold_mean=("threshold_mean", "mean")).reset_index()
        L += [f"Imbalance handling (negative sampling {imb['negative_sampling'].iloc[0]}; class weighting and "
              "threshold rule from the sidecars; threshold mean over tasks, folds and seeds):", "",
              to_markdown(plain_display(d)), "",
              f"Per task: {_files(_tbl('dq_imbalance', ctx['sfx']))}. Hyperparameters (fixed a priori, except the "
              "`posthoc` section: post-hoc variants added after the primary results, `prespecified` = False): "
              f"{_files(_tbl('config_hyperparameters'))}. Hardware and software: {_files(_tbl('env_manifest'))}.", ""]
    fail = T.get("dq_failures")
    if fail is not None and len(fail):
        cols = [c for c in fail.columns if c in ("n_instances", "n_view_failures", "n_with_features", "n_with_graph",
                                                 "n_graph_failures", "n_graph_truncated")
                or c.startswith("n_graph_not_built_outside_") or c.startswith("n_graph_missing_in_")]
        L += ["View, feature and graph failures (graphs are built only for the instances of the primary setting, "
              "which the neural models use; `n_graph_not_built_outside_R4` counts the other instances of the "
              "instance file, `n_graph_missing_in_R4` real gaps):", "",
              to_markdown(plain_display(fail.groupby("task")[cols].sum().reset_index())), "",
              f"Per repository and reason: {_files(_tbl('dq_failures'))}.", ""]
    gs = T.get("dq_graph_stats")
    if gs is not None and len(gs):
        cols = [c for c in ["task", "n_graphs", "n_nodes_mean", "n_nodes_median", "n_nodes_p95", "n_nodes_max",
                            "n_edges_mean", "n_edges_median", "n_truncated"] if c in gs]
        L += ["Graph sizes:", "", to_markdown(plain_display(gs[cols], digits=1)), "",
              f"Full: {_files(_tbl('dq_graph_stats'))}.", ""]
    pf = T.get("dq_parse_failures")
    if pf is not None and len(pf):
        cols = [c for c in ["repo", "n_commits", "n_non_merge", "n_bulk", "parse_failures", "parse_failures_pre",
                            "parse_failures_post"] if c in pf]
        L += ["Mining (commits and srcML parse failures over the history):", "", to_markdown(plain_display(pf[cols])),
              "", "parse_failures = 0 only means that srcML returned a tree for every file; it does not show that the "
              "tree is structurally correct (see the HEAD misparse counts below). "
              f"With the mining summary counts: {_files(_tbl('dq_parse_failures'))}.", ""]
    hm = T.get("dq_head_misparse")
    if hm is not None and len(hm):
        d = hm[hm["modeling"].astype(bool)] if "modeling" in hm else hm
        cols = [c for c in ["repo", "n_java_files", "n_parse_failures", "n_files_misparsed", "pct_files_misparsed",
                            "n_units_no_class", "n_formal_outside_units_misparse",
                            "n_statements_outside_units_misparse", "n_formal"] if c in d]
        L += ["HEAD snapshot, structural misparses (rq1 screening): a misparsed file has statements or members "
              "directly under `<unit>`; its method units lose their class (`n_units_no_class`) and statements "
              "outside any unit are not detected (`n_formal_outside_units_misparse` formal logging statements, "
              "`n_statements_outside_units_misparse` of any style); `n_formal` = formal statements detected at HEAD:",
              "", to_markdown(plain_display(d[cols], digits=1)), "",
              f"All screened repositories: {_files(_tbl('dq_head_misparse'))}; per file: `rq1/structural_misparse.csv`.",
              ""]
    ep = T.get("dq_extraction_precision")
    n_ann, n_rows, problems = _extraction(ctx)
    if ep is not None and len(ep):
        rows = [[r.event_label, f"{r.n_annotated} ({r.n_correct} / {r.n_wrong} / {r.n_unclear})", fmt(r.precision),
                 fmt_ci(r.wilson_ci_lo, r.wilson_ci_hi), fmt_ci(r.cluster_ci_lo, r.cluster_ci_hi),
                 fmt(r.precision_unclear_wrong), fmt_ci(r.unclear_wrong_wilson_ci_lo, r.unclear_wrong_wilson_ci_hi),
                 fmt(r.core_events), fmt(r.weight)] for r in ep.itertuples()]
        L += [f"Extraction precision from the annotation ({n_ann} of {n_rows} sampled events annotated). "
              "An event is correct when `is_logging_statement`, `label_correct` and, for CHANGE_LEVEL, "
              "`level_correct` are y; precision with `?` excluded and with `?` counted as wrong; Wilson "
              "95% CI and a bootstrap 95% CI over commits:", "",
              to_markdown(pd.DataFrame(rows, columns=["label", "annotated (correct / wrong / ?)", "precision",
                                                      "Wilson CI", "commit bootstrap CI", "precision (? wrong)",
                                                      "Wilson CI (? wrong)", "core events", "weight"])), "",
              "The sample is stratified by label (up to 40 core events each), so it over-represents rare labels. "
              "`ALL` is the stratified estimate Σ W_l·p_l with W_l = the label's share of the core events of the "
              "master table; its CI is a bootstrap of commits within each label (no Wilson interval). "
              "`ALL (sample, unweighted)` is the pooled share of the sample and is not an estimate for the corpus. "
              "Wilson intervals are optimistic because errors cluster by commit; a label whose annotated events are "
              f"all correct adds no bootstrap variance. Table: {_files(_tbl('dq_extraction_precision'))}.", ""]
    elif problems:
        L += ["Extraction precision: not computed. The annotation of `validation/event_sample.csv` has cells that "
              "are not allowed values, or started rows with a required cell empty: " + "; ".join(problems)
              + ". Allowed: `label_correct` y/n/?, `is_logging_statement` y/n, `level_correct` y/n/na; "
              "rows with every annotation cell empty are not annotated yet.", ""]
    else:
        L += [f"Extraction precision: the annotation of `validation/event_sample.csv` ({n_rows} sampled "
              "events) is pending; no precision is reported.", ""]
    return L


def _section_rq1(T, ctx):
    L = ["## 3. RQ1 - logging practices and their evolution", ""]
    rates = T.get("rq1_event_rates")
    if rates is not None and len(rates):
        cols = ["repo", "n_non_merge"] + [f"core_{x}" for x in ("ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL", "total")] + \
               ["core_total_per_1k", "n_formal_nonbulk", "formal_nonbulk_per_1k"]
        L += ["Logging events per repository:", "",
              to_markdown(plain_display(rates[[c for c in cols if c in rates]], digits=1)), "",
              "Columns: `n_non_merge` = non-merge commits reachable from the pinned HEAD (bulk commits included); "
              "`core_<label>` = core events (formal logging style, inside a method that exists before and after the "
              "commit, not relocated, not in a bulk commit); `core_total_per_1k` = core_total / n_non_merge × 1000; "
              "`n_formal_nonbulk` = formal events outside bulk commits in any scope (new/deleted methods and files, "
              "relocations included); `formal_nonbulk_per_1k` = n_formal_nonbulk / n_non_merge × 1000. The CSV also "
              "has `n_events_all` / `all_per_1k`: every event of the master table (all styles, scopes, bulk and "
              "relocated events), which counts code creation and deletion, not logging decisions.", ""]
        tot = {x: int(rates[f"core_{x}"].sum()) for x in ("ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL")}
        L += [f"Total core events: ADD_LOG {tot['ADD_LOG']}, REMOVE_LOG {tot['REMOVE_LOG']}, "
              f"CHANGE_LEVEL {tot['CHANGE_LEVEL']}.", ""]
    py = T.get("rq1_events_per_year")
    if py is not None and len(py):
        d = py[py["repo"] == "ALL"]
        cols = [c for c in ["year", "n_non_merge", "ADD_LOG", "REMOVE_LOG", "CHANGE_LEVEL", "total", "total_per_1k"]
                if c in d]
        L += ["Core events per commit year, all repositories (per repository and label: "
              f"{_files(_tbl('rq1_events_per_year'))}; figure `figures/rq1_events_per_year_*`):", "",
              to_markdown(plain_display(d[cols], digits=1)), ""]
    tr = T.get("rq1_transitions")
    if tr is not None and len(tr):
        value_cols = [c for c in tr.columns if c not in ("pre_level", "total")]
        long = tr.melt(id_vars="pre_level", value_vars=value_cols, var_name="post_level", value_name="n")
        long = long[long["n"] > 0].sort_values(["n", "pre_level", "post_level"], ascending=[False, True, True]).head(6)
        if len(long):
            L += [f"Most frequent CHANGE_LEVEL transitions (core, n = {int(tr['total'].sum())}): "
                  + "; ".join(f"{a}→{b} {int(n)}" for a, b, n in zip(long["pre_level"], long["post_level"], long["n"]))
                  + ".", ""]
    enr = T.get("rq1_enrichment")
    if enr is not None and len(enr):
        L += ["Context categories of positives vs negatives (R4 instances):", "",
              to_markdown(plain_display(enr[["task", "category", "n_pos", "share_pos", "n_neg", "share_neg",
                                             "enrichment"]])), ""]
    if ctx.get("rq1_snapshot_files"):
        L += ["HEAD snapshot tables from `scripts/screen_corpus.py`: "
              + ", ".join(f"`rq1/{n}`" for n in ctx["rq1_snapshot_files"]) + ".", ""]
    names = ["rq1_events", "rq1_events_validity", "rq1_events_scope", "rq1_event_rates", "rq1_events_per_year",
             "rq1_transitions", "rq1_transitions_by_repo", "rq1_enrichment"] + \
            (["rq1_levels"] if T.get("rq1_levels") is not None else [])
    L += [f"Tables: {_files(*[_tbl(n) for n in names])}. Figures (not setting-dependent): "
          "`figures/rq1_core_events_*`, `figures/rq1_events_per_year_*`, `figures/rq1_change_level_heatmap_*`"
          + (", `figures/rq1_levels_*`" if T.get("rq1_levels") is not None else "") + ".", ""]
    return L


def _section_rq2(T, ctx):
    sfx = ctx["sfx"]
    L = ["## 4. RQ2 - can history and code structure model logging decisions?", ""]
    pooled = T.get("rq3_overall_pooled")
    if pooled is not None and len(pooled):
        keep = ["naive_prior", "naive_size", "naive_rule", "hgb", "mlp_hist", "gnn_ggnn", "hybrid_ggnn"]
        sel = pooled[pooled["model"].isin(keep)]
        L += ["Pooled PR-AUC (the prevalence is the expected PR-AUC of a random ranking):", ""]
        L += _pivot_lines(sel, "pr_auc", order=[m for m in ctx["model_order"] if m in set(sel["model"])])
        L += ["Prevalence per task: " + "; ".join(f"{x} {v:.3f}" for x, v in
                                                       pooled.groupby("task")["prevalence"].first().items()) + ".", ""]
    groups = ", ".join(f"`{k}_` {v}" for k, v in (("h", "history"), ("f", "file"), ("m", "method"),
                                                     ("l", "logging context"), ("s", "statement"), ("d", "domain"),
                                                     ("x", "lexical")))
    imp = T.get("rq2_importance")
    if imp is not None and len(imp):
        L += [f"Feature groups: {groups} (the 128 `x_` buckets are hashed identifier subtokens and are read as one "
              "lexical group). Top-3 groups by permutation importance (drop in average precision when the group is "
              "permuted jointly; mean ± sd over folds):", ""]
        for (task, model), g in imp[imp["rank"] <= 3].groupby(["task", "model"]):
            L.append(f"- {task} / {model}: " + "; ".join(
                f"{group_name(r.group)} {fmt_mean_sd(r.importance_mean, r.importance_sd)} (folds={r.n_folds})"
                for r in g.itertuples()))
        L += ["", f"Full table: {_files(_tbl('rq2_importance', sfx))}.", ""]
    else:
        L += ["Permutation importance: not available.", ""]
    impf = T.get("rq2_importance_features")
    if impf is not None and len(impf):
        L += ["Top-5 non-lexical single features by permutation importance; the lexical buckets are summarised "
              "as one group (their single-bucket drops are not interpretable one by one):", ""]
        for (task, model), g in impf.groupby(["task", "model"]):
            lex = g["feature"].astype(str).str.startswith("x_")
            top = g[~lex].sort_values("rank").head(5)
            line = f"- {task} / {model}: " + "; ".join(
                f"{r.feature} ({group_name(str(r.feature).split('_')[0])}) {fmt_mean_sd(r.importance_mean, r.importance_sd)}"
                for r in top.itertuples())
            if lex.any():
                gl = None if imp is None else _get(imp, task=task, model=model, group="x")
                line += (f"; lexical group: {int(lex.sum())} of the top {len(g)} single features are `x_` buckets "
                         f"(best rank {int(g.loc[lex, 'rank'].min())})")
                if gl is not None:
                    line += f", group drop {fmt_mean_sd(gl['importance_mean'], gl['importance_sd'])}"
            L.append(line)
        L += ["", f"Top 15: {_files(_tbl('rq2_importance_features', sfx))}.", ""]
    return L


def _section_rq3(T, ctx):
    sfx = ctx["sfx"]
    L = ["## 5. RQ3 - graph-based models vs simpler baselines", ""]
    pooled = T.get("rq3_overall_pooled")
    if pooled is not None and len(pooled):
        order = [m for m in ctx["model_order"] if m in set(pooled["model"])]
        L += ["Pooled PR-AUC, all models:", ""] + _pivot_lines(pooled, "pr_auc", order=order)
        L += ["Pooled F1 (threshold frozen on validation):", ""] + _pivot_lines(pooled, "f1", order=order)
        L += ["Pooled precision (threshold frozen on validation):", ""] + _pivot_lines(pooled, "precision", order=order)
        L += ["Pooled recall (threshold frozen on validation):", ""] + _pivot_lines(pooled, "recall", order=order)
        L += ["Pooled ROC-AUC (mean ± sd over seeds):", ""] + _pivot_lines(pooled, "roc_auc", order=order)
        n = pooled.groupby("task")[["n", "n_pos"]].first().reset_index()
        L += ["n per task: " + "; ".join(f"{r.task} n={r.n}, n_pos={r.n_pos}" for r in n.itertuples()) + ".", ""]
    macro = T.get("rq3_overall_macro")
    if macro is not None and len(macro):
        order = [m for m in ctx["model_order"] if m in set(macro["model"])]
        L += ["Macro PR-AUC (mean over the test repositories each model was evaluated on):", ""]
        L += _pivot_lines(macro, "pr_auc", order=order)
        if "b_used" in macro:
            used = macro.groupby("task")["b_used"].agg(["min", "max"])
            L += [f"Macro CIs use only the resamples in which every repository of the macro has a positive (of B = "
                  f"{ctx['B']}): " + "; ".join(f"{task} {int(r['min'])}" + (f"–{int(r['max'])}" if r["max"] != r["min"]
                                                                             else "")
                                             for task, r in used.iterrows()) + ".", ""]
    few = T.get("rq3_overall_macro_no_few_commit")
    if few is not None and len(few) and macro is not None:
        rows = []
        tasks = list(dict.fromkeys(few["task"]))
        for m in [m for m in ctx["model_order"] if m in set(few["model"])]:
            row = [m]
            for task in tasks:
                a, b = _get(macro, task=task, model=m), _get(few, task=task, model=m)
                row += [_cell(a, "pr_auc") if a is not None else "–", _cell(b, "pr_auc") if b is not None else "–"]
            rows.append(row)
        cols = ["model"] + [x for task in tasks for x in (f"{task} all folds", f"{task} without few-commit folds")]
        excl = "; ".join(f"{task}: {few[few['task'] == task]['folds_excluded'].iloc[0]}" for task in tasks)
        L += [f"Macro PR-AUC with and without the few-commit folds ({excl}):", "", to_markdown(pd.DataFrame(rows, columns=cols)),
              "", f"Table: {_files(_tbl('rq3_overall_macro_no_few_commit', sfx))}.", ""]
    per_repo = T.get("rq3_per_repo")
    if per_repo is not None and len(per_repo):
        r = ctx.get("ratio")
        nominal = 1 / (1 + r) if r else None
        d = per_repo.groupby(["task", "test_repo"])["prevalence"].first().reset_index()
        if nominal is not None:
            off = d[(d["prevalence"] - nominal).abs() > 0.01]
            if len(off):
                L += [f"Per-repository prevalence differs from 1/(1+R) = {nominal:.3f} where a repository's negative "
                      "pool is smaller than R × its positives: "
                      + "; ".join(f"{x.task} {x.test_repo} {x.prevalence:.3f}" for x in off.itertuples())
                      + ". Per-repository PR-AUC values (heatmaps, macro averages) are relative to these prevalences; "
                        "the heatmap column labels give them.", ""]
    for name, col in (("rq3_per_engine", "engine"), ("rq3_per_size", "size"), ("rq3_per_ecosystem", "ecosystem")):
        d = T.get(name)
        if d is None or not len(d):
            continue
        L += [f"Pooled metrics per {col} (n_pos and prevalence of the group; naive_prior = chance reference; "
              "×lift = PR-AUC / prevalence):", "", to_markdown(group_display(d, col)), ""]
        note = partial_note(d[d["model"].isin(["naive_prior", "hgb", "gnn_ggnn", "hybrid_ggnn"])], col)
        if note:
            L += [note, ""]
    L += ["PR-AUC depends on the prevalence, which differs between groups (engines, sizes, ecosystems, subsets, "
          "categories): compare groups through the lift and ROC-AUC, not through raw PR-AUC.", ""]
    if ctx.get("ecosystem_source"):
        L += [f"Ecosystem = dominant formal logging framework per repository; source: {ctx['ecosystem_source']}.", ""]
    names = ["rq3_overall_pooled", "rq3_overall_macro", "rq3_per_repo", "rq3_per_engine", "rq3_per_size",
             "rq3_per_ecosystem"]
    L += [f"Tables: {_files(*[_tbl(n, sfx) for n in names])} (with French variants `*_fr.md`/`*_fr.tex` of the main "
          f"tables). Figures: `figures/pr_curves_<task>{sfx}_*` (seed 0), `figures/prauc_bars{sfx}_*`, "
          f"`figures/prauc_heatmap_<task>{sfx}_*`.", ""]
    return L


def _did_display(did, metrics=("pr_auc", "f1")):
    """Rows of a DiD table; a row below the support floor shows Δ and CI only (descriptive)."""
    rows = []
    for _, g in did.iterrows():
        for metric in metrics:
            flags = []
            if g.get("low_support_subset"):
                flags.append("subset < 30 pos")
            if g.get("low_support_complement"):
                flags.append("complement < 30 pos")
            descriptive = bool(g.get("descriptive_only", False))
            if descriptive:
                flags.append(f"descriptive only, no p ({_support_note(g)})")
            elif metric == "f1" and flags:
                flags.append("exploratory")
            commits = "" if _isnan(g.get("n_pos_commits_subset")) else f" / {g['n_pos_commits_subset']}"
            commits_c = "" if _isnan(g.get("n_pos_commits_complement")) else f" / {g['n_pos_commits_complement']}"
            rows.append([g["task"], f"{g['model_a']} - {g['model_b']}", metric, _delta_ci(g, f"{metric}_subset"),
                         _delta_ci(g, f"{metric}_complement"), _delta_ci(g, f"{metric}_did"),
                         _p_se(g, f"{metric}_did"), fmt_p(g[f"{metric}_did_p_holm"]),
                         f"{g['n_subset']} / {g['n_pos_subset']}{commits}",
                         f"{g['n_complement']} / {g['n_pos_complement']}{commits_c}", ", ".join(flags)])
    return pd.DataFrame(rows, columns=["task", "difference", "metric", "Δ subset [CI]", "Δ complement [CI]",
                                       "DiD [CI]", "p (MC SE; B used)", "p Holm", "subset n / n_pos / commits",
                                       "complement n / n_pos / commits", "flags"])


def _section_rq4(T, ctx):
    sfx = ctx["sfx"]
    L = ["## 6. RQ4 - performance-sensitive code", ""]
    did = T.get("rq4_did")
    if did is not None and len(did):
        L += ["Primary RQ4 test: PR-AUC difference-in-differences of hybrid_ggnn - hgb (hgb fixed a priori as the "
              "reference classical model), Holm over the three tasks; paired cluster bootstrap on the test resamples "
              f"(B = {ctx['B_test']}); p with its Monte-Carlo standard error and the number of resamples used (those "
              "with a positive in both parts). A row with a part below the support floor "
              f"({_floor_text(ctx)}) is descriptive only: Δ and CI, no p, not in the Holm family:", "",
              to_markdown(_did_display(did, ("pr_auc",))), "",
              "Secondary (threshold-dependent) F1 difference-in-differences, Holm over the tasks; rows with < 30 "
              "positives in the subset or the complement are exploratory:", "",
              to_markdown(_did_display(did, ("f1",))), ""]
    else:
        L += ["Difference-in-differences: not available (needs hybrid_ggnn, hgb and d_is_perf_sensitive).", ""]
    val = ctx.get("did_validation")
    best = T.get("rq4_did_bestval")
    if val is not None and len(val):
        sel = val[val["selected"].astype(bool)]
        L += ["Sensitivity to the reference model: the primary reference is hgb, fixed a priori; as a "
              "check, the reference is also chosen without test information, as the classical model (lr, rf, hgb) with the highest mean "
              "validation PR-AUC over folds and seeds: "
              + "; ".join(f"{r.task} {r.model} ({fmt(r.val_pr_auc_mean)})" for r in sel.itertuples()) + ".", ""]
        if len(sel) and sel["model"].eq("hgb").all():
            L += ["The validation choice is hgb for every task, so this check equals the table above.", ""]
        elif best is not None and len(best):
            L += ["Difference-in-differences against the validation-selected classical model (its own Holm "
                  "family over tasks):", "", to_markdown(_did_display(best)), ""]
        L += [f"Validation PR-AUC per classical model: {_files(_tbl('rq4_did_reference_validation', sfx))}.", ""]
    fu = T.get("rq4_did_frame_update")
    if fu is not None and len(fu):
        L += ["Stricter-subset sensitivity: subset = frame_update methods only, complement = every other method "
              "(hybrid_ggnn - hgb; its own Holm family over the tasks above the support floor; rows below it are "
              "descriptive only):", "", to_markdown(_did_display(fu)), ""]
    sub = T.get("rq4_subset")
    if sub is not None and len(sub):
        cov = []
        for task, g in sub.groupby("task", sort=False):
            s, c = _get(g, part="subset"), _get(g, part="complement")
            if s is not None and c is not None:
                cov.append(f"{task} {100 * s['n'] / (s['n'] + c['n']):.1f}% of the instances, "
                           f"{100 * s['n_pos'] / max(1, s['n_pos'] + c['n_pos']):.1f}% of the positives")
        if cov:
            L += ["Subset coverage (share of the test instances in the performance-sensitive subset): "
                  + "; ".join(cov) + ".", ""]
        L += ["Subset and complement (pooled; prevalence differs between the parts, so compare lift and ROC-AUC):", "",
              to_markdown(group_display(sub, "part")), ""]
    gap = T.get("rq4_subset_gap")
    if gap is not None and len(gap):
        d = gap[gap["model"].isin(["naive_prior", "hgb", "gnn_ggnn", "hybrid_ggnn"])]
        rows = [[g["task"], g["model"], _delta_ci(g, "pr_auc"), _delta_ci(g, "pr_auc_lift"), _delta_ci(g, "roc_auc"),
                 _delta_ci(g, "f1"), f"{g['prevalence_subset']:.3f} / {g['prevalence_complement']:.3f}",
                 "descriptive only" if bool(g.get("descriptive_only", False)) else ""]
                for _, g in d.iterrows()]
        L += ["Subset minus complement per model (same test resamples):", "",
              to_markdown(pd.DataFrame(rows, columns=["task", "model", "Δ PR-AUC [CI]", "Δ lift [CI]",
                                                      "Δ ROC-AUC [CI]", "Δ F1 [CI]", "prevalence subset / complement",
                                                      "flags"])),
              "", f"All models with p values, MC SE and B used: {_files(_tbl('rq4_subset_gap', sfx))}.", ""]
    cat = T.get("rq4_ctx_category")
    if cat is not None and len(cat):
        L += ["Context categories (mutually exclusive; pooled):", "", to_markdown(group_display(cat, "ctx_category")),
              "", f"Figure: `figures/rq4_ctx_category{sfx}_*`.", ""]
    mk = T.get("rq4_subsystem_markers")
    if mk is not None and len(mk):
        L += ["Subsystem markers, each on its own (descriptive; a method can carry several markers; markers with "
              "few positives give wide intervals):", "", to_markdown(group_display(mk, "marker")), ""]
    es = ctx.get("error_summary")
    if es is not None and len(es):
        rows = []
        for _, g in es.iterrows():
            rows.append([g["task"], g["n"], g["n_pos"],
                         f"{g.get('only_hybrid_ggnn_correct_pos', '–')} / {g.get('only_hgb_correct_pos', '–')}",
                         f"{g.get('only_hybrid_ggnn_correct_neg', '–')} / {g.get('only_hgb_correct_neg', '–')}",
                         f"{fmt(g.get('hybrid_ggnn_vote_precision'))} / {fmt(g.get('hybrid_ggnn_vote_recall'))} / "
                         f"{fmt(g.get('hybrid_ggnn_vote_f1'))}",
                         f"{fmt(g.get('hgb_vote_precision'))} / {fmt(g.get('hgb_vote_recall'))} / {fmt(g.get('hgb_vote_f1'))}",
                         f"{g.get('topk_overlap', '–')} / {g.get('topk_k', '–')} ({fmt(g.get('topk_overlap_share'))})",
                         f"{g.get('topk_pos_hybrid_ggnn', '–')} / {g.get('topk_pos_hgb', '–')}"])
        L += ["Agreement of hybrid_ggnn and hgb (majority vote over seeds). Gains on positives = TP of one model where "
              "the other has a FN; gains on negatives = TN against FP. Top-k: the k = n_pos highest seed-mean scores "
              "of each model (threshold-free):", "",
              to_markdown(pd.DataFrame(rows, columns=["task", "n", "n_pos", "TP gains hybrid / hgb",
                                                      "TN gains hybrid / hgb", "hybrid P / R / F1", "hgb P / R / F1",
                                                      "top-k overlap / k (share)", "positives in top-k hybrid / hgb"])),
              "", f"All counts: `error_analysis/disagreement{sfx}.csv`.", ""]
    rg = ctx.get("rate_gap")
    if rg is not None and len(rg):
        rows = [[g["task"], g["model"], f"{g['fp_rate_subset']:.3f} / {g['fp_rate_complement']:.3f}",
                 _delta_ci(g, "fp_rate"), _p_se(g, "fp_rate"), f"{g['fn_rate_subset']:.3f} / {g['fn_rate_complement']:.3f}",
                 _delta_ci(g, "fn_rate"), _p_se(g, "fn_rate"), f"{g['n_pos_subset']} / {g['n_pos_complement']}",
                 ", ".join(f"{r[:2].upper()} rate descriptive only" for r in ("fp_rate", "fn_rate")
                           if bool(g.get(f"{r}_descriptive_only", False)))] for _, g in rg.iterrows()]
        L += ["Error rates of the majority vote, subset vs complement (Δ = subset − complement, cluster bootstrap CI; "
              "p with MC SE and B used, no p below the support floor):",
              "", to_markdown(pd.DataFrame(rows, columns=["task", "model", "FP rate sub / comp", "Δ FP rate [CI]",
                                                          "p FP", "FN rate sub / comp", "Δ FN rate [CI]", "p FN",
                                                          "n_pos sub / comp", "flags"])),
              "", f"Table: `error_analysis/error_rate_gap{sfx}.csv`; confusion by context and part for naive_rule, lr, "
                  f"rf, hgb, gnn_ggnn, hybrid_ggnn: `error_analysis/confusion{sfx}.csv`.", ""]
    names = ["rq4_subset", "rq4_subset_gap", "rq4_did", "rq4_did_frame_update", "rq4_ctx_category",
             "rq4_subsystem_markers"]
    if best is not None and len(best):
        names.insert(3, "rq4_did_bestval")
    L += [f"Tables: {_files(*[_tbl(n, sfx) for n in names])}; error analysis in `error_analysis/` (confusion, "
          f"disagreement sets, examples stratified by part and error `<task>_examples{sfx}.md`). Figures: "
          f"`figures/rq4_forest_pr_auc{sfx}_*`, `figures/rq4_forest_f1{sfx}_*` (hollow markers: < 30 positives).", ""]
    return L


def _section_ablation(T, ctx):
    L = ["## 7. Ablations", ""]
    ab = T.get("ablation")
    if ab is None or not len(ab):
        return L + ["Ablation models not available.", ""]
    rows = []
    for _, g in ab.iterrows():
        delta = "" if g["variant"] == "full" else (
            f"{_delta_ci(g, 'pr_auc_vs_full')} (p={_p_se(g, 'pr_auc_vs_full')}, "
            f"Holm {fmt_p(g.get('pr_auc_vs_full_p_holm'))})")
        rows.append([g["task"], g["scope"], g["variant"], g["model"], g["n"], g["n_pos"], _cell(g, "pr_auc"), delta])
    L += [f"PR-AUC and paired difference vs full (test resamples B = {ctx['B_test']}; Holm within task, over variants "
          "and scopes):", "",
          to_markdown(pd.DataFrame(rows, columns=["task", "scope", "variant", "model", "n", "n_pos", "PR-AUC [CI]",
                                                  "Δ vs full [CI]"])), "",
          f"With F1 and every metric: {_files(_tbl('ablation', ctx['sfx']))}. Figure: `figures/ablation{ctx['sfx']}_*`.", ""]
    return L


def _pairwise_display(pw):
    rows = []
    for _, g in pw.iterrows():
        rows.append([g["task"], f"{g['model_a']} vs {g['model_b']}", g["n"], _delta_ci(g, "pr_auc"),
                     _p_se(g, "pr_auc"), fmt_p(g["pr_auc_p_holm"]), _delta_ci(g, "macro_pr_auc"),
                     _p_se(g, "macro_pr_auc"), fmt_p(g.get("macro_pr_auc_p_holm")),
                     f"{fmt_p(g['pr_auc_wilcoxon_p'])} (n={g['pr_auc_wilcoxon_n']})",
                     f"{fmt_signed(g['pr_auc_cliffs_delta'], 2)} {g['pr_auc_cliffs_magnitude']}",
                     _delta_ci(g, "f1"), fmt_p(g["f1_p_holm"])])
    return pd.DataFrame(rows, columns=["task", "comparison", "n", "Δ PR-AUC pooled [CI]", "p (MC SE; B used)", "p Holm",
                                       "Δ PR-AUC macro [CI]", "p macro (MC SE; B used)", "p Holm (macro)",
                                       "Wilcoxon p", "Cliff's δ", "Δ F1 [CI]", "p Holm (F1)"])


def _section_tests(T, ctx):
    sfx = ctx["sfx"]
    L = ["## 8. Statistical tests", ""]
    pw = T.get("pairwise")
    if pw is not None and len(pw):
        L += [f"Paired cluster bootstrap (B = {ctx['B_test']}) of the pooled difference A - B (primary) and of the "
              "macro difference (mean over test repositories of the per-repository PR-AUC), Holm within task per "
              "metric; Wilcoxon signed-rank over test repositories on seed-mean PR-AUC; Cliff's delta over "
              "per-(repository, seed) PR-AUC:", "", to_markdown(_pairwise_display(pw)), "",
              "Pooled PR-AUC ranks the concatenated scores of fold-specific models; scores of different folds are not "
              "calibrated to a common scale (cross-fold calibration), so the pooled value mixes ranking quality "
              "within folds with score shifts between folds. The macro value ranks within each fold only; its "
              "bootstrap uses only the resamples in which every test repository has a positive (B used).", ""]
        if "macro_no_few_commit_pr_auc_delta" in pw:
            d = pw[pw["macro_no_few_commit_pr_auc_delta"].notna()]
            rows = [[g["task"], f"{g['model_a']} vs {g['model_b']}", g["few_commit_folds_excluded"],
                     _delta_ci(g, "macro_pr_auc"), _p_se(g, "macro_pr_auc"), fmt_p(g.get("macro_pr_auc_p_holm")),
                     _delta_ci(g, "macro_no_few_commit_pr_auc"), _p_se(g, "macro_no_few_commit_pr_auc"),
                     fmt_p(g.get("macro_no_few_commit_pr_auc_p_holm"))] for _, g in d.iterrows()]
            if rows:
                L += ["Macro PR-AUC difference with and without the few-commit folds (positives from at most 2 "
                      "commits; Holm within task over the pairs, separately for each column):", "",
                      to_markdown(pd.DataFrame(rows, columns=["task", "comparison", "folds left out",
                                                              "Δ macro [CI]", "p (MC SE; B used)", "p Holm",
                                                              "Δ macro without them [CI]",
                                                              "p without (MC SE; B used)", "p Holm without"])), ""]
        L += [f"Full table (F1 tests, Wilcoxon Holm, statistics): {_files(_tbl('pairwise', sfx))}.", ""]
    sens = T.get("sensitivity_ratio")
    if sens is not None and len(sens):
        d = sens.copy()
        d["key"] = d["task"] + " / " + d["model"]
        L += ["Negative-ratio sensitivity, pooled PR-AUC (the prevalence differs by setting, so values are not "
              "comparable across columns without it; see `prevalence` in the table):", "",
              *_pivot_lines(d, "pr_auc", row="key", col="setting"),
              f"Full table: {_files(_tbl('sensitivity_ratio', sfx))}.", ""]
    mc = T.get("multiclass")
    if mc is not None and len(mc):
        cols = ["model", "n"] + [c for c in ("macro_f1", "balanced_accuracy", "mcc", "macro_precision", "macro_recall",
                                             "macro_pr_auc", "accuracy") if f"{c}_mean" in mc]
        rows = [[r["model"], fmt(r["n"])] + [fmt_mean_sd(r.get(f"{c}_mean"), r.get(f"{c}_sd")) for c in cols[2:]]
                for _, r in mc.iterrows()]
        top = mc.loc[mc["model"] == "majority_class", "predicts"] if "predicts" in mc else pd.Series(dtype=object)
        L += ["Multiclass supplement (method level, pooled over folds; mean ± sd over seeds). The majority_class row "
              f"always predicts {top.iloc[0] if len(top) else 'the most frequent class'}; accuracy is listed last "
              "because the majority class alone reaches most of it:", "",
              to_markdown(pd.DataFrame(rows, columns=cols)), "",
              f"Per class: {_files(_tbl('multiclass_per_class', sfx))}.", ""]
    return L


def _section_sensitivity(T, ctx):
    sfx = ctx["sfx"]
    L = ["## 9. Sensitivity analysis: ADD_LOG commit-time view (add_log_post)", ""]
    pooled = T.get("sens_add_log_post_pooled")
    if pooled is None or not len(pooled):
        return L + ["No predictions for add_log_post; the sensitivity analysis was not run.", ""]
    comp = T.get("sens_add_log_post_vs_add_log")
    paired = comp is not None and len(comp) and comp["paired"].astype(bool).all()
    L += ["Not part of the primary analysis. add_log_post is the ADD_LOG task in the "
          "masked post-state ('commit-time') view: every statement added in the commit is removed, with complete "
          "masking. The primary add_log view is the pre-state method. Every Holm family below is separate from the "
          "primary families.", ""]
    if paired:
        L += ["The evaluated instances (positives, negatives, folds) and the commit-cluster resamples are those of "
              "add_log, so the two views are compared pairwise.", ""]
    else:
        L += ["The evaluated instances differ from those of add_log (see the notices), so the views are compared "
              "without a paired test.", ""]
    split = ctx.get("view_split") or {}
    if split.get("n"):
        changed = (f"the performance-sensitive flag differs for {split['n_perf_changed']} of {split['n']} instances "
                   f"({split['n_perf_changed_pos']} positives) and the context category for "
                   f"{split['n_category_changed']} ({split['n_category_changed_pos']} positives)")
        if str(split.get("source", "")).startswith("pre-state"):
            L += ["The subset/complement split and the context categories of the tables below are those of the "
                  "pre-state view, so both views are compared on the same split; computed on the masked method, "
                  f"{changed}.", ""]
        else:
            L += ["The subset/complement split below is computed on the masked method (d_* flags of add_log_post); "
                  f"compared with the pre-state view, {changed}.", ""]
    if comp is not None and len(comp):
        rows = [[g["model"], g["n"], f"{g['pr_auc_pre']:.3f}", f"{g['pr_auc_post']:.3f}", _delta_ci(g, "pr_auc"),
                 fmt_p(g["pr_auc_p_holm"]), f"{g['f1_pre']:.3f}", f"{g['f1_post']:.3f}", _delta_ci(g, "f1"),
                 fmt_p(g["f1_p_holm"])] for _, g in comp.iterrows()]
        L += ["Pooled PR-AUC and F1 per model in both views; Δ = commit-time − pre-state, paired cluster bootstrap "
              "on identical resamples, Holm over the models per metric:", "",
              to_markdown(pd.DataFrame(rows, columns=["model", "n", "PR-AUC pre-state", "PR-AUC commit-time",
                                                      "Δ PR-AUC [CI]", "p Holm", "F1 pre-state", "F1 commit-time",
                                                      "Δ F1 [CI]", "p Holm (F1)"])), ""]
    else:
        L += ["Pooled PR-AUC (commit-time view):", ""] + _pivot_lines(pooled, "pr_auc")
    pw = T.get("sens_add_log_post_pairwise")
    if pw is not None and len(pw):
        L += ["Key comparisons in the commit-time view (Holm within this family):", "",
              to_markdown(_pairwise_display(pw)), ""]
    did = T.get("sens_add_log_post_did")
    if did is not None and len(did):
        L += ["RQ4 difference-in-differences in the commit-time view (hybrid_ggnn - hgb):", "",
              to_markdown(_did_display(did)), ""]
    names = [n for n in ("sens_add_log_post_pooled", "sens_add_log_post_macro", "sens_add_log_post_per_repo",
                         "sens_add_log_post_vs_add_log", "sens_add_log_post_pairwise", "sens_add_log_post_subset",
                         "sens_add_log_post_did") if T.get(n) is not None and len(T[n])]
    L += [f"Tables: {_files(*[_tbl(n, sfx) for n in names])}.", ""]
    return L


def _section_posthoc(T, ctx):
    sfx = ctx["sfx"]
    L = ["## 10. Post-hoc analysis: log1p preprocessing of tabular features (not pre-specified)", ""]
    pooled = T.get("posthoc_log1p_pooled")
    if pooled is None or not len(pooled):
        return L + ["No predictions for the post-hoc models (" + ", ".join(POSTHOC_BASE) + ").", ""]
    L += ["POST-HOC, added after the primary results were seen, not tuned. lr_log1p, "
          "mlp_full_log1p and hybrid_ggnn_log1p equal lr, mlp_full and hybrid_ggnn except that every non-binary "
          "tabular column (more than 2 distinct values in the fit part) is transformed x → sign(x)·log1p(|x|) "
          "before imputation and standardisation. The primary models keep the pre-specified preprocessing; these "
          "results answer no research question on their own and are not part of any primary table, figure or "
          "Holm family. They are evaluated on the primary instances and resamples.", "",
          "The transform also hits columns that the feature build already stores as log1p counts (the 128 `x_` "
          "lexical buckets, `h_commit_index`, `h_file_prior_churn`): those that are non-binary in the fit part are "
          "transformed twice.", ""]
    tr = T.get("posthoc_log1p_training")
    if tr is not None and len(tr) and "n_log1p_columns_mean" in tr:
        d = tr[tr["n_log1p_columns_mean"].notna()]
        L += ["Transformed columns per fold, from the sidecars (mean over folds and seeds; per group; "
              "of them already log1p counts):", ""]
        for r in d.itertuples():
            twice = "–" if _isnan(r.n_log1p_twice_mean) else f"{round(r.n_log1p_twice_mean, 1):g}"
            L.append(f"- {r.model} / {r.task}: {round(r.n_log1p_columns_mean, 1):g} columns "
                     f"({r.log1p_columns_by_group}); {twice} of them transformed twice.")
        L.append("")
    else:
        L += ["The sidecars of these runs do not list the transformed columns.", ""]
    order = [m for m in ["lr", "lr_log1p", "mlp_full", "mlp_full_log1p", "hybrid_ggnn", "hybrid_ggnn_log1p", "hgb"]
             if m in set(pooled["model"])]
    L += ["Pooled PR-AUC (post-hoc models next to their pre-specified versions and hgb):", ""]
    L += _pivot_lines(pooled, "pr_auc", order=order)
    L += ["Pooled F1:", ""] + _pivot_lines(pooled, "f1", order=order)
    pw = T.get("posthoc_log1p_pairwise")
    if pw is not None and len(pw):
        L += ["Paired comparisons (Holm within task over these post-hoc comparisons only):", "",
              to_markdown(_pairwise_display(pw)), ""]
    names = [n for n in ("posthoc_log1p_pooled", "posthoc_log1p_macro", "posthoc_log1p_pairwise",
                         "posthoc_log1p_training") if T.get(n) is not None and len(T[n])]
    L += [f"Tables: {_files(*[_tbl(n, sfx) for n in names])}.", ""]
    return L


def _section_limits(T, ctx):
    L = ["## 11. Limitations of evidence", ""]
    B, Bt = ctx["B"], ctx["B_test"]
    L.append(f"- Confidence intervals of single metrics use B = {B} resamples, paired tests (pairwise, ablation, "
             f"difference-in-differences, subset gaps) B = {Bt}. Bootstrap p-values cannot be smaller than "
             f"2/(B+1) = {2 / (Bt + 1):.5f}; Holm-adjusted values are bounded below by that floor times the family "
             "size. The Monte-Carlo standard error of each p is reported next to it.")
    L.append("- RQ4 reference model: the difference-in-differences uses hgb as reference, fixed a priori, "
             "because choosing the best classical model on the test folds would be a post-hoc selection on test data. "
             "A reference chosen on validation PR-AUC is reported as a sensitivity check (section 6).")
    L.append("- PR-AUC depends on the prevalence; group comparisons (subset/complement, categories, engines, sizes, "
             "ecosystems, repositories) differ in prevalence and are read through lift and ROC-AUC.")
    L.append("- Pooled ranking metrics concatenate fold-specific models whose scores are not calibrated across "
             "folds; the macro values and the macro paired bootstrap are reported next to them.")
    L.append("- A bootstrap resample without a positive in the instances a value needs leaves that value undefined; "
             "such resamples are left out and every CI and test reports how many it used (b_used, B used). A macro "
             "value (CI, macro paired test, macro without few-commit folds) is defined only in the resamples in "
             "which every repository of the macro has a positive, so all its resamples estimate the same mean over "
             "the same repositories; the resamples left out are those in which a repository with positives from "
             "few commits drew none of them.")
    L.append(f"- Support floor: a comparison on a part with {_floor_text(ctx)} (the few-commit rule of the folds) is "
             "descriptive only: Δ and CI are shown, without p, and it is not counted in its Holm family.")
    floor_rows = []
    for name in ("rq4_did", "rq4_did_frame_update", "rq4_did_bestval", "sens_add_log_post_did"):
        d = T.get(name)
        if d is not None and len(d) and "descriptive_only" in d:
            floor_rows += [f"{name} {g['task']} ({_support_note(g)})" for _, g in d.iterrows()
                           if bool(g["descriptive_only"])]
    gap = T.get("rq4_subset_gap")
    if gap is not None and len(gap) and "descriptive_only" in gap:
        floor_rows += [f"rq4_subset_gap {task}" for task in gap.loc[gap["descriptive_only"].astype(bool), "task"].unique()]
    if floor_rows:
        L.append("- Descriptive only in this run (below the support floor): " + "; ".join(floor_rows) + ".")
    folds = ctx.get("folds") or {}
    few = ctx.get("few_commit") or {}
    for task in ctx["tasks"]:
        f = folds.get(task)
        if not f:
            continue
        excl = ", ".join(f"{k} ({v})" for k, v in (f.get("excluded") or {}).items()) or "none"
        L.append(f"- {task}: test repositories {', '.join(f.get('test_repos', [])) or '(none)'}; low-support folds "
                 f"(< 30 positives): {', '.join(f.get('low_support', [])) or 'none'}; not a test fold (< 10 positives): "
                 f"{excl}; few-commit folds: {', '.join(few.get(task, [])) or 'none'}.")
    per_repo = T.get("rq3_per_repo")
    if per_repo is not None and len(per_repo):
        partial = per_repo["partial"].astype(bool) if "partial" in per_repo else pd.Series(False, index=per_repo.index)
        ref = per_repo[~partial & (per_repo["n"] > 0)]
        low = ref[ref["low_support"].astype(bool)].groupby("task")["test_repo"].unique()
        for task, repos in low.items():
            L.append(f"- {task}: evaluated repositories with < 30 positives: {', '.join(sorted(repos))}.")
        gaps = per_repo[partial & (per_repo["n"] == 0)].groupby(["task", "model"])["test_repo"].unique()
        for (task, model), repos in gaps.items():
            L.append(f"- {task}: {model} (partial) has no evaluated instance in {', '.join(sorted(repos))}; "
                     "its macro values average over the other test repositories.")
        for task, k in per_repo.groupby("task")["test_repo"].nunique().items():
            L.append(f"- {task}: Wilcoxon over {k} test repositories; smallest attainable two-sided p = {2 / 2 ** k:.4f}.")
    for task, models in ctx["models_by_task"].items():
        missing = [m for m in ctx["model_order"] if m not in models]
        if missing:
            L.append(f"- {task}: no predictions for {', '.join(missing)}.")
    if ctx["notices"]:
        L += ["", "Notices raised during evaluation:", ""] + [f"- {n}" for n in ctx["notices"]]
    L.append("")
    return L


def experiment_report(ctx):
    """Markdown lines of data/results/report/experiment_report.md.

    ctx: setting, sfx, B, B_test, ratio, tasks, generated, tables (name -> DataFrame or None), notices,
    folds, few_commit, ecosystem_source, models_by_task, model_order, error_summary, rate_gap,
    did_validation, extraction (n annotated, n rows, problems), sens_models, posthoc_models, view_split
    (analysis.align_view_split), min_test_positives and few_commits (support floor).
    """
    T = ctx["tables"]
    ctx.setdefault("B_test", ctx["B"])
    L = [f"# Experiment report ({ctx['setting']})", "",
         f"Generated {ctx['generated']}. Paths are relative to `data/results/`. Protocol: leave-one-repository-out; "
         "metrics pooled over the test folds unless stated; mean ± sd over training seeds; 95% CI = percentile "
         f"cluster bootstrap over commits within repositories (B = {ctx['B']}, seed {ctx.get('seed', 42)}) of the seed mean; paired "
         f"tests on B = {ctx['B_test']} resamples of the same clusters. Every table lists n (instances) and n_pos "
         "(positives). This report states measurements only. The primary analysis covers add_log (pre-state view), "
         "remove_log and change_level with the 12 pre-specified models; the commit-time view (add_log_post) and the "
         "post-hoc log1p models appear only in sections 9 and 10.", "",
         "## Models available", ""]
    for task, models in ctx["models_by_task"].items():
        L.append(f"- {task}: {', '.join(models) if models else '(none)'}")
    for task, models in (ctx.get("sens_models") or {}).items():
        L.append(f"- sensitivity {task}: {', '.join(models) if models else '(none)'}")
    for task, models in (ctx.get("posthoc_models") or {}).items():
        L.append(f"- post-hoc ({task}): {', '.join(models) if models else '(none)'}")
    L.append("")
    L += _section_summary(T, ctx)
    L += _section_quality(T, ctx)
    L += _section_rq1(T, ctx)
    L += _section_rq2(T, ctx)
    L += _section_rq3(T, ctx)
    L += _section_rq4(T, ctx)
    L += _section_ablation(T, ctx)
    L += _section_tests(T, ctx)
    L += _section_sensitivity(T, ctx)
    L += _section_posthoc(T, ctx)
    L += _section_limits(T, ctx)
    return L
