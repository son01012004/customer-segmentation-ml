"""FE-04 customer-level aggregation package.

Single entry point for the customer-level base dataset construction.

Public API
----------
:func:`aggregate_customer_base`
    Aggregate transaction-level data to customer-level.
:func:`validate_base_dataset`
    Validate the customer-level base dataset.
:func:`write_reports`
    Write all FE-04 reports to disk.
:func:`load_aggregation_config`
    Load ``configs/aggregation.yaml``.
:func:`compute_line_revenue`
    Derive LineRevenue in-memory.
"""

from customer_segmentation.aggregation.base_dataset import (
    LINE_REVENUE_COLUMN,
    CustomerBaseResult,
    aggregate_customer_base,
    build_base_schema,
    compute_line_revenue,
)
from customer_segmentation.aggregation.config_loader import (
    AGGREGATION_STATUS_PENDING_MENTOR_REVIEW,
    AGGREGATION_STATUS_WORKING_ASSUMPTION,
    DEFAULT_AGGREGATION_CONFIG_PATH,
    AggregationConfig,
    AggregationConfigError,
    AggregationSpec,
    LineRevenueColumns,
    MetadataConfig,
    OutputConfig,
    SourceConfig,
    aggregation_config_to_dict,
    find_default_aggregation_config_path,
    load_aggregation_config,
    resolve_aggregation_config_path,
)
from customer_segmentation.aggregation.report import write_reports
from customer_segmentation.aggregation.validation import (
    ValidationCheckResult,
    ValidationResult,
    validate_base_dataset,
    validation_result_to_dataframe,
)

__all__ = [
    # base_dataset
    "LINE_REVENUE_COLUMN",
    "CustomerBaseResult",
    "aggregate_customer_base",
    "build_base_schema",
    "compute_line_revenue",
    # config_loader
    "DEFAULT_AGGREGATION_CONFIG_PATH",
    "AGGREGATION_STATUS_PENDING_MENTOR_REVIEW",
    "AGGREGATION_STATUS_WORKING_ASSUMPTION",
    "AggregationConfig",
    "AggregationConfigError",
    "AggregationSpec",
    "LineRevenueColumns",
    "MetadataConfig",
    "OutputConfig",
    "SourceConfig",
    "aggregation_config_to_dict",
    "find_default_aggregation_config_path",
    "load_aggregation_config",
    "resolve_aggregation_config_path",
    # report
    "write_reports",
    # validation
    "ValidationCheckResult",
    "ValidationResult",
    "validate_base_dataset",
    "validation_result_to_dataframe",
]
