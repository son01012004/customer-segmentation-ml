"""End-to-end pipeline tests for DEV-06 (Phase 2H)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.prototype.segmentation.config_loader import (
    load_dev06_config,
)
from customer_segmentation.prototype.segmentation.pipeline import (
    LIFECYCLE_CACHED,
    LIFECYCLE_SUCCESS,
    SegmentationPipelineResult,
    compute_dataset_stats,
    run_segmentation_pipeline,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_storage(tmp_path: Path) -> dict:
    """Set up a synthetic storage root with a clustering run.

    Returns a dict with keys: storage_root, dataset_id, preprocessed_id,
    clustering_id, paths to manifest, cluster_labels, ml_dataset,
    preprocessed_manifest.
    """
    storage_root = tmp_path / "data"
    dataset_id = "ds_abc"
    preprocessed_id = "pp_xyz"
    clustering_id = "cl_" + "a" * 24

    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); ``dataset_id`` is
    # appended directly (no extra ``"datasets"`` literal). Post-A-1:
    # DEV-03 writes artefacts FLAT under
    # ``<storage_root>/<dataset_id>/preprocessed/`` — the manifest,
    # ML dataset, and log live here with no ``<preprocessed_id>``
    # subdirectory. DEV-04..08 then creates the
    # ``<preprocessed_id>/clustering/<clustering_id>/...`` subtree
    # alongside the flat artefacts. See the regression test in
    # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    pp_dir = storage_root / dataset_id / "preprocessed"
    pp_dir.mkdir(parents=True, exist_ok=True)
    pp_id_dir = pp_dir / preprocessed_id
    cl_dir = pp_id_dir / "clustering" / clustering_id
    cl_dir.mkdir(parents=True, exist_ok=True)

    # Synthetic ML dataset.
    rng = np.random.default_rng(42)
    n = 100
    df_ml = pd.DataFrame(
        {
            "CustomerID": np.arange(1, n + 1),
            "a": rng.standard_normal(n),
            "b": rng.standard_normal(n),
            "c": rng.standard_normal(n),
            "cat": rng.choice(["X", "Y", "Z"], size=n),
        }
    )
    ml_path = pp_dir / "ml_dataset_test.parquet"
    df_ml.to_parquet(ml_path)

    # Preprocessed manifest.
    pp_manifest = {
        "schema_version": "1.0.0",
        "config_hash": "f" * 64,
        "ml_dataset_block": {"artifact_path": "ml_dataset_test.parquet"},
    }
    pp_manifest_path = pp_dir / "preprocessed_manifest.json"
    pp_manifest_path.write_text(json.dumps(pp_manifest), encoding="utf-8")

    # Cluster labels.
    labels = np.array([0] * 25 + [1] * 25 + [2] * 25 + [3] * 25, dtype=np.int64)
    df_cl = pd.DataFrame(
        {
            "CustomerID": np.arange(1, n + 1),
            "ClusterLabel": labels,
            "IsNoise": [False] * n,
        }
    )
    cl_labels_path = cl_dir / "cluster_labels_test.parquet"
    df_cl.to_parquet(cl_labels_path)

    # Clustering manifest.
    cm_data = {
        "schema_version": "1.0.0",
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "algorithm": "kmeans",
        "algorithm_version": "sklearn_1.5",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "b" * 64,
        "feature_set": ["a", "b", "c"],
        "n_samples": n,
        "n_clusters": 4,
        "cluster_labels_path": "cluster_labels_test.parquet",
    }
    cm_path = cl_dir / "clustering_manifest.json"
    cm_path.write_text(json.dumps(cm_data), encoding="utf-8")

    return {
        "storage_root": storage_root,
        "dataset_id": dataset_id,
        "preprocessed_id": preprocessed_id,
        "clustering_id": clustering_id,
        "pp_manifest_path": pp_manifest_path,
        "ml_path": ml_path,
        "cl_dir": cl_dir,
        "cm_path": cm_path,
    }


def _patch_storage_root(monkeypatch, storage_root: Path) -> None:
    """Patch resolve_storage_root to return our test storage_root.

    The pipeline module imports ``resolve_storage_root`` directly (so
    it has its own reference in the pipeline's namespace). We patch
    BOTH the source (storage module) and the destination (pipeline
    module) so the call inside pipeline sees our patched value.
    """
    from customer_segmentation.prototype.segmentation import pipeline as pl_mod
    from customer_segmentation.prototype.segmentation import storage as st_mod

    monkeypatch.setattr(st_mod, "resolve_storage_root", lambda _=None: storage_root)
    monkeypatch.setattr(pl_mod, "resolve_storage_root", lambda _=None: storage_root)


# ---------------------------------------------------------------------------
# compute_dataset_stats
# ---------------------------------------------------------------------------


class TestComputeDatasetStats:
    def test_numeric_features_only(self) -> None:
        df = pd.DataFrame(
            {
                "a": [1.0, 2.0, 3.0, 4.0],
                "b": [10.0, 20.0, 30.0, 40.0],
                "cat": ["x", "y", "x", "y"],
            }
        )
        stats = compute_dataset_stats(df, ["a", "b", "cat"])
        assert "a" in stats
        assert "b" in stats
        assert "cat" not in stats
        assert "mean" in stats["a"]
        assert "median" in stats["a"]
        assert "std" in stats["a"]

    def test_empty_feature(self) -> None:
        df = pd.DataFrame({"a": [1.0, 2.0]})
        stats = compute_dataset_stats(df, ["nonexistent"])
        assert stats == {}


# ---------------------------------------------------------------------------
# run_segmentation_pipeline
# ---------------------------------------------------------------------------


class TestRunSegmentationPipeline:
    def test_end_to_end_kmeans(self, tmp_path: Path, monkeypatch) -> None:
        ctx = _setup_storage(tmp_path)
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        # Use the existing config (default).
        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        assert isinstance(result, SegmentationPipelineResult)
        assert result.lifecycle == LIFECYCLE_SUCCESS
        assert result.manifest_path.exists()
        # Segmentation output dir exists.
        seg_dir = ctx["cl_dir"] / "segmentation" / result.segmentation_id
        assert seg_dir.exists()
        # Required output files exist.
        assert (seg_dir / "segmentation_manifest.json").exists()
        assert (seg_dir / "segment_sizes.csv").exists()
        assert (seg_dir / "segment_sizes_long.csv").exists()
        assert (seg_dir / "segment_profiles.csv").exists()
        assert (seg_dir / "segment_profiles.json").exists()
        assert (seg_dir / "segment_characteristics.json").exists()

    def test_cached_rerun(self, tmp_path: Path, monkeypatch) -> None:
        ctx = _setup_storage(tmp_path)
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        config, _ = load_dev06_config()
        result1 = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        result2 = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        assert result1.lifecycle == LIFECYCLE_SUCCESS
        assert result2.lifecycle == LIFECYCLE_CACHED
        assert result1.segmentation_id == result2.segmentation_id

    def test_force_rerun(self, tmp_path: Path, monkeypatch) -> None:
        ctx = _setup_storage(tmp_path)
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        config, _ = load_dev06_config()
        result1 = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        result2 = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
            force_rerun=True,
        )
        assert result1.lifecycle == LIFECYCLE_SUCCESS
        assert result2.lifecycle == LIFECYCLE_SUCCESS
        assert result1.segmentation_id == result2.segmentation_id

    def test_missing_clustering_manifest_fails(self, tmp_path: Path, monkeypatch) -> None:
        from customer_segmentation.prototype.segmentation.pipeline import (
            Dev06PipelineError,
        )

        ctx = _setup_storage(tmp_path)
        # Remove the clustering manifest.
        ctx["cm_path"].unlink()
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        config, _ = load_dev06_config()
        with pytest.raises(Dev06PipelineError):
            run_segmentation_pipeline(
                dataset_id=ctx["dataset_id"],
                preprocessed_id=ctx["preprocessed_id"],
                clustering_id=ctx["clustering_id"],
                config=config,
            )

    def test_dbscan_end_to_end(self, tmp_path: Path, monkeypatch) -> None:
        ctx = _setup_storage(tmp_path)
        # Modify clustering manifest to be DBSCAN with noise.
        cm = json.loads(ctx["cm_path"].read_text(encoding="utf-8"))
        cm["algorithm"] = "dbscan"
        cm["algorithm_family"] = "density_based"
        # Add some noise labels.
        df_cl = pd.read_parquet(ctx["cl_dir"] / "cluster_labels_test.parquet")
        # Re-write with 10 noise rows.
        df_cl.iloc[:10, df_cl.columns.get_loc("ClusterLabel")] = -1
        df_cl.iloc[:10, df_cl.columns.get_loc("IsNoise")] = True
        df_cl.to_parquet(ctx["cl_dir"] / "cluster_labels_test.parquet")
        ctx["cm_path"].write_text(json.dumps(cm), encoding="utf-8")
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        assert result.lifecycle == LIFECYCLE_SUCCESS
        # noise_count should be 10.
        assert result.manifest.noise_count == 10
        # noise_ratio = 10 / 100 = 0.1.
        assert result.manifest.noise_ratio == pytest.approx(0.1)

    def test_storage_root_failure(self, tmp_path: Path, monkeypatch) -> None:
        from customer_segmentation.prototype.segmentation.pipeline import (
            Dev06PipelineError,
        )

        # Point storage_root to a path that doesn't have the clustering
        # directory.
        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        from customer_segmentation.prototype.segmentation import pipeline as pl_mod
        from customer_segmentation.prototype.segmentation import storage as st_mod

        monkeypatch.setattr(st_mod, "resolve_storage_root", lambda _=None: empty_root)
        monkeykey = monkeypatch  # noqa: F841 (alias for readability)
        monkeypatch.setattr(pl_mod, "resolve_storage_root", lambda _=None: empty_root)
        config, _ = load_dev06_config()
        with pytest.raises(Dev06PipelineError):
            run_segmentation_pipeline(
                dataset_id="ds_xxx",
                preprocessed_id="pp_xxx",
                clustering_id="cl_" + "a" * 24,
                config=config,
            )

    # -----------------------------------------------------------------
    # Non-KMeans / non-DBSCAN algorithm families (P2-2)
    # -----------------------------------------------------------------

    def _switch_to_algorithm_family(
        self,
        ctx: dict,
        *,
        algorithm: str,
        algorithm_family: str,
    ) -> None:
        """Re-write the clustering manifest + cluster_labels for a new
        algorithm family. Re-uses the same ml_dataset.
        """
        cm = json.loads(ctx["cm_path"].read_text(encoding="utf-8"))
        cm["algorithm"] = algorithm
        cm["algorithm_family"] = algorithm_family
        # Some families do not have noise; clear noise_policy
        # accordingly (default in the manifest is "n/a" for non-density).
        ctx["cm_path"].write_text(json.dumps(cm), encoding="utf-8")

    def test_end_to_end_agglomerative(self, tmp_path: Path, monkeypatch) -> None:
        """Agglomerative clustering → algorithm_family='hard' (same as K-Means)."""
        ctx = _setup_storage(tmp_path)
        self._switch_to_algorithm_family(ctx, algorithm="agglomerative", algorithm_family="hard")
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        assert result.lifecycle == LIFECYCLE_SUCCESS
        assert result.manifest.algorithm == "agglomerative"
        assert result.manifest.algorithm_family == "hard"
        # Non-density algorithm → noise fields MUST be None.
        assert result.manifest.noise_count is None
        assert result.manifest.noise_ratio is None
        assert result.manifest.noise_policy_used == "n/a"

    def test_end_to_end_gmm(self, tmp_path: Path, monkeypatch) -> None:
        """Gaussian Mixture → algorithm_family='model_based'."""
        ctx = _setup_storage(tmp_path)
        self._switch_to_algorithm_family(ctx, algorithm="gmm", algorithm_family="model_based")
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        assert result.lifecycle == LIFECYCLE_SUCCESS
        assert result.manifest.algorithm == "gmm"
        assert result.manifest.algorithm_family == "model_based"
        assert result.manifest.noise_count is None
        assert result.manifest.noise_ratio is None
        assert result.manifest.noise_policy_used == "n/a"

    def test_end_to_end_fuzzy_cmeans(self, tmp_path: Path, monkeypatch) -> None:
        """Fuzzy C-Means → algorithm_family='fuzzy'."""
        ctx = _setup_storage(tmp_path)
        self._switch_to_algorithm_family(ctx, algorithm="fuzzy_cmeans", algorithm_family="fuzzy")
        _patch_storage_root(monkeypatch, ctx["storage_root"])
        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        assert result.lifecycle == LIFECYCLE_SUCCESS
        assert result.manifest.algorithm == "fuzzy_cmeans"
        assert result.manifest.algorithm_family == "fuzzy"
        assert result.manifest.noise_count is None
        assert result.manifest.noise_ratio is None
        assert result.manifest.noise_policy_used == "n/a"
