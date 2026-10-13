"""Tests for the DEV-05 manifest module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.evaluation.manifest import (
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationManifestError,
    EvaluationMetricEntry,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    InputIdentityBlock,
    ResearchSafetyBlock,
    ValidationCheck,
    build_evaluation_manifest,
    make_computation_error_entry,
    make_missing_entry,
    make_not_applicable_entry,
    make_valid_entry,
    manifest_to_dict,
    now_utc_iso,
    read_evaluation_manifest,
    runtime_field_names,
    stable_field_names,
    write_evaluation_manifest,
)
from customer_segmentation.prototype.evaluation.scope import (
    METRIC_NAMES,
    MetricReason,
    MetricStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env_block() -> EnvironmentBlock:
    return EnvironmentBlock(
        python="3.14.4",
        platform="Linux",
        release="7.0.0",
        machine="x86_64",
        key_libraries={"numpy": "1.26", "pandas": "2.2", "scikit-learn": "1.5"},
    )


@pytest.fixture
def validation_report() -> EvaluationValidationReport:
    return EvaluationValidationReport(
        all_passed=True,
        checks=[
            ValidationCheck(check_id="alignment", passed=True),
            ValidationCheck(check_id="no_nan", passed=True),
            ValidationCheck(check_id="no_inf", passed=True),
        ],
    )


def _make_metrics(
    *,
    silhouette_value: float | None = 0.372,
    dbi_value: float | None = 1.064,
    ch_value: float | None = 1234.5,
    silhouette_status: str = MetricStatus.VALID_VALUE.value,
    dbi_status: str = MetricStatus.VALID_VALUE.value,
    ch_status: str = MetricStatus.VALID_VALUE.value,
) -> EvaluationMetricsResult:
    """Build an EvaluationMetricsResult with 3 entries."""
    s_reason = MetricReason.COMPUTED.value
    d_reason = MetricReason.COMPUTED.value
    c_reason = MetricReason.COMPUTED.value
    if silhouette_status != MetricStatus.VALID_VALUE.value:
        s_reason = (
            MetricReason.ALL_NOISE.value
            if silhouette_status == MetricStatus.NOT_APPLICABLE.value
            else MetricReason.SKLEARN_EXCEPTION.value
        )
    if dbi_status != MetricStatus.VALID_VALUE.value:
        d_reason = (
            MetricReason.ALL_NOISE.value
            if dbi_status == MetricStatus.NOT_APPLICABLE.value
            else MetricReason.SKLEARN_EXCEPTION.value
        )
    if ch_status != MetricStatus.VALID_VALUE.value:
        c_reason = (
            MetricReason.ALL_NOISE.value
            if ch_status == MetricStatus.NOT_APPLICABLE.value
            else MetricReason.SKLEARN_EXCEPTION.value
        )
    return EvaluationMetricsResult(
        entries={
            "silhouette": EvaluationMetricEntry(
                metric_name="silhouette",
                value=silhouette_value,
                status=silhouette_status,
                reason=s_reason,
                is_diagnostic_only=False,
                lower_is_better=False,
                computation_time_seconds=0.1,
            ),
            "davies_bouldin": EvaluationMetricEntry(
                metric_name="davies_bouldin",
                value=dbi_value,
                status=dbi_status,
                reason=d_reason,
                is_diagnostic_only=False,
                lower_is_better=True,
                computation_time_seconds=0.1,
            ),
            "calinski_harabasz": EvaluationMetricEntry(
                metric_name="calinski_harabasz",
                value=ch_value,
                status=ch_status,
                reason=c_reason,
                is_diagnostic_only=False,
                lower_is_better=False,
                computation_time_seconds=0.1,
            ),
        }
    )


# ---------------------------------------------------------------------------
# EvaluationMetricEntry
# ---------------------------------------------------------------------------


class TestEvaluationMetricEntry:
    def test_valid_value_with_value(self) -> None:
        e = make_valid_entry("silhouette", 0.5)
        assert e.value == 0.5
        assert e.status == MetricStatus.VALID_VALUE.value
        assert e.reason == MetricReason.COMPUTED.value
        assert e.is_diagnostic_only is False
        assert e.lower_is_better is False

    def test_dbi_is_lower_better(self) -> None:
        e = make_valid_entry("davies_bouldin", 1.0)
        assert e.lower_is_better is True

    def test_ch_is_higher_better(self) -> None:
        e = make_valid_entry("calinski_harabasz", 100.0)
        assert e.lower_is_better is False

    def test_value_none_with_valid_status_raises(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricEntry(
                metric_name="silhouette",
                value=None,
                status=MetricStatus.VALID_VALUE.value,
                reason=MetricReason.COMPUTED.value,
                is_diagnostic_only=False,
                lower_is_better=False,
                computation_time_seconds=None,
            )

    def test_value_set_with_non_valid_status_raises(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricEntry(
                metric_name="silhouette",
                value=0.5,
                status=MetricStatus.NOT_APPLICABLE.value,
                reason=MetricReason.ALL_NOISE.value,
                is_diagnostic_only=False,
                lower_is_better=False,
                computation_time_seconds=None,
            )

    def test_rejects_unknown_metric_name(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricEntry(
                metric_name="wcss",
                value=0.5,
                status=MetricStatus.VALID_VALUE.value,
                reason=MetricReason.COMPUTED.value,
                is_diagnostic_only=False,
                lower_is_better=False,
                computation_time_seconds=None,
            )

    def test_rejects_unknown_status(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricEntry(
                metric_name="silhouette",
                value=0.5,
                status="BOGUS_STATUS",
                reason=MetricReason.COMPUTED.value,
                is_diagnostic_only=False,
                lower_is_better=False,
                computation_time_seconds=None,
            )

    def test_rejects_reason_not_in_status_subgroup(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricEntry(
                metric_name="silhouette",
                value=0.5,
                status=MetricStatus.VALID_VALUE.value,
                reason=MetricReason.SKLEARN_EXCEPTION.value,  # not valid for VALID_VALUE
                is_diagnostic_only=False,
                lower_is_better=False,
                computation_time_seconds=None,
            )

    def test_rejects_diagnostic_only_true(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricEntry(
                metric_name="silhouette",
                value=0.5,
                status=MetricStatus.VALID_VALUE.value,
                reason=MetricReason.COMPUTED.value,
                is_diagnostic_only=True,  # forbidden for DEV-05
                lower_is_better=False,
                computation_time_seconds=None,
            )

    def test_dbscan_noise_excluded_valid_value(self) -> None:
        """DBSCAN_NOISE_EXCLUDED is an audit annotation, not failure."""
        e = make_valid_entry(
            "silhouette", 0.5, reason=MetricReason.DBSCAN_NOISE_EXCLUDED.value
        )
        assert e.reason == MetricReason.DBSCAN_NOISE_EXCLUDED.value
        assert e.status == MetricStatus.VALID_VALUE.value


# ---------------------------------------------------------------------------
# EvaluationMetricsResult
# ---------------------------------------------------------------------------


class TestEvaluationMetricsResult:
    def test_requires_exactly_three_metrics(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry("silhouette", 0.5),
                }
            )

    def test_rejects_extra_metric(self) -> None:
        with pytest.raises(EvaluationManifestError):
            EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry("silhouette", 0.5),
                    "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                    "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
                    "extra": make_valid_entry("silhouette", 0.5),
                }
            )

    def test_as_flat_rows_three_rows(self) -> None:
        metrics = _make_metrics()
        rows = metrics.as_flat_rows()
        assert len(rows) == 3
        names = [r["metric_name"] for r in rows]
        assert names == ["silhouette", "davies_bouldin", "calinski_harabasz"]


# ---------------------------------------------------------------------------
# ResearchSafetyBlock
# ---------------------------------------------------------------------------


class TestResearchSafetyBlock:
    def test_requires_evaluated_prototype_scope(self) -> None:
        with pytest.raises(EvaluationManifestError):
            ResearchSafetyBlock(
                automatically_promoted_to_research=False,
                scope="RESEARCH_APPROVED",
                appeared_in_research_evidence=False,
                read_only_paths_unmodified=[],
            )

    def test_requires_automatically_promoted_false(self) -> None:
        with pytest.raises(EvaluationManifestError):
            ResearchSafetyBlock(
                automatically_promoted_to_research=True,
                scope="EVALUATED_PROTOTYPE",
                appeared_in_research_evidence=False,
                read_only_paths_unmodified=[],
            )

    def test_requires_appeared_in_research_false(self) -> None:
        with pytest.raises(EvaluationManifestError):
            ResearchSafetyBlock(
                automatically_promoted_to_research=False,
                scope="EVALUATED_PROTOTYPE",
                appeared_in_research_evidence=True,
                read_only_paths_unmodified=[],
            )

    def test_valid_construction(self) -> None:
        rs = ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="EVALUATED_PROTOTYPE",
            appeared_in_research_evidence=False,
            read_only_paths_unmodified=["data/raw/primary"],
        )
        assert rs.read_only_paths_unmodified == ["data/raw/primary"]


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------


class TestMakeHelpers:
    def test_make_valid_entry_defaults(self) -> None:
        e = make_valid_entry("silhouette", 0.5)
        assert e.value == 0.5
        assert e.status == MetricStatus.VALID_VALUE.value
        assert e.reason == MetricReason.COMPUTED.value
        assert e.computation_time_seconds is None

    def test_make_valid_entry_with_time(self) -> None:
        e = make_valid_entry("silhouette", 0.5, computation_time_seconds=0.42)
        assert e.computation_time_seconds == 0.42

    def test_make_not_applicable(self) -> None:
        e = make_not_applicable_entry("silhouette", MetricReason.ALL_NOISE.value)
        assert e.value is None
        assert e.status == MetricStatus.NOT_APPLICABLE.value
        assert e.reason == MetricReason.ALL_NOISE.value

    def test_make_computation_error(self) -> None:
        e = make_computation_error_entry("silhouette", MetricReason.SKLEARN_EXCEPTION.value)
        assert e.value is None
        assert e.status == MetricStatus.COMPUTATION_ERROR.value
        assert e.reason == MetricReason.SKLEARN_EXCEPTION.value

    def test_make_missing(self) -> None:
        e = make_missing_entry("silhouette", MetricReason.MANIFEST_MISSING.value)
        assert e.value is None
        assert e.status == MetricStatus.MISSING.value
        assert e.reason == MetricReason.MANIFEST_MISSING.value


# ---------------------------------------------------------------------------
# build_evaluation_manifest
# ---------------------------------------------------------------------------


class TestBuildEvaluationManifest:
    def test_happy_path(self, env_block, validation_report) -> None:
        m = build_evaluation_manifest(
            evaluation_id="ev_" + "a" * 24,
            clustering_id="cl_" + "a" * 24,
            preprocessed_id="pp_xyz",
            dataset_id="ds_abc",
            ml_dataset_sha256="b" * 64,
            feature_set_sha256="c" * 64,
            preprocessing_config_sha256="d" * 64,
            algorithm="kmeans",
            algorithm_version="sklearn_1.5",
            algorithm_family="hard",
            n_samples=100,
            n_features=4,
            feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
            hyperparameters={"n_clusters": 4},
            seed_policy="stochastic",
            seed=42,
            noise_policy_used="exclude",
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_make_metrics(),
            n_samples_input=100,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            noise_count=None,
            noise_ratio=None,
            config_sha256="e" * 64,
            environment=env_block,
            log_file="ev_xx.log",
            validation_report=validation_report,
            readonly_paths=["data/raw/primary"],
        )
        assert m.scope == "EVALUATED_PROTOTYPE"
        assert m.schema_version == EVALUATION_MANIFEST_SCHEMA_VERSION
        assert m.algorithm == "kmeans"
        assert m.evaluation_id == "ev_" + "a" * 24
        assert m.research_safety.automatically_promoted_to_research is False
        assert m.research_safety.scope == "EVALUATED_PROTOTYPE"
        assert m.research_safety.appeared_in_research_evidence is False
        assert m.noise_count is None  # non-density algorithm

    def test_density_based_requires_noise_count(
        self, env_block, validation_report
    ) -> None:
        with pytest.raises(EvaluationManifestError):
            build_evaluation_manifest(
                evaluation_id="ev_" + "a" * 24,
                clustering_id="cl_" + "a" * 24,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256="b" * 64,
                feature_set_sha256="c" * 64,
                preprocessing_config_sha256="d" * 64,
                algorithm="dbscan",
                algorithm_version="sklearn_1.5",
                algorithm_family="density_based",
                n_samples=100,
                n_features=4,
                feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
                hyperparameters={"eps": 0.5, "min_samples": 5},
                seed_policy="deterministic",
                seed=None,
                noise_policy_used="exclude",
                metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
                metrics=_make_metrics(),
                n_samples_input=100,
                n_samples_used_for_compute=50,
                n_clusters_realized=2,
                noise_count=None,  # MUST be set for density_based
                noise_ratio=None,  # MUST be set for density_based
                config_sha256="e" * 64,
                environment=env_block,
                log_file="ev_xx.log",
                validation_report=validation_report,
                readonly_paths=["data/raw/primary"],
            )

    def test_density_based_with_noise_count_ok(
        self, env_block, validation_report
    ) -> None:
        m = build_evaluation_manifest(
            evaluation_id="ev_" + "a" * 24,
            clustering_id="cl_" + "a" * 24,
            preprocessed_id="pp_xyz",
            dataset_id="ds_abc",
            ml_dataset_sha256="b" * 64,
            feature_set_sha256="c" * 64,
            preprocessing_config_sha256="d" * 64,
            algorithm="dbscan",
            algorithm_version="sklearn_1.5",
            algorithm_family="density_based",
            n_samples=100,
            n_features=4,
            feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
            hyperparameters={"eps": 0.5, "min_samples": 5},
            seed_policy="deterministic",
            seed=None,
            noise_policy_used="exclude",
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_make_metrics(),
            n_samples_input=100,
            n_samples_used_for_compute=50,
            n_clusters_realized=2,
            noise_count=50,
            noise_ratio=0.5,
            config_sha256="e" * 64,
            environment=env_block,
            log_file="ev_xx.log",
            validation_report=validation_report,
            readonly_paths=["data/raw/primary"],
        )
        assert m.noise_count == 50
        assert m.noise_ratio == 0.5

    def test_non_density_with_noise_count_raises(
        self, env_block, validation_report
    ) -> None:
        with pytest.raises(EvaluationManifestError):
            build_evaluation_manifest(
                evaluation_id="ev_" + "a" * 24,
                clustering_id="cl_" + "a" * 24,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256="b" * 64,
                feature_set_sha256="c" * 64,
                preprocessing_config_sha256="d" * 64,
                algorithm="kmeans",
                algorithm_version="sklearn_1.5",
                algorithm_family="hard",
                n_samples=100,
                n_features=4,
                feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
                hyperparameters={"n_clusters": 4},
                seed_policy="stochastic",
                seed=42,
                noise_policy_used="exclude",
                metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
                metrics=_make_metrics(),
                n_samples_input=100,
                n_samples_used_for_compute=100,
                n_clusters_realized=4,
                noise_count=0,  # MUST be None for non-density
                noise_ratio=0.0,
                config_sha256="e" * 64,
                environment=env_block,
                log_file="ev_xx.log",
                validation_report=validation_report,
                readonly_paths=["data/raw/primary"],
            )

    def test_rejects_wrong_scope(self, env_block, validation_report) -> None:
        """Manifest scope must be 'EVALUATED_PROTOTYPE'."""
        with pytest.raises(EvaluationManifestError):
            EvaluationManifest(
                schema_version=EVALUATION_MANIFEST_SCHEMA_VERSION,
                evaluation_id="ev_" + "a" * 24,
                scope="RESEARCH_APPROVED",  # wrong
                clustering_id="cl_" + "a" * 24,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256="b" * 64,
                feature_set_sha256="c" * 64,
                preprocessing_config_sha256="d" * 64,
                algorithm="kmeans",
                algorithm_version="sklearn_1.5",
                algorithm_family="hard",
                n_samples=100,
                n_features=4,
                feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
                feature_count=4,
                hyperparameters={"n_clusters": 4},
                seed_policy="stochastic",
                seed=42,
                noise_policy_used="exclude",
                metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
                metrics=_make_metrics(),
                n_samples_input=100,
                n_samples_used_for_compute=100,
                n_clusters_realized=4,
                noise_count=None,
                noise_ratio=None,
                environment=env_block,
                config_sha256="e" * 64,
                created_utc="2026-10-09T00:00:00Z",
                last_seen_utc="2026-10-09T00:00:00Z",
                log_file="ev_xx.log",
                validation_report=validation_report,
                research_safety=ResearchSafetyBlock(
                    automatically_promoted_to_research=False,
                    scope="EVALUATED_PROTOTYPE",
                    appeared_in_research_evidence=False,
                    read_only_paths_unmodified=[],
                ),
            )

    def test_rejects_used_greater_than_input(
        self, env_block, validation_report
    ) -> None:
        with pytest.raises(EvaluationManifestError):
            build_evaluation_manifest(
                evaluation_id="ev_" + "a" * 24,
                clustering_id="cl_" + "a" * 24,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256="b" * 64,
                feature_set_sha256="c" * 64,
                preprocessing_config_sha256="d" * 64,
                algorithm="kmeans",
                algorithm_version="sklearn_1.5",
                algorithm_family="hard",
                n_samples=100,
                n_features=4,
                feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
                hyperparameters={"n_clusters": 4},
                seed_policy="stochastic",
                seed=42,
                noise_policy_used="exclude",
                metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
                metrics=_make_metrics(),
                n_samples_input=100,
                n_samples_used_for_compute=200,  # invalid
                n_clusters_realized=4,
                noise_count=None,
                noise_ratio=None,
                config_sha256="e" * 64,
                environment=env_block,
                log_file="ev_xx.log",
                validation_report=validation_report,
                readonly_paths=["data/raw/primary"],
            )

    def test_rejects_invalid_noise_policy(self, env_block, validation_report) -> None:
        with pytest.raises(EvaluationManifestError):
            build_evaluation_manifest(
                evaluation_id="ev_" + "a" * 24,
                clustering_id="cl_" + "a" * 24,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256="b" * 64,
                feature_set_sha256="c" * 64,
                preprocessing_config_sha256="d" * 64,
                algorithm="kmeans",
                algorithm_version="sklearn_1.5",
                algorithm_family="hard",
                n_samples=100,
                n_features=4,
                feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
                hyperparameters={"n_clusters": 4},
                seed_policy="stochastic",
                seed=42,
                noise_policy_used="drop",  # invalid
                metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
                metrics=_make_metrics(),
                n_samples_input=100,
                n_samples_used_for_compute=100,
                n_clusters_realized=4,
                noise_count=None,
                noise_ratio=None,
                config_sha256="e" * 64,
                environment=env_block,
                log_file="ev_xx.log",
                validation_report=validation_report,
                readonly_paths=["data/raw/primary"],
            )


# ---------------------------------------------------------------------------
# Round-trip I/O
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def _make_manifest(
        self, env_block, validation_report
    ) -> EvaluationManifest:
        return build_evaluation_manifest(
            evaluation_id="ev_" + "a" * 24,
            clustering_id="cl_" + "a" * 24,
            preprocessed_id="pp_xyz",
            dataset_id="ds_abc",
            ml_dataset_sha256="b" * 64,
            feature_set_sha256="c" * 64,
            preprocessing_config_sha256="d" * 64,
            algorithm="kmeans",
            algorithm_version="sklearn_1.5",
            algorithm_family="hard",
            n_samples=100,
            n_features=4,
            feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
            hyperparameters={"n_clusters": 4, "init": "k-means++"},
            seed_policy="stochastic",
            seed=42,
            noise_policy_used="exclude",
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_make_metrics(),
            n_samples_input=100,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            noise_count=None,
            noise_ratio=None,
            config_sha256="e" * 64,
            environment=env_block,
            log_file="ev_xx.log",
            validation_report=validation_report,
            readonly_paths=["data/raw/primary", "data/processed"],
        )

    def test_write_then_read(self, env_block, validation_report, tmp_path: Path) -> None:
        original = self._make_manifest(env_block, validation_report)
        path = tmp_path / "evaluation_manifest.json"
        write_evaluation_manifest(original, path)
        assert path.exists()
        # No leftover .tmp file
        assert not (path.with_suffix(path.suffix + ".tmp")).exists()
        reloaded = read_evaluation_manifest(path)
        assert reloaded.evaluation_id == original.evaluation_id
        assert reloaded.algorithm == original.algorithm
        assert reloaded.metrics.entries["silhouette"].value == 0.372
        assert reloaded.research_safety.automatically_promoted_to_research is False
        assert reloaded.environment.python == "3.14.4"
        assert reloaded.validation_report.all_passed is True

    def test_atomic_write_no_tmp_on_success(
        self, env_block, validation_report, tmp_path: Path
    ) -> None:
        m = self._make_manifest(env_block, validation_report)
        path = tmp_path / "m.json"
        write_evaluation_manifest(m, path)
        assert not (path.with_suffix(path.suffix + ".tmp")).exists()
        assert path.exists()

    def test_atomic_write_no_partial_on_failure(
        self, env_block, validation_report, tmp_path: Path, monkeypatch
    ) -> None:
        """Mock tmp.replace to raise; assert no manifest written and tmp cleaned."""
        m = self._make_manifest(env_block, validation_report)
        path = tmp_path / "m.json"

        def _raise_replace(self_path, other):  # type: ignore[no-untyped-def]
            raise OSError("simulated crash mid-rename")

        monkeypatch.setattr("pathlib.Path.replace", _raise_replace)
        with pytest.raises(OSError):
            write_evaluation_manifest(m, path)
        # Manifest not visible
        assert not path.exists()
        # tmp file cleaned up
        assert not (path.with_suffix(path.suffix + ".tmp")).exists()

    def test_read_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(EvaluationManifestError):
            read_evaluation_manifest(tmp_path / "nonexistent.json")

    def test_read_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not valid", encoding="utf-8")
        with pytest.raises(EvaluationManifestError):
            read_evaluation_manifest(path)

    def test_read_missing_required_field_raises(
        self, env_block, validation_report, tmp_path: Path
    ) -> None:
        m = self._make_manifest(env_block, validation_report)
        path = tmp_path / "m.json"
        write_evaluation_manifest(m, path)
        # Strip a required field
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        del data["algorithm"]
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh)
        with pytest.raises(EvaluationManifestError):
            read_evaluation_manifest(path)

    def test_round_trip_dbscan_manifest(
        self, env_block, validation_report, tmp_path: Path
    ) -> None:
        m = build_evaluation_manifest(
            evaluation_id="ev_" + "a" * 24,
            clustering_id="cl_" + "a" * 24,
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
            feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
            hyperparameters={"eps": 0.5, "min_samples": 5},
            seed_policy="deterministic",
            seed=None,
            noise_policy_used="exclude",
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_make_metrics(
                silhouette_value=0.281,
                dbi_value=1.402,
                ch_value=872.1,
            ),
            n_samples_input=1000,
            n_samples_used_for_compute=300,
            n_clusters_realized=2,
            noise_count=700,
            noise_ratio=0.7,
            config_sha256="e" * 64,
            environment=env_block,
            log_file="ev_xx.log",
            validation_report=validation_report,
            readonly_paths=["data/raw/primary"],
        )
        path = tmp_path / "dbscan.json"
        write_evaluation_manifest(m, path)
        reloaded = read_evaluation_manifest(path)
        assert reloaded.noise_count == 700
        assert reloaded.noise_ratio == 0.7
        assert reloaded.n_samples_used_for_compute == 300
        assert reloaded.algorithm_family == "density_based"


# ---------------------------------------------------------------------------
# Field classification
# ---------------------------------------------------------------------------


class TestFieldClassification:
    def test_stable_field_names_includes_canonical(self) -> None:
        stable = stable_field_names()
        for key in (
            "clustering_id",
            "preprocessed_id",
            "dataset_id",
            "ml_dataset_sha256",
            "noise_policy_used",
            "metric_set",
            "metrics",
            "config_sha256",
        ):
            assert key in stable, f"{key} should be in stable fields"

    def test_runtime_field_names_includes_time(self) -> None:
        runtime = runtime_field_names()
        for key in ("created_utc", "last_seen_utc", "environment"):
            assert key in runtime, f"{key} should be in runtime fields"

    def test_stable_runtime_disjoint(self) -> None:
        assert stable_field_names().isdisjoint(runtime_field_names())


# ---------------------------------------------------------------------------
# Manifest to dict
# ---------------------------------------------------------------------------


class TestManifestToDict:
    def test_json_serializable(
        self, env_block, validation_report
    ) -> None:
        m = build_evaluation_manifest(
            evaluation_id="ev_" + "a" * 24,
            clustering_id="cl_" + "a" * 24,
            preprocessed_id="pp_xyz",
            dataset_id="ds_abc",
            ml_dataset_sha256="b" * 64,
            feature_set_sha256="c" * 64,
            preprocessing_config_sha256="d" * 64,
            algorithm="kmeans",
            algorithm_version="sklearn_1.5",
            algorithm_family="hard",
            n_samples=100,
            n_features=4,
            feature_set=["Recency", "Frequency", "Monetary", "Tenure"],
            hyperparameters={"n_clusters": 4},
            seed_policy="stochastic",
            seed=42,
            noise_policy_used="exclude",
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_make_metrics(),
            n_samples_input=100,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            noise_count=None,
            noise_ratio=None,
            config_sha256="e" * 64,
            environment=env_block,
            log_file="ev_xx.log",
            validation_report=validation_report,
            readonly_paths=["data/raw/primary"],
        )
        d = manifest_to_dict(m)
        # Round-trip via json.dumps without error
        serialised = json.dumps(d, default=str)
        assert "ev_" in serialised
        assert "silhouette" in serialised


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def test_now_utc_iso_format() -> None:
    s = now_utc_iso()
    assert isinstance(s, str)
    assert s.endswith("Z")
    assert "T" in s
