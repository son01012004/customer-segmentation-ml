"""Tests for the ML-03 Agglomerative (hierarchical) clustering adapter.

The tests are organised by responsibility, mirroring the ML-02 K-Means
test layout and the ML-03 task contract:

- :class:`TestInterface` — adapter implements ``BaseClusterAlgorithm``,
  is registered under ``"agglomerative"``, exposes metadata,
  ``get_params``, ``get_model`` and ``supports_random_state``.
- :class:`TestParameterValidation` — bad hyperparameters (n_clusters,
  linkage, metric, ward+non-euclidean, insufficient samples) are
  rejected with ``ClusterAlgorithmError``.
- :class:`TestInputValidation` — bad input matrices (None, wrong
  dimensionality, insufficient samples, n_clusters>=n_samples) are
  rejected by ``fit``. The framework's identifier-leakage /
  NaN / Inf checks are NOT retested here — they belong to the
  framework's validation suite.
- :class:`TestLinkageCoverage` — the four advertised linkages
  (ward, complete, average, single) all fit successfully on a
  well-separated synthetic dataset; ward + non-euclidean is
  rejected at construction time.
- :class:`TestOutputSchema` — output conforms to ``ClusterResult``
  schema; algorithm-specific extras (linkage, metric, n_merges,
  merge-distance summary, cluster sizes) are populated.
- :class:`TestReproducibility` — Agglomerative is deterministic;
  same input + same configuration + same library version →
  same labels. No random_state is consumed.
- :class:`TestIntegrationWithFE06` — end-to-end run via
  ``ExperimentRunner`` on the real FE-06 dataset (skipped if
  absent).

The tests are intentionally value-neutral: they assert structural
properties (shape, dtype, schema, linkage constraints), not
"best/optimal" claims. Agglomerative clustering is deterministic in
``n_clusters`` mode; the test suite therefore does NOT include a
"different seed produces different labels" test (that property is
inapplicable to ML-03 by design).
"""

from __future__ import annotations

