"""Chart modules for DEV-08 Prototype Visualization.

Each chart module exposes:
- A ``plot_*`` function (matplotlib output)
- A ``format_*`` function (text/JSON output for CLI)
- A ``get_*_color`` helper (single source; per AGENTS.md §3)

Charts must import ``DEFAULT_COLOR_PALETTE`` from
``customer_segmentation.prototype.visualization.scope`` — never
hard-code colours inline (AGENTS.md §3 Visualization guardrail).

Chart modules
-------------
- ``cluster_distribution`` — segment-size bar chart + text table
  (Task 1.2)
- ``segment_profile`` — per-segment profile text table (Task 1.3)
- ``feature_comparison`` — feature × segment heatmap / bar chart
  + text table (Task 1.4)
- ``metric_comparison`` — evaluation-metric comparison across
  one or more ``EvaluationManifest`` (Task 1.5)
- ``marketing_placeholder`` — REVIEW_REQUIRED banner (later task)
"""

from __future__ import annotations

from customer_segmentation.prototype.visualization.charts.cluster_distribution import (
    format_cluster_distribution_table,
    get_segment_color,
    plot_cluster_distribution,
)
from customer_segmentation.prototype.visualization.charts.feature_comparison import (
    extract_statistic_matrix,
    format_feature_comparison_table,
    format_statistic_value,
    get_feature_color,
    is_numerical_statistic,
    plot_feature_bars,
    plot_feature_heatmap,
)
from customer_segmentation.prototype.visualization.charts.marketing_placeholder import (
    AVAILABLE_PLACEHOLDER,
    NOT_AVAILABLE_PLACEHOLDER,
    REVIEW_REQUIRED_PLACEHOLDER,
    format_marketing_placeholder,
    is_marketing_placeholder_visible,
)
from customer_segmentation.prototype.visualization.charts.metric_comparison import (
    extract_metric_matrix,
    format_metric_comparison_table,
    format_metric_status_block,
    format_metric_value,
    format_run_identifier,
    get_algorithm_color,
    is_metric_value,
    plot_metric_comparison,
)
from customer_segmentation.prototype.visualization.charts.segment_profile import (
    collect_segment_characteristics,
    format_characteristic_entry,
    format_segment_profile_table,
)

__all__ = [
    # Cluster distribution
    "get_segment_color",
    "format_cluster_distribution_table",
    "plot_cluster_distribution",
    # Segment profile
    "format_segment_profile_table",
    "format_characteristic_entry",
    "collect_segment_characteristics",
    # Feature comparison
    "get_feature_color",
    "is_numerical_statistic",
    "format_statistic_value",
    "extract_statistic_matrix",
    "format_feature_comparison_table",
    "plot_feature_heatmap",
    "plot_feature_bars",
    # Metric comparison
    "get_algorithm_color",
    "is_metric_value",
    "format_metric_value",
    "format_metric_status_block",
    "format_run_identifier",
    "extract_metric_matrix",
    "format_metric_comparison_table",
    "plot_metric_comparison",
    # Marketing placeholder (Phase A: REVIEW_REQUIRED only)
    "REVIEW_REQUIRED_PLACEHOLDER",
    "NOT_AVAILABLE_PLACEHOLDER",
    "AVAILABLE_PLACEHOLDER",
    "format_marketing_placeholder",
    "is_marketing_placeholder_visible",
]
