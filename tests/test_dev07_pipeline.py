"""End-to-end pipeline tests for DEV-07 Phase A.

The DEV-07 pipeline is a 7-stage orchestrator (A → G) that:

- A: load config, resolve storage root
- B: locate DEV-06 ``segmentation_manifest.json``
- C: validate input (manifest shape, research_safety, noise, dedup)
- D: build per-segment recommendation entries (Phase A: REVIEW_REQUIRED)
- E: write ``marketing_manifest.json`` (atomic)
- F: publish (atomic rename)
- G: finalize logging

This module covers:
- Stage B/C/D/E happy + error paths
- Idempotency / cache behaviour
- DBSCAN noise exclusion end-to-end
- ``research_safety`` invariants in the final manifest
- ``marketing_id`` determinism across reruns
- Path / config error handling
- Lifecycle strings
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.marketing.config_loader import (
    DEFAULT_DEV07_CONFIG_PATH,
    Dev07Config,
)
from customer_segmentation.prototype.marketing.exceptions import (
    MarketingInputError,
    MarketingValidationError,
)
from customer_segmentation.prototype.marketing.manifest import (
    MARKETING_MANIFEST_SCHEMA_VERSION,
    read_marketing_manifest,
)
from customer_segmentation.prototype.marketing.pipeline import (
    LIFECYCLE_CACHED,
    LIFECYCLE_FAILED,
    LIFECYCLE_SUCCESS,
    MarketingPipelineResult,
    compute_environment_block,
    run_marketing_pipeline,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_synthetic_storage(
    storage_root: Path,
    *,
    dataset_id: str = "ds_dev07test",
    preprocessed_id: str = "pp_dev07test",
    clustering_id: str | None = None,
    segmentation_id: str | None = None,
    include_noise: bool = False,
) -> dict:
    """Build a synthetic DEV-06 segmentation tree under storage_root.

    Returns a dict of useful paths/ids.
    """
    if clustering_id is None:
        clustering_id = "cl_" + "a" * 24
    if segmentation_id is None:
        segmentation_id = "seg_" + "b" * 24

    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); the dataset id is
    # appended directly (no extra ``"datasets"`` literal). Mirrors the
    # canonical on-disk layout produced by DEV-02..08 — see the
    # regression test in
    # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    seg_dir = (
        storage_root
        / dataset_id
        / "preprocessed"
        / preprocessed_id
        / "clustering"
        / clustering_id
        / "segmentation"
        / segmentation_id
    )
    seg_dir.mkdir(parents=True, exist_ok=True)

    # Build a synthetic DEV-06 segmentation manifest.
    segment_sizes: list[dict] = [
        {"segment_id": 0, "count": 50, "percentage": 0.5, "is_noise": False},
        {"segment_id": 1, "count": 50, "percentage": 0.5, "is_noise": False},
    ]
    if include_noise:
        segment_sizes.append({"segment_id": -1, "count": 20, "percentage": 0.2, "is_noise": True})

    seg_manifest = {
        "schema_version": "1.0.0",
        "segmentation_id": segmentation_id,
        "scope": "PROFILED_PROTOTYPE",
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "algorithm": "dbscan" if include_noise else "kmeans",
        "algorithm_family": "density_based" if include_noise else "hard",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "noise_policy_used": "exclude" if include_noise else "n/a",
        "segment_sizes": segment_sizes,
        "research_safety": {
            "automatically_promoted_to_research": False,
            "scope": "PROFILED_PROTOTYPE",
            "appeared_in_research_evidence": False,
            "read_only_paths_unmodified": [],
        },
        "input_segmentation_manifest": "segmentation_manifest.json",
        "input_cluster_labels": "cluster_labels.parquet",
        "input_ml_dataset": "ml_dataset.parquet",
        "input_evaluation_manifest": None,
    }
    seg_manifest_path = seg_dir / "segmentation_manifest.json"
    seg_manifest_path.write_text(json.dumps(seg_manifest), encoding="utf-8")

    return {
        "storage_root": storage_root,
        "dataset_id": dataset_id,
        "preprocessed_id": preprocessed_id,
        "clustering_id": clustering_id,
        "segmentation_id": segmentation_id,
        "seg_dir": seg_dir,
        "seg_manifest_path": seg_manifest_path,
    }


def _patch_storage_root(monkeypatch, storage_root: Path) -> None:
    """Patch ``resolve_storage_root`` in both the source module and the
    destination module that imports it."""
    from customer_segmentation.prototype.marketing import pipeline as pl_mod
    from customer_segmentation.prototype.marketing import storage as st_mod

    monkeypatch.setattr(st_mod, "resolve_storage_root", lambda _=None: storage_root)
    monkeypatch.setattr(pl_mod, "resolve_storage_root", lambda _=None: storage_root)


def _run_with_storage(
    monkeypatch,
    storage_root: Path,
    *,
    segmentation_id: str,
    manifest_path: Path | None = None,
    config_path: Path | str | None = None,
    force_rerun: bool = False,
) -> MarketingPipelineResult:
    """Run the pipeline with the given storage root patched in."""
    _patch_storage_root(monkeypatch, storage_root)
    return run_marketing_pipeline(
        segmentation_id=segmentation_id if manifest_path is None else None,
        manifest_path=manifest_path,
        config_path=config_path,
        force_rerun=force_rerun,
    )


# ---------------------------------------------------------------------------
# compute_environment_block
# ---------------------------------------------------------------------------


class TestComputeEnvironmentBlock:
    def test_returns_required_keys(self) -> None:
        env = compute_environment_block()
        for key in ("python", "platform", "release", "machine", "key_libraries"):
            assert key in env

    def test_key_libraries_is_dict(self) -> None:
        env = compute_environment_block()
        assert isinstance(env["key_libraries"], dict)

    def test_python_version_nonempty(self) -> None:
        env = compute_environment_block()
        assert env["python"]  # non-empty

    def test_includes_known_libs(self) -> None:
        env = compute_environment_block()
        libs = env["key_libraries"]
        for lib in ("pandas", "numpy", "yaml"):
            assert lib in libs


# ---------------------------------------------------------------------------
# Stage A: argument validation
# ---------------------------------------------------------------------------


class TestStageAArgs:
    def test_no_args_raises(self) -> None:
        with pytest.raises(MarketingInputError, match="must be provided"):
            run_marketing_pipeline()

    def test_both_args_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MarketingInputError, match="mutually exclusive"):
            run_marketing_pipeline(
                segmentation_id="seg_" + "0" * 24,
                manifest_path=tmp_path / "x.json",
            )

    def test_invalid_segmentation_id_format_raises(self) -> None:
        with pytest.raises(MarketingInputError, match="segmentation_id"):
            run_marketing_pipeline(segmentation_id="bad_format")


# ---------------------------------------------------------------------------
# Stage B: lookup
# ---------------------------------------------------------------------------


class TestStageBLookup:
    def test_manifest_not_found(self, tmp_path: Path, monkeypatch) -> None:
        """Empty storage root → raises."""
        empty_root = tmp_path / "empty"
        empty_root.mkdir()
        _patch_storage_root(monkeypatch, empty_root)
        with pytest.raises(MarketingInputError, match="Could not locate"):
            run_marketing_pipeline(segmentation_id="seg_" + "a" * 24)

    def test_explicit_manifest_path(self, tmp_path: Path, monkeypatch) -> None:
        """Explicit --manifest-path bypasses storage_root lookup."""
        # Set up a separate manifest file outside any storage root.
        seg_manifest_path = tmp_path / "my_seg.json"
        seg_manifest_path.write_text(
            json.dumps(_make_segmentation_manifest_data()), encoding="utf-8"
        )

        # Patch resolve_storage_root to point somewhere else; the
        # pipeline should still succeed because we pass manifest_path
        # explicitly.
        other_root = tmp_path / "other"
        other_root.mkdir()
        _patch_storage_root(monkeypatch, other_root)
        result = run_marketing_pipeline(manifest_path=seg_manifest_path)
        assert isinstance(result, MarketingPipelineResult)


def _make_segmentation_manifest_data(
    *,
    segmentation_id: str = "seg_" + "b" * 24,
    clustering_id: str = "cl_" + "c" * 24,
    dataset_id: str = "ds_test",
    preprocessed_id: str = "pp_test",
    include_noise: bool = False,
) -> dict:
    seg_sizes = [
        {"segment_id": 0, "count": 50, "percentage": 0.5, "is_noise": False},
        {"segment_id": 1, "count": 50, "percentage": 0.5, "is_noise": False},
    ]
    if include_noise:
        seg_sizes.append({"segment_id": -1, "count": 20, "percentage": 0.2, "is_noise": True})
    return {
        "schema_version": "1.0.0",
        "segmentation_id": segmentation_id,
        "scope": "PROFILED_PROTOTYPE",
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "algorithm": "dbscan" if include_noise else "kmeans",
        "algorithm_family": "density_based" if include_noise else "hard",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "noise_policy_used": "exclude" if include_noise else "n/a",
        "segment_sizes": seg_sizes,
        "research_safety": {
            "automatically_promoted_to_research": False,
            "scope": "PROFILED_PROTOTYPE",
            "appeared_in_research_evidence": False,
            "read_only_paths_unmodified": [],
        },
        "input_segmentation_manifest": "segmentation_manifest.json",
        "input_cluster_labels": "cluster_labels.parquet",
        "input_ml_dataset": "ml_dataset.parquet",
        "input_evaluation_manifest": None,
    }


# ---------------------------------------------------------------------------
# End-to-end happy path
# ---------------------------------------------------------------------------


class TestRunMarketingPipelineHappyPath:
    def test_end_to_end_kmeans(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root, include_noise=False)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert isinstance(result, MarketingPipelineResult)
        assert result.lifecycle == LIFECYCLE_SUCCESS
        # Manifest path exists.
        assert result.manifest_path.exists()
        # Run dir matches manifest dir.
        assert result.manifest_path.parent == result.run_dir

    def test_end_to_end_dbscan_with_noise(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root, include_noise=True)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.lifecycle == LIFECYCLE_SUCCESS
        # DBSCAN noise is excluded from the recommendation list, but
        # counted in n_segments_noise.
        assert result.manifest.n_segments_noise == 1
        # Only 2 non-noise segments → 2 recommendations.
        assert result.manifest.n_segments_with_recommendation == 2
        assert result.manifest.n_segments_input == 2  # noise excluded

    def test_all_entries_review_required(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.manifest.availability == "REVIEW_REQUIRED"
        for entry in result.manifest.recommendations:
            assert entry.availability == "REVIEW_REQUIRED"

    def test_no_kpi_in_phase_a(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        for entry in result.manifest.recommendations:
            assert entry.kpi is None

    def test_research_safety_block_invariant(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        rs = result.manifest.research_safety
        assert rs.scope == "MARKETING_PROTOTYPE"
        assert rs.automatically_promoted_to_research is False
        assert rs.appeared_in_research_evidence is False

    def test_schema_version_pinned(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.manifest.schema_version == MARKETING_MANIFEST_SCHEMA_VERSION

    def test_mkt_framework_found_false_phase_a(self, tmp_path: Path, monkeypatch) -> None:
        """Phase A: no MKT-01..05 in repo, so mkt_framework_found=False."""
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.manifest.mkt_framework_found is False
        assert result.manifest.source_framework_version is None

    def test_noise_policy_inherited(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root, include_noise=True)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        # DEV-06 manifest carries "exclude"; DEV-07 must inherit.
        assert result.manifest.noise_policy_used == "exclude"


# ---------------------------------------------------------------------------
# Idempotency / cache
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_first_run_success_second_run_cached(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        r1 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        r2 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert r1.lifecycle == LIFECYCLE_SUCCESS
        assert r2.lifecycle == LIFECYCLE_CACHED
        # Same marketing_id (deterministic).
        assert r1.manifest.marketing_id == r2.manifest.marketing_id

    def test_force_rerun_bypasses_cache(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        r1 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        r2 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
            force_rerun=True,
        )
        assert r1.lifecycle == LIFECYCLE_SUCCESS
        assert r2.lifecycle == LIFECYCLE_SUCCESS
        # Same marketing_id (deterministic).
        assert r1.manifest.marketing_id == r2.manifest.marketing_id

    def test_marketing_id_deterministic(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        r1 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        r2 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
            force_rerun=True,
        )
        # Even after re-write, the marketing_id is the same (deterministic).
        assert r1.manifest.marketing_id == r2.manifest.marketing_id

    def test_different_underlying_content_different_marketing_id(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Different DEV-06 file content → different marketing_id."""
        from customer_segmentation.prototype.marketing import pipeline as pl_mod
        from customer_segmentation.prototype.marketing import storage as st_mod

        storage_root_1 = tmp_path / "data1"
        ctx1 = _setup_synthetic_storage(storage_root_1)
        # Inject an extra field into the first manifest (mutate content).
        seg_manifest_path_1 = ctx1["seg_manifest_path"]
        data1 = json.loads(seg_manifest_path_1.read_text())
        data1["extra_marker"] = "alpha"
        seg_manifest_path_1.write_text(json.dumps(data1), encoding="utf-8")

        monkeypatch.setattr(st_mod, "resolve_storage_root", lambda _=None: storage_root_1)
        monkeypatch.setattr(pl_mod, "resolve_storage_root", lambda _=None: storage_root_1)
        r1 = run_marketing_pipeline(segmentation_id=ctx1["segmentation_id"])

        # Second storage root with manifest content differing in the extra field.
        storage_root_2 = tmp_path / "data2"
        ctx2 = _setup_synthetic_storage(storage_root_2)
        seg_manifest_path_2 = ctx2["seg_manifest_path"]
        data2 = json.loads(seg_manifest_path_2.read_text())
        data2["extra_marker"] = "beta"
        seg_manifest_path_2.write_text(json.dumps(data2), encoding="utf-8")

        monkeypatch.setattr(st_mod, "resolve_storage_root", lambda _=None: storage_root_2)
        monkeypatch.setattr(pl_mod, "resolve_storage_root", lambda _=None: storage_root_2)
        r2 = run_marketing_pipeline(segmentation_id=ctx2["segmentation_id"])

        # Different file content → different marketing_id.
        assert r1.manifest.marketing_id != r2.manifest.marketing_id


