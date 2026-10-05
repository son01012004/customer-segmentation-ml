"""RFM (Recency, Frequency, Monetary) feature computation.

This module computes RFM features for the FE-05 pipeline.

Key principles (Plan V5):
- ReferenceDate = max(InvoiceDate) + 1 day (deterministic strategy)
- ONE Frequency materialized (default: FREQ-01 = by invoice)
- ONE Monetary materialized (default: MonetarySigned)
- All variants computed for comparison, reports generated separately
- SHA-256 tracked for reproducibility
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

__all__ = [
    "compute_reference_date",
    "compute_recency",
    "compute_frequency_variants",
    "compute_monetary_variants",
    "build_rfm_report",
    "FrequencyVariants",
    "MonetaryVariants",
]


# ---------------------------------------------------------------------------
# Reference Date
# ---------------------------------------------------------------------------


def compute_reference_date(
    df_transactions: pd.DataFrame,
    *,
    date_column: str = "InvoiceDate",
) -> datetime:
    """Compute the reference date for Recency calculation.

    ReferenceDate = max(InvoiceDate) + 1 day (deterministic strategy).

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data with InvoiceDate column.
    date_column : str
        Name of the date column.

    Returns
    -------
    datetime
        Reference date = max(date_column) + 1 day.

    Notes
    -----
    - Deterministic: always derived from data.
    - Status: WORKING_ASSUMPTION (MENTOR_REVIEW_PENDING).
    - Includes all transactions (including cancellations/returns).
    """
    if date_column not in df_transactions.columns:
        raise KeyError(
            f"Column {date_column!r} not in DataFrame. "
            f"Available columns: {list(df_transactions.columns)}."
        )

    max_date = df_transactions[date_column].max()
    if pd.isna(max_date):
        raise ValueError(f"Column {date_column!r} has no valid dates.")

    reference_date = max_date + timedelta(days=1)
    return reference_date


# ---------------------------------------------------------------------------
# Recency
# ---------------------------------------------------------------------------


def compute_recency(
    df_base: pd.DataFrame,
    reference_date: datetime,
    *,
    last_purchase_column: str = "LastPurchaseDate",
    output_column: str = "Recency",
) -> pd.DataFrame:
    """Compute Recency for each customer.

    Recency = (ReferenceDate - LastPurchaseDate).days

    Parameters
    ----------
    df_base : pandas.DataFrame
        Customer-level base dataset from FE-04.
    reference_date : datetime
        Reference date for Recency calculation.
    last_purchase_column : str
        Name of the LastPurchaseDate column in df_base.
    output_column : str
        Name of the output Recency column.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and Recency column.

    Notes
    -----
    - Includes all transactions (cancellation/return included).
    - Status: PENDING_REVIEW for purchase-only Recency.
    - If LastPurchaseDate is a datetime, .days gives the difference.
    """
    if last_purchase_column not in df_base.columns:
        raise KeyError(
            f"Column {last_purchase_column!r} not in DataFrame. "
            f"Available columns: {list(df_base.columns)}."
        )

    result = df_base[["CustomerID", last_purchase_column]].copy()

    # Compute days since reference
    # Convert to datetime.date for clean subtraction
    ref_date_only = reference_date.date() if hasattr(reference_date, "date") else reference_date

    last_dates = pd.to_datetime(result[last_purchase_column]).dt.date
    result[output_column] = (ref_date_only - last_dates).apply(lambda x: x.days)

    return result[["CustomerID", output_column]]


# ---------------------------------------------------------------------------
# Frequency
# ---------------------------------------------------------------------------


@dataclass
class FrequencyVariants:
    """Container for frequency variant results."""

    by_invoice: pd.DataFrame  # FREQ-01: nunique InvoiceNo
    by_transaction_line: pd.DataFrame  # FREQ-02: count of transaction lines
    comparison_df: pd.DataFrame  # Comparison DataFrame


def compute_frequency_variants(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    invoice_column: str = "InvoiceNo",
    freq01_output: str = "Frequency_ByInvoice",
    freq02_output: str = "Frequency_ByTransactionLine",
) -> FrequencyVariants:
    """Compute Frequency variants for comparison.

    FREQ-01: Frequency_ByInvoice = nunique(InvoiceNo) per CustomerID
    FREQ-02: Frequency_ByTransactionLine = count(InvoiceNo) per CustomerID

    Both variants are computed for comparison. ONE is materialized (default: FREQ-01).

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.
    invoice_column : str
        Invoice number column name.
    freq01_output : str
        Output column name for FREQ-01.
    freq02_output : str
        Output column name for FREQ-02.

    Returns
    -------
    FrequencyVariants
        Container with both frequency variants and comparison DataFrame.
    """
    if customer_key not in df_transactions.columns:
        raise KeyError(f"Column {customer_key!r} not in df_transactions.")
    if invoice_column not in df_transactions.columns:
        raise KeyError(f"Column {invoice_column!r} not in df_transactions.")

    # FREQ-01: nunique InvoiceNo per CustomerID
    freq01 = (
        df_transactions.groupby(customer_key)[invoice_column].nunique(dropna=True).reset_index()
    )
    freq01.columns = [customer_key, freq01_output]
    freq01[freq01_output] = freq01[freq01_output].astype("Int64")

    # FREQ-02: count of transaction lines per CustomerID
    freq02 = df_transactions.groupby(customer_key)[invoice_column].count().reset_index()
    freq02.columns = [customer_key, freq02_output]
    freq02[freq02_output] = freq02[freq02_output].astype("Int64")

    # Merge with customer base to ensure all customers are included
    freq_df = customer_base[[customer_key]].merge(freq01, on=customer_key, how="left")
    freq_df = freq_df.merge(freq02, on=customer_key, how="left")

    # Comparison DataFrame
    comparison_df = freq_df[[customer_key, freq01_output, freq02_output]].copy()
    # Add difference column
    comparison_df["Difference"] = comparison_df[freq02_output] - comparison_df[freq01_output]

    return FrequencyVariants(
        by_invoice=freq01,
        by_transaction_line=freq02,
        comparison_df=comparison_df,
    )


def materialize_frequency(
    variants: FrequencyVariants,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    mode: str = "by_invoice",  # "by_invoice" | "by_transaction_line"
    output_column: str = "Frequency",
) -> pd.DataFrame:
    """Materialize ONE Frequency variant.

    Parameters
    ----------
    variants : FrequencyVariants
        Frequency variants from compute_frequency_variants.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.
    mode : str
        Which variant to materialize: "by_invoice" (FREQ-01) or "by_transaction_line" (FREQ-02).
    output_column : str
        Output column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and Frequency column.
    """
    if mode == "by_invoice":
        source_col = "Frequency_ByInvoice"
        source_df = variants.by_invoice
    elif mode == "by_transaction_line":
        source_col = "Frequency_ByTransactionLine"
        source_df = variants.by_transaction_line
    else:
        raise ValueError(
            f"Unknown frequency mode: {mode!r}. Use 'by_invoice' or 'by_transaction_line'."
        )

    result = customer_base[[customer_key]].merge(
        source_df[[customer_key, source_col]],
        on=customer_key,
        how="left",
    )
    result = result.rename(columns={source_col: output_column})

    return result[[customer_key, output_column]]


# ---------------------------------------------------------------------------
# Monetary
# ---------------------------------------------------------------------------


@dataclass
class MonetaryVariants:
    """Container for monetary variant results."""

    signed: pd.DataFrame  # MonetarySigned: sum of signed LineRevenue
    absolute: pd.DataFrame  # MonetaryAbsolute: sum of |LineRevenue|
    purchase_only: pd.DataFrame  # MonetaryPurchaseOnly: sum where IsCancellation=False
    cancellation_only: pd.DataFrame  # MonetaryCancellationOnly: sum where IsCancellation=True
    comparison_df: pd.DataFrame  # Comparison DataFrame with 4 variants
    overlap_df: pd.DataFrame  # Overlap detection DataFrame


def compute_monetary_variants(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    line_revenue_column: str = "LineRevenue",
    is_cancellation_column: str = "IsCancellation",
    signed_output: str = "MonetarySigned",
    absolute_output: str = "MonetaryAbsolute",
    purchase_only_output: str = "MonetaryPurchaseOnly",
    cancellation_only_output: str = "MonetaryCancellationOnly",
) -> MonetaryVariants:
    """Compute Monetary variants for comparison.

    4 distinct definition variants:
    1. MonetarySigned: sum of all (signed) LineRevenue
    2. MonetaryAbsolute: sum of |LineRevenue|
    3. MonetaryPurchaseOnly: sum where IsCancellation=False
    4. MonetaryCancellationOnly: sum where IsCancellation=True

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Transaction-level data with LineRevenue column.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.
    line_revenue_column : str
        LineRevenue column name.
    is_cancellation_column : str
        IsCancellation column name.
    signed_output : str
        Output column name for signed variant.
    absolute_output : str
        Output column name for absolute variant.
    purchase_only_output : str
        Output column name for purchase-only variant.
    cancellation_only_output : str
        Output column name for cancellation-only variant.

    Returns
    -------
    MonetaryVariants
        Container with all monetary variants and comparison DataFrame.
    """
    # Derive LineRevenue if not present
    if line_revenue_column not in df_transactions.columns:
        if "Quantity" in df_transactions.columns and "UnitPrice" in df_transactions.columns:
            work = df_transactions.copy()
            work[line_revenue_column] = work["Quantity"] * work["UnitPrice"]
        else:
            raise KeyError(
                f"Column {line_revenue_column!r} not in DataFrame, "
                f"and Quantity/UnitPrice not available."
            )
    else:
        work = df_transactions.copy()

    # Convert to numeric
    work[line_revenue_column] = pd.to_numeric(work[line_revenue_column], errors="coerce").fillna(0)

    # 1. MonetarySigned: sum of all (signed) LineRevenue
    signed = work.groupby(customer_key)[line_revenue_column].sum(min_count=1).reset_index()
    signed.columns = [customer_key, signed_output]

    # 2. MonetaryAbsolute: sum of |LineRevenue|
    abs_col = "__abs_revenue__"
    work[abs_col] = work[line_revenue_column].abs()
    absolute = work.groupby(customer_key)[abs_col].sum(min_count=1).reset_index()
    absolute.columns = [customer_key, absolute_output]
    work = work.drop(columns=[abs_col])

    # 3. MonetaryPurchaseOnly: sum where IsCancellation=False
    purchase_mask = work[is_cancellation_column] == False  # noqa: E712
    purchase_only = (
        work.loc[purchase_mask]
        .groupby(customer_key)[line_revenue_column]
        .sum(min_count=1)
        .reset_index()
    )
    purchase_only.columns = [customer_key, purchase_only_output]

    # 4. MonetaryCancellationOnly: sum where IsCancellation=True
    cancellation_mask = work[is_cancellation_column] == True  # noqa: E712
    cancellation_only = (
        work.loc[cancellation_mask]
        .groupby(customer_key)[line_revenue_column]
        .sum(min_count=1)
        .reset_index()
    )
    cancellation_only.columns = [customer_key, cancellation_only_output]

    # Merge all variants
    monetary_df = customer_base[[customer_key]].merge(signed, on=customer_key, how="left")
    monetary_df = monetary_df.merge(absolute, on=customer_key, how="left")
    monetary_df = monetary_df.merge(purchase_only, on=customer_key, how="left")
    monetary_df = monetary_df.merge(cancellation_only, on=customer_key, how="left")

    # Comparison DataFrame
    comparison_df = monetary_df[
        [
            customer_key,
            signed_output,
            absolute_output,
            purchase_only_output,
            cancellation_only_output,
        ]
    ].copy()

    # Overlap detection
    overlap_df = _detect_monetary_overlap(
        monetary_df,
        customer_key,
        signed_output,
        absolute_output,
        purchase_only_output,
        cancellation_only_output,
    )

    return MonetaryVariants(
        signed=signed,
        absolute=absolute,
        purchase_only=purchase_only,
        cancellation_only=cancellation_only,
        comparison_df=comparison_df,
        overlap_df=overlap_df,
    )


def _detect_monetary_overlap(
    df: pd.DataFrame,
    customer_key: str,
    signed_col: str,
    absolute_col: str,
    purchase_only_col: str,
    cancellation_only_col: str,
) -> pd.DataFrame:
    """Detect overlap between monetary variants.

    Returns DataFrame showing customer overlap between variants.
    """
    # Check for customers that appear in multiple variants
    has_signed = df[signed_col].notna() & (df[signed_col] != 0)
    has_absolute = df[absolute_col].notna() & (df[absolute_col] != 0)
    has_purchase = df[purchase_only_col].notna() & (df[purchase_only_col] != 0)
    has_cancellation = df[cancellation_only_col].notna() & (df[cancellation_only_col] != 0)

    overlap_summary = pd.DataFrame(
        {
            "Variant": [signed_col, absolute_col, purchase_only_col, cancellation_only_col],
            "CustomerCount": [
                has_signed.sum(),
                has_absolute.sum(),
                has_purchase.sum(),
                has_cancellation.sum(),
            ],
        }
    )

    return overlap_summary


def materialize_monetary(
    variants: MonetaryVariants,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    variant: str = "signed",  # "signed" | "absolute" | "purchase_only" | "cancellation_only"
    output_column: str = "Monetary",
) -> pd.DataFrame:
    """Materialize ONE Monetary variant.

    Parameters
    ----------
    variants : MonetaryVariants
        Monetary variants from compute_monetary_variants.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.
    variant : str
        Which variant to materialize: "signed", "absolute", "purchase_only", "cancellation_only".
    output_column : str
        Output column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and Monetary column.
    """
    variant_map = {
        "signed": ("MonetarySigned", variants.signed),
        "absolute": ("MonetaryAbsolute", variants.absolute),
        "purchase_only": ("MonetaryPurchaseOnly", variants.purchase_only),
        "cancellation_only": ("MonetaryCancellationOnly", variants.cancellation_only),
    }

    if variant not in variant_map:
        raise ValueError(
            f"Unknown monetary variant: {variant!r}. " f"Use: {list(variant_map.keys())}."
        )

    source_col, source_df = variant_map[variant]

    result = customer_base[[customer_key]].merge(
        source_df[[customer_key, source_col]],
        on=customer_key,
        how="left",
    )
    result = result.rename(columns={source_col: output_column})

    return result[[customer_key, output_column]]


# ---------------------------------------------------------------------------
# RFM Report
# ---------------------------------------------------------------------------


def build_rfm_report(
    reference_date: datetime,
    recency_df: pd.DataFrame,
    frequency_variants: FrequencyVariants,
    monetary_variants: MonetaryVariants,
    materialized_frequency: pd.DataFrame,
    materialized_monetary: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> dict:
    """Build RFM summary report data.

    Parameters
    ----------
    reference_date : datetime
        Computed reference date.
    recency_df : pandas.DataFrame
        Recency DataFrame.
    frequency_variants : FrequencyVariants
        Frequency variants.
    monetary_variants : MonetaryVariants
        Monetary variants.
    materialized_frequency : pandas.DataFrame
        Materialized Frequency DataFrame.
    materialized_monetary : pandas.DataFrame
        Materialized Monetary DataFrame.

    Returns
    -------
    dict
        Report data dictionary.
    """
    recency_col = "Recency"
    freq_col = "Frequency"
    mon_col = "Monetary"

    recency_stats = recency_df[recency_col].describe()
    freq_stats = materialized_frequency[freq_col].describe()
    mon_stats = materialized_monetary[mon_col].describe()

    return {
        "reference_date": reference_date.isoformat(),
        "reference_date_strategy": "snapshot_max",
        "status": "WORKING_ASSUMPTION",
        "review": "MENTOR_REVIEW_PENDING",
        "materialized_frequency": "Frequency_ByInvoice",
        "materialized_monetary": "MonetarySigned",
        "recency": {
            "count": int(recency_stats["count"]),
            "mean": float(recency_stats["mean"]),
            "std": float(recency_stats["std"]),
            "min": float(recency_stats["min"]),
            "max": float(recency_stats["max"]),
        },
        "frequency": {
            "count": int(freq_stats["count"]),
            "mean": float(freq_stats["mean"]),
            "std": float(freq_stats["std"]),
            "min": float(freq_stats["min"]),
            "max": float(freq_stats["max"]),
        },
        "monetary": {
            "count": int(mon_stats["count"]),
            "mean": float(mon_stats["mean"]),
            "std": float(mon_stats["std"]),
            "min": float(mon_stats["min"]),
            "max": float(mon_stats["max"]),
        },
    }
