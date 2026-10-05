"""Feature transformation utilities: imputation, skewness correction, scaling, pipelines.

FE-06 (Plan V2)
=================

Modules
-------
config_loader          - Load configs/transformation.yaml
fill_strategy          - NaN imputation (median)
skewness               - Transformation: none / log1p / yeo_johnson
scaling                - Scaling: none / standard / minmax / robust
feature_eligibility    - Feature eligibility gate
validators             - Final matrix validation
analysis               - Distribution, correlation, outlier, redundancy analysis
redundancy_analysis    - 3-category redundancy classification (FE-06 v1.1)
imputation_semantics   - Structural vs data-quality NaN distinction
versioning             - SHA-256 and dataset version
report                 - Report generation
pipeline               - End-to-end FE-06 pipeline

Working configuration (C7):
  - imputation: median for PurchaseIntervalMean, PurchaseIntervalStd
  - transformation: yeo_johnson for ALL 14 eligible features
  - scaling: robust for ALL 14 eligible features
  - Status: WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING
  - Dataset version: FE06-v1.0
  - Dataset status: TECHNICALLY_GENERATED (NOT RESEARCH_APPROVED_FINAL)

Hard constraints (Plan V2):
- CustomerID NEVER in clustering matrix
- No clustering, no evaluation, no tuning
- No "best/recommended/optimal" claim
- Redundancy is DIAGNOSTIC ONLY — no auto-drop, no scoring, no ranking
- Pipeline deterministic (random_seed = null)
- Input SHA-256 verified before/after
"""

from customer_segmentation.transformation.analysis import (
    CorrelationResult,
    DistributionResult,
    OutlierResult,
    RedundancyResult,
    compute_correlation_matrices,
    compute_distribution_stats,
    detect_outliers,
    detect_redundancy,
)
from customer_segmentation.transformation.config_loader import (
    DEFAULT_TRANSFORMATION_CONFIG_PATH,
    ScalingMethod,
    TransformationConfig,
    TransformationConfigError,
    TransformationMethod,
    TransformationStatus,
    load_transformation_config,
    resolve_transformation_config_path,
)
from customer_segmentation.transformation.feature_eligibility import (
    EligibilityResult,
    EligibilityStatus,
    FeatureEligibility,
    apply_feature_eligibility,
)
from customer_segmentation.transformation.fill_strategy import (
    ImputationResult,
    apply_imputation,
    impute_median,
)
from customer_segmentation.transformation.imputation_semantics import (
    SEMANTICS_DATA_QUALITY,
    SEMANTICS_STRUCTURAL,
    SEMANTICS_UNKNOWN,
    FeatureImputationSemantics,
    ImputationSemanticsResult,
    analyze_imputation_semantics,
)
from customer_segmentation.transformation.pipeline import (
    FE06PipelineResult,
    run_fe06_pipeline,
)
from customer_segmentation.transformation.redundancy_analysis import (
    FEATURE_DEFINITIONS,
    REDUNDANCY_DISTINCT_BUT_RELATED,
    REDUNDANCY_DUPLICATE,
    REDUNDANCY_HIGH_CORRELATION,
    REDUNDANCY_PENDING_REVIEW,
    RedundancyAnalysisResult,
    RedundancyCategory,
    RedundancyPair,
    analyze_redundancy_pair,
    analyze_redundancy_pairs,
)
from customer_segmentation.transformation.report import (
    write_comparison_matrix,
    write_fe06_reports,
    write_narrative_report,
)
from customer_segmentation.transformation.scaling import (
    ScalingResult,
    apply_scaling,
    scale_features,
)
from customer_segmentation.transformation.skewness import (
    SkewMethod,
    TransformationResult,
    apply_log1p,
    apply_none,
    apply_transformation,
    apply_yeo_johnson,
)
from customer_segmentation.transformation.validators import (
    FinalMatrixValidationResult,
    ValidationCheck,
    check_all_numeric,
    check_customer_metadata_alignment,
    check_metadata_alignment,
    check_no_constant_features,
    check_no_identifier_in_matrix,
    check_no_inf,
    check_no_nan,
    check_row_count,
    validate_final_matrix,
)
from customer_segmentation.transformation.versioning import (
    FE06_VERSION,
    compute_df_sha256,
    compute_file_sha256,
    compute_sha256,
)

__all__ = [
    # config_loader
    "DEFAULT_TRANSFORMATION_CONFIG_PATH",
    "TransformationConfig",
    "TransformationConfigError",
    "TransformationMethod",
    "TransformationStatus",
    "ScalingMethod",
    "load_transformation_config",
    "resolve_transformation_config_path",
    # fill_strategy
    "ImputationResult",
    "apply_imputation",
    "impute_median",
    # skewness
    "SkewMethod",
    "TransformationResult",
    "apply_none",
    "apply_log1p",
    "apply_yeo_johnson",
    "apply_transformation",
    # scaling
    "ScalingResult",
    "scale_features",
    "apply_scaling",
    # feature_eligibility
    "EligibilityStatus",
    "EligibilityResult",
    "FeatureEligibility",
    "apply_feature_eligibility",
    # validators
    "ValidationCheck",
    "FinalMatrixValidationResult",
    "check_row_count",
    "check_no_nan",
    "check_no_inf",
    "check_no_constant_features",
    "check_all_numeric",
    "check_no_identifier_in_matrix",
    "check_metadata_alignment",
    "check_customer_metadata_alignment",
    "validate_final_matrix",
    # analysis
    "DistributionResult",
    "CorrelationResult",
    "OutlierResult",
    "RedundancyResult",
    "compute_distribution_stats",
    "compute_correlation_matrices",
    "detect_outliers",
    "detect_redundancy",
    # redundancy_analysis (FE-06 v1.1)
    "RedundancyPair",
    "RedundancyAnalysisResult",
    "RedundancyCategory",
    "REDUNDANCY_DUPLICATE",
    "REDUNDANCY_HIGH_CORRELATION",
    "REDUNDANCY_DISTINCT_BUT_RELATED",
    "REDUNDANCY_PENDING_REVIEW",
    "FEATURE_DEFINITIONS",
    "analyze_redundancy_pair",
    "analyze_redundancy_pairs",
    # imputation_semantics (FE-06 v1.1)
    "SEMANTICS_STRUCTURAL",
    "SEMANTICS_DATA_QUALITY",
    "SEMANTICS_UNKNOWN",
    "FeatureImputationSemantics",
    "ImputationSemanticsResult",
    "analyze_imputation_semantics",
    # versioning
    "FE06_VERSION",
    "compute_sha256",
    "compute_file_sha256",
    "compute_df_sha256",
    # report
    "write_fe06_reports",
    "write_narrative_report",
    "write_comparison_matrix",
    # pipeline
    "FE06PipelineResult",
    "run_fe06_pipeline",
]
