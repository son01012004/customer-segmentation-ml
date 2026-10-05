"""Project-wide configuration loaders.

The :mod:`.loader` module is the only entry point that reads
``configs/preprocessing.yaml`` and produces a typed configuration for
the rest of the pipeline.

:mod:`.outlier_loader` reads ``configs/outlier.yaml`` (FE-03).
"""

from customer_segmentation.config.loader import (
    DEFAULT_PREPROCESSING_CONFIG_PATH,
    KEY_ANNOTATIONS,
    STATUS_PENDING_MENTOR_REVIEW,
    STATUS_WORKING_ASSUMPTION,
    VALID_STATUSES,
    ConfigAnnotation,
    PreprocessingConfigError,
    find_default_preprocessing_config_path,
    load_preprocessing_config,
    preprocessing_config_to_dict,
    resolve_preprocessing_config_path,
)
from customer_segmentation.config.outlier_loader import (
    DEFAULT_OUTLIER_CONFIG_PATH,
    KEY_ANNOTATIONS_OUTLIER,
    OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
    OUTLIER_STATUS_WORKING_ASSUMPTION,
    OUTLIER_VALID_AGGREGATIONS,
    OUTLIER_VALID_DETECTIONS,
    OUTLIER_VALID_FILTER_MODES,
    OUTLIER_VALID_STATUSES,
    OUTLIER_VALID_TREATMENTS,
    CustomerAggregationConfig,
    CustomerDiagnosticConfig,
    FeatureOutlierConfig,
    FilterModeConfig,
    OutlierAnalysisConfig,
    OutlierConfigError,
    OutputConfig,
    SensitivityConfig,
    SourceConfig,
    find_default_outlier_config_path,
    load_outlier_config,
    outlier_config_to_dict,
    resolve_outlier_config_path,
)

__all__ = [
    "DEFAULT_OUTLIER_CONFIG_PATH",
    "DEFAULT_PREPROCESSING_CONFIG_PATH",
    "ConfigAnnotation",
    "CustomerAggregationConfig",
    "CustomerDiagnosticConfig",
    "FeatureOutlierConfig",
    "FilterModeConfig",
    "KEY_ANNOTATIONS",
    "KEY_ANNOTATIONS_OUTLIER",
    "OUTLIER_STATUS_PENDING_MENTOR_REVIEW",
    "OUTLIER_STATUS_WORKING_ASSUMPTION",
    "OUTLIER_VALID_AGGREGATIONS",
    "OUTLIER_VALID_DETECTIONS",
    "OUTLIER_VALID_FILTER_MODES",
    "OUTLIER_VALID_STATUSES",
    "OUTLIER_VALID_TREATMENTS",
    "OutlierAnalysisConfig",
    "OutlierConfigError",
    "OutputConfig",
    "PreprocessingConfigError",
    "SensitivityConfig",
    "SourceConfig",
    "STATUS_PENDING_MENTOR_REVIEW",
    "STATUS_WORKING_ASSUMPTION",
    "VALID_STATUSES",
    "find_default_outlier_config_path",
    "find_default_preprocessing_config_path",
    "load_outlier_config",
    "load_preprocessing_config",
    "outlier_config_to_dict",
    "preprocessing_config_to_dict",
    "resolve_outlier_config_path",
    "resolve_preprocessing_config_path",
]
