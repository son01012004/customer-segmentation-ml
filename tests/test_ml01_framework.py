"""Tests for the ML-01 clustering experiment framework.

The tests are organised by responsibility:

- :class:`TestBaseAlgorithm` — abstract interface contract.
- :class:`TestRegistry` — registry semantics.
- :class:`TestValidation` — input + customer alignment validation.
- :class:`TestResultSchema` — schema fields, JSON serialisation.
- :class:`TestRunner` — end-to-end experiment run, including
  reproducibility, error handling, and artifact writing.
- :class:`TestArtifactWriting` — CustomerID alignment + DBSCAN noise
  preservation.
- :class:`TestConfig` — YAML loader.
- :class:`TestIntegrationWithFE06` — real FE-06 dataset path (skipped
  if absent).

The tests use small **toy / mock** algorithm adapters that satisfy
the ``BaseClusterAlgorithm`` interface. No real K-Means / DBSCAN
implementation is tested here; ML-02 → ML-06 will plug the production
algorithms in.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.clustering import (  # noqa: E402
    AlgorithmFamily,
    AlgorithmRegistry,
    AlgorithmRegistryError,
    BaseClusterAlgorithm,
    ClusterAlgorithmError,
    ClusteringInputError,
    ClusterResult,
    ExperimentResult,
    ExperimentRunner,
    ExperimentSpec,
    ExperimentStatus,
    FrameworkConfig,
    FrameworkConfigError,
    IdentifierLeakageError,
    MetricsResult,
    RunnerError,
    capture_library_versions,
    capture_platform_info,
    cluster_result_to_dict,
    compute_text_sha256,
    framework_config_to_dict,
    get_logger,
    load_framework_config,
    resolve_framework_config_path,
    resolve_random_seed,
    validate_clustering_matrix,
    validate_customer_alignment,
)

# ---------------------------------------------------------------------------
# Toy algorithm adapters (registered under unique names for testing)
# ---------------------------------------------------------------------------


class ToyHardAlgorithm(BaseClusterAlgorithm):
    """Toy hard clustering adapter. Splits points by sign of first feature."""

    version = "toy_hard_v1"
    family = AlgorithmFamily.HARD

    def __init__(self, k: int = 3, seed: int | None = None) -> None:
        self.k = k
        self.seed = seed

    def fit(self, X: np.ndarray) -> ClusterResult:
        if X.ndim != 2:
            raise ClusterAlgorithmError("ToyHard expects a 2-D matrix.")
        # Simple deterministic labelling: bucket by quantile of column 0.
        if self.k <= 0:
            raise ClusterAlgorithmError("k must be >= 1.")
        col = X[:, 0]
        try:
            edges = np.quantile(col, np.linspace(0, 1, self.k + 1)[1:-1])
        except ValueError as exc:
            raise ClusterAlgorithmError(str(exc)) from exc
        labels = np.zeros(X.shape[0], dtype=np.int64)
        for edge in edges:
            labels[col > edge] += 1
        n_clusters = int(labels.max()) + 1
        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=X.shape[0],
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=n_clusters,
            supports_random_state=True,
            random_seed_used=self.seed,
        )


class ToyNoiseAlgorithm(BaseClusterAlgorithm):
    """Toy DBSCAN-like adapter. Last 10% of rows marked as noise."""

    version = "toy_noise_v1"
    family = AlgorithmFamily.DENSITY_BASED

    def __init__(self, noise_ratio: float = 0.1) -> None:
        if not 0 < noise_ratio < 1:
            raise ClusterAlgorithmError("noise_ratio must be in (0, 1).")
        self.noise_ratio = float(noise_ratio)

    def fit(self, X: np.ndarray) -> ClusterResult:
        n = X.shape[0]
        k = max(int(round((1 - self.noise_ratio) * n)), 1)
        labels = np.zeros(n, dtype=np.int64)
        labels[:k] = (np.arange(k) % 3).astype(np.int64)
        labels[k:] = -1
        unique_clusters = sorted(set(labels.tolist()))
        n_clusters_real = sum(1 for c in unique_clusters if c != -1)
        noise_count = int((labels == -1).sum())
        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=n,
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=n_clusters_real,
            noise_label=-1,
            noise_count=noise_count,
            noise_ratio=noise_count / n,
            supports_random_state=False,  # deterministic toy
            random_seed_used=None,
        )


class ToySoftAlgorithm(BaseClusterAlgorithm):
    """Toy GMM/Fuzzy-like adapter. Returns posterior probabilities."""

    version = "toy_soft_v1"
    family = AlgorithmFamily.MODEL_BASED

    def __init__(self, n_components: int = 4) -> None:
        self.n_components = n_components

    def fit(self, X: np.ndarray) -> ClusterResult:
        n = X.shape[0]
        c = self.n_components
        # Build a deterministic probability matrix: argmax cycles through c.
        rng = np.random.default_rng(0)  # deterministic — no real randomness
        probs = rng.random((n, c))
        probs = probs / probs.sum(axis=1, keepdims=True)
        labels = probs.argmax(axis=1).astype(np.int64)
        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=n,
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=c,
            soft_probabilities=probs,
            supports_random_state=True,
            random_seed_used=None,
        )


class ToyFailingAlgorithm(BaseClusterAlgorithm):
    """Toy adapter that always raises. Used to test FAILED status."""

    version = "toy_failing_v1"
    family = AlgorithmFamily.HARD

    def fit(self, X: np.ndarray) -> ClusterResult:
        raise ClusterAlgorithmError("ToyFailingAlgorithm always fails.")

    def supports_random_state(self) -> bool:
        return True


class ToyDeterministicAlgorithm(BaseClusterAlgorithm):
    """Deterministic toy that respects random_state=False (records truth)."""

    version = "toy_det_v1"
    family = AlgorithmFamily.HARD

    def supports_random_state(self) -> bool:
        return False

    def fit(self, X: np.ndarray) -> ClusterResult:
        labels = (np.arange(X.shape[0]) % 2).astype(np.int64)
        return ClusterResult(
            algorithm=self.name,
            algorithm_version=self.version,
            algorithm_family=self.family,
            n_samples=X.shape[0],
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=2,
            supports_random_state=False,
            random_seed_used=None,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registered_toy_algorithms() -> None:
    """Register toy adapters under unique names; clean up after test."""
    AlgorithmRegistry.clear()
    AlgorithmRegistry.register("toy_hard")(ToyHardAlgorithm)
    AlgorithmRegistry.register("toy_noise")(ToyNoiseAlgorithm)
    AlgorithmRegistry.register("toy_soft")(ToySoftAlgorithm)
    AlgorithmRegistry.register("toy_failing")(ToyFailingAlgorithm)
    AlgorithmRegistry.register("toy_deterministic")(ToyDeterministicAlgorithm)
    yield
    AlgorithmRegistry.clear()


@pytest.fixture()
def small_matrix() -> pd.DataFrame:
    rng = np.random.default_rng(123)
    X = rng.normal(size=(50, 4))
    df = pd.DataFrame(X, columns=["f0", "f1", "f2", "f3"])
    return df


@pytest.fixture()
def small_metadata() -> pd.DataFrame:
    return pd.DataFrame({"CustomerID": np.arange(100, 150, dtype=np.int64)})


@pytest.fixture()
def minimal_framework_yaml(tmp_path: Path) -> Path:
    yaml_text = """\
