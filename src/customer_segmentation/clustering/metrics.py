"""Evaluation metrics layer for EXP-01.

This module provides the unified evaluation layer for the EXP-01 baseline
experiment. It computes internal clustering metrics (silhouette, Davies-Bouldin,
Calinski-Harabasz, WCSS) and attaches them to :class:`ClusterResult` with
clear applicability status.

EXP-01 is a baseline measurement task. This module does NOT:
- Rank algorithms or declare winners.
- Use metrics to select "best" configuration.
- Compute stability metrics (ARI/AMI — EPIC-08 scope).

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No "best/recommended/optimal/winner" language.
- Metrics are computed but never used for algorithm selection.
- WCSS uses arithmetic centroid from hard labels, not GMM Gaussian means
  or FCM fuzzy centroids.
- DBSCAN noise (label -1) is excluded from all metrics.

Metric applicability status
--------------------------

Each metric has a status attached to distinguish between:
- VALID_VALUE: metric computed successfully.
- NOT_APPLICABLE: metric not applicable (e.g., single cluster).
- COMPUTATION_ERROR: sklearn raised an exception.
- MISSING: placeholder (should not remain after successful EXP-01 run).

References
----------

- Silhouette: Rousseeuw (1987), J. Comput. Appl. Math.
- Davies-Bouldin: Davies & Bouldin (1979), IEEE Trans. Pattern Anal.
- Calinski-Harabasz: Calinski & Harabasz (1974), Commun. Stat.
- WCSS: standard within-cluster sum of squares definition.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

import numpy as np

from customer_segmentation.clustering.result import ClusterResult, MetricsResult

__all__ = [
    "METRIC_VALID",
    "METRIC_NOT_APPLICABLE",
    "METRIC_COMPUTATION_ERROR",
    "METRIC_MISSING",
    "REASON_ALL_NOISE",
    "REASON_SINGLE_CLUSTER",
    "REASON_INSUFFICIENT_CLUSTERS",
    "compute_internal_metrics",
    "compute_wcss",
    "compute_runtime_stats",
    "attach_metrics_with_status",
]


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

METRIC_VALID = "VALID_VALUE"
METRIC_NOT_APPLICABLE = "NOT_APPLICABLE"
METRIC_COMPUTATION_ERROR = "COMPUTATION_ERROR"
METRIC_MISSING = "MISSING"

# Reason codes for NOT_APPLICABLE status
REASON_ALL_NOISE = "ALL_NOISE"
REASON_SINGLE_CLUSTER = "SINGLE_CLUSTER"
REASON_INSUFFICIENT_CLUSTERS = "INSUFFICIENT_CLUSTERS"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _non_noise_mask(labels: np.ndarray, noise_label: int = -1) -> np.ndarray:
    """Return boolean mask for non-noise points."""
    return labels != noise_label


def _valid_clusters_mask(
    labels: np.ndarray, noise_label: int = -1, exclude_noise: bool = True
) -> tuple[np.ndarray, np.ndarray, int]:
    """Return (mask, unique_labels, n_unique) for non-noise clusters.

    For DBSCAN, the noise label -1 is excluded. For other algorithms,
    noise_label=-1 but there are no actual noise points.

    Returns
    -------
    mask : ndarray
        Boolean mask for points to include in metrics.
    unique_labels : ndarray
        Unique cluster labels (excluding noise if exclude_noise=True).
    n_unique : int
        Number of unique clusters.
    """
    if exclude_noise:
        mask = _non_noise_mask(labels, noise_label)
    else:
        mask = np.ones(len(labels), dtype=bool)

    subset = labels[mask]
    unique_labels = np.unique(subset)
    n_unique = len(unique_labels)
    return mask, unique_labels, n_unique


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_internal_metrics(
    X: np.ndarray,
    labels: np.ndarray,
    *,
    noise_label: int = -1,
    exclude_noise: bool = True,
) -> tuple[
    dict[str, float | None],  # values
    dict[str, str],  # status per metric
    dict[str, str | None],  # reason per metric (None if VALID)
    float,  # computation_time_seconds
]:
    """Compute silhouette, DBI, CH with noise handling + status.

    Parameters
    ----------
    X : ndarray
        Feature matrix of shape (n_samples, n_features).
    labels : ndarray
        Cluster labels of shape (n_samples,).
    noise_label : int
        Label value for noise points (default -1, sklearn convention).
    exclude_noise : bool
        If True, exclude noise points from metric computation.

    Returns
    -------
    values : dict
        Metric values: {"silhouette": float|None, "davies_bouldin": float|None,
        "calinski_harabasz": float|None}.
    status : dict
        Status per metric: {"silhouette": str, "davies_bouldin": str,
        "calinski_harabasz": str}.
    reason : dict
        Reason per metric (None if status is VALID_VALUE).
    computation_time : float
        Total computation time in seconds.
    """
    from sklearn.metrics import (
        calinski_harabasz_score,
        davies_bouldin_score,
        silhouette_score,
    )

    values: dict[str, float | None] = {}
    status: dict[str, str] = {}
    reason: dict[str, str | None] = {}

    start_time = time.perf_counter()

    # Get valid data subset
    mask, unique_labels, n_unique = _valid_clusters_mask(labels, noise_label, exclude_noise)

    # Edge case: all noise
    if n_unique == 0:
        for metric_name in ("silhouette", "davies_bouldin", "calinski_harabasz"):
            values[metric_name] = None
            status[metric_name] = METRIC_NOT_APPLICABLE
            reason[metric_name] = REASON_ALL_NOISE
        return values, status, reason, time.perf_counter() - start_time

    # Edge case: insufficient clusters
    if n_unique < 2:
        for metric_name in ("silhouette", "davies_bouldin", "calinski_harabasz"):
            values[metric_name] = None
            status[metric_name] = METRIC_NOT_APPLICABLE
            reason[metric_name] = REASON_SINGLE_CLUSTER
        return values, status, reason, time.perf_counter() - start_time

    X_subset = X[mask]
    labels_subset = labels[mask]

    # Compute each metric
    # Silhouette
    try:
        sil = float(silhouette_score(X_subset, labels_subset))
        values["silhouette"] = sil
        status["silhouette"] = METRIC_VALID
        reason["silhouette"] = None
    except Exception as exc:  # noqa: BLE001
        values["silhouette"] = None
        status["silhouette"] = METRIC_COMPUTATION_ERROR
        reason["silhouette"] = f"{type(exc).__name__}: {str(exc)[:100]}"

    # Davies-Bouldin
    try:
        dbi = float(davies_bouldin_score(X_subset, labels_subset))
        values["davies_bouldin"] = dbi
        status["davies_bouldin"] = METRIC_VALID
        reason["davies_bouldin"] = None
    except Exception as exc:  # noqa: BLE001
        values["davies_bouldin"] = None
        status["davies_bouldin"] = METRIC_COMPUTATION_ERROR
        reason["davies_bouldin"] = f"{type(exc).__name__}: {str(exc)[:100]}"

    # Calinski-Harabasz
    try:
        ch = float(calinski_harabasz_score(X_subset, labels_subset))
        values["calinski_harabasz"] = ch
        status["calinski_harabasz"] = METRIC_VALID
        reason["calinski_harabasz"] = None
    except Exception as exc:  # noqa: BLE001
        values["calinski_harabasz"] = None
        status["calinski_harabasz"] = METRIC_COMPUTATION_ERROR
        reason["calinski_harabasz"] = f"{type(exc).__name__}: {str(exc)[:100]}"

    computation_time = time.perf_counter() - start_time
    return values, status, reason, computation_time


def compute_wcss(
    X: np.ndarray,
    labels: np.ndarray,
    *,
    noise_label: int = -1,
    exclude_noise: bool = True,
) -> tuple[float | None, str, str | None]:
    """Compute WCSS using arithmetic centroid from hard labels.

    WCSS = Σ_i ‖x_i - μ_{c_i}‖²

    where μ_c is the arithmetic centroid of cluster c:
        μ_c = (1 / |C_c|) * Σ_{i∈C_c} x_i

    For GMM and FCM, hard labels are derived as argmax of soft outputs.
    GMM Gaussian means and FCM fuzzy centroids are NOT used for WCSS.

    Parameters
    ----------
    X : ndarray
        Feature matrix of shape (n_samples, n_features).
    labels : ndarray
        Cluster labels of shape (n_samples,).
    noise_label : int
        Label value for noise points (default -1).
    exclude_noise : bool
        If True, exclude noise points from WCSS computation.

    Returns
    -------
    wcss : float | None
        WCSS value, or None if not applicable.
    status : str
        Status: VALID_VALUE, NOT_APPLICABLE, or COMPUTATION_ERROR.
    reason : str | None
        Reason if status is not VALID_VALUE.
    """
    # Get valid data subset
    mask, unique_labels, n_unique = _valid_clusters_mask(labels, noise_label, exclude_noise)

    # Edge case: all noise
    if n_unique == 0:
        return None, METRIC_NOT_APPLICABLE, REASON_ALL_NOISE

    X_subset = X[mask]
    labels_subset = labels[mask]

    try:
        total_wcss = 0.0
        for label in unique_labels:
            cluster_mask = labels_subset == label
            cluster_points = X_subset[cluster_mask]
            if len(cluster_points) == 0:
                continue
            centroid = cluster_points.mean(axis=0)
            # Squared distances: sum over features then over points
            sq_dists = np.sum((cluster_points - centroid) ** 2, axis=1)
            total_wcss += float(np.sum(sq_dists))
        return total_wcss, METRIC_VALID, None
    except Exception as exc:  # noqa: BLE001
        return None, METRIC_COMPUTATION_ERROR, f"{type(exc).__name__}: {str(exc)[:100]}"


def compute_runtime_stats(
    raw_times: list[float],
) -> dict[str, Any]:
    """Compute runtime statistics from repeated measurements.

    Parameters
    ----------
    raw_times : list of float
        List of execution times in seconds.

    Returns
    -------
    stats : dict
        Statistics: mean, std, min, max, raw (list).
    """
    if not raw_times:
        return {
            "mean_seconds": None,
            "std_seconds": None,
            "min_seconds": None,
            "max_seconds": None,
            "raw_seconds": [],
        }

    raw = np.array(raw_times, dtype=np.float64)
    return {
        "mean_seconds": float(np.mean(raw)),
        "std_seconds": float(np.std(raw, ddof=1)) if len(raw) > 1 else 0.0,
        "min_seconds": float(np.min(raw)),
        "max_seconds": float(np.max(raw)),
        "raw_seconds": raw.tolist(),
    }


def attach_metrics_with_status(
    cluster_result: ClusterResult,
    X: np.ndarray,
    *,
    exclude_noise: bool = True,
    noise_label: int = -1,
    metric_computation_time: float = 0.0,
    runtime_stats: dict[str, Any] | None = None,
) -> ClusterResult:
    """Populate cluster_result.metrics with values + status + reasons.

    Parameters
    ----------
    cluster_result : ClusterResult
        The clustering result to annotate with metrics.
    X : ndarray
        Feature matrix used for clustering.
    exclude_noise : bool
        If True, exclude noise points from metric computation.
    noise_label : int
        Label value for noise points.
    metric_computation_time : float
        Time spent computing metrics (seconds).
    runtime_stats : dict | None
        Runtime statistics from repetition measurements.

    Returns
    -------
    ClusterResult
        Updated result with populated metrics.
    """
    labels = cluster_result.cluster_labels

    # Compute internal metrics (silhouette, DBI, CH)
    values, status, reason, _ = compute_internal_metrics(
        X, labels, noise_label=noise_label, exclude_noise=exclude_noise
    )

    # Compute WCSS
    wcss_value, wcss_status, wcss_reason = compute_wcss(
        X, labels, noise_label=noise_label, exclude_noise=exclude_noise
    )

    # Build extra dict with status and reason metadata
    extra: dict[str, Any] = {}
    for metric_name in ("silhouette", "davies_bouldin", "calinski_harabasz"):
        extra[f"{metric_name}_status"] = status[metric_name]
        extra[f"{metric_name}_reason"] = reason[metric_name]

    extra["wcss_status"] = wcss_status
    extra["wcss_reason"] = wcss_reason
    extra["metric_computation_time_seconds"] = metric_computation_time

    # Build runtime dict
    if runtime_stats is not None:
        runtime_dict: dict[str, Any] = {
            "algorithm_execution": runtime_stats,
            "metric_computation": {
                "total_seconds": metric_computation_time,
            },
            "note": "Artifact/report writing time excluded.",
        }
    else:
        runtime_dict = {
            "metric_computation": {
                "total_seconds": metric_computation_time,
            },
            "note": "Artifact/report writing time excluded.",
        }

    # Create updated MetricsResult
    new_metrics = MetricsResult(
        silhouette=values["silhouette"],
        davies_bouldin=values["davies_bouldin"],
        calinski_harabasz=values["calinski_harabasz"],
        wcss=wcss_value,
        runtime=runtime_dict,
        extra=extra,
    )

    # Replace metrics in cluster_result
    return replace(cluster_result, metrics=new_metrics)
