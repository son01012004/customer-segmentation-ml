"""CP-05 behavioral consistency evaluation (per plan §7).

Kiểm tra consistency giữa RFM tiers, behavioural modifiers, và
CP-02 direction profile. KHÔNG tự sửa segment name.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
)

# Mapping per CP-04 §4.1.
RFM_TIER_GROUNDING = {
    "Recency": {
        "Recent": "LOWER",  # Recency thấp hơn population → mua gần đây
        "Older": "HIGHER",
        "Mixed": "COMPARABLE",
    },
    "Frequency": {
        "Frequent": "HIGHER",
        "Occasional": "LOWER",
        "Mixed": "COMPARABLE",
    },
    "Monetary": {
        "HighValue": "HIGHER",
        "LowValue": "LOWER",
        "Mixed": "COMPARABLE",
    },
}

# Modifier rules per CP-04 §4.2.
MODIFIER_GROUNDING = {
    "LongTenured": {
        "feature": "TenureDays",
        "required_direction": "HIGHER",
    },
    "IrregularCadence": {
        "feature": "PurchaseIntervalStd",
        "required_direction": "HIGHER",
    },
    "Bulk": {
        "feature": "TotalQuantity",
        "required_direction": "HIGHER",
        "additional": [("Monetary", "HIGHER")],
    },
    "Active": {
        "feature": "ActiveDays",
        "required_direction": "HIGHER",
        "frequency_must_differ": True,
    },
}


@dataclass(frozen=True)
class ConsistencyResult:
    """Per-segment consistency evaluation result."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    naming_status: str
    segment_name: str
    recency_tier: str
    frequency_tier: str
    monetary_tier: str
    modifiers: str
    recency_tier_grounded: bool
    frequency_tier_grounded: bool
    monetary_tier_grounded: bool
    modifier_longtenured_grounded: bool
    modifier_irregularcadence_grounded: bool
    modifier_bulk_grounded: bool
    modifier_active_grounded: bool
    n_inconsistencies: int
    cross_check_flags: str  # semicolon-separated
    consistency_status: str
    supporting_evidence: str
    limitations: str
    is_noise: bool


def _parse_tier_from_name(segment_name: str, tier_word: str) -> str:
    """Tìm RFM tier word trong segment name."""
    if not segment_name:
        return "Mixed"
    words = segment_name.split()
    for w in words:
        if tier_word in w:
            return w
    return "Mixed"


def _direction_lookup(
    behavioral_df: pd.DataFrame | None,
    cluster_id: int,
    feature: str,
) -> str | None:
    if behavioral_df is None or behavioral_df.empty:
        return None
    rows = behavioral_df[
        (behavioral_df["cluster_id"] == cluster_id) & (behavioral_df["feature"] == feature)
    ]
    if rows.empty:
        return None
    return str(rows.iloc[0]["direction"])


def _parse_modifiers(modifiers: str) -> list[str]:
    if not modifiers or not isinstance(modifiers, str):
        return []
    return [m.strip() for m in modifiers.split(";") if m.strip()]


