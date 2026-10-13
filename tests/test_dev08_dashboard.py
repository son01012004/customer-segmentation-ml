"""Tests for DEV-08 dashboard orchestrator (DashboardGenerator)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from customer_segmentation.prototype.evaluation.manifest import (
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    build_evaluation_manifest,
    make_valid_entry,
)
from customer_segmentation.prototype.marketing.manifest import (
    build_marketing_manifest,
    build_recommendation_entry_review_required,
)
from customer_segmentation.prototype.segmentation.manifest import (
    FeatureProfile,
    SegmentationManifest,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
)
from customer_segmentation.prototype.visualization.config_loader import (
    Dev08Config,
    load_dev08_config,
)
from customer_segmentation.prototype.visualization.dashboard import (
    CLUSTER_VISUALIZATION_BLOCKED_NOTE,
    DASHBOARD_CHARTS,
    DashboardGenerator,
    build_dashboard_result,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
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


def _make_seg(**overrides: Any) -> SegmentationManifest:
    return build_segmentation_manifest(**_seg_args(**overrides))


def _make_eval(evaluation_id: str = "ev_" + "a" * 24) -> EvaluationManifest:
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


def _make_mkt() -> Any:
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
# Constants
# ---------------------------------------------------------------------------


def test_dashboard_charts_constant() -> None:
    assert "cluster_distribution" in DASHBOARD_CHARTS
    assert "segment_profile" in DASHBOARD_CHARTS
    assert "feature_comparison" in DASHBOARD_CHARTS
    assert "metric_comparison" in DASHBOARD_CHARTS
    assert "marketing" in DASHBOARD_CHARTS
    assert "cluster_visualization_2d" in DASHBOARD_CHARTS


def test_blocked_note_mentions_projection() -> None:
    assert (
        "projection" in CLUSTER_VISUALIZATION_BLOCKED_NOTE.lower()
        or "projection" in CLUSTER_VISUALIZATION_BLOCKED_NOTE
    )
    assert "BLOCKED" in CLUSTER_VISUALIZATION_BLOCKED_NOTE


# ---------------------------------------------------------------------------
# DashboardGenerator construction
# ---------------------------------------------------------------------------


def test_dashboard_generator_rejects_non_config() -> None:
    seg = _make_seg()
    with pytest.raises(VisualizationError, match="Dev08Config"):
        DashboardGenerator(
            config="bad",
            segmentation_manifest=seg,
            run_dir=Path("/tmp"),
        )


def test_dashboard_generator_rejects_non_segmentation_manifest() -> None:
    cfg = load_dev08_config()
    with pytest.raises(VisualizationError, match="SegmentationManifest"):
        DashboardGenerator(
            config=cfg,
            segmentation_manifest="bad",
            run_dir=Path("/tmp"),
        )


def test_dashboard_generator_rejects_non_list_evals() -> None:
    seg = _make_seg()
    cfg = load_dev08_config()
    with pytest.raises(VisualizationError, match="evaluation_manifests must be a list"):
        DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            evaluation_manifests="bad",
            run_dir=Path("/tmp"),
        )


def test_dashboard_generator_rejects_non_manifest_in_evals() -> None:
    seg = _make_seg()
    cfg = load_dev08_config()
    with pytest.raises(VisualizationError, match="EvaluationManifest"):
        DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            evaluation_manifests=[_make_eval(), "bad"],
            run_dir=Path("/tmp"),
        )


def test_dashboard_generator_rejects_non_mkt_manifest() -> None:
    seg = _make_seg()
    cfg = load_dev08_config()
    with pytest.raises(VisualizationError, match="MarketingRecommendationManifest"):
        DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            marketing_manifest="bad",
            run_dir=Path("/tmp"),
        )


def test_dashboard_generator_requires_existing_run_dir(tmp_path: Path) -> None:
    seg = _make_seg()
    cfg = load_dev08_config()
    missing = tmp_path / "missing_dir"
    with pytest.raises(VisualizationError, match="must already exist"):
        DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            run_dir=missing,
        )


def test_dashboard_generator_requires_dir_not_file(tmp_path: Path) -> None:
    seg = _make_seg()
    cfg = load_dev08_config()
    f = tmp_path / "file"
    f.write_text("x")
    with pytest.raises(VisualizationError, match="must be a directory"):
        DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            run_dir=f,
        )


def test_dashboard_generator_invalid_output_format(tmp_path: Path) -> None:
    seg = _make_seg()
    cfg = load_dev08_config()
    run_dir = tmp_path / "viz"
    run_dir.mkdir()
    with pytest.raises(VisualizationError, match="output_format"):
        DashboardGenerator(
            config=cfg,
            segmentation_manifest=seg,
            run_dir=run_dir,
            output_format="jpg",
        )


# ---------------------------------------------------------------------------
# DashboardGenerator.generate
# ---------------------------------------------------------------------------


@pytest.fixture
def gen_setup(tmp_path: Path) -> tuple[Dev08Config, SegmentationManifest, Path]:
    cfg = load_dev08_config()
    seg = _make_seg()
    run_dir = tmp_path / "viz"
    run_dir.mkdir()
    return cfg, seg, run_dir


def test_generate_returns_six_records(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    assert len(records) == 6
    for r in records:
        assert r.status in {"EMITTED", "SKIPPED", "BLOCKED", "ERROR"}


def test_generate_emits_cluster_distribution(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    cd = next(r for r in records if r.name == "cluster_distribution")
    assert cd.status == "EMITTED"
    assert (run_dir / "cluster_distribution.png").exists()
    assert (run_dir / "cluster_distribution.txt").exists()


def test_generate_emits_segment_profile(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    sp = next(r for r in records if r.name == "segment_profile")
    assert sp.status == "EMITTED"
    assert (run_dir / "segment_profile.txt").exists()


def test_generate_emits_feature_comparison(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    fc = next(r for r in records if r.name == "feature_comparison")
    assert fc.status == "EMITTED"
    assert (run_dir / "feature_comparison.png").exists()


def test_generate_skips_feature_comparison_when_no_profiles(tmp_path: Path) -> None:
    cfg = load_dev08_config()
    seg = _make_seg(profiles=[])
    run_dir = tmp_path / "viz"
    run_dir.mkdir()
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    fc = next(r for r in records if r.name == "feature_comparison")
    assert fc.status == "SKIPPED"
    assert "no FeatureProfile" in fc.note


def test_generate_emits_metric_comparison_with_eval(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(
        config=cfg,
        segmentation_manifest=seg,
        evaluation_manifests=[_make_eval()],
        run_dir=run_dir,
    )
    records = gen.generate()
    mc = next(r for r in records if r.name == "metric_comparison")
    assert mc.status == "EMITTED"
    assert (run_dir / "metric_comparison.png").exists()


def test_generate_skips_metric_comparison_no_eval(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    mc = next(r for r in records if r.name == "metric_comparison")
    assert mc.status == "SKIPPED"
    assert "no EvaluationManifest" in mc.note


def test_generate_emits_marketing_review_required(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    mkt = next(r for r in records if r.name == "marketing")
    assert mkt.status == "EMITTED"
    assert (run_dir / "marketing.txt").exists()
    assert "REVIEW_REQUIRED" in (run_dir / "marketing.txt").read_text(encoding="utf-8")


def test_generate_emits_marketing_with_manifest(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(
        config=cfg,
        segmentation_manifest=seg,
        marketing_manifest=_make_mkt(),
        run_dir=run_dir,
    )
    records = gen.generate()
    mkt = next(r for r in records if r.name == "marketing")
    assert mkt.status == "EMITTED"
    assert "REVIEW_REQUIRED" in mkt.note


def test_generate_hidden_marketing_skipped(tmp_path: Path) -> None:
    seg = _make_seg()
    run_dir = tmp_path / "viz"
    run_dir.mkdir()
    # Override marketing_section to hidden via a custom config.
    from dataclasses import replace

    hidden_cfg = replace(load_dev08_config(), marketing_section="hidden")
    gen = DashboardGenerator(config=hidden_cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    mkt = next(r for r in records if r.name == "marketing")
    assert mkt.status == "SKIPPED"


def test_generate_blocked_cluster_visualization(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    cv = next(r for r in records if r.name == "cluster_visualization_2d")
    assert cv.status == "BLOCKED"
    assert "BLOCKED" in cv.note


def test_generate_does_not_mutate_input_manifests(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    snap_before_n_profiles = len(seg.profiles)
    snap_before_seg_id = seg.segmentation_id
    snap_before_n_segments = seg.n_segments
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    gen.generate()
    # The manifest fields should be untouched.
    assert seg.segmentation_id == snap_before_seg_id
    assert seg.n_segments == snap_before_n_segments
    assert len(seg.profiles) == snap_before_n_profiles


def test_generate_outputs_within_run_dir(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(config=cfg, segmentation_manifest=seg, run_dir=run_dir)
    records = gen.generate()
    run_dir_resolved = run_dir.resolve()
    for r in records:
        if r.output_path:
            p = Path(r.output_path).resolve()
            assert p.is_relative_to(run_dir_resolved)


def test_generate_svg_format(gen_setup: tuple[Dev08Config, SegmentationManifest, Path]) -> None:
    cfg, seg, run_dir = gen_setup
    gen = DashboardGenerator(
        config=cfg, segmentation_manifest=seg, run_dir=run_dir, output_format="svg"
    )
    records = gen.generate()
    cd = next(r for r in records if r.name == "cluster_distribution")
    assert cd.status == "EMITTED"
    assert cd.output_path.endswith(".svg")


# ---------------------------------------------------------------------------
# build_dashboard_result
# ---------------------------------------------------------------------------


def test_build_dashboard_result_basic(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    result = build_dashboard_result(
        dashboard_id="viz_aaa",
        segmentation_manifest=seg,
        clustering_id=seg.clustering_id,
        preprocessed_id=seg.preprocessed_id,
        dataset_id=seg.dataset_id,
        run_dir=run_dir,
        lifecycle="SUCCESS",
        validation_passed=True,
        charts=[],
        input_segmentation_manifest_path="/tmp/seg.json",
    )
    assert result.dashboard_id == "viz_aaa"
    assert result.segmentation_id == seg.segmentation_id
    assert result.input_segmentation_manifest_path == "/tmp/seg.json"
    assert result.charts == []


def test_build_dashboard_result_with_paths(
    gen_setup: tuple[Dev08Config, SegmentationManifest, Path],
) -> None:
    cfg, seg, run_dir = gen_setup
    result = build_dashboard_result(
        dashboard_id="viz_bbb",
        segmentation_manifest=seg,
        clustering_id=seg.clustering_id,
        preprocessed_id=seg.preprocessed_id,
        dataset_id=seg.dataset_id,
        run_dir=run_dir,
        lifecycle="SUCCESS",
        validation_passed=True,
        charts=[],
        input_segmentation_manifest_path="/tmp/seg.json",
        input_evaluation_manifest_paths=["/tmp/ev1.json", "/tmp/ev2.json"],
        input_marketing_manifest_path="/tmp/mkt.json",
        notes=["x"],
    )
    assert len(result.input_evaluation_manifest_paths) == 2
    assert result.input_marketing_manifest_path == "/tmp/mkt.json"
    assert result.notes == ["x"]
