"""Matplotlib visualisations for EVA-02 cluster quality evaluation.

This module produces the descriptive plots referenced by the EVA-02
Markdown report. All plots are saved as PNG into the configured
output directory.

Conventions
-----------

- Each plot uses ONE y-axis per metric (no mixing scales).
- Algorithms are mapped to **stable colors** via :data:`ALGORITHM_COLORS`,
  the single source of truth for cluster colors (per AGENTS.md §3
  visualization rule).
- Plots never display "best", "winner", "optimal", or "recommended"
  labels.

Hard constraints (AGENTS.md §2):

- No ranking / "best/winner/optimal/recommended/final" labels.
- No mutation of source EVA-01 artifacts.
- All values come from the EVA-01 DataFrame.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import matplotlib

# Use a non-interactive backend so we can run inside a CI shell.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection)
import pandas as pd  # noqa: E402

from customer_segmentation.evaluation.eva02.metrics import (  # noqa: E402
    METRIC_COLUMNS,
    extract_metric_vector,
)

__all__ = [
    "ALGORITHM_COLORS",
    "plot_metric_vs_k",
    "plot_metric_by_algorithm",
    "plot_metric_by_preprocessing",
    "plot_metric_by_hyperparameter_family",
    "plot_metric_distributions",
]


# Stable algorithm -> color mapping. This is the single source of truth
# for cluster colors (per AGENTS.md §3). Do NOT redefine elsewhere.
ALGORITHM_COLORS: dict[str, str] = {
    "kmeans": "#1f77b4",          # blue
    "agglomerative": "#ff7f0e",    # orange
    "dbscan": "#2ca02c",           # green
    "gmm": "#d62728",              # red
    "fuzzy_cmeans": "#9467bd",     # purple
}


def _algorithm_color(algo: str) -> str:
    """Return the canonical color for an algorithm."""
    return ALGORITHM_COLORS.get(algo, "#7f7f7f")


def _save_figure(fig, output_path: Path) -> None:
    """Save a figure and close it."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def _filter_metric(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Drop rows that have NaN for the requested metric."""
    if metric not in df.columns:
        return df.iloc[0:0]
    sub = df.copy()
    sub[metric] = sub[metric].apply(
        lambda v: float(v) if (v is not None and not isinstance(v, str)) else math.nan
    )
    return sub.loc[sub[metric].notna()]


# DBSCAN does not accept a ``n_clusters`` argument — its ``n_clusters``
# value in the repository reflects the *realized* cluster count after
# fitting. K-bearing algorithms (K-Means, Agglomerative, GMM,
# Fuzzy C-Means) report the *requested* K. The two semantics must not
# be mixed on the same ``metric-vs-K`` plot without explicit
# clarification. Per the EVA-02 post-implementation review, the
# plot uses a distinct marker for DBSCAN and a title suffix that
# documents the semantic difference.
DBSCAN_K_MARKER: str = "x"
DBSCAN_K_LINE_STYLE: str = "--"


# ---------------------------------------------------------------------------
# Plot builders
# ---------------------------------------------------------------------------


