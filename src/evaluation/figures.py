"""
Thesis figures (matplotlib, Agg backend), each written as PNG (200 dpi) and PDF with
English or French labels (src/evaluation/labels.py).

Every figure is drawn from a table that is also written to data/results/tables, so the
numbers behind a figure can always be read in the table. Colours: fixed categorical order
(blue, orange, aqua, yellow, magenta), one-hue blue ramp for magnitudes and ordered levels;
line styles double the colour for print and colour-blind readers.

Figures of model results name the negative-sampling setting (R1/R4/R10) in the title. French
figures use the decimal comma and a space before ':' (labels.num, labels.colon).
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from matplotlib.ticker import FuncFormatter

from src.evaluation.labels import (t, model_name, variant_name, task_name, context_name, colon, num, LEVELS,
                                   EVENT_LABELS, MODEL_ORDER)

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
LEVEL_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]
STYLES = ["-", "--", "-.", ":", (0, (5, 1, 1, 1))]
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 9,
    "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "axes.titlesize": 10,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def save(fig, out_dir, name, lang, sfx=""):
    """<name><sfx>_<lang>.png|pdf; sfx is the setting suffix of a non-primary run (e.g. '_R1')."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"{name}{sfx}_{lang}"
    fig.savefig(f"{stem}.png", dpi=200, bbox_inches="tight")
    fig.savefig(f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)
    return [Path(f"{stem}.png"), Path(f"{stem}.pdf")]


def _fr_axis(axis, lang, digits=None):
    """Decimal comma on a numeric axis of a French figure."""
    if lang != "fr":
        return

    def f(v, _pos):
        txt = f"{v:.{digits}f}" if digits is not None else f"{v:g}"
        return txt.replace(".", ",").replace("-", "−")

    axis.set_major_formatter(FuncFormatter(f))


def _setting_of(df, setting):
    if setting is None and df is not None and "setting" in df and len(df):
        setting = str(df["setting"].iloc[0])
    return setting


def _title(text, setting, lang):
    """Title with the negative-sampling setting on a second line."""
    if not setting:
        return text
    r = setting[1:] if setting.startswith("R") else setting
    return text + "\n" + t("setting_line", lang).format(s=setting, r=r)


def _ordered_models(models):
    return sorted(models, key=lambda m: (MODEL_ORDER.index(m) if m in MODEL_ORDER else 99, m))


def _partial(df):
    """Models evaluated on fewer instances than the rest (analysis.load_task), marked with a dagger."""
    return set(df.loc[df["partial"].astype(bool), "model"]) if "partial" in df else set()


def _label(m, lang, partial):
    return model_name(m, lang) + (" †" if m in partial else "")


def pr_step(prec, rec):
    """Vertices of the drawn PR step curve for metrics.pr_curve output (recall ascending).

    Precision P_i is drawn over the recall interval (R_{i-1}, R_i], as in average precision
    and sklearn's PrecisionRecallDisplay, so the area under the drawn curve equals PR-AUC.
    """
    prec = np.asarray(prec, dtype=float)
    rec = np.asarray(rec, dtype=float)
    return np.repeat(rec, 2)[:-1], np.repeat(prec, 2)[1:]


def fig_pr_curves(curves, prevalence, task, out_dir, lang="en", sfx="", setting=None):
    """curves: {model: (precision, recall)} for one task (pooled test folds, seed 0)."""
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    for i, m in enumerate(_ordered_models(curves)):
        x, y = pr_step(*curves[m])
        ax.plot(x, y, color=SERIES[i % len(SERIES)], linestyle=STYLES[i % len(STYLES)],
                linewidth=1.6, label=model_name(m, lang))
    if prevalence is not None and np.isfinite(prevalence):
        ax.axhline(prevalence, color=MUTED, linewidth=0.8)
        ax.text(0.01, prevalence, f"{t('chance', lang)} {num(prevalence, 2, lang)}", color=MUTED, va="bottom",
                ha="left", fontsize=7)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel(t("recall", lang))
    ax.set_ylabel(t("precision", lang))
    _fr_axis(ax.xaxis, lang)
    _fr_axis(ax.yaxis, lang)
    ax.set_title(_title(f"{task_name(task, lang)}{colon(lang)}{t('pr_curves', lang)}", setting, lang), fontsize=9)
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    return save(fig, out_dir, f"pr_curves_{task}", lang, sfx)


