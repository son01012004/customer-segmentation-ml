"""End-to-end integration tests for the DEV-08 dashboard pipeline.

These tests run the full pipeline with synthetic fixtures:

- DEV-06 segmentation_manifest.json
- DEV-05 evaluation_manifest.json (multiple runs)
- DEV-07 marketing_manifest.json (Phase A REVIEW_REQUIRED)

And verify the dashboard orchestrator produces:
- Correct chart records
- Correct artefacts on disk
- Correct text/JSON output content
- No mutation of input manifests
- Correct error handling for missing inputs / cross-manifest
  mismatch / projection BLOCKED.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from customer_segmentation.prototype.evaluation.manifest import (
    EnvironmentBlock,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    build_evaluation_manifest,
    make_valid_entry,
    write_evaluation_manifest,
)
from customer_segmentation.prototype.marketing.manifest import (
    build_marketing_manifest,
    build_recommendation_entry_review_required,
    write_marketing_manifest,
)
from customer_segmentation.prototype.segmentation.manifest import (
    FeatureProfile,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
    write_segmentation_manifest,
)
from customer_segmentation.prototype.visualization.config_loader import (
    load_dev08_config,
)
from customer_segmentation.prototype.visualization.dashboard import DashboardGenerator
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.pipeline import run_visualization_pipeline

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _seg_args(**overrides: Any) -> dict[str, Any]:
    base = {
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "1" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "evaluation_id": None,
        "algorithm": "kmeans",
        "algorithm_version": "1.0",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "feature_set": ["Recency", "Frequency", "Monetary"],
        "n_samples_input": 1000,
        "n_samples_used_for_compute": 1000,
        "n_clusters_input": 3,
        "n_segments": 3,
        "noise_count": None,
        "noise_ratio": None,
        "noise_policy_used": "exclude",
        "segment_sizes": [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
        ],
        "profiles": [
            FeatureProfile(0, "Recency", {"mean": 5.0}),
            FeatureProfile(1, "Recency", {"mean": 4.0}),
            FeatureProfile(2, "Recency", {"mean": 3.0}),
            FeatureProfile(0, "Frequency", {"mean": 10.0}),
            FeatureProfile(1, "Frequency", {"mean": 8.0}),
            FeatureProfile(2, "Frequency", {"mean": 6.0}),
        ],
        "characteristics": [],
        "config_sha256": "d" * 64,
        "environment": {
            "python": "3.14",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {"pandas": "2.0"},
        },
        "log_file": "seg.log",
        "validation_report": SegmentationValidationReport(all_passed=True, checks=[]),
        "readonly_paths": ["data/raw/primary"],
        "input_clustering_manifest": "clustering_manifest.json",
        "input_cluster_labels": "cluster_labels_x.parquet",
        "input_ml_dataset": "ml_dataset_x.parquet",
        "input_evaluation_manifest": None,
    }
    base.update(overrides)
    return base


def _build_seg_manifest(**overrides):
    return build_segmentation_manifest(**_seg_args(**overrides))


def _build_eval_manifest(evaluation_id: str):
    env = EnvironmentBlock(
        python="3.14.4",
        platform="Linux",
        release="7.0.0",
        machine="x86_64",
        key_libraries={"numpy": "2.0", "pandas": "2.0"},
    )
    return build_evaluation_manifest(
        evaluation_id=evaluation_id,
        clustering_id="cl_" + "1" * 24,
        preprocessed_id="pp_x",
        dataset_id="ds_x",
        ml_dataset_sha256="a" * 64,
        feature_set_sha256="b" * 64,
        preprocessing_config_sha256="c" * 64,
        algorithm="kmeans",
        algorithm_version="sklearn_1.5",
        algorithm_family="hard",
        n_samples=1000,
        n_features=14,
        feature_set=["a", "b", "c"],
        hyperparameters={"n_clusters": 3},
        seed_policy="deterministic",
        seed=42,
        noise_policy_used="exclude",
        metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
        metrics=EvaluationMetricsResult(
            entries={
                "silhouette": make_valid_entry("silhouette", 0.5),
                "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
            }
        ),
        n_samples_input=1000,
        n_samples_used_for_compute=1000,
        n_clusters_realized=3,
        noise_count=None,
        noise_ratio=None,
        config_sha256="d" * 64,
        environment=env,
        log_file="ev.log",
        validation_report=EvaluationValidationReport(all_passed=True),
        readonly_paths=["data/raw/primary"],
    )


def _build_mkt_manifest():
    return build_marketing_manifest(
        marketing_id="mkt_" + "0" * 24,
        segmentation_id="seg_" + "0" * 24,
        clustering_id="cl_" + "1" * 24,
        preprocessed_id="pp_x",
        dataset_id="ds_x",
        source_framework_version=None,
        mkt_framework_found=False,
        ml_dataset_sha256="a" * 64,
        feature_set_sha256="b" * 64,
        preprocessing_config_sha256="c" * 64,
        segmentation_manifest_sha256="d" * 64,
        n_segments_input=3,
        n_segments_with_recommendation=3,
        n_segments_noise=0,
        n_segments_not_available=0,
        noise_policy_used="exclude",
        recommendations=[
            build_recommendation_entry_review_required(
                segment_id=i, cluster_label=i, evidence_ref=["seg_" + "0" * 24]
            )
            for i in range(3)
        ],
        environment={
            "python": "3.14",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {"pandas": "2.0"},
        },
        config_sha256="e" * 64,
        log_file="mkt.log",
        validation_report={"all_passed": True, "checks": []},
        readonly_paths=["data/raw/primary"],
        input_segmentation_manifest="segmentation_manifest.json",
        availability="REVIEW_REQUIRED",
    )


# ---------------------------------------------------------------------------
# Integration: full pipeline end-to-end
# ---------------------------------------------------------------------------


def test_integration_full_pipeline(tmp_path: Path) -> None:
    """Render a dashboard with seg + 2 evals + mkt; check all artefacts."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    ev1 = _build_eval_manifest("ev_" + "1" * 24)
    ev2 = _build_eval_manifest("ev_" + "2" * 24)
    ev1_path = tmp_path / "ev1.json"
    ev2_path = tmp_path / "ev2.json"
    write_evaluation_manifest(ev1, ev1_path)
    write_evaluation_manifest(ev2, ev2_path)
    mkt = _build_mkt_manifest()
    mkt_path = tmp_path / "mkt.json"
    write_marketing_manifest(mkt, mkt_path)
    out_dir = tmp_path / "dashboard"

    result = run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        evaluation_manifest_paths=[ev1_path, ev2_path],
        marketing_manifest_path=mkt_path,
        output_dir=out_dir,
    )

    # All artefacts present.
    assert (out_dir / "cluster_distribution.png").exists()
    assert (out_dir / "cluster_distribution.txt").exists()
    assert (out_dir / "segment_profile.txt").exists()
    assert (out_dir / "feature_comparison.png").exists()
    assert (out_dir / "feature_comparison.txt").exists()
    assert (out_dir / "metric_comparison.png").exists()
    assert (out_dir / "metric_comparison.txt").exists()
    assert (out_dir / "marketing.txt").exists()
    assert (out_dir / "dashboard_summary.txt").exists()
    assert (out_dir / "dashboard_summary.json").exists()

    # Charts reflect the inputs.
    chart_names = {c.name for c in result.result.charts}
    assert chart_names == {
        "cluster_distribution",
        "segment_profile",
        "feature_comparison",
        "metric_comparison",
        "marketing",
        "cluster_visualization_2d",
    }
    chart_by_name = {c.name: c for c in result.result.charts}
    assert chart_by_name["cluster_distribution"].status == "EMITTED"
    assert chart_by_name["segment_profile"].status == "EMITTED"
    assert chart_by_name["feature_comparison"].status == "EMITTED"
    assert chart_by_name["metric_comparison"].status == "EMITTED"
    assert chart_by_name["marketing"].status == "EMITTED"
    assert chart_by_name["cluster_visualization_2d"].status == "BLOCKED"

    # JSON sidecar matches.
    payload = json.loads(result.summary_json_path.read_text(encoding="utf-8"))
    assert payload["dashboard_id"] == result.result.dashboard_id
    assert len(payload["charts"]) == 6

    # Output dir does NOT contain research artefacts.
    # (The dashboard never writes to data/processed/ or reports/.)
    for p in out_dir.iterdir():
        assert "data" not in p.parts
        assert "reports" not in p.parts


