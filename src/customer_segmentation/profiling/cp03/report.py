"""CP-03 Markdown report builder.

The CP-03 report is descriptive. It documents:

1. Executive summary
2. Inputs and provenance
3. Analysis units
4. Feature comparison method (including WORKING_ANALYTICAL_THRESHOLD)
5. Segment comparison matrix (per-unit summary)
6. Distinguishing feature analysis (per-feature classification table)
7. Overlap and separation analysis (per-feature IQR overlap summary)
8. Visualisation index
9. Findings (per-unit, per-algorithm descriptive observations)
10. Cross-algorithm observations (descriptive only, no ranking)
11. Validation
12. Limitations
13. Research boundary

Hard constraints (AGENTS.md §2):

- No ranking, no "best", no "winner", no "optimal".
- No segment naming, no Marketing recommendation.
- DBSCAN noise separated.
- EXP-03 working-selected = ``NOT_AVAILABLE``.
- WORKING_ANALYTICAL_THRESHOLD explicitly labelled.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    Cp02AnalysisUnit,
)
from customer_segmentation.profiling.cp03.comparison import (
    Cp03ComparisonRow,
)
from customer_segmentation.profiling.cp03.difference_analysis import (
    WORKING_HIGH_DIFFERENCE_EFFECT_PCT,
    WORKING_HIGH_OVERLAP_MEAN,
    WORKING_LOW_DIFFERENCE_EFFECT_PCT,
    WORKING_MODERATE_DIFFERENCE_EFFECT_PCT,
    WORKING_MODERATE_OVERLAP_MEAN,
    Cp03DistinguishingRow,
)
from customer_segmentation.profiling.cp03.overlap_analysis import (
    Cp03OverlapRow,
)


@dataclass(frozen=True)
class Cp03ReportContext:
    """Inputs needed to build the CP-03 Markdown report."""

    units: Sequence[Cp02AnalysisUnit]
    comparison_rows: Sequence[Cp03ComparisonRow]
    distinguishing_rows: Sequence[Cp03DistinguishingRow]
    overlap_rows: Sequence[Cp03OverlapRow]
    artifacts: Mapping[str, Sequence[str]]
    analysis_units_total: int
    units_with_labels: int
    units_without_labels: int
    raw_features_path: str
    raw_features_sha256: str | None
    cp02_report_path: str


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


def _safe_int(x: object) -> int:
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return 0
        return int(x)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0


def _per_unit_classification_table(
    distinguishing_rows: Sequence[Cp03DistinguishingRow],
    unit_id: str,
) -> str:
    """Render the per-(unit, feature) classification table as Markdown."""
    rows = [r for r in distinguishing_rows if r.unit_id == unit_id]
    if not rows:
        return "_No distinguishing rows for this unit._\n"
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            -abs(r.effect_range_rel_pct)
            if r.effect_range_rel_pct is not None and np.isfinite(r.effect_range_rel_pct)
            else float("inf")
        ),
    )
    out: list[str] = []
    out.append(
        "| feature | classification | effect_range_rel_pct | iqr_overlap_mean | iqr_overlap_median | iqr_overlap_min | iqr_overlap_max | n_assessable | n_higher | n_lower | n_comparable | n_zero_ref | direction_consistency |"
    )
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows_sorted:
        out.append(
            "| {feat} | {cls} | {erp} | {imean} | {imed} | {imin} | {imax} | {n} | {nh} | {nl} | {nc} | {nzr} | {dcr} |".format(
                feat=r.feature,
                cls=r.classification,
                erp=_fmt_pct(r.effect_range_rel_pct, 1),
                imean=_fmt_num(r.iqr_overlap_mean, 2),
                imed=_fmt_num(r.iqr_overlap_median, 2),
                imin=_fmt_num(r.iqr_overlap_min, 2),
                imax=_fmt_num(r.iqr_overlap_max, 2),
                n=_safe_int(r.n_clusters_assessable),
                nh=_safe_int(r.n_clusters_higher),
                nl=_safe_int(r.n_clusters_lower),
                nc=_safe_int(r.n_clusters_comparable),
                nzr=_safe_int(r.n_clusters_zero_reference),
                dcr=(
                    _fmt_pct(r.direction_consistency_ratio * 100.0, 1)
                    if r.direction_consistency_ratio is not None
                    and np.isfinite(r.direction_consistency_ratio)
                    else "—"
                ),
            )
        )
    out.append("")
    return "\n".join(out)


def _per_unit_comparison_summary(
    comparison_rows: Sequence[Cp03ComparisonRow],
    unit_id: str,
) -> str:
    """Render a per-cluster summary table for one unit.

    Shows each cluster, feature subset, median, rel_diff, direction.
    """
    rows = [r for r in comparison_rows if r.unit_id == unit_id]
    if not rows:
        return "_No comparison rows for this unit._\n"
    # Group by cluster.
    by_cluster: dict[str, list[Cp03ComparisonRow]] = defaultdict(list)
    for r in rows:
        by_cluster[r.cluster_label].append(r)
    out: list[str] = []
    for cl_label in sorted(by_cluster.keys()):
        cl_rows = by_cluster[cl_label]
        n_customers = cl_rows[0].count_total if cl_rows else 0
        out.append(f"### {cl_label}  (n = {n_customers:,})\n")
        out.append(
            "| feature | median | P25 | P75 | OVERALL median | rel_diff_median | direction | iqr_overlap_with_population |"
        )
        out.append("|---|---|---|---|---|---|---|---|")
        for feat in FEATURE_COLUMNS:
            row = next((r for r in cl_rows if r.feature == feat), None)
            if row is None:
                continue
            out.append(
                f"| {feat} | {_fmt_num(row.median, 2)} | {_fmt_num(row.p25, 2)} | {_fmt_num(row.p75, 2)} | {_fmt_num(row.overall_median, 2)} | {_fmt_pct(row.rel_diff_median_pct, 1)} | {row.direction} | {_fmt_num(row.iqr_overlap_with_population, 2)} |"
            )
        out.append("")
    return "\n".join(out)


def _cross_unit_classification_summary(
    distinguishing_rows: Sequence[Cp03DistinguishingRow],
) -> str:
    """Render a cross-unit classification matrix (unit × feature → class)."""
    rows = list(distinguishing_rows)
    if not rows:
        return "_No distinguishing rows._\n"
    unit_ids = sorted({r.unit_id for r in rows})
    out: list[str] = []
    header = "| feature | " + " | ".join(unit_ids) + " |"
    sep = "|---|" + "|".join(["---"] * len(unit_ids)) + "|"
    out.append(header)
    out.append(sep)
    by_unit_feat: dict[tuple[str, str], Cp03DistinguishingRow] = {
        (r.unit_id, r.feature): r for r in rows
    }
    for feat in FEATURE_COLUMNS:
        cells: list[str] = []
        for uid in unit_ids:
            r = by_unit_feat.get((uid, feat))
            if r is None:
                cells.append("—")
            else:
                cells.append(r.classification)
        out.append(f"| {feat} | " + " | ".join(cells) + " |")
    out.append("")
    return "\n".join(out)


def _per_unit_overlap_summary(
    overlap_rows: Sequence[Cp03OverlapRow],
    unit_id: str,
) -> str:
    """Render the per-feature IQR overlap distribution table."""
    rows = [r for r in overlap_rows if r.unit_id == unit_id]
    if not rows:
        return "_No overlap rows for this unit._\n"
    by_feat: dict[str, list[Cp03OverlapRow]] = defaultdict(list)
    for r in rows:
        by_feat[r.feature].append(r)
    out: list[str] = []
    out.append("| feature | n_pairs | min_overlap | median_overlap | mean_overlap | max_overlap |")
    out.append("|---|---|---|---|---|---|")
    for feat in FEATURE_COLUMNS:
        fl = by_feat.get(feat, [])
        if not fl:
            out.append(f"| {feat} | 0 | — | — | — | — |")
            continue
        coefs = [r.iqr_overlap_coefficient for r in fl]
        finite = [c for c in coefs if np.isfinite(c)]
        if not finite:
            out.append(f"| {feat} | {len(fl)} | NA | NA | NA | NA |")
            continue
        out.append(
            f"| {feat} | {len(fl)} | "
            f"{min(finite):.2f} | {float(np.median(finite)):.2f} | "
            f"{float(np.mean(finite)):.2f} | {max(finite):.2f} |"
        )
    out.append("")
    return "\n".join(out)


def build_cp03_markdown(ctx: Cp03ReportContext, out_path: Path) -> Path:
    """Render the CP-03 Markdown report.

    Returns the output path.
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# CP-03 — Cluster Comparison and Distinguishing Feature Analysis\n")
    lines.append(f"_Generated: {now}_\n")
    lines.append("")

    # 1. Executive summary
    lines.append("## 1. Executive Summary\n")
    lines.append(
        "CP-03 so sánh các Customer Segment trên 14 customer-level features "
        "(RAW interpretable values từ FE-05 output), xác định feature có "
        "khác biệt quan sát được giữa các cluster, và đánh giá mức overlap "
        "/ separation giữa các cluster dựa trên IQR overlap coefficient.\n"
    )
    lines.append(
        "CP-03 **tái sử dụng trực tiếp** các hàm từ CP-02 "
        "(`feature_profiling`, `relative_comparison`, "
        "`behavioral_interpretation`) để đảm bảo consistency; CP-03 chỉ "
        "derive thêm các distinguishing indicators và IQR overlap metrics.\n"
    )
    lines.append("")
    lines.append("**Thống kê tổng quan:**")
    lines.append("")
    lines.append(f"- Số analysis units: **{ctx.analysis_units_total}**")
    lines.append(f"  - Có per-customer labels parquet: **{ctx.units_with_labels}**")
    lines.append(f"  - Không có (NOT_AVAILABLE): **{ctx.units_without_labels}**")
    lines.append("")
    lines.append(
        "**Phạm vi nghiên cứu:** CP-03 mô tả comparison và distinguishing "
        "evidence giữa các cluster. CP-03 KHÔNG đặt tên segment, KHÔNG "
        "đưa ra Marketing Recommendation, KHÔNG xếp hạng algorithm, "
        "KHÔNG tạo composite scoring framework để ranking distinguishing "
        "features. Classification dùng ``WORKING_ANALYTICAL_THRESHOLD`` "
        "(analytical defaults, không phải research-grade)."
    )
    lines.append("")

    # 2. Inputs and provenance
    lines.append("## 2. Inputs and Provenance\n")
    lines.append(
        "CP-03 đọc cùng các analysis units mà CP-01 / CP-02 đã sử dụng "
        "(algorithm × condition) và tái sử dụng CP-02 outputs làm primary "
        "evidence surface. KHÔNG recompute cluster statistics.\n"
    )
    if ctx.raw_features_sha256:
        lines.append(f"- RAW features source: `{ctx.raw_features_path}`")
        lines.append(f"  - SHA-256: `{ctx.raw_features_sha256}`")
    lines.append(f"- CP-02 report reference: `{ctx.cp02_report_path}`")
    lines.append("")
    lines.append(
        "| unit_id | algorithm | source_experiment | configuration_id | configuration_status | labels_persisted |"
    )
    lines.append("|---|---|---|---|---|---|")
    for u in ctx.units:
        lines.append(
            f"| {u.unit_id} | {u.algorithm} | {u.source_experiment} | "
            f"{u.configuration_id} | {u.configuration_status} | {u.labels_persisted} |"
        )
    lines.append("")
    lines.append(
        "EXP-03 working-selected units có configuration metadata nhưng "
        "KHÔNG có per-customer labels (xem `EV03-HP-01`); CP-03 reports "
        "chúng là `NOT_AVAILABLE` cho cluster-level comparison, giống CP-01 "
        "/ CP-02.\n"
    )

    # 3. Analysis units
    lines.append("## 3. Analysis Units\n")
    lines.append(
        "10 analysis units (5 algorithms × 2 conditions), identical to CP-01 " "/ CP-02:\n"
    )
    lines.append(
        "- Algorithm = K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means "
        "(K-Medoids OUT OF SCOPE per ADR-0003).\n"
    )
    lines.append(
        "- Condition = EXP-01 working-default (5 units, persisted labels) "
        "hoặc EXP-03 working-selected (5 units, NOT_AVAILABLE).\n"
    )
    lines.append(
        "- Configuration per unit giữ nguyên từ CP-01 / CP-02 "
        "(`WORKING_DEFAULT` cho EXP-01; `WORKING_SELECTED` / "
        "`TIED_WORKING_SELECTED` cho EXP-03).\n"
    )
    lines.append(
        "- DBSCAN ClusterLabel == -1 (noise) tách riêng; "
        "KHÔNG phải Customer Segment; KHÔNG được profile.\n"
    )
    lines.append("")

    # 4. Feature comparison method
    lines.append("## 4. Feature Comparison Method\n")
    lines.append(
        "CP-03 sử dụng RAW interpretable values từ "
        f"`{ctx.raw_features_path}` (FE-05 output) — KHÔNG dùng Yeo-Johnson "
        "+ RobustScaler values. CP-03 tái sử dụng CP-02 statistics:\n"
    )
    lines.append("")
    lines.append("- Per-cluster median, P25, P75, count, n_missing, mean, std (CP-02).")
    lines.append("- OVERALL (non-noise population) statistics cho mỗi analysis unit (CP-02).")
    lines.append("- Relative difference (cluster median vs OVERALL median × 100) (CP-02).")
    lines.append(
        "- Behavioural direction (HIGHER / LOWER / COMPARABLE / " "ZERO_REFERENCE / NA) (CP-02).\n"
    )
    lines.append("**CP-03 derives thêm (analytical, không có trong CP-02):**\n")
    lines.append("")
    lines.append(
        "- **Effect range** = max(cluster medians) − min(cluster medians) "
        "(RAW units), và effect range **relative** to OVERALL median × 100.\n"
    )
    lines.append(
        "- **IQR overlap coefficient** cho mỗi cặp cluster (a, b): "
        "`intersection([P25_a, P75_a], [P25_b, P75_b]) / max(IQR_a, IQR_b)` "
        "∈ [0, 1]. 1.0 = identical IQRs; 0.0 = disjoint IQRs.\n"
    )
    lines.append(
        "- **Direction counts**: n_clusters_higher / lower / comparable / "
        "zero_reference theo direction từ CP-02 (±10% threshold).\n"
    )
    lines.append(
        "- **Direction consistency**: max(n_higher, n_lower) / " "n_clusters_assessable.\n"
    )
    lines.append("")

    lines.append("### 4.1 WORKING_ANALYTICAL_THRESHOLD\n")
    lines.append(
        "Các threshold dưới đây là **analytical defaults**, KHÔNG phải "
        "research-grade. Chúng được dùng để gán analytical classification "
        "cho mỗi (unit, feature). Người đọc có thể thay đổi threshold và "
        "re-bin classification mà KHÔNG cần sửa CP-03 source.\n"
    )
    lines.append("")
    lines.append("| Threshold | Value | Meaning |")
    lines.append("|---|---|---|")
    lines.append(
        f"| `WORKING_HIGH_DIFFERENCE_EFFECT_PCT` | "
        f"{WORKING_HIGH_DIFFERENCE_EFFECT_PCT:+.0f}% | "
        f"effect_range_rel_pct ≥ threshold → HIGH_DIFFERENCE_OBSERVED "
        f"(kết hợp với IQR overlap) |"
    )
    lines.append(
        f"| `WORKING_MODERATE_DIFFERENCE_EFFECT_PCT` | "
        f"{WORKING_MODERATE_DIFFERENCE_EFFECT_PCT:+.0f}% | "
        f"effect_range_rel_pct ≥ threshold → MODERATE_DIFFERENCE_OBSERVED |"
    )
    lines.append(
        f"| `WORKING_LOW_DIFFERENCE_EFFECT_PCT` | "
        f"{WORKING_LOW_DIFFERENCE_EFFECT_PCT:+.0f}% | "
        f"effect_range_rel_pct < threshold → LOW_DIFFERENCE_OBSERVED |"
    )
    lines.append(
        f"| `WORKING_HIGH_OVERLAP_MEAN` | {WORKING_HIGH_OVERLAP_MEAN:.2f} | "
        f"mean IQR overlap ≥ threshold → HIGH_OVERLAP |"
    )
    lines.append(
        f"| `WORKING_MODERATE_OVERLAP_MEAN` | "
        f"{WORKING_MODERATE_OVERLAP_MEAN:.2f} | "
        f"mean IQR overlap ≤ threshold + HIGH effect range → HIGH separation |"
    )
    lines.append("")
    lines.append("**Classification rules (analytical):**\n")
    lines.append(
        f"- `HIGH_DIFFERENCE_OBSERVED`: effect_range_rel_pct ≥ "
        f"{WORKING_HIGH_DIFFERENCE_EFFECT_PCT:+.0f}% AND "
        f"iqr_overlap_mean ≤ {WORKING_MODERATE_OVERLAP_MEAN:.2f} AND "
        "n_clusters_assessable ≥ 2.\n"
    )
    lines.append(
        f"- `MODERATE_DIFFERENCE_OBSERVED`: effect_range_rel_pct ≥ "
        f"{WORKING_MODERATE_DIFFERENCE_EFFECT_PCT:+.0f}% AND not HIGH.\n"
    )
    lines.append(f"- `HIGH_OVERLAP`: iqr_overlap_mean ≥ " f"{WORKING_HIGH_OVERLAP_MEAN:.2f}.\n")
    lines.append(
        f"- `LOW_DIFFERENCE_OBSERVED`: effect_range_rel_pct < "
        f"{WORKING_LOW_DIFFERENCE_EFFECT_PCT:+.0f}%.\n"
    )
    lines.append("- `NOT_ASSESSABLE`: n_clusters_assessable < 2 hoặc NaN inputs.\n")

    # 5. Segment comparison matrix
    lines.append("## 5. Segment Comparison Matrix\n")
    lines.append(
        "Mục này trình bày Segment Comparison Matrix — một bảng per "
        "(unit, cluster, feature) tổng hợp median, P25, P75, relative "
        "difference, direction, và IQR overlap với OVERALL.\n"
    )
    unit_ids_with_labels = sorted({u.unit_id for u in ctx.units if u.labels_persisted})
    for uid in unit_ids_with_labels:
        lines.append(f"### {uid}\n")
        lines.append(_per_unit_comparison_summary(ctx.comparison_rows, uid))
        lines.append("")

    # 6. Distinguishing feature analysis
    lines.append("## 6. Distinguishing Feature Analysis\n")
    lines.append(
        "Mục này trình bày distinguishing feature indicators per "
        "(unit, feature) — effect range, IQR overlap, direction counts, "
        "và analytical classification.\n"
    )
    for uid in unit_ids_with_labels:
        lines.append(f"### {uid}\n")
        lines.append(_per_unit_classification_table(ctx.distinguishing_rows, uid))
        lines.append("")
    lines.append("### 6.1 Cross-unit classification summary\n")
    lines.append(
        "Bảng tổng hợp classification per (unit, feature) — chỉ chứa "
        "category, KHÔNG phải score / ranking.\n"
    )
    lines.append(_cross_unit_classification_summary(ctx.distinguishing_rows))

    # 7. Overlap and separation analysis
    lines.append("## 7. Overlap and Separation Analysis\n")
    lines.append(
        "Mục này trình bày pairwise IQR overlap distribution per feature, "
        "cho mỗi analysis unit. Số liệu dựa trên tất cả các cặp cluster "
        "(a, b) trong cùng analysis unit (không bao gồm noise, không "
        "bao gồm NaN).\n"
    )
    for uid in unit_ids_with_labels:
        lines.append(f"### {uid}\n")
        lines.append(_per_unit_overlap_summary(ctx.overlap_rows, uid))
        lines.append("")

    # 8. Visualisation
    lines.append("## 8. Visualisation\n")
    lines.append("Mỗi analysis unit có per-customer labels được render thành:\n")
    lines.append(
        "- Violin plots cho compact subset (7 features: Recency, "
        "Frequency, Monetary, TotalQuantity, TenureDays, ActiveDays, "
        "CancellationRate).\n"
    )
    lines.append(
        "- Distinguishing feature summary chart (horizontal bar chart, "
        "features sorted by effect_range_rel_pct, colored by classification).\n"
    )
    lines.append(
        "- IQR overlap summary heatmap (features × {mean, median, min, " "max} overlap).\n"
    )
    lines.append("")
    if any(ctx.artifacts.values()):
        for uid, files in ctx.artifacts.items():
            lines.append(f"### {uid}")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")
    else:
        lines.append("_No chart artifacts produced for this run._\n")
    lines.append("")

    # 9. Findings
    lines.append("## 9. Findings\n")
    lines.append(
        "Phần này tóm tắt descriptive observations cho từng analysis unit "
        "có labels. CP-03 KHÔNG đặt tên Customer Segment, KHÔNG ranking "
        "algorithm, KHÔNG marketing recommendation. Mỗi algorithm được "
        "mô tả độc lập.\n"
    )
    for uid in unit_ids_with_labels:
        unit_rows = [r for r in ctx.distinguishing_rows if r.unit_id == uid]
        if not unit_rows:
            continue
        high = [r for r in unit_rows if r.classification == "HIGH_DIFFERENCE_OBSERVED"]
        moderate = [r for r in unit_rows if r.classification == "MODERATE_DIFFERENCE_OBSERVED"]
        low = [r for r in unit_rows if r.classification == "LOW_DIFFERENCE_OBSERVED"]
        high_overlap = [r for r in unit_rows if r.classification == "HIGH_OVERLAP"]
        na = [r for r in unit_rows if r.classification == "NOT_ASSESSABLE"]
        algo = unit_rows[0].algorithm
        lines.append(f"### {uid}  (algorithm = {algo})\n")
        if high:
            lines.append(
                "**HIGH_DIFFERENCE_OBSERVED features:** "
                + ", ".join(r.feature for r in high)
                + "\n"
            )
        if moderate:
            lines.append(
                "**MODERATE_DIFFERENCE_OBSERVED features:** "
                + ", ".join(r.feature for r in moderate)
                + "\n"
            )
        if low:
            lines.append(
                "**LOW_DIFFERENCE_OBSERVED features:** " + ", ".join(r.feature for r in low) + "\n"
            )
        if high_overlap:
            lines.append(
                "**HIGH_OVERLAP features:** " + ", ".join(r.feature for r in high_overlap) + "\n"
            )
        if na:
            lines.append("**NOT_ASSESSABLE features:** " + ", ".join(r.feature for r in na) + "\n")
        lines.append("")

    # 10. Cross-algorithm observations
    lines.append("## 10. Cross-Algorithm Observations (Descriptive Only)\n")
    lines.append(
        "CP-03 mô tả rằng các algorithm tạo ra cluster profiles khác nhau "
        "nếu evidence hỗ trợ, nhưng KHÔNG tạo algorithm ranking / winner. "
        "Mỗi algorithm được mô tả độc lập trong §9.\n"
    )
    # Count HIGH features per unit (descriptive).
    cross: list[tuple[str, int, int, int]] = []
    for uid in unit_ids_with_labels:
        ur = [r for r in ctx.distinguishing_rows if r.unit_id == uid]
        n_high = sum(1 for r in ur if r.classification == "HIGH_DIFFERENCE_OBSERVED")
        n_mod = sum(1 for r in ur if r.classification == "MODERATE_DIFFERENCE_OBSERVED")
        n_low = sum(1 for r in ur if r.classification == "LOW_DIFFERENCE_OBSERVED")
        algo = ur[0].algorithm if ur else ""
        cross.append((uid, n_high, n_mod, n_low))
    if cross:
        lines.append(
            "Bảng dưới đây tổng hợp số feature trong mỗi analytical category theo analysis unit (descriptive):\n"
        )
        lines.append("| unit_id | n_HIGH | n_MODERATE | n_LOW |")
        lines.append("|---|---|---|---|")
        for uid, h, m, lo in cross:
            lines.append(f"| {uid} | {h} | {m} | {lo} |")
        lines.append("")
        lines.append(
            "Bảng này KHÔNG được dùng để xếp hạng algorithm. Số lượng "
            "feature HIGH/MODERATE/LOW phụ thuộc vào K (DBSCAN K_realized=17 "
            "so với fixed-K=4 cho các algorithm khác) và vào "
            "distribution shape, KHÔNG phải cluster quality.\n"
        )

    # 11. Validation
    lines.append("## 11. Validation\n")
    lines.append(
        "`tests/test_cp03.py` chạy validation tests cho CP-03 (xem file tests "
        "để biết số lượng test). Các check bao gồm:\n"
    )
    lines.append(
        "- CustomerID alignment giữa cluster labels và RAW feature matrix (CP-02 reuse).\n"
    )
    lines.append("- Mỗi customer chỉ thuộc một cluster trong một analysis unit (CP-02 reuse).\n")
    lines.append("- Cluster customer counts khớp CP-02 (consistency).\n")
    lines.append("- Segment comparison matrix không có duplicate (unit, cluster, feature).\n")
    lines.append("- IQR overlap coefficient deterministic và bounded trong [0, 1].\n")
    lines.append(
        "- Distinguishing indicators: effect_range_rel_pct, IQR overlap, "
        "direction counts đúng công thức.\n"
    )
    lines.append("- Analytical classification áp dụng đúng theo " "WORKING_ANALYTICAL_THRESHOLD.\n")
    lines.append(
        "- Methodological gate: không có forbidden tokens trong report "
        "(segment naming, marketing recommendation, ranking, ...).\n"
    )
    lines.append("- Output deterministic qua rerun.\n")
    lines.append(
        "- Read-only: SHA-256 của EXP-01 cluster_labels_*.parquet, "
        "customer_candidates.parquet, customer_metadata.parquet, "
        "CP-02 outputs giữ nguyên trước / sau CP-03 run.\n"
    )
    lines.append("")

    # 12. Limitations
    lines.append("## 12. Limitations\n")
    lines.append(
        "1. **EXP-03 working-selected cluster comparison = `NOT_AVAILABLE`** "
        " — per-customer labels parquet không được persist (xem "
        "`EV03-HP-01`). CP-03 báo cáo `NOT_AVAILABLE` cho cluster "
        "comparison của EXP-03 units.\n"
    )
    lines.append(
        "2. **DBSCAN noise** = ClusterLabel -1 (3,177 customers trong "
        "EXP-01-dbscan = 72.68% population) được tách riêng, KHÔNG được "
        "profile bởi CP-03. CP-03 chỉ phân tích non-noise clusters.\n"
    )
    lines.append(
        "3. **DBSCAN K_realized = 17** không so sánh trực tiếp với "
        "fixed-K algorithms (K=4 cho K-Means / Agglomerative / GMM / FCM).\n"
    )
    lines.append(
        "4. **WORKING_ANALYTICAL_THRESHOLD** là analytical defaults, "
        "KHÔNG phải research-grade. Người đọc có thể thay đổi threshold "
        "và re-bin classification.\n"
    )
    lines.append(
        "5. **IQR overlap coefficient** chỉ đo overlap giữa [P25, P75] "
        "của hai cluster. KHÔNG đo overlap ở đuôi (whiskers / outliers). "
        "Một feature có IQR overlap cao có thể vẫn có separation ở đuôi.\n"
    )
    lines.append(
        "6. **Effect range** chỉ dựa trên cluster medians, KHÔNG xét đến "
        "phân bố đầy đủ (mean, std, skew). Heavy skew hoặc outliers có "
        "thể ảnh hưởng cách diễn giải.\n"
    )
    lines.append(
        "7. **RAW values vs transformed values.** CP-03 dùng RAW "
        "interpretable values từ `customer_candidates.parquet`. KHÔNG "
        "dùng Yeo-Johnson + RobustScaler values.\n"
    )
    lines.append(
        "8. **NaN handling.** CP-03 KHÔNG impute NaN. Clusters có NaN "
        "P25/P75 (e.g., PurchaseIntervalMean/Std ở clusters với n=1) "
        "được loại khỏi `n_clusters_assessable`.\n"
    )
    lines.append(
        "9. **Cross-algorithm comparison** KHÔNG thuộc CP-03 scope. Mỗi "
        "algorithm báo cáo độc lập.\n"
    )
    lines.append(
        "10. **Feature redundancy** (BasketSize ↔ AverageQuantity, "
        "CancellationRate ↔ ReturnRate, Frequency ↔ ActiveDays) được "
        "CP-03 giữ nguyên 14 rows nhưng classification có thể trùng "
        "lặp giữa các cặp redundant features — đây là evidence-based, "
        "KHÔNG phải lỗi.\n"
    )
    lines.append("")

    # 13. Research boundary
    lines.append("## 13. Research Boundary\n")
    lines.append(
        "CP-03 chỉ được kết luận về **distinguishing features và overlap "
        "/ separation giữa các cluster** trong cùng analysis unit. "
        "CP-03 KHÔNG kết luận về:\n"
    )
    lines.append("- Cluster nào được ưu tiên trong business decision.")
    lines.append("- Cluster nào nên nhận chiến lược marketing.")
    lines.append("- Đặt tên Customer Segment (thuộc CP-04).")
    lines.append("- Xếp hạng giữa các algorithms.")
    lines.append("- Composite ranking / " "winner" " / " "optimal" " của algorithm.")
    lines.append("- Research-grade threshold cho distinguishing power.")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


__all__ = ["Cp03ReportContext", "build_cp03_markdown"]
