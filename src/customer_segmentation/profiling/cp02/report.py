"""CP-02 Markdown report builder.

The CP-02 report is descriptive only. It:

- Lists per-(analysis unit, cluster, feature) statistics.
- Summarises per-cluster relative-difference vs OVERALL median.
- Provides directional behavioural interpretation per (cluster, feature).
- Documents the provenance, analysis unit, feature representation,
  statistical method, and limitations.
- Does NOT rank algorithms, does NOT name segments, does NOT
  recommend marketing actions.

Output sections mirror the brief's documentation outline:

1. Executive summary
2. Inputs and provenance
3. Analysis units
4. Feature representation
5. Statistical method
6. Segment feature profiles (per-unit tables)
7. Feature statistics (per-unit detail tables)
8. Relative comparison (per-unit tables)
9. Behavioural analysis (per-cluster narrative)
10. Visualisation (chart index per unit)
11. Validation
12. Limitations
13. Research boundary
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from customer_segmentation.profiling.cp02.behavioral_interpretation import (
    FEATURE_SEMANTICS,
    HIGH_THRESHOLD_PCT,
    LOW_THRESHOLD_PCT,
    BehavioralInterpretationRow,
)
from customer_segmentation.profiling.cp02.feature_profiling import (
    FeatureProfileRow,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)
from customer_segmentation.profiling.cp02.relative_comparison import (
    RelativeComparisonRow,
)


@dataclass(frozen=True)
class Cp02ReportContext:
    """Inputs needed to build the CP-02 Markdown report."""

    units: Sequence[Cp02AnalysisUnit]
    feature_rows: Sequence[FeatureProfileRow]
    rel_rows: Sequence[RelativeComparisonRow]
    interp_rows: Sequence[BehavioralInterpretationRow]
    artifacts: Mapping[str, Sequence[str]]
    analysis_units_total: int
    units_with_labels: int
    units_without_labels: int
    raw_features_path: str
    raw_features_sha256: str | None
    cluster_size_table_path: str  # CP-01 reference for consistency


def _fmt_num(x: float, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{float(x):,.{decimals}f}"


def _fmt_pct(x: float, decimals: int = 1) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{float(x):+.{decimals}f}%"


def _fmt_int(x: int) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{int(x):,}"


def _cluster_profile_table(
    unit_id: str,
    cluster_rows: Sequence[FeatureProfileRow],
    overall_rows: Sequence[FeatureProfileRow],
) -> str:
    """Render one cluster's per-feature profile as a Markdown table."""
    if not cluster_rows:
        return "_No data._\n"
    # Group cluster_rows by cluster_label; overall_rows provides reference.
    by_cluster: dict[str, list[FeatureProfileRow]] = defaultdict(list)
    for r in cluster_rows:
        if r.unit_id != unit_id:
            continue
        by_cluster[r.cluster_label].append(r)
    overall_by_feat: dict[str, FeatureProfileRow] = {
        r.feature: r for r in overall_rows if r.unit_id == unit_id
    }
    if not by_cluster:
        return "_No cluster rows._\n"
    out_lines: list[str] = []
    for cl_label in sorted(by_cluster.keys()):
        cluster_count = by_cluster[cl_label][0].count_total if by_cluster[cl_label] else 0
        out_lines.append(f"### {cl_label}  (n = {cluster_count:,})\n")
        out_lines.append(
            "| Feature | count | median | P25 | P75 | mean | std | min | max | n_missing | OVERALL median | rel_diff_median |"
        )
        out_lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for feat in FEATURE_COLUMNS:
            row = next(
                (r for r in by_cluster[cl_label] if r.feature == feat),
                None,
            )
            overall = overall_by_feat.get(feat)
            if row is None or overall is None:
                continue
            if (row.median is None or (isinstance(row.median, float) and pd.isna(row.median))) or (
                overall.median is None
                or (isinstance(overall.median, float) and pd.isna(overall.median))
            ):
                rel_pct_str = "—"
            else:
                ref = float(overall.median)
                if abs(ref) <= 1e-9:
                    rel_pct_str = "ZERO_REFERENCE"
                else:
                    rel_pct = (float(row.median) - ref) / abs(ref) * 100.0
                    rel_pct_str = f"{rel_pct:+.1f}%"
            out_lines.append(
                f"| {feat} | {_fmt_int(row.count)} | {_fmt_num(row.median, 2)} | {_fmt_num(row.p25, 2)} | {_fmt_num(row.p75, 2)} | {_fmt_num(row.mean, 2)} | {_fmt_num(row.std, 2)} | {_fmt_num(row.min, 2)} | {_fmt_num(row.max, 2)} | {_fmt_int(row.n_missing)} | {_fmt_num(overall.median, 2)} | {rel_pct_str} |"
            )
        out_lines.append("")
    return "\n".join(out_lines)


