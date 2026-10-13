"""Prototype-layer visualization package for DEV-08.

This package provides prototype-layer visualization capability for
downstream prototype DEVs (DEV-09 → reporting). It consumes
SegmentationManifest and EvaluationManifest artefacts produced by
DEV-06 and DEV-05 and renders cluster-distribution, feature-comparison,
segment-profile, and metric-comparison charts.

The package is **the prototype layer**. It does not change research
methodology and does not modify any research artefact. Charts read
from manifest schemas; no new clustering experiments or metric
recomputations are performed.

Task 1.1 (this file) establishes the package foundation:
- ``VISUALIZATION_SCHEMA_VERSION``
- ``DEFAULT_COLOR_PALETTE`` (single colour source; per AGENTS.md §3)
- ``VisualizationError``
- ``BANNED_SUBSTRINGS`` / ``DEFAULT_DISCLAIMER_TEXT`` (display discipline)

Task 1.2 adds the cluster distribution chart:
- ``get_segment_color``
- ``format_cluster_distribution_table``
- ``plot_cluster_distribution``

Task 1.3 adds the segment profile table:
- ``format_segment_profile_table``
- ``format_characteristic_entry``
- ``collect_segment_characteristics``

Task 1.4 adds the feature comparison chart:
- ``get_feature_color``
- ``is_numerical_statistic``
- ``format_statistic_value``
- ``extract_statistic_matrix``
- ``format_feature_comparison_table``
- ``plot_feature_heatmap``
- ``plot_feature_bars``

Task 1.5 adds the metric comparison chart:
- ``get_algorithm_color``
- ``is_metric_value``
- ``format_metric_value``
- ``format_metric_status_block``
- ``format_run_identifier``
- ``extract_metric_matrix``
- ``format_metric_comparison_table``
- ``plot_metric_comparison``

Chart modules (``marketing_placeholder``) will be added in later tasks.

Public API is re-exported at the bottom; anything not listed is internal.
"""

from __future__ import annotations

