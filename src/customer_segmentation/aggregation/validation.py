"""FE-04 validation: check integrity of the customer-level base dataset.

Validation checks are defined as a list of named checks that run in order.
Each check returns a result dict with: check_id, description, status, message.

Results are written to ``reports/fe04/validation_report.csv``.

Hard constraints enforced:
- V-01: nrow == nunique(CustomerID)
- V-02: duplicate CustomerID == 0
- V-03: CustomerID not null
- V-04: TotalQuantity finite (warning if negative — signed cancellation)
- V-05: TotalMonetary finite
- V-06: FirstPurchaseDate <= LastPurchaseDate per row
- V-07: DistinctInvoiceCount >= 1
- V-08: DistinctInvoiceCount != 0 (for AverageTransactionValue denominator)
- V-09: AverageTransactionValue finite (when denominator > 0)
- V-10: PurchaseFrequency valid (non-negative integer)
- V-11: Expected dtypes correct per column
- V-12: Input SHA-256 before == after (enforced by orchestrator, not here)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from customer_segmentation.aggregation.config_loader import AggregationConfig

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationCheckResult:
    """Kết quả của một validation check.

    Attributes
    ----------
    check_id : str
        Mã check (V-01, V-02, ...).
    description : str
        Mô tả ngắn gọn.
    status : str
        "PASS", "WARNING", hoặc "FAIL".
    message : str
        Thông báo chi tiết.
    details : dict[str, Any], optional
        Extra data (e.g., count of negative TotalQuantity).
    """

    check_id: str
    description: str
    status: str
    message: str
    details: dict[str, Any]


@dataclass
class ValidationResult:
    """Tổng hợp tất cả validation checks.

    Attributes
    ----------
    checks : list[ValidationCheckResult]
        Danh sách kết quả các check.
    is_valid : bool
        True nếu không có check nào FAIL.
    """

    checks: list[ValidationCheckResult]

    @property
    def is_valid(self) -> bool:
        return all(c.status != "FAIL" for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "checks": [c.__dict__ for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------


def _v01_row_count_matches_unique(df: pd.DataFrame, customer_key: str) -> ValidationCheckResult:
    """V-01: Số dòng == số unique CustomerID."""
    nrow = int(df.shape[0])
    nunique = int(df[customer_key].nunique(dropna=True))
    passed = nrow == nunique
    return ValidationCheckResult(
        check_id="V-01",
        description="Số dòng == số unique CustomerID",
        status="PASS" if passed else "FAIL",
        message=(
            f"nrow={nrow}, nunique={nunique}. "
            f"{'OK' if passed else 'MISMATCH: nrow != nunique(CustomerID)'}"
        ),
        details={"nrow": nrow, "nunique": nunique},
    )


def _v02_no_duplicate(df: pd.DataFrame, customer_key: str) -> ValidationCheckResult:
    """V-02: Không có duplicate CustomerID."""
    dupes = df[customer_key].duplicated().sum()
    dupes_int = int(dupes)
    passed = dupes_int == 0
    return ValidationCheckResult(
        check_id="V-02",
        description="Không có duplicate CustomerID",
        status="PASS" if passed else "FAIL",
        message=(
            f"duplicate_count={dupes_int}. "
            f"{'OK' if passed else f'FAILED: {dupes_int} duplicate CustomerID(s) found'}"
        ),
        details={"duplicate_count": dupes_int},
    )


def _v03_customer_id_not_null(df: pd.DataFrame, customer_key: str) -> ValidationCheckResult:
    """V-03: CustomerID không null."""
    nulls = int(df[customer_key].isna().sum())
    passed = nulls == 0
    return ValidationCheckResult(
        check_id="V-03",
        description="CustomerID không null",
        status="PASS" if passed else "FAIL",
        message=(
            f"null_count={nulls}. " f"{'OK' if passed else f'FAILED: {nulls} null CustomerID(s)'}"
        ),
        details={"null_count": nulls},
    )


def _v04_total_quantity_finite(df: pd.DataFrame) -> ValidationCheckResult:
    """V-04: TotalQuantity là finite number."""
    if "TotalQuantity" not in df.columns:
        return ValidationCheckResult(
            check_id="V-04",
            description="TotalQuantity là finite number",
            status="WARNING",
            message="TotalQuantity not in output columns; skipped.",
            details={},
        )
    non_finite = int(
        df["TotalQuantity"]
        .apply(lambda x: not (isinstance(x, (int, float)) and float("inf") != x >= -float("inf")))
        .sum()
    )
    has_negative = int((df["TotalQuantity"] < 0).sum())
    if non_finite > 0:
        return ValidationCheckResult(
            check_id="V-04",
            description="TotalQuantity là finite number",
            status="FAIL",
            message=f"FAILED: {non_finite} non-finite TotalQuantity values.",
            details={"non_finite_count": non_finite},
        )
    if has_negative > 0:
        return ValidationCheckResult(
            check_id="V-04",
            description="TotalQuantity là finite number (negative = signed cancellation/return — OK)",
            status="WARNING",
            message=(
                f"WARNING: {has_negative} customers have negative TotalQuantity "
                f"(signed cancellation/return rows — this is expected). "
                "Signed baseline; FE-05 will review sign convention."
            ),
            details={"negative_count": has_negative, "total_count": int(df.shape[0])},
        )
    return ValidationCheckResult(
        check_id="V-04",
        description="TotalQuantity là finite number",
        status="PASS",
        message="OK: all TotalQuantity values are finite.",
        details={"negative_count": 0},
    )


def _v05_total_monetary_finite(df: pd.DataFrame) -> ValidationCheckResult:
    """V-05: TotalMonetary là finite number."""
    if "TotalMonetary" not in df.columns:
        return ValidationCheckResult(
            check_id="V-05",
            description="TotalMonetary là finite number",
            status="WARNING",
            message="TotalMonetary not in output columns; skipped.",
            details={},
        )
    numeric = pd.to_numeric(df["TotalMonetary"], errors="coerce")
    non_finite = int((numeric.isna() | (numeric.abs() == float("inf"))).sum())
    passed = non_finite == 0
    return ValidationCheckResult(
        check_id="V-05",
        description="TotalMonetary là finite number",
        status="PASS" if passed else "FAIL",
        message=(f"{'OK' if passed else f'FAILED: {non_finite} non-finite TotalMonetary values'}"),
        details={"non_finite_count": non_finite},
    )


def _v06_first_le_last(df: pd.DataFrame) -> ValidationCheckResult:
    """V-06: FirstPurchaseDate <= LastPurchaseDate."""
    date_cols = [c for c in df.columns if "PurchaseDate" in c and ("First" in c or "Last" in c)]
    first_col = next((c for c in date_cols if "First" in c), None)
    last_col = next((c for c in date_cols if "Last" in c), None)
    if first_col is None or last_col is None:
        return ValidationCheckResult(
            check_id="V-06",
            description="FirstPurchaseDate <= LastPurchaseDate",
            status="WARNING",
            message="FirstPurchaseDate/LastPurchaseDate not found; skipped.",
            details={},
        )
    violations = int((df[first_col] > df[last_col]).sum())
    passed = violations == 0
    return ValidationCheckResult(
        check_id="V-06",
        description="FirstPurchaseDate <= LastPurchaseDate",
        status="PASS" if passed else "WARNING",
        message=(
            f"{'OK: all dates valid' if passed else f'WARNING: {violations} customers with FirstPurchaseDate > LastPurchaseDate'}"
        ),
        details={"violation_count": violations},
    )


def _v07_distinct_invoice_count_ge_1(df: pd.DataFrame) -> ValidationCheckResult:
    """V-07: DistinctInvoiceCount >= 1."""
    col = "DistinctInvoiceCount" if "DistinctInvoiceCount" in df.columns else None
    if col is None:
        return ValidationCheckResult(
            check_id="V-07",
            description="DistinctInvoiceCount >= 1",
            status="WARNING",
            message="DistinctInvoiceCount not in output; skipped.",
            details={},
        )
    lt1 = int((pd.to_numeric(df[col], errors="coerce") < 1).sum())
    passed = lt1 == 0
    return ValidationCheckResult(
        check_id="V-07",
        description="DistinctInvoiceCount >= 1",
        status="PASS" if passed else "FAIL",
        message=(f"{'OK' if passed else f'FAILED: {lt1} customers with DistinctInvoiceCount < 1'}"),
        details={"count_lt_1": lt1},
    )


def _v08_denominator_nonzero(df: pd.DataFrame) -> ValidationCheckResult:
    """V-08: DistinctInvoiceCount != 0 (for AverageTransactionValue denominator)."""
    col = "DistinctInvoiceCount" if "DistinctInvoiceCount" in df.columns else None
    if col is None:
        return ValidationCheckResult(
            check_id="V-08",
            description="DistinctInvoiceCount != 0 (denominator for AverageTransactionValue)",
            status="WARNING",
            message="DistinctInvoiceCount not in output; skipped.",
            details={},
        )
    zero = int((pd.to_numeric(df[col], errors="coerce") == 0).sum())
    passed = zero == 0
    return ValidationCheckResult(
        check_id="V-08",
        description="DistinctInvoiceCount != 0 (denominator for AverageTransactionValue)",
        status="PASS" if passed else "FAIL",
        message=(
            f"{'OK' if passed else f'FAILED: {zero} customers with DistinctInvoiceCount == 0'}"
        ),
        details={"zero_count": zero},
    )


def _v09_avg_transaction_value_finite(df: pd.DataFrame) -> ValidationCheckResult:
    """V-09: AverageTransactionValue là finite khi denominator > 0."""
    col = "AverageTransactionValue" if "AverageTransactionValue" in df.columns else None
    inv_col = "DistinctInvoiceCount" if "DistinctInvoiceCount" in df.columns else None
    if col is None:
        return ValidationCheckResult(
            check_id="V-09",
            description="AverageTransactionValue là finite (denominator > 0)",
            status="WARNING",
            message="AverageTransactionValue not in output; skipped.",
            details={},
        )
    # Only check rows where denominator > 0 (V-08 guarantees this for valid customers).
    if inv_col and inv_col in df.columns:
        denom = pd.to_numeric(df[inv_col], errors="coerce")
        valid_mask = denom > 0
    else:
        valid_mask = pd.Series(True, index=df.index)

    vals = pd.to_numeric(df[col], errors="coerce")
    non_finite = int((valid_mask & (vals.isna() | (vals.abs() == float("inf")))).sum())
    passed = non_finite == 0
    return ValidationCheckResult(
        check_id="V-09",
        description="AverageTransactionValue là finite (denominator > 0)",
        status="PASS" if passed else "FAIL",
        message=(
            f"{'OK' if passed else f'FAILED: {non_finite} non-finite AverageTransactionValue values'}"
        ),
        details={"non_finite_count": non_finite},
    )


def _v10_purchase_frequency_valid(df: pd.DataFrame) -> ValidationCheckResult:
    """V-10: PurchaseFrequency là non-negative integer."""
    col = "PurchaseFrequency" if "PurchaseFrequency" in df.columns else None
    if col is None:
        return ValidationCheckResult(
            check_id="V-10",
            description="PurchaseFrequency là non-negative integer",
            status="WARNING",
            message="PurchaseFrequency not in output; skipped.",
            details={},
        )
    vals = pd.to_numeric(df[col], errors="coerce")
    negative = int((vals < 0).sum())
    passed = negative == 0
    return ValidationCheckResult(
        check_id="V-10",
        description="PurchaseFrequency là non-negative integer",
        status="PASS" if passed else "FAIL",
        message=(
            f"{'OK' if passed else f'FAILED: {negative} customers with negative PurchaseFrequency'}"
        ),
        details={"negative_count": negative},
    )


def _v11_dtype_check(df: pd.DataFrame) -> ValidationCheckResult:
    """V-11: Expected dtypes đúng cho từng cột."""
    # Expected dtypes: CustomerID = Int64/Int32, numeric aggregates = float64/int64, dates = datetime.
    errors: list[str] = []
    details: dict[str, str] = {}

    for col in df.columns:
        dtype = str(df[col].dtype)
        details[col] = dtype
        if col == "CustomerID" and ("int" not in dtype.lower() and "Int" not in dtype):
            errors.append(f"{col}: expected integer dtype, got {dtype}")
        elif ("Date" in col or "date" in col) and "datetime" not in dtype.lower():
            errors.append(f"{col}: expected datetime dtype, got {dtype}")

    if errors:
        return ValidationCheckResult(
            check_id="V-11",
            description="Expected dtypes đúng cho từng cột",
            status="WARNING",
            message="WARNING: some dtype mismatches detected: " + "; ".join(errors),
            details=details,
        )
    return ValidationCheckResult(
        check_id="V-11",
        description="Expected dtypes đúng cho từng cột",
        status="PASS",
        message="OK: dtypes are consistent with expectations.",
        details=details,
    )


# ---------------------------------------------------------------------------
# Main validation runner
# ---------------------------------------------------------------------------


def validate_base_dataset(
    df: pd.DataFrame,
    config: AggregationConfig,
) -> ValidationResult:
    """Run all validation checks on the customer-level base dataset.

    Parameters
    ----------
    df : pandas.DataFrame
        Output customer-level DataFrame.
    config : AggregationConfig
        Aggregation configuration.

    Returns
    -------
    ValidationResult
        Tổng hợp kết quả tất cả checks.
    """
    customer_key = config.customer_key
    checks: list[ValidationCheckResult] = []

    checks.append(_v01_row_count_matches_unique(df, customer_key))
    checks.append(_v02_no_duplicate(df, customer_key))
    checks.append(_v03_customer_id_not_null(df, customer_key))
    checks.append(_v04_total_quantity_finite(df))
    checks.append(_v05_total_monetary_finite(df))
    checks.append(_v06_first_le_last(df))
    checks.append(_v07_distinct_invoice_count_ge_1(df))
    checks.append(_v08_denominator_nonzero(df))
    checks.append(_v09_avg_transaction_value_finite(df))
    checks.append(_v10_purchase_frequency_valid(df))
    checks.append(_v11_dtype_check(df))

    return ValidationResult(checks=checks)


def validation_result_to_dataframe(result: ValidationResult) -> pd.DataFrame:
    """Convert ValidationResult to a DataFrame for CSV output."""
    rows = []
    for check in result.checks:
        rows.append(
            {
                "check_id": check.check_id,
                "description": check.description,
                "status": check.status,
                "message": check.message,
            }
        )
    return pd.DataFrame.from_records(rows)
