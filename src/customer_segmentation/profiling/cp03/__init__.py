"""CP-03 — Cluster Comparison and Distinguishing Feature Analysis.

CP-03 so sánh các Customer Segment trên các feature, xác định feature có
khác biệt quan sát được giữa các cluster, feature có mức khác biệt thấp,
và đánh giá mức overlap/separation giữa các cluster dựa trên evidence.

CP-03 TÁI SỬ DỤNG trực tiếp các hàm từ CP-02 (feature profiling,
relative comparison, behavioural interpretation) để đảm bảo consistency
và tránh duplicate statistics. CP-03 chỉ derive thêm các indicators mới
cho mục tiêu comparison.

Hard constraints (AGENTS.md §2):
- Read-only đối với EXP-01 / EXP-03 / FE-05 / FE-06 / CP-01 / CP-02 outputs.
- KHÔNG ranking algorithm / cluster.
- KHÔNG đặt tên Customer Segment ("Champions", "VIP", "Loyal", ...).
- KHÔNG đưa ra Marketing Recommendation.
- KHÔNG tạo overall "best / winner / optimal / recommended" claim.
- KHÔNG gộp cluster labels giữa các algorithm / condition khác nhau.
- KHÔNG tạo composite scoring / ranking framework để xếp hạng
  distinguishing features — chỉ dùng analytical classification với
  threshold được đánh dấu rõ là ``WORKING_ANALYTICAL_THRESHOLD``.
- DBSCAN noise tách riêng; KHÔNG coi noise là Customer Segment;
  KHÔNG dùng noise để tạo kết luận về segment.
- EXP-03 working-selected profiles = ``NOT_AVAILABLE`` (theo CP-01/CP-02).
- Sử dụng RAW interpretable feature values — KHÔNG dùng Yeo-Johnson +
  RobustScaler values để diễn giải business.

Submodules
----------
- :mod:`customer_segmentation.profiling.cp03.provenance`
    Re-export CP-02 analysis units and helpers.
- :mod:`customer_segmentation.profiling.cp03.comparison`
    Build the segment comparison matrix (per unit, cluster, feature).
- :mod:`customer_segmentation.profiling.cp03.difference_analysis`
    Per-(unit, feature) distinguishing indicators + analytical classification.
- :mod:`customer_segmentation.profiling.cp03.overlap_analysis`
    Pairwise IQR overlap between clusters, plus IQR overlap with OVERALL.
- :mod:`customer_segmentation.profiling.cp03.visualization`
    Violin plots, distinguishing-feature heatmaps, IQR-overlap heatmaps.
- :mod:`customer_segmentation.profiling.cp03.report`
    Markdown report builder.
- :mod:`customer_segmentation.profiling.cp03.runner`
    Top-level orchestration.
"""

from customer_segmentation.profiling.cp03.comparison import (
    Cp03ComparisonRow,
    compute_segment_comparison_matrix,
)
from customer_segmentation.profiling.cp03.difference_analysis import (
    WORKING_HIGH_DIFFERENCE_EFFECT_PCT,
    WORKING_HIGH_OVERLAP_MEAN,
    WORKING_LOW_DIFFERENCE_EFFECT_PCT,
    WORKING_MODERATE_OVERLAP_MEAN,
    Cp03DistinguishingRow,
    classify_distinguishing_feature,
    compute_distinguishing_feature_table,
)
from customer_segmentation.profiling.cp03.overlap_analysis import (
    Cp03OverlapRow,
    compute_pairwise_overlap_table,
    compute_population_overlap_lookup,
)
from customer_segmentation.profiling.cp03.provenance import (
    build_cp03_analysis_units,
)
from customer_segmentation.profiling.cp03.report import (
    Cp03ReportContext,
    build_cp03_markdown,
)
from customer_segmentation.profiling.cp03.runner import (
    DEFAULT_OUTPUT_DIR,
    Cp03Runner,
    run_cp03,
)
from customer_segmentation.profiling.cp03.visualization import (
    render_all_cp03_charts,
    render_distinguishing_heatmap,
    render_iqr_overlap_heatmap,
    render_violin_plot,
)

__all__ = [
    # Runner
    "Cp03Runner",
    "run_cp03",
    "DEFAULT_OUTPUT_DIR",
    # Provenance
    "build_cp03_analysis_units",
    # Comparison
    "Cp03ComparisonRow",
    "compute_segment_comparison_matrix",
    # Difference analysis
    "Cp03DistinguishingRow",
    "classify_distinguishing_feature",
    "compute_distinguishing_feature_table",
    "WORKING_HIGH_DIFFERENCE_EFFECT_PCT",
    "WORKING_LOW_DIFFERENCE_EFFECT_PCT",
    "WORKING_HIGH_OVERLAP_MEAN",
    "WORKING_MODERATE_OVERLAP_MEAN",
    # Overlap analysis
    "Cp03OverlapRow",
    "compute_pairwise_overlap_table",
    "compute_population_overlap_lookup",
    # Visualisation
    "render_violin_plot",
    "render_distinguishing_heatmap",
    "render_iqr_overlap_heatmap",
    "render_all_cp03_charts",
    # Report
    "Cp03ReportContext",
    "build_cp03_markdown",
]
