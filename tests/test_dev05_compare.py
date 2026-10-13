"""Tests for the DEV-05 compare module + R-EVAL-08 no-ranking guarantee."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.evaluation.compare import (
    DEFAULT_COMPARISON_DISCLAIMER,
    ComparisonGroup,
    ComparisonReport,
    CompatibilityKey,
    IncompatibilityReason,
    compare_evaluations,
)
from customer_segmentation.prototype.evaluation.display import (
    check_no_banned_substrings,
)
from customer_segmentation.prototype.evaluation.manifest import (
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    build_evaluation_manifest,
    make_valid_entry,
    write_evaluation_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_manifest(
    tmp_path: Path,
    *,
    evaluation_id: str = "ev_" + "a" * 24,
    algorithm: str = "kmeans",
    algorithm_family: str = "hard",
    n_samples: int = 100,
    n_clusters: int = 4,
    seed: int = 42,
    feature_set: list[str] | None = None,
    ml_dataset_sha: str = "b" * 64,
    feature_set_sha: str = "c" * 64,
    preprocessing_config_sha: str = "d" * 64,
    dataset_id: str = "ds_abc",
    preprocessed_id: str = "pp_xyz",
    clustering_id: str = "cl_" + "a" * 24,
    metric_set: list[str] | None = None,
    noise_count: int | None = None,
    noise_ratio: float | None = None,
    n_samples_used_for_compute: int | None = None,
    silhouette_value: float = 0.5,
    dbi_value: float = 1.0,
    ch_value: float = 100.0,
) -> Path:
    """Create a real on-disk manifest for compare tests."""
    if feature_set is None:
        feature_set = ["a", "b", "c", "d"]
    if metric_set is None:
        metric_set = ["silhouette", "davies_bouldin", "calinski_harabasz"]
    n_features = len(feature_set)
    # For density_based algorithm, default noise_count / noise_ratio if not set.
    if algorithm_family == "density_based":
        if noise_count is None:
            noise_count = 0
        if noise_ratio is None:
            noise_ratio = 0.0
    n_used = n_samples_used_for_compute
    if n_used is None:
        n_used = n_samples - (noise_count or 0)
    m = build_evaluation_manifest(
        evaluation_id=evaluation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha,
        feature_set_sha256=feature_set_sha,
        preprocessing_config_sha256=preprocessing_config_sha,
        algorithm=algorithm,
        algorithm_version="sklearn_1.5",
        algorithm_family=algorithm_family,
        n_samples=n_samples,
        n_features=n_features,
        feature_set=feature_set,
        hyperparameters={"n_clusters": n_clusters},
        seed_policy="stochastic" if seed is not None else "deterministic",
        seed=seed,
        noise_policy_used="exclude",
        metric_set=metric_set,
        metrics=EvaluationMetricsResult(
            entries={
                "silhouette": make_valid_entry("silhouette", silhouette_value),
                "davies_bouldin": make_valid_entry("davies_bouldin", dbi_value),
                "calinski_harabasz": make_valid_entry("calinski_harabasz", ch_value),
            }
        ),
        n_samples_input=n_samples,
        n_samples_used_for_compute=n_used,
        n_clusters_realized=n_clusters,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        config_sha256="e" * 64,
        environment=EnvironmentBlock(
            python="3.14.4", platform="Linux", release="7.0",
            machine="x86_64", key_libraries={}
        ),
        log_file="ev_xx.log",
        validation_report=EvaluationValidationReport(all_passed=True),
        readonly_paths=[],
    )
    # Write to disk so read_evaluation_manifest works.
    run_dir = tmp_path / "runs" / evaluation_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "evaluation_manifest.json"
    write_evaluation_manifest(m, path)
    return path


# ---------------------------------------------------------------------------
# compare_evaluations
# ---------------------------------------------------------------------------


class TestCompareEvaluations:
    def test_single_manifest_one_singleton_group(self, tmp_path: Path) -> None:
        p = _make_manifest(tmp_path)
        report = compare_evaluations([p])
        assert len(report.groups) == 1
        assert report.groups[0].is_singleton

    def test_two_compatible_manifests_one_group(self, tmp_path: Path) -> None:
        p1 = _make_manifest(
            tmp_path,
            evaluation_id="ev_" + "a" * 24,
            algorithm="kmeans",
        )
        p2 = _make_manifest(
            tmp_path,
            evaluation_id="ev_" + "b" * 24,
            algorithm="dbscan",
            algorithm_family="density_based",
        )
        report = compare_evaluations([p1, p2])
        assert len(report.groups) == 1
        assert len(report.groups[0].evaluations) == 2

    def test_incompatible_ml_dataset_splits_groups(self, tmp_path: Path) -> None:
        p1 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "a" * 24,
            ml_dataset_sha="b" * 64,
        )
        p2 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "b" * 24,
            ml_dataset_sha="z" * 64,  # different
        )
        report = compare_evaluations([p1, p2])
        assert len(report.groups) == 2

    def test_incompatibility_reasons_populated(self, tmp_path: Path) -> None:
        p1 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "a" * 24,
            ml_dataset_sha="b" * 64,
        )
        p2 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "b" * 24,
            ml_dataset_sha="z" * 64,
        )
        report = compare_evaluations([p1, p2])
        # The 2nd manifest is incompatible with the 1st on ml_dataset_sha256.
        assert len(report.incompatibility_reasons) >= 1
        reasons = [r.field_name for r in report.incompatibility_reasons]
        assert "ml_dataset_sha256" in reasons

    def test_report_to_dict_serializable(self, tmp_path: Path) -> None:
        p1 = _make_manifest(tmp_path, evaluation_id="ev_" + "a" * 24)
        p2 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "b" * 24,
            algorithm="agglomerative",
        )
        report = compare_evaluations([p1, p2])
        d = report.to_dict()
        # Must be JSON-serialisable.
        text = json.dumps(d, default=str)
        assert "groups" in text
        assert "disclaimer" in text

    def test_disclaimer_present_in_report(self, tmp_path: Path) -> None:
        p = _make_manifest(tmp_path)
        report = compare_evaluations([p])
        assert report.disclaimer == DEFAULT_COMPARISON_DISCLAIMER
        assert "ranking" in report.disclaimer

    def test_no_banned_substrings_in_output(self, tmp_path: Path) -> None:
        p1 = _make_manifest(tmp_path, evaluation_id="ev_" + "a" * 24)
        p2 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "b" * 24, algorithm="gmm",
            algorithm_family="model_based",
        )
        report = compare_evaluations([p1, p2])
        text = json.dumps(report.to_dict(), default=str)
        found = check_no_banned_substrings(text)
        assert found == [], f"banned words found: {found}"

    def test_compatibility_key_equality(self) -> None:
        a = CompatibilityKey(
            dataset_id="d1", preprocessed_id="p1", ml_dataset_sha256="x" * 64,
            feature_set_sha256="y" * 64, preprocessing_config_sha256="z" * 64,
            metric_set=("silhouette", "davies_bouldin", "calinski_harabasz"),
        )
        b = CompatibilityKey(
            dataset_id="d1", preprocessed_id="p1", ml_dataset_sha256="x" * 64,
            feature_set_sha256="y" * 64, preprocessing_config_sha256="z" * 64,
            metric_set=("silhouette", "davies_bouldin", "calinski_harabasz"),
        )
        c = CompatibilityKey(
            dataset_id="d2", preprocessed_id="p1", ml_dataset_sha256="x" * 64,
            feature_set_sha256="y" * 64, preprocessing_config_sha256="z" * 64,
            metric_set=("silhouette", "davies_bouldin", "calinski_harabasz"),
        )
        assert a == b
        assert hash(a) == hash(b)
        assert a != c

    def test_three_manifests_two_groups(self, tmp_path: Path) -> None:
        p1 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "a" * 24, algorithm="kmeans"
        )
        p2 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "b" * 24, algorithm="agglomerative"
        )
        p3 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "c" * 24, algorithm="kmeans",
            ml_dataset_sha="z" * 64,  # different → different group
        )
        report = compare_evaluations([p1, p2, p3])
        # p1 and p2 should group; p3 alone.
        group_sizes = sorted([len(g.evaluations) for g in report.groups])
        assert group_sizes == [1, 2]

    def test_mixed_density_filter_provenance(self, tmp_path: Path) -> None:
        """Per-row provenance surfaces n_used + noise_count + noise_policy."""
        p1 = _make_manifest(
            tmp_path, evaluation_id="ev_" + "a" * 24, algorithm="kmeans",
            n_samples=100, noise_count=None, noise_ratio=None,
        )
        # Build a DBSCAN manifest with explicit noise / n_samples_used.
        from customer_segmentation.prototype.evaluation.manifest import (
            build_evaluation_manifest,
            write_evaluation_manifest,
        )

        m2 = build_evaluation_manifest(
            evaluation_id="ev_" + "b" * 24,
            clustering_id="cl_" + "b" * 24,
            preprocessed_id="pp_xyz",
            dataset_id="ds_abc",
            ml_dataset_sha256="b" * 64,
            feature_set_sha256="c" * 64,
            preprocessing_config_sha256="d" * 64,
            algorithm="dbscan",
            algorithm_version="sklearn_1.5",
            algorithm_family="density_based",
            n_samples=1000,
            n_features=4,
            feature_set=["a", "b", "c", "d"],
            hyperparameters={"eps": 0.5, "min_samples": 5},
            seed_policy="deterministic",
            seed=None,
            noise_policy_used="exclude",
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry("silhouette", 0.281),
                    "davies_bouldin": make_valid_entry("davies_bouldin", 1.402),
                    "calinski_harabasz": make_valid_entry("calinski_harabasz", 872.1),
                }
            ),
            n_samples_input=1000,
            n_samples_used_for_compute=300,
            n_clusters_realized=2,
            noise_count=700,
            noise_ratio=0.7,
            config_sha256="e" * 64,
            environment=EnvironmentBlock(
                python="3.14", platform="Linux", release="7",
                machine="x86_64", key_libraries={}
            ),
            log_file="ev_xx.log",
            validation_report=EvaluationValidationReport(all_passed=True),
            readonly_paths=[],
        )
        run_dir = tmp_path / "runs" / ("ev_" + "b" * 24)
        run_dir.mkdir(parents=True, exist_ok=True)
        p2 = run_dir / "evaluation_manifest.json"
        write_evaluation_manifest(m2, p2)

        report = compare_evaluations([p1, p2])
        # Same CompatibilityKey, so 1 group with 2 evaluations.
        assert len(report.groups) == 1
        # The output dict must surface noise_count per evaluation.
        d = report.to_dict()
        evals = d["groups"][0]["evaluations"]
        noise_counts = {e["evaluation_id"]: e["noise_count"] for e in evals}
        assert noise_counts["ev_" + "a" * 24] is None
        assert noise_counts["ev_" + "b" * 24] == 700
