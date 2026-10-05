"""K-Medoids clustering wrapper.

STATUS: OUT OF SCOPE (per ADR-0003)
=====================================
K-Medoids is NOT in the current benchmark scope. The five algorithms
benchmarked are: K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means.
See docs/decisions/0003-algorithm-scope.md for the full decision rationale.

This file is retained as a placeholder. It may be reactivated for a
future research phase via a new ADR.
"""

from __future__ import annotations

import numpy as np

__all__: list[str] = []


def fit_kmedoids(
    X: np.ndarray,
    k_range: range | list[int],
    metric: str = "euclidean",
    init: str = "random",
    random_seed: int = 42,
) -> tuple[object, list[dict]]:
    """Fit K-Medoids for each value of `k` in `k_range`.

    Parameters
    ----------
    X : numpy.ndarray
        Scaled feature matrix.
    k_range : range or list[int]
        Values of ``k`` to evaluate.
    metric : str
        Distance metric (``"euclidean"`` or ``"precomputed"``).
    init : str
        Initialization strategy (``"random"`` or ``"k-medoids++"``).
    random_seed : int
        Random seed.

    Returns
    -------
    best_model : object
        Fitted K-Medoids model.
    results : list[dict]
        Per-``k`` metrics.

    Notes
    -----
    Placeholder. Implementation will be added in the clustering stage.
    """
    # TODO: implement K-Medoids benchmarking.
    raise NotImplementedError("fit_kmedoids is not implemented yet.")
