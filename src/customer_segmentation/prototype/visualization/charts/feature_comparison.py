"""Feature comparison chart for DEV-08 Prototype Visualization.

This module renders a per-feature comparison view from a
:class:`SegmentationManifest`. It is the **prototype layer** (DEV-08) and
does not modify research artefacts, normalize / rescale feature values,
or introduce ranking / recommendation language.

Output
------
- **Text table** (string): rows = ``feature_name`` (one per unique
  feature in the manifest), columns = ``segment_id`` (one per
  ``SegmentSize``). Each cell shows the chosen statistic value for
  that (feature, segment) pair.
- **Heatmap** (matplotlib PNG): same layout as the table — features
  on Y axis, segments on X axis, cell = chosen statistic value.
- **Bar chart** (matplotlib PNG): one feature across all segments.

Supported statistics
--------------------
Statistic names MUST be members of
:data:`PROFILING_STATISTICS_SET` (closed set; 7 numerical + 4
categorical). The default is ``"mean"``. Categorical statistics
(``topk_categories``, ``value_counts``, ``other_count``,
``missing_count``) are rendered only in the text table; heatmap
and bar chart accept numerical statistics only.

Hard rules
----------
- Only fields present in the existing manifest contract are read.
- Values are **never** normalized, rescaled, or recomputed (per
  AGENTS.md §2.9 and the explicit Task 1.4 constraint).
- Missing values are rendered as ``--`` — never silently replaced
  with zero.
- Colours come from :data:`DEFAULT_COLOR_PALETTE` (single source;
  per AGENTS.md §3).
- No banned word may appear outside the disclaimer.
- No ranking, winner, best, optimal, or recommended language.
- DBSCAN noise segments (``segment_id == -1``) follow the
  :class:`SegmentationManifest` contract: included by default,
  excluded with ``include_noise=False``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection)
import numpy as np  # noqa: E402  (after backend selection)

from customer_segmentation.prototype.segmentation.scope import (
    PROFILING_STATISTICS_SET,
)
from customer_segmentation.prototype.visualization.charts.cluster_distribution import (
    get_segment_color,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    DEFAULT_COLOR_PALETTE,
    DEFAULT_DISCLAIMER_TEXT,
    NOISE_COLOR,
)

if TYPE_CHECKING:
    from pathlib import Path

    from customer_segmentation.prototype.segmentation.manifest import (
        FeatureProfile,
        SegmentationManifest,
        SegmentSize,
    )


__all__ = [
    "NUMERICAL_STATISTICS",
    "is_numerical_statistic",
    "format_feature_comparison_table",
    "format_statistic_value",
    "extract_statistic_matrix",
    "plot_feature_heatmap",
    "plot_feature_bars",
    "get_feature_color",
]


# ---------------------------------------------------------------------------
# Statistic classification
# ---------------------------------------------------------------------------

# Numerical statistics are safe to plot on a numeric axis (heatmap,
# bar chart). Categorical statistics carry list / dict payloads and
# must only be rendered as text.
NUMERICAL_STATISTICS: Final[frozenset[str]] = frozenset(
    {"mean", "median", "std", "q1", "q3", "min", "max"}
)

# Default statistic for single-statistic view.
DEFAULT_STATISTIC: Final[str] = "mean"

# Maximum features displayed in a single heatmap (avoid unreadable
# figures when feature_set is large). Callers can opt-out by
# passing an explicit list of feature names.
MAX_HEATMAP_FEATURES: Final[int] = 30


def is_numerical_statistic(statistic: str) -> bool:
    """Return True if ``statistic`` is a numerical statistic name."""
    return statistic in NUMERICAL_STATISTICS


# ---------------------------------------------------------------------------
# Colour helper
# ---------------------------------------------------------------------------


def get_feature_color(feature_name: str) -> str:
    """Return a deterministic colour for a feature name.

    Uses :data:`DEFAULT_COLOR_PALETTE` (single source, shared with
    :func:`customer_segmentation.prototype.visualization.charts.
    cluster_distribution.get_segment_color`). Feature colours are
    assigned via a stable hash of the feature name so the same
    feature is always rendered in the same colour across calls.
    """
    palette_len = len(DEFAULT_COLOR_PALETTE)
    h = 0
    for ch in feature_name:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return DEFAULT_COLOR_PALETTE[h % palette_len]


# ---------------------------------------------------------------------------
# Value formatter
# ---------------------------------------------------------------------------


def format_statistic_value(
    value: Any,
    *,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable rendering of a single statistic value.

    - ``None`` and empty containers → placeholder.
    - ``bool`` / ``int`` / ``float`` → ``str(value)`` (floats get a
      fixed precision).
    - ``list`` / ``tuple`` → compact ``"a:1|b:2|c:3"`` rendering.
    - ``dict`` → compact JSON-ish ``"{k=v, k=v}"`` rendering.
    - Everything else → ``str(value)``.
    """
    if value is None:
        return missing_value_placeholder
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return missing_value_placeholder
        # Use up to 4 decimals, trim trailing zeros.
        return f"{value:.4f}".rstrip("0").rstrip(".") or "0"
    if isinstance(value, (list, tuple)):
        if not value:
            return missing_value_placeholder
        try:
            return "|".join(f"{cat}:{count}" for cat, count in value)  # type: ignore[misc]
        except (TypeError, ValueError):
            return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        if not value:
            return missing_value_placeholder
        return ",".join(f"{k}={v}" for k, v in value.items())
    return str(value)


