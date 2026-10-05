"""Tests for the ML-06 Algorithm Baseline Verification.

This test module verifies that **all five EPIC-06 algorithm
adapters** (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means)
are wired into the ML-01 framework correctly and run end-to-end
on the same FE-06 final clustering dataset with the same
unified schema.

Scope of verification (per ML-06 task contract §22-24):

1. **Registry completeness** — all five algorithm names are
   registered; each adapter is instantiable; each exposes the
   documented class metadata (``name``, ``version``, ``family``).
2. **Framework integration** — each adapter runs through the
   :class:`ExperimentRunner` end-to-end (without bypassing the
   framework) and produces the unified ``ExperimentResult``
   schema.
3. **Dataset boundary** — all five adapters consume the same
   ``final_clustering_dataset.parquet`` (FE-06 output); none
   mutates the FE-06 output; ``CustomerID`` is NEVER passed
   inside the matrix.
4. **Output schema** — every adapter writes
   ``cluster_labels_{experiment_id}.parquet``,
   ``experiment_log_{experiment_id}.json``, and (for soft
   algorithms — GMM, FCM) ``algorithm_output_{experiment_id}.parquet``.
5. **Algorithm-specific outputs** — hard algorithms produce
   ``cluster_labels`` only; DBSCAN preserves noise label ``-1``;
   GMM exposes ``soft_probabilities``; FCM exposes
   ``soft_membership``.
6. **Provenance** — each run records dataset SHA, config SHA,
   library versions, execution time, and seed policy.
7. **Reproducibility** — same input + same config + same seed
   (when applicable) → same labels / responsibilities /
   membership matrix in tolerance.

The tests are **value-neutral**: they assert structural
properties (registry, schema, alignment, SHA, library versions)
NOT "best/optimal/winner" claims. Baseline verification
demonstrates **infrastructure / adapter readiness**, not
research conclusions about which algorithm is "best" — that
belongs to EPIC-08.

These tests are skipped when the FE-06 outputs are not on disk,
so the test suite still passes in a fresh CI environment before
FE-06 has been run.
"""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.clustering import (
    AgglomerativeAdapter,
    AlgorithmFamily,
    AlgorithmRegistry,
    AlgorithmRegistryError,
    BaseClusterAlgorithm,
    DBSCANAdapter,
    ExperimentRunner,
    ExperimentSpec,
    ExperimentStatus,
    FuzzyCMeansAdapter,
    GMMAdapter,
    KMeansAdapter,
    load_framework_config,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Expected algorithm names per ML-06 task contract §22 (the four
# fixed benchmark algorithms + FCM).
EXPECTED_ALGORITHM_NAMES: tuple[str, ...] = (
    "kmeans",
    "agglomerative",
    "dbscan",
    "gmm",
    "fuzzy_cmeans",
)

# Expected algorithm family per algorithm (for sanity).
EXPECTED_FAMILY: dict[str, str] = {
    "kmeans": AlgorithmFamily.HARD,
    "agglomerative": AlgorithmFamily.HARD,
    "dbscan": AlgorithmFamily.DENSITY_BASED,
    "gmm": AlgorithmFamily.MODEL_BASED,
    "fuzzy_cmeans": AlgorithmFamily.FUZZY,
}

# Which algorithms consume random_state (control flow for
# reproducibility tests).
SUPPORTS_RANDOM_STATE: dict[str, bool] = {
    "kmeans": True,
    "agglomerative": False,
    "dbscan": False,
    "gmm": True,
    "fuzzy_cmeans": True,
}

# Per-algorithm working-default hyperparameters (mirrors
# configs/clustering.yaml + adapter defaults).
WORKING_HYPERPARAMETERS: dict[str, dict] = {
    "kmeans": {
        "n_clusters": 4,
        "init": "k-means++",
        "n_init": 10,
        "max_iter": 300,
        "random_state": 42,
    },
    "agglomerative": {
        "n_clusters": 4,
        "linkage": "ward",
        "metric": "euclidean",
    },
    "dbscan": {
        "eps": 0.5,
        "min_samples": 5,
        "metric": "euclidean",
    },
    "gmm": {
        "n_components": 4,
        "covariance_type": "full",
        "init_params": "kmeans",
        "random_state": 42,
        "tol": 1e-3,
        "reg_covar": 1e-6,
        "max_iter": 100,
        "n_init": 1,
    },
    "fuzzy_cmeans": {
        "n_clusters": 4,
        "m": 2.0,
        "max_iter": 300,
        "error": 1e-4,
        "random_state": 42,
    },
}


# ---------------------------------------------------------------------------
# Locating FE-06 inputs and the framework config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Autouse fixture: re-register production adapters
# ---------------------------------------------------------------------------
# ML-01 framework tests call AlgorithmRegistry.clear() as part of their
# test isolation. When the full test suite runs (test_ml01 → test_ml06),
# the ML-01 tests clear the registry and re-register only the toy
# adapters. By the time test_ml06_baseline runs, the production adapters
# (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means) have been
# removed from the registry.
#
# This autouse fixture re-registers all production adapters before
# every test in this module so the registry is always in a known
# state regardless of test execution order.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_production_adapters_registered() -> None:
    """Re-register all five EPIC-06 production adapters before each test.

    This fixture runs automatically (autouse=True) so the registry is
    always populated regardless of whether ML-01 framework tests
    cleared it.
    """
    # Re-register via the @register decorator on each class.  This is
    # safe because AlgorithmRegistry.register() raises on duplicate
    # registration; if the adapter is already registered (because a
    # prior test registered it without clearing), the decorator raises.
    # We therefore first try to register; on AlgorithmRegistryError we
    # know the adapter is already present and do nothing.
    for _adapter_cls in (
        KMeansAdapter,
        AgglomerativeAdapter,
        DBSCANAdapter,
        GMMAdapter,
        FuzzyCMeansAdapter,
    ):
        with suppress(AlgorithmRegistryError):
            AlgorithmRegistry.register(_adapter_cls.name)(_adapter_cls)


DATA_PROCESSED = REPO_ROOT / "data" / "processed"
FE06_DATASET = DATA_PROCESSED / "final_clustering_dataset.parquet"
FE06_METADATA = DATA_PROCESSED / "customer_metadata.parquet"
CONFIG_PATH = REPO_ROOT / "configs" / "clustering.yaml"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_parquet(FE06_DATASET)
    md = pd.read_parquet(FE06_METADATA)
    return df, md


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    """All five EPIC-06 algorithm adapters are registered with
    stable names."""

    def test_all_expected_algorithms_registered(self) -> None:
        registered = set(AlgorithmRegistry.list_registered())
        missing = set(EXPECTED_ALGORITHM_NAMES) - registered
        assert not missing, (
            f"Missing algorithm registrations: {sorted(missing)}. "
            f"Available: {sorted(registered)}."
        )

    def test_each_algorithm_is_subclass_of_base(self) -> None:
        for algo in EXPECTED_ALGORITHM_NAMES:
            cls = AlgorithmRegistry.get(algo)
            assert issubclass(cls, BaseClusterAlgorithm), (
                f"Algorithm {algo!r} ({cls.__name__}) is not a subclass of "
                f"BaseClusterAlgorithm."
            )

    def test_each_algorithm_has_name_version_family(self) -> None:
        for algo in EXPECTED_ALGORITHM_NAMES:
            cls = AlgorithmRegistry.get(algo)
            assert (
                cls.name == algo
            ), f"Algorithm {algo!r} reports name={cls.name!r} (expected {algo!r})."
            assert (
                isinstance(cls.version, str) and cls.version
            ), f"Algorithm {algo!r} has empty version."
            expected_family = EXPECTED_FAMILY[algo]
            assert cls.family == expected_family, (
                f"Algorithm {algo!r} reports family={cls.family!r} "
                f"(expected {expected_family!r})."
            )

    def test_each_algorithm_is_instantiable(self) -> None:
        # K-Means, Agglomerative need n_clusters; GMM needs
        # n_components; DBSCAN needs eps + min_samples; FCM needs
        # n_clusters. We construct with the working-default
        # hyperparameters defined above.
        for algo in EXPECTED_ALGORITHM_NAMES:
            hp = WORKING_HYPERPARAMETERS[algo]
            cls = AlgorithmRegistry.get(algo)
            instance = cls(**hp)
            assert isinstance(instance, BaseClusterAlgorithm)
            assert instance.name == algo
            assert instance.family == EXPECTED_FAMILY[algo]


# ---------------------------------------------------------------------------
# Adapter instantiation & metadata sanity
# ---------------------------------------------------------------------------


class TestAdapterInstantiation:
    """All five adapter classes can be imported and instantiated."""

    def test_kmeans_imports(self) -> None:
        adapter = KMeansAdapter(**WORKING_HYPERPARAMETERS["kmeans"])
        assert adapter.name == "kmeans"
        assert adapter.family == AlgorithmFamily.HARD
        assert adapter.supports_random_state() is True

    def test_agglomerative_imports(self) -> None:
        adapter = AgglomerativeAdapter(**WORKING_HYPERPARAMETERS["agglomerative"])
        assert adapter.name == "agglomerative"
        assert adapter.family == AlgorithmFamily.HARD
        assert adapter.supports_random_state() is False

    def test_dbscan_imports(self) -> None:
        adapter = DBSCANAdapter(**WORKING_HYPERPARAMETERS["dbscan"])
        assert adapter.name == "dbscan"
        assert adapter.family == AlgorithmFamily.DENSITY_BASED
        assert adapter.supports_random_state() is False

    def test_gmm_imports(self) -> None:
        adapter = GMMAdapter(**WORKING_HYPERPARAMETERS["gmm"])
        assert adapter.name == "gmm"
        assert adapter.family == AlgorithmFamily.MODEL_BASED
        assert adapter.supports_random_state() is True

    def test_fuzzy_cmeans_imports(self) -> None:
        adapter = FuzzyCMeansAdapter(**WORKING_HYPERPARAMETERS["fuzzy_cmeans"])
        assert adapter.name == "fuzzy_cmeans"
        assert adapter.family == AlgorithmFamily.FUZZY
        assert adapter.supports_random_state() is True


# ---------------------------------------------------------------------------
# End-to-end framework integration on the FE-06 dataset
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not FE06_DATASET.exists() or not FE06_METADATA.exists(),
    reason="FE-06 outputs not present",
)
class TestEndToEndFE06:
    """Each adapter runs end-to-end through ExperimentRunner on
    the real FE-06 dataset, produces the unified schema, and
    preserves FE-06 input integrity."""

    @pytest.fixture()
    def fe06_inputs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        return _load_inputs()

    @pytest.fixture()
    def framework_config(self):
        return load_framework_config(CONFIG_PATH)

    def _run_one(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
        hp: dict,
        experiment_id: str,
        input_sha: str = "baseline-test-sha",
    ):
        df, md = fe06_inputs
        spec = ExperimentSpec(
            experiment_id=experiment_id,
            algorithm=algorithm,
            hyperparameters=hp,
        )
        runner = ExperimentRunner(framework_config, spec)
        return runner.run(
            df,
            md,
            input_sha256=input_sha,
            input_path=str(FE06_DATASET),
            metadata_path=str(FE06_METADATA),
            output_dir=tmp_path,
        )

    @pytest.mark.parametrize("algorithm", list(EXPECTED_ALGORITHM_NAMES))
    def test_each_adapter_runs_end_to_end(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
    ) -> None:
        hp = WORKING_HYPERPARAMETERS[algorithm]
        result = self._run_one(
            framework_config,
            fe06_inputs,
            tmp_path,
            algorithm=algorithm,
            hp=hp,
            experiment_id=f"ML-06-baseline-{algorithm}",
        )
        # ---- Status ----
        assert (
            result.status == ExperimentStatus.SUCCESS
        ), f"Algorithm {algorithm!r} did not succeed: {result.error}"
        # ---- Metadata ----
        assert result.algorithm == algorithm
        assert result.dataset_version == framework_config.input.dataset_version
        assert result.dataset_sha256 == "baseline-test-sha"
        assert result.input_path == str(FE06_DATASET)
        assert result.metadata_path == str(FE06_METADATA)
        # ---- n_samples / n_features ----
        df, _ = fe06_inputs
        assert result.n_samples == len(df)
        assert result.feature_count == df.shape[1]
        # ---- Library versions + platform ----
        assert "numpy" in result.library_versions
        assert "scikit-learn" in result.library_versions
        assert "pyarrow" in result.library_versions
        assert "python" in result.platform
        # ---- Cluster labels ----
        assert result.cluster_labels is not None
        assert result.cluster_labels.shape == (len(df),)
        assert result.cluster_labels.dtype == np.int64
        # ---- Cluster result extras present ----
        assert result.cluster_result is not None
        assert result.cluster_result.algorithm == algorithm
        assert result.cluster_result.algorithm_family == EXPECTED_FAMILY[algorithm]
        # ---- Artifacts ----
        assert "cluster_labels" in result.artifact_paths
        assert "experiment_log" in result.artifact_paths
        # cluster_labels file must exist on disk.
        assert Path(result.artifact_paths["cluster_labels"]).exists()
        assert Path(result.artifact_paths["experiment_log"]).exists()

    @pytest.mark.parametrize(
        "algorithm,soft_field",
        [
            ("gmm", "soft_probabilities"),
            ("fuzzy_cmeans", "soft_membership"),
        ],
    )
    def test_soft_algorithms_preserve_soft_output(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
        soft_field: str,
    ) -> None:
        hp = WORKING_HYPERPARAMETERS[algorithm]
        result = self._run_one(
            framework_config,
            fe06_inputs,
            tmp_path,
            algorithm=algorithm,
            hp=hp,
            experiment_id=f"ML-06-baseline-soft-{algorithm}",
        )
        soft_output = getattr(result.cluster_result, soft_field)
        assert (
            soft_output is not None
        ), f"{algorithm!r}: {soft_field} must be populated for soft algorithm."
        # Shape: (n_samples, n_components_or_clusters).
        assert soft_output.shape[0] == result.n_samples
        assert soft_output.shape[1] == result.n_clusters
        # algorithm_output parquet must exist on disk.
        assert "algorithm_output" in result.artifact_paths
        algo_path = Path(result.artifact_paths["algorithm_output"])
        assert algo_path.exists()

    @pytest.mark.parametrize("algorithm", ["kmeans", "agglomerative"])
    def test_hard_algorithms_no_soft_output(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
    ) -> None:
        hp = WORKING_HYPERPARAMETERS[algorithm]
        result = self._run_one(
            framework_config,
            fe06_inputs,
            tmp_path,
            algorithm=algorithm,
            hp=hp,
            experiment_id=f"ML-06-baseline-hard-{algorithm}",
        )
        assert result.cluster_result.soft_probabilities is None
        assert result.cluster_result.soft_membership is None

    def test_dbscan_preserves_noise_label(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
    ) -> None:
        # DBSCAN must preserve the noise label -1 verbatim.
        hp = WORKING_HYPERPARAMETERS["dbscan"]
        result = self._run_one(
            framework_config,
            fe06_inputs,
            tmp_path,
            algorithm="dbscan",
            hp=hp,
            experiment_id="ML-06-baseline-dbscan-noise",
        )
        assert result.cluster_result.noise_label == -1
        # noise_count / noise_ratio populated.
        assert result.cluster_result.noise_count is not None
        assert result.cluster_result.noise_ratio is not None
        # noise_count <= n_samples.
        assert result.cluster_result.noise_count <= result.n_samples

    def test_cluster_labels_artifact_has_customer_id_alignment(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
    ) -> None:
        # Run one algorithm and verify positional alignment.
        df, md = fe06_inputs
        hp = WORKING_HYPERPARAMETERS["kmeans"]
        result = self._run_one(
            framework_config,
            fe06_inputs,
            tmp_path,
            algorithm="kmeans",
            hp=hp,
            experiment_id="ML-06-baseline-alignment",
        )
        labels_df = pd.read_parquet(result.artifact_paths["cluster_labels"])
        assert "CustomerID" in labels_df.columns
        # Positional alignment: row i of cluster_labels matches row
        # i of customer_metadata.
        np.testing.assert_array_equal(
            labels_df["CustomerID"].to_numpy(), md["CustomerID"].to_numpy()
        )
        assert "ClusterLabel" in labels_df.columns

    def test_experiment_log_schema_completeness(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
    ) -> None:
        # Every experiment log JSON contains the required ML-01
        # metadata fields.
        hp = WORKING_HYPERPARAMETERS["fuzzy_cmeans"]
        result = self._run_one(
            framework_config,
            fe06_inputs,
            tmp_path,
            algorithm="fuzzy_cmeans",
            hp=hp,
            experiment_id="ML-06-baseline-log-schema",
        )
        log = json.loads(Path(result.artifact_paths["experiment_log"]).read_text())
        required = {
            "experiment_id",
            "status",
            "algorithm",
            "algorithm_version",
            "dataset_version",
            "dataset_sha256",
            "feature_set",
            "feature_count",
            "n_samples",
            "hyperparameters",
            "random_seed",
            "random_seed_used",
            "n_clusters",
            "execution_time",
            "timestamp",
            "library_versions",
            "platform",
            "config_source",
            "config_sha256",
            "artifact_paths",
        }
        assert required.issubset(
            log.keys()
        ), f"Missing keys in experiment log: {sorted(required - log.keys())}."
        assert log["status"] == "SUCCESS"
        # Reproducibility metadata present.
        assert log["dataset_sha256"] == "baseline-test-sha"
        assert isinstance(log["library_versions"], dict)
        assert isinstance(log["platform"], dict)


# ---------------------------------------------------------------------------
# Reproducibility across the full baseline
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not FE06_DATASET.exists() or not FE06_METADATA.exists(),
    reason="FE-06 outputs not present",
)
class TestBaselineReproducibility:
    """Same input + same config + same seed (when supported) →
    same outputs across runs for each algorithm in the EPIC-06
    baseline.

    Baseline verification chứng minh infrastructure/adapter
    readiness, not research conclusions. The tests use the
    framework's ``ExperimentRunner.run`` end-to-end (no
    bypassing the framework).
    """

    @pytest.fixture()
    def fe06_inputs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        return _load_inputs()

    @pytest.fixture()
    def framework_config(self):
        return load_framework_config(CONFIG_PATH)

    @pytest.mark.parametrize("algorithm", list(EXPECTED_ALGORITHM_NAMES))
    def test_same_seed_reproducible(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
    ) -> None:
        df, md = fe06_inputs
        hp = WORKING_HYPERPARAMETERS[algorithm]
        # Two runs with the same hyperparameters + same seed.
        spec1 = ExperimentSpec(
            experiment_id=f"ML-06-baseline-repro-{algorithm}-1",
            algorithm=algorithm,
            hyperparameters=hp,
        )
        spec2 = ExperimentSpec(
            experiment_id=f"ML-06-baseline-repro-{algorithm}-2",
            algorithm=algorithm,
            hyperparameters=hp,
        )
        runner1 = ExperimentRunner(framework_config, spec1)
        runner2 = ExperimentRunner(framework_config, spec2)
        r1 = runner1.run(
            df,
            md,
            input_sha256="repro-sha",
            input_path=str(FE06_DATASET),
            metadata_path=str(FE06_METADATA),
            output_dir=tmp_path,
        )
        r2 = runner2.run(
            df,
            md,
            input_sha256="repro-sha",
            input_path=str(FE06_DATASET),
            metadata_path=str(FE06_METADATA),
            output_dir=tmp_path,
        )
        assert r1.status == ExperimentStatus.SUCCESS
        assert r2.status == ExperimentStatus.SUCCESS
        # Cluster labels are deterministic across runs.
        np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels, strict=True)

    @pytest.mark.parametrize(
        "algorithm,soft_field,atol",
        [
            ("gmm", "soft_probabilities", 1e-8),
            ("fuzzy_cmeans", "soft_membership", 1e-8),
        ],
    )
    def test_soft_output_reproducible(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
        soft_field: str,
        atol: float,
    ) -> None:
        df, md = fe06_inputs
        hp = WORKING_HYPERPARAMETERS[algorithm]
        spec1 = ExperimentSpec(
            experiment_id=f"ML-06-baseline-repro-soft-{algorithm}-1",
            algorithm=algorithm,
            hyperparameters=hp,
        )
        spec2 = ExperimentSpec(
            experiment_id=f"ML-06-baseline-repro-soft-{algorithm}-2",
            algorithm=algorithm,
            hyperparameters=hp,
        )
        runner1 = ExperimentRunner(framework_config, spec1)
        runner2 = ExperimentRunner(framework_config, spec2)
        r1 = runner1.run(
            df,
            md,
            input_sha256="repro-sha",
            input_path=str(FE06_DATASET),
            metadata_path=str(FE06_METADATA),
            output_dir=tmp_path,
        )
        r2 = runner2.run(
            df,
            md,
            input_sha256="repro-sha",
            input_path=str(FE06_DATASET),
            metadata_path=str(FE06_METADATA),
            output_dir=tmp_path,
        )
        soft_1 = getattr(r1.cluster_result, soft_field)
        soft_2 = getattr(r2.cluster_result, soft_field)
        assert soft_1 is not None and soft_2 is not None
        # Soft output is deterministic across runs (same seed).
        np.testing.assert_allclose(soft_1, soft_2, atol=atol, rtol=0)


