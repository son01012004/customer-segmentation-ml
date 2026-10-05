"""CP-05 interpretability evaluation (per plan §6).

Đánh giá khả năng diễn giải của segment dựa trên CP-04 naming
framework. KHÔNG đặt tên mới. KHÔNG ranking. KHÔNG composite score.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
)

# Complexity heuristic — segments with > 6 features HIGHER/LOWER
# có thể khó diễn giải ngắn gọn.
COMPLEXITY_THRESHOLD = 6

# Forbidden tokens bổ sung cho CP-05.
CP05_FORBIDDEN_INTERPRETATION_TOKENS = (
    "best segment",
    "best cluster",
    "best customer",
    "promising customer",
    "declining customer",
    "engagement",
    "loyalty indicator",
    "purchase probability",
    "high-value customer",
    "tier 1 customer",
    "tier 2 customer",
    "marketing recommendation",
    "campaign recommendation",
    "churn risk",
    "retention risk",
    "customer lifetime value",
    "CLV",
)

# Kế thừa từ CP-04.
CP04_FORBIDDEN_INTERPRETATION_TOKENS = (
    "champion",
    "vip customer",
    "at-risk customer",
    "low-engagement customer",
    "loyal customer",
    "outreach campaign",
    "remarketing",
    "campaign targeting",
)

ALL_FORBIDDEN_TOKENS = CP04_FORBIDDEN_INTERPRETATION_TOKENS + CP05_FORBIDDEN_INTERPRETATION_TOKENS


@dataclass(frozen=True)
class InterpretabilityResult:
    """Per-segment interpretability result."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    naming_status: str  # từ CP-04
    segment_name: str
    n_modifiers: int
    n_features_higher_or_lower: int
    n_features_comparable: int
    n_features_na: int
    rationale_grounded: bool
    modifier_grounded: bool
    complexity_flag: bool
    over_inference_markers: bool
    interpretability_status: str
    supporting_evidence: str
    limitations: str
    is_noise: bool


