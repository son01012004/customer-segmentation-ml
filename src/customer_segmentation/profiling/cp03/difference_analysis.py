"""CP-03 per-(unit, feature) distinguishing feature analysis.

For each (analysis unit, feature), CP-03 derives a set of **distinguishing
indicators** describing how much the cluster profiles differ on that
feature, then assigns an **analytical classification**:

- ``HIGH_DIFFERENCE_OBSERVED`` — large effect range AND low average
  IQR overlap; clusters clearly separate along this feature.
- ``MODERATE_DIFFERENCE_OBSERVED`` — meaningful effect range OR partial
  IQR separation; clusters differ on this feature but not strongly.
- ``LOW_DIFFERENCE_OBSERVED`` — small effect range AND high IQR overlap;
  clusters do not differ meaningfully along this feature.
- ``HIGH_OVERLAP`` — clusters have largely overlapping IQRs
  (overlap ≥ HIGH_OVERLAP_MEAN); separated from HIGH/MODERATE/LOW by
  stronger focus on overlap rather than effect range.
- ``NOT_ASSESSABLE`` — fewer than 2 assessable clusters, or all clusters
  ZERO_REFERENCE / NA; no meaningful comparison possible.

Indicators computed per (unit, feature)
---------------------------------------

- ``n_clusters_assessable`` — number of clusters with a valid
  median / P25 / P75 for the feature (excluding DBSCAN noise and
  excluding NaN statistics).
- ``cluster_median_min``, ``cluster_median_max`` — min/max of cluster
  medians.
- ``cluster_p25_min``, ``cluster_p75_max`` — extremes of cluster
  percentile values (not medians).
- ``effect_range`` = cluster_median_max − cluster_median_min (RAW units).
- ``effect_range_rel_pct`` = effect_range / |overall_median| × 100 if
  |overall_median| > 1e-9, else NaN.
- ``iqr_overlap_mean`` — mean pairwise IQR overlap coefficient across
  cluster pairs (NaN if fewer than 2 assessable clusters).
- ``iqr_overlap_median`` — median pairwise IQR overlap coefficient.
- ``iqr_overlap_min`` — minimum pairwise IQR overlap (i.e., most
  separated pair).
- ``iqr_overlap_max`` — maximum pairwise IQR overlap (i.e., most
  overlapping pair).
- ``n_clusters_higher`` — number of clusters with direction HIGHER
  (relative to OVERALL median) from CP-02.
- ``n_clusters_lower`` — number of clusters with direction LOWER.
- ``n_clusters_comparable`` — number of clusters with direction
  COMPARABLE.
- ``n_clusters_zero_reference`` — number of clusters with
  reference_status ZERO_REFERENCE (overall median ≈ 0).
- ``direction_consistency_ratio`` — max(n_higher, n_lower) /
  n_assessable if n_assessable > 0; otherwise NaN. Indicates whether
  most clusters push the feature in the same direction relative to
  OVERALL.

WORKING_ANALYTICAL_THRESHOLD
----------------------------

The thresholds used for analytical classification are NOT research-grade
and are explicitly labelled ``WORKING_ANALYTICAL_THRESHOLD`` in the
module-level constants and in the report. They are conservative
defaults chosen to be sensitive to clearly observable differences while
not over-claiming separation for partially overlapping features.

A reader (or mentor) may re-bin the classification with different
thresholds without modifying the CP-03 source code — the indicators
table is the primary evidence surface.

Hard constraints (AGENTS.md §2):

- No ranking, no "best", no "winner", no composite scoring framework.
- No segment naming, no Marketing recommendation.
- DBSCAN noise excluded.
- EXP-03 working-selected units produce empty indicator rows.
- Indicators are computed from RAW feature values (no transformation).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from customer_segmentation.profiling.cp02.feature_profiling import (
    FeatureProfileRow,
    compute_feature_profile_table,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)
from customer_segmentation.profiling.cp02.relative_comparison import (
    RelativeComparisonRow,
    compute_relative_comparison_table,
)
from customer_segmentation.profiling.cp03.overlap_analysis import (
    compute_pairwise_overlap_table,
)

# --- WORKING_ANALYTICAL_THRESHOLD -------------------------------------
# These thresholds are NOT research-grade. They are conservative
# analytical defaults for descriptive classification only. A reader
# may change them and re-bin classification without modifying the
# CP-03 source code.

# Effect range (relative to OVERALL median) at which a feature is
# considered to show "high" vs "moderate" vs "low" between-cluster
# difference in median values.
WORKING_HIGH_DIFFERENCE_EFFECT_PCT: float = 50.0
WORKING_MODERATE_DIFFERENCE_EFFECT_PCT: float = 15.0
WORKING_LOW_DIFFERENCE_EFFECT_PCT: float = 15.0

# Mean pairwise IQR overlap coefficient thresholds. Higher overlap =
# less separation; lower overlap = more separation.
WORKING_HIGH_OVERLAP_MEAN: float = 0.7
WORKING_MODERATE_OVERLAP_MEAN: float = 0.5

# Minimum number of assessable clusters required for a meaningful
# classification. Below this, the indicator is reported as
# NOT_ASSESSABLE regardless of effect size.
MIN_ASSESSABLE_CLUSTERS: int = 2

# Numerical guard for |overall_median| when computing effect range.
# If |overall_median| is below this, effect_range_rel_pct is NaN.
OVERALL_MEDIAN_FLOOR: float = 1e-9


@dataclass(frozen=True)
class Cp03DistinguishingRow:
    """One (unit, feature) distinguishing-indicator row."""

    unit_id: str
    algorithm: str
    source_experiment: str
    feature: str
    n_clusters_assessable: int
    cluster_median_min: float
    cluster_median_max: float
    cluster_p25_min: float
    cluster_p75_max: float
    effect_range: float
    effect_range_rel_pct: float
    iqr_overlap_mean: float
    iqr_overlap_median: float
    iqr_overlap_min: float
    iqr_overlap_max: float
    n_clusters_higher: int
    n_clusters_lower: int
    n_clusters_comparable: int
    n_clusters_zero_reference: int
    direction_consistency_ratio: float
    classification: str  # HIGH/MODERATE/LOW_DIFFERENCE_OBSERVED / HIGH_OVERLAP / NOT_ASSESSABLE


def _safe_min(values: Sequence[float]) -> float:
    arr = np.array([v for v in values if np.isfinite(v)], dtype=float)
    if arr.size == 0:
        return float("nan")
    return float(arr.min())


def _safe_max(values: Sequence[float]) -> float:
    arr = np.array([v for v in values if np.isfinite(v)], dtype=float)
    if arr.size == 0:
        return float("nan")
    return float(arr.max())


def _safe_mean(values: Sequence[float]) -> float:
    arr = np.array([v for v in values if np.isfinite(v)], dtype=float)
    if arr.size == 0:
        return float("nan")
    return float(arr.mean())


def _safe_median(values: Sequence[float]) -> float:
    arr = np.array([v for v in values if np.isfinite(v)], dtype=float)
    if arr.size == 0:
        return float("nan")
    return float(np.median(arr))


def classify_distinguishing_feature(
    effect_range_rel_pct: float,
    iqr_overlap_mean: float,
    n_clusters_assessable: int,
) -> str:
    """Classify a (unit, feature) into an analytical category.

    Returns one of:

    - ``NOT_ASSESSABLE`` — fewer than MIN_ASSESSABLE_CLUSTERS clusters.
    - ``HIGH_OVERLAP`` — IQR overlap ≥ WORKING_HIGH_OVERLAP_MEAN
      (cluster IQRs are largely overlapping).
    - ``HIGH_DIFFERENCE_OBSERVED`` — effect range (rel %) ≥
      WORKING_HIGH_DIFFERENCE_EFFECT_PCT AND mean IQR overlap ≤
      WORKING_MODERATE_OVERLAP_MEAN.
    - ``MODERATE_DIFFERENCE_OBSERVED`` — effect range (rel %) ≥
      WORKING_MODERATE_DIFFERENCE_EFFECT_PCT.
    - ``LOW_DIFFERENCE_OBSERVED`` — none of the above.

    Returns ``NOT_ASSESSABLE`` if the inputs are non-finite.
    """
    if n_clusters_assessable < MIN_ASSESSABLE_CLUSTERS or np.isnan(n_clusters_assessable):
        return "NOT_ASSESSABLE"
    if np.isnan(effect_range_rel_pct):
        return "NOT_ASSESSABLE"
    if not np.isnan(iqr_overlap_mean) and iqr_overlap_mean >= WORKING_HIGH_OVERLAP_MEAN:
        return "HIGH_OVERLAP"
    if effect_range_rel_pct >= WORKING_HIGH_DIFFERENCE_EFFECT_PCT and (
        np.isnan(iqr_overlap_mean) or iqr_overlap_mean <= WORKING_MODERATE_OVERLAP_MEAN
    ):
        return "HIGH_DIFFERENCE_OBSERVED"
    if effect_range_rel_pct >= WORKING_MODERATE_DIFFERENCE_EFFECT_PCT:
        return "MODERATE_DIFFERENCE_OBSERVED"
    return "LOW_DIFFERENCE_OBSERVED"


def _index_cluster_rows(
    feature_rows: Sequence[FeatureProfileRow],
) -> Mapping[tuple[str, str], list[FeatureProfileRow]]:
    """Group cluster-level rows (non-OVERALL) by (unit_id, feature)."""
    out: dict[tuple[str, str], list[FeatureProfileRow]] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            continue
        out.setdefault((r.unit_id, r.feature), []).append(r)
    return out


def _index_overall_rows(
    feature_rows: Sequence[FeatureProfileRow],
) -> Mapping[tuple[str, str], FeatureProfileRow]:
    out: dict[tuple[str, str], FeatureProfileRow] = {}
    for r in feature_rows:
        if r.cluster_label == "OVERALL":
            out[(r.unit_id, r.feature)] = r
    return out


def _index_rel_rows_by_unit_feature(
    rel_rows: Sequence[RelativeComparisonRow],
) -> Mapping[tuple[str, str], list[RelativeComparisonRow]]:
    out: dict[tuple[str, str], list[RelativeComparisonRow]] = {}
    for r in rel_rows:
        out.setdefault((r.unit_id, r.feature), []).append(r)
    return out


def _index_overlap_by_unit_feature() -> Mapping[tuple[str, str], list[float]]:
    """Index pairwise overlap coefficients by (unit_id, feature).

    Reads from the module-level ``compute_pairwise_overlap_table`` output.
    Implemented lazily so the difference-analysis module does not depend
    on the runner's specific pass order.
    """
    # This helper is replaced by compute_distinguishing_feature_table
    # below which calls compute_pairwise_overlap_table directly.
    raise NotImplementedError


def compute_distinguishing_feature_table(
    units: Sequence[Cp02AnalysisUnit],
) -> list[Cp03DistinguishingRow]:
    """Compute per-(unit, feature) distinguishing indicator rows.

    Units without persisted labels contribute zero rows. DBSCAN noise
    is excluded from cluster statistics.
    """
    feature_rows = compute_feature_profile_table(units)
    cluster_idx = _index_cluster_rows(feature_rows)
    overall_idx = _index_overall_rows(feature_rows)
    rel_rows = compute_relative_comparison_table(units)
    rel_by_uf = _index_rel_rows_by_unit_feature(rel_rows)
    overlap_rows = compute_pairwise_overlap_table(units)

    overlap_by_uf: dict[tuple[str, str], list[float]] = {}
    for r in overlap_rows:
        overlap_by_uf.setdefault((r.unit_id, r.feature), []).append(r.iqr_overlap_coefficient)

    out: list[Cp03DistinguishingRow] = []
    for (unit_id, feature), cl_rows in cluster_idx.items():
        # Filter clusters with finite median/p25/p75.
        assessable = [
            r
            for r in cl_rows
            if np.isfinite(r.median) and np.isfinite(r.p25) and np.isfinite(r.p75)
        ]
        n_assessable = len(assessable)
        medians = [r.median for r in assessable]
        p25s = [r.p25 for r in assessable]
        p75s = [r.p75 for r in assessable]
        median_min = _safe_min(medians)
        median_max = _safe_max(medians)
        p25_min = _safe_min(p25s)
        p75_max = _safe_max(p75s)
        if np.isfinite(median_min) and np.isfinite(median_max):
            effect_range = float(median_max - median_min)
        else:
            effect_range = float("nan")
        # Effect range relative to OVERALL median.
        overall = overall_idx.get((unit_id, feature))
        if overall is not None and np.isfinite(overall.median):
            overall_med = float(overall.median)
            if abs(overall_med) > OVERALL_MEDIAN_FLOOR and np.isfinite(effect_range):
                effect_range_rel_pct = effect_range / abs(overall_med) * 100.0
            else:
                effect_range_rel_pct = float("nan")
        else:
            overall_med = float("nan")
            effect_range_rel_pct = float("nan")
        # Pairwise IQR overlap stats.
        coefs = overlap_by_uf.get((unit_id, feature), [])
        iqr_mean = _safe_mean(coefs)
        iqr_median = _safe_median(coefs)
        iqr_min = _safe_min(coefs)
        iqr_max = _safe_max(coefs)
        # Direction counts from CP-02 relative comparison rows.
        unit_rel = rel_by_uf.get((unit_id, feature), [])
        n_higher = sum(
            1
            for r in unit_rel
            if r.reference_status == "OK"
            and np.isfinite(r.rel_diff_median_pct)
            and r.rel_diff_median_pct >= 10.0
        )
        n_lower = sum(
            1
            for r in unit_rel
            if r.reference_status == "OK"
            and np.isfinite(r.rel_diff_median_pct)
            and r.rel_diff_median_pct <= -10.0
        )
        n_comparable = sum(
            1
            for r in unit_rel
            if r.reference_status == "OK"
            and np.isfinite(r.rel_diff_median_pct)
            and -10.0 < r.rel_diff_median_pct < 10.0
        )
        n_zero_ref = sum(1 for r in unit_rel if r.reference_status == "ZERO_REFERENCE")
        consistency = max(n_higher, n_lower) / n_assessable if n_assessable > 0 else float("nan")
        classification = classify_distinguishing_feature(
            effect_range_rel_pct=effect_range_rel_pct,
            iqr_overlap_mean=iqr_mean,
            n_clusters_assessable=n_assessable,
        )
        # Use algorithm / source_experiment from any cluster row.
        algo = cl_rows[0].algorithm if cl_rows else ""
        src_exp = cl_rows[0].source_experiment if cl_rows else ""
        out.append(
            Cp03DistinguishingRow(
                unit_id=unit_id,
                algorithm=algo,
                source_experiment=src_exp,
                feature=feature,
                n_clusters_assessable=n_assessable,
                cluster_median_min=median_min,
                cluster_median_max=median_max,
                cluster_p25_min=p25_min,
                cluster_p75_max=p75_max,
                effect_range=effect_range,
                effect_range_rel_pct=effect_range_rel_pct,
                iqr_overlap_mean=iqr_mean,
                iqr_overlap_median=iqr_median,
                iqr_overlap_min=iqr_min,
                iqr_overlap_max=iqr_max,
                n_clusters_higher=n_higher,
                n_clusters_lower=n_lower,
                n_clusters_comparable=n_comparable,
                n_clusters_zero_reference=n_zero_ref,
                direction_consistency_ratio=consistency,
                classification=classification,
            )
        )
    out.sort(key=lambda r: (r.unit_id, r.feature))
    return out


def distinguishing_rows_to_dicts(
    rows: Sequence[Cp03DistinguishingRow],
) -> list[dict[str, object]]:
    """Serialise distinguishing rows to plain dicts for CSV output."""
    return [
        {
            "unit_id": r.unit_id,
            "algorithm": r.algorithm,
            "source_experiment": r.source_experiment,
            "feature": r.feature,
            "n_clusters_assessable": r.n_clusters_assessable,
            "cluster_median_min": r.cluster_median_min,
            "cluster_median_max": r.cluster_median_max,
            "cluster_p25_min": r.cluster_p25_min,
            "cluster_p75_max": r.cluster_p75_max,
            "effect_range": r.effect_range,
            "effect_range_rel_pct": r.effect_range_rel_pct,
            "iqr_overlap_mean": r.iqr_overlap_mean,
            "iqr_overlap_median": r.iqr_overlap_median,
            "iqr_overlap_min": r.iqr_overlap_min,
            "iqr_overlap_max": r.iqr_overlap_max,
            "n_clusters_higher": r.n_clusters_higher,
            "n_clusters_lower": r.n_clusters_lower,
            "n_clusters_comparable": r.n_clusters_comparable,
            "n_clusters_zero_reference": r.n_clusters_zero_reference,
            "direction_consistency_ratio": r.direction_consistency_ratio,
            "classification": r.classification,
        }
        for r in rows
    ]


__all__ = [
    "Cp03DistinguishingRow",
    "classify_distinguishing_feature",
    "compute_distinguishing_feature_table",
    "distinguishing_rows_to_dicts",
    "WORKING_HIGH_DIFFERENCE_EFFECT_PCT",
    "WORKING_MODERATE_DIFFERENCE_EFFECT_PCT",
    "WORKING_LOW_DIFFERENCE_EFFECT_PCT",
    "WORKING_HIGH_OVERLAP_MEAN",
    "WORKING_MODERATE_OVERLAP_MEAN",
    "MIN_ASSESSABLE_CLUSTERS",
    "OVERALL_MEDIAN_FLOOR",
    "FEATURE_COLUMNS",
]
