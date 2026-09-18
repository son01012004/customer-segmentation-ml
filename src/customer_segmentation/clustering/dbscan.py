"""DBSCAN clustering wrapper.

TODO
----
- Implement `fit_dbscan(X, eps_range, min_samples_range) -> (best_model, results)`.
- Track number of clusters and noise points per parameter combination.
"""

from __future__ import annotations

import numpy as np

__all__: list[str] = []


def fit_dbscan(
    X: np.ndarray,
    eps_range: list[float],
    min_samples_range: list[int],
) -> tuple[object, list[dict]]:
    """Fit DBSCAN over a grid of (eps, min_samples).

    Parameters
    ----------
    X : numpy.ndarray
        Scaled feature matrix.
    eps_range : list[float]
        Candidate neighbourhood radii.
    min_samples_range : list[int]
        Candidate ``min_samples`` values.

    Returns
    -------
    best_model : sklearn.cluster.DBSCAN
        Fitted DBSCAN model for the best parameter pair.
    results : list[dict]
        Per-combination metrics (n_clusters, n_noise, silhouette on core samples, ...).

    Notes
    -----
    Placeholder. Implementation will be added in the clustering stage.
    """
    # TODO: implement DBSCAN grid search.
    raise NotImplementedError("fit_dbscan is not implemented yet.")
