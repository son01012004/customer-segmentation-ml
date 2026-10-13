"""Regression tests for the DEV-05 pipeline helpers.

This file covers the two MINOR findings from the independent
verification (see ``docs/system/DEV-05_verification_report.md``):

- **F1**: ``_make_manifest`` must receive ``dataset_id`` from the
  pipeline input (the DEV-04 ``clustering_manifest.json`` schema does
  not contain ``dataset_id``; re-reading it from
  ``clustering_manifest_data`` would silently produce an empty
  ``dataset_id`` field in every evaluation manifest).
- **F2**: ``n_clusters_realized`` must reflect the point set actually
  used to compute the metrics (per plan §5.4.4 + ADR-0006): for
  ``density_based`` + ``noise_policy="exclude"`` it counts unique
  non-noise labels; for ``include`` it counts unique labels including
  ``-1``; for non-density algorithms it counts unique labels
  regardless of policy.

The tests call the private helpers directly with synthetic data; no
real DEV-04 artefact is needed (per the audit brief: "không cần
chạy end-to-end trên dữ liệu thật").
"""

from __future__ import annotations

import platform
import sys

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.prototype.evaluation.config_loader import (
    Dev05Config,
    load_dev05_config,
)
from customer_segmentation.prototype.evaluation.manifest import (
    EnvironmentBlock,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    build_evaluation_manifest,
    make_valid_entry,
    read_evaluation_manifest,
    write_evaluation_manifest,
)
from customer_segmentation.prototype.evaluation.pipeline import (
    _compute_n_clusters_realized,
    _make_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dev05_config() -> Dev05Config:
    """Loaded DEV-05 config (does not require a real storage layout)."""
    cfg, _ = load_dev05_config()
    return cfg


@pytest.fixture
def config_text() -> str:
    """Canonical DEV-05 config text (raw YAML) for ``_make_manifest``."""
    from customer_segmentation.prototype.evaluation.config_loader import (
        DEFAULT_DEV05_CONFIG_PATH,
    )

    return DEFAULT_DEV05_CONFIG_PATH.read_text(encoding="utf-8")


def _dummy_environment() -> EnvironmentBlock:
    return EnvironmentBlock(
        python=sys.version.split()[0],
        platform=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        key_libraries={"numpy": "1.26", "scikit-learn": "1.5"},
    )


def _three_valid_metrics() -> EvaluationMetricsResult:
    return EvaluationMetricsResult(
        entries={
            "silhouette": make_valid_entry("silhouette", 0.5),
            "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
            "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
        }
    )


def _dummy_clustering_manifest_data(
    *, algorithm: str = "kmeans", algorithm_family: str | None = None
) -> dict:
    """Synthetic DEV-04 manifest payload as a JSON-like dict.

    Note: this payload intentionally does NOT include ``dataset_id``
    (mirroring the actual DEV-04 ``ClusteringManifest`` schema, which
    does not carry that field). The fix under test (F1) is precisely
    about NOT re-deriving ``dataset_id`` from this dict.
    """
    if algorithm_family is None:
        algorithm_family = {
            "kmeans": "hard",
            "agglomerative": "hard",
            "dbscan": "density_based",
            "gmm": "model_based",
            "fuzzy_cmeans": "fuzzy",
        }.get(algorithm, "hard")
    return {
        "algorithm": algorithm,
        "algorithm_version": "sklearn_1.5",
        "algorithm_family": algorithm_family,
        "preprocessed_id": "pp_test01",
        "ml_dataset_sha256": "b" * 64,
        "preprocessing_config_sha256": "d" * 64,
        "hyperparameters": {"n_clusters": 4},
        "seed_policy": "stochastic",
        "seed": 42,
        "feature_set": ["Recency", "Frequency", "Monetary", "Tenure"],
        "feature_count": 4,
    }


def _dummy_cluster_labels_df() -> pd.DataFrame:
    """Cluster labels DataFrame with 100 rows and a valid ClusterLabel column."""
    return pd.DataFrame(
        {
            "CustomerID": list(range(1, 101)),
            "ClusterLabel": ([0] * 25 + [1] * 25 + [2] * 25 + [3] * 25),
        }
    )


def _dummy_X() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.normal(size=(100, 4))


# ---------------------------------------------------------------------------
# F1 — _make_manifest dataset_id propagation
# ---------------------------------------------------------------------------


class TestMakeManifestDatasetId:
    """F1 regression: dataset_id must come from the pipeline input,
    not from clustering_manifest_data (which does not contain it)."""

    def test_dataset_id_recorded_from_input(
        self,
        dev05_config: Dev05Config,
        config_text: str,
    ) -> None:
        m = _make_manifest(
            evaluation_id="ev_" + "a" * 24,
            dataset_id="ds_test_f1_01",
            clustering_id="cl_" + "a" * 24,
            clustering_manifest_data=_dummy_clustering_manifest_data(),
            config=dev05_config,
            config_text=config_text,
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_three_valid_metrics(),
            X=_dummy_X(),
            cluster_labels_df=_dummy_cluster_labels_df(),
            noise_count=None,
            noise_ratio=None,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            validation_report=EvaluationValidationReport(all_passed=True),
            log_file="ev_xx.log",
        )
        assert m.dataset_id == "ds_test_f1_01", (
            f"dataset_id must come from the pipeline input; got {m.dataset_id!r}"
        )

    def test_dataset_id_not_empty_when_input_provided(
        self,
        dev05_config: Dev05Config,
        config_text: str,
    ) -> None:
        """The pre-fix bug produced an empty ``dataset_id`` for every run.
        This test ensures the field is now non-empty when the caller
        passes a valid id."""
        m = _make_manifest(
            evaluation_id="ev_" + "a" * 24,
            dataset_id="ds_test_f1_02",
            clustering_id="cl_" + "a" * 24,
            clustering_manifest_data=_dummy_clustering_manifest_data(),
            config=dev05_config,
            config_text=config_text,
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_three_valid_metrics(),
            X=_dummy_X(),
            cluster_labels_df=_dummy_cluster_labels_df(),
            noise_count=None,
            noise_ratio=None,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            validation_report=EvaluationValidationReport(all_passed=True),
            log_file="ev_xx.log",
        )
        assert m.dataset_id != "", "dataset_id must be the caller-supplied value"

    def test_dataset_id_survives_manifest_round_trip(
        self,
        dev05_config: Dev05Config,
        config_text: str,
        tmp_path,
    ) -> None:
        """The dataset_id must round-trip through the on-disk JSON
        representation, so downstream consumers (compare, audit) can
        read it back."""
        m = _make_manifest(
            evaluation_id="ev_" + "a" * 24,
            dataset_id="ds_roundtrip_f1",
            clustering_id="cl_" + "a" * 24,
            clustering_manifest_data=_dummy_clustering_manifest_data(),
            config=dev05_config,
            config_text=config_text,
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_three_valid_metrics(),
            X=_dummy_X(),
            cluster_labels_df=_dummy_cluster_labels_df(),
            noise_count=None,
            noise_ratio=None,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            validation_report=EvaluationValidationReport(all_passed=True),
            log_file="ev_xx.log",
        )
        path = tmp_path / "m.json"
        write_evaluation_manifest(m, path)
        reloaded = read_evaluation_manifest(path)
        assert reloaded.dataset_id == "ds_roundtrip_f1"

    def test_dataset_id_ignored_when_not_in_manifest_data(
        self,
        dev05_config: Dev05Config,
        config_text: str,
    ) -> None:
        """Even if a stray ``dataset_id`` key is present in
        ``clustering_manifest_data`` (e.g. a forward-compatible
        upstream extension), the caller-supplied value wins. This
        prevents accidental shadowing."""
        manifest_data = _dummy_clustering_manifest_data()
        # Add a stray dataset_id in the dict (mimics a future DEV-04
        # schema extension that is not yet canonical).
        manifest_data["dataset_id"] = "ds_stale_legacy_value"
        m = _make_manifest(
            evaluation_id="ev_" + "a" * 24,
            dataset_id="ds_caller_value",
            clustering_id="cl_" + "a" * 24,
            clustering_manifest_data=manifest_data,
            config=dev05_config,
            config_text=config_text,
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_three_valid_metrics(),
            X=_dummy_X(),
            cluster_labels_df=_dummy_cluster_labels_df(),
            noise_count=None,
            noise_ratio=None,
            n_samples_used_for_compute=100,
            n_clusters_realized=4,
            validation_report=EvaluationValidationReport(all_passed=True),
            log_file="ev_xx.log",
        )
        assert m.dataset_id == "ds_caller_value"


# ---------------------------------------------------------------------------
# F2 — n_clusters_realized semantics
# ---------------------------------------------------------------------------


class TestComputeNClustersRealized:
    """F2 regression: ``_compute_n_clusters_realized`` must match the
    data point set actually used for the metrics (plan §5.4.4 +
    ADR-0006)."""

    # --- non-density algorithms ---

    def test_non_density_count_all_unique(self) -> None:
        labels = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2], dtype=int)
        # is_density_based=False → count all unique labels regardless
        # of noise_policy.
        for policy in ("include", "exclude"):
            n = _compute_n_clusters_realized(
                labels=labels,
                noise_label=-1,
                is_density_based=False,
                noise_policy=policy,
            )
            assert n == 3, f"policy={policy}: expected 3 clusters, got {n}"

    def test_non_density_single_cluster(self) -> None:
        labels = np.zeros(10, dtype=int)
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=False,
            noise_policy="exclude",
        )
        assert n == 1

    # --- density_based + exclude (the prototype default per ADR-0006) ---

    def test_density_exclude_excludes_noise(self) -> None:
        # 4 noise + 2 clusters of 4 each.
        labels = np.array(
            [0, 0, 0, 0, 1, 1, 1, 1, -1, -1, -1, -1], dtype=int
        )
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="exclude",
        )
        assert n == 2, f"expected 2 non-noise clusters, got {n}"

    def test_density_exclude_all_noise_returns_zero(self) -> None:
        labels = -np.ones(8, dtype=int)
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="exclude",
        )
        assert n == 0, (
            "all-noise input → filter is empty → n_clusters_realized == 0 "
            "(not 1, not NaN, not a fake default)"
        )

    def test_density_exclude_single_non_noise_cluster(self) -> None:
        """Edge case: one real cluster + noise → after exclude, only one
        unique non-noise label remains. This is the case where
        ``compute_internal_metrics`` returns NOT_APPLICABLE/SINGLE_CLUSTER,
        and the manifest's ``n_clusters_realized`` correctly reflects 1
        (the size of the post-filter set)."""
        labels = np.array(
            [0, 0, 0, 0, 0, -1, -1, -1, -1, -1], dtype=int
        )
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="exclude",
        )
        assert n == 1

    def test_density_exclude_no_noise_in_data(self) -> None:
        """When the data has no -1 label, exclude is a no-op."""
        labels = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2], dtype=int)
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="exclude",
        )
        assert n == 3

    # --- density_based + include (the override per ADR-0006) ---

    def test_density_include_treats_minus_one_as_cluster(self) -> None:
        # 4 noise + 2 clusters of 4 each.
        labels = np.array(
            [0, 0, 0, 0, 1, 1, 1, 1, -1, -1, -1, -1], dtype=int
        )
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="include",
        )
        assert n == 3, (
            f"include: -1 is a regular cluster → expected 3 (0, 1, -1), got {n}"
        )

    def test_density_include_all_noise_returns_one(self) -> None:
        labels = -np.ones(8, dtype=int)
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="include",
        )
        assert n == 1, "include: -1 is the only cluster → 1"

    # --- immutability / no source mutation ---

    def test_input_labels_not_mutated(self) -> None:
        labels = np.array(
            [0, 0, 0, 1, 1, 1, -1, -1], dtype=int
        )
        before = labels.copy()
        _ = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="exclude",
        )
        np.testing.assert_array_equal(labels, before)

    def test_no_fake_default_value(self) -> None:
        """All-noise under exclude must return 0, not 1, -1, or NaN."""
        labels = -np.ones(5, dtype=int)
        n = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="exclude",
        )
        # Per plan §5.5 rule 2: no fake defaults (0 / -1 / NaN
        # substitutions for missing values). Here 0 is the genuine
        # count of clusters in an empty filtered set, NOT a fake
        # placeholder for "missing".
        assert n == 0
        assert isinstance(n, int)


