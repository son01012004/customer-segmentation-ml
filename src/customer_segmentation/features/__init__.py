"""Feature engineering: RFM, extended behavioral features, validation.

FE-05 (Plan V5 - Approved)
============================

Modules
-------
config_loader       - Load configs/feature_engineering.yaml
rfm                 - RFM computation (Recency, Frequency, Monetary variants)
monetary_comparison - 4 distinct monetary variants comparison
transaction_behavior - Tenure, PurchaseInterval, ActiveDays, AverageInvoiceValue, Quantity
diversity           - ProductsPerInvoice ratio proxy
cancellation        - CancellationRate, ReturnRate
analysis            - Distribution, variance, correlation, redundancy, outlier analysis
selection           - Evidence-based feature selection (no score/rank/weight)
validation          - Validation checks (ONE Monetary, ONE Frequency, no CategoryCount)
candidate_dataset   - Build final candidate dataset Tầng 2
report              - All report generation

Hard constraints (Plan V5):
- ONE Monetary materialized (default: MonetarySigned)
- ONE Frequency materialized (default: Frequency_ByInvoice)
- ONE Quantity working set materialized (default: signed)
- PurchaseInterval uses ddof=1, NaN for < 2 invoices (not filled with 0)
- CategoryCount NOT materialized
- ProductsPerInvoice is ratio proxy
- Selection: evidence-based gates only, no score/rank/weight
- No "best/recommended/final" language
- All PENDING_REVIEW decisions documented in reports
"""

from customer_segmentation.features.analysis import (
    CorrelationResult,
    DistributionResult,
    OutlierResult,
    RedundancyResult,
    VarianceResult,
    assess_interpretability,
    compute_correlation_matrices,
    compute_distribution_stats,
    compute_variance_stats,
    detect_outliers,
    detect_redundancy,
    select_numeric_candidate_columns,
    shapiro_wilk_diagnostic,
)
from customer_segmentation.features.cancellation import (
    compute_cancellation_features,
    compute_cancellation_rate,
    compute_return_rate,
)
from customer_segmentation.features.candidate_dataset import (
    CandidateDatasetResult,
    build_candidate_features,
    validate_candidate_dataset,
)
from customer_segmentation.features.config_loader import (
    DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH,
    AnalysisScopeConfig,
    CancellationConfig,
    CancellationFeatureSpec,
    DiversityConfig,
    DiversityFeatureSpec,
    FeatureEngineeringConfig,
    FeatureEngineeringConfigError,
    FeatureEngineeringStatus,
    LayerClassification,
    LayerRole,
    MetadataConfig,
    OutputConfig,
    QuantityConfig,
    QuantityFeatureSpec,
    ReferenceDateConfig,
    RFMConfig,
    SelectionConfig,
    SelectionDecision,
    SelectionGateConfig,
    SourceConfig,
    TransactionBehaviorConfig,
    TransactionBehaviorFeatureSpec,
    UnsupportedFeatureSpec,
    find_default_feature_engineering_config_path,
    load_feature_engineering_config,
    resolve_feature_engineering_config_path,
)
from customer_segmentation.features.diversity import (
    compute_diversity_features,
    compute_products_per_invoice,
)
from customer_segmentation.features.monetary_comparison import (
    build_monetary_comparison_csv,
    compute_all_monetary_variants,
    detect_overlap,
    materialize_one_monetary_candidate,
)
from customer_segmentation.features.report import (
    ReportPaths,
    write_all_fe05_reports,
    write_candidate_feature_report,
    write_correlation_matrices,
    write_distribution_analysis,
    write_fe05_run_json,
    write_feature_dictionary,
    write_feature_selection_report,
    write_frequency_comparison_csv,
    write_interpretability_csv,
    write_monetary_comparison,
    write_narrative_report,
    write_outlier_detection,
    write_quantity_comparison_csv,
    write_redundancy_report,
    write_rfm_report,
    write_variance_analysis,
)
from customer_segmentation.features.rfm import (
    FrequencyVariants,
    MonetaryVariants,
    build_rfm_report,
    compute_frequency_variants,
    compute_monetary_variants,
    compute_recency,
    compute_reference_date,
    materialize_frequency,
    materialize_monetary,
)
from customer_segmentation.features.selection import (
    DECISION_ADJUST,
    DECISION_EXCLUDE,
    DECISION_PENDING_REVIEW,
    DECISION_RETAIN_CANDIDATE,
    DEFAULT_INTERPRETABLE_FEATURES,
    GATE_STATUS_DIAGNOSTIC,
    GATE_STATUS_FAIL,
    GATE_STATUS_NOT_APPLICABLE,
    GATE_STATUS_PASS,
    GATE_STATUS_WARNING,
    FeatureSelectionResult,
    GateResult,
    apply_data_quality_gate,
    apply_interpretability_gate,
    apply_leakage_gate,
    apply_redundancy_gate,
    apply_shapiro_wilk_gate,
    apply_stability_gate,
    apply_zero_variance_gate,
    build_feature_selection_report,
    make_selection_decisions,
)
from customer_segmentation.features.transaction_behavior import (
    QuantityVariants,
    TransactionBehaviorResult,
    compute_active_days,
    compute_all_transaction_behavior,
    compute_average_invoice_value,
    compute_purchase_interval,
    compute_purchase_only_quantity_set,
    compute_quantity_variants,
    compute_signed_quantity_set,
    compute_tenure_days,
    write_quantity_variants_comparison,
)
from customer_segmentation.features.validation import (
    ValidationCheck,
    ValidationReport,
    validate_candidate_features,
    validate_customer_features,
    validate_no_category_count,
    validate_no_leakage,
    validate_one_frequency,
    validate_one_monetary,
    validate_one_quantity_set,
    validate_purchase_interval_na,
    validate_rfm_constraints,
    validate_unique_customers,
)

