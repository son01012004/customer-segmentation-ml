"""Input validation for the ML-01 clustering experiment framework.

Two distinct validation surfaces:

1. :func:`validate_clustering_matrix` — checks the numeric feature
   matrix that will be fed to the algorithm. Fails fast on missing
   dataset, empty matrix, NaN, Inf, non-numeric columns, missing
   features, or constant columns. **Never mutates the input.**

2. :func:`validate_customer_alignment` — checks that the customer
   metadata (carrying ``CustomerID``) is correctly aligned with the
   feature matrix by row position and by uniqueness of
   ``CustomerID``. The CustomerID must NEVER appear inside the
   clustering matrix.

Both validators return a :class:`ValidationReport` that the runner
writes into the experiment log so failures are explainable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "ValidationCheck",
    "ValidationReport",
    "validate_clustering_matrix",
    "validate_customer_alignment",
    "IdentifierLeakageError",
    "ClusteringInputError",
]


STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"


@dataclass
class ValidationCheck:
    """A single validation check result.

    Mirrors the shape used by FE-06 ``transformations.validators`` so
    the experiment log format is consistent across stages.
    """

    name: str
    status: str  # "PASS" | "FAIL"
    message: str
    details: dict | None = None


@dataclass
class ValidationReport:
    """Aggregated validation report.

    ``all_passed`` is ``True`` iff every check has status PASS. The
    runner inspects this to decide whether to abort the experiment
    before calling the adapter.
    """

    checks: list[ValidationCheck] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.status == STATUS_PASS for c in self.checks)

    def failed(self) -> list[ValidationCheck]:
        """Return only the failed checks."""
        return [c for c in self.checks if c.status == STATUS_FAIL]

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict."""
        return {
            "all_passed": self.all_passed,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class ClusteringInputError(ValueError):
    """Raised when the input matrix fails a hard validation check.

    The runner catches this and turns the failure into
    ``status = FAILED`` with the check messages preserved in the
    experiment log.
    """


class IdentifierLeakageError(ClusteringInputError):
    """Raised when an identifier column is detected in the matrix.

    The ML-01 framework refuses to run if ``CustomerID`` (or any other
    known identifier) leaks into the clustering matrix. This is a hard
    constraint inherited from FE-06.
    """


# Identifiers that MUST NOT appear in the clustering matrix (FE-06 v1.0).
_FORBIDDEN_IDENTIFIERS: frozenset[str] = frozenset(
    {"CustomerID", "InvoiceNo", "InvoiceDate", "StockCode", "Description", "Country"}
)


# ---------------------------------------------------------------------------
# Matrix validation
# ---------------------------------------------------------------------------


def _check_dataset_exists(df: pd.DataFrame | None, source_label: str) -> ValidationCheck:
    name = "dataset_exists"
    if df is None:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Input dataset '{source_label}' is None.",
            details={"source": source_label},
        )
    if not isinstance(df, pd.DataFrame):
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Input dataset '{source_label}' is not a pandas DataFrame.",
            details={"source": source_label, "type": type(df).__name__},
        )
    if df.empty:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Input dataset '{source_label}' is empty.",
            details={"source": source_label},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message=f"Input dataset '{source_label}' is a non-empty DataFrame.",
        details={"rows": len(df), "cols": len(df.columns)},
    )


def _check_all_numeric(df: pd.DataFrame) -> ValidationCheck:
    name = "all_numeric"
    non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    if non_numeric:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Non-numeric columns detected: {non_numeric}.",
            details={"non_numeric_columns": non_numeric},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message="All columns are numeric.",
        details={"numeric_count": len(df.columns)},
    )


def _check_no_nan(df: pd.DataFrame) -> ValidationCheck:
    name = "no_nan"
    nan_per_col = df.isna().sum()
    total = int(nan_per_col.sum())
    if total > 0:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Found {total} NaN values in matrix.",
            details={"nan_columns": {k: int(v) for k, v in nan_per_col.items() if v > 0}},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message="No NaN values in matrix.",
        details={"total_nan": 0},
    )


def _check_no_inf(df: pd.DataFrame) -> ValidationCheck:
    name = "no_inf"
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    inf_counts: dict[str, int] = {}
    for col in numeric_cols:
        n = int(np.isinf(df[col]).sum())
        if n > 0:
            inf_counts[col] = n
    if inf_counts:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Found Inf values in columns: {list(inf_counts.keys())}.",
            details={"inf_columns": inf_counts},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message="No Inf values in matrix.",
        details={"total_inf": 0},
    )


def _check_required_features(
    df: pd.DataFrame,
    expected_features: list[str] | None,
) -> ValidationCheck:
    name = "required_features"
    if expected_features is None:
        return ValidationCheck(
            name=name,
            status=STATUS_PASS,
            message="No required-feature list provided; skipping.",
            details={"expected": None},
        )
    missing = [c for c in expected_features if c not in df.columns]
    if missing:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Required features missing: {missing}.",
            details={"expected": expected_features, "missing": missing},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message=f"All {len(expected_features)} required features present.",
        details={"expected": expected_features},
    )


