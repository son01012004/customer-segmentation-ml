"""CP-05 distinctiveness evaluation (per plan §5).

Phân loại segment theo số lượng distinguishing features mà segment
đóng góp vào. KHÔNG composite scoring. KHÔNG ranking.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
)

# Inherited thresholds từ CP-03 WORKING_ANALYTICAL_THRESHOLD.
# KHÔNG threshold mới ngoài CP-03.
HIGH_DIFFERENCE_EFFECT_PCT = 50.0  # CP-03 §4.5
MODERATE_OVERLAP_MEAN = 0.5  # CP-03 §4.5
MIN_ASSESSABLE_CLUSTERS = 2  # CP-03 §4.5

# Redundant pairs per FE-06 (Pearson = 1.0).
# CP-05 chỉ tính 1 evidence độc lập.
REDUNDANT_PAIRS: list[tuple[str, str]] = [
    ("AverageQuantity", "BasketSize"),
    ("CancellationRate", "ReturnRate"),
]


@dataclass(frozen=True)
class DistinctivenessResult:
    """Per-segment distinctiveness result."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    n_features_assessable: int
    n_distinguishing_features: int
    n_high_overlap_features: int
    distinctiveness_status: str
    supporting_features: str  # semicolon-separated
    rationale: str
    evidence_source: str


def _is_redundant_pair(f1: str, f2: str) -> bool:
    return any((f1 == a and f2 == b) or (f1 == b and f2 == a) for a, b in REDUNDANT_PAIRS)


def evaluate_distinctiveness(
    bundle: Cp04EvidenceBundle,
) -> list[DistinctivenessResult]:
    """Evaluate distinctiveness cho một analysis unit.

    Parameters
    ----------
    bundle : Cp04EvidenceBundle

    Returns
    -------
    list[DistinctivenessResult]
        Một entry per non-noise cluster.
    """
    unit: Cp05AnalysisUnit = bundle.unit
    comparison_df = bundle.comparison_df
    distinguishing_df = bundle.distinguishing_df

    if comparison_df is None or comparison_df.empty:
        return []

    # Index distinguishing classifications per feature.
    feature_class: dict[str, str] = {}
    feature_effect_range_rel_pct: dict[str, float] = {}
    feature_iqr_overlap_mean: dict[str, float] = {}
    if distinguishing_df is not None and not distinguishing_df.empty:
        for _, drow in distinguishing_df.iterrows():
            feature = str(drow["feature"])
            feature_class[feature] = str(drow["classification"])
            feature_effect_range_rel_pct[feature] = float(
                drow.get("effect_range_rel_pct", float("nan"))
            )
            feature_iqr_overlap_mean[feature] = float(drow.get("iqr_overlap_mean", float("nan")))

    # Group by cluster_id.
    non_noise = comparison_df[comparison_df["cluster_id"] != -1].copy()
    out: list[DistinctivenessResult] = []

    # Build a redundancy-aware feature list per cluster.
    cluster_features: dict[int, list[str]] = {}
    for cid, group in non_noise.groupby("cluster_id"):
        features = list(group["feature"].astype(str).unique())
        deduped: list[str] = []
        for f in features:
            is_dup = False
            for existing in deduped:
                if _is_redundant_pair(existing, f):
                    is_dup = True
                    break
            if not is_dup:
                deduped.append(f)
        cluster_features[int(cid)] = deduped

    # For each cluster, count distinguishing features.
    for cid in sorted(cluster_features.keys()):
        features = cluster_features[cid]
        n_assessable = 0
        n_distinguishing = 0
        n_high_overlap = 0
        supporting: list[str] = []

        for feature in features:
            classification = feature_class.get(feature, "NOT_ASSESSABLE")
            effect_rel = feature_effect_range_rel_pct.get(feature, float("nan"))
            iqr_mean = feature_iqr_overlap_mean.get(feature, float("nan"))

            if classification == "NOT_ASSESSABLE":
                continue

            n_assessable += 1

            if (
                classification == "HIGH_DIFFERENCE_OBSERVED"
                and pd.notna(effect_rel)
                and effect_rel >= HIGH_DIFFERENCE_EFFECT_PCT
                and pd.notna(iqr_mean)
                and iqr_mean <= MODERATE_OVERLAP_MEAN
            ):
                n_distinguishing += 1
                supporting.append(feature)
            elif classification == "HIGH_OVERLAP":
                n_high_overlap += 1

        if n_assessable < MIN_ASSESSABLE_CLUSTERS:
            status = "NOT_ASSESSABLE"
            rationale = (
                f"n_features_assessable={n_assessable} < "
                f"{MIN_ASSESSABLE_CLUSTERS}; not enough evidence."
            )
        elif n_distinguishing >= 2:
            status = "DISTINCT"
            rationale = (
                f"Segment contributes to distinction in {n_distinguishing} "
                f"features: {'; '.join(supporting)}."
            )
        elif n_distinguishing == 1:
            status = "LIMITED_DIFFERENTIVENESS"
            rationale = (
                f"Segment contributes to distinction in 1 feature: "
                f"{supporting[0] if supporting else 'N/A'}."
            )
        elif n_high_overlap >= 1:
            status = "NOT_DISTINCT"
            rationale = (
                f"No HIGH_DIFFERENCE feature; {n_high_overlap} features in "
                f"HIGH_OVERLAP category."
            )
        else:
            status = "LIMITED_DIFFERENTIVENESS"
            rationale = "Mixed evidence; insufficient HIGH_DIFFERENCE features."

        out.append(
            DistinctivenessResult(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                cluster_id=int(cid),
                cluster_label=f"C{int(cid)}",
                n_features_assessable=n_assessable,
                n_distinguishing_features=n_distinguishing,
                n_high_overlap_features=n_high_overlap,
                distinctiveness_status=status,
                supporting_features=";".join(supporting),
                rationale=rationale,
                evidence_source="cp03_distinguishing_features.csv+cp03_segment_comparison_matrix.csv",
            )
        )

    return out


def distinctiveness_results_to_rows(
    results: Iterable[DistinctivenessResult],
) -> list[dict]:
    rows: list[dict] = []
    for r in results:
        rows.append(
            {
                "unit_id": r.unit_id,
                "algorithm": r.algorithm,
                "source_experiment": r.source_experiment,
                "cluster_id": r.cluster_id,
                "cluster_label": r.cluster_label,
                "n_features_assessable": r.n_features_assessable,
                "n_distinguishing_features": r.n_distinguishing_features,
                "n_high_overlap_features": r.n_high_overlap_features,
                "distinctiveness_status": r.distinctiveness_status,
                "supporting_features": r.supporting_features,
                "rationale": r.rationale,
                "evidence_source": r.evidence_source,
            }
        )
    return rows