def _behavioural_narrative(
    unit_id: str,
    interp_rows: Sequence[BehavioralInterpretationRow],
    cluster_label: str,
) -> str:
    """Render a Vietnamese narrative summary for one cluster.

    The narrative groups interpretations by direction (HIGHER /
    LOWER / COMPARABLE) and lists features in each group.
    """
    sub = [r for r in interp_rows if r.unit_id == unit_id and r.cluster_label == cluster_label]
    if not sub:
        return ""
    higher = [r for r in sub if r.direction == "HIGHER"]
    lower = [r for r in sub if r.direction == "LOWER"]
    comparable = [r for r in sub if r.direction == "COMPARABLE"]
    other = [r for r in sub if r.direction not in {"HIGHER", "LOWER", "COMPARABLE"}]
    out: list[str] = []
    if higher:
        out.append(
            "Có xu hướng cao hơn tương đối so với population median (theo median-based direction): "
            + ", ".join(r.feature for r in higher)
            + "."
        )
    if lower:
        out.append(
            "Có xu hướng thấp hơn tương đối so với population median: "
            + ", ".join(r.feature for r in lower)
            + "."
        )
    if comparable:
        out.append(
            "Các feature còn lại gần với population median (khác biệt không đáng kể theo threshold "
            f"{HIGH_THRESHOLD_PCT:+.0f}% / {LOW_THRESHOLD_PCT:+.0f}%): "
            + ", ".join(r.feature for r in comparable)
            + "."
        )
    if other:
        out.append(
            "Một số feature có direction không xác định được (ZERO_REFERENCE hoặc NA): "
            + ", ".join(r.feature for r in other)
            + "."
        )
    return " ".join(out)


