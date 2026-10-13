"""Tests for the metric_comparison type-check guard (Task 1.6 fix).

Verify that extract_metric_matrix raises VisualizationError with a clear
message when given a non-EvaluationManifest object (e.g. a
SegmentationManifest), rather than surfacing a confusing AttributeError.
"""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.segmentation.manifest import (
    FeatureProfile,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
)
from customer_segmentation.prototype.visualization.charts.metric_comparison import (
    extract_metric_matrix,
    format_metric_comparison_table,
    plot_metric_comparison,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)


def _seg_args(**overrides):
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
        "feature_set": ["Recency"],
        "n_samples_input": 1000,
        "n_samples_used_for_compute": 1000,
        "n_clusters_input": 3,
        "n_segments": 3,
        "noise_count": None,
        "noise_ratio": None,
        "noise_policy_used": "exclude",
        "segment_sizes": [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
        ],
        "profiles": [FeatureProfile(0, "Recency", {"mean": 5.0})],
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


def test_extract_metric_matrix_rejects_segmentation_manifest() -> None:
    """Passing a SegmentationManifest must raise VisualizationError."""
    seg = build_segmentation_manifest(**_seg_args())
    with pytest.raises(VisualizationError, match="not an EvaluationManifest"):
        extract_metric_matrix(seg)


def test_extract_metric_matrix_rejects_segmentation_manifest_in_list() -> None:
    """A list containing a SegmentationManifest must raise."""
    seg = build_segmentation_manifest(**_seg_args())
    with pytest.raises(VisualizationError, match="manifests\\[0\\]"):
        extract_metric_matrix([seg, seg])


def test_format_metric_comparison_table_rejects_segmentation_manifest() -> None:
    seg = build_segmentation_manifest(**_seg_args())
    with pytest.raises(VisualizationError, match="not an EvaluationManifest"):
        format_metric_comparison_table(seg)


def test_plot_metric_comparison_rejects_segmentation_manifest() -> None:
    seg = build_segmentation_manifest(**_seg_args())
    with pytest.raises(VisualizationError, match="not an EvaluationManifest"):
        plot_metric_comparison(seg)


def test_extract_metric_matrix_rejects_dict() -> None:
    """A plain dict is not an EvaluationManifest."""
    with pytest.raises(VisualizationError, match="not an EvaluationManifest"):
        extract_metric_matrix({"evaluation_id": "ev_x"})


def test_extract_metric_matrix_still_accepts_evaluations() -> None:
    """Sanity: legitimate EvaluationManifest inputs still work."""
    from customer_segmentation.prototype.evaluation.manifest import (
        EnvironmentBlock,
        EvaluationMetricsResult,
        EvaluationValidationReport,
        build_evaluation_manifest,
        make_valid_entry,
    )

    env = EnvironmentBlock(
        python="3.14.4",
        platform="Linux",
        release="7.0.0",
        machine="x86_64",
        key_libraries={"numpy": "2.0"},
    )
    m = build_evaluation_manifest(
        evaluation_id="ev_" + "a" * 24,
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
        n_features=4,
        feature_set=["a"],
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
    run_ids, metric_names, values = extract_metric_matrix(m)
    assert len(run_ids) == 1
    assert len(metric_names) == 3
    assert len(values) == 1
