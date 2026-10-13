"""Validation rules for DEV-02.

DEV-02 separates two concepts that are often conflated:

- :class:`customer_segmentation.dataset_management.scope.ValidationStatus`
  — the *lifecycle status* of a dataset. The manifest stores one of
  these values per dataset.
- :class:`customer_segmentation.dataset_management.scope.ValidationResult`
  — the *per-pass outcome* of one validation pass. ``PASS`` /
  ``WARNING`` / ``FAIL``.

The mapping from aggregate result to lifecycle status is defined in
:func:`map_to_lifecycle`.

Three independent categories are validated per pass:

- ``file_level``    — only ``PASS`` / ``FAIL``. This category is
  settled in Stage A (file preflight) and is recorded for idempotency.
- ``structural``    — may be ``PASS`` / ``WARNING`` / ``FAIL``.
- ``data_quality``  — may be ``PASS`` / ``WARNING`` / ``FAIL``.

The aggregate result is:

- ``PASS``     if all three categories are ``PASS``.
- ``WARNING``  if at least one is ``WARNING`` and none is ``FAIL``.
- ``FAIL``     if at least one is ``FAIL``.

The lifecycle status is then:

- ``PASS``    → ``VALID``
- ``WARNING`` → ``VALID`` (with ``validation.warnings[]`` populated)
- ``FAIL``    → ``FAILED``
- (no pass)  → ``NOT_VALIDATED`` (only if a manifest is hand-edited;
  not reachable from the public import API)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from customer_segmentation.dataset_management.scope import (
    VALIDATION_RESULTS,
    VALIDATION_STATUSES,
    ValidationResult as _VR,
    ValidationStatus as _VS,
)

__all__ = [
    "CategoryResult",
    "ValidationBlock",
    "FilePreflightError",
    "run_validation",
    "aggregate",
    "map_to_lifecycle",
]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class CategoryResult:
    """Outcome of one validation category.

    Attributes
    ----------
    result : str
        ``"PASS"``, ``"WARNING"``, or ``"FAIL"``.
    errors : list[str]
        Fatal issues (used to drive FAIL).
    warnings : list[str]
        Non-fatal issues (used to drive WARNING).
    stats : dict[str, int]
        Per-check counters (e.g. ``{"nan_columns": 2}``).
    """

    result: str = "PASS"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


@dataclass
class ValidationBlock:
    """Three-category validation block."""

    file_level: CategoryResult
    structural: CategoryResult
    data_quality: CategoryResult


# ---------------------------------------------------------------------------
# File-level preflight exception
# ---------------------------------------------------------------------------


class FilePreflightError(ValueError):
    """Raised in Stage A of the import pipeline for a fatal file-level issue.

    The pipeline catches this exception and records the error in the
    manifest's ``file_level`` category without writing an artefact.
    """


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate(block: ValidationBlock) -> str:
    """Aggregate three category results into one :class:`ValidationResult`.

    Returns ``"PASS"``, ``"WARNING"``, or ``"FAIL"``. Raises
    :class:`ValueError` if any category contains an invalid value.
    """
    for label, cat in (
        ("file_level", block.file_level),
        ("structural", block.structural),
        ("data_quality", block.data_quality),
    ):
        if cat.result not in VALIDATION_RESULTS:
            raise ValueError(
                f"validation.{label}.result is {cat.result!r}; "
                f"expected one of {sorted(VALIDATION_RESULTS)}."
            )
    if any(c.result == _VR.FAIL.value for c in (block.file_level, block.structural, block.data_quality)):
        return _VR.FAIL.value
    if any(c.result == _VR.WARNING.value for c in (block.structural, block.data_quality)):
        return _VR.WARNING.value
    return _VR.PASS.value


def map_to_lifecycle(aggregate_result: str) -> str:
    """Map an aggregate :class:`ValidationResult` to a lifecycle status.

    Raises :class:`ValueError` if the input is not a valid result.
    """
    if aggregate_result not in VALIDATION_RESULTS:
        raise ValueError(
            f"aggregate result {aggregate_result!r} is not one of "
            f"{sorted(VALIDATION_RESULTS)}."
        )
    if aggregate_result == _VR.FAIL.value:
        return _VS.FAILED.value
    # PASS or WARNING -> VALID
    return _VS.VALID.value


# ---------------------------------------------------------------------------
# Rules — structural
# ---------------------------------------------------------------------------


_SHELL_UNSAFE = set(" \t\n\r\\'\"`$;&|<>(){}[]*?!#~")


def _check_column_names(df: pd.DataFrame, structural: CategoryResult) -> None:
    """Apply the column-name structural checks.

    Tolerant of duplicate column names: the duplicate is recorded as
    an error, but the iteration over ``df.columns`` (which yields
    duplicate names once each in pandas ≥ 1.x) does not crash.
    """
    seen: set[str] = set()
    for col in df.columns:
        col_str = str(col)
        if not col_str:
            structural.errors.append("Empty column name found.")
            continue
        if col_str in seen:
            structural.errors.append(f"Duplicate column name: {col_str!r}.")
        else:
            seen.add(col_str)
        for ch in col_str:
            if ch in _SHELL_UNSAFE:
                structural.errors.append(
                    f"Column {col_str!r} contains shell-unsafe character {ch!r}."
                )
                break
        for ch in col_str:
            if not (ch.isalnum() or ch in "._-"):
                structural.errors.append(
                    f"Column {col_str!r} contains non [A-Za-z0-9_.-] character {ch!r}."
                )
                break


def _check_all_null_columns(df: pd.DataFrame, structural: CategoryResult) -> None:
    """Record each all-NULL column as a structural WARNING.

    Handles duplicate column names: ``df[col]`` may return a
    DataFrame instead of a Series; in that case we coerce via
    ``pd.concat``.
    """
    n_all_null = 0
    for col in df.columns:
        try:
            s = df[col]
        except Exception:
            continue
        if isinstance(s, pd.DataFrame):
            # Duplicate column name: pandas returns a DataFrame.
            all_null = bool(pd.concat([s[c] for c in s.columns], axis=1).isna().all().all())
        else:
            try:
                all_null = bool(s.isna().all())
            except (TypeError, ValueError):
                all_null = False
        if all_null:
            structural.warnings.append(f"Column {str(col)!r} is all-NULL.")
            n_all_null += 1
    structural.stats["all_null_columns"] = n_all_null


def _check_row_count(df: pd.DataFrame, structural: CategoryResult) -> None:
    if int(df.shape[0]) <= 0:
        structural.errors.append("Empty file: row_count == 0.")
    structural.stats["row_count"] = int(df.shape[0])


def _check_column_count(df: pd.DataFrame, structural: CategoryResult) -> None:
    if int(df.shape[1]) <= 0:
        structural.errors.append("Empty file: column_count == 0.")
    structural.stats["column_count"] = int(df.shape[1])


def run_structural(df: pd.DataFrame) -> CategoryResult:
    """Run the structural validation rules on a DataFrame."""
    cat = CategoryResult(result="PASS")
    _check_row_count(df, cat)
    _check_column_count(df, cat)
    _check_column_names(df, cat)
    _check_all_null_columns(df, cat)
    if cat.errors:
        cat.result = "FAIL"
    elif cat.warnings:
        cat.result = "WARNING"
    return cat


# ---------------------------------------------------------------------------
# Rules — data quality
# ---------------------------------------------------------------------------


_INF_DTYPES = frozenset({"float", "float64", "float32", "complex64", "complex128"})


def _check_nan(df: pd.DataFrame, cat: CategoryResult) -> None:
    """Count columns with any NaN; tolerant of duplicate column names."""
    nan_columns: list[str] = []
    for c in df.columns:
        try:
            s = df[c]
        except Exception:
            continue
        if isinstance(s, pd.DataFrame):
            # Duplicate column: any NaN across the duplicated sub-DataFrame.
            try:
                has_nan = bool(pd.concat([s[c2] for c2 in s.columns], axis=1).isna().any().any())
            except Exception:
                has_nan = False
        else:
            try:
                has_nan = bool(s.isna().any())
            except (TypeError, ValueError):
                has_nan = False
        if has_nan:
            nan_columns.append(str(c))
    if nan_columns:
        cat.warnings.append(
            f"NaN values present in {len(nan_columns)} column(s)."
        )
    cat.stats["nan_columns"] = len(nan_columns)


def _check_inf(df: pd.DataFrame, cat: CategoryResult) -> None:
    """Detect Inf / -Inf in numeric columns; tolerant of duplicates."""
    inf_columns: list[str] = []
    for c in df.columns:
        try:
            s = df[c]
        except Exception:
            continue
        if isinstance(s, pd.DataFrame):
            # Iterate sub-columns.
            for c2 in s.columns:
                if not pd.api.types.is_numeric_dtype(s[c2]):
                    continue
                try:
                    if ((s[c2] == float("inf")) | (s[c2] == float("-inf"))).any():
                        inf_columns.append(str(c))
                        break
                except TypeError:
                    continue
            continue
        if not pd.api.types.is_numeric_dtype(s):
            continue
        try:
            if ((s == float("inf")) | (s == float("-inf"))).any():
                inf_columns.append(str(c))
        except TypeError:
            continue
    if inf_columns:
        cat.warnings.append(
            f"Inf / -Inf values present in {len(inf_columns)} column(s)."
        )
    cat.stats["inf_columns"] = len(inf_columns)


def _check_constant(df: pd.DataFrame, cat: CategoryResult) -> None:
    """Detect constant columns.

    Skips bool columns (in DEV-02 bool columns are not "constant" in
    the same sense; they are a separate dtype) and is tolerant of
    duplicate column names.
    """
    constant_columns: list[str] = []
    for c in df.columns:
        try:
            s = df[c]
        except Exception:
            continue
        if isinstance(s, pd.DataFrame):
            # Duplicate column name: skip the duplicate check.
            continue
        if pd.api.types.is_bool_dtype(s):
            continue
        try:
            s_dropped = s.dropna()
        except (TypeError, ValueError):
            continue
        if not s_dropped.empty and s_dropped.nunique(dropna=True) == 1:
            constant_columns.append(str(c))
    if constant_columns:
        cat.warnings.append(
            f"Constant columns (single unique value): {len(constant_columns)}."
        )
    cat.stats["constant_columns"] = len(constant_columns)


def _check_duplicate_rows(df: pd.DataFrame, cat: CategoryResult) -> None:
    """Count full-row duplicates; explicit int conversion to avoid
    numpy boolean arithmetic surprises."""
    try:
        dup = int(df.duplicated().sum())
    except (TypeError, ValueError):
        dup = 0
    if dup > 0:
        cat.warnings.append(f"Duplicate rows: {dup}.")
    cat.stats["duplicate_rows"] = dup


def _check_mixed_columns(
    df: pd.DataFrame,
    cat: CategoryResult,
    *,
    sample_size: int = 1000,
) -> None:
    """Detect mixed-type columns deterministically.

    Skips duplicate column names (already flagged structurally).
    """
    from customer_segmentation.dataset_management.importer import detect_mixed

    mixed: list[str] = []
    for c in df.columns:
        try:
            s = df[c]
        except Exception:
            continue
        if isinstance(s, pd.DataFrame):
            continue
        try:
            if detect_mixed(s, sample_size=sample_size):
                mixed.append(str(c))
        except Exception:
            continue
    if mixed:
        cat.warnings.append(
            f"Mixed-type columns: {len(mixed)} column(s)."
        )
    cat.stats["mixed_columns"] = len(mixed)


def run_data_quality(df: pd.DataFrame) -> CategoryResult:
    """Run the data-quality validation rules on a DataFrame."""
    cat = CategoryResult(result="PASS")
    _check_nan(df, cat)
    _check_inf(df, cat)
    _check_constant(df, cat)
    _check_duplicate_rows(df, cat)
    _check_mixed_columns(df, cat)
    cat.result = "WARNING" if cat.warnings else "PASS"
    return cat


# ---------------------------------------------------------------------------
# Rules — file level
# ---------------------------------------------------------------------------


def make_file_level_result(
    *,
    passed: bool,
    errors: list[str] | None = None,
) -> CategoryResult:
    """Build a file-level :class:`CategoryResult`.

    The CLI uses this to record the result of Stage A without
    re-running preflight in :func:`run_validation`.
    """
    return CategoryResult(
        result="PASS" if passed else "FAIL",
        errors=list(errors) if errors else [],
        warnings=[],
        stats={},
    )


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------


def run_validation(
    df: pd.DataFrame,
    file_level: CategoryResult,
) -> ValidationBlock:
    """Run the full validation pipeline on a DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame to validate. The function does not mutate it.
    file_level : CategoryResult
        The pre-computed file-level result (from Stage A).

    Returns
    -------
    ValidationBlock
        The three-category validation result.

    Notes
    -----
    This is the **only** validation runner exposed by DEV-02. The
    CLI uses it once per import, with ``file_level`` reflecting the
    outcome of the file preflight in Stage A.
    """
    structural = run_structural(df)
    data_quality = run_data_quality(df)
    return ValidationBlock(
        file_level=file_level,
        structural=structural,
        data_quality=data_quality,
    )


# ---------------------------------------------------------------------------
# Lifecycle status (aliasing helpers)
# ---------------------------------------------------------------------------


def lifecycle_status_for_pass(aggregate_result: str) -> str:
    """Same as :func:`map_to_lifecycle`; provided for naming parity.

    Kept distinct from :func:`map_to_lifecycle` for tests that want a
    name that reads naturally in a manifest construction context.
    """
    return map_to_lifecycle(aggregate_result)


def is_valid_lifecycle_status(value: str) -> bool:
    """Return whether ``value`` is a valid lifecycle status string."""
    return value in VALIDATION_STATUSES


# `Any` import is intentionally kept referenced to avoid "unused
# import" lints; the type is exposed for type-hint convenience in
# future extension points.
_ = Any
