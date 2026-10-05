"""End-to-end cleaning pipeline for FE-02.

The cleaning pipeline is a deterministic, fully traceable composition
of the four preprocessing stages:

1. **Type coercion** — ensure ``InvoiceDate`` is ``datetime64[ns]`` and
   ``CustomerID`` is a nullable integer (``Int64``). This step does not
   drop any rows; it only fixes representations.
2. **Invalid-record filtering + flagging** — apply :class:`InvalidRecordRules`.
   This is where cancellations and returns are flagged and the obvious
   data-quality issues (missing IDs, missing dates, non-positive prices,
   exact-row duplicates) are dropped.
3. **Missing-value handling** — apply :func:`handle_missing` with the
   strategy declared in the configuration.
4. **Optional outlier handling** — :func:`treat_outliers`. Off by
   default because outlier policy is not yet approved.

The pipeline never mutates the input. The raw DataFrame is returned
unchanged; the cleaned DataFrame, drop report, and per-stage statistics
are returned in :class:`CleaningResult`.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from customer_segmentation.preprocessing.duplicates import (
    DuplicateResult,
)
from customer_segmentation.preprocessing.duplicates import (
    drop_duplicates as _drop_duplicates,
)
from customer_segmentation.preprocessing.invalid_records import (
    InvalidRecordResult,
    InvalidRecordRules,
    apply_invalid_rules,
)
from customer_segmentation.preprocessing.missing_values import (
    MissingHandlingResult,
)
from customer_segmentation.preprocessing.missing_values import (
    handle_missing as _handle_missing,
)
from customer_segmentation.preprocessing.outliers import (
    OutlierResult,
)
from customer_segmentation.preprocessing.outliers import (
    treat_outliers as _treat_outliers,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """Typed configuration for the FE-02 cleaning pipeline.

    Attributes
    ----------
    invalid_rules : InvalidRecordRules
        Invalid-record rules (drop flags + flag toggles).
    missing_strategy : str
        Strategy applied to remaining missing values (after the invalid
        rules have already dropped the most egregious ones). Use
        ``"keep"`` to leave any residual missing values untouched.
    missing_columns : list[str]
        Columns that ``missing_strategy`` applies to.
    duplicate_subset : list[str] or None
        Subset used by the duplicate-removal step. ``None`` means
        exact-row deduplication.
    duplicate_keep : {"first", "last", "none"}
        Which duplicate occurrence to keep.
    outlier_action : {"clip", "remove", "flag", "none"}
        Outlier handling. ``"none"`` skips outlier processing entirely.
    outlier_method : {"iqr", "zscore"}
        Outlier detection method (only used if ``outlier_action != "none"``).
    outlier_columns : list[str]
        Columns that the outlier step inspects.
    """

    invalid_rules: InvalidRecordRules = field(default_factory=InvalidRecordRules)
    missing_strategy: str = "keep"
    missing_columns: list[str] = field(default_factory=list)
    duplicate_subset: list[str] | None = None
    duplicate_keep: str = "first"
    outlier_action: str = "none"
    outlier_method: str = "iqr"
    outlier_columns: list[str] = field(default_factory=list)
    # Multiplier / threshold used by the outlier algorithms. Only
    # consulted when :attr:`outlier_action` is not ``"none"`` and
    # :attr:`outlier_columns` is non-empty. Defaults match the module
    # constants in ``preprocessing.outliers``.
    outlier_iqr_multiplier: float = 1.5
    outlier_zscore_threshold: float = 3.0


def default_pipeline_config() -> PipelineConfig:
    """Return the default FE-02 pipeline configuration.

    Returns
    -------
    PipelineConfig
        Configuration that matches the FE-01 audit findings:

        - ``CustomerID`` missing → drop (cannot do customer-level
          analysis without it).
        - ``Description`` missing → drop.
        - ``InvoiceDate`` unparseable → drop.
        - ``InvoiceNo`` missing or empty → drop.
        - ``Quantity == 0`` → drop.
        - ``UnitPrice <= 0`` → drop.
        - ``Quantity < 0`` → flag as ``IsReturn`` (not dropped).
        - ``InvoiceNo`` starting with ``"C"`` → flag as
          ``IsCancellation`` (not dropped).
        - Exact-row duplicates → drop (keep="first").
        - No outlier processing (``outlier_action="none"``).
    """
    return PipelineConfig(
        invalid_rules=InvalidRecordRules(),
        missing_strategy="keep",
        missing_columns=[],
        duplicate_subset=None,
        duplicate_keep="first",
        outlier_action="none",
        outlier_method="iqr",
        outlier_columns=[],
        outlier_iqr_multiplier=1.5,
        outlier_zscore_threshold=3.0,
    )


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class CleaningResult:
    """Result of the full cleaning pipeline.

    Attributes
    ----------
    df : pandas.DataFrame
        Cleaned DataFrame.
    report : dict[str, Any]
        Per-stage summary (counters, removed counts, rule IDs).
    invalid : InvalidRecordResult or None
        Detailed result from the invalid-record stage.
    duplicates : DuplicateResult or None
        Detailed result from the duplicate stage.
    missing : MissingHandlingResult or None
        Detailed result from the missing-value stage.
    outliers : OutlierResult or None
        Detailed result from the outlier stage.
    """

    df: pd.DataFrame
    report: dict[str, Any]
    invalid: InvalidRecordResult | None = None
    duplicates: DuplicateResult | None = None
    missing: MissingHandlingResult | None = None
    outliers: OutlierResult | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce ``InvoiceDate`` to datetime and ``CustomerID`` to ``Int64``.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.

    Returns
    -------
    pandas.DataFrame
        Copy of the input with the following columns coerced:

        - ``InvoiceDate`` → ``datetime64[ns]`` (unparseable values become
          ``NaT``).
        - ``CustomerID`` → ``Int64`` (pandas nullable integer; missing
          values become ``pd.NA``).
        - ``InvoiceNo`` → ``string`` (since the raw column mixes
          integers like ``536365`` with ``C``-prefixed cancellations like
          ``"C536379"``; a single string dtype is the only consistent
          representation).

        Other columns are unchanged.

    Notes
    -----
    This step is purely a representation fix. It never drops rows.
    Unparseable dates and missing IDs are handled later by
    :func:`apply_invalid_rules`.
    """
    work = df.copy(deep=True)

    if "InvoiceDate" in work.columns and not pd.api.types.is_datetime64_any_dtype(
        work["InvoiceDate"]
    ):
        work["InvoiceDate"] = pd.to_datetime(work["InvoiceDate"], errors="coerce")

    if "CustomerID" in work.columns:
        # Convert from float64 to the pandas nullable Int64 so missing IDs
        # are properly represented as ``pd.NA`` (and not as ``NaN`` that
        # downstream code might accidentally treat as a number).
        with contextlib.suppress(TypeError, ValueError):
            work["CustomerID"] = (
                pd.to_numeric(work["CustomerID"], errors="coerce").round().astype("Int64")
            )

    if "InvoiceNo" in work.columns:
        # The raw column mixes integers and C-prefixed strings. Normalise
        # to a single string dtype so parquet / downstream code can handle
        # it consistently.
        work["InvoiceNo"] = work["InvoiceNo"].astype("string")

    if "StockCode" in work.columns:
        # StockCode is mostly numeric but contains alphanumeric codes
        # (``85123A``, ``POST``). Use the nullable string dtype.
        with contextlib.suppress(TypeError, ValueError):
            work["StockCode"] = work["StockCode"].astype("string")

    return work


