"""Transaction behavior feature computation for FE-05.

Computes extended behavioral features:
- TenureDays: Transaction tenure (all transactions)
- PurchaseIntervalMean: Mean days between consecutive invoices (NaN if < 2 invoices)
- PurchaseIntervalStd: Std of days between consecutive invoices (ddof=1, NaN if < 2 invoices)
- ActiveDays: Unique calendar days with transactions
- AverageInvoiceValue: Monetary / Frequency (FE-05 candidate)

Hard constraints:
- PurchaseInterval: Invoice-level. NaN = N/A for < 2 invoices. NOT filled with 0.
- std uses ddof=1 (sample std).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

__all__ = [
    "QuantityVariants",
    "compute_signed_quantity_set",
    "compute_purchase_only_quantity_set",
    "write_quantity_variants_comparison",
    "compute_tenure_days",
    "compute_purchase_interval",
    "compute_active_days",
    "compute_average_invoice_value",
    "TransactionBehaviorResult",
]


# ---------------------------------------------------------------------------
# Quantity variants
# ---------------------------------------------------------------------------


@dataclass
class QuantityVariants:
    """Container for quantity variants."""

    signed: pd.DataFrame  # TotalQuantity, AverageQuantity, BasketSize (signed)
    purchase_only: pd.DataFrame  # Purchase-only equivalents
    comparison_df: pd.DataFrame  # Comparison DataFrame


def _compute_quantity_set(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    invoice_column: str = "InvoiceNo",
    quantity_column: str = "Quantity",
    is_cancellation_column: str = "IsCancellation",
    include_cancellations: bool,
    total_quantity_col: str = "TotalQuantity",
    avg_quantity_col: str = "AverageQuantity",
    basket_size_col: str = "BasketSize",
) -> pd.DataFrame:
    """Compute one quantity set (signed or purchase-only).

    Includes:
    - TotalQuantity
    - AverageQuantity (per invoice)
    - BasketSize (alias for AverageQuantity per invoice)
    """
    work = df_transactions.copy()
    work[quantity_column] = pd.to_numeric(work[quantity_column], errors="coerce").fillna(0)

    if not include_cancellations:
        work = work.loc[work[is_cancellation_column] == False]  # noqa: E712

    # Group by CustomerID
    grouped = work.groupby(customer_key, sort=False)

    # TotalQuantity
    total = grouped[quantity_column].sum(min_count=1).reset_index()
    total.columns = [customer_key, total_quantity_col]

    # AverageQuantity: sum(Quantity) / nunique(InvoiceNo) per CustomerID
    sum_qty = grouped[quantity_column].sum(min_count=1)
    nunique_inv = grouped[invoice_column].nunique(dropna=True)
    # Avoid division by zero
    avg = (sum_qty / nunique_inv.replace(0, pd.NA)).reset_index()
    avg.columns = [customer_key, avg_quantity_col]

    # BasketSize = AverageQuantity (same definition)
    basket = avg.rename(columns={avg_quantity_col: basket_size_col})

    # Merge with customer base to ensure all customers included
    result = customer_base[[customer_key]].merge(total, on=customer_key, how="left")
    result = result.merge(avg, on=customer_key, how="left")
    result = result.merge(basket, on=customer_key, how="left")

    return result[[customer_key, total_quantity_col, avg_quantity_col, basket_size_col]]


def compute_signed_quantity_set(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute signed quantity set (ONE working set, default).

    Includes all transactions (cancellations/returns with signed quantities).

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with TotalQuantity, AverageQuantity, BasketSize columns (signed).
    """
    return _compute_quantity_set(
        df_transactions,
        customer_base,
        customer_key=customer_key,
        include_cancellations=True,
        total_quantity_col="TotalQuantity_Signed",
        avg_quantity_col="AverageQuantity_Signed",
        basket_size_col="BasketSize_Signed",
    )


