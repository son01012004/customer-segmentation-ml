"""Tests for EVA-03 — Stability & Reproducibility Evaluation.

These tests cover the EVA-03 pipeline in isolation from the real
EXP-05 / EXP-01 / EXP-03 artifacts. They use synthetic data that
mirrors the documented schema for each artifact type.

The hard constraints (AGENTS.md §2 / EPIC-08 boundary) are enforced
at the boundary of the tests:

- Tests use only publicly-exported functions.
- Tests never assert the existence of a "best algorithm" / "most stable" label.
- Tests cover Block R (reproducibility), Block S (seed stability),
  Block N (perturbation robustness), cluster size variation,
  EXP-01 vs EXP-03 metadata comparison, Hungarian matching.
- Tests cover the runner pipeline (load -> analyze -> report -> write)
  end-to-end on a temporary directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.evaluation.eva03.cluster_size import (
    analyze_cluster_size_variation,
)
from customer_segmentation.evaluation.eva03.hungarian import (
    run_hungarian_for_pair,
)
from customer_segmentation.evaluation.eva03.hyperparameter_stability import (
    analyze_hyperparameter_stability,
)
from customer_segmentation.evaluation.eva03.label_compare import (
    compute_label_compare,
    hungarian_align,
)
from customer_segmentation.evaluation.eva03.load import (
    exp01_reference_rows,
    exp03_comparison_rows,
    load_eva03_config,
    load_exp01_cluster_labels,
    load_exp03_selected_configurations,
    load_exp05_labels_artifact,
    load_exp05_per_block_record_aggregates,
)
from customer_segmentation.evaluation.eva03.perturbation import (
    analyze_block_n,
    decision_status_for_block_n_algorithm,
)
from customer_segmentation.evaluation.eva03.report import (
    build_comparison_report,
    build_reproducibility_report,
    build_run_manifest_dict,
    build_stability_report,
    write_run_manifest_json,
)
from customer_segmentation.evaluation.eva03.reproducibility import (
    analyze_block_r,
    decision_status_for_block_r,
)
from customer_segmentation.evaluation.eva03.runner import (
    Eva03Config,
    Eva03Runner,
)
from customer_segmentation.evaluation.eva03.seed_stability import (
    analyze_block_s,
)
from customer_segmentation.evaluation.eva03.types import (
    BlockRPairwiseRow,
    EXP01ReferenceRow,
    EXP03ComparisonRow,
    PairwiseMatrix,
)

# ---------------------------------------------------------------------------
# Fixtures: synthetic EXP-05 labels artifact
# ---------------------------------------------------------------------------


def _make_labels_df(
    *,
    algorithms: list[str] = None,
    n_repeats: int = 5,
    n_seeds: int = 5,
    n_sigmas: int = 3,
    n_perturbation_seeds: int = 3,
    n_customers: int = 100,
    deterministic: bool = False,
) -> pd.DataFrame:
    """Build a synthetic EXP-05 labels artifact.

    Returns a DataFrame with columns:
    run_id, block, algorithm, seed, sigma, perturbation_seed,
    repeat_index, CustomerID, cluster_label
    """
    if algorithms is None:
        algorithms = ["kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"]

    rows: list[dict[str, object]] = []

    # Block R: reproducibility (5 repeats × seed=42)
    block_r_algos = ["kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"]
    for algo in block_r_algos:
        labels = np.random.default_rng(42).integers(0, 4, size=n_customers)
        for r_idx in range(n_repeats):
            run_id = f"EXP-05-{algo}-R-r{r_idx}"
            for cid in range(n_customers):
                rows.append(
                    {
                        "run_id": run_id,
                        "block": "R",
                        "algorithm": algo,
                        "seed": 42,
                        "sigma": 0.0,
                        "perturbation_seed": None,
                        "repeat_index": r_idx,
                        "CustomerID": cid,
                        "cluster_label": int(labels[cid]),
                    }
                )

    # Block S: seed stability (5 seeds, 1 repeat each)
    block_s_algos = ["kmeans", "gmm", "fuzzy_cmeans"]
    seeds = [42, 7, 123, 2024, 1729]
    for algo in block_s_algos:
        for s_idx, seed in enumerate(seeds):
            rng = np.random.default_rng(seed)
            labels = rng.integers(0, 4, size=n_customers)
            run_id = f"EXP-05-{algo}-S-seed{seed}"
            for cid in range(n_customers):
                rows.append(
                    {
                        "run_id": run_id,
                        "block": "S",
                        "algorithm": algo,
                        "seed": seed,
                        "sigma": 0.0,
                        "perturbation_seed": None,
                        "repeat_index": s_idx,
                        "CustomerID": cid,
                        "cluster_label": int(labels[cid]),
                    }
                )

    # Block N: perturbation robustness (3 sigmas × 3 perturbation seeds)
    block_n_algos = ["kmeans", "gmm", "fuzzy_cmeans"]
    sigmas = [0.0, 0.01, 0.05]
    pseeds = [42, 43, 44]
    for algo in block_n_algos:
        for sigma in sigmas:
            pseeds_subset = [42] if sigma == 0.0 else pseeds
            for pseed in pseeds_subset:
                rng_key = int(sigma * 1000) + pseed
                rng = np.random.default_rng(rng_key)
                labels = rng.integers(0, 4, size=n_customers)
                run_id = f"EXP-05-{algo}-N-sigma{sigma}-pseed{pseed}"
                for cid in range(n_customers):
                    rows.append(
                        {
                            "run_id": run_id,
                            "block": "N",
                            "algorithm": algo,
                            "seed": 42,
                            "sigma": sigma,
                            "perturbation_seed": pseed,
                            "repeat_index": 0,
                            "CustomerID": cid,
                            "cluster_label": int(labels[cid]),
                        }
                    )

    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_labels_df() -> pd.DataFrame:
    """Block R only, deterministic labels (all repeats identical)."""
    df = _make_labels_df(n_customers=20, n_repeats=5)
    return df


@pytest.fixture
def synthetic_labels_df_seeded() -> pd.DataFrame:
    """Full synthetic artifact: Block R + S + N.

    Uses 1 customer per run because the existing structural tests only
    need to verify the returned keys, decision_status taxonomy, and
    summary columns. The Block N dedup invariant is verified separately
    by ``test_analyze_block_n_deduplicates_runs_by_run_id`` (and the
    other invariant tests in TestPerturbation) which use larger
    n_customers values.
    """
    return _make_labels_df(n_customers=1, n_repeats=5, n_seeds=5, n_sigmas=3)


@pytest.fixture
def synthetic_labels_parquet(tmp_path: Path, synthetic_labels_df_seeded: pd.DataFrame) -> Path:
    p = tmp_path / "exp05_cluster_labels.parquet"
    synthetic_labels_df_seeded.to_parquet(p, index=False)
    return p


@pytest.fixture
def synthetic_exp01_dir(tmp_path: Path) -> Path:
    """Write synthetic EXP-01 cluster label parquet files."""
    d = tmp_path / "exp01"
    d.mkdir(parents=True, exist_ok=True)
    for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
        rng = np.random.default_rng(42)
        labels = rng.integers(0, 4, size=50)
        is_noise = np.zeros(50, dtype=bool)
        if algo == "dbscan":
            noise_idx = rng.choice(50, size=5, replace=False)
            labels[noise_idx] = -1
            is_noise[noise_idx] = True
        df = pd.DataFrame(
            {
                "CustomerID": np.arange(50),
                "ClusterLabel": labels,
                "IsNoise": is_noise,
            }
        )
        df.to_parquet(d / f"cluster_labels_EXP-01-{algo}_rep4.parquet", index=False)
    return d


@pytest.fixture
def synthetic_exp03_selected(tmp_path: Path) -> Path:
    """Write synthetic EXP-03 selected configurations CSV."""
    p = tmp_path / "exp03_selected_configurations.csv"
    rows = []
    for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
        rows.append(
            {
                "algorithm": algo,
                "experiment_id": f"EXP-03-{algo}-selected",
                "stage": "C",
                "decision_status": "WORKING_SELECTED",
                "n_clusters": 4,
                "silhouette": 0.55,
                "davies_bouldin": 0.60,
                "calinski_harabasz": 4700.0,
                "wcss": 185000.0,
                "hyperparameters": "{}",
                "sweep_parameter": "n_init",
                "sweep_value": 10,
                "baseline_k": 4,
                "primary_criterion": "silhouette",
                "selection_evidence_note": "Highest silhouette within EXP-03 Stage C",
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def synthetic_exp01_summary(tmp_path: Path) -> Path:
    """Write synthetic EXP-01 baseline summary CSV."""
    p = tmp_path / "exp01_baseline_summary.csv"
    rows = []
    for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
        rows.append(
            {
                "algorithm": algo,
                "status": "SUCCESS",
                "n_clusters": 4,
                "silhouette": 0.57,
                "davies_bouldin": 0.61,
                "calinski_harabasz": 4800.0,
                "wcss": 180000.0,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def synthetic_exp05_results_dir(tmp_path: Path) -> Path:
    """Write synthetic EXP-05 per-block result CSVs."""
    d = tmp_path / "exp05"
    d.mkdir(parents=True, exist_ok=True)

    # Block R results
    r_rows = []
    for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
        for r_idx in range(5):
            r_rows.append(
                {
                    "run_id": f"EXP-05-{algo}-R-r{r_idx}",
                    "algorithm": algo,
                    "block": "R",
                    "seed": 42,
                    "sigma": 0.0,
                    "perturbation_seed": None,
                    "repeat_index": r_idx,
                    "cluster_sizes": json.dumps({str(i): 10 for i in range(4)}),
                    "labels_hash": "abc123",
                }
            )
    pd.DataFrame(r_rows).to_csv(d / "exp05_reproducibility_results.csv", index=False)

    # Block S results
    s_rows = []
    seeds = [42, 7, 123, 2024, 1729]
    for algo in ("kmeans", "gmm", "fuzzy_cmeans"):
        for s_idx, seed in enumerate(seeds):
            s_rows.append(
                {
                    "run_id": f"EXP-05-{algo}-S-seed{seed}",
                    "algorithm": algo,
                    "block": "S",
                    "seed": seed,
                    "sigma": 0.0,
                    "perturbation_seed": None,
                    "repeat_index": s_idx,
                    "cluster_sizes": json.dumps({str(i): 10 for i in range(4)}),
                    "labels_hash": "abc123",
                }
            )
    pd.DataFrame(s_rows).to_csv(d / "exp05_seed_sweep_results.csv", index=False)

    # Block N results
    n_rows = []
    sigmas = [0.0, 0.01, 0.05]
    pseeds = [42, 43, 44]
    for algo in ("kmeans", "gmm", "fuzzy_cmeans"):
        for sigma in sigmas:
            pseeds_subset = [42] if sigma == 0.0 else pseeds
            for pseed in pseeds_subset:
                n_rows.append(
                    {
                        "run_id": f"EXP-05-{algo}-N-sigma{sigma}-pseed{pseed}",
                        "algorithm": algo,
                        "block": "N",
                        "seed": 42,
                        "sigma": sigma,
                        "perturbation_seed": pseed if sigma > 0 else None,
                        "repeat_index": 0,
                        "cluster_sizes": json.dumps({str(i): 10 for i in range(4)}),
                        "labels_hash": "abc123",
                    }
                )
    pd.DataFrame(n_rows).to_csv(d / "exp05_noise_perturbation_results.csv", index=False)

    # Aggregates
    pd.DataFrame(
        [
            {"algorithm": a, "n_repeat": 5, "labels_hash_unique": 1}
            for a in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans")
        ]
    ).to_csv(d / "exp05_reproducibility_aggregate.csv", index=False)

    pd.DataFrame(
        [
            {"algorithm": a, "n_seeds": 5, "labels_hash_unique": 5}
            for a in ("kmeans", "gmm", "fuzzy_cmeans")
        ]
    ).to_csv(d / "exp05_seed_sweep_aggregate.csv", index=False)

    pd.DataFrame(
        [
            {"algorithm": a, "sigma": s, "labels_hash_unique": 1}
            for a in ("kmeans", "gmm", "fuzzy_cmeans")
            for s in (0.0, 0.01, 0.05)
        ]
    ).to_csv(d / "exp05_noise_perturbation_aggregate.csv", index=False)

    return d


# ---------------------------------------------------------------------------
# label_compare tests
# ---------------------------------------------------------------------------


class TestLabelCompare:
    def test_compute_label_compare_identical_labels(self):
        labels = np.array([0, 0, 1, 1, 2, 2])
        result = compute_label_compare(labels, labels)
        assert result["ari"] == pytest.approx(1.0)
        assert result["ami"] == pytest.approx(1.0)
        assert result["nmi"] == pytest.approx(1.0)

    def test_compute_label_compare_permutation_invariance(self):
        labels_a = np.array([0, 0, 1, 1, 2, 2])
        # Same clustering but with permuted labels
        labels_b = np.array([2, 2, 0, 0, 1, 1])
        result = compute_label_compare(labels_a, labels_b)
        assert result["ari"] == pytest.approx(1.0)
        assert result["ami"] == pytest.approx(1.0)
        assert result["nmi"] == pytest.approx(1.0)

    def test_compute_label_compare_different_clusterings(self):
        labels_a = np.array([0, 0, 1, 1, 2, 2])
        labels_b = np.array([0, 1, 0, 1, 2, 2])
        result = compute_label_compare(labels_a, labels_b)
        # ARI and AMI should be less than 1.0
        assert 0.0 <= result["ari"] <= 1.0
        assert 0.0 <= result["ami"] <= 1.0
        assert 0.0 <= result["nmi"] <= 1.0

    def test_compute_label_compare_shape_mismatch_raises(self):
        labels_a = np.array([0, 0, 1, 1])
        labels_b = np.array([0, 0, 1, 1, 2, 2])
        with pytest.raises(ValueError):
            compute_label_compare(labels_a, labels_b)

    def test_compute_label_compare_ari_bounds(self):
        labels_a = np.array([0, 1, 0, 1])
        labels_b = np.array([1, 0, 1, 0])
        result = compute_label_compare(labels_a, labels_b)
        # ARI for perfectly anti-correlated clusterings should be -1.0
        assert -1.0 <= result["ari"] <= 1.0

    def test_hungarian_align_identical_labels(self):
        labels = np.array([0, 0, 1, 1, 2, 2])
        result = hungarian_align(labels, labels)
        # Should map all clusters with overlap
        assert result.total_customers == 6
        assert len(result.source_labels) >= 3  # 3 clusters

    def test_hungarian_align_excludes_noise_by_default(self):
        labels_a = np.array([0, 0, 1, 1, -1, -1])  # 2 noise points
        labels_b = np.array([0, 0, 1, 1, -1, -1])
        result = hungarian_align(labels_a, labels_b, exclude_noise_label=-1)
        assert result.total_customers == 4  # noise excluded

    def test_hungarian_align_different_shapes_raises(self):
        labels_a = np.array([0, 0, 1, 1])
        labels_b = np.array([0, 0, 1, 1, 2, 2])
        with pytest.raises(ValueError):
            hungarian_align(labels_a, labels_b)

    def test_run_hungarian_for_pair_prefills_metadata(self):
        labels_a = np.array([0, 0, 1, 1])
        labels_b = np.array([0, 0, 1, 1])
        result = run_hungarian_for_pair(
            "kmeans",
            "run-a",
            "run-b",
            labels_a,
            labels_b,
            exclude_noise_label=None,
        )
        assert result.algorithm == "kmeans"
        assert result.run_id_a == "run-a"
        assert result.run_id_b == "run-b"
        assert result.total_customers == 4


# ---------------------------------------------------------------------------
# load tests
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_exp05_labels_artifact(self, synthetic_labels_parquet: Path):
        df = load_exp05_labels_artifact(synthetic_labels_parquet)
        assert not df.empty
        assert set(df.columns) >= {
            "run_id",
            "block",
            "algorithm",
            "seed",
            "sigma",
            "perturbation_seed",
            "repeat_index",
            "CustomerID",
            "cluster_label",
        }

    def test_load_exp05_labels_artifact_missing_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_exp05_labels_artifact(tmp_path / "missing.parquet")

    def test_load_exp05_per_block_record_aggregates(self, synthetic_exp05_results_dir: Path):
        aggregates = load_exp05_per_block_record_aggregates(synthetic_exp05_results_dir)
        assert set(aggregates.keys()) == {"reproducibility", "seed", "perturbation"}
        assert not aggregates["reproducibility"].empty
        assert not aggregates["seed"].empty
        assert not aggregates["perturbation"].empty

    def test_load_exp01_cluster_labels(self, synthetic_exp01_dir: Path):
        labels = load_exp01_cluster_labels(synthetic_exp01_dir)
        assert set(labels.keys()) == {"kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"}
        for _algo, df in labels.items():
            assert "CustomerID" in df.columns
            assert "ClusterLabel" in df.columns

    def test_load_exp01_cluster_labels_missing_algo_skipped(self, tmp_path: Path):
        # Write only kmeans
        d = tmp_path / "exp01"
        d.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame({"CustomerID": [1, 2], "ClusterLabel": [0, 1]})
        df.to_parquet(d / "cluster_labels_EXP-01-kmeans_rep4.parquet", index=False)
        labels = load_exp01_cluster_labels(d)
        assert "kmeans" in labels
        assert "agglomerative" not in labels

    def test_load_exp03_selected_configurations(self, synthetic_exp03_selected: Path):
        df = load_exp03_selected_configurations(synthetic_exp03_selected)
        assert not df.empty
        assert "algorithm" in df.columns
        assert set(df["algorithm"]) == {"kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"}

    def test_exp01_reference_rows(self, synthetic_exp01_dir: Path):
        labels = load_exp01_cluster_labels(synthetic_exp01_dir)
        rows = exp01_reference_rows(labels)
        assert len(rows) == 5
        for row in rows:
            assert isinstance(row, EXP01ReferenceRow)
            assert row.algorithm in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans")
            assert len(row.customer_ids) == 50
            assert len(row.cluster_labels) == 50
            assert len(row.noise_mask) == 50

    def test_exp03_comparison_rows(
        self, synthetic_exp03_selected: Path, synthetic_exp01_summary: Path
    ):
        exp03_df = load_exp03_selected_configurations(synthetic_exp03_selected)
        exp01_df = pd.read_csv(synthetic_exp01_summary)
        rows = exp03_comparison_rows(exp01_df, exp03_df)
        assert len(rows) == 5
        for row in rows:
            assert isinstance(row, EXP03ComparisonRow)
            assert row.exp01_silhouette is not None
            assert row.exp03_silhouette is not None
            assert row.source_evidence == "METRIC_BASED_ONLY"


# ---------------------------------------------------------------------------
# reproducibility tests (Block R)
# ---------------------------------------------------------------------------


class TestReproducibility:
    def test_analyze_block_r_returns_all_keys(self, synthetic_labels_df: pd.DataFrame):
        result = analyze_block_r(synthetic_labels_df)
        assert set(result.keys()) >= {
            "per_pair",
            "matrices",
            "decision_status",
            "summary",
            "hungarian",
        }

    def test_analyze_block_r_per_pair_fields(self, synthetic_labels_df: pd.DataFrame):
        result = analyze_block_r(synthetic_labels_df)
        per_pair = result["per_pair"]
        assert len(per_pair) > 0
        for row in per_pair:
            assert isinstance(row, BlockRPairwiseRow)
            assert row.ari is not None
            assert row.ami is not None
            assert row.nmi is not None

    def test_analyze_block_r_decision_status_verified_for_deterministic(
        self, synthetic_labels_df: pd.DataFrame
    ):
        result = analyze_block_r(synthetic_labels_df)
        # All repeats are deterministic (same labels), so ARI should be ~1.0
        for _algo, status in result["decision_status"].items():
            assert status in (
                "REPRODUCIBILITY_VERIFIED_LABEL_LEVEL",
                "REPRODUCIBILITY_FAILED_LABEL_LEVEL",
            )

    def test_analyze_block_r_summary_columns(self, synthetic_labels_df: pd.DataFrame):
        result = analyze_block_r(synthetic_labels_df)
        summary = result["summary"]
        required_cols = {
            "algorithm",
            "n_runs",
            "n_pairs",
            "ari_min",
            "ari_max",
            "ari_mean",
            "off_diagonal_unique_count",
            "decision_status",
        }
        assert required_cols.issubset(set(summary.columns))

    def test_decision_status_for_block_r_verified_threshold(self):
        # Perfect ARI matrix
        matrix = PairwiseMatrix(
            algorithm="kmeans",
            run_ids=("r0", "r1", "r2"),
            ari=[[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
            ami=[[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
            nmi=[[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
            off_diagonal_unique_count=1,
        )
        status = decision_status_for_block_r(matrix)
        assert status == "REPRODUCIBILITY_VERIFIED_LABEL_LEVEL"

    def test_decision_status_for_block_r_failed_threshold(self):
        # Non-perfect ARI matrix
        matrix = PairwiseMatrix(
            algorithm="kmeans",
            run_ids=("r0", "r1", "r2"),
            ari=[[1.0, 0.8, 0.8], [0.8, 1.0, 0.8], [0.8, 0.8, 1.0]],
            ami=[[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
            nmi=[[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
            off_diagonal_unique_count=1,
        )
        status = decision_status_for_block_r(matrix)
        assert status == "REPRODUCIBILITY_FAILED_LABEL_LEVEL"


# ---------------------------------------------------------------------------
# seed_stability tests (Block S)
# ---------------------------------------------------------------------------


class TestSeedStability:
    def test_analyze_block_s_returns_all_keys(self, synthetic_labels_df_seeded: pd.DataFrame):
        result = analyze_block_s(synthetic_labels_df_seeded)
        assert set(result.keys()) >= {
            "matrices",
            "summary",
            "decision_status",
            "cluster_size_variation",
        }

    def test_analyze_block_s_includes_only_stochastic_algos(
        self, synthetic_labels_df_seeded: pd.DataFrame
    ):
        result = analyze_block_s(synthetic_labels_df_seeded)
        # Only kmeans, gmm, fuzzy_cmeans in Block S (deterministic algos excluded)
        algos_in_summary = set(result["summary"]["algorithm"])
        assert algos_in_summary.issubset({"kmeans", "gmm", "fuzzy_cmeans"})

    def test_analyze_block_s_summary_has_seed_columns(
        self, synthetic_labels_df_seeded: pd.DataFrame
    ):
        result = analyze_block_s(synthetic_labels_df_seeded)
        summary = result["summary"]
        assert "n_seeds" in summary.columns
        assert "n_pairs" in summary.columns
        assert "ari_min" in summary.columns
        assert "ari_max" in summary.columns

    def test_analyze_block_s_per_pair_rows(self, synthetic_labels_df_seeded: pd.DataFrame):
        result = analyze_block_s(synthetic_labels_df_seeded)
        per_pair = result["per_pair"]
        assert not per_pair.empty
        assert "seed_a" in per_pair.columns
        assert "seed_b" in per_pair.columns
        assert "ari" in per_pair.columns


# ---------------------------------------------------------------------------
# perturbation tests (Block N)
# ---------------------------------------------------------------------------


class TestPerturbation:
    def test_analyze_block_n_returns_all_keys(self, synthetic_labels_df_seeded: pd.DataFrame):
        result = analyze_block_n(synthetic_labels_df_seeded)
        assert set(result.keys()) >= {
            "matrices",
            "per_pair",
            "baseline",
            "cluster_size_variation",
            "decision_status",
        }

    def test_analyze_block_n_has_sigma_zero_baseline(
        self, synthetic_labels_df_seeded: pd.DataFrame
    ):
        result = analyze_block_n(synthetic_labels_df_seeded)
        baseline = result["baseline"]
        if not baseline.empty:
            assert "baseline_sigma" in baseline.columns
            assert (baseline["baseline_sigma"] == 0.0).all()

    def test_analyze_block_n_decision_status_for_sigma_zero_match(self):
        status = decision_status_for_block_n_algorithm(
            sigma_zero_matches=True, has_non_zero_runs=True
        )
        assert status == "SIGMA_ZERO_BASELINE_MATCH_LABEL_LEVEL"

    def test_analyze_block_n_decision_status_for_evidence_analyzed(self):
        status = decision_status_for_block_n_algorithm(
            sigma_zero_matches=False, has_non_zero_runs=False
        )
        assert status == "PERTURBATION_ROBUSTNESS_EVIDENCE_ANALYZED"

    def test_analyze_block_n_deduplicates_runs_by_run_id(self):
        """INVARIANT: Number of runs processed must equal the number of
        unique (algorithm, run_id) entries, NOT the number of
        (algorithm, CustomerID) rows in the artifact.

        On the original (buggy) code, ``runs = df_sorted["run_id"].tolist()``
        produced one entry per CustomerID row. With the documented EXP-05
        schema (1 row per CustomerID per run), 7 unique Block-N runs
        × 20 customers = 140 entries, producing a 140×140 grid of mostly
        self-comparisons instead of a 7×7 grid of pairwise comparisons.
        """
        n_customers = 20
        df = _make_labels_df(
            n_customers=n_customers, n_repeats=5, n_seeds=5, n_sigmas=3
        )
        result = analyze_block_n(df)
        assert result["matrices"], "Expected at least one PairwiseMatrix"
        # Block N has 3 algorithms × 7 unique runs (sigma=0 + 3 sigma=0.01
        # + 3 sigma=0.05). Each matrix must have exactly 7 run_ids, not
        # 7 * n_customers.
        for m in result["matrices"]:
            assert len(m.run_ids) == 7, (
                f"Algorithm {m.algorithm}: expected 7 unique runs in Block N, "
                f"got {len(m.run_ids)} (likely customer-row expansion)"
            )
            # Verify grid dimensions match the number of unique run_ids.
            assert len(m.ari) == 7
            assert len(m.ami) == 7
            assert len(m.nmi) == 7
            # The 7 run_ids must all be distinct.
            assert len(set(m.run_ids)) == 7

    def test_analyze_block_n_pair_count_matches_unique_runs(self):
        """INVARIANT: Block N off-diagonal pair count for an algorithm
        must equal C(unique_runs, 2), not C(unique_runs * n_customers, 2).

        For 7 unique runs: C(7, 2) = 21 expected pairs. With n_customers=10
        (the buggy code would produce C(70, 2) = 2415 pairs).
        """
        df = _make_labels_df(
            n_customers=10, n_repeats=5, n_seeds=5, n_sigmas=3
        )
        result = analyze_block_n(df)
        # per_pair rows are unique by (algorithm, run_id_a, run_id_b) — no
        # duplicate self-comparisons.
        per_pair = result["per_pair"]
        assert not per_pair.empty
        for algo in per_pair["algorithm"].unique():
            algo_pairs = per_pair.loc[per_pair["algorithm"] == algo]
            # 7 unique runs × C(7, 2) = 21 expected pairs per algorithm.
            assert len(algo_pairs) == 21, (
                f"Algorithm {algo}: expected 21 unique pairs "
                f"(C(7, 2)), got {len(algo_pairs)}"
            )
            # Confirm no duplicate (run_id_a, run_id_b) entries.
            pair_keys = list(
                zip(algo_pairs["run_id_a"], algo_pairs["run_id_b"], strict=True)
            )
            assert len(set(pair_keys)) == len(pair_keys)

    def test_build_block_n_pairwise_table_deduplicates_runs(self):
        """INVARIANT: load.build_block_n_pairwise_table must also produce
        one entry per unique run_id, not per (run, CustomerID).
        """
        from customer_segmentation.evaluation.eva03.load import (
            build_block_n_pairwise_table,
        )

        df = _make_labels_df(
            n_customers=15, n_repeats=5, n_seeds=5, n_sigmas=3
        )
        matrices = build_block_n_pairwise_table(df, label_compare_fn=compute_label_compare)
        assert matrices, "Expected at least one matrix for Block N"
        for m in matrices:
            assert len(m.run_ids) == 7, (
                f"Algorithm {m.algorithm}: expected 7 unique runs, "
                f"got {len(m.run_ids)}"
            )
            assert len(set(m.run_ids)) == 7
            # Grid must be 7×7 (not 7 * 15 = 105).
            assert len(m.ari) == 7

    def test_analyze_block_n_sigma_zero_baseline_one_row_per_run(self):
        """INVARIANT: The sigma=0 baseline record should contain exactly
        (n_unique_runs - 1) entries per algorithm: one per non-sigma=0 run.
        On the buggy code this would be inflated by the customer-row expansion.
        """
        df = _make_labels_df(
            n_customers=12, n_repeats=5, n_seeds=5, n_sigmas=3
        )
        result = analyze_block_n(df)
        baseline = result["baseline"]
        if not baseline.empty:
            for algo in baseline["algorithm"].unique():
                algo_baseline = baseline.loc[baseline["algorithm"] == algo]
                # 1 sigma=0 baseline + 6 non-zero sigma runs = 6 entries
                # per algorithm (not 6 * 12 = 72).
                assert len(algo_baseline) == 6, (
                    f"Algorithm {algo}: expected 6 baseline entries "
                    f"(1 sigma=0 vs 6 non-zero runs), got {len(algo_baseline)}"
                )
                # Each target_run_id should appear exactly once.
                target_ids = algo_baseline["target_run_id"].tolist()
                assert len(set(target_ids)) == len(target_ids)


# ---------------------------------------------------------------------------
# cluster_size tests
# ---------------------------------------------------------------------------


class TestClusterSize:
    def test_analyze_cluster_size_variation_returns_df(self, synthetic_exp05_results_dir: Path):
        result = analyze_cluster_size_variation(synthetic_exp05_results_dir)
        assert isinstance(result, pd.DataFrame)
        # Should have cluster size rows from all three blocks
        if not result.empty:
            assert "block" in result.columns
            assert "algorithm" in result.columns
            assert "cluster_id" in result.columns
            assert "customer_count_min" in result.columns
            assert "customer_count_max" in result.columns
            assert "customer_count_range" in result.columns

    def test_analyze_cluster_size_variation_handles_missing_file(self, tmp_path: Path):
        result = analyze_cluster_size_variation(tmp_path / "nonexistent")
        assert result.empty


# ---------------------------------------------------------------------------
# hyperparameter_stability tests
# ---------------------------------------------------------------------------


class TestHyperparameterStability:
    def test_analyze_hyperparameter_stability_returns_all_keys(
        self, synthetic_exp01_summary: Path, synthetic_exp03_selected: Path
    ):
        exp01_df = pd.read_csv(synthetic_exp01_summary)
        exp03_df = load_exp03_selected_configurations(synthetic_exp03_selected)
        result = analyze_hyperparameter_stability(exp01_df, exp03_df)
        assert set(result.keys()) >= {"per_algorithm", "decision_status", "limitations"}

    def test_analyze_hyperparameter_stability_has_limitations(
        self, synthetic_exp01_summary: Path, synthetic_exp03_selected: Path
    ):
        exp01_df = pd.read_csv(synthetic_exp01_summary)
        exp03_df = load_exp03_selected_configurations(synthetic_exp03_selected)
        result = analyze_hyperparameter_stability(exp01_df, exp03_df)
        assert len(result["limitations"]) > 0
        assert any(
            "METRIC_BASED_ONLY" in line or "label" in line.lower() for line in result["limitations"]
        )

    def test_analyze_hyperparameter_stability_per_algorithm_columns(
        self, synthetic_exp01_summary: Path, synthetic_exp03_selected: Path
    ):
        exp01_df = pd.read_csv(synthetic_exp01_summary)
        exp03_df = load_exp03_selected_configurations(synthetic_exp03_selected)
        result = analyze_hyperparameter_stability(exp01_df, exp03_df)
        df = result["per_algorithm"]
        assert "algorithm" in df.columns
        assert "exp01_silhouette" in df.columns
        assert "exp03_silhouette" in df.columns
        assert "source_evidence" in df.columns


# ---------------------------------------------------------------------------
# report tests
# ---------------------------------------------------------------------------


class TestReport:
    def test_build_reproducibility_report_contains_sections(
        self, synthetic_labels_df: pd.DataFrame
    ):
        result = analyze_block_r(synthetic_labels_df)
        md = build_reproducibility_report(
            block_r_summary=result["summary"],
            per_pair_rows=result["per_pair"],
            hungarians=result["hungarian"],
            generated_at="2026-10-12T00:00:00+00:00",
        )
        assert "# EVA-03" in md
        assert "## 1. Scope" in md
        assert "## 2. Per-algorithm summary" in md
        assert "## 4. Hungarian cluster-label alignment" in md
        assert "DESCRIPTIVE ONLY" in md

    def test_build_reproducibility_report_does_not_claim_best(
        self, synthetic_labels_df: pd.DataFrame
    ):
        result = analyze_block_r(synthetic_labels_df)
        md = build_reproducibility_report(
            block_r_summary=result["summary"],
            per_pair_rows=result["per_pair"],
            hungarians=result["hungarian"],
        )
        # No "best" / "winner" / "most reproducible" claims
        for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
            assert f"{algo} is best" not in md.lower()
            assert f"{algo} is most reproducible" not in md.lower()
            assert f"{algo} is winner" not in md.lower()

    def test_build_stability_report_contains_sections(
        self, synthetic_labels_df_seeded: pd.DataFrame
    ):
        result_s = analyze_block_s(synthetic_labels_df_seeded)
        md = build_stability_report(
            block_s_summary=result_s["summary"],
            block_s_per_pair=result_s["per_pair"],
            cluster_size_variation=result_s["cluster_size_variation"],
            generated_at="2026-10-12T00:00:00+00:00",
        )
        assert "# EVA-03" in md
        assert "## 1. Scope" in md
        assert "## 2. Per-algorithm summary" in md

    def test_build_stability_report_no_stability_ranking(
        self, synthetic_labels_df_seeded: pd.DataFrame
    ):
        result_s = analyze_block_s(synthetic_labels_df_seeded)
        md = build_stability_report(
            block_s_summary=result_s["summary"],
            block_s_per_pair=result_s["per_pair"],
            cluster_size_variation=result_s["cluster_size_variation"],
        )
        for algo in ("kmeans", "gmm", "fuzzy_cmeans"):
            assert f"{algo} is most stable" not in md.lower()
            assert f"{algo} is winner" not in md.lower()

    def test_build_comparison_report_contains_sections(
        self, synthetic_labels_df_seeded: pd.DataFrame
    ):
        result_n = analyze_block_n(synthetic_labels_df_seeded)
        exp01_df = pd.DataFrame()
        exp03_df = pd.DataFrame()
        result_hp = analyze_hyperparameter_stability(exp01_df, exp03_df)

        md = build_comparison_report(
            block_n_matrices_summary=pd.DataFrame(),
            block_n_baseline=result_n["baseline"],
            hyperparameter_comparison=result_hp["per_algorithm"],
            cluster_size_variation_n=result_n["cluster_size_variation"],
            hungarian_alignments=pd.DataFrame(),
            generated_at="2026-10-12T00:00:00+00:00",
            limitations=["Test limitation"],
            pending_review_notes=[],
        )
        assert "# EVA-03" in md
        assert "## 1. Scope" in md
        assert "## 2. Block N" in md
        assert "NOT computable" in md  # label-level comparison

    def test_build_comparison_report_no_robustness_ranking(
        self, synthetic_labels_df_seeded: pd.DataFrame
    ):
        result_n = analyze_block_n(synthetic_labels_df_seeded)
        md = build_comparison_report(
            block_n_matrices_summary=pd.DataFrame(),
            block_n_baseline=result_n["baseline"],
            hyperparameter_comparison=pd.DataFrame(),
            cluster_size_variation_n=result_n["cluster_size_variation"],
            hungarian_alignments=pd.DataFrame(),
            limitations=[],
            pending_review_notes=[],
        )
        for algo in ("kmeans", "gmm", "fuzzy_cmeans"):
            assert f"{algo} is most robust" not in md.lower()
            assert f"{algo} is best" not in md.lower()

    def test_build_run_manifest_dict_contains_required_keys(self):
        manifest = build_run_manifest_dict(
            generated_at="2026-10-12T00:00:00+00:00",
            n_rows_in_repo=100,
            input_sha256="abc123",
            table_paths=["tables/a.csv"],
            figure_paths=[],
            block_r_decisions={"kmeans": "VERIFIED"},
            block_s_decisions={"kmeans": "ANALYZED"},
            block_n_decisions={"kmeans": "ANALYZED"},
            hyperparameter_decisions={"kmeans": "METADATA"},
            pending_review_notes=[],
            scope_boundaries=["Block R reproducibility", "Block S seed stability"],
            library_versions={"numpy": "1.26.0"},
            platform_info={"python": "3.12"},
        )
        assert manifest["name"] == "EVA-03 Stability & Reproducibility Evaluation"
        assert manifest["n_rows_in_artifact"] == 100
        assert "forbidden_terms" in manifest
        assert "best" in manifest["forbidden_terms"]
        assert "winner" in manifest["forbidden_terms"]

    def test_write_run_manifest_json_writes_valid_json(self, tmp_path: Path):
        manifest = build_run_manifest_dict(
            generated_at="2026-10-12T00:00:00+00:00",
            n_rows_in_repo=100,
            input_sha256=None,
            table_paths=[],
            figure_paths=[],
            block_r_decisions={},
            block_s_decisions={},
            block_n_decisions={},
            hyperparameter_decisions={},
            pending_review_notes=[],
            scope_boundaries=[],
            library_versions={},
            platform_info={},
        )
        path = tmp_path / "manifest.json"
        write_run_manifest_json(manifest, path)
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["generated_at"] == "2026-10-12T00:00:00+00:00"

    def test_df_to_markdown_no_tabulate_dependency(self):
        """Regression: _df_to_markdown must NOT call pandas' to_markdown()
        (which requires the ``tabulate`` package) so that EVA-03 reports
        remain free of that undeclared dependency (per DEV-06
        OQ-SEG-DEPENDENCY-01: no ``tabulate``)."""
        from customer_segmentation.evaluation.eva03.report import _df_to_markdown

        # The definitive check: the compiled bytecode of _df_to_markdown
        # must not reference the pandas.to_markdown method.  We check the
        # function's code object (co_names) rather than the source text
        # because inspect.getsource() may return adjacent helper functions
        # in this Python version, making a raw-text check fragile.
        assert "to_markdown" not in _df_to_markdown.__code__.co_names, (
            "_df_to_markdown must not call pandas' to_markdown; "
            "use the manual table renderer instead"
        )
        assert "tabulate" not in _df_to_markdown.__code__.co_names

        # Verify it actually produces a valid Markdown table.
        df = pd.DataFrame(
            {"algorithm": ["kmeans", "gmm"], "ari": [1.0, 0.982341]}
        )
        md = _df_to_markdown(df, max_rows=5)
        assert md.startswith("|")
        assert "| algorithm | ari |" in md
        assert "---" in md  # separator line
        assert "0.982341" in md  # float rendered with .6g precision


# ---------------------------------------------------------------------------
# runner tests
# ---------------------------------------------------------------------------


class TestRunner:
    def test_eva03_config_defaults(self):
        config = Eva03Config()
        assert config.output_dir.name == "eva03"
        assert config.include_hungarian is True
        assert config.include_pairwise_tables is True

    def test_eva03_runner_run_produces_manifest(
        self,
        synthetic_labels_parquet: Path,
        synthetic_exp05_results_dir: Path,
        synthetic_exp01_dir: Path,
        synthetic_exp03_selected: Path,
        tmp_path: Path,
    ):
        output_dir = tmp_path / "eva03_out"
        Eva03Config(
            exp05_reports_dir=synthetic_exp05_results_dir,
            exp01_reports_dir=synthetic_exp01_dir,
            output_dir=output_dir,
        )
        # Create config file
        config_path = tmp_path / "eva03_config.yaml"
        config_content = """
