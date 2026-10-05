"""DBSCAN clustering adapter (ML-04).

This module implements Density-Based Spatial Clustering of Applications
with Noise (DBSCAN) as a concrete :class:`BaseClusterAlgorithm` adapter
that plugs into the ML-01 experiment framework. It is one of the four
benchmark algorithms fixed by the research methodology (K-Means, K-Medoids,
Agglomerative Clustering, DBSCAN — see AGENTS.md §2.1).

The adapter is a **thin, value-neutral wrapper** around
``sklearn.cluster.DBSCAN``. It does NOT:

- evaluate the result (silhouette, DBI, CH are EPIC-07/08 scope);
- compare DBSCAN to other algorithms (EPIC-08 scope);
- pick the "best" ``eps`` or ``min_samples`` (EPIC-07 scope);
- transform, scale, or impute the input (FE-06 scope);
- mutate the input matrix.

The adapter only exposes the DBSCAN hyperparameters explicitly listed
in the ML-04 task contract: ``eps``, ``min_samples`` and ``metric``.
Additional sklearn ``DBSCAN`` parameters (``algorithm``, ``leaf_size``,
``p``, ``n_jobs``) are intentionally NOT exposed in this ML-04 layer
because they are sklearn-internal configuration details that do not
affect the research methodology; EPIC-07 will own the controlled sweep
of ``eps`` and ``min_samples``.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No "best/recommended/optimal/winner" language.
- The adapter MUST NOT mutate the input matrix ``X``.
- The adapter MUST NOT compute evaluation metrics (silhouette, DBI,
  CH, ...).
- The adapter MUST NOT remove or relabel noise points.
- The noise label convention (``-1``) MUST be preserved verbatim.
- The adapter MUST respect the random-state policy of ML-01:
  DBSCAN is deterministic; ``supports_random_state()`` returns
  ``False``.

Methodology background
---------------------

**DBSCAN** (Ester et al., 1996) groups points that are close to each
other into clusters, and marks isolated points as noise. The algorithm
is parameterised by two hyperparameters:

- ``eps`` — the neighbourhood radius (epsilon).
- ``min_samples`` — the minimum number of points required to form a
  dense region.

Definitions (per sklearn convention):

**Epsilon-neighbourhood** of a point ``x``:

    N_eps(x) = {x_j | d(x, x_j) <= eps}

where ``d`` is the chosen pairwise distance metric.

**Core point**: a point ``x`` is a *core point* if
``|N_eps(x)| >= min_samples``. In sklearn's convention (which this
adapter inherits), the point itself is **included** in the count,
so a point with exactly ``min_samples`` neighbours (including itself)
is a core point.

**Border point**: a point that is not a core point but that lies
within the epsilon-neighbourhood of a core point.

**Noise point**: a point that is neither a core point nor a border
point. In sklearn's convention, noise points receive the label
``-1``.

**Density reachability**:
Point ``p`` is *directly density-reachable* from point ``q``
if ``p ∈ N_eps(q)`` and ``q`` is a core point.
Point ``p`` is *density-reachable* from point ``q`` if there exists
a chain of points ``p_1, p_2, ..., p_n`` where
``p_1 = q`` and ``p_n = p``, and each ``p_{i+1}`` is directly
density-reachable from ``p_i``.

**Density connectivity**:
Two points ``p`` and ``q`` are *density-connected* if there exists
a point ``o`` such that both ``p`` and ``q`` are density-reachable
from ``o``.

A **cluster** is a maximal set of density-connected points that
are not noise.

Key differences from centroid / hierarchical clustering
-----------------------------------------------------

1. **No ``n_clusters`` parameter**: DBSCAN discovers the number of
   clusters from the data rather than requiring the user to specify
   it up front.

2. **Noise label**: points labelled ``-1`` are noise, not outliers
   to be dropped or re-labelled. The adapter preserves the ``-1``
   convention verbatim in ``ClusterResult.cluster_labels`` and
   records ``noise_count`` / ``noise_ratio`` explicitly.

3. **No ``random_state``**: DBSCAN in ``n_clusters``-free mode is
   deterministic in sklearn; there is no random initialisation.
   ``supports_random_state()`` returns ``False`` so the runner does
   not inject a seed.

4. **Cluster count depends on hyperparameters**: different
   ``(eps, min_samples)`` pairs may produce different numbers of
   clusters and different noise ratios. EPIC-07 will own the
   controlled sweep that explores this space.

Algorithm-specific diagnostics (ML-04 scope)
-----------------------------------------

The adapter records the following DBSCAN-specific diagnostics in
:attr:`ClusterResult.extra`:

- ``eps``, ``min_samples``, ``metric`` — the configuration used.
- ``n_clusters`` — number of clusters discovered (excluding noise).
- ``noise_count``, ``noise_ratio`` — noise statistics.
- ``core_sample_count``, ``core_sample_ratio`` — number and
  proportion of core points (points whose neighbourhood meets
  ``min_samples``).
- ``cluster_sizes`` — dict mapping cluster label → count,
  **excluding** noise.
- ``all_noise`` — ``True`` if every point is labelled ``-1``
  (edge case: ``n_clusters == 0``).
- ``has_noise`` — ``True`` if at least one point is labelled ``-1``.
- ``has_single_cluster`` — ``True`` if exactly one non-noise
  cluster was found.
- ``labels_value_counts`` — compact label distribution (label →
  count), including ``-1`` for noise.

These diagnostics are **diagnostic-only** in ML-04; EPIC-07 will own
the controlled sweep and EPIC-08 will own formal evaluation.

K-distance diagnostic note
------------------------

A *k-distance plot* (sorting each point's distance to its ``k``-th
nearest neighbour) is a common heuristic for choosing ``eps``. The
adapter does NOT produce a k-distance plot here — that is an
**optional** EPIC-06 diagnostic visualisation. The adapter records
the ingredients needed for a downstream k-distance plot via
``core_sample_indices_`` introspection if EPIC-06 diagnostic
viz is requested later.

Reproducibility
---------------

``sklearn.cluster.DBSCAN`` in its standard form is deterministic —
there is no internal random state to seed. The adapter therefore:

- Does **not** accept a ``random_state`` parameter.
- Overrides :meth:`supports_random_state` to return ``False``.
- Lets the ML-01 runner record ``random_seed_used = None`` and
  ``supports_random_state = False`` truthfully.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import sklearn
from sklearn.cluster import DBSCAN

from customer_segmentation.clustering.base import BaseClusterAlgorithm, ClusterAlgorithmError
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import AlgorithmFamily, ClusterResult

__all__ = [
    "DBSCANAdapter",
    "DEFAULT_EPS",
    "DEFAULT_MIN_SAMPLES",
    "DEFAULT_METRIC",
    "MIN_SAMPLES_MIN",
    "EPS_MIN",
    "SUPPORTED_METRICS",
]


# ---------------------------------------------------------------------------
# Working defaults (mirror configs/clustering.yaml algorithms.dbscan.*).
# These are *working* defaults (TECHNICALLY_IMPLEMENTED), not final approved
# methodology. EPIC-07 will run the controlled sweep over eps / min_samples.
# ---------------------------------------------------------------------------

DEFAULT_EPS: float = 0.5
DEFAULT_MIN_SAMPLES: int = 5
DEFAULT_METRIC: str = "euclidean"
MIN_SAMPLES_MIN: int = 1
EPS_MIN: float = 1e-6  # strictly positive; using a small floor to catch typos

# Metrics supported by this adapter. The list is intentionally
# conservative: we advertise the metrics most commonly used with
# DBSCAN on continuous feature data. Additional metrics that sklearn
# accepts (precomputed, minkowski, cosine, etc.) are accepted at
# runtime if sklearn itself accepts them; a failed sklearn fit
# results in a ClusterAlgorithmError rather than a silent failure.
SUPPORTED_METRICS: frozenset[str] = frozenset(
    {
        "euclidean",
        "manhattan",
        "cityblock",
        "cosine",
        "chebyshev",
        "l1",
        "l2",
    }
)


@AlgorithmRegistry.register("dbscan")
class DBSCANAdapter(BaseClusterAlgorithm):
    """DBSCAN density-based clustering adapter for ML-01 framework.

    The adapter wraps ``sklearn.cluster.DBSCAN``. It does NOT
    transform, scale, or impute the input — that is FE-06's job.

    Attributes
    ----------
    name : str
        Stable, lowercase identifier (``"dbscan"``). Set by the
        registry on registration.
    version : str
        ``"sklearn_<version>"`` so the experiment log captures the
        underlying library version.
    family : str
        :attr:`AlgorithmFamily.DENSITY_BASED` — DBSCAN produces hard
        labels with a dedicated noise label.

    Parameters
    ----------
    eps : float
        Maximum distance between two samples to be considered as
        in the same neighbourhood. Must be ``> 0``. Working default
        is **not set here** — ML-04 must always receive an explicit
        ``eps`` from the caller / EPIC-07 sweep.
    min_samples : int
        Number of samples in a neighbourhood for a point to be
        considered a core point (includes the point itself). Must
        be ``>= 1``. Working default is **not set here** — ML-04
        must always receive an explicit ``min_samples`` from the
        caller / EPIC-07 sweep.
    metric : str
        Distance metric. Default: ``"euclidean"``. Options include
        ``"manhattan"``, ``"cityblock"``, ``"cosine"``,
        ``"chebyshev"``, ``"l1"``, ``"l2"``, ``"precomputed"``.
        The choice of metric affects both cluster formation and the
        meaning of ``eps``.

    Notes
    -----
    - The adapter does NOT mutate the input matrix ``X``.
    - The adapter does NOT remove or re-label noise points (``-1``
      is preserved verbatim).
    - The adapter records ``noise_count`` and ``noise_ratio``
      explicitly in :attr:`ClusterResult` fields and in
      :attr:`ClusterResult.extra`.
    - The adapter does NOT compute silhouette, Davies-Bouldin, or
      Calinski-Harabasz indices (out of scope).
    - The adapter does NOT accept a ``random_state``: DBSCAN is
      deterministic in sklearn. ``supports_random_state()`` returns
      ``False`` so the framework's runner records the truth.
    """

    name: str = "dbscan"
    version: str = f"sklearn_{sklearn.__version__}"
    family: str = AlgorithmFamily.DENSITY_BASED

    def __init__(
        self,
        eps: float,
        min_samples: int,
        metric: str = DEFAULT_METRIC,
    ) -> None:
        # ---- Hyperparameter validation (fail-fast on bad config) ----
        if not isinstance(eps, (int, float)):
            raise ClusterAlgorithmError(f"eps must be a number; got {type(eps).__name__}.")
        if float(eps) <= 0.0:
            raise ClusterAlgorithmError(f"eps must be strictly positive; got {eps}.")
        if not isinstance(min_samples, (int, np.integer)):
            raise ClusterAlgorithmError(
                f"min_samples must be an integer; got {type(min_samples).__name__}."
            )
        if int(min_samples) < MIN_SAMPLES_MIN:
            raise ClusterAlgorithmError(
                f"min_samples must be >= {MIN_SAMPLES_MIN}; got {min_samples}."
            )
        if not isinstance(metric, str):
            raise ClusterAlgorithmError(f"metric must be a string; got {type(metric).__name__}.")
        # Metric validation is delegated to sklearn at fit-time so
        # that we do not hard-code sklearn's full metric table. If
        # sklearn raises a ValueError we convert it to a
        # ClusterAlgorithmError.

        self.eps = float(eps)
        self.min_samples = int(min_samples)
        self.metric = metric

        # Fitted state (populated by fit()).
        self._model: DBSCAN | None = None

    # ----- Algorithm interface -----
    def fit(self, X: np.ndarray) -> ClusterResult:
        """Fit DBSCAN on the feature matrix.

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
            Hard cluster labels with noise label ``-1``, plus
            DBSCAN-specific diagnostics (noise count/ratio, core
            sample count, cluster sizes, label distribution).

        Raises
        ------
        ClusterAlgorithmError
            If the input is invalid for DBSCAN (e.g. wrong
            dimensionality, sklearn rejects the metric, etc.).
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
        if n_features < 1:
            raise ClusterAlgorithmError(
                f"DBSCAN requires n_features >= 1; got n_features={n_features}."
            )
        # DBSCAN can technically run with n_samples=0 or n_samples=1;
        # sklearn will label everything as noise. We allow it so that
        # the framework does not abort before the algorithm gets a
        # chance to report the edge case.

        # Build the DBSCAN estimator.
        try:
            model = DBSCAN(
                eps=self.eps,
                min_samples=self.min_samples,
                metric=self.metric,
            )
            labels_array = model.fit_predict(X)
        except ValueError as exc:
            # sklearn raises ValueError for unknown metric, invalid
            # precomputed matrix, etc. Convert to a framework
            # exception so the runner records a clean FAILED status.
            raise ClusterAlgorithmError(f"DBSCAN fit failed: {exc}") from exc
        except TypeError as exc:
            # Some sklearn versions raise TypeError for unknown metric.
            raise ClusterAlgorithmError(f"DBSCAN fit failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - convert any sklearn error
            raise ClusterAlgorithmError(f"DBSCAN fit failed: {exc}") from exc

        # Cast labels to int64 explicitly so downstream artifact
        # writers can rely on the dtype.
        labels = np.asarray(labels_array, dtype=np.int64)

        # ---- Compute DBSCAN-specific statistics ----
        # sklearn 1.9.x does not expose n_clusters_ as a fitted attribute
        # (it was added in a later sklearn release). We compute the
        # cluster count from the labels directly.
        unique_labels = np.unique(labels)
        noise_label_value = -1
        cluster_labels_only = [lbl for lbl in unique_labels if lbl != noise_label_value]
        n_clusters_found = len(cluster_labels_only)

        noise_mask = labels == noise_label_value
        noise_count = int(noise_mask.sum())
        noise_ratio = float(noise_count) / float(n_samples) if n_samples > 0 else 0.0

        # Core sample statistics: sklearn exposes core_sample_indices_
        # after fit. An empty array means no core points (all noise).
        core_indices = getattr(model, "core_sample_indices_", None)
        core_sample_count = int(len(core_indices)) if core_indices is not None else 0
        core_sample_ratio = float(core_sample_count) / float(n_samples) if n_samples > 0 else 0.0

        # Cluster sizes (excluding noise).
        cluster_sizes: dict[str, int] = {}
        for lbl in cluster_labels_only:
            cluster_sizes[str(int(lbl))] = int((labels == lbl).sum())

        # Label distribution (compact: label → count, including noise).
        labels_vc = {}
        for lbl, cnt in zip(*np.unique(labels, return_counts=True), strict=True):
            labels_vc[str(int(lbl))] = int(cnt)

        # Edge-case flags.
        all_noise = bool(noise_count == n_samples)
        has_noise = bool(noise_count > 0)
        # ``has_single_cluster`` is True when DBSCAN found exactly
        # ONE non-noise cluster. Noise points are not part of a
        # cluster, so having noise alongside the cluster does NOT
        # change the answer; the test suite distinguishes
        # ``has_single_cluster`` (structural property of the
        # non-noise labels) from ``has_noise`` (presence of -1).
        has_single_cluster = bool(n_clusters_found == 1)

        # Cache the fitted model so callers can introspect via
        # get_model().
        self._model = model

        extra: dict[str, Any] = {
            "eps": float(self.eps),
            "min_samples": int(self.min_samples),
            "metric": str(self.metric),
            # Cluster statistics.
            "n_clusters": n_clusters_found,
            "noise_count": noise_count,
            "noise_ratio": noise_ratio,
            "has_noise": has_noise,
            "all_noise": all_noise,
            "has_single_cluster": has_single_cluster,
            # Core sample statistics.
            "core_sample_count": core_sample_count,
            "core_sample_ratio": core_sample_ratio,
            # Cluster sizes (noise excluded).
            "cluster_sizes": cluster_sizes,
            # Full label distribution (including noise label -1).
            "labels_value_counts": labels_vc,
        }

        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=int(n_samples),
            n_features=int(n_features),
            cluster_labels=labels,
            n_clusters=n_clusters_found,
            # DBSCAN noise label is -1 (sklearn convention).
            noise_label=noise_label_value,
            noise_count=noise_count,
            noise_ratio=noise_ratio,
            # DBSCAN is deterministic; no random_state is consumed.
            # The runner will see supports_random_state=False and
            # skip seed-injection.
            supports_random_state=False,
            random_seed_used=None,
            extra=extra,
            # metrics placeholder stays default (all None) — EPIC-07/08
            # will populate.
        )

    # ----- Convenience hooks -----
    def get_params(self) -> dict[str, Any]:
        """Return the adapter's hyperparameters as a JSON-friendly dict."""
        return {
            "eps": self.eps,
            "min_samples": self.min_samples,
            "metric": self.metric,
        }

    def get_model(self) -> Any:
        """Return the underlying fitted ``sklearn.cluster.DBSCAN``.

        Returns ``None`` if :meth:`fit` has not been called yet. This
        hook lets EPIC-07/08 introspect the fitted model
        (``core_sample_indices_``, ``components_``, ``labels_``,
        ``eps``, ``min_samples``, ``metric``) without coupling to
        the adapter.
        """
        return self._model

    def supports_random_state(self) -> bool:
        """DBSCAN does NOT consume ``random_state``.

        DBSCAN in its standard form (without approximate neighbour
        search that involves randomness) is deterministic in sklearn.
        There is no internal RNG to seed. The framework's runner
        inspects this method to decide whether to pass a seed;
        returning ``False`` here means the runner sets
        ``seed_to_pass = None`` even when a caller requests a seed
        via :class:`ExperimentSpec.seed_override` or the YAML
        ``framework.random_seed.default``. The experiment log records
        this via ``random_seed_used = None``.
        """
        return False
