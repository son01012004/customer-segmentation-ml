"""CP-02 behavioural interpretation.

For each (unit, cluster, feature) this module produces a directional
interpretation string that:

- Names the **direction** (cao hơn tương đối / thấp hơn tương đối /
  gần tương đương) using the median-based relative difference
  computed by :mod:`relative_comparison`.
- Names the **observed behaviour** in plain Vietnamese using feature-
  specific semantics defined below.
- Uses qualifying language ("cao hơn tương đối", "có xu hướng",
  "quan sát thấy") so the statement is descriptive, not absolute.
- Does NOT use forbidden tokens (segment names, marketing
  recommendations, "best / winner / optimal").
- Does NOT make absolute claims about causality or future behaviour.

Feature semantics
-----------------

For each feature we encode:

- ``direction_high``: what behaviour does a HIGHER value indicate?
- ``direction_low``: what behaviour does a LOWER value indicate?
- ``direction_neutral``: how to describe a near-overall value.

The thresholds that decide "higher / lower / comparable" use the
relative difference (median vs overall median):

- ``HIGH_THRESHOLD_PCT`` = +10% → "cao hơn tương đối"
- ``LOW_THRESHOLD_PCT`` = -10% → "thấp hơn tương đối"
- Otherwise → "gần tương đương" / "khác biệt không đáng kể"

These thresholds are analytical defaults — the report notes that they
are not research-grade and a reader may re-bin with different
thresholds.

Hard constraints (AGENTS.md §2):
- Behavioural text must use qualifying language.
- No segment naming.
- No marketing recommendation.
- No algorithm ranking.
- No claim of "best", "winner", "optimal".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)
from customer_segmentation.profiling.cp02.relative_comparison import (
    RelativeComparisonRow,
    compute_relative_comparison_table,
)

# Default analytical thresholds (percent). Not research-grade.
HIGH_THRESHOLD_PCT = 10.0
LOW_THRESHOLD_PCT = -10.0


@dataclass(frozen=True)
class BehavioralInterpretationRow:
    """One (unit, cluster, feature) directional interpretation row."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    feature: str
    direction: str  # "HIGHER" | "LOWER" | "COMPARABLE" | "ZERO_REFERENCE" | "NA"
    rel_diff_median_pct: float
    cluster_median: float
    overall_median: float
    interpretation: str  # Vietnamese sentence


