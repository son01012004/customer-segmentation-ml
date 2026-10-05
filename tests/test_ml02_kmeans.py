"""Tests for the ML-02 K-Means clustering adapter.

The tests are organised by responsibility, mirroring the task contract:

- :class:`TestInterface` — adapter implements ``BaseClusterAlgorithm``,
  is registered under ``"kmeans"``, exposes metadata, ``get_params``
  and ``get_model``.
- :class:`TestParameterValidation` — bad hyperparameters are rejected
  with ``ClusterAlgorithmError``.
- :class:`TestInputValidation` — bad input matrices are rejected by
  ``fit``.
- :class:`TestOutputSchema` — output conforms to ``ClusterResult``
  schema.
- :class:`TestReproducibility` — same seed + same input + same config
  → same labels.
- :class:`TestIntegrationWithFE06` — end-to-end run via
  ``ExperimentRunner`` on the real FE-06 dataset (skipped if absent).

The tests are intentionally value-neutral: they assert structural
properties (shape, dtype, schema), not "best/optimal" claims.
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
    KMeansAdapter,
    load_framework_config,
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
def small_matrix() -> pd.DataFrame:
    rng = np.random.default_rng(123)
    X = rng.normal(size=(50, 4))
    return pd.DataFrame(X, columns=["f0", "f1", "f2", "f3"])


@pytest.fixture()
def small_metadata() -> pd.DataFrame:
    return pd.DataFrame({"CustomerID": np.arange(1000, 1050, dtype=np.int64)})


@pytest.fixture(autouse=True)
def _ensure_kmeans_registered() -> None:
    """Autouse: re-register ``KMeansAdapter`` before every test.

    ML-01 tests' ``registered_toy_algorithms`` fixture calls
    ``AlgorithmRegistry.clear()`` at teardown, which removes
    ``KMeansAdapter`` from the registry. This fixture re-registers
    the existing class before each test so the registry is in a
    known state.
    """
    if not AlgorithmRegistry.is_registered("kmeans"):
        AlgorithmRegistry.register("kmeans")(KMeansAdapter)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_kmeans_is_base_algorithm(self) -> None:
        assert issubclass(KMeansAdapter, BaseClusterAlgorithm)

    def test_kmeans_is_registered(self) -> None:
        # KMeansAdapter is registered at module import via
        # ``@AlgorithmRegistry.register("kmeans")``.
        assert AlgorithmRegistry.is_registered("kmeans")
        cls = AlgorithmRegistry.get("kmeans")
        assert cls is KMeansAdapter

    def test_kmeans_name_is_stable(self) -> None:
        assert KMeansAdapter.name == "kmeans"

    def test_kmeans_family_is_hard(self) -> None:
        assert KMeansAdapter.family == AlgorithmFamily.HARD

    def test_kmeans_version_references_sklearn(self) -> None:
        # Format is "sklearn_<version>" — captures library version.
        assert KMeansAdapter.version.startswith("sklearn_")
        import sklearn

        assert sklearn.__version__ in KMeansAdapter.version

    def test_supports_random_state(self) -> None:
        assert KMeansAdapter(n_clusters=3).supports_random_state() is True

    def test_get_params_returns_serialisable_dict(self) -> None:
        adapter = KMeansAdapter(
            n_clusters=5, init="k-means++", n_init=10, max_iter=300, random_state=42
        )
        params = adapter.get_params()
        assert params["n_clusters"] == 5
        assert params["init"] == "k-means++"
        assert params["n_init"] == 10
        assert params["max_iter"] == 300
        assert params["random_state"] == 42
        # Must be JSON-serialisable.
        json.dumps(params)

    def test_get_model_returns_none_before_fit(self) -> None:
        adapter = KMeansAdapter(n_clusters=3)
        assert adapter.get_model() is None

    def test_get_model_returns_fitted_model_after_fit(
        self, well_separated_matrix: pd.DataFrame
    ) -> None:
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        adapter.fit(X)
        model = adapter.get_model()
        assert model is not None
        # sklearn's KMeans exposes these after fit.
        assert hasattr(model, "cluster_centers_")
        assert hasattr(model, "inertia_")
        assert model.cluster_centers_.shape == (3, 2)

    def test_double_registration_raises(self) -> None:
        # Trying to register another class under "kmeans" should fail.
        with pytest.raises(AlgorithmRegistryError):

            @AlgorithmRegistry.register("kmeans")
            class _Other(BaseClusterAlgorithm):
                version = "other_v1"
                family = AlgorithmFamily.HARD

                def fit(self, X):
                    raise ClusterAlgorithmError("not implemented")

    def test_unregistered_algorithm_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):
            AlgorithmRegistry.get("definitely_not_registered_xyz")


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_n_clusters_must_be_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            KMeansAdapter(n_clusters="4")  # type: ignore[arg-type]

    def test_n_clusters_must_be_positive(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            KMeansAdapter(n_clusters=0)

    def test_n_init_must_be_positive(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            KMeansAdapter(n_clusters=3, n_init=0)

    def test_max_iter_must_be_positive(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            KMeansAdapter(n_clusters=3, max_iter=0)

    def test_random_state_must_be_int_or_none(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            KMeansAdapter(n_clusters=3, random_state="seed")  # type: ignore[arg-type]

    def test_invalid_init_string_raises(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            KMeansAdapter(n_clusters=3, init="kmeans--")  # type: ignore[arg-type]

    def test_init_random_accepted(self) -> None:
        # sklearn also accepts "random" init.
        adapter = KMeansAdapter(n_clusters=3, init="random")
        assert adapter.init == "random"

    def test_default_values(self) -> None:
        adapter = KMeansAdapter(n_clusters=3)
        assert adapter.init == "k-means++"
        assert adapter.n_init == 10
        assert adapter.max_iter == 300
        assert adapter.random_state is None
        assert adapter.tol == pytest.approx(1e-4)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_none_matrix_raises(self) -> None:
        adapter = KMeansAdapter(n_clusters=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(None)  # type: ignore[arg-type]

    def test_1d_matrix_raises(self) -> None:
        adapter = KMeansAdapter(n_clusters=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros(10))

    def test_n_clusters_greater_than_n_samples_raises(self, small_matrix: pd.DataFrame) -> None:
        adapter = KMeansAdapter(n_clusters=100)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(small_matrix.to_numpy(dtype=np.float64))

    def test_too_few_samples_raises(self) -> None:
        adapter = KMeansAdapter(n_clusters=2)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros((1, 3)))

    def test_input_not_mutated(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        original = X.copy()
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        adapter.fit(X)
        assert np.array_equal(X, original)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_returns_cluster_result(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert isinstance(result, ClusterResult)

    def test_labels_shape_matches_n_samples(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.cluster_labels.shape == (X.shape[0],)
        assert result.cluster_labels.dtype == np.int64

    def test_n_clusters_matches_k(self, well_separated_matrix: pd.DataFrame) -> None:
        k = 3
        adapter = KMeansAdapter(n_clusters=k, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.n_clusters == k
        assert int(result.cluster_labels.max()) + 1 == k
        assert int(result.cluster_labels.min()) >= 0

    def test_metadata_fields(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = KMeansAdapter(n_clusters=3, init="k-means++", n_init=10, random_state=42)
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.algorithm == "kmeans"
        assert result.algorithm_family == AlgorithmFamily.HARD
        assert result.algorithm_version.startswith("sklearn_")
        assert result.n_samples == X.shape[0]
        assert result.n_features == X.shape[1]
        assert result.supports_random_state is True
        assert result.random_seed_used == 42

    def test_extra_includes_diagnostic_info(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert "wcss" in result.extra
        assert "n_iter" in result.extra
        assert "init_strategy" in result.extra
        assert "effective_n_init" in result.extra
        assert "converged" in result.extra
        assert "cluster_sizes" in result.extra
        # WCSS is a diagnostic value, not a metric.
        assert isinstance(result.extra["wcss"], float)
        assert result.extra["wcss"] >= 0.0

    def test_metrics_placeholder_is_default(self, well_separated_matrix: pd.DataFrame) -> None:
        # ML-02 MUST NOT compute evaluation metrics.
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.metrics.silhouette is None
        assert result.metrics.davies_bouldin is None
        assert result.metrics.calinski_harabasz is None
        assert result.metrics.wcss is None  # EPIC-07/08 owns this slot
        assert result.metrics.stability is None
        assert result.metrics.runtime is None

    def test_noise_count_zero_for_kmeans(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        # K-Means has no noise concept.
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0

    def test_result_is_serialisable(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = KMeansAdapter(n_clusters=3, random_state=0)
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        # to_dict() must produce JSON-friendly dict.
        d = result.to_dict()
        json.dumps(d, default=str)
        assert d["n_samples"] == result.n_samples
        assert d["algorithm"] == "kmeans"


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    def test_same_seed_same_labels(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        r1 = KMeansAdapter(n_clusters=4, random_state=42).fit(X)
        r2 = KMeansAdapter(n_clusters=4, random_state=42).fit(X)
        # sklearn KMeans with fixed seed + init="k-means++" is
        # deterministic at the cost-function level (lowest inertia
        # across n_init restarts is the same), so labels are stable.
        np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels)

    def test_different_seed_can_differ(self, small_matrix: pd.DataFrame) -> None:
        # The seed itself MUST be recorded truthfully.
        r1 = KMeansAdapter(n_clusters=4, random_state=1).fit(
            small_matrix.to_numpy(dtype=np.float64)
        )
        r2 = KMeansAdapter(n_clusters=4, random_state=2).fit(
            small_matrix.to_numpy(dtype=np.float64)
        )
        # The recorded seed must match.
        assert r1.random_seed_used == 1
        assert r2.random_seed_used == 2
        # We do NOT assert label equality between different seeds;
        # sklearn is deterministic per-seed but two different seeds
        # may or may not converge to the same partition.

    def test_get_params_reflects_init(self) -> None:
        adapter = KMeansAdapter(n_clusters=5, init="random", n_init=3, random_state=7)
        p = adapter.get_params()
        assert p["init"] == "random"
        assert p["n_init"] == 3
        assert p["random_state"] == 7

    def test_reproducibility_via_labels_aligned_to_centroids(
        self, well_separated_matrix: pd.DataFrame
    ) -> None:
        # When comparing two K-Means runs with the same seed, the
        # *labels* are stable. We verify via a permutation-invariant
        # property: for each cluster, the centroid (mean of assigned
        # points) is the same set.
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        r1 = KMeansAdapter(n_clusters=3, random_state=0).fit(X)
        r2 = KMeansAdapter(n_clusters=3, random_state=0).fit(X)
        labels_1 = r1.cluster_labels
        labels_2 = r2.cluster_labels
        # Compute per-cluster centroids for each run, sort by centroid
        # x-coordinate, and compare.
        centroids_1 = np.array(
            sorted([X[labels_1 == k].mean(axis=0).tolist() for k in np.unique(labels_1)])
        )
        centroids_2 = np.array(
            sorted([X[labels_2 == k].mean(axis=0).tolist() for k in np.unique(labels_2)])
        )
        np.testing.assert_allclose(centroids_1, centroids_2, atol=1e-8)


# ---------------------------------------------------------------------------
# Integration with ExperimentRunner
# ---------------------------------------------------------------------------


class TestIntegrationWithFE06:
    """End-to-end runs via ExperimentRunner.

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
    def test_runner_kmeans_basic(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-02-test-basic",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "n_init": 5, "max_iter": 100},
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
        assert result.algorithm == "kmeans"
        assert result.dataset_version == cfg.input.dataset_version
        assert result.dataset_sha256 == "deadbeef"
        assert result.n_clusters == 4
        assert result.n_samples == len(df)
        assert result.cluster_labels.shape == (len(df),)
        # Artifacts must be written.
        assert "cluster_labels" in result.artifact_paths
        assert "experiment_log" in result.artifact_paths
        # Check files exist on disk.
        assert Path(result.artifact_paths["cluster_labels"]).exists()
        assert Path(result.artifact_paths["experiment_log"]).exists()

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_kmeans_reproducibility(self, tmp_path: Path) -> None:
        # NOTE: K-Means labels are permutation-invariant — running the
        # same configuration twice may yield the same partition but
        # with cluster IDs permuted (cluster "0" in run 1 may be
        # labelled "2" in run 2). The task contract explicitly forbids
        # naive equality assertions; we use permutation-invariant
        # checks (sorted per-cluster centroids + WCSS) AND verify
        # that the recorded seed matches.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        # Include random_state explicitly in hyperparameters so both
        # runs are seeded identically. The framework's seed_override
        # field is recorded but not auto-injected into the adapter;
        # explicit passing via hyperparameters is the ML-02 contract.
        hp = {"n_clusters": 4, "n_init": 10, "max_iter": 100, "random_state": 42}
        spec1 = ExperimentSpec(
            experiment_id="ML-02-test-repro-1",
            algorithm="kmeans",
            hyperparameters=hp,
        )
        spec2 = ExperimentSpec(
            experiment_id="ML-02-test-repro-2",
            algorithm="kmeans",
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
        # Recorded seed must match the requested seed.
        assert r1.random_seed_used == 42
        assert r2.random_seed_used == 42
        # Both runs must have succeeded.
        assert r1.cluster_result is not None
        assert r2.cluster_result is not None
        # WCSS (inertia) must match — K-Means picks the lowest-inertia
        # restart, so WCSS is fully deterministic for a given seed.
        wcss1 = r1.cluster_result.extra["wcss"]
        wcss2 = r2.cluster_result.extra["wcss"]
        assert wcss1 == pytest.approx(wcss2, rel=1e-9)
        # Per-cluster sorted centroids must match (permutation-invariant).
        X = df.to_numpy(dtype=np.float64)
        centroids_1 = np.array(
            sorted(
                [
                    X[r1.cluster_labels == k].mean(axis=0).tolist()
                    for k in np.unique(r1.cluster_labels)
                ]
            )
        )
        centroids_2 = np.array(
            sorted(
                [
                    X[r2.cluster_labels == k].mean(axis=0).tolist()
                    for k in np.unique(r2.cluster_labels)
                ]
            )
        )
        np.testing.assert_allclose(centroids_1, centroids_2, atol=1e-8)

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_kmeans_label_alignment_with_customer_metadata(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-02-test-alignment",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "n_init": 5, "max_iter": 100},
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
        # Positional alignment: row i of cluster_labels matches row i
        # of customer_metadata.
        assert (labels_df["CustomerID"].to_numpy() == md["CustomerID"].to_numpy()).all()
        assert "ClusterLabel" in labels_df.columns
        assert "IsNoise" in labels_df.columns
        # K-Means does not produce noise; all rows must be non-noise.
        assert labels_df["IsNoise"].sum() == 0

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_kmeans_experiment_log_schema(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-02-test-log-schema",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "n_init": 5, "max_iter": 100},
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
            "n_clusters",
            "execution_time",
            "library_versions",
            "platform",
        }
        assert required.issubset(log.keys())
        assert log["status"] == "SUCCESS"
        assert log["algorithm"] == "kmeans"
        assert log["n_clusters"] == 4
        assert "numpy" in log["library_versions"]
        assert "scikit-learn" in log["library_versions"]
