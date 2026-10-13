"""Integration tests for the DEV-04 clustering pipeline.

These tests use a tmpdir as the storage root so the real on-disk data
is never touched. A synthetic DEV-03 ML Dataset is written to simulate
a preprocessed artefact.

The shared fixtures (``dev02_config``, ``synthetic_ml_dataset``,
``synthetic_dev03_artefact``) live in ``tests/conftest.py`` so other
DEV-04 test modules can reuse them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class TestPipelineImports:
    def test_pipeline_imports(self) -> None:
        from customer_segmentation.prototype.clustering import (
            ClusteringPipelineResult,
            run_clustering_pipeline,
        )

        assert callable(run_clustering_pipeline)
        assert ClusteringPipelineResult is not None


class TestPipelineRunKMeans:
    def test_kmeans_run_success(
        self,
        synthetic_dev03_artefact,
        monkeypatch,
    ) -> None:
        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        ml_path, manifest_path, storage_root = synthetic_dev03_artefact
        dataset_id = "ds_dev04test01"
        preprocessed_id = "pp_dev04test01"

        # Patch storage_root resolution to use our tmp storage.
        def _mock_resolve(_=None):
            return storage_root

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            _mock_resolve,
        )

        result = run_clustering_pipeline(
            dataset_id=dataset_id,
            preprocessed_id=preprocessed_id,
            algorithm="kmeans",
            hyperparameters={"n_clusters": 3},
            seed=42,
        )

        assert result.lifecycle in ("SUCCESS", "CACHED")
        assert result.clustering_id.startswith("cl_")
        assert len(result.clustering_id) == 27  # cl_ + 24 hex
        assert result.algorithm == "kmeans"
        assert result.preprocessed_id == preprocessed_id
        assert result.manifest_path.exists()
        assert result.log_path.exists()

    def test_deterministic_algorithm_no_seed(
        self,
        synthetic_dev03_artefact,
        monkeypatch,
    ) -> None:
        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        ml_path, manifest_path, storage_root = synthetic_dev03_artefact
        dataset_id = "ds_dev04test01"
        preprocessed_id = "pp_dev04test01"

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            lambda _=None: storage_root,
        )

        result = run_clustering_pipeline(
            dataset_id=dataset_id,
            preprocessed_id=preprocessed_id,
            algorithm="dbscan",
            hyperparameters={"eps": 1.0, "min_samples": 3},
        )

        assert result.lifecycle in ("SUCCESS", "CACHED")
        assert result.algorithm == "dbscan"
        # Deterministic: seed is None in manifest.
        assert result.manifest is not None

    def test_unknown_algorithm_raises(
        self,
        synthetic_dev03_artefact,
        monkeypatch,
    ) -> None:
        from customer_segmentation.prototype.clustering import (
            Dev04ConfigError,
            run_clustering_pipeline,
        )

        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            lambda _=None: storage_root,
        )

        with pytest.raises(Dev04ConfigError):
            run_clustering_pipeline(
                dataset_id="ds_dev04test01",
                preprocessed_id="pp_dev04test01",
                algorithm="unknown_algo",
            )


class TestPipelineIdempotency:
    def test_second_run_is_cached(
        self,
        synthetic_dev03_artefact,
        monkeypatch,
    ) -> None:
        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            lambda _=None: storage_root,
        )

        # First run.
        result1 = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
            seed=42,
        )

        # Second run (same config) → CACHED.
        result2 = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
            seed=42,
        )

        assert result1.lifecycle == "SUCCESS"
        assert result2.lifecycle == "CACHED"
        assert result1.clustering_id == result2.clustering_id

    def test_force_rerun_overrides_cache(
        self,
        synthetic_dev03_artefact,
        monkeypatch,
    ) -> None:
        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            lambda _=None: storage_root,
        )

        result1 = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
            seed=42,
        )

        result2 = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
            seed=42,
            force_rerun=True,
        )

        # With force_rerun=True, lifecycle is SUCCESS (not CACHED).
        assert result1.lifecycle == "SUCCESS"
        assert result2.lifecycle == "SUCCESS"
        assert result1.clustering_id == result2.clustering_id


class TestPipelineResultSummary:
    def test_as_summary_is_json_serialisable(
        self,
        synthetic_dev03_artefact,
        monkeypatch,
    ) -> None:
        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            lambda _=None: storage_root,
        )

        result = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 3},
            seed=42,
        )

        summary = result.as_summary()
        assert isinstance(summary, dict)
        assert summary["clustering_id"] == result.clustering_id
        assert summary["algorithm"] == "kmeans"
        assert summary["lifecycle"] in ("SUCCESS", "CACHED")

        # Verify JSON serialisable.
        json.dumps(summary)


# ---------------------------------------------------------------------------
# Regression: A-1 path-doubling bug — full pipeline round-trip on
# canonical on-disk layout.
# ---------------------------------------------------------------------------
# This test exercises the actual ``run_clustering_pipeline`` against a
# synthetic DEV-03 artefact laid out at the canonical on-disk path
# (i.e. ``<storage_root>/<dataset_id>/preprocessed/<pp_id>/`` — the
# same layout that DEV-02 + DEV-03 produce on disk in production).
#
# Pre-A-1 the pipeline failed with ``FileNotFoundError`` because the
# production code looked for the ML Dataset at
# ``<storage_root>/datasets/<dataset_id>/preprocessed/<pp_id>/...``
# (extra ``"datasets"`` segment). See
# ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
# ---------------------------------------------------------------------------


class TestClusteringPipelineOnCanonicalLayout:
    """A-1 regression: full clustering pipeline against canonical on-disk layout."""

    def test_kmeans_succeeds_on_canonical_layout(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import pandas as pd

        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )
        # ``storage_root`` is ``tmp_path / "datasets"`` — exactly matches
        # ``configs/dev02_dataset_management.yaml::dataset_management.storage_root``.
        storage_root = tmp_path / "datasets"
        storage_root.mkdir(parents=True, exist_ok=True)

        dataset_id = "ds_a1reg01"
        preprocessed_id = "pp_a1reg01"

        # Canonical on-disk layout (post-A-1): DEV-03 writes artefacts FLAT
        # under ``<storage_root>/<dataset_id>/preprocessed/`` (no
        # ``<preprocessed_id>`` subdirectory). The ``preprocessed_id`` is
        # embedded in the filename (e.g.
        # ``ml_dataset_<ts>_<pp_id>.parquet``,
        # ``pp_<pp_id>.log``, ``preprocessed_manifest.json``).
        pp_dir = storage_root / dataset_id / "preprocessed"
        pp_dir.mkdir(parents=True, exist_ok=True)

        # Write a tiny synthetic ML Dataset.
        import numpy as np

        rng = np.random.default_rng(42)
        n = 20
        df_ml = pd.DataFrame(
            {
                "CustomerID": np.arange(1, n + 1),
                "Recency": rng.integers(1, 30, n),
                "Frequency": rng.integers(1, 100, n),
                "Monetary": rng.uniform(10, 1000, n).round(2),
            }
        )
        ml_dataset_name = f"ml_dataset_a1_{preprocessed_id}.parquet"
        ml_dataset_path = pp_dir / ml_dataset_name
        df_ml.to_parquet(ml_dataset_path, index=False)

        # Write the DEV-03 manifest.
        import hashlib

        ml_dataset_sha = hashlib.sha256(ml_dataset_path.read_bytes()).hexdigest()
        manifest = {
            "schema_version": "1.0.0",
            "preprocessed_id": preprocessed_id,
            "preprocessed_scope": "PREPROCESSED_PROTOTYPE",
            "source_dataset_id": dataset_id,
            "source_dataset_sha256": "b" * 64,
            "config_hash": "c" * 64,
            "preprocessing_block": {
                "enabled": True,
                "input_row_count": 1000,
                "input_column_count": 8,
                "output_row_count": 1000,
                "rows_removed_total": 0,
                "rows_retained": 1000,
                "cancellation_prefix": "C",
                "flag_cancellations": True,
                "flag_returns": True,
                "outlier_action": "none",
                "outlier_method": "iqr",
                "transformation": "none",
                "scaling": "none",
                "stage_outcomes": {"A": "PASS", "B": "PASS", "C": "PASS"},
                "rules": [],
                "config_snapshot": {},
                "status": "WORKING_ASSUMPTION",
            },
            "feature_generation_block": {
                "reference_date": "2010-12-05",
                "customer_count": n,
                "candidate_feature_count": 3,
                "outcome": "PASS",
                "validation_passed": True,
                "f1_input_row_count": 1000,
                "f2_base_row_count": n,
                "errors": [],
                "warnings": [],
                "status": "WORKING_ASSUMPTION",
            },
            "ml_dataset_block": {
                "row_count": n,
                "column_count": 4,
                "columns": ["CustomerID", "Recency", "Frequency", "Monetary"],
                "sha256": ml_dataset_sha,
                "file_size_bytes": int(ml_dataset_path.stat().st_size),
                "artifact_path": ml_dataset_name,
                "status": "WORKING_ASSUMPTION",
            },
            "environment": {
                "python": "3.14",
                "platform": "Linux",
                "release": "7.0",
                "machine": "x86_64",
                "key_libraries": {"pandas": "2.0"},
            },
            "research_safety": {
                "automatically_promoted_to_research": False,
                "scope": "PREPROCESSED_PROTOTYPE",
                "appeared_in_research_evidence": False,
                "read_only_paths_unmodified": [],
            },
            "created_utc": "2026-10-12T00:00:00Z",
            "last_seen_utc": "2026-10-12T00:00:00Z",
            "log_file": f"{preprocessed_id}.log",
            "intermediate_artifact_path": None,
        }
        manifest_path = pp_dir / "preprocessed_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

        # Patch ``resolve_storage_root`` in the DEV-04 pipeline module to
        # return the synthetic storage_root.
        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            lambda _=None: storage_root.resolve(),
        )

        # Run the real (unmocked) clustering pipeline.
        result = run_clustering_pipeline(
            dataset_id=dataset_id,
            preprocessed_id=preprocessed_id,
            algorithm="kmeans",
            hyperparameters={"n_clusters": 3},
            seed=42,
        )

        # Pre-A-1 this raised FileNotFoundError; post-A-1 it succeeds.
        assert result.lifecycle in ("SUCCESS", "CACHED"), (
            f"Expected SUCCESS/CACHED; got lifecycle={result.lifecycle!r}. "
            "If FAILED, the A-1 fix has been undone."
        )
        assert result.clustering_id.startswith("cl_")
        assert result.preprocessed_id == preprocessed_id
        assert result.manifest_path.exists()
        # The clustering run_dir must live inside the canonical preprocessed dir
        # (post-A-1 layout: <storage_root>/<ds_id>/preprocessed/<pp_id>/clustering/<cl_id>/)
        assert result.run_dir.parent.name == "clustering"
        assert result.run_dir.parent.parent.name == preprocessed_id
        assert result.run_dir.parent.parent.parent.name == "preprocessed"
        assert result.run_dir.parent.parent.parent.parent.name == dataset_id
        # No doubled "datasets" segment.
        parts = result.run_dir.resolve().relative_to(storage_root.resolve()).parts
        assert "datasets" not in parts, (
            f"A-1 regression: clustering run_dir={result.run_dir} contains a "
            f"doubled 'datasets' segment relative to storage_root. parts={parts}"
        )
