"""CP-05 Markdown report builder.

Báo cáo tiếng Việt; technical terms (algorithm, metric, feature, code
identifier, file path) giữ nguyên tiếng Anh.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pandas as pd

from customer_segmentation.profiling.cp05.final_definition import (
    FinalSegmentDefinition,
)


@dataclass(frozen=True)
class Cp05ReportContext:
    """Input cho report builder."""

    final_definitions: list[FinalSegmentDefinition]
    units: list  # list of Cp05AnalysisUnit
    sha_manifest: dict[str, str]


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Convert DataFrame thành Markdown table không phụ thuộc tabulate."""
    if df.empty:
        return "_Không có dữ liệu._"
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(str(c) for c in cols) + " |",
        "|" + "|".join(["---"] * len(cols)) + "|",
    ]
    for _, row in df.iterrows():
        cells = [str(row[c]) for c in cols]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _per_algorithm_summary(defs: list[FinalSegmentDefinition]) -> pd.DataFrame:
    if not defs:
        return pd.DataFrame()
    df = pd.DataFrame(
        [
            {
                "algorithm": d.algorithm,
                "distinctiveness": d.distinctiveness_status,
                "interpretability": d.interpretability_status,
                "consistency": d.consistency_status,
                "business_relevance": d.business_relevance_status,
                "interpretation_readiness": d.interpretation_readiness,
                "is_interpretation_ready": d.is_interpretation_ready,
                "is_noise": d.is_noise,
            }
            for d in defs
            if not d.is_noise
        ]
    )
    if df.empty:
        return df
    agg = (
        df.groupby("algorithm")
        .agg(
            n_segments=("distinctiveness", "count"),
            n_distinct=(
                "distinctiveness",
                lambda s: (s == "DISTINCT").sum(),
            ),
            n_interpretable=(
                "interpretability",
                lambda s: (s == "INTERPRETABLE").sum(),
            ),
            n_consistent=(
                "consistency",
                lambda s: (s == "CONSISTENT").sum(),
            ),
            n_supported=(
                "business_relevance",
                lambda s: (s == "SUPPORTED").sum(),
            ),
            n_ready=(
                "interpretation_readiness",
                lambda s: (s == "READY").sum(),
            ),
            n_interpretation_ready=(
                "is_interpretation_ready",
                lambda s: s.sum(),
            ),
        )
        .reset_index()
    )
    return agg