from customer_segmentation.prototype.visualization.charts import (
    AVAILABLE_PLACEHOLDER,
    NOT_AVAILABLE_PLACEHOLDER,
    REVIEW_REQUIRED_PLACEHOLDER,
    collect_segment_characteristics,
    extract_metric_matrix,
    extract_statistic_matrix,
    format_characteristic_entry,
    format_cluster_distribution_table,
    format_feature_comparison_table,
    format_marketing_placeholder,
    format_metric_comparison_table,
    format_metric_status_block,
    format_metric_value,
    format_run_identifier,
    format_segment_profile_table,
    format_statistic_value,
    get_algorithm_color,
    get_feature_color,
    get_segment_color,
    is_marketing_placeholder_visible,
    is_metric_value,
    is_numerical_statistic,
    plot_cluster_distribution,
    plot_feature_bars,
    plot_feature_heatmap,
    plot_metric_comparison,
)
from customer_segmentation.prototype.visualization.config_loader import (
    DEFAULT_DEV08_CONFIG_PATH,
    DEV08_CONFIG_TOP_KEY,
    Dev08Config,
    Dev08DisplayConfig,
    Dev08LoggingConfig,
    Dev08ResearchSafetyConfig,
    Dev08StorageConfig,
    find_default_dev08_config_path,
    load_dev08_config,
)
from customer_segmentation.prototype.visualization.dashboard import (
    CLUSTER_VISUALIZATION_BLOCKED_NOTE,
    DASHBOARD_CHARTS,
    DashboardGenerator,
    build_dashboard_result,
)
from customer_segmentation.prototype.visualization.display import (
    DEFAULT_DISCLAIMER_TEXT as _DISPLAY_DEFAULT_DISCLAIMER_TEXT,
)
from customer_segmentation.prototype.visualization.display import (
    DashboardChartRecord,
    DashboardResult,
    dashboard_result_to_dict,
    dashboard_result_to_json,
    format_dashboard_run_report,
    format_dashboard_section_header,
    format_dashboard_summary,
    now_utc_iso,
)
from customer_segmentation.prototype.visualization.display import (
    check_no_banned_substrings as display_check_no_banned_substrings,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationConfigError,
    VisualizationError,
    VisualizationInputError,
    VisualizationStoragePathError,
)
from customer_segmentation.prototype.visualization.loaders import (
    load_evaluation_manifest,
    load_marketing_manifest,
    load_segmentation_manifest,
)
from customer_segmentation.prototype.visualization.logging_config import (
    DEV08_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.visualization.pipeline import (
    LIFECYCLE_CACHED,
    LIFECYCLE_FAILED,
    LIFECYCLE_SUCCESS,
    VisualizationPipelineResult,
    compute_environment_block,
    run_visualization_pipeline,
)
from customer_segmentation.prototype.visualization.scope import (
    BANNED_SUBSTRINGS,
    BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER,
    DEFAULT_COLOR_PALETTE,
    DEFAULT_DISCLAIMER_TEXT,
    NOISE_COLOR,
    VISUALIZATION_SCHEMA_VERSION,
)
from customer_segmentation.prototype.visualization.storage import (
    CANONICAL_PAYLOAD_KEYS,
    DASHBOARD_ID_PREFIX,
    compute_config_sha256,
    derive_dashboard_id,
    prototype_visualization_base_dir,
    prototype_visualization_run_dir,
)
from customer_segmentation.prototype.visualization.storage import (
    resolve_storage_root as resolve_visualization_storage_root,
)

__all__ = [
    # Scope / constants
    "VISUALIZATION_SCHEMA_VERSION",
    "DEFAULT_COLOR_PALETTE",
    "NOISE_COLOR",
    # Display discipline
    "BANNED_SUBSTRINGS",
    "BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER",
    "DEFAULT_DISCLAIMER_TEXT",
    # Errors
    "VisualizationError",
    "VisualizationStoragePathError",
    "VisualizationInputError",
    "VisualizationConfigError",
    # Charts — cluster distribution (Task 1.2)
    "get_segment_color",
    "format_cluster_distribution_table",
    "plot_cluster_distribution",
    # Charts — segment profile (Task 1.3)
    "format_segment_profile_table",
    "format_characteristic_entry",
    "collect_segment_characteristics",
    # Charts — feature comparison (Task 1.4)
    "get_feature_color",
    "is_numerical_statistic",
    "format_statistic_value",
    "extract_statistic_matrix",
    "format_feature_comparison_table",
    "plot_feature_heatmap",
    "plot_feature_bars",
    # Charts — metric comparison (Task 1.5)
    "get_algorithm_color",
    "is_metric_value",
    "format_metric_value",
    "format_metric_status_block",
    "format_run_identifier",
    "extract_metric_matrix",
    "format_metric_comparison_table",
    "plot_metric_comparison",
    # Charts — marketing placeholder (Task 1.6)
    "REVIEW_REQUIRED_PLACEHOLDER",
    "NOT_AVAILABLE_PLACEHOLDER",
    "AVAILABLE_PLACEHOLDER",
    "format_marketing_placeholder",
    "is_marketing_placeholder_visible",
    # Dashboard orchestrator (Task 1.6)
    "DASHBOARD_CHARTS",
    "CLUSTER_VISUALIZATION_BLOCKED_NOTE",
    "DashboardGenerator",
    "build_dashboard_result",
    # Pipeline (Task 1.6)
    "LIFECYCLE_CACHED",
    "LIFECYCLE_SUCCESS",
    "LIFECYCLE_FAILED",
    "VisualizationPipelineResult",
    "compute_environment_block",
    "run_visualization_pipeline",
    # Loaders (Task 1.6)
    "load_segmentation_manifest",
    "load_evaluation_manifest",
    "load_marketing_manifest",
    # Storage (Task 1.6)
    "DASHBOARD_ID_PREFIX",
    "CANONICAL_PAYLOAD_KEYS",
    "compute_config_sha256",
    "derive_dashboard_id",
    "prototype_visualization_base_dir",
    "prototype_visualization_run_dir",
    "resolve_visualization_storage_root",
    # Logging (Task 1.6)
    "DEV08_LOGGER_NAME",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "get_logger",
    # Config (Task 1.6)
    "DEFAULT_DEV08_CONFIG_PATH",
    "DEV08_CONFIG_TOP_KEY",
    "Dev08Config",
    "Dev08DisplayConfig",
    "Dev08StorageConfig",
    "Dev08LoggingConfig",
    "Dev08ResearchSafetyConfig",
    "find_default_dev08_config_path",
    "load_dev08_config",
    # Display helpers (Task 1.6)
    "DashboardChartRecord",
    "DashboardResult",
    "dashboard_result_to_dict",
    "dashboard_result_to_json",
    "format_dashboard_run_report",
    "format_dashboard_section_header",
    "format_dashboard_summary",
    "display_check_no_banned_substrings",
    "now_utc_iso",
]