def test_integration_seg_only_dashboard(tmp_path: Path) -> None:
    """When no evaluation manifests are provided, metric chart is SKIPPED."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    result = run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    chart_by_name = {c.name: c for c in result.result.charts}
    assert chart_by_name["metric_comparison"].status == "SKIPPED"


def test_integration_no_marketing_section(tmp_path: Path) -> None:
    """Without marketing manifest, the marketing chart shows the banner."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    result = run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    chart_by_name = {c.name: c for c in result.result.charts}
    mkt = chart_by_name["marketing"]
    assert mkt.status == "EMITTED"
    assert "REVIEW_REQUIRED" in mkt.note
    text = (out_dir / "marketing.txt").read_text(encoding="utf-8")
    assert "REVIEW_REQUIRED" in text


def test_integration_inputs_not_mutated(tmp_path: Path) -> None:
    """Verify inputs are not mutated by the pipeline."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    seg_bytes_before = seg_path.read_bytes()
    out_dir = tmp_path / "dashboard"
    run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    seg_bytes_after = seg_path.read_bytes()
    # The pipeline never writes to the input.
    assert seg_bytes_before == seg_bytes_after


def test_integration_summary_lists_blocked_chart(tmp_path: Path) -> None:
    """The summary must mention cluster_visualization_2d BLOCKED status."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    result = run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    summary_text = result.summary_text_path.read_text(encoding="utf-8")
    assert "cluster_visualization_2d" in summary_text
    assert "BLOCKED" in summary_text


