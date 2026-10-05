"""Outlier detection and treatment for FE-02.

FE-02 supports three detection methods and three actions. Outlier
handling is intentionally **off by default** in the cleaning pipeline
because the methodology for outlier treatment of transactional data has
not been approved by the mentor yet. Outliers are *detected* and
reported; whether they are *treated* is a working decision per column.

Methods
-------

- ``"iqr"`` — values outside ``[Q1 - k * IQR, Q3 + k * IQR]`` are flagged.
- ``"zscore"`` — values with ``|z| > threshold`` (using mean / std) are flagged.
- ``"winsorize"`` — values outside the IQR fences are clipped to the fences.

Actions
-------

- ``"clip"`` — clip values to the chosen fences (winsorize / clip).
- ``"remove"`` — drop the affected rows.
- ``"flag"`` — add a boolean column marking the row as an outlier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

__all__ = [
    "OutlierMethod",
    "OutlierAction",
    "OutlierResult",
    "detect_outliers",
    "treat_outliers",
    "summarise_outliers",
]


OutlierMethod = Literal["iqr", "zscore", "winsorize"]
OutlierAction = Literal["clip", "remove", "flag"]


@dataclass
class OutlierResult:
    """Outcome of an outlier-treatment pass.

    Attributes
    ----------
    df : pandas.DataFrame
        DataFrame after treatment.
    rows_before : int
        Rows in the input.
    rows_after : int
        Rows in the output.
    rows_removed : int
        Rows removed (only set when ``action="remove"``).
    per_column : list[dict]
        One record per inspected column with ``column``, ``method``,
        ``action``, ``lower``, ``upper``, ``outlier_count``,
        ``outlier_rate``.
    """

    df: pd.DataFrame
    rows_before: int
    rows_after: int
    rows_removed: int
    per_column: list[dict] = field(default_factory=list)


def _iqr_bounds(
    series: pd.Series,
    multiplier: float,
) -> tuple[float, float]:
    """Return the lower / upper IQR fences for `series`."""
    non_na = series.dropna()
    if non_na.empty:
        return (float("nan"), float("nan"))
    q1 = float(non_na.quantile(0.25))
    q3 = float(non_na.quantile(0.75))
    iqr = q3 - q1
    return (q1 - multiplier * iqr, q3 + multiplier * iqr)


def _zscore_bounds(series: pd.Series, threshold: float) -> tuple[float, float]:
    """Return ``(mean - k * std, mean + k * std)`` for `series`."""
    non_na = series.dropna()
    if non_na.empty:
        return (float("nan"), float("nan"))
    mean = float(non_na.mean())
    std = float(non_na.std(ddof=0))
    if std == 0 or np.isnan(std):
        return (mean, mean)
    return (mean - threshold * std, mean + threshold * std)


def detect_outliers(
    df: pd.DataFrame,
    columns: list[str],
    *,
    method: OutlierMethod = "iqr",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
) -> dict[str, pd.Series]:
    """Return a ``{column: boolean_mask}`` dictionary of outlier rows.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    columns : list[str]
        Numeric columns to inspect.
    method : {"iqr", "zscore"}
        Detection method.
    iqr_multiplier : float, default 1.5
        Multiplier for the IQR fences.
    zscore_threshold : float, default 3.0
        Absolute z-score threshold.

    Returns
    -------
    dict[str, pandas.Series]
        Boolean Series per column. ``True`` indicates an outlier.
    """
    out: dict[str, pd.Series] = {}
    for col in columns:
        if col not in df.columns:
            raise KeyError(f"Column {col!r} not in DataFrame.")
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(
                f"Column {col!r} has dtype {df[col].dtype!r}; outlier detection "
                "requires numeric dtype."
            )
        if method == "iqr":
            lo, hi = _iqr_bounds(df[col], iqr_multiplier)
        elif method == "zscore":
            lo, hi = _zscore_bounds(df[col], zscore_threshold)
        else:
            raise ValueError(f"Detection method {method!r} not supported for detect_outliers().")
        s = df[col]
        mask = ((s < lo) | (s > hi)).fillna(False)
        out[col] = mask.astype(bool)
    return out


def summarise_outliers(
    df: pd.DataFrame,
    columns: list[str],
    *,
    method: OutlierMethod = "iqr",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
) -> pd.DataFrame:
    """Build a per-column summary of outliers.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    columns : list[str]
        Numeric columns to inspect.
    method, iqr_multiplier, zscore_threshold
        See :func:`detect_outliers`.

    Returns
    -------
    pandas.DataFrame
        Columns ``column``, ``method``, ``lower``, ``upper``,
        ``outlier_count``, ``outlier_rate``, ``total_non_null``.
    """
    masks = detect_outliers(
        df,
        columns,
        method=method,
        iqr_multiplier=iqr_multiplier,
        zscore_threshold=zscore_threshold,
    )
    records: list[dict] = []
    for col in columns:
        m = masks[col]
        s = df[col]
        non_na = s.dropna()
        if method == "iqr":
            lo, hi = _iqr_bounds(s, iqr_multiplier)
        else:
            lo, hi = _zscore_bounds(s, zscore_threshold)
        records.append(
            {
                "column": col,
                "method": method,
                "lower": lo,
                "upper": hi,
                "outlier_count": int(m.sum()),
                "outlier_rate": round(m.sum() / max(int(df.shape[0]), 1) * 100.0, 4),
                "total_non_null": int(non_na.shape[0]),
            }
        )
    return pd.DataFrame.from_records(records)


def treat_outliers(
    df: pd.DataFrame,
    columns: list[str],
    *,
    method: OutlierMethod = "iqr",
    action: OutlierAction = "flag",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
) -> OutlierResult:
    """Detect and treat outliers in the selected numeric columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame (not mutated).
    columns : list[str]
        Numeric columns to inspect.
    method : {"iqr", "zscore", "winsorize"}
        Detection / treatment method.
    action : {"clip", "remove", "flag"}
        Treatment action.
    iqr_multiplier : float, default 1.5
        Multiplier for the IQR fences (used by ``iqr`` and ``winsorize``).
    zscore_threshold : float, default 3.0
        Absolute z-score threshold (used by ``zscore``).

    Returns
    -------
    OutlierResult
        Cleaned DataFrame plus a per-column report.
    """
    valid_methods = {"iqr", "zscore", "winsorize"}
    valid_actions = {"clip", "remove", "flag"}
    if method not in valid_methods:
        raise ValueError(f"Unknown method {method!r}. Valid: {sorted(valid_methods)}.")
    if action not in valid_actions:
        raise ValueError(f"Unknown action {action!r}. Valid: {sorted(valid_actions)}.")

    rows_before = int(df.shape[0])
    work = df.copy(deep=True)
    per_column: list[dict] = []
    rows_removed = 0

    if method == "winsorize":
        # Winsorize always uses IQR fences regardless of the action.
        for col in columns:
            if col not in work.columns:
                raise KeyError(f"Column {col!r} not in DataFrame.")
            if not pd.api.types.is_numeric_dtype(work[col]):
                raise ValueError(
                    f"Column {col!r} has dtype {work[col].dtype!r}; winsorize "
                    "requires numeric dtype."
                )
            lo, hi = _iqr_bounds(work[col], iqr_multiplier)
            before = work[col].copy()
            work[col] = work[col].clip(lower=lo, upper=hi)
            n_outliers = int(((before < lo) | (before > hi)).fillna(False).sum())
            per_column.append(
                {
                    "column": col,
                    "method": method,
                    "action": action,
                    "lower": lo,
                    "upper": hi,
                    "outlier_count": n_outliers,
                    "outlier_rate": round(n_outliers / max(rows_before, 1) * 100.0, 4),
                }
            )
        return OutlierResult(
            df=work,
            rows_before=rows_before,
            rows_after=int(work.shape[0]),
            rows_removed=0,
            per_column=per_column,
        )

    masks = detect_outliers(
        work,
        columns,
        method=method,
        iqr_multiplier=iqr_multiplier,
        zscore_threshold=zscore_threshold,
    )

    # Aggregate outlier mask across columns.
    any_outlier = pd.Series(False, index=work.index)
    for col in columns:
        m = masks[col]
        any_outlier = any_outlier | m
        s = work[col]
        if method == "iqr":
            lo, hi = _iqr_bounds(s, iqr_multiplier)
        else:
            lo, hi = _zscore_bounds(s, zscore_threshold)
        n_outliers = int(m.sum())
        per_column.append(
            {
                "column": col,
                "method": method,
                "action": action,
                "lower": lo,
                "upper": hi,
                "outlier_count": n_outliers,
                "outlier_rate": round(n_outliers / max(rows_before, 1) * 100.0, 4),
            }
        )

    if action == "flag":
        work["IsOutlier"] = any_outlier.astype(bool)
    elif action == "clip":
        for col in columns:
            s = work[col]
            m = masks[col]
            if method == "iqr":
                lo, hi = _iqr_bounds(s, iqr_multiplier)
            else:
                lo, hi = _zscore_bounds(s, zscore_threshold)
            work.loc[m, col] = work.loc[m, col].clip(lower=lo, upper=hi)
    elif action == "remove":
        rows_removed = int(any_outlier.sum())
        work = work.loc[~any_outlier].reset_index(drop=True)

    return OutlierResult(
        df=work,
        rows_before=rows_before,
        rows_after=int(work.shape[0]),
        rows_removed=rows_removed,
        per_column=per_column,
    )
