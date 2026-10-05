"""Validation helpers for FE-05 candidate features.

Validates:
- ONE Monetary materialized
- ONE Frequency materialized
- ONE Quantity working set materialized
- No CategoryCount
- No duplicate customers
- CustomerID is unique
- No leakage
- PurchaseInterval NaN semantics correct

Also provides legacy placeholder validate_customer_features for backwards
compatibility with FE-01.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from customer_segmentation.data.validator import ValidationResult

__all__ = [
    "ValidationCheck",
    "ValidationReport",
    "validate_candidate_features",
    "validate_customer_features",  # Legacy placeholder
    "validate_rfm_constraints",
    "validate_no_leakage",
    "validate_purchase_interval_na",
    "validate_one_monetary",
    "validate_one_frequency",
    "validate_one_quantity_set",
    "validate_no_category_count",
    "validate_unique_customers",
]


def validate_customer_features(df: pd.DataFrame) -> ValidationResult:
    """Legacy placeholder for FE-01 compatibility.

    Real checks will be added once FE-01 columns are defined.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix.

    Returns
    -------
    ValidationResult
        Aggregated validation outcome.
    """
    return ValidationResult()


@dataclass
class ValidationCheck:
    """Single validation check result."""

    check_id: str
    description: str
    status: str  # PASS | FAIL | WARNING
    message: str


@dataclass
class ValidationReport:
    """Container for validation checks."""

    checks: list[ValidationCheck] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if no checks have status FAIL."""
        return not any(c.status == "FAIL" for c in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARNING")

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")


def validate_candidate_features(
    df_candidates: pd.DataFrame,
    *,
    monetary_columns: Sequence[str] = ("Monetary",),
    frequency_columns: Sequence[str] = ("Frequency",),
    quantity_columns: Sequence[str] = ("TotalQuantity", "AverageQuantity", "BasketSize"),
    customer_key: str = "CustomerID",
) -> ValidationReport:
    """Run all FE-05 candidate feature validation checks.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.
    monetary_columns : Sequence[str]
        Expected monetary column names.
    frequency_columns : Sequence[str]
        Expected frequency column names.
    quantity_columns : Sequence[str]
        Expected quantity column names.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    ValidationReport
        Container with all checks.
    """
    report = ValidationReport()

    # Check unique customers
    report.checks.append(validate_unique_customers(df_candidates, customer_key=customer_key))

    # Check one monetary
    report.checks.append(validate_one_monetary(df_candidates, monetary_columns=monetary_columns))

    # Check one frequency
    report.checks.append(validate_one_frequency(df_candidates, frequency_columns=frequency_columns))

    # Check one quantity set
    report.checks.append(
        validate_one_quantity_set(df_candidates, quantity_columns=quantity_columns)
    )

    # Check no category count
    report.checks.append(validate_no_category_count(df_candidates))

    # Check no leakage (basic heuristic)
    report.checks.append(validate_no_leakage(df_candidates))

    return report


def validate_rfm_constraints(
    df_candidates: pd.DataFrame,
    *,
    expected_columns: dict[str, str],
) -> ValidationReport:
    """Validate RFM constraints.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.
    expected_columns : dict[str, str]
        Map of expected column names to descriptions.

    Returns
    -------
    ValidationReport
        Container with checks.
    """
    report = ValidationReport()

    for col, desc in expected_columns.items():
        if col not in df_candidates.columns:
            report.checks.append(
                ValidationCheck(
                    check_id=f"V-RFM-MISSING-{col}",
                    description=f"Column {col!r} ({desc}) must exist.",
                    status="FAIL",
                    message=f"Expected column {col!r} not found.",
                )
            )
        else:
            report.checks.append(
                ValidationCheck(
                    check_id=f"V-RFM-PRESENT-{col}",
                    description=f"Column {col!r} ({desc}) must exist.",
                    status="PASS",
                    message=f"Column {col!r} present.",
                )
            )

    return report


def validate_no_leakage(df_candidates: pd.DataFrame) -> ValidationCheck:
    """Check no obvious leakage in candidate features.

    Basic heuristic: check no suspicious column names like 'Target', 'Label'.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.

    Returns
    -------
    ValidationCheck
        Validation check result.
    """
    suspicious_keywords = ["target", "label", "class", "answer"]
    leakage_columns = [
        col for col in df_candidates.columns if any(kw in col.lower() for kw in suspicious_keywords)
    ]

    if leakage_columns:
        return ValidationCheck(
            check_id="V-LEAKAGE",
            description="No leakage: candidate features must not contain target/label columns.",
            status="FAIL",
            message=f"Potential leakage columns: {leakage_columns}.",
        )

    return ValidationCheck(
        check_id="V-LEAKAGE",
        description="No leakage: candidate features must not contain target/label columns.",
        status="PASS",
        message="No leakage columns detected.",
    )


def validate_purchase_interval_na(
    df_candidates: pd.DataFrame,
    *,
    purchase_interval_mean: str = "PurchaseIntervalMean",
    purchase_interval_std: str = "PurchaseIntervalStd",
    frequency_column: str = "Frequency",
    customer_key: str = "CustomerID",
) -> ValidationCheck:
    """Validate PurchaseInterval NaN semantics.

    NaN must occur for customers with Frequency < 2.
    NaN MUST NOT be filled with 0.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.
    purchase_interval_mean : str
        PurchaseIntervalMean column name.
    purchase_interval_std : str
        PurchaseIntervalStd column name.
    frequency_column : str
        Frequency column name.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    ValidationCheck
        Validation check result.
    """
    if purchase_interval_mean not in df_candidates.columns:
        return ValidationCheck(
            check_id="V-PURCHASE-INTERVAL-NA",
            description="PurchaseIntervalMean must exist.",
            status="FAIL",
            message=f"Column {purchase_interval_mean!r} not found.",
        )

    # Customers with Frequency < 2 must have NaN
    freq = pd.to_numeric(df_candidates[frequency_column], errors="coerce")
    pim = df_candidates[purchase_interval_mean]

    # Customers with freq < 2 should have NaN
    single_inv_mask = freq < 2
    single_inv_nan_count = pim.loc[single_inv_mask].isna().sum()
    single_inv_count = single_inv_mask.sum()

    if single_inv_count > 0 and single_inv_nan_count == single_inv_count:
        return ValidationCheck(
            check_id="V-PURCHASE-INTERVAL-NA",
            description=(
                "Customers with Frequency < 2 must have NaN for PurchaseIntervalMean. "
                "NaN MUST NOT be filled with 0."
            ),
            status="PASS",
            message=(
                f"All {single_inv_count} customers with Frequency < 2 have NaN. "
                "Correct semantics."
            ),
        )

    return ValidationCheck(
        check_id="V-PURCHASE-INTERVAL-NA",
        description=(
            "Customers with Frequency < 2 must have NaN for PurchaseIntervalMean. "
            "NaN MUST NOT be filled with 0."
        ),
        status="FAIL",
        message=(
            f"{single_inv_count - single_inv_nan_count} customers with Frequency < 2 "
            "have non-NaN values (incorrect semantics)."
        ),
    )


def validate_one_monetary(
    df_candidates: pd.DataFrame,
    *,
    monetary_columns: Sequence[str] = ("Monetary",),
) -> ValidationCheck:
    """Validate that exactly ONE Monetary column is materialized.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.
    monetary_columns : Sequence[str]
        Expected monetary column names.

    Returns
    -------
    ValidationCheck
        Validation check result.
    """
    # Check that all expected monetary columns are present
    missing = [c for c in monetary_columns if c not in df_candidates.columns]

    # Check that no extra Monetary-prefixed columns are present
    extra_monetary = [
        c for c in df_candidates.columns if c.startswith("Monetary") and c not in monetary_columns
    ]

    if missing:
        return ValidationCheck(
            check_id="V-ONE-MONETARY",
            description="Exactly ONE Monetary column must be materialized.",
            status="FAIL",
            message=f"Missing Monetary columns: {missing}.",
        )

    if extra_monetary:
        return ValidationCheck(
            check_id="V-ONE-MONETARY",
            description="Exactly ONE Monetary column must be materialized.",
            status="FAIL",
            message=f"Extra Monetary columns found (should be in comparison report only): {extra_monetary}.",
        )

    return ValidationCheck(
        check_id="V-ONE-MONETARY",
        description="Exactly ONE Monetary column must be materialized.",
        status="PASS",
        message=f"ONE Monetary column materialized: {list(monetary_columns)}.",
    )


def validate_one_frequency(
    df_candidates: pd.DataFrame,
    *,
    frequency_columns: Sequence[str] = ("Frequency",),
) -> ValidationCheck:
    """Validate that exactly ONE Frequency column is materialized.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.
    frequency_columns : Sequence[str]
        Expected frequency column names.

    Returns
    -------
    ValidationCheck
        Validation check result.
    """
    missing = [c for c in frequency_columns if c not in df_candidates.columns]

    # Check that no extra Frequency-prefixed columns are present
    extra_freq = [
        c for c in df_candidates.columns if c.startswith("Frequency") and c not in frequency_columns
    ]

    if missing:
        return ValidationCheck(
            check_id="V-ONE-FREQUENCY",
            description="Exactly ONE Frequency column must be materialized.",
            status="FAIL",
            message=f"Missing Frequency columns: {missing}.",
        )

    if extra_freq:
        return ValidationCheck(
            check_id="V-ONE-FREQUENCY",
            description="Exactly ONE Frequency column must be materialized.",
            status="FAIL",
            message=f"Extra Frequency columns found (should be in comparison report only): {extra_freq}.",
        )

    return ValidationCheck(
        check_id="V-ONE-FREQUENCY",
        description="Exactly ONE Frequency column must be materialized.",
        status="PASS",
        message=f"ONE Frequency column materialized: {list(frequency_columns)}.",
    )


def validate_one_quantity_set(
    df_candidates: pd.DataFrame,
    *,
    quantity_columns: Sequence[str] = ("TotalQuantity", "AverageQuantity", "BasketSize"),
) -> ValidationCheck:
    """Validate that exactly ONE Quantity working set is materialized.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.
    quantity_columns : Sequence[str]
        Expected quantity columns.

    Returns
    -------
    ValidationCheck
        Validation check result.
    """
    # Check that all expected quantity columns are present
    missing = [c for c in quantity_columns if c not in df_candidates.columns]

    # Check that no extra working-set quantity columns are present
    extra_qty = [
        c
        for c in df_candidates.columns
        if (
            c.startswith("TotalQuantity")
            or c.startswith("AverageQuantity")
            or c.startswith("BasketSize")
        )
        and c not in quantity_columns
    ]

    if missing:
        return ValidationCheck(
            check_id="V-ONE-QUANTITY-SET",
            description="Exactly ONE Quantity working set must be materialized.",
            status="FAIL",
            message=f"Missing Quantity columns: {missing}.",
        )

    if extra_qty:
        return ValidationCheck(
            check_id="V-ONE-QUANTITY-SET",
            description="Exactly ONE Quantity working set must be materialized.",
            status="FAIL",
            message=f"Extra Quantity working set columns: {extra_qty}.",
        )

    return ValidationCheck(
        check_id="V-ONE-QUANTITY-SET",
        description="Exactly ONE Quantity working set must be materialized.",
        status="PASS",
        message=f"ONE Quantity working set materialized: {list(quantity_columns)}.",
    )


def validate_no_category_count(df_candidates: pd.DataFrame) -> ValidationCheck:
    """Validate that CategoryCount is NOT materialized.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.

    Returns
    -------
    ValidationCheck
        Validation check result.
    """
    if "CategoryCount" in df_candidates.columns:
        return ValidationCheck(
            check_id="V-NO-CATEGORY-COUNT",
            description="CategoryCount must NOT be materialized.",
            status="FAIL",
            message="CategoryCount is materialized. Dataset has no official taxonomy.",
        )

    return ValidationCheck(
        check_id="V-NO-CATEGORY-COUNT",
        description="CategoryCount must NOT be materialized.",
        status="PASS",
        message="CategoryCount is not materialized. Correct.",
    )


def validate_unique_customers(
    df_candidates: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> ValidationCheck:
    """Validate that CustomerID is unique.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate feature DataFrame.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    ValidationCheck
        Validation check result.
    """
    if customer_key not in df_candidates.columns:
        return ValidationCheck(
            check_id="V-UNIQUE-CUSTOMERS",
            description="CustomerID must be unique.",
            status="FAIL",
            message=f"Column {customer_key!r} not found.",
        )

    n_total = len(df_candidates)
    n_unique = df_candidates[customer_key].nunique()
    duplicate_count = n_total - n_unique

    if duplicate_count == 0:
        return ValidationCheck(
            check_id="V-UNIQUE-CUSTOMERS",
            description="CustomerID must be unique.",
            status="PASS",
            message=f"All {n_total} CustomerIDs are unique.",
        )

    return ValidationCheck(
        check_id="V-UNIQUE-CUSTOMERS",
        description="CustomerID must be unique.",
        status="FAIL",
        message=f"{duplicate_count} duplicate CustomerIDs found.",
    )
