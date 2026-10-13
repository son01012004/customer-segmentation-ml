"""Per-segment feature profile computation for DEV-06.

This module computes:

- :func:`compute_segment_sizes` — count per segment_id.
- :func:`compute_segment_percentages` — percentage per segment_id,
  with explicit ``percentage_base`` (per OQ-SEG-DENOM-01).
- :func:`detect_feature_type` — feature type detection
  (numerical / categorical / text_or_id / unknown).
- :func:`compute_feature_profiles` — per-segment feature profile
  (numerical stats + categorical top-K).
- :func:`format_profiles_csv_rows` — long-format CSV rows for
  ``segment_profiles.csv``.

Per OQ-SEG-PROFILE-01:
- Default scope is ``L1.feature_set`` (from the clustering manifest).
- Values are post-preprocessing (scaled / transformed), NOT original
  business units. A warning is emitted at compute time.
- The function NEVER accesses forbidden research artefacts; it only
  reads the DEV-04 cluster_labels parquet + the DEV-03 ML Dataset.

Per OQ-SEG-NOISE-01:
- DBSCAN noise (``ClusterLabel = -1``) is excluded by default from
  the non-noise profile compute.
- ``exclude_noise=False`` keeps the noise row but flags it via
  ``is_noise=True`` in the output.

Per OQ-SEG-DISPLAY-01:
- Categorical top-K default = 10; tie-break = count DESC, name ASC.
- ``other_count`` for omitted categories.
- ``missing_count`` for NaN/missing.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

import numpy as np
import pandas as pd

from customer_segmentation.prototype.segmentation.manifest import FeatureProfile

__all__ = [
    "FeatureType",
    "ProfileComputeError",
    "PROFILE_FEATURE_TYPES",
    "compute_segment_sizes",
    "compute_segment_percentages",
    "detect_feature_type",
    "compute_feature_profiles",
    "format_profiles_csv_rows",
    "ALLOWED_PERCENTAGE_BASES",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_PERCENTAGE_BASES: Final[frozenset[str]] = frozenset(
    {"n_samples_input", "n_samples_used_for_compute"}
)

# Reserved column name that must never be profiled.
CUSTOMER_ID_COLUMN_CANDIDATES: Final[frozenset[str]] = frozenset(
    {"CustomerID", "customer_id", "Customer Id", "Customer_Id", "customerId"}
)

DBSCAN_NOISE_LABEL: Final[int] = -1


class FeatureType(Enum):
    """Per-feature type detection result."""

    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    TEXT_OR_ID = "text_or_id"
    UNKNOWN = "unknown"


PROFILE_FEATURE_TYPES: Final[frozenset[str]] = frozenset(t.value for t in FeatureType)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProfileComputeError(ValueError):
    """Raised on profile computation failure."""


# ---------------------------------------------------------------------------
# Segment size
# ---------------------------------------------------------------------------


def compute_segment_sizes(cluster_labels: pd.DataFrame) -> dict[int, int]:
    """Return ``{segment_id: count}`` for all unique ``ClusterLabel`` values.

    Includes noise label ``-1`` if present. Preserves the segment order
    observed in the data (ascending first-occurrence).
    """
    if "ClusterLabel" not in cluster_labels.columns:
        raise ValueError("cluster_labels must contain 'ClusterLabel' column.")
    labels = cluster_labels["ClusterLabel"]
    sizes: dict[int, int] = {}
    # Use value_counts for performance; preserve order of first appearance
    # by iterating in the data order.
    seen: set[int] = set()
    for lbl in labels:
        lbl_int = int(lbl)
        if lbl_int not in seen:
            sizes[lbl_int] = 0
            seen.add(lbl_int)
        sizes[lbl_int] += 1
    return sizes


# ---------------------------------------------------------------------------
# Segment percentage
# ---------------------------------------------------------------------------


def compute_segment_percentages(
    sizes: dict[int, int],
    *,
    n_samples_input: int,
    n_samples_used_for_compute: int | None = None,
    percentage_base: str = "n_samples_input",
    decimals: int = 2,
) -> dict[int, float]:
    """Return ``{segment_id: percentage}`` under the chosen base.

    Per OQ-SEG-DENOM-01:
    - ``percentage_base='n_samples_input'``: denominator is total input
      rows (includes noise if any).
    - ``percentage_base='n_samples_used_for_compute'``: denominator is
      non-noise rows (= n_samples_input - noise_count). For
      non-density algorithms, n_samples_used_for_compute equals
      n_samples_input; the caller is responsible for setting it
      correctly. The DBSCAN noise segment (``-1``) is reported as 0.0
      under this base (it is excluded from the denominator — its
      "non-noise percentage" is not applicable).
    - Zero denominator ⇒ 0.0 (no division by zero).
    - Rounding: ``decimals`` decimal places (default 2).
    """
    if percentage_base not in ALLOWED_PERCENTAGE_BASES:
        raise ValueError(
            f"percentage_base MUST be one of {sorted(ALLOWED_PERCENTAGE_BASES)}; "
            f"got {percentage_base!r}."
        )
    if n_samples_input <= 0:
        # Empty input: all percentages are 0.
        return dict.fromkeys(sizes, 0.0)
    if percentage_base == "n_samples_input":
        denom = n_samples_input
    else:
        if n_samples_used_for_compute is None:
            raise ValueError(
                "n_samples_used_for_compute MUST be provided when "
                "percentage_base='n_samples_used_for_compute'."
            )
        if n_samples_used_for_compute <= 0:
            return dict.fromkeys(sizes, 0.0)
        denom = n_samples_used_for_compute
    out: dict[int, float] = {}
    for seg_id, count in sizes.items():
        if count < 0:
            raise ValueError(f"size for segment {seg_id!r} is negative: {count!r}.")
        # Noise segment under n_samples_used_for_compute base is 0
        # (denominator excludes noise).
        if seg_id == DBSCAN_NOISE_LABEL and percentage_base != "n_samples_input":
            out[seg_id] = 0.0
            continue
        out[seg_id] = round(count / denom * 100.0, decimals)
    return out


# ---------------------------------------------------------------------------
# Feature type detection
# ---------------------------------------------------------------------------


def detect_feature_type(series: pd.Series, *, uniqueness_threshold: int) -> FeatureType:
    """Detect the type of a feature column.

    Rules (mirror DEV-03 §7.1):
    - ``int64`` / ``float64`` → NUMERICAL.
    - ``bool`` → CATEGORICAL.
    - ``category`` / ``object``:
      - If unique count <= ``uniqueness_threshold`` → CATEGORICAL.
      - Else → TEXT_OR_ID (skipped from profile).
    - Empty / all-NaN → UNKNOWN.
    """
    if series is None or len(series) == 0:
        return FeatureType.UNKNOWN
    s = series.dropna()
    if len(s) == 0:
        return FeatureType.UNKNOWN
    if pd.api.types.is_bool_dtype(series):
        return FeatureType.CATEGORICAL
    if pd.api.types.is_numeric_dtype(series):
        return FeatureType.NUMERICAL
    # Object / category / string.
    nunique = s.nunique(dropna=True)
    if nunique <= uniqueness_threshold:
        return FeatureType.CATEGORICAL
    return FeatureType.TEXT_OR_ID


# ---------------------------------------------------------------------------
# Feature profile compute
# ---------------------------------------------------------------------------


def _select_segment(
    cluster_labels: pd.DataFrame,
    ml_dataset: pd.DataFrame,
) -> pd.DataFrame:
    """Align cluster_labels and ml_dataset on CustomerID or row index.

    Returns a DataFrame whose columns are the union of cluster_labels and
    ml_dataset, aligned by CustomerID if present, else by row index.
    """
    if "CustomerID" in cluster_labels.columns and "CustomerID" in ml_dataset.columns:
        # Merge on CustomerID (left = ml_dataset for feature lookup).
        merged = ml_dataset.merge(
            cluster_labels[["CustomerID", "ClusterLabel", "IsNoise"]],
            on="CustomerID",
            how="inner",
            suffixes=("", "_cl"),
        )
        return merged
    # Fall back to row index (no CustomerID alignment).
    n = min(len(cluster_labels), len(ml_dataset))
    return pd.concat(
        [
            ml_dataset.iloc[:n].reset_index(drop=True),
            cluster_labels[["ClusterLabel", "IsNoise"]].iloc[:n].reset_index(drop=True),
        ],
        axis=1,
    )


def _compute_numerical_stats(
    s: pd.Series,
    statistics: Iterable[str],
) -> dict[str, Any]:
    """Compute numerical descriptive statistics for a pandas Series.

    Uses ``.quantile()`` directly for each percentile (avoids pandas'
    ``describe()`` returning ``25%``/``50%``/``75%`` labels which vary
    across versions).
    """
    s_clean = s.dropna()
    if len(s_clean) == 0:
        return dict.fromkeys(statistics)
    out: dict[str, Any] = {}
    if "mean" in statistics:
        out["mean"] = float(s_clean.mean())
    if "median" in statistics:
        out["median"] = float(s_clean.quantile(0.5))
    if "std" in statistics:
        out["std"] = float(s_clean.std())
    if "q1" in statistics:
        out["q1"] = float(s_clean.quantile(0.25))
    if "q3" in statistics:
        out["q3"] = float(s_clean.quantile(0.75))
    if "min" in statistics:
        out["min"] = float(s_clean.min())
    if "max" in statistics:
        out["max"] = float(s_clean.max())
    return out


def _compute_categorical_stats(
    s: pd.Series,
    *,
    topk: int,
) -> dict[str, Any]:
    """Compute categorical top-K + other_count + missing_count.

    Per OQ-SEG-DISPLAY-01:
    - tie-break: count DESC, then name ASC
    - topk: configurable (default 10)
    - other_count: sum of counts for categories not in topk
    - missing_count: NaN count
    """
    missing_count = int(s.isna().sum())
    s_clean = s.dropna()
    total_count = len(s_clean)
    if total_count == 0:
        return {
            "topk_categories": [],
            "value_counts": {},
            "other_count": 0,
            "missing_count": missing_count,
        }
    counts = s_clean.value_counts()
    # Tie-break: count DESC, then name ASC.
    sorted_items = sorted(
        counts.items(),
        key=lambda kv: (-int(kv[1]), str(kv[0])),
    )
    topk_items = sorted_items[:topk]
    other_count = total_count - sum(int(c) for _, c in topk_items)
    # Normalise keys to str for JSON-friendliness.
    topk_serialised = [(str(k), int(c)) for k, c in topk_items]
    value_counts = {str(k): int(c) for k, c in sorted_items}
    return {
        "topk_categories": topk_serialised,
        "value_counts": value_counts,
        "other_count": int(other_count),
        "missing_count": missing_count,
    }


def compute_feature_profiles(
    *,
    ml_dataset: pd.DataFrame,
    cluster_labels: pd.DataFrame,
    feature_set: list[str],
    statistics: Iterable[str] = ("mean", "median", "std", "q1", "q3", "min", "max"),
    categorical_topk: int = 10,
    uniqueness_threshold: int = 50,
    exclude_noise: bool = True,
) -> list[FeatureProfile]:
    """Compute per-segment feature profiles.

    Per OQ-SEG-PROFILE-01 + R-DEV-06-23:
    - Emits a ``UserWarning`` about post-preprocessing values (scaled /
      transformed) at compute time.
    - Default scope is the supplied ``feature_set`` (typically
      ``L1.feature_set``).
    - ``CustomerID`` is NEVER included in the profile, even if requested.

    Per OQ-SEG-NOISE-01 + R-DEV-06-22:
    - DBSCAN noise (``ClusterLabel == -1``) is excluded from segment
      profiles by default.
    - ``exclude_noise=False`` keeps the noise row.

    Returns
    -------
    list[FeatureProfile]
        One entry per (segment_id × feature_name). Empty if no
        non-noise segments exist.
    """
    if not isinstance(feature_set, list):
        raise ValueError("feature_set must be a list.")
    # Strip CustomerID (R-DEV-06-15 CustomerID leak defence).
    feature_set_filtered = [f for f in feature_set if f not in CUSTOMER_ID_COLUMN_CANDIDATES]
    if "ClusterLabel" not in cluster_labels.columns:
        raise ValueError("cluster_labels must contain 'ClusterLabel' column.")
    # Validate feature_set against actual dataset columns.
    missing_cols = [f for f in feature_set_filtered if f not in ml_dataset.columns]
    if missing_cols:
        raise ValueError(
            f"Features {missing_cols!r} not found in dataset columns "
            f"{list(ml_dataset.columns)!r}."
        )

    # Emit post-preprocessing warning (R-DEV-06-23).
    warnings.warn(
        "DEV-06 feature profile values are post-preprocessing (scaled / "
        "transformed) — values may NOT be directly interpretable in original "
        "business units. See docs/system/DEV-06_customer_segment_module.md §7.",
        UserWarning,
        stacklevel=2,
    )

    # Align cluster_labels and ml_dataset.
    aligned = _select_segment(cluster_labels, ml_dataset)

    # Optionally exclude noise.
    if exclude_noise:
        aligned = aligned[aligned["ClusterLabel"] != DBSCAN_NOISE_LABEL]

    profiles: list[FeatureProfile] = []
    for feature_name in feature_set_filtered:
        s = aligned[feature_name]
        ft = detect_feature_type(s, uniqueness_threshold=uniqueness_threshold)
        if ft == FeatureType.TEXT_OR_ID:
            # Skip with no profile.
            continue
        if ft == FeatureType.UNKNOWN:
            # Skip empty/all-NaN columns.
            continue
        for seg_id, group in aligned.groupby("ClusterLabel", sort=True):
            seg_id = int(seg_id)
            if exclude_noise and seg_id == DBSCAN_NOISE_LABEL:
                continue
            seg_series = group[feature_name]
            if ft == FeatureType.NUMERICAL:
                stats = _compute_numerical_stats(seg_series, statistics)
            else:
                stats = _compute_categorical_stats(seg_series, topk=categorical_topk)
            profiles.append(
                FeatureProfile(
                    segment_id=seg_id,
                    feature_name=feature_name,
                    statistics=stats,
                )
            )
    return profiles


# ---------------------------------------------------------------------------
# CSV formatting
# ---------------------------------------------------------------------------


def format_profiles_csv_rows(profiles: list[FeatureProfile]) -> list[dict[str, Any]]:
    """Return long-format rows for ``segment_profiles.csv``.

    Each row has the keys: ``segment_id``, ``feature_name``, ``statistic``,
    ``value``, ``value_str``, ``is_diagnostic_only``.
    """
    rows: list[dict[str, Any]] = []
    for p in profiles:
        for stat_name, stat_value in p.statistics.items():
            value: Any = stat_value
            value_str: str
            if isinstance(value, float):
                # NaN handling.
                value_str = "" if np.isnan(value) else repr(value)
            elif isinstance(value, list):
                # Categorical topk: serialise as "cat1:count1|cat2:count2|..."
                value_str = "|".join(f"{cat}:{count}" for cat, count in value)
                # value is a string for CSV.
                value = value_str
            elif isinstance(value, dict):
                # value_counts: serialise as "cat1:c1;cat2:c2;..."
                value_str = ";".join(f"{k}:{v}" for k, v in value.items())
                value = value_str
            elif value is None:
                value_str = ""
            else:
                value_str = str(value)
            rows.append(
                {
                    "segment_id": p.segment_id,
                    "feature_name": p.feature_name,
                    "statistic": stat_name,
                    "value": value,
                    "value_str": value_str,
                    "is_diagnostic_only": False,
                }
            )
    return rows
