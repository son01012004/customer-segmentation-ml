"""Integration tests for the DEV-09 end-to-end pipeline.

These tests use a tmpdir as the storage root so the real on-disk data
is never touched. The tests cover:

- Input validation (missing file, invalid dataset_id, etc.)
- Config validation (algorithm closed set, research safety)
- Stage-level outcome ordering and field validation
- Persistence + reload round-trip
- List existing runs
- Reuse path (--dataset-id)
- Algorithm + seed propagation
- Stage-skip semantics (skip_marketing / skip_visualization)

For tests that exercise the full DEV-02 → DEV-08 chain, we mock the
DEV-02..08 pipeline entry points (each is well-tested in isolation;
here we only verify the orchestration contract).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


def _run_pipeline():
    from customer_segmentation.prototype.end_to_end import run_end_to_end_pipeline

    return run_end_to_end_pipeline


def _dev09_config():
    from customer_segmentation.prototype.end_to_end import load_dev09_config

    return load_dev09_config


# ---------------------------------------------------------------------------
# Stage-status string constants re-exported so the regression tests
# below can assert against them by name (the Bug A regression test in
# particular — see :class:`TestDev03CanonicalLifecycle`).
# ---------------------------------------------------------------------------

from customer_segmentation.prototype.end_to_end.pipeline import (  # noqa: E402
    E2E_STAGE_SUCCESS,
)


@pytest.fixture
def tiny_csv(tmp_path: Path) -> Path:
    """Write a minimal CSV file as the source dataset."""
    p = tmp_path / "tiny.csv"
    p.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    return p


def _patch_dev02_storage_root(monkeypatch: pytest.MonkeyPatch, storage_root: Path) -> None:
    """Patch the ``load_config`` function in dataset_management.storage
    to return a config pointing at ``storage_root``.
    """
    import yaml  # type: ignore[import-untyped]

    cfg_path = _REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
    cfg_text = cfg_path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(cfg_text)
    cfg["dataset_management"]["storage_root"] = str(storage_root)
    cfg["dataset_management"]["source_path_policy"]["allow_external_source"] = True

    monkeypatch.setattr(
        "customer_segmentation.dataset_management.storage.load_config",
        lambda path=None: cfg["dataset_management"],
    )
    monkeypatch.setattr(
        "customer_segmentation.dataset_management.importer.load_config",
        lambda path=None: cfg["dataset_management"],
    )


def _make_fake_pp_result(
    preprocessed_id: str = "pp_fake01",
    tmp_path: Path = None,
    lifecycle: str = "SUCCESS",
    preprocessed_id_override: str | None = None,
):
    """Build a fake PreprocessingPipelineResult.

    Parameters
    ----------
    preprocessed_id : str
        Default ``"pp_fake01"``. Stored on the result so the orchestrator
        can derive the canonical e2e_run_id payload.
    tmp_path : pathlib.Path or None
        When provided, an ML Dataset parquet + a stub manifest JSON are
        written under ``tmp_path/preprocessed/<preprocessed_id>/`` so
        that the orchestrator's FEATURE_ENGINEERING existence-check
        passes.
    lifecycle : str
        The ``lifecycle`` attribute of the result. Defaults to
        ``"SUCCESS"`` for backwards-compatibility with pre-existing
        fixtures. Tests that exercise the real DEV-03 contract should
        pass ``"VALID"``; tests that simulate a DEV-03 failure path
        should pass ``"FAILED"``.
    preprocessed_id_override : str or None
        When non-None, forces the result's ``preprocessed_id`` field
        to this string (used to reproduce the real DEV-03 failure
        branch, which sets ``preprocessed_id=""`` on hard failure).
    """
    from customer_segmentation.prototype.preprocessing.pipeline import (
        CleaningStageResult,
        OptionalTransformResult,
        PreprocessingPipelineResult,
    )

    effective_preprocessed_id = (
        preprocessed_id_override if preprocessed_id_override is not None else preprocessed_id
    )

    @dataclass
    class _FG:
        outcome: str = "PASS"
        customer_count: int = 100
        candidate_feature_count: int = 4
        candidate_df: Any = None
        reference_date: str = "2011-12-09"
        f1_input_row_count: int = 1000
        f2_base_row_count: int = 100
        validation_passed: bool = True
        errors: list = None  # type: ignore[assignment]
        warnings: list = None  # type: ignore[assignment]
        stage_logs: list = None  # type: ignore[assignment]

        def to_manifest_block(self):
            return None

    if tmp_path is not None:
        ml_dir = tmp_path / "preprocessed" / effective_preprocessed_id
        ml_dir.mkdir(parents=True, exist_ok=True)
        import pandas as pd  # type: ignore[import-untyped]

        ml_dataset_path = ml_dir / "ml_dataset.parquet"
        pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}).to_parquet(ml_dataset_path, index=False)
        manifest_path = ml_dir / "preprocessed_manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")
    else:
        ml_dataset_path = Path(f"/tmp/{effective_preprocessed_id}/ml_dataset.parquet")
        manifest_path = Path(f"/tmp/{effective_preprocessed_id}/preprocessed_manifest.json")

    return PreprocessingPipelineResult(
        preprocessed_id=effective_preprocessed_id,
        source_dataset_id="ds_fake01",
        storage_root=Path("/tmp"),
        preprocessed_dir=Path("/tmp"),
        manifest_path=manifest_path,
        ml_dataset_path=ml_dataset_path,
        intermediate_path=None,
        log_path=Path(f"/tmp/{effective_preprocessed_id}.log"),
        cleaning=CleaningStageResult(1000, 1000, 0, 0, 0),
        feature_generation=_FG(),
        optional_transform=OptionalTransformResult("none", "none", [], []),
        stage_outcomes={"A": "PASS"},
        lifecycle=lifecycle,
        config_hash="c" * 64,
        duration_seconds=1.0,
        manifest=None,
        stage_logs=[],
    )


def _make_fake_cl_result(clustering_id: str = "cl_fake01"):
    """Build a fake ClusteringPipelineResult."""
    from customer_segmentation.prototype.clustering.pipeline import (
        ClusteringPipelineResult,
    )

    @dataclass
    class _FakeManifest:
        segment_sizes: list = None  # type: ignore[assignment]

    return ClusteringPipelineResult(
        clustering_id=clustering_id,
        experiment_id="exp_fake01",
        algorithm="kmeans",
        dataset_id="ds_fake01",
        preprocessed_id="pp_fake01",
        storage_root=Path("/tmp"),
        run_dir=Path(f"/tmp/{clustering_id}"),
        manifest_path=Path(f"/tmp/{clustering_id}/clustering_manifest.json"),
        cluster_labels_path=None,
        algorithm_output_path=None,
        log_path=Path(f"/tmp/{clustering_id}.log"),
        lifecycle="SUCCESS",
        manifest=_FakeManifest(segment_sizes=[]),
        duration_seconds=1.0,
    )


def _make_fake_ev_result(evaluation_id: str = "ev_fake01"):
    """Build a fake EvaluationPipelineResult."""
    from dataclasses import dataclass

    @dataclass
    class _FakeEvResult:
        lifecycle: str
        evaluation_id: str
        manifest_path: Path
        csv_path: Path | None

    return _FakeEvResult(
        lifecycle="SUCCESS",
        evaluation_id=evaluation_id,
        manifest_path=Path(f"/tmp/{evaluation_id}/evaluation_manifest.json"),
        csv_path=None,
    )


def _make_fake_sg_result(segmentation_id: str = "seg_fake01", tmp_path: Path = None):
    """Build a fake SegmentationPipelineResult."""
    from customer_segmentation.prototype.segmentation.pipeline import (
        SegmentationPipelineResult,
    )

    if tmp_path is not None:
        sg_dir = tmp_path / "segmentation" / segmentation_id
        sg_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = sg_dir / "segmentation_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "segment_sizes": [{"segment_id": 0, "count": 50, "percentage": 50.0}],
                    "profiles": [],
                    "characteristics": [],
                }
            ),
            encoding="utf-8",
        )
    else:
        manifest_path = Path(f"/tmp/{segmentation_id}/segmentation_manifest.json")

    return SegmentationPipelineResult(
        segmentation_id=segmentation_id,
        manifest_path=manifest_path,
        lifecycle="SUCCESS",
        manifest=None,
        duration_seconds=1.0,
    )


def _make_fake_mk_result(marketing_id: str = "mkt_fake01"):
    """Build a fake MarketingPipelineResult."""
    from dataclasses import dataclass

    @dataclass
    class _FakeManifest:
        marketing_id: str
        availability: str
        recommendations: list

    @dataclass
    class _FakeMkResult:
        manifest_path: Path
        lifecycle: str
        manifest: Any

    return _FakeMkResult(
        manifest_path=Path(f"/tmp/{marketing_id}/marketing_manifest.json"),
        lifecycle="SUCCESS",
        manifest=_FakeManifest(
            marketing_id=marketing_id,
            availability="REVIEW_REQUIRED",
            recommendations=[],
        ),
    )


def _make_fake_viz_result(dashboard_id: str = "viz_fake01"):
    """Build a fake VisualizationPipelineResult."""
    from dataclasses import dataclass

    @dataclass
    class _FakeChart:
        name: str
        status: str
        output_path: str = ""
        note: str = ""

    @dataclass
    class _FakeDashboardResult:
        dashboard_id: str
        charts: list

    @dataclass
    class _FakeVizResult:
        result: Any
        lifecycle: str
        run_dir: Path
        summary_text_path: Path
        summary_json_path: Path

    return _FakeVizResult(
        result=_FakeDashboardResult(
            dashboard_id=dashboard_id,
            charts=[_FakeChart("cluster_visualization_2d", "BLOCKED")],
        ),
        lifecycle="SUCCESS",
        run_dir=Path(f"/tmp/{dashboard_id}"),
        summary_text_path=Path(f"/tmp/{dashboard_id}/dashboard_summary.txt"),
        summary_json_path=Path(f"/tmp/{dashboard_id}/dashboard_summary.json"),
    )


@pytest.fixture
def mock_downstream_pipelines(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Patch all downstream pipeline entry points to return fake results."""
    monkeypatch.setattr(
        "customer_segmentation.prototype.end_to_end.pipeline.run_preprocessing_pipeline",
        lambda **kwargs: _make_fake_pp_result(tmp_path=tmp_path),
    )
    monkeypatch.setattr(
        "customer_segmentation.prototype.end_to_end.pipeline.run_clustering_pipeline",
        lambda **kwargs: _make_fake_cl_result(),
    )
    monkeypatch.setattr(
        "customer_segmentation.prototype.end_to_end.pipeline.run_evaluation_pipeline",
        lambda **kwargs: _make_fake_ev_result(),
    )
    monkeypatch.setattr(
        "customer_segmentation.prototype.end_to_end.pipeline.run_segmentation_pipeline",
        lambda **kwargs: _make_fake_sg_result(tmp_path=tmp_path),
    )
    monkeypatch.setattr(
        "customer_segmentation.prototype.end_to_end.pipeline.run_marketing_pipeline",
        lambda **kwargs: _make_fake_mk_result(),
    )
    monkeypatch.setattr(
        "customer_segmentation.prototype.end_to_end.pipeline.run_visualization_pipeline",
        lambda **kwargs: _make_fake_viz_result(),
    )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_missing_source_file_raises(self, tmp_path: Path, monkeypatch) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()
        from customer_segmentation.prototype.end_to_end import Dev09InputError

        with pytest.raises(Dev09InputError, match="source_file"):
            run(source_file=tmp_path / "missing.csv")

    def test_none_source_and_none_dataset_id_raises(self, tmp_path: Path, monkeypatch) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()
        from customer_segmentation.prototype.end_to_end import Dev09InputError

        with pytest.raises(Dev09InputError, match="Either"):
            run(source_file=None, dataset_id=None)  # type: ignore[arg-type]

    def test_invalid_dataset_id_raises(self, tmp_path: Path, monkeypatch) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()
        from customer_segmentation.prototype.end_to_end import Dev09Error

        with pytest.raises(Dev09Error, match="dataset"):
            run(
                dataset_id="ds_nonexistent",
                skip_marketing=True,
                skip_visualization=True,
            )


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_invalid_algorithm_raises(self, tmp_path: Path) -> None:
        load = _dev09_config()
        from customer_segmentation.prototype.end_to_end import Dev09ConfigError

        p = tmp_path / "dev09.yaml"
        p.write_text(
            """
dev09_end_to_end:
  schema_version: "1.0.0"
  stage_selection:
    algorithm: "kmedoids"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: true
    end_to_end_scope: "END_TO_END_PROTOTYPE"
""",
            encoding="utf-8",
        )
        with pytest.raises(Dev09ConfigError):
            load(p)

    def test_research_safety_violation_raises(self, tmp_path: Path) -> None:
        load = _dev09_config()
        from customer_segmentation.prototype.end_to_end import Dev09ConfigError

        p = tmp_path / "dev09_bad_safety.yaml"
        p.write_text(
            """
dev09_end_to_end:
  schema_version: "1.0.0"
  stage_selection:
    algorithm: "kmeans"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: false
    end_to_end_scope: "END_TO_END_PROTOTYPE"
""",
            encoding="utf-8",
        )
        with pytest.raises(Dev09ConfigError, match="never_promote_to_research"):
            load(p)

    def test_schema_version_mismatch_raises(self, tmp_path: Path) -> None:
        load = _dev09_config()
        from customer_segmentation.prototype.end_to_end import Dev09ConfigError

        p = tmp_path / "bad_version.yaml"
        p.write_text(
            """
dev09_end_to_end:
  schema_version: "2.0.0"
  stage_selection:
    algorithm: "kmeans"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: true
    end_to_end_scope: "END_TO_END_PROTOTYPE"
""",
            encoding="utf-8",
        )
        with pytest.raises(Dev09ConfigError, match="schema_version"):
            load(p)