# ---------------------------------------------------------------------------
# Boundary discipline: no evaluation metrics, no algorithm ranking
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not FE06_DATASET.exists() or not FE06_METADATA.exists(),
    reason="FE-06 outputs not present",
)
class TestBoundaryDiscipline:
    """Baseline verification MUST NOT introduce evaluation
    metrics, best/optimal/winner claims, or any other
    EPIC-07/08/09 scope creep."""

    @pytest.fixture()
    def fe06_inputs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        return _load_inputs()

    @pytest.fixture()
    def framework_config(self):
        return load_framework_config(CONFIG_PATH)

    @pytest.mark.parametrize("algorithm", list(EXPECTED_ALGORITHM_NAMES))
    def test_no_evaluation_metrics_populated(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
    ) -> None:
        hp = WORKING_HYPERPARAMETERS[algorithm]
        spec = ExperimentSpec(
            experiment_id=f"ML-06-baseline-no-metrics-{algorithm}",
            algorithm=algorithm,
            hyperparameters=hp,
        )
        runner = ExperimentRunner(framework_config, spec)
        df, md = fe06_inputs
        result = runner.run(
            df,
            md,
            input_sha256="boundary-sha",
            input_path=str(FE06_DATASET),
            metadata_path=str(FE06_METADATA),
            output_dir=tmp_path,
        )
        # MetricsResult MUST stay None in EPIC-06.
        assert result.metrics.silhouette is None
        assert result.metrics.davies_bouldin is None
        assert result.metrics.calinski_harabasz is None
        assert result.metrics.wcss is None
        assert result.metrics.stability is None
        assert result.metrics.runtime is None

    @pytest.mark.parametrize("algorithm", list(EXPECTED_ALGORITHM_NAMES))
    def test_fe06_input_not_mutated(
        self,
        framework_config,
        fe06_inputs,
        tmp_path: Path,
        algorithm: str,
    ) -> None:
        # The FE-06 final clustering dataset MUST stay
        # read-only. We hash the file before and after each run
        # and verify the SHA is unchanged.
        import hashlib

        def _file_sha256(p: Path) -> str:
            h = hashlib.sha256()
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()

        before = _file_sha256(FE06_DATASET)
        hp = WORKING_HYPERPARAMETERS[algorithm]
        spec = ExperimentSpec(
            experiment_id=f"ML-06-baseline-immut-{algorithm}",
            algorithm=algorithm,
            hyperparameters=hp,
        )
        runner = ExperimentRunner(framework_config, spec)
        df, md = fe06_inputs
        runner.run(
            df,
            md,
            input_sha256="immut-sha",
            input_path=str(FE06_DATASET),
            metadata_path=str(FE06_METADATA),
            output_dir=tmp_path,
        )
        after = _file_sha256(FE06_DATASET)
        assert before == after, (
            f"FE-06 dataset SHA changed after {algorithm!r} run: " f"{before} != {after}."
        )


