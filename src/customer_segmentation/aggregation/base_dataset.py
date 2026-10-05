"""FE-04 core aggregation: customer-level base dataset construction.

Scope
-----
Tổng hợp dữ liệu transaction-level (FE-02 output) thành customer-level
dataset. Mỗi CustomerID xuất hiện đúng một lần.

Các aggregate features được định nghĩa trong ``configs/aggregation.yaml`` và
tuân theo AggregationSpec dataclasses từ ``config_loader``.

Output: ``data/processed/customer_base.parquet``

Hard constraints (AGENTS.md / Plan V3):
- Input FE-02 parquet is read-only.
- LineRevenue is derived in-memory; never persisted back to input.
- SHA-256 của input được ghi nhận trong fe04_run.json, không embed vào Parquet metadata.
- No clustering, no feature selection, no scaling, no transformation.
- PurchaseFrequency là working proxy, không phải RFM Frequency cuối cùng.
- TotalMonetary là signed monetary baseline, không phải RFM Monetary cuối cùng.
- Cancellation/return rows được giữ nguyên; treatment deferred to FE-05.

Reuse
-----
- ``compute_line_revenue()`` reuse từ
  ``customer_segmentation.outlier_analysis.customer_aggregates``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from customer_segmentation.aggregation.config_loader import AggregationConfig


LINE_REVENUE_COLUMN: str = "LineRevenue"


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


@dataclass
class CustomerBaseResult:
    """Kết quả của customer-level aggregation.

    Attributes
    ----------
    df : pandas.DataFrame
        Customer-level dataset. Mỗi dòng = một CustomerID.
    config : AggregationConfig
        Config được sử dụng.
    input_row_count : int
        Số dòng của input transaction-level dataset.
    output_row_count : int
        Số dòng của output customer-level dataset.
    features_created : list[str]
        Danh sách tên các feature columns được tạo (không bao gồm CustomerID).
    """

    df: pd.DataFrame
    config: AggregationConfig
    input_row_count: int
    output_row_count: int
    features_created: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# LineRevenue
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
    Never mutates the input. Derived in-memory; not persisted.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame (not mutated).
    quantity_column : str
    unit_price_column : str
    out_column : str

    Returns
    -------
    pandas.DataFrame
        Copy of `df` with the additional `out_column`.
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


# ---------------------------------------------------------------------------
# Aggregation dispatch
# ---------------------------------------------------------------------------


def _apply_aggregation(
    grouped: pd.core.groupby.generic.DataFrameGroupBy,
    *,
    fn_name: str,
    source: str,
) -> pd.Series:
    """Apply a named aggregation function to a grouped series."""
    if fn_name == "sum":
        return grouped[source].sum(min_count=1)
    if fn_name == "nunique":
        return grouped[source].nunique(dropna=True)
    if fn_name == "min":
        return grouped[source].min()
    if fn_name == "max":
        return grouped[source].max()
    if fn_name == "count":
        return grouped[source].count()
    if fn_name == "nunique_date":
        # nunique over the date component of a datetime column.
        return grouped[source].apply(lambda s: int(pd.Series(s.values).dt.date.dropna().nunique()))
    if fn_name == "avg_by_invoice":
        # Special: TotalMonetary / DistinctInvoiceCount.
        # We receive LineRevenue grouped by CustomerID and InvoiceNo separately.
        raise NotImplementedError(
            "avg_by_invoice must be handled at the top-level "
            "aggregate_customer_base() function, not here."
        )
    if fn_name == "conditional_nunique_cancellation":
        # nunique InvoiceNo where IsCancellation == True.
        if "IsCancellation" not in grouped.obj.columns:
            raise KeyError("IsCancellation column required for conditional_nunique_cancellation.")
        filtered = grouped.obj.loc[grouped.obj["IsCancellation"] == True]  # noqa: E712
        # Use the same index type as other aggregations (the groupby index).
        group_keys = pd.Index(grouped.groups.keys())
        if filtered.empty:
            return pd.Series(0, index=group_keys, dtype="Int64")
        sub_grouped = filtered.groupby(grouped.keys, dropna=False)
        result = sub_grouped[source].nunique(dropna=True).fillna(0)
        # Reindex to the full group index so alignment is consistent.
        result = result.reindex(group_keys, fill_value=0).astype("Int64")
        return result
    if fn_name == "conditional_nunique_return":
        # nunique InvoiceNo where IsReturn == True.
        if "IsReturn" not in grouped.obj.columns:
            raise KeyError("IsReturn column required for conditional_nunique_return.")
        filtered = grouped.obj.loc[grouped.obj["IsReturn"] == True]  # noqa: E712
        group_keys = pd.Index(grouped.groups.keys())
        if filtered.empty:
            return pd.Series(0, index=group_keys, dtype="Int64")
        sub_grouped = filtered.groupby(grouped.keys, dropna=False)
        result = sub_grouped[source].nunique(dropna=True).fillna(0)
        result = result.reindex(group_keys, fill_value=0).astype("Int64")
        return result
    raise ValueError(f"Unknown aggregation fn {fn_name!r}.")


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------


def aggregate_customer_base(
    df: pd.DataFrame,
    config: AggregationConfig,
) -> CustomerBaseResult:
    """Aggregate transaction-level data to customer-level base dataset.

    Parameters
    ----------
    df : pandas.DataFrame
        Transaction-level dataset (FE-02 output).
        Must contain all required columns referenced by ``config``.
    config : AggregationConfig
        Aggregation configuration from ``configs/aggregation.yaml``.

    Returns
    -------
    CustomerBaseResult
        Container with the customer-level DataFrame and metadata.

    Notes
    -----
    - No row is dropped or filtered in this function.
    - Cancellation/return rows are included with signed values.
    - ``LineRevenue`` is derived in-memory only.
    - ``AverageTransactionValue`` is computed as ``TotalMonetary / DistinctInvoiceCount``.
    - ``PurchaseFrequency`` is set equal to ``DistinctInvoiceCount`` (working proxy).

    Hard constraints enforced here:
    - CustomerID null check before grouping.
    - ``DistinctInvoiceCount`` must be >= 1 (production assertion).
    """
    input_row_count = int(df.shape[0])
    customer_key = config.customer_key

    if customer_key not in df.columns:
        raise KeyError(
            f"Customer key column {customer_key!r} not in DataFrame. "
            f"Available columns: {list(df.columns)}."
        )

    # Check for null CustomerIDs — should not exist after FE-02 but we validate.
    null_mask = df[customer_key].isna()
    if null_mask.any():
        raise ValueError(
            f"Found {int(null_mask.sum())} rows with null {customer_key!r} in input. "
            "FE-02 should have dropped these. Check FE-02 cleaning output."
        )

    # Derive LineRevenue in-memory.
    work = df.copy(deep=True)
    lr_col = config.line_revenue_columns.output
    if lr_col not in work.columns:
        work = compute_line_revenue(
            work,
            quantity_column=config.line_revenue_columns.quantity,
            unit_price_column=config.line_revenue_columns.unit_price,
            out_column=lr_col,
        )

    # Group by CustomerID.
    grouped = work.groupby(customer_key, dropna=False, sort=True)

    # Determine which spec uses avg_by_invoice (AverageTransactionValue).
    avg_spec_names: set[str] = set()
    for spec in config.aggregations:
        if spec.fn == "avg_by_invoice":
            avg_spec_names.add(spec.name)

    # Separate specs: avg_by_invoice vs. the rest.
    standard_specs = [s for s in config.aggregations if s.fn != "avg_by_invoice"]
    avg_specs = [s for s in config.aggregations if s.fn == "avg_by_invoice"]

    # Standard aggregations.
    records: dict[str, pd.Series] = {}
    for spec in standard_specs:
        records[spec.name] = _apply_aggregation(
            grouped,
            fn_name=spec.fn,
            source=spec.source,
        )

    # Special handling for avg_by_invoice:
    # AverageTransactionValue = sum(LineRevenue) / nunique(InvoiceNo).
    # We need TotalMonetary and DistinctInvoiceCount.
    if avg_specs:
        total_money_name = "TotalMonetary"
        distinct_inv_name = "DistinctInvoiceCount"
        if total_money_name not in records:
            records[total_money_name] = _apply_aggregation(grouped, fn_name="sum", source=lr_col)
        if distinct_inv_name not in records:
            records[distinct_inv_name] = _apply_aggregation(
                grouped, fn_name="nunique", source="InvoiceNo"
            )

        for spec in avg_specs:
            total_money = records[total_money_name]
            distinct_inv = records[distinct_inv_name]

            # Guard against zero denominator.
            if (distinct_inv == 0).any():
                zero_denom_count = int((distinct_inv == 0).sum())
                raise ValueError(
                    f"AverageTransactionValue: {zero_denom_count} customers have "
                    f"DistinctInvoiceCount == 0. This should not happen for valid customers."
                )

            avg_series = total_money / distinct_inv
            avg_series = avg_series.replace([float("inf"), float("-inf")], float("nan"))
            records[spec.name] = avg_series

    # Also set PurchaseFrequency = DistinctInvoiceCount (working proxy).
    purchase_freq_names = {
        s.name for s in config.aggregations if s.fn == "nunique" and s.source == "InvoiceNo"
    }
    for pf_name in purchase_freq_names:
        if pf_name in records and "DistinctInvoiceCount" in records:
            records[pf_name] = records["DistinctInvoiceCount"]

    # Build DataFrame.
    diag = pd.DataFrame(records)
    diag.index.name = customer_key
    diag = diag.reset_index()

    # Sort deterministically: by TotalMonetary descending, then by CustomerID ascending.
    sort_cols = [customer_key]
    if "TotalMonetary" in diag.columns:
        sort_cols = ["TotalMonetary", customer_key]
    diag = diag.sort_values(sort_cols, ascending=[False, True]).reset_index(drop=True)

    output_row_count = int(diag.shape[0])
    features_created = [c for c in diag.columns if c != customer_key]

    return CustomerBaseResult(
        df=diag,
        config=config,
        input_row_count=input_row_count,
        output_row_count=output_row_count,
        features_created=features_created,
    )


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------


def build_base_schema(config: AggregationConfig) -> dict[str, str]:
    """Return the expected output schema as a {column: dtype} mapping.

    Parameters
    ----------
    config : AggregationConfig
        Aggregation configuration.

    Returns
    -------
    dict[str, str]
        Column name → expected dtype name.
    """
    schema: dict[str, str] = {config.customer_key: "Int64"}
    for spec in config.aggregations:
        if spec.fn in (
            "sum",
            "avg_by_invoice",
            "conditional_nunique_cancellation",
            "conditional_nunique_return",
        ):
            schema[spec.name] = "float64"
        elif spec.fn in ("nunique", "count"):
            schema[spec.name] = "int64"
        elif spec.fn in ("min", "max") and "Date" in spec.name:
            schema[spec.name] = "datetime64[ns]"
        else:
            schema[spec.name] = "object"
    return schema