# Feature → (semantic direction when high, semantic direction when low,
# semantic direction when comparable). These are the canonical
# behavioural meanings used by the interpretation module.
#
# Recency is INVERTED: lower Recency means MORE recent activity
# (closer to the reference date). This matches the convention used
# throughout FE-05 / FE-06 documentation.
FEATURE_SEMANTICS: Mapping[str, dict[str, str]] = {
    "Recency": {
        "high": "khoảng cách từ lần mua cuối đến thời điểm tham chiếu dài hơn tương đối (Recency cao hơn population)",
        "low": "lần mua gần đây hơn tương đối (Recency thấp hơn population)",
        "neutral": "Recency gần với median của population — khoảng cách từ lần mua cuối không khác biệt đáng kể",
    },
    "Frequency": {
        "high": "số lượng hóa đơn (DistinctInvoiceCount) cao hơn tương đối — giao dịch thường xuyên hơn population",
        "low": "số lượng hóa đơn (DistinctInvoiceCount) thấp hơn tương đối — giao dịch ít thường xuyên hơn population",
        "neutral": "số lượng hóa đơn (DistinctInvoiceCount) gần với median population — tần suất giao dịch không khác biệt đáng kể",
    },
    "Monetary": {
        "high": "tổng giá trị chi tiêu (Monetary) cao hơn tương đối — chi tiêu quan sát được lớn hơn population",
        "low": "tổng giá trị chi tiêu (Monetary) thấp hơn tương đối — chi tiêu quan sát được nhỏ hơn population",
        "neutral": "tổng giá trị chi tiêu (Monetary) gần với median population — chi tiêu quan sát không khác biệt đáng kể",
    },
    "TotalQuantity": {
        "high": "tổng số lượng sản phẩm (TotalQuantity, có dấu) cao hơn tương đối",
        "low": "tổng số lượng sản phẩm (TotalQuantity, có dấu) thấp hơn tương đối",
        "neutral": "tổng số lượng sản phẩm (TotalQuantity) gần với median population",
    },
    "AverageQuantity": {
        "high": "số lượng sản phẩm trung bình mỗi hóa đơn (AverageQuantity / BasketSize, alias) cao hơn tương đối",
        "low": "số lượng sản phẩm trung bình mỗi hóa đơn (AverageQuantity / BasketSize, alias) thấp hơn tương đối",
        "neutral": "số lượng sản phẩm trung bình mỗi hóa đơn gần với median population",
    },
    "BasketSize": {
        "high": "BasketSize (= AverageQuantity theo FE-06 redundancy gate, Pearson = 1.0) cao hơn tương đối",
        "low": "BasketSize (= AverageQuantity theo FE-06 redundancy gate, Pearson = 1.0) thấp hơn tương đối",
        "neutral": "BasketSize gần với median population — redundant với AverageQuantity, không mang thêm thông tin độc lập",
    },
    "TenureDays": {
        "high": "thời gian quan hệ (TenureDays = ngày từ FirstPurchaseDate đến reference date) dài hơn tương đối",
        "low": "thời gian quan hệ (TenureDays) ngắn hơn tương đối",
        "neutral": "TenureDays gần với median population — thời gian quan hệ không khác biệt đáng kể",
    },
    "PurchaseIntervalMean": {
        "high": "khoảng cách trung bình giữa các hóa đơn (PurchaseIntervalMean) dài hơn tương đối — giao dịch thưa hơn",
        "low": "khoảng cách trung bình giữa các hóa đơn (PurchaseIntervalMean) ngắn hơn tương đối — giao dịch sát nhau hơn",
        "neutral": "PurchaseIntervalMean gần với median population (chú ý: STRUCTURALLY_UNDEFINED đã được median-impute trong FE-06; CP-02 dùng RAW giá trị có NaN)",
    },
    "PurchaseIntervalStd": {
        "high": "độ lệch chuẩn khoảng cách giữa các hóa đơn (PurchaseIntervalStd) cao hơn tương đối — cadence thay đổi nhiều hơn",
        "low": "độ lệch chuẩn khoảng cách giữa các hóa đơn (PurchaseIntervalStd) thấp hơn tương đối — cadence ổn định hơn",
        "neutral": "PurchaseIntervalStd gần với median population (chú ý: STRUCTURALLY_UNDEFINED đã được median-impute trong FE-06; CP-02 dùng RAW giá trị có NaN)",
    },
    "ActiveDays": {
        "high": "số ngày hoạt động (ActiveDays = distinct invoice dates) cao hơn tương đối",
        "low": "số ngày hoạt động (ActiveDays) thấp hơn tương đối",
        "neutral": "ActiveDays gần với median population (chú ý: HIGH_CORRELATION với Frequency, Pearson 0.97; không phải duplicate)",
    },
    "AverageInvoiceValue": {
        "high": "giá trị trung bình mỗi hóa đơn (AverageInvoiceValue, có dấu) cao hơn tương đối",
        "low": "giá trị trung bình mỗi hóa đơn (AverageInvoiceValue, có dấu) thấp hơn tương đối",
        "neutral": "AverageInvoiceValue gần với median population",
    },
    "ProductsPerInvoice": {
        "high": "số sản phẩm (distinct StockCode) trung bình mỗi hóa đơn (ProductsPerInvoice) cao hơn tương đối",
        "low": "số sản phẩm (distinct StockCode) trung bình mỗi hóa đơn (ProductsPerInvoice) thấp hơn tương đối",
        "neutral": "ProductsPerInvoice gần với median population",
    },
    "CancellationRate": {
        "high": "tỷ lệ hóa đơn có cancellation/return flag (CancellationRate = CancellationInvoiceCount / Frequency) cao hơn tương đối",
        "low": "CancellationRate thấp hơn tương đối",
        "neutral": "CancellationRate gần với median population (chú ý: DUPLICATE_INFORMATION với ReturnRate, Pearson 1.0; không phải hai hành vi độc lập)",
    },
    "ReturnRate": {
        "high": "tỷ lệ hóa đơn có cancellation/return flag (ReturnRate = ReturnInvoiceCount / Frequency) cao hơn tương đối",
        "low": "ReturnRate thấp hơn tương đối",
        "neutral": "ReturnRate gần với median population (chú ý: DUPLICATE_INFORMATION với CancellationRate, Pearson 1.0; không phải hai hành vi độc lập)",
    },
}


def _direction_label(rel_diff_pct: float) -> str:
    if np.isnan(rel_diff_pct):
        return "NA"
    if rel_diff_pct >= HIGH_THRESHOLD_PCT:
        return "HIGHER"
    if rel_diff_pct <= LOW_THRESHOLD_PCT:
        return "LOWER"
    return "COMPARABLE"


