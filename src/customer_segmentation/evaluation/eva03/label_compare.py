"""Label comparison primitives for EVA-03.

Provides:

- ``compute_label_compare`` — ARI / AMI / NMI for two label arrays.
- ``hungarian_align`` — Hungarian-matching cluster-label alignment
  via the contingency matrix. DESCRIPTIVE ONLY: produces per-cluster
  correspondence between two runs, NOT a stability metric.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- ARI / AMI / NMI use sklearn defaults (permutation-invariant).
- Hungarian matching is DESCRIPTIVE only. The output is recorded
  for traceability, not as a score that enters a "best algorithm"
  comparison.
- DBSCAN noise label (-1) is included in ARI / AMI / NMI by
  construction; it is excluded from Hungarian matching because
  Hungarian's score assumes clusters with positive overlap counts.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    adjusted_mutual_info_score,
    adjusted_rand_score,
    normalized_mutual_info_score,
)
from scipy.optimize import linear_sum_assignment

from customer_segmentation.evaluation.eva03.types import HungarianAssignment

__all__ = [
    "compute_label_compare",
    "hungarian_align",
    "DBSCAN_NOISE_LABEL",
]


DBSCAN_NOISE_LABEL: int = -1


def compute_label_compare(labels_a: np.ndarray, labels_b: np.ndarray) -> dict[str, float]:
    """Compute ARI / AMI / NMI for two label arrays.

    Uses sklearn defaults:

    - ``adjusted_rand_score`` — ARI.
    - ``adjusted_mutual_info_score`` — AMI (default ``average_method='arithmetic'``).
    - ``normalized_mutual_info_score`` — NMI (default
      ``average_method='arithmetic'``).

    Parameters
    ----------
    labels_a, labels_b : np.ndarray
        Same-shape 1-D integer arrays of cluster labels. ARI / AMI / NMI
        are permutation-invariant, so order does not matter.

    Returns
    -------
    dict[str, float]
        ``{ari, ami, nmi}`` each in [-1, 1] (ARI) / [0, 1] (AMI/NMI).

    Notes
    -----
    All three metrics are bounded in [-1, 1] (ARI) / [0, 1] (AMI / NMI).
    ARI = AMI = NMI = 1.0 indicates the two clusterings are identical
    (up to label permutation).
    """
    if labels_a.shape != labels_b.shape:
        raise ValueError(
            f"Labels must have the same shape. Got {labels_a.shape} and {labels_b.shape}."
        )
    ari = float(adjusted_rand_score(labels_a, labels_b))
    ami = float(adjusted_mutual_info_score(labels_a, labels_b))
    nmi = float(normalized_mutual_info_score(labels_a, labels_b))
    return {"ari": ari, "ami": ami, "nmi": nmi}


def _contingency_matrix(
    labels_a: np.ndarray, labels_b: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a contingency matrix between two cluster label arrays.

    Returns
    -------
    matrix : np.ndarray (shape [n_a, n_b])
        Where ``matrix[i, j]`` = number of points with label a==i and b==j.
    rows_a, cols_b : np.ndarray
        Sorted unique label sets for rows / cols.
    """
    a = np.asarray(labels_a, dtype=np.int64)
    b = np.asarray(labels_b, dtype=np.int64)
    rows_a = np.unique(a)
    cols_b = np.unique(b)
    row_idx = {v: i for i, v in enumerate(rows_a)}
    col_idx = {v: j for j, v in enumerate(cols_b)}
    matrix = np.zeros((len(rows_a), len(cols_b)), dtype=np.int64)
    for ai, bi in zip(a, b):
        matrix[row_idx[int(ai)], col_idx[int(bi)]] += 1
    return matrix, rows_a, cols_b


def hungarian_align(
    labels_a: np.ndarray,
    labels_b: np.ndarray,
    *,
    exclude_noise_label: int | None = DBSCAN_NOISE_LABEL,
) -> HungarianAssignment:
    """Hungarian cluster-label alignment between two label arrays.

    Given two clusterings ``labels_a`` and ``labels_b`` of the same
    N points, this function finds the bijection between the clusters
    of ``labels_a`` and the clusters of ``labels_b`` that maximizes
    the total overlap count.

    Parameters
    ----------
    labels_a, labels_b : np.ndarray
        Same-shape 1-D integer arrays of cluster labels.
    exclude_noise_label : int | None, optional
        If not None, treat this label as "noise" and exclude it from
        the contingency matrix before Hungarian matching. DBSCAN uses
        ``-1`` as the noise label. For other algorithms, set to None.

    Returns
    -------
    HungarianAssignment
        Per-cluster correspondence mapping. ``source_labels[i]`` is
        mapped to ``target_labels[i]`` with ``overlap_counts[i]``
        customer overlap. The Hungarian matching maximizes total
        overlap_count across the matched clusters.

    Notes
    -----
    Hungarian matching is DESCRIPTIVE ONLY — it is intended for
    traceability and inspection of "which cluster in run A maps to
    which cluster in run B?". It is NOT a stability metric and is
    NOT used to rank algorithms or configurations.
    """
    if labels_a.shape != labels_b.shape:
        raise ValueError(
            f"Labels must have the same shape. Got {labels_a.shape} and {labels_b.shape}."
        )
    a = np.asarray(labels_a, dtype=np.int64)
    b = np.asarray(labels_b, dtype=np.int64)
    if exclude_noise_label is not None:
        mask = (a != exclude_noise_label) & (b != exclude_noise_label)
        a = a[mask]
        b = b[mask]
        total_customers = int(mask.sum())
    else:
        total_customers = int(len(a))

    matrix, rows_a, cols_b = _contingency_matrix(a, b)
    # Pad the smaller side so the bipartite graph is square (linear_sum_assignment
    # requires a square cost matrix).
    n_max = max(matrix.shape)
    padded = np.zeros((n_max, n_max), dtype=np.int64)
    padded[: matrix.shape[0], : matrix.shape[1]] = matrix
    # Hungarian maximizes sum; minimize the negation.
    cost = -padded
    row_ind, col_ind = linear_sum_assignment(cost)

    source_labels: list[int] = []
    target_labels: list[int] = []
    overlap_counts: list[int] = []
    for r, c in zip(row_ind, col_ind):
        # Drop padded dummy mappings.
        if r >= matrix.shape[0] or c >= matrix.shape[1]:
            continue
        source_labels.append(int(rows_a[r]))
        target_labels.append(int(cols_b[c]))
        overlap_counts.append(int(matrix[r, c]))

    # Run IDs are not known at this layer; default placeholders will be
    # filled in by the caller.
    return HungarianAssignment(
        algorithm="",
        run_id_a="",
        run_id_b="",
        source_labels=source_labels,
        target_labels=target_labels,
        overlap_counts=overlap_counts,
        total_customers=total_customers,
    )


def run_hungarian_for_pair(
    algorithm: str,
    run_id_a: str,
    run_id_b: str,
    labels_a: np.ndarray,
    labels_b: np.ndarray,
    *,
    exclude_noise_label: int | None = DBSCAN_NOISE_LABEL,
) -> HungarianAssignment:
    """Convenience wrapper that pre-fills ``algorithm`` / ``run_id*``."""
    res = hungarian_align(labels_a, labels_b, exclude_noise_label=exclude_noise_label)
    return HungarianAssignment(
        algorithm=algorithm,
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        source_labels=res.source_labels,
        target_labels=res.target_labels,
        overlap_counts=res.overlap_counts,
        total_customers=res.total_customers,
    )