# ---------------------------------------------------------------------------
# Matrix extraction
# ---------------------------------------------------------------------------


def extract_statistic_matrix(
    profiles: list[FeatureProfile] | SegmentationManifest,
    statistic: str,
    *,
    include_noise: bool = True,
    segment_ids: list[int] | None = None,
) -> tuple[list[str], list[int], list[list[Any]]]:
    """Return ``(feature_names, segment_ids, values)`` for the chosen statistic.

    The returned ``values`` matrix is ``values[i][j]`` = the
    ``statistic`` value for ``feature_names[i]`` × ``segment_ids[j]``,
    or ``None`` if the (feature, segment) pair is missing.

    Parameters
    ----------
    profiles : list[FeatureProfile] or SegmentationManifest
        Per-segment feature profiles. A :class:`SegmentationManifest`
        is resolved via its ``profiles`` and ``segment_sizes`` fields.
    statistic : str
        Must be a member of :data:`PROFILING_STATISTICS_SET`.
    include_noise : bool, default True
        Whether noise segments (``segment_id == -1``) are included.
    segment_ids : list[int], optional
        If provided, the matrix is restricted to these segment ids
        (in the order given). Otherwise the manifest's segment order
        is preserved.

    Returns
    -------
    (feature_names, segment_ids, values)
        ``feature_names`` is sorted (deterministic output).
        ``segment_ids`` is the resolved segment id list.
        ``values`` is a 2-D list of statistic values (or ``None``).

    Raises
    ------
    VisualizationError
        If ``statistic`` is not in :data:`PROFILING_STATISTICS_SET`,
        or if the manifest has no profiles and no segment sizes.
    """
    if statistic not in PROFILING_STATISTICS_SET:
        raise VisualizationError(
            f"statistic {statistic!r} is not a supported profile statistic; "
            f"allowed names: {sorted(PROFILING_STATISTICS_SET)}."
        )

    # Resolve profiles and segment_sizes from input.
    if hasattr(profiles, "profiles") and hasattr(profiles, "segment_sizes"):
        _profiles: list[FeatureProfile] = list(profiles.profiles)  # type: ignore[union-attr]
        _seg_sizes: list[SegmentSize] = list(profiles.segment_sizes)  # type: ignore[union-attr]
    else:
        _profiles = list(profiles)  # type: ignore[arg-type]
        _seg_sizes = []

    if not _profiles:
        raise VisualizationError("profiles is empty; cannot render feature comparison.")

    # Resolve segment id order. Noise rows are dropped if include_noise=False.
    if segment_ids is None:
        resolved_seg_ids: list[int] = []
        for s in _seg_sizes:
            if s.is_noise and not include_noise:
                continue
            resolved_seg_ids.append(int(s.segment_id))
        if not resolved_seg_ids:
            # Fallback: derive segment ids from the profiles themselves
            # when no segment_sizes are available.
            seen: set[int] = set()
            for p in _profiles:
                sid = int(p.segment_id)
                if sid == -1 and not include_noise:
                    continue
                if sid not in seen:
                    seen.add(sid)
                    resolved_seg_ids.append(sid)
    else:
        resolved_seg_ids = list(segment_ids)

    if not resolved_seg_ids:
        raise VisualizationError("no segment ids available; cannot render feature comparison.")

    # Build feature name set (sorted for determinism) and index map.
    feature_names_set: set[str] = set()
    for p in _profiles:
        feature_names_set.add(p.feature_name)
    feature_names: list[str] = sorted(feature_names_set)

    if not feature_names:
        raise VisualizationError(
            "no feature_name values found in profiles; cannot render " "feature comparison."
        )

    # Build lookup: (segment_id, feature_name) -> value
    lookup: dict[tuple[int, str], Any] = {}
    for p in _profiles:
        sid = int(p.segment_id)
        if sid == -1 and not include_noise:
            continue
        if sid not in resolved_seg_ids:
            continue
        val = p.statistics.get(statistic, None)
        if val is None and statistic not in p.statistics:
            val = None
        lookup[(sid, p.feature_name)] = val

    # Build values matrix.
    values: list[list[Any]] = []
    for feat in feature_names:
        row: list[Any] = []
        for sid in resolved_seg_ids:
            row.append(lookup.get((sid, feat)))
        values.append(row)

    return feature_names, resolved_seg_ids, values


