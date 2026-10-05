"""Fuzzy C-Means (FCM) clustering adapter (ML-06).

This module implements Fuzzy C-Means as a concrete
:class:`BaseClusterAlgorithm` adapter that plugs into the ML-01
experiment framework. FCM is the **fuzzy clustering** family
member of the EPIC-06 benchmark set and serves as the
algorithm-baseline completion task for ML-06.

The adapter is a **thin, value-neutral wrapper** around a
**custom** Fuzzy C-Means implementation built on top of
``numpy`` (no additional dependency required; the
``scikit-fuzzy`` / ``skfuzzy`` library is intentionally not
introduced in this ML-06 layer to avoid expanding the
dependency surface without methodological justification —
see AGENTS.md §5, "Adding a new dependency without ADR").
The custom implementation reproduces the canonical
Bezdek / Dunn FCM algorithm (membership update +
fuzzy centroid + iterative optimisation until convergence
or ``max_iter``) and is fully deterministic when a
``random_state`` is fixed.

The adapter does NOT:

- evaluate the result (silhouette, DBI, CH are EPIC-07/08 scope);
- compare FCM to other algorithms (EPIC-08 scope);
- pick the "best" ``c`` or ``m`` (EPIC-07 scope);
- transform, scale, or impute the input (FE-06 scope);
- mutate the input matrix;
- replace the soft membership with hard labels (hard labels
  are derived as ``argmax``; the membership matrix ``U`` is
  preserved as the primary output).

The adapter exposes the FCM hyperparameters explicitly listed
in the ML-06 task contract: ``n_clusters`` (number of fuzzy
clusters ``c``), ``m`` (fuzziness parameter), ``max_iter``,
``error`` (convergence threshold) and ``random_state`` (seed
for the membership-matrix initialisation). All five are the
minimum knobs required by FCM theory; no additional sklearn
or scikit-fuzzy–specific knobs are exposed.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No "best/recommended/optimal/winner" language.
- The adapter MUST NOT mutate the input matrix ``X``.
- The adapter MUST NOT compute evaluation metrics
  (silhouette, DBI, CH, ...).
- The adapter MUST NOT remove or re-label observations.
- The adapter MUST preserve the soft-clustering output
  (per-sample fuzzy membership); this is the defining
  characteristic of fuzzy clustering and MUST be exposed via
  :attr:`ClusterResult.soft_membership` and the
  ``algorithm_output`` artifact.
- The adapter MUST respect the random-state policy of ML-01:
  FCM with random membership initialisation consumes
  ``random_state``; the adapter advertises
  :meth:`supports_random_state` as ``True`` so the framework
  can inject a seed.

Mathematical background (concise; not a textbook)
-------------------------------------------------

**Fuzzy C-Means** (Dunn 1973; Bezdek 1981) generalises
K-Means by replacing the binary "ownership" of K-Means with a
*membership degree* ``u_ik ∈ [0, 1]`` that quantifies how
strongly observation ``x_i`` belongs to cluster ``k``. The
constraints on the membership matrix ``U = [u_ik]`` are:

    u_ik ∈ [0, 1]    for all i, k
    Σ_{k=1..c} u_ik = 1    for every observation i

where ``c`` is the number of fuzzy clusters. Each row of
``U`` is a probability simplex vector (it does not represent a
Bayesian probability — it represents a degree of belonging).

**Objective function** that FCM minimises:

    J_m(U, V) = Σ_{i=1..n} Σ_{k=1..c} (u_ik)^m · ||x_i - v_k||^2

where:

- ``V = {v_1, ..., v_c}`` is the set of fuzzy centroids,
- ``m > 1`` is the **fuzziness parameter** controlling how
  "soft" the partition is (``m = 1`` reduces to K-Means;
  ``m → ∞`` makes every membership equal to ``1 / c``).

The squared distance is typically Euclidean
``||x - v||^2 = Σ_d (x_i,d - v_k,d)^2``; this adapter exposes
only the Euclidean metric to keep the experimental design
narrow.

**Fuzzy centroid** — the centre of mass of cluster ``k``
weighted by ``(u_ik)^m``:

    v_k = [Σ_{i=1..n} (u_ik)^m · x_i] / [Σ_{i=1..n} (u_ik)^m]

Note that this is NOT the arithmetic mean of the cluster
members (that would be the K-Means centroid); the weighting by
``(u_ik)^m`` is what gives the centroid its fuzzy character.

**Membership update** (for Euclidean distance, when
``||x_i - v_k|| > 0`` for every cluster):

    u_ik = 1 / Σ_{j=1..c} ( ||x_i - v_k|| / ||x_i - v_j|| )^(2/(m-1))

The exponent ``2 / (m - 1)`` is strictly positive when
``m > 1``, which is the canonical FCM regime. When
``||x_i - v_k|| = 0`` (the observation coincides with a
centroid), the standard convention is to set
``u_ik = 1`` and ``u_ij = 0`` for ``j ≠ k``; this preserves
the row-sum-to-one constraint and avoids ``0 / 0`` in the
membership update.

**Iterative optimisation**:

1. Initialise the membership matrix ``U`` (randomly, under
   ``random_state`` if provided) so that every row sums to 1.
2. Compute the fuzzy centroids ``v_k`` using ``U`` and the
   weighting ``(u_ik)^m``.
3. Compute the distances ``d_ik = ||x_i - v_k||``.
4. Update ``u_ik`` using the membership formula, treating
   ``d_ik = 0`` as the limit case (full membership).
5. Compute the new objective ``J_m``.
6. Stop when the membership matrix stops changing (relative
   change < ``error`` / ``tol``) or when ``max_iter`` is
   reached.
7. Repeat from step 2 otherwise.

**Hard label** — the cluster assignment most consistent with
the fuzzy membership — is derived as:

    label_i = argmax_k u_ik

Hard labels are NOT the primary output of FCM; the membership
matrix ``U`` is. This adapter writes both into the result
schema so downstream consumers can use either.

**Convergence**: FCM converges monotonically (the objective
``J_m`` is non-increasing across iterations) under the
standard assumptions; the standard convergence check is on
the relative change in either the membership matrix
``||U_new - U_old||`` or the objective
``|J_{new} - J_{old}| / |J_{old}|`` (or both). The adapter
uses the **membership change** as the primary convergence
criterion (matches the canonical ``cmeans`` update in
``scikit-fuzzy``); the **objective change** is recorded as a
diagnostic so callers can inspect both.

Reproducibility
---------------

The adapter uses ``numpy.random.default_rng(random_state)``
to seed the membership-matrix initialisation. With a fixed
``random_state`` (and identical library version + identical
floating-point arithmetic), the resulting membership matrix
``U``, centroids ``V``, objective ``J_m``, hard labels,
convergence behaviour and final ``n_iter`` are deterministic.

Algorithm-specific diagnostics (ML-06 scope)
-------------------------------------------

The adapter records the following FCM-specific diagnostics in
:attr:`ClusterResult.extra`:

- ``n_clusters`` (int) — number of fuzzy clusters ``c``.
- ``fuzziness`` (float) — ``m``.
- ``max_iter`` (int) — maximum number of iterations.
- ``error`` (float) — convergence threshold on membership
  change.
- ``random_state`` (int or None).
- ``converged`` (bool) — whether the algorithm converged
  within ``max_iter``.
- ``n_iter`` (int) — number of iterations actually run.
- ``final_objective`` (float) — value of ``J_m`` at the end
  of the iteration.
- ``objective_history_first_5`` / ``_last_5`` / ``_length`` —
  coarse objective-trace summary (recorded so the
  experiment log can show convergence behaviour without
  flooding the JSON).
- ``centroid_shape`` (list) — ``(c, p)``.
- ``membership_shape`` (list) — ``(n, c)``.
- ``membership_min`` / ``membership_max`` (float) — global
  range of membership values.
- ``membership_row_sum_min`` / ``_max`` (float) — verify that
  every row sums to 1.
- ``cluster_sizes`` (dict label → count) — derived from hard
  labels (NOT from the soft membership).
- ``membership_confidence_min`` / ``_max`` / ``_mean``
  (float) — max membership per row, used as a confidence
  summary of the soft partition (high values mean the
  observation clearly belongs to one cluster; low values mean
  the observation is on a cluster boundary).

These diagnostics are **diagnostic-only** in ML-06; EPIC-07
will own the controlled sweep over ``c`` and ``m`` and
EPIC-08 will own formal evaluation. The adapter does NOT use
the objective / confidence diagnostics to declare a "best"
configuration.

Why a custom FCM (not ``scikit-fuzzy``)?
---------------------------------------

The repository currently does not declare ``scikit-fuzzy``
(``skfuzzy``) as a dependency. AGENTS.md §5 forbids adding a
new dependency without an ADR. The custom implementation:

- is built entirely on ``numpy`` (a dependency already in the
  project),
- reproduces the canonical Bezdek FCM update rule
  (membership + centroid + iterative optimisation),
- is deterministic under a fixed ``random_state``,
- supports the full diagnostic surface required by ML-06,
- does not expand the dependency surface, and
- is small enough to be fully reviewed by a reader.

If a future ADR promotes ``skfuzzy`` as a research dependency,
the adapter can be re-pointed at ``skfuzzy.cmeans``; the
public surface (``FuzzyCMeansAdapter``) and the
``ClusterResult`` schema would not change.

Randomness note
---------------

If ``random_state`` is ``None``, the membership matrix
initialisation is non-reproducible. This is **truthfully**
recorded: ``supports_random_state()`` returns ``True`` so the
runner knows a seed *can* be consumed; ``random_seed_used``
records the actual seed that was used (or ``None`` if the
caller did not supply one). The reproducibility tests in
``tests/test_ml06_fuzzy.py`` always pass an explicit seed.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from customer_segmentation.clustering.base import BaseClusterAlgorithm, ClusterAlgorithmError
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import AlgorithmFamily, ClusterResult

__all__ = [
    "FuzzyCMeansAdapter",
    "DEFAULT_N_CLUSTERS",
    "DEFAULT_M",
    "DEFAULT_MAX_ITER",
    "DEFAULT_ERROR",
    "MIN_N_CLUSTERS",
    "MIN_M",
    "MIN_MAX_ITER",
    "MIN_ERROR",
]


# ---------------------------------------------------------------------------
# Working defaults (mirror configs/clustering.yaml algorithms.fuzzy_cmeans.*).
# These are *working* defaults (TECHNICALLY_IMPLEMENTED), not final
# approved methodology. EPIC-07 will run the controlled sweep over
# n_clusters (c) and fuzziness (m).
# ---------------------------------------------------------------------------

DEFAULT_N_CLUSTERS: int = 4
DEFAULT_M: float = 2.0
DEFAULT_MAX_ITER: int = 300
DEFAULT_ERROR: float = 1e-4

# Hyperparameter bounds (per ML-06 task contract).
MIN_N_CLUSTERS: int = 1  # FCM allows c >= 1; we use 1 as the lower bound.
MIN_M: float = 1.0 + 1e-6  # strictly > 1 in theory; we accept m >= 1+epsilon.
MIN_MAX_ITER: int = 1
MIN_ERROR: float = 1e-12  # must be strictly positive.

# Internal numerical constant — exponent in the membership update.
_EPSILON: float = 1e-12


@AlgorithmRegistry.register("fuzzy_cmeans")
class FuzzyCMeansAdapter(BaseClusterAlgorithm):
    """Fuzzy C-Means clustering adapter for ML-01 framework.

    The adapter wraps the canonical Bezdek / Dunn Fuzzy C-Means
    update (membership + centroid + iterative optimisation) on
    top of ``numpy``. It does NOT transform, scale, or impute
    the input — that is FE-06's job.

    Attributes
    ----------
    name : str
        Stable, lowercase identifier (``"fuzzy_cmeans"``). Set by
        the registry on registration.
    version : str
        ``"custom_v1"`` — the implementation is a custom
        ``numpy``-based FCM core (no external FCM library).
    family : str
        :attr:`AlgorithmFamily.FUZZY` — FCM produces a soft
        membership matrix and a derived hard label.

    Parameters
    ----------
    n_clusters : int
        Number of fuzzy clusters ``c``. Must be ``>= 1`` and
        ``<= n_samples``. Working default **not set here** —
        ML-06 must always receive an explicit ``n_clusters`` from
        the caller / EPIC-07 sweep.
    m : float
        Fuzziness parameter. Must be ``> 1`` (canonical FCM
        regime). ``m = 1`` reduces to K-Means (in the limit);
        ``m → ∞`` makes every membership uniform ``1 / c``.
        Default: ``2.0``.
    max_iter : int
        Maximum number of FCM iterations. Default: ``300``.
    error : float
        Convergence threshold on the membership matrix norm
        (``max |u_ik_new - u_ik_old|``). Iteration stops when
        the change falls below this threshold. Default:
        ``1e-4``.
    random_state : int or None
        Seed for the membership-matrix initialisation.
        ``None`` means non-reproducible initialisation. The
        framework may pass an explicit seed via
        ``resolve_random_seed``; with a fixed seed, the adapter
        is fully deterministic for a given input / library
        version.

    Notes
    -----
    - The adapter does NOT mutate the input matrix ``X``.
    - The adapter records the full membership matrix in
      :attr:`ClusterResult.soft_membership`; the framework's
      artifact writer emits ``Membership_k`` columns in both
      the cluster_labels parquet and a separate
      ``algorithm_output`` parquet.
    - The hard label is derived as ``argmax`` over the
      membership matrix (``label_i = argmax_k u_ik``); the
      hard label alone does NOT capture the soft membership
      and MUST NOT be used in place of ``U`` for downstream
      consumer that needs soft output.
    - The adapter does NOT compute silhouette, Davies-Bouldin,
      or Calinski-Harabasz indices (out of scope).
    - The adapter DOES consume ``random_state``; the runner
      injects the framework seed.
    - The custom implementation does NOT use ``scikit-fuzzy``;
      see the module docstring for the rationale.

    Hard cluster assignment versus membership
    ---------------------------------------

    Hard cluster assignment (which every customer belongs to
    "exactly one cluster") is a *lossy projection* of the
    fuzzy membership. Two customers assigned to the same hard
    label may have very different membership profiles
    (e.g. one with ``u_i = [0.95, 0.05, 0, 0]`` versus one
    with ``u_i = [0.40, 0.30, 0.20, 0.10]``). Downstream
    consumers that need the soft information must read from
    ``algorithm_output_*.parquet`` / the
    ``Membership_k`` columns of ``cluster_labels_*.parquet``.
    """

    name: str = "fuzzy_cmeans"
    version: str = "custom_v1"
    family: str = AlgorithmFamily.FUZZY

    def __init__(
        self,
        n_clusters: int,
        *,
        m: float = DEFAULT_M,
        max_iter: int = DEFAULT_MAX_ITER,
        error: float = DEFAULT_ERROR,
        random_state: int | None = None,
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
        if not isinstance(m, (int, float)):
            raise ClusterAlgorithmError(f"m must be a number; got {type(m).__name__}.")
        if float(m) <= 1.0:
            # m > 1 is the canonical FCM regime. We reject m <= 1
            # because (a) m = 1 reduces to K-Means (out of FCM
            # scope) and (b) the membership-update exponent
            # 2 / (m - 1) is undefined at m = 1.
            raise ClusterAlgorithmError(f"m (fuzziness) must be > 1; got {m}.")
        if not isinstance(max_iter, (int, np.integer)) or int(max_iter) < MIN_MAX_ITER:
            raise ClusterAlgorithmError(f"max_iter must be a positive integer; got {max_iter!r}.")
        if not isinstance(error, (int, float)) or float(error) <= 0:
            raise ClusterAlgorithmError(
                f"error (convergence threshold) must be a positive number; got {error!r}."
            )
        if random_state is not None and not isinstance(random_state, (int, np.integer)):
            raise ClusterAlgorithmError(
                f"random_state must be an integer or None; got "
                f"{type(random_state).__name__}={random_state!r}."
            )

        self.n_clusters = int(n_clusters)
        self.m = float(m)
        self.max_iter = int(max_iter)
        self.error = float(error)
        self.random_state = None if random_state is None else int(random_state)

        # Fitted state (populated by fit()).
        self._centroids: np.ndarray | None = None
        self._membership: np.ndarray | None = None
        self._n_iter: int = 0
        self._converged: bool = False
        self._final_objective: float = float("nan")
        self._objective_history: list[float] = []

    # ----- Algorithm interface -----
    def fit(self, X: np.ndarray) -> ClusterResult:
        """Fit Fuzzy C-Means on the feature matrix.

        Parameters
        ----------
        X : numpy.ndarray
            Numeric feature matrix of shape ``(n_samples,
            n_features)``. MUST be the matrix delivered by the
            framework (``matrix_df.to_numpy(dtype=np.float64,
            copy=False)``). MUST NOT contain identifiers
            (validated upstream by
            :func:`validate_clustering_matrix`).

        Returns
        -------
        ClusterResult
            Hard cluster labels (derived from
            ``argmax(U)``), full fuzzy membership matrix in
            :attr:`ClusterResult.soft_membership`, and FCM-
            specific diagnostics in
            :attr:`ClusterResult.extra`.

        Raises
        ------
        ClusterAlgorithmError
            If the input is invalid for FCM (e.g. wrong
            dimensionality, sklearn raises during the
            membership update, ...).
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
        if n_samples < 1:
            raise ClusterAlgorithmError(f"FCM requires n_samples >= 1; got n_samples={n_samples}.")
        if n_features < 1:
            raise ClusterAlgorithmError(
                f"FCM requires n_features >= 1; got n_features={n_features}."
            )
        if self.n_clusters < 1:
            raise ClusterAlgorithmError(
                f"FCM requires n_clusters >= 1; got n_clusters={self.n_clusters}."
            )
        if self.n_clusters > n_samples:
            # FCM in exact arithmetic can technically run with
            # c == n (every observation is its own singleton
            # fuzzy cluster); we reject c > n because the
            # partition would be degenerate. Mirrors sklearn's
            # K-Means constraint.
            raise ClusterAlgorithmError(
                f"n_clusters ({self.n_clusters}) must be <= n_samples " f"({n_samples})."
            )

        # Custom FCM core. Reproducible under a fixed
        # random_state.
        (
            centroids,
            membership,
            n_iter_used,
            converged,
            final_objective,
            objective_history,
        ) = _fcm_core(
            X=X,
            n_clusters=self.n_clusters,
            m=self.m,
            max_iter=self.max_iter,
            error=self.error,
            random_state=self.random_state,
        )

        # Hard label = argmax over membership rows.
        labels_array = np.asarray(membership.argmax(axis=1), dtype=np.int64)
        labels = labels_array

        # Cache the fitted state so callers can read it through
        # get_model().
        self._centroids = centroids
        self._membership = membership
        self._n_iter = n_iter_used
        self._converged = converged
        self._final_objective = final_objective
        self._objective_history = objective_history

        # ---- Diagnostics ----
        # Per-row max membership (cluster confidence summary).
        max_per_row = membership.max(axis=1)
        # Row-sum check (each row must sum to ~1).
        row_sums = membership.sum(axis=1)

        # Cluster sizes derived from hard labels (diagnostic only).
        cluster_sizes: dict[str, int] = {}
        unique_labels, counts = np.unique(labels, return_counts=True)
        for u, c in zip(unique_labels.tolist(), counts.tolist(), strict=True):
            cluster_sizes[str(int(u))] = int(c)

        # Objective trace summary (first 5 / last 5 / length).
        obj_history = objective_history
        first_5 = [float(x) for x in obj_history[:5]]
        last_5 = [float(x) for x in obj_history[-5:]] if obj_history else []

        extra: dict[str, Any] = {
            # Configuration echo.
            "n_clusters": int(self.n_clusters),
            "fuzziness": float(self.m),
            "max_iter": int(self.max_iter),
            "error": float(self.error),
            "random_state": (None if self.random_state is None else int(self.random_state)),
            # Convergence.
            "converged": bool(converged),
            "n_iter": int(n_iter_used),
            # Objective (NOT a clustering quality metric — this is
            # the FCM internal cost, monotonically non-increasing
            # across iterations by construction).
            "final_objective": float(final_objective),
            "objective_history_length": int(len(obj_history)),
            "objective_history_first_5": first_5,
            "objective_history_last_5": last_5,
            # Shapes.
            "centroid_shape": list(centroids.shape),
            "membership_shape": list(membership.shape),
            # Membership integrity.
            "membership_min": float(membership.min()),
            "membership_max": float(membership.max()),
            "membership_row_sum_min": float(row_sums.min()),
            "membership_row_sum_max": float(row_sums.max()),
            # Cluster sizes derived from hard labels.
            "cluster_sizes": cluster_sizes,
            # Confidence summary.
            "membership_confidence_min": float(max_per_row.min()),
            "membership_confidence_max": float(max_per_row.max()),
            "membership_confidence_mean": float(max_per_row.mean()),
        }

        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=int(n_samples),
            n_features=int(n_features),
            cluster_labels=labels,
            n_clusters=int(self.n_clusters),
            # The fuzzy membership matrix (shape (n_samples, c))
            # is the defining characteristic of FCM. The
            # framework's artifact writer emits ``Membership_k``
            # columns in both the labels parquet and a separate
            # ``algorithm_output`` parquet so downstream
            # consumers (EPIC-07/08/09) can use the soft
            # partition directly.
            soft_membership=membership,
            # FCM does not have a dedicated noise label; every
            # observation belongs to every cluster with some
            # degree (>= 0). Leave the default -1 unchanged so
            # the framework does not interpret FCM labels as
            # noise.
            noise_label=-1,
            noise_count=0,
            noise_ratio=0.0,
            supports_random_state=True,
            random_seed_used=self.random_state,
            extra=extra,
            # metrics placeholder stays default (all None) —
            # EPIC-07/08 will populate.
        )

    # ----- Convenience hooks -----
    def get_params(self) -> dict[str, Any]:
        """Return the adapter's hyperparameters as a JSON-friendly dict.

        Override the base default to expose the explicit
        hyperparameters used by FCM. The framework records this
        in the experiment log so future readers can reproduce
        the exact configuration.
        """
        return {
            "n_clusters": self.n_clusters,
            "m": self.m,
            "max_iter": self.max_iter,
            "error": self.error,
            "random_state": self.random_state,
        }

    def get_model(self) -> Any:
        """Return a fitted-model-like object exposing FCM internals.

        Returns a small namespace with the fitted centroids,
        membership matrix, ``n_iter``, ``converged`` flag and
        final objective, or ``None`` if :meth:`fit` has not
        been called yet. This hook lets EPIC-07/08 introspect
        the FCM state (``centroids``, ``membership``,
        ``n_iter``, ``converged``, ``objective``) without
        coupling to the adapter.

        The returned object is intentionally a plain
        ``types.SimpleNamespace`` (not a sklearn estimator)
        because the FCM core is a custom ``numpy``-based
        implementation. Downstream consumers that depend on
        sklearn attributes (``cluster_centers_``,
        ``inertia_``, ...) should not assume they exist;
        EPIC-07/08 will write FCM-specific diagnostics.
        """
        if self._centroids is None or self._membership is None:
            return None
        from types import SimpleNamespace

        return SimpleNamespace(
            algorithm="fuzzy_cmeans",
            n_clusters=self.n_clusters,
            m=self.m,
            centroids=self._centroids,
            membership=self._membership,
            n_iter=self._n_iter,
            converged=self._converged,
            objective=self._final_objective,
            objective_history=list(self._objective_history),
        )

    def supports_random_state(self) -> bool:
        """FCM consumes ``random_state`` (membership-matrix init seed).

        The membership-matrix initialisation uses
        ``numpy.random.default_rng(random_state)`` so a fixed
        seed yields a fully deterministic FCM run (membership
        ``U``, centroids ``V``, objective, hard labels,
        ``n_iter``, ``converged`` flag).

        Returning ``True`` here tells the ML-01 runner to
        inject the framework seed; the recorded
        ``random_seed_used`` then reflects what the adapter
        actually consumed.
        """
        return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fcm_core(
    *,
    X: np.ndarray,
    n_clusters: int,
    m: float,
    max_iter: int,
    error: float,
    random_state: int | None,
) -> tuple[np.ndarray, np.ndarray, int, bool, float, list[float]]:
    """Run the canonical Bezdek / Dunn Fuzzy C-Means iteration.

    Returns
    -------
    centroids : ndarray of shape (n_clusters, n_features)
        Final fuzzy centroids.
    membership : ndarray of shape (n_samples, n_clusters)
        Final fuzzy membership matrix; rows sum to ~1.
    n_iter : int
        Number of iterations actually executed.
    converged : bool
        True iff the membership change fell below ``error``
        within ``max_iter``.
    final_objective : float
        Value of the FCM objective ``J_m`` at the end.
    objective_history : list of float
        ``J_m`` after each iteration (length ``n_iter``).
    """
    n_samples, n_features = X.shape

    # ---- Initialise membership matrix U ----
    # Random Dirichlet draws (one per observation) yield a
    # row-stochastic matrix (rows sum to 1) and produce
    # non-trivial fuzzy partitions. With a fixed ``random_state``
    # the initialisation is fully reproducible.
    rng = np.random.default_rng(random_state)
    # ``rng.dirichlet(alpha=np.ones(n_clusters))`` returns an
    # (n_clusters,) sample; we vectorise across all rows so the
    # resulting matrix has shape (n_samples, n_clusters) and every
    # row sums to 1 in exact arithmetic.
    membership = rng.dirichlet(alpha=np.ones(n_clusters), size=n_samples).astype(np.float64)
    # Defensive: clip into [0, 1] and renormalise so numerical
    # drift in the Dirichlet sampler does not violate the row-sum
    # constraint (especially under m -> 1).
    membership = np.clip(membership, 0.0, 1.0)
    membership = membership / membership.sum(axis=1, keepdims=True)

    objective_history: list[float] = []
    converged = False
    n_iter_used = 0
    final_objective = float("nan")
    centroids = np.zeros((n_clusters, n_features), dtype=np.float64)

    # Pre-compute the membership-update exponent (constant per
    # iteration set).
    exponent = 2.0 / (m - 1.0)

    for it in range(int(max_iter)):
        n_iter_used = it + 1
        # ---- Step 1: compute fuzzy centroids ----
        # v_k = sum_i u_ik^m x_i / sum_i u_ik^m
        membership_m = np.power(membership, m)  # shape (n_samples, c)
        denom = membership_m.sum(axis=0)  # shape (c,)
        # Avoid 0/0 when an entire cluster is empty (u_ik = 0 for
        # all i): use a small positive floor on denom and let the
        # next iteration redistribute the memberships. This is the
        # canonical Bezdek safeguard for empty clusters.
        denom_safe = np.where(denom > _EPSILON, denom, _EPSILON)
        centroids = (membership_m.T @ X) / denom_safe[:, None]

        # ---- Step 2: compute distances d_ik = ||x_i - v_k|| ----
        # Squared Euclidean distance, vectorised:
        # ||x_i - v_k||^2 = ||x_i||^2 - 2 x_i . v_k + ||v_k||^2
        x_sq = (X * X).sum(axis=1)  # shape (n_samples,)
        v_sq = (centroids * centroids).sum(axis=1)  # shape (c,)
        dist_sq = x_sq[:, None] - 2.0 * (X @ centroids.T) + v_sq[None, :]
        # Clip negative distances to 0 (caused by floating-point
        # rounding when x_i and v_k coincide numerically).
        dist_sq = np.clip(dist_sq, 0.0, None)
        dist = np.sqrt(dist_sq)

        # ---- Step 3: compute the new objective J_m ----
        # J_m = Σ_i Σ_k u_ik^m ||x_i - v_k||^2
        objective_value = float((membership_m * dist_sq).sum())
        objective_history.append(objective_value)

        # ---- Step 4: update the membership matrix ----
        # Handle the limit case where an observation coincides
        # with a centroid (d_ik = 0 for some k).
        # The canonical Bezdek update is:
        #     u_ik = 1 / Σ_j (d_ik / d_ij)^(2/(m-1))
        # which can be rewritten as:
        #     u_ik = d_ik^(-p) / Σ_j d_ij^(-p)
        # where ``p = 2/(m-1) > 0`` (canonical FCM regime).
        # The reformulation avoids per-row normalisation of the
        # inner ``d_ik^p`` ratio and is numerically stable as long
        # as d_ik > 0 (the limit case d_ik = 0 is handled below).
        # Vectorised form: numerator = d^(-p), denominator = sum
        # over j.
        with np.errstate(divide="ignore", invalid="ignore"):
            d_neg_pow = np.where(dist > _EPSILON, np.power(dist, -exponent), np.inf)
            # Replace inf with neutral 1 / c so the row still sums to
            # ~1 (defensive only — we overwrite zero-distance rows
            # below).
            d_neg_pow_safe = np.where(np.isfinite(d_neg_pow), d_neg_pow, 1.0 / n_clusters)
            denom_update = d_neg_pow_safe.sum(axis=1, keepdims=True)
            denom_update_safe = np.where(denom_update > _EPSILON, denom_update, 1.0)
            new_membership = d_neg_pow_safe / denom_update_safe
        new_membership = np.clip(new_membership, 0.0, 1.0)
        # Zero-distance handling: for any observation i where
        # d_ik = 0 for some k, set u_ik = 1 and u_ij = 0 for
        # j != k. Iterate over the rows where any distance is
        # ~0 to find the first such cluster per row.
        zero_mask = dist <= _EPSILON
        if zero_mask.any():
            # For each row, pick the first column where dist == 0
            # (there may be multiple if two centroids coincide
            # numerically; the first is chosen deterministically).
            row_has_zero = zero_mask.any(axis=1)
            for i in np.where(row_has_zero)[0]:
                first_zero_k = int(np.argmax(zero_mask[i]))
                new_row = np.zeros(n_clusters, dtype=np.float64)
                new_row[first_zero_k] = 1.0
                new_membership[i] = new_row

        # Renormalise so every row sums to 1 in exact arithmetic.
        row_sums = new_membership.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums > _EPSILON, row_sums, 1.0)
        new_membership = new_membership / row_sums

        # ---- Step 5: convergence check ----
        # Membership change (max-norm):
        membership_change = float(np.abs(new_membership - membership).max())
        membership = new_membership

        if membership_change < float(error):
            converged = True
            break

    # Final centroids (recompute using the converged membership
    # so the returned ``centroids`` matches the final
    # ``membership``). The final objective is the value
    # corresponding to these recomputed centroids (NOT the last
    # entry in ``objective_history``, which was computed using
    # the centroid values that were current at the start of the
    # last iteration).
    membership_m = np.power(membership, m)
    denom = membership_m.sum(axis=0)
    denom_safe = np.where(denom > _EPSILON, denom, _EPSILON)
    centroids = (membership_m.T @ X) / denom_safe[:, None]

    # Final objective.
    x_sq = (X * X).sum(axis=1)
    v_sq = (centroids * centroids).sum(axis=1)
    dist_sq = x_sq[:, None] - 2.0 * (X @ centroids.T) + v_sq[None, :]
    dist_sq = np.clip(dist_sq, 0.0, None)
    final_objective = float((membership_m * dist_sq).sum())

    return (
        centroids.astype(np.float64, copy=False),
        membership.astype(np.float64, copy=False),
        int(n_iter_used),
        bool(converged),
        float(final_objective),
        objective_history,
    )