clustering:
  random_seed: 42
  n_jobs: -1
  preprocessing:
    skewness_correction: "none"
    scaler: "none"
  algorithms:
    kmeans: {enabled: true}
    kmedoids: {enabled: true}
    agglomerative: {enabled: true}
    dbscan: {enabled: true}
  output:
    labels_path: "./data/processed/cluster_labels.parquet"
    models_path: "./data/processed/cluster_models/"
  framework:
    enabled: true
    experiment:
      id: "TEST-ML01"
      description: "minimal test config"
    random_seed:
      default: 42
      per_algorithm_override: {}
    input:
      final_clustering_dataset_path: "./data/processed/final_clustering_dataset.parquet"
      customer_metadata_path: "./data/processed/customer_metadata.parquet"
      dataset_version: "FE06-v1.0"
      customer_key: "CustomerID"
    validation:
      require_no_nan: true
      require_no_inf: true
      require_all_numeric: true
      min_samples: 2
      min_features: 1
      exclude_customer_id_from_features: true
    output:
      artifacts_dir: "./data/processed/clustering_experiments"
      report_dir: "./reports/ml01"
      save_labels: true
      save_metadata: false
      save_algorithm_specific: true
      cluster_labels_filename: "cluster_labels_{experiment_id}.parquet"
      experiment_log_filename: "experiment_log_{experiment_id}.json"
      algorithm_output_filename: "algorithm_output_{experiment_id}.parquet"
    logging:
      log_to_console: false
      log_to_file: false
      log_file_dir: "./reports/ml01"
      log_level: "INFO"
    metadata:
      stage: "ML-01"
      stage_version: "ML01-v1.0"
      stage_status: "TECHNICALLY_IMPLEMENTED"
      scope_boundaries: ["framework only"]
      pending_review_notes: ["none"]
      assumptions: ["none"]