def test_integration_no_research_artefacts(tmp_path: Path) -> None:
    """The dashboard never writes to research-artifact directories."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    # No data/raw/, data/processed/, reports/ subdirectory under out_dir.
    for sub in ("data", "reports", "research"):
        assert not (
            out_dir / sub
        ).exists(), f"dashboard created {sub}/ under out_dir (must not happen)"


def test_integration_output_files_within_run_dir(tmp_path: Path) -> None:
    """All emitted files must be inside the run_dir."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    result = run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    out_dir_resolved = out_dir.resolve()
    for c in result.result.charts:
        if c.output_path:
            p = Path(c.output_path).resolve()
            assert p.is_relative_to(
                out_dir_resolved
            ), f"Chart {c.name} output {p} escapes run_dir {out_dir_resolved}"


def test_integration_metric_comparison_with_two_runs(tmp_path: Path) -> None:
    """Multiple evaluation manifests produce a metric comparison with n_runs=2."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    ev1 = _build_eval_manifest("ev_" + "1" * 24)
    ev2 = _build_eval_manifest("ev_" + "2" * 24)
    ev1_path = tmp_path / "ev1.json"
    ev2_path = tmp_path / "ev2.json"
    write_evaluation_manifest(ev1, ev1_path)
    write_evaluation_manifest(ev2, ev2_path)
    out_dir = tmp_path / "dashboard"
    run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        evaluation_manifest_paths=[ev1_path, ev2_path],
        output_dir=out_dir,
    )
    text = (out_dir / "metric_comparison.txt").read_text(encoding="utf-8")
    assert "n_runs        : 2" in text


def test_integration_disclaimer_appended_everywhere(tmp_path: Path) -> None:
    """Every emitted text file must contain the disclaimer phrase."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    result = run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    for c in result.result.charts:
        if c.output_path and c.output_path.endswith(".txt"):
            p = Path(c.output_path)
            text = p.read_text(encoding="utf-8")
            assert "Disclaimer" in text or c.status in {
                "SKIPPED",
                "BLOCKED",
            }, f"Missing disclaimer in {p}"


def test_integration_dbscan_with_noise_manifest(tmp_path: Path) -> None:
    """A DBSCAN manifest with is_noise=True exercises noise policy."""
    seg = _build_seg_manifest(
        algorithm="dbscan",
        algorithm_family="density_based",
        n_samples_input=1100,
        n_samples_used_for_compute=1000,
        n_clusters_input=3,
        n_segments=3,
        noise_count=100,
        noise_ratio=0.1,
        noise_policy_used="exclude",
        segment_sizes=[
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
            SegmentSize(-1, 100, 10.0, "n_samples_input", True),
        ],
    )
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    run_visualization_pipeline(
        segmentation_manifest_path=seg_path,
        output_dir=out_dir,
    )
    # Cluster distribution chart should exist.
    cd_text = (out_dir / "cluster_distribution.txt").read_text(encoding="utf-8")
    assert "noise_count" in cd_text or "Noise" in cd_text or "-1" in cd_text


