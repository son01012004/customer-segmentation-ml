"""CP-02 per-cluster feature statistics.

For each analysis unit with persisted labels, this module computes
per-(cluster, feature) descriptive statistics over the RAW
interpretable feature values:

- ``count`` — number of customers with non-NaN value in the cluster.
- ``count_total`` — total customers in cluster (same as CP-01 size).
- ``mean`` — arithmetic mean of non-NaN values.
- ``median`` — P50 of non-NaN values.
- ``p25`` — first quartile.
- ``p75`` — third quartile.
- ``min`` — minimum non-NaN value.
- ``max`` — maximum non-NaN value.
- ``std`` — sample standard deviation (ddof=1) over non-NaN values.
- ``n_missing`` — number of NaN values in the cluster for the feature.

The output is one row per (analysis unit, cluster, feature) tuple
plus an ``OVERALL`` summary row per (analysis unit, feature) used
as the reference for relative comparison.

Hard constraints (AGENTS.md §2):
- Statistics are computed on RAW feature values
  (``customer_candidates.parquet``), NOT on Yeo-Johnson / RobustScaler
  values.
- DBSCAN noise (ClusterLabel == -1) is excluded from cluster rows.
- NaN values are kept as NaN — they are NOT imputed by CP-02.
  ``count`` records the number of valid (non-NaN) observations per
  (cluster, feature).
- No claim of "best", "winner", "optimal" is produced from these
  statistics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)


@dataclass(frozen=True)
class FeatureProfileRow:
    """One (unit, cluster, feature) statistics row."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int  # -1 is NOT a profile row; OVERALL is encoded via cluster_label="OVERALL"
    cluster_label: str  # "C<id>" or "OVERALL"
    feature: str
    count: int  # non-NaN observations
    count_total: int  # total customers in cluster (NaN included)
    mean: float
    median: float
    p25: float
    p75: float
    min: float
    max: float
    std: float
    n_missing: int


def _safe_float(x: float) -> float:
    """Convert NaN to a sentinel so dataclass can stay frozen.

    The sentinel is np.nan which is JSON-incompatible; downstream
    CSV/Markdown writers handle NaN explicitly via ``pd.NA``.
    """
    return float(x) if np.isfinite(x) else float("nan")


def _cluster_label(cluster_id: int) -> str:
    """Render a cluster id as the canonical label string."""
    return f"C{cluster_id}"


def _stats_for_series(s: pd.Series) -> dict[str, float]:
    """Compute count / mean / median / percentiles / min / max / std.

    NaN values are excluded from descriptive statistics; ``count``
    records the number of valid observations.
    """
    s_clean = s.dropna()
    n = int(s_clean.size)
    if n == 0:
        return {
            "count": 0,
            "mean": float("nan"),
            "median": float("nan"),
            "p25": float("nan"),
            "p75": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "std": float("nan"),
        }
    return {
        "count": n,
        "mean": _safe_float(s_clean.mean()),
        "median": _safe_float(s_clean.median()),
        "p25": _safe_float(s_clean.quantile(0.25)),
        "p75": _safe_float(s_clean.quantile(0.75)),
        "min": _safe_float(s_clean.min()),
        "max": _safe_float(s_clean.max()),
        "std": _safe_float(s_clean.std(ddof=1)) if n > 1 else float("nan"),
    }


def _per_cluster_rows(
    unit: Cp02AnalysisUnit,
) -> list[FeatureProfileRow]:
    """Compute per-(cluster, feature) statistics for one unit."""
    if not unit.labels_persisted:
        return []
    df = unit.cluster_labels_frame
    rows: list[FeatureProfileRow] = []
    # Group by cluster id, excluding -1 (noise) — DBSCAN noise is
    # reported separately by CP-01 and is NOT a Customer Segment here.
    eligible = df.loc[df["ClusterLabel"] != -1].copy()
    for cl, sub in eligible.groupby("ClusterLabel", sort=True):
        cl_int = int(cl)
        cl_label = _cluster_label(cl_int)
        count_total = int(sub["CustomerID"].nunique())
        for feat in FEATURE_COLUMNS:
            stats = _stats_for_series(sub[feat])
            rows.append(
                FeatureProfileRow(
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    cluster_id=cl_int,
                    cluster_label=cl_label,
                    feature=feat,
                    count=stats["count"],
                    count_total=count_total,
                    mean=stats["mean"],
                    median=stats["median"],
                    p25=stats["p25"],
                    p75=stats["p75"],
                    min=stats["min"],
                    max=stats["max"],
                    std=stats["std"],
                    n_missing=count_total - stats["count"],
                )
            )
    return rows


def _overall_rows(
    unit: Cp02AnalysisUnit,
) -> list[FeatureProfileRow]:
    """Compute the OVERALL (cluster_label="OVERALL") reference row per feature.

    The reference is computed over the FULL customer population used
    in the analysis unit — that is, every customer with a valid
    ClusterLabel (noise excluded). For DBSCAN this is the
    ``non-noise`` subset. For other algorithms it is the full
    population. This matches the denominator used for the cluster
    counts and keeps the relative comparison meaningful.
    """
    if not unit.labels_persisted:
        return []
    df = unit.cluster_labels_frame
    eligible = df.loc[df["ClusterLabel"] != -1].copy()
    rows: list[FeatureProfileRow] = []
    count_total = int(eligible["CustomerID"].nunique())
    for feat in FEATURE_COLUMNS:
        stats = _stats_for_series(eligible[feat])
        rows.append(
            FeatureProfileRow(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                cluster_id=-999,  # sentinel; cluster_label="OVERALL" is the user-facing key
                cluster_label="OVERALL",
                feature=feat,
                count=stats["count"],
                count_total=count_total,
                mean=stats["mean"],
                median=stats["median"],
                p25=stats["p25"],
                p75=stats["p75"],
                min=stats["min"],
                max=stats["max"],
                std=stats["std"],
                n_missing=count_total - stats["count"],
            )
        )
    return rows


def compute_feature_profile_table(
    units: Sequence[Cp02AnalysisUnit],
) -> list[FeatureProfileRow]:
    """Compute per-(unit, cluster, feature) statistics.

    For each analysis unit with persisted labels, this returns:

    - One row per (cluster, feature) for every non-noise cluster.
    - One ``OVERALL`` row per feature, computed over the union of
      non-noise customers in the unit.

    The OVERALL rows are used by the relative-comparison module as
    the reference for "how different is this cluster from the
    overall population?".

    Analysis units without persisted labels (EXP-03 working-selected)
    contribute zero rows here; the runner records that as
    ``NOT_AVAILABLE``.
    """
    rows: list[FeatureProfileRow] = []
    for unit in units:
        rows.extend(_per_cluster_rows(unit))
        rows.extend(_overall_rows(unit))
    return rows


def compute_overall_feature_summary(
    units: Sequence[Cp02AnalysisUnit],
) -> Mapping[tuple[str, str], FeatureProfileRow]:
    """Return a dict of OVERALL rows keyed by (unit_id, feature).

    Convenience accessor used by the relative-comparison module and
    the report.
    """
    out: dict[tuple[str, str], FeatureProfileRow] = {}
    for unit in units:
        for row in _overall_rows(unit):
            out[(row.unit_id, row.feature)] = row
    return out


__all__ = [
    "FeatureProfileRow",
    "compute_feature_profile_table",
    "compute_overall_feature_summary",
    "FEATURE_COLUMNS",
]
