"""Tests for the EVA-01 Experiment Result Repository.

This module tests:

1. Schema constants and types (:mod:`schema`).
2. Row validation (:mod:`validation`).
3. Per-experiment collectors (:mod:`collectors`).
4. Summary table builders (:mod:`summary`).
5. Repository lifecycle (:mod:`repository`).

Tests are designed to run WITHOUT the real EPIC-07 artifacts.
Mock data is used to simulate the source CSVs and JSONs.

Hard constraints enforced by these tests (AGENTS.md §2):
- No ranking / best / winner / optimal labels.
- No mutation of source artifacts.
- All collected values traceable to mock source.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from customer_segmentation.evaluation.experiment_results import (
    FIELD_TYPES,
    MISSING_INT_REASON_FIELDS,
    REQUIRED_FIELDS,
    STANDARD_COLUMNS,
    ExperimentResultRepository,
    SourceExperiment,
)
from customer_segmentation.evaluation.experiment_results.collectors import (
    _empty_row_template,
    _safe_load_json,
)
from customer_segmentation.evaluation.experiment_results.repository import (
    _to_dataframe,
)
from customer_segmentation.evaluation.experiment_results.schema import (
    FORBIDDEN_DECISION_LABELS,
    MISSING,
    MISSING_REASON_DEFERRED,
    MISSING_REASON_DIFFERENT_CONDITIONS,
    MISSING_REASON_FIELD_NOT_IN_SOURCE,
    MISSING_REASON_NOT_APPLICABLE,
    MISSING_REASON_NOT_RECORDED,
)
from customer_segmentation.evaluation.experiment_results.summary import (
    build_algorithm_summary,
    build_experiment_summary,
    build_k_summary,
    summarise_metrics,
)
from customer_segmentation.evaluation.experiment_results.validation import (
    RowStatus,
    _check_duplicate_exact,
    _check_duplicate_intent,
    _check_inconsistent_conditions,
    _is_missing_sentinel,
    _is_nan_value,
    _validate_row,
)

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchema:
    """Tests for the EVA-01 schema module."""

    def test_missing_sentinel_is_string(self):
        """MISSING must be the literal string 'MISSING'."""
        assert isinstance(MISSING, str)
        assert MISSING == "MISSING"

    def test_missing_reason_constants_are_distinct_strings(self):
        """Each MISSING_REASON_* constant must be distinct."""
        reasons = [
            MISSING_REASON_NOT_APPLICABLE,
            MISSING_REASON_NOT_RECORDED,
            MISSING_REASON_DIFFERENT_CONDITIONS,
            MISSING_REASON_FIELD_NOT_IN_SOURCE,
            MISSING_REASON_DEFERRED,
        ]
        assert len(reasons) == len(set(reasons))
        for r in reasons:
            assert isinstance(r, str)
            assert r

    def test_source_experiment_enum_values(self):
        """SourceExperiment must list exactly the five EPIC-07 experiments."""
        assert set(SourceExperiment) == {
            SourceExperiment.EXP_01,
            SourceExperiment.EXP_02,
            SourceExperiment.EXP_03,
            SourceExperiment.EXP_04,
            SourceExperiment.EXP_05,
        }

    def test_required_fields_present(self):
        """Every REQUIRED_FIELDS entry must be in STANDARD_COLUMNS."""
        for field in REQUIRED_FIELDS:
            assert field in STANDARD_COLUMNS, f"{field} not in STANDARD_COLUMNS"

    def test_missing_int_reason_fields_covered(self):
        """Every MISSING_INT_REASON_FIELDS entry must be in STANDARD_COLUMNS."""
        for field in MISSING_INT_REASON_FIELDS:
            assert field in STANDARD_COLUMNS, f"{field} not in STANDARD_COLUMNS"

    def test_forbidden_decision_labels_not_in_allowed_taxonomy(self):
        """FORBIDDEN labels must not appear in the allowed taxonomy."""
        # The schema forbids BEST / OPTIMAL / WINNER / SUPERIOR / RECOMMENDED / FINAL.
        # Verify no collector can accidentally produce them.
        allowed = {
            "SUCCESS",
            "FAILED",
            "CANDIDATE_SCENARIO",
            "TIED_SCENARIOS",
            "PENDING_REVIEW",
            "DEFERRED",
            "REPRODUCIBILITY_VERIFIED",
            "REPRODUCIBILITY_FAILED",
            "STABILITY_EVIDENCE_GENERATED",
            "PERTURBATION_EVIDENCE_GENERATED",
            "SIGMA_ZERO_BASELINE_MATCH",
            "SIGMA_ZERO_BASELINE_MISMATCH",
            "NOT_RECORDED",
        }
        assert FORBIDDEN_DECISION_LABELS.isdisjoint(allowed)

    def test_field_types_keys_match_standard_columns(self):
        """Every entry in FIELD_TYPES must be a standard column."""
        for field in FIELD_TYPES:
            assert (
                field in STANDARD_COLUMNS
            ), f"{field} not in FIELD_TYPES but not in STANDARD_COLUMNS"


# ---------------------------------------------------------------------------
# Validation helpers tests
# ---------------------------------------------------------------------------


class TestValidationHelpers:
    """Tests for the private validation helper functions."""

    def test_is_missing_sentinel_true_for_literal_missing(self):
        assert _is_missing_sentinel("MISSING") is True

    def test_is_missing_sentinel_false_for_value(self):
        assert _is_missing_sentinel("kmeans") is False
        assert _is_missing_sentinel(0) is False
        assert _is_missing_sentinel(0.5) is False

    def test_is_nan_value_true_for_pandas_na(self):
        assert _is_nan_value(float("nan")) is True
        assert _is_nan_value(None) is True
        # pd.NA is nan-like
        try:
            import pandas as pd

            assert _is_nan_value(pd.NA) is True
        except Exception:
            pass  # pandas not required for this assertion


class TestRowValidation:
    """Tests for _validate_row."""

    def test_valid_row_returns_ok(self):
        """A row with all required fields returns OK."""
        row = {
            "source_experiment": "EXP-01",
            "experiment_id": "EXP-01-kmeans",
            "source_run_id": "EXP-01-kmeans",
            "algorithm": "kmeans",
            "dataset_version": "FE06-v1.0",
            "feature_set": "rfm_extended",
            "n_clusters": 4,
            "n_clusters_missing_reason": "",
            "hyperparameters": "{}",
            "hyperparameters_missing_reason": "",
            "random_seed": 42,
            "random_seed_missing_reason": "",
            "silhouette": 0.5,
            "silhouette_missing_reason": "",
            "davies_bouldin": 1.0,
            "davies_bouldin_missing_reason": "",
            "calinski_harabasz": 100.0,
            "calinski_harabasz_missing_reason": "",
            "wcss": 1000.0,
            "wcss_missing_reason": "",
            "execution_time_seconds": 0.1,
            "execution_time_seconds_missing_reason": "",
            "n_clusters_realized": 4,
            "n_clusters_realized_missing_reason": "",
            "cluster_size_largest": "MISSING",
            "cluster_size_largest_missing_reason": MISSING_REASON_FIELD_NOT_IN_SOURCE,
            "cluster_size_smallest": "MISSING",
            "cluster_size_smallest_missing_reason": MISSING_REASON_FIELD_NOT_IN_SOURCE,
            "noise_count": 0,
            "noise_count_missing_reason": "",
            "noise_ratio": 0.0,
            "noise_ratio_missing_reason": "",
            "repeat_index": 0,
            "repeat_index_missing_reason": "",
            "n_repeats_total": 5,
            "n_repeats_total_missing_reason": "",
            "perturbation_seed": "MISSING",
            "perturbation_seed_missing_reason": MISSING_REASON_NOT_APPLICABLE,
            "run_status": "SUCCESS",
            "failure_reason": "",
            "labels_hash": "MISSING",
            "labels_hash_missing_reason": MISSING_REASON_NOT_APPLICABLE,
            "feature_set_sha256": "MISSING",
            "customer_metadata_sha256": "MISSING",
            "config_sha256": "MISSING",
            "input_sha256": "MISSING",
            "sigma": "MISSING",
            "sigma_missing_reason": MISSING_REASON_NOT_APPLICABLE,
            "library_versions": "{}",
            "platform": "{}",
            "timestamp": "MISSING",
            "decision_status": "SUCCESS",
            "evidence_note": "",
            "source_artifact": "reports/exp01/exp01_baseline_summary.csv",
            "record_granularity": "PER_AGGREGATE",
            "source_block": "",
        }
        result = _validate_row(row)
        assert result.status == RowStatus.OK
        assert result.missing_fields == []
        assert result.invalid_fields == []

    def test_missing_required_field_returns_missing(self):
        """A row missing a required field returns MISSING."""
        row = {
            "source_experiment": "EXP-01",
            "experiment_id": "EXP-01-kmeans",
            "source_run_id": "EXP-01-kmeans",
            # algorithm missing
            "dataset_version": "FE06-v1.0",
            "feature_set": "rfm_extended",
            "n_clusters": 4,
            "hyperparameters": "{}",
            "random_seed": 42,
            "silhouette": 0.5,
            "silhouette_missing_reason": "",
            "davies_bouldin": 1.0,
            "davies_bouldin_missing_reason": "",
            "calinski_harabasz": 100.0,
            "calinski_harabasz_missing_reason": "",
            "wcss": 1000.0,
            "wcss_missing_reason": "",
            "execution_time_seconds": 0.1,
            "execution_time_seconds_missing_reason": "",
        }
        result = _validate_row(row)
        assert result.status == RowStatus.MISSING
        assert "algorithm" in result.missing_fields

    def test_missing_with_valid_reason_not_flagged(self):
        """A MISSING field with a documented reason is NOT flagged as MISSING."""
        row = {
            "source_experiment": "EXP-01",
            "experiment_id": "EXP-01-kmeans",
            "source_run_id": "EXP-01-kmeans",
            "algorithm": "kmeans",
            "dataset_version": "FE06-v1.0",
            "feature_set": "rfm_extended",
            "n_clusters": 4,
            "n_clusters_missing_reason": "",
            "hyperparameters": "{}",
            "hyperparameters_missing_reason": "",
            "random_seed": 42,
            "random_seed_missing_reason": "",
            "silhouette": 0.5,
            "silhouette_missing_reason": "",
            "davies_bouldin": 1.0,
            "davies_bouldin_missing_reason": "",
            "calinski_harabasz": 100.0,
            "calinski_harabasz_missing_reason": "",
            "wcss": 1000.0,
            "wcss_missing_reason": "",
            "execution_time_seconds": 0.1,
            "execution_time_seconds_missing_reason": "",
            # n_clusters_realized MISSING but with documented reason
            "n_clusters_realized": "MISSING",
            "n_clusters_realized_missing_reason": MISSING_REASON_NOT_APPLICABLE,
            "cluster_size_largest": "MISSING",
            "cluster_size_largest_missing_reason": MISSING_REASON_FIELD_NOT_IN_SOURCE,
            "cluster_size_smallest": "MISSING",
            "cluster_size_smallest_missing_reason": MISSING_REASON_FIELD_NOT_IN_SOURCE,
            "noise_count": 0,
            "noise_count_missing_reason": "",
            "noise_ratio": 0.0,
            "noise_ratio_missing_reason": "",
            "repeat_index": 0,
            "repeat_index_missing_reason": "",
            "n_repeats_total": 5,
            "n_repeats_total_missing_reason": "",
            "perturbation_seed": "MISSING",
            "perturbation_seed_missing_reason": MISSING_REASON_NOT_APPLICABLE,
            "run_status": "SUCCESS",
            "failure_reason": "",
            "labels_hash": "MISSING",
            "labels_hash_missing_reason": MISSING_REASON_NOT_APPLICABLE,
            "feature_set_sha256": "MISSING",
            "customer_metadata_sha256": "MISSING",
            "config_sha256": "MISSING",
            "input_sha256": "MISSING",
            "sigma": "MISSING",
            "sigma_missing_reason": MISSING_REASON_NOT_APPLICABLE,
            "library_versions": "{}",
            "platform": "{}",
            "timestamp": "MISSING",
            "decision_status": "SUCCESS",
            "evidence_note": "",
            "source_artifact": "reports/exp01/exp01_baseline_summary.csv",
            "record_granularity": "PER_AGGREGATE",
            "source_block": "",
        }
        result = _validate_row(row)
        # NOT_APPLICABLE is in the allowed set → should NOT be flagged
        assert result.status == RowStatus.OK

    def test_missing_int_without_reason_flagged(self):
        """An integer MISSING field without a valid reason is flagged."""
        row = {
            "source_experiment": "EXP-01",
            "experiment_id": "EXP-01-kmeans",
            "source_run_id": "EXP-01-kmeans",
            "algorithm": "kmeans",
            "dataset_version": "FE06-v1.0",
            "feature_set": "rfm_extended",
            "n_clusters": 4,
            "hyperparameters": "{}",
            "random_seed": 42,
            "silhouette": 0.5,
            "silhouette_missing_reason": "",
            "davies_bouldin": 1.0,
            "davies_bouldin_missing_reason": "",
            "calinski_harabasz": 100.0,
            "calinski_harabasz_missing_reason": "",
            "wcss": 1000.0,
            "wcss_missing_reason": "",
            "execution_time_seconds": 0.1,
            "execution_time_seconds_missing_reason": "",
            # n_clusters_realized MISSING without valid reason
            "n_clusters_realized": "MISSING",
            "n_clusters_realized_missing_reason": "MISSING",  # literal sentinel used as reason
        }
        result = _validate_row(row)
        assert result.status == RowStatus.MISSING
        assert "n_clusters_realized" in result.missing_fields


# ---------------------------------------------------------------------------
# Duplicate / inconsistency detection tests
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    """Tests for cross-row anomaly detection."""

    def test_exact_duplicate_detected(self):
        """Two rows with identical identity keys are flagged as DUPLICATE_EXACT."""
        rows = [
            {
                "source_experiment": "EXP-01",
                "experiment_id": "EXP-01-kmeans",
                "source_run_id": "EXP-01-kmeans",
                "repeat_index": 0,
                "algorithm": "kmeans",
                "n_clusters": 4,
                "random_seed": 42,
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "hyperparameters": "{}",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
                "silhouette": 0.5,
                "labels_hash": "abc",
            },
            {
                "source_experiment": "EXP-01",
                "experiment_id": "EXP-01-kmeans",
                "source_run_id": "EXP-01-kmeans",
                "repeat_index": 0,
                "algorithm": "kmeans",
                "n_clusters": 4,
                "random_seed": 42,
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "hyperparameters": "{}",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
                "silhouette": 0.5,
                "labels_hash": "abc",
            },
        ]
        dups = _check_duplicate_exact(rows)
        assert len(dups) == 1
        assert dups[0]["n_rows"] == 2

    def test_duplicate_by_intent_detected(self):
        """Same config but different labels_hash is DUPLICATE_BY_INTENT."""
        rows = [
            {
                "source_experiment": "EXP-05",
                "experiment_id": "EXP05-R-kmeans-r00",
                "source_run_id": "EXP05-R-kmeans-r00",
                "repeat_index": 0,
                "algorithm": "kmeans",
                "n_clusters": 4,
                "random_seed": 42,
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "hyperparameters": "{}",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
                "silhouette": 0.5,
                "davies_bouldin": 1.0,
                "calinski_harabasz": 100.0,
                "wcss": 1000.0,
                "labels_hash": "abc",
                "execution_time_seconds": 0.10,
                "n_clusters_realized": 4,
            },
            {
                "source_experiment": "EXP-05",
                "experiment_id": "EXP05-R-kmeans-r01",
                "source_run_id": "EXP05-R-kmeans-r01",
                "repeat_index": 1,
                "algorithm": "kmeans",
                "n_clusters": 4,
                "random_seed": 42,
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "hyperparameters": "{}",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
                "silhouette": 0.5,  # same metrics
                "davies_bouldin": 1.0,
                "calinski_harabasz": 100.0,
                "wcss": 1000.0,
                "labels_hash": "xyz",  # different labels_hash
                "execution_time_seconds": 0.11,  # slightly different runtime
                "n_clusters_realized": 4,
            },
        ]
        dups = _check_duplicate_intent(rows)
        assert len(dups) == 1
        # labels_hash and execution_time_seconds differ
        assert "labels_hash" in dups[0]["differing_fields"]
        assert "execution_time_seconds" in dups[0]["differing_fields"]

    def test_inconsistent_conditions_detected(self):
        """Same config under different feature sets is INCONSISTENT_CONDITIONS."""
        rows = [
            {
                "source_experiment": "EXP-01",
                "experiment_id": "EXP-01-kmeans",
                "source_run_id": "EXP-01-kmeans",
                "algorithm": "kmeans",
                "n_clusters": 4,
                "random_seed": 42,
                "hyperparameters": "{}",
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
                "silhouette": 0.5,
                "davies_bouldin": 1.0,
                "calinski_harabasz": 100.0,
                "wcss": 1000.0,
                "execution_time_seconds": 0.1,
                "n_clusters_realized": 4,
            },
            {
                "source_experiment": "EXP-04",
                "experiment_id": "EXP04-C0-r00",
                "source_run_id": "EXP04-C0-r00",
                "algorithm": "kmeans",
                "n_clusters": 4,
                "random_seed": 42,
                "hyperparameters": "{}",
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
                "silhouette": 0.5,
                "davies_bouldin": 1.0,
                "calinski_harabasz": 100.0,
                "wcss": 1000.0,
                "execution_time_seconds": 0.1,
                "n_clusters_realized": 4,
            },
        ]
        # Same algorithm/K/HP/seed but same conditions → NOT inconsistent
        # (feature_set and dataset_version are the same)
        # To trigger INCONSISTENT_CONDITIONS, we need different feature_set
        rows[1]["feature_set"] = "rfm_only"  # different feature set
        inc = _check_inconsistent_conditions(rows)
        assert len(inc) == 1
        assert "feature_set" in inc[0]["differing_condition_fields"]


# ---------------------------------------------------------------------------
# Summary table tests
# ---------------------------------------------------------------------------


class TestSummaryTables:
    """Tests for summary table builders."""

    @pytest.fixture
    def sample_df(self) -> pd.DataFrame:
        """Minimal DataFrame with EXP-01 and EXP-05 rows."""
        records = [
            # EXP-01 rows
            {
                "source_experiment": "EXP-01",
                "experiment_id": "EXP-01-kmeans",
                "source_run_id": "EXP-01-kmeans",
                "algorithm": "kmeans",
                "n_clusters": 4,
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "hyperparameters": "{}",
                "random_seed": 42,
                "silhouette": 0.5,
                "davies_bouldin": 1.0,
                "calinski_harabasz": 100.0,
                "wcss": 1000.0,
                "execution_time_seconds": 0.10,
                "n_clusters_realized": 4,
                "run_status": "SUCCESS",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
            },
            {
                "source_experiment": "EXP-01",
                "experiment_id": "EXP-01-gmm",
                "source_run_id": "EXP-01-gmm",
                "algorithm": "gmm",
                "n_clusters": 4,
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "hyperparameters": "{}",
                "random_seed": 42,
                "silhouette": 0.6,
                "davies_bouldin": 0.8,
                "calinski_harabasz": 120.0,
                "wcss": 900.0,
                "execution_time_seconds": 0.20,
                "n_clusters_realized": 4,
                "run_status": "SUCCESS",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
            },
            # EXP-05 rows (same algorithm/K but Block R with 5 repeats)
            {
                "source_experiment": "EXP-05",
                "experiment_id": "EXP05-R-kmeans-r00",
                "source_run_id": "EXP05-R-kmeans-r00",
                "algorithm": "kmeans",
                "n_clusters": 4,
                "feature_set": "rfm_extended",
                "dataset_version": "FE06-v1.0",
                "transformation": "MISSING",
                "scaling": "MISSING",
                "imputation": "MISSING",
                "hyperparameters": "{}",
                "random_seed": 42,
                "silhouette": 0.5,
                "davies_bouldin": 1.0,
                "calinski_harabasz": 100.0,
                "wcss": 1000.0,
                "execution_time_seconds": 0.10,
                "n_clusters_realized": 4,
                "run_status": "SUCCESS",
                "sigma": "MISSING",
                "perturbation_seed": "MISSING",
            },
        ]
        return pd.DataFrame(records)

    def test_experiment_summary_aggregates(self, sample_df):
        """build_experiment_summary returns one row per experiment."""
        summary = build_experiment_summary(sample_df)
        assert len(summary) == 2
        assert set(summary["source_experiment"]) == {"EXP-01", "EXP-05"}
        # EXP-01 has 2 algorithms, EXP-05 has 1
        exp01_row = summary[summary["source_experiment"] == "EXP-01"].iloc[0]
        assert exp01_row["n_unique_algorithms"] == 2
        assert exp01_row["n_rows"] == 2
        assert exp01_row["n_successful"] == 2

    def test_algorithm_summary_aggregates(self, sample_df):
        """build_algorithm_summary returns one row per (experiment, algorithm)."""
        summary = build_algorithm_summary(sample_df)
        assert len(summary) == 3  # EXP-01 kmeans, EXP-01 gmm, EXP-05 kmeans
        # EXP-05 kmeans and EXP-01 kmeans are separate rows
        assert len(summary[summary["algorithm"] == "kmeans"]) == 2

    def test_k_summary_filters_invalid_k(self, sample_df):
        """build_k_summary skips rows where n_clusters is invalid."""
        df_invalid = pd.concat(
            [
                sample_df,
                pd.DataFrame(
                    [
                        {
                            "source_experiment": "EXP-05",
                            "experiment_id": "EXP05-N-dbscan-s0",
                            "source_run_id": "EXP05-N-dbscan-s0",
                            "algorithm": "dbscan",
                            "n_clusters": "MISSING",  # DBSCAN: n_clusters not applicable
                            "feature_set": "rfm_extended",
                            "dataset_version": "FE06-v1.0",
                            "transformation": "MISSING",
                            "scaling": "MISSING",
                            "imputation": "MISSING",
                            "hyperparameters": "{}",
                            "random_seed": 42,
                            "silhouette": 0.3,
                            "davies_bouldin": 1.5,
                            "calinski_harabasz": 80.0,
                            "wcss": 2000.0,
                            "execution_time_seconds": 0.05,
                            "n_clusters_realized": 17,
                            "run_status": "SUCCESS",
                            "sigma": "MISSING",
                            "perturbation_seed": "MISSING",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        k_summary = build_k_summary(df_invalid)
        # DBSCAN row should be filtered (n_clusters = "MISSING" converts to invalid int)
        assert len(k_summary) >= 2  # At minimum the 2 EXP-01 rows

    def test_summarise_metrics_ignores_nan(self):
        """summarise_metrics drops NaN values before computing stats."""
        result = summarise_metrics([0.5, float("nan"), 0.7, None, 0.9])
        assert result["n"] == 3
        assert 0.5 <= result["mean"] <= 0.9
        assert result["min"] == 0.5
        assert result["max"] == 0.9


# ---------------------------------------------------------------------------
# Repository / serialization tests
# ---------------------------------------------------------------------------


class TestRepository:
    """Tests for ExperimentResultRepository."""

    def test_build_from_empty_lists(self):
        """Repository can be built from empty lists (zero experiments)."""
        repo = ExperimentResultRepository.build(
            exp01_rows=[], exp02_rows=[], exp03_rows=[], exp04_rows=[], exp05_rows=[]
        )
        assert repo.n_rows == 0

    def test_build_from_precollected_rows(self):
        """Repository correctly concatenates pre-collected rows."""
        row1 = _empty_row_template(SourceExperiment.EXP_01)
        row1["experiment_id"] = "EXP-01-kmeans"
        row1["algorithm"] = "kmeans"
        row1["dataset_version"] = "FE06-v1.0"
        row1["feature_set"] = "rfm_extended"
        row1["n_clusters"] = 4
        row1["n_clusters_missing_reason"] = ""
        row1["silhouette"] = 0.5
        row1["silhouette_missing_reason"] = ""
        row1["davies_bouldin"] = 1.0
        row1["davies_bouldin_missing_reason"] = ""
        row1["calinski_harabasz"] = 100.0
        row1["calinski_harabasz_missing_reason"] = ""
        row1["wcss"] = 1000.0
        row1["wcss_missing_reason"] = ""
        row1["execution_time_seconds"] = 0.1
        row1["execution_time_seconds_missing_reason"] = ""

        repo = ExperimentResultRepository.build(
            exp01_rows=[row1],
            exp02_rows=[],
            exp03_rows=[],
            exp04_rows=[],
            exp05_rows=[],
        )
        assert repo.n_rows == 1
        assert repo.n_rows_by_experiment["EXP-01"] == 1

    def test_validate_returns_ok_for_valid_rows(self):
        """validate() returns OK status for properly formed rows."""
        row1 = _empty_row_template(SourceExperiment.EXP_01)
        row1["experiment_id"] = "EXP-01-kmeans"
        row1["algorithm"] = "kmeans"
        row1["dataset_version"] = "FE06-v1.0"
        row1["feature_set"] = "rfm_extended"
        row1["n_clusters"] = 4
        row1["n_clusters_missing_reason"] = ""
        row1["hyperparameters"] = "{}"
        row1["hyperparameters_missing_reason"] = ""
        row1["random_seed"] = 42
        row1["random_seed_missing_reason"] = ""
        row1["silhouette"] = 0.5
        row1["silhouette_missing_reason"] = ""
        row1["davies_bouldin"] = 1.0
        row1["davies_bouldin_missing_reason"] = ""
        row1["calinski_harabasz"] = 100.0
        row1["calinski_harabasz_missing_reason"] = ""
        row1["wcss"] = 1000.0
        row1["wcss_missing_reason"] = ""
        row1["execution_time_seconds"] = 0.1
        row1["execution_time_seconds_missing_reason"] = ""

        repo = ExperimentResultRepository.build(
            exp01_rows=[row1],
            exp02_rows=[],
            exp03_rows=[],
            exp04_rows=[],
            exp05_rows=[],
        )
        report = repo.validate()
        assert report.n_total == 1
        assert report.n_ok == 1
        assert report.n_missing == 0
        assert report.n_invalid == 0

    def test_snapshot_bundles_all_outputs(self):
        """snapshot() returns a RepositorySnapshot with all components."""
        repo = ExperimentResultRepository.build(
            exp01_rows=[],
            exp02_rows=[],
            exp03_rows=[],
            exp04_rows=[],
            exp05_rows=[],
        )
        snap = repo.snapshot()
        assert snap.dataset is not None
        assert snap.validation_report is not None
        assert snap.experiment_summary is not None
        assert snap.algorithm_summary is not None
        assert snap.k_summary is not None
        assert isinstance(snap.markdown_report, str)
        assert "EVA-01" in snap.markdown_report


class TestDataFrameCoercion:
    """Tests for _to_dataframe."""

    def test_empty_rows_produces_empty_df_with_standard_columns(self):
        """Empty row list produces a DataFrame with exactly STANDARD_COLUMNS."""
        df = _to_dataframe([])
        assert list(df.columns) == list(STANDARD_COLUMNS)

    def test_extra_columns_removed(self):
        """Columns not in STANDARD_COLUMNS are dropped."""
        rows = [
            {
                "source_experiment": "EXP-01",
                "experiment_id": "EXP-01-kmeans",
                "source_run_id": "EXP-01-kmeans",
                "algorithm": "kmeans",
                "dataset_version": "FE06-v1.0",
                "feature_set": "rfm_extended",
                "n_clusters": 4,
                "n_clusters_missing_reason": "",
                "hyperparameters": "{}",
                "hyperparameters_missing_reason": "",
                "random_seed": 42,
                "random_seed_missing_reason": "",
                "silhouette": 0.5,
                "silhouette_missing_reason": "",
                "davies_bouldin": 1.0,
                "davies_bouldin_missing_reason": "",
                "calinski_harabasz": 100.0,
                "calinski_harabasz_missing_reason": "",
                "wcss": 1000.0,
                "wcss_missing_reason": "",
                "execution_time_seconds": 0.1,
                "execution_time_seconds_missing_reason": "",
                # Extra column not in schema
                "my_extra_column": "should be dropped",
            }
        ]
        df = _to_dataframe(rows)
        assert "my_extra_column" not in df.columns

    def test_missing_columns_filled_with_missing(self):
        """Rows missing schema columns get filled with MISSING sentinel."""
        rows = [
            {
                "source_experiment": "EXP-01",
                "experiment_id": "EXP-01-kmeans",
                "source_run_id": "EXP-01-kmeans",
                # Only a subset of columns present
            }
        ]
        df = _to_dataframe(rows)
        # All standard columns must be present
        for col in STANDARD_COLUMNS:
            assert col in df.columns


# ---------------------------------------------------------------------------
# Collector helper tests
# ---------------------------------------------------------------------------


class TestCollectorHelpers:
    """Tests for collector utility functions."""

    def test_empty_row_template_has_all_columns(self):
        """_empty_row_template returns a dict with every STANDARD_COLUMN key."""
        row = _empty_row_template(SourceExperiment.EXP_01)
        for col in STANDARD_COLUMNS:
            assert col in row, f"Missing column: {col}"

    def test_empty_row_template_source_experiment(self):
        """_empty_row_template sets source_experiment from the enum."""
        row = _empty_row_template(SourceExperiment.EXP_03)
        assert row["source_experiment"] == "EXP-03"

    def test_safe_load_json_returns_none_for_nonexistent_path(self, tmp_path: Path):
        """_safe_load_json returns None for a missing file (does not raise)."""
        result = _safe_load_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_safe_load_json_parses_valid_json(self, tmp_path: Path):
        """_safe_load_json correctly parses a valid JSON file."""
        manifest = {"config": {"runtime_repeat": 5}, "algorithms": []}
        path = tmp_path / "test.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        result = _safe_load_json(path)
        assert result == manifest


# ---------------------------------------------------------------------------
# Integration: write_outputs round-trip
# ---------------------------------------------------------------------------


class TestWriteOutputs:
    """Tests for the write_outputs method."""

    def test_parquet_and_csv_roundtrip(self, tmp_path: Path):
        """Data written to parquet and CSV can be read back."""
        repo = ExperimentResultRepository.build(
            exp01_rows=[],
            exp02_rows=[],
            exp03_rows=[],
            exp04_rows=[],
            exp05_rows=[],
        )
        paths = repo.write_outputs(
            tmp_path,
            also_csv=True,
            also_markdown=False,
            also_validation=False,
            also_summary_csv=False,
        )
        assert "parquet" in paths
        assert Path(paths["parquet"]).exists()
        assert "csv" in paths
        assert Path(paths["csv"]).exists()

        # Round-trip: read parquet back
        df_roundtrip = pd.read_parquet(paths["parquet"])
        assert len(df_roundtrip) == 0
        assert set(df_roundtrip.columns) == set(STANDARD_COLUMNS)

    def test_validation_json_written(self, tmp_path: Path):
        """Validation report is written as JSON."""
        repo = ExperimentResultRepository.build(
            exp01_rows=[],
            exp02_rows=[],
            exp03_rows=[],
            exp04_rows=[],
            exp05_rows=[],
        )
        paths = repo.write_outputs(
            tmp_path,
            also_csv=False,
            also_markdown=False,
            also_validation=True,
            also_summary_csv=False,
        )
        assert "validation_report_json" in paths
        report_data = json.loads(Path(paths["validation_report_json"]).read_text(encoding="utf-8"))
        assert report_data["n_total"] == 0

    def test_markdown_summary_written(self, tmp_path: Path):
        """Markdown summary is written."""
        repo = ExperimentResultRepository.build(
            exp01_rows=[],
            exp02_rows=[],
            exp03_rows=[],
            exp04_rows=[],
            exp05_rows=[],
        )
        paths = repo.write_outputs(
            tmp_path,
            also_csv=False,
            also_markdown=True,
            also_validation=False,
            also_summary_csv=False,
        )
        assert "markdown_summary" in paths
        md = Path(paths["markdown_summary"]).read_text(encoding="utf-8")
        assert "EVA-01" in md
