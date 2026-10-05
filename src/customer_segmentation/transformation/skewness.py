"""Skewness correction for numeric features.

Implements:
- T0: none (identity)
- T1: log1p (natural log with +1 for zero)
- T2: Yeo-Johnson (sklearn PowerTransformer, supports negatives)

Hard constraints:
- T1 (log1p): only applied to non-negative features.
- T2 (yeo_johnson): supports all features.
- Pipeline must NOT silently apply log1p to feature with negatives.
- Pipeline must NOT shift data by a constant to force log1p.
- No random state used (deterministic pipeline).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.preprocessing import PowerTransformer  # type: ignore[import-untyped]

__all__ = [
    "apply_transformation",
    "apply_log1p",
    "apply_yeo_johnson",
    "apply_none",
]

SkewMethod = Literal["none", "log1p", "yeo_johnson"]


@dataclass
class TransformationResult:
    """Result of transformation operation."""

    df: pd.DataFrame
    method: str
    feature_columns: list[str]
    lambda_values: dict[str, float | None] | None = None


def apply_none(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Apply identity transformation (no change).

    Parameters
    ----------
    df : pandas.DataFrame
        Feature DataFrame.
    feature_columns : list[str]
        Columns to transform.

    Returns
    -------
    pandas.DataFrame
        Same DataFrame (identity).
    """
    return df


def apply_log1p(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Apply log1p transformation.

    log1p(x) = log(1 + x) for x >= 0.

    Parameters
    ----------
    df : pandas.DataFrame
        Feature DataFrame.
    feature_columns : list[str]
        Columns to transform.

    Returns
    -------
    pandas.DataFrame
        Transformed DataFrame.

    Raises
    ------
    ValueError
        If any value in feature_columns is negative.
    """
    result = df.copy()
    for col in feature_columns:
        series = result[col]
        if series.isna().all():
            continue
        min_val = series.min()
        if min_val < 0:
            raise ValueError(
                f"log1p cannot be applied to feature {col!r}: "
                f"has negative values (min={min_val}). "
                f"Use yeo_johnson for features with negative values."
            )
        result[col] = np.log1p(series)
    return result


def apply_yeo_johnson(
    df: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, PowerTransformer, dict[str, float | None]]:
    """Apply Yeo-Johnson power transformation.

    Supports features with negative, zero, and positive values.
    Uses sklearn.preprocessing.PowerTransformer with method="yeo-johnson".

    Parameters
    ----------
    df : pandas.DataFrame
        Feature DataFrame.
    feature_columns : list[str]
        Columns to transform.

    Returns
    -------
    tuple[pandas.DataFrame, PowerTransformer, dict]
        (transformed DataFrame, fitted PowerTransformer, lambda values per feature).
    """
    result = df.copy()
    subset = result[feature_columns].astype(float)

    # Fill NaN with 0 temporarily for fitting (they will be filled by imputation earlier)
    # But PowerTransformer drops NaN rows for fitting - we need to handle this.
    # Approach: fit only on non-NaN rows, transform all rows.
    mask = subset.notna().all(axis=1)
    if mask.sum() == 0:
        raise ValueError(
            f"All rows have at least one NaN in features {feature_columns!r}. "
            f"Imputation must be applied before transformation."
        )

    pt = PowerTransformer(method="yeo-johnson", standardize=False)

    # Fit on non-NaN subset
    subset_fit = subset.loc[mask]
    pt.fit(subset_fit)

    # Transform all rows (PowerTransformer handles NaN by propagating)
    subset_transformed = pt.transform(subset)
    result[feature_columns] = subset_transformed

    # Lambda is per-feature; extract from lambdas_
    # PowerTransformer stores lambdas_ as array, one per column
    lambda_values: dict[str, float | None] = {}
    for i, col in enumerate(feature_columns):
        lambda_values[col] = (
            float(pt.lambdas_[i]) if hasattr(pt, "lambdas_") and pt.lambdas_ is not None else None
        )

    return result, pt, lambda_values


def apply_transformation(
    df: pd.DataFrame,
    feature_columns: list[str],
    method: SkewMethod,
) -> TransformationResult:
    """Apply a skewness-correction transform to numeric columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix (numeric columns only).
    feature_columns : list[str]
        List of column names to transform.
    method : {"none", "log1p", "yeo_johnson"}
        Transform to apply.

    Returns
    -------
    TransformationResult
        Transformed DataFrame and metadata.

    Raises
    ------
    ValueError
        If method is not recognized or log1p is applied to negative values.
    """
    if method == "none":
        result_df = apply_none(df, feature_columns)
        return TransformationResult(
            df=result_df,
            method=method,
            feature_columns=feature_columns,
            lambda_values=None,
        )
    elif method == "log1p":
        result_df = apply_log1p(df, feature_columns)
        return TransformationResult(
            df=result_df,
            method=method,
            feature_columns=feature_columns,
            lambda_values=None,
        )
    elif method == "yeo_johnson":
        result_df, pt, lambda_values = apply_yeo_johnson(df, feature_columns)
        return TransformationResult(
            df=result_df,
            method=method,
            feature_columns=feature_columns,
            lambda_values=lambda_values,
        )
    else:
        raise ValueError(
            f"Unknown transformation method: {method!r}. " f"Supported: none, log1p, yeo_johnson."
        )
