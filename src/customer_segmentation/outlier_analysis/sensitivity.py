"""FE-03 outlier analysis: sensitivity analysis across thresholds.

Sweeps the IQR multiplier and the upper-percentile threshold and
records how the candidate count changes. Used by the report to
illustrate how sensitive the outlier count is to the chosen threshold.

Hard rules (from AGENTS.md):
- All thresholds come from the YAML config (via the orchestrator).
- This module is purely diagnostic. It never mutates input or applies
  treatment.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from customer_segmentation.config.outlier_loader import (
    SensitivityConfig,
)
from customer_segmentation.outlier_analysis.detection import (
    iqr_mask,
    percentile_mask,
    zscore_mask,
)

__all__ = [
    "sensitivity_table",
    "sensitivity_summary_table",
    "iqr_sensitivity",
    "percentile_sensitivity",
    "zscore_sensitivity",
]


# ---------------------------------------------------------------------------
# Single-axis sweeps
# ---------------------------------------------------------------------------


def iqr_sensitivity(
    series: pd.Series,
    multipliers: Iterable[float] = (1.5, 3.0),
) -> pd.DataFrame:
    """Run IQR detection with several multipliers and summarise.

    Parameters
    ----------
    series : pandas.Series
        Numeric Series.
    multipliers : iterable of float
        IQR multipliers to sweep.

    Returns
    -------
    pandas.DataFrame
        Columns ``multiplier``, ``lower``, ``upper``, ``candidates``,
        ``rate``, ``total_rows``.
    """
    total_rows = int(len(series))
    rows: list[dict[str, Any]] = []
    for k in multipliers:
        mask, lo, hi = iqr_mask(series, multiplier=float(k))
        rows.append(
            {
                "multiplier": float(k),
                "lower": float(lo),
                "upper": float(hi),
                "candidates": int(mask.sum()),
                "rate": float(mask.sum()) / max(total_rows, 1),
                "total_rows": total_rows,
            }
        )
    return pd.DataFrame.from_records(rows)


def percentile_sensitivity(
    series: pd.Series,
    percentiles: Iterable[float] = (99.0, 99.5, 99.9),
) -> pd.DataFrame:
    """Run percentile detection at several thresholds and summarise."""
    total_rows = int(len(series))
    rows: list[dict[str, Any]] = []
    for p in percentiles:
        mask, lo, hi = percentile_mask(series, upper_percentile=float(p))
        rows.append(
            {
                "percentile": float(p),
                "lower": float(lo),
                "upper": float(hi),
                "candidates": int(mask.sum()),
                "rate": float(mask.sum()) / max(total_rows, 1),
                "total_rows": total_rows,
            }
        )
    return pd.DataFrame.from_records(rows)


def zscore_sensitivity(
    series: pd.Series,
    thresholds: Iterable[float] = (3.0,),
) -> pd.DataFrame:
    """Run z-score detection at several thresholds and summarise.

    Note
    ----
    The default threshold list is just ``(3.0,)`` because sweeping
    z-score thresholds on heavy-tailed data produces noisy results;
    we surface this explicitly in the report.
    """
    total_rows = int(len(series))
    rows: list[dict[str, Any]] = []
    for t in thresholds:
        mask, lo, hi = zscore_mask(series, threshold=float(t))
        rows.append(
            {
                "zscore_threshold": float(t),
                "lower": float(lo),
                "upper": float(hi),
                "candidates": int(mask.sum()),
                "rate": float(mask.sum()) / max(total_rows, 1),
                "total_rows": total_rows,
            }
        )
    return pd.DataFrame.from_records(rows)


# ---------------------------------------------------------------------------
# Combined sensitivity table for one (feature, filter_mode) pair
# ---------------------------------------------------------------------------


def sensitivity_table(
    series: pd.Series,
    feature_name: str,
    *,
    filter_mode: str = "all_rows",
    config: SensitivityConfig | None = None,
) -> pd.DataFrame:
    """Build a combined sensitivity table for one feature.

    Parameters
    ----------
    series : pandas.Series
        Numeric Series (already filtered by the caller).
    feature_name : str
        Logical feature name.
    filter_mode : str, default "all_rows"
        Filter mode the caller applied.
    config : SensitivityConfig, optional
        Sensitivity configuration. ``None`` uses the dataclass
        defaults.

    Returns
    -------
    pandas.DataFrame
        One row per (method, threshold) pair. Columns include
        ``feature``, ``filter_mode``, ``method``, ``threshold``,
        ``lower``, ``upper``, ``candidates``, ``rate``, ``total_rows``.
    """
    if config is None:
        config = SensitivityConfig()

    total_rows = int(len(series))
    rows: list[dict[str, Any]] = []

    for k in config.thresholds:
        mask, lo, hi = iqr_mask(series, multiplier=float(k))
        rows.append(
            {
                "feature": feature_name,
                "filter_mode": filter_mode,
                "method": "iqr",
                "threshold": float(k),
                "lower": float(lo),
                "upper": float(hi),
                "candidates": int(mask.sum()),
                "rate": float(mask.sum()) / max(total_rows, 1),
                "total_rows": total_rows,
            }
        )

    for p in config.percentiles:
        mask, lo, hi = percentile_mask(series, upper_percentile=float(p))
        rows.append(
            {
                "feature": feature_name,
                "filter_mode": filter_mode,
                "method": "percentile",
                "threshold": float(p),
                "lower": float(lo),
                "upper": float(hi),
                "candidates": int(mask.sum()),
                "rate": float(mask.sum()) / max(total_rows, 1),
                "total_rows": total_rows,
            }
        )

    if not config.enabled:
        return pd.DataFrame.from_records(rows)

    # Z-score diagnostic only — sweep one threshold (default 3.0) so
    # the report can show how heavy-tailed data interacts with the
    # parametric assumption.
    for t in (3.0,):
        mask, lo, hi = zscore_mask(series, threshold=float(t))
        rows.append(
            {
                "feature": feature_name,
                "filter_mode": filter_mode,
                "method": "zscore",
                "threshold": float(t),
                "lower": float(lo),
                "upper": float(hi),
                "candidates": int(mask.sum()),
                "rate": float(mask.sum()) / max(total_rows, 1),
                "total_rows": total_rows,
            }
        )

    return pd.DataFrame.from_records(rows)


# ---------------------------------------------------------------------------
# Convenience: aggregate across features
# ---------------------------------------------------------------------------


def sensitivity_summary_table(
    tables: Iterable[pd.DataFrame],
) -> pd.DataFrame:
    """Concatenate multiple sensitivity tables into one summary.

    Parameters
    ----------
    tables : iterable of pandas.DataFrame
        One per (feature, filter_mode) pair.

    Returns
    -------
    pandas.DataFrame
        Concatenated table, sorted for deterministic output.
    """
    chunks = [t for t in tables if not t.empty]
    if not chunks:
        return pd.DataFrame(
            columns=[
                "feature",
                "filter_mode",
                "method",
                "threshold",
                "lower",
                "upper",
                "candidates",
                "rate",
                "total_rows",
            ]
        )
    out = pd.concat(chunks, ignore_index=True, sort=False)
    return out.sort_values(["feature", "filter_mode", "method", "threshold"]).reset_index(drop=True)