def plot_metric_vs_k(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
    experiments: Iterable[str] | None = None,
) -> list[Path]:
    """Produce one ``metric vs K`` plot per metric per experiment.

    Each plot has ``n_clusters`` on the x-axis and the metric value on
    the y-axis; one line per algorithm (color from
    :data:`ALGORITHM_COLORS`).

    K semantics
    -----------

    * K-Means / Agglomerative / GMM / Fuzzy C-Means are K-bearing
      algorithms: ``n_clusters`` is the *requested* K.
    * DBSCAN is a density-based algorithm: ``n_clusters`` is the
      *realized* cluster count. DBSCAN is plotted with a distinct
      marker (:data:`DBSCAN_K_MARKER`) and dashed line style, and the
      plot title is suffixed with a caveat that DBSCAN points are
      "realized K, not requested K".

    Per-K comparisons between K-bearing algorithms and DBSCAN therefore
    describe *different quantities*; the visual distinction is the
    single point that prevents the reader from inferring "DBSCAN was
    fitted with K=17" from the plot.
    """
    output_dir = Path(output_dir)
    paths: list[Path] = []
    metrics = list(metrics)
    experiments = list(experiments) if experiments is not None else None

    for exp, exp_df in df.groupby("source_experiment", dropna=False):
        if experiments is not None and exp not in experiments:
            continue
        for metric in metrics:
            work = _filter_metric(exp_df, metric)
            if work.empty:
                continue
            fig, ax = plt.subplots(figsize=(7, 4))
            for algo, sub in work.groupby("algorithm", dropna=False):
                if not isinstance(algo, str) or not algo:
                    continue
                ordered = sub.sort_values("n_clusters")
                if algo == "dbscan":
                    ax.plot(
                        ordered["n_clusters"].astype(int),
                        ordered[metric],
                        marker=DBSCAN_K_MARKER,
                        linestyle=DBSCAN_K_LINE_STYLE,
                        label=f"{algo} (realized K)",
                        color=_algorithm_color(algo),
                    )
                else:
                    ax.plot(
                        ordered["n_clusters"].astype(int),
                        ordered[metric],
                        marker="o",
                        label=f"{algo} (requested K)",
                        color=_algorithm_color(algo),
                    )
            ax.set_xlabel("K (n_clusters) — K-bearing: requested; DBSCAN: realized")
            ax.set_ylabel(metric)
            ax.set_title(
                f"{metric} vs K — {exp} "
                f"(DBSCAN points are realized K, not requested K)"
            )
            ax.grid(True, linestyle=":", alpha=0.5)
            ax.legend(loc="best", fontsize=8)
            output_path = (
                output_dir / f"eva02_{exp.lower()}_metric_{metric}_vs_k.png"
            )
            _save_figure(fig, output_path)
            paths.append(output_path)
    return paths


def plot_metric_by_algorithm(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
    experiments: Iterable[str] | None = None,
) -> list[Path]:
    """Produce one ``metric by algorithm`` boxplot per metric per experiment."""
    output_dir = Path(output_dir)
    paths: list[Path] = []
    metrics = list(metrics)
    experiments = list(experiments) if experiments is not None else None

    for exp, exp_df in df.groupby("source_experiment", dropna=False):
        if experiments is not None and exp not in experiments:
            continue
        for metric in metrics:
            work = _filter_metric(exp_df, metric)
            if work.empty:
                continue
            algos = sorted(work["algorithm"].dropna().astype(str).unique().tolist())
            data = [
                work.loc[work["algorithm"] == a, metric].astype(float).to_numpy()
                for a in algos
            ]
            fig, ax = plt.subplots(figsize=(7, 4))
            bp = ax.boxplot(
                data,
                labels=algos,
                patch_artist=True,
                showmeans=True,
                meanline=True,
            )
            for patch, algo in zip(bp["boxes"], algos):
                patch.set_facecolor(_algorithm_color(algo))
                patch.set_alpha(0.6)
            ax.set_ylabel(metric)
            ax.set_title(f"{metric} by algorithm — {exp}")
            ax.grid(True, axis="y", linestyle=":", alpha=0.5)
            ax.tick_params(axis="x", labelrotation=30)
            output_path = (
                output_dir / f"eva02_{exp.lower()}_metric_{metric}_by_algorithm.png"
            )
            _save_figure(fig, output_path)
            paths.append(output_path)
    return paths


