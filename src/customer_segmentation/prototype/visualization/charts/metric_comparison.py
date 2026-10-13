"""Metric comparison chart for DEV-08 Prototype Visualization.

This module renders a comparison view of evaluation metrics across one
or more :class:`EvaluationManifest` instances. It is the **prototype
layer** (DEV-08) and does not modify research artefacts, aggregate
metrics into a composite score, rank algorithms, or claim a "best"
configuration.

Supported metrics
-----------------
The DEV-05 evaluation manifest has a closed 3-metric set
(:data:`METRIC_NAMES`): ``silhouette``, ``davies_bouldin``,
``calinski_harabasz``. These are the only metric names this module
reads from the manifest. There is no "runtime" field in
:data:`EvaluationMetricEntry` — only the per-metric
``computation_time_seconds`` (which is rendered as a sub-column
when present). Total fit time lives in the DEV-04 ``experiment_log``
(EPIC-06 contract §8.5) and is out of scope for DEV-08.

Output
------
- **Text table** (string): rows = evaluation manifests, columns =
  metric values + status. The mandatory disclaimer is appended.
- **Bar chart** (matplotlib PNG): one subplot per metric. Each
  subplot shows the metric value across evaluation runs (one bar per
  run, colored by algorithm). Subplots share a common x-axis
  (manifest index) so values are visually aligned, but **each metric
  has its own y-axis** because the three metrics are on different
  scales and have different "direction of improvement" semantics.

Hard rules
----------
- Only fields present in the existing manifest contract are read.
- No composite score, weighted aggregate, or normalized index is
  computed. Per-metric values are displayed as-is.
- No ranking / best / winner / optimal claims (R-EVAL-08 / R-EVAL-15).
- Banned words may appear only inside the disclaimer.
- Colours come from :data:`DEFAULT_COLOR_PALETTE` (single source).
- Invalid / missing manifests raise :class:`VisualizationError` with
  an explicit message — never silent.
- Multiple-evaluation display shows the
  ``algorithm``, ``n_clusters_realized``, ``noise_policy_used`` and
  a truncated ``evaluation_id`` so the source of every row is
  traceable.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (after backend selection)
import numpy as np  # noqa: E402  (after backend selection)

from customer_segmentation.prototype.evaluation.scope import (
    METRIC_NAMES,
    MetricStatus,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    DEFAULT_COLOR_PALETTE,
    DEFAULT_DISCLAIMER_TEXT,
)

if TYPE_CHECKING:
    from pathlib import Path

    from customer_segmentation.prototype.evaluation.manifest import (
        EvaluationManifest,
        EvaluationMetricEntry,
    )


__all__ = [
    "METRIC_VALUE_COLUMNS",
    "is_metric_value",
    "get_algorithm_color",
    "format_metric_value",
    "format_metric_status_block",
    "format_run_identifier",
    "extract_metric_matrix",
    "format_metric_comparison_table",
    "plot_metric_comparison",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Canonical order of metric columns in the text table.
METRIC_VALUE_COLUMNS: Final[tuple[str, ...]] = tuple(sorted(METRIC_NAMES))

# Truncation length for evaluation_id display (last 8 chars).
EVAL_ID_DISPLAY_TAIL: Final[int] = 8

# Maximum number of evaluation manifests per chart (legibility guard).
MAX_RUNS_PER_CHART: Final[int] = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_metric_value(value: Any) -> bool:
    """Return True if ``value`` is a finite numeric value (int or float).

    Mirrors the schema invariant: ``value is None`` iff
    ``status != VALID_VALUE``. NaN / Inf are treated as "not a value"
    so they are rendered as the missing-value placeholder, never
    silently substituted with zero.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        fv = float(value)
        return not (math.isnan(fv) or math.isinf(fv))
    return False


def get_algorithm_color(algorithm: str) -> str:
    """Return a deterministic colour for an algorithm name.

    Uses :data:`DEFAULT_COLOR_PALETTE` (single source). The mapping is
    a stable hash of the algorithm string, so the same algorithm is
    always rendered in the same colour across calls.
    """
    palette_len = len(DEFAULT_COLOR_PALETTE)
    h = 0
    for ch in algorithm:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return DEFAULT_COLOR_PALETTE[h % palette_len]


