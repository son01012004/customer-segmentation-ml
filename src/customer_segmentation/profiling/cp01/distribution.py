"""CP-01 cluster-size distribution indicators.

For every analysis unit whose per-customer labels are persisted, this
module computes a small set of descriptive distribution indicators:

- ``n_clusters``                — number of segments (excluding noise).
- ``n_total_customers``         — eligible customer count.
- ``largest_cluster_count``     — size of the largest segment.
- ``smallest_cluster_count``    — size of the smallest segment.
- ``largest_pct_of_total``      — share of the largest segment.
- ``largest_to_smallest_ratio`` — a relative-size measure.
- ``size_range``                — ``largest - smallest``.
- ``deviation_from_equal_size`` — average deviation of cluster sizes
                                  from the equal-size reference
                                  ``n_total / n_clusters``.
- ``median_cluster_size``       — median of cluster sizes.

Each indicator is reported with floating-point precision so no
truncation has occurred in the computation. The report then reads
these numbers to describe whether the distribution is balanced or
imbalanced — without claiming which algorithm is "best".

Hard constraints (AGENTS.md §2):

- No ranking, no "best / winner / optimal / recommended" labels.
- No cluster-quality claim from sizes alone.
- No threshold fixed at "cluster too small" — descriptive only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from customer_segmentation.profiling.cp01.size_analysis import ClusterSizeRow


@dataclass(frozen=True)
class DistributionIndicators:
    """Numerical summary of distribution within one analysis unit."""

    unit_id: str
    algorithm: str
    source_experiment: str
    n_clusters: int
    n_total_customers: int
    largest_cluster_count: int
    smallest_cluster_count: int
    largest_pct_of_total: float
    largest_to_smallest_ratio: float
    size_range: int
    deviation_from_equal_size: float
    median_cluster_size: float


def _safe_pct(numer: float, denom: float) -> float:
    if denom <= 0:
        return float("nan")
    return numer / denom * 100.0


def _safe_div(numer: float, denom: float) -> float:
    if denom <= 0:
        return float("nan")
    return numer / denom


def _equal_size_deviation(sizes: Sequence[int]) -> float:
    """Average absolute deviation from the equal-size reference.

    Returns ``0.0`` for empty or single-cluster sequences (no
    deviation possible). For ``n_clusters`` equal-sized clusters, the
    ideal reference is ``n_total / n_clusters`` and this metric is the
    mean of ``|size_i - ref|``.
    """
    sizes = [s for s in sizes if s is not None]
    if len(sizes) <= 1:
        return 0.0
    ref = sum(sizes) / len(sizes)
    return sum(abs(s - ref) for s in sizes) / len(sizes)


def compute_distribution_indicators(
    size_rows: Sequence[ClusterSizeRow],
) -> list[DistributionIndicators]:
    """Aggregate ``ClusterSizeRow`` entries into per-unit indicators.

    Skips cluster-id == -1 (DBSCAN noise) — those rows do not represent
    customer segments and are excluded from n_clusters / median /
    deviation statistics.
    """
    by_unit: dict[str, list[ClusterSizeRow]] = {}
    for r in size_rows:
        if r.is_noise:
            continue  # noise is reported separately, not a segment
        by_unit.setdefault(r.unit_id, []).append(r)

    out: list[DistributionIndicators] = []
    for unit_id, rows in by_unit.items():
        sizes = [r.customer_count for r in rows]
        if not sizes:
            continue
        sorted_sizes = sorted(sizes)
        largest = sorted_sizes[-1]
        smallest = sorted_sizes[0]
        total = sum(sizes)
        median = (
            sorted_sizes[len(sorted_sizes) // 2]
            if len(sorted_sizes) % 2 == 1
            else (sorted_sizes[len(sorted_sizes) // 2 - 1]
                  + sorted_sizes[len(sorted_sizes) // 2]) / 2.0
        )
        deviation = _equal_size_deviation(sizes)
        out.append(
            DistributionIndicators(
                unit_id=unit_id,
                algorithm=rows[0].algorithm,
                source_experiment=rows[0].source_experiment,
                n_clusters=len(sizes),
                n_total_customers=total,
                largest_cluster_count=largest,
                smallest_cluster_count=smallest,
                largest_pct_of_total=_safe_pct(largest, total),
                largest_to_smallest_ratio=_safe_div(largest, smallest),
                size_range=largest - smallest,
                deviation_from_equal_size=float(deviation),
                median_cluster_size=float(median),
            )
        )
    return out


__all__ = ["DistributionIndicators", "compute_distribution_indicators"]
