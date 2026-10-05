"""FE-03 outlier analysis: outlier detection methods.

Single-sources detection logic by **wrapping and reusing**
:mod:`customer_segmentation.preprocessing.outliers` for IQR / zscore
detection. Adds a **percentile-based** detector on top (the existing
outliers module only supports IQR fences and z-score thresholds).

Why wrap rather than duplicate?
-------------------------------
FE-02's outlier module already implements IQR / zscore detection
correctly (with NaN-safe quantile computation). Duplicating that
logic here would risk silent drift between FE-02 and FE-03. So this
module:

- Re-exports ``detect_outliers`` and ``summarise_outliers`` so FE-03
  callers have one import path.
- Adds a percentile-based detector and a unified per-feature summary
  table that handles the three methods consistently.

Hard rules (from AGENTS.md):
- No mutation of the input DataFrame. All public functions return new
  Series / DataFrames.
- No hard-coded thresholds; all come from the caller (ultimately from
  ``configs/outlier.yaml``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from customer_segmentation.preprocessing.outliers import (
    OutlierMethod,
    detect_outliers,
    summarise_outliers,
)

__all__ = [
    "DetectionMethod",
    "DetectionRecord",
    "iqr_bounds",
    "iqr_mask",
    "zscore_bounds",
    "zscore_mask",
    "percentile_bounds",
    "percentile_mask",
    "detect_for_feature",
    "summarise_detection_for_features",
    "build_detection_summary_table",
]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


# FE-03 supports three detection methods. The string values mirror the
# YAML (``configs/outlier.yaml``).
DetectionMethod = Literal["iqr", "zscore", "percentile"]


@dataclass(frozen=True)
class DetectionRecord:
    """Per-feature detection result.

    Attributes
    ----------
    feature : str
        Logical feature name (``"Quantity"``, ``"LineRevenue"``, ...).
    method : str
        Detection method (``"iqr"``, ``"zscore"``, ``"percentile"``).
    threshold : float
        Threshold used by the method (IQR multiplier, z-score
        threshold, or upper percentile).
    lower : float
        Lower fence / bound.
    upper : float
        Upper fence / bound.
    candidates : int
        Number of rows flagged as outliers.
    rate : float
        ``candidates / total_rows``.
    total_rows : int
        Total rows considered.
    filter_mode : str
        Name of the filter mode used to subset the input (e.g.
        ``"all_rows"``, ``"clean_purchase"``).
    """

    feature: str
    method: str
    threshold: float
    lower: float
    upper: float
    candidates: int
    rate: float
    total_rows: int
    filter_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "method": self.method,
            "threshold": self.threshold,
            "lower": self.lower,
            "upper": self.upper,
            "candidates": self.candidates,
            "rate": self.rate,
            "total_rows": self.total_rows,
            "filter_mode": self.filter_mode,
        }


# ---------------------------------------------------------------------------
# IQR
# ---------------------------------------------------------------------------


def iqr_bounds(series: pd.Series, multiplier: float = 1.5) -> tuple[float, float]:
    """IQR fences for `series` (NaN-safe).

    Returns
    -------
    (lower, upper) : tuple[float, float]
        Lower = Q1 − k·IQR, Upper = Q3 + k·IQR. NaN for empty.
    """
    non_na = series.dropna()
    if non_na.empty:
        return (float("nan"), float("nan"))
    q1 = float(non_na.quantile(0.25))
    q3 = float(non_na.quantile(0.75))
    iqr = q3 - q1
    return (q1 - multiplier * iqr, q3 + multiplier * iqr)


def iqr_mask(
    series: pd.Series,
    multiplier: float = 1.5,
) -> tuple[pd.Series, float, float]:
    """Boolean mask for IQR outliers (values outside ``[lo, hi]``).

    Parameters
    ----------
    series : pandas.Series
        Numeric Series.
    multiplier : float, default 1.5
        IQR multiplier.

    Returns
    -------
    (mask, lower, upper)
        ``mask`` is aligned with ``series.index``.
    """
    lo, hi = iqr_bounds(series, multiplier=multiplier)
    if np.isnan(lo) or np.isnan(hi):
        mask = pd.Series(False, index=series.index)
    else:
        mask = ((series < lo) | (series > hi)).fillna(False).astype(bool)
    return mask, lo, hi


# ---------------------------------------------------------------------------
# Z-score
# ---------------------------------------------------------------------------


def zscore_bounds(series: pd.Series, threshold: float = 3.0) -> tuple[float, float]:
    """Return ``(mean − k·std, mean + k·std)`` for `series` (NaN-safe)."""
    non_na = series.dropna()
    if non_na.empty:
        return (float("nan"), float("nan"))
    mean = float(non_na.mean())
    std = float(non_na.std(ddof=0))
    if std == 0 or np.isnan(std):
        return (mean, mean)
    return (mean - threshold * std, mean + threshold * std)


def zscore_mask(
    series: pd.Series,
    threshold: float = 3.0,
) -> tuple[pd.Series, float, float]:
    """Boolean mask for ``|z| > threshold`` (NaN-safe)."""
    lo, hi = zscore_bounds(series, threshold=threshold)
    if np.isnan(lo) or np.isnan(hi) or lo == hi:
        mask = pd.Series(False, index=series.index)
    else:
        mask = ((series < lo) | (series > hi)).fillna(False).astype(bool)
    return mask, lo, hi


# ---------------------------------------------------------------------------
# Percentile
# ---------------------------------------------------------------------------


def percentile_bounds(
    series: pd.Series,
    upper_percentile: float = 99.0,
) -> tuple[float, float]:
    """Return ``(lower_fence, upper_value)`` for the upper percentile.

    The lower fence is set to the symmetric lower percentile
    (``100 − upper_percentile``). This matches the convention used by
    :mod:`customer_segmentation.preprocessing.outliers._iqr_bounds`
    (symmetric fences).

    Parameters
    ----------
    series : pandas.Series
        Numeric Series.
    upper_percentile : float, default 99.0
        Upper percentile in (0, 100).

    Returns
    -------
    (lower_fence, upper_value) : tuple[float, float]
        NaN for empty input.
    """
    non_na = series.dropna()
    if non_na.empty:
        return (float("nan"), float("nan"))
    if not (0 < upper_percentile < 100):
        raise ValueError(f"upper_percentile must be in (0, 100); got {upper_percentile}.")
    lower_p = max(0.0, 100.0 - upper_percentile)
    lower = float(non_na.quantile(lower_p / 100.0))
    upper = float(non_na.quantile(upper_percentile / 100.0))
    return (lower, upper)


def percentile_mask(
    series: pd.Series,
    upper_percentile: float = 99.0,
) -> tuple[pd.Series, float, float]:
    """Boolean mask for percentile outliers.

    A row is flagged if its value lies strictly below the symmetric
    lower percentile **or** strictly above the upper percentile.
    """
    lo, hi = percentile_bounds(series, upper_percentile=upper_percentile)
    if np.isnan(lo) or np.isnan(hi):
        mask = pd.Series(False, index=series.index)
    else:
        # Use ``<`` and ``>`` (strict) so values that fall *exactly* on
        # the fence are not flagged; this avoids spurious flagging of
        # values that are common in the dataset.
        mask = ((series < lo) | (series > hi)).fillna(False).astype(bool)
    return mask, lo, hi


# ---------------------------------------------------------------------------
# Unified per-feature detection
# ---------------------------------------------------------------------------


def detect_for_feature(
    series: pd.Series,
    *,
    feature_name: str,
    method: DetectionMethod = "iqr",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
    percentile_threshold: float = 99.0,
    filter_mode: str = "all_rows",
) -> tuple[pd.Series, DetectionRecord]:
    """Run one detection method on one Series and return a :class:`DetectionRecord`.

    Parameters
    ----------
    series : pandas.Series
        Numeric Series (already filtered by the chosen ``filter_mode``).
    feature_name : str
        Logical feature name (used in the record).
    method : {"iqr", "zscore", "percentile"}
        Detection method.
    iqr_multiplier : float, default 1.5
        Used when ``method="iqr"``.
    zscore_threshold : float, default 3.0
        Used when ``method="zscore"``.
    percentile_threshold : float, default 99.0
        Used when ``method="percentile"``.
    filter_mode : str, default "all_rows"
        Name of the filter mode the caller applied (informational).

    Returns
    -------
    (mask, DetectionRecord)
        ``mask`` is a boolean Series aligned with ``series.index``.
    """
    if method == "iqr":
        mask, lo, hi = iqr_mask(series, multiplier=iqr_multiplier)
        record = DetectionRecord(
            feature=feature_name,
            method="iqr",
            threshold=float(iqr_multiplier),
            lower=float(lo),
            upper=float(hi),
            candidates=int(mask.sum()),
            rate=float(mask.sum()) / max(int(len(series)), 1),
            total_rows=int(len(series)),
            filter_mode=filter_mode,
        )
    elif method == "zscore":
        mask, lo, hi = zscore_mask(series, threshold=zscore_threshold)
        record = DetectionRecord(
            feature=feature_name,
            method="zscore",
            threshold=float(zscore_threshold),
            lower=float(lo),
            upper=float(hi),
            candidates=int(mask.sum()),
            rate=float(mask.sum()) / max(int(len(series)), 1),
            total_rows=int(len(series)),
            filter_mode=filter_mode,
        )
    elif method == "percentile":
        mask, lo, hi = percentile_mask(series, upper_percentile=percentile_threshold)
        record = DetectionRecord(
            feature=feature_name,
            method="percentile",
            threshold=float(percentile_threshold),
            lower=float(lo),
            upper=float(hi),
            candidates=int(mask.sum()),
            rate=float(mask.sum()) / max(int(len(series)), 1),
            total_rows=int(len(series)),
            filter_mode=filter_mode,
        )
    else:
        raise ValueError(
            f"Unknown detection method {method!r}; " f"valid: ['iqr', 'zscore', 'percentile']."
        )
    return mask, record


def summarise_detection_for_features(
    df: pd.DataFrame,
    columns: Iterable[str],
    *,
    method: DetectionMethod = "iqr",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
    percentile_threshold: float = 99.0,
    filter_mode: str = "all_rows",
) -> list[DetectionRecord]:
    """Run a single detection method across several columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Source DataFrame (already filtered).
    columns : iterable of str
        Columns to inspect.
    method : {"iqr", "zscore", "percentile"}
        Detection method.
    iqr_multiplier : float, default 1.5
    zscore_threshold : float, default 3.0
    percentile_threshold : float, default 99.0
    filter_mode : str, default "all_rows"

    Returns
    -------
    list[DetectionRecord]
        One record per column.
    """
    records: list[DetectionRecord] = []
    for col in columns:
        if col not in df.columns:
            raise KeyError(f"Column {col!r} not in DataFrame.")
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(
                f"Column {col!r} has dtype {df[col].dtype!r}; detection requires numeric."
            )
        _, rec = detect_for_feature(
            df[col],
            feature_name=col,
            method=method,
            iqr_multiplier=iqr_multiplier,
            zscore_threshold=zscore_threshold,
            percentile_threshold=percentile_threshold,
            filter_mode=filter_mode,
        )
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Detection summary table
# ---------------------------------------------------------------------------


def build_detection_summary_table(
    records: Iterable[DetectionRecord],
) -> pd.DataFrame:
    """Convert an iterable of :class:`DetectionRecord` into a DataFrame.

    Parameters
    ----------
    records : iterable of DetectionRecord
        Records to serialise.

    Returns
    -------
    pandas.DataFrame
        One row per record. Sorted by ``feature`` then ``method`` for
        deterministic output.
    """
    rows = [r.to_dict() for r in records]
    df = pd.DataFrame.from_records(rows)
    if df.empty:
        return df
    df = df.sort_values(["feature", "method", "filter_mode"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Convenience re-export (for callers that prefer the FE-02 helper API)
# ---------------------------------------------------------------------------


def detect_outliers_dataframe(
    df: pd.DataFrame,
    columns: Iterable[str],
    *,
    method: OutlierMethod = "iqr",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
) -> Mapping[str, pd.Series]:
    """Wrap :func:`preprocessing.outliers.detect_outliers`.

    Provided so FE-03 callers have a single import path.
    """
    return detect_outliers(
        df,
        list(columns),
        method=method,  # type: ignore[arg-type]
        iqr_multiplier=iqr_multiplier,
        zscore_threshold=zscore_threshold,
    )


def summarise_outliers_dataframe(
    df: pd.DataFrame,
    columns: Iterable[str],
    *,
    method: OutlierMethod = "iqr",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
) -> pd.DataFrame:
    """Wrap :func:`preprocessing.outliers.summarise_outliers`."""
    return summarise_outliers(
        df,
        list(columns),
        method=method,  # type: ignore[arg-type]
        iqr_multiplier=iqr_multiplier,
        zscore_threshold=zscore_threshold,
    )