def fig_prauc_bars(pooled, out_dir, lang="en", sfx="", setting=None, name="prauc_bars"):
    """One panel per task: pooled PR-AUC (seed mean) with its 95% bootstrap CI for every model;
    the grey line is the prevalence (expected PR-AUC of a random ranking)."""
    setting = _setting_of(pooled, setting)
    tasks = [x for x in ["add_log", "remove_log", "change_level", "add_log_post"] if x in set(pooled["task"])]
    partial = _partial(pooled)
    fig, axes = plt.subplots(1, len(tasks), figsize=(3.4 * len(tasks), 3.8), squeeze=False, sharey=True,
                             layout="constrained")
    for ax, task in zip(axes[0], tasks):
        d = pooled[pooled["task"] == task].copy()
        d["order"] = [MODEL_ORDER.index(m) if m in MODEL_ORDER else 99 for m in d["model"]]
        d = d.sort_values("order")
        x = np.arange(len(d))
        mean = d["pr_auc_mean"].to_numpy()
        lo = mean - d["pr_auc_ci_lo"].to_numpy()
        hi = d["pr_auc_ci_hi"].to_numpy() - mean
        ax.bar(x, mean, width=0.6, color=SERIES[0], edgecolor="white", linewidth=1)
        ax.errorbar(x, mean, yerr=[np.nan_to_num(lo), np.nan_to_num(hi)], fmt="none", ecolor=INK, elinewidth=0.8,
                    capsize=2)
        prev = d["prevalence"].iloc[0] if "prevalence" in d else np.nan
        if np.isfinite(prev):
            ax.axhline(prev, color=MUTED, linewidth=0.8)
            if ax is axes[0][-1]:
                # labelled once, outside the plot area, so it never covers a bar; the value only
                # when every panel has the same prevalence (2 decimals)
                same = pooled[pooled["task"].isin(tasks)].groupby("task")["prevalence"].first().round(2).nunique() == 1
                text = f"{t('chance', lang)}\n{num(prev, 2, lang)}" if same else t("chance", lang)
                ax.text(1.01, prev, text, color=MUTED, va="center", ha="left", fontsize=6.5,
                        transform=ax.get_yaxis_transform())
        ax.set_xticks(x)
        ax.set_xticklabels([_label(m, lang, partial) for m in d["model"]], rotation=60, ha="right", fontsize=7)
        ax.set_title(task_name(task, lang))
        ax.set_ylim(0, 1)
        _fr_axis(ax.yaxis, lang)
        ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel(t("pr_auc", lang))
    fig.suptitle(_title(t("prauc_bars", lang), setting, lang), fontsize=10)
    if partial:
        # constrained layout places the note below the rotated tick labels
        fig.supxlabel(f"† {t('partial', lang)}", fontsize=7, color=INK2, x=0.01, ha="left")
    return save(fig, out_dir, name, lang, sfx)


