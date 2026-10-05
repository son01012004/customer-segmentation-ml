"""Tests for the ML-04 DBSCAN clustering adapter.

The tests are organised by responsibility, mirroring the K-Means
(ML-02) and Agglomerative (ML-03) test layouts and the ML-04 task
contract:

- :class:`TestInterface` — adapter implements ``BaseClusterAlgorithm``,
  is registered under ``"dbscan"``, exposes metadata, ``get_params``
  and ``get_model``.
- :class:`TestParameterValidation` — bad hyperparameters (eps,
  min_samples, metric) are rejected with ``ClusterAlgorithmError``.
- :class:`TestInputValidation` — bad input matrices (None, wrong
  dimensionality) are rejected by ``fit``. The framework's
  identifier-leakage / NaN / Inf / constant-feature checks are NOT
  retested here — they belong to the framework's validation suite.
- :class:`TestOutputSchema` — output conforms to ``ClusterResult``
  schema; DBSCAN-specific extras (eps, min_samples, metric,
  noise_count/ratio, core_sample_count, cluster_sizes,
  label distribution) are populated.
- :class:`TestNoiseHandling` — DBSCAN-specific tests for noise:
  clusters + noise, no-noise, all-noise, single-cluster, multi-cluster.
- :class:`TestReproducibility` — DBSCAN is deterministic; same input
  + same configuration + same library version → same labels.
- :class:`TestIntegrationWithFE06` — end-to-end run via
  ``ExperimentRunner`` on the real FE-06 dataset (skipped if
  absent).

The tests are intentionally value-neutral: they assert structural
properties (shape, dtype, schema, noise accounting), not
"best/optimal" claims.
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
    DBSCANAdapter,
    ExperimentRunner,
    ExperimentSpec,
    ExperimentStatus,
    load_framework_config,
)
from customer_segmentation.clustering.dbscan import (
    DEFAULT_EPS,
    DEFAULT_METRIC,
    DEFAULT_MIN_SAMPLES,
    MIN_SAMPLES_MIN,
    SUPPORTED_METRICS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expected_cluster_count(labels: np.ndarray, noise_label: int = -1) -> int:
    """Compute the number of non-noise clusters from labels."""
    return int(len([lbl for lbl in np.unique(labels) if lbl != noise_label]))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_clusters_with_noise() -> pd.DataFrame:
    """Synthetic data with two well-separated clusters and isolated noise.

    Noise points are spaced FAR from any cluster AND far from each
    other so they cannot form their own cluster. DBSCAN should find
    2 clusters and 5 noise.
    """
    rng = np.random.default_rng(7)
    c1 = rng.normal(loc=[0.0, 0.0], scale=0.3, size=(30, 2))
    c2 = rng.normal(loc=[5.0, 5.0], scale=0.3, size=(30, 2))
    # Isolated noise points — each separated by more than eps so
    # none can form a cluster.
    noise_points = [
        [100.0, 100.0],
        [-100.0, -100.0],
        [200.0, -50.0],
        [-50.0, 200.0],
        [0.0, 300.0],
    ]
    noise = np.array(noise_points)
    X = np.vstack([c1, c2, noise])
    return pd.DataFrame(X, columns=["x", "y"])


@pytest.fixture()
def well_separated_matrix() -> pd.DataFrame:
    """Synthetic data with three well-separated clusters, no noise."""
    rng = np.random.default_rng(7)
    n_per_cluster = 30
    centers = np.array([[0.0, 0.0], [10.0, 10.0], [-10.0, 10.0]])
    parts = []
    for c in centers:
        parts.append(rng.normal(loc=c, scale=0.5, size=(n_per_cluster, 2)))
    X = np.vstack(parts)
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
def _ensure_dbscan_registered() -> None:
    """Autouse: re-register ``DBSCANAdapter`` before every test.

    The ML-01 framework tests' ``registered_toy_algorithms`` fixture
    calls ``AlgorithmRegistry.clear()`` at teardown, which removes
    ``DBSCANAdapter`` from the registry. This fixture re-registers
    the existing class before each test so the registry is in a
    known state.
    """
    if not AlgorithmRegistry.is_registered("dbscan"):
        AlgorithmRegistry.register("dbscan")(DBSCANAdapter)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_dbscan_is_base_algorithm(self) -> None:
        assert issubclass(DBSCANAdapter, BaseClusterAlgorithm)

    def test_dbscan_is_registered(self) -> None:
        assert AlgorithmRegistry.is_registered("dbscan")
        cls = AlgorithmRegistry.get("dbscan")
        assert cls is DBSCANAdapter

    def test_dbscan_name_is_stable(self) -> None:
        assert DBSCANAdapter.name == "dbscan"

    def test_dbscan_family_is_density_based(self) -> None:
        # DBSCAN is density-based — produces hard labels with a
        # dedicated noise label.
        assert DBSCANAdapter.family == AlgorithmFamily.DENSITY_BASED

    def test_dbscan_version_references_sklearn(self) -> None:
        # Format is "sklearn_<version>" — captures library version.
        assert DBSCANAdapter.version.startswith("sklearn_")
        import sklearn

        assert sklearn.__version__ in DBSCANAdapter.version

    def test_supports_random_state_is_false(self) -> None:
        # DBSCAN is deterministic in sklearn — no random_state to
        # consume. The runner relies on this truthful answer.
        assert DBSCANAdapter(eps=0.5, min_samples=5).supports_random_state() is False

    def test_get_params_returns_serialisable_dict(self) -> None:
        adapter = DBSCANAdapter(eps=0.7, min_samples=10, metric="manhattan")
        params = adapter.get_params()
        assert params["eps"] == 0.7
        assert params["min_samples"] == 10
        assert params["metric"] == "manhattan"
        # Must be JSON-serialisable.
        json.dumps(params)

    def test_get_model_returns_none_before_fit(self) -> None:
        adapter = DBSCANAdapter(eps=0.5, min_samples=5)
        assert adapter.get_model() is None

    def test_get_model_returns_fitted_model_after_fit(
        self, two_clusters_with_noise: pd.DataFrame
    ) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        X = two_clusters_with_noise.to_numpy(dtype=np.float64)
        adapter.fit(X)
        model = adapter.get_model()
        assert model is not None
        # sklearn's DBSCAN exposes these after fit.
        assert hasattr(model, "labels_")
        assert hasattr(model, "core_sample_indices_")
        assert hasattr(model, "components_")

    def test_double_registration_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):

            @AlgorithmRegistry.register("dbscan")
            class _Other(BaseClusterAlgorithm):
                version = "other_v1"
                family = AlgorithmFamily.DENSITY_BASED

                def fit(self, X):
                    raise ClusterAlgorithmError("not implemented")

    def test_unregistered_algorithm_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):
            AlgorithmRegistry.get("definitely_not_registered_xyz")

    def test_supported_metrics_constant(self) -> None:
        assert "euclidean" in SUPPORTED_METRICS
        assert "manhattan" in SUPPORTED_METRICS

    def test_module_defaults_exposed(self) -> None:
        assert DEFAULT_EPS == 0.5
        assert DEFAULT_MIN_SAMPLES == 5
        assert DEFAULT_METRIC == "euclidean"
        assert MIN_SAMPLES_MIN == 1


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_eps_must_be_number(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            DBSCANAdapter(eps="0.5", min_samples=5)  # type: ignore[arg-type]

    def test_eps_must_be_positive(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            DBSCANAdapter(eps=0.0, min_samples=5)
        with pytest.raises(ClusterAlgorithmError):
            DBSCANAdapter(eps=-1.0, min_samples=5)

    def test_min_samples_must_be_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            DBSCANAdapter(eps=0.5, min_samples="5")  # type: ignore[arg-type]

    def test_min_samples_must_be_at_least_1(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            DBSCANAdapter(eps=0.5, min_samples=0)
        with pytest.raises(ClusterAlgorithmError):
            DBSCANAdapter(eps=0.5, min_samples=-1)

    def test_metric_must_be_string(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            DBSCANAdapter(eps=0.5, min_samples=5, metric=42)  # type: ignore[arg-type]

    def test_default_values(self) -> None:
        # `metric` is the only optional hyperparameter with a default.
        adapter = DBSCANAdapter(eps=0.5, min_samples=5)
        assert adapter.eps == 0.5
        assert adapter.min_samples == 5
        assert adapter.metric == DEFAULT_METRIC


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_none_matrix_raises(self) -> None:
        adapter = DBSCANAdapter(eps=0.5, min_samples=5)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(None)  # type: ignore[arg-type]

    def test_1d_matrix_raises(self) -> None:
        adapter = DBSCANAdapter(eps=0.5, min_samples=5)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros(10))

    def test_input_not_mutated(self, two_clusters_with_noise: pd.DataFrame) -> None:
        X = two_clusters_with_noise.to_numpy(dtype=np.float64)
        original = X.copy()
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        adapter.fit(X)
        assert np.array_equal(X, original)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_returns_cluster_result(self, two_clusters_with_noise: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        result = adapter.fit(two_clusters_with_noise.to_numpy(dtype=np.float64))
        assert isinstance(result, ClusterResult)

    def test_labels_shape_matches_n_samples(self, two_clusters_with_noise: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        X = two_clusters_with_noise.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.cluster_labels.shape == (X.shape[0],)
        assert result.cluster_labels.dtype == np.int64

    def test_noise_label_is_minus_one(self) -> None:
        # Convention: noise label is -1 (sklearn).
        assert (
            DBSCANAdapter(eps=0.6, min_samples=3)
            .fit(np.random.default_rng(7).normal(size=(20, 2)))
            .noise_label
            == -1
        )

    def test_metadata_fields(self, two_clusters_with_noise: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3, metric="euclidean")
        X = two_clusters_with_noise.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.algorithm == "dbscan"
        assert result.algorithm_family == AlgorithmFamily.DENSITY_BASED
        assert result.algorithm_version.startswith("sklearn_")
        assert result.n_samples == X.shape[0]
        assert result.n_features == X.shape[1]
        # Determinism: random_state_used is always None and the
        # adapter advertises no random_state support.
        assert result.supports_random_state is False
        assert result.random_seed_used is None

    def test_extra_includes_dbscan_diagnostics(self, two_clusters_with_noise: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3, metric="euclidean")
        result = adapter.fit(two_clusters_with_noise.to_numpy(dtype=np.float64))
        for key in (
            "eps",
            "min_samples",
            "metric",
            "n_clusters",
            "noise_count",
            "noise_ratio",
            "has_noise",
            "all_noise",
            "has_single_cluster",
            "core_sample_count",
            "core_sample_ratio",
            "cluster_sizes",
            "labels_value_counts",
        ):
            assert key in result.extra, f"missing extra key: {key}"
        # Type checks.
        assert isinstance(result.extra["eps"], float)
        assert isinstance(result.extra["min_samples"], int)
        assert isinstance(result.extra["metric"], str)
        assert isinstance(result.extra["n_clusters"], int)
        assert isinstance(result.extra["noise_count"], int)
        assert isinstance(result.extra["noise_ratio"], float)
        assert isinstance(result.extra["core_sample_count"], int)
        assert isinstance(result.extra["core_sample_ratio"], float)
        assert isinstance(result.extra["cluster_sizes"], dict)
        assert isinstance(result.extra["labels_value_counts"], dict)
        # Cluster sizes must NOT include noise (only non-noise labels).
        assert "-1" not in result.extra["cluster_sizes"]

    def test_metrics_placeholder_is_default(self, two_clusters_with_noise: pd.DataFrame) -> None:
        # ML-04 MUST NOT compute evaluation metrics.
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        result = adapter.fit(two_clusters_with_noise.to_numpy(dtype=np.float64))
        assert result.metrics.silhouette is None
        assert result.metrics.davies_bouldin is None
        assert result.metrics.calinski_harabasz is None
        assert result.metrics.wcss is None
        assert result.metrics.stability is None
        assert result.metrics.runtime is None

    def test_noise_count_and_ratio_consistency(self, two_clusters_with_noise: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        result = adapter.fit(two_clusters_with_noise.to_numpy(dtype=np.float64))
        # noise_count matches actual label count.
        actual_noise = int((result.cluster_labels == -1).sum())
        assert result.noise_count == actual_noise
        # noise_ratio = noise_count / n_samples.
        assert result.noise_ratio == pytest.approx(actual_noise / result.n_samples)

    def test_n_clusters_consistent_with_labels(self, two_clusters_with_noise: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        result = adapter.fit(two_clusters_with_noise.to_numpy(dtype=np.float64))
        # n_clusters is computed from labels, NOT max(labels) + 1.
        expected = _expected_cluster_count(result.cluster_labels)
        assert result.n_clusters == expected
        # Cluster sizes dict has exactly n_clusters entries.
        assert len(result.extra["cluster_sizes"]) == expected

    def test_result_is_serialisable(self, two_clusters_with_noise: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        result = adapter.fit(two_clusters_with_noise.to_numpy(dtype=np.float64))
        # to_dict() must produce JSON-friendly dict.
        d = result.to_dict()
        json.dumps(d, default=str)
        assert d["n_samples"] == result.n_samples
        assert d["algorithm"] == "dbscan"
        assert d["noise_label"] == -1


# ---------------------------------------------------------------------------
# Noise handling — required edge cases
# ---------------------------------------------------------------------------


class TestNoiseHandling:
    def test_clusters_plus_noise(self, two_clusters_with_noise: pd.DataFrame) -> None:
        # Two well-separated clusters + 5 isolated noise points.
        # DBSCAN should find 2 clusters and 5 noise.
        adapter = DBSCANAdapter(eps=0.6, min_samples=3)
        result = adapter.fit(two_clusters_with_noise.to_numpy(dtype=np.float64))
        assert result.n_clusters == 2
        assert result.noise_count >= 1
        assert result.noise_ratio > 0.0
        assert result.extra["has_noise"] is True
        assert result.extra["all_noise"] is False
        assert result.extra["has_single_cluster"] is False

    def test_no_noise(self, well_separated_matrix: pd.DataFrame) -> None:
        # Three well-separated clusters, well-tuned eps: DBSCAN
        # should find 3 clusters and 0 noise.
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        # Pick eps large enough to capture all points (and avoid
        # spurious noise on this well-separated synthetic data).
        adapter = DBSCANAdapter(eps=2.0, min_samples=5)
        result = adapter.fit(X)
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0
        assert result.extra["has_noise"] is False
        assert result.extra["all_noise"] is False
        assert result.n_clusters >= 1

    def test_all_noise_case(self) -> None:
        # Use a very small eps so nothing forms a dense region.
        rng = np.random.default_rng(42)
        X = rng.normal(size=(30, 4))
        adapter = DBSCANAdapter(eps=1e-6, min_samples=5)
        result = adapter.fit(X)
        assert result.noise_count == result.n_samples
        assert result.noise_ratio == pytest.approx(1.0)
        assert result.n_clusters == 0
        assert result.extra["all_noise"] is True
        assert result.extra["has_noise"] is True
        assert result.extra["has_single_cluster"] is False
        # Cluster sizes dict is empty (no non-noise clusters).
        assert result.extra["cluster_sizes"] == {}

    def test_single_cluster_only(self) -> None:
        # One dense cluster + isolated scattered noise -> n_clusters=1.
        rng = np.random.default_rng(7)
        c1 = rng.normal(loc=[0.0, 0.0], scale=0.2, size=(30, 2))
        # Isolated noise points — each spaced far from any cluster
        # AND far from each other so they cannot form a cluster.
        noise_points = [
            [100.0, 100.0],
            [-100.0, -100.0],
            [200.0, -50.0],
            [-50.0, 200.0],
            [0.0, 300.0],
            [300.0, 0.0],
            [-200.0, 100.0],
            [150.0, -200.0],
            [-150.0, 250.0],
            [250.0, 50.0],
        ]
        X = np.vstack([c1, np.array(noise_points)])
        adapter = DBSCANAdapter(eps=0.5, min_samples=5)
        result = adapter.fit(X)
        assert result.n_clusters == 1
        assert result.extra["has_single_cluster"] is True
        assert result.extra["has_noise"] is True
        assert result.extra["all_noise"] is False
        # Single cluster captures the dense points; the scattered
        # points become noise.
        assert result.noise_count >= 1

    def test_multiple_clusters_no_noise(self) -> None:
        # Multiple well-separated clusters with a generous eps and
        # small min_samples to avoid noise.
        rng = np.random.default_rng(7)
        c1 = rng.normal(loc=[0.0, 0.0, 0.0], scale=0.2, size=(40, 3))
        c2 = rng.normal(loc=[10.0, 10.0, 10.0], scale=0.2, size=(40, 3))
        c3 = rng.normal(loc=[-10.0, -10.0, -10.0], scale=0.2, size=(40, 3))
        X = np.vstack([c1, c2, c3])
        adapter = DBSCANAdapter(eps=1.5, min_samples=3)
        result = adapter.fit(X)
        assert result.n_clusters >= 2
        assert result.noise_count == 0
        assert result.extra["has_noise"] is False
        assert result.extra["all_noise"] is False

    def test_noise_count_zero_when_no_noise(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = DBSCANAdapter(eps=2.0, min_samples=5)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0

    def test_labels_value_counts_includes_noise_label(self) -> None:
        # The label distribution must include the noise label.
        rng = np.random.default_rng(7)
        c1 = rng.normal(loc=[0.0, 0.0], scale=0.2, size=(30, 2))
        c2 = rng.normal(loc=[100.0, 100.0], scale=0.5, size=(5, 2))
        X = np.vstack([c1, c2])
        adapter = DBSCANAdapter(eps=0.5, min_samples=5)
        result = adapter.fit(X)
        vc = result.extra["labels_value_counts"]
        assert "-1" in vc
        assert vc["-1"] == result.noise_count


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """DBSCAN is deterministic in sklearn. Same input + same configuration
    + same library version → same labels, with no seed consumed. The
    framework's seed-injection logic uses ``supports_random_state()`` to
    skip the seed for deterministic adapters.
    """

    def test_same_config_same_labels(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        r1 = DBSCANAdapter(eps=0.5, min_samples=5).fit(X)
        r2 = DBSCANAdapter(eps=0.5, min_samples=5).fit(X)
        np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels)

    def test_same_config_same_labels_two_clusters(
        self, two_clusters_with_noise: pd.DataFrame
    ) -> None:
        X = two_clusters_with_noise.to_numpy(dtype=np.float64)
        r1 = DBSCANAdapter(eps=0.6, min_samples=3).fit(X)
        r2 = DBSCANAdapter(eps=0.6, min_samples=3).fit(X)
        np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels)

    def test_random_seed_used_is_none(self, small_matrix: pd.DataFrame) -> None:
        # No seed is consumed even if the caller requests one via
        # the framework seed_override — the adapter does not accept
        # a seed and the runner's seed-injection is gated by
        # supports_random_state().
        r1 = DBSCANAdapter(eps=0.5, min_samples=5).fit(small_matrix.to_numpy(dtype=np.float64))
        assert r1.random_seed_used is None
        assert r1.supports_random_state is False

    def test_get_params_reflects_configuration(self) -> None:
        adapter = DBSCANAdapter(eps=0.7, min_samples=10, metric="manhattan")
        p = adapter.get_params()
        assert p["eps"] == 0.7
        assert p["min_samples"] == 10
        assert p["metric"] == "manhattan"


# ---------------------------------------------------------------------------
# Integration with ExperimentRunner
# ---------------------------------------------------------------------------


class TestIntegrationWithFE06:
    """End-to-end runs via ExperimentRunner on the real FE-06 dataset.

    These tests require the FE-06 outputs on disk. They are skipped
    if those files are absent.
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
    def test_runner_dbscan_basic(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-04-test-basic",
            algorithm="dbscan",
            hyperparameters={"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
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
        assert result.algorithm == "dbscan"
        assert result.dataset_version == cfg.input.dataset_version
        assert result.dataset_sha256 == "deadbeef"
        assert result.n_samples == len(df)
        assert result.cluster_labels.shape == (len(df),)
        # Artifacts must be written.
        assert "cluster_labels" in result.artifact_paths
        assert "experiment_log" in result.artifact_paths
        # Files exist on disk.
        assert Path(result.artifact_paths["cluster_labels"]).exists()
        assert Path(result.artifact_paths["experiment_log"]).exists()

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_dbscan_reproducibility(self, tmp_path: Path) -> None:
        # DBSCAN is deterministic: two runs with the same config
        # must produce identical labels, regardless of seed_override.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        hp = {"eps": 0.5, "min_samples": 5, "metric": "euclidean"}
        spec1 = ExperimentSpec(
            experiment_id="ML-04-test-repro-1",
            algorithm="dbscan",
            hyperparameters=hp,
            seed_override=42,  # should be ignored by runner (supports_random_state=False)
        )
        spec2 = ExperimentSpec(
            experiment_id="ML-04-test-repro-2",
            algorithm="dbscan",
            hyperparameters=hp,
            seed_override=99,  # different request, same outcome
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
        # Labels identical (deterministic; seed ignored).
        np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels)
        # Framework recorded requested seeds truthfully but did
        # NOT consume them (random_seed_used == None).
        assert r1.random_seed == 42
        assert r2.random_seed == 99
        assert r1.random_seed_used is None
        assert r2.random_seed_used is None
        # supports_random_state is recorded as False.
        assert r1.cluster_result.supports_random_state is False
        assert r2.cluster_result.supports_random_state is False

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_dbscan_label_alignment_with_customer_metadata(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-04-test-alignment",
            algorithm="dbscan",
            hyperparameters={"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
            seed_override=42,  # ignored
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
        # DBSCAN may produce noise — IsNoise column correctly
        # mirrors the noise label.
        expected_is_noise = labels_df["ClusterLabel"] == -1
        assert labels_df["IsNoise"].to_numpy().tolist() == expected_is_noise.to_numpy().tolist()

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_dbscan_experiment_log_schema(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-04-test-log-schema",
            algorithm="dbscan",
            hyperparameters={"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
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
        assert log["algorithm"] == "dbscan"
        # Cluster result extras include DBSCAN diagnostics. DBSCAN-
        # specific noise accounting lives inside cluster_result per
        # the unified schema (ClusterResult.noise_count / noise_ratio /
        # noise_label), not at the ExperimentResult top level.
        assert "cluster_result" in log
        cr = log["cluster_result"]
        assert cr["noise_label"] == -1
        assert cr["noise_count"] >= 0
        assert 0.0 <= cr["noise_ratio"] <= 1.0
        extras = cr["extra"]
        assert extras["eps"] == 0.5
        assert extras["min_samples"] == 5
        assert extras["metric"] == "euclidean"
        assert "noise_count" in extras
        assert "core_sample_count" in extras
        assert "cluster_sizes" in extras
        # Seed requested truthfully, but the deterministic adapter
        # consumed None.
        assert log["random_seed"] == 42
        assert log["random_seed_used"] is None
        assert "numpy" in log["library_versions"]
        assert "scikit-learn" in log["library_versions"]

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_dbscan_noise_artifacts_preserve_minus_one(self, tmp_path: Path) -> None:
        # Verify the noise label -1 is preserved verbatim in the
        # parquet artifact (no relabeling to a positive integer).
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-04-test-noise-label",
            algorithm="dbscan",
            hyperparameters={"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
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
        # If there is noise, the label is -1.
        noise_rows = labels_df[labels_df["IsNoise"]]
        if len(noise_rows) > 0:
            assert (noise_rows["ClusterLabel"] == -1).all()
