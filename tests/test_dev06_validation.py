"""Tests for the DEV-06 validation module (Phase 2F)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from customer_segmentation.prototype.segmentation.config_loader import (
    load_dev06_config,
)
from customer_segmentation.prototype.segmentation.validation import (
    validate_cluster_labels,
    validate_clustering_manifest,
    validate_evaluation_manifest_if_provided,
    validate_feature_set,
    validate_inputs,
    validate_label_dataset_alignment,
    validate_ml_dataset,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_clustering_manifest(
    path: Path,
    *,
    schema_version: str = "1.0.0",
    include_required: bool = True,
) -> None:
    data: dict = {
        "schema_version": schema_version,
        "clustering_id": "cl_" + "a" * 24,
        "preprocessed_id": "pp_xyz",
        "dataset_id": "ds_abc",
        "algorithm": "kmeans",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "b" * 64,
        "feature_set": ["a", "b", "c", "d"],
        "n_samples": 100,
        "n_clusters": 4,
    }
    if not include_required:
        data.pop("feature_set", None)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_cluster_labels(
    path: Path,
    *,
    n: int = 100,
    n_clusters: int = 4,
    add_isnoise: bool = True,
    add_customer_id: bool = True,
) -> None:
    rng = np.random.default_rng(42)
    labels = rng.integers(0, n_clusters, size=n).astype(np.int64)
    df = pd.DataFrame({"ClusterLabel": labels})
    if add_isnoise:
        df["IsNoise"] = (labels == -1).astype(bool)
    if add_customer_id:
        df["CustomerID"] = np.arange(1, n + 1)
    df.to_parquet(path)


def _write_ml_dataset(
    path: Path,
    *,
    n: int = 100,
    columns: list[str] | None = None,
) -> None:
    if columns is None:
        columns = ["a", "b", "c", "d"]
    rng = np.random.default_rng(42)
    df = pd.DataFrame(
        rng.standard_normal((n, len(columns))),
        columns=columns,
    )
    df.insert(0, "CustomerID", np.arange(1, n + 1))
    df.to_parquet(path)


def _write_preprocessed_manifest(
    path: Path,
    *,
    schema_version: str = "1.0.0",
    artifact_path: str = "ml_dataset_test.parquet",
    config_hash: str = "f" * 64,
) -> None:
    data = {
        "schema_version": schema_version,
        "config_hash": config_hash,
        "ml_dataset_block": {"artifact_path": artifact_path},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# validate_clustering_manifest
# ---------------------------------------------------------------------------


class TestValidateClusteringManifest:
    def test_valid(self, tmp_path: Path) -> None:
        p = tmp_path / "cm.json"
        _write_clustering_manifest(p)
        data, checks = validate_clustering_manifest(p)
        assert all(c.passed for c in checks)
        assert data["clustering_id"] == "cl_" + "a" * 24

    def test_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.json"
        _, checks = validate_clustering_manifest(p)
        assert not checks[0].passed

    def test_wrong_schema_version(self, tmp_path: Path) -> None:
        p = tmp_path / "cm.json"
        _write_clustering_manifest(p, schema_version="0.0.0")
        _, checks = validate_clustering_manifest(p)
        assert any(not c.passed and "schema_version" in c.check_id for c in checks)

    def test_missing_feature_set(self, tmp_path: Path) -> None:
        p = tmp_path / "cm.json"
        _write_clustering_manifest(p, include_required=False)
        _, checks = validate_clustering_manifest(p)
        assert any(not c.passed and "feature_set" in c.check_id for c in checks)


# ---------------------------------------------------------------------------
# validate_cluster_labels
# ---------------------------------------------------------------------------


class TestValidateClusterLabels:
    def test_valid(self, tmp_path: Path) -> None:
        p = tmp_path / "cl.parquet"
        _write_cluster_labels(p)
        df, checks = validate_cluster_labels(p)
        assert all(c.passed for c in checks)
        assert "ClusterLabel" in df.columns
        assert "IsNoise" in df.columns

    def test_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.parquet"
        _, checks = validate_cluster_labels(p)
        assert not checks[0].passed

    def test_dbscan_noise_consistent(self, tmp_path: Path) -> None:
        p = tmp_path / "cl.parquet"
        _write_cluster_labels(p)
        df, checks = validate_cluster_labels(p, algorithm_family="density_based")
        # All passed (no noise rows but IsNoise is consistent).
        assert all(c.passed for c in checks)

    def test_dbscan_with_noise(self, tmp_path: Path) -> None:
        p = tmp_path / "cl.parquet"
        # Force some noise rows.
        np.random.default_rng(42)
        labels = np.array([0, 0, 0, -1, -1, 1, 1, 2], dtype=np.int64)
        df = pd.DataFrame({"ClusterLabel": labels, "IsNoise": (labels == -1)})
        df.to_parquet(p)
        df, checks = validate_cluster_labels(p, algorithm_family="density_based")
        assert all(c.passed for c in checks)

    def test_non_dbscan_negative_label_fail(self, tmp_path: Path) -> None:
        p = tmp_path / "cl.parquet"
        # Inject a -1 label.
        labels = np.array([0, 0, 0, -1, 1, 1, 2], dtype=np.int64)
        df = pd.DataFrame({"ClusterLabel": labels, "IsNoise": (labels == -1).astype(bool)})
        df.to_parquet(p)
        _, checks = validate_cluster_labels(p, algorithm_family="hard")
        assert any(not c.passed and "non_dbscan" in c.check_id for c in checks)

    def test_isnoise_inconsistent(self, tmp_path: Path) -> None:
        p = tmp_path / "cl.parquet"
        labels = np.array([0, 0, 0, 1, 1, 2], dtype=np.int64)
        # Mark a non-noise row as noise.
        df = pd.DataFrame(
            {"ClusterLabel": labels, "IsNoise": [False, False, False, True, False, False]}
        )
        df.to_parquet(p)
        _, checks = validate_cluster_labels(p, algorithm_family="density_based")
        assert any(not c.passed and "IsNoise_consistent" in c.check_id for c in checks)


# ---------------------------------------------------------------------------
# validate_ml_dataset
# ---------------------------------------------------------------------------


class TestValidateMlDataset:
    def test_valid(self, tmp_path: Path) -> None:
        p = tmp_path / "ml.parquet"
        _write_ml_dataset(p)
        df, checks = validate_ml_dataset(p)
        assert all(c.passed for c in checks)

    def test_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.parquet"
        _, checks = validate_ml_dataset(p)
        assert not checks[0].passed

    def test_min_features(self, tmp_path: Path) -> None:
        p = tmp_path / "ml.parquet"
        # Only 1 column (just "a", no CustomerID).
        _write_ml_dataset(p, columns=["a"])
        # Read the file as-is (the helper adds CustomerID, so the actual
        # file has 2 columns). Manually write a 1-column file instead.
        import pyarrow as pa
        import pyarrow.parquet as pq

        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        pq.write_table(pa.Table.from_pandas(df), p)
        _, checks = validate_ml_dataset(p, min_features=2)
        assert any(not c.passed and "min_features" in c.check_id for c in checks)


# ---------------------------------------------------------------------------
# validate_label_dataset_alignment
# ---------------------------------------------------------------------------


class TestValidateAlignment:
    def test_same_size(self) -> None:
        rng = np.random.default_rng(0)
        cl = pd.DataFrame(
            {
                "ClusterLabel": rng.integers(0, 3, 10),
                "IsNoise": [False] * 10,
                "CustomerID": np.arange(1, 11),
            }
        )
        ml = pd.DataFrame(
            {
                "a": rng.standard_normal(10),
                "CustomerID": np.arange(1, 11),
            }
        )
        checks = validate_label_dataset_alignment(cl, ml)
        passed = [c.passed for c in checks]
        assert any(passed)  # row_count_match should be True
        assert any(c.passed and c.check_id == "customer_id_alignment" for c in checks)

    def test_different_size(self) -> None:
        cl = pd.DataFrame(
            {
                "ClusterLabel": [0] * 5,
                "IsNoise": [False] * 5,
            }
        )
        ml = pd.DataFrame({"a": [0.0] * 10})
        checks = validate_label_dataset_alignment(cl, ml)
        assert any(not c.passed and c.check_id == "row_count_match" for c in checks)

    def test_mismatched_customer_id(self) -> None:
        cl = pd.DataFrame(
            {
                "ClusterLabel": [0] * 5,
                "IsNoise": [False] * 5,
                "CustomerID": [1, 2, 3, 4, 5],
            }
        )
        ml = pd.DataFrame(
            {
                "a": [0.0] * 5,
                "CustomerID": [10, 20, 30, 40, 50],
            }
        )
        checks = validate_label_dataset_alignment(cl, ml)
        assert any(not c.passed and c.check_id == "customer_id_alignment" for c in checks)


# ---------------------------------------------------------------------------
# validate_feature_set
# ---------------------------------------------------------------------------


class TestValidateFeatureSet:
    def test_valid(self) -> None:
        ml = pd.DataFrame({"a": [1.0], "b": [2.0], "c": [3.0]})
        checks = validate_feature_set(["a", "b", "c"], ml)
        assert all(c.passed for c in checks)

    def test_missing_features(self) -> None:
        ml = pd.DataFrame({"a": [1.0]})
        checks = validate_feature_set(["a", "b"], ml)
        assert any(not c.passed and "subset_of_dataset_columns" in c.check_id for c in checks)

    def test_empty_feature_set(self) -> None:
        ml = pd.DataFrame({"a": [1.0]})
        checks = validate_feature_set([], ml)
        assert any(not c.passed and "non_empty" in c.check_id for c in checks)

    def test_customer_id_excluded(self) -> None:
        ml = pd.DataFrame({"a": [1.0], "CustomerID": [1]})
        # feature_set has CustomerID — should be silently dropped.
        checks = validate_feature_set(["a", "CustomerID"], ml)
        assert all(c.passed for c in checks)


# ---------------------------------------------------------------------------
# validate_evaluation_manifest_if_provided
# ---------------------------------------------------------------------------


class TestValidateEvaluationManifest:
    def test_none_path(self) -> None:
        _, checks = validate_evaluation_manifest_if_provided(None, "cl_xxx", "m1")
        assert any(c.passed and "not_provided" in c.check_id for c in checks)

    def test_valid(self, tmp_path: Path) -> None:
        p = tmp_path / "ev.json"
        p.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "clustering_id": "cl_" + "a" * 24,
                    "ml_dataset_sha256": "b" * 64,
                }
            )
        )
        _, checks = validate_evaluation_manifest_if_provided(p, "cl_" + "a" * 24, "b" * 64)
        assert all(c.passed for c in checks)

    def test_mismatched_clustering_id(self, tmp_path: Path) -> None:
        p = tmp_path / "ev.json"
        p.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "clustering_id": "cl_" + "b" * 24,
                    "ml_dataset_sha256": "b" * 64,
                }
            )
        )
        _, checks = validate_evaluation_manifest_if_provided(p, "cl_" + "a" * 24, "b" * 64)
        assert any(not c.passed and "clustering_id_match" in c.check_id for c in checks)

    def test_malformed_json(self, tmp_path: Path) -> None:
        p = tmp_path / "ev.json"
        p.write_text("not json")
        _, checks = validate_evaluation_manifest_if_provided(p, "cl_x", "b" * 64)
        assert any(not c.passed for c in checks)


# ---------------------------------------------------------------------------
# validate_inputs (top-level)
# ---------------------------------------------------------------------------


class TestValidateInputs:
    def test_all_valid(self, tmp_path: Path) -> None:
        cm = tmp_path / "cm.json"
        cl = tmp_path / "cl.parquet"
        ml = tmp_path / "ml.parquet"
        pp = tmp_path / "pp.json"
        _write_clustering_manifest(cm)
        _write_cluster_labels(cl)
        _write_ml_dataset(ml)
        _write_preprocessed_manifest(pp, artifact_path=ml.name)
        config, _ = load_dev06_config()
        report = validate_inputs(
            clustering_manifest_path=cm,
            cluster_labels_path=cl,
            ml_dataset_path=ml,
            preprocessed_manifest_path=pp,
            config=config,
        )
        assert report.all_passed, [c for c in report.checks if not c.passed]

    def test_missing_artifact_in_pp_manifest(self, tmp_path: Path) -> None:
        cm = tmp_path / "cm.json"
        cl = tmp_path / "cl.parquet"
        ml = tmp_path / "ml.parquet"
        pp = tmp_path / "pp.json"
        _write_clustering_manifest(cm)
        _write_cluster_labels(cl)
        _write_ml_dataset(ml)
        _write_preprocessed_manifest(pp, artifact_path="")
        config, _ = load_dev06_config()
        report = validate_inputs(
            clustering_manifest_path=cm,
            cluster_labels_path=cl,
            ml_dataset_path=ml,
            preprocessed_manifest_path=pp,
            config=config,
        )
        assert not report.all_passed

    def test_min_samples_violation(self, tmp_path: Path) -> None:
        cm = tmp_path / "cm.json"
        cl = tmp_path / "cl.parquet"
        ml = tmp_path / "ml.parquet"
        pp = tmp_path / "pp.json"
        _write_clustering_manifest(cm)
        _write_cluster_labels(cl, n=1)
        _write_ml_dataset(ml, n=1)
        _write_preprocessed_manifest(pp, artifact_path=ml.name)
        config, _ = load_dev06_config()
        report = validate_inputs(
            clustering_manifest_path=cm,
            cluster_labels_path=cl,
            ml_dataset_path=ml,
            preprocessed_manifest_path=pp,
            config=config,
        )
        assert any(not c.passed and "min_samples" in c.check_id for c in report.checks)
