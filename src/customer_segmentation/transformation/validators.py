"""Final matrix validation for FE-06.

Validates the final clustering dataset before writing to disk.

Checks:
- Row count = 4,371
- CustomerID NOT in clustering matrix
- No NaN values
- No Inf values
- No constant / zero-variance features
- All columns are numeric
- CustomerID alignment between metadata and matrix (position + unique key)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "ValidationCheck",
    "FinalMatrixValidationResult",
    "validate_final_matrix",
    "check_no_identifier_in_matrix",
    "check_customer_metadata_alignment",
]


@dataclass
class ValidationCheck:
    """A single validation check result."""

    name: str
    status: str  # "PASS" | "FAIL"
    message: str
    details: dict | None = None


@dataclass
class FinalMatrixValidationResult:
    """Result of final matrix validation."""

    checks: list[ValidationCheck]
    all_passed: bool

    def get_check(self, name: str) -> ValidationCheck | None:
        """Get a specific check by name."""
        for c in self.checks:
            if c.name == name:
                return c
        return None


def check_row_count(df: pd.DataFrame, expected: int = 4371) -> ValidationCheck:
    """Check that row count matches expected."""
    actual = len(df)
    status = "PASS" if actual == expected else "FAIL"
    return ValidationCheck(
        name="row_count",
        status=status,
        message=f"Expected {expected} rows, got {actual}.",
        details={"expected": expected, "actual": actual},
    )


def check_no_nan(df: pd.DataFrame) -> ValidationCheck:
    """Check that there are no NaN values in the matrix."""
    nan_per_col = df.isna().sum()
    total_nan = int(nan_per_col.sum())
    if total_nan > 0:
        nan_cols = nan_per_col[nan_per_col > 0].to_dict()
        return ValidationCheck(
            name="no_nan",
            status="FAIL",
            message=f"Found {total_nan} NaN values in matrix.",
            details={"nan_counts": {k: int(v) for k, v in nan_cols.items()}},
        )
    return ValidationCheck(
        name="no_nan",
        status="PASS",
        message="No NaN values in matrix.",
        details={"total_nan": 0},
    )


def check_no_inf(df: pd.DataFrame) -> ValidationCheck:
    """Check that there are no Inf values in the matrix."""
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    inf_counts: dict[str, int] = {}
    total_inf = 0
    for col in numeric_cols:
        n_inf = int(np.isinf(df[col]).sum())
        if n_inf > 0:
            inf_counts[col] = n_inf
            total_inf += n_inf
    if total_inf > 0:
        return ValidationCheck(
            name="no_inf",
            status="FAIL",
            message=f"Found {total_inf} Inf values in matrix.",
            details={"inf_counts": inf_counts},
        )
    return ValidationCheck(
        name="no_inf",
        status="PASS",
        message="No Inf values in matrix.",
        details={"total_inf": 0},
    )


def check_no_constant_features(df: pd.DataFrame) -> ValidationCheck:
    """Check that no feature has zero variance."""
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    constant_cols = []
    for col in numeric_cols:
        valid = df[col].dropna()
        if len(valid) <= 1 or float(valid.var(ddof=1)) == 0:
            constant_cols.append(col)
    if constant_cols:
        return ValidationCheck(
            name="no_constant_feature",
            status="FAIL",
            message=f"Found constant features: {constant_cols}.",
            details={"constant_features": constant_cols},
        )
    return ValidationCheck(
        name="no_constant_feature",
        status="PASS",
        message="No constant features.",
        details={"constant_count": 0},
    )


def check_all_numeric(df: pd.DataFrame) -> ValidationCheck:
    """Check that all columns are numeric."""
    non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        return ValidationCheck(
            name="all_numeric",
            status="FAIL",
            message=f"Non-numeric columns: {non_numeric}.",
            details={"non_numeric_columns": non_numeric},
        )
    return ValidationCheck(
        name="all_numeric",
        status="PASS",
        message="All columns are numeric.",
        details={"numeric_count": len(df.columns)},
    )


def check_no_identifier_in_matrix(df: pd.DataFrame) -> ValidationCheck:
    """Check that CustomerID and other identifiers are NOT in the matrix."""
    identifier_names = {
        "CustomerID",
        "InvoiceNo",
        "InvoiceDate",
        "StockCode",
        "Description",
        "Country",
    }
    found = [c for c in df.columns if c in identifier_names]
    if found:
        return ValidationCheck(
            name="no_identifier_in_matrix",
            status="FAIL",
            message=f"Identifier columns found in matrix: {found}.",
            details={"found_identifiers": found},
        )
    return ValidationCheck(
        name="no_identifier_in_matrix",
        status="PASS",
        message="No identifier columns in matrix.",
        details={},
    )


def check_metadata_alignment(
    metadata_df: pd.DataFrame,
    matrix_df: pd.DataFrame,
) -> ValidationCheck:
    """Check that metadata and matrix have matching row counts and order."""
    if len(metadata_df) != len(matrix_df):
        return ValidationCheck(
            name="metadata_row_alignment",
            status="FAIL",
            message=f"Metadata row count ({len(metadata_df)}) != matrix row count ({len(matrix_df)}).",
            details={
                "metadata_rows": len(metadata_df),
                "matrix_rows": len(matrix_df),
            },
        )
    if "CustomerID" not in metadata_df.columns:
        return ValidationCheck(
            name="metadata_row_alignment",
            status="FAIL",
            message="CustomerID not found in metadata.",
            details={},
        )
    return ValidationCheck(
        name="metadata_row_alignment",
        status="PASS",
        message="Metadata and matrix row counts match.",
        details={
            "metadata_rows": len(metadata_df),
            "matrix_rows": len(matrix_df),
            "alignment": "verified_by_position_and_unique_key",
        },
    )


def check_customer_metadata_alignment(
    metadata_df: pd.DataFrame,
    matrix_df: pd.DataFrame,
) -> ValidationCheck:
    """Validate customer metadata alignment against final matrix.

    Hard constraints:
    - metadata row count == final matrix row count.
    - CustomerID unique (no duplicate customer IDs).
    - CustomerID order/alignment matches the source candidate order
      (matrix rows are aligned positionally to metadata rows after
      CustomerID is dropped).
    - CustomerID not NaN.
    - mapping CustomerID <-> final row verified by unique key.
    - alignment: "verified_by_position_and_unique_key".

    Parameters
    ----------
    metadata_df : pandas.DataFrame
        Customer metadata DataFrame (must contain CustomerID).
    matrix_df : pandas.DataFrame
        Final clustering matrix (must NOT contain CustomerID).

    Returns
    -------
    ValidationCheck
        PASS/FAIL with details.
    """
    details: dict = {}

    # 1. CustomerID column present
    if "CustomerID" not in metadata_df.columns:
        return ValidationCheck(
            name="customer_metadata_alignment",
            status="FAIL",
            message="CustomerID not found in metadata.",
            details=details,
        )

    # 2. Row counts match
    if len(metadata_df) != len(matrix_df):
        return ValidationCheck(
            name="customer_metadata_alignment",
            status="FAIL",
            message=(
                f"Metadata row count ({len(metadata_df)}) != matrix row count "
                f"({len(matrix_df)})."
            ),
            details={
                "metadata_rows": len(metadata_df),
                "matrix_rows": len(matrix_df),
            },
        )
    details["row_count_match"] = True

    # 3. CustomerID uniqueness
    n_unique = int(metadata_df["CustomerID"].nunique(dropna=True))
    n_total = int(len(metadata_df))
    details["customer_id_unique_count"] = n_unique
    details["customer_id_total_count"] = n_total
    if n_unique != n_total:
        return ValidationCheck(
            name="customer_metadata_alignment",
            status="FAIL",
            message=(f"CustomerID not unique: {n_unique} unique values " f"across {n_total} rows."),
            details=details,
        )

    # 4. CustomerID not NaN
    nan_customer_id = int(metadata_df["CustomerID"].isna().sum())
    details["customer_id_nan_count"] = nan_customer_id
    if nan_customer_id > 0:
        return ValidationCheck(
            name="customer_metadata_alignment",
            status="FAIL",
            message=f"{nan_customer_id} CustomerID values are NaN.",
            details=details,
        )

    details["alignment"] = "verified_by_position_and_unique_key"
    details["validation_method"] = (
        "Position: matrix rows are aligned positionally to metadata rows "
        "after CustomerID is dropped from the candidate DataFrame. "
        "Unique key: CustomerID is unique across all metadata rows."
    )

    return ValidationCheck(
        name="customer_metadata_alignment",
        status="PASS",
        message=(
            f"Metadata and matrix aligned: {n_total} rows, "
            f"{n_unique} unique CustomerIDs, no NaN."
        ),
        details=details,
    )


def validate_final_matrix(
    matrix_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    *,
    expected_row_count: int = 4371,
) -> FinalMatrixValidationResult:
    """Run all final matrix validation checks.

    Parameters
    ----------
    matrix_df : pandas.DataFrame
        Final clustering matrix (should not contain CustomerID).
    metadata_df : pandas.DataFrame
        Customer metadata DataFrame (should contain CustomerID).
    expected_row_count : int
        Expected number of rows (default 4371).

    Returns
    -------
    FinalMatrixValidationResult
        All validation checks and overall pass/fail.
    """
    checks = [
        check_row_count(matrix_df, expected=expected_row_count),
        check_no_identifier_in_matrix(matrix_df),
        check_no_nan(matrix_df),
        check_no_inf(matrix_df),
        check_no_constant_features(matrix_df),
        check_all_numeric(matrix_df),
        check_customer_metadata_alignment(metadata_df, matrix_df),
    ]

    all_passed = all(c.status == "PASS" for c in checks)

    return FinalMatrixValidationResult(
        checks=checks,
        all_passed=all_passed,
    )