"""
    p = tmp_path / "clustering.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Base algorithm interface
# ---------------------------------------------------------------------------


class TestBaseAlgorithm:
    def test_base_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseClusterAlgorithm()  # type: ignore[abstract]

    def test_subclass_must_implement_fit(self) -> None:
        class Incomplete(BaseClusterAlgorithm):
            name = "incomplete"
            version = "v1"
            family = AlgorithmFamily.HARD

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_get_params_returns_serialisable_dict(self) -> None:
        a = ToyHardAlgorithm(k=4, seed=7)
        params = a.get_params()
        assert params["k"] == 4
        assert params["seed"] == 7
        # Must be JSON-serialisable.
        json.dumps(params)

    def test_supports_random_state_default_true(self) -> None:
        assert ToyHardAlgorithm(k=2).supports_random_state() is True

    def test_supports_random_state_can_be_overridden(self) -> None:
        assert ToyDeterministicAlgorithm().supports_random_state() is False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_register_and_get(self, registered_toy_algorithms: None) -> None:
        cls = AlgorithmRegistry.get("toy_hard")
        assert cls is ToyHardAlgorithm

    def test_unknown_algorithm_raises(self, registered_toy_algorithms: None) -> None:
        with pytest.raises(AlgorithmRegistryError):
            AlgorithmRegistry.get("not_registered")

    def test_list_registered_sorted(self, registered_toy_algorithms: None) -> None:
        assert AlgorithmRegistry.list_registered() == sorted(
            ["toy_hard", "toy_noise", "toy_soft", "toy_failing", "toy_deterministic"]
        )

    def test_double_registration_raises(self) -> None:
        AlgorithmRegistry.clear()
        AlgorithmRegistry.register("dup")(ToyHardAlgorithm)
        try:
            with pytest.raises(AlgorithmRegistryError):
                AlgorithmRegistry.register("dup")(ToyHardAlgorithm)
        finally:
            AlgorithmRegistry.clear()

    def test_invalid_name_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):
            AlgorithmRegistry.register("")  # type: ignore[arg-type]

    def test_non_subclass_registration_raises(self) -> None:
        AlgorithmRegistry.clear()
        try:
            with pytest.raises(AlgorithmRegistryError):

                class NotAnAdapter:
                    pass

                AlgorithmRegistry.register("bad")(NotAnAdapter)  # type: ignore[arg-type]
        finally:
            AlgorithmRegistry.clear()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_matrix_passes(self, small_matrix: pd.DataFrame) -> None:
        report = validate_clustering_matrix(small_matrix)
        assert report.all_passed

    def test_none_matrix_fails_fast(self) -> None:
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(None)  # type: ignore[arg-type]

    def test_empty_matrix_fails(self) -> None:
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(pd.DataFrame())

    def test_nan_matrix_fails(self, small_matrix: pd.DataFrame) -> None:
        df = small_matrix.copy()
        df.iloc[0, 0] = np.nan
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(df)

    def test_inf_matrix_fails(self, small_matrix: pd.DataFrame) -> None:
        df = small_matrix.copy()
        df.iloc[0, 0] = np.inf
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(df)

    def test_non_numeric_matrix_fails(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(df)

    def test_identifier_leakage_raises_special_error(self) -> None:
        df = pd.DataFrame({"CustomerID": [1, 2, 3], "f0": [0.1, 0.2, 0.3]})
        with pytest.raises(IdentifierLeakageError):
            validate_clustering_matrix(df)

    def test_missing_required_feature_fails(self, small_matrix: pd.DataFrame) -> None:
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(small_matrix, expected_features=["f0", "missing"])

    def test_min_samples_enforced(self) -> None:
        df = pd.DataFrame({"f0": [0.1, 0.2]})
        # 2 rows, min_samples=3 → fail
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(df, min_samples=3)

    def test_fail_fast_false_returns_report(self, small_matrix: pd.DataFrame) -> None:
        df = small_matrix.copy()
        df.iloc[0, 0] = np.nan
        report = validate_clustering_matrix(df, fail_fast=False)
        assert not report.all_passed
        assert any(c.status == "FAIL" for c in report.checks)

    def test_constant_feature_fails(self) -> None:
        df = pd.DataFrame({"f0": [1.0, 1.0, 1.0], "f1": [0.0, 0.5, 1.0]})
        with pytest.raises(ClusteringInputError):
            validate_clustering_matrix(df)


# ---------------------------------------------------------------------------
# Customer alignment
# ---------------------------------------------------------------------------


class TestCustomerAlignment:
    def test_valid_alignment_passes(
        self, small_matrix: pd.DataFrame, small_metadata: pd.DataFrame
    ) -> None:
        report = validate_customer_alignment(small_metadata, small_matrix)
        assert report.all_passed

    def test_row_count_mismatch_fails(self, small_matrix: pd.DataFrame) -> None:
        meta = pd.DataFrame({"CustomerID": [1, 2, 3]})
        with pytest.raises(ClusteringInputError):
            validate_customer_alignment(meta, small_matrix)

    def test_duplicate_customer_id_fails(self, small_matrix: pd.DataFrame) -> None:
        meta = pd.DataFrame({"CustomerID": np.zeros(len(small_matrix), dtype=np.int64)})
        with pytest.raises(ClusteringInputError):
            validate_customer_alignment(meta, small_matrix)

    def test_nan_customer_id_fails(self, small_matrix: pd.DataFrame) -> None:
        ids = np.arange(len(small_matrix), dtype=np.float64)
        ids[0] = np.nan
        meta = pd.DataFrame({"CustomerID": ids})
        with pytest.raises(ClusteringInputError):
            validate_customer_alignment(meta, small_matrix)

    def test_missing_customer_key_column_fails(self, small_matrix: pd.DataFrame) -> None:
        meta = pd.DataFrame({"not_customer_id": np.arange(len(small_matrix))})
        with pytest.raises(ClusteringInputError):
            validate_customer_alignment(meta, small_matrix)

    def test_none_metadata_fails(self, small_matrix: pd.DataFrame) -> None:
        with pytest.raises(ClusteringInputError):
            validate_customer_alignment(None, small_matrix)


# ---------------------------------------------------------------------------
# Result schema
# ---------------------------------------------------------------------------


class TestResultSchema:
    def test_cluster_result_required_fields(self) -> None:
        labels = np.array([0, 1, 1, 0], dtype=np.int64)
        r = ClusterResult(
            algorithm="x",
            algorithm_version="v1",
            algorithm_family="hard",
            n_samples=4,
            n_features=2,
            cluster_labels=labels,
            n_clusters=2,
        )
        assert r.algorithm == "x"
        assert r.cluster_labels.shape == (4,)
        assert r.noise_label == -1

    def test_cluster_result_to_dict_is_json_safe(self) -> None:
        labels = np.array([0, 1, 1, 0], dtype=np.int64)
        r = ClusterResult(
            algorithm="x",
            algorithm_version="v1",
            algorithm_family="hard",
            n_samples=4,
            n_features=2,
            cluster_labels=labels,
            n_clusters=2,
        )
        d = r.to_dict()
        json.dumps(d)  # must not raise
        assert d["n_samples"] == 4
        assert d["cluster_labels_shape"] == [4]

    def test_soft_probability_round_trip(self) -> None:
        labels = np.array([0, 1, 2, 0], dtype=np.int64)
        probs = np.array(
            [
                [0.7, 0.2, 0.1],
                [0.1, 0.8, 0.1],
                [0.1, 0.2, 0.7],
                [0.6, 0.3, 0.1],
            ]
        )
        r = ClusterResult(
            algorithm="soft",
            algorithm_version="v1",
            algorithm_family=AlgorithmFamily.MODEL_BASED,
            n_samples=4,
            n_features=2,
            cluster_labels=labels,
            n_clusters=3,
            soft_probabilities=probs,
        )
        d = r.to_dict()
        assert d["soft_probabilities_shape"] == [4, 3]

    def test_noise_preserved(self) -> None:
        labels = np.array([0, 0, -1, -1, 1], dtype=np.int64)
        r = ClusterResult(
            algorithm="noise",
            algorithm_version="v1",
            algorithm_family=AlgorithmFamily.DENSITY_BASED,
            n_samples=5,
            n_features=2,
            cluster_labels=labels,
            n_clusters=2,
            noise_label=-1,
            noise_count=2,
            noise_ratio=0.4,
        )
        assert (r.cluster_labels == -1).sum() == 2
        d = r.to_dict()
        assert d["noise_count"] == 2
        assert d["noise_ratio"] == 0.4

    def test_metrics_default_empty(self) -> None:
        r = ClusterResult(
            algorithm="x",
            algorithm_version="v1",
            algorithm_family="hard",
            n_samples=3,
            n_features=1,
            cluster_labels=np.array([0, 1, 2]),
            n_clusters=3,
        )
        assert isinstance(r.metrics, MetricsResult)
        assert r.metrics.silhouette is None
        assert r.metrics.davies_bouldin is None
        assert r.metrics.calinski_harabasz is None

    def test_experiment_result_to_dict(self) -> None:
        labels = np.array([0, 1, 0], dtype=np.int64)
        cr = ClusterResult(
            algorithm="x",
            algorithm_version="v1",
            algorithm_family="hard",
            n_samples=3,
            n_features=1,
            cluster_labels=labels,
            n_clusters=2,
        )
        er = ExperimentResult(
            experiment_id="e1",
            status=ExperimentStatus.SUCCESS,
            algorithm="x",
            algorithm_version="v1",
            dataset_version="FE06-v1.0",
            dataset_sha256=None,
            input_path=None,
            metadata_path=None,
            feature_set=["f0"],
            feature_count=1,
            n_samples=3,
            hyperparameters={"k": 2},
            random_seed=42,
            random_seed_used=42,
            n_clusters=2,
            cluster_labels=labels,
            execution_time=0.01,
            timestamp="2026-01-01T00:00:00Z",
            cluster_result=cr,
            metrics=cr.metrics,
            artifact_paths={},
        )
        d = cluster_result_to_dict(er)
        assert d["experiment_id"] == "e1"
        assert d["status"] == "SUCCESS"
        assert d["cluster_labels_shape"] == [3]
        json.dumps(d)

    def test_experiment_result_failed(self) -> None:
        er = ExperimentResult(
            experiment_id="e1",
            status=ExperimentStatus.FAILED,
            algorithm="x",
            algorithm_version="v1",
            dataset_version="FE06-v1.0",
            dataset_sha256=None,
            input_path=None,
            metadata_path=None,
            feature_set=["f0"],
            feature_count=1,
            n_samples=3,
            hyperparameters={"k": 2},
            random_seed=None,
            random_seed_used=None,
            n_clusters=None,
            cluster_labels=None,
            execution_time=0.0,
            timestamp="2026-01-01T00:00:00Z",
            cluster_result=None,
            metrics=MetricsResult(),
            artifact_paths={},
            error={"type": "ValueError", "message": "boom"},
        )
        d = er.to_dict()
        assert d["status"] == "FAILED"
        # Cluster labels are not serialised into the log (too large; stored
        # separately as a parquet artifact). The log records shape / dtype.
        assert d["cluster_labels_shape"] is None
        assert d["cluster_labels_dtype"] is None
        assert "cluster_labels" not in d  # intentionally excluded
        assert d["error"]["type"] == "ValueError"


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    def test_same_seed_same_labels(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
    ) -> None:
        # Ensure the YAML loads cleanly even if we don't need the cfg here.
        _ = load_framework_config(minimal_framework_yaml)
        X = small_matrix.to_numpy()

        a1 = ToyHardAlgorithm(k=3, seed=42).fit(X)
        a2 = ToyHardAlgorithm(k=3, seed=42).fit(X)
        np.testing.assert_array_equal(a1.cluster_labels, a2.cluster_labels)

    def test_different_seeds_can_differ(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
    ) -> None:
        X = small_matrix.to_numpy()
        # ToyHard ignores seed in its actual fit (deterministic),
        # but the framework-level seed override still gets recorded.
        a1 = ToyHardAlgorithm(k=3, seed=1).fit(X)
        a2 = ToyHardAlgorithm(k=3, seed=2).fit(X)
        # Labels are deterministic but seed metadata is recorded.
        assert a1.random_seed_used == 1
        assert a2.random_seed_used == 2

    def test_deterministic_algorithm_does_not_get_seed(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        spec = ExperimentSpec(
            experiment_id="ML-01-test-det",
            algorithm="toy_deterministic",
            hyperparameters={},
            seed_override=42,
        )
        runner = ExperimentRunner(
            cfg, spec, config_source=str(minimal_framework_yaml), config_text="dummy"
        )
        result = runner.run(small_matrix, small_metadata, output_dir=tmp_path / "out")
        assert result.status == ExperimentStatus.SUCCESS
        # Deterministic algorithm must report seed=None.
        assert result.random_seed == 42  # requested
        assert result.random_seed_used is None  # not consumed


# ---------------------------------------------------------------------------
# Runner end-to-end
# ---------------------------------------------------------------------------


class TestRunner:
    def test_happy_path(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        spec = ExperimentSpec(
            experiment_id="ML-01-test-hard",
            algorithm="toy_hard",
            hyperparameters={"k": 3, "seed": 7},
            seed_override=7,
        )
        runner = ExperimentRunner(
            cfg, spec, config_source=str(minimal_framework_yaml), config_text="dummy"
        )
        out_dir = tmp_path / "artifacts"
        result = runner.run(
            small_matrix,
            small_metadata,
            input_sha256="abc123",
            input_path="/some/path.parquet",
            metadata_path="/some/meta.parquet",
            output_dir=out_dir,
        )
        assert result.status == ExperimentStatus.SUCCESS
        assert result.n_samples == len(small_matrix)
        assert result.feature_count == small_matrix.shape[1]
        assert result.n_clusters is not None
        assert "cluster_labels" in result.artifact_paths
        assert "experiment_log" in result.artifact_paths
        # Labels match CustomerID count.
        assert result.cluster_labels is not None
        assert len(result.cluster_labels) == len(small_metadata)
        # File exists.
        assert Path(result.artifact_paths["cluster_labels"]).exists()

    def test_failed_status_on_algorithm_exception(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        spec = ExperimentSpec(
            experiment_id="ML-01-test-failing",
            algorithm="toy_failing",
            hyperparameters={},
        )
        runner = ExperimentRunner(
            cfg, spec, config_source=str(minimal_framework_yaml), config_text="dummy"
        )
        result = runner.run(small_matrix, small_metadata, output_dir=tmp_path / "out")
        assert result.status == ExperimentStatus.FAILED
        assert result.cluster_result is None
        assert result.error is not None
        assert result.error["type"] == "ClusterAlgorithmError"
        # Experiment log still written.
        assert "experiment_log" in result.artifact_paths

    def test_failed_status_on_invalid_matrix(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        bad = small_matrix.copy()
        bad.iloc[0, 0] = np.nan
        spec = ExperimentSpec(
            experiment_id="ML-01-test-bad-input",
            algorithm="toy_hard",
            hyperparameters={"k": 2},
        )
        runner = ExperimentRunner(
            cfg, spec, config_source=str(minimal_framework_yaml), config_text="dummy"
        )
        result = runner.run(bad, small_metadata, output_dir=tmp_path / "out")
        assert result.status == ExperimentStatus.FAILED
        assert result.error is not None
        assert "no_nan" in str(result.error)

    def test_unknown_algorithm_raises_runner_error(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        spec = ExperimentSpec(
            experiment_id="ML-01-test-unknown",
            algorithm="does_not_exist",
            hyperparameters={},
        )
        runner = ExperimentRunner(cfg, spec)
        with pytest.raises(RunnerError):
            runner.run(small_matrix, small_metadata)

    def test_runner_records_config_sha(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        text = minimal_framework_yaml.read_text(encoding="utf-8")
        spec = ExperimentSpec(
            experiment_id="ML-01-test-sha",
            algorithm="toy_hard",
            hyperparameters={"k": 2},
        )
        runner = ExperimentRunner(
            cfg, spec, config_source=str(minimal_framework_yaml), config_text=text
        )
        result = runner.run(small_matrix, small_metadata, output_dir=tmp_path / "out")
        assert result.config_sha256 == compute_text_sha256(text)
        assert result.config_source == str(minimal_framework_yaml)


# ---------------------------------------------------------------------------
# Artifact writing (CustomerID alignment + DBSCAN noise)
# ---------------------------------------------------------------------------


class TestArtifactWriting:
    def test_cluster_labels_parquet_aligned(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        spec = ExperimentSpec(
            experiment_id="ML-01-align",
            algorithm="toy_hard",
            hyperparameters={"k": 2},
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(small_matrix, small_metadata, output_dir=tmp_path / "out")
        assert result.status == ExperimentStatus.SUCCESS
        labels_path = Path(result.artifact_paths["cluster_labels"])
        df = pd.read_parquet(labels_path)
        assert "CustomerID" in df.columns
        assert "ClusterLabel" in df.columns
        assert "IsNoise" in df.columns
        assert len(df) == len(small_metadata)
        # CustomerID alignment: row i in labels == row i in metadata.
        np.testing.assert_array_equal(
            df["CustomerID"].to_numpy(), small_metadata["CustomerID"].to_numpy()
        )

    def test_dbscan_noise_preserved_in_artifact(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        spec = ExperimentSpec(
            experiment_id="ML-01-noise",
            algorithm="toy_noise",
            hyperparameters={"noise_ratio": 0.2},
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(small_matrix, small_metadata, output_dir=tmp_path / "out")
        assert result.status == ExperimentStatus.SUCCESS
        labels_path = Path(result.artifact_paths["cluster_labels"])
        df = pd.read_parquet(labels_path)
        # -1 must be preserved.
        assert (df["ClusterLabel"] == -1).sum() == int(result.cluster_result.noise_count)
        assert df["IsNoise"].sum() == (df["ClusterLabel"] == -1).sum()

    def test_soft_output_artifact_written(
        self,
        registered_toy_algorithms: None,
        small_matrix: pd.DataFrame,
        small_metadata: pd.DataFrame,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        spec = ExperimentSpec(
            experiment_id="ML-01-soft",
            algorithm="toy_soft",
            hyperparameters={"n_components": 3},
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(small_matrix, small_metadata, output_dir=tmp_path / "out")
        assert result.status == ExperimentStatus.SUCCESS
        assert "algorithm_output" in result.artifact_paths
        algo_path = Path(result.artifact_paths["algorithm_output"])
        df = pd.read_parquet(algo_path)
        # 3 probability columns + CustomerID.
        prob_cols = [c for c in df.columns if c.startswith("Probability_")]
        assert len(prob_cols) == 3
        np.testing.assert_allclose(df[prob_cols].sum(axis=1).to_numpy(), 1.0, atol=1e-8)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


class TestConfig:
    def test_load_minimal_yaml(self, minimal_framework_yaml: Path) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        assert isinstance(cfg, FrameworkConfig)
        assert cfg.metadata.stage == "ML-01"
        assert cfg.input.dataset_version == "FE06-v1.0"
        assert cfg.experiment.id == "TEST-ML01"

    def test_framework_to_dict_roundtrip(self, minimal_framework_yaml: Path) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        d = framework_config_to_dict(cfg)
        # Must be JSON-serialisable.
        json.dumps(d)
        assert d["experiment"]["id"] == "TEST-ML01"
        assert d["input"]["customer_key"] == "CustomerID"

    def test_missing_framework_section_fails(self, tmp_path: Path) -> None:
        yaml_text = """\
