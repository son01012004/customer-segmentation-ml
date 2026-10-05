"""Feature scaling utilities.

Implements:
- S0: none (identity)
- S1: standard (StandardScaler: mean=0, std=1)
- S2: minmax (MinMaxScaler: range=[0, 1])
- S3: robust (RobustScaler: median=0, IQR=1)

All scalers are sklearn-compatible and can be pickled for reproducibility.

Hard constraints:
- Scaler is fit on the full dataset (unsupervised preprocessing).
- All scaled features are cast to float64.
- No random state used by any scaler (deterministic).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from sklearn.preprocessing import (  # type: ignore[import-untyped]
    MinMaxScaler,
    RobustScaler,
    StandardScaler,
)

__all__ = [
    "ScalerKind",
    "ScalingResult",
    "scale_features",
    "apply_scaling",
]

ScalerKind = Literal["none", "standard", "minmax", "robust"]


@dataclass
class ScalingResult:
    """Result of scaling operation."""

    df: pd.DataFrame
    method: str
    feature_columns: list[str]
    scaler: StandardScaler | RobustScaler | MinMaxScaler | None


def apply_scaling(
    df: pd.DataFrame,
    feature_columns: list[str],
    method: ScalerKind,
) -> ScalingResult:
    """Scale numeric features using the requested scaler.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix.
    feature_columns : list[str]
        Columns to scale.
    method : {"none", "standard", "minmax", "robust"}
        Scaler to use.

    Returns
    -------
    ScalingResult
        Scaled DataFrame and fitted scaler (or None if method="none").

    Raises
    ------
    ValueError
        If method is not recognized.
    """
    result = df.copy()
    subset = result[feature_columns].astype(float)

    if method == "none":
        return ScalingResult(
            df=result,
            method=method,
            feature_columns=feature_columns,
            scaler=None,
        )
    elif method == "standard":
        scaler = StandardScaler()
        scaled = scaler.fit_transform(subset)
        result[feature_columns] = scaled.astype(float)
        return ScalingResult(
            df=result,
            method=method,
            feature_columns=feature_columns,
            scaler=scaler,
        )
    elif method == "minmax":
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(subset)
        result[feature_columns] = scaled.astype(float)
        return ScalingResult(
            df=result,
            method=method,
            feature_columns=feature_columns,
            scaler=scaler,
        )
    elif method == "robust":
        scaler = RobustScaler()
        scaled = scaler.fit_transform(subset)
        result[feature_columns] = scaled.astype(float)
        return ScalingResult(
            df=result,
            method=method,
            feature_columns=feature_columns,
            scaler=scaler,
        )
    else:
        raise ValueError(
            f"Unknown scaling method: {method!r}. " f"Supported: none, standard, minmax, robust."
        )


def scale_features(
    df: pd.DataFrame,
    method: ScalerKind = "standard",
) -> tuple[pd.DataFrame, StandardScaler | RobustScaler | MinMaxScaler | None]:
    """Scale numeric features using the requested scaler.

    Backward-compatible wrapper for apply_scaling.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix.
    method : {"standard", "robust", "minmax", "none"}
        Scaler to use.

    Returns
    -------
    tuple[pandas.DataFrame, object]
        (scaled DataFrame, fitted scaler or None).
    """
    feature_columns = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    result = apply_scaling(df, feature_columns, method)
    return result.df, result.scaler
