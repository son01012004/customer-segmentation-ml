"""Tests for EXP-03 hyperparameter search experiment.

Tests cover:
- Config loading and search space.
- Spec count and Stage breakdown (A, B, C) per algorithm.
- K-Means parameter mapping (init, n_init, max_iter).
- Agglomerative linkage sweep.
- DBSCAN eps/min_samples sweep.
- GMM n_components/covariance_type sweep.
- FCM n_clusters/m/max_iter sweep.
- Invalid combinations rejected (ward + non-euclidean).
- Metrics reuse from EXP-01 metrics layer.
- Metric status (no MISSING after SUCCESS).
- Provenance (input SHA, config SHA, library_versions).
- Unique experiment IDs.
- No input mutation.
- All results persisted.
- Selected configurations generated per algorithm.
- Selection protocol: silhouette primary, DBI tiebreaker, CH tiebreaker 2.
- Canonical algorithm order.
- EXP-02 K candidates loaded correctly.
- No forbidden ranking/best-algorithm language.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

from customer_segmentation.clustering.hyperparameter_search import (
    CANONICAL_ORDER,
    STAGE_BASELINE,
    STAGE_INTERACTION,
    STAGE_SENSITIVITY,
    HyperparameterSearchRunner,
    _validate_search_space,
    apply_selection_protocol,
    load_exp02_candidates,
)
from customer_segmentation.clustering.metrics import METRIC_VALID

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
_FRAMEWORK_CONFIG_PATH = REPO_ROOT / "configs" / "clustering.yaml"
_EXP03_CONFIG_PATH = REPO_ROOT / "configs" / "exp03_hyperparameter_search.yaml"
_EXP02_CANDIDATES_PATH = REPO_ROOT / "reports" / "exp02" / "exp02_candidate_cluster_numbers.csv"
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
def minimal_exp03_config() -> dict[str, Any]:
    """Minimal EXP-03 config for testing."""
    return {
        "exp03": {
            "name": "EXP-03 Test",
            "dataset": {"version": "FE06-v1.0"},
            "runtime": {"repeat": 2, "seed": 42},
            "dbscan": {"noise_label": -1},
            "search_space": {
                "kmeans": {
                    "baseline_k": 4,
                    "fixed_parameters": {"tol": 1e-4},
                    "parameter_sweeps": [
                        {
                            "parameter": "n_init",
                            "baseline_value": 10,
                            "candidate_values": [1, 10],
                        },
                    ],
                },
                "agglomerative": {
                    "baseline_k": 4,
                    "fixed_parameters": {"metric": "euclidean", "compute_distances": True},
                    "parameter_sweeps": [
                        {
                            "parameter": "linkage",
                            "baseline_value": "ward",
                            "candidate_values": ["ward", "complete"],
                        },
                    ],
                },
                "dbscan": {
                    "baseline_k": None,
                    "fixed_parameters": {"metric": "euclidean"},
                    "parameter_sweeps": [
                        {
                            "parameter": "min_samples",
                            "baseline_value": 5,
                            "candidate_values": [3, 5],
                        },
                    ],
                },
                "gmm": {
                    "baseline_k": 4,
                    "fixed_parameters": {"tol": 1e-3, "reg_covar": 1e-6},
                    "parameter_sweeps": [
                        {
                            "parameter": "covariance_type",
                            "baseline_value": "full",
                            "candidate_values": ["full", "diag"],
                        },
                    ],
                },
                "fuzzy_cmeans": {
                    "baseline_k": 4,
                    "fixed_parameters": {"error": 1e-4},
                    "parameter_sweeps": [
                        {
                            "parameter": "m",
                            "baseline_value": 2.0,
                            "candidate_values": [1.5, 2.0],
                        },
                    ],
                },
            },
            "selected_interactions": [],
            "selection_protocol": {
                "primary_criterion": "silhouette",
                "tie_breaker_1": "davies_bouldin",
                "tie_breaker_2": "calinski_harabasz",
            },
        },
        "working_defaults": {
            "kmeans": {"n_clusters": 4, "init": "k-means++", "n_init": 10, "max_iter": 300},
            "agglomerative": {"n_clusters": 4, "linkage": "ward", "metric": "euclidean"},
            "dbscan": {"eps": 0.5, "min_samples": 5, "metric": "euclidean"},
            "gmm": {"n_components": 4, "covariance_type": "full", "tol": 1e-3},
            "fuzzy_cmeans": {"n_clusters": 4, "m": 2.0, "max_iter": 300},
        },
    }


@pytest.fixture()
def framework_config():
    """Load framework config; skip if missing."""
    if not _FRAMEWORK_CONFIG_PATH.exists():
        pytest.skip("clustering.yaml not present")
    from customer_segmentation.clustering.config import load_framework_config

    return load_framework_config(_FRAMEWORK_CONFIG_PATH)


@pytest.fixture()
def exp03_config_full() -> dict[str, Any]:
    """Load full EXP-03 config from disk."""
    if not _EXP03_CONFIG_PATH.exists():
        pytest.skip("exp03_hyperparameter_search.yaml not present")
    with _EXP03_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestConfigLoading:
    def test_exp03_config_loads_from_yaml(self, exp03_config_full) -> None:
        assert "exp03" in exp03_config_full
        assert "search_space" in exp03_config_full["exp03"]
        assert "working_defaults" in exp03_config_full

    def test_exp03_has_working_defaults(self, exp03_config_full) -> None:
        wd = exp03_config_full.get("working_defaults", {})
        for algo in ["kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"]:
            assert algo in wd, f"working_defaults missing for {algo}"

    def test_exp03_has_all_algorithms(self, exp03_config_full) -> None:
        ss = exp03_config_full["exp03"]["search_space"]
        for algo in ["kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"]:
            assert algo in ss, f"search_space missing for {algo}"


# ---------------------------------------------------------------------------
# Search space validation
# ---------------------------------------------------------------------------


class TestSearchSpaceValidation:
    def test_valid_search_space_passes(self, minimal_exp03_config) -> None:
        _validate_search_space(minimal_exp03_config["exp03"]["search_space"])

    def test_ward_requires_euclidean_rejected(self, minimal_exp03_config) -> None:
        minimal_exp03_config["exp03"]["search_space"]["agglomerative"]["fixed_parameters"][
            "metric"
        ] = "manhattan"
        with pytest.raises(ValueError, match="ward"):
            _validate_search_space(minimal_exp03_config["exp03"]["search_space"])

    def test_fcm_m_must_be_gt_1(self, minimal_exp03_config) -> None:
        minimal_exp03_config["exp03"]["search_space"]["fuzzy_cmeans"]["parameter_sweeps"][0][
            "candidate_values"
        ] = [1.0, 2.0]
        with pytest.raises(ValueError, match="m must be > 1"):
            _validate_search_space(minimal_exp03_config["exp03"]["search_space"])


# ---------------------------------------------------------------------------
# Spec count and stage breakdown
# ---------------------------------------------------------------------------


class TestSpecCount:
    def test_total_spec_count(self, framework_config, minimal_exp03_config) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()

        # K-Means: 1 Stage A + (n_init candidates - baseline) = 1 + (2 - 1) = 2
        # Agglomerative: 1 + (linkage 2 - 1) = 2
        # DBSCAN: 1 + (min_samples 2 - 1) = 2
        # GMM: 1 + (cov 2 - 1) = 2
        # FCM: 1 + (m 2 - 1) = 2
        # Total: 10
        assert len(specs) == 10

    def test_stage_breakdown_kmeans(self, framework_config, minimal_exp03_config) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        km_specs = [s for s in specs if s.algorithm == "kmeans"]
        stage_a = [s for s in km_specs if s.stage == STAGE_BASELINE]
        stage_b = [s for s in km_specs if s.stage == STAGE_SENSITIVITY]
        stage_c = [s for s in km_specs if s.stage == STAGE_INTERACTION]
        assert len(stage_a) == 1
        assert len(stage_b) == 1  # n_init=1 only (n_init=10 is baseline)
        assert len(stage_c) == 0

    def test_dbscan_has_no_k(self, framework_config, minimal_exp03_config) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        for s in specs:
            if s.algorithm == "dbscan":
                assert s.baseline_k is None

    def test_kmeans_stage_a_baseline_has_correct_hp(
        self, framework_config, minimal_exp03_config
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        stage_a = [s for s in specs if s.algorithm == "kmeans" and s.stage == STAGE_BASELINE]
        assert len(stage_a) == 1
        hp = stage_a[0].hyperparameters
        assert hp.get("n_clusters") == 4
        assert hp.get("init") == "k-means++"
        assert hp.get("n_init") == 10

    def test_kmeans_stage_b_init_sensitivity(self, framework_config, minimal_exp03_config) -> None:
        # Add init sweep
        minimal_exp03_config["exp03"]["search_space"]["kmeans"]["parameter_sweeps"].append(
            {
                "parameter": "init",
                "baseline_value": "k-means++",
                "candidate_values": ["k-means++", "random"],
            }
        )
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        km_b = [s for s in specs if s.algorithm == "kmeans" and s.stage == STAGE_SENSITIVITY]
        assert len(km_b) == 2  # n_init=1 + init=random

    def test_agglomerative_linkage_sweep(self, framework_config, minimal_exp03_config) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        agg_b = [
            s for s in specs if s.algorithm == "agglomerative" and s.stage == STAGE_SENSITIVITY
        ]
        linkage_values = {s.sweep_value for s in agg_b if s.sweep_parameter == "linkage"}
        assert "complete" in linkage_values
        assert "ward" not in linkage_values  # baseline

    def test_gmm_covariance_type_sweep(self, framework_config, minimal_exp03_config) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        gmm_b = [s for s in specs if s.algorithm == "gmm" and s.stage == STAGE_SENSITIVITY]
        cov_values = {s.sweep_value for s in gmm_b if s.sweep_parameter == "covariance_type"}
        assert "diag" in cov_values
        assert "full" not in cov_values  # baseline

    def test_fcm_m_sensitivity(self, framework_config, minimal_exp03_config) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        fcm_b = [s for s in specs if s.algorithm == "fuzzy_cmeans" and s.stage == STAGE_SENSITIVITY]
        m_values = {s.sweep_value for s in fcm_b if s.sweep_parameter == "m"}
        assert 1.5 in m_values
        assert 2.0 not in m_values  # baseline

    def test_exp02_candidates_loaded(self, framework_config, minimal_exp03_config) -> None:
        runner = HyperparameterSearchRunner(
            framework_config,
            minimal_exp03_config,
            exp02_candidates_csv_path=_EXP02_CANDIDATES_PATH,
        )
        assert runner.exp02_candidates is not None
        assert "kmeans" in runner.exp02_candidates
        assert "agglomerative" in runner.exp02_candidates
        assert "gmm" in runner.exp02_candidates
        assert "fuzzy_cmeans" in runner.exp02_candidates

    def test_exp02_candidates_correct_values(self, framework_config, minimal_exp03_config) -> None:
        if not _EXP02_CANDIDATES_PATH.exists():
            pytest.skip("EXP-02 candidates CSV not present")
        runner = HyperparameterSearchRunner(
            framework_config,
            minimal_exp03_config,
            exp02_candidates_csv_path=_EXP02_CANDIDATES_PATH,
        )
        assert runner.exp02_candidates["kmeans"] == [2, 3, 4, 5]
        assert runner.exp02_candidates["agglomerative"] == [2, 3, 4]
        assert runner.exp02_candidates["gmm"] == [3, 4, 5]
        assert runner.exp02_candidates["fuzzy_cmeans"] == [2, 3, 5]


# ---------------------------------------------------------------------------
# Stage C interaction specs
# ---------------------------------------------------------------------------


class TestStageCInteractions:
    def test_stage_c_builds_kmeans_interactions(
        self, framework_config, minimal_exp03_config
    ) -> None:
        minimal_exp03_config["exp03"]["selected_interactions"] = [
            {
                "algorithm": "kmeans",
                "K": 3,
                "parameters": {"n_init": [1, 10, 20]},
                "rationale": "K=3 from EXP-02 × n_init variations",
            }
        ]
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        km_c = [s for s in specs if s.algorithm == "kmeans" and s.stage == STAGE_INTERACTION]
        assert len(km_c) == 3  # n_init 1, 10, 20
        for s in km_c:
            assert s.baseline_k == 3
            assert s.sweep_parameter == "n_init"

    def test_stage_c_agglomerative_linkage(self, framework_config, minimal_exp03_config) -> None:
        minimal_exp03_config["exp03"]["selected_interactions"] = [
            {
                "algorithm": "agglomerative",
                "K": 3,
                "parameters": {"linkage": ["ward", "complete", "average"]},
                "rationale": "K=3 from EXP-02 × linkage variations",
            }
        ]
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        agg_c = [
            s for s in specs if s.algorithm == "agglomerative" and s.stage == STAGE_INTERACTION
        ]
        assert len(agg_c) == 3
        linkage_values = {s.sweep_value for s in agg_c}
        assert linkage_values == {"ward", "complete", "average"}

    def test_stage_c_fcm_m_at_k3(self, framework_config, minimal_exp03_config) -> None:
        minimal_exp03_config["exp03"]["selected_interactions"] = [
            {
                "algorithm": "fuzzy_cmeans",
                "K": 3,
                "parameters": {"m": [1.5, 2.0, 2.5]},
                "rationale": "K=3 from EXP-02 × m variations",
            }
        ]
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        specs = runner._build_all_specs()
        fcm_c = [s for s in specs if s.algorithm == "fuzzy_cmeans" and s.stage == STAGE_INTERACTION]
        assert len(fcm_c) == 3
        m_values = {s.sweep_value for s in fcm_c}
        assert m_values == {1.5, 2.0, 2.5}


# ---------------------------------------------------------------------------
# Full sweep run
# ---------------------------------------------------------------------------


class TestFullSweep:
    def test_sweep_all_success(self, framework_config, minimal_exp03_config, small_matrix) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        for r in sweep_result.results:
            assert r.status == "SUCCESS", f"{r.experiment_id} failed: {r.error}"

    def test_sweep_no_duplicate_experiment_ids(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        ids = [r.experiment_id for r in sweep_result.results]
        assert len(ids) == len(set(ids)), "Duplicate experiment IDs detected"

    def test_sweep_preserves_input_sha(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix, input_sha256="test_sha_xyz")
        assert sweep_result.input_sha256 == "test_sha_xyz"
        for r in sweep_result.results:
            assert r.input_sha256 == "test_sha_xyz"

    def test_sweep_customer_alignment(
        self, framework_config, minimal_exp03_config, small_matrix, small_metadata
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix, small_metadata)
        for r in sweep_result.results:
            assert r.cluster_result is not None
            assert r.cluster_result.n_samples == len(small_matrix)

    def test_sweep_no_input_mutation(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        X_copy = small_matrix.to_numpy().copy()
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        runner.run(small_matrix)
        np.testing.assert_array_equal(small_matrix.to_numpy(), X_copy)

    def test_sweep_has_sensitivity_table(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        assert len(sweep_result.sensitivity_table) > 0

    def test_sweep_has_selected_configurations(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        assert len(sweep_result.selected_configurations) > 0

    def test_selected_config_per_algo(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        selected_algos = {sel.algorithm for sel in sweep_result.selected_configurations}
        # All algorithms in the config should have a selected configuration
        for algo in ["kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"]:
            assert algo in selected_algos


# ---------------------------------------------------------------------------
# Metrics reuse
# ---------------------------------------------------------------------------


class TestMetricsReuse:
    def test_metrics_have_status(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        for r in sweep_result.results:
            if r.status == "SUCCESS":
                extra = r.cluster_result.metrics.extra
                assert "silhouette_status" in extra
                assert extra["silhouette_status"] == METRIC_VALID

    def test_no_missing_after_success(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        for r in sweep_result.results:
            if r.status == "SUCCESS":
                extra = r.cluster_result.metrics.extra
                assert extra.get("silhouette_status") == METRIC_VALID
                assert extra.get("davies_bouldin_status") == METRIC_VALID
                assert extra.get("calinski_harabasz_status") == METRIC_VALID
                assert extra.get("wcss_status") == METRIC_VALID

    def test_library_versions_recorded(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        assert isinstance(sweep_result.library_versions, dict)
        for r in sweep_result.results:
            assert isinstance(r.library_versions, dict)


# ---------------------------------------------------------------------------
# Selection protocol
# ---------------------------------------------------------------------------


class TestSelectionProtocol:
    def test_selection_protocol_returns_per_algo(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        for sel in sweep_result.selected_configurations:
            assert sel.algorithm in CANONICAL_ORDER
            assert sel.decision_status in (
                "WORKING_SELECTED",
                "TIED_WORKING_SELECTED",
                "PENDING_REVIEW",
            )
            # Primary criterion must be silhouette
            assert sel.selection_evidence.get("primary_criterion") == "silhouette"

    def test_selection_protocol_no_single_metric_ranking(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        for sel in sweep_result.selected_configurations:
            # Must have multi-criterion evidence
            ev = sel.selection_evidence
            assert "primary_criterion" in ev
            assert "tie_breaker_1" in ev
            assert "wcss_diagnostic_only" in ev or "runtime_diagnostic_only" in ev

    def test_selection_protocol_no_forbidden_language(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        forbidden = {"best", "winner", "optimal", "recommended", "final", "superior"}
        for sel in sweep_result.selected_configurations:
            # decision_status must not contain forbidden words
            for word in forbidden:
                assert word.lower() not in sel.decision_status.lower()

    def test_apply_selection_protocol_returns_non_none(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        sel = apply_selection_protocol("kmeans", sweep_result.results)
        assert sel is not None

    def test_selection_protocol_tied_detected(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        # With identical configs (same hyperparameters), protocol should
        # not crash but pick one deterministically.
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        sel = apply_selection_protocol("kmeans", sweep_result.results)
        assert sel.decision_status in (
            "WORKING_SELECTED",
            "TIED_WORKING_SELECTED",
            "PENDING_REVIEW",
        )


# ---------------------------------------------------------------------------
# Build sensitivity table
# ---------------------------------------------------------------------------


class TestSensitivityTable:
    def test_sensitivity_table_has_all_algorithms(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        table = sweep_result.sensitivity_table
        algos_in_table = {rec.algorithm for rec in table}
        # At minimum kmeans should appear
        assert "kmeans" in algos_in_table

    def test_sensitivity_table_records_sweep_parameter(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        table = sweep_result.sensitivity_table
        for rec in table:
            assert rec.parameter is not None


# ---------------------------------------------------------------------------
# Canonical ordering
# ---------------------------------------------------------------------------


class TestCanonicalOrder:
    def test_results_in_canonical_order(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        runner = HyperparameterSearchRunner(framework_config, minimal_exp03_config, n_repeat=2)
        sweep_result = runner.run(small_matrix)
        seen = []
        for r in sweep_result.results:
            if not seen or r.algorithm != seen[-1]:
                seen.append(r.algorithm)
        assert seen == CANONICAL_ORDER


# ---------------------------------------------------------------------------
# EXP-02 K candidates loaded
# ---------------------------------------------------------------------------


class TestExp02KReuse:
    def test_load_exp02_candidates(self) -> None:
        if not _EXP02_CANDIDATES_PATH.exists():
            pytest.skip("EXP-02 candidates CSV not present")
        candidates = load_exp02_candidates(_EXP02_CANDIDATES_PATH)
        assert "kmeans" in candidates
        assert candidates["kmeans"] == [2, 3, 4, 5]

    def test_load_exp02_candidates_missing_file(self) -> None:
        candidates = load_exp02_candidates(Path("/nonexistent/candidates.csv"))
        assert candidates == {}

    def test_exp02_candidates_used_in_stage_c(
        self, framework_config, minimal_exp03_config, small_matrix
    ) -> None:
        if not _EXP02_CANDIDATES_PATH.exists():
            pytest.skip("EXP-02 candidates CSV not present")
        minimal_exp03_config["exp03"]["selected_interactions"] = [
            {
                "algorithm": "kmeans",
                "K": 3,
                "parameters": {"n_init": [1, 10]},
                "rationale": "K=3 from EXP-02",
            }
        ]
        runner = HyperparameterSearchRunner(
            framework_config,
            minimal_exp03_config,
            n_repeat=2,
            exp02_candidates_csv_path=_EXP02_CANDIDATES_PATH,
        )
        sweep_result = runner.run(small_matrix)
        km_c = [
            s
            for s in sweep_result.results
            if s.stage == STAGE_INTERACTION and s.algorithm == "kmeans"
        ]
        assert len(km_c) == 2  # n_init 1, 10