def _build_interpretation(
    feature: str,
    direction: str,
    cluster_median: float,
    overall_median: float,
    rel_diff_pct: float,
) -> str:
    """Compose a single-sentence Vietnamese interpretation.

    Returns a string that uses qualifying language and never uses
    forbidden tokens (segment names, "best", "winner", etc.).
    """
    semantics = FEATURE_SEMANTICS.get(
        feature,
        {
            "high": f"{feature} cao hơn tương đối",
            "low": f"{feature} thấp hơn tương đối",
            "neutral": f"{feature} gần với median population",
        },
    )
    if direction == "HIGHER":
        return (
            f"Quan sát thấy cluster có {semantics['high']} "
            f"(cluster median = {cluster_median:.2f}, overall median = {overall_median:.2f}, "
            f"relative difference ≈ {rel_diff_pct:+.1f}%)."
        )
    if direction == "LOWER":
        return (
            f"Quan sát thấy cluster có {semantics['low']} "
            f"(cluster median = {cluster_median:.2f}, overall median = {overall_median:.2f}, "
            f"relative difference ≈ {rel_diff_pct:+.1f}%)."
        )
    if direction == "COMPARABLE":
        return (
            f"Cluster có {semantics['neutral']} "
            f"(cluster median = {cluster_median:.2f}, overall median = {overall_median:.2f}, "
            f"relative difference ≈ {rel_diff_pct:+.1f}%)."
        )
    return (
        f"Direction không xác định được cho feature {feature} "
        f"(cluster median = {cluster_median}, overall median = {overall_median})."
    )


def interpret_feature_for_cluster(
    feature: str,
    cluster_median: float,
    overall_median: float,
    rel_diff_pct: float,
    reference_status: str,
) -> BehavioralInterpretationRow:
    """Build an interpretation row from raw inputs.

    Used by :func:`compute_behavioral_interpretation_table` and
    directly by unit-tests / ad-hoc calls.
    """
    if reference_status == "ZERO_REFERENCE":
        direction = "ZERO_REFERENCE"
        interpretation = (
            f"Không tính được relative percentage cho {feature}: "
            f"overall median ≈ 0 ({overall_median:.4f}). "
            f"Cluster median = {cluster_median:.2f}; không có ý nghĩa so sánh phần trăm."
        )
    elif reference_status == "NA":
        direction = "NA"
        interpretation = (
            f"Không tính được direction cho {feature}: "
            f"cluster median = {cluster_median}, overall median = {overall_median}."
        )
    else:
        direction = _direction_label(rel_diff_pct)
        interpretation = _build_interpretation(
            feature=feature,
            direction=direction,
            cluster_median=cluster_median,
            overall_median=overall_median,
            rel_diff_pct=rel_diff_pct,
        )
    return BehavioralInterpretationRow(
        unit_id="",
        algorithm="",
        source_experiment="",
        cluster_id=-999,
        cluster_label="",
        feature=feature,
        direction=direction,
        rel_diff_median_pct=rel_diff_pct,
        cluster_median=cluster_median,
        overall_median=overall_median,
        interpretation=interpretation,
    )


def compute_behavioral_interpretation_table(
    rel_rows: Sequence[RelativeComparisonRow],
) -> list[BehavioralInterpretationRow]:
    """Build a behavioral interpretation table for every rel row.

    The table mirrors :func:`compute_relative_comparison_table`
    row-for-row and adds a Vietnamese interpretation sentence.
    """
    out: list[BehavioralInterpretationRow] = []
    for r in rel_rows:
        interp = interpret_feature_for_cluster(
            feature=r.feature,
            cluster_median=r.cluster_median,
            overall_median=r.overall_median,
            rel_diff_pct=r.rel_diff_median_pct,
            reference_status=r.reference_status,
        )
        out.append(
            BehavioralInterpretationRow(
                unit_id=r.unit_id,
                algorithm=r.algorithm,
                source_experiment=r.source_experiment,
                cluster_id=r.cluster_id,
                cluster_label=r.cluster_label,
                feature=r.feature,
                direction=interp.direction,
                rel_diff_median_pct=r.rel_diff_median_pct,
                cluster_median=r.cluster_median,
                overall_median=r.overall_median,
                interpretation=interp.interpretation,
            )
        )
    return out


def compute_behavioral_interpretation_table_from_units(
    units: Sequence[Cp02AnalysisUnit],
) -> list[BehavioralInterpretationRow]:
    """Convenience wrapper: build rel rows then interpret.

    Equivalent to calling ``compute_relative_comparison_table``
    followed by ``compute_behavioral_interpretation_table``.
    """
    rel_rows = compute_relative_comparison_table(units)
    return compute_behavioral_interpretation_table(rel_rows)


__all__ = [
    "BehavioralInterpretationRow",
    "compute_behavioral_interpretation_table",
    "compute_behavioral_interpretation_table_from_units",
    "interpret_feature_for_cluster",
    "FEATURE_SEMANTICS",
    "HIGH_THRESHOLD_PCT",
    "LOW_THRESHOLD_PCT",
    "FEATURE_COLUMNS",
]