def format_metric_value(
    value: Any,
    *,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable rendering of a metric numeric value.

    - Finite numbers → ``"{:>10.4f}"``.
    - ``None`` / ``NaN`` / ``Inf`` / non-numeric → placeholder.
    - Booleans are treated as 0/1 (defensive; not expected per schema).
    """
    if not is_metric_value(value):
        return f"{missing_value_placeholder:>10}"
    return f"{float(value):>10.4f}"


def format_metric_status_block(
    entry: EvaluationMetricEntry,
) -> str:
    """Return a compact ``[STATUS] reason`` string for one metric entry.

    The status block is appended in parentheses when the value is
    missing so the reader can see WHY it is missing without
    consulting another file.
    """
    return f"[{entry.status}] {entry.reason}"


def format_run_identifier(
    manifest: EvaluationManifest,
    *,
    tail_length: int = EVAL_ID_DISPLAY_TAIL,
) -> str:
    """Return a short identifier for a run in chart axes / tables.

    Format: ``"<algorithm> k=<n> np=<noise> ev=<id-tail>"`` where
    ``id-tail`` is the last ``tail_length`` characters of the
    evaluation id (or the full id if it is shorter than
    ``tail_length``). This keeps the source of every row
    traceable without taking up the entire line.
    """
    eid = str(manifest.evaluation_id)
    eid_tail = eid[-tail_length:] if len(eid) > tail_length else eid
    return (
        f"{manifest.algorithm} "
        f"k={manifest.n_clusters_realized} "
        f"np={manifest.noise_policy_used} "
        f"ev={eid_tail}"
    )


# ---------------------------------------------------------------------------
# Matrix extraction
# ---------------------------------------------------------------------------


def extract_metric_matrix(
    manifests: list[EvaluationManifest] | EvaluationManifest,
) -> tuple[list[str], list[str], list[list[Any]]]:
    """Return ``(run_ids, metric_names, values)`` for the input manifests.

    Parameters
    ----------
    manifests : list[EvaluationManifest] or EvaluationManifest
        One or more evaluation manifests to compare. A single manifest
        is treated as a list of length 1.

    Returns
    -------
    (run_ids, metric_names, values)
        - ``run_ids`` is the list of human-readable identifiers in the
          same order as the input manifests.
        - ``metric_names`` is the canonical 3-metric closed set in
          :data:`METRIC_VALUE_COLUMNS` order.
        - ``values`` is a 2-D list ``values[run][metric]`` whose
          entries are either the numeric metric ``value`` (when
          ``status == VALID_VALUE``) or ``None``.

    Raises
    ------
    VisualizationError
        If ``manifests`` is empty or if any element does not look like
        an :class:`EvaluationManifest` (defence against accidentally
        passing a SegmentationManifest, which has no ``metrics``
        attribute).
    """
    if hasattr(manifests, "evaluation_id") and not isinstance(manifests, list):
        manifest_list: list[EvaluationManifest] = [manifests]  # type: ignore[list-item]
    else:
        manifest_list = list(manifests)  # type: ignore[arg-type]

    if not manifest_list:
        raise VisualizationError("manifests is empty; cannot render metric comparison.")

    # Defence against wrong-manifest type errors (e.g. passing a
    # SegmentationManifest which has no ``metrics`` attribute).
    # Without this guard the AttributeError surfaces deep in the
    # renderer and is hard to trace back to the caller.
    for i, m in enumerate(manifest_list):
        if not hasattr(m, "metrics") or not hasattr(m, "evaluation_id"):
            raise VisualizationError(
                f"manifests[{i}] is not an EvaluationManifest: missing "
                f"'metrics' / 'evaluation_id' attributes. Got "
                f"{type(m).__name__}."
            )

    if len(manifest_list) > MAX_RUNS_PER_CHART:
        raise VisualizationError(
            f"manifests has {len(manifest_list)} entries which exceeds "
            f"MAX_RUNS_PER_CHART={MAX_RUNS_PER_CHART}. Split into smaller "
            f"batches explicitly."
        )

    run_ids: list[str] = [format_run_identifier(m) for m in manifest_list]
    metric_names: list[str] = list(METRIC_VALUE_COLUMNS)
    values: list[list[Any]] = []
    for m in manifest_list:
        row: list[Any] = []
        for metric_name in metric_names:
            entry = m.metrics.entries.get(metric_name)
            if entry is None:
                row.append(None)
            elif entry.status == MetricStatus.VALID_VALUE.value:
                row.append(entry.value)
            else:
                row.append(None)
        values.append(row)

    return run_ids, metric_names, values


# ---------------------------------------------------------------------------
# Text table formatter
# ---------------------------------------------------------------------------


def format_metric_comparison_table(
    manifests: list[EvaluationManifest] | EvaluationManifest,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
    missing_value_placeholder: str = "--",
    separator_char: str = "  ",
    status_suffix: bool = True,
) -> str:
    """Return a printable per-run metric comparison table.

    Layout: rows = evaluation manifests; columns = identification
    fields (``algorithm``, ``k``, ``noise_policy``, ``ev``) plus
    one column per metric. When ``status_suffix=True`` (default),
    a non-``VALID_VALUE`` cell is followed by a parenthesised
    ``[STATUS] reason`` block so the reason is visible in the table
    itself.

    Parameters
    ----------
    manifests : list[EvaluationManifest] or EvaluationManifest
        Evaluation manifests to render.
    disclaimer : str
        Disclaimer text appended at the end. Must contain the
        banned-substrings pattern.
    missing_value_placeholder : str
        Placeholder for unavailable values.
    separator_char : str
        Column separator string.
    status_suffix : bool
        If True, missing-value cells are followed by the status
        block in parentheses; if False, only the placeholder is
        shown (more compact).

    Returns
    -------
    str
        Multi-line plain-text table.

    Raises
    ------
    VisualizationError
        If ``manifests`` is empty.
    """
    run_ids, metric_names, values = extract_metric_matrix(manifests)

    lines: list[str] = []
    lines.append("# Metric Comparison")
    lines.append("# " + "=" * 78)
    lines.append(f"# n_runs        : {len(run_ids)}")
    lines.append(f"# metrics       : {', '.join(metric_names)}")
    lines.append("# " + "-" * 78)
    lines.append(
        "Each metric is reported on its native scale and direction "
        "(silhouette higher = better, DBI lower = better, "
        "CH higher = better). Values are not directly comparable "
        "across metrics; no composite score is computed."
    )
    lines.append("")

    id_width = max(len("run_identifier"), max(len(r) for r in run_ids))
    metric_width = max(10, len("metric"))
    val_width = max(len(missing_value_placeholder), 10)

    # Header row.
    header_cells = ["run_identifier".ljust(id_width)]
    for m in metric_names:
        header_cells.append(m.rjust(metric_width + val_width + 1))
    lines.append(separator_char.join(header_cells))
    total_width = sum(len(c) for c in header_cells) + len(separator_char) * (len(header_cells) - 1)
    lines.append("-" * total_width)

    # Body rows.
    if hasattr(manifests, "evaluation_id") and not isinstance(manifests, list):
        manifest_list: list[EvaluationManifest] = [manifests]  # type: ignore[list-item]
    else:
        manifest_list = list(manifests)  # type: ignore[arg-type]

    for run_id, manifest, row in zip(run_ids, manifest_list, values, strict=True):
        cells: list[str] = [run_id.ljust(id_width)]
        for metric_name, v in zip(metric_names, row, strict=True):
            entry = manifest.metrics.entries.get(metric_name)
            value_str = format_metric_value(v, missing_value_placeholder=missing_value_placeholder)
            if (
                status_suffix
                and entry is not None
                and entry.status != MetricStatus.VALID_VALUE.value
            ):
                value_str = f"{value_str} " f"({format_metric_status_block(entry)})"
            cells.append(value_str)
        lines.append(separator_char.join(cells))

    # Computation-time sub-table (only when at least one entry has a time).
    any_time = any(
        m.metrics.entries.get(name) is not None
        and m.metrics.entries[name].computation_time_seconds is not None
        for m in manifest_list
        for name in metric_names
    )
    if any_time:
        lines.append("")
        lines.append("# Computation time (seconds) per metric:")
        time_header = ["run_identifier".ljust(id_width)] + [
            n.rjust(metric_width + val_width + 1) for n in metric_names
        ]
        lines.append(separator_char.join(time_header))
        lines.append("-" * total_width)
        for run_id, manifest in zip(run_ids, manifest_list, strict=True):
            cells = [run_id.ljust(id_width)]
            for name in metric_names:
                entry = manifest.metrics.entries.get(name)
                t = None if entry is None else entry.computation_time_seconds
                if t is None:
                    cells.append(f"{missing_value_placeholder:>{metric_width + val_width + 1}}")
                else:
                    cells.append(f"{float(t):>{metric_width + val_width + 1}.4f}")
            lines.append(separator_char.join(cells))

    lines.append("")
    lines.append("# " + "-" * 78)
    lines.append(f"Disclaimer: {disclaimer}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------------


def plot_metric_comparison(
    manifests: list[EvaluationManifest] | EvaluationManifest,
    *,
    title: str | None = None,
    output_path: Path | None = None,
    missing_value_placeholder: str = "--",
) -> plt.Figure:
    """Render a 1×3 subplot bar chart of metric values per evaluation run.

    Layout
    ------
    Three subplots, one per metric, in the canonical
    :data:`METRIC_VALUE_COLUMNS` order
    (``silhouette``, ``davies_bouldin``, ``calinski_harabasz``).
    Each subplot has:
    - X axis: run index (one tick per manifest, label = run id).
    - Y axis: the metric value (each subplot has its own scale).
    - Bars: coloured by algorithm (deterministic from
      :func:`get_algorithm_color`).
    - Value label on top of each bar (or placeholder for non-VALID).

    Notes
    -----
    - Each metric has its own y-axis because the three metrics are
      on different scales and have different "direction of
      improvement" semantics. The implementation does not normalise
      / rescale / aggregate.
    - A run with status != VALID_VALUE renders as a bar of height 0
      with the placeholder label on top, so the slot is visible but
      no fake number is plotted.
    """
    run_ids, metric_names, values = extract_metric_matrix(manifests)

    if hasattr(manifests, "evaluation_id") and not isinstance(manifests, list):
        manifest_list: list[EvaluationManifest] = [manifests]  # type: ignore[list-item]
    else:
        manifest_list = list(manifests)  # type: ignore[arg-type]

    n_metrics = len(metric_names)
    n_runs = len(run_ids)
    fig, axes = plt.subplots(1, n_metrics, figsize=(max(6.0, 1.2 * n_runs + 3), 4.5), sharex=True)
    if n_metrics == 1:
        axes = [axes]

    x_positions = np.arange(n_runs)
    bar_colors = [get_algorithm_color(m.algorithm) for m in manifest_list]

    for i, (metric_name, ax) in enumerate(zip(metric_names, axes, strict=True)):
        col_values = [v[i] for v in values]
        numeric_values: list[float] = []
        labels: list[str] = []
        for v in col_values:
            if is_metric_value(v):
                numeric_values.append(float(v))
            else:
                numeric_values.append(0.0)
            labels.append(
                format_metric_value(v, missing_value_placeholder=missing_value_placeholder)
            )
        bars = ax.bar(
            x_positions,
            numeric_values,
            color=bar_colors,
            width=0.6,
            edgecolor="white",
            linewidth=0.5,
        )
        ax.set_xticks(x_positions)
        ax.set_xticklabels(
            [rid[:EVAL_ID_DISPLAY_TAIL] for rid in run_ids],
            fontsize=7,
            rotation=45,
            ha="right",
        )
        ax.set_title(metric_name, fontsize=10, fontweight="bold")
        ax.set_ylabel(metric_name, fontsize=9)
        ax.axhline(0, color="black", linewidth=0.5)
        # Per-bar value label.
        for bar, lab in zip(bars, labels, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                lab,
                ha="center",
                va="bottom",
                fontsize=6,
            )

    chart_title = title or "Metric Comparison (per metric, native scale)"
    fig.suptitle(chart_title, fontsize=11, fontweight="bold")

    # Disclaimer in subtitle.
    subtitle = (
        "Each metric is on its own y-axis scale; no normalization, no "
        "composite score, no ranking. The three metrics are not directly "
        "comparable — silhouette higher = better, DBI lower = better, "
        "CH higher = better. Status != VALID_VALUE renders as "
        "placeholder (not zero)."
    )
    fig.text(0.5, 0.01, subtitle, ha="center", fontsize=6, style="italic")

    # X-axis label (shared): run identifier.
    fig.supxlabel("Run (algorithm, k, noise_policy, ev-id-tail)", fontsize=8)

    fig.tight_layout(rect=(0, 0.04, 1, 0.96))

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close(fig)

    return fig
