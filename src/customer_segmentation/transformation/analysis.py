"""Analysis utilities for FE-06.

Computes:
- Distribution statistics (pre/post transformation/scaling)
- Correlation matrices (Pearson + Spearman)
- Outlier detection (IQR-based)
- Redundancy detection (high correlation pairs)

Mirrors pattern from customer_segmentation.features.analysis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "compute_distribution_stats",
    "compute_correlation_matrices",
    "detect_outliers",
    "detect_redundancy",
    "DistributionResult",
    "CorrelationResult",
    "OutlierResult",
    "RedundancyResult",
]


@dataclass
class DistributionResult:
    """Distribution statistics container."""

    stats_df: pd.DataFrame


@dataclass
class CorrelationResult:
    """Correlation matrices container."""

    pearson: pd.DataFrame
    spearman: pd.DataFrame


@dataclass
class OutlierResult:
    """Outlier detection result."""

    outlier_counts: pd.DataFrame


@dataclass
class RedundancyResult:
    """Redundancy detection result."""

    pairs_df: pd.DataFrame


def compute_distribution_stats(
    df: pd.DataFrame,
    feature_columns: list[str],
) -> DistributionResult:
    """Compute distribution statistics for numeric features.

    Computes: count, missing, inf, min, max, mean, median, std, variance,
    Q1, Q3, IQR, skewness, kurtosis, P1, P5, P25, P50, P75, P95, P99.

    Parameters
    ----------
    df : pandas.DataFrame
        Feature DataFrame.
    feature_columns : list[str]
        Numeric feature columns.

    Returns
    -------
    DistributionResult
        Container with stats DataFrame.
    """
    rows = []
    for col in feature_columns:
        series = df[col]
        valid = series.dropna()
        inf_count = int(np.isinf(series).sum())
        missing_count = int(series.isna().sum())

        if len(valid) == 0:
            rows.append(
                {
                    "Feature": col,
                    "Count": 0,
                    "Missing": missing_count,
                    "Inf": inf_count,
                    "Min": np.nan,
                    "Max": np.nan,
                    "Mean": np.nan,
                    "Median": np.nan,
                    "Std": np.nan,
                    "Variance": np.nan,
                    "Q1": np.nan,
                    "Q3": np.nan,
                    "IQR": np.nan,
                    "Skewness": np.nan,
                    "Kurtosis": np.nan,
                    "P1": np.nan,
                    "P5": np.nan,
                    "P25": np.nan,
                    "P50": np.nan,
                    "P75": np.nan,
                    "P95": np.nan,
                    "P99": np.nan,
                }
            )
            continue

        valid_float = valid.astype(float)
        mean = float(valid_float.mean())
        median = float(valid_float.median())
        std = float(valid_float.std(ddof=1)) if len(valid_float) > 1 else 0.0
        variance = std**2
        q1 = float(valid_float.quantile(0.25))
        q3 = float(valid_float.quantile(0.75))
        iqr = q3 - q1
        skewness = float(valid_float.skew()) if len(valid_float) > 2 else np.nan
        kurtosis = float(valid_float.kurtosis()) if len(valid_float) > 3 else np.nan

        rows.append(
            {
                "Feature": col,
                "Count": int(len(valid)),
                "Missing": missing_count,
                "Inf": inf_count,
                "Min": float(valid_float.min()),
                "Max": float(valid_float.max()),
                "Mean": mean,
                "Median": median,
                "Std": std,
                "Variance": variance,
                "Q1": q1,
                "Q3": q3,
                "IQR": iqr,
                "Skewness": skewness,
                "Kurtosis": kurtosis,
                "P1": float(valid_float.quantile(0.01)),
                "P5": float(valid_float.quantile(0.05)),
                "P25": float(valid_float.quantile(0.25)),
                "P50": float(valid_float.quantile(0.50)),
                "P75": float(valid_float.quantile(0.75)),
                "P95": float(valid_float.quantile(0.95)),
                "P99": float(valid_float.quantile(0.99)),
            }
        )

    return DistributionResult(stats_df=pd.DataFrame(rows))


def compute_correlation_matrices(
    df: pd.DataFrame,
    feature_columns: list[str],
) -> CorrelationResult:
    """Compute Pearson and Spearman correlation matrices.

    Parameters
    ----------
    df : pandas.DataFrame
        Feature DataFrame.
    feature_columns : list[str]
        Numeric feature columns.

    Returns
    -------
    CorrelationResult
        Container with Pearson and Spearman matrices.
    """
    numeric_cols = [
        c for c in feature_columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
    ]
    if len(numeric_cols) == 0:
        return CorrelationResult(pearson=pd.DataFrame(), spearman=pd.DataFrame())

    sub_df = df[numeric_cols]
    pearson = sub_df.corr(method="pearson", numeric_only=True)
    spearman = sub_df.corr(method="spearman", numeric_only=True)
    return CorrelationResult(pearson=pearson, spearman=spearman)


def detect_outliers(
    df: pd.DataFrame,
    feature_columns: list[str],
    *,
    iqr_multiplier: float = 1.5,
) -> OutlierResult:
    """Detect outliers using IQR method.

    Parameters
    ----------
    df : pandas.DataFrame
        Feature DataFrame.
    feature_columns : list[str]
        Numeric feature columns.
    iqr_multiplier : float
        IQR multiplier (default 1.5).

    Returns
    -------
    OutlierResult
        Container with outlier counts DataFrame.
    """
    rows = []
    for col in feature_columns:
        series = df[col]
        valid = series.dropna()
        if len(valid) < 4:
            rows.append(
                {
                    "Feature": col,
                    "Count": len(series),
                    "Q1": np.nan,
                    "Q3": np.nan,
                    "IQR": np.nan,
                    "LowerBound": np.nan,
                    "UpperBound": np.nan,
                    "OutlierCount": 0,
                    "OutlierRatio": 0.0,
                }
            )
            continue

        q1 = float(valid.quantile(0.25))
        q3 = float(valid.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - iqr_multiplier * iqr
        upper = q3 + iqr_multiplier * iqr
        is_outlier = (series < lower) | (series > upper)
        outlier_count = int(is_outlier.sum())

        rows.append(
            {
                "Feature": col,
                "Count": len(series),
                "Q1": q1,
                "Q3": q3,
                "IQR": iqr,
                "LowerBound": lower,
                "UpperBound": upper,
                "OutlierCount": outlier_count,
                "OutlierRatio": outlier_count / max(len(series), 1),
            }
        )

    return OutlierResult(outlier_counts=pd.DataFrame(rows))


def detect_redundancy(
    correlation_matrix: pd.DataFrame,
    *,
    threshold: float = 0.95,
) -> RedundancyResult:
    """Detect high-correlation feature pairs (redundancy candidates).

    Parameters
    ----------
    correlation_matrix : pandas.DataFrame
        Correlation matrix.
    threshold : float
        Correlation threshold (default 0.95).

    Returns
    -------
    RedundancyResult
        Container with pairs DataFrame.
    """
    if correlation_matrix.empty:
        return RedundancyResult(
            pairs_df=pd.DataFrame(columns=["Feature1", "Feature2", "Correlation", "AbsCorrelation"])
        )

    features = list(correlation_matrix.columns)
    pairs = []
    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            corr = correlation_matrix.iloc[i, j]
            if pd.notna(corr) and abs(corr) >= threshold:
                pairs.append(
                    {
                        "Feature1": features[i],
                        "Feature2": features[j],
                        "Correlation": float(corr),
                        "AbsCorrelation": abs(float(corr)),
                    }
                )

    if not pairs:
        pairs_df = pd.DataFrame(columns=["Feature1", "Feature2", "Correlation", "AbsCorrelation"])
    else:
        pairs_df = (
            pd.DataFrame(pairs)
            .sort_values("AbsCorrelation", ascending=False)
            .reset_index(drop=True)
        )

    return RedundancyResult(pairs_df=pairs_df)
