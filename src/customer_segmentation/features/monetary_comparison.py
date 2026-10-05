"""Monetary definition comparison for FE-05.

Computes 4 distinct definition variants of Monetary for comparison:
1. MonetarySigned: sum of all (signed) LineRevenue (default)
2. MonetaryAbsolute: sum of |LineRevenue|
3. MonetaryPurchaseOnly: sum where IsCancellation=False
4. MonetaryCancellationOnly: sum where IsCancellation=True

Detects overlap between variants and writes comparison report.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from customer_segmentation.features.rfm import (
    MonetaryVariants,
    compute_monetary_variants,
    materialize_monetary,
)

__all__ = [
    "compute_all_monetary_variants",
    "detect_overlap",
    "build_monetary_comparison_csv",
    "materialize_one_monetary_candidate",
]


def compute_all_monetary_variants(
    df_transactions: pd.DataFrame,
    customer_base: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
    line_revenue_column: str = "LineRevenue",
    is_cancellation_column: str = "IsCancellation",
) -> MonetaryVariants:
    """Compute all 4 monetary definition variants.

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

    Returns
    -------
    MonetaryVariants
        Container with all monetary variants.
    """
    return compute_monetary_variants(
        df_transactions,
        customer_base,
        customer_key=customer_key,
        line_revenue_column=line_revenue_column,
        is_cancellation_column=is_cancellation_column,
    )


def detect_overlap(variants: MonetaryVariants, customer_key: str = "CustomerID") -> pd.DataFrame:
    """Detect overlap between monetary variants.

    Returns a summary DataFrame showing how many customers have non-zero
    values in each variant and the overlap matrix.

    Parameters
    ----------
    variants : MonetaryVariants
        Monetary variants from compute_all_monetary_variants.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns: Variant, CustomerCount, Percentage.
    """
    df = variants.comparison_df

    # Build boolean mask for each variant
    overlap_rows = []
    total_customers = len(df)

    variant_cols = [
        ("MonetarySigned", "signed"),
        ("MonetaryAbsolute", "absolute"),
        ("MonetaryPurchaseOnly", "purchase_only"),
        ("MonetaryCancellationOnly", "cancellation_only"),
    ]

    for col_name, variant_label in variant_cols:
        non_zero = (df[col_name].notna()) & (df[col_name] != 0)
        count = int(non_zero.sum())
        percentage = (count / total_customers * 100) if total_customers > 0 else 0
        overlap_rows.append(
            {
                "Variant": col_name,
                "VariantLabel": variant_label,
                "CustomerCount": count,
                "Percentage": percentage,
            }
        )

    return pd.DataFrame(overlap_rows)


def build_monetary_comparison_csv(
    variants: MonetaryVariants,
    output_path: Path,
    *,
    customer_key: str = "CustomerID",
) -> Path:
    """Build and write monetary definition comparison CSV.

    The comparison CSV includes:
    - CustomerID
    - All 4 monetary variants
    - Overlap summary

    Parameters
    ----------
    variants : MonetaryVariants
        Monetary variants.
    output_path : pathlib.Path
        Output CSV path.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pathlib.Path
        Path to the written CSV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build the comparison DataFrame
    df = variants.comparison_df.copy()

    # Add overlap detection columns
    df["HasSigned"] = (df["MonetarySigned"].notna()) & (df["MonetarySigned"] != 0)
    df["HasAbsolute"] = (df["MonetaryAbsolute"].notna()) & (df["MonetaryAbsolute"] != 0)
    df["HasPurchaseOnly"] = (df["MonetaryPurchaseOnly"].notna()) & (df["MonetaryPurchaseOnly"] != 0)
    df["HasCancellationOnly"] = (df["MonetaryCancellationOnly"].notna()) & (
        df["MonetaryCancellationOnly"] != 0
    )

    df.to_csv(output_path, index=False)
    return output_path


def materialize_one_monetary_candidate(
    variants: MonetaryVariants,
    customer_base: pd.DataFrame,
    *,
    variant: str = "signed",
    output_column: str = "Monetary",
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Materialize ONE Monetary candidate.

    Default: MonetarySigned.

    Parameters
    ----------
    variants : MonetaryVariants
        Monetary variants.
    customer_base : pandas.DataFrame
        Customer-level base dataset.
    variant : str
        Which variant to materialize.
    output_column : str
        Output column name.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and Monetary column.
    """
    return materialize_monetary(
        variants,
        customer_base,
        customer_key=customer_key,
        variant=variant,
        output_column=output_column,
    )
