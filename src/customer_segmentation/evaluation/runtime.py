"""Runtime benchmarking for clustering algorithms.

TODO
----
- Implement `measure_runtime(fit_fn, X, repeat) -> dict` returning mean and
  std of wall-clock time across repeats.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

__all__: list[str] = []


def measure_runtime(
    fit_fn: Callable[[np.ndarray], object],
    X: np.ndarray,
    repeat: int = 5,
) -> dict[str, float]:
    """Measure wall-clock runtime of a clustering fit function.

    Parameters
    ----------
    fit_fn : Callable[[numpy.ndarray], object]
        Function that fits a clustering model on `X`.
    X : numpy.ndarray
        Feature matrix.
    repeat : int
        Number of repetitions.

    Returns
    -------
    dict[str, float]
        Keys ``mean``, ``std``, ``min``, ``max`` in seconds.

    Notes
    -----
    Placeholder. Implementation will be added in the evaluation stage.
    """
    # TODO: implement runtime measurement.
    raise NotImplementedError("measure_runtime is not implemented yet.")
