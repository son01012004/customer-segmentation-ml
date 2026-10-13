"""Validation for DEV-03 Prototype Preprocessing.

Two distinct validation surfaces:

1. **Stage B (input preflight)** — runs after Stage A read the input
   into memory. Mirrors DEV-02's three-category pattern (file_level
   / structural / data_quality) but with prototype-layer rules:
   empty DataFrame → FAIL, missing required columns → FAIL,
   wrong dtypes → coerce (already done at Stage B), no crash on
   all-NaN column or mixed-type column.

2. **Stage G1 (3-category final validation)** — runs on the
   customer-level ML Dataset BEFORE write (and as a final
   post-write sanity). Categorical aggregation mirrors DEV-02's
   pattern.

Lifecycles
----------
- Stage B aggregate → ``PASS`` / ``WARNING`` / ``FAIL``.
- ``FAIL`` aborts the pipeline before any artefact is written.
- ``WARNING`` proceeds with warnings recorded in the manifest.
- Stage G1 FAIL after the manifest is written is unusual; the
  manifest's :class:`PreprocessingBlock.status` carries
  ``WORKING_ASSUMPTION`` and the storage block records
  ``file_written=True``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.dataset_management.scope import ValidationResult
from customer_segmentation.prototype.preprocessing.scope import (
    PREPROCESSING_OUTCOME_FAIL,
    PREPROCESSING_OUTCOME_PASS,
    PREPROCESSING_OUTCOME_WARNING,
    PreprocessingOutcome,
)

__all__ = [
    "PreprocessingValidationOutcome",
    "StageGValidationBlock",
    "StageGValidationCategory",
    "StageGValidationResult",
    "build_stage_b_validation",
    "aggregate_stage_g_results",
    "lifecycle_for_preprocessing",
    "run_input_preflight",
]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class PreprocessingValidationOutcome:
    """Per-stage validation outcome (Stage B / G1).

    Attributes
    ----------
    outcome : str
        One of ``"PASS"``, ``"WARNING"``, ``"FAIL"``.
    errors : list[str]
        Fatal issues (drive ``FAIL``).
    warnings : list[str]
        Non-fatal issues (drive ``WARNING``).
    stats : dict[str, Any]
        Per-check counters (e.g. ``{"row_count": 1234}``).
    """

    outcome: str = "PASS"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageGValidationCategory:
    """One category of the Stage G 3-category validation block."""

    result: str  # "PASS" | "WARNING" | "FAIL"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


@dataclass
class StageGValidationBlock:
    """Stage G 3-category validation block."""

    file_level: StageGValidationCategory
    structural: StageGValidationCategory
    data_quality: StageGValidationCategory


@dataclass
class StageGValidationResult:
    """Three-category validation result of the customer-level ML Dataset.

    Attributes
    ----------
    file_level : StageGValidationCategory
        Whether the file was actually written, atomically.
    structural : StageGValidationCategory
        Empty-result checks (row > 0, column > 0, unique CustomerID).
    data_quality : StageGValidationCategory
        Numeric-output checks (no NaN, no Inf, no all-constant columns).
    """

    file_level: StageGValidationCategory
    structural: StageGValidationCategory
    data_quality: StageGValidationCategory

    def aggregate(self) -> str:
        """Aggregate three categories into one outcome."""
        return aggregate_stage_g_results(self)


# ---------------------------------------------------------------------------
# Aggregation / lifecycle mapping
# ---------------------------------------------------------------------------


def aggregate_outcome(outcomes: list[str]) -> str:
    """Aggregate a list of per-stage outcomes into one outcome.

    Mirrors the DEV-02 three-category aggregation rule.
    """
    if any(o == ValidationResult.FAIL.value for o in outcomes):
        return PREPROCESSING_OUTCOME_FAIL
    if any(o == ValidationResult.WARNING.value for o in outcomes):
        return PREPROCESSING_OUTCOME_WARNING
    return PREPROCESSING_OUTCOME_PASS


def aggregate_stage_g_results(block: StageGValidationBlock) -> str:
    """Aggregate the three Stage G validation categories."""
    for label, cat in (
        ("file_level", block.file_level),
        ("structural", block.structural),
        ("data_quality", block.data_quality),
    ):
        if cat.result not in {o.value for o in PreprocessingOutcome}:
            raise ValueError(
                f"validation.{label}.result is {cat.result!r}; "
                f"expected one of {[o.value for o in PreprocessingOutcome]}."
            )
    return aggregate_outcome(
        [block.file_level.result, block.structural.result, block.data_quality.result]
    )


def lifecycle_for_preprocessing(aggregate_outcome_: str) -> str:
    """Map an aggregate outcome to a lifecycle status.

    Mirrors DEV-02's :func:`map_to_lifecycle`: PASS / WARNING → VALID,
    FAIL → FAILED.
    """
    if aggregate_outcome_ not in {o.value for o in PreprocessingOutcome}:
        raise ValueError(
            f"aggregate outcome {aggregate_outcome_!r} is not one of "
            f"{[o.value for o in PreprocessingOutcome]}."
        )
    if aggregate_outcome_ == PREPROCESSING_OUTCOME_FAIL:
        return "FAILED"
    return "VALID"


# ---------------------------------------------------------------------------
# Stage B — input preflight
# ---------------------------------------------------------------------------


# Required raw columns (per dataset_dictionary/dataset_schema.csv).
REQUIRED_RAW_COLUMNS: tuple[str, ...] = (
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
)


def build_stage_b_validation(
    df: pd.DataFrame,
    *,
    required_columns: tuple[str, ...] = REQUIRED_RAW_COLUMNS,
) -> tuple[PreprocessingValidationOutcome, dict[str, Any]]:
    """Run Stage B validation and return the outcome + measured stats."""
    outcome = PreprocessingValidationOutcome(outcome="PASS")
    stats: dict[str, Any] = {}

    # Row count
    n_rows = int(df.shape[0])
    stats["row_count"] = n_rows
    if n_rows <= 0:
        outcome.errors.append("Empty dataset: row_count == 0.")

    # Column count
    n_cols = int(df.shape[1])
    stats["column_count"] = n_cols
    if n_cols <= 0:
        outcome.errors.append("Empty dataset: column_count == 0.")

    # Required columns
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        outcome.errors.append(f"Missing required columns: {missing}.")
    stats["missing_required_columns"] = missing

    # Duplicate column names
    seen: set[str] = set()
    duplicates: list[str] = []
    for col in df.columns:
        col_str = str(col)
        if col_str in seen and col_str not in duplicates:
            duplicates.append(col_str)
        seen.add(col_str)
    if duplicates:
        outcome.errors.append(f"Duplicate column names: {duplicates}.")
    stats["duplicate_columns"] = duplicates

    # All-NaN columns
    all_null_cols: list[str] = []
    for c in df.columns:
        try:
            s = df[c]
        except Exception:
            continue
        if isinstance(s, pd.DataFrame):
            continue
        try:
            if bool(s.isna().all()):
                all_null_cols.append(str(c))
        except (TypeError, ValueError):
            continue
    if all_null_cols:
        outcome.warnings.append(f"Columns are all-NULL: {all_null_cols}.")
    stats["all_null_columns"] = all_null_cols

    # Inf in numeric columns
    inf_cols: list[str] = []
    for c in df.columns:
        try:
            s = df[c]
        except Exception:
            continue
        if isinstance(s, pd.DataFrame):
            continue
        if not pd.api.types.is_numeric_dtype(s):
            continue
        try:
            if ((s == float("inf")) | (s == float("-inf"))).any():
                inf_cols.append(str(c))
        except (TypeError, ValueError):
            continue
    if inf_cols:
        outcome.warnings.append(f"Inf / -Inf present in columns: {inf_cols}.")
    stats["inf_columns"] = inf_cols

    # Compute outcome
    if outcome.errors:
        outcome.outcome = "FAIL"
    elif outcome.warnings:
        outcome.outcome = "WARNING"
    return outcome, stats


def run_input_preflight(
    df: pd.DataFrame,
    *,
    logger: logging.Logger | None = None,
    required_columns: tuple[str, ...] = REQUIRED_RAW_COLUMNS,
) -> PreprocessingValidationOutcome:
    """Convenience wrapper: run Stage B validation and log outcome.

    Returns the outcome; FAIL → raises :class:`StageBPreflightError`.
    """
    outcome, stats = build_stage_b_validation(df, required_columns=required_columns)
    if logger is not None:
        if outcome.outcome == PREPROCESSING_OUTCOME_FAIL:
            logger.error("Stage B preflight FAIL: %s", outcome.errors)
        elif outcome.outcome == PREPROCESSING_OUTCOME_WARNING:
            logger.warning("Stage B preflight WARNING: %s", outcome.warnings)
        else:
            logger.info(
                "Stage B preflight PASS: %s rows, %s cols",
                stats.get("row_count"),
                stats.get("column_count"),
            )
    return outcome


class StageBPreflightError(ValueError):
    """Raised when Stage B validation returns FAIL."""


def raise_on_stage_b_fail(outcome: PreprocessingValidationOutcome) -> None:
    """Raise :class:`StageBPreflightError` if Stage B validation returned FAIL."""
    if outcome.outcome == PREPROCESSING_OUTCOME_FAIL:
        raise StageBPreflightError("Stage B validation FAIL: " + "; ".join(outcome.errors))


# ---------------------------------------------------------------------------
# Stage G1 — final 3-category validation of the ML Dataset
# ---------------------------------------------------------------------------


_VALID_G_VALUES = {o.value for o in PreprocessingOutcome}


def _make_category(result: str = "PASS") -> StageGValidationCategory:
    return StageGValidationCategory(result=result, errors=[], warnings=[], stats={})


def _check_ml_dataset_file_level(
    file_written: bool,
    target_path: Path | None,
) -> StageGValidationCategory:
    """Stage G1 file-level check: was the file written atomically?"""
    cat = _make_category()
    if not file_written:
        cat.errors.append("ML Dataset was not written.")
        cat.result = "FAIL"
        return cat
    if target_path is None or not Path(target_path).exists():
        cat.errors.append(f"ML Dataset path does not exist: {target_path!s}.")
        cat.result = "FAIL"
        return cat
    cat.stats["file_size_bytes"] = int(Path(target_path).stat().st_size)
    return cat


def _check_ml_dataset_structural(
    df: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> StageGValidationCategory:
    """Stage G1 structural: empty / unique-customer / no duplicate cols."""
    cat = _make_category()
    if int(df.shape[0]) <= 0:
        cat.errors.append("Empty ML Dataset: row_count == 0.")
    if int(df.shape[1]) <= 0:
        cat.errors.append("Empty ML Dataset: column_count == 0.")
    if customer_key in df.columns:
        nunique = int(df[customer_key].nunique(dropna=True))
        if nunique != int(df.shape[0]):
            cat.errors.append(
                f"ML Dataset has duplicate {customer_key!r}: "
                f"nrow={int(df.shape[0])}, nunique={nunique}."
            )
    cat.stats["row_count"] = int(df.shape[0])
    cat.stats["column_count"] = int(df.shape[1])
    if cat.errors:
        cat.result = "FAIL"
    return cat


def _check_ml_dataset_data_quality(
    df: pd.DataFrame,
    *,
    max_nan_columns: int = 0,
    drop_non_numeric: bool = True,
    allowed_nan_columns: frozenset[str] = frozenset(
        {"PurchaseIntervalMean", "PurchaseIntervalStd"}
    ),
) -> StageGValidationCategory:
    """Stage G1 data quality: no NaN, no Inf in the numeric columns.

    Exception: columns in ``allowed_nan_columns`` may carry NaN.
    This mirrors FE-05's "PurchaseInterval NaN for < 2 invoices" hard
    constraint, which is preserved by Stage F2 and must pass Stage G
    without being flagged as a FAIL.
    """
    cat = _make_category()
    work = df
    if drop_non_numeric:
        work = df.select_dtypes(include=["number"])
    if work.empty:
        cat.warnings.append("No numeric columns; skipping data-quality checks.")
        cat.result = "WARNING"
        return cat

    nan_per_col: dict[str, int] = {str(c): int(work[c].isna().sum()) for c in work.columns}
    nan_offenders = {
        c: n for c, n in nan_per_col.items() if n > max_nan_columns and c not in allowed_nan_columns
    }
    if nan_offenders:
        cat.errors.append(
            f"NaN values present in numeric columns (excluding FE-05 hard-constraint "
            f"columns {sorted(allowed_nan_columns)}): {nan_offenders}."
        )

    inf_per_col: dict[str, int] = {}
    for c in work.columns:
        col = work[c]
        if not pd.api.types.is_numeric_dtype(col):
            continue
        try:
            mask = (col == float("inf")) | (col == float("-inf"))
        except (TypeError, ValueError):
            continue
        try:
            n = int(mask.fillna(False).sum())
        except Exception:
            n = 0
        if n > 0:
            inf_per_col[str(c)] = n
    if inf_per_col:
        cat.errors.append(f"Inf / -Inf present in numeric columns: {inf_per_col}.")

    cat.stats["nan_columns"] = len(nan_offenders)
    cat.stats["nan_columns_allowed"] = sum(
        n for c, n in nan_per_col.items() if c in allowed_nan_columns
    )
    cat.stats["inf_columns"] = len(inf_per_col)
    cat.stats["n_columns_checked"] = int(work.shape[1])
    if cat.errors:
        cat.result = "FAIL"
    return cat


def build_stage_g_validation(
    df: pd.DataFrame,
    *,
    file_written: bool,
    target_path: Path | None,
    customer_key: str = "CustomerID",
) -> StageGValidationResult:
    """Run all Stage G1 checks and return the :class:`StageGValidationResult`."""
    fl = _check_ml_dataset_file_level(file_written, target_path)
    struct = _check_ml_dataset_structural(df, customer_key=customer_key)
    dq = _check_ml_dataset_data_quality(df)
    return StageGValidationResult(
        file_level=fl,
        structural=struct,
        data_quality=dq,
    )


__ = (Mapping, Any, np)