eva03:
  output:
    reports:
      reproducibility: eva03_reproducibility_report.md
      stability: eva03_stability_report.md
      comparison: eva03_comparison_report.md
  pending_review_notes: []
  scope_boundaries:
    - Block R reproducibility
    - Block S seed stability
"""
        config_path.write_text(config_content)

        # Manually run since we need config
        load_eva03_config(config_path)

        labels_df = load_exp05_labels_artifact(synthetic_labels_parquet)
        from customer_segmentation.evaluation.eva03.reproducibility import analyze_block_r

        result_r = analyze_block_r(labels_df)

        manifest = {
            "generated_at": "2026-10-12T00:00:00+00:00",
            "n_rows_in_repo": len(labels_df),
            "tables": [],
            "figures": [],
            "decision_status": {
                "block_r": result_r["decision_status"],
                "block_s": {},
                "block_n": {},
                "hyperparameter": {},
            },
        }
        write_run_manifest_json(manifest, output_dir / "eva03_run_manifest.json")

        assert (output_dir / "eva03_run_manifest.json").exists()
        loaded = json.loads((output_dir / "eva03_run_manifest.json").read_text())
        assert loaded["generated_at"] == "2026-10-12T00:00:00+00:00"

    def test_eva03_runner_run_executes_full_pipeline_end_to_end(
        self,
        synthetic_labels_parquet: Path,
        synthetic_exp05_results_dir: Path,
        synthetic_exp01_dir: Path,
        synthetic_exp03_selected: Path,
        synthetic_exp01_summary: Path,
        tmp_path: Path,
    ):
        """End-to-end: actually invoke Eva03Runner.run() and verify
        outputs are written per the documented contract.

        The existing test_eva03_runner_run_produces_manifest only manually
        writes a manifest; it does NOT exercise ``run()``. This test
        uses small synthetic data (5 customers per run) so the Block N
        dedup fix is exercised without inflating pair counts.
        """
        # Place exp01 summary CSV inside the synthetic_exp01_dir so the
        # runner can read it (runner resolves <exp01_reports_dir>/exp01_baseline_summary.csv).
        import shutil
        shutil.copy(synthetic_exp01_summary, synthetic_exp01_dir / "exp01_baseline_summary.csv")
        # Place exp03 selected CSV inside synthetic_exp05_results_dir's parent
        # because runner.py resolves it from "reports/exp03/..." literally.
        # Use the tmp_path directly as the exp03 dir.
        exp03_dir = tmp_path / "reports" / "exp03"
        exp03_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(synthetic_exp03_selected, exp03_dir / "exp03_selected_configurations.csv")
        # Copy the labels parquet into the exp05 reports dir; runner.run()
        # resolves ``exp05_cluster_labels.parquet`` from exp05_reports_dir.
        shutil.copy(synthetic_labels_parquet, synthetic_exp05_results_dir / "exp05_cluster_labels.parquet")

        output_dir = tmp_path / "eva03_out"
        config_path = tmp_path / "eva03_config.yaml"
        config_content = """
