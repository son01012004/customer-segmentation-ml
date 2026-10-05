"""CP-03 visualisation.

CP-03 produces three chart families that complement the CP-02 boxplots
and heatmaps:

1. **Violin plot** — per (analysis unit, feature) showing the cluster
   distribution shape. We use a compact feature subset for readability,
   matching the CP-02 boxplot subset (RFM core + behavioural +
   cancellation). The violin shape is symmetric about the median and
   shows the kernel density estimate; cluster medians and the OVERALL
   median are marked.

2. **Distinguishing feature summary chart** — per analysis unit, a
   horizontal bar chart of ``effect_range_rel_pct`` (relative range of
   cluster medians divided by OVERALL median × 100) for each feature,
   sorted descending. Bars are coloured by analytical classification
   (HIGH / MODERATE / LOW_DIFFERENCE_OBSERVED, HIGH_OVERLAP,
   NOT_ASSESSABLE). This is the headline chart for CP-03 — it shows
   which features distinguish clusters and which do not.

3. **IQR overlap summary heatmap** — per analysis unit, a heatmap of
   feature × {mean_iqr_overlap, median_iqr_overlap, min_iqr_overlap,
   max_iqr_overlap}. Reads as a "how much do cluster IQRs overlap?"
   summary, complementing the bar chart (which shows effect range).

Hard constraints (AGENTS.md §2):

- No ranking, no "best", no "winner".
- No segment naming.
- No Marketing recommendation.
- DBSCAN noise excluded.
- EXP-03 working-selected units produce no charts (no labels).
- Colour choices come from existing CP-01 ``ALGORITHM_COLORS`` palette
  (single source of truth) and a fixed qualitative palette for
  classification categories (single source of truth here).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from customer_segmentation.profiling.cp01.visualization import (
    ALGORITHM_COLORS,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)
from customer_segmentation.profiling.cp03.difference_analysis import (
    Cp03DistinguishingRow,
    compute_distinguishing_feature_table,
)

# Compact subset of features for violin plots. Mirrors CP-02's
# BOXPLOT_FEATURE_SUBSET so the two chart families line up.
VIOLIN_FEATURE_SUBSET: tuple[str, ...] = (
    "Recency",
    "Frequency",
    "Monetary",
    "TotalQuantity",
    "TenureDays",
    "ActiveDays",
    "CancellationRate",
)

# Single-source-of-truth palette for analytical classifications.
CLASSIFICATION_COLORS: dict[str, str] = {
    "HIGH_DIFFERENCE_OBSERVED": "#d62728",  # red — strong separation
    "MODERATE_DIFFERENCE_OBSERVED": "#ff7f0e",  # orange — partial
    "LOW_DIFFERENCE_OBSERVED": "#2ca02c",  # green — minimal
    "HIGH_OVERLAP": "#9467bd",  # purple — overlapping
    "NOT_ASSESSABLE": "#7f7f7f",  # grey — cannot assess
}

CLASSIFICATION_ORDER: tuple[str, ...] = (
    "HIGH_DIFFERENCE_OBSERVED",
    "MODERATE_DIFFERENCE_OBSERVED",
    "LOW_DIFFERENCE_OBSERVED",
    "HIGH_OVERLAP",
    "NOT_ASSESSABLE",
)


def _cluster_order(unit: Cp02AnalysisUnit) -> list[int]:
    """Return cluster ids present in the unit, excluding noise, sorted."""
    if not unit.labels_persisted:
        return []
    df = unit.cluster_labels_frame
    eligible = df.loc[df["ClusterLabel"] != -1]
    return sorted(int(c) for c in eligible["ClusterLabel"].unique())


def render_violin_plot(
    unit: Cp02AnalysisUnit,
    feature: str,
    out_path: Path,
) -> Path:
    """Render a per-cluster violin plot for one (unit, feature).

    Each cluster is rendered as a violin showing the kernel density
    estimate of the RAW feature values. Cluster medians and the OVERALL
    median are marked.

    The plot is deliberately complementary to the CP-02 boxplot: it
    shows the shape of the distribution, not just the quartile summary.
    """
    if not unit.labels_persisted:
        return out_path
    df = unit.cluster_labels_frame
    eligible = df.loc[df["ClusterLabel"] != -1].copy()
    cluster_ids = _cluster_order(unit)
    if not cluster_ids:
        return out_path
    fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(cluster_ids) + 4), 5.0))
    data: list[np.ndarray] = []
    positions: list[int] = []
    palette = plt.get_cmap("tab10").colors
    for i, cl in enumerate(cluster_ids):
        sub = eligible.loc[eligible["ClusterLabel"] == cl, feature].dropna()
        if len(sub) < 2:
            # Need at least 2 points to draw a violin.
            continue
        data.append(sub.values)
        positions.append(i)
    if not data:
        plt.close(fig)
        return out_path
    parts = ax.violinplot(
        data,
        positions=positions,
        widths=0.7,
        showmedians=True,
        showextrema=False,
    )
    for body, c in zip(parts["bodies"], positions, strict=False):
        body.set_facecolor(palette[c % len(palette)])
        body.set_edgecolor("black")
        body.set_alpha(0.55)
    if "cmedians" in parts:
        parts["cmedians"].set_color("black")
        parts["cmedians"].set_linewidth(1.4)
    # OVERALL median reference line.
    overall_median = float(eligible[feature].dropna().median())
    ax.axhline(
        overall_median,
        color="red",
        linestyle="--",
        linewidth=1.0,
        label=f"OVERALL median = {overall_median:.2f}",
    )
    ax.set_xticks(positions)
    ax.set_xticklabels([f"C{cluster_ids[i]}" for i in positions], fontsize=9)
    ax.set_xlabel("Cluster id (per source artifact)", fontsize=9)
    ax.set_ylabel(f"{feature} (RAW value)", fontsize=9)
    ax.set_title(
        f"CP-03 — {feature} by cluster (violin)\n"
        f"{unit.source_experiment} / {unit.algorithm}\n"
        f"{unit.unit_id}",
        fontsize=10,
    )
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def render_distinguishing_heatmap(
    unit: Cp02AnalysisUnit,
    distinguishing_rows: Sequence[Cp03DistinguishingRow],
    out_path: Path,
) -> Path:
    """Render a per-unit horizontal bar chart of effect_range_rel_pct.

    Each bar is one feature; bar length = effect_range_rel_pct (%);
    bar colour = analytical classification. Bars are sorted descending
    by effect_range_rel_pct so the most distinguishing features
    appear at the top.

    Features with ``classification = NOT_ASSESSABLE`` are included but
    shown with NaN bar (empty), coloured grey.
    """
    if not unit.labels_persisted:
        return out_path
    rows = [r for r in distinguishing_rows if r.unit_id == unit.unit_id]
    if not rows:
        return out_path
    df = pd.DataFrame(
        [
            {
                "feature": r.feature,
                "effect_range_rel_pct": r.effect_range_rel_pct,
                "iqr_overlap_mean": r.iqr_overlap_mean,
                "classification": r.classification,
            }
            for r in rows
        ]
    )
    df["abs_effect"] = df["effect_range_rel_pct"].abs()
    df = df.sort_values(["classification", "abs_effect"], ascending=[True, False]).reset_index(
        drop=True
    )
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    y = np.arange(len(df))
    colours = [CLASSIFICATION_COLORS.get(c, "#7f7f7f") for c in df["classification"]]
    # Plot bars: NaN values are skipped (matplotlib emits a RuntimeWarning
    # if we don't handle them) — replace NaN with 0 only for plotting,
    # but show them with hatch "x" to indicate no value.
    plot_vals = df["effect_range_rel_pct"].fillna(0.0).values
    ax.barh(y, plot_vals, color=colours, edgecolor="black", linewidth=0.5)
    # Mark NaN bars with diagonal hatch overlay.
    nan_mask = df["effect_range_rel_pct"].isna()
    if nan_mask.any():
        ax.barh(
            y[nan_mask],
            np.zeros(int(nan_mask.sum())),
            color="none",
            edgecolor="grey",
            hatch="///",
            linewidth=0.5,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(df["feature"].tolist(), fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Effect range relative to OVERALL median (%)", fontsize=9)
    ax.set_title(
        f"CP-03 — Distinguishing feature summary\n"
        f"{unit.source_experiment} / {unit.algorithm}\n"
        f"{unit.unit_id}",
        fontsize=10,
    )
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    # Legend.
    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=CLASSIFICATION_COLORS[c], edgecolor="black", label=c)
        for c in CLASSIFICATION_ORDER
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def render_iqr_overlap_heatmap(
    unit: Cp02AnalysisUnit,
    distinguishing_rows: Sequence[Cp03DistinguishingRow],
    out_path: Path,
) -> Path:
    """Render a per-unit feature-level IQR-overlap summary heatmap.

    Rows = features; columns = [mean_overlap, median_overlap,
    min_overlap, max_overlap]. Cell value = IQR overlap coefficient
    in [0, 1]. Higher = more overlap (less separation).

    This complements the distinguishing bar chart: the bar chart shows
    effect size (between-cluster spread), the overlap heatmap shows
    distribution separation. Together they support the
    classification.
    """
    if not unit.labels_persisted:
        return out_path
    rows = [r for r in distinguishing_rows if r.unit_id == unit.unit_id]
    if not rows:
        return out_path
    features = list(FEATURE_COLUMNS)
    indicators = ("mean", "median", "min", "max")
    matrix = np.full((len(features), len(indicators)), np.nan, dtype=float)
    by_feat = {r.feature: r for r in rows}
    for i, feat in enumerate(features):
        r = by_feat.get(feat)
        if r is None:
            continue
        matrix[i, 0] = r.iqr_overlap_mean
        matrix[i, 1] = r.iqr_overlap_median
        matrix[i, 2] = r.iqr_overlap_min
        matrix[i, 3] = r.iqr_overlap_max
    fig, ax = plt.subplots(figsize=(7.0, 5.5))
    im = ax.imshow(
        matrix,
        aspect="auto",
        cmap="viridis_r",
        vmin=0.0,
        vmax=1.0,
    )
    ax.set_xticks(range(len(indicators)))
    ax.set_xticklabels([f"{n}_overlap" for n in indicators], fontsize=9)
    ax.set_yticks(range(len(features)))
    ax.set_yticklabels(features, fontsize=8)
    for i in range(len(features)):
        for j in range(len(indicators)):
            v = matrix[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    f"{v:.2f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if v > 0.6 else "black",
                )
            else:
                ax.text(
                    j,
                    i,
                    "NA",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="grey",
                )
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03)
    cbar.set_label("IQR overlap coefficient (1 = identical, 0 = disjoint)", fontsize=8)
    ax.set_title(
        f"CP-03 — Pairwise IQR overlap summary (per feature)\n"
        f"{unit.source_experiment} / {unit.algorithm}\n"
        f"{unit.unit_id}",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def render_all_cp03_charts(
    units: Sequence[Cp02AnalysisUnit],
    out_dir: Path,
    feature_subset: Sequence[str] = VIOLIN_FEATURE_SUBSET,
) -> list[Path]:
    """Render the full CP-03 chart set.

    Per analysis unit with persisted labels:

    - One violin plot per feature in ``feature_subset``.
    - One distinguishing-feature bar chart.
    - One IQR-overlap summary heatmap.

    Total expected: 5 units × (|feature_subset| + 2) = 5 × 9 = 45
    charts.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    distinguishing_rows = compute_distinguishing_feature_table(units)
    out_paths: list[Path] = []
    for unit in units:
        if not unit.labels_persisted:
            continue
        safe_id = unit.unit_id.replace("/", "_").replace(" ", "_")
        # Violin plots.
        for feat in feature_subset:
            out_paths.append(
                render_violin_plot(
                    unit=unit,
                    feature=feat,
                    out_path=out_dir / f"cp03_{safe_id}_{feat}_violin.png",
                )
            )
        # Distinguishing bar chart.
        out_paths.append(
            render_distinguishing_heatmap(
                unit=unit,
                distinguishing_rows=distinguishing_rows,
                out_path=out_dir / f"cp03_{safe_id}_distinguishing.png",
            )
        )
        # IQR overlap summary heatmap.
        out_paths.append(
            render_iqr_overlap_heatmap(
                unit=unit,
                distinguishing_rows=distinguishing_rows,
                out_path=out_dir / f"cp03_{safe_id}_iqr_overlap.png",
            )
        )
    return out_paths


__all__ = [
    "render_violin_plot",
    "render_distinguishing_heatmap",
    "render_iqr_overlap_heatmap",
    "render_all_cp03_charts",
    "VIOLIN_FEATURE_SUBSET",
    "CLASSIFICATION_COLORS",
    "CLASSIFICATION_ORDER",
    "ALGORITHM_COLORS",
    "FEATURE_COLUMNS",
]
