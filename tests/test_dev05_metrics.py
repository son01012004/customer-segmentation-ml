"""Tests for the DEV-05 metrics module."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

from customer_segmentation.prototype.evaluation.metrics import (
    DBSCAN_NOISE_LABEL,
    compute_internal_metrics,
)
from customer_segmentation.prototype.evaluation.scope import (
    METRIC_NAMES,
    MetricName,
    MetricReason,
    MetricStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_cluster_X() -> np.ndarray:
    """8-row, 2-feature matrix forming 2 well-separated blobs."""
    return np.array(
        [
            [1.0, 1.0],
            [1.0, 2.0],
            [2.0, 1.0],
            [2.0, 2.0],
            [10.0, 10.0],
            [10.0, 11.0],
            [11.0, 10.0],
            [11.0, 11.0],
        ]
    )


@pytest.fixture
def two_cluster_labels() -> np.ndarray:
    return np.array([0, 0, 0, 0, 1, 1, 1, 1])


@pytest.fixture
def dbscan_with_noise_X() -> np.ndarray:
    """12-row matrix: 4 noise rows + 2 clusters of 4 each."""
    base = np.array(
        [
            [1.0, 1.0],
            [1.0, 2.0],
            [2.0, 1.0],
            [2.0, 2.0],
            [10.0, 10.0],
            [10.0, 11.0],
            [11.0, 10.0],
            [11.0, 11.0],
        ]
    )
    noise = np.array(
        [
            [50.0, 50.0],
            [51.0, 51.0],
            [52.0, 52.0],
            [53.0, 53.0],
        ]
    )
    return np.vstack([base, noise])


@pytest.fixture
def dbscan_with_noise_labels() -> np.ndarray:
    return np.array([0, 0, 0, 0, 1, 1, 1, 1, -1, -1, -1, -1])


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_three_metrics_valid_for_two_clusters(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        assert set(result.entries.keys()) == METRIC_NAMES
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.VALID_VALUE.value
            assert entry.value is not None
            assert entry.reason == MetricReason.COMPUTED.value
            assert entry.is_diagnostic_only is False
            assert entry.lower_is_better == (
                name == MetricName.DAVIES_BOULDIN.value
            )

    def test_silhouette_value_matches_sklearn_direct(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        """Values must match a direct sklearn call within 1e-6."""
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        expected = float(silhouette_score(two_cluster_X, two_cluster_labels))
        actual = result.entries["silhouette"].value
        assert actual is not None
        assert abs(actual - expected) < 1e-6

    def test_dbi_value_matches_sklearn_direct(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        expected = float(davies_bouldin_score(two_cluster_X, two_cluster_labels))
        actual = result.entries["davies_bouldin"].value
        assert actual is not None
        assert abs(actual - expected) < 1e-6

    def test_ch_value_matches_sklearn_direct(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        expected = float(calinski_harabasz_score(two_cluster_X, two_cluster_labels))
        actual = result.entries["calinski_harabasz"].value
        assert actual is not None
        assert abs(actual - expected) < 1e-6

    def test_silhouette_in_minus_1_1_range(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        v = result.entries["silhouette"].value
        assert v is not None
        assert -1.0 <= v <= 1.0

    def test_dbi_non_negative(self, two_cluster_X, two_cluster_labels) -> None:
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        v = result.entries["davies_bouldin"].value
        assert v is not None
        assert v >= 0.0

    def test_ch_non_negative(self, two_cluster_X, two_cluster_labels) -> None:
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        v = result.entries["calinski_harabasz"].value
        assert v is not None
        assert v >= 0.0


# ---------------------------------------------------------------------------
# DBSCAN noise handling (per ADR-0006 + plan §5.4)
# ---------------------------------------------------------------------------


class TestDBSCANNoise:
    def test_exclude_applied_uniformly_to_three_metrics(
        self, dbscan_with_noise_X, dbscan_with_noise_labels
    ) -> None:
        result = compute_internal_metrics(
            dbscan_with_noise_X,
            dbscan_with_noise_labels,
            algorithm_family="density_based",
            noise_policy="exclude",
        )
        for name, entry in result.entries.items():
            assert entry.reason == MetricReason.DBSCAN_NOISE_EXCLUDED.value, (
                f"{name}: {entry.reason}"
            )
            assert entry.status == MetricStatus.VALID_VALUE.value

    def test_exclude_values_match_sklearn_on_filtered_subset(
        self, dbscan_with_noise_X, dbscan_with_noise_labels
    ) -> None:
        result = compute_internal_metrics(
            dbscan_with_noise_X,
            dbscan_with_noise_labels,
            algorithm_family="density_based",
            noise_policy="exclude",
        )
        mask = dbscan_with_noise_labels != DBSCAN_NOISE_LABEL
        X_f = dbscan_with_noise_X[mask]
        y_f = dbscan_with_noise_labels[mask]
        for name, sklearn_fn in [
            ("silhouette", silhouette_score),
            ("davies_bouldin", davies_bouldin_score),
            ("calinski_harabasz", calinski_harabasz_score),
        ]:
            expected = float(sklearn_fn(X_f, y_f))
            actual = result.entries[name].value
            assert actual is not None
            assert abs(actual - expected) < 1e-6, f"{name}: {actual} vs {expected}"

    def test_include_does_not_filter(
        self, dbscan_with_noise_X, dbscan_with_noise_labels
    ) -> None:
        """noise_policy='include' passes labels as-is to sklearn."""
        result = compute_internal_metrics(
            dbscan_with_noise_X,
            dbscan_with_noise_labels,
            algorithm_family="density_based",
            noise_policy="include",
        )
        # Sklearn default treats -1 as cluster; silhouette requires n_labels>=2
        # and n_labels<=n-1. With 3 unique labels (0, 1, -1) and 12 rows,
        # silhouette should compute.
        # The reason is COMPUTED (not DBSCAN_NOISE_EXCLUDED) since no filter
        # was applied.
        for name, entry in result.entries.items():
            if entry.status == MetricStatus.VALID_VALUE.value:
                assert entry.reason == MetricReason.COMPUTED.value

    def test_all_noise_returns_not_applicable(
        self, two_cluster_X
    ) -> None:
        all_noise_labels = -np.ones(two_cluster_X.shape[0], dtype=int)
        result = compute_internal_metrics(
            two_cluster_X,
            all_noise_labels,
            algorithm_family="density_based",
            noise_policy="exclude",
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.NOT_APPLICABLE.value
            assert entry.reason == MetricReason.ALL_NOISE.value
            assert entry.value is None

    def test_non_density_does_not_filter(
        self, dbscan_with_noise_X, dbscan_with_noise_labels
    ) -> None:
        """For non-DBSCAN algorithms, no filter is applied even if -1 present."""
        result = compute_internal_metrics(
            dbscan_with_noise_X,
            dbscan_with_noise_labels,
            algorithm_family="hard",  # not density_based
            noise_policy="exclude",  # ignored
        )
        # If compute succeeds, reason is COMPUTED.
        for name, entry in result.entries.items():
            if entry.status == MetricStatus.VALID_VALUE.value:
                assert entry.reason == MetricReason.COMPUTED.value


# ---------------------------------------------------------------------------
# Edge cases (per plan §5.3 matrix)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_single_cluster_not_applicable(
        self, two_cluster_X
    ) -> None:
        labels = np.zeros(two_cluster_X.shape[0], dtype=int)
        result = compute_internal_metrics(two_cluster_X, labels, algorithm_family="hard")
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.NOT_APPLICABLE.value
            assert entry.reason == MetricReason.SINGLE_CLUSTER.value
            assert entry.value is None

    def test_alignment_error_when_X_too_short(
        self, two_cluster_labels
    ) -> None:
        X_short = np.array([[1.0, 1.0]] * 5)
        result = compute_internal_metrics(
            X_short, two_cluster_labels, algorithm_family="hard"
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.COMPUTATION_ERROR.value
            assert entry.reason == MetricReason.ALIGNMENT_ERROR.value
            assert entry.value is None

    def test_alignment_error_when_labels_too_short(
        self, two_cluster_X
    ) -> None:
        labels_short = np.array([0, 0, 0, 0, 1, 1, 1])
        result = compute_internal_metrics(
            two_cluster_X, labels_short, algorithm_family="hard"
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.COMPUTATION_ERROR.value
            assert entry.reason == MetricReason.ALIGNMENT_ERROR.value

    def test_nan_input_computation_error(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        X_nan = two_cluster_X.copy()
        X_nan[0, 0] = float("nan")
        result = compute_internal_metrics(
            X_nan, two_cluster_labels, algorithm_family="hard"
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.COMPUTATION_ERROR.value
            assert entry.reason == MetricReason.NAN_OR_INF_INPUT.value

    def test_inf_input_computation_error(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        X_inf = two_cluster_X.copy()
        X_inf[0, 0] = float("inf")
        result = compute_internal_metrics(
            X_inf, two_cluster_labels, algorithm_family="hard"
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.COMPUTATION_ERROR.value
            assert entry.reason == MetricReason.NAN_OR_INF_INPUT.value

    def test_each_sample_own_cluster_not_applicable(
        self, two_cluster_X
    ) -> None:
        """n_samples unique labels triggers sklearn ValueError → NOT_APPLICABLE."""
        labels = np.arange(two_cluster_X.shape[0], dtype=int)
        result = compute_internal_metrics(two_cluster_X, labels, algorithm_family="hard")
        # sklearn raises "Number of labels is N. ..., greater than number of samples"
        # ValueError → mapped to INSUFFICIENT_CLUSTERS (NOT_APPLICABLE).
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.NOT_APPLICABLE.value

    def test_empty_input_after_filter(
        self, two_cluster_X
    ) -> None:
        """DBSCAN all noise → empty after filter → ALL_NOISE NOT_APPLICABLE."""
        labels = -np.ones(two_cluster_X.shape[0], dtype=int)
        result = compute_internal_metrics(
            two_cluster_X,
            labels,
            algorithm_family="density_based",
            noise_policy="exclude",
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.NOT_APPLICABLE.value
            assert entry.reason == MetricReason.ALL_NOISE.value


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_unknown_algorithm_family_returns_missing(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        result = compute_internal_metrics(
            two_cluster_X,
            two_cluster_labels,
            algorithm_family="not_a_family",
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.MISSING.value
            assert entry.reason == MetricReason.ALGORITHM_FAMILY_NOT_SUPPORTED.value

    def test_unknown_noise_policy_returns_missing(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        result = compute_internal_metrics(
            two_cluster_X,
            two_cluster_labels,
            algorithm_family="hard",
            noise_policy="drop_all",
        )
        for name, entry in result.entries.items():
            assert entry.status == MetricStatus.MISSING.value

    def test_metric_set_subset_returns_missing(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        """Metric not in user metric_set → MISSING entry."""
        result = compute_internal_metrics(
            two_cluster_X,
            two_cluster_labels,
            algorithm_family="hard",
            metric_set={"silhouette"},
        )
        assert result.entries["silhouette"].status == MetricStatus.VALID_VALUE.value
        assert result.entries["davies_bouldin"].status == MetricStatus.MISSING.value
        assert result.entries["calinski_harabasz"].status == MetricStatus.MISSING.value


# ---------------------------------------------------------------------------
# Defensive / immutability
# ---------------------------------------------------------------------------


class TestDefensiveCopies:
    def test_input_X_not_mutated(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        original = two_cluster_X.copy()
        _ = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        np.testing.assert_array_equal(two_cluster_X, original)

    def test_input_labels_not_mutated(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        original = two_cluster_labels.copy()
        _ = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        np.testing.assert_array_equal(two_cluster_labels, original)

    def test_dbscan_noise_filter_does_not_modify_input(
        self, dbscan_with_noise_X, dbscan_with_noise_labels
    ) -> None:
        X_orig = dbscan_with_noise_X.copy()
        y_orig = dbscan_with_noise_labels.copy()
        _ = compute_internal_metrics(
            dbscan_with_noise_X,
            dbscan_with_noise_labels,
            algorithm_family="density_based",
            noise_policy="exclude",
        )
        np.testing.assert_array_equal(dbscan_with_noise_X, X_orig)
        np.testing.assert_array_equal(dbscan_with_noise_labels, y_orig)


# ---------------------------------------------------------------------------
# Output invariants (R-EVAL-16 + plan §5.5)
# ---------------------------------------------------------------------------


class TestOutputInvariants:
    def test_value_none_iff_status_not_valid(
        self, two_cluster_X
    ) -> None:
        """For every entry, value is None iff status != VALID_VALUE."""
        # Single cluster → all NOT_APPLICABLE
        labels = np.zeros(two_cluster_X.shape[0], dtype=int)
        result = compute_internal_metrics(two_cluster_X, labels, algorithm_family="hard")
        for entry in result.entries.values():
            assert entry.value is None
            assert entry.status != MetricStatus.VALID_VALUE.value

    def test_metric_set_closed_three_metrics(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        """Output must have exactly the 3 metric names."""
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        assert set(result.entries.keys()) == METRIC_NAMES

    def test_is_diagnostic_only_always_false(
        self, two_cluster_X, two_cluster_labels
    ) -> None:
        result = compute_internal_metrics(
            two_cluster_X, two_cluster_labels, algorithm_family="hard"
        )
        for entry in result.entries.values():
            assert entry.is_diagnostic_only is False

    def test_no_fake_default_values(
        self, two_cluster_X
    ) -> None:
        """No 0 or -1 substitution for missing values."""
        labels = np.zeros(two_cluster_X.shape[0], dtype=int)
        result = compute_internal_metrics(two_cluster_X, labels, algorithm_family="hard")
        for entry in result.entries.values():
            assert entry.value is None  # no fake defaults
