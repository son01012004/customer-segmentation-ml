"""K-Medoids clustering wrapper.

TODO
----
- Implement `fit_kmedoids(X, k_range, metric, init)` using scikit-learn-extra
  if available, otherwise a documented fallback.
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