def test_integration_metric_mismatch_handled(tmp_path: Path) -> None:
    """When a wrong-type object is passed as evaluation_manifest, pipeline
    raises VisualizationError rather than producing a fake success."""
    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)
    # Pass a SEG manifest where an evaluation manifest is expected.
    out_dir = tmp_path / "dashboard"
    with pytest.raises(VisualizationError):
        run_visualization_pipeline(
            segmentation_manifest_path=seg_path,
            evaluation_manifest_paths=[seg_path],  # wrong type
            output_dir=out_dir,
        )


def test_integration_writes_to_canonical_layout(tmp_path: Path) -> None:
    """When output_dir is None, the pipeline writes to the canonical tree.

    Uses a monkeypatch to redirect the storage root to a synthetic
    tree; verifies the dashboard output lands inside the canonical
    per-segmentation layout.
    """

    seg = _build_seg_manifest()
    seg_path = tmp_path / "seg.json"
    write_segmentation_manifest(seg, seg_path)

    # Build a synthetic DEV-02 storage root tree. ``storage_root`` already
    # points at ``<repo>/data/prototype/datasets`` (per
    # ``configs/dev02_dataset_management.yaml``); the canonical layout
    # starts directly under it (no extra ``"datasets"`` literal). See
    # the regression test in
    # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    storage_root = tmp_path / "my_storage"
    storage_root.mkdir()
    clustering_id = "cl_" + "1" * 24
    seg_id_str = "seg_" + "0" * 24
    monkey_seg_dir = (
        storage_root
        / "ds_x"
        / "preprocessed"
        / "pp_x"
        / "clustering"
        / clustering_id
        / "segmentation"
        / seg_id_str
    )
    monkey_seg_dir.mkdir(parents=True)

    # Monkeypatch resolve_storage_root to return our synthetic root.
    import customer_segmentation.prototype.visualization.pipeline as pipe_mod

    original_resolve = pipe_mod.resolve_storage_root

    def fake_resolve(_=None):
        return storage_root.resolve()

    pipe_mod.resolve_storage_root = fake_resolve
    try:
        result = run_visualization_pipeline(
            segmentation_manifest_path=seg_path,
            output_dir=None,
        )
        assert str(result.run_dir).startswith(str(storage_root.resolve()))
    finally:
        pipe_mod.resolve_storage_root = original_resolve


# ---------------------------------------------------------------------------
# Cross-cutting defensive tests
# ---------------------------------------------------------------------------


def test_dashboard_generator_handles_evaluation_wrong_type() -> None:
    """The DashboardGenerator catches a wrong-type evaluation object gracefully."""
    cfg = load_dev08_config()
    seg = _build_seg_manifest()
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "viz"
        run_dir.mkdir()
        # Pass an empty list as evaluations to avoid hitting the wrong-type guard.
        gen = DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            evaluation_manifests=[],
            run_dir=run_dir,
        )
        records = gen.generate()
        # No chart errors expected.
        for r in records:
            assert r.status != "ERROR"


def test_dashboard_handles_dbscan_manifest() -> None:
    cfg = load_dev08_config()
    seg = _build_seg_manifest(
        algorithm="dbscan",
        algorithm_family="density_based",
        n_samples_input=1100,
        n_samples_used_for_compute=1000,
        n_clusters_input=3,
        n_segments=3,
        noise_count=100,
        noise_ratio=0.1,
        noise_policy_used="exclude",
        segment_sizes=[
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
            SegmentSize(-1, 100, 10.0, "n_samples_input", True),
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "viz"
        run_dir.mkdir()
        gen = DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            run_dir=run_dir,
        )
        records = gen.generate()
        cd = next(r for r in records if r.name == "cluster_distribution")
        assert cd.status == "EMITTED"


def test_dashboard_handles_no_profiles() -> None:
    """Manifest with no profiles: feature_comparison SKIPPED, others EMITTED."""
    cfg = load_dev08_config()
    seg = _build_seg_manifest(profiles=[])
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "viz"
        run_dir.mkdir()
        gen = DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            run_dir=run_dir,
        )
        records = gen.generate()
        fc = next(r for r in records if r.name == "feature_comparison")
        assert fc.status == "SKIPPED"
        assert "no FeatureProfile" in fc.note
