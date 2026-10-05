"""CP-02 visualisation.

CP-02 produces charts that support the descriptive feature-profile and
behavioural analysis. Two chart families are produced:

1. **Boxplot** — per (analysis unit, feature) showing the cluster-wise
   distribution of RAW feature values. We deliberately use boxplots
   (with overlay of cluster-level medians and the OVERALL median as a
   reference line) so the reader can compare each cluster to the
   overall population without confusing standardised values with
   business-meaningful values.

2. **Heatmap** — per analysis unit, a heatmap of cluster-median
   relative to overall-median (signed %), across all 14 features. The
   colour scale is centred at 0 (overall median); warm colours mean
   "cao hơn tương đối", cool colours mean "thấp hơn tương đối".
   The heatmap is explicitly framed as a **standardised profile
   heatmap** — i.e., a way to compare clusters, NOT a way to read
   business values. The colour bar caption says so.

Default chart subset
--------------------
Drawing 14 features × 5 algorithms × ≥4 clusters is too dense.
CP-02 draws boxplots for a **compact subset** of features:

- Recency, Frequency, Monetary (RFM core — interpretable in business
  units, well-known).
- TotalQuantity (volume).
- TenureDays (relationship length).
- ActiveDays (cadence proxy).
- CancellationRate (cancellation behaviour).

These 7 features cover the RFM core + behavioural + cancellation
dimensions without crowding the figure. The heatmap uses ALL 14
features so the reader can see the full picture at a glance.

Hard constraints (AGENTS.md §2):
- No ranking, no "best", no "winner", no "optimal".
- No segment naming.
- No marketing recommendation.
- DBSCAN noise is NOT included in cluster boxplots — only non-noise
  segments.
- The heatmap is framed as a **profile comparison** chart; its
  caption tells the reader that the colours are SIGNED %-vs-overall
  and that this is NOT a business value chart.

Boxplot conventions:
- Box shows P25, median, P75.
- Whiskers extend to 1.5 × IQR (matplotlib default).
- Outliers are shown individually.
- A horizontal red dashed line marks the OVERALL median.
- Cluster labels are "C<id>" exactly as in CP-01 (no relabelling).
- X-axis = cluster id; Y-axis = feature RAW value (with feature name
  + unit in the title).
- The chart's caption repeats the unit_id, the algorithm and the
  experiment so a reader can map each chart to its analysis unit.
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
from customer_segmentation.profiling.cp02.relative_comparison import (
    RelativeComparisonRow,
    compute_relative_comparison_table,
)

# Compact subset of features for boxplots. These are RFM core +
# behavioural + cancellation. They are chosen for readability, NOT
# because they are the "best" features.
BOXPLOT_FEATURE_SUBSET: tuple[str, ...] = (
    "Recency",
    "Frequency",
    "Monetary",
    "TotalQuantity",
    "TenureDays",
    "ActiveDays",
    "CancellationRate",
)


def _cluster_order(unit: Cp02AnalysisUnit) -> list[int]:
    """Return cluster ids present in the unit, excluding noise, sorted."""
    if not unit.labels_persisted:
        return []
    df = unit.cluster_labels_frame
    eligible = df.loc[df["ClusterLabel"] != -1]
    return sorted(int(c) for c in eligible["ClusterLabel"].unique())


def render_boxplot(
    unit: Cp02AnalysisUnit,
    feature: str,
    out_path: Path,
) -> Path:
    """Render a per-cluster boxplot for one (unit, feature).

    Parameters
    ----------
    unit
        A CP-02 analysis unit with persisted labels.
    feature
        One of FEATURE_COLUMNS.
    out_path
        Where to save the PNG.

    Returns
    -------
    Path
        The output PNG path.
    """
    if not unit.labels_persisted:
        return out_path
    df = unit.cluster_labels_frame
    eligible = df.loc[df["ClusterLabel"] != -1].copy()
    cluster_ids = _cluster_order(unit)
    if not cluster_ids:
        return out_path
    fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(cluster_ids) + 4), 5.0))
    color = ALGORITHM_COLORS.get(unit.algorithm, "#4c4c4c")
    data = []
    positions = []
    box_colors = []
    # Light variants per cluster so clusters are distinguishable.
    palette = plt.get_cmap("tab10").colors
    for i, cl in enumerate(cluster_ids):
        sub = eligible.loc[eligible["ClusterLabel"] == cl, feature].dropna()
        if len(sub) == 0:
            continue
        data.append(sub.values)
        positions.append(i)
        box_colors.append(palette[i % len(palette)])
    if not data:
        plt.close(fig)
        return out_path
    bp = ax.boxplot(
        data,
        positions=positions,
        widths=0.55,
        patch_artist=True,
        showfliers=True,
        flierprops={"marker": "o", "markersize": 2.5, "alpha": 0.4, "markerfacecolor": color},
        medianprops={"color": "black", "linewidth": 1.4},
    )
    for patch, c in zip(bp["boxes"], box_colors, strict=False):
        patch.set_facecolor(c)
        patch.set_alpha(0.55)
        patch.set_edgecolor("black")
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
    ax.set_xticklabels([f"C{cl}" for cl in cluster_ids], fontsize=9)
    ax.set_xlabel("Cluster id (per source artifact)", fontsize=9)
    ax.set_ylabel(f"{feature} (RAW value)", fontsize=9)
    ax.set_title(
        f"CP-02 — {feature} by cluster\n"
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


def render_relative_heatmap(
    unit: Cp02AnalysisUnit,
    rel_rows: Sequence[RelativeComparisonRow],
    out_path: Path,
) -> Path:
    """Render a per-unit heatmap of cluster-median-relative-to-overall.

    Each row is one cluster; each column is one of FEATURE_COLUMNS.
    The cell value is the signed percentage difference between
    cluster median and OVERALL median (NaN if undefined). The colour
    scale diverges at 0; warm = HIGHER, cool = LOWER.

    The heatmap is **explicitly framed** in its caption as a relative-
    to-overall percentage, NOT as a business-value chart.
    """
    if not unit.labels_persisted:
        return out_path
    cluster_ids = _cluster_order(unit)
    if not cluster_ids:
        return out_path
    # Build a (clusters × features) matrix from rel_rows.
    matrix = pd.DataFrame(
        index=[f"C{c}" for c in cluster_ids],
        columns=list(FEATURE_COLUMNS),
        dtype=float,
    )
    for r in rel_rows:
        if r.unit_id != unit.unit_id:
            continue
        if r.cluster_label not in matrix.index:
            continue
        if r.feature in matrix.columns:
            matrix.loc[r.cluster_label, r.feature] = r.rel_diff_median_pct
    fig, ax = plt.subplots(figsize=(max(8.5, 0.9 * len(FEATURE_COLUMNS) + 2.0), 4.5))
    # Use a symmetric colour scale centred at 0.
    finite_vals = matrix.values[np.isfinite(matrix.values)]
    vmax = float(np.nanpercentile(np.abs(finite_vals), 98)) if finite_vals.size else 100.0
    vmax = max(vmax, 10.0)  # avoid degenerate scale
    im = ax.imshow(
        matrix.values.astype(float),
        aspect="auto",
        cmap="RdBu_r",
        vmin=-vmax,
        vmax=vmax,
    )
    ax.set_xticks(range(len(FEATURE_COLUMNS)))
    ax.set_xticklabels(list(FEATURE_COLUMNS), rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(cluster_ids)))
    ax.set_yticklabels([f"C{c}" for c in cluster_ids], fontsize=9)
    # Annotate cells with the signed % (one decimal).
    for i in range(len(cluster_ids)):
        for j in range(len(FEATURE_COLUMNS)):
            v = matrix.values[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    f"{v:+.0f}%",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="black" if abs(v) < vmax * 0.6 else "white",
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
    cbar.set_label("Cluster median vs OVERALL median (%)", fontsize=8)
    ax.set_title(
        f"CP-02 — Standardised profile heatmap (relative % vs overall median)\n"
        f"{unit.source_experiment} / {unit.algorithm}\n"
        f"{unit.unit_id}\n"
        f"NOTE: signed percentage, NOT a business-value chart",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def render_all_cp02_charts(
    units: Sequence[Cp02AnalysisUnit],
    out_dir: Path,
    feature_subset: Sequence[str] = BOXPLOT_FEATURE_SUBSET,
) -> list[Path]:
    """Render boxplots + heatmaps for every analysis unit.

    Boxplots are drawn for ``feature_subset`` features only
    (default = RFM + behavioural + cancellation — see module docstring
    for rationale). Heatmaps use the full 14-feature set.

    Parameters
    ----------
    units
        All CP-02 analysis units.
    out_dir
        Output directory; created if missing.
    feature_subset
        Sequence of feature names to draw boxplots for. Pass a
        custom list from tests / ad-hoc scripts as needed.

    Returns
    -------
    list[Path]
        Paths of the generated PNGs.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []
    # Pre-compute relative comparison for the heatmaps.
    rel_rows = compute_relative_comparison_table(units)
    for unit in units:
        if not unit.labels_persisted:
            continue
        safe_id = unit.unit_id.replace("/", "_").replace(" ", "_")
        # Boxplots for the compact feature subset.
        for feat in feature_subset:
            out_paths.append(
                render_boxplot(
                    unit=unit,
                    feature=feat,
                    out_path=out_dir / f"cp02_{safe_id}_{feat}_boxplot.png",
                )
            )
        # Heatmap for all 14 features.
        out_paths.append(
            render_relative_heatmap(
                unit=unit,
                rel_rows=rel_rows,
                out_path=out_dir / f"cp02_{safe_id}_heatmap.png",
            )
        )
    return out_paths


__all__ = [
    "render_boxplot",
    "render_relative_heatmap",
    "render_all_cp02_charts",
    "BOXPLOT_FEATURE_SUBSET",
    "ALGORITHM_COLORS",
    "FEATURE_COLUMNS",
]
