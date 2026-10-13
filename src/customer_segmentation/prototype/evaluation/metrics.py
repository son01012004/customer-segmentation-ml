"""Metric compute primitive for DEV-05.

Wraps three ``sklearn.metrics`` functions:

- ``silhouette_score`` (sklearn convention: noise=-1 excluded)
- ``davies_bouldin_score`` (sklearn default: includes -1 as cluster)
- ``calinski_harabasz_score`` (sklearn default: includes -1 as cluster)

Per ADR-0006 (Accepted 2026-10-09) and DEV-05 plan §5.4, the
**prototype layer** applies a **uniform DBSCAN-noise exclusion policy**
to all three metrics when:

- ``algorithm_family == "density_based"`` (i.e. clustering run used DBSCAN)
- ``noise_policy == "exclude"`` (default per ADR-0006)

The filter is **in-memory only**: rows where ``ClusterLabel == noise_label``
(default ``-1``) are removed from a copy of X and labels **before** being
passed to sklearn. The original ``cluster_labels_*.parquet`` and the
upstream DEV-04 manifest are **never modified** (R-EVAL-14).

Hard rules
----------
- The metric functions take ``X`` (np.ndarray) and ``labels`` (np.ndarray).
- The functions **never mutate** the caller's X or labels (defensive copy).
- All three metrics are computed; ``metric_set`` selects which entries
  are emitted, but the closed set is hard-coded to all 3 in DEV-05.
- On any per-metric failure, the function returns a non-VALID status
  for that metric only (others still computed).
- On any input failure (NaN/Inf, alignment, etc.), all three entries
  are set to ``COMPUTATION_ERROR`` with the same reason.
- Sklearn exception messages are NOT surfaced in the reason (R-EVAL-12);
  only the closed-set reason code is emitted.
- ``metric_value = None`` iff ``metric_status != VALID_VALUE``
  (no fake defaults per plan §5.5 rule 2).

This module is pure (no I/O, no logging, no path resolution).
"""

from __future__ import annotations

import time
from typing import Any, Final

import numpy as np
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

from customer_segmentation.prototype.evaluation.manifest import (
    EvaluationMetricEntry,
    EvaluationMetricsResult,
    make_computation_error_entry,
    make_missing_entry,
    make_not_applicable_entry,
    make_valid_entry,
)
from customer_segmentation.prototype.evaluation.scope import (
    METRIC_NAMES,
    MetricReason,
    MetricStatus,
)

