"""CP-05 size evaluation — Segment Size Evaluation (per plan §8).

Sử dụng WORKING_ANALYTICAL_SIZE_BAND (PENDING_REVIEW) để phân loại
size. ``n < 30`` chỉ là reliability warning, KHÔNG tự động loại
segment.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
)

# WORKING_ANALYTICAL_SIZE_BAND (per plan §8.3) — cần mentor review
# trước khi promote.
DOMINANT_PCT = 50.0
LARGE_PCT = 25.0
MEDIUM_PCT = 5.0
SMALL_PCT = 1.0

# Statistical reliability heuristic (Central Limit Theorem rough).
N_RELIABILITY_THRESHOLD = 30

SIZE_BANDS = (
    "DOMINANT",
    "LARGE",
    "MEDIUM",
    "SMALL",
    "VERY_SMALL",
)


@dataclass(frozen=True)
class SizeResult:
    """Per-segment size evaluation result."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    n_customers: int
    pct_of_assigned: float
    pct_of_total: float
    relative_size_ratio: float
    size_band: str
    statistical_reliability_flag: str
    is_noise: bool
    evidence_source: str
    limitations: str


def _classify_size_band(pct_assigned: float) -> str:
    """Apply WORKING_ANALYTICAL_SIZE_BAND thresholds."""
    if pct_assigned >= DOMINANT_PCT:
        return "DOMINANT"
    if pct_assigned >= LARGE_PCT:
        return "LARGE"
    if pct_assigned >= MEDIUM_PCT:
        return "MEDIUM"
    if pct_assigned >= SMALL_PCT:
        return "SMALL"
    return "VERY_SMALL"


def _classify_reliability(n: int) -> str:
    """Statistical reliability warning (heuristic only)."""
    if n < N_RELIABILITY_THRESHOLD:
        return "LOW"
    return "ADEQUATE"


def evaluate_size(
    bundle: Cp04EvidenceBundle,
) -> list[SizeResult]:
    """Evaluate segment size cho một analysis unit.

    Parameters
    ----------
    bundle : Cp04EvidenceBundle
        Evidence bundle đã load CP-01 → CP-04.

    Returns
    -------
    list[SizeResult]
        Một entry per non-noise cluster. Noise bucket (DBSCAN) được
        trả về với ``is_noise=True`` và ``size_band='NOT_APPLICABLE'``.
    """
    unit: Cp05AnalysisUnit = bundle.unit
    size_df: pd.DataFrame = bundle.size_df
    results: list[SizeResult] = []

    for _, row in size_df.iterrows():
        cluster_id = int(row["cluster_id"])
        is_noise = cluster_id == -1
        cluster_label = "noise (-1)" if is_noise else f"C{cluster_id}"
        n_customers = int(row["customer_count"])
        pct_of_assigned = float(row["pct_of_assigned"])
        pct_of_total = float(row["pct_of_total"])
        rel_ratio = float(row["relative_size_ratio"])

        if is_noise:
            size_band = "NOT_APPLICABLE"
            reliability_flag = "NOT_APPLICABLE"
            limitations = "DBSCAN noise bucket — KHÔNG phải Customer Segment " "(per CP-04 §3.2)."
        else:
            size_band = _classify_size_band(pct_of_assigned)
            reliability_flag = _classify_reliability(n_customers)
            limitations = (
                f"WORKING_ANALYTICAL_SIZE_BAND thresholds "
                f"({DOMINANT_PCT}/{LARGE_PCT}/{MEDIUM_PCT}/{SMALL_PCT}%) "
                f"PENDING_REVIEW. n<{N_RELIABILITY_THRESHOLD} chỉ là reliability warning."
            )

        results.append(
            SizeResult(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                cluster_id=cluster_id,
                cluster_label=cluster_label,
                n_customers=n_customers,
                pct_of_assigned=pct_of_assigned,
                pct_of_total=pct_of_total,
                relative_size_ratio=rel_ratio,
                size_band=size_band,
                statistical_reliability_flag=reliability_flag,
                is_noise=is_noise,
                evidence_source="cp01_cluster_size_table.csv",
                limitations=limitations,
            )
        )

    return results


def size_results_to_rows(results: Iterable[SizeResult]) -> list[dict]:
    """Convert results thành dict rows để ghi CSV."""
    rows: list[dict] = []
    for r in results:
        rows.append(
            {
                "unit_id": r.unit_id,
                "algorithm": r.algorithm,
                "source_experiment": r.source_experiment,
                "cluster_id": r.cluster_id,
                "cluster_label": r.cluster_label,
                "n_customers": r.n_customers,
                "pct_of_assigned": r.pct_of_assigned,
                "pct_of_total": r.pct_of_total,
                "relative_size_ratio": r.relative_size_ratio,
                "size_band": r.size_band,
                "statistical_reliability_flag": r.statistical_reliability_flag,
                "is_noise": r.is_noise,
                "evidence_source": r.evidence_source,
                "limitations": r.limitations,
            }
        )
    return rows
