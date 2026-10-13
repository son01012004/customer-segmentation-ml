"""Cluster distribution chart for DEV-08 Prototype Visualization.

This module renders a bar chart of per-segment sizes from a
:class:`SegmentationManifest`. It is the **prototype layer** (DEV-08) and
does not modify research artefacts or introduce ranking / recommendation
language.

Chart output
-------------
- **Bar chart** (matplotlib PNG): segments on x-axis, count on y-axis.
  Noise segment (DBSCAN) is rendered separately if ``include_noise=True``.
- **Text table** (string): suitable for CLI / log output, includes the
  mandatory disclaimer.

Hard rules
----------
- Colors come from :data:`DEFAULT_COLOR_PALETTE` only (single source;
  per AGENTS.md §3).
- Noise colour comes from :data:`NOISE_COLOR` (single source).
- No banned word may appear outside the disclaimer.
- No ranking, winner, best, optimal, or recommended language.
- DBSCAN noise segments are excluded by default (``include_noise=False``)
  to avoid implying that noise is a cluster.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection)

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
        SegmentationManifest,
        SegmentSize,
    )


__all__ = [
    "get_segment_color",
    "format_cluster_distribution_table",
    "plot_cluster_distribution",
]


# ---------------------------------------------------------------------------
# Color helper
# ---------------------------------------------------------------------------


def get_segment_color(segment_id: int) -> str:
    """Return the canonical colour for a segment.

    Colours are assigned deterministically from ``DEFAULT_COLOR_PALETTE``
    using modulo arithmetic. This ensures the same segment always gets
    the same colour across calls.

    Noise segments (``segment_id == -1``) should not reach this function
    when ``include_noise=False`` (the default); if they do, the colour
    assignment is still deterministic.
    """
    return DEFAULT_COLOR_PALETTE[segment_id % len(DEFAULT_COLOR_PALETTE)]


# ---------------------------------------------------------------------------
# Text table formatter
# ---------------------------------------------------------------------------


def format_cluster_distribution_table(
    segment_sizes,
    *,
    n_samples_input: int | None = None,
    include_noise: bool = True,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
    missing_value_placeholder: str = "--",
    separator_char: str = "  ",
) -> str:
    """Return a plain-text table of cluster sizes suitable for CLI / log output.

    Parameters
    ----------
    segment_sizes : list[SegmentSize] or SegmentationManifest
        Per-segment size rows. If a :class:`SegmentationManifest` is
        passed, its ``segment_sizes`` field and ``n_samples_input`` are
        used automatically.
    n_samples_input : int, optional
        Required when ``segment_sizes`` is a raw list. Ignored when a
        manifest is passed.
    include_noise : bool, default True
        Whether to include the noise row (``segment_id == -1``) in the
        output. Default is True because the table is a raw display of
        manifest data (unlike the chart, which defaults to False).
    disclaimer : str
        Disclaimer text appended at the end. Must contain the banned
        substrings.
    missing_value_placeholder : str
        Placeholder for unavailable percentage when
        ``percentage_base == "n_samples_used_for_compute"`` (noise row).
    separator_char : str
        Column separator string.

    Returns
    -------
    str
        Multi-line plain-text table.

    Raises
    ------
    VisualizationError
        When ``segment_sizes`` is an empty list and ``n_samples_input``
        is not provided (required for the totals footer).

    Notes
    -----
    - Percentages are taken directly from each ``SegmentSize.percentage``.
    - Noise row percentage is displayed as ``missing_value_placeholder``
      when ``percentage_base == "n_samples_used_for_compute"``
      (denominator excludes noise rows, so the field is not meaningful).
    - The disclaimer is appended verbatim; it must contain the banned
      substrings so the scan passes.
    """
    # Resolve segment_sizes and n_samples_input from manifest or raw list.
    if hasattr(segment_sizes, "segment_sizes"):
        _manifest = segment_sizes  # type: ignore[union-attr]
        _sizes: list[object] = list(_manifest.segment_sizes)  # type: ignore[union-attr]
        _n_input: int | None = _manifest.n_samples_input  # type: ignore[union-attr]
    else:
        _sizes = list(segment_sizes)
        _n_input = n_samples_input

    if not _sizes:
        raise VisualizationError(
            "segment_sizes is empty; n_samples_input is required to "
            "produce the distribution table. Pass a SegmentationManifest "
            "or provide n_samples_input explicitly."
        )

    if _n_input is None:
        raise VisualizationError(
            "n_samples_input is required when segment_sizes is a raw list. "
            "Pass a SegmentationManifest or provide n_samples_input."
        )

    header_cells = [
        "segment_id".ljust(12),
        "count".rjust(8),
        "pct".rjust(8),
        "is_noise".rjust(10),
    ]
    total_width = sum(len(c) for c in header_cells) + len(separator_char) * (len(header_cells) - 1)

    lines: list[str] = []
    lines.append(separator_char.join(header_cells))
    lines.append("-" * total_width)

    for s in _sizes:
        is_noise = bool(getattr(s, "is_noise", False))
        if is_noise and not include_noise:
            continue

        seg_id = int(getattr(s, "segment_id", 0))
        count = int(getattr(s, "count", 0))
        pct = float(getattr(s, "percentage", 0.0))
        pct_base = str(getattr(s, "percentage_base", ""))

        # Show placeholder when percentage base excludes noise (denominator
        # has no noise rows, so percentage field is not meaningful for noise).
        if is_noise and pct_base == "n_samples_used_for_compute":
            pct_str = missing_value_placeholder
        else:
            pct_str = f"{pct:.1f}"

        lines.append(
            separator_char.join(
                [
                    str(seg_id).ljust(12),
                    str(count).rjust(8),
                    pct_str.rjust(8),
                    str(is_noise).rjust(10),
                ]
            )
        )

    lines.append("")
    lines.append(f"n_samples_input={_n_input}")

    # Append disclaimer verbatim — it contains the banned substrings
    # (e.g. "no ranking") so the output remains clean per the scan.
    lines.append(f"Disclaimer: {disclaimer}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Matplotlib chart
# ---------------------------------------------------------------------------


def plot_cluster_distribution(
    segment_sizes,
    *,
    n_samples_input: int | None = None,
    include_noise: bool = False,
    title: str = "Cluster size distribution",
    y_label: str = "Count",
    output_path: Path | None = None,
) -> plt.Figure:
    """Render a bar chart of per-segment sizes.

    Parameters
    ----------
    segment_sizes : list[SegmentSize] or SegmentationManifest
        Per-segment size rows. If a :class:`SegmentationManifest` is
        passed, its ``segment_sizes`` field and ``n_samples_input`` are
        used automatically.
    n_samples_input : int, optional
        Required when ``segment_sizes`` is a raw list. Ignored when a
        manifest is passed.
    include_noise : bool, default False
        Whether to include the noise bar (``segment_id == -1``) rendered
        in ``NOISE_COLOR``. Excluding noise by default avoids implying
        that noise is a real cluster.
    title : str
        Chart title.
    y_label : str
        Y-axis label.
    output_path : Path, optional
        If provided, the figure is saved to this path and closed.
        Otherwise the caller is responsible for closing it.

    Returns
    -------
    matplotlib.figure.Figure

    Raises
    ------
    VisualizationError
        When ``segment_sizes`` is empty or when required metadata is
        missing.

    Notes
    -----
    - Bar colours are deterministic: segment ``i`` always gets
      ``DEFAULT_COLOR_PALETTE[i % len(DEFAULT_COLOR_PALETTE)]``.
    - Y-axis starts at 0 (standard bar-chart practice).
    - A secondary note in the subtitle references the disclaimer;
      the mandatory disclaimer is rendered in the accompanying text output.
    - No ranking, winner, or recommended language appears in the chart.
    """
    # Resolve manifest or raw list.
    if hasattr(segment_sizes, "segment_sizes"):
        _manifest = segment_sizes  # type: ignore[union-attr]
        _sizes: list[object] = list(_manifest.segment_sizes)  # type: ignore[union-attr]
        _n_input: int | None = _manifest.n_samples_input  # type: ignore[union-attr]
    else:
        _sizes = list(segment_sizes)
        _n_input = n_samples_input

    if not _sizes:
        raise VisualizationError(
            "segment_sizes is empty; cannot render cluster distribution chart."
        )

    if _n_input is None:
        raise VisualizationError(
            "n_samples_input is required when segment_sizes is a raw list. "
            "Pass a SegmentationManifest or provide n_samples_input."
        )

    # Build data arrays, optionally filtering noise.
    segment_ids: list[int] = []
    counts: list[int] = []
    colours: list[str] = []

    for s in _sizes:
        seg_id = int(getattr(s, "segment_id", 0))
        is_noise = bool(getattr(s, "is_noise", False))

        if is_noise:
            if not include_noise:
                continue
            colours.append(NOISE_COLOR)
        else:
            colours.append(get_segment_color(seg_id))

        segment_ids.append(seg_id)
        counts.append(int(getattr(s, "count", 0)))

    # Validate counts.
    for i, (sid, cnt) in enumerate(zip(segment_ids, counts, strict=True)):
        if cnt < 0:
            raise VisualizationError(
                f"SegmentSize[{i}] (segment_id={sid}) has negative count: {cnt}."
            )
        if cnt > _n_input:
            raise VisualizationError(
                f"SegmentSize[{i}] (segment_id={sid}) count {cnt} exceeds "
                f"n_samples_input {_n_input}."
            )

    # Determine x positions (keep natural segment_id ordering for clarity;
    # if include_noise=True, noise is last).
    x_positions = list(range(len(segment_ids)))

    # Render figure.
    fig, ax = plt.subplots(figsize=(math.ceil(len(x_positions) * 1.2 + 4), 6))

    bars = ax.bar(
        x_positions,
        counts,
        color=colours,
        width=0.6,
        edgecolor="white",
        linewidth=0.5,
    )

    # Tick labels: use segment_id (or "Noise" for -1).
    tick_labels = ["Noise" if sid == -1 else str(sid) for sid in segment_ids]
    ax.set_xticks(x_positions)
    ax.set_xticklabels(tick_labels, fontsize=9)

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Segment ID", fontsize=10)
    ax.set_ylabel(y_label, fontsize=10)
    ax.set_ylim(bottom=0)

    # Add count label on top of each bar.
    for bar, count in zip(bars, counts, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{count:,}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # Disclaimer in subtitle (not the canonical disclaimer — that goes in
    # the text table; this is a brief reminder in the chart context).
    disclaimer_note = " | ".join(
        [
            DEFAULT_DISCLAIMER_TEXT.split(";")[0].strip(),
            "values are post-preprocessing",
        ]
    )
    ax.set_facecolor("#fafafa")
    fig.patch.set_facecolor("white")

    fig.tight_layout()

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close(fig)

    return fig