def fig_repo_heatmap(per_repo, task, out_dir, lang="en", sfx="", setting=None):
    """PR-AUC per model and test repository; the column labels give the repository's prevalence,
    which differs between repositories when a negative pool is smaller than R x positives."""
    d = per_repo[per_repo["task"] == task]
    if not len(d):
        return []
    setting = _setting_of(d, setting)
    mat = d.pivot_table(index="model", columns="test_repo", values="pr_auc_mean", aggfunc="first")
    mat = mat.reindex(_ordered_models(mat.index))
    partial = _partial(d)
    # support of a repository comes from the complete models (a partial model may lack the fold)
    ref = d[~d["model"].isin(partial) & (d["n"] > 0)]
    low = (ref if len(ref) else d).groupby("test_repo")["low_support"].any()
    prev = (ref if len(ref) else d).groupby("test_repo")["prevalence"].first()
    fig, ax = plt.subplots(figsize=(1.0 + 0.75 * mat.shape[1], 0.9 + 0.32 * mat.shape[0]))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#86b6ef", "#2a78d6", "#104281"])
    im = ax.imshow(mat.to_numpy(dtype=float), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.iat[i, j]
            if np.isfinite(v):
                ax.text(j, i, num(v, 2, lang), ha="center", va="center", fontsize=6.5,
                        color="white" if v > 0.55 else INK)
    ax.set_xticks(range(mat.shape[1]))
    ax.set_xticklabels([f"{c}{'*' if low.get(c, False) else ''}\n{t('prev_short', lang)} {num(prev.get(c, np.nan), 2, lang)}"
                        for c in mat.columns], rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(mat.shape[0]))
    ax.set_yticklabels([_label(m, lang, partial) for m in mat.index], fontsize=7)
    ax.grid(False)
    ax.set_xlabel(t("repo", lang) + (f"  (* {t('low_support', lang)})" if low.any() else "")
                  + (f"  († {t('partial', lang)})" if partial else ""))
    ax.set_title(_title(f"{task_name(task, lang)}{colon(lang)}{t('heatmap', lang)}", setting, lang), fontsize=9)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label(t("pr_auc", lang))
    _fr_axis(cb.ax.yaxis, lang)
    cb.outline.set_visible(False)
    return save(fig, out_dir, f"prauc_heatmap_{task}", lang, sfx)


def fig_ablation(ablation, out_dir, lang="en", sfx="", setting=None):
    tasks = [x for x in ["add_log", "remove_log", "change_level"] if x in set(ablation["task"])]
    if not tasks:
        return []
    setting = _setting_of(ablation, setting)
    order = ["full", "no_history", "no_graph", "history_only", "graph_only"]
    fig, axes = plt.subplots(1, len(tasks), figsize=(3.4 * len(tasks), 3.4), squeeze=False, sharey=True)
    for ax, task in zip(axes[0], tasks):
        d = ablation[ablation["task"] == task]
        variants = [v for v in order if v in set(d["variant"])]
        x = np.arange(len(variants))
        for k, (scope, label) in enumerate([("full_test", t("full_test", lang)), ("subset", t("subset", lang))]):
            s = d[d["scope"] == scope].set_index("variant").reindex(variants)
            if s["pr_auc_mean"].isna().all():
                continue
            mean = s["pr_auc_mean"].to_numpy()
            err = [np.nan_to_num(mean - s["pr_auc_ci_lo"].to_numpy()), np.nan_to_num(s["pr_auc_ci_hi"].to_numpy() - mean)]
            ax.bar(x + (k - 0.5) * 0.36, mean, width=0.34, color=SERIES[k], edgecolor="white", linewidth=1,
                   label=label)
            ax.errorbar(x + (k - 0.5) * 0.36, mean, yerr=err, fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
        ax.set_xticks(x)
        ax.set_xticklabels([variant_name(v, lang) for v in variants], rotation=30, ha="right", fontsize=7)
        ax.set_title(task_name(task, lang))
        ax.set_ylim(0, 1)
        _fr_axis(ax.yaxis, lang)
        ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel(t("pr_auc", lang))
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=7, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.10))
    fig.suptitle(_title(t("ablation", lang), setting, lang), fontsize=9, y=1.06)
    return save(fig, out_dir, "ablation", lang, sfx)