__all__ = [
    # config_loader
    "DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH",
    "AnalysisScopeConfig",
    "CancellationConfig",
    "CancellationFeatureSpec",
    "DiversityConfig",
    "DiversityFeatureSpec",
    "FeatureEngineeringConfig",
    "FeatureEngineeringConfigError",
    "FeatureEngineeringStatus",
    "LayerClassification",
    "LayerRole",
    "MetadataConfig",
    "OutputConfig",
    "QuantityConfig",
    "QuantityFeatureSpec",
    "RFMConfig",
    "ReferenceDateConfig",
    "SelectionConfig",
    "SelectionDecision",
    "SelectionGateConfig",
    "SourceConfig",
    "TransactionBehaviorConfig",
    "TransactionBehaviorFeatureSpec",
    "UnsupportedFeatureSpec",
    "find_default_feature_engineering_config_path",
    "load_feature_engineering_config",
    "resolve_feature_engineering_config_path",
    # rfm
    "FrequencyVariants",
    "MonetaryVariants",
    "build_rfm_report",
    "compute_frequency_variants",
    "compute_monetary_variants",
    "compute_recency",
    "compute_reference_date",
    "materialize_frequency",
    "materialize_monetary",
    # monetary_comparison
    "build_monetary_comparison_csv",
    "compute_all_monetary_variants",
    "detect_overlap",
    "materialize_one_monetary_candidate",
    # transaction_behavior
    "QuantityVariants",
    "TransactionBehaviorResult",
    "compute_active_days",
    "compute_all_transaction_behavior",
    "compute_average_invoice_value",
    "compute_purchase_interval",
    "compute_purchase_only_quantity_set",
    "compute_quantity_variants",
    "compute_signed_quantity_set",
    "compute_tenure_days",
    "write_quantity_variants_comparison",
    # diversity
    "compute_diversity_features",
    "compute_products_per_invoice",
    # cancellation
    "compute_cancellation_features",
    "compute_cancellation_rate",
    "compute_return_rate",
    # analysis
    "CorrelationResult",
    "DistributionResult",
    "OutlierResult",
    "RedundancyResult",
    "VarianceResult",
    "assess_interpretability",
    "compute_correlation_matrices",
    "compute_distribution_stats",
    "compute_variance_stats",
    "detect_outliers",
    "detect_redundancy",
    "select_numeric_candidate_columns",
    "shapiro_wilk_diagnostic",
    # selection
    "DECISION_ADJUST",
    "DECISION_EXCLUDE",
    "DECISION_PENDING_REVIEW",
    "DECISION_RETAIN_CANDIDATE",
    "DEFAULT_INTERPRETABLE_FEATURES",
    "GATE_STATUS_DIAGNOSTIC",
    "GATE_STATUS_FAIL",
    "GATE_STATUS_NOT_APPLICABLE",
    "GATE_STATUS_PASS",
    "GATE_STATUS_WARNING",
    "FeatureSelectionResult",
    "GateResult",
    "apply_data_quality_gate",
    "apply_interpretability_gate",
    "apply_leakage_gate",
    "apply_redundancy_gate",
    "apply_shapiro_wilk_gate",
    "apply_stability_gate",
    "apply_zero_variance_gate",
    "build_feature_selection_report",
    "make_selection_decisions",
    # validation
    "ValidationCheck",
    "ValidationReport",
    "validate_candidate_features",
    "validate_customer_features",
    "validate_no_category_count",
    "validate_no_leakage",
    "validate_one_frequency",
    "validate_one_monetary",
    "validate_one_quantity_set",
    "validate_purchase_interval_na",
    "validate_rfm_constraints",
    "validate_unique_customers",
    # candidate_dataset
    "CandidateDatasetResult",
    "build_candidate_features",
    "validate_candidate_dataset",
    # report
    "ReportPaths",
    "write_all_fe05_reports",
    "write_candidate_feature_report",
    "write_correlation_matrices",
    "write_distribution_analysis",
    "write_feature_dictionary",
    "write_feature_selection_report",
    "write_fe05_run_json",
    "write_frequency_comparison_csv",
    "write_interpretability_csv",
    "write_monetary_comparison",
    "write_narrative_report",
    "write_outlier_detection",
    "write_quantity_comparison_csv",
    "write_redundancy_report",
    "write_rfm_report",
    "write_variance_analysis",
]
