"""CP-03 segment comparison matrix.

For each analysis unit with persisted labels, this module builds the
**Segment Comparison Matrix** — one row per (analysis unit, cluster,
feature) — by joining CP-02 outputs with CP-03 IQR overlap with the
OVERALL population.

Schema (one row per unit, cluster, feature)
-------------------------------------------

- ``unit_id``, ``algorithm``, ``source_experiment``, ``cluster_id``,
  ``cluster_label``, ``feature``: provenance.
- ``count``, ``count_total``, ``mean``, ``median``, ``p25``, ``p75``,
  ``min``, ``max``, ``std``, ``n_missing``: from CP-02 feature profile
  rows (cluster-level).
- ``overall_count``, ``overall_mean``, ``overall_median``,
  ``overall_p25``, ``overall_p75``: from CP-02 OVERALL rows.
- ``rel_diff_median_pct``, ``rel_diff_mean_pct``, ``reference_status``:
  from CP-02 relative comparison rows.
- ``iqr_overlap_with_population``: CP-03 derived IQR overlap between
  cluster IQR and OVERALL IQR (see :mod:`overlap_analysis`).
- ``direction``: HIGHER / LOWER / COMPARABLE / ZERO_REFERENCE / NA from
  CP-02 behavioural interpretation.

DBSCAN noise (``cluster_id == -1``) is NEVER a row in this matrix.
Cluster labels are reported as ``C<id>`` exactly as in CP-01/CP-02.

Hard constraints (AGENTS.md §2):

- Read-only against CP-01 / CP-02 outputs.
- No ranking, no "best / winner / optimal / recommended".
- No segment naming.
- No Marketing recommendation.
- EXP-03 working-selected units contribute zero rows (CP-02 reports
  them as ``NOT_AVAILABLE``).
- All numeric values traceable to CP-02 outputs (no silent recompute).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from customer_segmentation.profiling.cp02.behavioral_interpretation import (
    compute_behavioral_interpretation_table_from_units,
)
from customer_segmentation.profiling.cp02.feature_profiling import (
    FeatureProfileRow,
    compute_feature_profile_table,
)
from customer_segmentation.profiling.cp02.provenance import (
    Cp02AnalysisUnit,
)
from customer_segmentation.profiling.cp02.relative_comparison import (
    RelativeComparisonRow,
    compute_relative_comparison_table,
)
from customer_segmentation.profiling.cp03.overlap_analysis import (
    compute_population_overlap_lookup,
)


@dataclass(frozen=True)
class Cp03ComparisonRow:
    """One row of the segment comparison matrix.

    Combines CP-02 cluster-level statistics + CP-02 OVERALL statistics
    + CP-02 relative comparison + CP-03 IQR overlap with population.
    """

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    feature: str
    count: int
    count_total: int
    mean: float
    median: float
    p25: float
    p75: float
    min: float
    max: float
    std: float
    n_missing: int
    overall_count: int
    overall_mean: float
    overall_median: float
    overall_p25: float
    overall_p75: float
    rel_diff_median_pct: float
    rel_diff_mean_pct: float
    reference_status: str
    iqr_overlap_with_population: float
    direction: str


def _index_feature_rows(
    feature_rows: Sequence[FeatureProfileRow],
) -> Mapping[tuple[str, int, str], FeatureProfileRow]:
    """Index cluster-level feature rows by (unit_id, cluster_id, feature)."""
    out: dict[tuple[str, int, str], FeatureProfileRow] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            continue
        out[(r.unit_id, r.cluster_id, r.feature)] = r
    return out


def _index_overall_rows(
    feature_rows: Sequence[FeatureProfileRow],
) -> Mapping[tuple[str, str], FeatureProfileRow]:
    """Index OVERALL rows by (unit_id, feature)."""
    out: dict[tuple[str, str], FeatureProfileRow] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            out[(r.unit_id, r.feature)] = r
    return out


def _index_rel_rows(
    rel_rows: Sequence[RelativeComparisonRow],
) -> Mapping[tuple[str, int, str], RelativeComparisonRow]:
    """Index relative comparison rows by (unit_id, cluster_id, feature)."""
    out: dict[tuple[str, int, str], RelativeComparisonRow] = {}
    for r in rel_rows:
        out[(r.unit_id, r.cluster_id, r.feature)] = r
    return out


def _index_direction(
    units: Sequence[Cp02AnalysisUnit],
) -> Mapping[tuple[str, int, str], str]:
    """Compute and index direction by (unit_id, cluster_id, feature)."""
    interp = compute_behavioral_interpretation_table_from_units(units)
    out: dict[tuple[str, int, str], str] = {}
    for r in interp:
        out[(r.unit_id, r.cluster_id, r.feature)] = r.direction
    return out


def compute_segment_comparison_matrix(
    units: Sequence[Cp02AnalysisUnit],
) -> list[Cp03ComparisonRow]:
    """Build the segment comparison matrix.

    Steps:
    1. Compute CP-02 cluster-level feature rows.
    2. Compute CP-02 OVERALL rows.
    3. Compute CP-02 relative comparison rows.
    4. Compute CP-03 IQR overlap between cluster IQR and OVERALL IQR.
    5. Compute CP-02 behavioural interpretation (direction).
    6. Join all five sources by (unit_id, cluster_id, feature) for
       non-noise clusters only.
    """
    feature_rows = compute_feature_profile_table(units)
    cluster_idx = _index_feature_rows(feature_rows)
    overall_idx = _index_overall_rows(feature_rows)
    rel_rows = compute_relative_comparison_table(units)
    rel_idx = _index_rel_rows(rel_rows)
    direction_idx = _index_direction(units)
    pop_overlap = compute_population_overlap_lookup(units)

    out: list[Cp03ComparisonRow] = []
    for key, cl_row in cluster_idx.items():
        unit_id, cluster_id, feature = key
        # Lookup overall row.
        overall = overall_idx.get((unit_id, feature))
        if overall is None:
            continue
        rel = rel_idx.get(key)
        rel_med = rel.rel_diff_median_pct if rel is not None else float("nan")
        rel_mean = rel.rel_diff_mean_pct if rel is not None else float("nan")
        ref_status = rel.reference_status if rel is not None else "NA"
        direction = direction_idx.get(key, "NA")
        iqr_overlap = pop_overlap.get(key, float("nan"))
        out.append(
            Cp03ComparisonRow(
                unit_id=unit_id,
                algorithm=cl_row.algorithm,
                source_experiment=cl_row.source_experiment,
                cluster_id=cluster_id,
                cluster_label=cl_row.cluster_label,
                feature=feature,
                count=cl_row.count,
                count_total=cl_row.count_total,
                mean=cl_row.mean,
                median=cl_row.median,
                p25=cl_row.p25,
                p75=cl_row.p75,
                min=cl_row.min,
                max=cl_row.max,
                std=cl_row.std,
                n_missing=cl_row.n_missing,
                overall_count=overall.count,
                overall_mean=overall.mean,
                overall_median=overall.median,
                overall_p25=overall.p25,
                overall_p75=overall.p75,
                rel_diff_median_pct=rel_med,
                rel_diff_mean_pct=rel_mean,
                reference_status=ref_status,
                iqr_overlap_with_population=iqr_overlap,
                direction=direction,
            )
        )
    out.sort(
        key=lambda r: (
            r.unit_id,
            int(r.cluster_label[1:]) if r.cluster_label.startswith("C") else -1,
            r.feature,
        )
    )
    return out


def comparison_rows_to_dicts(rows: Sequence[Cp03ComparisonRow]) -> list[dict[str, Any]]:
    """Serialise comparison rows to plain dicts for CSV output."""
    return [
        {
            "unit_id": r.unit_id,
            "algorithm": r.algorithm,
            "source_experiment": r.source_experiment,
            "cluster_id": r.cluster_id,
            "cluster_label": r.cluster_label,
            "feature": r.feature,
            "count": r.count,
            "count_total": r.count_total,
            "mean": r.mean,
            "median": r.median,
            "p25": r.p25,
            "p75": r.p75,
            "min": r.min,
            "max": r.max,
            "std": r.std,
            "n_missing": r.n_missing,
            "overall_count": r.overall_count,
            "overall_mean": r.overall_mean,
            "overall_median": r.overall_median,
            "overall_p25": r.overall_p25,
            "overall_p75": r.overall_p75,
            "rel_diff_median_pct": r.rel_diff_median_pct,
            "rel_diff_mean_pct": r.rel_diff_mean_pct,
            "reference_status": r.reference_status,
            "iqr_overlap_with_population": r.iqr_overlap_with_population,
            "direction": r.direction,
        }
        for r in rows
    ]


__all__ = [
    "Cp03ComparisonRow",
    "compute_segment_comparison_matrix",
    "comparison_rows_to_dicts",
]
