"""CP-02 relative comparison between clusters and the overall population.

For each (analysis unit, cluster, feature) triple this module computes
the **relative difference** between the cluster statistic (mean,
median) and the OVERALL population reference (same unit, same feature,
non-noise subset).

Formula (per task brief §9):

    relative_difference = (cluster_value - reference_value) / reference_value × 100

Reference
---------
The reference is the OVERALL (non-noise) population statistic
computed inside the SAME analysis unit. The reference depends on the
feature — for ``Monetary`` it is the overall population median
Monetary; for ``Recency`` it is the overall population median Recency.

Why median as primary reference?
- Most features are heavy-tailed / right-skewed (Monetary, TotalQuantity,
  Frequency, ActiveDays, ...); the median is robust to skew and to
  small cluster sizes (especially DBSCAN sub-clusters with ≤ 10
  customers).
- Mean is provided as a secondary reference for completeness but the
  behavioural interpretation module primarily reads the median-based
  relative difference.

Division-by-zero / unsuitability handling
-----------------------------------------
When ``reference_value == 0`` the percentage is mathematically
undefined. CP-02 records ``relative_difference_pct = NA`` and flags
the row with ``reference_status = "ZERO_REFERENCE"``. For features
where 0 is a frequent value (e.g., ``CancellationRate`` can be 0 for
customers with no cancellations) the cluster-mean reference is also
checked; if it is meaningfully larger than 0 we still emit a
qualitative directional note (see behavioural_interpretation module).

Features where 0 reference is plausible:
- CancellationRate, ReturnRate — many customers may have 0.
- All other features (Recency, Frequency, Monetary, ...) have min ≥ 0
  in the dataset; 0 may appear for Recency = "today" or Frequency = 1,
  etc. CP-02 handles each row on its own merits.

Hard constraints (AGENTS.md §2):
- No ranking, no "best", no "winner", no "optimal".
- No segment naming.
- No marketing recommendation.
- Direction is descriptive only — relative to a population statistic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from customer_segmentation.profiling.cp02.feature_profiling import (
    compute_feature_profile_table,
    compute_overall_feature_summary,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)

# Reference value below which we treat the reference as "not
# meaningfully larger than zero" for percentage comparison. This is
# not a research-grade threshold — it is a defensive guard against
# noisy percentages from near-zero references.
ZERO_REFERENCE_FLOOR = 1e-9


@dataclass(frozen=True)
class RelativeComparisonRow:
    """One (unit, cluster, feature) relative-comparison row."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    feature: str
    cluster_median: float
    cluster_mean: float
    overall_median: float
    overall_mean: float
    rel_diff_median_pct: float  # NaN if undefined
    rel_diff_mean_pct: float  # NaN if undefined
    reference_status: str  # "OK" | "ZERO_REFERENCE" | "NA"
    reference_count: int  # OVERALL count used as denominator


def _pct_diff(cluster_value: float, ref_value: float) -> tuple[float, str]:
    """Return (percentage, status).

    status = "OK" when ref_value is meaningfully > 0.
    status = "ZERO_REFERENCE" when ref_value ≤ ZERO_REFERENCE_FLOOR.
    status = "NA" when either input is NaN.
    """
    if np.isnan(cluster_value) or np.isnan(ref_value):
        return float("nan"), "NA"
    if abs(ref_value) <= ZERO_REFERENCE_FLOOR:
        return float("nan"), "ZERO_REFERENCE"
    pct = (cluster_value - ref_value) / abs(ref_value) * 100.0
    return float(pct), "OK"


def compute_relative_comparison_table(
    units: Sequence[Cp02AnalysisUnit],
) -> list[RelativeComparisonRow]:
    """Compute relative differences per (unit, cluster, feature).

    For each analysis unit:

    - Build the OVERALL reference (per feature, median + mean).
    - For every cluster row, compute relative_diff vs OVERALL using
      both median and mean as the cluster statistic.

    Units without persisted labels contribute zero rows (the runner
    reports them as ``NOT_AVAILABLE``).
    """
    overall_lookup = compute_overall_feature_summary(units)
    cluster_rows = [r for r in compute_feature_profile_table(units) if r.cluster_label != "OVERALL"]
    out: list[RelativeComparisonRow] = []
    for r in cluster_rows:
        ref = overall_lookup.get((r.unit_id, r.feature))
        if ref is None:
            continue
        rel_med_pct, status_med = _pct_diff(r.median, ref.median)
        rel_mean_pct, status_mean = _pct_diff(r.mean, ref.mean)
        # If either branch is ZERO_REFERENCE, prefer that flag; if both
        # are OK use OK; if NA on one but OK on other, mark NA.
        if status_med == "ZERO_REFERENCE" or status_mean == "ZERO_REFERENCE":
            status = "ZERO_REFERENCE"
        elif status_med == "NA" or status_mean == "NA":
            status = "NA"
        else:
            status = "OK"
        out.append(
            RelativeComparisonRow(
                unit_id=r.unit_id,
                algorithm=r.algorithm,
                source_experiment=r.source_experiment,
                cluster_id=r.cluster_id,
                cluster_label=r.cluster_label,
                feature=r.feature,
                cluster_median=r.median,
                cluster_mean=r.mean,
                overall_median=ref.median,
                overall_mean=ref.mean,
                rel_diff_median_pct=rel_med_pct,
                rel_diff_mean_pct=rel_mean_pct,
                reference_status=status,
                reference_count=ref.count,
            )
        )
    return out


__all__ = [
    "RelativeComparisonRow",
    "compute_relative_comparison_table",
    "ZERO_REFERENCE_FLOOR",
    "FEATURE_COLUMNS",
]