def fig_forest(did, out_dir, lang="en", metric="pr_auc", sfx="", setting=None, name="rq4_forest"):
    """Rows per task: (hybrid - HGB) on the subset, on the complement, and their difference.
    A hollow marker flags a part with < 30 positives or below the support floor (the DiD row: either part)."""
    if did is None or not len(did):
        return []
    setting = _setting_of(did, setting)
    rows = []
    for _, r in did.iterrows():
        low_s = bool(r.get("low_support_subset", False)) or bool(r.get("below_floor_subset", False))
        low_c = bool(r.get("low_support_complement", False)) or bool(r.get("below_floor_complement", False))
        for part, key, low in (("subset", f"{metric}_subset", low_s), ("complement", f"{metric}_complement", low_c),
                               ("did", f"{metric}_did", low_s or low_c)):
            rows.append((task_name(r["task"], lang), part, r[f"{key}_delta"], r[f"{key}_ci_lo"], r[f"{key}_ci_hi"], low))
    labels = {"subset": t("subset", lang), "complement": t("complement", lang), "did": t("did", lang)}
    fig, ax = plt.subplots(figsize=(6.0, 0.9 + 0.32 * len(rows)))
    ypos = np.arange(len(rows))[::-1]
    colors = {"subset": SERIES[0], "complement": SERIES[1], "did": SERIES[2]}
    for y, (task, part, d, lo, hi, low) in zip(ypos, rows):
        ax.plot([lo, hi], [y, y], color=colors[part], linewidth=1.6, linestyle=":" if low else "-")
        ax.plot([d], [y], "o", color=colors[part], markersize=5.5, markerfacecolor="white" if low else colors[part],
                markeredgecolor=colors[part] if low else "white", markeredgewidth=1.2)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.set_yticks(ypos)
    ax.set_yticklabels([f"{task}{colon(lang)}{labels[part]}" for task, part, *_ in rows], fontsize=7)
    ax.grid(axis="y", visible=False)
    _fr_axis(ax.xaxis, lang)
    note = f"\n({t('hollow_low_support', lang)})" if any(r[-1] for r in rows) else ""
    ax.set_xlabel(f"{t('delta', lang)} {t(metric, lang)}{note}", fontsize=8)
    ax.set_title(_title(t("forest", lang), setting, lang), fontsize=9)
    return save(fig, out_dir, f"{name}_{metric}", lang, sfx)


def fig_ctx_category(ctx, out_dir, lang="en", sfx="", setting=None, models=("naive_prior", "hgb", "hybrid_ggnn")):
    """One panel per task: pooled PR-AUC (95% CI) per context category for a few models; the
    black tick is the category's prevalence (the expected PR-AUC of a random ranking)."""
    if ctx is None or not len(ctx):
        return []
    setting = _setting_of(ctx, setting)
    tasks = [x for x in ["add_log", "remove_log", "change_level"] if x in set(ctx["task"])]
    cats = ["frame_update", "loop", "subsystem", "general"]
    models = [m for m in models if m in set(ctx["model"])]
    if not tasks or not models:
        return []
    fig, axes = plt.subplots(1, len(tasks), figsize=(3.4 * len(tasks), 3.4), squeeze=False, sharey=True)
    w = 0.8 / len(models)
    for ax, task in zip(axes[0], tasks):
        d = ctx[ctx["task"] == task]
        present = [c for c in cats if c in set(d["ctx_category"])]
        x = np.arange(len(present))
        for k, m in enumerate(models):
            s = d[d["model"] == m].set_index("ctx_category").reindex(present)
            mean = s["pr_auc_mean"].to_numpy(dtype=float)
            err = [np.nan_to_num(mean - s["pr_auc_ci_lo"].to_numpy(dtype=float)),
                   np.nan_to_num(s["pr_auc_ci_hi"].to_numpy(dtype=float) - mean)]
            xs = x - 0.4 + w * (k + 0.5)
            ax.bar(xs, mean, width=w * 0.92, color=SERIES[k], edgecolor="white", linewidth=1,
                   label=model_name(m, lang))
            ax.errorbar(xs, mean, yerr=err, fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
        prev = d.groupby("ctx_category")["prevalence"].first().reindex(present).to_numpy(dtype=float)
        npos = d.groupby("ctx_category")["n_pos"].first().reindex(present)
        ax.hlines(prev, x - 0.42, x + 0.42, color=INK, linewidth=1.4)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{context_name(c, lang)}\nn_pos={int(npos[c])}" for c in present], rotation=30,
                           ha="right", fontsize=7)
        ax.set_title(task_name(task, lang))
        ax.set_ylim(0, 1)
        _fr_axis(ax.yaxis, lang)
        ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel(t("pr_auc", lang))
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=7, loc="upper center", ncol=len(models), bbox_to_anchor=(0.5, -0.12))
    fig.suptitle(_title(t("ctx_title", lang), setting, lang), fontsize=9, y=1.06)
    return save(fig, out_dir, "rq4_ctx_category", lang, sfx)


