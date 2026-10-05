"""Build candidate dataset Tầng 2 for FE-05.

Builds the final candidate feature dataset by combining:
- RFM features (ONE Monetary, ONE Frequency)
- Extended behavioral features (tenure, interval, active days, etc.)
- Quantity working set (signed, ONE set)
- Diversity feature (ProductsPerInvoice)
- Cancellation/Return features (rate-based)

Hard constraints:
- Only numeric CANDIDATE features (no date features in output).
- NO CategoryCount.
- FE-04 AverageTransactionValue is NOT in candidate dataset
  (kept in BASE_REFERENCE, FE-05 uses AverageInvoiceValue).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

__all__ = ["CandidateDatasetResult", "build_candidate_features", "validate_candidate_dataset"]


@dataclass
class CandidateDatasetResult:
    """Result of building candidate dataset."""

    df: pd.DataFrame
    candidate_features: list[str]
    customer_count: int


def build_candidate_features(
    df_base: pd.DataFrame,
    recency_df: pd.DataFrame,
    frequency_df: pd.DataFrame,
    monetary_df: pd.DataFrame,
    quantity_set: pd.DataFrame,
    tenure_df: pd.DataFrame,
    purchase_interval_df: pd.DataFrame,
    active_days_df: pd.DataFrame,
    average_invoice_value_df: pd.DataFrame,
    products_per_invoice_df: pd.DataFrame,
    cancellation_features_df: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> CandidateDatasetResult:
    """Build candidate dataset Tầng 2.

    Combines all CANDIDATE features into a single DataFrame.

    Parameters
    ----------
    df_base : pandas.DataFrame
        Customer base dataset (FE-04 output).
    recency_df : pandas.DataFrame
        Recency features.
    frequency_df : pandas.DataFrame
        Materialized Frequency (ONE variant).
    monetary_df : pandas.DataFrame
        Materialized Monetary (ONE variant).
    quantity_set : pandas.DataFrame
        Materialized Quantity working set (signed).
    tenure_df : pandas.DataFrame
        TenureDays.
    purchase_interval_df : pandas.DataFrame
        PurchaseInterval Mean and Std.
    active_days_df : pandas.DataFrame
        ActiveDays.
    average_invoice_value_df : pandas.DataFrame
        AverageInvoiceValue.
    products_per_invoice_df : pandas.DataFrame
        ProductsPerInvoice.
    cancellation_features_df : pandas.DataFrame
        CancellationRate, ReturnRate.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    CandidateDatasetResult
        Container with candidate DataFrame and metadata.
    """
    # Start with base
    result = df_base[[customer_key]].copy()

    # Merge each feature set
    merge_targets = [
        recency_df,
        frequency_df,
        monetary_df,
        quantity_set,
        tenure_df,
        purchase_interval_df,
        active_days_df,
        average_invoice_value_df,
        products_per_invoice_df,
        cancellation_features_df,
    ]

    for target in merge_targets:
        result = result.merge(target, on=customer_key, how="left")

    # Identify candidate features (exclude customer_key)
    candidate_features = [c for c in result.columns if c != customer_key]

    return CandidateDatasetResult(
        df=result,
        candidate_features=candidate_features,
        customer_count=len(result),
    )


def validate_candidate_dataset(
    result: CandidateDatasetResult,
    *,
    customer_key: str = "CustomerID",
) -> dict:
    """Validate candidate dataset structure.

    Parameters
    ----------
    result : CandidateDatasetResult
        Candidate dataset result.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    dict
        Validation results dictionary.
    """
    df = result.df
    checks = {}

    # Check 1: CustomerID is unique
    checks["unique_customers"] = {
        "status": "PASS" if df[customer_key].duplicated().sum() == 0 else "FAIL",
        "n_total": len(df),
        "n_unique": df[customer_key].nunique(),
    }

    # Check 2: No CategoryCount
    checks["no_category_count"] = {
        "status": "PASS" if "CategoryCount" not in df.columns else "FAIL",
    }

    # Check 3: ONE Monetary column
    monetary_cols = [
        c
        for c in df.columns
        if c.startswith("Monetary")
        and not c.startswith("MonetarySigned")
        and not c.startswith("MonetaryAbsolute")
        and not c.startswith("MonetaryPurchase")
        and not c.startswith("MonetaryCancellation")
    ]
    checks["one_monetary"] = {
        "status": "PASS" if len(monetary_cols) == 1 else "FAIL",
        "monetary_columns": monetary_cols,
    }

    # Check 4: ONE Frequency column
    freq_cols = [
        c
        for c in df.columns
        if c.startswith("Frequency")
        and c != "Frequency_ByInvoice"
        and c != "Frequency_ByTransactionLine"
    ]
    checks["one_frequency"] = {
        "status": "PASS" if len(freq_cols) == 1 else "FAIL",
        "frequency_columns": freq_cols,
    }

    # Check 5: ONE Quantity working set
    qty_cols = [
        c
        for c in df.columns
        if (
            c.startswith("TotalQuantity")
            or c.startswith("AverageQuantity")
            or c.startswith("BasketSize")
        )
        and not c.endswith("_Signed")
        and not c.endswith("_PurchaseOnly")
    ]
    checks["one_quantity_set"] = {
        "status": "PASS" if len(qty_cols) >= 3 else "FAIL",
        "quantity_columns": qty_cols,
    }

    # Check 6: All customers have values (no NaN in critical fields)
    critical_cols = ["CustomerID", "Recency", "Frequency", "Monetary"]
    nan_counts = {c: int(df[c].isna().sum()) for c in critical_cols if c in df.columns}
    checks["critical_no_nan"] = {
        "status": "PASS" if all(v == 0 for v in nan_counts.values()) else "WARNING",
        "nan_counts": nan_counts,
    }

    return checks