def _resolve_missing_columns(df: pd.DataFrame, requested: list[str]) -> list[str]:
    """Filter requested missing-value columns to those actually present."""
    return [c for c in requested if c in df.columns]


def _safe_missing_handle(
    df: pd.DataFrame,
    columns: list[str],
    strategy: str,
) -> MissingHandlingResult | None:
    """Run :func:`handle_missing` only if at least one column has missing values."""
    if not columns:
        return None
    present = [c for c in columns if c in df.columns and int(df[c].isna().sum()) > 0]
    if not present:
        # No-op report: still record that the stage was considered.
        return MissingHandlingResult(
            df=df,
            rows_before=int(df.shape[0]),
            rows_after=int(df.shape[0]),
            rows_dropped=0,
            rows_imputed=0,
            strategy=strategy,
            per_column=[
                {
                    "column": c,
                    "strategy": strategy,
                    "missing_count_before": 0,
                    "missing_count_after": 0,
                    "imputed_count": 0,
                }
                for c in columns
                if c in df.columns
            ],
        )
    return _handle_missing(df, present, strategy)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def clean_transactions(
    df: pd.DataFrame,
    config: PipelineConfig | None = None,
) -> CleaningResult:
    """Run the full cleaning pipeline.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw transactions loaded by
        :func:`customer_segmentation.data.loader.load_raw_transactions`.
    config : PipelineConfig, optional
        Pipeline configuration. ``None`` uses the defaults returned by
        :func:`default_pipeline_config`.

    Returns
    -------
    CleaningResult
        Cleaned DataFrame plus a detailed per-stage report.

    Notes
    -----
    Determinism: no randomness is used at any stage. The pipeline is
    reproducible from the raw input and the configuration alone.
    """
    if config is None:
        config = default_pipeline_config()

    rows_in = int(df.shape[0])
    report: dict[str, Any] = {
        "rows_in": rows_in,
        "stages": [],
        "rows_removed_total": 0,
        "rows_retained": rows_in,
    }

    # ------------------------------------------------------------------
    # Stage 0: type coercion (no row removal)
    # ------------------------------------------------------------------
    work = coerce_dtypes(df)
    report["stages"].append(
        {
            "stage": "coerce_dtypes",
            "action": "coerce",
            "rows_in": rows_in,
            "rows_out": int(work.shape[0]),
            "rows_removed": 0,
        }
    )

    # ------------------------------------------------------------------
    # Stage 1: invalid records (drop + flag)
    # ------------------------------------------------------------------
    invalid = apply_invalid_rules(work, config.invalid_rules)
    work = invalid.df
    rows_after_invalid = int(work.shape[0])
    report["stages"].append(
        {
            "stage": "invalid_records",
            "action": "drop+flag",
            "rule_ids": [r["rule_id"] for r in invalid.per_rule],
            "rows_in": rows_in,
            "rows_out": rows_after_invalid,
            "rows_removed": int(invalid.rows_dropped),
            "flagged_cancellations": int(invalid.flagged_cancellations),
            "flagged_returns": int(invalid.flagged_returns),
        }
    )

    # ------------------------------------------------------------------
    # Stage 2: exact-row / subset duplicates
    # ------------------------------------------------------------------
    dup = _drop_duplicates(
        work,
        subset=config.duplicate_subset,
        keep=config.duplicate_keep,
        rule_id="CL-09",
    )
    work = dup.df
    rows_after_dup = int(work.shape[0])
    report["stages"].append(
        {
            "stage": "duplicates",
            "action": "drop",
            "subset": list(dup.subset) if dup.subset is not None else None,
            "keep": dup.keep,
            "rows_in": rows_after_invalid,
            "rows_out": rows_after_dup,
            "rows_removed": int(dup.rows_removed),
        }
    )

    # ------------------------------------------------------------------
    # Stage 3: missing values
    # ------------------------------------------------------------------
    missing_cols = _resolve_missing_columns(work, config.missing_columns)
    if config.missing_strategy != "keep" and not missing_cols:
        # Nothing to do. Surface a clear report entry so the pipeline log
        # is still complete.
        missing: MissingHandlingResult | None = MissingHandlingResult(
            df=work,
            rows_before=int(work.shape[0]),
            rows_after=int(work.shape[0]),
            rows_dropped=0,
            rows_imputed=0,
            strategy=config.missing_strategy,
            per_column=[],
        )
    else:
        missing = _safe_missing_handle(work, missing_cols, config.missing_strategy)

    if missing is not None:
        work = missing.df
    rows_after_missing = int(work.shape[0])
    report["stages"].append(
        {
            "stage": "missing_values",
            "action": config.missing_strategy,
            "columns": missing_cols,
            "rows_in": rows_after_dup,
            "rows_out": rows_after_missing,
            "rows_removed": int(missing.rows_dropped) if missing else 0,
            "rows_imputed": int(missing.rows_imputed) if missing else 0,
        }
    )

    # ------------------------------------------------------------------
    # Stage 4: outliers (off by default)
    # ------------------------------------------------------------------
    outlier_result: OutlierResult | None = None
    rows_after_outliers = rows_after_missing
    if config.outlier_action != "none" and config.outlier_columns:
        outlier_result = _treat_outliers(
            work,
            columns=config.outlier_columns,
            method=config.outlier_method,  # type: ignore[arg-type]
            action=config.outlier_action,  # type: ignore[arg-type]
            iqr_multiplier=config.outlier_iqr_multiplier,
            zscore_threshold=config.outlier_zscore_threshold,
        )
        work = outlier_result.df
        rows_after_outliers = int(work.shape[0])
        report["stages"].append(
            {
                "stage": "outliers",
                "action": config.outlier_action,
                "method": config.outlier_method,
                "columns": config.outlier_columns,
                "rows_in": rows_after_missing,
                "rows_out": rows_after_outliers,
                "rows_removed": int(outlier_result.rows_removed),
            }
        )

    rows_out = int(work.shape[0])
    report["rows_out"] = rows_out
    report["rows_retained"] = rows_out
    report["rows_removed_total"] = rows_in - rows_out

    return CleaningResult(
        df=work,
        report=report,
        invalid=invalid,
        duplicates=dup,
        missing=missing,
        outliers=outlier_result,
    )


