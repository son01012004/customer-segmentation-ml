"""CP-02 — Per-Cluster Feature Profile & Behavioural Analysis.

CP-02 phân tích đặc trưng và hành vi của từng Customer Segment, dựa trên
analysis units đã được CP-01 xác định (algorithm × condition).

Hard constraints (AGENTS.md §2):
- Read-only đối với EXP-01 / EXP-03 / FE-05 / FE-06 outputs.
- KHÔNG ranking / "best / winner / optimal / recommended" labels.
- KHÔNG đặt tên Customer Segment ("Champions", "VIP", "Loyal", ...).
- KHÔNG đưa ra Marketing recommendation.
- Sử dụng RAW interpretable feature values
  (``data/processed/customer_candidates.parquet``) — KHÔNG dùng
  transformed / Yeo-Johnson / RobustScaler values cho diễn giải
  business.
- DBSCAN noise tách riêng, không gộp vào segment profiling.
- Mỗi analysis unit báo cáo độc lập — KHÔNG merge labels từ nhiều
  algorithm.
- Behavioural interpretation phải dùng ngôn ngữ mô tả tương đối
  ("cao hơn tương đối", "có xu hướng", ...), không claim tuyệt đối.

Submodules
----------
- :mod:`customer_segmentation.profiling.cp02.provenance`
    Load cluster labels + RAW customer features + align by CustomerID.
- :mod:`customer_segmentation.profiling.cp02.feature_profiling`
    Per-(unit, cluster, feature) statistics: count, mean, median,
    P25, P75, min, max.
- :mod:`customer_segmentation.profiling.cp02.relative_comparison`
    Relative difference vs overall population reference (median,
    mean).
- :mod:`customer_segmentation.profiling.cp02.behavioral_interpretation`
    Heuristic interpretation text per cluster per feature.
- :mod:`customer_segmentation.profiling.cp02.visualization`
    Boxplots, distribution plots, per-(cluster, feature) plots.
- :mod:`customer_segmentation.profiling.cp02.report`
    Markdown report builder.
- :mod:`customer_segmentation.profiling.cp02.runner`
    Top-level orchestration.
"""

from customer_segmentation.profiling.cp02.behavioral_interpretation import (
    BehavioralInterpretationRow,
    compute_behavioral_interpretation_table,
    interpret_feature_for_cluster,
)
from customer_segmentation.profiling.cp02.feature_profiling import (
    FeatureProfileRow,
    compute_feature_profile_table,
    compute_overall_feature_summary,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    RAW_FEATURES_PATH,
    Cp02AnalysisUnit,
    build_cp02_analysis_units,
    load_raw_customer_features,
)
from customer_segmentation.profiling.cp02.relative_comparison import (
    RelativeComparisonRow,
    compute_relative_comparison_table,
)
from customer_segmentation.profiling.cp02.report import (
    Cp02ReportContext,
    build_cp02_markdown,
)
from customer_segmentation.profiling.cp02.runner import (
    DEFAULT_OUTPUT_DIR,
    Cp02Runner,
    run_cp02,
)
from customer_segmentation.profiling.cp02.visualization import (
    render_all_cp02_charts,
    render_boxplot,
    render_relative_heatmap,
)

__all__ = [
    # Runner
    "Cp02Runner",
    "run_cp02",
    "DEFAULT_OUTPUT_DIR",
    # Provenance
    "Cp02AnalysisUnit",
    "build_cp02_analysis_units",
    "load_raw_customer_features",
    "FEATURE_COLUMNS",
    "RAW_FEATURES_PATH",
    # Feature profiling
    "FeatureProfileRow",
    "compute_feature_profile_table",
    "compute_overall_feature_summary",
    # Relative comparison
    "RelativeComparisonRow",
    "compute_relative_comparison_table",
    # Behavioural interpretation
    "BehavioralInterpretationRow",
    "interpret_feature_for_cluster",
    "compute_behavioral_interpretation_table",
    # Visualisation
    "render_boxplot",
    "render_relative_heatmap",
    "render_all_cp02_charts",
    # Report
    "Cp02ReportContext",
    "build_cp02_markdown",
]
