"""Agglomerative (hierarchical) clustering adapter (ML-03).

This module implements Hierarchical / Agglomerative Clustering as a
concrete :class:`BaseClusterAlgorithm` adapter that plugs into the
ML-01 experiment framework. It is one of the four benchmark
algorithms fixed by the research methodology (K-Means, K-Medoids,
Agglomerative Clustering, DBSCAN — see AGENTS.md §2.1).

The adapter is a **thin, value-neutral wrapper** around
``sklearn.cluster.AgglomerativeClustering``. It does NOT:

- evaluate the result (silhouette, DBI, CH are EPIC-07/08 scope);
- compare Agglomerative to other algorithms (EPIC-08 scope);
- pick the "best" number of clusters, linkage or metric
  (EPIC-07 scope);
- transform, scale, or impute the input (FE-06 scope);
- mutate the input matrix.

The adapter only exposes the Agglomerative hyperparameters explicitly
listed in the ML-03 task contract: ``n_clusters``, ``linkage`` and
``metric``. Additional sklearn ``AgglomerativeClustering`` parameters
(``connectivity``, ``memory``, ``compute_full_tree``,
``distance_threshold``) are intentionally NOT exposed in this ML-03
layer because EPIC-07 will own the controlled sweep of
hyperparameters, and exposing more knobs now would expand scope
without methodological justification.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No "best/recommended/optimal/winner" language.
- The adapter MUST NOT mutate the input matrix ``X``.
- The adapter MUST NOT compute evaluation metrics (silhouette, DBI,
  CH, WCSS as a metric, ...).
- The adapter MUST respect the random-state policy of ML-01:
  Agglomerative clustering with ``n_clusters`` specified (the only
  mode this adapter supports) is **deterministic** in modern
  sklearn — there is no internal randomness to seed. Therefore
  ``supports_random_state()`` returns ``False`` and the experiment
  runner will NOT pass a seed to the adapter.

Methodology background
----------------------

**Hierarchical clustering** builds a nested tree of clusters. There
are two directions:

- **Divisive** (top-down): start with all observations in a single
  cluster and recursively split.
- **Agglomerative** (bottom-up): start with every observation as its
  own singleton cluster and recursively merge the two clusters that
  are "closest" under a chosen linkage criterion.

This adapter implements the **agglomerative / bottom-up** direction,
matching the ML-03 task contract and the EPIC-06 documentation
contract §3.3.

Agglomerative process (per iteration):

1. **Initialise** — every observation is its own cluster (``n``
   singleton clusters for ``n`` samples).
2. **Compute pairwise distances** between all points (cached by
   sklearn; cost depends on ``metric``).
3. **Select** the pair of clusters with the smallest inter-cluster
   distance under the chosen ``linkage`` criterion.
4. **Merge** the two clusters into a new cluster.
5. **Update** the distance matrix / heap.
6. **Repeat** steps 3–5 until the desired ``n_clusters`` remain
   (or, in the ``distance_threshold`` mode which this adapter does
   NOT expose, until the merge distance exceeds a threshold).

The output cluster assignment at the chosen ``n_clusters`` is what
the adapter records as ``cluster_labels``. The ``children_`` array
(which encodes the merge tree) and the optional ``distances_``
array (per-merge linkage distance) are recorded as algorithm-
specific diagnostics in :attr:`ClusterResult.extra`; they are
**not** used for ranking or "best k" decisions — those belong to
EPIC-07/08.

Linkage criteria
----------------

Given two clusters ``A`` and ``B`` and a pairwise distance function
``d(x, y)`` between points, the inter-cluster distance
``D(A, B)`` is defined by the linkage criterion:

- **Single linkage** (nearest neighbour):
  ``D(A, B) = min_{a in A, b in B} d(a, b)``
  Tends to produce long, "chained" clusters; sensitive to noise.

- **Complete linkage** (farthest neighbour):
  ``D(A, B) = max_{a in A, b in B} d(a, b)``
  Avoids chaining; tends to produce compact, equal-diameter
  clusters; sensitive to outliers.

- **Average linkage** (UPGMA):
  ``D(A, B) = (1 / (|A| * |B|)) Σ_{a in A, b in B} d(a, b)``
  Compromise between single and complete; sensitive to cluster
  shape.

- **Ward linkage**:
  ``D(A, B) = Δ(ESS) = ESS(A ∪ B) - ESS(A) - ESS(B)``
  where ``ESS(C) = Σ_{x in C} ||x - μ_C||²`` and ``μ_C`` is the
  centroid of ``C``. Ward minimises the increase in total
  within-cluster variance at each merge. **In scikit-learn, Ward
  linkage is restricted to Euclidean metric** (any L2-equivalent
  metric); the adapter validates this constraint and rejects any
  combination that sklearn itself rejects.

No linkage criterion is claimed to be "best" — the choice of
linkage is OUT OF SCOPE for ML-03; EPIC-07 will own the controlled
sweep.

Distance / metric
-----------------

The adapter distinguishes two related but distinct concepts:

- **Point-wise distance** ``d(x, y)``: defined by the ``metric``
  parameter. Euclidean is the default and the only metric
  compatible with Ward linkage.
- **Inter-cluster distance** ``D(A, B)``: derived from
  ``d(x, y)`` by the linkage criterion (see above).

Reproducibility
---------------

``sklearn.cluster.AgglomerativeClustering`` in ``n_clusters`` mode is
**deterministic** given the same input, the same configuration, and
the same library version — there is no internal RNG to seed. The
adapter therefore:

- Does **not** accept a ``random_state`` parameter.
- Overrides :meth:`supports_random_state` to return ``False``.
- Lets the ML-01 runner record ``random_seed_used = None`` and
  ``supports_random_state = False`` truthfully.

Dendrogram diagnostic
---------------------

A dendrogram is the canonical visualisation of the merge tree
produced by agglomerative clustering. The adapter does **not**
produce a rendered image (that would be EPIC-06 diagnostic
visualisation, which is optional and out of scope for ML-03 — see
EPIC06_DOCUMENTATION_CONTRACT §3.3, §9). The adapter does expose
the *numerical* ingredients needed for a downstream dendrogram in
:attr:`ClusterResult.extra`:

- ``linkage`` (str), ``metric`` (str): what was used.
- ``n_merges`` (int): ``n_samples - 1`` (every merge reduces the
  cluster count by 1 until ``n_clusters`` remain).
- ``n_leaves`` (int): ``n_samples``.
- ``max_merge_distance`` (float): largest linkage distance
  observed, useful as a coarse "cut height" reference (NOT a
  research-grade cut-decision).
- ``first_merges_distances`` (list of float): first few per-merge
  distances.
- ``last_merges_distances`` (list of float): last few per-merge
  distances.
- ``dendrogram_data_path`` (str or None): path to a parquet
  artifact with the full ``children_`` and ``distances_`` arrays,
  if the diagnostic write is requested.

A future EPIC-06 diagnostic visualiser MAY consume these fields
without re-running the algorithm; ML-03 itself does not draw the
dendrogram and does not use it to declare any ``n_clusters`` as
"optimal".

Algorithm-specific diagnostics (ML-03 scope)
--------------------------------------------

This ML-03 adapter is intentionally diagnostic-only with respect
to ``n_clusters`` selection, linkage selection, metric selection
and cut-height selection. EPIC-07 will own:

- the controlled sweep over ``n_clusters`` (and possibly
  ``linkage`` / ``metric``),
- the formal evaluation metrics (silhouette, DBI, CH, ...).

EPIC-08 will own:

- stability analysis (ARI / AMI across seeds — N/A for
  deterministic Agglomerative; recorded for completeness),
- runtime comparison,
- algorithm ranking.

ML-03 records the diagnostics listed above and nothing more.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import sklearn
from sklearn.cluster import AgglomerativeClustering

from customer_segmentation.clustering.base import BaseClusterAlgorithm, ClusterAlgorithmError
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import AlgorithmFamily, ClusterResult

__all__ = [
    "AgglomerativeAdapter",
    "DEFAULT_LINKAGE",
    "DEFAULT_METRIC",
    "MIN_N_CLUSTERS",
    "SUPPORTED_LINKAGES",
    "SUPPORTED_METRICS",
]


# ---------------------------------------------------------------------------
# Working defaults (mirror configs/clustering.yaml algorithms.agglomerative.*).
# These are *working* defaults (TECHNICALLY_IMPLEMENTED), not final approved
# methodology. EPIC-07 will run the controlled sweep over n_clusters / linkage
# / metric.
# ---------------------------------------------------------------------------

DEFAULT_LINKAGE: str = "ward"
DEFAULT_METRIC: str = "euclidean"
MIN_N_CLUSTERS: int = 2  # ML-03 task contract: validate n_clusters >= 2.

# Linkage criteria supported by this adapter. Mirrors the values accepted by
# sklearn.cluster.AgglomerativeClustering.linkage. "average", "complete" and
# "single" accept arbitrary metrics supported by sklearn; "ward" is restricted
# to Euclidean (sklearn enforces this at fit-time).
SUPPORTED_LINKAGES: frozenset[str] = frozenset({"ward", "complete", "average", "single"})

# Metrics supported by this adapter. The list is intentionally conservative:
# "euclidean" is the only metric compatible with Ward linkage; the others
# work with non-Ward linkages (complete / average / single) but require
# sklearn to support the metric string in the current environment. We do
# not pre-enumerate every sklearn-supported metric to avoid hard-coding
# sklearn's metric table; instead we delegate the final compatibility
# check to sklearn at fit-time and convert any sklearn ValueError into a
# ClusterAlgorithmError.
SUPPORTED_METRICS: frozenset[str] = frozenset(
    {"euclidean", "manhattan", "cityblock", "cosine", "chebyshev", "l1", "l2"}
)


@AlgorithmRegistry.register("agglomerative")
class AgglomerativeAdapter(BaseClusterAlgorithm):
    """Agglomerative hierarchical clustering adapter for ML-01 framework.

    The adapter wraps ``sklearn.cluster.AgglomerativeClustering`` with
    the ``n_clusters`` stopping rule. It does NOT transform, scale, or
    impute the input — that is FE-06's job.

    Attributes
    ----------
    name : str
        Stable, lowercase identifier (``"agglomerative"``). Set by the
        registry on registration.
    version : str
        ``"sklearn_<version>"`` so the experiment log captures the
        underlying library version.
    family : str
        :attr:`AlgorithmFamily.HARD` — Agglomerative clustering assigns
        every point to exactly one cluster (no soft probability, no
        fuzzy membership, no noise label in ``n_clusters`` mode).

    Parameters
    ----------
    n_clusters : int
        Number of clusters ``K``. Must be ``>= 2`` (ML-03 task
        contract) and ``< n_samples``. Working default is **not set
        here** — ML-03 must always receive an explicit ``n_clusters``
        from the caller / EPIC-07 sweep.
    linkage : str
        Linkage criterion: ``"ward"``, ``"complete"``, ``"average"``
        or ``"single"``. Default: ``"ward"``.
    metric : str
        Pairwise distance metric. Default: ``"euclidean"``. The
        ``"ward"`` linkage requires Euclidean metric; the adapter
        validates this constraint up-front.
    compute_distances : bool
        Whether to compute and store the per-merge linkage
        distances. Required for the dendrogram diagnostic recorded
        in :attr:`ClusterResult.extra`. Default: ``True`` because
        the diagnostic is small for n=4371 and useful for ML-03's
        algorithm-specific scope. Can be set to ``False`` to skip
        the extra memory / compute when only ``cluster_labels``
        are needed.

    Notes
    -----
    - The adapter does NOT mutate the input matrix ``X``.
    - The adapter records algorithm-specific extras (``linkage``,
      ``metric``, ``n_merges``, ``max_merge_distance``, first/last
      merge distances, cluster sizes) in
      :attr:`ClusterResult.extra` for EPIC-06 diagnostic viz and
      EPIC-07 sweeps. These are **diagnostic-only** in ML-03;
      EPIC-08 will own formal metrics.
    - The adapter does NOT compute silhouette, Davies-Bouldin, or
      Calinski-Harabasz indices (out of scope).
    - The adapter does NOT accept a ``random_state``: Agglomerative
      clustering in ``n_clusters`` mode is deterministic in modern
      sklearn. ``supports_random_state()`` returns ``False`` so the
      framework's runner records the truth.
    """

    name: str = "agglomerative"
    version: str = f"sklearn_{sklearn.__version__}"
    family: str = AlgorithmFamily.HARD

    def __init__(
        self,
        n_clusters: int,
        *,
        linkage: str = DEFAULT_LINKAGE,
        metric: str = DEFAULT_METRIC,
        compute_distances: bool = True,
    ) -> None:
        # ---- Hyperparameter validation (fail-fast on bad config) ----
        if not isinstance(n_clusters, (int, np.integer)):
            raise ClusterAlgorithmError(
                f"n_clusters must be an integer; got {type(n_clusters).__name__}."
            )
        if int(n_clusters) < MIN_N_CLUSTERS:
            raise ClusterAlgorithmError(
                f"n_clusters must be >= {MIN_N_CLUSTERS}; got {n_clusters}."
            )
        if not isinstance(linkage, str):
            raise ClusterAlgorithmError(
                f"linkage must be a string; got {type(linkage).__name__}={linkage!r}."
            )
        if linkage not in SUPPORTED_LINKAGES:
            raise ClusterAlgorithmError(
                f"linkage must be one of {sorted(SUPPORTED_LINKAGES)}; got {linkage!r}."
            )
        if not isinstance(metric, str):
            raise ClusterAlgorithmError(
                f"metric must be a string; got {type(metric).__name__}={metric!r}."
            )
        if metric not in SUPPORTED_METRICS:
            # We do not pre-enumerate every sklearn metric; we surface a
            # clear error listing the ones this adapter advertises. If
            # sklearn later accepts the metric, the user can extend
            # SUPPORTED_METRICS (or pass a callable, which this adapter
            # intentionally does not support in ML-03 scope).
            raise ClusterAlgorithmError(
                f"metric must be one of {sorted(SUPPORTED_METRICS)}; got {metric!r}."
            )
        # ward + non-euclidean is a sklearn hard constraint. Reject
        # up-front with a clear message rather than waiting for
        # sklearn to raise at fit-time.
        if linkage == "ward" and metric != "euclidean":
            raise ClusterAlgorithmError(
                f"linkage 'ward' is only compatible with metric "
                f"'euclidean' (or an L2-equivalent); got metric={metric!r}."
            )
        if not isinstance(compute_distances, bool):
            raise ClusterAlgorithmError(
                f"compute_distances must be a bool; got "
                f"{type(compute_distances).__name__}={compute_distances!r}."
            )

        self.n_clusters = int(n_clusters)
        self.linkage = linkage
        self.metric = metric
        self.compute_distances = bool(compute_distances)

        # Fitted state (populated by fit()).
        self._model: AgglomerativeClustering | None = None

    # ----- Algorithm interface -----
    def fit(self, X: np.ndarray) -> ClusterResult:
        """Fit Agglomerative clustering on the feature matrix.

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
            (linkage, metric, n_merges, merge-distance summary,
            cluster sizes, dendrogram-data path if produced).

        Raises
        ------
        ClusterAlgorithmError
            If the input is invalid for Agglomerative clustering
            (e.g. wrong dimensionality, ``n_clusters`` not less than
            ``n_samples``, or sklearn rejects the (linkage, metric)
            combination).
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
                f"Agglomerative clustering requires n_samples >= 2; " f"got n_samples={n_samples}."
            )
        if self.n_clusters >= n_samples:
            raise ClusterAlgorithmError(
                f"n_clusters ({self.n_clusters}) must be < n_samples ({n_samples})."
            )
        if n_features < 1:
            raise ClusterAlgorithmError(
                f"Agglomerative clustering requires n_features >= 1; "
                f"got n_features={n_features}."
            )

        # Build the AgglomerativeClustering estimator.
        try:
            model = AgglomerativeClustering(
                n_clusters=self.n_clusters,
                linkage=self.linkage,
                metric=self.metric,
                compute_distances=self.compute_distances,
            )
            labels_array = model.fit_predict(X)
        except ValueError as exc:
            # sklearn raises ValueError for impossible configurations
            # (e.g. ward + non-euclidean, n_clusters > n_samples,
            # unknown metric). Convert to a framework exception so
            # the runner records a clean FAILED status.
            raise ClusterAlgorithmError(f"Agglomerative fit failed: {exc}") from exc
        except TypeError as exc:
            # Some sklearn versions raise TypeError for unknown metric
            # strings or for passing non-supported kwargs.
            raise ClusterAlgorithmError(f"Agglomerative fit failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - convert any sklearn error
            raise ClusterAlgorithmError(f"Agglomerative fit failed: {exc}") from exc

        # Cast labels to int64 explicitly so downstream artifact
        # writers can rely on the dtype.
        labels = np.asarray(labels_array, dtype=np.int64)
        n_clusters_found = int(labels.max()) + 1 if labels.size > 0 else 0

        # Cache the fitted model so callers can introspect via
        # get_model().
        self._model = model

        # Build the algorithm-specific diagnostic extras. These are
        # value-neutral diagnostics — they do NOT make any claim of
        # "best linkage" or "best n_clusters". EPIC-07 will own the
        # controlled sweep that consumes them.
        extra: dict[str, Any] = {
            "linkage": str(self.linkage),
            "metric": str(self.metric),
            "compute_distances_used": bool(self.compute_distances),
            # sklearn exposes n_leaves_ (== n_samples) and children_
            # (the merge tree) after fit.
            "n_leaves": int(getattr(model, "n_leaves_", n_samples)),
            "n_merges": int(max(n_samples - 1, 0)),
        }
        # Cluster sizes — diagnostic only.
        try:
            unique, counts = np.unique(labels, return_counts=True)
            extra["cluster_sizes"] = {
                int(u): int(c) for u, c in zip(unique.tolist(), counts.tolist(), strict=True)
            }
        except Exception:  # pragma: no cover - defensive only
            extra["cluster_sizes"] = None

        # Distance-summary fields. Always present in ``extra`` so
        # downstream consumers can rely on the schema; populated when
        # ``compute_distances=True`` and ``None`` otherwise. We do
        # NOT serialise the full ``distances_`` array (length
        # ``n-1``, up to ~4370 floats for n=4371) into the
        # experiment log to keep log size manageable; the
        # dendrogram-data artifact parquet (if produced by a caller)
        # is the canonical place for the full array.
        if self.compute_distances:
            distances = getattr(model, "distances_", None)
            if distances is not None:
                try:
                    distances_arr = np.asarray(distances, dtype=np.float64)
                    extra["max_merge_distance"] = float(distances_arr.max())
                    extra["min_merge_distance"] = float(distances_arr.min())
                    extra["median_merge_distance"] = float(np.median(distances_arr))
                    # Keep first/last 5 entries as a coarse summary
                    # sufficient for log readers without flooding
                    # the JSON.
                    k_show = 5
                    if distances_arr.size <= 2 * k_show:
                        extra["merge_distances_summary"] = distances_arr.tolist()
                    else:
                        extra["merge_distances_summary"] = (
                            distances_arr[:k_show].tolist()
                            + ["..."]
                            + distances_arr[-k_show:].tolist()
                        )
                except Exception:  # pragma: no cover - defensive only
                    # Do NOT fail the experiment if the summary
                    # cannot be computed; the cluster labels are
                    # already produced.
                    extra["max_merge_distance"] = None
                    extra["min_merge_distance"] = None
                    extra["median_merge_distance"] = None
                    extra["merge_distances_summary"] = None
            else:
                # compute_distances=True but sklearn did not expose
                # distances_ — record the absence for transparency.
                extra["max_merge_distance"] = None
                extra["min_merge_distance"] = None
                extra["median_merge_distance"] = None
                extra["merge_distances_summary"] = None
        else:
            # compute_distances=False: distance-summary fields are
            # reserved as None for schema stability.
            extra["max_merge_distance"] = None
            extra["min_merge_distance"] = None
            extra["median_merge_distance"] = None
            extra["merge_distances_summary"] = None

        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=int(n_samples),
            n_features=int(n_features),
            cluster_labels=labels,
            n_clusters=n_clusters_found,
            # Agglomerative (n_clusters mode) has no noise label;
            # leave the default -1 unchanged so the framework does
            # not interpret Agglomerative labels as noise.
            noise_label=-1,
            noise_count=0,
            noise_ratio=0.0,
            # Agglomerative clustering in n_clusters mode is
            # deterministic; no random_state is consumed. The runner
            # will see supports_random_state=False and skip
            # seed-injection even if a seed is requested via the
            # framework config.
            supports_random_state=False,
            random_seed_used=None,
            extra=extra,
            # metrics placeholder stays default (all None) — EPIC-07/08
            # will populate.
        )

    # ----- Convenience hooks -----
    def get_params(self) -> dict[str, Any]:
        """Return the adapter's hyperparameters as a JSON-friendly dict.

        Override the base default to expose the explicit
        hyperparameters used by Agglomerative clustering. The
        framework records this in the experiment log so future
        readers can reproduce the exact configuration.
        """
        return {
            "n_clusters": self.n_clusters,
            "linkage": str(self.linkage),
            "metric": str(self.metric),
            "compute_distances": self.compute_distances,
        }

    def get_model(self) -> Any:
        """Return the underlying fitted ``sklearn.cluster.AgglomerativeClustering``.

        Returns ``None`` if :meth:`fit` has not been called yet. This
        hook lets EPIC-07/08 introspect the fitted model
        (``children_``, ``labels_``, ``n_leaves_``, ``distances_``
        if ``compute_distances=True``, ...) without coupling to the
        adapter.
        """
        return self._model

    def supports_random_state(self) -> bool:
        """Agglomerative clustering does NOT consume ``random_state``.

        In ``n_clusters`` mode, ``sklearn.cluster.AgglomerativeClustering``
        has no internal randomness to seed — given the same input,
        configuration, and library version, the result is identical.

        The framework's runner inspects this method to decide
        whether to pass a seed; returning ``False`` here means
        the runner will set ``seed_to_pass = None`` even when the
        caller requested a seed via
        :class:`ExperimentSpec.seed_override` or the YAML
        ``framework.random_seed.default``. The experiment log
        records this truth via ``random_seed`` (requested) and
        ``random_seed_used = None`` (not consumed).
        """
        return False