def build_cp05_markdown(ctx: Cp05ReportContext) -> str:
    """Build Vietnamese Markdown report."""
    defs = ctx.final_definitions
    n_units = len(ctx.units)

    # Status distributions.
    distinct_counter = Counter(d.distinctiveness_status for d in defs)
    interp_counter = Counter(d.interpretability_status for d in defs)
    cons_counter = Counter(d.consistency_status for d in defs)
    size_counter = Counter(d.size_band for d in defs)
    stab_counter = Counter(d.stability_status for d in defs)
    biz_counter = Counter(d.business_relevance_status for d in defs)
    readiness_counter = Counter(d.interpretation_readiness for d in defs)

    n_total = len(defs)
    n_named = sum(1 for d in defs if d.naming_status == "NAMED")
    n_noise = sum(1 for d in defs if d.is_noise)
    n_not_available = sum(1 for d in defs if d.labels_persisted is False and not d.is_noise)
    n_ready_flag = sum(1 for d in defs if d.is_interpretation_ready)

    per_alg_df = _per_algorithm_summary(defs)
    per_alg_md = (
        _df_to_markdown(per_alg_df) if not per_alg_df.empty else "_Không có dữ liệu._"
    )

    # Final Definition table (top rows for readability).
    final_table_rows: list[dict] = []
    for d in defs[:50]:
        final_table_rows.append(
            {
                "segment_id": d.segment_id,
                "algorithm": d.algorithm,
                "n": d.n_customers,
                "size_band": d.size_band,
                "naming_status": d.naming_status,
                "segment_name": (d.segment_name or "")[:40],
                "distinctiveness": d.distinctiveness_status,
                "interpretability": d.interpretability_status,
                "consistency": d.consistency_status,
                "stability": d.stability_status,
                "business_relevance": d.business_relevance_status,
                "is_interpretation_ready": d.is_interpretation_ready,
                "interpretation_readiness": d.interpretation_readiness,
            }
        )
    final_table_df = pd.DataFrame(final_table_rows)
    final_table_md = (
        _df_to_markdown(final_table_df)
        if not final_table_df.empty
        else "_Không có dữ liệu._"
    )

    lines: list[str] = []
    lines.append("# CP-05 — Đánh giá khả năng diễn giải và ứng dụng Customer Segment")
    lines.append("")
    lines.append("> **Task ID:** EPIC-09 / CP-05")
    lines.append("> **Status:** IMPLEMENTED + VERIFIED")
    lines.append("> **Generated:** 2026-09-23")
    lines.append("")
    lines.append("## 1. Mục tiêu CP-05")
    lines.append("")
    lines.append(
        "CP-05 đánh giá **khả năng diễn giải** và **khả năng ứng dụng "
        "phân tích** của các Customer Segment hiện có, dựa trên "
        "evidence surface đã được CP-01 → CP-04 (và EXP-05) sản xuất "
        "ra. CP-05 KHÔNG recompute cluster statistics, KHÔNG fit "
        "model, KHÔNG ranking algorithm, KHÔNG đặt tên segment mới, "
        "KHÔNG marketing recommendation."
    )
    lines.append("")
    lines.append("## 2. Input / Provenance")
    lines.append("")
    lines.append("CP-05 đọc trực tiếp evidence từ các artifact đã tồn tại:")
    lines.append("")
    lines.append("| Nguồn | Vai trò |")
    lines.append("|---|---|")
    lines.append("| `cp01_cluster_size_table.csv` | Cluster size + percentage |")
    lines.append("| `cp01_noise_summary.csv` | DBSCAN noise fact |")
    lines.append("| `cp02_feature_profile_table.csv` | Per-cluster statistics |")
    lines.append("| `cp02_relative_comparison.csv` | rel_diff + direction |")
    lines.append("| `cp02_behavioral_interpretation.csv` | direction profile |")
    lines.append("| `cp03_segment_comparison_matrix.csv` | CP-02 + IQR overlap |")
    lines.append("| `cp03_distinguishing_features.csv` | effect range + classification |")
    lines.append("| `cp04_segment_profiles.csv` | RFM tiers + behavioural profile |")
    lines.append("| `cp04_segment_naming.csv` | segment name + rationale + modifier |")
    lines.append("| `cp04_segment_evidence.csv` | per-(profile, feature) evidence |")
    lines.append(
        "| EXP-05 reproducibility / seed sweep / noise perturbation | stability evidence |"
    )
    lines.append("")
    lines.append("## 3. Analysis Units")
    lines.append("")
    lines.append(
        f"CP-05 giữ nguyên **{n_units} analysis units** từ CP-04 " "(5 algorithms × 2 conditions)."
    )
    lines.append("")
    lines.append("## 4. Tính phân biệt (Distinctiveness)")
    lines.append("")
    lines.append("Phân loại theo số distinguishing features mà segment đóng góp:")
    lines.append("")
    for status, count in sorted(distinct_counter.items()):
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("## 5. Khả năng diễn giải (Interpretability)")
    lines.append("")
    lines.append("Phân loại theo naming_status + rationale groundedness:")
    lines.append("")
    for status, count in sorted(interp_counter.items()):
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("## 6. Tính nhất quán hành vi (Behavioral Consistency)")
    lines.append("")
    lines.append("Phân loại theo RFM tier grounding + modifier grounding:")
    lines.append("")
    for status, count in sorted(cons_counter.items()):
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("## 7. Quy mô segment (Segment Size)")
    lines.append("")
    lines.append(
        "Sử dụng `WORKING_ANALYTICAL_SIZE_BAND` (PENDING_REVIEW). "
        "`n < 30` chỉ là reliability warning, KHÔNG tự động loại "
        "segment."
    )
    lines.append("")
    for status, count in sorted(size_counter.items()):
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("## 8. Stability / Reproducibility")
    lines.append("")
    lines.append("**Reproducibility ≠ stability.** CP-05 phân biệt rõ hai khái " "niệm:")
    lines.append("")
    lines.append("- `reproducibility_status`: từ EXP-05 Block R " "(cùng seed → cùng labels).")
    lines.append(
        "- `stability_status`: cần ARI / AMI / NMI / Hungarian "
        "(**deferred to EPIC-08**). CP-05 chỉ báo cáo evidence "
        "availability."
    )
    lines.append("")
    lines.append(
        "**CP-05 KHÔNG compute ARI / AMI / NMI / Hungarian.** "
        "**CP-05 KHÔNG gọi segment 'stable' nếu chưa có stability "
        "metric.**"
    )
    lines.append("")
    for status, count in sorted(stab_counter.items()):
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("## 9. Mức độ liên quan nghiệp vụ (Business Relevance)")
    lines.append("")
    lines.append(
        "Chỉ mô tả dựa trên behavioral feature evidence trong dataset. "
        "**KHÔNG** suy diễn CLV/LTV/loyalty/churn/retention/purchase "
        "probability/profitability/customer value/marketing potential."
    )
    lines.append("")
    lines.append(
        "**Lưu ý:** `SUPPORTED` được hiểu là 'Có đủ behavioral "
        "feature-level evidence trong dataset để mô tả business "
        "relevance trong phạm vi nghiên cứu'. `SUPPORTED` KHÔNG có "
        "nghĩa 'business value đã được chứng minh'."
    )
    lines.append("")
    for status, count in sorted(biz_counter.items()):
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("## 10. Final Segment Definition")
    lines.append("")
    lines.append(
        f"Tổng số segment definitions: **{n_total}** (NAMED: {n_named}; "
        f"NOISE: {n_noise}; NOT_AVAILABLE: {n_not_available}; "
        f"`is_interpretation_ready = True`: {n_ready_flag})."
    )
    lines.append("")
    lines.append("### 10.1 Interpretation Readiness")
    lines.append("")
    lines.append(
        "`interpretation_readiness` (`READY` / `CONDITIONAL` / "
        "`LIMITED` / `NOT_ASSESSABLE`) là flag deterministic, KHÔNG "
        "phải winner/best/preferred/optimal/recommended claim. KHÔNG "
        "được dùng để ranking segment."
    )
    lines.append("")
    for status, count in sorted(readiness_counter.items()):
        lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append("### 10.2 Bảng Final Segment Definition (top rows)")
    lines.append("")
    lines.append(final_table_md)
    lines.append("")
    lines.append("### 10.3 Per-Algorithm Distribution (descriptive only)")
    lines.append("")
    lines.append("Bảng dưới đây chỉ mô tả (descriptive). KHÔNG ranking, KHÔNG " "winner.")
    lines.append("")
    lines.append(per_alg_md)
    lines.append("")
    lines.append("## 11. DBSCAN Handling")
    lines.append("")
    lines.append(
        "- DBSCAN `K_realized` ≠ requested K. KHÔNG so sánh trực tiếp " "với fixed-K algorithms."
    )
    lines.append("- Noise bucket (`cluster_id = -1`) KHÔNG phải Customer " "Segment.")
    lines.append(
        "- Small clusters (n ≤ 10) thường NaN-heavy → "
        "`LIMITED_DIFFERENTIVENESS` / `LIMITED_INTERPRETABILITY` "
        "phổ biến hơn. CP-05 không ép status."
    )
    lines.append("")
    lines.append("## 12. EXP-03 Limitation")
    lines.append("")
    lines.append(
        "EXP-03 working-selected cluster profiles = `NOT_AVAILABLE` "
        "(per `EV03-HP-01`). CP-05 KHÔNG rerun EXP-03. Tất cả 6 axes "
        "trả về `NOT_AVAILABLE` / `NOT_ASSESSABLE` cho 5 EXP-03 units."
    )
    lines.append("")
    lines.append("## 13. Methodology Limitations")
    lines.append("")
    lines.append(
        "- `WORKING_ANALYTICAL_SIZE_BAND` thresholds (50% / 25% / 5% / "
        "1%) — PENDING_REVIEW, KHÔNG research-grade."
    )
    lines.append(
        "- Interpretability groundedness heuristic — best-effort, " "KHÔNG research-grade."
    )
    lines.append("- ARI / AMI / NMI / Hungarian stability metrics — deferred " "to EPIC-08.")
    lines.append("- K-Medoids OUT OF SCOPE per ADR-0003.")
    lines.append(
        "- CancellationRate / ReturnRate = `NOT_ASSESSABLE` per "
        "CP-03 → không business interpretation evidence."
    )
    lines.append("- AverageQuantity ↔ BasketSize redundant → chỉ coi 1 " "evidence độc lập.")
    lines.append(
        "- RAW feature values only (KHÔNG inverse-transform Yeo-" "Johnson + RobustScaler)."
    )
    lines.append("")
    lines.append("## 14. Open / PENDING_REVIEW Decisions")
    lines.append("")
    lines.append("- `WORKING_ANALYTICAL_SIZE_BAND` (per §8.3).")
    lines.append("- Interpretability groundedness heuristic (per §6.3).")
    lines.append("- Business interpretation wording (per §10.3).")
    lines.append("- ARI/AMI/NMI/Hungarian stability metrics (deferred EPIC-08).")
    lines.append("")
    lines.append("## 15. Boundary với EPIC-08")
    lines.append("")
    lines.append(
        "EPIC-08 owns stability analysis (ARI / AMI / NMI / Hungarian), "
        "statistical tests, CI, runtime. CP-05 chỉ báo cáo evidence "
        "availability; KHÔNG compute metric mới."
    )
    lines.append("")
    lines.append("## 16. Boundary với EPIC-10")
    lines.append("")
    lines.append(
        "EPIC-10 owns visualization (segment profile charts, "
        "dashboard). CP-05 chỉ cung cấp definition rows; KHÔNG tạo "
        "viz."
    )
    lines.append("")
    lines.append("## 17. SHA / Read-only Manifest")
    lines.append("")
    if ctx.sha_manifest:
        lines.append("| File | SHA-256 |")
        lines.append("|---|---|")
        for path, sha in sorted(ctx.sha_manifest.items())[:30]:
            short = path.split("/")[-1]
            lines.append(f"| `{short}` | `{sha[:16]}...` |")
        if len(ctx.sha_manifest) > 30:
            lines.append(f"| _... và {len(ctx.sha_manifest) - 30} files khác_ | |")
    lines.append("")
    lines.append("## 18. Traceability")
    lines.append("")
    lines.append("- Source package: `src/customer_segmentation/profiling/cp05/`")
    lines.append("- Runner: `scripts/run_cp05.py`")
    lines.append("- Tests: `tests/test_cp05.py`")
    lines.append("- Plan: `docs/research/EPIC09_CP05_PLAN.md`")
    lines.append("- Documentation: `docs/evaluation/CP-05.md`")
    lines.append("- AGENTS.md: root")
    return "\n".join(lines)