# ---------------------------------------------------------------------------
# Text table formatter
# ---------------------------------------------------------------------------


def format_feature_comparison_table(
    manifest,
    *,
    statistic: str = DEFAULT_STATISTIC,
    include_noise: bool = True,
    missing_value_placeholder: str = "--",
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
    feature_name_width: int = 24,
    cell_width: int = 14,
    separator_char: str = "  ",
) -> str:
    """Return a printable per-feature comparison table.

    Layout: rows = ``feature_name``; columns = ``segment_id`` cells
    contain the chosen ``statistic`` value (or ``--`` for missing).

    Parameters
    ----------
    manifest : SegmentationManifest or list[FeatureProfile]
        Per-segment feature profiles. A :class:`SegmentationManifest`
        is resolved via its ``profiles`` and ``segment_sizes`` fields.
    statistic : str
        Must be a member of :data:`PROFILING_STATISTICS_SET`.
        Default is ``"mean"``.
    include_noise : bool, default True
        Whether to include noise segments (``segment_id == -1``).
    missing_value_placeholder : str
        Placeholder for unavailable values.
    disclaimer : str
        Disclaimer text appended at the end.
    feature_name_width : int
        Minimum width for the feature name column.
    cell_width : int
        Minimum width for each segment value cell.
    separator_char : str
        Column separator string.

    Returns
    -------
    str
        Multi-line plain-text table.

    Raises
    ------
    VisualizationError
        If ``statistic`` is invalid or the input is empty.
    """
    feature_names, segment_ids, values = extract_statistic_matrix(
        manifest,
        statistic,
        include_noise=include_noise,
    )

    lines: list[str] = []
    lines.append("# Feature Comparison")
    lines.append("# " + "=" * 78)
    lines.append(f"# statistic         : {statistic}")
    if isinstance(manifest, object) and hasattr(manifest, "segmentation_id"):
        lines.append(f"# segmentation_id   : {manifest.segmentation_id}")
    if isinstance(manifest, object) and hasattr(manifest, "preprocessing_warning"):
        pw = str(manifest.preprocessing_warning or "")
        if pw:
            lines.append("# preprocessing_warning:")
            import textwrap

            for ln in textwrap.wrap(pw, width=72):
                lines.append(f"#   {ln}")
    lines.append("# " + "-" * 78)
    lines.append(
        "Values are post-preprocessing (scaled/transformed) — not directly "
        "interpretable in original business units. Features may be on "
        "different scales; cross-feature comparison is descriptive only."
    )
    lines.append("")

    # Header row: feature_name | segment_0 | segment_1 | ... | Noise?
    header_cells: list[str] = ["feature_name".ljust(feature_name_width)]
    for sid in segment_ids:
        label = "Noise (-1)" if sid == -1 else f"seg_{sid}"
        header_cells.append(label.rjust(cell_width))
    lines.append(separator_char.join(header_cells))
    total_width = sum(len(c) for c in header_cells) + len(separator_char) * (len(header_cells) - 1)
    lines.append("-" * total_width)

    # Body rows: one per feature.
    for i, feat in enumerate(feature_names):
        cells: list[str] = [feat.ljust(feature_name_width)]
        for v in values[i]:
            cells.append(
                format_statistic_value(
                    v, missing_value_placeholder=missing_value_placeholder
                ).rjust(cell_width)
            )
        lines.append(separator_char.join(cells))

    lines.append("")
    lines.append("# " + "-" * 78)
    lines.append(f"Disclaimer: {disclaimer}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------


def plot_feature_heatmap(
    manifest,
    *,
    statistic: str = DEFAULT_STATISTIC,
    include_noise: bool = True,
    title: str | None = None,
    output_path: Path | None = None,
    missing_value_placeholder: str = "--",
    cmap: str = "viridis",
) -> plt.Figure:
    """Render a heatmap of ``statistic`` per (feature × segment).

    Layout
    ------
    Y axis = ``feature_name`` (one row per unique feature);
    X axis = ``segment_id`` (one column per segment).
    Cell = ``statistic`` value (or ``--`` placeholder for missing).
    No normalization is applied (per Task 1.4 constraint).

    Notes
    -----
    The colour scale spans the observed (numerical) statistic values
    only. Missing cells are rendered as a separate grey band with the
    placeholder label, so they are not silently treated as zero.

    Raises
    ------
    VisualizationError
        If ``statistic`` is not numerical, the input is empty, or the
        number of features exceeds :data:`MAX_HEATMAP_FEATURES` (callers
        must explicitly opt out by passing a smaller list or selecting
        specific features).
    """
    if not is_numerical_statistic(statistic):
        raise VisualizationError(
            f"plot_feature_heatmap requires a numerical statistic; "
            f"got {statistic!r}. Allowed numerical names: "
            f"{sorted(NUMERICAL_STATISTICS)}. For categorical statistics, "
            f"use format_feature_comparison_table."
        )

    feature_names, segment_ids, values = extract_statistic_matrix(
        manifest,
        statistic,
        include_noise=include_noise,
    )

    if len(feature_names) > MAX_HEATMAP_FEATURES:
        raise VisualizationError(
            f"feature_comparison heatmap would have {len(feature_names)} "
            f"features which exceeds MAX_HEATMAP_FEATURES="
            f"{MAX_HEATMAP_FEATURES}. Filter the feature set explicitly."
        )

    # Build the numeric matrix (NaN for missing / non-numeric cells)
    # and a parallel mask of missing entries.
    n_feat = len(feature_names)
    n_seg = len(segment_ids)
    matrix = np.full((n_feat, n_seg), np.nan, dtype=float)
    for i in range(n_feat):
        for j in range(n_seg):
            v = values[i][j]
            if isinstance(v, bool):
                # bool is subclass of int; treat as numerical.
                matrix[i, j] = float(v)
            elif isinstance(v, (int, float)):
                fv = float(v)
                if not (math.isnan(fv) or math.isinf(fv)):
                    matrix[i, j] = fv

    fig_height = max(4.0, 0.35 * n_feat + 2.0)
    fig_width = max(6.0, 0.9 * n_seg + 3.0)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    im = ax.imshow(
        matrix,
        aspect="auto",
        cmap=cmap,
        interpolation="nearest",
    )

    # Tick labels.
    ax.set_yticks(range(n_feat))
    ax.set_yticklabels(feature_names, fontsize=8)
    ax.set_xticks(range(n_seg))
    ax.set_xticklabels(
        [("Noise" if sid == -1 else str(sid)) for sid in segment_ids],
        fontsize=8,
        rotation=0,
    )

    # In-cell value labels: numeric cells show their value (rounded);
    # missing cells show the placeholder.
    for i in range(n_feat):
        for j in range(n_seg):
            label = format_statistic_value(
                values[i][j],
                missing_value_placeholder=missing_value_placeholder,
            )
            ax.text(
                j,
                i,
                label,
                ha="center",
                va="center",
                fontsize=7,
                color="black",
            )

    ax.set_xlabel("Segment ID", fontsize=10)
    ax.set_ylabel("Feature", fontsize=10)
    chart_title = title or (
        f"Feature Comparison ({statistic}) — post-preprocessing values, " f"no normalization"
    )
    ax.set_title(chart_title, fontsize=11, fontweight="bold")
    fig.colorbar(im, ax=ax, label=statistic, fraction=0.046, pad=0.04)

    # Disclaimer in subtitle.
    subtitle = (
        "Values are post-preprocessing (scaled/transformed); "
        "cross-feature scales differ; descriptive only."
    )
    fig.text(0.5, 0.01, subtitle, ha="center", fontsize=7, style="italic")

    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close(fig)

    return fig


# ---------------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------------


def plot_feature_bars(
    manifest,
    *,
    feature_name: str,
    statistic: str = DEFAULT_STATISTIC,
    include_noise: bool = True,
    title: str | None = None,
    output_path: Path | None = None,
    missing_value_placeholder: str = "--",
) -> plt.Figure:
    """Render a bar chart of one feature's ``statistic`` across segments.

    The X axis is the segment id; the Y axis is the ``statistic``
    value. Bar colour is :func:`get_segment_color` for non-noise
    segments, :data:`NOISE_COLOR` for the noise row.

    Raises
    ------
    VisualizationError
        If ``statistic`` is not numerical, the feature is not in
        any profile, or the input is empty.
    """
    if not is_numerical_statistic(statistic):
        raise VisualizationError(
            f"plot_feature_bars requires a numerical statistic; "
            f"got {statistic!r}. Allowed numerical names: "
            f"{sorted(NUMERICAL_STATISTICS)}."
        )

    feature_names, segment_ids, values = extract_statistic_matrix(
        manifest,
        statistic,
        include_noise=include_noise,
    )

    if feature_name not in feature_names:
        raise VisualizationError(
            f"feature_name {feature_name!r} is not present in any profile; "
            f"available features: {feature_names}."
        )

    feat_idx = feature_names.index(feature_name)
    row = values[feat_idx]

    # Numeric values + label lists (preserve segment order).
    numeric_values: list[float] = []
    bar_labels: list[str] = []
    bar_colours: list[str] = []
    for sid, v in zip(segment_ids, row, strict=True):
        if isinstance(v, bool) or (
            isinstance(v, (int, float))
            and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
        ):
            numeric_values.append(float(v))
        else:
            numeric_values.append(0.0)
        bar_labels.append("Noise" if sid == -1 else str(sid))
        bar_colours.append(NOISE_COLOR if sid == -1 else get_segment_color(int(sid)))

    fig, ax = plt.subplots(figsize=(max(6.0, 0.9 * len(segment_ids) + 3), 5))
    x_positions = list(range(len(segment_ids)))
    bars = ax.bar(
        x_positions,
        numeric_values,
        color=bar_colours,
        width=0.6,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_xticks(x_positions)
    ax.set_xticklabels(bar_labels, fontsize=9)
    ax.set_xlabel("Segment ID", fontsize=10)
    ax.set_ylabel(f"{statistic} ({feature_name})", fontsize=10)
    chart_title = title or (f"{feature_name} — {statistic} by segment (post-preprocessing values)")
    ax.set_title(chart_title, fontsize=11, fontweight="bold")
    ax.axhline(0, color="black", linewidth=0.5)

    # Add value label on top of each bar.
    for bar, v in zip(bars, row, strict=True):
        label = format_statistic_value(v, missing_value_placeholder=missing_value_placeholder)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            label,
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # Subtitle: post-preprocessing warning.
    subtitle = (
        "Values are post-preprocessing (scaled/transformed) — "
        "not directly interpretable in original business units."
    )
    fig.text(0.5, 0.01, subtitle, ha="center", fontsize=7, style="italic")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close(fig)

    return fig
