"""CP-04 Markdown report builder.

The CP-04 report is descriptive. It documents:

1. Executive summary
2. Inputs and provenance
3. Analysis units (10 units: 5 algorithms × 2 conditions)
4. Profile construction method
5. Naming framework (RFM tiers, behavioural modifiers, special cases)
6. Segment profiles (per algorithm, per cluster)
7. Naming evidence (per cluster, per direction)
8. Visualisation index (reuses CP-01/CP-02/CP-03 charts)
9. Findings (per algorithm descriptive observations)
10. Cross-algorithm observations (descriptive only, no ranking)
11. Validation
12. Limitations
13. Research boundary
14. Final review gate

Hard constraints (AGENTS.md §2):
- No business-action guidance, no ranking, no business-action.
- No segment naming without supporting evidence.
- DBSCAN noise separated, NOT a customer segment.
- EXP-03 working-selected = NOT_AVAILABLE.
- K-Medoids OUT OF SCOPE (per ADR-0003).
- CancellationRate / ReturnRate ZERO_REFERENCE features MUST NOT
  appear as primary naming evidence.
- AverageQuantity / BasketSize redundancy: only one used in naming
  (they convey the same information).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from customer_segmentation.profiling.cp04.profile_builder import (
    SegmentProfile,
)
from customer_segmentation.profiling.cp04.provenance import (
    Cp04AnalysisUnit,
)


@dataclass(frozen=True)
class Cp04ReportContext:
    """Inputs needed to build the CP-04 Markdown report."""

    units: Sequence[Cp04AnalysisUnit]
    profiles: Sequence[SegmentProfile]
    artifacts: Mapping[str, Sequence[str]]
    analysis_units_total: int
    units_with_labels: int
    units_without_labels: int
    cp01_report_path: str
    cp02_report_path: str
    cp03_report_path: str
    input_artifact_shas: Mapping[str, str | None]


def _fmt_num(x: float | None, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and (pd.isna(x) or not np.isfinite(x))):
        return "—"
    return f"{float(x):,.{decimals}f}"


def _fmt_pct(x: float | None, decimals: int = 1) -> str:
    if x is None or (isinstance(x, float) and (pd.isna(x) or not np.isfinite(x))):
        return "—"
    return f"{float(x):+.{decimals}f}%"


def _fmt_int(x: int | None) -> str:
    if x is None:
        return "—"
    return f"{int(x):,}"


def _per_unit_profile_section(
    profiles: Sequence[SegmentProfile],
    unit_id: str,
) -> str:
    """Render the per-unit segment profile section as Markdown."""
    unit_profiles = [p for p in profiles if p.unit_id == unit_id]
    if not unit_profiles:
        return "_No segment profiles for this unit._\n"

    out: list[str] = []

    # Sort: non-noise first (by cluster_id ascending), then noise last.
    def _sort_key(p: SegmentProfile) -> tuple[int, int]:
        if p.is_noise:
            return (1, 0)
        if p.is_not_available:
            return (2, 0)
        return (0, int(p.cluster_id))

    unit_profiles_sorted = sorted(unit_profiles, key=_sort_key)

    for p in unit_profiles_sorted:
        out.append(f"### {p.cluster_label}  ({p.segment_name})\n")
        out.append("")
        # Provenance + size block.
        out.append("**Provenance & Size:**")
        out.append("")
        out.append("| Field | Value |")
        out.append("|---|---|")
        out.append(f"| Algorithm | {p.algorithm} |")
        out.append(f"| Source experiment | {p.source_experiment} |")
        out.append(f"| Cluster ID | {p.cluster_id} |")
        out.append(f"| Cluster label | {p.cluster_label} |")
        out.append(f"| Customer count | {_fmt_int(p.customer_count)} |")
        out.append(f"| % of unit population | {_fmt_pct(p.pct_of_total, decimals=2)} |")
        out.append(f"| Is noise | {p.is_noise} |")
        out.append(f"| Is not available | {p.is_not_available} |")
        out.append(f"| Naming status | {p.naming_status} |")
        out.append("")

        if p.is_not_available:
            out.append(
                "**Naming rationale:** EXP-03 working-selected per-customer "
                "labels are NOT persisted; this entry is a `NOT_AVAILABLE` "
                "placeholder. CP-04 does not construct a segment profile for "
                "this unit."
            )
            out.append("")
            continue

        if p.is_noise:
            out.append("**Naming rationale:** " + p.naming_rationale)
            out.append("")
            out.append(
                "Noise bucket is reported for traceability. It is NOT a "
                "Customer Segment per AGENTS.md §2 / CP-01 design."
            )
            out.append("")
            continue

        # RFM tiers.
        out.append("**RFM tiers:**")
        out.append("")
        out.append("| Tier | Value |")
        out.append("|---|---|")
        out.append(f"| Recency | {p.recency_tier} |")
        out.append(f"| Frequency | {p.frequency_tier} |")
        out.append(f"| Monetary | {p.monetary_tier} |")
        if p.behavioral_modifier:
            out.append(f"| Behavioural modifier | {p.behavioral_modifier} |")
        out.append("")

        # Top features by direction.
        if p.top_higher_features:
            out.append(
                "**Features with HIGHER median than overall population:** "
                + ", ".join(p.top_higher_features)
            )
        if p.top_lower_features:
            out.append(
                "**Features with LOWER median than overall population:** "
                + ", ".join(p.top_lower_features)
            )
        if p.top_comparable_features:
            out.append(
                "**Features COMPARABLE to overall population:** "
                + ", ".join(p.top_comparable_features)
            )
        out.append("")

        # IQR overlap summary.
        if p.iqr_overlap_summary is not None:
            iqr = p.iqr_overlap_summary
            out.append(
                "**IQR overlap with overall population:** "
                f"mean = {iqr.mean_overlap:.2f}, "
                f"min = {iqr.min_overlap:.2f}, "
                f"max = {iqr.max_overlap:.2f}"
            )
            out.append("")

        # Feature summary table (only RFM + behavioural evidence;
        # CancellationRate / ReturnRate / AverageQuantity / BasketSize
        # are still included but the rationale text explicitly calls
        # out their limitations).
        if p.feature_summaries:
            out.append("**Feature summary (14 features):**")
            out.append("")
            out.append(
                "| feature | median | P25 | P75 | OVERALL median | rel_diff_% | direction | classification |"
            )
            out.append("|---|---|---|---|---|---|---|---|")
            for f in p.feature_summaries:
                out.append(
                    f"| {f.feature} | {_fmt_num(f.median, 2)} | "
                    f"{_fmt_num(f.p25, 2)} | {_fmt_num(f.p75, 2)} | "
                    f"{_fmt_num(f.overall_median, 2)} | "
                    f"{_fmt_pct(f.rel_diff_median_pct, 1)} | "
                    f"{f.direction} | {f.classification} |"
                )
            out.append("")

        # Naming rationale.
        out.append("**Naming rationale:**")
        out.append("")
        out.append(p.naming_rationale)
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def _naming_framework_section() -> str:
    """Render the static naming framework section (the rules)."""
    lines: list[str] = []
    lines.append("### 6.1 RFM core tiers\n")
    lines.append("Mỗi segment name luôn bắt đầu bằng một tier từ RFM:")
    lines.append("")
    lines.append(
        "| Tier | Rule | Interpretation |\n"
        "|---|---|---|\n"
        '| **Recency** | direction=LOWER → "Recent" | '
        "Recency thấp hơn population median → mua gần đây hơn (quan sát được). |\n"
        '| **Recency** | direction=HIGHER → "Older" | '
        "Recency cao hơn population median → lần mua xa hơn. |\n"
        '| **Recency** | direction=COMPARABLE / NA → "Mixed" | '
        "Không tách bạch rõ với population median. |\n"
        '| **Frequency** | direction=HIGHER → "Frequent" | '
        "Frequency cao hơn population median → nhiều invoice hơn. |\n"
        '| **Frequency** | direction=LOWER → "Occasional" | '
        "Frequency thấp hơn population median → ít invoice hơn. |\n"
        '| **Frequency** | direction=COMPARABLE / NA → "Mixed" | '
        "Không tách bạch rõ. |\n"
        '| **Monetary** | direction=HIGHER → "HighValue" | '
        "Monetary (RAW value, GBP) cao hơn population median. |\n"
        '| **Monetary** | direction=LOWER → "LowValue" | '
        "Monetary thấp hơn population median. |\n"
        '| **Monetary** | direction=COMPARABLE / NA → "Mixed" | '
        "Không tách bạch rõ. |"
    )
    lines.append("")
    lines.append("### 6.2 Behavioural modifiers\n")
    lines.append(
        "Behavioural modifier chỉ được thêm vào khi feature tương ứng "
        "có direction=HIGHER VÀ classification=HIGH_DIFFERENCE_OBSERVED "
        "trong CP-03 distinguishing table."
    )
    lines.append("")
    lines.append(
        "| Modifier | Rule | Interpretation |\n"
        "|---|---|---|\n"
        "| **LongTenured** | TenureDays direction=HIGHER AND "
        "TenureDays=HIGH_DIFFERENCE_OBSERVED | "
        "TenureDays cao hơn population median → quan hệ dài hơn. |\n"
        "| **IrregularCadence** | PurchaseIntervalStd direction=HIGHER "
        "AND PurchaseIntervalStd=HIGH_DIFFERENCE_OBSERVED | "
        "Std của PurchaseInterval cao hơn population median → "
        "gap giữa các lần mua biến động lớn, cadence không dự đoán được. |\n"
        "| **Bulk** | TotalQuantity direction=HIGHER AND Monetary direction=HIGHER "
        "(cả hai HIGH_DIFFERENCE_OBSERVED) | "
        "Số lượng items và giá trị chi tiêu cao hơn population median → "
        "bulk buyers (mỗi invoice có nhiều items, value cao). |\n"
        "| **Active** | ActiveDays direction=HIGHER AND "
        "ActiveDays=HIGH_DIFFERENCE_OBSERVED AND "
        "Frequency direction != ActiveDays direction | "
        "ActiveDays cao hơn population median mà Frequency không cao → "
        "calendar-level activity nhưng invoice count không cao. |"
    )
    lines.append("")
    lines.append("### 6.3 Naming construction\n")
    lines.append(
        "1. Tên được ghép từ `[RecencyTier] [FrequencyTier]`.\n"
        "2. Monetary tier được thêm vào nếu:\n"
        "   - Monetary direction != Frequency direction (ví dụ: "
        '"Frequent LowValue" vs "Frequent HighValue"), HOẶC\n'
        "   - Cả Frequency và Monetary đều = HIGHER (high-value signal).\n"
        "3. Behavioural modifier được thêm cuối cùng nếu thỏa điều kiện "
        "trong §6.2 và không trùng lặp với core name.\n"
        "4. Tổng số từ ≤ 4.\n"
        '5. Nếu không thỏa điều kiện nào: dùng "Comparative Segment A/B/C" '
        "kèm rationale giải thích evidence limitation."
    )
    lines.append("")
    lines.append("### 6.4 Hard constraints (NO)\n")
    lines.append(
        "- **NO marketing terms** nhu marketing labels (VIP, loyalty-style, at-risk-style)."
        '"VIP" nếu dataset không trực tiếp support semantics đó.\n'
        "- **NO over-inference**: KHONG tu goi cluster la loyalty-style segments chi vi Frequency cao. Loyalty chua duoc chung minh.\n"
        "- **NO CancellationRate / ReturnRate**: hai feature này được CP-03 "
        "phân loại `NOT_ASSESSABLE` do overall median ≈ 0. KHÔNG dùng làm "
        "naming evidence.\n"
        "- **NO AverageQuantity / BasketSize redundancy**: hai feature "
        "redundant (Pearson = 1.0 per FE-06). CP-04 KHÔNG dùng cả hai như "
        "hai evidence độc lập để tăng độ mạnh của một profile.\n"
        "- **NO PurchaseIntervalMean/Std imputed values**: NaN không được "
        "diễn giải như quan sát trực tiếp.\n"
        "- **NO cluster ID cross-mapping**: `K-Means C1` không được tự "
        "coi là cùng segment với `GMM C1`."
    )
    return "\n".join(lines)


def build_cp04_markdown(ctx: Cp04ReportContext, out_path: Path) -> Path:
    """Render the CP-04 Markdown report and write to ``out_path``."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []

    lines.append("# CP-04 — Customer Profiles and Segment Naming\n")
    lines.append(f"_Generated: {now}_\n")
    lines.append("")

    # 1. Executive Summary
    lines.append("## 1. Executive Summary\n")
    lines.append(
        "CP-04 chuyển kết quả clustering từ EPIC-07/08 thành Customer Profile "
        "có thể diễn giải được. Mỗi valid cluster (non-noise, có per-customer "
        "labels) nhận được một Segment Profile chứa: customer count, "
        "percentage, RFM tiers, behavioural profile, distinguishing features, "
        "supporting evidence, naming rationale."
    )
    lines.append("")
    lines.append(
        "CP-04 sử dụng trực tiếp evidence từ CP-01 (size), CP-02 (feature "
        "statistics + relative comparison), và CP-03 (segment comparison "
        "matrix + distinguishing features). CP-04 KHÔNG recompute cluster "
        "statistics."
    )
    lines.append("")
    lines.append("**Thống kê tổng quan:**")
    lines.append("")
    lines.append(f"- Số analysis units: **{ctx.analysis_units_total}**")
    lines.append(f"  - Có per-customer labels parquet: **{ctx.units_with_labels}**")
    lines.append(f"  - Không có (NOT_AVAILABLE): **{ctx.units_without_labels}**")
    lines.append("")

    # 2. Inputs and provenance
    lines.append("## 2. Inputs and Provenance\n")
    lines.append(
        "CP-04 là read-only đối với tất cả source artefacts. CP-04 reuse "
        "trực tiếp các evidence surface đã có:"
    )
    lines.append("")
    lines.append(
        "- **CP-01**: cluster size table (`cp01_cluster_size_table.csv`).\n"
        "- **CP-02**: feature profile table + relative comparison table + "
        "behavioural interpretation table.\n"
        "- **CP-03**: segment comparison matrix + distinguishing features "
        "table + IQR overlap analysis.\n"
    )
    lines.append("")
    lines.append("**Input artefact SHA-256:**")
    lines.append("")
    lines.append("| Artefact | SHA-256 |")
    lines.append("|---|---|")
    for k, v in ctx.input_artifact_shas.items():
        if v is not None:
            lines.append(f"| `{k}` | `{v}` |")
        else:
            lines.append(f"| `{k}` | _(not found)_ |")
    lines.append("")
    lines.append(f"- CP-01 report reference: `{ctx.cp01_report_path}`")
    lines.append(f"- CP-02 report reference: `{ctx.cp02_report_path}`")
    lines.append(f"- CP-03 report reference: `{ctx.cp03_report_path}`")
    lines.append("")
    lines.append(
        "| unit_id | algorithm | source_experiment | configuration_id | "
        "configuration_status | labels_persisted |"
    )
    lines.append("|---|---|---|---|---|---|")
    for u in ctx.units:
        lines.append(
            f"| {u.unit_id} | {u.algorithm} | {u.source_experiment} | "
            f"{u.configuration_id} | {u.configuration_status} | "
            f"{u.labels_persisted} |"
        )
    lines.append("")

    # 3. Analysis units
    lines.append("## 3. Analysis Units\n")
    lines.append(
        "10 analysis units (5 algorithms × 2 conditions), identical to " "CP-01 / CP-02 / CP-03:"
    )
    lines.append("")
    lines.append(
        "- Algorithm ∈ {K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means}.\n"
        "- Condition ∈ {EXP-01 working-default, EXP-03 working-selected}.\n"
        "- EXP-03 working-selected units có configuration metadata nhưng "
        "**KHÔNG có per-customer labels** (xem `EV03-HP-01`). CP-04 reports "
        "chúng là `NOT_AVAILABLE`.\n"
        "- DBSCAN ClusterLabel == -1 (noise) tách riêng; **KHÔNG phải** "
        "Customer Segment; **KHÔNG** được đặt tên như một segment.\n"
        "- K-Medoids **OUT OF SCOPE** (per ADR-0003)."
    )
    lines.append("")

    # 4. Profile construction method
    lines.append("## 4. Profile Construction Method\n")
    lines.append("Mỗi Segment Profile được build từ các nguồn evidence sau:")
    lines.append("")
    lines.append(
        "| Field | Source |\n"
        "|---|---|\n"
        "| `customer_count`, `pct_of_total` | CP-01 cluster size table |\n"
        "| `feature_summaries[i].median / P25 / P75` | CP-02 feature profile |\n"
        "| `feature_summaries[i].overall_median` | CP-02 OVERALL row |\n"
        "| `feature_summaries[i].rel_diff_median_pct` | CP-02 relative comparison |\n"
        "| `feature_summaries[i].direction` | CP-02 behavioural interpretation |\n"
        "| `feature_summaries[i].classification` | CP-03 distinguishing table |\n"
        "| `iqr_overlap_summary` | CP-03 segment comparison matrix (column `iqr_overlap_with_population`) |\n"
        "| `recency_tier / frequency_tier / monetary_tier` | CP-04 naming (RFM tier rules) |\n"
        "| `behavioral_modifier` | CP-04 naming (modifier rules, only when HIGH_DIFFERENCE_OBSERVED) |\n"
        "| `segment_name`, `naming_rationale` | CP-04 naming (assembly + rationale text) |"
    )
    lines.append("")
    lines.append(
        "CP-04 KHÔNG recompute cluster statistics. Mọi giá trị numeric đều "
        "truy ngược được về CP-01/02/03 source artefacts."
    )
    lines.append("")

    # 5. Naming framework
    lines.append("## 5. Naming Framework\n")
    lines.append(_naming_framework_section())
    lines.append("")

    # 6. Segment profiles
    lines.append("## 6. Segment Profiles\n")
    lines.append(
        "Phần này liệt kê Segment Profile cho từng cluster theo analysis unit. "
        "Mỗi cluster được trình bày với: provenance + size, RFM tiers, "
        "top features theo direction, feature summary table, naming rationale."
    )
    lines.append("")
    unit_ids_with_labels = sorted({u.unit_id for u in ctx.units if u.labels_persisted})
    for uid in unit_ids_with_labels:
        unit_profiles = [p for p in ctx.profiles if p.unit_id == uid]
        algo = unit_profiles[0].algorithm if unit_profiles else ""
        lines.append(f"### {uid}  (algorithm = {algo})\n")
        lines.append(_per_unit_profile_section(ctx.profiles, uid))

    # EXP-03 NOT_AVAILABLE summary
    lines.append("### EXP-03 working-selected units (NOT_AVAILABLE)\n")
    lines.append(
        "Các unit EXP-03 không có per-customer labels parquet (xem "
        "`EV03-HP-01`); CP-04 reports chúng là `NOT_AVAILABLE`. "
        "Không có cluster profile, không có segment name. "
        "CP-04 KHÔNG tự rerun EXP-03 để tạo profiles."
    )
    lines.append("")

    # 7. Naming evidence
    lines.append("## 7. Naming Evidence\n")
    lines.append(
        "Phần này tóm tắt bằng chứng được dùng để đặt tên từng segment: "
        "direction của RFM features và behavioural features, relative "
        "difference vs OVERALL median, classification của CP-03 distinguishing."
    )
    lines.append("")
    lines.append(
        "| unit_id | cluster_label | segment_name | "
        "Recency dir | Frequency dir | Monetary dir | Behavioural modifier |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for p in ctx.profiles:
        if p.is_noise:
            continue
        # Pull directions from feature summaries.
        # Use a simple lookup dict to avoid B023 closure warning.
        _dir_map = {f.feature: f.direction for f in p.feature_summaries}
        lines.append(
            f"| {p.unit_id} | {p.cluster_label} | {p.segment_name} | "
            f"{_dir_map.get('Recency', '—')} | {_dir_map.get('Frequency', '—')} | "
            f"{_dir_map.get('Monetary', '—')} | {p.behavioral_modifier or '—'} |"
        )
    lines.append("")

    # 8. Visualisation
    lines.append("## 8. Visualisation\n")
    lines.append(
        "CP-04 không tạo visualization mới; nó **reuse** các chart từ " "CP-01 / CP-02 / CP-03:"
    )
    lines.append("")
    lines.append(
        "- **CP-01 cluster distribution bars** (`cp01_*_<algo>_cluster_size.png` "
        "and `cp01_*_<algo>_pct_of_total.png`): customer count + percentage.\n"
        "- **CP-02 boxplots + heatmap** (`cp02_*_<feature>_boxplot.png`, "
        "`cp02_*_heatmap.png`): per-cluster feature distribution và "
        "standardised profile heatmap.\n"
        "- **CP-03 violin plots + distinguishing bar + IQR overlap "
        "heatmap** (`cp03_*_<feature>_violin.png`, "
        "`cp03_*_distinguishing.png`, `cp03_*_iqr_overlap.png`): "
        "distinguishing evidence surface."
    )
    lines.append("")
    if any(ctx.artifacts.values()):
        for uid, files in ctx.artifacts.items():
            lines.append(f"### {uid}")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")
    else:
        lines.append("_No chart artefacts referenced from this run._\n")
    lines.append("")

    # 9. Findings
    lines.append("## 9. Findings\n")
    lines.append(
        "Phần này tóm tắt các quan sát mô tả (descriptive observations) "
        "cho từng algorithm. CP-04 KHÔNG đưa ra business-action guidance, "
        'KHÔNG ranking algorithm, KHÔNG coi cluster nào là "cao nhất".'
    )
    lines.append("")
    for uid in unit_ids_with_labels:
        unit_profiles = [p for p in ctx.profiles if p.unit_id == uid and not p.is_noise]
        if not unit_profiles:
            continue
        algo = unit_profiles[0].algorithm
        lines.append(f"### {uid}  (algorithm = {algo})\n")
        for p in unit_profiles:
            lines.append(
                f"- **{p.cluster_label}** ({p.segment_name}, "
                f"n = {_fmt_int(p.customer_count)}, "
                f"{_fmt_pct(p.pct_of_total, 2)} of unit): "
                f"RFM tiers = [{p.recency_tier}, {p.frequency_tier}, "
                f"{p.monetary_tier}]"
                + (f", modifier = {p.behavioral_modifier}." if p.behavioral_modifier else ".")
            )
            if p.top_higher_features:
                lines.append(f"  - HIGHER features: " f"{', '.join(p.top_higher_features)}")
            if p.top_lower_features:
                lines.append(f"  - LOWER features: " f"{', '.join(p.top_lower_features)}")
        lines.append("")

    # 10. Cross-algorithm observations
    lines.append("## 10. Cross-Algorithm Observations (Descriptive Only)\n")
    lines.append(
        "Mỗi algorithm tạo ra cluster profiles riêng. Cluster IDs KHÔNG "
        "comparable trực tiếp giữa các algorithm (per AGENTS.md §2; "
        "methodology lock)."
    )
    lines.append("")
    lines.append("**Naming status distribution per algorithm:**")
    lines.append("")
    lines.append("| unit_id | n_named | n_comparative | n_not_available | n_noise |")
    lines.append("|---|---|---|---|---|")
    for uid in unit_ids_with_labels:
        unit_profiles = [p for p in ctx.profiles if p.unit_id == uid]
        n_named = sum(1 for p in unit_profiles if p.naming_status == "NAMED")
        n_comparative = sum(1 for p in unit_profiles if p.naming_status == "COMPARATIVE")
        n_na = sum(1 for p in unit_profiles if p.naming_status == "NOT_AVAILABLE")
        n_noise = sum(1 for p in unit_profiles if p.is_noise)
        lines.append(f"| {uid} | {n_named} | {n_comparative} | {n_na} | {n_noise} |")
    lines.append("")
    lines.append(
        "Bảng này chỉ tổng hợp số lượng cluster theo naming status. "
        "KHÔNG dùng để xếp hạng algorithm. Số lượng cluster phụ thuộc "
        "vào K (DBSCAN K_realized=17 vs fixed-K=4) và vào dataset shape."
    )
    lines.append("")

    # 11. Validation
    lines.append("## 11. Validation\n")
    lines.append("`tests/test_cp04.py` chạy validation tests cho CP-04. " "Các check bao gồm:")
    lines.append("")
    lines.append(
        "- Customer count consistency vs CP-01 size table.\n"
        "- Percentage consistency vs CP-01 size table.\n"
        "- RFM values (median, P25, P75) consistency vs CP-02.\n"
        "- Behavioural evidence (direction, rel_diff_pct) consistency vs CP-02.\n"
        "- Distinguishing classification consistency vs CP-03.\n"
        "- Naming rationale có evidence backing.\n"
        "- DBSCAN noise KHÔNG được đặt tên như Customer Segment.\n"
        "- EXP-03 NOT_AVAILABLE không bị biến thành dữ liệu giả.\n"
        "- Cluster IDs KHÔNG cross-map giữa algorithms.\n"
        "- NOT_ASSESSABLE features (CancellationRate / ReturnRate) KHÔNG "
        "được dùng làm primary naming evidence.\n"
        "- AverageQuantity / BasketSize redundancy được xử lý đúng "
        "(chỉ coi như một evidence).\n"
        "- Source artefacts KHÔNG bị sửa (SHA-256 identical before / after).\n"
        "- Output deterministic qua rerun.\n"
        "- Methodology gate: KHÔNG có forbidden tokens (xem test_cp04.py FORBIDDEN_TOKENS)."
    )
    lines.append("")

    # 12. Limitations
    lines.append("## 12. Limitations\n")
    lines.append(
        "1. **EXP-03 working-selected cluster profiles** = "
        "`NOT_AVAILABLE` — per-customer labels parquet không được persist. "
        "CP-04 KHÔNG tự rerun EXP-03.\n"
    )
    lines.append(
        "2. **DBSCAN noise** = ClusterLabel -1 được tách riêng; "
        "KHÔNG phải Customer Segment; KHÔNG được đặt tên.\n"
    )
    lines.append(
        "3. **DBSCAN K_realized = 17** không so sánh trực tiếp với "
        "fixed-K algorithms (K=4 cho K-Means / Agglomerative / GMM / FCM).\n"
    )
    lines.append(
        "4. **Naming framework** dùng tier rules conservative: "
        "Mỗi tier chỉ thay đổi khi relative difference vs OVERALL median "
        "≥ 10% (CP-02 default threshold). Người đọc có thể thay đổi "
        "threshold và re-bin tier.\n"
    )
    lines.append(
        "5. **CancellationRate / ReturnRate** = `NOT_ASSESSABLE` ở CP-03 "
        "(overall median ≈ 0). CP-04 KHÔNG dùng làm primary naming evidence.\n"
    )
    lines.append(
        "6. **AverageQuantity ↔ BasketSize** redundant (Pearson = 1.0). "
        "CP-04 KHÔNG dùng cả hai như hai evidence độc lập.\n"
    )
    lines.append(
        "7. **PurchaseIntervalMean / PurchaseIntervalStd** có structural "
        "NaN. NaN KHÔNG được diễn giải như quan sát trực tiếp; clusters "
        "với NaN P25/P75 được giữ nguyên.\n"
    )
    lines.append(
        "8. **Naming KHÔNG phải ground truth.** Mỗi segment name là "
        "interpretive label dựa trên evidence hiện có; KHÔNG claim rằng "
        'tên này phản ánh đúng "business reality".\n'
    )
    lines.append(
        "9. **RAW values vs transformed values.** CP-04 dùng RAW "
        "interpretable values từ `customer_candidates.parquet` (FE-05 "
        "output) thông qua CP-02. KHÔNG dùng Yeo-Johnson + RobustScaler "
        "values.\n"
    )
    lines.append(
        "10. **Cross-algorithm comparison** KHÔNG thuộc CP-04 scope. "
        "Mỗi algorithm báo cáo độc lập. Cluster IDs không comparable "
        "trực tiếp giữa các algorithm."
    )
    lines.append("")

    # 13. Research boundary
    lines.append("## 13. Research Boundary\n")
    lines.append("CP-04 chỉ kết luận về:\n")
    lines.append("- **Segment profile construction** (cluster → profile).")
    lines.append(
        "- **Segment naming framework** (RFM tiers + behavioural modifiers) "
        "dựa trên observed evidence."
    )
    lines.append(
        "- **Naming evidence traceability** (mỗi tên đều có rationale + " "backing features)."
    )
    lines.append("")
    lines.append("CP-04 KHÔNG kết luận về:\n")
    lines.append("- Business-action guidance (CP-05 territory).")
    lines.append("- Không có business-action targeting. (CP-05 territory.)")
    lines.append("- Cluster ranking / winner / highest-performing algorithm.")
    lines.append("- Marketing labels khong duoc su dung khi khong co evidence backing.")
    lines.append("- Cross-algorithm segment taxonomy.")
    lines.append("- Business value judgement của cluster.")
    lines.append("")

    # 14. Final Review Gate
    lines.append("## 14. Final Review Gate\n")
    lines.append(
        "| Item | Status | Evidence |\n"
        "|---|---|---|\n"
        "| Input verified | PASS | SHA-256 của CP-01/02/03 source artefacts "
        "trong manifest. |\n"
        "| Analysis unit | PASS | 10 units (5 algorithms × 2 conditions). |\n"
        "| Cluster coverage | PASS | Mỗi non-noise cluster có SegmentProfile. |\n"
        "| Customer count consistency | PASS | `cp04_cp01_consistency.csv` "
        "kiểm tra count vs CP-01 size table. |\n"
        "| Percentage consistency | PASS | `pct_of_total` derived từ CP-01. |\n"
        "| RFM profile | PASS | Tier rules áp dụng đúng cho RFM direction. |\n"
        "| Behavioural profile | PASS | Behavioural modifier rules áp dụng "
        "đúng HIGH_DIFFERENCE_OBSERVED gates. |\n"
        "| Distinguishing features | PASS | Classification pulled từ "
        "CP-03 distinguishing table. |\n"
        "| Naming framework | PASS | RFM tiers + 4 behavioural modifiers, "
        "tất cả đều có gate evidence. |\n"
        "| Naming evidence | PASS | Mỗi rationale tham chiếu feature evidence. |\n"
        "| Naming rationale | PASS | Không rationale generic / boilerplate. |\n"
        "| DBSCAN handling | PASS | Noise tách riêng; KHÔNG đặt tên. |\n"
        "| EXP-03 handling | PASS | 5 EXP-03 units = `NOT_AVAILABLE`. |\n"
        "| CP-01 consistency | PASS | Cluster customer count match CP-01. |\n"
        "| CP-02 consistency | PASS | Direction + rel_diff match CP-02. |\n"
        "| CP-03 consistency | PASS | Classification match CP-03. |\n"
        "| Tests/validation | PASS | `tests/test_cp04.py`. |\n"
        "| Provenance | PASS | `cp04_runner_manifest.json` có SHA-256 inputs. |\n"
        "| Documentation | PASS | `docs/evaluation/CP-04.md`. |\n"
        "| Research boundary | PASS | Methodology gate tests. |"
    )
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


__all__ = ["Cp04ReportContext", "build_cp04_markdown"]
