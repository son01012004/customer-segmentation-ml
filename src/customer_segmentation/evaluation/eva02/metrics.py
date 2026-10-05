"""Internal metric helpers for EVA-02.

This module provides:

- A canonical list of metric names and their "direction" (higher is
  better vs lower is better).
- Helpers to extract metric vectors from the EVA-01 DataFrame with
  NaN / MISSING filtering.
- Per-metric summary statistics that are reused by the comparison,
  quality, and visualization layers.

Hard constraints (AGENTS.md §2):

- No ranking, no "best/winner/optimal/recommended/final" labels.
- No synthetic metric values.
- NaN values are returned as ``NaN``, not filled with placeholders.

Direction convention
---------------------

``silhouette`` and ``calinski_harabasz`` are "higher is better".
``davies_bouldin`` and ``wcss`` are "lower is better". The
``METRIC_DIRECTIONS`` mapping is the single source of truth.
"""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.experiment_results.schema import MISSING

__all__ = [
    "METRIC_COLUMNS",
    "METRIC_DIRECTIONS",
    "HIGHER_IS_BETTER",
    "LOWER_IS_BETTER",
    "RUNTIME_COLUMN",
    "NOISE_METRIC_COLUMNS",
    "extract_metric_vector",
    "filter_metric_rows",
    "summarise_metric",
    "summarise_metrics_long",
]


# Canonical metric columns used by EVA-02. WCSS is kept as a
# diagnostic-only metric (per AGENTS.md / methodology) and is still
# included so the user can review it, but it is NOT used in any
# ranking.
METRIC_COLUMNS: tuple[str, ...] = (
    "silhouette",
    "davies_bouldin",
    "calinski_harabasz",
    "wcss",
)


# Direction convention: ``HIGHER_IS_BETTER`` / ``LOWER_IS_BETTER``.
HIGHER_IS_BETTER: str = "higher_is_better"
LOWER_IS_BETTER: str = "lower_is_better"


METRIC_DIRECTIONS: dict[str, str] = {
    "silhouette": HIGHER_IS_BETTER,
    "davies_bouldin": LOWER_IS_BETTER,
    "calinski_harabasz": HIGHER_IS_BETTER,
    "wcss": LOWER_IS_BETTER,
}


RUNTIME_COLUMN: str = "execution_time_seconds"


# Noise-related metrics — DBSCAN's noise points are excluded from
# silhouette / DBI / CH computation in the source; we still surface
# ``noise_count`` and ``noise_ratio`` as separate dimensions.
NOISE_METRIC_COLUMNS: tuple[str, ...] = (
    "noise_count",
    "noise_ratio",
    "n_clusters_realized",
)


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _to_float(value: object) -> float:
    """Convert a metric cell to float; ``NaN`` for missing / sentinel."""
    if value is None:
        return math.nan
    if isinstance(value, str) and value == MISSING:
        return math.nan
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return math.nan
    if math.isnan(f) or math.isinf(f):
        return math.nan
    return f


def extract_metric_vector(
    df: pd.DataFrame,
    column: str,
) -> np.ndarray:
    """Return a 1D float array of the requested metric, with NaN for missing.

    Parameters
    ----------
    df : pandas.DataFrame
        Standardised EVA-01 repository.
    column : str
        Metric column name (e.g. ``"silhouette"``).

    Returns
    -------
    numpy.ndarray
        Float array; NaN where the source had no value.
    """
    if column not in df.columns:
        raise KeyError(f"column {column!r} not found in repository")
    return df[column].apply(_to_float).to_numpy()