def _has_forbidden_token(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(tok.lower() in lower for tok in ALL_FORBIDDEN_TOKENS)


def _rationale_grounded(rationale: str, behavioral_df: pd.DataFrame, cluster_id: int) -> bool:
    """Rationale grounded nếu reference ít nhất 1 feature direction.

    Heuristic: rationale phải reference ≥1 RAW feature name hoặc
    direction word (cao/thấp/HIGHER/LOWER/COMPARABLE/...).
    """
    if not rationale or not isinstance(rationale, str):
        return False
    # Check for any feature name from behavioral table.
    if behavioral_df is not None and not behavioral_df.empty:
        cluster_features = behavioral_df[behavioral_df["cluster_id"] == cluster_id]
        feature_names = set(cluster_features["feature"].astype(str).unique())
        for fname in feature_names:
            if fname.lower() in rationale.lower():
                return True

    direction_keywords = (
        "cao",
        "thấp",
        "higher",
        "lower",
        "comparable",
        "tương đương",
        "quan sát",
        "direction",
    )
    lower = rationale.lower()
    return any(kw in lower for kw in direction_keywords)


def evaluate_interpretability(
    bundle: Cp04EvidenceBundle,
) -> list[InterpretabilityResult]:
    """Evaluate interpretability cho một analysis unit.

    Parameters
    ----------
    bundle : Cp04EvidenceBundle

    Returns
    -------
    list[InterpretabilityResult]
        Một entry per cluster (including noise bucket).
    """
    unit: Cp05AnalysisUnit = bundle.unit
    naming_df = bundle.naming_df
    size_df = bundle.size_df
    behavioral_df = bundle.behavioral_df

    # Default rows cho noise + clusters không có naming.
    out: list[InterpretabilityResult] = []

    # Build cluster id -> naming lookup.
    naming_lookup: dict[int, dict] = {}
    if naming_df is not None and not naming_df.empty:
        for _, row in naming_df.iterrows():
            cid = int(row["cluster_id"])
            naming_lookup[cid] = {
                "naming_status": str(row.get("naming_status", "NOT_AVAILABLE")),
                "segment_name": str(row.get("segment_name", "")),
                "modifiers": str(row.get("modifiers", "")),
                "naming_rationale": str(row.get("naming_rationale", "")),
                "n_modifiers": int(row.get("n_modifiers", 0)),
            }

    # Build behavioral direction counts per cluster.
    direction_counts: dict[int, dict[str, int]] = {}
    if behavioral_df is not None and not behavioral_df.empty:
        for cid, group in behavioral_df.groupby("cluster_id"):
            counts = {"HIGHER": 0, "LOWER": 0, "COMPARABLE": 0, "NA": 0}
            for d in group["direction"]:
                d = str(d)
                if d in counts:
                    counts[d] += 1
                else:
                    counts["NA"] += 1
            direction_counts[int(cid)] = counts

    for _, row in size_df.iterrows():
        cid = int(row["cluster_id"])
        is_noise = cid == -1
        cluster_label = "noise (-1)" if is_noise else f"C{cid}"

        if is_noise:
            out.append(
                InterpretabilityResult(
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    cluster_id=cid,
                    cluster_label=cluster_label,
                    naming_status="NOISE",
                    segment_name="DBSCAN noise",
                    n_modifiers=0,
                    n_features_higher_or_lower=0,
                    n_features_comparable=0,
                    n_features_na=0,
                    rationale_grounded=False,
                    modifier_grounded=False,
                    complexity_flag=False,
                    over_inference_markers=False,
                    interpretability_status="NOT_APPLICABLE",
                    supporting_evidence="",
                    limitations="DBSCAN noise KHÔNG phải Customer Segment.",
                    is_noise=True,
                )
            )
            continue

        info = naming_lookup.get(cid)
        if info is None:
            # Cluster không có naming trong CP-04 (ví dụ DBSCAN small
            # cluster không tạo naming row).
            out.append(
                InterpretabilityResult(
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    cluster_id=cid,
                    cluster_label=cluster_label,
                    naming_status="NOT_AVAILABLE",
                    segment_name="",
                    n_modifiers=0,
                    n_features_higher_or_lower=sum(
                        direction_counts.get(cid, {"HIGHER": 0, "LOWER": 0}).values()
                    ),
                    n_features_comparable=direction_counts.get(cid, {"COMPARABLE": 0}).get(
                        "COMPARABLE", 0
                    ),
                    n_features_na=direction_counts.get(cid, {"NA": 0}).get("NA", 0),
                    rationale_grounded=False,
                    modifier_grounded=False,
                    complexity_flag=False,
                    over_inference_markers=False,
                    interpretability_status="NOT_AVAILABLE",
                    supporting_evidence="",
                    limitations="Cluster không có CP-04 naming row.",
                    is_noise=False,
                )
            )
            continue

        naming_status = info["naming_status"]
        segment_name = info["segment_name"]
        modifiers = info["modifiers"]
        rationale = info["naming_rationale"]
        n_modifiers = info["n_modifiers"]

        direction = direction_counts.get(cid, {"HIGHER": 0, "LOWER": 0, "COMPARABLE": 0, "NA": 0})
        n_higher_or_lower = direction["HIGHER"] + direction["LOWER"]
        n_comparable = direction["COMPARABLE"]
        n_na = direction["NA"]

        rationale_grounded = _rationale_grounded(rationale, behavioral_df, cid)
        # Modifier groundedness requires HIGH_DIFFERENCE_OBSERVED on the
        # modifier feature — simplified check: n_modifiers == 0 →
        # trivially grounded.
        modifier_grounded = n_modifiers == 0 or rationale_grounded

        complexity_flag = n_higher_or_lower > COMPLEXITY_THRESHOLD

        over_inference = (
            _has_forbidden_token(segment_name)
            or _has_forbidden_token(rationale)
            or _has_forbidden_token(modifiers)
        )

        if naming_status == "COMPARATIVE":
            status = "COMPARATIVE"
        elif naming_status == "NOT_AVAILABLE":
            status = "NOT_AVAILABLE"
        elif over_inference or not rationale_grounded:
            status = "LIMITED_INTERPRETABILITY"
        elif complexity_flag:
            status = "PARTIALLY_INTERPRETABLE"
        elif rationale_grounded and modifier_grounded:
            status = "INTERPRETABLE"
        else:
            status = "PARTIALLY_INTERPRETABLE"

        if status in ("INTERPRETABLE", "PARTIALLY_INTERPRETABLE"):
            supporting = f"name={segment_name!r}; rationale_grounded=True"
        elif status == "LIMITED_INTERPRETABILITY":
            supporting = (
                f"name={segment_name!r}; rationale_grounded={rationale_grounded}; "
                f"over_inference_markers={over_inference}"
            )
        else:
            supporting = ""

        if status in ("INTERPRETABLE", "PARTIALLY_INTERPRETABLE"):
            limitations = (
                "Naming framework giữ theo CP-04. Heuristic groundedness " "KHÔNG research-grade."
            )
        elif status == "LIMITED_INTERPRETABILITY":
            limitations = (
                "Rationale thiếu feature reference HOẶC có forbidden token. "
                "CP-05 không tự sửa segment name."
            )
        else:
            limitations = ""

        out.append(
            InterpretabilityResult(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                cluster_id=cid,
                cluster_label=cluster_label,
                naming_status=naming_status,
                segment_name=segment_name,
                n_modifiers=n_modifiers,
                n_features_higher_or_lower=n_higher_or_lower,
                n_features_comparable=n_comparable,
                n_features_na=n_na,
                rationale_grounded=rationale_grounded,
                modifier_grounded=modifier_grounded,
                complexity_flag=complexity_flag,
                over_inference_markers=over_inference,
                interpretability_status=status,
                supporting_evidence=supporting,
                limitations=limitations,
                is_noise=False,
            )
        )

    return out


def interpretability_results_to_rows(
    results: Iterable[InterpretabilityResult],
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
                "naming_status": r.naming_status,
                "segment_name": r.segment_name,
                "n_modifiers": r.n_modifiers,
                "n_features_higher_or_lower": r.n_features_higher_or_lower,
                "n_features_comparable": r.n_features_comparable,
                "n_features_na": r.n_features_na,
                "rationale_grounded": r.rationale_grounded,
                "modifier_grounded": r.modifier_grounded,
                "complexity_flag": r.complexity_flag,
                "over_inference_markers": r.over_inference_markers,
                "interpretability_status": r.interpretability_status,
                "supporting_evidence": r.supporting_evidence,
                "limitations": r.limitations,
            }
        )
    return rows