clustering:
  random_seed: 42
  preprocessing: {skewness_correction: "none", scaler: "none"}
  algorithms:
    kmeans: {enabled: true}
  output:
    labels_path: "./x.parquet"
    models_path: "./m/"
"""
        p = tmp_path / "no_framework.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        with pytest.raises(FrameworkConfigError):
            load_framework_config(p)

    def test_disabled_framework_fails(self, tmp_path: Path) -> None:
        yaml_text = """\
clustering:
  random_seed: 42
  preprocessing: {skewness_correction: "none", scaler: "none"}
  algorithms:
    kmeans: {enabled: true}
  output:
    labels_path: "./x.parquet"
    models_path: "./m/"
  framework:
    enabled: false
"""
        p = tmp_path / "disabled.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        with pytest.raises(FrameworkConfigError):
            load_framework_config(p)

    def test_canonical_yaml_loads_when_present(self) -> None:
        path = resolve_framework_config_path()
        if path is None:
            pytest.skip("Canonical clustering.yaml not present.")
        cfg = load_framework_config(path)
        assert cfg.metadata.stage == "ML-01"


# ---------------------------------------------------------------------------
# Seed resolution
# ---------------------------------------------------------------------------


class TestSeedResolution:
    def test_override_wins(self, minimal_framework_yaml: Path) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        req, used = resolve_random_seed(cfg, "toy_hard", override=999)
        assert req == 999
        assert used == 999

    def test_default_used_when_no_override(self, minimal_framework_yaml: Path) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        req, used = resolve_random_seed(cfg, "toy_hard")
        assert req == 42
        assert used == 42

    def test_per_algorithm_override(self, tmp_path: Path) -> None:
        yaml_text = """\