def fig_events_per_year(per_year, out_dir, lang="en"):
    """Core events per commit year (all repositories), stacked by label. Not setting-dependent."""
    if per_year is None or not len(per_year):
        return []
    d = per_year[per_year["repo"] == "ALL"].sort_values("year")
    if not len(d):
        return []
    years = d["year"].astype(int).to_numpy()
    fig, ax = plt.subplots(figsize=(2.0 + 0.32 * len(years), 3.2))
    bottom = np.zeros(len(d))
    for k, lab in enumerate(EVENT_LABELS):
        v = d[lab].to_numpy(dtype=float)
        ax.bar(years, v, bottom=bottom, width=0.75, color=SERIES[k], edgecolor="white", linewidth=0.8, label=lab)
        bottom += v
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right", fontsize=7)
    ax.set_xlabel(t("year", lang))
    ax.set_ylabel(t("core_events", lang))
    ax.grid(axis="x", visible=False)
    ax.set_title(t("per_year_title", lang), fontsize=9)
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    return save(fig, out_dir, "rq1_events_per_year", lang)


def fig_levels(levels, out_dir, lang="en"):
    """Stacked shares of formal statements per level and repository (snapshot)."""
    if levels is None or not len(levels):
        return []
    cols = LEVELS + (["unknown"] if "unknown" in levels.columns else [])
    d = levels.set_index("repo")[cols].astype(float)
    d = d[d.sum(axis=1) > 0]
    if not len(d):
        return []
    share = d.div(d.sum(axis=1), axis=0)
    colors = LEVEL_RAMP + ["#c3c2b7"]
    fig, ax = plt.subplots(figsize=(6.0, 0.6 + 0.3 * len(share)))
    left = np.zeros(len(share))
    y = np.arange(len(share))
    for k, lv in enumerate(cols):
        label = t("unknown_level", lang) if lv == "unknown" else lv
        ax.barh(y, share[lv], left=left, height=0.6, color=colors[k], edgecolor="white", linewidth=1, label=label)
        left += share[lv].to_numpy()
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r} (n={int(d.loc[r].sum())})" for r in share.index], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    _fr_axis(ax.xaxis, lang)
    ax.set_xlabel(t("share", lang))
    ax.grid(axis="y", visible=False)
    ax.set_title(t("levels_title", lang), fontsize=9)
    ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5))
    return save(fig, out_dir, "rq1_levels", lang)


def fig_core_events(rates, out_dir, lang="en"):
    if rates is None or not len(rates):
        return []
    d = rates.sort_values("core_total", ascending=False)
    x = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(2.0 + 0.7 * len(d), 3.4))
    w = 0.26
    for k, lab in enumerate(EVENT_LABELS):
        ax.bar(x + (k - 1) * w, d[f"core_{lab}"], width=w - 0.02, color=SERIES[k], edgecolor="white", linewidth=1,
               label=lab)
    ax.set_xticks(x)
    ax.set_xticklabels(d["repo"], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel(t("core_events", lang))
    ax.grid(axis="x", visible=False)
    ax.set_title(t("core_title", lang), fontsize=9)
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    return save(fig, out_dir, "rq1_core_events", lang)


def fig_transitions(trans, out_dir, lang="en"):
    if trans is None or not len(trans):
        return []
    mat = trans.set_index("pre_level").reindex(LEVELS)[LEVELS].fillna(0).astype(float)
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#86b6ef", "#2a78d6", "#104281"])
    vmax = max(mat.to_numpy().max(), 1)
    im = ax.imshow(mat.to_numpy(), cmap=cmap, vmin=0, vmax=vmax)
    for i in range(5):
        for j in range(5):
            v = mat.iat[i, j]
            if i != j or v > 0:
                ax.text(j, i, f"{int(v)}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.55 * vmax else INK)
    ax.set_xticks(range(5))
    ax.set_xticklabels(LEVELS, fontsize=7)
    ax.set_yticks(range(5))
    ax.set_yticklabels(LEVELS, fontsize=7)
    ax.set_xlabel(t("level_after", lang))
    ax.set_ylabel(t("level_before", lang))
    ax.grid(False)
    ax.set_title(f"{t('transition_title', lang)} (n={int(mat.to_numpy().sum())})", fontsize=9)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.outline.set_visible(False)
    return save(fig, out_dir, "rq1_change_level_heatmap", lang)