def evaluate_consistency(
    bundle: Cp04EvidenceBundle,
) -> list[ConsistencyResult]:
    """Evaluate consistency cho một analysis unit."""
    unit: Cp05AnalysisUnit = bundle.unit
    naming_df = bundle.naming_df
    behavioral_df = bundle.behavioral_df
    size_df = bundle.size_df

    if naming_df is None or naming_df.empty:
        naming_df = pd.DataFrame(
            columns=["cluster_id", "naming_status", "segment_name", "modifiers"]
        )

    # Build lookup.
    naming_lookup: dict[int, dict] = {}
    for _, row in naming_df.iterrows():
        cid = int(row["cluster_id"])
        naming_lookup[cid] = {
            "naming_status": str(row.get("naming_status", "NOT_AVAILABLE")),
            "segment_name": str(row.get("segment_name", "")),
            "modifiers": str(row.get("modifiers", "")),
        }

    out: list[ConsistencyResult] = []

    for _, row in size_df.iterrows():
        cid = int(row["cluster_id"])
        is_noise = cid == -1
        cluster_label = "noise (-1)" if is_noise else f"C{cid}"

        if is_noise:
            out.append(
                ConsistencyResult(
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    cluster_id=cid,
                    cluster_label=cluster_label,
                    naming_status="NOISE",
                    segment_name="",
                    recency_tier="",
                    frequency_tier="",
                    monetary_tier="",
                    modifiers="",
                    recency_tier_grounded=False,
                    frequency_tier_grounded=False,
                    monetary_tier_grounded=False,
                    modifier_longtenured_grounded=False,
                    modifier_irregularcadence_grounded=False,
                    modifier_bulk_grounded=False,
                    modifier_active_grounded=False,
                    n_inconsistencies=0,
                    cross_check_flags="",
                    consistency_status="NOT_APPLICABLE",
                    supporting_evidence="",
                    limitations="DBSCAN noise KHÔNG phải Customer Segment.",
                    is_noise=True,
                )
            )
            continue

        info = naming_lookup.get(cid)
        if info is None:
            out.append(
                ConsistencyResult(
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    cluster_id=cid,
                    cluster_label=cluster_label,
                    naming_status="NOT_AVAILABLE",
                    segment_name="",
                    recency_tier="",
                    frequency_tier="",
                    monetary_tier="",
                    modifiers="",
                    recency_tier_grounded=False,
                    frequency_tier_grounded=False,
                    monetary_tier_grounded=False,
                    modifier_longtenured_grounded=False,
                    modifier_irregularcadence_grounded=False,
                    modifier_bulk_grounded=False,
                    modifier_active_grounded=False,
                    n_inconsistencies=0,
                    cross_check_flags="",
                    consistency_status="NOT_APPLICABLE",
                    supporting_evidence="",
                    limitations="Cluster không có CP-04 naming row.",
                    is_noise=False,
                )
            )
            continue

        naming_status = info["naming_status"]
        segment_name = info["segment_name"]
        modifiers = info["modifiers"]

        if naming_status != "NAMED":
            out.append(
                ConsistencyResult(
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    cluster_id=cid,
                    cluster_label=cluster_label,
                    naming_status=naming_status,
                    segment_name=segment_name,
                    recency_tier="",
                    frequency_tier="",
                    monetary_tier="",
                    modifiers=modifiers,
                    recency_tier_grounded=False,
                    frequency_tier_grounded=False,
                    monetary_tier_grounded=False,
                    modifier_longtenured_grounded=False,
                    modifier_irregularcadence_grounded=False,
                    modifier_bulk_grounded=False,
                    modifier_active_grounded=False,
                    n_inconsistencies=0,
                    cross_check_flags="",
                    consistency_status="NOT_APPLICABLE",
                    supporting_evidence="",
                    limitations=f"naming_status={naming_status}; CP-05 KHÔNG đánh giá consistency.",
                    is_noise=False,
                )
            )
            continue

        # Parse tiers from name (best-effort).
        recency_tier = _parse_tier_from_name(segment_name, "Recent")
        if recency_tier == "Mixed":
            recency_tier = _parse_tier_from_name(segment_name, "Older")
        frequency_tier = _parse_tier_from_name(segment_name, "Frequent")
        if frequency_tier == "Mixed":
            frequency_tier = _parse_tier_from_name(segment_name, "Occasional")
        monetary_tier = _parse_tier_from_name(segment_name, "HighValue")
        if monetary_tier == "Mixed":
            monetary_tier = _parse_tier_from_name(segment_name, "LowValue")

        recency_dir = _direction_lookup(behavioral_df, cid, "Recency")
        frequency_dir = _direction_lookup(behavioral_df, cid, "Frequency")
        monetary_dir = _direction_lookup(behavioral_df, cid, "Monetary")

        recency_grounded = (
            recency_tier == "Mixed"
            or recency_dir is None
            or recency_dir == RFM_TIER_GROUNDING["Recency"].get(recency_tier, "COMPARABLE")
            or recency_dir == "ZERO_REFERENCE"
        )
        frequency_grounded = (
            frequency_tier == "Mixed"
            or frequency_dir is None
            or frequency_dir == RFM_TIER_GROUNDING["Frequency"].get(frequency_tier, "COMPARABLE")
            or frequency_dir == "ZERO_REFERENCE"
        )
        monetary_grounded = (
            monetary_tier == "Mixed"
            or monetary_dir is None
            or monetary_dir == RFM_TIER_GROUNDING["Monetary"].get(monetary_tier, "COMPARABLE")
            or monetary_dir == "ZERO_REFERENCE"
        )

        # Modifier grounding.
        modifier_list = _parse_modifiers(modifiers)
        m_longtenured = True
        m_irregular = True
        m_bulk = True
        m_active = True
        unresolved = 0

        if "LongTenured" in modifier_list:
            tenure_dir = _direction_lookup(behavioral_df, cid, "TenureDays")
            if tenure_dir == "NA":
                m_longtenured = False  # UNRESOLVED
                unresolved += 1
            else:
                m_longtenured = tenure_dir == "HIGHER"
        if "IrregularCadence" in modifier_list:
            pstd_dir = _direction_lookup(behavioral_df, cid, "PurchaseIntervalStd")
            if pstd_dir == "NA":
                m_irregular = False
                unresolved += 1
            else:
                m_irregular = pstd_dir == "HIGHER"
        if "Bulk" in modifier_list:
            qty_dir = _direction_lookup(behavioral_df, cid, "TotalQuantity")
            m_dir = _direction_lookup(behavioral_df, cid, "Monetary")
            if qty_dir == "NA" or m_dir == "NA":
                m_bulk = False
                unresolved += 1
            else:
                m_bulk = qty_dir == "HIGHER" and m_dir == "HIGHER"
        if "Active" in modifier_list:
            active_dir = _direction_lookup(behavioral_df, cid, "ActiveDays")
            if active_dir == "NA":
                m_active = False
                unresolved += 1
            else:
                m_active = active_dir == "HIGHER" and (
                    frequency_dir is None or frequency_dir != "HIGHER"
                )

        n_inconsistencies = sum(
            1
            for grounded in (
                recency_grounded,
                frequency_grounded,
                monetary_grounded,
                m_longtenured,
                m_irregular,
                m_bulk,
                m_active,
            )
            if not grounded
        )

        # Cross-check flag.
        cross_flags: list[str] = []
        if monetary_tier == "HighValue" and recency_tier == "Recent":
            tenure_dir = _direction_lookup(behavioral_df, cid, "TenureDays")
            if tenure_dir == "LOWER":
                cross_flags.append("HighValue+Recent+LowTenure unusual")

        # Decide status.
        rfm_grounded = recency_grounded and frequency_grounded and monetary_grounded
        rfm_unresolved = (
            recency_dir in ("NA", None)
            or frequency_dir in ("NA", None)
            or monetary_dir in ("NA", None)
        )

        if rfm_unresolved and not rfm_grounded:
            status = "NOT_ASSESSABLE"
        elif not rfm_grounded:
            status = "RFM_INCONSISTENT"
        elif (
            any(not m for m in (m_longtenured, m_irregular, m_bulk, m_active) if m is False)
            and not any(m is False for m in (m_longtenured, m_irregular, m_bulk, m_active))
            or all(m for m in (m_longtenured, m_irregular, m_bulk, m_active))
        ):
            status = "CONSISTENT"
        elif unresolved > 0:
            status = "PARTIALLY_CONSISTENT"
        else:
            status = "MODIFIER_INCONSISTENT"

        supporting_parts: list[str] = []
        if recency_dir:
            supporting_parts.append(f"Recency:{recency_dir}")
        if frequency_dir:
            supporting_parts.append(f"Frequency:{frequency_dir}")
        if monetary_dir:
            supporting_parts.append(f"Monetary:{monetary_dir}")
        supporting = "; ".join(supporting_parts)

        limitations = (
            "Tier parser heuristic (best-effort). CP-05 KHÔNG tự sửa " "segment name — chỉ flag."
        )

        out.append(
            ConsistencyResult(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                cluster_id=cid,
                cluster_label=cluster_label,
                naming_status=naming_status,
                segment_name=segment_name,
                recency_tier=recency_tier,
                frequency_tier=frequency_tier,
                monetary_tier=monetary_tier,
                modifiers=modifiers,
                recency_tier_grounded=recency_grounded,
                frequency_tier_grounded=frequency_grounded,
                monetary_tier_grounded=monetary_grounded,
                modifier_longtenured_grounded=m_longtenured,
                modifier_irregularcadence_grounded=m_irregular,
                modifier_bulk_grounded=m_bulk,
                modifier_active_grounded=m_active,
                n_inconsistencies=n_inconsistencies,
                cross_check_flags=";".join(cross_flags),
                consistency_status=status,
                supporting_evidence=supporting,
                limitations=limitations,
                is_noise=False,
            )
        )

    return out


def consistency_results_to_rows(
    results: Iterable[ConsistencyResult],
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
                "recency_tier": r.recency_tier,
                "frequency_tier": r.frequency_tier,
                "monetary_tier": r.monetary_tier,
                "modifiers": r.modifiers,
                "recency_tier_grounded": r.recency_tier_grounded,
                "frequency_tier_grounded": r.frequency_tier_grounded,
                "monetary_tier_grounded": r.monetary_tier_grounded,
                "modifier_longtenured_grounded": r.modifier_longtenured_grounded,
                "modifier_irregularcadence_grounded": r.modifier_irregularcadence_grounded,
                "modifier_bulk_grounded": r.modifier_bulk_grounded,
                "modifier_active_grounded": r.modifier_active_grounded,
                "n_inconsistencies": r.n_inconsistencies,
                "cross_check_flags": r.cross_check_flags,
                "consistency_status": r.consistency_status,
                "supporting_evidence": r.supporting_evidence,
                "limitations": r.limitations,
            }
        )
    return rows
