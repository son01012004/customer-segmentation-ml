"""Diversity feature computation for FE-05.

Computes:
- ProductsPerInvoice: Ratio proxy (DistinctProducts / DistinctInvoiceCount)

Hard constraints:
- CategoryCount is NOT materialized (unsupported - dataset has no official taxonomy).
- ProductsPerInvoice must be documented as ratio proxy (not standard diversity metric).
"""

from __future__ import annotations

import pandas as pd

__all__ = ["compute_products_per_invoice", "compute_diversity_features"]


def compute_products_per_invoice(
    df_base: pd.DataFrame,
    *,
    distinct_products_column: str = "DistinctProducts",
    distinct_invoice_column: str = "DistinctInvoiceCount",
    output_column: str = "ProductsPerInvoice",
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute ProductsPerInvoice as a ratio proxy.

    ProductsPerInvoice = DistinctProducts / DistinctInvoiceCount

    IMPORTANT:
    - This is a RATIO PROXY, NOT a standard diversity metric.
    - It represents the average number of unique products per invoice.
    - Interpretation: higher value = customer buys more diverse products per transaction.

    Parameters
    ----------
    df_base : pandas.DataFrame
        Customer-level base dataset.
    distinct_products_column : str
        DistinctProducts column name.
    distinct_invoice_column : str
        DistinctInvoiceCount column name.
    output_column : str
        Output column name.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and ProductsPerInvoice.
    """
    result = df_base[[customer_key]].copy()
    distinct_products = pd.to_numeric(df_base[distinct_products_column], errors="coerce")
    distinct_invoices = pd.to_numeric(df_base[distinct_invoice_column], errors="coerce")

    # Avoid division by zero
    freq_safe = distinct_invoices.replace(0, pd.NA)
    ratio = distinct_products / freq_safe
    ratio = ratio.replace([float("inf"), float("-inf")], pd.NA)

    result[output_column] = ratio

    return result[[customer_key, output_column]]


def compute_diversity_features(
    df_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute all diversity features.

    Only ProductsPerInvoice is materialized. CategoryCount is NOT materialized.

    Parameters
    ----------
    df_base : pandas.DataFrame
        Customer-level base dataset.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and ProductsPerInvoice.
    """
    products_per_invoice = compute_products_per_invoice(
        df_base,
        customer_key=customer_key,
    )
    return products_per_invoice