def build_rule_inventory(config: PipelineConfig | None = None) -> list[dict[str, Any]]:
    """Return a list of every cleaning rule the pipeline will apply.

    The list mirrors the report generated by :func:`clean_transactions`
    but is suitable for direct emission to a CSV/JSON report file.

    Parameters
    ----------
    config : PipelineConfig, optional
        Pipeline configuration. ``None`` uses the defaults.

    Returns
    -------
    list[dict]
        One record per rule with ``rule_id``, ``stage``, ``action``,
        ``column``, ``condition``, ``default_behaviour`` and
        ``status`` (``WORKING_ASSUMPTION`` or ``PENDING_MENTOR_REVIEW``).
    """
    if config is None:
        config = default_pipeline_config()
    rules = config.invalid_rules
    inventory: list[dict[str, Any]] = [
        {
            "rule_id": "CL-01",
            "stage": "invalid_records",
            "action": "drop",
            "column": "CustomerID",
            "condition": "missing or empty",
            "default_behaviour": rules.drop_missing_customer_id,
            "status": "WORKING_ASSUMPTION",
            "rationale": "CustomerID is the customer-level join key.",
        },
        {
            "rule_id": "CL-03",
            "stage": "invalid_records",
            "action": "drop",
            "column": "Description",
            "condition": "missing or empty",
            "default_behaviour": rules.drop_missing_description,
            "status": "WORKING_ASSUMPTION",
            "rationale": "Small share (~0.27%); RFM does not use Description.",
        },
        {
            "rule_id": "CL-04",
            "stage": "invalid_records",
            "action": "drop",
            "column": "InvoiceDate",
            "condition": "unparseable (NaT after coercion)",
            "default_behaviour": rules.drop_unparseable_invoice_date,
            "status": "WORKING_ASSUMPTION",
            "rationale": "Unparseable dates break Recency computation.",
        },
        {
            "rule_id": "CL-05",
            "stage": "invalid_records",
            "action": "drop",
            "column": "Quantity",
            "condition": "== 0",
            "default_behaviour": rules.drop_zero_quantity,
            "status": "WORKING_ASSUMPTION",
            "rationale": "Zero quantity has no transactional value.",
        },
        {
            "rule_id": "CL-06",
            "stage": "invalid_records",
            "action": "flag",
            "column": "Quantity",
            "condition": "< 0",
            "default_behaviour": rules.flag_returns,
            "status": "PENDING_MENTOR_REVIEW",
            "rationale": (
                "Negative quantity typically means a return/cancellation. "
                "Flagged; final decision belongs to the RFM stage."
            ),
        },
        {
            "rule_id": "CL-07",
            "stage": "invalid_records",
            "action": "drop",
            "column": "UnitPrice",
            "condition": "<= 0",
            "default_behaviour": rules.drop_non_positive_unit_price,
            "status": "WORKING_ASSUMPTION",
            "rationale": "Non-positive prices have no monetary value.",
        },
        {
            "rule_id": "CL-08",
            "stage": "invalid_records",
            "action": "flag",
            "column": "InvoiceNo",
            "condition": f"starts_with({rules.cancellation_prefix!r})",
            "default_behaviour": rules.flag_cancellations,
            "status": "PENDING_MENTOR_REVIEW",
            "rationale": (
                "Cancellation-prefix records are flagged; final decision "
                "belongs to the RFM stage."
            ),
        },
        {
            "rule_id": "CL-09",
            "stage": "duplicates",
            "action": "drop",
            "column": "(exact row or subset)",
            "condition": "duplicate",
            "default_behaviour": True,
            "status": "WORKING_ASSUMPTION",
            "rationale": (
                "Exact-row duplicates are pure data-quality issues. "
                "Subset-key duplicates are reported but not dropped by default."
            ),
        },
        {
            "rule_id": "CL-10",
            "stage": "invalid_records",
            "action": "drop",
            "column": "InvoiceNo",
            "condition": "missing or empty",
            "default_behaviour": rules.drop_missing_invoice_no,
            "status": "WORKING_ASSUMPTION",
            "rationale": "Missing InvoiceNo breaks transaction grouping.",
        },
    ]
    return inventory