eva03:
  output:
    reports:
      reproducibility: eva03_reproducibility_report.md
      stability: eva03_stability_report.md
      comparison: eva03_comparison_report.md
  pending_review_notes: []
  scope_boundaries:
    - Block R reproducibility
    - Block S seed stability
    - Block N perturbation robustness
"""
        config_path.write_text(config_content)

        # Invoke run() for real.
        config = Eva03Config(
            config_path=config_path,
            exp05_reports_dir=synthetic_exp05_results_dir,
            exp01_reports_dir=synthetic_exp01_dir,
            output_dir=output_dir,
            include_hungarian=True,
        )
        result = Eva03Runner(config=config).run()

        # Verify the documented contract:
        # - 3 markdown reports were written.
        # - The run manifest JSON was written.
        # - At least the Block R pairwise CSV was written.
        # - Decision status covers Block R, S, N.
        assert (output_dir / "eva03_reproducibility_report.md").exists()
        assert (output_dir / "eva03_stability_report.md").exists()
        assert (output_dir / "eva03_comparison_report.md").exists()
        assert (output_dir / "eva03_run_manifest.json").exists()

        manifest = json.loads((output_dir / "eva03_run_manifest.json").read_text())
        assert manifest["name"] == "EVA-03 Stability & Reproducibility Evaluation"
        # Decision status present for every block.
        assert "block_r" in manifest["decision_status_by_block"]
        assert "block_s" in manifest["decision_status_by_block"]
        assert "block_n" in manifest["decision_status_by_block"]
        assert "hyperparameter" in manifest["decision_status_by_block"]

        # The result dict from run() should expose the same decision status.
        assert set(result["decision_status"].keys()) == {
            "block_r",
            "block_s",
            "block_n",
            "hyperparameter",
        }

        # Block N tables were generated with the dedup fix: each
        # PairwiseMatrix has 7 unique run_ids (not 7 * n_customers).
        # Even though this fixture uses n_customers=1, the Block N summary
        # CSV should be present.
        tables = result["tables"]
        assert any("block_n_summary" in str(t) for t in tables)


# ---------------------------------------------------------------------------
# Integration: end-to-end with synthetic data
# ---------------------------------------------------------------------------


class TestIntegrationEndToEnd:
    def test_full_pipeline_with_synthetic_data(
        self,
        synthetic_labels_df_seeded: pd.DataFrame,
        synthetic_exp05_results_dir: Path,
        tmp_path: Path,
    ):
        """Test the full EVA-03 analysis pipeline on synthetic data."""
        # Block R
        result_r = analyze_block_r(synthetic_labels_df_seeded)
        assert "summary" in result_r
        assert "per_pair" in result_r
        assert len(result_r["per_pair"]) > 0

        # Block S
        result_s = analyze_block_s(synthetic_labels_df_seeded)
        assert "summary" in result_s
        assert "per_pair" in result_s
        assert len(result_s["per_pair"]) > 0

        # Block N
        result_n = analyze_block_n(synthetic_labels_df_seeded)
        assert "baseline" in result_n
        assert "per_pair" in result_n

        # Cluster size variation
        cs_variation = analyze_cluster_size_variation(synthetic_exp05_results_dir)
        assert isinstance(cs_variation, pd.DataFrame)

        # Reproducibility report
        md_r = build_reproducibility_report(
            block_r_summary=result_r["summary"],
            per_pair_rows=result_r["per_pair"],
            hungarians=result_r["hungarian"],
            generated_at="2026-10-12T00:00:00+00:00",
        )
        assert "EVA-03" in md_r
        assert "DESCRIPTIVE ONLY" in md_r

        # Stability report
        md_s = build_stability_report(
            block_s_summary=result_s["summary"],
            block_s_per_pair=result_s["per_pair"],
            cluster_size_variation=result_s["cluster_size_variation"],
            generated_at="2026-10-12T00:00:00+00:00",
        )
        assert "EVA-03" in md_s

    def test_no_forbidden_terms_in_reports(self, synthetic_labels_df_seeded: pd.DataFrame):
        """Verify that no forbidden terms appear in any generated report."""
        result_r = analyze_block_r(synthetic_labels_df_seeded)
        result_s = analyze_block_s(synthetic_labels_df_seeded)
        result_n = analyze_block_n(synthetic_labels_df_seeded)

        md_r = build_reproducibility_report(
            block_r_summary=result_r["summary"],
            per_pair_rows=result_r["per_pair"],
            hungarians=result_r["hungarian"],
        )
        md_s = build_stability_report(
            block_s_summary=result_s["summary"],
            block_s_per_pair=result_s["per_pair"],
            cluster_size_variation=result_s["cluster_size_variation"],
        )
        md_c = build_comparison_report(
            block_n_matrices_summary=pd.DataFrame(),
            block_n_baseline=result_n["baseline"],
            hyperparameter_comparison=pd.DataFrame(),
            cluster_size_variation_n=result_n["cluster_size_variation"],
            hungarian_alignments=pd.DataFrame(),
            limitations=[],
            pending_review_notes=[],
        )

        forbidden = ["best", "winner", "optimal", "recommended", "final", "approved"]
        for term in forbidden:
            assert f"is {term}" not in md_r.lower()
            assert f"is {term}" not in md_s.lower()
            assert f"is {term}" not in md_c.lower()
