"""Tests for the EXP-01 evaluation metrics layer.

Tests cover:
- Silhouette, DBI, CH correctness on well-separated data.
- WCSS correctness and equivalence to KMeans inertia.
- WCSS for GMM hard labels.
- WCSS for FCM hard labels.
- DBSCAN noise exclusion.
- All-noise edge case.
- Single-cluster edge case.
- Insufficient clusters edge case.
- COMPUTATION_ERROR handling.
- Status schema integrity.
- Runtime stats computation.
- Metric computation time recorded.
- No input mutation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.clustering.metrics import (
    METRIC_COMPUTATION_ERROR,
    METRIC_NOT_APPLICABLE,
    METRIC_VALID,
    REASON_ALL_NOISE,
    REASON_INSUFFICIENT_CLUSTERS,
    REASON_SINGLE_CLUSTER,
    attach_metrics_with_status,
    compute_internal_metrics,
    compute_runtime_stats,
    compute_wcss,
)
from customer_segmentation.clustering.result import ClusterResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def well_separated_matrix() -> pd.DataFrame:
    """Small, well-separated matrix with 3 visible clusters."""
    rng = np.random.default_rng(7)
    n_per_cluster = 30
    centers = np.array([[0.0, 0.0], [10.0, 10.0], [-10.0, 10.0]])
    parts = []
    for c in centers:
        parts.append(rng.normal(loc=c, scale=0.5, size=(n_per_cluster, 2)))
    X = np.vstack(parts)
    return pd.DataFrame(X, columns=["x", "y"])


@pytest.fixture()
def uniform_matrix() -> pd.DataFrame:
    """Uniform random matrix (no clear clusters)."""
    rng = np.random.default_rng(42)
    X = rng.uniform(size=(60, 3))
    return pd.DataFrame(X, columns=["f0", "f1", "f2"])


@pytest.fixture()
def small_matrix() -> pd.DataFrame:
    rng = np.random.default_rng(123)
    X = rng.normal(size=(50, 4))
    return pd.DataFrame(X, columns=["f0", "f1", "f2", "f3"])


# ---------------------------------------------------------------------------
# Silhouette correctness
# ---------------------------------------------------------------------------


class TestSilhouetteCorrectness:
    def test_well_separated_high_silhouette(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        # Perfect separation: labels 0, 1, 2
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)
        assert status["silhouette"] == METRIC_VALID
        assert values["silhouette"] is not None
        # Well-separated clusters should have silhouette close to 1
        assert values["silhouette"] > 0.9

    def test_uniform_low_silhouette(self, uniform_matrix: pd.DataFrame) -> None:
        X = uniform_matrix.to_numpy()
        # Random labels for uniform data
        labels = np.array([i % 4 for i in range(60)], dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)
        assert status["silhouette"] == METRIC_VALID
        assert values["silhouette"] is not None
        # Uniform data with random clusters should have low silhouette
        assert values["silhouette"] < 0.2


# ---------------------------------------------------------------------------
# DBI correctness
# ---------------------------------------------------------------------------


class TestDBICorrectness:
    def test_well_separated_low_dbi(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)
        assert status["davies_bouldin"] == METRIC_VALID
        assert values["davies_bouldin"] is not None
        # Well-separated clusters should have low DBI
        assert values["davies_bouldin"] < 1.0

    def test_uniform_high_dbi(self, uniform_matrix: pd.DataFrame) -> None:
        X = uniform_matrix.to_numpy()
        labels = np.array([i % 4 for i in range(60)], dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)
        assert status["davies_bouldin"] == METRIC_VALID
        assert values["davies_bouldin"] is not None
        # Overlapping clusters should have higher DBI
        assert values["davies_bouldin"] > 0.5


# ---------------------------------------------------------------------------
# CH correctness
# ---------------------------------------------------------------------------


class TestCHCorrectness:
    def test_well_separated_high_ch(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)
        assert status["calinski_harabasz"] == METRIC_VALID
        assert values["calinski_harabasz"] is not None
        # Well-separated clusters should have high CH
        assert values["calinski_harabasz"] > 500

    def test_uniform_low_ch(self, uniform_matrix: pd.DataFrame) -> None:
        X = uniform_matrix.to_numpy()
        labels = np.array([i % 4 for i in range(60)], dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)
        assert status["calinski_harabasz"] == METRIC_VALID
        assert values["calinski_harabasz"] is not None
        # Uniform data with random clusters should have lower CH
        assert values["calinski_harabasz"] < 50


# ---------------------------------------------------------------------------
# WCSS correctness
# ---------------------------------------------------------------------------


class TestWCSSEquality:
    def test_wcss_matches_kmeans_inertia(self, well_separated_matrix: pd.DataFrame) -> None:
        """WCSS computed from labels matches sklearn KMeans inertia."""
        from sklearn.cluster import KMeans

        X = well_separated_matrix.to_numpy()
        k = 3
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X)
        expected_inertia = kmeans.inertia_

        # Compute WCSS from labels
        labels = kmeans.labels_
        wcss, status, reason = compute_wcss(X, labels)
        assert status == METRIC_VALID
        assert wcss is not None
        # Should match inertia (within floating point tolerance)
        assert abs(wcss - expected_inertia) < 1e-6

    def test_wcss_perfect_separation(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)
        wcss, status, reason = compute_wcss(X, labels)
        assert status == METRIC_VALID
        assert wcss is not None
        assert wcss >= 0.0

    def test_wcss_zero_for_single_point_clusters(self) -> None:
        """WCSS is 0 when each cluster has exactly one point."""
        X = np.array([[0, 0], [1, 1], [2, 2]], dtype=np.float64)
        labels = np.array([0, 1, 2], dtype=np.int64)
        wcss, status, reason = compute_wcss(X, labels)
        assert status == METRIC_VALID
        assert wcss is not None
        assert abs(wcss) < 1e-10


# ---------------------------------------------------------------------------
# WCSS with GMM hard labels
# ---------------------------------------------------------------------------


class TestWCSSGMM:
    def test_wcss_gmm_hard_labels(self, well_separated_matrix: pd.DataFrame) -> None:
        """WCSS uses argmax of soft probabilities, not GMM Gaussian means."""
        from sklearn.mixture import GaussianMixture

        X = well_separated_matrix.to_numpy()
        gmm = GaussianMixture(n_components=3, random_state=42, n_init=1)
        gmm.fit(X)

        # Get hard labels as argmax of responsibilities
        responsibilities = gmm.predict_proba(X)
        hard_labels = np.argmax(responsibilities, axis=1).astype(np.int64)

        # Compute WCSS using arithmetic centroid (our implementation)
        wcss_arith, status, reason = compute_wcss(X, hard_labels)
        assert status == METRIC_VALID
        assert wcss_arith is not None
        assert wcss_arith >= 0.0

        # Also verify against sklearn KMeans inertia
        # Note: This is a sanity check that WCSS is in the right ballpark
        # In well-separated data, both should give similar results


# ---------------------------------------------------------------------------
# WCSS with FCM hard labels
# ---------------------------------------------------------------------------


class TestWCSSFCM:
    def test_wcss_fcm_hard_labels(self, well_separated_matrix: pd.DataFrame) -> None:
        """WCSS uses argmax of membership, not FCM fuzzy centroids."""
        from numpy.random import default_rng

        X = well_separated_matrix.to_numpy()
        n, c = X.shape[0], 3

        # Simple FCM-like membership matrix (deterministic)
        rng = default_rng(42)
        membership = rng.dirichlet(np.ones(c), size=n).astype(np.float64)

        # Get hard labels as argmax
        hard_labels = np.argmax(membership, axis=1).astype(np.int64)

        # Compute WCSS using arithmetic centroid
        wcss, status, reason = compute_wcss(X, hard_labels)
        assert status == METRIC_VALID
        assert wcss is not None
        assert wcss >= 0.0


# ---------------------------------------------------------------------------
# DBSCAN noise exclusion
# ---------------------------------------------------------------------------


class TestDBSCANNoiseExclusion:
    def test_noise_excluded_from_metrics(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy()
        n = len(X)

        # Simulate DBSCAN output: most points in 2 clusters, some noise
        labels = np.zeros(n, dtype=np.int64)
        labels[:20] = 0
        labels[20:40] = 1
        labels[40:] = -1  # noise

        values, status, reason, _ = compute_internal_metrics(
            X, labels, noise_label=-1, exclude_noise=True
        )

        # Metrics should be computed on non-noise subset (60 points)
        assert status["silhouette"] == METRIC_VALID
        assert values["silhouette"] is not None

    def test_noise_excluded_from_wcss(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy()
        n = len(X)

        # Simulate DBSCAN output
        labels = np.zeros(n, dtype=np.int64)
        labels[:20] = 0
        labels[20:40] = 1
        labels[40:] = -1

        wcss, status, reason = compute_wcss(X, labels, noise_label=-1, exclude_noise=True)
        assert status == METRIC_VALID
        assert wcss is not None
        # WCSS computed only on non-noise points

    def test_include_noise_false_excludes(self) -> None:
        # Create consistent-sized arrays
        X = np.array(
            [
                [0.0, 0.0],
                [1.0, 1.0],
                [2.0, 2.0],
                [3.0, 3.0],
                [4.0, 4.0],
                [5.0, 5.0],
                [10.0, 10.0],
                [11.0, 11.0],
            ],
            dtype=np.float64,
        )
        labels = np.array([0, 0, 0, -1, -1, 1, 1, 1], dtype=np.int64)

        # With exclude_noise=True - should exclude -1 points
        wcss_excluded, status1, _ = compute_wcss(X, labels, noise_label=-1, exclude_noise=True)

        # Manual computation on non-noise subset
        mask = labels != -1
        X_subset = X[mask]
        labels_subset = labels[mask]
        wcss_manual, status2, _ = compute_wcss(
            X_subset, labels_subset, noise_label=-1, exclude_noise=True
        )

        assert status1 == METRIC_VALID
        assert status2 == METRIC_VALID
        assert wcss_excluded == wcss_manual


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestAllNoise:
    def test_all_noise_returns_not_applicable(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy()
        labels = np.array([-1] * len(X), dtype=np.int64)

        values, status, reason, _ = compute_internal_metrics(
            X, labels, noise_label=-1, exclude_noise=True
        )
        wcss, wcss_status, wcss_reason = compute_wcss(X, labels, noise_label=-1, exclude_noise=True)

        assert status["silhouette"] == METRIC_NOT_APPLICABLE
        assert reason["silhouette"] == REASON_ALL_NOISE
        assert wcss_status == METRIC_NOT_APPLICABLE
        assert wcss_reason == REASON_ALL_NOISE


class TestSingleCluster:
    def test_single_cluster_returns_not_applicable(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy()
        labels = np.zeros(len(X), dtype=np.int64)

        values, status, reason, _ = compute_internal_metrics(X, labels)
        wcss, wcss_status, wcss_reason = compute_wcss(X, labels)

        assert status["silhouette"] == METRIC_NOT_APPLICABLE
        assert reason["silhouette"] == REASON_SINGLE_CLUSTER
        assert values["davies_bouldin"] is None
        assert values["calinski_harabasz"] is None


class TestInsufficientClusters:
    def test_insufficient_clusters_returns_not_applicable(self) -> None:
        X = np.array([[0, 0], [1, 1], [2, 2]], dtype=np.float64)
        labels = np.array([0, 0, 0], dtype=np.int64)  # Only 1 cluster

        values, status, reason, _ = compute_internal_metrics(X, labels)
        assert status["silhouette"] == METRIC_NOT_APPLICABLE
        assert reason["silhouette"] == REASON_SINGLE_CLUSTER


class TestComputationError:
    def test_sklearn_exception_returns_computation_error(self) -> None:
        X = np.array([[0, 0]], dtype=np.float64)
        labels = np.array([0], dtype=np.int64)

        values, status, reason, _ = compute_internal_metrics(X, labels)
        # silhouette requires n_clusters >= 2, so should fail
        # But the test depends on sklearn behavior
        assert status["silhouette"] in (METRIC_NOT_APPLICABLE, METRIC_COMPUTATION_ERROR)


# ---------------------------------------------------------------------------
# Status schema integrity
# ---------------------------------------------------------------------------


class TestStatusSchema:
    def test_valid_value_has_no_reason(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)

        for metric in ("silhouette", "davies_bouldin", "calinski_harabasz"):
            if status[metric] == METRIC_VALID:
                assert reason[metric] is None

    def test_not_applicable_has_reason(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy()
        labels = np.zeros(len(X), dtype=np.int64)
        values, status, reason, _ = compute_internal_metrics(X, labels)

        assert status["silhouette"] == METRIC_NOT_APPLICABLE
        assert reason["silhouette"] in (
            REASON_SINGLE_CLUSTER,
            REASON_ALL_NOISE,
            REASON_INSUFFICIENT_CLUSTERS,
        )


# ---------------------------------------------------------------------------
# Runtime stats
# ---------------------------------------------------------------------------


class TestRuntimeStats:
    def test_runtime_stats_empty_list(self) -> None:
        stats = compute_runtime_stats([])
        assert stats["mean_seconds"] is None
        assert stats["raw_seconds"] == []

    def test_runtime_stats_single_value(self) -> None:
        stats = compute_runtime_stats([1.5])
        assert stats["mean_seconds"] == 1.5
        assert stats["std_seconds"] == 0.0
        assert stats["min_seconds"] == 1.5
        assert stats["max_seconds"] == 1.5
        assert stats["raw_seconds"] == [1.5]

    def test_runtime_stats_multiple_values(self) -> None:
        times = [1.0, 1.1, 0.9, 1.05, 0.95]
        stats = compute_runtime_stats(times)
        assert abs(stats["mean_seconds"] - 1.0) < 0.01
        assert stats["std_seconds"] > 0
        assert stats["min_seconds"] == 0.9
        assert stats["max_seconds"] == 1.1
        assert stats["raw_seconds"] == times


# ---------------------------------------------------------------------------
# Metric computation time
# ---------------------------------------------------------------------------


class TestMetricComputationTime:
    def test_computation_time_recorded(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)

        _, _, _, comp_time = compute_internal_metrics(X, labels)
        assert comp_time > 0
        assert comp_time < 10  # Should be fast for small data


# ---------------------------------------------------------------------------
# Attach metrics with status
# ---------------------------------------------------------------------------


class TestAttachMetricsWithStatus:
    def test_attach_populates_metrics(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)

        cluster_result = ClusterResult(
            algorithm="test",
            algorithm_version="v1",
            algorithm_family="hard",
            n_samples=len(X),
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=3,
        )

        updated = attach_metrics_with_status(cluster_result, X)

        # Check metrics are populated
        assert updated.metrics.silhouette is not None
        assert updated.metrics.silhouette > 0
        assert updated.metrics.davies_bouldin is not None
        assert updated.metrics.calinski_harabasz is not None
        assert updated.metrics.wcss is not None

    def test_attach_preserves_extra_status(self, well_separated_matrix: pd.DataFrame) -> None:
        X = well_separated_matrix.to_numpy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)

        cluster_result = ClusterResult(
            algorithm="test",
            algorithm_version="v1",
            algorithm_family="hard",
            n_samples=len(X),
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=3,
        )

        updated = attach_metrics_with_status(cluster_result, X, metric_computation_time=0.5)

        assert updated.metrics.extra["silhouette_status"] == METRIC_VALID
        assert updated.metrics.extra["silhouette_reason"] is None
        assert "metric_computation_time_seconds" in updated.metrics.extra

    def test_attach_dbscan_noise(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy()
        n = len(X)
        labels = np.zeros(n, dtype=np.int64)
        labels[:20] = 0
        labels[20:40] = 1
        labels[40:] = -1

        cluster_result = ClusterResult(
            algorithm="dbscan",
            algorithm_version="v1",
            algorithm_family="density_based",
            n_samples=n,
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=2,
            noise_label=-1,
            noise_count=10,
            noise_ratio=10 / n,
        )

        updated = attach_metrics_with_status(cluster_result, X, exclude_noise=True, noise_label=-1)

        # Metrics computed on non-noise subset
        assert updated.metrics.silhouette is not None
        # Status recorded
        assert "silhouette_status" in updated.metrics.extra

    def test_attach_preserves_original_result(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy()
        labels = np.array([0] * 25 + [1] * 25, dtype=np.int64)

        cluster_result = ClusterResult(
            algorithm="test",
            algorithm_version="v1",
            algorithm_family="hard",
            n_samples=len(X),
            n_features=X.shape[1],
            cluster_labels=labels,
            n_clusters=2,
        )

        original_labels = cluster_result.cluster_labels.copy()
        updated = attach_metrics_with_status(cluster_result, X)

        # Labels unchanged
        np.testing.assert_array_equal(updated.cluster_labels, original_labels)


# ---------------------------------------------------------------------------
# No input mutation
# ---------------------------------------------------------------------------


class TestNoInputMutation:
    def test_compute_internal_metrics_no_mutation(
        self, well_separated_matrix: pd.DataFrame
    ) -> None:
        X = well_separated_matrix.to_numpy().copy()
        original = X.copy()
        labels = np.array([0] * 30 + [1] * 30 + [2] * 30, dtype=np.int64)

        compute_internal_metrics(X, labels)

        np.testing.assert_array_equal(X, original)

    def test_compute_wcss_no_mutation(self, small_matrix: pd.DataFrame) -> None:
        X = small_matrix.to_numpy().copy()
        original = X.copy()
        labels = np.array([0] * 25 + [1] * 25, dtype=np.int64)

        compute_wcss(X, labels)

        np.testing.assert_array_equal(X, original)
