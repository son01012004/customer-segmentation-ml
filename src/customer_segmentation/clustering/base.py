"""Base interface for clustering algorithm adapters (ML-01).

This module defines :class:`BaseClusterAlgorithm`, an abstract base class
that every concrete algorithm adapter (K-Means, Agglomerative, DBSCAN,
GMM, Fuzzy C-Means, ...) MUST implement to be plugged into the ML-01
experiment framework.

The design philosophy follows the AGENTS.md rules:

- Each algorithm family has its own mathematical characteristics
  (hard vs. soft, partition vs. density-based, deterministic vs.
  stochastic). ML-01 does NOT force a one-size-fits-all internal API.
  Instead, each subclass is free to expose its own outputs in
  :class:`customer_segmentation.clustering.result.ClusterResult`
  (e.g. ``noise_label`` for DBSCAN, ``soft_probabilities`` for GMM,
  ``soft_membership`` for Fuzzy C-Means).

- Random-state handling is explicit: algorithms that support
  ``random_state`` advertise it via :meth:`supports_random_state`;
  algorithms that do not (Agglomerative with Ward linkage) advertise
  ``False`` so the experiment log records the truth.

- No "best/recommended/optimal" claim. The base class is value-neutral.

- No mutation of the input matrix. The base class never calls
  ``DataFrame.copy`` automatically — the runner is responsible for
  handing the adapter a *view* it can read without mutating.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from customer_segmentation.clustering.result import ClusterResult


class ClusterAlgorithmError(ValueError):
    """Raised when an algorithm adapter is misconfigured or fails to fit.

    Subclasses MAY raise this with additional context, or use their own
    exception type. The experiment runner catches this together with any
    other ``Exception`` to populate the experiment log with
    ``status = FAILED``.
    """


class BaseClusterAlgorithm(ABC):
    """Abstract base class for clustering algorithm adapters.

    Concrete subclasses MUST define:

    - :attr:`name` — short, stable identifier (e.g. ``"kmeans"``).
    - :attr:`version` — implementation / library version string.
    - :attr:`family` — see :class:`AlgorithmFamily`.
    - :meth:`fit` — fit on the feature matrix and return a
      :class:`ClusterResult` populated with the algorithm-specific
      outputs.

    Concrete subclasses SHOULD define:

    - :meth:`get_params` — current hyperparameters as a dict, used for
      the experiment log.
    - :meth:`get_model` — return the fitted underlying model object
      (``sklearn.cluster.KMeans``, ...) for downstream evaluation, or
      ``None`` if the implementation does not expose one.

    Notes
    -----
    - The framework does NOT assume every algorithm supports
      ``random_state``. Subclasses that do not support randomness
      (e.g. deterministic algorithms) should advertise it via
      :meth:`supports_random_state`.
    - The base class does NOT mutate the input matrix. Subclasses MUST
      NOT mutate the input either.
    """

    # ----- Class-level metadata (subclasses MUST set) -----
    name: str = ""  # e.g. "kmeans"
    version: str = ""  # e.g. "sklearn_1.x"
    family: str = ""  # see AlgorithmFamily constants in result.py

    # ----- Abstract methods -----
    @abstractmethod
    def fit(self, X: np.ndarray) -> ClusterResult:
        """Fit the algorithm on ``X`` and return a :class:`ClusterResult`.

        Parameters
        ----------
        X : numpy.ndarray
            Numeric feature matrix of shape ``(n_samples, n_features)``.
            The input is owned by the caller; the adapter MUST NOT
            mutate it.

        Returns
        -------
        ClusterResult
            Algorithm-specific cluster outputs. See
            :class:`customer_segmentation.clustering.result.ClusterResult`.

        Raises
        ------
        ClusterAlgorithmError
            If the adapter cannot produce a valid result.
        """

    # ----- Default hooks (subclasses MAY override) -----
    def get_params(self) -> dict[str, Any]:
        """Return the algorithm's current hyperparameters as a dict.

        The default implementation reflects an empty ``__dict__`` subset
        that is JSON-serialisable. Subclasses SHOULD override this to
        expose their full hyperparameter set so the experiment log
        captures exactly what was run.

        Returns
        -------
        dict
            Mapping of parameter name to value. Values must be
            JSON-serialisable (numbers, strings, lists, booleans,
            ``None``).
        """
        out: dict[str, Any] = {}
        for key in sorted(self.__dict__):
            if key.startswith("_"):
                continue
            value = self.__dict__[key]
            if isinstance(value, (int, float, str, bool, type(None))):
                out[key] = value
            elif isinstance(value, (list, tuple)):
                out[key] = list(value)
        return out

    def get_model(self) -> Any:
        """Return the fitted underlying model object, or ``None``.

        The default returns ``None`` because most algorithms store
        their fitted state inside the adapter. Subclasses that wrap an
        external estimator (e.g. ``sklearn.cluster.KMeans``) MAY
        override this to return the underlying fitted estimator, so
        downstream evaluation (EPIC-07/08) can introspect it.

        Returns
        -------
        object or None
            The fitted model object, or ``None`` if not available.
        """
        return None

    def supports_random_state(self) -> bool:
        """Whether this algorithm supports ``random_state``.

        Subclasses SHOULD override this with the truthful answer for
        their algorithm. The default assumes ``True`` because the most
        common clustering algorithms (K-Means, GMM, ...) do support
        randomness control; deterministic algorithms (Agglomerative
        with Ward linkage, DBSCAN) MUST override this and return
        ``False`` so the experiment log records the truth.

        Returns
        -------
        bool
            ``True`` if ``random_state`` is respected, ``False`` otherwise.
        """
        return True

    # ----- Convenience constructors (used by the registry / runner) -----
    def __repr__(self) -> str:  # pragma: no cover - trivial
        params = ", ".join(f"{k}={v!r}" for k, v in sorted(self.get_params().items()))
        cls = type(self).__name__
        return f"{cls}(name={self.name!r}, family={self.family!r}, {params})"


__all__ = ["BaseClusterAlgorithm", "ClusterAlgorithmError"]