clustering:
  random_seed: 42
  preprocessing: {skewness_correction: "none", scaler: "none"}
  algorithms: {kmeans: {enabled: true}}
  output:
    labels_path: "./x.parquet"
    models_path: "./m/"
  framework:
    enabled: true
    experiment: {id: "t", description: "t"}
    random_seed:
      default: 42
      per_algorithm_override:
        gmm: 123
    input:
      final_clustering_dataset_path: "./d.parquet"
      customer_metadata_path: "./m.parquet"
      dataset_version: "v1"
      customer_key: "CustomerID"
    validation:
      require_no_nan: true
      require_no_inf: true
      require_all_numeric: true
      min_samples: 2
      min_features: 1
      exclude_customer_id_from_features: true
    output:
      artifacts_dir: "./a"
      report_dir: "./r"
      save_labels: true
      save_metadata: false
      save_algorithm_specific: true
      cluster_labels_filename: "c_{experiment_id}.parquet"
      experiment_log_filename: "l_{experiment_id}.json"
      algorithm_output_filename: "o_{experiment_id}.parquet"
    logging:
      log_to_console: false
      log_to_file: false
      log_file_dir: "./r"
      log_level: "INFO"
    metadata:
      stage: "ML-01"
      stage_version: "ML01-v1.0"
      stage_status: "TECHNICALLY_IMPLEMENTED"
