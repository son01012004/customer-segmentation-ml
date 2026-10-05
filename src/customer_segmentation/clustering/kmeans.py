"""K-Means clustering adapter (ML-02).

This module implements the K-Means algorithm as a concrete
:class:`BaseClusterAlgorithm` adapter that plugs into the ML-01
experiment framework. It is one of the four benchmark algorithms
fixed by the research methodology (K-Means, K-Medoids, Agglomerative
Clustering, DBSCAN — see AGENTS.md §2.1).

The adapter is a **thin, value-neutral wrapper** around
``sklearn.cluster.KMeans``. It does NOT:

- evaluate the result (silhouette, DBI, CH are EPIC-07/08 scope);
- compare K-Means to other algorithms (EPIC-08 scope);
- pick the "best" number of clusters (EPIC-07 scope);
- transform, scale, or impute the input (FE-06 scope);
- mutate the input matrix.

The adapter only exposes the K-Means hyperparameters explicitly listed
in the ML-02 task contract: ``n_clusters``, ``init``, ``n_init``,
``max_iter``, ``random_state``. Additional sklearn K-Means parameters
are intentionally NOT exposed in this ML-02 layer because EPIC-07 will
own the controlled sweep of hyperparameters, and exposing more knobs
now would expand scope without methodological justification.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No "best/recommended/optimal/winner" language.
- The adapter MUST NOT mutate the input matrix ``X``.
- The adapter MUST NOT compute evaluation metrics (silhouette, DBI,
  CH, WCSS as a metric, ...).
- The adapter MUST respect the random-state policy of ML-01:
  ``supports_random_state() == True`` for K-Means, and the framework
  may pass a ``random_state`` to make runs reproducible.

Mathematical background (concise; not a textbook):

K-Means solves the following objective:

    J = Σ_i Σ_{j=1..K} 1(c_i = j) · ||x_i - μ_j||²

where ``x_i`` is observation ``i``, ``c_i ∈ {0, ..., K-1}`` is its
cluster assignment, and ``μ_j`` is the centroid of cluster ``j``. The
algorithm alternates two steps until convergence:

1. **Assignment** — for each observation, assign it to the cluster
   whose centroid is closest (typically Euclidean distance).
2. **Update** — recompute each centroid as the mean of the points
   currently assigned to it.

The objective ``J`` is also called the **within-cluster sum of
squares** (WCSS) or **inertia**. K-Means converges to a (local)
minimum because ``J`` is monotonically non-increasing across the two
steps. Convergence is reached when assignments no longer change or
when ``max_iter`` is exceeded.

K-Means requires the user to choose ``K`` in advance. The choice of
``K`` is OUT OF SCOPE for ML-02; EPIC-07 owns the sweep over
``k_range`` defined in ``configs/clustering.yaml``.

Initialization: sklearn's default is ``init="k-means++"`` (since
sklearn 1.1), which seeds initial centroids using a
distance-proportional probability scheme. This avoids the poor
local minima of pure random initialization in most practical cases,
but K-Means is still sensitive to initialization. To mitigate this,
``n_init`` restarts are run with different seeds and the run with the
lowest inertia is returned. The ML-02 working default
(``n_init=10``) is read from ``configs/clustering.yaml`` and follows
the sklearn recommendation.

Reproducibility: K-Means is deterministic **given** a fixed
``random_state``, ``init``, ``n_init``, and library version. The
adapter records ``random_seed_used`` so EPIC-07/08 can reproduce
specific runs.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import sklearn
from sklearn.cluster import KMeans

from customer_segmentation.clustering.base import BaseClusterAlgorithm, ClusterAlgorithmError
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import AlgorithmFamily, ClusterResult

__all__ = [
    "KMeansAdapter",
    "DEFAULT_INIT",
    "DEFAULT_N_INIT",
    "DEFAULT_MAX_ITER",
    "MIN_N_CLUSTERS",
]


# ---------------------------------------------------------------------------
# Working defaults (mirror configs/clustering.yaml algorithms.kmeans.*).
# These are *working* defaults (TECHNICALLY_IMPLEMENTED), not final
# approved methodology. EPIC-07 will run the controlled sweep.
# ---------------------------------------------------------------------------

DEFAULT_INIT: str = "k-means++"
DEFAULT_N_INIT: int = 10
DEFAULT_MAX_ITER: int = 300
MIN_N_CLUSTERS: int = 1


@AlgorithmRegistry.register("kmeans")
class KMeansAdapter(BaseClusterAlgorithm):
    """K-Means clustering adapter for the ML-01 experiment framework.

    The adapter wraps ``sklearn.cluster.KMeans``. It does NOT
    transform, scale, or impute the input — that is FE-06's job.

    Attributes
    ----------
    name : str
        Stable, lowercase identifier (``"kmeans"``). Set by the
        registry on registration.
    version : str
        ``"sklearn_<version>"`` so the experiment log captures the
        underlying library version.
    family : str
        :attr:`AlgorithmFamily.HARD` — K-Means assigns every point to
        exactly one cluster (no soft probability).

    Parameters
    ----------
    n_clusters : int
        Number of clusters ``K``. Must be ``>= 1`` and ``< n_samples``.
        Working default is **not set here** — ML-02 must always receive
        an explicit ``n_clusters`` from the caller / EPIC-07 sweep.
    init : str
        Initialization method. ``"k-means++"`` (default since sklearn
        1.1) or ``"random"``. Other sklearn-supported options
        (``"k-means++"``, ``"random"``, callable) are accepted
        verbatim.
    n_init : int
        Number of random restarts. sklearn runs the algorithm this
        many times with different seeds and returns the result with
        the lowest inertia. Default: ``10`` (matches
        ``configs/clustering.yaml``).
    max_iter : int
        Maximum number of iterations per restart. Default: ``300``
        (matches ``configs/clustering.yaml``).
    random_state : int or None
        Seed for the random number generator. ``None`` means
        non-reproducible. The framework may pass an explicit seed via
        ``resolve_random_seed``.
    tol : float
        Relative tolerance for convergence. Default: ``1e-4`` (sklearn
        default). Not exposed as a working knob but accepted for
        compatibility with sklearn.

    Notes
    -----
    - The adapter does NOT mutate the input matrix ``X``.
    - The adapter records WCSS (inertia), ``n_iter_``, and the actual
      ``n_init`` used in :attr:`ClusterResult.extra` for EPIC-07
      diagnostics. These are **diagnostic-only** in ML-02; EPIC-08
      will own formal metrics.
    - The adapter does NOT compute silhouette, Davies-Bouldin, or
      Calinski-Harabasz indices (out of scope).
    """

    name: str = "kmeans"
    version: str = f"sklearn_{sklearn.__version__}"
    family: str = AlgorithmFamily.HARD

    def __init__(
        self,
        n_clusters: int,
        *,
        init: str = DEFAULT_INIT,
        n_init: int = DEFAULT_N_INIT,
        max_iter: int = DEFAULT_MAX_ITER,
        random_state: int | None = None,
        tol: float = 1e-4,
    ) -> None:
        # Validate hyperparameters up-front so the runner can record
        # a clear ClusterAlgorithmError on bad configuration.
        if not isinstance(n_clusters, (int, np.integer)):
            raise ClusterAlgorithmError(
                f"n_clusters must be an integer; got {type(n_clusters).__name__}."
            )
        if int(n_clusters) < MIN_N_CLUSTERS:
            raise ClusterAlgorithmError(
                f"n_clusters must be >= {MIN_N_CLUSTERS}; got {n_clusters}."
            )
        # Validate init strategy. sklearn 1.4+ accepts a string init
        # (``"k-means++"`` / ``"random"``), a numpy array of initial
        # centroids, or a callable. We reject any other string to fail
        # fast on typos (e.g. ``"kmeans--"``) instead of letting
        # sklearn raise a less informative error during fit.
        if isinstance(init, str):
            if init not in ("k-means++", "random"):
                raise ClusterAlgorithmError(
                    f"init must be 'k-means++' or 'random' when given as "
                    f"a string; got {init!r}."
                )
        elif not (callable(init) or isinstance(init, np.ndarray)):
            raise ClusterAlgorithmError(
                f"init must be a string ('k-means++' or 'random'), a numpy "
                f"array, or a callable; got {type(init).__name__}={init!r}."
            )
        if not isinstance(n_init, (int, np.integer)) or int(n_init) < 1:
            raise ClusterAlgorithmError(f"n_init must be a positive integer; got {n_init!r}.")
        if not isinstance(max_iter, (int, np.integer)) or int(max_iter) < 1:
            raise ClusterAlgorithmError(f"max_iter must be a positive integer; got {max_iter!r}.")
        if random_state is not None and not isinstance(random_state, (int, np.integer)):
            raise ClusterAlgorithmError(
                f"random_state must be an integer or None; got "
                f"{type(random_state).__name__}={random_state!r}."
            )

        self.n_clusters = int(n_clusters)
        self.init = init
        self.n_init = int(n_init)
        self.max_iter = int(max_iter)
        self.random_state = None if random_state is None else int(random_state)
        self.tol = float(tol)

        # Fitted state (populated by fit()).
        self._model: KMeans | None = None

    # ----- Algorithm interface -----
    def fit(self, X: np.ndarray) -> ClusterResult:
        """Fit K-Means on the feature matrix and return a ClusterResult.

        Parameters
        ----------
        X : numpy.ndarray
            Numeric feature matrix of shape ``(n_samples, n_features)``.
            MUST be the matrix delivered by the framework
            (``matrix_df.to_numpy(dtype=np.float64, copy=False)``).
            MUST NOT contain identifiers (validated upstream by
            :func:`validate_clustering_matrix`).

        Returns
        -------
        ClusterResult
            Hard cluster labels, plus algorithm-specific extras
            (``wcss`` / inertia, ``n_iter_``, ``effective_n_init``).

        Raises
        ------
        ClusterAlgorithmError
            If the input is invalid for K-Means (e.g. wrong
            dimensionality, ``n_clusters`` not less than ``n_samples``)
            or sklearn fails to fit.
        """
        if X is None:
            raise ClusterAlgorithmError("Input matrix X is None.")
        if not isinstance(X, np.ndarray):
            raise ClusterAlgorithmError(
                f"Input matrix must be a numpy.ndarray; got {type(X).__name__}."
            )
        if X.ndim != 2:
            raise ClusterAlgorithmError(f"Input matrix must be 2-D; got ndim={X.ndim}.")
        n_samples, n_features = X.shape
        if n_samples < 2:
            raise ClusterAlgorithmError(
                f"K-Means requires n_samples >= 2; got n_samples={n_samples}."
            )
        if self.n_clusters >= n_samples:
            raise ClusterAlgorithmError(
                f"n_clusters ({self.n_clusters}) must be < n_samples ({n_samples})."
            )
        if n_features < 1:
            raise ClusterAlgorithmError(
                f"K-Means requires n_features >= 1; got n_features={n_features}."
            )

        # sklearn accepts init as string, ndarray, or callable.
        sklearn_init: Any = self.init

        # Build the KMeans estimator. We do NOT pass a pre-existing
        # model; we construct a fresh one each fit.
        try:
            model = KMeans(
                n_clusters=self.n_clusters,
                init=sklearn_init,
                n_init=self.n_init,
                max_iter=self.max_iter,
                random_state=self.random_state,
                tol=self.tol,
            )
            labels_array = model.fit_predict(X)
        except ValueError as exc:
            # sklearn raises ValueError for impossible configurations
            # (e.g. n_clusters > n_samples). Convert to a framework
            # exception so the runner records a clean FAILED status.
            raise ClusterAlgorithmError(f"K-Means fit failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - convert any sklearn error
            raise ClusterAlgorithmError(f"K-Means fit failed: {exc}") from exc

        # Cast labels to int64 explicitly so downstream artifact
        # writers can rely on the dtype.
        labels = np.asarray(labels_array, dtype=np.int64)
        n_clusters_found = int(labels.max()) + 1 if labels.size > 0 else 0

        # Cache the fitted model so callers can introspect via
        # get_model().
        self._model = model

        # WCSS (inertia) is recorded in ``extra`` as a diagnostic. It
        # is NOT the formal ``metrics.wcss`` slot, which EPIC-07/08
        # owns.
        try:
            wcss_value = float(model.inertia_)
        except AttributeError:
            wcss_value = None

        extra: dict[str, Any] = {
            "init_strategy": str(self.init),
            "effective_n_init": int(getattr(model, "n_init_used", self.n_init)),
            "n_iter": int(getattr(model, "n_iter_", -1)),
            "converged": bool(getattr(model, "n_iter_", -1) < self.max_iter),
        }
        if wcss_value is not None:
            extra["wcss"] = wcss_value

        # Cluster sizes — diagnostic only.
        try:
            unique, counts = np.unique(labels, return_counts=True)
            extra["cluster_sizes"] = {
                int(u): int(c) for u, c in zip(unique.tolist(), counts.tolist(), strict=True)
            }
        except Exception:  # pragma: no cover - defensive only
            extra["cluster_sizes"] = None

        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=int(n_samples),
            n_features=int(n_features),
            cluster_labels=labels,
            n_clusters=n_clusters_found,
            # K-Means has no noise label; leave default -1 unchanged
            # so the framework does not interpret K-Means labels as
            # noise.
            noise_label=-1,
            noise_count=0,
            noise_ratio=0.0,
            supports_random_state=True,
            random_seed_used=self.random_state,
            extra=extra,
            # metrics placeholder stays default (all None) — EPIC-07/08
            # will populate.
        )

    # ----- Convenience hooks -----
    def get_params(self) -> dict[str, Any]:
        """Return the adapter's hyperparameters as a JSON-friendly dict.

        Override the base default to expose the explicit
        hyperparameters used by K-Means. The framework records this in
        the experiment log so future readers can reproduce the exact
        configuration.
        """
        return {
            "n_clusters": self.n_clusters,
            "init": str(self.init),
            "n_init": self.n_init,
            "max_iter": self.max_iter,
            "random_state": self.random_state,
            "tol": self.tol,
        }

    def get_model(self) -> Any:
        """Return the underlying fitted ``sklearn.cluster.KMeans``.

        Returns ``None`` if :meth:`fit` has not been called yet. This
        hook lets EPIC-07/08 introspect the fitted model (centroids,
        inertia, n_iter_, ...) without coupling to the adapter.
        """
        return self._model

    def supports_random_state(self) -> bool:
        """K-Means supports ``random_state`` (consumed by sklearn).

        This is truthful: sklearn's KMeans uses ``random_state`` to
        seed the initialization step (``k-means++`` or ``random``).
        Combined with ``n_init``, this makes K-Means deterministic
        given the same input, init, n_init, max_iter, random_state,
        and library version.
        """
        return True