def summarise_cleaning_result(result: CleaningResult) -> dict[str, Any]:
    """Build a compact, JSON-serialisable summary of the cleaning result.

    Parameters
    ----------
    result : CleaningResult
        Result of :func:`clean_transactions`.

    Returns
    -------
    dict
        Summary suitable for direct writing to JSON.
    """
    return {
        "rows_in": int(result.report.get("rows_in", 0)),
        "rows_out": int(result.report.get("rows_out", 0)),
        "rows_removed_total": int(result.report.get("rows_removed_total", 0)),
        "flagged_cancellations": int(result.invalid.flagged_cancellations if result.invalid else 0),
        "flagged_returns": int(result.invalid.flagged_returns if result.invalid else 0),
        "stages": list(result.report.get("stages", [])),
    }


def ensure_flag_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure that the cancellation/return flag columns exist.

    Parameters
    ----------
    df : pandas.DataFrame
        Cleaned DataFrame.

    Returns
    -------
    pandas.DataFrame
        Copy of `df` with ``IsCancellation`` and ``IsReturn`` columns
        added if missing (default ``False``). No row is removed.
    """
    work = df.copy(deep=True)
    for col, default in (("IsCancellation", False), ("IsReturn", False)):
        if col not in work.columns:
            work[col] = default
    return work


__all__ = [
    "CleaningResult",
    "PipelineConfig",
    "build_rule_inventory",
    "clean_transactions",
    "coerce_dtypes",
    "default_pipeline_config",
    "ensure_flag_columns",
    "summarise_cleaning_result",
]
