"""K-Means clustering wrapper.

TODO
----
- Implement `fit_kmeans(X, k_range, n_init, max_iter) -> (best_model, results)`
  where `results` contains the per-k inertia and silhouette score.
"""

from __future__ import annotations

import numpy as np

__all__: list[str] = []


def fit_kmeans(
    X: np.ndarray,
    k_range: range | list[int],
    n_init: int = 10,
    max_iter: int = 300,
    random_seed: int = 42,
) -> tuple[object, list[dict]]:
    """Fit K-Means for each value of `k` in `k_range`.

    Parameters
    ----------
    X : numpy.ndarray
        Scaled feature matrix (n_samples, n_features).
    k_range : range or list[int]
        Values of ``k`` to evaluate.
    n_init : int
        Number of random restarts per ``k``.
    max_iter : int
        Maximum iterations per restart.
    random_seed : int
        Random seed for reproducibility.

    Returns
    -------
    best_model : sklearn.cluster.KMeans
        Fitted model for the best ``k`` (selection criterion TBD).
    results : list[dict]
        Per-``k`` metrics (inertia, silhouette, ...).

    Notes
    -----
    Placeholder. Implementation will be added in the clustering stage.
    """
    # TODO: implement K-Means benchmarking.
    raise NotImplementedError("fit_kmeans is not implemented yet.")
