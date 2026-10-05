"""Invalid-record filtering and flagging for FE-02.

This module implements the invalid-record rules registered as ``CL-04``
through ``CL-08`` and ``CL-10`` in :mod:`customer_segmentation.preprocessing.cleaning`.

Two kinds of operations are supported:

- **Drop**: remove rows that fail the configured rule.
- **Flag**: keep the row and add a boolean indicator column so the
  downstream RFM stage can decide whether to include or exclude the
  flagged records.

The key design choice for FE-02 is **conservative semantics**:

- Quantity = 0 has no transactional meaning (no goods, no money) → drop.
- Quantity < 0 is treated as a *return / cancellation line* → flag.
- UnitPrice ≤ 0 has no monetary value → drop.
- InvoiceNo with a leading ``C`` is treated as a *cancellation record*
  in the original UCI convention → flag, do not drop.
- Unparseable / missing dates → drop.
- Missing or empty InvoiceNo → drop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

__all__ = [
    "InvalidRecordRules",
    "InvalidRecordResult",
    "apply_invalid_rules",
    "cancellation_prefix_mask",
    "negative_quantity_mask",
    "non_positive_unit_price_mask",
    "unparseable_date_mask",
    "missing_identifier_mask",
    "flag_cancellations",
    "flag_returns",
]


# ---------------------------------------------------------------------------
# Rule structure
# ---------------------------------------------------------------------------


@dataclass
class InvalidRecordRules:
    """Configuration for invalid-record filtering and flagging.

    Attributes
    ----------
    drop_missing_customer_id : bool
        Drop rows whose ``CustomerID`` is missing. Required for
        customer-level analysis. Default ``True``.
    drop_missing_invoice_no : bool
        Drop rows whose ``InvoiceNo`` is missing or empty. Default
        ``True``.
    drop_missing_description : bool
        Drop rows whose ``Description`` is missing. Default ``True``.
    drop_unparseable_invoice_date : bool
        Drop rows whose ``InvoiceDate`` cannot be parsed to a
        ``datetime``. Default ``True``.
    drop_zero_quantity : bool
        Drop rows with ``Quantity == 0`` (no transactional value).
        Default ``True``.
    drop_non_positive_unit_price : bool
        Drop rows with ``UnitPrice <= 0``. Default ``True``.
    flag_cancellations : bool
        Add an ``IsCancellation`` boolean column for InvoiceNo starting
        with the cancellation prefix. Default ``True`` (flag, not drop).
    flag_returns : bool
        Add an ``IsReturn`` boolean column for negative-quantity rows.
        Default ``True`` (flag, not drop).
    cancellation_prefix : str, default "C"
        Prefix that conventionally marks a cancellation in UCI Online
        Retail.
    """

    drop_missing_customer_id: bool = True
    drop_missing_invoice_no: bool = True
    drop_missing_description: bool = True
    drop_unparseable_invoice_date: bool = True
    drop_zero_quantity: bool = True
    drop_non_positive_unit_price: bool = True
    flag_cancellations: bool = True
    flag_returns: bool = True
    cancellation_prefix: str = "C"


@dataclass
class InvalidRecordResult:
    """Outcome of an invalid-record pass.

    Attributes
    ----------
    df : pandas.DataFrame
        DataFrame after the rules have been applied.
    rows_before : int
        Rows in the input.
    rows_after : int
        Rows in the output.
    rows_dropped : int
        Total rows removed by the drop rules.
    flagged_cancellations : int
        Number of rows flagged as cancellations.
    flagged_returns : int
        Number of rows flagged as returns.
    per_rule : list[dict]
        One record per applied rule with ``rule_id``, ``column``,
        ``condition``, ``action``, ``affected_rows``.
    """

    df: pd.DataFrame
    rows_before: int
    rows_after: int
    rows_dropped: int
    flagged_cancellations: int
    flagged_returns: int
    per_rule: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation (excluding the df)."""
        return {
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "rows_dropped": self.rows_dropped,
            "flagged_cancellations": self.flagged_cancellations,
            "flagged_returns": self.flagged_returns,
            "per_rule": list(self.per_rule),
        }


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def cancellation_prefix_mask(
    df: pd.DataFrame,
    column: str = "InvoiceNo",
    prefix: str = "C",
) -> pd.Series:
    """Return a boolean mask marking rows whose InvoiceNo starts with `prefix`.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    column : str, default "InvoiceNo"
        Column to inspect.
    prefix : str, default "C"
        Prefix that signals a cancellation.

    Returns
    -------
    pandas.Series
        Boolean Series aligned with `df.index`.
    """
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not in DataFrame.")
    s = df[column].astype("string")
    return s.str.startswith(prefix).fillna(False)