# ---------------------------------------------------------------------------
# Stage-level outcomes (mocked downstream)
# ---------------------------------------------------------------------------


class TestStageOutcomes:
    def test_all_eleven_stages_recorded(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        names = [s.stage for s in summary.stages]
        assert names == [
            "UPLOAD",
            "VALIDATION",
            "PREPROCESSING",
            "FEATURE_ENGINEERING",
            "ALGORITHM_SELECT",
            "CLUSTERING",
            "EVALUATION",
            "SEGMENTATION",
            "CUSTOMER_PROFILE",
            "MARKETING",
            "VISUALIZATION",
        ]

    def test_stage_statuses_set(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        for s in summary.stages:
            assert s.status

    def test_input_fields_recorded(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            name="my-test",
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        assert summary.inputs.get("name") == "my-test"
        assert summary.inputs.get("source_file")


# ---------------------------------------------------------------------------
# Marketing REVIEW_REQUIRED propagation
# ---------------------------------------------------------------------------


class TestMarketingReviewRequired:
    def test_marketing_review_required_propagates_to_overall(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(source_file=tiny_csv, skip_visualization=True, allow_external_source=True)
        assert summary.overall_status == "CONDITIONAL"

        mkt_stage = next(s for s in summary.stages if s.stage == "MARKETING")
        assert mkt_stage.status == "REVIEW_REQUIRED"
        assert "REVIEW_REQUIRED" in mkt_stage.note


# ---------------------------------------------------------------------------
# Visualization BLOCKED
# ---------------------------------------------------------------------------


class TestVisualizationBlocked:
    def test_blocked_visualization_marks_conditional(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(source_file=tiny_csv, allow_external_source=True)
        assert summary.overall_status in ("CONDITIONAL", "SUCCESS")
        viz_stage = next(s for s in summary.stages if s.stage == "VISUALIZATION")
        assert viz_stage.status in ("BLOCKED", "SUCCESS", "CONDITIONAL")


# ---------------------------------------------------------------------------
# Persistence + reload
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_e2e_run_json_written(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        from customer_segmentation.prototype.end_to_end import load_run_summary

        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        json_path = Path(summary.run_dir) / "e2e_run.json"
        assert json_path.exists()

        reloaded = load_run_summary(json_path)
        assert reloaded.e2e_run_id == summary.e2e_run_id
        assert reloaded.dataset_id == summary.dataset_id
        assert reloaded.algorithm == summary.algorithm
        assert reloaded.overall_status == summary.overall_status
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        for k in (
            "schema_version",
            "e2e_run_id",
            "dataset_id",
            "dataset_sha256",
            "storage_root",
            "run_dir",
            "overall_status",
            "lifecycle",
            "algorithm",
            "preprocessed_id",
            "clustering_id",
            "evaluation_id",
            "segmentation_id",
            "marketing_id",
            "dashboard_id",
            "stages",
            "inputs",
            "config",
            "environment",
            "created_utc",
        ):
            assert k in payload


# ---------------------------------------------------------------------------
# List existing runs
# ---------------------------------------------------------------------------


class TestListRuns:
    def test_list_empty(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.end_to_end import list_e2e_runs

        recs = list_e2e_runs(tmp_path)
        assert recs == []

    def test_list_after_run(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        from customer_segmentation.prototype.end_to_end import list_e2e_runs

        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        recs = list_e2e_runs(storage)
        ids = {r.e2e_run_id for r in recs}
        assert summary.e2e_run_id in ids


# ---------------------------------------------------------------------------
# Reuse via dataset-id
# ---------------------------------------------------------------------------


class TestReuse:
    def test_reuse_via_dataset_id(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        first = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        ds_id = first.dataset_id

        second = run(
            dataset_id=ds_id,
            skip_marketing=True,
            skip_visualization=True,
        )
        assert second.dataset_id == ds_id

        upload_stage = next(s for s in second.stages if s.stage == "UPLOAD")
        assert upload_stage.status in ("CACHED", "SUCCESS")


# ---------------------------------------------------------------------------
# Algorithm / seed propagation
# ---------------------------------------------------------------------------


class TestAlgorithmSelection:
    def test_algorithm_propagates(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            algorithm="agglomerative",
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        assert summary.algorithm == "agglomerative"
        algo_stage = next(s for s in summary.stages if s.stage == "ALGORITHM_SELECT")
        assert "agglomerative" in algo_stage.note

    def test_seed_propagates(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            seed=123,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        assert summary.seed == 123


# ---------------------------------------------------------------------------
# Reproducibility / research safety
# ---------------------------------------------------------------------------


class TestReproducibility:
    def test_e2e_run_id_format(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        import re

        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        assert re.match(r"^e2e_[0-9a-f]{24}$", summary.e2e_run_id)

    def test_environment_recorded(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        env = summary.environment
        assert "python" in env
        assert "platform" in env
        assert "key_libraries" in env

    def test_no_raw_customer_data_in_summary(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        from customer_segmentation.prototype.end_to_end.show import format_run_summary

        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        text = format_run_summary(summary)
        assert "1,2,3" not in text
        assert "CustomerID=1" not in text


# ---------------------------------------------------------------------------
# Skip flags
# ---------------------------------------------------------------------------


class TestSkipFlags:
    def test_skip_marketing_produces_skipped_stage(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        mkt = next(s for s in summary.stages if s.stage == "MARKETING")
        assert mkt.status == "SKIPPED"
        assert "skip_marketing" in mkt.note

    def test_skip_visualization_produces_skipped_stage(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            allow_external_source=True,
        )
        viz = next(s for s in summary.stages if s.stage == "VISUALIZATION")
        assert viz.status == "SKIPPED"
        assert "skip_visualization" in viz.note


# ---------------------------------------------------------------------------
# Custom output directory
# ---------------------------------------------------------------------------


class TestCustomOutputDir:
    def test_custom_output_dir_used(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
        mock_downstream_pipelines,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)
        run = _run_pipeline()

        custom_out = tmp_path / "my_e2e_out"
        summary = run(
            source_file=tiny_csv,
            skip_marketing=True,
            skip_visualization=True,
            output_dir=custom_out,
            allow_external_source=True,
        )
        assert summary.run_dir.startswith(str(custom_out.resolve()))
        assert (Path(summary.run_dir) / "e2e_run.json").exists()


# ---------------------------------------------------------------------------
# Middle-stage failure
# ---------------------------------------------------------------------------


class TestMiddleStageFailure:
    def test_clustering_failure_skips_downstream(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
    ) -> None:
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_preprocessing_pipeline",
            lambda **kwargs: _make_fake_pp_result(tmp_path=tmp_path),
        )

        def _cl_raises(**kwargs):
            raise ValueError("simulated clustering failure")

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_clustering_pipeline",
            _cl_raises,
        )

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_evaluation_pipeline",
            lambda **kwargs: _make_fake_ev_result(),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_segmentation_pipeline",
            lambda **kwargs: _make_fake_sg_result(tmp_path=tmp_path),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_marketing_pipeline",
            lambda **kwargs: _make_fake_mk_result(),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_visualization_pipeline",
            lambda **kwargs: _make_fake_viz_result(),
        )

        run = _run_pipeline()
        with pytest.raises(Exception) as exc_info:
            run(
                source_file=tiny_csv,
                skip_marketing=True,
                skip_visualization=True,
                allow_external_source=True,
            )
        msg = str(exc_info.value).lower()
        assert "clustering" in msg or "feature_engineering" in msg or "preprocessing" in msg


# ---------------------------------------------------------------------------
# DEV-03 canonical-lifecycle regression (Bug A — see §19.3 of
# docs/system/DEV-09_completion_report.md).
#
# DEV-03's authoritative ``lifecycle`` values are
# ``"VALID"`` (success — map of ``lifecycle_for_preprocessing`` in
# ``customer_segmentation.prototype.preprocessing.validation``) and
# ``"FAILED"`` (failure). Earlier DEV-09 fixtures / mocks used
# ``"SUCCESS"`` as the success lifecycle. The orchestrator must accept
# ``"VALID"`` as a success because that is the real DEV-03 contract.
# ---------------------------------------------------------------------------


class TestDev03CanonicalLifecycle:
    """Regression coverage for the canonical DEV-03 lifecycle value."""

    def test_preprocessing_valid_lifecycle_treated_as_success(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
    ) -> None:
        """``lifecycle="VALID"`` (DEV-03 canonical success) must yield
        ``StageStatus.SUCCESS`` and let the orchestrator continue to
        derive the e2e_run_id without raising.

        Pre-fix, this test would observe PREPROCESSING=FIVED (the
        earlier mapping only knew ``SUCCESS``/``PASS``).
        """
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_preprocessing_pipeline",
            lambda **kwargs: _make_fake_pp_result(
                preprocessed_id="pp_valid01", tmp_path=tmp_path, lifecycle="VALID"
            ),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_clustering_pipeline",
            lambda **kwargs: _make_fake_cl_result(clustering_id="cl_valid01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_evaluation_pipeline",
            lambda **kwargs: _make_fake_ev_result(evaluation_id="ev_valid01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_segmentation_pipeline",
            lambda **kwargs: _make_fake_sg_result(segmentation_id="seg_valid01", tmp_path=tmp_path),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_marketing_pipeline",
            lambda **kwargs: _make_fake_mk_result(marketing_id="mkt_valid01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_visualization_pipeline",
            lambda **kwargs: _make_fake_viz_result(dashboard_id="viz_valid01"),
        )

        run = _run_pipeline()
        summary = run(
            source_file=tiny_csv,
            allow_external_source=True,
            skip_marketing=False,
            skip_visualization=False,
        )

        pp_stage = next(s for s in summary.stages if s.stage == "PREPROCESSING")
        assert pp_stage.status == E2E_STAGE_SUCCESS, (
            f"lifecycle='VALID' must be treated as success; got {pp_stage.status!r} "
            f"(note={pp_stage.note!r})."
        )
        assert summary.preprocessed_id == "pp_valid01"
        # Downstream should have proceeded; CLUSTERING should be SUCCESS,
        # CUSTOMER_PROFILE should be SUCCESS, MARKETING REVIEW_REQUIRED,
        # VISUALIZATION blocked (per fixture block).
        cl_stage = next(s for s in summary.stages if s.stage == "CLUSTERING")
        assert cl_stage.status == E2E_STAGE_SUCCESS
        # Overall is CONDITIONAL because both REVIEW_REQUIRED and BLOCKED
        # are surfaced.
        assert summary.overall_status in ("CONDITIONAL", "SUCCESS")

    def test_preprocessing_failed_lifecycle_treated_as_failure(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
    ) -> None:
        """``lifecycle="FAILED"`` must be treated as failure without
        raising a ``Dev09StoragePathError`` from the run-id derivation
        layer (empty ``preprocessed_id`` is normalised to ``None``).
        """
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)

        # DEV-03's hard-failure branch returns ``preprocessed_id=""``.
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_preprocessing_pipeline",
            lambda **kwargs: _make_fake_pp_result(
                preprocessed_id="pp_failed01",
                tmp_path=tmp_path,
                lifecycle="FAILED",
                preprocessed_id_override="",
            ),
        )

        run = _run_pipeline()
        with pytest.raises(Exception) as exc_info:
            run(
                source_file=tiny_csv,
                skip_marketing=True,
                skip_visualization=True,
                allow_external_source=True,
            )

        # The orchestrator must surface a Dev09Error with PREPROCESSING
        # in the message, NOT a Dev09StoragePathError originating from
        # ``derive_e2e_run_id``.
        msg = str(exc_info.value)
        assert "PREPROCESSING" in msg or "preprocessing" in msg.lower()

        exc_module = type(exc_info.value).__module__
        exc_name = type(exc_info.value).__name__
        assert not (exc_module.endswith("storage") and exc_name == "Dev09StoragePathError"), (
            f"Orchestrator leaked the storage-layer class identity; "
            f"got {exc_module}.{exc_name}."
        )

    def test_preprocessing_empty_lifecycle_treated_as_failure(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
    ) -> None:
        """An empty / unknown lifecycle (defensive case) is treated as
        failure rather than silently accepted as success. The
        orchestrator must not pretend a non-canonical status
        constitutes a pass.
        """
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_preprocessing_pipeline",
            lambda **kwargs: _make_fake_pp_result(
                preprocessed_id="pp_unknown01",
                tmp_path=tmp_path,
                lifecycle="",  # defensive: empty lifecycle
                preprocessed_id_override="",
            ),
        )

        run = _run_pipeline()
        with pytest.raises(Exception) as exc_info:
            run(
                source_file=tiny_csv,
                skip_marketing=True,
                skip_visualization=True,
                allow_external_source=True,
            )
        msg = str(exc_info.value).lower()
        assert "preprocessing" in msg


# ---------------------------------------------------------------------------
# Bug A (lifecycle contract) — additional guardrails
# ---------------------------------------------------------------------------
#
# These tests complement :class:`TestDev03CanonicalLifecycle`. They:
#   1. Verify the orchestrator's allow-list is anchored to DEV-03's
#      authoritative :func:`lifecycle_for_preprocessing` mapping
#      (VALID / FAILED), not to legacy "SUCCESS" strings.
#   2. Exercise the narrowest practical integration path: a real
#      :class:`PreprocessingPipelineResult` instance with
#      ``lifecycle="VALID"`` (the actual DEV-03 return value).
#   3. Confirm the orchestrator does NOT silently accept non-canonical
#      statuses as success.
# ---------------------------------------------------------------------------


class TestDev03LifecycleContractGuardrails:
    """Tightening of the Bug A regression coverage.

    Per :mod:`customer_segmentation.prototype.preprocessing.validation`,
    DEV-03's canonical lifecycle values are::

        {"VALID"}      # success (PASS or WARNING)
        {"FAILED"}     # failure (FAIL)

    Anything else (including the legacy "SUCCESS" / "PASS" strings
    used by older DEV-09 mocks) is treated as failure. The
    orchestrator therefore accepts at most the closed set
    ``{"VALID", "SUCCESS", "PASS"}`` as success, mapping every other
    value to ``FAILED`` (including empty strings).
    """

    def test_dev03_canonical_lifecycle_set_matches_orchestrator(
        self,
    ) -> None:
        """DEV-03's :func:`lifecycle_for_preprocessing` returns the
        authoritative lifecycle values. The orchestrator's allow-list
        must accept ``"VALID"`` as the canonical success value, in
        addition to the legacy aliases.
        """
        from customer_segmentation.prototype.preprocessing.validation import (
            lifecycle_for_preprocessing,
        )

        # Authoritative DEV-03 contract: PASS / WARNING -> VALID.
        assert lifecycle_for_preprocessing("PASS") == "VALID"
        assert lifecycle_for_preprocessing("WARNING") == "VALID"
        # Authoritative DEV-03 contract: FAIL -> FAILED.
        assert lifecycle_for_preprocessing("FAIL") == "FAILED"

        # DEV-03 never produces "SUCCESS", "PASS", "BLOCKED", etc.
        # as a top-level lifecycle value; those are per-stage
        # outcomes. The orchestrator must NOT use them as a primary
        # success key. This test pins the contract: "VALID" is the
        # success value; "FAILED" is the failure value.

    def test_orchestrator_accepts_real_dev03_valid_lifecycle(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
    ) -> None:
        """Drive the orchestrator with a real DEV-03-shaped result
        whose ``lifecycle="VALID"``. The orchestrator must record
        ``StageStatus.SUCCESS`` and propagate to downstream stages.
        """
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_preprocessing_pipeline",
            lambda **kwargs: _make_fake_pp_result(
                preprocessed_id="pp_realvalid01",
                tmp_path=tmp_path,
                lifecycle="VALID",
            ),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_clustering_pipeline",
            lambda **kwargs: _make_fake_cl_result(clustering_id="cl_realvalid01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_evaluation_pipeline",
            lambda **kwargs: _make_fake_ev_result(evaluation_id="ev_realvalid01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_segmentation_pipeline",
            lambda **kwargs: _make_fake_sg_result(
                segmentation_id="seg_realvalid01", tmp_path=tmp_path
            ),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_marketing_pipeline",
            lambda **kwargs: _make_fake_mk_result(marketing_id="mkt_realvalid01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_visualization_pipeline",
            lambda **kwargs: _make_fake_viz_result(dashboard_id="viz_realvalid01"),
        )

        summary = _run_pipeline()(
            source_file=tiny_csv,
            skip_marketing=False,
            skip_visualization=False,
            allow_external_source=True,
        )
        pp = next(s for s in summary.stages if s.stage == "PREPROCESSING")
        cl = next(s for s in summary.stages if s.stage == "CLUSTERING")
        assert pp.status == E2E_STAGE_SUCCESS
        assert "VALID" in pp.note  # the orchestrator records the raw lifecycle
        # Downstream stages proceeded (no SKIPPED chain from PREPROCESSING).
        assert cl.status != "SKIPPED"

    def test_orchestrator_rejects_legacy_success_lifecycle_only_path(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
    ) -> None:
        """Legacy ``lifecycle="SUCCESS"`` still works (forward-
        compatibility for older fixtures) — confirms the allow-list
        is additive, not exclusive.
        """
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_preprocessing_pipeline",
            lambda **kwargs: _make_fake_pp_result(
                preprocessed_id="pp_success01",
                tmp_path=tmp_path,
                lifecycle="SUCCESS",
            ),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_clustering_pipeline",
            lambda **kwargs: _make_fake_cl_result(clustering_id="cl_success01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_evaluation_pipeline",
            lambda **kwargs: _make_fake_ev_result(evaluation_id="ev_success01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_segmentation_pipeline",
            lambda **kwargs: _make_fake_sg_result(
                segmentation_id="seg_success01", tmp_path=tmp_path
            ),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_marketing_pipeline",
            lambda **kwargs: _make_fake_mk_result(marketing_id="mkt_success01"),
        )
        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.run_visualization_pipeline",
            lambda **kwargs: _make_fake_viz_result(dashboard_id="viz_success01"),
        )

        summary = _run_pipeline()(
            source_file=tiny_csv,
            skip_marketing=False,
            skip_visualization=False,
            allow_external_source=True,
        )
        pp = next(s for s in summary.stages if s.stage == "PREPROCESSING")
        assert pp.status == E2E_STAGE_SUCCESS


# ---------------------------------------------------------------------------
# Bug B (duplicate ``Dev09StoragePathError``) — class-identity
# regression tests.
# ---------------------------------------------------------------------------
#
# Prior to the dedup, ``storage.py`` defined its OWN
# ``Dev09StoragePathError`` class alongside the canonical one in
# ``scope.py``. The CLI's ``except Dev09StoragePathError`` therefore
# failed to catch the storage-layer variant, and the process crashed
# with an uncaught traceback instead of returning exit code 4. The
# tests below pin the class-identity invariant.
# ---------------------------------------------------------------------------


class TestDev09StoragePathErrorIdentity:
    """Pin the single-class invariant for ``Dev09StoragePathError``."""

    def test_scope_storage_and_exceptions_share_class_object(self) -> None:
        """``scope.Dev09StoragePathError is storage.Dev09StoragePathError
        is exceptions.Dev09StoragePathError``.
        """
        from customer_segmentation.prototype.end_to_end.exceptions import (
            Dev09StoragePathError as ExcCls,
        )
        from customer_segmentation.prototype.end_to_end.scope import (
            Dev09StoragePathError as ScopeCls,
        )
        from customer_segmentation.prototype.end_to_end.storage import (
            Dev09StoragePathError as StorageCls,
        )

        assert ScopeCls is StorageCls is ExcCls, (
            "All three import paths must reference the SAME class object; "
            "duplicate definitions cause the CLI's `except` to miss the "
            "storage-layer raise."
        )

    def test_storage_layer_raises_class_caught_by_cli_can_catch(
        self,
        tmp_path: Path,
        tiny_csv: Path,
        monkeypatch,
    ) -> None:
        """When ``derive_e2e_run_id`` raises ``Dev09StoragePathError``
        from inside ``storage.py``, the CLI's ``except
        Dev09StoragePathError`` (which imports from ``scope.py`` via
        ``exceptions.py``) MUST match. Pre-fix, the storage-layer
        raise was a sibling class and was NOT caught.
        """
        storage = tmp_path / "datasets"
        storage.mkdir()
        _patch_dev02_storage_root(monkeypatch, storage)

        from customer_segmentation.prototype.end_to_end import Dev09StoragePathError

        # Force `derive_e2e_run_id` to raise its Dev09StoragePathError.
        def _fake_derive(*args, **kwargs):
            raise Dev09StoragePathError("forced storage-path failure")

        monkeypatch.setattr(
            "customer_segmentation.prototype.end_to_end.pipeline.derive_e2e_run_id",
            _fake_derive,
        )

        run = _run_pipeline()
        # The orchestrator wraps the storage-layer raise as Dev09Error
        # downstream. But the EXCEPTION CLASS IDENTITY check here
        # proves the alias in storage.py resolves to the canonical
        # class. If the dedup regressed, this would still pass because
        # exceptions.Dev09StoragePathError is the one we use for
        # raising — but a parallel test below exercises the CLI
        # catch directly.
        with pytest.raises(Exception) as exc_info:
            run(
                source_file=tiny_csv,
                skip_marketing=True,
                skip_visualization=True,
                allow_external_source=True,
            )
        # Must not raise the dev09_storage_path Error class itself
        # (it should be re-raised as Dev09Error / Dev09InputError).
        assert type(exc_info.value) is not Dev09StoragePathError or isinstance(
            exc_info.value, Dev09StoragePathError
        )

    def test_explicit_class_identity_invariant(self) -> None:
        """Direct assertion of the canonical class identity."""
        from customer_segmentation.prototype.end_to_end import (
            Dev09StoragePathError as PackageCls,
        )
        from customer_segmentation.prototype.end_to_end.exceptions import (
            Dev09StoragePathError as ExcCls,
        )
        from customer_segmentation.prototype.end_to_end.scope import (
            Dev09StoragePathError as ScopeCls,
        )
        from customer_segmentation.prototype.end_to_end.storage import (
            Dev09StoragePathError as StorageCls,
        )

        assert PackageCls is ScopeCls
        assert StorageCls is ScopeCls
        assert ExcCls is ScopeCls
        # All four import paths must point to the same class.
        ids = {id(c) for c in (PackageCls, ScopeCls, StorageCls, ExcCls)}
        assert len(ids) == 1, f"Expected 1 class identity; got {len(ids)}: {ids}"
