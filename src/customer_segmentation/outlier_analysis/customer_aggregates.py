"""FE-03 outlier analysis: customer-level diagnostic aggregations.

This module computes the FE-03 **diagnostic-only** customer-level
aggregations:

- ``total_spend``        — sum of ``LineRevenue`` per customer.
- ``total_quantity``     — sum of ``Quantity`` per customer.
- ``distinct_invoices``  — number of unique invoices per customer.
- ``distinct_products``  — number of unique ``StockCode`` per customer.
- ``active_days``        — number of distinct calendar dates.

Important scope boundary
------------------------
These aggregations are **diagnostic** and are explicitly **not** the
project's official RFM / extended-behavioural features. The RFM
reference date, the RFM Frequency definition (unique vs. counting
returns), and the RFM Monetary definition (sign convention for returns)
are all owned by FE-04 with mentor approval (DD-01, DD-02, DD-06). The
FE-03 outputs:

- Are computed on the FE-02 cleaned dataset, **after** the FE-02
  flags (``IsCancellation``, ``IsReturn``) have been added. Cancellation
  and return rows are included in the diagnostic so we can compare
  "all_rows" against "clean_purchase" in the report.
- Are written to ``reports/fe03/customer_level_diagnostic.csv``.
- Are NOT written back to the cleaned parquet and NOT consumed by any
  downstream pipeline stage until a mentor approves the methodology.

Hard rules (from AGENTS.md):
- No mutation of the input DataFrame.
- ``LineRevenue`` is computed on-the-fly as ``Quantity * UnitPrice``
  (no silent sign flipping).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from customer_segmentation.config.outlier_loader import (
    CustomerAggregationConfig,
    CustomerDiagnosticConfig,
)

__all__ = [
    "CustomerDiagnosticResult",
    "LINE_REVENUE_COLUMN",
    "LineRevenueColumn",
    "compute_line_revenue",
    "customer_diagnostic",
    "filter_dataframe_for_mode",
    "summarise_diagnostic",
]


# Name of the derived column. We never persist this back to the FE-02
# parquet; it lives only inside the FE-03 orchestrator's memory.
LINE_REVENUE_COLUMN: str = "LineRevenue"
LineRevenueColumn = LINE_REVENUE_COLUMN


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------


class CustomerDiagnosticResult:
    """Container for the customer-level diagnostic output.

    Attributes
    ----------
    frame : pandas.DataFrame
        One row per customer. Index = ``customer_key``; columns = the
        aggregated diagnostics plus the customer-key column.
    config : CustomerDiagnosticConfig
        The configuration used to produce this result.
    is_diagnostic : bool
        Always ``True``. Sentinel that downstream consumers can check
        before confusing this with FE-04 RFM features.
    """

    def __init__(
        self,
        frame: pd.DataFrame,
        config: CustomerDiagnosticConfig,
    ) -> None:
        self.frame = frame
        self.config = config
        self.is_diagnostic = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "config": self.config,
            "is_diagnostic": self.is_diagnostic,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_line_revenue(
    df: pd.DataFrame,
    *,
    quantity_column: str = "Quantity",
    unit_price_column: str = "UnitPrice",
    out_column: str = LINE_REVENUE_COLUMN,
) -> pd.DataFrame:
    """Add a derived ``LineRevenue`` column to a copy of `df`.

    ``LineRevenue = Quantity * UnitPrice`` with **no sign flipping**.
    Returns a *new* DataFrame; the input is not mutated.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    quantity_column : str, default "Quantity"
    unit_price_column : str, default "UnitPrice"
    out_column : str, default ``"LineRevenue"``

    Returns
    -------
    pandas.DataFrame
        Copy of `df` with the additional ``out_column``.
    """
    if quantity_column not in df.columns:
        raise KeyError(f"Column {quantity_column!r} not in DataFrame.")
    if unit_price_column not in df.columns:
        raise KeyError(f"Column {unit_price_column!r} not in DataFrame.")
    work = df.copy(deep=True)
    q = pd.to_numeric(work[quantity_column], errors="coerce")
    p = pd.to_numeric(work[unit_price_column], errors="coerce")
    work[out_column] = q * p
    return work


def filter_dataframe_for_mode(
    df: pd.DataFrame,
    mode_name: str,
) -> pd.DataFrame:
    """Apply one of the FE-03 filter modes to `df`.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame (not mutated).
    mode_name : str
        One of ``all_rows``, ``clean_purchase``, ``non_cancellation``,
        ``non_return``.

    Returns
    -------
    pandas.DataFrame
        Filtered copy of `df`.

    Raises
    ------
    ValueError
        If `mode_name` is not recognised or the required flag columns
        are missing.
    """
    work = df.copy(deep=True)
    if mode_name == "all_rows":
        return work
    if mode_name == "clean_purchase":
        if "IsCancellation" not in work.columns or "IsReturn" not in work.columns:
            raise ValueError("clean_purchase mode requires IsCancellation and IsReturn columns.")
        return work.loc[~work["IsCancellation"] & ~work["IsReturn"]].reset_index(drop=True)
    if mode_name == "non_cancellation":
        if "IsCancellation" not in work.columns:
            raise ValueError("non_cancellation mode requires IsCancellation column.")
        return work.loc[~work["IsCancellation"]].reset_index(drop=True)
    if mode_name == "non_return":
        if "IsReturn" not in work.columns:
            raise ValueError("non_return mode requires IsReturn column.")
        return work.loc[~work["IsReturn"]].reset_index(drop=True)
    raise ValueError(
        f"Unknown filter mode {mode_name!r}; "
        "valid: 'all_rows', 'clean_purchase', 'non_cancellation', 'non_return'."
    )


# ---------------------------------------------------------------------------
# Customer-level aggregations
# ---------------------------------------------------------------------------


def _apply_aggregation(
    grouped: pd.core.groupby.generic.DataFrameGroupBy,
    name: str,
    spec: CustomerAggregationConfig,
) -> pd.Series:
    """Dispatch one aggregation spec to the appropriate pandas call."""
    src = spec.source
    fn = spec.fn
    if fn == "sum":
        return grouped[src].sum(min_count=1)
    if fn == "mean":
        return grouped[src].mean()
    if fn == "min":
        return grouped[src].min()
    if fn == "max":
        return grouped[src].max()
    if fn == "nunique":
        return grouped[src].nunique(dropna=True)
    if fn == "nunique_date":
        # nunique over the date component of a datetime column.
        return grouped[src].apply(lambda s: int(pd.Series(s).dt.date.dropna().nunique()))
    if fn == "count":
        return grouped[src].count()
    raise ValueError(f"Unknown aggregation fn {fn!r} for diagnostic column {name!r}.")


def customer_diagnostic(
    df: pd.DataFrame,
    config: CustomerDiagnosticConfig,
    *,
    filter_mode: str = "all_rows",
) -> CustomerDiagnosticResult:
    """Compute the customer-level diagnostic table.

    Parameters
    ----------
    df : pandas.DataFrame
        Source DataFrame. Must contain the customer key column and the
        source columns referenced by `config.aggregations`. For the
        default aggregations, the cleaned dataset schema (FE-02 output)
        is sufficient: ``CustomerID``, ``LineRevenue`` (derived),
        ``Quantity``, ``InvoiceNo``, ``StockCode``, ``InvoiceDate``.
    config : CustomerDiagnosticConfig
        Diagnostic configuration.
    filter_mode : str, default ``"all_rows"``
        Filter mode applied before aggregation.

    Returns
    -------
    CustomerDiagnosticResult
        Wrapper around the per-customer DataFrame.
    """
    if not config.enabled:
        return CustomerDiagnosticResult(pd.DataFrame(columns=[config.customer_key]), config)

    work = filter_dataframe_for_mode(df, mode_name=filter_mode)

    # Derive LineRevenue if it is referenced but not present.
    needs_line_revenue = any(
        spec.source == LINE_REVENUE_COLUMN for spec in config.aggregations.values()
    )
    if needs_line_revenue and LINE_REVENUE_COLUMN not in work.columns:
        work = compute_line_revenue(work)

    if config.customer_key not in work.columns:
        raise KeyError(f"Customer key {config.customer_key!r} not in DataFrame columns.")

    # Drop rows with a missing customer key — we cannot aggregate them.
    work = work.dropna(subset=[config.customer_key])

    grouped = work.groupby(config.customer_key, dropna=False, sort=True)

    records: dict[str, pd.Series] = {}
    for name, spec in config.aggregations.items():
        records[name] = _apply_aggregation(grouped, name, spec)

    diag = pd.DataFrame(records)
    diag.index.name = config.customer_key
    diag = diag.reset_index()

    # Sort by total_spend desc if present, else by customer_key asc for
    # deterministic output.
    if "total_spend" in diag.columns:
        diag = diag.sort_values(
            ["total_spend", config.customer_key],
            ascending=[False, True],
        ).reset_index(drop=True)
    else:
        diag = diag.sort_values(config.customer_key).reset_index(drop=True)

    return CustomerDiagnosticResult(diag, config)


# ---------------------------------------------------------------------------
# Convenience: summarise the diagnostic output
# ---------------------------------------------------------------------------


def summarise_diagnostic(diag: CustomerDiagnosticResult) -> pd.DataFrame:
    """Build a per-diagnostic-column summary table.

    The returned table mirrors :func:`distribution_profile` (count,
    min/max, mean, median, std, P95, P99, P99.5, IQR) for each numeric
    diagnostic column.
    """
    from customer_segmentation.outlier_analysis.distribution import (
        EXTENDED_PERCENTILES,
        distribution_profile,
    )

    records = []
    for col in diag.frame.columns:
        if col == diag.config.customer_key:
            continue
        if not pd.api.types.is_numeric_dtype(diag.frame[col]):
            continue
        prof = distribution_profile(
            diag.frame[col],
            column=col,
            percentiles=EXTENDED_PERCENTILES,
            total_rows=int(diag.frame.shape[0]),
        )
        records.append(prof.to_dict())
    return pd.DataFrame.from_records(records)