# ---------------------------------------------------------------------------
# Smoke test — F1 + F2 together via the public surface
# ---------------------------------------------------------------------------


class TestF1F2Integration:
    """End-to-end-shape smoke test: build a manifest via ``_make_manifest``
    (which is what the pipeline calls) for a DBSCAN run with noise,
    and verify the resulting on-disk manifest records both the
    caller-supplied ``dataset_id`` and the post-filter
    ``n_clusters_realized``."""

    def test_dbscan_manifest_records_dataset_id_and_post_filter_clusters(
        self,
        dev05_config: Dev05Config,
        config_text: str,
        tmp_path,
    ) -> None:
        # Synthetic DBSCAN-like data: 4 noise + 2 clusters of 4.
        labels = np.array(
            [0, 0, 0, 0, 1, 1, 1, 1, -1, -1, -1, -1], dtype=int
        )
        # Cluster label DataFrame with 12 rows.
        cluster_labels_df = pd.DataFrame(
            {
                "CustomerID": list(range(1, 13)),
                "ClusterLabel": labels,
            }
        )
        rng = np.random.default_rng(42)
        X = np.vstack(
            [
                rng.normal(loc=(0, 0), scale=0.5, size=(4, 2)),
                rng.normal(loc=(10, 10), scale=0.5, size=(4, 2)),
                rng.normal(loc=(50, 50), scale=1.0, size=(4, 2)),  # noise
            ]
        )
        n_clusters_realized = _compute_n_clusters_realized(
            labels=labels,
            noise_label=-1,
            is_density_based=True,
            noise_policy="exclude",
        )
        # 2 real clusters (noise excluded).
        assert n_clusters_realized == 2

        m = _make_manifest(
            evaluation_id="ev_" + "b" * 24,
            dataset_id="ds_dbscan_f1f2",
            clustering_id="cl_" + "b" * 24,
            clustering_manifest_data=_dummy_clustering_manifest_data(
                algorithm="dbscan", algorithm_family="density_based"
            ),
            config=dev05_config,
            config_text=config_text,
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
            metrics=_three_valid_metrics(),
            X=X,
            cluster_labels_df=cluster_labels_df,
            noise_count=4,
            noise_ratio=4 / 12,
            n_samples_used_for_compute=8,  # 12 - 4 noise
            n_clusters_realized=n_clusters_realized,
            validation_report=EvaluationValidationReport(all_passed=True),
            log_file="ev_xx.log",
        )
        path = tmp_path / "dbscan.json"
        write_evaluation_manifest(m, path)
        reloaded = read_evaluation_manifest(path)
        # F1: dataset_id is the caller-supplied value, not empty.
        assert reloaded.dataset_id == "ds_dbscan_f1f2"
        # F2: n_clusters_realized is the post-filter count, not 3
        # (which would include -1).
        assert reloaded.n_clusters_realized == 2
        # Auxiliary fields stay consistent.
        assert reloaded.n_samples_input == 12
        assert reloaded.n_samples_used_for_compute == 8
        assert reloaded.noise_count == 4
        assert reloaded.noise_ratio == pytest.approx(4 / 12)
        assert reloaded.algorithm_family == "density_based"
        assert reloaded.noise_policy_used == "exclude"
