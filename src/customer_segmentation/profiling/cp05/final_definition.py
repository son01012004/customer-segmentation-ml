"""CP-05 final segment definition (per plan §11 + task brief §6).

Aggregates 6 evaluation axes + CP-01 → CP-04 evidence per segment.
KHÔNG chọn segment tốt nhất. KHÔNG ranking.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from customer_segmentation.profiling.cp05.business_relevance import (
    BusinessRelevanceResult,
)
from customer_segmentation.profiling.cp05.consistency import ConsistencyResult
from customer_segmentation.profiling.cp05.distinctiveness import (
    DistinctivenessResult,
)
from customer_segmentation.profiling.cp05.interpretability import (
    InterpretabilityResult,
)
from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
)
from customer_segmentation.profiling.cp05.size_evaluation import SizeResult
from customer_segmentation.profiling.cp05.stability import StabilityResult

INTERPRETATION_READINESS_VALUES = (
    "READY",
    "CONDITIONAL",
    "LIMITED",
    "NOT_ASSESSABLE",
)


@dataclass(frozen=True)
class FinalSegmentDefinition:
    """Per-segment final definition."""

    segment_id: str
    unit_id: str
    algorithm: str
    source_experiment: str
    configuration_status: str
    labels_persisted: bool
    cluster_id: int
    cluster_label: str
    naming_status: str
    segment_name: str
    modifiers: str
    naming_rationale: str
    n_customers: int
    pct_of_assigned: float
    pct_of_total: float
    relative_size_ratio: float
    size_band: str
    statistical_reliability_flag: str
    recency_tier: str
    frequency_tier: str
    monetary_tier: str
    behavioural_modifiers_summary: str
    behavioural_profile_text: str
    n_distinguishing_features: int
    n_features_assessable: int
    distinctiveness_status: str
    distinctiveness_supporting_features: str
    interpretability_status: str
    interpretability_note: str
    consistency_status: str
    n_inconsistencies: int
    consistency_note: str
    reproducibility_status: str
    seed_stability_status: str
    perturbation_status: str
    stability_status: str
    stability_note: str
    n_features_supported_direction: int
    business_relevance_status: str
    business_interpretation_text: str
    evidence_sources: str
    inconsistencies_across_cps: str
    limitations: str
    is_interpretation_ready: bool
    interpretation_readiness: str
    is_noise: bool


def _is_interpretation_ready(
    *,
    distinctiveness_status: str,
    interpretability_status: str,
    consistency_status: str,
    business_relevance_status: str,
    is_noise: bool,
    labels_persisted: bool,
) -> bool:
    """Deterministic rule (NOT a winner/best claim).

    Segment được coi là có đủ evidence tối thiểu để xây dựng
    interpretation/profile khi:
    - Có labels_persisted (EXP-01 only).
    - KHÔNG phải noise.
    - Có distinctiveness_status ∈ {DISTINCT, LIMITED_DIFFERENTIVENESS}.
    - Có interpretability_status ∈ {HIGH_INTERPRETABILITY,
      INTERPRETABLE, PARTIALLY_INTERPRETABLE}.
    - Có consistency_status ∈ {CONSISTENT, PARTIALLY_CONSISTENT}.
    - Có business_relevance_status ∈ {SUPPORTED, LIMITED}.
    """
    if is_noise or not labels_persisted:
        return False
    if distinctiveness_status not in ("DISTINCT", "LIMITED_DIFFERENTIVENESS"):
        return False
    if interpretability_status not in (
        "HIGH_INTERPRETABILITY",
        "INTERPRETABLE",
        "PARTIALLY_INTERPRETABLE",
    ):
        return False
    if consistency_status not in ("CONSISTENT", "PARTIALLY_CONSISTENT"):
        return False
    return business_relevance_status in ("SUPPORTED", "LIMITED")


def _interpretation_readiness(
    *,
    is_ready: bool,
    size_band: str,
) -> str:
    """Map is_interpretation_ready + size_band → readiness value.

    KHÔNG dùng để ranking segment.
    """
    if not is_ready:
        return "NOT_ASSESSABLE"
    if size_band in ("DOMINANT", "LARGE"):
        return "READY"
    if size_band in ("MEDIUM", "SMALL"):
        return "CONDITIONAL"
    if size_band == "VERY_SMALL":
        return "LIMITED"
    return "NOT_ASSESSABLE"


def _index_by_cluster(results: Iterable) -> dict[int, object]:
    out: dict[int, object] = {}
    for r in results:
        out[r.cluster_id] = r
    return out


def build_final_segment_definition(
    unit: Cp05AnalysisUnit,
    bundle: Cp04EvidenceBundle,
    *,
    distinctiveness_results: list[DistinctivenessResult],
    interpretability_results: list[InterpretabilityResult],
    consistency_results: list[ConsistencyResult],
    size_results: list[SizeResult],
    stability_results: list[StabilityResult],
    business_relevance_results: list[BusinessRelevanceResult],
) -> list[FinalSegmentDefinition]:
    """Build Final Segment Definition rows cho một analysis unit."""
    # Index everything by cluster_id.
    d_idx = _index_by_cluster(distinctiveness_results)
    i_idx = _index_by_cluster(interpretability_results)
    c_idx = _index_by_cluster(consistency_results)
    s_idx = _index_by_cluster(size_results)
    st_idx = _index_by_cluster(stability_results)
    b_idx = _index_by_cluster(business_relevance_results)

    # Naming lookup.
    name_lookup: dict[int, dict] = {}
    if bundle.naming_df is not None and not bundle.naming_df.empty:
        for _, row in bundle.naming_df.iterrows():
            cid = int(row["cluster_id"])
            name_lookup[cid] = {
                "naming_status": str(row.get("naming_status", "")),
                "modifiers": str(row.get("modifiers", "")),
                "naming_rationale": str(row.get("naming_rationale", "")),
            }

    # Profile lookup.
    profile_lookup: dict[int, dict] = {}
    if bundle.profile_df is not None and not bundle.profile_df.empty:
        for _, row in bundle.profile_df.iterrows():
            cid = int(row["cluster_id"])
            profile_lookup[cid] = {
                "recency_tier": str(row.get("recency_tier", "")),
                "frequency_tier": str(row.get("frequency_tier", "")),
                "monetary_tier": str(row.get("monetary_tier", "")),
                "behavioural_modifiers_summary": str(row.get("behavioural_modifiers_summary", "")),
                "behavioural_profile_text": str(row.get("behavioural_profile_text", "")),
            }

    out: list[FinalSegmentDefinition] = []
    for _, row in bundle.size_df.iterrows():
        cid = int(row["cluster_id"])
        is_noise = cid == -1
        cluster_label = "noise (-1)" if is_noise else f"C{cid}"
        segment_id = f"{unit.unit_id}__{cluster_label}"

        name_info = name_lookup.get(cid, {})
        profile_info = profile_lookup.get(cid, {})

        d = d_idx.get(cid)
        i = i_idx.get(cid)
        c = c_idx.get(cid)
        s = s_idx.get(cid)
        st = st_idx.get(cid)
        b = b_idx.get(cid)

        # Fill defaults for noise.
        if is_noise:
            out.append(
                FinalSegmentDefinition(
                    segment_id=segment_id,
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    configuration_status=unit.configuration_status,
                    labels_persisted=unit.labels_persisted,
                    cluster_id=cid,
                    cluster_label=cluster_label,
                    naming_status="NOISE",
                    segment_name="DBSCAN noise",
                    modifiers="",
                    naming_rationale="",
                    n_customers=int(s.n_customers) if s else int(row["customer_count"]),
                    pct_of_assigned=(
                        float(s.pct_of_assigned) if s else float(row.get("pct_of_assigned", 0.0))
                    ),
                    pct_of_total=(
                        float(s.pct_of_total) if s else float(row.get("pct_of_total", 0.0))
                    ),
                    relative_size_ratio=float(s.relative_size_ratio) if s else 0.0,
                    size_band="NOT_APPLICABLE",
                    statistical_reliability_flag="NOT_APPLICABLE",
                    recency_tier="",
                    frequency_tier="",
                    monetary_tier="",
                    behavioural_modifiers_summary="",
                    behavioural_profile_text="",
                    n_distinguishing_features=0,
                    n_features_assessable=0,
                    distinctiveness_status="NOT_APPLICABLE",
                    distinctiveness_supporting_features="",
                    interpretability_status="NOT_APPLICABLE",
                    interpretability_note="",
                    consistency_status="NOT_APPLICABLE",
                    n_inconsistencies=0,
                    consistency_note="",
                    reproducibility_status="NOT_APPLICABLE",
                    seed_stability_status="NOT_APPLICABLE",
                    perturbation_status="NOT_APPLICABLE",
                    stability_status="NOT_APPLICABLE",
                    stability_note="",
                    n_features_supported_direction=0,
                    business_relevance_status="NOT_APPLICABLE",
                    business_interpretation_text="",
                    evidence_sources="",
                    inconsistencies_across_cps="",
                    limitations="DBSCAN noise KHÔNG phải Customer Segment.",
                    is_interpretation_ready=False,
                    interpretation_readiness="NOT_ASSESSABLE",
                    is_noise=True,
                )
            )
            continue

        # Non-noise.
        distinctiveness_status = d.distinctiveness_status if d else "NOT_ASSESSABLE"
        interpretability_status = i.interpretability_status if i else "NOT_AVAILABLE"
        consistency_status = c.consistency_status if c else "NOT_ASSESSABLE"
        business_relevance_status = b.business_relevance_status if b else "NOT_ASSESSABLE"
        size_band = s.size_band if s else "NOT_APPLICABLE"

        ready = _is_interpretation_ready(
            distinctiveness_status=distinctiveness_status,
            interpretability_status=interpretability_status,
            consistency_status=consistency_status,
            business_relevance_status=business_relevance_status,
            is_noise=False,
            labels_persisted=unit.labels_persisted,
        )
        readiness = _interpretation_readiness(is_ready=ready, size_band=size_band)

        out.append(
            FinalSegmentDefinition(
                segment_id=segment_id,
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                configuration_status=unit.configuration_status,
                labels_persisted=unit.labels_persisted,
                cluster_id=cid,
                cluster_label=cluster_label,
                naming_status=name_info.get("naming_status", ""),
                segment_name=name_info.get("segment_name", "") if i is None else i.segment_name,
                modifiers=name_info.get("modifiers", ""),
                naming_rationale=name_info.get("naming_rationale", ""),
                n_customers=int(s.n_customers) if s else int(row["customer_count"]),
                pct_of_assigned=float(s.pct_of_assigned) if s else 0.0,
                pct_of_total=float(s.pct_of_total) if s else 0.0,
                relative_size_ratio=float(s.relative_size_ratio) if s else 0.0,
                size_band=size_band,
                statistical_reliability_flag=(
                    s.statistical_reliability_flag if s else "NOT_APPLICABLE"
                ),
                recency_tier=profile_info.get("recency_tier", ""),
                frequency_tier=profile_info.get("frequency_tier", ""),
                monetary_tier=profile_info.get("monetary_tier", ""),
                behavioural_modifiers_summary=profile_info.get("behavioural_modifiers_summary", ""),
                behavioural_profile_text=profile_info.get("behavioural_profile_text", ""),
                n_distinguishing_features=(d.n_distinguishing_features if d else 0),
                n_features_assessable=d.n_features_assessable if d else 0,
                distinctiveness_status=distinctiveness_status,
                distinctiveness_supporting_features=(d.supporting_features if d else ""),
                interpretability_status=interpretability_status,
                interpretability_note=i.limitations if i else "",
                consistency_status=consistency_status,
                n_inconsistencies=c.n_inconsistencies if c else 0,
                consistency_note=c.limitations if c else "",
                reproducibility_status=st.reproducibility_status if st else "NOT_ASSESSABLE",
                seed_stability_status=st.seed_stability_status if st else "NOT_ASSESSABLE",
                perturbation_status=st.perturbation_status if st else "NOT_ASSESSABLE",
                stability_status=st.stability_status if st else "NOT_ASSESSABLE",
                stability_note=st.stability_evidence_note if st else "",
                n_features_supported_direction=(b.n_features_supported_direction if b else 0),
                business_relevance_status=business_relevance_status,
                business_interpretation_text=(b.business_interpretation_text if b else ""),
                evidence_sources="cp01,cp02,cp03,cp04,exp05",
                inconsistencies_across_cps=(c.cross_check_flags if c else ""),
                limitations="Aggregated từ 6 axes; per-segment limitations inherited từ CP-01 → CP-04.",
                is_interpretation_ready=ready,
                interpretation_readiness=readiness,
                is_noise=False,
            )
        )

    return out


def final_segment_definitions_to_rows(
    defs: Iterable[FinalSegmentDefinition],
) -> list[dict]:
    rows: list[dict] = []
    for d in defs:
        rows.append(
            {
                "segment_id": d.segment_id,
                "unit_id": d.unit_id,
                "algorithm": d.algorithm,
                "source_experiment": d.source_experiment,
                "configuration_status": d.configuration_status,
                "labels_persisted": d.labels_persisted,
                "cluster_id": d.cluster_id,
                "cluster_label": d.cluster_label,
                "naming_status": d.naming_status,
                "segment_name": d.segment_name,
                "modifiers": d.modifiers,
                "naming_rationale": d.naming_rationale,
                "n_customers": d.n_customers,
                "pct_of_assigned": d.pct_of_assigned,
                "pct_of_total": d.pct_of_total,
                "relative_size_ratio": d.relative_size_ratio,
                "size_band": d.size_band,
                "statistical_reliability_flag": d.statistical_reliability_flag,
                "recency_tier": d.recency_tier,
                "frequency_tier": d.frequency_tier,
                "monetary_tier": d.monetary_tier,
                "behavioural_modifiers_summary": d.behavioural_modifiers_summary,
                "behavioural_profile_text": d.behavioural_profile_text,
                "n_distinguishing_features": d.n_distinguishing_features,
                "n_features_assessable": d.n_features_assessable,
                "distinctiveness_status": d.distinctiveness_status,
                "distinctiveness_supporting_features": d.distinctiveness_supporting_features,
                "interpretability_status": d.interpretability_status,
                "interpretability_note": d.interpretability_note,
                "consistency_status": d.consistency_status,
                "n_inconsistencies": d.n_inconsistencies,
                "consistency_note": d.consistency_note,
                "reproducibility_status": d.reproducibility_status,
                "seed_stability_status": d.seed_stability_status,
                "perturbation_status": d.perturbation_status,
                "stability_status": d.stability_status,
                "stability_note": d.stability_note,
                "n_features_supported_direction": d.n_features_supported_direction,
                "business_relevance_status": d.business_relevance_status,
                "business_interpretation_text": d.business_interpretation_text,
                "evidence_sources": d.evidence_sources,
                "inconsistencies_across_cps": d.inconsistencies_across_cps,
                "limitations": d.limitations,
                "is_interpretation_ready": d.is_interpretation_ready,
                "interpretation_readiness": d.interpretation_readiness,
            }
        )
    return rows