def plot_metric_by_preprocessing(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> list[Path]:
    """Produce per-metric bar plots across EXP-04 preprocessing scenarios.

    Only EXP-04 rows have populated preprocessing columns. The function
    silently skips rows where preprocessing is ``MISSING``.
    """
    output_dir = Path(output_dir)
    paths: list[Path] = []
    metrics = list(metrics)

    work = df.copy()
    if "transformation" not in work.columns or "scaling" not in work.columns:
        return paths
    # Only rows with populated preprocessing belong to EXP-04.
    work = work.loc[
        (work["source_experiment"] == "EXP-04")
        & (work["transformation"].astype(str) != "MISSING")
        & (work["scaling"].astype(str) != "MISSING")
    ]
    if work.empty:
        return paths

    work["preprocessing_label"] = work.apply(
        lambda r: f"{r['transformation']}|{r['scaling']}",
        axis=1,
    )
    scenarios = sorted(work["preprocessing_label"].unique().tolist())

    for metric in metrics:
        sub = _filter_metric(work, metric)
        if sub.empty:
            continue
        means = sub.groupby("preprocessing_label")[metric].mean()
        stds = sub.groupby("preprocessing_label")[metric].std().fillna(0.0)
        ordered_labels = [s for s in scenarios if s in means.index]
        values = [means[s] for s in ordered_labels]
        errs = [stds.get(s, 0.0) for s in ordered_labels]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(ordered_labels, values, yerr=errs, capsize=4, color="#1f77b4", alpha=0.8)
        ax.set_ylabel(metric)
        ax.set_title(f"{metric} by preprocessing scenario — EXP-04")
        ax.grid(True, axis="y", linestyle=":", alpha=0.5)
        ax.tick_params(axis="x", labelrotation=20)
        output_path = output_dir / f"eva02_exp04_{metric}_by_preprocessing.png"
        _save_figure(fig, output_path)
        paths.append(output_path)
    return paths


def plot_metric_by_hyperparameter_family(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> list[Path]:
    """Produce per-algorithm bar plots across EXP-03 hyperparameter families."""
    output_dir = Path(output_dir)
    paths: list[Path] = []
    metrics = list(metrics)

    work = df.copy()
    work = work.loc[work["source_experiment"] == "EXP-03"]
    if work.empty:
        return paths

    # Identify the hyperparameter family from experiment_id
    # (kmeans-stageB-n_init-1 -> n_init; agglomerative-stageB-linkage-average -> linkage; ...).
    # Rows that do not match a known family token are surfaced with a
    # explicit ``unmapped`` label (NOT "OTHER") so the plot's x-axis
    # is honest about the boundary.
    from customer_segmentation.evaluation.eva02.comparison import (
        EXP03_HYPERPARAMETER_FAMILIES,
    )

    def _family(eid: object) -> str:
        if not isinstance(eid, str):
            return "unmapped"
        parts = eid.split("-")
        for token in parts[3:]:
            if token in EXP03_HYPERPARAMETER_FAMILIES:
                return EXP03_HYPERPARAMETER_FAMILIES[token]
        return "unmapped"

    work["_hp_family"] = work["experiment_id"].apply(_family)

    # Drop unmapped rows from the plot — they have no defined
    # hyperparameter family and would otherwise pollute the visual.
    work = work.loc[work["_hp_family"] != "unmapped"]
    if work.empty:
        return paths

    for metric in metrics:
        sub = _filter_metric(work, metric)
        if sub.empty:
            continue
        algos = sorted(sub["algorithm"].dropna().astype(str).unique().tolist())
        for algo in algos:
            algo_sub = sub.loc[sub["algorithm"] == algo]
            if algo_sub.empty:
                continue
            pivot = (
                algo_sub.groupby("_hp_family")[metric]
                .agg(["mean", "std", "count"])
                .reset_index()
            )
            pivot = pivot.sort_values("_hp_family")
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.bar(
                pivot["_hp_family"],
                pivot["mean"],
                yerr=pivot["std"].fillna(0.0),
                capsize=4,
                color=_algorithm_color(algo),
                alpha=0.8,
            )
            ax.set_ylabel(metric)
            ax.set_title(
                f"{metric} by EXP-03 hyperparameter family — {algo} "
                f"(rows outside known families are excluded)"
            )
            ax.grid(True, axis="y", linestyle=":", alpha=0.5)
            ax.tick_params(axis="x", labelrotation=20)
            output_path = (
                output_dir / f"eva02_exp03_{algo}_{metric}_by_hp_family.png"
            )
            _save_figure(fig, output_path)
            paths.append(output_path)
    return paths


def plot_metric_distributions(
    df: pd.DataFrame,
    output_dir: Path,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> list[Path]:
    """Produce per-metric distribution (histogram) plots across all rows."""
    output_dir = Path(output_dir)
    paths: list[Path] = []
    metrics = list(metrics)
    for metric in metrics:
        sub = _filter_metric(df, metric)
        if sub.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(sub[metric].astype(float).to_numpy(), bins=20, color="#1f77b4", alpha=0.8)
        ax.set_xlabel(metric)
        ax.set_ylabel("count")
        ax.set_title(f"Distribution of {metric} (all experiments)")
        ax.grid(True, linestyle=":", alpha=0.5)
        output_path = output_dir / f"eva02_distribution_{metric}.png"
        _save_figure(fig, output_path)
        paths.append(output_path)
    return paths
