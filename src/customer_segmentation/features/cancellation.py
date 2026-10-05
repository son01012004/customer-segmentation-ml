"""Cancellation/Return feature computation for FE-05.

Computes:
- CancellationRate: CancellationInvoiceCount / Frequency
- ReturnRate: ReturnInvoiceCount / Frequency

Hard constraints:
- Ratios are computed only where Frequency > 0 (no division by zero).
- NaN/Inf values are not silently filled.
"""

from __future__ import annotations

import pandas as pd

__all__ = [
    "compute_cancellation_rate",
    "compute_return_rate",
    "compute_cancellation_features",
]


def compute_cancellation_rate(
    df_candidates: pd.DataFrame,
    *,
    cancellation_count_column: str = "CancellationInvoiceCount",
    frequency_column: str = "Frequency",
    output_column: str = "CancellationRate",
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute CancellationRate.

    CancellationRate = CancellationInvoiceCount / Frequency

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate DataFrame with CancellationInvoiceCount and Frequency columns.
    cancellation_count_column : str
        CancellationInvoiceCount column name.
    frequency_column : str
        Frequency column name.
    output_column : str
        Output column name.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and CancellationRate.
    """
    result = df_candidates[[customer_key]].copy()
    cancellation_count = pd.to_numeric(df_candidates[cancellation_count_column], errors="coerce")
    frequency = pd.to_numeric(df_candidates[frequency_column], errors="coerce")

    # Avoid division by zero
    freq_safe = frequency.replace(0, pd.NA)
    rate = cancellation_count / freq_safe
    rate = rate.replace([float("inf"), float("-inf")], pd.NA)

    result[output_column] = rate

    return result[[customer_key, output_column]]


def compute_return_rate(
    df_candidates: pd.DataFrame,
    *,
    return_count_column: str = "ReturnInvoiceCount",
    frequency_column: str = "Frequency",
    output_column: str = "ReturnRate",
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute ReturnRate.

    ReturnRate = ReturnInvoiceCount / Frequency

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate DataFrame with ReturnInvoiceCount and Frequency columns.
    return_count_column : str
        ReturnInvoiceCount column name.
    frequency_column : str
        Frequency column name.
    output_column : str
        Output column name.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID and ReturnRate.
    """
    result = df_candidates[[customer_key]].copy()
    return_count = pd.to_numeric(df_candidates[return_count_column], errors="coerce")
    frequency = pd.to_numeric(df_candidates[frequency_column], errors="coerce")

    # Avoid division by zero
    freq_safe = frequency.replace(0, pd.NA)
    rate = return_count / freq_safe
    rate = rate.replace([float("inf"), float("-inf")], pd.NA)

    result[output_column] = rate

    return result[[customer_key, output_column]]


def compute_cancellation_features(
    df_candidates: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute all cancellation/return features.

    Parameters
    ----------
    df_candidates : pandas.DataFrame
        Candidate DataFrame with CancellationInvoiceCount, ReturnInvoiceCount, Frequency.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pandas.DataFrame
        DataFrame with CustomerID, CancellationRate, ReturnRate.
    """
    cancellation_rate = compute_cancellation_rate(
        df_candidates,
        customer_key=customer_key,
    )
    return_rate = compute_return_rate(
        df_candidates,
        customer_key=customer_key,
    )

    result = cancellation_rate.merge(return_rate, on=customer_key, how="left")
    return result