def _check_no_identifier(df: pd.DataFrame) -> ValidationCheck:
    name = "no_identifier_in_matrix"
    found = [c for c in df.columns if c in _FORBIDDEN_IDENTIFIERS]
    if found:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Identifier columns detected in matrix: {found}.",
            details={"forbidden_found": found},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message="No identifier columns in matrix.",
        details={"forbidden_set": sorted(_FORBIDDEN_IDENTIFIERS)},
    )


def _check_min_samples(df: pd.DataFrame, min_samples: int) -> ValidationCheck:
    name = "min_samples"
    if len(df) < max(min_samples, 1):
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"n_samples={len(df)} < min_samples={min_samples}.",
            details={"n_samples": len(df), "min_samples": min_samples},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message=f"n_samples={len(df)} >= min_samples={min_samples}.",
        details={"n_samples": len(df), "min_samples": min_samples},
    )


def _check_min_features(df: pd.DataFrame, min_features: int) -> ValidationCheck:
    name = "min_features"
    if len(df.columns) < max(min_features, 1):
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"n_features={len(df.columns)} < min_features={min_features}.",
            details={"n_features": len(df.columns), "min_features": min_features},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message=f"n_features={len(df.columns)} >= min_features={min_features}.",
        details={"n_features": len(df.columns), "min_features": min_features},
    )


def _check_no_constant_features(df: pd.DataFrame) -> ValidationCheck:
    name = "no_constant_feature"
    constant: list[str] = []
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        valid = df[col].dropna()
        # Drop inf values to avoid spurious RuntimeWarning during
        # variance computation; Inf is already detected by the
        # no_inf check (which runs first in the pipeline).
        valid = valid[np.isfinite(valid)]
        if len(valid) <= 1:
            continue
        if float(valid.var(ddof=1)) == 0:
            constant.append(col)
    if constant:
        return ValidationCheck(
            name=name,
            status=STATUS_FAIL,
            message=f"Constant features detected: {constant}.",
            details={"constant_columns": constant},
        )
    return ValidationCheck(
        name=name,
        status=STATUS_PASS,
        message="No constant features.",
        details={"constant_count": 0},
    )


def validate_clustering_matrix(
    df: pd.DataFrame,
    *,
    source_label: str = "clustering_matrix",
    expected_features: list[str] | None = None,
    min_samples: int = 2,
    min_features: int = 1,
    fail_fast: bool = True,
) -> ValidationReport:
    """Validate the input clustering matrix.

    Parameters
    ----------
    df : pandas.DataFrame
        Feature matrix. MUST NOT contain ``CustomerID`` or any other
        identifier. MUST be numeric, non-empty, NaN-free, Inf-free.
    source_label : str
        Human-readable label used in error messages (e.g. the file
        path the matrix was loaded from).
    expected_features : list of str, optional
        If provided, every entry must be a column of ``df``.
    min_samples : int
        Minimum acceptable row count.
    min_features : int
        Minimum acceptable column count.
    fail_fast : bool
        If ``True`` (default), raise :class:`IdentifierLeakageError`
        on identifier leakage or :class:`ClusteringInputError` on any
        other FAIL check. If ``False``, the runner can read the report
        instead and decide.

    Returns
    -------
    ValidationReport
        Aggregated check results.

    Raises
    ------
    IdentifierLeakageError
        If an identifier column leaks into the matrix AND
        ``fail_fast=True``.
    ClusteringInputError
        If any check fails AND ``fail_fast=True``.
    """
    if df is None:
        report = ValidationReport(
            checks=[
                ValidationCheck(
                    name="dataset_exists",
                    status=STATUS_FAIL,
                    message=f"Input dataset '{source_label}' is None.",
                    details={"source": source_label},
                )
            ]
        )
        if fail_fast:
            raise ClusteringInputError(f"Input dataset '{source_label}' is None.")
        return report

    report = ValidationReport(
        checks=[
            _check_dataset_exists(df, source_label),
            _check_required_features(df, expected_features),
            _check_no_identifier(df),
            _check_all_numeric(df),
            _check_no_nan(df),
            _check_no_inf(df),
            _check_no_constant_features(df),
            _check_min_samples(df, min_samples),
            _check_min_features(df, min_features),
        ]
    )

    if not report.all_passed and fail_fast:
        # Surface identifier leakage with a dedicated exception type so
        # the runner can mark it as a hard scope violation in the log.
        identifier_check = next(
            (c for c in report.checks if c.name == "no_identifier_in_matrix"),
            None,
        )
        if identifier_check is not None and identifier_check.status == STATUS_FAIL:
            raise IdentifierLeakageError(identifier_check.message)
        messages = [c.message for c in report.failed()]
        raise ClusteringInputError("Clustering matrix validation failed: " + "; ".join(messages))

    return report


