"""CP-03 IQR overlap analysis.

For each (analysis unit, cluster, feature) and each pair of clusters
within the same unit, this module computes an **IQR overlap
coefficient** to support cluster-separation evidence.

Definitions
-----------

For two cluster (or cluster-vs-population) IQRs:

    IQR_A = [P25_A, P75_A]
    IQR_B = [P25_B, P75_B]

We compute:

    intersection_width = max(0, min(P75_A, P75_B) - max(P25_A, P25_B))
    iqr_width_A        = max(P75_A - P25_A, 0)
    iqr_width_B        = max(P75_B - P25_B, 0)

The IQR overlap coefficient is then:

    iqr_overlap = intersection_width / max(iqr_width_A, iqr_width_B)

This is bounded in [0, 1]:

- ``1.0`` = identical IQRs (perfect overlap).
- ``0.0`` = disjoint IQRs (no overlap).
- in between = partial overlap.

If both IQRs are zero-width (constant feature within both groups), the
IQR overlap is defined as ``1.0`` when both medians are equal and
``0.0`` otherwise.

Why IQR overlap (not range or kernel-density overlap)?

- The IQR is robust to outliers and skew — appropriate for the
  heavily skewed RAW RFM features (Monetary, TotalQuantity, ...).
- It is computable from the same CP-02 outputs (P25, P75) — no
  recomputation needed.
- It is monotonic in cluster separation: smaller IQR overlap ↔
  larger cluster separation in IQR terms.

Hard constraints (AGENTS.md §2):

- No ranking, no "best", no "winner".
- DBSCAN noise excluded.
- EXP-03 working-selected units = ``NOT_AVAILABLE`` (no overlap rows).
- The IQR overlap coefficient is descriptive only; CP-03 does NOT
  promote it to a "separation score" or composite ranking metric.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

import numpy as np

from customer_segmentation.profiling.cp02.feature_profiling import (
    FeatureProfileRow,
    compute_feature_profile_table,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)

# Numerical guard for IQR width when both sides are essentially zero.
IQR_WIDTH_FLOOR = 1e-12


def iqr_overlap_coefficient(p25_a: float, p75_a: float, p25_b: float, p75_b: float) -> float:
    """Compute the IQR overlap coefficient between two IQRs.

    Returns a value in [0, 1]:

    - ``1.0`` if the IQRs are identical (or both zero-width with equal
      medians).
    - ``0.0`` if the IQRs are disjoint (no overlap) or both zero-width
      with different medians.
    - in between = partial overlap, defined as
      ``intersection_width / max(iqr_width_a, iqr_width_b)``.

    If either IQR has NaN percentile, the function returns ``NaN``.
    """
    a_vals = (p25_a, p75_a)
    b_vals = (p25_b, p75_b)
    if any(np.isnan(v) for v in (*a_vals, *b_vals)):
        return float("nan")
    width_a = max(p75_a - p25_a, 0.0)
    width_b = max(p75_b - p25_b, 0.0)
    if width_a <= IQR_WIDTH_FLOOR and width_b <= IQR_WIDTH_FLOOR:
        # Both IQRs are zero-width; we define overlap by median equality.
        median_a = (p25_a + p75_a) / 2.0
        median_b = (p25_b + p75_b) / 2.0
        return 1.0 if abs(median_a - median_b) <= IQR_WIDTH_FLOOR else 0.0
    intersection = max(0.0, min(p75_a, p75_b) - max(p25_a, p25_b))
    denom = max(width_a, width_b)
    if denom <= IQR_WIDTH_FLOOR:
        # Pathological: one is zero-width, the other is wider but
        # intersection = 0. We return 0.
        return 0.0
    return float(intersection / denom)


@dataclass(frozen=True)
class Cp03OverlapRow:
    """One pairwise IQR overlap row (cluster_a, cluster_b, feature)."""

    unit_id: str
    algorithm: str
    source_experiment: str
    feature: str
    cluster_a_label: str
    cluster_a_id: int
    cluster_b_label: str
    cluster_b_id: int
    iqr_overlap_coefficient: float
    iqr_intersection_width: float
    iqr_width_a: float
    iqr_width_b: float


def _index_cluster_feature_rows(
    feature_rows: Sequence[FeatureProfileRow],
) -> Mapping[tuple[str, int, str], FeatureProfileRow]:
    """Index cluster-level feature rows by (unit_id, cluster_id, feature)."""
    out: dict[tuple[str, int, str], FeatureProfileRow] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            continue
        out[(r.unit_id, r.cluster_id, r.feature)] = r
    return out


def compute_pairwise_overlap_table(
    units: Sequence[Cp02AnalysisUnit],
) -> list[Cp03OverlapRow]:
    """Compute pairwise IQR overlap rows for every (unit, cluster pair, feature).

    For each analysis unit with persisted labels and ``n`` non-noise
    clusters, this returns ``n × (n − 1) / 2`` cluster pairs ×
    ``len(FEATURE_COLUMNS)`` overlap rows. Units without persisted
    labels (EXP-03 working-selected) contribute zero rows.

    The pair (a, b) is encoded with ``a_id < b_id`` so each unordered
    pair appears exactly once.
    """
    feature_rows = compute_feature_profile_table(units)
    # Group rows by (unit_id, feature) for fast pair iteration.
    by_unit_feature: dict[tuple[str, str], list[FeatureProfileRow]] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            continue
        by_unit_feature.setdefault((r.unit_id, r.feature), []).append(r)
    out: list[Cp03OverlapRow] = []
    for (unit_id, feature), rows in by_unit_feature.items():
        # Sort by cluster_id for deterministic ordering.
        sorted_rows = sorted(rows, key=lambda r: r.cluster_id)
        for ra, rb in combinations(sorted_rows, 2):
            a_id = ra.cluster_id
            b_id = rb.cluster_id
            if a_id == b_id:
                continue
            if a_id > b_id:
                ra, rb = rb, ra
                a_id, b_id = b_id, a_id
            iqr_a = ra.p75 - ra.p25
            iqr_b = rb.p75 - rb.p25
            intersection = max(0.0, min(ra.p75, rb.p75) - max(ra.p25, rb.p25))
            coef = iqr_overlap_coefficient(ra.p25, ra.p75, rb.p25, rb.p75)
            out.append(
                Cp03OverlapRow(
                    unit_id=unit_id,
                    algorithm=ra.algorithm,
                    source_experiment=ra.source_experiment,
                    feature=feature,
                    cluster_a_label=ra.cluster_label,
                    cluster_a_id=a_id,
                    cluster_b_label=rb.cluster_label,
                    cluster_b_id=b_id,
                    iqr_overlap_coefficient=coef,
                    iqr_intersection_width=intersection,
                    iqr_width_a=iqr_a,
                    iqr_width_b=iqr_b,
                )
            )
    out.sort(key=lambda r: (r.unit_id, r.feature, r.cluster_a_id, r.cluster_b_id))
    return out


def compute_population_overlap_lookup(
    units: Sequence[Cp02AnalysisUnit],
) -> Mapping[tuple[str, int, str], float]:
    """Compute IQR overlap between each cluster and the OVERALL population.

    Returns a dict keyed by ``(unit_id, cluster_id, feature)`` mapping to
    the IQR overlap coefficient ``intersection / max(IQR_cluster,
    IQR_OVERALL)``. Used by the segment comparison matrix.
    """
    feature_rows = compute_feature_profile_table(units)
    overall_by_key: dict[tuple[str, str], FeatureProfileRow] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            overall_by_key[(r.unit_id, r.feature)] = r
    out: dict[tuple[str, int, str], float] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            continue
        overall = overall_by_key.get((r.unit_id, r.feature))
        if overall is None:
            continue
        coef = iqr_overlap_coefficient(
            p25_a=r.p25, p75_a=r.p75, p25_b=overall.p25, p75_b=overall.p75
        )
        out[(r.unit_id, r.cluster_id, r.feature)] = coef
    return out


__all__ = [
    "Cp03OverlapRow",
    "compute_pairwise_overlap_table",
    "compute_population_overlap_lookup",
    "iqr_overlap_coefficient",
    "IQR_WIDTH_FLOOR",
    "FEATURE_COLUMNS",
]