def compute_purchase_only_quantity_set(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute purchase-only quantity set (comparison only).

    Excludes cancellation rows.

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with TotalQuantity, AverageQuantity, BasketSize columns (purchase-only).
    """
    return _compute_quantity_set(
        df_transactions,
        customer_base,
        customer_key=customer_key,
        include_cancellations=False,
        total_quantity_col="TotalQuantity_PurchaseOnly",
        avg_quantity_col="AverageQuantity_PurchaseOnly",
        basket_size_col="BasketSize_PurchaseOnly",
    )


def write_quantity_variants_comparison(
    signed_set: pd.DataFrame,
    purchase_only_set: pd.DataFrame,
    output_path: Path,
    *,
    customer_key: str = "CustomerID",
) -> Path:
    """Write quantity variants comparison CSV.

    Parameters
    ----------
    signed_set : pandas.DataFrame
        Signed quantity set.
    purchase_only_set : pandas.DataFrame
        Purchase-only quantity set.
    output_path : pathlib.Path
        Output CSV path.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    comparison = signed_set.merge(
        purchase_only_set,
        on=customer_key,
        how="left",
        suffixes=("", "_purchase_only"),
    )

    # Add difference columns
    comparison["TotalQuantity_Diff"] = (
        comparison["TotalQuantity_Signed"] - comparison["TotalQuantity_PurchaseOnly"]
    )
    comparison["AverageQuantity_Diff"] = (
        comparison["AverageQuantity_Signed"] - comparison["AverageQuantity_PurchaseOnly"]
    )
    comparison["BasketSize_Diff"] = (
        comparison["BasketSize_Signed"] - comparison["BasketSize_PurchaseOnly"]
    )

    comparison.to_csv(output_path, index=False)
    return output_path


def compute_quantity_variants(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> QuantityVariants:
    """Compute signed and purchase-only quantity sets and comparison.

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    QuantityVariants
        Container with signed set, purchase-only set, and comparison DataFrame.
    """
    signed_set = compute_signed_quantity_set(
        df_transactions, customer_base, customer_key=customer_key
    )
    purchase_only_set = compute_purchase_only_quantity_set(
        df_transactions, customer_base, customer_key=customer_key
    )

    # Build comparison DataFrame
    comparison_df = signed_set.merge(
        purchase_only_set,
        on=customer_key,
        how="left",
        suffixes=("", "_purchase_only"),
    )

    return QuantityVariants(
        signed=signed_set,
        purchase_only=purchase_only_set,
        comparison_df=comparison_df,
    )


# ---------------------------------------------------------------------------
# Transaction Behavior Features
# ---------------------------------------------------------------------------


def compute_tenure_days(
    df_base: pd.DataFrame,
    *,
    first_purchase_column: str = "FirstPurchaseDate",
    last_purchase_column: str = "LastPurchaseDate",
    output_column: str = "TenureDays",
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute TenureDays for each customer.

    TenureDays = (LastPurchaseDate - FirstPurchaseDate).days

    Uses all transactions (includes cancellation/return dates).

    Parameters
    ----------
    df_base : pandas.DataFrame
        Customer-level base dataset.
    first_purchase_column : str
        FirstPurchaseDate column name.
    last_purchase_column : str
        LastPurchaseDate column name.
    output_column : str
        Output column name.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and TenureDays.
    """
    result = df_base[[customer_key, first_purchase_column, last_purchase_column]].copy()

    first_dates = pd.to_datetime(result[first_purchase_column]).dt.date
    last_dates = pd.to_datetime(result[last_purchase_column]).dt.date
    result[output_column] = (last_dates - first_dates).apply(lambda x: x.days)

    return result[[customer_key, output_column]]


def compute_purchase_interval(
    df_transactions: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    invoice_column: str = "InvoiceNo",
    date_column: str = "InvoiceDate",
    output_mean: str = "PurchaseIntervalMean",
    output_std: str = "PurchaseIntervalStd",
) -> pd.DataFrame:
    """Compute PurchaseIntervalMean and PurchaseIntervalStd for each customer.

    Invoice-level computation:
    1. Group by CustomerID + InvoiceNo, take min InvoiceDate per invoice
    2. Sort InvoiceDate per customer
    3. Compute diff of consecutive invoice dates
    4. Mean and std (ddof=1) of these diffs

    Hard constraints:
    - < 2 invoices: NaN (NOT filled with 0)
    - std uses ddof=1 (sample std)

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data.
    customer_key : str
        Customer ID column name.
    invoice_column : str
        Invoice number column name.
    date_column : str
        Invoice date column name.
    output_mean : str
        Output column name for mean.
    output_std : str
        Output column name for std.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID, PurchaseIntervalMean, PurchaseIntervalStd.
        NaN = N/A for customers with < 2 invoices.
    """
    work = df_transactions.copy()
    work[date_column] = pd.to_datetime(work[date_column])

    # Group by CustomerID + InvoiceNo, take min InvoiceDate per invoice
    invoice_dates = work.groupby([customer_key, invoice_column])[date_column].min().reset_index()

    # Sort by customer and date
    invoice_dates = invoice_dates.sort_values([customer_key, date_column]).reset_index(drop=True)

    # Compute diff of consecutive invoice dates per customer
    invoice_dates["__date_diff__"] = invoice_dates.groupby(customer_key)[date_column].diff().dt.days

    # Group by customer to compute mean and std (ddof=1)
    grouped = invoice_dates.groupby(customer_key)

    mean_series = grouped["__date_diff__"].mean()
    # ddof=1 for sample std
    std_series = grouped["__date_diff__"].std(ddof=1)

    result = pd.DataFrame(
        {
            customer_key: mean_series.index,
            output_mean: mean_series.values,
            output_std: std_series.values,
        }
    )

    return result[[customer_key, output_mean, output_std]]


def compute_active_days(
    df_transactions: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    date_column: str = "InvoiceDate",
    output_column: str = "ActiveDays",
) -> pd.DataFrame:
    """Compute ActiveDays for each customer.

    ActiveDays = number of unique calendar days with transactions.

    Uses the date component of InvoiceDate (not raw datetime).

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data.
    customer_key : str
        Customer ID column name.
    date_column : str
        Invoice date column name.
    output_column : str
        Output column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and ActiveDays.
    """
    work = df_transactions.copy()
    work[date_column] = pd.to_datetime(work[date_column])

    # Extract date component (calendar date, not datetime)
    work["__date_only__"] = work[date_column].dt.date

    # Count unique calendar dates per customer
    active = work.groupby(customer_key)["__date_only__"].nunique(dropna=True).reset_index()
    active.columns = [customer_key, output_column]
    active[output_column] = active[output_column].astype("Int64")

    return active


def compute_average_invoice_value(
    df_candidates: pd.DataFrame,
    *,
    monetary_column: str = "Monetary",
    frequency_column: str = "Frequency",
    output_column: str = "AverageInvoiceValue",
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute AverageInvoiceValue = Monetary / Frequency.

    FE-05 candidate mới. FE-04 AverageTransactionValue giữ nguyên (BASE_REFERENCE).

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate DataFrame with Monetary and Frequency columns.
    monetary_column : str
        Monetary column name.
    frequency_column : str
        Frequency column name.
    output_column : str
        Output column name.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and AverageInvoiceValue.
    """
    result = df_candidates[[customer_key]].copy()
    monetary = df_candidates[monetary_column].astype(float)
    frequency = pd.to_numeric(df_candidates[frequency_column], errors="coerce")

    # Avoid division by zero
    freq_safe = frequency.replace(0, pd.NA)
    avg = monetary / freq_safe
    avg = avg.replace([float("inf"), float("-inf")], pd.NA)

    result[output_column] = avg

    return result[[customer_key, output_column]]


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


@dataclass
class TransactionBehaviorResult:
    """Container for transaction behavior results."""

    tenure_days: pd.DataFrame
    purchase_interval: pd.DataFrame
    active_days: pd.DataFrame
    average_invoice_value: pd.DataFrame
    quantity_variants: QuantityVariants


def compute_all_transaction_behavior(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    df_candidates: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> TransactionBehaviorResult:
    """Compute all transaction behavior features.

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    df_candidates : pandas.DataFrame
        Candidate DataFrame with Monetary and Frequency (for AverageInvoiceValue).
    customer_key : str
        Customer ID column name.

    Returns
    -------
    TransactionBehaviorResult
        Container with all transaction behavior features.
    """
    tenure = compute_tenure_days(customer_base, customer_key=customer_key)
    interval = compute_purchase_interval(df_transactions, customer_key=customer_key)
    active = compute_active_days(df_transactions, customer_key=customer_key)
    avg_inv = compute_average_invoice_value(df_candidates, customer_key=customer_key)
    quantity = compute_quantity_variants(df_transactions, customer_base, customer_key=customer_key)

    return TransactionBehaviorResult(
        tenure_days=tenure,
        purchase_interval=interval,
        active_days=active,
        average_invoice_value=avg_inv,
        quantity_variants=quantity,
    )
