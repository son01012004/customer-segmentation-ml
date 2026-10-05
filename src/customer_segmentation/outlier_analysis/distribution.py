"""FE-03 outlier analysis: distribution profiling.

Pure functions. No I/O. No mutation. Designed to be reused by the
detection, sensitivity, customer-diagnostic, and report modules.

Why a separate module?
----------------------
``customer_segmentation.data.audit`` already exposes ``numerical_profile``
which is used by FE-01 / FE-02. FE-03 needs additional percentiles
(P99.5, P99.9), skewness, and shape diagnostics that the FE-02 helper
does not provide. We keep the implementation here so FE-03 stays
self-contained and does not silently change FE-01 / FE-02 outputs.

Hard rules (from AGENTS.md):
- All thresholds / percentiles must be passed in by the caller. No
  hard-coded literals.
- Functions never mutate the input Series.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "DistributionProfile",
    "DEFAULT_PERCENTILES",
    "EXTENDED_PERCENTILES",
    "distribution_profile",
    "skewness",
    "compute_percentiles",
    "compute_iqr_bounds",
    "summarise_distribution_dataframe",
]


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# The minimum percentile set required by the FE-03 task spec (section 6).
DEFAULT_PERCENTILES: tuple[float, ...] = (1, 5, 25, 50, 75, 90, 95, 99, 99.5, 99.9)


# An extended set used when extra tail detail is needed (e.g. for
# sensitivity analysis).
EXTENDED_PERCENTILES: tuple[float, ...] = (
    0.1,
    1,
    5,
    25,
    50,
    75,
    90,
    95,
    99,
    99.5,
    99.9,
    99.95,
)


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------


@dataclass
class DistributionProfile:
    """Distribution summary for a single numeric Series.

    Attributes
    ----------
    column : str
        Column name.
    count : int
        Number of non-null values used for the profile.
    missing_count : int
        Number of NaN / NA entries in the column.
    missing_rate : float
        ``missing_count / total_rows`` (between 0 and 1).
    total_rows : int
        Total number of rows in the parent DataFrame.
    min, max, mean, median, std : float
        First-order statistics.
    q1, q3, iqr : float
        Quartile statistics.
    zero_count, negative_count : int
        Counts of zero / negative values.
    skewness : float
        Fisher-Pearson skewness (adjusted for sample bias).
    percentiles : dict[str, float]
        Mapping ``"p01" → 1.0`` etc. Keys are ``f"p{p:02.1f}"``
        (e.g. ``"p99.9"``).
    """

    column: str
    count: int
    missing_count: int
    missing_rate: float
    total_rows: int
    min: float
    max: float
    mean: float
    median: float
    std: float
    q1: float
    q3: float
    iqr: float
    zero_count: int
    negative_count: int
    skewness: float
    percentiles: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict (flat)."""
        out = {
            "column": self.column,
            "count": self.count,
            "missing_count": self.missing_count,
            "missing_rate": self.missing_rate,
            "total_rows": self.total_rows,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "median": self.median,
            "std": self.std,
            "q1": self.q1,
            "q3": self.q3,
            "iqr": self.iqr,
            "zero_count": self.zero_count,
            "negative_count": self.negative_count,
            "skewness": self.skewness,
        }
        out.update(self.percentiles)
        return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(x: Any) -> float:
    """Coerce a numpy / pandas scalar to a Python float; NaN for NaN."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    if not np.isfinite(v):
        return float("nan")
    return v


def _percentile_label(p: float) -> str:
    """Stable column label for a percentile, e.g. ``p99.9``.

    Integer percentiles (``1``, ``99``) produce ``"p1"``, ``"p99"``.
    Fractional percentiles (``99.5``, ``99.9``) produce ``"p99.5"``,
    ``"p99.9"`` with a single decimal place. Trailing zeros are stripped.
    """
    if p == int(p):
        return f"p{int(p)}"
    # Strip trailing zeros while keeping at least one decimal place.
    formatted = f"{p:.1f}".rstrip("0").rstrip(".")
    return f"p{formatted}"


def compute_percentiles(
    series: pd.Series,
    percentiles: Iterable[float],
) -> dict[str, float]:
    """Compute percentiles for `series` (non-null values only).

    Parameters
    ----------
    series : pandas.Series
        Input values.
    percentiles : iterable of float
        Percentile values in [0, 100].

    Returns
    -------
    dict[str, float]
        Mapping ``"p01" → value``. NaN for empty input.
    """
    non_na = series.dropna()
    if non_na.empty:
        return {_percentile_label(p): float("nan") for p in percentiles}
    quantiles = non_na.quantile([p / 100.0 for p in percentiles])
    out: dict[str, float] = {}
    for p in percentiles:
        q = p / 100.0
        if q in quantiles.index:
            out[_percentile_label(p)] = _safe_float(quantiles.loc[q])
        else:
            out[_percentile_label(p)] = float("nan")
    return out


def skewness(series: pd.Series) -> float:
    """Compute Fisher-Pearson adjusted skewness (NaN-safe)."""
    non_na = series.dropna()
    if non_na.empty:
        return float("nan")
    try:
        # ``ddof=1`` → Fisher-Pearson adjusted estimator (consistent with
        # ``scipy.stats.skew(bias=False)``).
        return _safe_float(non_na.skew())
    except (ValueError, ZeroDivisionError):
        return float("nan")


def compute_iqr_bounds(
    series: pd.Series,
    multiplier: float = 1.5,
) -> tuple[float, float]:
    """Return the IQR fences (lower, upper) for `series`.

    Parameters
    ----------
    series : pandas.Series
        Input values.
    multiplier : float, default 1.5
        Multiplier applied to IQR.

    Returns
    -------
    (lower, upper) : tuple[float, float]
        Lower = Q1 − k·IQR, Upper = Q3 + k·IQR. NaN for empty input.

    Notes
    -----
    Pure wrapper; the actual fence calculation lives in
    :func:`customer_segmentation.preprocessing.outliers._iqr_bounds` and
    is reused by the detection module. This convenience helper exists
    so report builders can quote IQR fences without importing the
    outlier-detection module.
    """
    non_na = series.dropna()
    if non_na.empty:
        return (float("nan"), float("nan"))
    q1 = _safe_float(non_na.quantile(0.25))
    q3 = _safe_float(non_na.quantile(0.75))
    iqr = q3 - q1
    return (q1 - multiplier * iqr, q3 + multiplier * iqr)


# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------


def distribution_profile(
    series: pd.Series,
    column: str | None = None,
    *,
    percentiles: Iterable[float] = DEFAULT_PERCENTILES,
    total_rows: int | None = None,
) -> DistributionProfile:
    """Build a full distribution profile of `series`.

    Parameters
    ----------
    series : pandas.Series
        Numeric Series (other dtypes raise ``TypeError``).
    column : str, optional
        Logical column name to embed in the result. Defaults to
        ``series.name``.
    percentiles : iterable of float, default ``DEFAULT_PERCENTILES``
        Percentiles to compute, in [0, 100].
    total_rows : int, optional
        Total rows in the parent DataFrame. Used to compute the
        missing rate. Defaults to ``len(series)``.

    Returns
    -------
    DistributionProfile
        Fully populated profile.

    Raises
    ------
    TypeError
        If `series` is not numeric.
    """
    if not isinstance(series, pd.Series):
        raise TypeError(f"series must be a pandas.Series; got {type(series).__name__}.")
    if not pd.api.types.is_numeric_dtype(series):
        raise TypeError(
            f"Series dtype {series.dtype!r} is not numeric; distribution_profile "
            "requires a numeric dtype."
        )
    if total_rows is None:
        total_rows = int(len(series))

    col = column if column is not None else str(series.name) if series.name is not None else "?"

    missing_count = int(series.isna().sum())
    missing_rate = (missing_count / total_rows) if total_rows else 0.0
    non_na = series.dropna()

    if non_na.empty:
        empty_pctiles = {_percentile_label(p): float("nan") for p in percentiles}
        return DistributionProfile(
            column=col,
            count=0,
            missing_count=missing_count,
            missing_rate=float(missing_rate),
            total_rows=int(total_rows),
            min=float("nan"),
            max=float("nan"),
            mean=float("nan"),
            median=float("nan"),
            std=float("nan"),
            q1=float("nan"),
            q3=float("nan"),
            iqr=float("nan"),
            zero_count=0,
            negative_count=0,
            skewness=float("nan"),
            percentiles=empty_pctiles,
        )

    min_v = _safe_float(non_na.min())
    max_v = _safe_float(non_na.max())
    mean_v = _safe_float(non_na.mean())
    median_v = _safe_float(non_na.median())
    std_v = _safe_float(non_na.std())
    q1_v = _safe_float(non_na.quantile(0.25))
    q3_v = _safe_float(non_na.quantile(0.75))
    iqr_v = q3_v - q1_v
    zero_count = int((non_na == 0).sum())
    negative_count = int((non_na < 0).sum())
    skew_v = skewness(non_na)
    pctiles = compute_percentiles(non_na, percentiles)

    return DistributionProfile(
        column=col,
        count=int(non_na.shape[0]),
        missing_count=missing_count,
        missing_rate=float(missing_rate),
        total_rows=int(total_rows),
        min=min_v,
        max=max_v,
        mean=mean_v,
        median=median_v,
        std=std_v,
        q1=q1_v,
        q3=q3_v,
        iqr=iqr_v,
        zero_count=zero_count,
        negative_count=negative_count,
        skewness=skew_v,
        percentiles=pctiles,
    )


def summarise_distribution_dataframe(
    series_dict: dict[str, pd.Series],
    *,
    percentiles: Iterable[float] = DEFAULT_PERCENTILES,
    total_rows: int | None = None,
) -> pd.DataFrame:
    """Build a per-column distribution table for a set of Series.

    Parameters
    ----------
    series_dict : dict[str, pandas.Series]
        Mapping ``column_name → Series``. The keys are used as the
        profile ``column`` field.
    percentiles : iterable of float
        Percentiles passed to each profile.
    total_rows : int, optional
        Shared denominator for missing-rate computation. Defaults to
        the length of the longest Series (or ``len(series)`` per call
        if the dict has one entry).

    Returns
    -------
    pandas.DataFrame
        One row per input Series, with the columns defined in
        :class:`DistributionProfile.to_dict`.
    """
    records: list[dict[str, Any]] = []
    for name, s in series_dict.items():
        prof = distribution_profile(
            s,
            column=name,
            percentiles=percentiles,
            total_rows=total_rows,
        )
        records.append(prof.to_dict())
    return pd.DataFrame.from_records(records)
