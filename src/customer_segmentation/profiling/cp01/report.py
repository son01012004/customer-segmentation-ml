"""CP-01 Markdown report builder.

The report is descriptive only. It does NOT claim any algorithm is
"best" / "winner" / "optimal" / "recommended". It does NOT name
customer segments. It does NOT use clustering quality metrics to
substitute for size analysis.

Sections
--------

1. Executive summary
2. Inputs and provenance (per analysis unit)
3. Per-unit cluster-size results (table)
4. Per-unit distribution indicators (table)
5. DBSCAN noise separation (where applicable)
6. Per-unit visualisation list
7. Limitations
8. Research boundary
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from customer_segmentation.profiling.cp01.size_analysis import (
    ClusterSizeRow,
    NoiseRow,
)
from customer_segmentation.profiling.cp01.distribution import (
    DistributionIndicators,
)


@dataclass(frozen=True)
class ReportContext:
    """Inputs needed to build the Markdown report."""

    cluster_rows: Sequence[ClusterSizeRow]
    noise_rows: Sequence[NoiseRow]
    indicators: Sequence[DistributionIndicators]
    units_metadata: Sequence[Mapping[str, str]]
    artifacts: Mapping[str, Sequence[str]]
    analysis_units_total: int
    units_with_labels: int
    units_without_labels: int


def _fmt_pct(x: float) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{x:.2f}%"


def _fmt_ratio(x: float) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{x:.4f}"


def _fmt_int(x: int) -> str:
    if x is None:
        return "—"
    return f"{int(x)}"


def _cluster_rows_table(rows: Sequence[ClusterSizeRow]) -> str:
    if not rows:
        return "_No analysis unit has persisted labels._\n"
    # Group by unit
    grouped: dict[str, list[ClusterSizeRow]] = defaultdict(list)
    for r in rows:
        grouped[r.unit_id].append(r)
    out_lines: list[str] = []
    for unit_id in sorted(grouped.keys()):
        unit_rows = sorted(grouped[unit_id], key=lambda r: r.cluster_id)
        out_lines.append(f"### {unit_id}\n")
        out_lines.append(
            "| Cluster id | is_noise | customer_count | pct_of_assigned | pct_of_total | relative_size_ratio |\n"
            "|---|---|---|---|---|---|"
        )
        for r in unit_rows:
            out_lines.append(
                "| {cid} | {isn} | {cnt} | {pa} | {pt} | {rs} |".format(
                    cid=_fmt_int(r.cluster_id),
                    isn="yes" if r.is_noise else "no",
                    cnt=_fmt_int(r.customer_count),
                    pa=_fmt_pct(r.pct_of_assigned),
                    pt=_fmt_pct(r.pct_of_total),
                    rs=_fmt_ratio(r.relative_size_ratio),
                )
            )
        out_lines.append("")
    return "\n".join(out_lines)


def _indicators_table(indicators: Sequence[DistributionIndicators]) -> str:
    if not indicators:
        return "_No analysis unit has persisted labels._\n"
    out = [
        "| unit_id | algorithm | n_clusters | n_total | largest | smallest | largest_pct_of_total | largest_to_smallest_ratio | size_range | deviation_from_equal_size | median_cluster_size |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i in sorted(indicators, key=lambda x: x.unit_id):
        out.append(
            "| {uid} | {algo} | {nc} | {nt} | {L} | {S} | {lp:.2f}% | {r} | {rng} | {dev:.2f} | {med:.2f} |".format(
                uid=i.unit_id,
                algo=i.algorithm,
                nc=i.n_clusters,
                nt=i.n_total_customers,
                L=i.largest_cluster_count,
                S=i.smallest_cluster_count,
                lp=i.largest_pct_of_total,
                r=("—" if isinstance(i.largest_to_smallest_ratio, float) and pd.isna(i.largest_to_smallest_ratio) else f"{i.largest_to_smallest_ratio:.4f}"),
                rng=i.size_range,
                dev=i.deviation_from_equal_size,
                med=i.median_cluster_size,
            )
        )
    return "\n".join(out) + "\n"


def _noise_table(noise: Sequence[NoiseRow]) -> str:
    if not noise:
        return "_No DBSCAN noise rows._\n"
    out = [
        "| unit_id | algorithm | noise_count | pct_of_total |",
        "|---|---|---|---|",
    ]
    for n in sorted(noise, key=lambda x: x.unit_id):
        out.append(
            f"| {n.unit_id} | {n.algorithm} | {n.noise_count} | {n.pct_of_total:.2f}% |"
        )
    return "\n".join(out) + "\n"


def build_markdown(ctx: ReportContext, out_path: Path) -> Path:
    """Render the Markdown CP-01 report."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# CP-01 — Customer Segment Size & Distribution Analysis\n")
    lines.append(f"_Generated: {now}_\n")
    lines.append("")

    # 1. Executive summary
    lines.append("## 1. Executive Summary\n")
    lines.append(
        "CP-01 phân tích số lượng khách hàng, tỷ lệ, quy mô tương đối và "
        "phân bố cho từng Customer Segment do EPIC-07 sản xuất. Mỗi "
        "analysis unit (algorithm × condition) được báo cáo độc lập; "
        "noise của DBSCAN được tách riêng, không gộp vào segment.\n"
    )
    lines.append("**Thống kê tổng quan:**")
    lines.append("")
    lines.append(f"- Số analysis units: **{ctx.analysis_units_total}**")
    lines.append(f"  - Có per-customer labels parquet: **{ctx.units_with_labels}**")
    lines.append(f"  - Không có (NOT_AVAILABLE): **{ctx.units_without_labels}**")
    lines.append("")
    lines.append(
        "**Phạm vi nghiên cứu:** CP-01 KHÔNG đặt tên segment, KHÔNG so "
        "sánh thuật toán, KHÔNG đưa ra marketing recommendation, KHÔNG "
        "dùng clustering quality metric thay cho size analysis.\n"
    )

    # 2. Inputs and provenance
    lines.append("## 2. Inputs and Provenance\n")
    lines.append(
        "CP-01 đọc cluster assignment artifact của EPIC-07 (EXP-01) và "
        "configuration metadata của EPIC-08 working-selected (EXP-03). "
        "Per-customer labels parquet chỉ tồn tại cho EXP-01; EXP-03 "
        "working-selected labels không được persist (xem `EV03-HP-01`).\n"
    )
    lines.append("| unit_id | algorithm | source_experiment | configuration_id | configuration_status |")
    lines.append("|---|---|---|---|---|")
    for u in ctx.units_metadata:
        lines.append(
            f"| {u['unit_id']} | {u['algorithm']} | {u['source_experiment']} | "
            f"{u['configuration_id']} | {u['configuration_status']} |"
        )
    lines.append("")

    # 3. Per-unit cluster-size results
    lines.append("## 3. Cluster-size Results\n")
    lines.append(_cluster_rows_table(ctx.cluster_rows))

    # 4. Distribution indicators
    lines.append("## 4. Distribution Indicators\n")
    lines.append(
        "Các chỉ báo dưới đây mang tính mô tả. KHÔNG có threshold "
        "\"quá nhỏ / quá lớn\" nào được gán trước — đó là analytical "
        "threshold được người đọc tự quyết sau khi xem dữ liệu.\n"
    )
    lines.append(_indicators_table(ctx.indicators))

    # 5. DBSCAN noise
    lines.append("## 5. DBSCAN Noise Separation\n")
    lines.append(
        "DBSCAN gán nhãn -1 (noise) cho các điểm không thuộc cluster nào. "
        "CP-01 tách noise thành bucket riêng; không gộp vào phân bố "
        "segment, và KHÔNG tự động coi noise là một Customer Segment.\n"
    )
    lines.append(_noise_table(ctx.noise_rows))

    # 6. Visualisation list
    lines.append("## 6. Visualisation\n")
    lines.append(
        "Mỗi analysis unit có per-customer labels được render thành hai "
        "biểu đồ:"
    )
    lines.append("- bar chart (count),")
    lines.append("- bar chart (percentage, denominator = total).")
    lines.append("")
    lines.append("Noise (DBSCAN) được render riêng với hatch khác, không gây hiểu nhầm là segment.")
    lines.append("")
    if any(ctx.artifacts.values()):
        for unit_id, files in ctx.artifacts.items():
            lines.append(f"### {unit_id}")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")
    else:
        lines.append("_No chart artifacts produced for this run._\n")

    # 7. Limitations
    lines.append("## 7. Limitations\n")
    lines.append(
        "1. **EXP-03 working-selected labels không persist.** "
        "Cluster sizes cho EXP-03 working-selected được báo cáo là "
        "`NOT_AVAILABLE`. Số liệu metric (silhouette, DBI, CH) cho các "
        "config này đã có ở EVA-02 / EVA-04; CP-01 chỉ thiếu cluster "
        "size vì per-customer labels không được persist.\n"
    )
    lines.append(
        "2. **DBSCAN K semantics.** K được báo cáo là `n_clusters_realized` "
        "không phải K yêu cầu. CP-01 tách noise riêng; không so sánh "
        "trực tiếp DBSCAN với fixed-K algorithms.\n"
    )
    lines.append(
        "3. **Threshold.** Không có methodology-approved threshold cho "
        "\"cluster quá nhỏ / quá lớn\". Các giá trị trong bảng "
        "Distribution Indicators mang tính mô tả — người đọc tự quyết "
        "định ngưỡng phù hợp (analytical, not research-grade).\n"
    )
    lines.append(
        "4. **Distribution cross-algorithm.** Mỗi analysis unit được "
        "báo cáo độc lập. CP-01 KHÔNG gộp cluster sizes của các "
        "algorithm khác nhau vào một phân bố chung.\n"
    )
    lines.append(
        "5. **Reproducibility.** CP-01 là đọc-thuần trên EXP-01 "
        "parquets. Random seed=42 / rep4 được bảo toàn.\n"
    )

    # 8. Research boundary
    lines.append("## 8. Research Boundary\n")
    lines.append(
        "CP-01 chỉ được kết luận về **quy mô, tỷ lệ, phân bố, relative "
        "size** của customer segments. CP-01 KHÔNG kết luận về:\n"
    )
    lines.append("- giá trị / hành vi của cluster (CP-02/03),")
    lines.append("- đặt tên customer segment (EPIC-09 plan pending),")
    lines.append("- marketing recommendation (out of scope),")
    lines.append("- thuật toán nào tốt nhất (AGENTS.md §2.5; pending `EPIC08-CROSS-ALG-01`).\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


__all__ = ["ReportContext", "build_markdown"]
