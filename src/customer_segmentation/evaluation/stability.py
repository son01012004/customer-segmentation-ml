"""Cluster stability analysis via bootstrap resampling.

TODO
----
- Implement `bootstrap_stability(X, fit_fn, n_bootstrap, seed) -> dict` that
  returns the distribution of ARI/AMI between each bootstrap fit and the
  reference fit on the full dataset.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

__all__: list[str] = []


def bootstrap_stability(
    X: np.ndarray,
    fit_fn: Callable[[np.ndarray], np.ndarray],
    n_bootstrap: int = 30,
    seed: int = 42,
) -> dict[str, list[float]]:
    """Estimate cluster stability via bootstrap resampling.

    Parameters
    ----------
    X : numpy.ndarray
        Scaled feature matrix.
    fit_fn : Callable[[np.ndarray], numpy.ndarray]
        Function that fits a clustering model and returns integer labels.
    n_bootstrap : int
        Number of bootstrap resamples.
    seed : int
        Random seed.

    Returns
    -------
    dict[str, list[float]]
        Mapping of metric name to the list of per-bootstrap values
        (e.g. ``{"ari": [...], "ami": [...]}``).

    Notes
    -----
    Placeholder. Implementation will be added in the evaluation stage.
    """
    # TODO: implement bootstrap stability.
    raise NotImplementedError("bootstrap_stability is not implemented yet.")