def negative_quantity_mask(df: pd.DataFrame, column: str = "Quantity") -> pd.Series:
    """Return a boolean mask marking rows with negative `column` values."""
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not in DataFrame.")
    s = pd.to_numeric(df[column], errors="coerce")
    return (s < 0).fillna(False)


def non_positive_unit_price_mask(df: pd.DataFrame, column: str = "UnitPrice") -> pd.Series:
    """Return a boolean mask marking rows with non-positive `column` values."""
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not in DataFrame.")
    s = pd.to_numeric(df[column], errors="coerce")
    return (s <= 0).fillna(False)


def unparseable_date_mask(df: pd.DataFrame, column: str = "InvoiceDate") -> pd.Series:
    """Return a boolean mask marking rows whose date cannot be parsed.

    A row is considered *unparseable* when coercion to ``datetime``
    yields ``NaT`` **and** the original value was not already ``NaN``
    (we do not want to double-count missing dates as unparseable).
    """
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not in DataFrame.")
    parsed = pd.to_datetime(df[column], errors="coerce")
    is_nat = parsed.isna()
    originally_missing = df[column].isna()
    return (is_nat & ~originally_missing).fillna(False)


def missing_identifier_mask(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a boolean mask marking rows with missing/empty identifier."""
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not in DataFrame.")
    s = df[column]
    is_missing = s.isna()
    # Treat empty strings as missing for object columns.
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
        is_missing = is_missing | s.astype("string").str.strip().fillna("").eq("")
    return is_missing.fillna(False)


# ---------------------------------------------------------------------------
# Flagging helpers
# ---------------------------------------------------------------------------


def flag_cancellations(
    df: pd.DataFrame,
    column: str = "InvoiceNo",
    prefix: str = "C",
    flag_column: str = "IsCancellation",
) -> tuple[pd.DataFrame, int]:
    """Add an ``IsCancellation`` boolean column to `df`.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame (not mutated).
    column : str, default "InvoiceNo"
        Column to inspect.
    prefix : str, default "C"
        Prefix that signals a cancellation.
    flag_column : str, default "IsCancellation"
        Name of the new column.

    Returns
    -------
    (df, n_flagged)
        New DataFrame (with the flag column) and the number of flagged rows.
    """
    work = df.copy(deep=True)
    mask = cancellation_prefix_mask(work, column=column, prefix=prefix)
    work[flag_column] = mask.astype(bool)
    return work, int(mask.sum())


def flag_returns(
    df: pd.DataFrame,
    column: str = "Quantity",
    flag_column: str = "IsReturn",
) -> tuple[pd.DataFrame, int]:
    """Add an ``IsReturn`` boolean column for negative-quantity rows."""
    work = df.copy(deep=True)
    mask = negative_quantity_mask(work, column=column)
    work[flag_column] = mask.astype(bool)
    return work, int(mask.sum())


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def apply_invalid_rules(
    df: pd.DataFrame,
    rules: InvalidRecordRules | None = None,
) -> InvalidRecordResult:
    """Apply drop + flag rules to a raw transactions DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    rules : InvalidRecordRules, optional
        Rule configuration. ``None`` uses the defaults.

    Returns
    -------
    InvalidRecordResult
        Cleaned DataFrame plus a structured report.
    """
    if rules is None:
        rules = InvalidRecordRules()

    rows_before = int(df.shape[0])
    work = df.copy(deep=True)
    per_rule: list[dict] = []

    # ---- 1. Flag cancellations (does not drop). ----
    flagged_canc = 0
    if rules.flag_cancellations and "InvoiceNo" in work.columns:
        work, n_flag = flag_cancellations(
            work,
            column="InvoiceNo",
            prefix=rules.cancellation_prefix,
            flag_column="IsCancellation",
        )
        flagged_canc = n_flag
        per_rule.append(
            {
                "rule_id": "CL-08",
                "column": "InvoiceNo",
                "condition": f"starts_with({rules.cancellation_prefix!r})",
                "action": "flag",
                "affected_rows": n_flag,
                "rationale": (
                    "Cancellation-prefix records are flagged but not removed. "
                    "Final decision (keep vs. drop) belongs to the RFM stage."
                ),
            }
        )

    # ---- 2. Flag returns (does not drop). ----
    flagged_ret = 0
    if rules.flag_returns and "Quantity" in work.columns:
        work, n_flag = flag_returns(work, column="Quantity", flag_column="IsReturn")
        flagged_ret = n_flag
        per_rule.append(
            {
                "rule_id": "CL-06",
                "column": "Quantity",
                "condition": "< 0",
                "action": "flag",
                "affected_rows": n_flag,
                "rationale": (
                    "Negative-quantity rows are typically returns/cancellations. "
                    "Flagged but kept; downstream stage decides treatment."
                ),
            }
        )

    # ---- 3. Drop rules (order matters: drop non-identifier issues first). ----

    drop_masks: list[tuple[str, str, str, str, pd.Series]] = []

    if rules.drop_unparseable_invoice_date and "InvoiceDate" in work.columns:
        m = unparseable_date_mask(work, "InvoiceDate")
        drop_masks.append(
            (
                "CL-04",
                "InvoiceDate",
                "unparseable (NaT after coercion)",
                "drop",
                m,
            )
        )

    if rules.drop_missing_invoice_no and "InvoiceNo" in work.columns:
        m = missing_identifier_mask(work, "InvoiceNo")
        drop_masks.append(
            (
                "CL-10",
                "InvoiceNo",
                "missing or empty",
                "drop",
                m,
            )
        )

    if rules.drop_missing_customer_id and "CustomerID" in work.columns:
        m = missing_identifier_mask(work, "CustomerID")
        drop_masks.append(
            (
                "CL-01",
                "CustomerID",
                "missing or empty",
                "drop",
                m,
            )
        )

    if rules.drop_missing_description and "Description" in work.columns:
        m = missing_identifier_mask(work, "Description")
        drop_masks.append(
            (
                "CL-03",
                "Description",
                "missing or empty",
                "drop",
                m,
            )
        )

    if rules.drop_zero_quantity and "Quantity" in work.columns:
        s = pd.to_numeric(work["Quantity"], errors="coerce")
        m = (s == 0).fillna(False)
        drop_masks.append(
            (
                "CL-05",
                "Quantity",
                "== 0",
                "drop",
                m,
            )
        )

    if rules.drop_non_positive_unit_price and "UnitPrice" in work.columns:
        m = non_positive_unit_price_mask(work, "UnitPrice")
        drop_masks.append(
            (
                "CL-07",
                "UnitPrice",
                "<= 0",
                "drop",
                m,
            )
        )

    # Combine drop masks (any rule applies → drop)
    if drop_masks:
        combined = pd.Series(False, index=work.index)
        for rule_id, col, cond, action, m in drop_masks:
            n_affected = int(m.sum())
            per_rule.append(
                {
                    "rule_id": rule_id,
                    "column": col,
                    "condition": cond,
                    "action": action,
                    "affected_rows": n_affected,
                    "rationale": _RATIONALE_BY_RULE.get(rule_id, ""),
                }
            )
            combined = combined | m
        rows_dropped = int(combined.sum())
        work = work.loc[~combined].reset_index(drop=True)
    else:
        rows_dropped = 0

    rows_after = int(work.shape[0])
    return InvalidRecordResult(
        df=work,
        rows_before=rows_before,
        rows_after=rows_after,
        rows_dropped=rows_dropped,
        flagged_cancellations=flagged_canc,
        flagged_returns=flagged_ret,
        per_rule=per_rule,
    )


_RATIONALE_BY_RULE: dict[str, str] = {
    "CL-01": (
        "CustomerID is the customer-level join key. Missing values cannot be "
        "imputed without breaking the identifier semantics; rows are dropped."
    ),
    "CL-03": (
        "Missing Description accounts for ~0.27% of rows; downstream RFM does "
        "not use this column, so dropping has negligible impact."
    ),
    "CL-04": (
        "Unparseable InvoiceDate rows would break Recency computation; they "
        "are dropped. FE-01 reports zero such rows in the primary dataset."
    ),
    "CL-05": (
        "Quantity == 0 carries no transactional value; dropping avoids "
        "contaminating basket-size statistics."
    ),
    "CL-07": (
        "UnitPrice <= 0 has no monetary value and would distort Monetary "
        "computations; rows are dropped."
    ),
    "CL-10": ("Missing or empty InvoiceNo breaks transaction grouping; rows are " "dropped."),
}
