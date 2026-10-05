"""Data loading, validation, schema, and audit utilities.

Subpackages:
    loader   - read raw UCI Online Retail files into pandas DataFrames.
    validator - schema and value-range checks for raw and processed data.
    schema   - canonical column names, dtypes, and expected ranges.
    audit    - reusable raw-dataset audit functions (FE-01).
"""

from customer_segmentation.data.audit import (
    AuditSummary,
    DateProfile,
    DuplicateProfile,
    IdentifierProfile,
    basic_overview,
    categorical_profile,
    coerce_object_dtype_strings,
    date_profile,
    detect_string_pattern,
    duplicate_profile,
    frequency_table,
    identifier_profile,
    looks_like_cancellation_prefix,
    missing_profile,
    numerical_profile,
    safe_quantile,
    select_columns_by_dtype,
)
from customer_segmentation.data.loader import (
    list_raw_files,
    list_sheet_names,
    load_raw_transactions,
)
from customer_segmentation.data.validator import (
    ValidationResult,
    assert_columns_exist,
    validate_customer_features,
    validate_raw_transactions,
)

__all__ = [
    # loader
    "load_raw_transactions",
    "list_sheet_names",
    "list_raw_files",
    # validator
    "ValidationResult",
    "assert_columns_exist",
    "validate_raw_transactions",
    "validate_customer_features",
    # audit
    "AuditSummary",
    "DateProfile",
    "DuplicateProfile",
    "IdentifierProfile",
    "basic_overview",
    "categorical_profile",
    "coerce_object_dtype_strings",
    "date_profile",
    "detect_string_pattern",
    "duplicate_profile",
    "frequency_table",
    "identifier_profile",
    "looks_like_cancellation_prefix",
    "missing_profile",
    "numerical_profile",
    "safe_quantile",
    "select_columns_by_dtype",
]
