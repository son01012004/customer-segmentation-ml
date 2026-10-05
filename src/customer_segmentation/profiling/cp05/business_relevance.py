"""CP-05 business relevance evaluation (per plan §10 + task brief §4).

KHÔNG suy diễn CLV/LTV/loyalty/churn/retention/purchase probability /
profitability / customer value / marketing potential.

Chỉ mô tả dựa trên behavioral feature evidence đã có trong dataset.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from customer_segmentation.profiling.cp05.interpretability import (
    ALL_FORBIDDEN_TOKENS,
)
from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
)

# Feature → inferred observation (data-supported, RAW).
FEATURE_INTERPRETATION = {
    "Recency": "có invoice gần đây hơn / xa hơn population median",
    "Frequency": "có nhiều / ít invoice hơn population",
    "Monetary": "chi tiêu RAW GBP cao hơn / thấp hơn population",
    "TotalQuantity": "tổng quantity items (signed) cao hơn / thấp hơn",
    "TenureDays": "quan hệ kéo dài / ngắn hơn population",
    "ActiveDays": "calendar-level activity nhiều / ít hơn population",
    "PurchaseIntervalMean": "cadence ổn định (chỉ khi non-NaN)",
    "PurchaseIntervalStd": "cadence biến động (chỉ khi non-NaN)",
    "AverageInvoiceValue": "invoice size (GBP) cao hơn / thấp hơn",
    "ProductsPerInvoice": "diversity per invoice",
}

# Features KHÔNG được dùng cho business interpretation.
# CancellationRate / ReturnRate → NOT_ASSESSABLE per CP-03.
EXCLUDED_FROM_BUSINESS_INTERPRETATION = frozenset({"CancellationRate", "ReturnRate"})

# Allowed qualitative wording.
ALLOWED_QUALIFIERS = (
    "quan sát thấy",
    "có xu hướng",
    "theo dữ liệu",
    "RAW feature evidence shows",
    "evidence cho thấy",
)


@dataclass(frozen=True)
class BusinessRelevanceResult:
    """Per-segment business relevance evaluation result."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    n_features_supported_direction: int
    n_features_na: int
    feature_evidence: str  # semicolon-separated feature:direction
    business_relevance_status: str
    business_interpretation_text: str
    over_inference_check: bool
    limitations: str
    is_noise: bool


def _build_interpretation_text(
    feature_evidence_list: list[tuple[str, str]],
    segment_name: str,
) -> str:
    """Build a 1-3 sentence qualitative interpretation, bám sát evidence.

    Chỉ dùng qualifiers trong ALLOWED_QUALIFIERS. KHÔNG dùng forbidden
    tokens.
    """
    if not feature_evidence_list:
        return ""

    top_features = feature_evidence_list[:3]
    parts: list[str] = []
    for feature, direction in top_features:
        interp = FEATURE_INTERPRETATION.get(feature, "")
        if not interp:
            continue
        if direction == "HIGHER":
            parts.append(f"{feature} cao hơn tương đối ({interp})")
        elif direction == "LOWER":
            parts.append(f"{feature} thấp hơn tương đối ({interp})")

    if not parts:
        return ""

    seg_phrase = f"segment '{segment_name}'" if segment_name else "segment"
    body = "; ".join(parts)
    text = (
        f"Theo RAW feature evidence, {seg_phrase} có {body}. "
        f"Đây là mô tả descriptive dựa trên dữ liệu hiện có; "
        f"business value chưa được chứng minh."
    )
    return text


def _text_has_forbidden(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(tok.lower() in lower for tok in ALL_FORBIDDEN_TOKENS)


def evaluate_business_relevance(
    bundle: Cp04EvidenceBundle,
) -> list[BusinessRelevanceResult]:
    """Evaluate business relevance cho một analysis unit."""
    unit: Cp05AnalysisUnit = bundle.unit
    behavioral_df = bundle.behavioral_df
    naming_df = bundle.naming_df
    size_df = bundle.size_df

    # Build segment name lookup.
    name_lookup: dict[int, str] = {}
    if naming_df is not None and not naming_df.empty:
        for _, row in naming_df.iterrows():
            cid = int(row["cluster_id"])
            name_lookup[cid] = str(row.get("segment_name", ""))

    out: list[BusinessRelevanceResult] = []

    for _, row in size_df.iterrows():
        cid = int(row["cluster_id"])
        is_noise = cid == -1
        cluster_label = "noise (-1)" if is_noise else f"C{cid}"

        if is_noise:
            out.append(
                BusinessRelevanceResult(
                    unit_id=unit.unit_id,
                    algorithm=unit.algorithm,
                    source_experiment=unit.source_experiment,
                    cluster_id=cid,
                    cluster_label=cluster_label,
                    n_features_supported_direction=0,
                    n_features_na=0,
                    feature_evidence="",
                    business_relevance_status="NOT_APPLICABLE",
                    business_interpretation_text="",
                    over_inference_check=True,
                    limitations="DBSCAN noise KHÔNG phải Customer Segment.",
                    is_noise=True,
                )
            )
            continue

        # Per-cluster direction filter.
        supported: list[tuple[str, str]] = []
        n_na = 0
        if behavioral_df is not None and not behavioral_df.empty:
            cluster_rows = behavioral_df[behavioral_df["cluster_id"] == cid]
            for _, brow in cluster_rows.iterrows():
                feature = str(brow["feature"])
                direction = str(brow["direction"])
                if feature in EXCLUDED_FROM_BUSINESS_INTERPRETATION:
                    continue
                if direction in ("HIGHER", "LOWER"):
                    supported.append((feature, direction))
                elif direction in ("NA", "ZERO_REFERENCE", "COMPARABLE", None):
                    n_na += 1

        n_supported = len(supported)

        if n_supported >= 3:
            status = "SUPPORTED"
            limitations_text = (
                "SUPPORTED = 'Có đủ behavioral feature-level evidence trong "
                "dataset để mô tả business relevance trong phạm vi nghiên cứu'. "
                "KHÔNG có nghĩa 'business value đã được chứng minh'."
            )
        elif n_supported >= 1:
            status = "LIMITED"
            limitations_text = (
                "LIMITED = 'Có 1-2 features với direction quan sát được'. "
                "Interpretation rất hạn chế."
            )
        else:
            status = "NOT_ASSESSABLE"
            limitations_text = (
                "NOT_ASSESSABLE = 'Không có feature nào với direction quan "
                "sát được' hoặc 'toàn bộ features COMPARABLE / NA'."
            )

        seg_name = name_lookup.get(cid, "")
        interp_text = _build_interpretation_text(supported, seg_name)
        over_inference = _text_has_forbidden(interp_text)

        out.append(
            BusinessRelevanceResult(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                cluster_id=cid,
                cluster_label=cluster_label,
                n_features_supported_direction=n_supported,
                n_features_na=n_na,
                feature_evidence=";".join(f"{f}:{d}" for f, d in supported),
                business_relevance_status=status,
                business_interpretation_text=interp_text,
                over_inference_check=over_inference,
                limitations=limitations_text,
                is_noise=False,
            )
        )

    return out


def business_relevance_results_to_rows(
    results: Iterable[BusinessRelevanceResult],
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
                "n_features_supported_direction": r.n_features_supported_direction,
                "n_features_na": r.n_features_na,
                "feature_evidence": r.feature_evidence,
                "business_relevance_status": r.business_relevance_status,
                "business_interpretation_text": r.business_interpretation_text,
                "over_inference_check": r.over_inference_check,
                "limitations": r.limitations,
            }
        )
    return rows