"""
        p = tmp_path / "seed.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        cfg = load_framework_config(p)
        # Per-algorithm override for "gmm" → 123.
        req, used = resolve_random_seed(cfg, "gmm")
        assert req == 123 and used == 123
        # No override for "kmeans" → default 42.
        req, used = resolve_random_seed(cfg, "kmeans")
        assert req == 42 and used == 42


# ---------------------------------------------------------------------------
# Environment snapshots
# ---------------------------------------------------------------------------


class TestEnvironmentSnapshots:
    def test_capture_platform_info(self) -> None:
        info = capture_platform_info()
        assert "python" in info
        assert "system" in info
        assert "release" in info
        assert "machine" in info

    def test_capture_library_versions(self) -> None:
        versions = capture_library_versions()
        for key in ("numpy", "pandas", "scipy", "scikit-learn", "pyarrow"):
            assert key in versions
            assert isinstance(versions[key], str)


# ---------------------------------------------------------------------------
# Logger smoke test
# ---------------------------------------------------------------------------


class TestLogger:
    def test_get_logger_returns_logger(self) -> None:
        logger = get_logger()
        assert logger is not None
        # Logging must not raise.
        logger.info("smoke test")


# ---------------------------------------------------------------------------
# Integration with the real FE-06 dataset (skipped if data is absent)
# ---------------------------------------------------------------------------


class TestIntegrationWithFE06:
    def test_run_real_dataset_with_toy_hard(
        self,
        registered_toy_algorithms: None,
        minimal_framework_yaml: Path,
        tmp_path: Path,
    ) -> None:
        matrix_path = _REPO_ROOT / "data" / "processed" / "final_clustering_dataset.parquet"
        meta_path = _REPO_ROOT / "data" / "processed" / "customer_metadata.parquet"
        if not (matrix_path.exists() and meta_path.exists()):
            pytest.skip("FE-06 dataset not present.")

        from dataclasses import replace

        cfg_base = load_framework_config(minimal_framework_yaml)
        cfg = replace(
            cfg_base,
            input=replace(
                cfg_base.input,
                final_clustering_dataset_path=str(matrix_path),
                customer_metadata_path=str(meta_path),
            ),
        )
        spec = ExperimentSpec(
            experiment_id="ML-01-int-toy",
            algorithm="toy_hard",
            hyperparameters={"k": 4},
        )
        runner = ExperimentRunner(
            cfg, spec, config_source=str(minimal_framework_yaml), config_text="real"
        )
        matrix = pd.read_parquet(matrix_path)
        metadata = pd.read_parquet(meta_path)
        result = runner.run(
            matrix,
            metadata,
            input_sha256="placeholder",
            input_path=str(matrix_path),
            metadata_path=str(meta_path),
            output_dir=tmp_path / "out",
        )
        assert result.status == ExperimentStatus.SUCCESS
        assert result.n_samples == 4371
        assert result.feature_count == 14
        assert "CustomerID" not in matrix.columns  # FE-06 invariant

    def test_identifier_leakage_rejected_at_validation(
        self,
        registered_toy_algorithms: None,
        minimal_framework_yaml: Path,
    ) -> None:
        cfg = load_framework_config(minimal_framework_yaml)
        # Build a matrix that leaks CustomerID.
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3, 4, 5],
                "f0": [0.1, 0.2, 0.3, 0.4, 0.5],
                "f1": [0.5, 0.4, 0.3, 0.2, 0.1],
            }
        )
        spec = ExperimentSpec(
            experiment_id="ML-01-leak",
            algorithm="toy_hard",
            hyperparameters={"k": 2},
        )
        runner = ExperimentRunner(cfg, spec)
        with pytest.raises(IdentifierLeakageError):
            runner.run(df, None)
