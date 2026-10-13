"""Tests for the post-preprocessing warning contract (P1-2 fix).

Per plan §14.2.4 / R-DEV-06-23: the warning about post-preprocessing
values MUST be in:

- ``segmentation_manifest.json`` ``preprocessing_warning`` field
- the first-line of every CSV output file
- not depend on the Python caller catching ``UserWarning``

These tests read the artifacts written by the end-to-end pipeline and
assert the warning is present on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from customer_segmentation.prototype.segmentation.manifest import (
    POST_PREPROCESSING_WARNING,
)
from customer_segmentation.prototype.segmentation.pipeline import (
    POST_PREPROCESSING_WARNING as PIPELINE_POST_PREPROCESSING_WARNING,
)

# ---------------------------------------------------------------------------
# Manifest contract
# ---------------------------------------------------------------------------


def test_manifest_dataclass_has_preprocessing_warning_field() -> None:
    """SegmentationManifest exposes preprocessing_warning field."""
    from dataclasses import fields

    from customer_segmentation.prototype.segmentation.manifest import (
        SegmentationManifest,
    )

    names = {f.name for f in fields(SegmentationManifest)}
    assert "preprocessing_warning" in names
    assert "preprocessing_applied" in names


def test_manifest_warning_text_matches_plan_14_2_4() -> None:
    """The warning text matches plan §14.2.4 verbatim."""
    assert POST_PREPROCESSING_WARNING.startswith("Feature profile uses scaled/transformed values")
    assert "not directly interpretable" in POST_PREPROCESSING_WARNING
    assert "per DEV-03 preprocessing" in POST_PREPROCESSING_WARNING
    # Same constant exposed by both modules.
    assert POST_PREPROCESSING_WARNING == PIPELINE_POST_PREPROCESSING_WARNING


def test_build_segmentation_manifest_accepts_preprocessing_warning() -> None:
    """build_segmentation_manifest stores the warning in the dataclass."""
    from customer_segmentation.prototype.segmentation.manifest import (
        EnvironmentBlock,
        SegmentationValidationReport,
        SegmentSize,
        build_segmentation_manifest,
    )

    m = build_segmentation_manifest(
        segmentation_id="seg_" + "0" * 24,
        clustering_id="cl_" + "0" * 24,
        preprocessed_id="pp_x",
        dataset_id="ds_x",
        evaluation_id=None,
        algorithm="kmeans",
        algorithm_version="sklearn_1.5",
        algorithm_family="hard",
        ml_dataset_sha256="a" * 64,
        feature_set_sha256="b" * 64,
        preprocessing_config_sha256="c" * 64,
        feature_set=["a", "b"],
        n_samples_input=10,
        n_samples_used_for_compute=10,
        n_clusters_input=2,
        n_segments=2,
        noise_count=None,
        noise_ratio=None,
        noise_policy_used="n/a",
        segment_sizes=[
            SegmentSize(0, 5, 50.0, "n_samples_input", False),
            SegmentSize(1, 5, 50.0, "n_samples_input", False),
        ],
        profiles=[],
        characteristics=[],
        config_sha256="d" * 64,
        environment=EnvironmentBlock(
            python="3.11",
            platform="Linux",
            release="7.0",
            machine="x86_64",
            key_libraries={},
        ),
        log_file="x.log",
        validation_report=SegmentationValidationReport(all_passed=True),
        readonly_paths=[],
        input_clustering_manifest="cm.json",
        input_cluster_labels="cl.parquet",
        input_ml_dataset="ml.parquet",
        input_evaluation_manifest=None,
        preprocessing_applied={"transformation": "log", "scaling": "standard"},
        preprocessing_warning=POST_PREPROCESSING_WARNING,
    )
    assert m.preprocessing_warning == POST_PREPROCESSING_WARNING
    assert m.preprocessing_applied == {"transformation": "log", "scaling": "standard"}


# ---------------------------------------------------------------------------
# End-to-end: warning persists to disk artifacts
# ---------------------------------------------------------------------------


class TestEndToEndPreprocessingWarningOnDisk:
    """Run the full pipeline and assert the warning is written to every artifact."""

    def _setup_storage(self, tmp_path: Path) -> dict:
        """Build synthetic DEV-04 clustering tree (mirrors test_dev06_pipeline)."""
        import numpy as np
        import pandas as pd

        storage_root = tmp_path / "data"
        dataset_id = "ds_ppwarn"
        preprocessed_id = "pp_ppwarn"
        clustering_id = "cl_" + "a" * 24

        # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
        # (per ``configs/dev02_dataset_management.yaml``); ``dataset_id`` is
        # appended directly (no extra ``"datasets"`` literal). Post-A-1:
        # DEV-03 writes artefacts FLAT under
        # ``<storage_root>/<dataset_id>/preprocessed/`` (no
        # ``<preprocessed_id>`` subdirectory); DEV-04..08 creates the
        # ``<preprocessed_id>/clustering/<clustering_id>/...`` subtree
        # alongside. See the regression test in
        # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
        pp_dir = storage_root / dataset_id / "preprocessed"
        pp_id_dir = pp_dir / preprocessed_id
        cl_dir = pp_id_dir / "clustering" / clustering_id
        pp_dir.mkdir(parents=True, exist_ok=True)
        pp_id_dir.mkdir(parents=True, exist_ok=True)
        cl_dir.mkdir(parents=True, exist_ok=True)

        rng = np.random.default_rng(42)
        n = 100
        df_ml = pd.DataFrame(
            {
                "CustomerID": np.arange(1, n + 1),
                "a": rng.standard_normal(n),
                "b": rng.standard_normal(n),
                "c": rng.standard_normal(n),
            }
        )
        ml_path = pp_dir / "ml_dataset_ppwarn.parquet"
        df_ml.to_parquet(ml_path)

        # Preprocessed manifest WITH preprocessing_block populated.
        pp_manifest = {
            "schema_version": "1.0.0",
            "config_hash": "f" * 64,
            "ml_dataset_block": {"artifact_path": "ml_dataset_ppwarn.parquet"},
            "preprocessing_block": {
                "transformation": "log",
                "scaling": "standard",
                "enabled": True,
            },
        }
        pp_manifest_path = pp_dir / "preprocessed_manifest.json"
        pp_manifest_path.write_text(json.dumps(pp_manifest), encoding="utf-8")

        labels = np.array([0] * 25 + [1] * 25 + [2] * 25 + [3] * 25, dtype=np.int64)
        df_cl = pd.DataFrame(
            {
                "CustomerID": np.arange(1, n + 1),
                "ClusterLabel": labels,
                "IsNoise": [False] * n,
            }
        )
        cl_labels_path = cl_dir / "cluster_labels_ppwarn.parquet"
        df_cl.to_parquet(cl_labels_path)

        cm = {
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
            "cluster_labels_path": "cluster_labels_ppwarn.parquet",
        }
        cm_path = cl_dir / "clustering_manifest.json"
        cm_path.write_text(json.dumps(cm), encoding="utf-8")

        return {
            "storage_root": storage_root,
            "dataset_id": dataset_id,
            "preprocessed_id": preprocessed_id,
            "clustering_id": clustering_id,
            "cl_dir": cl_dir,
        }

    def _patch_storage_root(self, monkeypatch, storage_root: Path) -> None:
        from customer_segmentation.prototype.segmentation import pipeline as pl_mod
        from customer_segmentation.prototype.segmentation import storage as st_mod

        monkeypatch.setattr(st_mod, "resolve_storage_root", lambda _=None: storage_root)
        monkeypatch.setattr(pl_mod, "resolve_storage_root", lambda _=None: storage_root)

    def test_warning_in_segmentation_manifest_json(self, tmp_path, monkeypatch) -> None:
        ctx = self._setup_storage(tmp_path)
        self._patch_storage_root(monkeypatch, ctx["storage_root"])
        from customer_segmentation.prototype.segmentation.config_loader import (
            load_dev06_config,
        )
        from customer_segmentation.prototype.segmentation.pipeline import (
            run_segmentation_pipeline,
        )

        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        # Read the persisted manifest from disk (not the in-memory one).
        payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        assert (
            "preprocessing_warning" in payload
        ), "segmentation_manifest.json is missing 'preprocessing_warning' field"
        assert payload["preprocessing_warning"] == POST_PREPROCESSING_WARNING
        # Also: preprocessing_applied records transformation/scaling.
        assert "preprocessing_applied" in payload
        assert payload["preprocessing_applied"]["transformation"] == "log"
        assert payload["preprocessing_applied"]["scaling"] == "standard"

    def test_warning_in_segment_sizes_long_csv(self, tmp_path, monkeypatch) -> None:
        ctx = self._setup_storage(tmp_path)
        self._patch_storage_root(monkeypatch, ctx["storage_root"])
        from customer_segmentation.prototype.segmentation.config_loader import (
            load_dev06_config,
        )
        from customer_segmentation.prototype.segmentation.pipeline import (
            run_segmentation_pipeline,
        )

        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        seg_dir = result.manifest_path.parent
        sizes_long = (seg_dir / "segment_sizes_long.csv").read_text(encoding="utf-8")
        # First non-empty line carries the comment.
        lines = sizes_long.splitlines()
        assert lines, "CSV file is empty"
        assert lines[0].startswith(
            "# preprocessing_warning:"
        ), f"first line is not the warning comment: {lines[0]!r}"
        assert POST_PREPROCESSING_WARNING in lines[0]

    def test_warning_in_segment_sizes_csv(self, tmp_path, monkeypatch) -> None:
        ctx = self._setup_storage(tmp_path)
        self._patch_storage_root(monkeypatch, ctx["storage_root"])
        from customer_segmentation.prototype.segmentation.config_loader import (
            load_dev06_config,
        )
        from customer_segmentation.prototype.segmentation.pipeline import (
            run_segmentation_pipeline,
        )

        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        seg_dir = result.manifest_path.parent
        sizes_csv = (seg_dir / "segment_sizes.csv").read_text(encoding="utf-8")
        lines = sizes_csv.splitlines()
        assert lines[0].startswith("# preprocessing_warning:")
        assert POST_PREPROCESSING_WARNING in lines[0]

    def test_warning_in_segment_profiles_csv(self, tmp_path, monkeypatch) -> None:
        ctx = self._setup_storage(tmp_path)
        self._patch_storage_root(monkeypatch, ctx["storage_root"])
        from customer_segmentation.prototype.segmentation.config_loader import (
            load_dev06_config,
        )
        from customer_segmentation.prototype.segmentation.pipeline import (
            run_segmentation_pipeline,
        )

        config, _ = load_dev06_config()
        result = run_segmentation_pipeline(
            dataset_id=ctx["dataset_id"],
            preprocessed_id=ctx["preprocessed_id"],
            clustering_id=ctx["clustering_id"],
            config=config,
        )
        seg_dir = result.manifest_path.parent
        profiles_csv = (seg_dir / "segment_profiles.csv").read_text(encoding="utf-8")
        lines = profiles_csv.splitlines()
        assert lines[0].startswith("# preprocessing_warning:")
        assert POST_PREPROCESSING_WARNING in lines[0]


# ---------------------------------------------------------------------------
# Backward compat: old manifests without preprocessing_warning still load
# ---------------------------------------------------------------------------


def test_read_manifest_without_preprocessing_warning_default_empty(tmp_path: Path) -> None:
    """A pre-remediation manifest (no preprocessing_warning field) loads
    with empty string default; no crash."""
    from customer_segmentation.prototype.segmentation.manifest import (
        read_segmentation_manifest,
    )

    # Build a manifest that pre-dates the new fields. We have to write
    # the JSON manually without the new keys.
    manifest_path = tmp_path / "old_manifest.json"
    payload = {
        "schema_version": "1.0.0",
        "segmentation_id": "seg_" + "0" * 24,
        "scope": "PROFILED_PROTOTYPE",
        "clustering_id": "cl_" + "0" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "evaluation_id": None,
        "algorithm": "kmeans",
        "algorithm_version": "sklearn_1.5",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "feature_set": ["a"],
        "feature_count": 1,
        "n_samples_input": 10,
        "n_samples_used_for_compute": 10,
        "n_clusters_input": 2,
        "n_segments": 2,
        "noise_count": None,
        "noise_ratio": None,
        "noise_policy_used": "n/a",
        "segment_sizes": [
            {
                "segment_id": 0,
                "count": 5,
                "percentage": 50.0,
                "percentage_base": "n_samples_input",
                "is_noise": False,
            },
            {
                "segment_id": 1,
                "count": 5,
                "percentage": 50.0,
                "percentage_base": "n_samples_input",
                "is_noise": False,
            },
        ],
        "profiles": [],
        "characteristics": [],
        "environment": {
            "python": "3.11",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {},
        },
        "config_sha256": "d" * 64,
        "created_utc": "2026-10-10T00:00:00Z",
        "last_seen_utc": "2026-10-10T00:00:00Z",
        "log_file": "x.log",
        "validation_report": {"all_passed": True, "checks": []},
        "research_safety": {
            "automatically_promoted_to_research": False,
            "scope": "PROFILED_PROTOTYPE",
            "appeared_in_research_evidence": False,
            "read_only_paths_unmodified": [],
        },
        "input_clustering_manifest": "cm.json",
        "input_cluster_labels": "cl.parquet",
        "input_ml_dataset": "ml.parquet",
        "input_evaluation_manifest": None,
        # NO preprocessing_warning / preprocessing_applied
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    # Read back — must not crash.
    m = read_segmentation_manifest(manifest_path)
    assert m.preprocessing_warning == ""
    assert m.preprocessing_applied == {}
