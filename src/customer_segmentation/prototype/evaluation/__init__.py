"""Prototype-layer evaluation package for DEV-05.

This package provides prototype-layer evaluation capability for
downstream prototype DEVs (DEV-06 → DEV-09). It wraps the 3 internal
sklearn metrics (``silhouette_score``, ``davies_bouldin_score``,
``calinski_harabasz_score``) and adds per-stage pipeline driver,
manifest, and storage helpers.

The package is **the prototype layer**. It does not change research
methodology and does not modify any research artefact.

Public API (re-exported at the bottom; anything not listed is internal).
"""

from __future__ import annotations

from customer_segmentation.prototype.evaluation.compare import (
    DEFAULT_COMPARISON_DISCLAIMER,
    ComparisonGroup,
    ComparisonReport,
    CompatibilityKey,
    IncompatibilityReason,
    compare_evaluations,
)
from customer_segmentation.prototype.evaluation.config_loader import (
    DEFAULT_DEV05_CONFIG_PATH,
    DEV05_CONFIG_TOP_KEY,
    Dev05CompareConfig,
    Dev05Config,
    Dev05ConfigError,
    Dev05DisplayConfig,
    Dev05LoggingConfig,
    Dev05MetricsConfig,
    Dev05NoisePolicyConfig,
    Dev05ResearchSafetyConfig,
    Dev05StorageConfig,
    Dev05ValidationConfig,
    VALID_LOG_LEVELS,
    find_default_dev05_config_path,
    load_dev05_config,
)
from customer_segmentation.prototype.evaluation.display import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
    check_no_banned_substrings,
    format_manifest_path,
    format_metrics_table,
)
from customer_segmentation.prototype.evaluation.logging_config import (
    DEV05_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.evaluation.manifest import (
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationManifestError,
    EvaluationMetricEntry,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    InputIdentityBlock,
    ResearchSafetyBlock,
    ValidationCheck,
    build_evaluation_manifest,
    make_computation_error_entry,
    make_missing_entry,
    make_not_applicable_entry,
    make_valid_entry,
    manifest_to_dict,
    now_utc_iso,
    read_evaluation_manifest,
    runtime_field_names,
    stable_field_names,
    write_evaluation_manifest,
)
from customer_segmentation.prototype.evaluation.metrics import (
    DBSCAN_NOISE_LABEL,
    compute_internal_metrics,
)
from customer_segmentation.prototype.evaluation.pipeline import (
    EvaluationPipelineResult,
    run_evaluation_pipeline,
)
from customer_segmentation.prototype.evaluation.scope import (
    DEFAULT_METRIC_SET,
    DEFAULT_NOISE_POLICY,
    EVALUATED_SCOPES,
    EvaluatedScope,
    METRIC_NAMES,
    METRIC_REASONS,
    METRIC_REASON_BY_STATUS,
    METRIC_STATUSES,
    MetricName,
    MetricReason,
    MetricStatus,
    NOISE_POLICIES,
    NoisePolicy,
)
from customer_segmentation.prototype.evaluation.storage import (
    EVALUATION_ID_HEX_LEN,
    EVALUATION_ID_PREFIX,
    Dev05CollisionError,
    Dev05ManifestCorrupt,
    Dev05StoragePathError,
    compute_config_sha256,
    compute_metric_set_hash,
    derive_evaluation_id,
    find_existing_evaluation,
    prototype_evaluation_base_dir,
    prototype_evaluation_run_dir,
    resolve_storage_root,
)

__all__ = [
    # Config
    "DEFAULT_DEV05_CONFIG_PATH",
    "DEV05_CONFIG_TOP_KEY",
    "Dev05CompareConfig",
    "Dev05Config",
    "Dev05ConfigError",
    "Dev05DisplayConfig",
    "Dev05LoggingConfig",
    "Dev05MetricsConfig",
    "Dev05NoisePolicyConfig",
    "Dev05ResearchSafetyConfig",
    "Dev05StorageConfig",
    "Dev05ValidationConfig",
    "VALID_LOG_LEVELS",
    "find_default_dev05_config_path",
    "load_dev05_config",
    # Scope
    "DEFAULT_METRIC_SET",
    "DEFAULT_NOISE_POLICY",
    "EVALUATED_SCOPES",
    "EvaluatedScope",
    "MetricName",
    "METRIC_NAMES",
    "METRIC_REASONS",
    "METRIC_REASON_BY_STATUS",
    "METRIC_STATUSES",
    "MetricReason",
    "MetricStatus",
    "NOISE_POLICIES",
    "NoisePolicy",
    # Storage
    "EVALUATION_ID_HEX_LEN",
    "EVALUATION_ID_PREFIX",
    "Dev05CollisionError",
    "Dev05ManifestCorrupt",
    "Dev05StoragePathError",
    "compute_config_sha256",
    "compute_metric_set_hash",
    "derive_evaluation_id",
    "find_existing_evaluation",
    "prototype_evaluation_base_dir",
    "prototype_evaluation_run_dir",
    "resolve_storage_root",
    # Manifest
    "EVALUATION_MANIFEST_SCHEMA_VERSION",
    "EnvironmentBlock",
    "EvaluationManifest",
    "EvaluationManifestError",
    "EvaluationMetricEntry",
    "EvaluationMetricsResult",
    "EvaluationValidationReport",
    "InputIdentityBlock",
    "ResearchSafetyBlock",
    "ValidationCheck",
    "build_evaluation_manifest",
    "make_computation_error_entry",
    "make_missing_entry",
    "make_not_applicable_entry",
    "make_valid_entry",
    "manifest_to_dict",
    "now_utc_iso",
    "read_evaluation_manifest",
    "runtime_field_names",
    "stable_field_names",
    "write_evaluation_manifest",
    # Metrics
    "DBSCAN_NOISE_LABEL",
    "compute_internal_metrics",
    # Pipeline
    "EvaluationPipelineResult",
    "run_evaluation_pipeline",
    # Logging
    "DEV05_LOGGER_NAME",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "get_logger",
    # Display
    "BANNED_SUBSTRINGS",
    "DEFAULT_DISCLAIMER_TEXT",
    "check_no_banned_substrings",
    "format_manifest_path",
    "format_metrics_table",
    # Compare
    "DEFAULT_COMPARISON_DISCLAIMER",
    "ComparisonGroup",
    "ComparisonReport",
    "CompatibilityKey",
    "IncompatibilityReason",
    "compare_evaluations",
]