def filter_metric_rows(
    df: pd.DataFrame,
    *,
    require: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Return rows that have a non-NaN value for every required metric.

    Parameters
    ----------
    df : pandas.DataFrame
        Standardised EVA-01 repository.
    require : iterable of str, default ``METRIC_COLUMNS``
        Metric columns that must be present (non-NaN) for a row to
        be included.

    Returns
    -------
    pandas.DataFrame
        Subset of ``df`` where all required metrics are non-NaN.

    Notes
    -----
    This filter is intentionally strict: a row missing any of the
    primary metrics is excluded. EVA-01 marks DBSCAN's metrics as
    ``VALID_VALUE`` even though they are computed on a noise-free
    subset, so DBSCAN rows are NOT excluded by this filter.
    """
    mask = pd.Series(True, index=df.index)
    for col in require:
        if col not in df.columns:
            return df.iloc[0:0]  # empty DataFrame
        mask &= df[col].apply(_to_float).notna()
    return df.loc[mask].copy()


# ---------------------------------------------------------------------------
# Per-metric summary statistics
# ---------------------------------------------------------------------------


def summarise_metric(values: Iterable[float]) -> dict[str, float]:
    """Compute n / min / max / mean / std for an iterable of metric values.

    NaN entries are dropped. Returns ``n=0`` and NaN statistics if
    the input is empty after filtering.
    """
    cleaned: list[float] = []
    for v in values:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(f) or math.isinf(f):
            continue
        cleaned.append(f)
    if not cleaned:
        return {
            "n": 0,
            "min": math.nan,
            "max": math.nan,
            "mean": math.nan,
            "std": math.nan,
        }
    arr = np.asarray(cleaned, dtype=float)
    return {
        "n": int(arr.size),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
        "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
    }


def summarise_metrics_long(
    df: pd.DataFrame,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Return a long-format per-metric summary table.

    One row per (metric, source_experiment) combination. Useful for
    cross-experiment metric-by-metric inspection.
    """
    rows: list[dict[str, object]] = []
    for source_exp, group in df.groupby("source_experiment", dropna=False):
        for metric in metrics:
            if metric not in group.columns:
                continue
            stats = summarise_metric(extract_metric_vector(group, metric))
            rows.append(
                {
                    "source_experiment": source_exp,
                    "metric": metric,
                    "direction": METRIC_DIRECTIONS.get(metric, ""),
                    "n": stats["n"],
                    "min": stats["min"],
                    "max": stats["max"],
                    "mean": stats["mean"],
                    "std": stats["std"],
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["source_experiment", "metric"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Cross-metric conflict detection
# ---------------------------------------------------------------------------


def metric_conflicts(
    df: pd.DataFrame,
    *,
    primary: str = "silhouette",
    secondary: str = "davies_bouldin",
    tertiary: str = "calinski_harabasz",
) -> pd.DataFrame:
    """Identify rows where the primary metric disagrees with the others.

    For each row the function looks at the *rank* of the row within
    its group (default: per algorithm at fixed K). A "conflict" is
    a row whose primary rank differs from its secondary / tertiary
    rank by more than ``rank_tolerance`` positions.

    The output table is intended for qualitative review, not as a
    claim about cluster quality.

    Parameters
    ----------
    df : pandas.DataFrame
        Standardised repository. Should be pre-filtered with
        :func:`filter_metric_rows`.
    primary, secondary, tertiary : str
        Metric columns to compare.

    Notes
    -----
    This helper is exported for completeness; the main EVA-02 entry
    point uses :func:`customer_segmentation.evaluation.eva02.quality.cross_metric_conflicts`
    which adds the rank-tolerance flag.
    """
    if not {primary, secondary, tertiary}.issubset(df.columns):
        missing = {primary, secondary, tertiary} - set(df.columns)
        raise KeyError(f"missing metric columns: {missing}")

    work = df.copy()
    group_cols = ["source_experiment", "algorithm", "n_clusters"]

    def _rank(sub_df: pd.DataFrame, col: str) -> pd.Series:
        direction = METRIC_DIRECTIONS.get(col, HIGHER_IS_BETTER)
        ascending = direction == LOWER_IS_BETTER
        return sub_df[col].rank(method="min", ascending=ascending)

    ranks: dict[str, pd.Series] = {}
    for col in (primary, secondary, tertiary):
        grouped = work.groupby(group_cols, dropna=False)[col]
        ranks[col] = grouped.transform(
            lambda s, c=col: s.rank(
                method="min",
                ascending=(METRIC_DIRECTIONS.get(c, HIGHER_IS_BETTER) == LOWER_IS_BETTER),
            )
        )

    work = work.assign(
        rank_primary=ranks[primary],
        rank_secondary=ranks[secondary],
        rank_tertiary=ranks[tertiary],
    )
    # Signed-integer subtraction avoids UInt64 underflow when the
    # primary rank is *smaller* than the secondary / tertiary rank.
    left = work["rank_primary"].astype("Int64")
    sec = work["rank_secondary"].astype("Int64")
    ter = work["rank_tertiary"].astype("Int64")
    work["abs_diff_primary_secondary"] = (left - sec).abs().astype("Float64")
    work["abs_diff_primary_tertiary"] = (left - ter).abs().astype("Float64")

    keep_cols = [
        "source_experiment",
        "experiment_id",
        "algorithm",
        "n_clusters",
        primary,
        secondary,
        tertiary,
        "rank_primary",
        "rank_secondary",
        "rank_tertiary",
        "abs_diff_primary_secondary",
        "abs_diff_primary_tertiary",
    ]
    return work.loc[:, keep_cols].sort_values(
        ["source_experiment", "algorithm", "n_clusters"]
    ).reset_index(drop=True)
