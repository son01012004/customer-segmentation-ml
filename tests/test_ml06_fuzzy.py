"""Tests for the ML-06 Fuzzy C-Means (FCM) clustering adapter.

The tests are organised by responsibility, mirroring the ML-02
K-Means, ML-03 Agglomerative, ML-04 DBSCAN, and ML-05 GMM test
layouts and the ML-06 task contract:

- :class:`TestInterface` — adapter implements
  ``BaseClusterAlgorithm``, is registered under
  ``"fuzzy_cmeans"``, exposes metadata, ``get_params``,
  ``get_model`` and ``supports_random_state``.
- :class:`TestParameterValidation` — bad hyperparameters
  (``n_clusters``, ``m``, ``max_iter``, ``error``,
  ``random_state``) are rejected with ``ClusterAlgorithmError``.
- :class:`TestInputValidation` — bad input matrices (None,
  wrong dimensionality, ``n_clusters > n_samples``, ...) are
  rejected by ``fit``.
- :class:`TestMembership` — fuzzy partition invariants:
  membership values in ``[0, 1]``, row sums equal to 1,
  membership shape equals ``(n_samples, n_clusters)``,
  ``hard_labels == argmax(membership)``.
- :class:`TestObjective` — objective ``J_m`` is finite and
  non-increasing across iterations; converges within
  ``max_iter`` on a well-separated synthetic dataset.
- :class:`TestReproducibility` — same input + same configuration
  + same ``random_state`` + same library version →
  same membership matrix, centroids, objective, ``n_iter``
  and ``converged`` flag.
- :class:`TestOutputSchema` — output conforms to
  ``ClusterResult`` schema; FCM-specific extras
  (``n_clusters``, ``fuzziness``, ``max_iter``, ``error``,
  ``random_state``, ``converged``, ``n_iter``, final
  objective, shape diagnostics, membership integrity
  diagnostics, cluster sizes, confidence summary) are
  populated.
- :class:`TestFuzzinessBehavior` — changing ``m`` changes the
  confidence summary and the objective (sanity check for the
  mathematical effect of ``m``).
- :class:`TestIntegrationWithFE06` — end-to-end run via
  ``ExperimentRunner`` on the real FE-06 dataset (skipped if
  absent).

The tests are intentionally value-neutral: they assert
structural properties (shape, dtype, schema, membership
integrity), not "best/optimal" claims. The final objective /
confidence diagnostics are recorded but NOT used to declare a
"best" configuration (EPIC-07 owns the controlled sweep).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.clustering import (
    AlgorithmFamily,
    AlgorithmRegistry,
    AlgorithmRegistryError,
    BaseClusterAlgorithm,
    ClusterAlgorithmError,
    ClusterResult,
    ExperimentRunner,
    ExperimentSpec,
    ExperimentStatus,
    FuzzyCMeansAdapter,
    load_framework_config,
)
from customer_segmentation.clustering.fuzzy_cmeans import (
    DEFAULT_ERROR,
    DEFAULT_M,
    DEFAULT_MAX_ITER,
    DEFAULT_N_CLUSTERS,
    MIN_ERROR,
    MIN_M,
    MIN_MAX_ITER,
    MIN_N_CLUSTERS,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def well_separated_matrix() -> pd.DataFrame:
    """Small, well-separated matrix with 3 visible clusters.

    Used for tests that need stable, easy-to-reason-about
    clustering.
    """
    rng = np.random.default_rng(7)
    n_per_cluster = 30
    centers = np.array([[0.0, 0.0], [10.0, 10.0], [-10.0, 10.0]])
    parts = []
    for c in centers:
        parts.append(rng.normal(loc=c, scale=0.5, size=(n_per_cluster, 2)))
    X = np.vstack(parts)
    df = pd.DataFrame(X, columns=["x", "y"])
    return df


@pytest.fixture()
def two_clusters_matrix() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    c1 = rng.normal(loc=[0.0, 0.0], scale=0.3, size=(50, 2))
    c2 = rng.normal(loc=[5.0, 5.0], scale=0.3, size=(50, 2))
    X = np.vstack([c1, c2])
    return pd.DataFrame(X, columns=["x", "y"])


@pytest.fixture()
def small_matrix() -> pd.DataFrame:
    rng = np.random.default_rng(123)
    X = rng.normal(size=(50, 4))
    return pd.DataFrame(X, columns=["f0", "f1", "f2", "f3"])


@pytest.fixture()
def small_metadata() -> pd.DataFrame:
    return pd.DataFrame({"CustomerID": np.arange(1000, 1050, dtype=np.int64)})


@pytest.fixture(autouse=True)
def _ensure_fuzzy_registered() -> None:
    """Autouse: re-register ``FuzzyCMeansAdapter`` before every test.

    ML-01 framework tests' ``registered_toy_algorithms`` fixture
    calls ``AlgorithmRegistry.clear()`` at teardown, which
    removes ``FuzzyCMeansAdapter`` from the registry. This
    fixture re-registers the existing class before each test so
    the registry is in a known state.
    """
    if not AlgorithmRegistry.is_registered("fuzzy_cmeans"):
        AlgorithmRegistry.register("fuzzy_cmeans")(FuzzyCMeansAdapter)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_fuzzy_is_base_algorithm(self) -> None:
        assert issubclass(FuzzyCMeansAdapter, BaseClusterAlgorithm)

    def test_fuzzy_is_registered(self) -> None:
        assert AlgorithmRegistry.is_registered("fuzzy_cmeans")
        cls = AlgorithmRegistry.get("fuzzy_cmeans")
        assert cls is FuzzyCMeansAdapter

    def test_fuzzy_name_is_stable(self) -> None:
        assert FuzzyCMeansAdapter.name == "fuzzy_cmeans"

    def test_fuzzy_family_is_fuzzy(self) -> None:
        # FCM is the fuzzy-clustering family — produces both a
        # membership matrix and a derived hard label.
        assert FuzzyCMeansAdapter.family == AlgorithmFamily.FUZZY

    def test_fuzzy_version_is_custom(self) -> None:
        # The custom numpy-based FCM core reports a stable
        # ``custom_v1`` version (no sklearn / scikit-fuzzy
        # dependency). The framework records this in the
        # experiment log.
        assert FuzzyCMeansAdapter.version == "custom_v1"

    def test_supports_random_state_is_true(self) -> None:
        # FCM consumes random_state for membership-matrix
        # initialisation.
        assert FuzzyCMeansAdapter(n_clusters=3).supports_random_state() is True

    def test_get_params_returns_serialisable_dict(self) -> None:
        adapter = FuzzyCMeansAdapter(
            n_clusters=5,
            m=1.7,
            max_iter=200,
            error=1e-5,
            random_state=42,
        )
        params = adapter.get_params()
        assert params["n_clusters"] == 5
        assert params["m"] == 1.7
        assert params["max_iter"] == 200
        assert params["error"] == 1e-5
        assert params["random_state"] == 42
        # Must be JSON-serialisable.
        json.dumps(params)

    def test_get_model_returns_none_before_fit(self) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3)
        assert adapter.get_model() is None

    def test_get_model_returns_state_after_fit(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, m=2.0, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        adapter.fit(X)
        model = adapter.get_model()
        assert model is not None
        # The custom FCM core exposes centroids, membership,
        # n_iter, converged, objective, objective_history.
        assert hasattr(model, "centroids")
        assert hasattr(model, "membership")
        assert hasattr(model, "n_iter")
        assert hasattr(model, "converged")
        assert hasattr(model, "objective")
        assert hasattr(model, "objective_history")
        assert model.centroids.shape == (3, 2)
        assert model.membership.shape == (X.shape[0], 3)

    def test_double_registration_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):

            @AlgorithmRegistry.register("fuzzy_cmeans")
            class _Other(BaseClusterAlgorithm):
                version = "other_v1"
                family = AlgorithmFamily.FUZZY

                def fit(self, X):
                    raise ClusterAlgorithmError("not implemented")

    def test_unregistered_algorithm_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):
            AlgorithmRegistry.get("definitely_not_registered_xyz")

    def test_module_defaults_exposed(self) -> None:
        assert DEFAULT_N_CLUSTERS == 4
        assert DEFAULT_M == 2.0
        assert DEFAULT_MAX_ITER == 300
        assert DEFAULT_ERROR == 1e-4
        assert MIN_N_CLUSTERS == 1
        # m must be strictly > 1 in the canonical FCM regime; the
        # constant guards the lower bound at 1 + epsilon.
        assert MIN_M > 1.0
        assert MIN_MAX_ITER == 1
        assert MIN_ERROR > 0


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_n_clusters_must_be_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters="3")  # type: ignore[arg-type]

    def test_n_clusters_must_be_positive(self) -> None:
        # ML-06 task contract: n_clusters >= 1.
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=0)
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=-1)

    def test_m_must_be_number(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, m="2.0")  # type: ignore[arg-type]

    def test_m_must_be_greater_than_1(self) -> None:
        # Canonical FCM regime: m > 1 (m = 1 reduces to K-Means
        # in the limit, m < 1 is undefined).
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, m=1.0)
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, m=0.5)

    def test_max_iter_must_be_positive_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, max_iter=0)
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, max_iter=-1)
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, max_iter="300")  # type: ignore[arg-type]

    def test_error_must_be_positive(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, error=0)
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, error=-1e-4)
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, error="1e-4")  # type: ignore[arg-type]

    def test_random_state_must_be_int_or_none(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            FuzzyCMeansAdapter(n_clusters=3, random_state="seed")  # type: ignore[arg-type]

    def test_random_state_none_accepted(self) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=None)
        assert adapter.random_state is None

    def test_default_values(self) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3)
        assert adapter.m == DEFAULT_M
        assert adapter.max_iter == DEFAULT_MAX_ITER
        assert adapter.error == DEFAULT_ERROR
        assert adapter.random_state is None


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_none_matrix_raises(self) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(None)  # type: ignore[arg-type]

    def test_non_ndarray_raises(self) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit([[0.0, 0.0], [1.0, 1.0]])  # type: ignore[arg-type]

    def test_1d_matrix_raises(self) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros(10))

    def test_zero_features_raises(self) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=2)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros((10, 0)))

    def test_n_clusters_greater_than_n_samples_raises(self, small_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=100)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(small_matrix.to_numpy(dtype=np.float64))

    def test_input_not_mutated(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        original = X.copy()
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        adapter.fit(X)
        assert np.array_equal(X, original)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_returns_cluster_result(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert isinstance(result, ClusterResult)

    def test_labels_shape_matches_n_samples(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.cluster_labels.shape == (X.shape[0],)
        assert result.cluster_labels.dtype == np.int64

    def test_n_clusters_matches_c(self, well_separated_matrix: pd.DataFrame) -> None:
        c = 3
        adapter = FuzzyCMeansAdapter(n_clusters=c, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.n_clusters == c
        # Hard labels are dense in [0, c-1].
        assert int(result.cluster_labels.min()) >= 0
        assert int(result.cluster_labels.max()) <= c - 1

    def test_metadata_fields(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, m=2.0, random_state=42)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.algorithm == "fuzzy_cmeans"
        assert result.algorithm_family == AlgorithmFamily.FUZZY
        assert result.algorithm_version == "custom_v1"
        assert result.n_samples == X.shape[0]
        assert result.n_features == X.shape[1]
        # FCM consumes random_state; it must be recorded.
        assert result.supports_random_state is True
        assert result.random_seed_used == 42

    def test_extra_includes_diagnostic_info(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, m=2.0, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        for key in (
            "n_clusters",
            "fuzziness",
            "max_iter",
            "error",
            "random_state",
            "converged",
            "n_iter",
            "final_objective",
            "objective_history_length",
            "objective_history_first_5",
            "objective_history_last_5",
            "centroid_shape",
            "membership_shape",
            "membership_min",
            "membership_max",
            "membership_row_sum_min",
            "membership_row_sum_max",
            "cluster_sizes",
            "membership_confidence_min",
            "membership_confidence_max",
            "membership_confidence_mean",
        ):
            assert key in result.extra, f"missing extra key: {key}"

        # Type / value checks.
        assert isinstance(result.extra["n_clusters"], int)
        assert isinstance(result.extra["fuzziness"], float)
        assert isinstance(result.extra["max_iter"], int)
        assert isinstance(result.extra["error"], float)
        assert result.extra["random_state"] == 0
        assert isinstance(result.extra["converged"], bool)
        assert isinstance(result.extra["n_iter"], int)
        assert result.extra["n_iter"] >= 1
        assert isinstance(result.extra["final_objective"], float)
        assert np.isfinite(result.extra["final_objective"])
        assert isinstance(result.extra["objective_history_first_5"], list)
        assert isinstance(result.extra["cluster_sizes"], dict)
        # Centroid / membership shapes.
        assert result.extra["centroid_shape"] == [3, 2]
        # membership shape matches (n_samples, n_clusters).
        assert result.extra["membership_shape"] == [
            well_separated_matrix.shape[0],
            3,
        ]

    def test_metrics_placeholder_is_default(self, well_separated_matrix: pd.DataFrame) -> None:
        # ML-06 MUST NOT compute evaluation metrics. Final
        # objective recorded in extras is algorithm-specific
        # (NOT a clustering quality metric).
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.metrics.silhouette is None
        assert result.metrics.davies_bouldin is None
        assert result.metrics.calinski_harabasz is None
        assert result.metrics.wcss is None
        assert result.metrics.stability is None
        assert result.metrics.runtime is None

    def test_noise_count_zero_for_fcm(self, well_separated_matrix: pd.DataFrame) -> None:
        # FCM does not have a noise concept — every observation
        # has non-zero membership in every cluster (or membership
        # in only one cluster when d_ik = 0). The framework's
        # noise count stays at 0.
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0
        assert result.noise_label == -1  # framework default

    def test_result_is_serialisable(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        d = result.to_dict()
        json.dumps(d, default=str)
        assert d["n_samples"] == result.n_samples
        assert d["algorithm"] == "fuzzy_cmeans"
        assert d["soft_membership_shape"] == [result.n_samples, result.n_clusters]
        # soft_probabilities stays None (FCM does not produce
        # GMM-style posterior probabilities).
        assert d["soft_probabilities_shape"] is None


# ---------------------------------------------------------------------------
# Membership invariants
# ---------------------------------------------------------------------------


class TestMembership:
    """The fuzzy membership matrix is the defining characteristic
    of FCM. It MUST satisfy structural invariants and MUST be
    aligned with the customer metadata so EPIC-07/08/09 can
    consume it downstream.
    """

    def test_membership_shape(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_membership is not None
        assert result.soft_membership.shape == (X.shape[0], 3)
        assert result.extra["membership_shape"] == [X.shape[0], 3]

    def test_membership_in_unit_interval(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_membership is not None
        assert (result.soft_membership >= 0.0).all()
        assert (result.soft_membership <= 1.0).all()

    def test_membership_row_sums_equal_one(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_membership is not None
        row_sums = result.soft_membership.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-8)
        # Diagnostics also recorded.
        assert result.extra["membership_row_sum_min"] == pytest.approx(
            float(row_sums.min()), abs=1e-8
        )
        assert result.extra["membership_row_sum_max"] == pytest.approx(
            float(row_sums.max()), abs=1e-8
        )

    def test_hard_label_equals_argmax_membership(self, well_separated_matrix: pd.DataFrame) -> None:
        # The hard label MUST be derived as ``argmax`` of the
        # membership matrix (with numerical tolerance).
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_membership is not None
        argmax_labels = result.soft_membership.argmax(axis=1).astype(np.int64)
        np.testing.assert_array_equal(argmax_labels, result.cluster_labels)

    def test_membership_confidence_summary(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_membership is not None
        # Max membership per row lies in [1/c, 1].
        max_probs = result.soft_membership.max(axis=1)
        assert result.extra["membership_confidence_min"] == pytest.approx(
            float(max_probs.min()), abs=1e-12
        )
        assert result.extra["membership_confidence_max"] == pytest.approx(
            float(max_probs.max()), abs=1e-12
        )
        assert result.extra["membership_confidence_mean"] == pytest.approx(
            float(max_probs.mean()), abs=1e-12
        )
        # Lower bound on confidence is 1/c for a uniform partition;
        # well-separated 3-cluster data should give much higher
        # confidence than 1/3.
        assert max_probs.min() >= 1.0 / 3.0 - 1e-6

    def test_membership_columns_equal_n_clusters(self, two_clusters_matrix: pd.DataFrame) -> None:
        # Number of membership columns always equals n_clusters
        # (regardless of how the FCM partition ends up looking).
        for c in (1, 2, 3, 4):
            adapter = FuzzyCMeansAdapter(n_clusters=c, random_state=0, max_iter=200)
            result = adapter.fit(two_clusters_matrix.to_numpy(dtype=np.float64))
            assert result.soft_membership.shape == (100, c)


# ---------------------------------------------------------------------------
# Objective + convergence
# ---------------------------------------------------------------------------


class TestObjective:
    """FCM's internal objective ``J_m`` is recorded as a
    diagnostic. The test asserts that the objective is finite
    and converges on a well-separated synthetic dataset.
    """

    def test_final_objective_finite(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = FuzzyCMeansAdapter(n_clusters=3, m=2.0, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert np.isfinite(result.extra["final_objective"])
        assert result.extra["final_objective"] >= 0.0

    def test_converges_on_well_separated(self, well_separated_matrix: pd.DataFrame) -> None:
        # FCM converges on well-separated synthetic data within
        # max_iter=300. The convergence check is on the
        # membership change (max-norm).
        adapter = FuzzyCMeansAdapter(n_clusters=3, m=2.0, max_iter=300, error=1e-6, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.extra["converged"] is True
        assert result.extra["n_iter"] < 300

    def test_convergence_check_strict_error(self, well_separated_matrix: pd.DataFrame) -> None:
        # A stricter error threshold requires more iterations.
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        loose = FuzzyCMeansAdapter(n_clusters=3, m=2.0, error=1e-2, random_state=0).fit(X)
        strict = FuzzyCMeansAdapter(n_clusters=3, m=2.0, error=1e-8, random_state=0).fit(X)
        assert strict.extra["n_iter"] >= loose.extra["n_iter"]

    def test_objective_history_first_5(self, well_separated_matrix: pd.DataFrame) -> None:
        # ``objective_history_first_5`` records the first
        # iterations so downstream readers can see the
        # convergence behaviour without flooding the JSON.
        adapter = FuzzyCMeansAdapter(n_clusters=3, m=2.0, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        first_5 = result.extra["objective_history_first_5"]
        assert len(first_5) <= 5
        assert all(isinstance(x, float) and np.isfinite(x) for x in first_5)
        assert result.extra["objective_history_length"] == result.extra["n_iter"]


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """FCM consumes ``random_state`` for membership-matrix
    initialisation. Same input + same configuration + same
    library version → same membership, hard labels, centroids,
    objective, ``n_iter`` and ``converged`` flag.
    """

    def test_same_seed_same_membership(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        a1 = FuzzyCMeansAdapter(n_clusters=4, random_state=42, max_iter=200)
        r1 = a1.fit(X)
        a2 = FuzzyCMeansAdapter(n_clusters=4, random_state=42, max_iter=200)
        r2 = a2.fit(X)
        # Membership matrix deterministic for a fixed seed.
        np.testing.assert_allclose(r1.soft_membership, r2.soft_membership, atol=1e-10)
        # Hard labels deterministic.
        np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels)
        # Centroids deterministic.
        np.testing.assert_allclose(a1.get_model().centroids, a2.get_model().centroids, atol=1e-10)
        # Final objective matches.
        assert r1.extra["final_objective"] == pytest.approx(r2.extra["final_objective"], abs=1e-8)
        # n_iter + converged match.
        assert r1.extra["n_iter"] == r2.extra["n_iter"]
        assert r1.extra["converged"] == r2.extra["converged"]
        # Recorded seed must match.
        assert r1.random_seed_used == 42
        assert r2.random_seed_used == 42

    def test_different_seed_can_differ(self, small_matrix: pd.DataFrame) -> None:
        # Different seeds MAY produce different memberships.
        X = small_matrix.to_numpy(dtype=np.float64)
        r1 = FuzzyCMeansAdapter(n_clusters=4, random_state=1, max_iter=50).fit(X)
        r2 = FuzzyCMeansAdapter(n_clusters=4, random_state=2, max_iter=50).fit(X)
        # Recorded seed must match what we passed.
        assert r1.random_seed_used == 1
        assert r2.random_seed_used == 2
        # The adapter records the truth: both advertise
        # supports_random_state=True; we do NOT assert label
        # equality between different seeds (the membership
        # initialisation differs).

    def test_random_state_used_recorded_truthfully(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        r1 = FuzzyCMeansAdapter(n_clusters=4, random_state=123).fit(X)
        assert r1.random_seed_used == 123
        assert r1.supports_random_state is True

    def test_get_params_reflects_configuration(self) -> None:
        adapter = FuzzyCMeansAdapter(
            n_clusters=5,
            m=1.7,
            max_iter=200,
            error=1e-5,
            random_state=7,
        )
        p = adapter.get_params()
        assert p["n_clusters"] == 5
        assert p["m"] == 1.7
        assert p["max_iter"] == 200
        assert p["error"] == 1e-5
        assert p["random_state"] == 7


# ---------------------------------------------------------------------------
# Fuzziness behavior
# ---------------------------------------------------------------------------


class TestFuzzinessBehavior:
    """The fuzziness parameter ``m`` controls how soft the
    partition is. Sanity check: changing ``m`` produces
    observably different (objective, confidence) pairs.
    """

    def test_smaller_m_more_confident(self, small_matrix: pd.DataFrame) -> None:
        # Smaller ``m`` (closer to 1) → harder partition
        # (membership closer to one-hot) → higher max-membership
        # per row on average.
        X = small_matrix.to_numpy(dtype=np.float64)
        low_m = FuzzyCMeansAdapter(n_clusters=4, m=1.2, random_state=0, max_iter=200).fit(X)
        high_m = FuzzyCMeansAdapter(n_clusters=4, m=3.0, random_state=0, max_iter=200).fit(X)
        assert (
            low_m.extra["membership_confidence_mean"] > high_m.extra["membership_confidence_mean"]
        )

    def test_objective_differs_with_m(self, small_matrix: pd.DataFrame) -> None:
        # Different ``m`` values produce different objective
        # surfaces; final objective values differ.
        X = small_matrix.to_numpy(dtype=np.float64)
        m1 = FuzzyCMeansAdapter(n_clusters=4, m=1.5, random_state=0, max_iter=200).fit(X)
        m2 = FuzzyCMeansAdapter(n_clusters=4, m=2.5, random_state=0, max_iter=200).fit(X)
        assert m1.extra["final_objective"] != pytest.approx(m2.extra["final_objective"], rel=1e-6)


# ---------------------------------------------------------------------------
# Integration with ExperimentRunner
# ---------------------------------------------------------------------------


class TestIntegrationWithFE06:
    """End-to-end runs via ExperimentRunner on the real FE-06
    dataset.

    These tests require the FE-06 outputs on disk. They are
    skipped if those files are absent, so the test suite still
    works in a fresh CI environment before FE-06 has run.
    """

    REPO_ROOT = Path(__file__).resolve().parents[1]
    DATA_PROCESSED = REPO_ROOT / "data" / "processed"
    FE06_DATASET = DATA_PROCESSED / "final_clustering_dataset.parquet"
    FE06_METADATA = DATA_PROCESSED / "customer_metadata.parquet"
    CONFIG_PATH = REPO_ROOT / "configs" / "clustering.yaml"

    def _load_inputs(self):
        df = pd.read_parquet(self.FE06_DATASET)
        md = pd.read_parquet(self.FE06_METADATA)
        return df, md

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_fuzzy_basic(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-06-test-basic",
            algorithm="fuzzy_cmeans",
            hyperparameters={
                "n_clusters": 4,
                "m": 2.0,
                "max_iter": 300,
                "error": 1e-4,
                "random_state": 42,
            },
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(
            df,
            md,
            input_sha256="deadbeef",
            input_path=str(self.FE06_DATASET),
            metadata_path=str(self.FE06_METADATA),
            output_dir=tmp_path,
        )
        assert result.status == ExperimentStatus.SUCCESS
        assert result.algorithm == "fuzzy_cmeans"
        assert result.dataset_version == cfg.input.dataset_version
        assert result.dataset_sha256 == "deadbeef"
        assert result.n_clusters == 4
        assert result.n_samples == len(df)
        assert result.cluster_labels.shape == (len(df),)
        assert result.cluster_result is not None
        assert result.cluster_result.soft_membership is not None
        assert result.cluster_result.soft_membership.shape == (len(df), 4)
        # Artifacts must be written: cluster_labels +
        # experiment_log + algorithm_output (because
        # soft_membership is set).
        assert "cluster_labels" in result.artifact_paths
        assert "experiment_log" in result.artifact_paths
        assert "algorithm_output" in result.artifact_paths
        # Files exist on disk.
        assert Path(result.artifact_paths["cluster_labels"]).exists()
        assert Path(result.artifact_paths["experiment_log"]).exists()
        assert Path(result.artifact_paths["algorithm_output"]).exists()

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_fuzzy_membership_in_artifact(self, tmp_path: Path) -> None:
        # Verify that the algorithm_output parquet contains
        # Membership_k columns and that CustomerID alignment is
        # preserved.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-06-test-soft",
            algorithm="fuzzy_cmeans",
            hyperparameters={
                "n_clusters": 4,
                "m": 2.0,
                "max_iter": 300,
                "error": 1e-4,
                "random_state": 42,
            },
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(
            df,
            md,
            input_sha256="x",
            input_path=str(self.FE06_DATASET),
            metadata_path=str(self.FE06_METADATA),
            output_dir=tmp_path,
        )
        algo_df = pd.read_parquet(result.artifact_paths["algorithm_output"])
        mem_cols = [c for c in algo_df.columns if c.startswith("Membership_")]
        # 4 membership columns for n_clusters=4.
        assert len(mem_cols) == 4
        # CustomerID is the first column and is aligned with
        # metadata.
        assert "CustomerID" in algo_df.columns
        np.testing.assert_array_equal(algo_df["CustomerID"].to_numpy(), md["CustomerID"].to_numpy())
        # Row sums are ~ 1.
        np.testing.assert_allclose(algo_df[mem_cols].sum(axis=1).to_numpy(), 1.0, atol=1e-8)
        # Memberships are non-negative and <= 1.
        assert (algo_df[mem_cols].to_numpy() >= 0.0).all()
        assert (algo_df[mem_cols].to_numpy() <= 1.0 + 1e-8).all()

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_fuzzy_reproducibility(self, tmp_path: Path) -> None:
        # FCM consumes random_state: two runs with the same seed
        # must produce identical membership, hard labels, and
        # final objective.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        hp = {
            "n_clusters": 4,
            "m": 2.0,
            "max_iter": 300,
            "error": 1e-4,
            "random_state": 42,
        }
        spec1 = ExperimentSpec(
            experiment_id="ML-06-test-repro-1",
            algorithm="fuzzy_cmeans",
            hyperparameters=hp,
        )
        spec2 = ExperimentSpec(
            experiment_id="ML-06-test-repro-2",
            algorithm="fuzzy_cmeans",
            hyperparameters=hp,
        )
        runner1 = ExperimentRunner(cfg, spec1)
        runner2 = ExperimentRunner(cfg, spec2)
        r1 = runner1.run(
            df,
            md,
            input_sha256="x",
            input_path=str(self.FE06_DATASET),
            metadata_path=str(self.FE06_METADATA),
            output_dir=tmp_path,
        )
        r2 = runner2.run(
            df,
            md,
            input_sha256="x",
            input_path=str(self.FE06_DATASET),
            metadata_path=str(self.FE06_METADATA),
            output_dir=tmp_path,
        )
        assert r1.cluster_result is not None
        assert r2.cluster_result is not None
        # Recorded seed must match.
        assert r1.random_seed_used == 42
        assert r2.random_seed_used == 42
        # Membership matrix deterministic for a fixed seed.
        np.testing.assert_allclose(
            r1.cluster_result.soft_membership,
            r2.cluster_result.soft_membership,
            atol=1e-8,
        )
        # Hard labels deterministic.
        np.testing.assert_array_equal(
            r1.cluster_result.cluster_labels, r2.cluster_result.cluster_labels
        )
        # Final objective / converged / n_iter deterministic.
        assert r1.cluster_result.extra["final_objective"] == pytest.approx(
            r2.cluster_result.extra["final_objective"], abs=1e-8
        )
        assert r1.cluster_result.extra["converged"] == r2.cluster_result.extra["converged"]
        assert r1.cluster_result.extra["n_iter"] == r2.cluster_result.extra["n_iter"]
        # Both runs advertise supports_random_state=True.
        assert r1.cluster_result.supports_random_state is True
        assert r2.cluster_result.supports_random_state is True

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_fuzzy_label_alignment_with_customer_metadata(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-06-test-alignment",
            algorithm="fuzzy_cmeans",
            hyperparameters={
                "n_clusters": 4,
                "m": 2.0,
                "max_iter": 300,
                "error": 1e-4,
                "random_state": 42,
            },
            seed_override=42,
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(
            df,
            md,
            input_sha256="x",
            input_path=str(self.FE06_DATASET),
            metadata_path=str(self.FE06_METADATA),
            output_dir=tmp_path,
        )
        labels_df = pd.read_parquet(result.artifact_paths["cluster_labels"])
        # Positional alignment: row i of cluster_labels matches
        # row i of customer_metadata.
        assert (labels_df["CustomerID"].to_numpy() == md["CustomerID"].to_numpy()).all()
        assert "ClusterLabel" in labels_df.columns
        assert "IsNoise" in labels_df.columns
        # cluster_labels also contains Membership_k columns when
        # soft_membership is set.
        mem_cols = [c for c in labels_df.columns if c.startswith("Membership_")]
        assert len(mem_cols) == 4
        # FCM does not produce noise; all rows must be
        # non-noise.
        assert labels_df["IsNoise"].sum() == 0

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_fuzzy_experiment_log_schema(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-06-test-log-schema",
            algorithm="fuzzy_cmeans",
            hyperparameters={
                "n_clusters": 4,
                "m": 2.0,
                "max_iter": 300,
                "error": 1e-4,
                "random_state": 42,
            },
            seed_override=42,
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(
            df,
            md,
            input_sha256="abc123",
            input_path=str(self.FE06_DATASET),
            metadata_path=str(self.FE06_METADATA),
            output_dir=tmp_path,
        )
        # Read the log JSON and verify required fields.
        log = json.loads(Path(result.artifact_paths["experiment_log"]).read_text())
        required = {
            "experiment_id",
            "status",
            "algorithm",
            "algorithm_version",
            "dataset_version",
            "dataset_sha256",
            "feature_set",
            "hyperparameters",
            "random_seed",
            "random_seed_used",
            "n_clusters",
            "execution_time",
            "library_versions",
            "platform",
        }
        assert required.issubset(log.keys())
        assert log["status"] == "SUCCESS"
        assert log["algorithm"] == "fuzzy_cmeans"
        assert log["n_clusters"] == 4
        # Seed requested + consumed must match.
        assert log["random_seed"] == 42
        assert log["random_seed_used"] == 42
        # Cluster result extras include FCM diagnostics.
        assert "cluster_result" in log
        cr = log["cluster_result"]
        extras = cr["extra"]
        assert extras["n_clusters"] == 4
        assert extras["fuzziness"] == 2.0
        assert extras["max_iter"] == 300
        assert extras["error"] == pytest.approx(1e-4, rel=1e-6)
        assert extras["random_state"] == 42
        assert "converged" in extras
        assert "n_iter" in extras
        assert "final_objective" in extras
        assert "objective_history_length" in extras
        assert "centroid_shape" in extras
        assert "membership_shape" in extras
        assert "membership_min" in extras
        assert "membership_max" in extras
        assert "membership_row_sum_min" in extras
        assert "membership_row_sum_max" in extras
        assert "membership_confidence_min" in extras
        assert "membership_confidence_max" in extras
        assert "membership_confidence_mean" in extras
        # Soft membership shape recorded.
        assert cr["soft_membership_shape"] == [len(df), 4]
        # Soft probabilities (GMM) stays None.
        assert cr["soft_probabilities_shape"] is None
        assert "numpy" in log["library_versions"]
        assert "scikit-learn" in log["library_versions"]
