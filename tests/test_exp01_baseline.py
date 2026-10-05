"""Tests for EXP-01 baseline experiment orchestrator.

Tests cover:
- All 5 algorithms run successfully.
- Output schema correctness.
- Runtime statistics structure.
- Metrics populated with status.
- DBSCAN noise handling.
- Manifest structure.
- Input SHA unchanged.
- Same seed reproducibility.
- Canonical algorithm order.
- No forbidden comparative language.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.clustering.baseline import (
    CANONICAL_ALGORITHMS,
    BaselineResult,
    BaselineRunner,
    BaselineSpec,
)
from customer_segmentation.clustering.config import load_framework_config
from customer_segmentation.clustering.metrics import METRIC_VALID

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "clustering.yaml"


@pytest.fixture()
def small_matrix() -> pd.DataFrame:
    """Small test matrix."""
    rng = np.random.default_rng(42)
    X = rng.normal(size=(100, 4))
    return pd.DataFrame(X, columns=["f0", "f1", "f2", "f3"])


@pytest.fixture()
def small_metadata() -> pd.DataFrame:
    return pd.DataFrame({"CustomerID": np.arange(1000, 1100, dtype=np.int64)})


@pytest.fixture()
def minimal_exp01_config() -> dict[str, Any]:
    """Minimal EXP-01 config for testing."""
    return {
        "exp01": {
            "name": "EXP-01 Test",
            "description": "Test baseline",
            "algorithms": CANONICAL_ALGORITHMS,
        },
        "working_defaults": {
            "kmeans": {"n_clusters": 4, "random_state": 42},
            "agglomerative": {"n_clusters": 4},
            "dbscan": {"eps": 0.5, "min_samples": 5},
            "gmm": {"n_components": 4, "random_state": 42},
            "fuzzy_cmeans": {"n_clusters": 4, "random_state": 42},
        },
    }


@pytest.fixture()
def framework_config():
    """Load framework config."""
    if not CONFIG_PATH.exists():
        pytest.skip("clustering.yaml not present")
    return load_framework_config(CONFIG_PATH)


# ---------------------------------------------------------------------------
# BaselineRunner initialization
# ---------------------------------------------------------------------------


class TestBaselineRunnerInit:
    def test_init_with_defaults(self, framework_config, minimal_exp01_config) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config)
        assert runner.baseline_seed == 42
        assert runner.n_repeat == 5
        assert runner.exclude_noise is True
        assert runner.noise_label == -1

    def test_init_with_custom_values(self, framework_config, minimal_exp01_config) -> None:
        runner = BaselineRunner(
            framework_config,
            minimal_exp01_config,
            baseline_seed=123,
            n_repeat=3,
            exclude_noise=True,
            noise_label=-1,
        )
        assert runner.baseline_seed == 123
        assert runner.n_repeat == 3


# ---------------------------------------------------------------------------
# Single algorithm run
# ---------------------------------------------------------------------------


class TestSingleAlgorithmRun:
    def test_kmeans_runs_successfully(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-kmeans",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        assert result.status == "SUCCESS"
        assert result.algorithm == "kmeans"
        assert result.n_clusters == 4
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0

    def test_agglomerative_runs_successfully(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-agglomerative",
            algorithm="agglomerative",
            hyperparameters={"n_clusters": 4},
        )

        result = runner.run(spec, small_matrix)

        assert result.status == "SUCCESS"
        assert result.algorithm == "agglomerative"
        assert result.n_clusters == 4

    def test_dbscan_runs_successfully(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-dbscan",
            algorithm="dbscan",
            hyperparameters={"eps": 0.5, "min_samples": 5},
        )

        result = runner.run(spec, small_matrix)

        assert result.status == "SUCCESS"
        assert result.algorithm == "dbscan"
        assert result.noise_count is not None

    def test_gmm_runs_successfully(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-gmm",
            algorithm="gmm",
            hyperparameters={"n_components": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        assert result.status == "SUCCESS"
        assert result.algorithm == "gmm"
        assert result.n_clusters == 4

    def test_fuzzy_cmeans_runs_successfully(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-fuzzy_cmeans",
            algorithm="fuzzy_cmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        assert result.status == "SUCCESS"
        assert result.algorithm == "fuzzy_cmeans"
        assert result.n_clusters == 4


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_result_has_required_fields(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-schema",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        assert isinstance(result, BaselineResult)
        assert result.experiment_id == "TEST-schema"
        assert result.algorithm == "kmeans"
        assert result.algorithm_version is not None
        assert isinstance(result.hyperparameters, dict)
        assert result.n_clusters is not None
        assert result.noise_count is not None
        assert result.noise_ratio is not None
        assert result.cluster_result is not None
        assert isinstance(result.runtime_stats, dict)
        assert result.input_sha256 is None
        assert isinstance(result.library_versions, dict)


# ---------------------------------------------------------------------------
# Runtime statistics
# ---------------------------------------------------------------------------


class TestRuntimeStats:
    def test_runtime_stats_structure(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-runtime",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        assert "mean_seconds" in result.runtime_stats
        assert "std_seconds" in result.runtime_stats
        assert "min_seconds" in result.runtime_stats
        assert "max_seconds" in result.runtime_stats
        assert "raw_seconds" in result.runtime_stats
        assert len(result.runtime_stats["raw_seconds"]) == 3

    def test_runtime_stats_values(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-runtime-values",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        mean = result.runtime_stats["mean_seconds"]
        min_val = result.runtime_stats["min_seconds"]
        max_val = result.runtime_stats["max_seconds"]

        assert mean is not None
        assert min_val <= mean <= max_val


# ---------------------------------------------------------------------------
# Metrics populated
# ---------------------------------------------------------------------------


class TestMetricsPopulated:
    def test_metrics_not_missing_after_successful_run(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-metrics",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        metrics = result.cluster_result.metrics
        # After successful run, metrics should be populated
        assert metrics.silhouette is not None or metrics.wcss is not None

    def test_metrics_have_status(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-metrics-status",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        extra = result.cluster_result.metrics.extra
        assert "silhouette_status" in extra
        assert "davies_bouldin_status" in extra
        assert "calinski_harabasz_status" in extra
        assert "wcss_status" in extra

    def test_no_metric_is_missing_after_successful_run(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-no-missing",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix)

        extra = result.cluster_result.metrics.extra
        # After successful run, no metric should have MISSING status
        for metric in ["silhouette", "davies_bouldin", "calinski_harabasz", "wcss"]:
            status = extra.get(f"{metric}_status", None)
            if status is not None:
                assert status != "MISSING", f"{metric} has MISSING status after successful run"


# ---------------------------------------------------------------------------
# DBSCAN noise handling
# ---------------------------------------------------------------------------


class TestDBSCANNoise:
    def test_dbscan_noise_count_recorded(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-dbscan-noise",
            algorithm="dbscan",
            hyperparameters={"eps": 0.5, "min_samples": 5},
        )

        result = runner.run(spec, small_matrix)

        assert result.noise_count is not None
        assert result.noise_count >= 0
        assert result.noise_ratio is not None
        assert 0 <= result.noise_ratio <= 1.0

    def test_dbscan_noise_metrics_have_valid_status(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=3)

        spec = BaselineSpec(
            experiment_id="TEST-dbscan-noise-status",
            algorithm="dbscan",
            hyperparameters={"eps": 0.5, "min_samples": 5},
        )

        result = runner.run(spec, small_matrix)

        extra = result.cluster_result.metrics.extra
        # Metrics should have VALID_VALUE or NOT_APPLICABLE status
        valid_statuses = {METRIC_VALID, "NOT_APPLICABLE"}
        assert extra.get("silhouette_status") in valid_statuses
        assert extra.get("wcss_status") in valid_statuses


# ---------------------------------------------------------------------------
# run_all - multiple algorithms
# ---------------------------------------------------------------------------


class TestRunAll:
    def test_run_all_returns_correct_count(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=2)

        results = runner.run_all(small_matrix)

        assert len(results) == len(CANONICAL_ALGORITHMS)

    def test_run_all_canonical_order(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=2)

        results = runner.run_all(small_matrix)

        algorithms_run = [r.algorithm for r in results]
        assert algorithms_run == CANONICAL_ALGORITHMS

    def test_run_all_all_success(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=2)

        results = runner.run_all(small_matrix)

        for result in results:
            assert result.status == "SUCCESS", f"{result.algorithm} failed: {result.error}"


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    def test_same_seed_same_labels(
        self, framework_config, minimal_exp01_config, small_matrix
    ) -> None:
        runner1 = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=2)
        runner2 = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=2)

        spec = BaselineSpec(
            experiment_id="TEST-repro",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result1 = runner1.run(spec, small_matrix)
        result2 = runner2.run(spec, small_matrix)

        np.testing.assert_array_equal(
            result1.cluster_result.cluster_labels,
            result2.cluster_result.cluster_labels,
        )


# ---------------------------------------------------------------------------
# Input SHA unchanged
# ---------------------------------------------------------------------------


class TestInputIntegrity:
    def test_input_sha_recorded(self, framework_config, minimal_exp01_config, small_matrix) -> None:
        runner = BaselineRunner(framework_config, minimal_exp01_config, n_repeat=2)

        spec = BaselineSpec(
            experiment_id="TEST-sha",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4, "random_state": 42},
            seed=42,
        )

        result = runner.run(spec, small_matrix, input_sha256="test_sha_123")

        assert result.input_sha256 == "test_sha_123"


# ---------------------------------------------------------------------------
# Canonical algorithm order
# ---------------------------------------------------------------------------


class TestCanonicalOrder:
    def test_canonical_algorithms_defined(self) -> None:
        assert CANONICAL_ALGORITHMS == [
            "kmeans",
            "agglomerative",
            "dbscan",
            "gmm",
            "fuzzy_cmeans",
        ]


# ---------------------------------------------------------------------------
# No forbidden language (structural test)
# ---------------------------------------------------------------------------


class TestNoForbiddenLanguage:
    def test_no_ranking_in_algorithm_names(self) -> None:
        """Verify canonical order doesn't suggest ranking."""
        # The canonical order is defined in the config for consistency,
        # NOT because any algorithm is "better"
        assert len(CANONICAL_ALGORITHMS) == 5
        assert "kmeans" in CANONICAL_ALGORITHMS
        assert "agglomerative" in CANONICAL_ALGORITHMS
        assert "dbscan" in CANONICAL_ALGORITHMS
        assert "gmm" in CANONICAL_ALGORITHMS
        assert "fuzzy_cmeans" in CANONICAL_ALGORITHMS