# ---------------------------------------------------------------------------
# Baseline configuration matrix
# ---------------------------------------------------------------------------


class TestBaselineConfigurationMatrix:
    """The baseline configuration matrix (per ML-06 task
    contract §23) records, for each algorithm:

    - family
    - working hyperparameters
    - random-state support
    - primary output
    - soft-output field name (if any)
    """

    def test_working_hyperparameters_have_no_research_claim(self) -> None:
        # All working_* values are WORKING_ASSUMPTION, not
        # research-approved. The matrix itself contains NO
        # 'best' / 'optimal' / 'winner' column by construction.
        for algo, hp in WORKING_HYPERPARAMETERS.items():
            assert isinstance(hp, dict) and hp, f"Working hyperparameters missing for {algo!r}."
            for key in (
                "best",
                "optimal",
                "winner",
                "recommended",
                "final",
                "preferred",
            ):
                assert key not in hp, (
                    f"Working hyperparameters for {algo!r} contain the "
                    f"keyword {key!r} which is a research decision "
                    f"(AGENTS.md §2.5)."
                )

    def test_supports_random_state_truthful(self) -> None:
        # Cross-check the documented supports_random_state() value
        # for each algorithm against the expected baseline.
        for algo, expected in SUPPORTS_RANDOM_STATE.items():
            cls = AlgorithmRegistry.get(algo)
            instance = cls(**WORKING_HYPERPARAMETERS[algo])
            assert instance.supports_random_state() is expected, (
                f"{algo!r}: supports_random_state() must be {expected}, "
                f"got {instance.supports_random_state()}."
            )

    def test_family_label_consistent(self) -> None:
        # Each algorithm reports the family documented in the
        # EPIC-06 contract §3.
        for algo, expected_family in EXPECTED_FAMILY.items():
            cls = AlgorithmRegistry.get(algo)
            instance = cls(**WORKING_HYPERPARAMETERS[algo])
            assert instance.family == expected_family, (
                f"{algo!r}: family must be {expected_family!r}, " f"got {instance.family!r}."
            )