def build_cp02_markdown(ctx: Cp02ReportContext, out_path: Path) -> Path:
    """Render the CP-02 Markdown report.

    Returns the output path.
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# CP-02 — Per-Cluster Feature Profile & Behavioural Analysis\n")
    lines.append(f"_Generated: {now}_\n")
    lines.append("")

    # 1. Executive summary
    lines.append("## 1. Executive Summary\n")
    lines.append(
        "CP-02 phân tích đặc trưng và hành vi của từng Customer Segment, "
        "dựa trên cùng các analysis units đã được CP-01 xác định (algorithm "
        "× condition). CP-02 dùng RAW interpretable feature values từ "
        f"`{ctx.raw_features_path}` (FE-05 output), KHÔNG dùng Yeo-Johnson + "
        "RobustScaler values từ FE-06 — vì transformation không trực tiếp "
        "diễn giải được bằng business units.\n"
    )
    lines.append("**Thống kê tổng quan:**")
    lines.append("")
    lines.append(f"- Số analysis units: **{ctx.analysis_units_total}**")
    lines.append(f"  - Có per-customer labels parquet: **{ctx.units_with_labels}**")
    lines.append(f"  - Không có (NOT_AVAILABLE): **{ctx.units_without_labels}**")
    lines.append("")
    lines.append(
        "**Phạm vi nghiên cứu:** CP-02 mô tả đặc trưng và hành vi ("
        "descriptive only). CP-02 KHÔNG đặt tên Customer Segment, KHÔNG "
        "đưa ra Marketing Recommendation, KHÔNG xếp hạng algorithm, "
        "KHÔNG dùng transformed values để diễn giải business. "
        "DBSCAN noise tách riêng, không gộp vào cluster profiling."
    )
    lines.append("")

    # 2. Inputs and provenance
    lines.append("## 2. Inputs and Provenance\n")
    lines.append(
        "CP-02 đọc cluster assignment artifacts của EPIC-07 (EXP-01) và "
        "configuration metadata của EPIC-08 (EXP-03) — đồng bộ với CP-01 — "
        f"kết hợp với RAW customer-level feature matrix tại "
        f"`{ctx.raw_features_path}` (FE-05 output, READ-ONLY).\n"
    )
    if ctx.raw_features_sha256:
        lines.append(f"- RAW features SHA-256: `{ctx.raw_features_sha256}`")
    lines.append(f"- Cluster size table (CP-01 reference): `{ctx.cluster_size_table_path}`")
    lines.append("")
    lines.append(
        "Per-customer labels parquet chỉ tồn tại cho EXP-01; EXP-03 "
        "working-selected labels không được persist (xem `EV03-HP-01`). "
        "CP-02 báo cáo EXP-03 units là `NOT_AVAILABLE` cho cluster "
        "profiles, tương tự CP-01.\n"
    )
    lines.append(
        "| unit_id | algorithm | source_experiment | configuration_id | configuration_status |"
    )
    lines.append("|---|---|---|---|---|")
    for u in ctx.units:
        lines.append(
            f"| {u.unit_id} | {u.algorithm} | {u.source_experiment} | "
            f"{u.configuration_id} | {u.configuration_status} |"
        )
    lines.append("")

    # 3. Analysis units
    lines.append("## 3. Analysis Units\n")
    lines.append(
        "Analysis units giống CP-01: mỗi (algorithm × condition) là một "
        "đơn vị phân tích độc lập. Đối với CP-02:\n"
    )
    lines.append(
        "- Algorithm = một trong năm thuật toán benchmark cố định: "
        "K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means (K-Medoids "
        "OUT OF SCOPE per ADR-0003).\n"
    )
    lines.append(
        "- Configuration = EXP-01 working-default (K = 4 cho fixed-K "
        "algorithms; DBSCAN realised K = 17) hoặc EXP-03 working-selected.\n"
    )
    lines.append(
        "- Customer-level labels = per-customer ClusterLabel từ source "
        "artifact. KHÔNG gộp labels từ nhiều algorithm.\n"
    )
    lines.append(
        "- DBSCAN ClusterLabel == -1 (noise) được tách riêng, KHÔNG phải "
        "Customer Segment, KHÔNG được profile bởi CP-02.\n"
    )
    lines.append("")

    # 4. Feature representation
    lines.append("## 4. Feature Representation\n")
    lines.append(
        "CP-02 sử dụng 14 customer-level features trong working "
        "representation đã được FE-05 + FE-06 lock. CP-02 LUÔN dùng RAW "
        "interpretable values từ `customer_candidates.parquet` (FE-05 "
        "output) — không dùng Yeo-Johnson / RobustScaler values.\n"
    )
    lines.append("")
    lines.append("**14 working features (CP-02 input):**\n")
    lines.append("")
    lines.append("| # | Feature | Definition (FE-05 / FE-06) | Notes |\n" "|---|---|---|---|")
    for i, feat in enumerate(FEATURE_COLUMNS, start=1):
        sem = FEATURE_SEMANTICS.get(feat, {})
        high = sem.get("high", "—")
        lines.append(f"| {i} | `{feat}` | {high} | RAW value (pre-transformation) |")
    lines.append("")
    lines.append("**Special notes (từ FE-06 redundancy gate):**\n")
    lines.append(
        "- `AverageQuantity` ↔ `BasketSize` (DUPLICATE_INFORMATION, Pearson = 1.0). "
        "`BasketSize` là alias của `AverageQuantity` — KHÔNG phải hai hành vi "
        "độc lập.\n"
    )
    lines.append(
        "- `CancellationRate` ↔ `ReturnRate` (DUPLICATE_INFORMATION, Pearson = 1.0). "
        "`CancellationInvoiceCount == ReturnInvoiceCount` trong dataset hiện tại "
        "— KHÔNG phải hai hành vi độc lập trong dataset này.\n"
    )
    lines.append(
        "- `Frequency` ↔ `ActiveDays` (HIGH_CORRELATION, Pearson = 0.97). "
        "Hai feature KHÔNG identical (EqualityRate = 77%); `Frequency` ở "
        "invoice-level, `ActiveDays` ở calendar-day-level.\n"
    )
    lines.append(
        "- `PurchaseIntervalMean` và `PurchaseIntervalStd` có NaN trong RAW "
        "values (STRUCTURALLY_UNDEFINED cho khách hàng có < 2 invoices). "
        "CP-02 giữ NaN và KHÔNG impute; số lượng NaN được ghi nhận trong "
        "bảng cluster feature profile.\n"
    )
    lines.append("")

    # 5. Statistical method
    lines.append("## 5. Statistical Method\n")
    lines.append(
        "Với mỗi (analysis unit, cluster, feature) CP-02 tính các "
        "thống kê mô tả sau trên RAW values (NaN được loại trừ khỏi "
        "tính toán, không impute):\n"
    )
    lines.append("")
    lines.append("- ``count`` — số khách hàng có giá trị non-NaN trong cluster cho feature.\n")
    lines.append("- ``count_total`` — tổng khách hàng trong cluster (bao gồm NaN).\n")
    lines.append("- ``mean``, ``median``, ``P25``, ``P75``, ``min``, ``max``, ``std``.\n")
    lines.append("- ``n_missing`` — số khách hàng có NaN trong cluster cho feature.\n")
    lines.append("")
    lines.append(
        "**Reference cho relative comparison:** OVERALL (non-noise) "
        "population statistic cho cùng analysis unit. Reference được "
        "tính trên tập non-noise (DBSCAN noise được loại trừ khỏi "
        "denominator).\n"
    )
    lines.append("")
    lines.append("**Direction thresholds (analytical defaults, không phải research-grade):**\n")
    lines.append(f"- HIGHER nếu `rel_diff_median_pct ≥ {HIGH_THRESHOLD_PCT:+.0f}%`")
    lines.append(f"- LOWER nếu `rel_diff_median_pct ≤ {LOW_THRESHOLD_PCT:+.0f}%`")
    lines.append("- COMPARABLE nếu trong khoảng giữa hai threshold.")
    lines.append("")
    lines.append("Reference = 0 → báo `ZERO_REFERENCE`; không tính percentage.\n")

    # 6. Segment feature profiles (per unit)
    lines.append("## 6. Segment Feature Profiles\n")
    lines.append(
        "Bảng dưới đây trình bày profile đặc trưng cho từng cluster "
        "trong từng analysis unit. Mỗi cell có count (số non-NaN), "
        "median / P25 / P75 / mean / std / min / max, n_missing, "
        "OVERALL median, và relative difference (median-based) "
        "so với OVERALL.\n"
    )
    # Group rows by unit
    cluster_rows_by_unit: dict[str, list[FeatureProfileRow]] = defaultdict(list)
    overall_rows_by_unit: dict[str, list[FeatureProfileRow]] = defaultdict(list)
    for r in ctx.feature_rows:
        if r.cluster_label == "OVERALL":
            overall_rows_by_unit[r.unit_id].append(r)
        else:
            cluster_rows_by_unit[r.unit_id].append(r)
    for unit_id in sorted(cluster_rows_by_unit.keys()):
        unit = next((u for u in ctx.units if u.unit_id == unit_id), None)
        if unit is None:
            continue
        # Get the count from CP-01 cluster-size table reference.
        lines.append(f"### {unit_id}\n")
        if unit.algorithm == "dbscan":
            lines.append(
                "_DBSCAN ClusterLabel == -1 (noise) được tách riêng, "
                "KHÔNG được profile trong CP-02._\n"
            )
        lines.append(
            _cluster_profile_table(
                unit_id=unit_id,
                cluster_rows=cluster_rows_by_unit[unit_id],
                overall_rows=overall_rows_by_unit[unit_id],
            )
        )

    # 7. Feature statistics
    lines.append("## 7. Feature Statistics\n")
    lines.append(
        "Bảng tóm tắt thống kê OVERALL cho từng analysis unit (non-noise " "population).\n"
    )
    lines.append(
        "| unit_id | feature | count | median | mean | std | P25 | P75 | min | max | n_missing |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for unit_id in sorted(overall_rows_by_unit.keys()):
        for r in sorted(overall_rows_by_unit[unit_id], key=lambda x: x.feature):
            lines.append(
                f"| {r.unit_id} | {r.feature} | {_fmt_int(r.count)} | {_fmt_num(r.median, 2)} | {_fmt_num(r.mean, 2)} | {_fmt_num(r.std, 2)} | {_fmt_num(r.p25, 2)} | {_fmt_num(r.p75, 2)} | {_fmt_num(r.min, 2)} | {_fmt_num(r.max, 2)} | {_fmt_int(r.n_missing)} |"
            )
    lines.append("")

    # 8. Relative comparison
    lines.append("## 8. Relative Comparison\n")
    lines.append(
        "Bảng relative difference (median-based) cho mỗi (cluster, feature). "
        "Giá trị dương = cluster median CAO hơn overall median; giá trị âm = "
        "THẤP hơn. `ZERO_REFERENCE` = overall median ≈ 0; `NA` = không tính "
        "được.\n"
    )
    lines.append(
        "| unit_id | cluster | feature | cluster_median | overall_median | rel_diff_median_pct | reference_status |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in sorted(
        ctx.rel_rows,
        key=lambda x: (x.unit_id, int(x.cluster_label[1:]), x.feature),
    ):
        lines.append(
            f"| {r.unit_id} | {r.cluster_label} | {r.feature} | {_fmt_num(r.cluster_median, 2)} | {_fmt_num(r.overall_median, 2)} | {_fmt_pct(r.rel_diff_median_pct, 1)} | {r.reference_status} |"
        )
    lines.append("")

    # 9. Behavioural analysis
    lines.append("## 9. Behavioural Analysis\n")
    lines.append(
        "Mục này tóm tắt diễn giải hành vi bằng ngôn ngữ mô tả tương đối "
        "cho mỗi cluster. Direction dựa trên median-based relative "
        "difference (so với OVERALL median của cùng analysis unit, non-noise "
        "subset).\n"
    )
    lines.append(
        '**Ngôn ngữ sử dụng:** "cao hơn tương đối", "thấp hơn tương đối", '
        '"có xu hướng", "quan sát thấy" — KHÔNG claim tuyệt đối. '
        "KHÔNG dùng tên segment đã biết (các tên segment thuộc CP-04). "
        "KHÔNG đưa ra Marketing Recommendation.\n"
    )
    interp_by_unit_cluster: dict[tuple[str, str], list[BehavioralInterpretationRow]] = defaultdict(
        list
    )
    for r in ctx.interp_rows:
        interp_by_unit_cluster[(r.unit_id, r.cluster_label)].append(r)
    for unit_id in sorted({k[0] for k in interp_by_unit_cluster}):
        lines.append(f"### {unit_id}\n")
        for cl_label in sorted({k[1] for k in interp_by_unit_cluster if k[0] == unit_id}):
            lines.append(f"#### {cl_label}\n")
            narrative = _behavioural_narrative(
                unit_id=unit_id,
                interp_rows=ctx.interp_rows,
                cluster_label=cl_label,
            )
            if narrative:
                lines.append(narrative + "\n")
            # Per-feature one-liner table.
            lines.append("")
            lines.append(
                "| feature | cluster_median | overall_median | rel_diff_median_pct | direction | interpretation |"
            )
            lines.append("|---|---|---|---|---|---|")
            for r in sorted(
                interp_by_unit_cluster[(unit_id, cl_label)],
                key=lambda x: x.feature,
            ):
                lines.append(
                    "| {feat} | {cm} | {om} | {rp} | {dr} | {it} |".format(
                        feat=r.feature,
                        cm=_fmt_num(r.cluster_median, 2),
                        om=_fmt_num(r.overall_median, 2),
                        rp=_fmt_pct(r.rel_diff_median_pct, 1),
                        dr=r.direction,
                        it=r.interpretation.replace("|", "\\|"),
                    )
                )
            lines.append("")

    # 10. Visualisation
    lines.append("## 10. Visualisation\n")
    lines.append("Mỗi analysis unit có per-customer labels được render thành:\n")
    lines.append(
        "- Một boxplot cho mỗi feature trong compact subset "
        f"({len(_compact_subset_features_for_report())} features: "
        "Recency, Frequency, Monetary, TotalQuantity, TenureDays, "
        "ActiveDays, CancellationRate).\n"
    )
    lines.append(
        "- Một heatmap 14-feature × n_clusters của relative % "
        "vs OVERALL median (signed, centered at 0).\n"
    )
    lines.append("")
    if any(ctx.artifacts.values()):
        for unit_id, files in ctx.artifacts.items():
            lines.append(f"### {unit_id}")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")
    else:
        lines.append("_No chart artifacts produced for this run._\n")
    lines.append("")

    # 11. Validation
    lines.append("## 11. Validation\n")
    lines.append(
        "`tests/test_cp02.py` chạy validation tests cho CP-02 (số test, "
        "xem file tests). Các check bao gồm:\n"
    )
    lines.append("- CustomerID alignment giữa cluster labels và RAW feature matrix.\n")
    lines.append("- Mỗi customer chỉ thuộc một cluster trong một analysis unit.\n")
    lines.append("- Số customer mỗi cluster khớp CP-01 (consistency check).\n")
    lines.append("- Statistics đúng (count, mean, median, percentiles).\n")
    lines.append(
        "- Relative difference đúng công thức, division-by-zero được "
        "xử lý bằng flag `ZERO_REFERENCE`.\n"
    )
    lines.append(
        "- Missing values được giữ nguyên (không silent impute); n_missing "
        "được report per (cluster, feature).\n"
    )
    lines.append(
        "- Không có duplicate (unit_id, cluster_label, feature) trong " "feature profile table.\n"
    )
    lines.append("- Tổng cluster customer count (non-noise) khớp CP-01.\n")
    lines.append("- Output deterministic qua rerun.\n")
    lines.append(
        "- Methodology gate: không có forbidden tokens trong report "
        "(segment naming, marketing recommendation, ...).\n"
    )
    lines.append("")

    # 12. Limitations
    lines.append("## 12. Limitations\n")
    lines.append(
        "1. **EXP-03 working-selected cluster sizes là `NOT_AVAILABLE`** "
        " — per-customer labels parquet không được persist (xem "
        "`EV03-HP-01`). CP-02 báo cáo `NOT_AVAILABLE` cho cluster "
        "profiles của EXP-03 units.\n"
    )
    lines.append(
        "2. **DBSCAN noise** = ClusterLabel -1 (3177 customers trong "
        "EXP-01-dbscan = 72.68% population) được tách riêng, KHÔNG "
        "được profile bởi CP-02. CP-02 chỉ phân tích non-noise "
        "clusters.\n"
    )
    lines.append(
        "3. **RAW values vs transformed values.** CP-02 dùng RAW "
        "interpretable values từ `customer_candidates.parquet`. Đây là "
        "surface diễn giải canonical; CP-02 KHÔNG dùng Yeo-Johnson + "
        "RobustScaler values vì transformation không trực tiếp map "
        "về business units.\n"
    )
    lines.append(
        "4. **Median imputation từ FE-06 không áp dụng cho CP-02.** "
        "CP-02 giữ NaN của `PurchaseIntervalMean` / `PurchaseIntervalStd` "
        "từ RAW values; `n_missing` được báo cáo per (cluster, feature) "
        "thay vì impute.\n"
    )
    lines.append(
        "5. **Threshold cho HIGHER / LOWER.** Ngưỡng "
        f"{HIGH_THRESHOLD_PCT:+.0f}% / {LOW_THRESHOLD_PCT:+.0f}% là analytical "
        "defaults — KHÔNG phải research-grade. Người đọc có thể thay "
        "đổi threshold và re-interpret direction.\n"
    )
    lines.append(
        "6. **Heavy skew / outliers.** Một số feature (Monetary, "
        "TotalQuantity, AverageQuantity, ...) có heavy skew ngay cả "
        "trong RAW values. CP-02 ưu tiên median / P25 / P75 cho "
        "diễn giải; mean được giữ nhưng không dùng để kết luận hành vi.\n"
    )
    lines.append(
        "7. **Redundancy giữa các feature.** `BasketSize` = alias của "
        "`AverageQuantity`; `CancellationRate` = `ReturnRate` trong "
        "dataset hiện tại. CP-02 vẫn báo cáo cả hai để giữ đầy đủ 14 "
        "feature rows; người đọc không nên diễn giải chúng như hai "
        "hành vi độc lập.\n"
    )
    lines.append(
        "8. **Direction là relative, không phải absolute.** "
        '"Cao hơn tương đối" chỉ có nghĩa so với OVERALL median '
        "trong cùng analysis unit. KHÔNG nói lên giá trị business "
        "tuyệt đối.\n"
    )
    lines.append("")

    # 13. Research boundary
    lines.append("## 13. Research Boundary\n")
    lines.append(
        "CP-02 chỉ được kết luận về **đặc trưng và hành vi mô tả** "
        "của customer segments. CP-02 KHÔNG kết luận về:\n"
    )
    lines.append("- Cluster nào được ưu tiên trong business decision.")
    lines.append("- Cluster nào nên nhận chiến lược marketing.")
    lines.append("- Đặt tên Customer Segment (thuộc CP-04).")
    lines.append("- Xếp hạng giữa các algorithms.")
    lines.append("- Khuyến nghị kinh doanh cho cluster.")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _compact_subset_features_for_report() -> tuple[str, ...]:
    """Mirror the boxplot feature subset for documentation consistency."""
    from customer_segmentation.profiling.cp02.visualization import (
        BOXPLOT_FEATURE_SUBSET,
    )

    return BOXPLOT_FEATURE_SUBSET


__all__ = [
    "Cp02ReportContext",
    "build_cp02_markdown",
]
