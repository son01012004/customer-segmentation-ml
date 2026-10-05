"""NaN imputation strategy for FE-06.

Handles missing values in candidate features:
- PurchaseIntervalMean: NaN = customer has < 2 invoices
- PurchaseIntervalStd: NaN = customer has < 2 invoices (not enough observations)

Imputation strategy: median (WORKING_ASSUMPTION).

Hard constraints:
- Does NOT fill with 0 (would mislead "no interval" as "zero interval").
- Does NOT drop customers (would lose ~30-49% of data).
- Does NOT create sentinel -1 values.
- Does NOT apply imputation to features not listed in config.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

__all__ = [
    "ImputationResult",
    "impute_median",
    "apply_imputation",
]


@dataclass
class ImputationResult:
    """Result of imputation operation."""

    df: pd.DataFrame
    imputed_features: list[str]
    median_values: dict[str, float]
    nan_counts_before: dict[str, int]
    nan_counts_after: dict[str, int]


def impute_median(
    series: pd.Series,
) -> tuple[pd.Series, float]:
    """Impute NaN values with median.

    Parameters
    ----------
    series : pandas.Series
        Series with possible NaN values.

    Returns
    -------
    tuple[pandas.Series, float]
        (imputed series, median value).
    """
    valid = series.dropna()
    median_val = float("nan") if len(valid) == 0 else float(valid.median())

    imputed = series.copy()
    imputed = imputed.fillna(median_val)
    return imputed, median_val


def apply_imputation(
    df: pd.DataFrame,
    features_to_impute: list[str],
    *,
    method: str = "median",
) -> ImputationResult:
    """Apply imputation to specified features.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature DataFrame.
    features_to_impute : list[str]
        List of feature names to impute.
    method : str
        Imputation method. Currently only "median" is supported.

    Returns
    -------
    ImputationResult
        Imputed DataFrame and metadata.

    Raises
    ------
    ValueError
        If method is not supported.
    """
    if method != "median":
        raise ValueError(f"Unsupported imputation method: {method!r}. Only 'median' is supported.")

    result_df = df.copy()
    median_values: dict[str, float] = {}
    nan_counts_before: dict[str, int] = {}
    nan_counts_after: dict[str, int] = {}

    for feat in features_to_impute:
        if feat not in result_df.columns:
            continue

        series = result_df[feat]
        nan_before = int(series.isna().sum())
        nan_counts_before[feat] = nan_before

        if nan_before == 0:
            # No NaN to impute; still record median for reproducibility
            valid = series.dropna()
            median_val = float(valid.median()) if len(valid) > 0 else float("nan")
            median_values[feat] = median_val
            nan_counts_after[feat] = 0
            continue

        imputed_series, median_val = impute_median(series)
        result_df[feat] = imputed_series
        median_values[feat] = median_val
        nan_counts_after[feat] = int(result_df[feat].isna().sum())

    return ImputationResult(
        df=result_df,
        imputed_features=list(features_to_impute),
        median_values=median_values,
        nan_counts_before=nan_counts_before,
        nan_counts_after=nan_counts_after,
    )
