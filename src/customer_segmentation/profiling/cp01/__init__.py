"""CP-01 — Customer Segment Size & Distribution Analysis.

Phân tích số lượng / tỷ lệ / quy mô / phân bố của các Customer Segments
do EPIC-07 algorithms sản xuất, với phân biệt rõ DBSCAN noise so với
customer segment thực sự.

Hard constraints (AGENTS.md §2):
- Read-only đối với EXP-01 / EXP-03 / EVA-01 outputs.
- Không ranking / "best / winner / optimal / recommended" labels.
- Không đặt tên Customer Segment ("Champions", "VIP", ...).
- Không đưa ra Marketing recommendation.
- Không dùng clustering quality metrics thay thế cho size analysis.
- KHÔNG gộp noise vào customer segment distribution.

Submodules
----------
- :mod:`customer_segmentation.profiling.cp01.provenance`
    Resolution of analysis units từ EXP-01 / EXP-03 source artefacts.
- :mod:`customer_segmentation.profiling.cp01.size_analysis`
    Per-(unit, cluster) cluster size analysis.
- :mod:`customer_segmentation.profiling.cp01.distribution`
    Distribution indicators (largest / smallest / range / ratio...).
- :mod:`customer_segmentation.profiling.cp01.visualization`
    Bar-chart visualisation cho mỗi analysis unit.
- :mod:`customer_segmentation.profiling.cp01.report`
    Markdown report builder.
- :mod:`customer_segmentation.profiling.cp01.runner`
    Top-level orchestration.
"""

from customer_segmentation.profiling.cp01.runner import (
    Cp01Runner,
    run_cp01,
)
from customer_segmentation.profiling.cp01.size_analysis import (
    ClusterSizeRow,
    NoiseRow,
    compute_cluster_size_table,
    compute_noise_summary,
)
from customer_segmentation.profiling.cp01.distribution import (
    DistributionIndicators,
    compute_distribution_indicators,
)
from customer_segmentation.profiling.cp01.provenance import (
    AnalysisUnit,
    build_analysis_units,
)

__all__ = [
    # Runner
    "Cp01Runner",
    "run_cp01",
    # Provenance
    "AnalysisUnit",
    "build_analysis_units",
    # Size analysis
    "ClusterSizeRow",
    "NoiseRow",
    "compute_cluster_size_table",
    "compute_noise_summary",
    # Distribution
    "DistributionIndicators",
    "compute_distribution_indicators",
]
