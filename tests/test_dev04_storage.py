"""Tests for the DEV-04 storage helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_segmentation.prototype.clustering.storage import (
    CLUSTERING_ID_HEX_LEN,
    CLUSTERING_ID_PREFIX,
    Dev04CollisionError,
    Dev04ConfigError,
    Dev04StoragePathError,
    derive_clustering_id,
    find_existing_clustering,
    prototype_clustering_base_dir,
    prototype_clustering_run_dir,
)


class TestDeriveClusteringId:
    def test_format_prefix_and_length(self) -> None:
        cid = derive_clustering_id(
            preprocessed_id="pp_test123",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
            effective_seed=42,
            ml_dataset_sha256="a" * 64,
            config_sha256="b" * 64,
        )
        assert cid.startswith(CLUSTERING_ID_PREFIX)
        assert len(cid) == len(CLUSTERING_ID_PREFIX) + CLUSTERING_ID_HEX_LEN
        assert cid == CLUSTERING_ID_PREFIX + cid[len(CLUSTERING_ID_PREFIX) :]

    def test_same_inputs_produce_same_id(self) -> None:
        kwargs = {
            "preprocessed_id": "pp_abc",
            "algorithm": "kmeans",
            "hyperparameters": {"n_clusters": 4},
            "effective_seed": 42,
            "ml_dataset_sha256": "a" * 64,
            "config_sha256": "b" * 64,
        }
        assert derive_clustering_id(**kwargs) == derive_clustering_id(**kwargs)

    def test_different_algorithm_different_id(self) -> None:
        base = {
            "preprocessed_id": "pp_abc",
            "hyperparameters": {"n_clusters": 4},
            "effective_seed": 42,
            "ml_dataset_sha256": "a" * 64,
            "config_sha256": "b" * 64,
        }
        id_a = derive_clustering_id(algorithm="kmeans", **base)
        id_b = derive_clustering_id(algorithm="gmm", **base)
        assert id_a != id_b

    def test_different_seed_different_id(self) -> None:
        base = {
            "preprocessed_id": "pp_abc",
            "algorithm": "kmeans",
            "hyperparameters": {"n_clusters": 4},
            "ml_dataset_sha256": "a" * 64,
            "config_sha256": "b" * 64,
        }
        id_a = derive_clustering_id(effective_seed=42, **base)
        id_b = derive_clustering_id(effective_seed=99, **base)
        assert id_a != id_b

    def test_deterministic_algorithm_ignores_seed(self) -> None:
        """Deterministic algorithms must pass None for effective_seed."""
        base = {
            "preprocessed_id": "pp_abc",
            "algorithm": "dbscan",
            "hyperparameters": {"eps": 0.5},
            "ml_dataset_sha256": "a" * 64,
            "config_sha256": "b" * 64,
        }
        id_a = derive_clustering_id(effective_seed=None, **base)
        id_b = derive_clustering_id(effective_seed=99, **base)
        # Both must produce the same ID (seed always null in canonical payload).
        assert id_a == id_b

    def test_hyperparameter_order_does_not_matter(self) -> None:
        base = {
            "preprocessed_id": "pp_abc",
            "algorithm": "kmeans",
            "effective_seed": 42,
            "ml_dataset_sha256": "a" * 64,
            "config_sha256": "b" * 64,
        }
        id_a = derive_clustering_id(hyperparameters={"a": 1, "b": 2}, **base)
        id_b = derive_clustering_id(hyperparameters={"b": 2, "a": 1}, **base)
        assert id_a == id_b

    def test_rejects_empty_preprocessed_id(self) -> None:
        with pytest.raises(Dev04ConfigError):
            derive_clustering_id(
                preprocessed_id="",
                algorithm="kmeans",
                hyperparameters={},
                effective_seed=42,
                ml_dataset_sha256="a" * 64,
                config_sha256="b" * 64,
            )

    def test_rejects_unknown_algorithm(self) -> None:
        with pytest.raises(Dev04ConfigError):
            derive_clustering_id(
                preprocessed_id="pp_abc",
                algorithm="unknown_algo",
                hyperparameters={},
                effective_seed=42,
                ml_dataset_sha256="a" * 64,
                config_sha256="b" * 64,
            )


class TestPrototypeClusteringBaseDir:
    def test_inside_storage_root(self, tmp_path: Path) -> None:
        base = prototype_clustering_base_dir(tmp_path, "ds_abc123", "pp_xyz789")
        assert base.is_relative_to(tmp_path)

    def test_path_structure(self, tmp_path: Path) -> None:
        base = prototype_clustering_base_dir(tmp_path, "ds_abc", "pp_xyz")
        parts = base.relative_to(tmp_path).parts
        assert parts == ("ds_abc", "preprocessed", "pp_xyz", "clustering")

    def test_rejects_empty_dataset_id(self, tmp_path: Path) -> None:
        with pytest.raises(Dev04StoragePathError):
            prototype_clustering_base_dir(tmp_path, "", "pp_xyz")

    def test_rejects_empty_preprocessed_id(self, tmp_path: Path) -> None:
        with pytest.raises(Dev04StoragePathError):
            prototype_clustering_base_dir(tmp_path, "ds_abc", "")


# ---------------------------------------------------------------------------
# Regression: A-1 path-doubling bug
# ---------------------------------------------------------------------------
# When ``storage_root`` matches the value from
# ``configs/dev02_dataset_management.yaml::dataset_management.storage_root``
# (i.e. ``data/prototype/datasets``), the resolved base_dir must NOT
# contain a doubled ``"datasets"`` segment. The previous
# implementation prepended an extra ``"datasets"`` literal to every
# base_dir formula, which produced
# ``<storage_root>/datasets/<dataset_id>/preprocessed/<pp_id>/clustering``.
# Because DEV-02/DEV-03 already write into
# ``<storage_root>/<dataset_id>/...`` (no second ``datasets`` segment),
# the lookup path never matched DEV-03's on-disk output and
# CLUSTERING stage in DEV-09 failed with ``FileNotFoundError``.
#
# This regression test must FAIL before the A-1 fix and PASS after.
# See ``docs/system/DEV-04_clustering_execution.md`` for the storage
# layout convention that DEV-02/03/04/06/08 now share.
# ---------------------------------------------------------------------------


class TestPathDoublingRegressionA1:
    """Regression test for the A-1 path-doubling bug (DEV-04..08)."""

    def test_clustering_base_dir_no_datasets_segment_rejects(
        self, tmp_path: Path
    ) -> None:
        """When ``storage_root`` is itself named ``datasets`` (matching
        the canonical DEV-02 config), the base_dir must NOT prepend an
        extra ``"datasets"`` literal. This is the exact scenario that
        broke DEV-09 in production."""
        # Simulate configs/dev02_dataset_management.yaml::storage_root = "data/prototype/datasets"
        storage_root = (tmp_path / "datasets").resolve()
        base = prototype_clustering_base_dir(
            storage_root,
            dataset_id="ds_test01",
            preprocessed_id="pp_test01",
        )
        # The path should be: storage_root / ds_test01 / preprocessed / pp_test01 / clustering
        # (NOT: storage_root / datasets / ds_test01 / preprocessed / pp_test01 / clustering)
        parts = base.relative_to(storage_root).parts
        assert "datasets" not in parts, (
            f"Path-doubling regression: base_dir={base} contains a doubled "
            f"'datasets' segment relative to storage_root={storage_root}. "
            f"parts={parts}"
        )
        assert parts == ("ds_test01", "preprocessed", "pp_test01", "clustering")

    def test_clustering_run_dir_no_datasets_segment_rejects(
        self, tmp_path: Path
    ) -> None:
        """Same regression but for ``prototype_clustering_run_dir``."""
        storage_root = (tmp_path / "datasets").resolve()
        cid = "cl_" + "f" * 24
        run = prototype_clustering_run_dir(
            storage_root, "ds_test01", "pp_test01", cid
        )
        parts = run.relative_to(storage_root).parts
        assert "datasets" not in parts, (
            f"Path-doubling regression: run_dir={run} contains a doubled "
            f"'datasets' segment relative to storage_root={storage_root}. "
            f"parts={parts}"
        )
        assert parts == (
            "ds_test01",
            "preprocessed",
            "pp_test01",
            "clustering",
            cid,
        )


class TestPrototypeClusteringRunDir:
    def test_inside_storage_root(self, tmp_path: Path) -> None:
        run = prototype_clustering_run_dir(tmp_path, "ds_abc", "pp_xyz", "cl_" + "f" * 24)
        assert run.is_relative_to(tmp_path)

    def test_path_structure(self, tmp_path: Path) -> None:
        run = prototype_clustering_run_dir(tmp_path, "ds_abc", "pp_xyz", "cl_" + "f" * 24)
        parts = run.relative_to(tmp_path).parts
        assert parts == (
            "ds_abc",
            "preprocessed",
            "pp_xyz",
            "clustering",
            "cl_" + "f" * 24,
        )

    def test_rejects_invalid_clustering_id_format(self, tmp_path: Path) -> None:
        with pytest.raises(Dev04StoragePathError):
            prototype_clustering_run_dir(tmp_path, "ds_abc", "pp_xyz", "invalid")
        with pytest.raises(Dev04StoragePathError):
            prototype_clustering_run_dir(tmp_path, "ds_abc", "pp_xyz", "cl_short")


class TestFindExistingClustering:
    def test_returns_none_when_no_manifest(self, tmp_path: Path) -> None:
        result = find_existing_clustering(
            tmp_path,
            "ds_abc",
            "pp_xyz",
            "cl_" + "f" * 24,
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
            effective_seed=42,
            ml_dataset_sha256="a" * 64,
            config_sha256="b" * 64,
        )
        assert result is None

    def test_returns_path_when_manifest_matches(self, tmp_path: Path) -> None:
        cid = "cl_" + "f" * 24
        base = prototype_clustering_base_dir(tmp_path, "ds_abc", "pp_xyz")
        run_dir = base / cid
        run_dir.mkdir(parents=True)

        # Write a valid manifest.
        import json

        manifest = {
            "schema_version": "1.0.0",
            "clustering_id": cid,
            "scope": "CLUSTERED_PROTOTYPE",
            "preprocessed_id": "pp_xyz",
            "ml_dataset_sha256": "a" * 64,
            "algorithm": "kmeans",
            "algorithm_version": "1.0.0",
            "algorithm_family": "hard",
            "experiment_id": "kmeans_" + cid,
            "experiment_log_path": f"experiment_log_kmeans_{cid}.json",
            "cluster_labels_path": f"cluster_labels_kmeans_{cid}.parquet",
            "hyperparameters": {"n_clusters": 4},
            "seed_policy": "stochastic",
            "seed": 42,
            "config_sha256": "b" * 64,
            "n_samples": 100,
            "feature_set": ["F1", "F2"],
            "feature_count": 2,
            "input_identity": {
                "dataset_sha256": "a" * 64,
                "input_path": "/dev/null",
                "metadata_path": "",
            },
            "environment": {
                "python": "3.14",
                "platform": "Linux",
                "release": "7.0",
                "machine": "x86_64",
                "key_libraries": {},
            },
            "created_utc": "2026-10-09T00:00:00Z",
            "last_seen_utc": "2026-10-09T00:00:00Z",
            "log_file": f"{cid}.log",
            "research_safety": {
                "automatically_promoted_to_research": False,
                "scope": "CLUSTERED_PROTOTYPE",
                "appeared_in_research_evidence": False,
                "read_only_paths_unmodified": [],
            },
        }
        manifest_path = run_dir / "clustering_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

        result = find_existing_clustering(
            tmp_path,
            "ds_abc",
            "pp_xyz",
            cid,
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
            effective_seed=42,
            ml_dataset_sha256="a" * 64,
            config_sha256="b" * 64,
        )
        assert result == manifest_path

    def test_raises_on_mismatched_canonical_payload(self, tmp_path: Path) -> None:
        cid = "cl_" + "f" * 24
        base = prototype_clustering_base_dir(tmp_path, "ds_abc", "pp_xyz")
        run_dir = base / cid
        run_dir.mkdir(parents=True)

        import json

        manifest = {
            "schema_version": "1.0.0",
            "clustering_id": cid,
            "scope": "CLUSTERED_PROTOTYPE",
            "preprocessed_id": "pp_xyz",
            "ml_dataset_sha256": "a" * 64,
            "algorithm": "kmeans",
            "algorithm_version": "1.0.0",
            "algorithm_family": "hard",
            "experiment_id": "kmeans_" + cid,
            "experiment_log_path": f"experiment_log_kmeans_{cid}.json",
            "cluster_labels_path": f"cluster_labels_kmeans_{cid}.parquet",
            "hyperparameters": {"n_clusters": 5},  # DIFFERENT from caller's 4
            "seed_policy": "stochastic",
            "seed": 42,
            "config_sha256": "b" * 64,
            "n_samples": 100,
            "feature_set": ["F1", "F2"],
            "feature_count": 2,
            "input_identity": {
                "dataset_sha256": "a" * 64,
                "input_path": "/dev/null",
                "metadata_path": "",
            },
            "environment": {
                "python": "3.14",
                "platform": "Linux",
                "release": "7.0",
                "machine": "x86_64",
                "key_libraries": {},
            },
            "created_utc": "2026-10-09T00:00:00Z",
            "last_seen_utc": "2026-10-09T00:00:00Z",
            "log_file": f"{cid}.log",
            "research_safety": {
                "automatically_promoted_to_research": False,
                "scope": "CLUSTERED_PROTOTYPE",
                "appeared_in_research_evidence": False,
                "read_only_paths_unmodified": [],
            },
        }
        manifest_path = run_dir / "clustering_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

        with pytest.raises(Dev04CollisionError):
            find_existing_clustering(
                tmp_path,
                "ds_abc",
                "pp_xyz",
                cid,
                algorithm="kmeans",
                hyperparameters={"n_clusters": 4},
                effective_seed=42,
                ml_dataset_sha256="a" * 64,
                config_sha256="b" * 64,
            )