# ---------------------------------------------------------------------------
# Customer alignment
# ---------------------------------------------------------------------------


def validate_customer_alignment(
    metadata_df: pd.DataFrame | None,
    matrix_df: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    source_label: str = "customer_metadata",
    fail_fast: bool = True,
) -> ValidationReport:
    """Validate customer metadata alignment with the clustering matrix.

    Hard checks (mirroring FE-06 v1.0 A6):

    1. Metadata row count equals matrix row count.
    2. ``customer_key`` column exists in metadata.
    3. ``customer_key`` values are unique across all rows.
    4. ``customer_key`` has no NaN values.

    The matrix is *never* required to contain ``customer_key`` —
    CustomerID lives in metadata, not in the matrix.

    Parameters
    ----------
    metadata_df : pandas.DataFrame or None
        Customer metadata carrying ``customer_key``.
    matrix_df : pandas.DataFrame
        Clustering matrix.
    customer_key : str
        Name of the customer ID column (default ``"CustomerID"``).
    source_label : str
        Human-readable label used in error messages.
    fail_fast : bool
        If ``True``, raise :class:`ClusteringInputError` on FAIL.

    Returns
    -------
    ValidationReport
        Aggregated check results.

    Raises
    ------
    ClusteringInputError
        If any check fails AND ``fail_fast=True``.
    """
    checks: list[ValidationCheck] = []

    if metadata_df is None:
        checks.append(
            ValidationCheck(
                name="metadata_present",
                status=STATUS_FAIL,
                message=f"Customer metadata '{source_label}' is None.",
                details={"source": source_label},
            )
        )
        report = ValidationReport(checks=checks)
        if fail_fast:
            raise ClusteringInputError(f"Customer metadata '{source_label}' is None.")
        return report

    checks.append(
        _check_dataset_exists(metadata_df, source_label),
    )
    # Replace the dataset_exists check label with one specific to metadata.
    checks[-1] = ValidationCheck(
        name="metadata_present",
        status=checks[-1].status,
        message=checks[-1].message,
        details=checks[-1].details,
    )

    # 1. Row counts
    if len(metadata_df) != len(matrix_df):
        checks.append(
            ValidationCheck(
                name="metadata_row_alignment",
                status=STATUS_FAIL,
                message=(
                    f"Metadata rows ({len(metadata_df)}) != matrix rows " f"({len(matrix_df)})."
                ),
                details={
                    "metadata_rows": len(metadata_df),
                    "matrix_rows": len(matrix_df),
                },
            )
        )
    else:
        checks.append(
            ValidationCheck(
                name="metadata_row_alignment",
                status=STATUS_PASS,
                message="Metadata and matrix row counts match.",
                details={
                    "metadata_rows": len(metadata_df),
                    "matrix_rows": len(matrix_df),
                },
            )
        )

    # 2. Customer key column
    if customer_key not in metadata_df.columns:
        checks.append(
            ValidationCheck(
                name="customer_key_present",
                status=STATUS_FAIL,
                message=f"Customer key '{customer_key}' not in metadata.",
                details={"columns": list(metadata_df.columns)},
            )
        )
    else:
        checks.append(
            ValidationCheck(
                name="customer_key_present",
                status=STATUS_PASS,
                message=f"Customer key '{customer_key}' present.",
                details={"column": customer_key},
            )
        )

    # 3. Customer key uniqueness
    if customer_key in metadata_df.columns:
        n_unique = int(metadata_df[customer_key].nunique(dropna=True))
        n_total = int(len(metadata_df))
        if n_unique != n_total:
            checks.append(
                ValidationCheck(
                    name="customer_key_unique",
                    status=STATUS_FAIL,
                    message=(
                        f"Customer key '{customer_key}' is not unique: "
                        f"{n_unique} unique across {n_total} rows."
                    ),
                    details={"unique": n_unique, "total": n_total},
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    name="customer_key_unique",
                    status=STATUS_PASS,
                    message=(f"Customer key '{customer_key}' unique across " f"{n_total} rows."),
                    details={"unique": n_unique, "total": n_total},
                )
            )

        # 4. Customer key NaN
        n_nan = int(metadata_df[customer_key].isna().sum())
        if n_nan > 0:
            checks.append(
                ValidationCheck(
                    name="customer_key_no_nan",
                    status=STATUS_FAIL,
                    message=(f"Customer key '{customer_key}' has {n_nan} NaN values."),
                    details={"nan_count": n_nan},
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    name="customer_key_no_nan",
                    status=STATUS_PASS,
                    message=f"Customer key '{customer_key}' has no NaN values.",
                    details={"nan_count": 0},
                )
            )

    report = ValidationReport(checks=checks)
    if not report.all_passed and fail_fast:
        messages = [c.message for c in report.failed()]
        raise ClusteringInputError("Customer alignment validation failed: " + "; ".join(messages))
    return report