import json
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
    ClusterAlgorithmError,
    ClusterResult,
    ExperimentRunner,
    ExperimentSpec,
    ExperimentStatus,
    load_framework_config,
)
from customer_segmentation.clustering.agglomerative import (
    DEFAULT_LINKAGE,
    DEFAULT_METRIC,
    MIN_N_CLUSTERS,
    SUPPORTED_LINKAGES,
    SUPPORTED_METRICS,
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
def _ensure_agglomerative_registered() -> None:
    """Autouse: re-register ``AgglomerativeAdapter`` before every test.

    The ML-01 framework tests' ``registered_toy_algorithms`` fixture
    calls ``AlgorithmRegistry.clear()`` at teardown, which removes
    ``AgglomerativeAdapter`` from the registry. This fixture
    re-registers the existing class before each test so the registry
    is in a known state.
    """
    if not AlgorithmRegistry.is_registered("agglomerative"):
        AlgorithmRegistry.register("agglomerative")(AgglomerativeAdapter)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_agglomerative_is_base_algorithm(self) -> None:
        assert issubclass(AgglomerativeAdapter, BaseClusterAlgorithm)

    def test_agglomerative_is_registered(self) -> None:
        # AgglomerativeAdapter is registered at module import via
        # ``@AlgorithmRegistry.register("agglomerative")``.
        assert AlgorithmRegistry.is_registered("agglomerative")
        cls = AlgorithmRegistry.get("agglomerative")
        assert cls is AgglomerativeAdapter

    def test_agglomerative_name_is_stable(self) -> None:
        assert AgglomerativeAdapter.name == "agglomerative"

    def test_agglomerative_family_is_hard(self) -> None:
        # Agglomerative clustering is hard (each point belongs to
        # exactly one cluster in n_clusters mode).
        assert AgglomerativeAdapter.family == AlgorithmFamily.HARD

    def test_agglomerative_version_references_sklearn(self) -> None:
        # Format is "sklearn_<version>" — captures library version.
        assert AgglomerativeAdapter.version.startswith("sklearn_")
        import sklearn

        assert sklearn.__version__ in AgglomerativeAdapter.version

    def test_supports_random_state_is_false(self) -> None:
        # Agglomerative clustering in n_clusters mode is
        # deterministic in modern sklearn — there is no random_state
        # to consume. The runner relies on this truthful answer to
        # avoid injecting a fake seed.
        assert AgglomerativeAdapter(n_clusters=3).supports_random_state() is False

    def test_get_params_returns_serialisable_dict(self) -> None:
        adapter = AgglomerativeAdapter(
            n_clusters=5,
            linkage="complete",
            metric="euclidean",
            compute_distances=False,
        )
        params = adapter.get_params()
        assert params["n_clusters"] == 5
        assert params["linkage"] == "complete"
        assert params["metric"] == "euclidean"
        assert params["compute_distances"] is False
        # Must be JSON-serialisable.
        json.dumps(params)

    def test_get_model_returns_none_before_fit(self) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3)
        assert adapter.get_model() is None

    def test_get_model_returns_fitted_model_after_fit(
        self, well_separated_matrix: pd.DataFrame
    ) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward")
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        adapter.fit(X)
        model = adapter.get_model()
        assert model is not None
        # sklearn's AgglomerativeClustering exposes these after fit.
        assert hasattr(model, "children_")
        assert hasattr(model, "n_leaves_")
        assert model.n_leaves_ == X.shape[0]

    def test_double_registration_raises(self) -> None:
        # Trying to register another class under "agglomerative"
        # should fail.
        with pytest.raises(AlgorithmRegistryError):

            @AlgorithmRegistry.register("agglomerative")
            class _Other(BaseClusterAlgorithm):
                version = "other_v1"
                family = AlgorithmFamily.HARD

                def fit(self, X):
                    raise ClusterAlgorithmError("not implemented")

    def test_unregistered_algorithm_raises(self) -> None:
        with pytest.raises(AlgorithmRegistryError):
            AlgorithmRegistry.get("definitely_not_registered_xyz")

    def test_supported_linkages_constant(self) -> None:
        assert "ward" in SUPPORTED_LINKAGES
        assert "complete" in SUPPORTED_LINKAGES
        assert "average" in SUPPORTED_LINKAGES
        assert "single" in SUPPORTED_LINKAGES

    def test_supported_metrics_constant(self) -> None:
        assert "euclidean" in SUPPORTED_METRICS
        assert "manhattan" in SUPPORTED_METRICS

    def test_module_defaults_exposed(self) -> None:
        assert DEFAULT_LINKAGE == "ward"
        assert DEFAULT_METRIC == "euclidean"
        assert MIN_N_CLUSTERS == 2


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_n_clusters_must_be_int(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters="4")  # type: ignore[arg-type]

    def test_n_clusters_must_be_at_least_2(self) -> None:
        # ML-03 task contract: n_clusters >= 2.
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=1)
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=0)

    def test_linkage_must_be_string(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=3, linkage=123)  # type: ignore[arg-type]

    def test_invalid_linkage_rejected(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=3, linkage="centroid")  # not in SUPPORTED

    def test_metric_must_be_string(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=3, metric=42)  # type: ignore[arg-type]

    def test_invalid_metric_rejected(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=3, metric="hamming")  # not in SUPPORTED

    def test_ward_requires_euclidean_metric(self) -> None:
        # sklearn constraint: ward + non-euclidean → reject up-front.
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=3, linkage="ward", metric="manhattan")

    def test_ward_accepts_euclidean_metric(self) -> None:
        # Sanity: ward + euclidean should construct without error.
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward", metric="euclidean")
        assert adapter.linkage == "ward"
        assert adapter.metric == "euclidean"

    def test_non_ward_accepts_non_euclidean_metric(self) -> None:
        # complete / average / single accept non-euclidean metrics.
        for linkage in ("complete", "average", "single"):
            adapter = AgglomerativeAdapter(n_clusters=3, linkage=linkage, metric="manhattan")
            assert adapter.linkage == linkage
            assert adapter.metric == "manhattan"

    def test_compute_distances_must_be_bool(self) -> None:
        with pytest.raises(ClusterAlgorithmError):
            AgglomerativeAdapter(n_clusters=3, compute_distances="yes")  # type: ignore[arg-type]

    def test_default_values(self) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3)
        assert adapter.linkage == DEFAULT_LINKAGE
        assert adapter.metric == DEFAULT_METRIC
        assert adapter.compute_distances is True

    def test_compute_distances_false_accepted(self) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3, compute_distances=False)
        assert adapter.compute_distances is False


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_none_matrix_raises(self) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(None)  # type: ignore[arg-type]

    def test_1d_matrix_raises(self) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros(10))

    def test_n_clusters_greater_than_n_samples_raises(self, small_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(n_clusters=100)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(small_matrix.to_numpy(dtype=np.float64))

    def test_n_clusters_equal_n_samples_raises(self, small_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(n_clusters=len(small_matrix))
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(small_matrix.to_numpy(dtype=np.float64))

    def test_too_few_samples_raises(self) -> None:
        adapter = AgglomerativeAdapter(n_clusters=2)
        with pytest.raises(ClusterAlgorithmError):
            adapter.fit(np.zeros((1, 3)))

    def test_input_not_mutated(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        original = X.copy()
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward")
        adapter.fit(X)
        assert np.array_equal(X, original)


# ---------------------------------------------------------------------------
# Linkage coverage
# ---------------------------------------------------------------------------


class TestLinkageCoverage:
    """All four advertised linkages must fit successfully on the
    well-separated matrix. Each linkage has its own characteristic
    distance profile (different max_merge_distance), so the test
    verifies that the adapter produces distinct, valid results
    rather than silently collapsing to a single linkage's output.
    """

    @pytest.mark.parametrize("linkage", sorted(SUPPORTED_LINKAGES))
    def test_linkage_fits(self, well_separated_matrix: pd.DataFrame, linkage: str) -> None:
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        # Ward requires Euclidean; the others accept any supported metric.
        metric = "euclidean"
        adapter = AgglomerativeAdapter(n_clusters=3, linkage=linkage, metric=metric)
        result = adapter.fit(X)
        assert isinstance(result, ClusterResult)
        assert result.n_clusters == 3
        assert result.cluster_labels.shape == (X.shape[0],)
        # Extras reflect the requested linkage / metric.
        assert result.extra["linkage"] == linkage
        assert result.extra["metric"] == metric

    def test_linkages_produce_different_merge_distances(
        self, well_separated_matrix: pd.DataFrame
    ) -> None:
        # Sanity: the four linkages should produce observably
        # different merge-distance profiles on the same data. We
        # compare only that the max_merge_distance differs between
        # the most distinct linkages (ward vs. single) to avoid
        # over-constraining a fuzzy property.
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        ward_max = (
            AgglomerativeAdapter(n_clusters=3, linkage="ward", metric="euclidean")
            .fit(X)
            .extra["max_merge_distance"]
        )
        single_max = (
            AgglomerativeAdapter(n_clusters=3, linkage="single", metric="euclidean")
            .fit(X)
            .extra["max_merge_distance"]
        )
        # ward and single linkage use very different distance
        # regimes; on a well-separated 2-D synthetic dataset the
        # max distance under ward is much larger than under single.
        assert isinstance(ward_max, float)
        assert isinstance(single_max, float)
        assert ward_max > single_max


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_returns_cluster_result(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward")
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert isinstance(result, ClusterResult)

    def test_labels_shape_matches_n_samples(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward")
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.cluster_labels.shape == (X.shape[0],)
        assert result.cluster_labels.dtype == np.int64

    def test_n_clusters_matches_k(self, well_separated_matrix: pd.DataFrame) -> None:
        k = 3
        adapter = AgglomerativeAdapter(n_clusters=k, linkage="ward")
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.n_clusters == k
        assert int(result.cluster_labels.max()) + 1 == k
        assert int(result.cluster_labels.min()) >= 0

    def test_metadata_fields(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(
            n_clusters=3,
            linkage="average",
            metric="euclidean",
            compute_distances=True,
        )
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        result = adapter.fit(X)
        assert result.algorithm == "agglomerative"
        assert result.algorithm_family == AlgorithmFamily.HARD
        assert result.algorithm_version.startswith("sklearn_")
        assert result.n_samples == X.shape[0]
        assert result.n_features == X.shape[1]
        # Determinism: random_state_used is always None and the
        # adapter advertises no random_state support.
        assert result.supports_random_state is False
        assert result.random_seed_used is None

    def test_extra_includes_diagnostic_info(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(
            n_clusters=3, linkage="ward", metric="euclidean", compute_distances=True
        )
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        for key in (
            "linkage",
            "metric",
            "compute_distances_used",
            "n_leaves",
            "n_merges",
            "cluster_sizes",
            "max_merge_distance",
            "min_merge_distance",
            "median_merge_distance",
            "merge_distances_summary",
        ):
            assert key in result.extra, f"missing extra key: {key}"
        # n_merges should be n_samples - 1.
        assert result.extra["n_merges"] == result.n_samples - 1
        assert result.extra["n_leaves"] == result.n_samples
        # merge distance fields are floats (None only if sklearn did
        # not expose distances_, which it should for n_samples>1).
        assert isinstance(result.extra["max_merge_distance"], float)
        assert isinstance(result.extra["min_merge_distance"], float)
        assert isinstance(result.extra["median_merge_distance"], float)
        assert result.extra["max_merge_distance"] >= result.extra["min_merge_distance"]
        # cluster_sizes is a dict.
        assert isinstance(result.extra["cluster_sizes"], dict)
        # Merge distances summary is a list.
        assert isinstance(result.extra["merge_distances_summary"], list)

    def test_extra_no_distances_when_disabled(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(
            n_clusters=3, linkage="ward", metric="euclidean", compute_distances=False
        )
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        # compute_distances_used is recorded truthfully.
        assert result.extra["compute_distances_used"] is False
        # Distance-summary fields must be None (sklearn did not
        # populate model.distances_).
        assert result.extra["max_merge_distance"] is None
        assert result.extra["min_merge_distance"] is None
        assert result.extra["median_merge_distance"] is None
        assert result.extra["merge_distances_summary"] is None
        # But cluster_sizes and other diagnostic fields remain.
        assert isinstance(result.extra["cluster_sizes"], dict)
        assert result.extra["n_merges"] == result.n_samples - 1

    def test_metrics_placeholder_is_default(self, well_separated_matrix: pd.DataFrame) -> None:
        # ML-03 MUST NOT compute evaluation metrics.
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward")
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.metrics.silhouette is None
        assert result.metrics.davies_bouldin is None
        assert result.metrics.calinski_harabasz is None
        assert result.metrics.wcss is None
        assert result.metrics.stability is None
        assert result.metrics.runtime is None

    def test_noise_count_zero_for_agglomerative(self, well_separated_matrix: pd.DataFrame) -> None:
        # Agglomerative (n_clusters mode) has no noise concept.
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward")
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        assert result.noise_count == 0
        assert result.noise_ratio == 0.0

    def test_result_is_serialisable(self, well_separated_matrix: pd.DataFrame) -> None:
        adapter = AgglomerativeAdapter(n_clusters=3, linkage="ward")
        result = adapter.fit(well_separated_matrix.to_numpy(dtype=np.float64))
        # to_dict() must produce JSON-friendly dict.
        d = result.to_dict()
        json.dumps(d, default=str)
        assert d["n_samples"] == result.n_samples
        assert d["algorithm"] == "agglomerative"


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """Agglomerative clustering in n_clusters mode is deterministic in
    modern sklearn. Same input + same configuration + same library
    version → same labels, with no seed consumed. The framework's
    seed-injection logic uses ``supports_random_state()`` to skip the
    seed for deterministic adapters; the experiments below verify
    both the deterministic labels AND the framework's seed-handling.
    """

    def test_same_config_same_labels(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        r1 = AgglomerativeAdapter(n_clusters=4, linkage="ward").fit(X)
        r2 = AgglomerativeAdapter(n_clusters=4, linkage="ward").fit(X)
        np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels)

    def test_same_config_same_labels_all_linkages(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy(dtype=np.float64)
        for linkage in sorted(SUPPORTED_LINKAGES):
            metric = "euclidean"  # ward requires euclidean
            r1 = AgglomerativeAdapter(n_clusters=4, linkage=linkage, metric=metric).fit(X)
            r2 = AgglomerativeAdapter(n_clusters=4, linkage=linkage, metric=metric).fit(X)
            np.testing.assert_array_equal(r1.cluster_labels, r2.cluster_labels)

    def test_random_seed_used_is_none(self, small_matrix: pd.DataFrame) -> None:
        # No seed is consumed even if a user tries to pass one via
        # the framework seed_override — the adapter constructor does
        # not accept a seed and the runner's seed-injection is
        # gated by supports_random_state().
        r1 = AgglomerativeAdapter(n_clusters=4, linkage="ward").fit(
            small_matrix.to_numpy(dtype=np.float64)
        )
        assert r1.random_seed_used is None
        assert r1.supports_random_state is False

    def test_reproducibility_via_centroids(self, well_separated_matrix: pd.DataFrame) -> None:
        # Agglomerative labels are deterministic — verify via
        # permutation-invariant per-cluster centroids sorted by
        # first coordinate, matching the K-Means test pattern.
        X = well_separated_matrix.to_numpy(dtype=np.float64)
        r1 = AgglomerativeAdapter(n_clusters=3, linkage="ward").fit(X)
        r2 = AgglomerativeAdapter(n_clusters=3, linkage="ward").fit(X)
        labels_1 = r1.cluster_labels
        labels_2 = r2.cluster_labels
        centroids_1 = np.array(
            sorted([X[labels_1 == k].mean(axis=0).tolist() for k in np.unique(labels_1)])
        )
        centroids_2 = np.array(
            sorted([X[labels_2 == k].mean(axis=0).tolist() for k in np.unique(labels_2)])
        )
        np.testing.assert_allclose(centroids_1, centroids_2, atol=1e-8)

    def test_get_params_reflects_configuration(self) -> None:
        adapter = AgglomerativeAdapter(
            n_clusters=5, linkage="complete", metric="euclidean", compute_distances=False
        )
        p = adapter.get_params()
        assert p["n_clusters"] == 5
        assert p["linkage"] == "complete"
        assert p["metric"] == "euclidean"
        assert p["compute_distances"] is False


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
    def test_runner_agglomerative_basic(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-03-test-basic",
            algorithm="agglomerative",
            hyperparameters={"n_clusters": 4, "linkage": "ward", "metric": "euclidean"},
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
        assert result.algorithm == "agglomerative"
        assert result.dataset_version == cfg.input.dataset_version
        assert result.dataset_sha256 == "deadbeef"
        assert result.n_clusters == 4
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
    def test_runner_agglomerative_reproducibility(self, tmp_path: Path) -> None:
        # Agglomerative in n_clusters mode is deterministic: two
        # runs with the same config must produce identical labels.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        hp = {
            "n_clusters": 4,
            "linkage": "ward",
            "metric": "euclidean",
            "compute_distances": True,
        }
        spec1 = ExperimentSpec(
            experiment_id="ML-03-test-repro-1",
            algorithm="agglomerative",
            hyperparameters=hp,
            seed_override=42,  # should be ignored by runner (supports_random_state=False)
        )
        spec2 = ExperimentSpec(
            experiment_id="ML-03-test-repro-2",
            algorithm="agglomerative",
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
        # Both runs succeeded.
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
    def test_runner_agglomerative_label_alignment_with_customer_metadata(
        self, tmp_path: Path
    ) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-03-test-alignment",
            algorithm="agglomerative",
            hyperparameters={"n_clusters": 4, "linkage": "ward", "metric": "euclidean"},
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
        # Agglomerative does not produce noise; all rows must be
        # non-noise.
        assert labels_df["IsNoise"].sum() == 0

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    def test_runner_agglomerative_experiment_log_schema(self, tmp_path: Path) -> None:
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        spec = ExperimentSpec(
            experiment_id="ML-03-test-log-schema",
            algorithm="agglomerative",
            hyperparameters={
                "n_clusters": 4,
                "linkage": "ward",
                "metric": "euclidean",
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
        assert log["algorithm"] == "agglomerative"
        assert log["n_clusters"] == 4
        # Seed requested truthfully, but the deterministic adapter
        # consumed None.
        assert log["random_seed"] == 42
        assert log["random_seed_used"] is None
        # Cluster result extras include linkage / metric diagnostics.
        assert "cluster_result" in log
        extras = log["cluster_result"]["extra"]
        assert extras["linkage"] == "ward"
        assert extras["metric"] == "euclidean"
        assert extras["n_merges"] == result.n_samples - 1
        assert "max_merge_distance" in extras
        assert "numpy" in log["library_versions"]
        assert "scikit-learn" in log["library_versions"]

    @pytest.mark.skipif(
        not FE06_DATASET.exists() or not FE06_METADATA.exists(),
        reason="FE-06 outputs not present",
    )
    @pytest.mark.parametrize("linkage", sorted(SUPPORTED_LINKAGES))
    def test_runner_agglomerative_all_linkages(self, tmp_path: Path, linkage: str) -> None:
        # All four advertised linkages must run successfully via
        # the framework runner on the real FE-06 dataset. Ward
        # requires euclidean; the others accept any supported
        # metric in SUPPORTED_METRICS.
        df, md = self._load_inputs()
        cfg = load_framework_config(self.CONFIG_PATH)
        metric = "euclidean"
        spec = ExperimentSpec(
            experiment_id=f"ML-03-test-linkage-{linkage}",
            algorithm="agglomerative",
            hyperparameters={
                "n_clusters": 4,
                "linkage": linkage,
                "metric": metric,
                "compute_distances": False,  # keep small for parametrize speed
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
        # Linkage / metric recorded truthfully.
        extras = result.cluster_result.extra
        assert extras["linkage"] == linkage
        assert extras["metric"] == metric
