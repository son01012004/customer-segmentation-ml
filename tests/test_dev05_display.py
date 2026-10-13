"""Tests for the DEV-05 display module + R-EVAL-08/R-EVAL-15 conformance."""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.evaluation.display import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
    check_no_banned_substrings,
    format_manifest_path,
    format_metrics_table,
)
from customer_segmentation.prototype.evaluation.manifest import (
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    ResearchSafetyBlock,
    make_computation_error_entry,
    make_not_applicable_entry,
    make_valid_entry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def three_valid_metrics() -> EvaluationMetricsResult:
    return EvaluationMetricsResult(
        entries={
            "silhouette": make_valid_entry("silhouette", 0.5),
            "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
            "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
        }
    )


@pytest.fixture
def mixed_metrics() -> EvaluationMetricsResult:
    return EvaluationMetricsResult(
        entries={
            "silhouette": make_valid_entry("silhouette", 0.5),
            "davies_bouldin": make_not_applicable_entry(
                "davies_bouldin", "ALL_NOISE"
            ),
            "calinski_harabasz": make_computation_error_entry(
                "calinski_harabasz", "SKLEARN_EXCEPTION"
            ),
        }
    )


# ---------------------------------------------------------------------------
# format_metrics_table
# ---------------------------------------------------------------------------


class TestFormatMetricsTable:
    def test_table_contains_three_metric_names(
        self, three_valid_metrics
    ) -> None:
        text = format_metrics_table(three_valid_metrics)
        for name in ("silhouette", "davies_bouldin", "calinski_harabasz"):
            assert name in text

    def test_table_shows_valid_status(
        self, three_valid_metrics
    ) -> None:
        text = format_metrics_table(three_valid_metrics)
        assert "VALID_VALUE" in text

    def test_mixed_table_uses_placeholder(
        self, mixed_metrics
    ) -> None:
        text = format_metrics_table(mixed_metrics)
        assert "--" in text
        assert "NOT_APPLICABLE" in text
        assert "COMPUTATION_ERROR" in text

    def test_custom_placeholder(self, mixed_metrics) -> None:
        text = format_metrics_table(
            mixed_metrics, missing_value_placeholder="n/a"
        )
        # The custom placeholder appears in the value column.
        assert "n/a" in text

    def test_table_has_72_char_separator(
        self, three_valid_metrics
    ) -> None:
        text = format_metrics_table(three_valid_metrics)
        assert "-" * 72 in text

    def test_output_no_banned_substrings_default_disclaimer(
        self, three_valid_metrics
    ) -> None:
        """format_metrics_table alone must not emit banned words."""
        text = format_metrics_table(three_valid_metrics)
        found = check_no_banned_substrings(text)
        assert found == [], f"banned words found: {found}"


# ---------------------------------------------------------------------------
# format_manifest_path
# ---------------------------------------------------------------------------


class TestFormatManifestPath:
    def _make_manifest(self) -> EvaluationManifest:
        from customer_segmentation.prototype.evaluation.manifest import (
            build_evaluation_manifest,
        )

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
            feature_set=["a", "b", "c", "d"],
            hyperparameters={"n_clusters": 4},
            seed_policy="stochastic",
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
            n_samples_input=100,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            noise_count=None,
            noise_ratio=None,
            config_sha256="e" * 64,
            environment=EnvironmentBlock(
                python="3.14.4", platform="Linux", release="7.0.0",
                machine="x86_64", key_libraries={}
            ),
            log_file="ev_xx.log",
            validation_report=EvaluationValidationReport(all_passed=True),
            readonly_paths=["data/raw/primary"],
        )

    def test_contains_evaluation_id(self) -> None:
        m = self._make_manifest()
        text = format_manifest_path(m)
        assert m.evaluation_id in text

    def test_contains_algorithm(self) -> None:
        m = self._make_manifest()
        text = format_manifest_path(m)
        assert "kmeans" in text

    def test_contains_n_samples(self) -> None:
        m = self._make_manifest()
        text = format_manifest_path(m)
        assert "100" in text

    def test_no_banned_substrings(self) -> None:
        m = self._make_manifest()
        text = format_manifest_path(m)
        found = check_no_banned_substrings(text)
        assert found == []


# ---------------------------------------------------------------------------
# check_no_banned_substrings (R-EVAL-08 / R-EVAL-15)
# ---------------------------------------------------------------------------


class TestCheckNoBannedSubstrings:
    def test_clean_text_passes(self) -> None:
        text = "Silhouette: 0.5. Davies-Bouldin: 1.0. Calinski-Harabasz: 100.0"
        found = check_no_banned_substrings(text)
        assert found == []

    def test_detects_banned_word(self) -> None:
        text = "The best algorithm is kmeans"
        found = check_no_banned_substrings(text)
        assert "best" in found

    def test_disclaimer_negation_allowed(self) -> None:
        text = f"some text. {DEFAULT_DISCLAIMER_TEXT}. more text."
        found = check_no_banned_substrings(text)
        assert found == []

    def test_disclaimer_plus_other_usage_fails(self) -> None:
        text = f"{DEFAULT_DISCLAIMER_TEXT} but this is the best approach"
        found = check_no_banned_substrings(text)
        assert "best" in found

    def test_detects_winner(self) -> None:
        found = check_no_banned_substrings("kmeans is the winner")
        assert "winner" in found

    def test_detects_optimal(self) -> None:
        found = check_no_banned_substrings("optimal configuration found")
        assert "optimal" in found

    def test_detects_recommended(self) -> None:
        found = check_no_banned_substrings("the recommended approach is good")
        assert "recommended" in found

    def test_detects_ranking(self) -> None:
        found = check_no_banned_substrings("according to the ranking")
        assert "ranking" in found

    def test_detects_composite_score(self) -> None:
        found = check_no_banned_substrings("composite_score is 0.8")
        assert "composite_score" in found

    def test_case_insensitive(self) -> None:
        found = check_no_banned_substrings("The BEST algorithm")
        assert "best" in found

    def test_custom_disclaimer(self) -> None:
        text = "the recommended approach is good"
        # Default disclaimer doesn't include "recommended" so it shows up.
        found = check_no_banned_substrings(text)
        assert "recommended" in found
        # Custom disclaimer that explicitly negates the phrase:
        #   "we disavow recommended choices"
        # The disclaimer mentions "recommended" once, but the text
        # mentions it independently, so it should still be detected.
        custom_dl = "we disavow recommended choices"
        found2 = check_no_banned_substrings(text, disclaimer=custom_dl)
        # Even with a custom disclaimer, banned words in the text are
        # detected (the disclaimer only excludes the disclaimer phrase
        # itself from being flagged).
        assert "recommended" in found2

    def test_banned_substrings_constant_matches_module(self) -> None:
        assert "best" in BANNED_SUBSTRINGS
        assert "winner" in BANNED_SUBSTRINGS
        assert "ranking" in BANNED_SUBSTRINGS
