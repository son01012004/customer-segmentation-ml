"""Tests for the DEV-04 clustering manifest schema and I/O."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from customer_segmentation.prototype.clustering.manifest import (
    CLUSTERING_MANIFEST_SCHEMA_VERSION,
    ClusteringManifest,
    ClusteringManifestError,
    EnvironmentBlock,
    InputIdentityBlock,
    ResearchSafetyBlock,
    build_clustering_manifest,
    manifest_to_dict,
    now_utc_iso,
    read_clustering_manifest,
    runtime_field_names,
    stable_field_names,
    write_clustering_manifest,
)


def _make_minimal_experiment_result() -> MagicMock:
    """Create a minimal mock ExperimentResult for manifest building."""
    result = MagicMock()
    result.algorithm = "kmeans"
    result.algorithm_version = "1.0.0"
    result.experiment_id = "kmeans_test123"
    result.random_seed_used = 42
    result.hyperparameters = {"n_clusters": 4}
    result.n_clusters = 4
    result.n_samples = 100
    result.feature_set = ["F1", "F2"]
    result.feature_count = 2
    result.cluster_result = MagicMock()
    result.cluster_result.algorithm_family = "hard"
    return result


def test_manifest_schema_version() -> None:
    assert CLUSTERING_MANIFEST_SCHEMA_VERSION == "1.0.0"


def test_stable_fields_contains_clustering_id() -> None:
    assert "clustering_id" in stable_field_names()
    assert "clustering_id" in stable_field_names()


def test_runtime_fields_contains_created_utc() -> None:
    assert "created_utc" in runtime_field_names()
    assert "last_seen_utc" in runtime_field_names()


def test_write_and_read_round_trip(tmp_path: Path) -> None:
    env = EnvironmentBlock(
        python="3.14",
        platform="Linux",
        release="7.0",
        machine="x86_64",
        key_libraries={"numpy": "1.26"},
    )
    identity = InputIdentityBlock(
        dataset_sha256="a" * 64,
        input_path="/dev/null",
        metadata_path="",
    )
    safety = ResearchSafetyBlock(
        automatically_promoted_to_research=False,
        scope="CLUSTERED_PROTOTYPE",
        appeared_in_research_evidence=False,
        read_only_paths_unmodified=["data/raw/primary"],
    )
    manifest = ClusteringManifest(
        schema_version="1.0.0",
        clustering_id="cl_" + "f" * 24,
        scope="CLUSTERED_PROTOTYPE",
        preprocessed_id="pp_abc",
        ml_dataset_sha256="a" * 64,
        algorithm="kmeans",
        algorithm_version="1.0.0",
        algorithm_family="hard",
        experiment_id="kmeans_cl_abc",
        experiment_log_path="experiment_log.json",
        cluster_labels_path="cluster_labels.parquet",
        algorithm_output_path=None,
        hyperparameters={"n_clusters": 4},
        seed_policy="stochastic",
        seed=42,
        config_sha256="b" * 64,
        n_clusters=4,
        n_samples=100,
        feature_set=["F1", "F2"],
        feature_count=2,
        input_identity=identity,
        environment=env,
        created_utc="2026-10-09T00:00:00Z",
        last_seen_utc="2026-10-09T00:00:00Z",
        log_file="test.log",
        research_safety=safety,
    )

    path = tmp_path / "clustering_manifest.json"
    write_clustering_manifest(manifest, path)
    assert path.exists()

    loaded = read_clustering_manifest(path)
    assert loaded.clustering_id == manifest.clustering_id
    assert loaded.algorithm == manifest.algorithm
    assert loaded.preprocessed_id == manifest.preprocessed_id
    assert loaded.n_clusters == manifest.n_clusters
    assert loaded.n_samples == manifest.n_samples
    assert loaded.scope == "CLUSTERED_PROTOTYPE"
    assert loaded.research_safety.automatically_promoted_to_research is False


def test_atomic_write(tmp_path: Path) -> None:
    env = EnvironmentBlock(
        python="3.14", platform="Linux", release="7", machine="x", key_libraries={}
    )
    identity = InputIdentityBlock(dataset_sha256="a" * 64, input_path="/x", metadata_path="")
    safety = ResearchSafetyBlock(
        automatically_promoted_to_research=False,
        scope="CLUSTERED_PROTOTYPE",
        appeared_in_research_evidence=False,
        read_only_paths_unmodified=[],
    )
    manifest = ClusteringManifest(
        schema_version="1.0.0",
        clustering_id="cl_" + "f" * 24,
        scope="CLUSTERED_PROTOTYPE",
        preprocessed_id="pp_abc",
        ml_dataset_sha256="a" * 64,
        algorithm="dbscan",
        algorithm_version="1.0.0",
        algorithm_family="density_based",
        experiment_id="dbscan_test",
        experiment_log_path="exp.json",
        cluster_labels_path="labels.parquet",
        algorithm_output_path=None,
        hyperparameters={"eps": 0.5, "min_samples": 5},
        seed_policy="deterministic",
        seed=None,
        config_sha256="b" * 64,
        n_clusters=None,
        n_samples=100,
        feature_set=["F1", "F2"],
        feature_count=2,
        input_identity=identity,
        environment=env,
        created_utc="2026-10-09T00:00:00Z",
        last_seen_utc="2026-10-09T00:00:00Z",
        log_file="test.log",
        research_safety=safety,
    )

    path = tmp_path / "atomic.json"
    write_clustering_manifest(manifest, path)

    # Verify JSON is well-formed.
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["clustering_id"] == manifest.clustering_id
    assert data["seed"] is None  # deterministic: seed null


def test_read_nonexistent_raises(tmp_path: Path) -> None:
    with pytest.raises(ClusteringManifestError):
        read_clustering_manifest(tmp_path / "nonexistent.json")


def test_read_corrupt_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.json"
    path.write_text("{ invalid json", encoding="utf-8")
    with pytest.raises(ClusteringManifestError):
        read_clustering_manifest(path)


def test_read_missing_required_field_raises(tmp_path: Path) -> None:
    path = tmp_path / "incomplete.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump({"clustering_id": "cl_test"}, fh)
    with pytest.raises(ClusteringManifestError):
        read_clustering_manifest(path)


def test_build_manifest_from_experiment_result() -> None:
    result = _make_minimal_experiment_result()
    manifest = build_clustering_manifest(
        experiment_result=result,
        clustering_id="cl_" + "f" * 24,
        preprocessed_id="pp_abc",
        ml_dataset_sha256="a" * 64,
        config_sha256="b" * 64,
        experiment_log_path="experiment_log.json",
        cluster_labels_path="cluster_labels.parquet",
        algorithm_output_path=None,
        log_file="test.log",
        input_identity=InputIdentityBlock(
            dataset_sha256="a" * 64, input_path="/dev/null", metadata_path=""
        ),
        environment=EnvironmentBlock(
            python="3.14", platform="Linux", release="7", machine="x", key_libraries={}
        ),
        readonly_paths=["data/raw/primary"],
    )

    assert manifest.clustering_id == "cl_" + "f" * 24
    assert manifest.preprocessed_id == "pp_abc"
    assert manifest.algorithm == "kmeans"
    assert manifest.seed_policy == "stochastic"
    assert manifest.seed == 42
    assert manifest.scope == "CLUSTERED_PROTOTYPE"
    assert manifest.research_safety.automatically_promoted_to_research is False
    assert manifest.research_safety.scope == "CLUSTERED_PROTOTYPE"


def test_deterministic_algorithm_seed_is_null() -> None:
    result = _make_minimal_experiment_result()
    result.algorithm = "dbscan"
    result.cluster_result.algorithm_family = "density_based"
    result.random_seed_used = None

    manifest = build_clustering_manifest(
        experiment_result=result,
        clustering_id="cl_" + "f" * 24,
        preprocessed_id="pp_abc",
        ml_dataset_sha256="a" * 64,
        config_sha256="b" * 64,
        experiment_log_path="exp.json",
        cluster_labels_path="labels.parquet",
        algorithm_output_path=None,
        log_file="test.log",
        input_identity=InputIdentityBlock(
            dataset_sha256="a" * 64, input_path="/dev/null", metadata_path=""
        ),
        environment=EnvironmentBlock(
            python="3.14", platform="Linux", release="7", machine="x", key_libraries={}
        ),
        readonly_paths=[],
    )

    assert manifest.seed_policy == "deterministic"
    assert manifest.seed is None


def test_manifest_to_dict_round_trip(tmp_path: Path) -> None:
    env = EnvironmentBlock(
        python="3.14", platform="Linux", release="7", machine="x", key_libraries={}
    )
    identity = InputIdentityBlock(dataset_sha256="a" * 64, input_path="/x", metadata_path="")
    safety = ResearchSafetyBlock(
        automatically_promoted_to_research=False,
        scope="CLUSTERED_PROTOTYPE",
        appeared_in_research_evidence=False,
        read_only_paths_unmodified=[],
    )
    manifest = ClusteringManifest(
        schema_version="1.0.0",
        clustering_id="cl_" + "f" * 24,
        scope="CLUSTERED_PROTOTYPE",
        preprocessed_id="pp_abc",
        ml_dataset_sha256="a" * 64,
        algorithm="gmm",
        algorithm_version="1.0.0",
        algorithm_family="model_based",
        experiment_id="gmm_test",
        experiment_log_path="exp.json",
        cluster_labels_path="labels.parquet",
        algorithm_output_path="algo_out.parquet",
        hyperparameters={"n_components": 4},
        seed_policy="stochastic",
        seed=42,
        config_sha256="b" * 64,
        n_clusters=4,
        n_samples=100,
        feature_set=["F1"],
        feature_count=1,
        input_identity=identity,
        environment=env,
        created_utc="2026-10-09T00:00:00Z",
        last_seen_utc="2026-10-09T00:00:00Z",
        log_file="test.log",
        research_safety=safety,
    )

    d = manifest_to_dict(manifest)
    assert isinstance(d, dict)
    assert d["clustering_id"] == manifest.clustering_id
    assert d["algorithm_output_path"] == "algo_out.parquet"


def test_now_utc_iso_format() -> None:
    ts = now_utc_iso()
    assert ts.endswith("Z")
    assert "T" in ts
    assert len(ts) == 20  # ISO 8601 without microseconds
