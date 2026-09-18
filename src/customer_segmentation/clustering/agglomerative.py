"""Agglomerative (hierarchical) clustering wrapper.

TODO
----
- Implement `fit_agglomerative(X, k_range, linkage, metric) -> (best_model, results)`.
- Default linkage to ``"ward"`` with ``metric="euclidean"``.
"""

from __future__ import annotations

import numpy as np

__all__: list[str] = []


def fit_agglomerative(
    X: np.ndarray,
    k_range: range | list[int],
    linkage: str = "ward",
    metric: str = "euclidean",
) -> tuple[object, list[dict]]:
    """Fit Agglomerative clustering for each value of `k` in `k_range`.

    Parameters
    ----------
    X : numpy.ndarray
        Scaled feature matrix.
    k_range : range or list[int]
        Values of ``k`` to evaluate.
    linkage : str
        Linkage criterion (``"ward"``, ``"complete"``, ``"average"``, ``"single"``).
    metric : str
        Distance metric.

    Returns
    -------
    best_model : sklearn.cluster.AgglomerativeClustering
        Fitted model for the best ``k``.
    results : list[dict]
        Per-``k`` metrics.

    Notes
    -----
    Placeholder. Implementation will be added in the clustering stage.
    """
    # TODO: implement Agglomerative benchmarking.
    raise NotImplementedError("fit_agglomerative is not implemented yet.")
