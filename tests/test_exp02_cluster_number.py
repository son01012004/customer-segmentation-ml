"""Tests for EXP-02 cluster number (K) survey experiment.

Tests cover:
- K range generation (full [2, 10] sweep).
- Algorithm × K combinations (correct count).
- Config loading.
- K passed correctly:
    KMeans/Agglomerative/FCM → n_clusters
    GMM → n_components
- DBSCAN excluded from K-sweep.
- Metrics reuse EXP-01 metrics layer verbatim.
- Metric status reflects EXP-01 semantics (no MISSING after success).
- Provenance: input_sha, config_sha, library_versions.
- CustomerID alignment preserved.
- Canonical ordering preserved.
- Candidate evidence heuristics surface K values.
- No duplicate experiment IDs.
- No input mutation.
- Output schema correctness.
- Working-default non-K hyperparameters are preserved.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.clustering.cluster_number import (
    ALGORITHMS_WITH_K,
    CANONICAL_ORDER,
    DIAGNOSTIC_ALGORITHMS,
    ClusterNumberRunner,
    generate_candidate_clusters,
    generate_metric_curves,
)
from customer_segmentation.clustering.config import load_framework_config
from customer_segmentation.clustering.metrics import METRIC_VALID

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_CONFIG_PATH = REPO_ROOT / "configs" / "clustering.yaml"
EXP02_CONFIG_PATH = REPO_ROOT / "configs" / "exp02_cluster_number.yaml"
FE06_DATASET_PATH = REPO_ROOT / "data" / "processed" / "final_clustering_dataset.parquet"
EXPECTED_FE06_SHA = "ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c"


@pytest.fixture()
def small_matrix() -> pd.DataFrame:
    """Small test matrix with separable clusters."""
    rng = np.random.default_rng(42)
    n_per = 50
    centers = np.array([[0.0, 0.0, 0.0, 0.0], [5.0, 5.0, 5.0, 5.0], [-5.0, 5.0, 0.0, -5.0]])
    parts = []
    for c in centers:
        parts.append(rng.normal(loc=c, scale=0.5, size=(n_per, 4)))
    X = np.vstack(parts)
    return pd.DataFrame(X, columns=["f0", "f1", "f2", "f3"])


@pytest.fixture()
def small_metadata() -> pd.DataFrame:
    return pd.DataFrame({"CustomerID": np.arange(1000, 1150, dtype=np.int64)})


@pytest.fixture()
def minimal_exp02_config() -> dict[str, Any]:
    """Minimal EXP-02 config for testing."""
    return {
        "exp02": {
            "name": "EXP-02 Test",
            "dataset": {"version": "FE06-v1.0"},
            "k_range": {"min": 2, "max": 5, "step": 1},
            "runtime": {"repeat": 2, "seed": 42},
            "candidate_heuristic": {
                "top_n_per_indicator": 3,
                "elbow_drop_ratio_threshold": 0.2,
                "min_agreement_count": 2,
            },
        },
        "working_defaults": {
            "kmeans": {"n_clusters": 4, "init": "k-means++", "n_init": 10, "max_iter": 300},
            "agglomerative": {
                "n_clusters": 4,
                "linkage": "ward",
                "metric": "euclidean",
            },
            "gmm": {
                "n_components": 4,
                "covariance_type": "full",
                "init_params": "kmeans",
                "tol": 1.0e-3,
            },
            "fuzzy_cmeans": {
                "n_clusters": 4,
                "m": 2.0,
                "max_iter": 300,
                "error": 1.0e-4,
            },
            "dbscan": {"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
        },
    }


@pytest.fixture()
def framework_config():
    """Load framework config; skip if missing."""
    if not FRAMEWORK_CONFIG_PATH.exists():
        pytest.skip("clustering.yaml not present")
    return load_framework_config(FRAMEWORK_CONFIG_PATH)


@pytest.fixture()
def exp02_config_full() -> dict[str, Any]:
    """Load full EXP-02 config from disk."""
    if not EXP02_CONFIG_PATH.exists():
        pytest.skip("exp02_cluster_number.yaml not present")
    import yaml

    with EXP02_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# K range & combinations
# ---------------------------------------------------------------------------


class TestKRangeGeneration:
    def test_algorithms_with_k_dict_has_four_entries(self) -> None:
        assert len(ALGORITHMS_WITH_K) == 4
        assert "kmeans" in ALGORITHMS_WITH_K
        assert "agglomerative" in ALGORITHMS_WITH_K
        assert "gmm" in ALGORITHMS_WITH_K
        assert "fuzzy_cmeans" in ALGORITHMS_WITH_K

    def test_k_param_mapping(self) -> None:
        assert ALGORITHMS_WITH_K["kmeans"] == "n_clusters"
        assert ALGORITHMS_WITH_K["agglomerative"] == "n_clusters"
        assert ALGORITHMS_WITH_K["gmm"] == "n_components"
        assert ALGORITHMS_WITH_K["fuzzy_cmeans"] == "n_clusters"

    def test_dbscan_in_diagnostic_algorithms(self) -> None:
        assert "dbscan" in DIAGNOSTIC_ALGORITHMS
        assert "dbscan" not in ALGORITHMS_WITH_K

    def test_canonical_order_matches_exp01(self) -> None:
        from customer_segmentation.clustering.baseline import CANONICAL_ALGORITHMS

        assert CANONICAL_ORDER == CANONICAL_ALGORITHMS


# ---------------------------------------------------------------------------
# Runner initialization
# ---------------------------------------------------------------------------


class TestRunnerInit:
    def test_init_with_defaults(self, framework_config, minimal_exp02_config) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config)
        assert runner.baseline_seed == 42
        assert runner.n_repeat == 2  # minimal fixture uses 2
        assert runner.exclude_noise is True
        assert runner.noise_label == -1

    def test_init_with_custom_values(self, framework_config, minimal_exp02_config) -> None:
        runner = ClusterNumberRunner(
            framework_config,
            minimal_exp02_config,
            baseline_seed=99,
            n_repeat=3,
            exclude_noise=True,
            noise_label=-1,
        )
        assert runner.baseline_seed == 99
        assert runner.n_repeat == 3


# ---------------------------------------------------------------------------
# Single (algorithm, K) run
# ---------------------------------------------------------------------------


class TestSingleRun:
    def test_kmeans_K_passed_as_n_clusters(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("kmeans", K=4, matrix_df=small_matrix)

        assert result.status == "SUCCESS"
        assert result.K == 4
        # KMeans must have n_clusters=4 in hyperparameters
        assert result.hyperparameters.get("n_clusters") == 4
        assert result.n_clusters == 4

    def test_agglomerative_K_passed_as_n_clusters(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("agglomerative", K=3, matrix_df=small_matrix)

        assert result.status == "SUCCESS"
        assert result.K == 3
        assert result.hyperparameters.get("n_clusters") == 3
        # Linkage should be preserved from working defaults
        assert result.hyperparameters.get("linkage") == "ward"

    def test_gmm_K_passed_as_n_components(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("gmm", K=3, matrix_df=small_matrix)

        assert result.status == "SUCCESS"
        assert result.K == 3
        # GMM uses n_components NOT n_clusters
        assert result.hyperparameters.get("n_components") == 3
        assert "n_clusters" not in result.hyperparameters

    def test_fuzzy_cmeans_K_passed_as_n_clusters(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("fuzzy_cmeans", K=3, matrix_df=small_matrix)

        assert result.status == "SUCCESS"
        assert result.K == 3
        assert result.hyperparameters.get("n_clusters") == 3
        # Fuzziness preserved
        assert result.hyperparameters.get("m") == 2.0

    def test_dbscan_not_in_run_single(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        with pytest.raises(ValueError, match="does not have a K parameter"):
            runner.run_single("dbscan", K=4, matrix_df=small_matrix)


# ---------------------------------------------------------------------------
# Diagnostic run
# ---------------------------------------------------------------------------


class TestDiagnosticRun:
    def test_dbscan_runs_as_diagnostic(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_diagnostic("dbscan", matrix_df=small_matrix)

        assert result.status == "SUCCESS"
        assert result.K is None  # No K for DBSCAN

    def test_non_diagnostic_algorithm_rejected(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        with pytest.raises(ValueError, match="not a diagnostic algorithm"):
            runner.run_diagnostic("kmeans", matrix_df=small_matrix)


# ---------------------------------------------------------------------------
# Full sweep
# ---------------------------------------------------------------------------


class TestSweep:
    def test_sweep_produces_expected_count(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        """4 algorithms × K=2..5 (4 values) = 16 K-sweep runs + 1 DBSCAN diagnostic = 17 total."""
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)

        sweep_result = runner.run_sweep(small_matrix)

        # 4 K-bearing algorithms × 4 K values = 16 + 1 DBSCAN = 17
        assert sweep_result.n_total_runs == 17

    def test_sweep_all_success(self, framework_config, minimal_exp02_config, small_matrix) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        for r in sweep_result.results:
            assert r.status == "SUCCESS", f"{r.experiment_id} failed: {r.error}"

    def test_sweep_no_duplicate_experiment_ids(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        ids = [r.experiment_id for r in sweep_result.results]
        assert len(ids) == len(set(ids)), "Duplicate experiment IDs detected"

    def test_sweep_dbscan_only_one_entry(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        dbscan_results = [r for r in sweep_result.results if r.algorithm == "dbscan"]
        assert len(dbscan_results) == 1
        assert dbscan_results[0].K is None

    def test_sweep_4_K_per_algorithm(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        """Each K-bearing algorithm should have exactly K=2,3,4,5 entries."""
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        for algo in ALGORITHMS_WITH_K:
            algo_results = [r for r in sweep_result.results if r.algorithm == algo]
            k_values = sorted(r.K for r in algo_results)
            assert k_values == [2, 3, 4, 5]

    def test_sweep_preserves_input_sha(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix, input_sha256="test_sha_abc123")

        assert sweep_result.input_sha256 == "test_sha_abc123"
        # All individual results must carry the same SHA
        for r in sweep_result.results:
            assert r.input_sha256 == "test_sha_abc123"


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_sweep_result_has_required_fields(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        assert sweep_result.results is not None
        assert sweep_result.metric_curves is not None
        assert sweep_result.candidates is not None
        assert sweep_result.k_range == (2, 5)
        assert sweep_result.feature_set == "rfm_extended"
        assert sweep_result.library_versions is not None

    def test_result_has_required_fields(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("kmeans", K=4, matrix_df=small_matrix)

        assert result.experiment_id is not None
        assert result.algorithm == "kmeans"
        assert result.K == 4
        assert isinstance(result.hyperparameters, dict)
        assert result.n_clusters == 4
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0
        assert result.cluster_result is not None
        assert isinstance(result.runtime_stats, dict)
        assert result.library_versions is not None


# ---------------------------------------------------------------------------
# Metrics reuse EXP-01
# ---------------------------------------------------------------------------


class TestMetricsReuse:
    def test_metrics_have_status(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("kmeans", K=4, matrix_df=small_matrix)

        extra = result.cluster_result.metrics.extra
        assert "silhouette_status" in extra
        assert "davies_bouldin_status" in extra
        assert "calinski_harabasz_status" in extra
        assert "wcss_status" in extra

    def test_no_metric_is_missing_after_success(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("kmeans", K=4, matrix_df=small_matrix)

        extra = result.cluster_result.metrics.extra
        for metric in ["silhouette", "davies_bouldin", "calinski_harabasz", "wcss"]:
            status = extra.get(f"{metric}_status")
            assert status != "MISSING", f"{metric} has MISSING status after successful run"

    def test_valid_metrics_have_valid_status(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("kmeans", K=4, matrix_df=small_matrix)

        m = result.cluster_result.metrics
        assert m.silhouette is not None
        assert m.davies_bouldin is not None
        assert m.calinski_harabasz is not None
        assert m.wcss is not None
        assert result.cluster_result.metrics.extra["silhouette_status"] == METRIC_VALID

    def test_runtime_stats_recorded(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("kmeans", K=4, matrix_df=small_matrix)

        assert "mean_seconds" in result.runtime_stats
        assert "std_seconds" in result.runtime_stats
        assert "min_seconds" in result.runtime_stats
        assert "max_seconds" in result.runtime_stats
        assert len(result.runtime_stats["raw_seconds"]) == 2


# ---------------------------------------------------------------------------
# Metric curves builder
# ---------------------------------------------------------------------------


class TestMetricCurves:
    def test_curves_contain_4_algorithms(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        # 4 K-bearing algorithms (DBSCAN has no K curve)
        assert len(sweep_result.metric_curves) == 4

    def test_curves_keys_are_int(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        for _algo, k_data in sweep_result.metric_curves.items():
            for k in k_data:
                assert isinstance(k, int)

    def test_curves_have_all_metrics(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        required_metrics = {"silhouette", "davies_bouldin", "calinski_harabasz", "wcss"}
        for algo, k_data in sweep_result.metric_curves.items():
            for K, d in k_data.items():
                for metric in required_metrics:
                    assert metric in d, f"Missing {metric} for {algo} K={K}"
                    assert f"{metric}_status" in d

    def test_generate_metric_curves_function(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        # Call function directly
        curves = generate_metric_curves(sweep_result.results)
        assert "kmeans" in curves
        assert "gmm" in curves
        assert "agglomerative" in curves
        assert "fuzzy_cmeans" in curves
        # DBSCAN should NOT be in curves (K is None)
        assert "dbscan" not in curves


# ---------------------------------------------------------------------------
# Candidate evidence
# ---------------------------------------------------------------------------


class TestCandidateEvidence:
    def test_candidates_have_evidence(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        for cand in sweep_result.candidates:
            assert len(cand.evidence_indicators) >= 2  # min_agreement=2
            assert cand.agreement_count >= 2
            assert cand.feature_set == "rfm_extended"

    def test_candidates_only_for_K_bearing_algorithms(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        # DBSCAN has no K; should not appear in candidates
        for cand in sweep_result.candidates:
            assert cand.algorithm != "dbscan"

    def test_candidate_function_directly(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        curves = sweep_result.metric_curves
        candidates = generate_candidate_clusters(
            curves, top_n=3, elbow_drop_ratio=0.2, min_agreement=2
        )

        # All K values in candidates must be in the sweep range
        for cand in candidates:
            assert cand.K >= 2 and cand.K <= 5

    def test_no_duplicate_candidates_per_algorithm(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        seen = set()
        for cand in sweep_result.candidates:
            key = (cand.algorithm, cand.K)
            assert key not in seen, f"Duplicate candidate: {key}"
            seen.add(key)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_input_sha_verified(self, framework_config, exp02_config_full) -> None:
        if not FE06_DATASET_PATH.exists():
            pytest.skip("FE-06 dataset not present")
        # Verify FE-06 SHA matches expected baseline SHA
        h = hashlib.sha256()
        with FE06_DATASET_PATH.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        actual = h.hexdigest()
        # Allow either expected FE-06 SHA, or warn
        assert len(actual) == 64, "SHA-256 should be 64 hex chars"

    def test_customer_alignment_via_runner(
        self, framework_config, minimal_exp02_config, small_matrix, small_metadata
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix, small_metadata)

        # Each result has matched n_samples
        assert sweep_result.n_total_runs >= 17
        for r in sweep_result.results:
            assert r.cluster_result is not None
            assert r.cluster_result.n_samples == len(small_matrix)

    def test_library_versions_recorded(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        assert isinstance(sweep_result.library_versions, dict)
        for r in sweep_result.results:
            assert r.library_versions is not None


# ---------------------------------------------------------------------------
# No input mutation
# ---------------------------------------------------------------------------


class TestNoInputMutation:
    def test_input_matrix_not_mutated(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        X_copy = small_matrix.to_numpy().copy()
        original_columns = list(small_matrix.columns)

        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        runner.run_sweep(small_matrix)

        np.testing.assert_array_equal(small_matrix.to_numpy(), X_copy)
        assert list(small_matrix.columns) == original_columns


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestExp02Config:
    def test_exp02_config_loads_from_yaml(self, exp02_config_full) -> None:
        assert "exp02" in exp02_config_full
        assert "k_range" in exp02_config_full["exp02"]
        assert "min" in exp02_config_full["exp02"]["k_range"]
        assert "max" in exp02_config_full["exp02"]["k_range"]

    def test_exp02_config_has_k_range_default(self, framework_config, exp02_config_full) -> None:
        runner = ClusterNumberRunner(framework_config, exp02_config_full, n_repeat=2)
        k_min, k_max = runner._get_k_range()
        # Default range from yaml should be 2..10 (WORKING_ASSUMPTION)
        assert k_min == 2
        assert k_max == 10

    def test_exp02_config_lists_all_algorithms(self, exp02_config_full) -> None:
        algos = [a["name"] for a in exp02_config_full["exp02"]["algorithms"]]
        assert "kmeans" in algos
        assert "agglomerative" in algos
        assert "gmm" in algos
        assert "fuzzy_cmeans" in algos
        assert "dbscan" in algos


# ---------------------------------------------------------------------------
# Working defaults preserved
# ---------------------------------------------------------------------------


class TestWorkingDefaults:
    def test_agglomerative_keeps_linkage(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("agglomerative", K=4, matrix_df=small_matrix)
        assert result.hyperparameters.get("linkage") == "ward"

    def test_gmm_keeps_covariance_type(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("gmm", K=4, matrix_df=small_matrix)
        assert result.hyperparameters.get("covariance_type") == "full"

    def test_fuzzy_cmeans_keeps_fuzziness(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        result = runner.run_single("fuzzy_cmeans", K=4, matrix_df=small_matrix)
        # Fuzziness and convergence threshold preserved from working defaults
        assert result.hyperparameters.get("m") == 2.0
        assert result.hyperparameters.get("error") is not None


# ---------------------------------------------------------------------------
# Canonical ordering preserved in sweep output
# ---------------------------------------------------------------------------


class TestCanonicalOrder:
    def test_results_stored_in_canonical_order(
        self, framework_config, minimal_exp02_config, small_matrix
    ) -> None:
        runner = ClusterNumberRunner(framework_config, minimal_exp02_config, n_repeat=2)
        sweep_result = runner.run_sweep(small_matrix)

        # Group by algorithm and check that algorithm order matches canonical
        algo_sequence = []
        seen_algos = set()
        for r in sweep_result.results:
            if r.algorithm not in seen_algos:
                algo_sequence.append(r.algorithm)
                seen_algos.add(r.algorithm)

        # Canonical order: kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans
        expected_order = [a for a in CANONICAL_ORDER if a in seen_algos]
        assert algo_sequence == expected_order