__all__ = [
    "DBSCAN_NOISE_LABEL",
    "compute_internal_metrics",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# DBSCAN noise label (sklearn convention; plan §4.1).
DBSCAN_NOISE_LABEL: Final[int] = -1

# Algorithm families that emit noise rows.
DENSITY_BASED_FAMILY: Final[str] = "density_based"

# Closed set of valid algorithm families (mirror research core).
ALGORITHM_FAMILIES: Final[frozenset[str]] = frozenset(
    {"hard", "density_based", "model_based", "fuzzy"}
)

# Noise policies (mirror scope.py).
NOISE_POLICIES: Final[frozenset[str]] = frozenset({"include", "exclude"})


# ---------------------------------------------------------------------------
# Public compute function
# ---------------------------------------------------------------------------


def compute_internal_metrics(
    X: np.ndarray,
    labels: np.ndarray,
    *,
    algorithm_family: str,
    noise_policy: str = "exclude",
    noise_label: int = DBSCAN_NOISE_LABEL,
    metric_set: Any = None,  # any iterable of str
) -> EvaluationMetricsResult:
    """Compute silhouette, DBI, and CH for one clustering run.

    Parameters
    ----------
    X : np.ndarray of shape (n_samples, n_features)
        Feature matrix (DEV-05 re-loads the DEV-03 ML Dataset features
        after stripping CustomerID; the runner does NOT do this).
    labels : np.ndarray of shape (n_samples,)
        Cluster labels from the DEV-04 ``cluster_labels_*.parquet``.
        For DBSCAN, ``-1`` denotes noise.
    algorithm_family : {"hard", "density_based", "model_based", "fuzzy"}
        The DEV-04 algorithm family. Only ``"density_based"`` runs
        (DBSCAN) have noise rows.
    noise_policy : {"include", "exclude"}, default "exclude"
        Per ADR-0006 prototype default. When ``"exclude"`` and
        ``algorithm_family == "density_based"``, noise rows are
        filtered in-memory before calling sklearn. When ``"include"``,
        sklearn default applies (treating ``-1`` as a regular cluster).
    noise_label : int, default -1
        The label value denoting noise. Default is sklearn's convention.
    metric_set : iterable of str, optional
        Subset of :data:`METRIC_NAMES` to compute. Default = all 3
        (``silhouette``, ``davies_bouldin``, ``calinski_harabasz``).
        If a name is in the closed set but the user did not include
        it, an entry is still produced with status ``MISSING`` /
        ``MANIFEST_MISSING`` (consumers must see all 3 metric slots).

    Returns
    -------
    EvaluationMetricsResult
        Dict of 3 entries: ``silhouette``, ``davies_bouldin``,
        ``calinski_harabasz``. Each entry has value/status/reason
        per the plan §5.5 invariants.
    """
    # --- Validate inputs ---
    if algorithm_family not in ALGORITHM_FAMILIES:
        # Unknown family is a fail-closed case; all 3 entries MISSING.
        return EvaluationMetricsResult(
            entries={
                name: _make_unknown_family_entry(name)
                for name in METRIC_NAMES
            }
        )
    if noise_policy not in NOISE_POLICIES:
        return EvaluationMetricsResult(
            entries={
                name: make_missing_entry(
                    name, MetricReason.MANIFEST_MISSING.value
                )
                for name in METRIC_NAMES
            }
        )

    # Default metric_set = all 3.
    if metric_set is None:
        ms = frozenset(METRIC_NAMES)
    else:
        ms = frozenset(metric_set)
        unknown = ms - METRIC_NAMES
        if unknown:
            # Unknown metric name in user input.
            return EvaluationMetricsResult(
                entries={
                    name: make_computation_error_entry(
                        name, MetricReason.SKLEARN_EXCEPTION.value
                    )
                    for name in METRIC_NAMES
                }
            )

    # Defensive copies (no mutation of caller's arrays).
    X = np.asarray(X, dtype=np.float64).copy()
    labels = np.asarray(labels).copy()

    # Alignment check.
    if X.shape[0] != labels.shape[0]:
        return EvaluationMetricsResult(
            entries={
                name: make_computation_error_entry(
                    name, MetricReason.ALIGNMENT_ERROR.value
                )
                for name in METRIC_NAMES
            }
        )

    # NaN / Inf check on X.
    if not np.isfinite(X).all():
        return EvaluationMetricsResult(
            entries={
                name: make_computation_error_entry(
                    name, MetricReason.NAN_OR_INF_INPUT.value
                )
                for name in METRIC_NAMES
            }
        )

    # labels dtype check.
    if labels.dtype not in (np.int32, np.int64):
        # Try to coerce; if impossible, fail.
        try:
            labels = labels.astype(np.int64)
        except (TypeError, ValueError):
            return EvaluationMetricsResult(
                entries={
                    name: make_computation_error_entry(
                        name, MetricReason.CLUSTER_DTYPE_INVALID.value
                    )
                    for name in METRIC_NAMES
                }
            )

    # --- Apply noise filter (per ADR-0006 + plan §5.4) ---
    filter_applied = False
    if (
        algorithm_family == DENSITY_BASED_FAMILY
        and noise_policy == "exclude"
    ):
        mask = labels != noise_label
        n_noise = int((~mask).sum())
        if n_noise > 0:
            X = X[mask]
            labels = labels[mask]
            filter_applied = True
        # If n_noise == 0, no filter needed (no DBSCAN noise rows).

    # --- Edge case: empty / too few rows after filter ---
    n_samples_used = int(X.shape[0])
    unique_labels = np.unique(labels)
    n_clusters = int(unique_labels.size)

    if n_samples_used == 0:
        return EvaluationMetricsResult(
            entries={
                name: make_not_applicable_entry(
                    name, MetricReason.ALL_NOISE.value
                )
                for name in METRIC_NAMES
            }
        )
    if n_clusters < 2:
        return EvaluationMetricsResult(
            entries={
                name: make_not_applicable_entry(
                    name, MetricReason.SINGLE_CLUSTER.value
                )
                for name in METRIC_NAMES
            }
        )

    # --- Per-metric compute ---
    entries: dict[str, EvaluationMetricEntry] = {}

    # silhouette
    if "silhouette" in ms:
        entries["silhouette"] = _compute_one_metric(
            name="silhouette",
            metric_fn=lambda X_, y_: silhouette_score(X_, y_),
            X=X,
            labels=labels,
            filter_applied=filter_applied,
        )
    else:
        entries["silhouette"] = make_missing_entry(
            "silhouette", MetricReason.MANIFEST_MISSING.value
        )

    # davies_bouldin
    if "davies_bouldin" in ms:
        entries["davies_bouldin"] = _compute_one_metric(
            name="davies_bouldin",
            metric_fn=lambda X_, y_: davies_bouldin_score(X_, y_),
            X=X,
            labels=labels,
            filter_applied=filter_applied,
        )
    else:
        entries["davies_bouldin"] = make_missing_entry(
            "davies_bouldin", MetricReason.MANIFEST_MISSING.value
        )

    # calinski_harabasz
    if "calinski_harabasz" in ms:
        entries["calinski_harabasz"] = _compute_one_metric(
            name="calinski_harabasz",
            metric_fn=lambda X_, y_: calinski_harabasz_score(X_, y_),
            X=X,
            labels=labels,
            filter_applied=filter_applied,
        )
    else:
        entries["calinski_harabasz"] = make_missing_entry(
            "calinski_harabasz", MetricReason.MANIFEST_MISSING.value
        )

    return EvaluationMetricsResult(entries=entries)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unknown_family_entry(name: str) -> EvaluationMetricEntry:
    return make_missing_entry(
        name, MetricReason.ALGORITHM_FAMILY_NOT_SUPPORTED.value
    )


def _make_computation_error_entry_all(
    name: str, reason: str
) -> EvaluationMetricEntry:
    return make_computation_error_entry(name, reason)


def _make_not_applicable_entry_all(
    name: str, reason: str
) -> EvaluationMetricEntry:
    return make_not_applicable_entry(name, reason)


def _compute_one_metric(
    *,
    name: str,
    metric_fn,
    X: np.ndarray,
    labels: np.ndarray,
    filter_applied: bool,
) -> EvaluationMetricEntry:
    """Compute one metric with full status/reason capture.

    Returns one :class:`EvaluationMetricEntry`. Catches sklearn
    exceptions and returns COMPUTATION_ERROR (R-EVAL-12: raw exception
    message NOT surfaced).
    """
    start = time.perf_counter()
    try:
        value = float(metric_fn(X, labels))
    except ValueError as exc:
        elapsed = time.perf_counter() - start
        # Map sklearn ValueError to status.
        # Pattern: "Number of labels is N. Valid values are 2 to n_samples - 1"
        #          "Number of unique clusters" / "n_clusters" / etc.
        # When invalid → INSUFFICIENT_CLUSTERS (NOT_APPLICABLE).
        # All other ValueErrors → SKLEARN_EXCEPTION.
        msg = str(exc).lower()
        not_applicable_patterns = (
            "n_labels",
            "n_clusters",
            "number of labels",
            "number of unique",
            "valid values are 2 to",
        )
        if any(p in msg for p in not_applicable_patterns):
            return make_not_applicable_entry(
                name, MetricReason.INSUFFICIENT_CLUSTERS.value
            )
        return make_computation_error_entry(
            name,
            MetricReason.SKLEARN_EXCEPTION.value,
            computation_time_seconds=elapsed,
        )
    except Exception:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return make_computation_error_entry(
            name,
            MetricReason.SKLEARN_EXCEPTION.value,
            computation_time_seconds=elapsed,
        )
    elapsed = time.perf_counter() - start

    # Sklearn occasionally returns NaN / Inf for degenerate inputs.
    if not np.isfinite(value):
        return make_computation_error_entry(
            name,
            MetricReason.DEGENERATE_RESULT.value,
            computation_time_seconds=elapsed,
        )

    # Valid value.
    reason = (
        MetricReason.DBSCAN_NOISE_EXCLUDED.value
        if filter_applied
        else MetricReason.COMPUTED.value
    )
    return make_valid_entry(
        name, value, reason=reason, computation_time_seconds=elapsed
    )
