"""Tests for the ML-05 Gaussian Mixture Model (GMM) clustering adapter.

The tests are organised by responsibility, mirroring the ML-02
K-Means, ML-03 Agglomerative, and ML-04 DBSCAN test layouts and
the ML-05 task contract:

- :class:`TestInterface` — adapter implements
  ``BaseClusterAlgorithm``, is registered under ``"gmm"``,
  exposes metadata, ``get_params``, ``get_model`` and
  ``supports_random_state``.
- :class:`TestParameterValidation` — bad hyperparameters
  (``n_components``, ``covariance_type``, ``init_params``,
  ``random_state``, ``tol``, ``reg_covar``, ``max_iter``,
  ``n_init``) are rejected with ``ClusterAlgorithmError``.
- :class:`TestInputValidation` — bad input matrices (None,
  wrong dimensionality, single row, ...) are rejected by
  ``fit``. The framework's identifier-leakage / NaN / Inf /
  constant-feature checks are NOT retested here — they
  belong to the framework's validation suite.
- :class:`TestCovarianceTypes` — every advertised covariance
  type (``full``, ``tied``, ``diag``, ``spherical``) must fit
  successfully on the well-separated synthetic dataset.
- :class:`TestOutputSchema` — output conforms to
  ``ClusterResult`` schema; GMM-specific extras (n_components,
  covariance_type, init_params, convergence, lower bound,
  AIC, BIC, mixture weights, responsibility statistics,
  cluster sizes) are populated.
- :class:`TestResponsibility` — soft clustering output is
  preserved: shape, non-negative, row sums ≈ 1, column count
  == n_components, alignment with CustomerID.
- :class:`TestReproducibility` — GMM consumes ``random_state``;
  same input + same configuration + same library version →
  same responsibilities, mixture weights, lower bound. Naive
  label equality is NOT asserted because component permutation
  is a known GMM property.
- :class:`TestIntegrationWithFE06` — end-to-end run via
  ``ExperimentRunner`` on the real FE-06 dataset (skipped if
  absent).

The tests are intentionally value-neutral: they assert
structural properties (shape, dtype, schema, responsibility
integrity), not "best/optimal" claims. AIC / BIC are recorded
and asserted as diagnostics only; they are NOT used in ML-05
to declare a "best" configuration (EPIC-07 owns that).
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
    GMMAdapter,
    load_framework_config,
)
from customer_segmentation.clustering.gmm import (
    DEFAULT_COVARIANCE_TYPE,
    DEFAULT_INIT_PARAMS,
    DEFAULT_MAX_ITER,
    DEFAULT_N_INIT,
    DEFAULT_REG_COVAR,
    DEFAULT_TOL,
    MIN_N_COMPONENTS,
    SUPPORTED_COVARIANCE_TYPES,
    SUPPORTED_INIT_PARAMS,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def well_separated_matrix() -> pd.DataFrame:
    """Small, well-separated matrix with 3 visible clusters.

    Used for tests that need stable, easy-to-reason-about clustering.
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
def _ensure_gmm_registered() -> None:
    """Autouse: re-register ``GMMAdapter`` before every test.

    ML-01 framework tests' ``registered_toy_algorithms`` fixture
    calls ``AlgorithmRegistry.clear()`` at teardown, which removes
    ``GMMAdapter`` from the registry. This fixture re-registers
    the existing class before each test so the registry is in a
    known state.
    """
    if not AlgorithmRegistry.is_registered("gmm"):
        AlgorithmRegistry.register("gmm")(GMMAdapter)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_gmm_is_base_algorithm(self) -> None:
        assert issubclass(GMMAdapter, BaseClusterAlgorithm)

    def test_gmm_is_registered(self) -> None:
        # GMMAdapter is registered at module import via
        # ``@AlgorithmRegistry.register("gmm")``.
        assert AlgorithmRegistry.is_registered("gmm")
        cls = AlgorithmRegistry.get("gmm")
        assert cls is GMMAdapter

    def test_gmm_name_is_stable(self) -> None:
        assert GMMAdapter.name == "gmm"

    def test_gmm_family_is_model_based(self) -> None:
        # GMM is the model-based / probabilistic family —
        # produces both hard labels and soft probabilities.
        assert GMMAdapter.family == AlgorithmFamily.MODEL_BASED

    def test_gmm_version_references_sklearn(self) -> None:
        # Format is "sklearn_<version>" — captures library version.
        assert GMMAdapter.version.startswith("sklearn_")
        import sklearn

        assert sklearn.__version__ in GMMAdapter.version

    def test_supports_random_state_is_true(self) -> None:
        # GMM consumes random_state for EM initialisation.
        # The runner relies on this truthful answer to inject
        # the framework seed.
        assert GMMAdapter(n_components=3).supports_random_state() is True

    def test_get_params_returns_serialisable_dict(self) -> None:
        adapter = GMMAdapter(
            n_components=5,
            covariance_type="tied",
            init_params="random",
            random_state=42,
            tol=1e-4,
            reg_covar=1e-5,
            max_iter=50,
            n_init=2,
        )
        params = adapter.get_params()
        assert params["n_components"] == 5
        assert params["covariance_type"] == "tied"
        assert params["init_params"] == "random"
        assert params["random_state"] == 42
        assert params["tol"] == 1e-4
        assert params["reg_covar"] == 1e-5
        assert params["max_iter"] == 50
        assert params["n_init"] == 2
        # Must be JSON-serialisable.
        json.dumps(params)

    def test_get_model_returns_none_before_fit(self) -> None:
        adapter = GMMAdapter(n_components=3)
        assert adapter.get_model() is None

    def test_get_model_returns_fitted_model_after_fit(
        self, well_separated_matrix: pd.DataFrame
    ) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        adapter.fit(X)
        model = adapter.get_model()
        assert model is not None
        # sklearn's GaussianMixture exposes these after fit.
        assert hasattr(model, "means_")
        assert hasattr(model, "covariances_")
        assert hasattr(model, "weights_")
        assert hasattr(model, "lower_bound_")
        assert hasattr(model, "n_iter_")
        assert hasattr(model, "converged_")
        assert hasattr(model, "predict_proba")

    def test_double_registration_raises(self) -> None:
        # Trying to register another class under "gmm" should fail.
        with pytest.raises(AlgorithmRegistryError):

            @AlgorithmRegistry.register("gmm")
            class _Other(BaseClusterAlgorithm):
                version = "other_v1"
                family = AlgorithmFamily.MODEL_BASED

                def fit(self, X):
                    raise ClusterAlgorithmError("not implemented")

    def test_unregistered_algorithm_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):
            AlgorithmRegistry.get("definitely_not_registered_xyz")

    def test_supported_covariance_types_constant(self) -> None:
        assert frozenset({"full", "tied", "diag", "spherical"}) == SUPPORTED_COVARIANCE_TYPES

    def test_supported_init_params_constant(self) -> None:
        assert frozenset({"kmeans", "random"}) == SUPPORTED_INIT_PARAMS

    def test_module_defaults_exposed(self) -> None:
        assert DEFAULT_COVARIANCE_TYPE == "full"
        assert DEFAULT_INIT_PARAMS == "kmeans"
        assert DEFAULT_TOL == 1e-3
        assert DEFAULT_REG_COVAR == 1e-6
        assert DEFAULT_MAX_ITER == 100
        assert DEFAULT_N_INIT == 1
        assert MIN_N_COMPONENTS == 1


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_n_components_must_be_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components="3")  # type: ignore[arg-type]

    def test_n_components_must_be_at_least_1(self) -> None:
        # ML-05 task contract: n_components >= 1.
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=0)
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=-1)

    def test_covariance_type_must_be_string(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, covariance_type=42)  # type: ignore[arg-type]

    def test_invalid_covariance_type_rejected(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, covariance_type="lower_triangular")

    def test_init_params_must_be_string(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, init_params=123)  # type: ignore[arg-type]

    def test_invalid_init_params_rejected(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, init_params="kmedoids")

    def test_random_state_must_be_int_or_none(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, random_state="seed")  # type: ignore[arg-type]

    def test_random_state_none_accepted(self) -> None:
        adapter = GMMAdapter(n_components=2, random_state=None)
        assert adapter.random_state is None

    def test_tol_must_be_positive(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, tol=0)
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, tol=-1e-3)

    def test_tol_must_be_number(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, tol="1e-3")  # type: ignore[arg-type]

    def test_reg_covar_must_be_positive(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, reg_covar=0)
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, reg_covar=-1e-6)

    def test_max_iter_must_be_positive_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, max_iter=0)
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, max_iter=-1)

    def test_max_iter_must_be_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, max_iter="100")  # type: ignore[arg-type]

    def test_n_init_must_be_positive_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, n_init=0)
        with pytest.raises(ClusterAlgorithmError):
            GMMAdapter(n_components=2, n_init=-1)

    def test_default_values(self) -> None:
        adapter = GMMAdapter(n_components=3)
        assert adapter.covariance_type == DEFAULT_COVARIANCE_TYPE
        assert adapter.init_params == DEFAULT_INIT_PARAMS
        assert adapter.random_state is None
        assert adapter.tol == pytest.approx(DEFAULT_TOL)
        assert adapter.reg_covar == pytest.approx(DEFAULT_REG_COVAR)
        assert adapter.max_iter == DEFAULT_MAX_ITER
        assert adapter.n_init == DEFAULT_N_INIT


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_none_matrix_raises(self) -> None:
        adapter = GMMAdapter(n_components=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(None)  # type: ignore[arg-type]

    def test_non_ndarray_raises(self) -> None:
        adapter = GMMAdapter(n_components=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit([[0.0, 0.0], [1.0, 1.0]])  # type: ignore[arg-type]

    def test_1d_matrix_raises(self) -> None:
        adapter = GMMAdapter(n_components=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros(10))

    def test_zero_features_raises(self) -> None:
        adapter = GMMAdapter(n_components=2)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros((10, 0)))

    def test_input_not_mutated(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        original = X.copy()
        adapter = GMMAdapter(n_components=3, random_state=0)
        adapter.fit(X)
        assert np.array_equal(X, original)


# ---------------------------------------------------------------------------
# Covariance type coverage
# ---------------------------------------------------------------------------


class TestCovarianceTypes:
    """All four advertised covariance types must fit successfully on
    a well-separated dataset. EPIC-07 will own the comparison
    sweep; ML-05 only verifies the adapter supports all four
    sklearn options on the FE-06-scaled feature matrix.
    """

    @pytest.mark.parametrize("covariance_type", sorted(SUPPORTED_COVARIANCE_TYPES))
    def test_covariance_type_fits(
        self, well_separated_matrix: pd.DataFrame, covariance_type: str
    ) -> None:
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        adapter = GMMAdapter(
            n_components=3, covariance_type=covariance_type, random_state=0, max_iter=50
        )
        result = adapter.fit(X)
        assert isinstance(result, ClusterResult)
        assert result.n_clusters == 3
        assert result.cluster_labels.shape == (X.shape[0],)
        assert result.extra["covariance_type"] == covariance_type
        # Convergence: synthetic 3-cluster data is easy; EM should
        # converge within 50 iterations.
        assert result.extra["converged"] is True
        # Lower bound must be finite.
        assert np.isfinite(result.extra["lower_bound"])

    def test_covariance_types_produce_different_lower_bounds(
        self, two_clusters_matrix: pd.DataFrame
    ) -> None:
        # Sanity: the four covariance types should produce
        # observably different (but related) log-likelihoods on
        # the same data. ``full`` is the most flexible model and
        # should achieve a higher (less negative) lower bound than
        # ``spherical`` on this well-separated 2-D synthetic
        # dataset. We do NOT assert any "best" type; we only
        # verify that the adapter actually uses the covariance
        # type (the lower bounds differ).
        X = two_clusters_matrix.to_numpy(dtype=np.float64)
        full_lb = (
            GMMAdapter(n_components=2, covariance_type="full", random_state=0, max_iter=100)
            .fit(X)
            .extra["lower_bound"]
        )
        spherical_lb = (
            GMMAdapter(n_components=2, covariance_type="spherical", random_state=0, max_iter=100)
            .fit(X)
            .extra["lower_bound"]
        )
        # ``full`` is the most flexible model and should achieve a
        # higher (less negative) lower bound than ``spherical`` on
        # this well-separated 2-D synthetic dataset. If the dataset
        # were 1-D the two would coincide; we are explicitly
        # using 2-D centres so ``full`` wins. (In sklearn's
        # convention, ``lower_bound_`` is the negative variational
        # lower bound, which is maximized during EM; less negative
        # means better fit.)
        assert full_lb > spherical_lb


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_returns_cluster_result(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert isinstance(result, ClusterResult)

    def test_labels_shape_matches_n_samples(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.cluster_labels.shape == (X.shape[0],)
        assert result.cluster_labels.dtype == np.int64

    def test_n_clusters_matches_n_components(self, well_separated_matrix: pd.DataFrame) -> None:
        k = 3
        adapter = GMMAdapter(n_components=k, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.n_clusters == k
        # GMM labels are dense in [0, K-1] when predict succeeds.
        assert int(result.cluster_labels.min()) >= 0
        assert int(result.cluster_labels.max()) <= k - 1

    def test_metadata_fields(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(
            n_components=3,
            covariance_type="full",
            init_params="kmeans",
            random_state=42,
        )
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.algorithm == "gmm"
        assert result.algorithm_family == AlgorithmFamily.MODEL_BASED
        assert result.algorithm_version.startswith("sklearn_")
        assert result.n_samples == X.shape[0]
        assert result.n_features == X.shape[1]
        # GMM consumes random_state; it must be recorded.
        assert result.supports_random_state is True
        assert result.random_seed_used == 42

    def test_extra_includes_diagnostic_info(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        for key in (
            "n_components",
            "covariance_type",
            "init_params",
            "random_state",
            "tol",
            "reg_covar",
            "max_iter",
            "n_init",
            "converged",
            "n_iter",
            "lower_bound",
            "aic",
            "bic",
            "mixture_weights",
            "cluster_sizes",
            "soft_probabilities_shape",
            "soft_probabilities_row_sum_min",
            "soft_probabilities_row_sum_max",
            "responsibility_max_probability_min",
            "responsibility_max_probability_max",
            "responsibility_max_probability_mean",
        ):
            assert key in result.extra, f"missing extra key: {key}"

        # Type / value checks.
        assert isinstance(result.extra["n_components"], int)
        assert isinstance(result.extra["covariance_type"], str)
        assert isinstance(result.extra["init_params"], str)
        assert isinstance(result.extra["converged"], bool)
        assert isinstance(result.extra["n_iter"], int)
        assert isinstance(result.extra["lower_bound"], float)
        assert isinstance(result.extra["aic"], (int, float))
        assert isinstance(result.extra["bic"], (int, float))
        assert isinstance(result.extra["mixture_weights"], list)
        assert isinstance(result.extra["cluster_sizes"], dict)
        # Mixture weights sum to 1.
        weights_sum = float(sum(result.extra["mixture_weights"]))
        assert weights_sum == pytest.approx(1.0, abs=1e-6)
        # len(mixture_weights) == n_components.
        assert len(result.extra["mixture_weights"]) == result.extra["n_components"]
        # Cluster sizes dict has exactly n_components entries
        # (GMM labels are dense in [0, K-1]).
        assert len(result.extra["cluster_sizes"]) == result.extra["n_components"]

    def test_metrics_placeholder_is_default(self, well_separated_matrix: pd.DataFrame) -> None:
        # ML-05 MUST NOT compute evaluation metrics. AIC / BIC
        # recorded in extras are algorithm-specific diagnostics,
        # not clustering quality metrics.
        adapter = GMMAdapter(n_components=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.metrics.silhouette is None
        assert result.metrics.davies_bouldin is None
        assert result.metrics.calinski_harabasz is None
        assert result.metrics.wcss is None
        assert result.metrics.stability is None
        assert result.metrics.runtime is None

    def test_noise_count_zero_for_gmm(self, well_separated_matrix: pd.DataFrame) -> None:
        # GMM does not have a noise concept — every observation
        # has a posterior responsibility summing to ~1.
        adapter = GMMAdapter(n_components=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0
        assert result.noise_label == -1  # framework default

    def test_result_is_serialisable(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        # to_dict() must produce JSON-friendly dict.
        d = result.to_dict()
        json.dumps(d, default=str)
        assert d["n_samples"] == result.n_samples
        assert d["algorithm"] == "gmm"
        assert d["soft_probabilities_shape"] == [result.n_samples, result.n_clusters]


# ---------------------------------------------------------------------------
# Responsibility / soft clustering
# ---------------------------------------------------------------------------


class TestResponsibility:
    """Soft clustering output is the defining characteristic of GMM.
    The responsibilities matrix MUST satisfy structural invariants
    and MUST be aligned with the customer metadata so EPIC-07/08/09
    can consume it downstream.
    """

    def test_responsibilities_shape(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_probabilities is not None
        assert result.soft_probabilities.shape == (X.shape[0], 3)
        assert result.extra["soft_probabilities_shape"] == [X.shape[0], 3]

    def test_responsibilities_non_negative(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_probabilities is not None
        # Posterior probabilities are non-negative.
        assert (result.soft_probabilities >= 0.0).all()

    def test_responsibilities_row_sum_equals_one(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_probabilities is not None
        row_sums = result.soft_probabilities.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-8)
        # Diagnostics also recorded.
        assert result.extra["soft_probabilities_row_sum_min"] == pytest.approx(
            float(row_sums.min()), abs=1e-8
        )
        assert result.extra["soft_probabilities_row_sum_max"] == pytest.approx(
            float(row_sums.max()), abs=1e-8
        )

    def test_responsibilities_consistent_with_hard_labels(
        self, well_separated_matrix: pd.DataFrame
    ) -> None:
        # sklearn's predict(X) returns argmax over the responsibility
        # matrix for GMM (the model's predict() implementation uses
        # the posterior probabilities). Verify that this property
        # holds in our adapter output.
        adapter = GMMAdapter(n_components=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.soft_probabilities is not None
        argmax_labels = result.soft_probabilities.argmax(axis=1).astype(np.int64)
        np.testing.assert_array_equal(argmax_labels, result.cluster_labels)

    def test_responsibility_confidence_summary(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = GMMAdapter(n_components=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        # Max probability per row lies in [1/K, 1].
        max_probs = result.soft_probabilities.max(axis=1)
        assert result.extra["responsibility_max_probability_min"] == pytest.approx(
            float(max_probs.min()), abs=1e-12
        )
        assert result.extra["responsibility_max_probability_max"] == pytest.approx(
            float(max_probs.max()), abs=1e-12
        )
        assert result.extra["responsibility_max_probability_mean"] == pytest.approx(
            float(max_probs.mean()), abs=1e-12
        )
        # Lower bound on max prob is 1/K for a uniform prior; on
        # well-separated 3-cluster data the max prob is much higher
        # than 1/K=1/3.
        assert max_probs.min() >= 1.0 / 3.0 - 1e-6

    def test_responsibility_columns_equal_n_components(
        self, two_clusters_matrix: pd.DataFrame
    ) -> None:
        # Number of responsibility columns always equals
        # n_components (regardless of whether the fitted GMM
        # actually finds K visually distinct clusters).
        for k in (1, 2, 3, 4):
            adapter = GMMAdapter(n_components=k, random_state=0, max_iter=50)
            result = adapter.fit(two_clusters_matrix.to_numpy(dtype=np.float64))
            assert result.soft_probabilities.shape == (100, k)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """GMM consumes ``random_state`` for EM initialisation. Same
    input + same configuration + same library version → same
    responsibilities, mixture weights, lower bound.

    GMM has a known **label permutation** property: across runs
    the ``k``-th component may swap indices with another component
    even with the same seed (e.g. when EM lands in different local
    maxima). Naive label equality is therefore NOT asserted;
    permutation-invariant comparison is used instead.
    """

    def test_same_seed_same_responsibilities(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        r1 = GMMAdapter(n_components=4, random_state=42, max_iter=50).fit(X)
        r2 = GMMAdapter(n_components=4, random_state=42, max_iter=50).fit(X)
        # Responsibilities are deterministic for a fixed seed.
        np.testing.assert_allclose(r1.soft_probabilities, r2.soft_probabilities, atol=1e-8)
        # Mixture weights match.
        np.testing.assert_allclose(
            r1.extra["mixture_weights"], r2.extra["mixture_weights"], atol=1e-8
        )
        # Lower bound matches.
        assert r1.extra["lower_bound"] == pytest.approx(r2.extra["lower_bound"], abs=1e-8)
        # AIC / BIC match.
        assert r1.extra["aic"] == pytest.approx(r2.extra["aic"], abs=1e-6)
        assert r1.extra["bic"] == pytest.approx(r2.extra["bic"], abs=1e-6)
        # Converged + n_iter match.
        assert r1.extra["converged"] == r2.extra["converged"]
        assert r1.extra["n_iter"] == r2.extra["n_iter"]
        # Recorded seed must match.
        assert r1.random_seed_used == 42
        assert r2.random_seed_used == 42

    def test_permutation_invariant_centroids(self, well_separated_matrix: pd.DataFrame) -> None:
        # GMM labels may swap cluster IDs across runs because
        # the K-Means init step inside sklearn's
        # ``init_params='kmeans'`` initialisation path can pick
        # initial means in a different order. We therefore
        # compare **per-cluster** centroids after sorting them
        # (permutation-invariant).
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        r1 = GMMAdapter(n_components=3, random_state=0, max_iter=100).fit(X)
        r2 = GMMAdapter(n_components=3, random_state=0, max_iter=100).fit(X)
        labels_1 = r1.cluster_labels
        labels_2 = r2.cluster_labels
        centroids_1 = np.array(
            sorted([X[labels_1 == k].mean(axis=0).tolist() for k in np.unique(labels_1)])
        )
        centroids_2 = np.array(
            sorted([X[labels_2 == k].mean(axis=0).tolist() for k in np.unique(labels_2)])
        )
        np.testing.assert_allclose(centroids_1, centroids_2, atol=1e-6)

    def test_random_state_used_recorded_truthfully(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        r1 = GMMAdapter(n_components=4, random_state=123).fit(X)
        # The framework's runner injects the seed; the adapter
        # records it.
        assert r1.random_seed_used == 123
        assert r1.supports_random_state is True

    def test_get_params_reflects_configuration(self) -> None:
        adapter = GMMAdapter(
            n_components=5,
            covariance_type="diag",
            init_params="random",
            random_state=7,
            tol=1e-4,
            reg_covar=1e-5,
            max_iter=20,
            n_init=2,
        )
        p = adapter.get_params()
        assert p["n_components"] == 5
        assert p["covariance_type"] == "diag"
        assert p["init_params"] == "random"
        assert p["random_state"] == 7
        assert p["tol"] == 1e-4
        assert p["reg_covar"] == 1e-5
        assert p["max_iter"] == 20
        assert p["n_init"] == 2


# ---------------------------------------------------------------------------
# Integration with ExperimentRunner
# ---------------------------------------------------------------------------


class TestIntegrationWithFE06:
    """End-to-end runs via ExperimentRunner on the real FE-06 dataset.

    These tests require the FE-06 outputs on disk. They are skipped
    if those files are absent, so the test suite still works in a
    fresh CI environment before FE-06 has run.
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
    def test_runner_gmm_basic(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-05-test-basic",
            algorithm="gmm",
            hyperparameters={
                "n_components": 4,
                "covariance_type": "full",
                "init_params": "kmeans",
                "random_state": 42,
                "max_iter": 100,
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
        assert result.algorithm == "gmm"
        assert result.dataset_version == cfg.input.dataset_version
        assert result.dataset_sha256 == "deadbeef"
        assert result.n_clusters == 4
        assert result.n_samples == len(df)
        assert result.cluster_labels.shape == (len(df),)
        # Artifacts must be written: cluster_labels + experiment_log +
        # algorithm_output (because soft_probabilities is set).
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
    def test_runner_gmm_soft_probabilities_in_artifact(self, tmp_path: Path) -> None:
        # Verify that the algorithm_output parquet contains
        # Probability_k columns and that CustomerID alignment is
        # preserved.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-05-test-soft",
            algorithm="gmm",
            hyperparameters={
                "n_components": 4,
                "covariance_type": "full",
                "init_params": "kmeans",
                "random_state": 42,
                "max_iter": 100,
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
        prob_cols = [c for c in algo_df.columns if c.startswith("Probability_")]
        # 4 probability columns for n_components=4.
        assert len(prob_cols) == 4
        # CustomerID is the first column and is aligned with metadata.
        assert "CustomerID" in algo_df.columns
        np.testing.assert_array_equal(algo_df["CustomerID"].to_numpy(), md["CustomerID"].to_numpy())
        # Row sums are ~ 1.
        np.testing.assert_allclose(algo_df[prob_cols].sum(axis=1).to_numpy(), 1.0, atol=1e-8)
        # Probabilities are non-negative.
        assert (algo_df[prob_cols].to_numpy() >= 0.0).all()

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_gmm_reproducibility(self, tmp_path: Path) -> None:
        # GMM consumes random_state: two runs with the same seed
        # must produce identical responsibilities / mixture weights
        # / lower bound. Naive label equality is NOT asserted.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        hp = {
            "n_components": 4,
            "covariance_type": "full",
            "init_params": "kmeans",
            "random_state": 42,
            "max_iter": 100,
        }
        spec1 = ExperimentSpec(
            experiment_id="ML-05-test-repro-1",
            algorithm="gmm",
            hyperparameters=hp,
        )
        spec2 = ExperimentSpec(
            experiment_id="ML-05-test-repro-2",
            algorithm="gmm",
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
        # Responsibilities deterministic for a fixed seed.
        np.testing.assert_allclose(
            r1.cluster_result.soft_probabilities,
            r2.cluster_result.soft_probabilities,
            atol=1e-6,
        )
        # Lower bound / AIC / BIC deterministic.
        assert r1.cluster_result.extra["lower_bound"] == pytest.approx(
            r2.cluster_result.extra["lower_bound"], abs=1e-6
        )
        assert r1.cluster_result.extra["aic"] == pytest.approx(
            r2.cluster_result.extra["aic"], abs=1e-3
        )
        assert r1.cluster_result.extra["bic"] == pytest.approx(
            r2.cluster_result.extra["bic"], abs=1e-3
        )
        # Mixture weights deterministic.
        np.testing.assert_allclose(
            r1.cluster_result.extra["mixture_weights"],
            r2.cluster_result.extra["mixture_weights"],
            atol=1e-8,
        )
        # Both runs advertise supports_random_state=True.
        assert r1.cluster_result.supports_random_state is True
        assert r2.cluster_result.supports_random_state is True

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_gmm_label_alignment_with_customer_metadata(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-05-test-alignment",
            algorithm="gmm",
            hyperparameters={
                "n_components": 4,
                "covariance_type": "full",
                "init_params": "kmeans",
                "random_state": 42,
                "max_iter": 100,
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
        # Positional alignment: row i of cluster_labels matches row
        # i of customer_metadata.
        assert (labels_df["CustomerID"].to_numpy() == md["CustomerID"].to_numpy()).all()
        assert "ClusterLabel" in labels_df.columns
        assert "IsNoise" in labels_df.columns
        # cluster_labels also contains Probability_k columns when
        # soft_probabilities is set (artifact writer mirrors the
        # responsibility matrix into the labels parquet too).
        prob_cols = [c for c in labels_df.columns if c.startswith("Probability_")]
        assert len(prob_cols) == 4
        # GMM does not produce noise; all rows must be non-noise.
        assert labels_df["IsNoise"].sum() == 0

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_gmm_experiment_log_schema(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-05-test-log-schema",
            algorithm="gmm",
            hyperparameters={
                "n_components": 4,
                "covariance_type": "full",
                "init_params": "kmeans",
                "random_state": 42,
                "max_iter": 100,
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
        assert log["algorithm"] == "gmm"
        assert log["n_clusters"] == 4
        # Seed requested + consumed must match.
        assert log["random_seed"] == 42
        assert log["random_seed_used"] == 42
        # Cluster result extras include GMM diagnostics.
        assert "cluster_result" in log
        cr = log["cluster_result"]
        extras = cr["extra"]
        assert extras["n_components"] == 4
        assert extras["covariance_type"] == "full"
        assert extras["init_params"] == "kmeans"
        assert extras["random_state"] == 42
        assert "converged" in extras
        assert "n_iter" in extras
        assert "lower_bound" in extras
        assert "aic" in extras
        assert "bic" in extras
        assert "mixture_weights" in extras
        assert "cluster_sizes" in extras
        assert "soft_probabilities_shape" in extras
        assert "soft_probabilities_row_sum_min" in extras
        assert "soft_probabilities_row_sum_max" in extras
        # Soft probabilities shape recorded.
        assert cr["soft_probabilities_shape"] == [len(df), 4]
        assert "numpy" in log["library_versions"]
        assert "scikit-learn" in log["library_versions"]

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    @pytest.mark.parametrize("covariance_type", sorted(SUPPORTED_COVARIANCE_TYPES))
    def test_runner_gmm_all_covariance_types(self, tmp_path: Path, covariance_type: str) -> None:
        # All four covariance types must run successfully via
        # the framework runner on the real FE-06 dataset.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id=f"ML-05-test-cov-{covariance_type}",
            algorithm="gmm",
            hyperparameters={
                "n_components": 4,
                "covariance_type": covariance_type,
                "init_params": "kmeans",
                "random_state": 42,
                "max_iter": 100,
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
        assert result.status == ExperimentStatus.SUCCESS
        assert result.n_clusters == 4
        extras = result.cluster_result.extra
        assert extras["covariance_type"] == covariance_type
        assert extras["n_components"] == 4
        # The FE-06 matrix is well-conditioned (StandardScaler),
        # so EM should converge for all four covariance types
        # within 100 iterations.
        assert extras["converged"] is True
        assert np.isfinite(extras["lower_bound"])
