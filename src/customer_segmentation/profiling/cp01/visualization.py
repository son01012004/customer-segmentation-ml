"""CP-01 cluster-size visualisation.

Each analysis unit with persisted labels receives a single
``cp01_<unit_id>_cluster_size.png`` bar chart. DBSCAN bar charts are
labelled with noise as a separate visual element (hatched + outlined)
so a reader cannot mistake noise for a customer segment.

Charts are saved as PNG; the figure width scales with the number of
clusters so the bars are readable for both K=4 (most algorithms) and
the wider K=17 of DBSCAN.

Hard constraints (AGENTS.md §2):

- No ranking, no "best / winner / optimal / recommended" labels.
- No cluster-quality annotation from sizes alone.
- No segment naming. Bars are labelled ``Cluster <id>`` only.
- DBSCAN noise is rendered with a distinct hatch and a separate legend
  entry so it cannot be confused with a customer segment.
- The bar y-axis label explicitly states the unit (count vs percent).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")  # non-interactive backend

import matplotlib.pyplot as plt  # noqa: E402

from customer_segmentation.profiling.cp01.size_analysis import (
    ClusterSizeRow,
    NoiseRow,
)

# Stable visual palette per algorithm (single source of truth).
ALGORITHM_COLORS: dict[str, str] = {
    "kmeans": "#1f77b4",
    "agglomerative": "#2ca02c",
    "dbscan": "#d62728",
    "gmm": "#9467bd",
    "fuzzy_cmeans": "#ff7f0e",
}

NOISE_COLOR = "#7f7f7f"
NOISE_HATCH = "///"


def _bar_width(n_bars: int) -> float:
    """Pick a width that keeps bars readable for small or large n."""
    if n_bars <= 6:
        return 0.65
    if n_bars <= 20:
        return 0.85
    return 0.95


def render_cluster_size_bar_chart(
    unit_id: str,
    algorithm: str,
    source_experiment: str,
    cluster_rows: Sequence[ClusterSizeRow],
    noise_row: NoiseRow | None,
    out_path: Path,
) -> Path:
    """Render one bar chart per analysis unit.

    Returns the path of the saved PNG.
    """
    segments = [r for r in cluster_rows if not r.is_noise]
    if not segments:
        # Nothing to draw
        return out_path
    # Sort by cluster id for readability
    segments = sorted(segments, key=lambda r: r.cluster_id)
    n_segments = len(segments)
    # Add a noise bar at the end (right) for DBSCAN if present
    has_noise = noise_row is not None and noise_row.noise_count > 0
    n_bars = n_segments + (1 if has_noise else 0)
    fig, ax = plt.subplots(figsize=(min(max(6, n_bars * 0.45), 18), 5.0))
    fig.suptitle(
        f"CP-01 — Cluster size distribution\n"
        f"{source_experiment} / {algorithm}",
        fontsize=11,
    )
    bar_width = _bar_width(n_bars)
    color = ALGORITHM_COLORS.get(algorithm, "#4c4c4c")

    # Customer-segment bars
    x = list(range(n_segments))
    counts = [r.customer_count for r in segments]
    ax.bar(
        x,
        counts,
        color=color,
        width=bar_width,
        edgecolor="black",
        linewidth=0.4,
        label="customer segment",
    )
    # Count labels above each bar
    for i, c in enumerate(counts):
        ax.text(
            i,
            c + max(counts) * 0.01,
            f"{c}",
            ha="center",
            va="bottom",
            fontsize=7,
        )

    # Noise bar (DBSCAN only)
    if has_noise:
        nx = n_bars - 1
        ax.bar(
            [nx],
            [noise_row.noise_count],
            color=NOISE_COLOR,
            hatch=NOISE_HATCH,
            width=bar_width,
            edgecolor="black",
            linewidth=0.4,
            label="noise (-1) — NOT a customer segment",
        )
        ax.text(
            nx,
            noise_row.noise_count + max(counts) * 0.01,
            f"{noise_row.noise_count}",
            ha="center",
            va="bottom",
            fontsize=7,
        )

    # X-axis labels: Cluster <id>; for noise use "noise (-1)"
    labels = [f"C{r.cluster_id}" for r in segments]
    if has_noise:
        labels.append("noise (-1)")
    ax.set_xticks(list(range(n_bars)))
    ax.set_xticklabels(labels, rotation=45 if n_bars > 8 else 0, fontsize=8)
    ax.set_xlabel("Cluster id (per source artifact)", fontsize=9)
    ax.set_ylabel("Number of customers", fontsize=9)
    ax.set_title(
        f"{unit_id}\n"
        f"n_segments={n_segments}{', noise=' + str(noise_row.noise_count) if has_noise else ''}",
        fontsize=10,
    )
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def render_pct_bar_chart(
    unit_id: str,
    algorithm: str,
    source_experiment: str,
    cluster_rows: Sequence[ClusterSizeRow],
    noise_row: NoiseRow | None,
    out_path: Path,
    *,
    pct_basis: str = "total",
) -> Path:
    """Render a percentage bar chart; ``pct_basis`` in {'assigned','total'}."""
    segments = [r for r in cluster_rows if not r.is_noise]
    if not segments:
        return out_path
    segments = sorted(segments, key=lambda r: r.cluster_id)
    n_segments = len(segments)
    has_noise = noise_row is not None and noise_row.noise_count > 0
    n_bars = n_segments + (1 if has_noise else 0)
    fig, ax = plt.subplots(figsize=(min(max(6, n_bars * 0.45), 18), 5.0))
    fig.suptitle(
        f"CP-01 — Cluster percentage distribution ({pct_basis} basis)\n"
        f"{source_experiment} / {algorithm}",
        fontsize=11,
    )
    color = ALGORITHM_COLORS.get(algorithm, "#4c4c4c")
    bar_width = _bar_width(n_bars)
    # Compute percentages
    if pct_basis == "assigned":
        pcts = [r.pct_of_assigned for r in segments]
        if has_noise:
            n_total_assigned = sum(r.customer_count for r in segments)
            noise_pct = (
                (noise_row.noise_count / (noise_row.noise_count + n_total_assigned))
                * 100.0
            )
    else:
        n_total = sum(r.customer_count for r in segments) + (
            noise_row.noise_count if has_noise else 0
        )
        pcts = [
            (r.customer_count / n_total * 100.0) if n_total > 0 else 0.0
            for r in segments
        ]
        if has_noise:
            noise_pct = (noise_row.noise_count / n_total * 100.0) if n_total > 0 else 0.0
    x = list(range(n_segments))
    ax.bar(
        x,
        pcts,
        color=color,
        width=bar_width,
        edgecolor="black",
        linewidth=0.4,
        label="customer segment",
    )
    for i, p in enumerate(pcts):
        ax.text(
            i,
            p + max(pcts + [noise_pct if has_noise else 0]) * 0.01,
            f"{p:.2f}%",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    if has_noise:
        nx = n_bars - 1
        ax.bar(
            [nx],
            [noise_pct],
            color=NOISE_COLOR,
            hatch=NOISE_HATCH,
            width=bar_width,
            edgecolor="black",
            linewidth=0.4,
            label="noise (-1) — NOT a customer segment",
        )
        ax.text(
            nx,
            noise_pct + max(pcts + [noise_pct]) * 0.01,
            f"{noise_pct:.2f}%",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    labels = [f"C{r.cluster_id}" for r in segments]
    if has_noise:
        labels.append("noise (-1)")
    ax.set_xticks(list(range(n_bars)))
    ax.set_xticklabels(labels, rotation=45 if n_bars > 8 else 0, fontsize=8)
    ax.set_xlabel("Cluster id (per source artifact)", fontsize=9)
    ax.set_ylabel("Percentage of customers", fontsize=9)
    ax.set_title(
        f"{unit_id}\ndenominator = {'assigned (excl. noise)' if pct_basis == 'assigned' else 'total (incl. noise)'}",
        fontsize=10,
    )
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def render_all_charts(
    units_with_rows: dict[str, tuple[Sequence[ClusterSizeRow], NoiseRow | None]],
    out_dir: Path,
) -> list[Path]:
    """Render count bar and percentage bar for every analysis unit.

    ``units_with_rows`` maps ``unit_id`` → (cluster rows for that unit,
    optional noise row). Charts are saved as PNG into ``out_dir``.

    Returns the list of generated file paths.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []
    for unit_id, (rows, noise) in units_with_rows.items():
        if not rows:
            continue
        algorithm = rows[0].algorithm
        source_experiment = rows[0].source_experiment
        safe_id = unit_id.replace("/", "_").replace(" ", "_")
        out_count = out_dir / f"cp01_{safe_id}_size.png"
        render_cluster_size_bar_chart(
            unit_id=unit_id,
            algorithm=algorithm,
            source_experiment=source_experiment,
            cluster_rows=rows,
            noise_row=noise,
            out_path=out_count,
        )
        out_pct = out_dir / f"cp01_{safe_id}_pct.png"
        render_pct_bar_chart(
            unit_id=unit_id,
            algorithm=algorithm,
            source_experiment=source_experiment,
            cluster_rows=rows,
            noise_row=noise,
            out_path=out_pct,
            pct_basis="total",
        )
        out_paths.append(out_count)
        out_paths.append(out_pct)
    return out_paths


__all__ = [
    "render_cluster_size_bar_chart",
    "render_pct_bar_chart",
    "render_all_charts",
    "ALGORITHM_COLORS",
    "NOISE_COLOR",
    "NOISE_HATCH",
]