# ---------------------------------------------------------------------------
# Stage C: validation failures
# ---------------------------------------------------------------------------


class TestStageCValidation:
    def test_missing_segment_sizes_fails(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        # Remove segment_sizes from the manifest.
        data = json.loads(ctx["seg_manifest_path"].read_text())
        del data["segment_sizes"]
        ctx["seg_manifest_path"].write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(MarketingValidationError):
            _run_with_storage(
                monkeypatch,
                storage_root,
                segmentation_id=ctx["segmentation_id"],
            )

    def test_promoted_to_research_fails(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        data = json.loads(ctx["seg_manifest_path"].read_text())
        data["research_safety"]["automatically_promoted_to_research"] = True
        ctx["seg_manifest_path"].write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(MarketingValidationError):
            _run_with_storage(
                monkeypatch,
                storage_root,
                segmentation_id=ctx["segmentation_id"],
            )

    def test_duplicate_segment_id_fails(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        data = json.loads(ctx["seg_manifest_path"].read_text())
        data["segment_sizes"] = [
            {"segment_id": 0, "count": 50, "percentage": 0.5, "is_noise": False},
            {"segment_id": 0, "count": 50, "percentage": 0.5, "is_noise": False},
        ]
        ctx["seg_manifest_path"].write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(MarketingValidationError):
            _run_with_storage(
                monkeypatch,
                storage_root,
                segmentation_id=ctx["segmentation_id"],
            )


# ---------------------------------------------------------------------------
# I/O invariants
# ---------------------------------------------------------------------------


class TestManifestIO:
    def test_manifest_is_valid_json(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        # Re-parse.
        loaded = read_marketing_manifest(result.manifest_path)
        assert loaded.marketing_id == result.manifest.marketing_id

    def test_atomic_write_no_tmp_leftover(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        # No .tmp files left over in the run dir.
        leftovers = list(result.run_dir.glob("*.tmp"))
        assert leftovers == []

    def test_run_dir_under_segmentation_dir(self, tmp_path: Path, monkeypatch) -> None:
        """``marketing/<marketing_id>/`` must live under the segmentation dir."""
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        # The run_dir is at: <seg_dir>/marketing/<marketing_id>/
        # So run_dir.parent is the "marketing" base dir.
        assert result.run_dir.parent.name == "marketing"
        # And the marketing base dir is a direct child of the seg dir.
        assert result.run_dir.parent.parent == ctx["seg_dir"]
        # Run dir name = marketing_id.
        assert result.run_dir.name == result.manifest.marketing_id

    def test_marketing_id_format(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.manifest.marketing_id.startswith("mkt_")
        assert len(result.manifest.marketing_id) == 4 + 24  # prefix + 24 hex


# ---------------------------------------------------------------------------
# Provenance / SHA-256 chain
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_sha256_chain_populated(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        # All four SHA fields populated and 64 chars long.
        for field_name in (
            "ml_dataset_sha256",
            "feature_set_sha256",
            "preprocessing_config_sha256",
            "segmentation_manifest_sha256",
        ):
            value = getattr(result.manifest, field_name)
            assert value
            assert len(value) == 64

    def test_segmentation_manifest_sha_matches_file(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        expected_sha = hashlib.sha256(ctx["seg_manifest_path"].read_bytes()).hexdigest()
        assert result.manifest.segmentation_manifest_sha256 == expected_sha

    def test_input_segmentation_manifest_recorded(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.manifest.input_segmentation_manifest == str(ctx["seg_manifest_path"])


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_missing_config_file_raises(self, tmp_path: Path, monkeypatch) -> None:
        from customer_segmentation.prototype.marketing.exceptions import (
            MarketingConfigError,
        )

        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        with pytest.raises(MarketingConfigError):
            _run_with_storage(
                monkeypatch,
                storage_root,
                segmentation_id=ctx["segmentation_id"],
                config_path=tmp_path / "missing.yaml",
            )

    def test_default_config_path_used(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.manifest.config_sha256
        assert len(result.manifest.config_sha256) == 64

    def test_config_sha_changes_with_content(self, tmp_path: Path, monkeypatch) -> None:
        """Two different config files → different config_sha256."""
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)

        cfg_path_1 = tmp_path / "dev07_a.yaml"
        cfg_path_2 = tmp_path / "dev07_b.yaml"
        cfg_path_1.write_text(_make_minimal_yaml(level="INFO"), encoding="utf-8")
        cfg_path_2.write_text(_make_minimal_yaml(level="DEBUG"), encoding="utf-8")

        r1 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
            config_path=cfg_path_1,
        )
        r2 = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
            config_path=cfg_path_2,
            force_rerun=True,
        )
        assert r1.manifest.config_sha256 != r2.manifest.config_sha256


def _make_minimal_yaml(level: str = "INFO") -> str:
    return f"""
dev07_marketing:
  schema_version: "1.0.0"
  availability_default: "REVIEW_REQUIRED"
  mkt_framework:
    path_relative: "docs/marketing"
    # Canonical aggregate form per ADR-0008 (Option A). Single
    # quotes to avoid YAML double-quoted escape processing of
    # the backslashes; the pattern keeps the regex backslashes as
    # literal characters.
    version_pattern: '^MKT-01\\.\\.05__v\\d+(?:\\.\\d+)*$'
  display:
    percentage_decimals: 2
    missing_value_placeholder: "--"
    csv_missing_value: ""
    disclaimer_text: "descriptive only"
  storage:
    output_dir_relative: "marketing"
    emit_manifest_json: true
    emit_recommendations_csv: false
    emit_recommendations_jsonl: false
  logging:
    level: "{level}"
    format: "%(message)s"
    log_dir_relative: "data/prototype/datasets"
    emit_to_console: true
  research_safety:
    readonly_paths:
      - "data/raw/primary"
    never_promote_to_research: true
    marketing_scope: "MARKETING_PROTOTYPE"
  validation:
    forbid_internal_metrics_as_kpi: true
    forbid_marketing_terminology: true
    require_no_duplicate_segment_id: true
    exclude_dbscan_noise: true
"""


# ---------------------------------------------------------------------------
# Pipeline result dataclass
# ---------------------------------------------------------------------------


class TestMarketingPipelineResult:
    def test_result_is_frozen(self, tmp_path: Path, monkeypatch) -> None:
        from dataclasses import FrozenInstanceError

        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        with pytest.raises(FrozenInstanceError):
            # frozen dataclass → assignment raises FrozenInstanceError.
            result.lifecycle = "MODIFIED"  # type: ignore[misc]

    def test_result_has_required_fields(self, tmp_path: Path, monkeypatch) -> None:
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        for attr in (
            "lifecycle",
            "manifest",
            "run_dir",
            "manifest_path",
            "cached",
            "validation_passed",
        ):
            assert hasattr(result, attr)


# ---------------------------------------------------------------------------
# Lifecycle constants
# ---------------------------------------------------------------------------


def test_lifecycle_constants() -> None:
    assert LIFECYCLE_CACHED == "CACHED"
    assert LIFECYCLE_SUCCESS == "SUCCESS"
    assert LIFECYCLE_FAILED == "FAILED"


# ---------------------------------------------------------------------------
# Default config sanity
# ---------------------------------------------------------------------------


def test_default_config_exists_and_loads() -> None:
    assert DEFAULT_DEV07_CONFIG_PATH.exists()
    from customer_segmentation.prototype.marketing.config_loader import (
        load_dev07_config,
    )

    cfg = load_dev07_config()
    assert isinstance(cfg, Dev07Config)


# ---------------------------------------------------------------------------
# preprocessing_warning carry-over (audit §4.10, §6.10, §7.2)
#
# Per DEV-07 implementation plan §4.2 + §4.4 + AC-D07-10, the
# ``preprocessing_warning`` from the DEV-06 manifest should be
# carried forward into the DEV-07 output. However:
#   - The E-MKT schema (SYS-03 §15.1) does NOT include an explicit
#     ``preprocessing_warning`` field.
#   - ``MarketingRecommendationManifest`` v1.0.0 does NOT have a
#     ``preprocessing_warning`` field.
#   - The DEV-07 pipeline does NOT currently read
#     ``preprocessing_warning`` from the DEV-06 manifest.
#
# This is a documented contract gap pending owner decision. The
# tests below document the current observable behaviour:
#
#   1. The DEV-07 manifest schema does NOT carry a
#      ``preprocessing_warning`` field (defensive witness).
#   2. The DEV-07 manifest's ``limitation`` / ``limitation_note`` /
#      top-level ``limitation`` do NOT reference the DEV-06
#      ``preprocessing_warning`` text.
#   3. The pipeline produces a valid manifest even when the DEV-06
#      ``preprocessing_warning`` is non-empty (no exception).
#
# The remediation report (F-P3-03 from audit) recommends either:
#   (a) Add an explicit ``preprocessing_warning`` field to the
#       E-MKT schema and ``MarketingRecommendationManifest`` (requires
#       ADR + schema-version bump).
#   (b) Concatenate the DEV-06 ``preprocessing_warning`` into
#       ``limitation_note`` (text-level propagation, no schema change).
#   (c) Document explicitly that DEV-07 does NOT carry the warning
#       forward (no propagation).
#
# Owner decision required.
# ---------------------------------------------------------------------------


class TestPreprocessingWarningCarryOver:
    """Witness tests for the ``preprocessing_warning`` contract gap."""

    def test_marketing_manifest_has_no_preprocessing_warning_field(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Witness: ``MarketingRecommendationManifest`` v1.0.0 does NOT
        expose a ``preprocessing_warning`` field. This documents the
        current schema, not a bug — owner decision required to add
        the field (audit F-P3-03)."""
        from dataclasses import fields

        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        field_names = {f.name for f in fields(result.manifest)}
        assert "preprocessing_warning" not in field_names

    def test_dev06_preprocessing_warning_does_not_propagate_to_limitation(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Witness: even when the DEV-06 manifest has a non-empty
        ``preprocessing_warning``, the DEV-07 manifest's
        ``limitation`` / per-entry ``limitation_note`` do NOT
        contain the warning text. This documents the current
        behaviour; owner decision required to change it (audit
        F-P3-03)."""
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        # Inject a non-empty ``preprocessing_warning`` into the
        # synthetic DEV-06 manifest.
        dev06_warning = (
            "POST_PREPROCESSING_VALUES: scaling and transformation have "
            "been applied; raw feature values are no longer directly "
            "interpretable as business quantities."
        )
        data = json.loads(ctx["seg_manifest_path"].read_text())
        data["preprocessing_warning"] = dev06_warning
        ctx["seg_manifest_path"].write_text(json.dumps(data), encoding="utf-8")

        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        # Top-level manifest limitation does NOT include the warning.
        assert dev06_warning not in result.manifest.limitation
        # Per-entry limitation_note does NOT include the warning.
        for entry in result.manifest.recommendations:
            assert dev06_warning not in entry.limitation_note
            assert dev06_warning not in (entry.limitation or "")

    def test_dev07_pipeline_succeeds_with_preprocessing_warning(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Defensive: the DEV-07 pipeline must NOT fail when the
        DEV-06 manifest carries a ``preprocessing_warning`` field
        (even non-empty). DEV-06 contract treats this field as
        mandatory; DEV-07 must accept it without parsing it."""
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        data = json.loads(ctx["seg_manifest_path"].read_text())
        data["preprocessing_warning"] = "post-preprocessing values disclaimer from DEV-06"
        ctx["seg_manifest_path"].write_text(json.dumps(data), encoding="utf-8")

        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        # Pipeline succeeds; manifest is valid; lifecycle is SUCCESS.
        assert result.lifecycle == LIFECYCLE_SUCCESS
        assert result.manifest_path.exists()
        # Round-trip works (the field is not consumed by DEV-07 but
        # does not break I/O either).
        loaded = read_marketing_manifest(result.manifest_path)
        assert loaded.marketing_id == result.manifest.marketing_id

    def test_dev06_preprocessing_warning_empty_string_is_accepted(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """DEV-06 default ``preprocessing_warning`` is empty string.
        DEV-07 pipeline must accept this case (no exception)."""
        storage_root = tmp_path / "data"
        ctx = _setup_synthetic_storage(storage_root)
        data = json.loads(ctx["seg_manifest_path"].read_text())
        data["preprocessing_warning"] = ""
        ctx["seg_manifest_path"].write_text(json.dumps(data), encoding="utf-8")

        result = _run_with_storage(
            monkeypatch,
            storage_root,
            segmentation_id=ctx["segmentation_id"],
        )
        assert result.lifecycle == LIFECYCLE_SUCCESS
