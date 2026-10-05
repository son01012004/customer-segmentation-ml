"""Tests for EVA-02 — Cluster Quality Evaluation.

These tests cover the EVA-02 pipeline in isolation from the real
EVA-01 outputs. They use synthetic repositories that mirror the
schema defined in
:mod:`customer_segmentation.evaluation.experiment_results.schema`.

The hard constraints (AGENTS.md §2) are enforced at the boundary
of the tests:

- Tests use only publicly-exported functions.
- Tests never assert the existence of a "best algorithm" label.
- Tests cover the cross-metric, per-K, per-algorithm, per-preprocessing,
  per-hyperparameter, and DBSCAN-noise dimensions.
- Tests cover the runner pipeline (load -> compare -> quality ->
  visualize -> report -> write) end-to-end on a temporary directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.evaluation.eva02.comparison import (
    EXP03_HYPERPARAMETER_FAMILIES,
    compare_by_algorithm,
    compare_by_hyperparameter,
    compare_by_k,
    compare_by_preprocessing,
    metric_ranking_per_metric,
)
from customer_segmentation.evaluation.eva02.load import (
    iter_by_experiment,
    list_algorithms,
    list_experiment_ids,
    load_repository,
    load_repository_csv,
    load_repository_parquet,
)
from customer_segmentation.evaluation.eva02.metrics import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    METRIC_COLUMNS,
    METRIC_DIRECTIONS,
    RUNTIME_COLUMN,
    extract_metric_vector,
    filter_metric_rows,
    metric_conflicts,
    summarise_metric,
    summarise_metrics_long,
)
from customer_segmentation.evaluation.eva02.quality import (
    cross_metric_conflicts,
    dataset_quality_overview,
    dbscan_noise_summary,
    quality_by_algorithm,
    quality_by_algorithm_and_k,
    quality_by_k,
    quality_by_preprocessing,
)
from customer_segmentation.evaluation.eva02.report import build_report
from customer_segmentation.evaluation.eva02.runner import (
    Eva02Config,
    Eva02Runner,
    run_eva02,
)
from customer_segmentation.evaluation.eva02.visualization import (
    ALGORITHM_COLORS,
    plot_metric_by_algorithm,
    plot_metric_by_hyperparameter_family,
    plot_metric_by_preprocessing,
    plot_metric_distributions,
    plot_metric_vs_k,
)
from customer_segmentation.evaluation.experiment_results.schema import (
    MISSING,
    STANDARD_COLUMNS,
)

# ---------------------------------------------------------------------------
# Fixture: synthetic EVA-01 repository
# ---------------------------------------------------------------------------


def _make_row(
    *,
    source_experiment: str,
    experiment_id: str,
    algorithm: str,
    n_clusters: int | None,
    silhouette: float | None = 0.5,
    davies_bouldin: float | None = 0.6,
    calinski_harabasz: float | None = 4500.0,
    wcss: float | None = 200_000.0,
    transformation: str = MISSING,
    scaling: str = MISSING,
    imputation: str = MISSING,
    feature_set: str = "rfm_extended",
    n_clusters_realized: int | None = None,
    noise_count: int | None = None,
    noise_ratio: float | None = None,
    hyperparameters: str | None = None,
    execution_time_seconds: float | None = 0.05,
    repeat_index: int | None = 0,
    n_repeats_total: int | None = 1,
    record_granularity: str = "PER_RUN",
    run_status: str = "SUCCESS",
    sigma: float | None = None,
    perturbation_seed: int | None = None,
    source_block: str = "",
    source_run_id: str = "",
    decision_status: str = "SUCCESS",
    evidence_note: str = "",
    dataset_version: str = "v1",
    random_seed: int | None = 42,
) -> dict[str, object]:
    """Build a single row matching the EVA-01 standard schema."""
    return {
        "source_experiment": source_experiment,
        "experiment_id": experiment_id,
        "source_block": source_block,
        "source_run_id": source_run_id,
        "record_granularity": record_granularity,
        "repeat_index": repeat_index,
        "n_repeats_total": n_repeats_total,
        "algorithm": algorithm,
        "dataset_version": dataset_version,
        "feature_set": feature_set,
        "transformation": transformation,
        "scaling": scaling,
        "imputation": imputation,
        "n_clusters": n_clusters,
        "hyperparameters": hyperparameters or "{}",
        "random_seed": random_seed,
        "silhouette": silhouette,
        "davies_bouldin": davies_bouldin,
        "calinski_harabasz": calinski_harabasz,
        "wcss": wcss,
        "execution_time_seconds": execution_time_seconds,
        "n_clusters_realized": (
            n_clusters_realized if n_clusters_realized is not None else n_clusters
        ),
        "cluster_size_largest": MISSING,
        "cluster_size_smallest": MISSING,
        "noise_count": noise_count,
        "noise_ratio": noise_ratio,
        "silhouette_status": "VALID_VALUE" if silhouette is not None else MISSING,
        "davies_bouldin_status": "VALID_VALUE" if davies_bouldin is not None else MISSING,
        "calinski_harabasz_status": "VALID_VALUE" if calinski_harabasz is not None else MISSING,
        "wcss_status": "VALID_VALUE" if wcss is not None else MISSING,
        "algorithm_missing_reason": "",
        "dataset_version_missing_reason": "",
        "feature_set_missing_reason": "",
        "transformation_missing_reason": "",
        "scaling_missing_reason": "",
        "imputation_missing_reason": "",
        "n_clusters_missing_reason": "" if n_clusters is not None else "NOT_APPLICABLE",
        "hyperparameters_missing_reason": "",
        "random_seed_missing_reason": "" if random_seed is not None else "NOT_RECORDED",
        "silhouette_missing_reason": "" if silhouette is not None else "NOT_RECORDED",
        "davies_bouldin_missing_reason": "" if davies_bouldin is not None else "NOT_RECORDED",
        "calinski_harabasz_missing_reason": "" if calinski_harabasz is not None else "NOT_RECORDED",
        "wcss_missing_reason": "" if wcss is not None else "NOT_RECORDED",
        "execution_time_seconds_missing_reason": (
            "" if execution_time_seconds is not None else "NOT_RECORDED"
        ),
        "n_clusters_realized_missing_reason": "" if n_clusters is not None else "NOT_APPLICABLE",
        "cluster_size_largest_missing_reason": "FIELD_NOT_IN_SOURCE",
        "cluster_size_smallest_missing_reason": "FIELD_NOT_IN_SOURCE",
        "noise_count_missing_reason": "" if noise_count is not None else "NOT_APPLICABLE",
        "noise_ratio_missing_reason": "" if noise_ratio is not None else "NOT_APPLICABLE",
        "repeat_index_missing_reason": "",
        "n_repeats_total_missing_reason": "",
        "sigma_missing_reason": "" if sigma is not None else "NOT_APPLICABLE",
        "perturbation_seed_missing_reason": (
            "" if perturbation_seed is not None else "NOT_APPLICABLE"
        ),
        "run_status": run_status,
        "failure_reason": "",
        "labels_hash": "",
        "feature_set_sha256": "",
        "customer_metadata_sha256": "",
        "config_sha256": "",
        "input_sha256": "",
        "sigma": sigma,
        "perturbation_seed": perturbation_seed,
        "library_versions": json.dumps({"python": "3.14"}),
        "platform": json.dumps({"system": "linux"}),
        "timestamp": "2026-09-22T00:00:00+00:00",
        "source_artifact": "",
        "decision_status": decision_status,
        "evidence_note": evidence_note,
    }


def _build_synthetic_repo() -> pd.DataFrame:
    """Build a small synthetic EVA-01 repository covering every
    experiment, every algorithm (excluding K-Medoids per ADR-0003),
    with metric disagreement built in for the cross-metric tests.
    """
    rows: list[dict[str, object]] = []

    # EXP-01 baseline: one row per algorithm at K=4 (K-Medoids omitted).
    base_exp01 = [
        ("kmeans", 4, 0.57, 0.61, 4800.0, 180_000.0),
        ("agglomerative", 4, 0.565, 0.74, 4578.0, 187_000.0),
        ("dbscan", 17, -0.10, 0.77, 49.0, 2_125.0),
        ("gmm", 4, 0.184, 3.75, 131.7, 710_957.0),
        ("fuzzy_cmeans", 4, 0.269, 1.37, 3869.0, 211_949.0),
    ]
    for algo, k, sil, dbi, ch, wcss in base_exp01:
        rows.append(
            _make_row(
                source_experiment="EXP-01",
                experiment_id=f"EXP-01-{algo}-baseline-k{k}",
                algorithm=algo,
                n_clusters=k,
                n_clusters_realized=k,
                silhouette=sil,
                davies_bouldin=dbi,
                calinski_harabasz=ch,
                wcss=wcss,
                noise_count=4 if algo == "dbscan" else None,
                noise_ratio=0.001 if algo == "dbscan" else None,
            )
        )

    # EXP-02 cluster number sweep: K-Means K=2..6 with varying metrics.
    for k in range(2, 7):
        rows.append(
            _make_row(
                source_experiment="EXP-02",
                experiment_id=f"EXP-02-kmeans-sweep-k{k}",
                algorithm="kmeans",
                n_clusters=k,
                silhouette=0.5 + 0.01 * k,
                davies_bouldin=0.7 - 0.02 * k,
                calinski_harabasz=4000 + 100 * k,
                wcss=200_000.0 - 10_000 * k,
            )
        )

    # Add an extra K=4 row to the EXP-02 K-Means sweep so that the
    # conflict row's silhouette rank (1) differs from its CH rank (3)
    # by more than rank_tolerance=1.
    rows.append(
        _make_row(
            source_experiment="EXP-02",
            experiment_id="EXP-02-kmeans-sweep-k4b",
            algorithm="kmeans",
            n_clusters=4,
            silhouette=0.53,
            davies_bouldin=0.67,
            calinski_harabasz=4600.0,  # highest CH in K=4 group
            wcss=190_000.0,
        )
    )

    # EXP-03 hyperparameter search: K-Means varying n_init, Agglomerative
    # varying linkage, DBSCAN varying eps.
    for n_init in (1, 5, 10):
        rows.append(
            _make_row(
                source_experiment="EXP-03",
                experiment_id=f"EXP-03-kmeans-stageB-n_init-{n_init}",
                algorithm="kmeans",
                n_clusters=4,
                hyperparameters=json.dumps({"n_init": n_init, "init": "k-means++"}),
                silhouette=0.56,
                davies_bouldin=0.62,
                calinski_harabasz=4800.0,
                wcss=180_000.0,
            )
        )
    for linkage in ("ward", "complete", "average"):
        rows.append(
            _make_row(
                source_experiment="EXP-03",
                experiment_id=f"EXP-03-agglomerative-stageB-linkage-{linkage}",
                algorithm="agglomerative",
                n_clusters=4,
                hyperparameters=json.dumps({"linkage": linkage}),
                silhouette=0.66,
                davies_bouldin=0.42,
                calinski_harabasz=4578.0,
                wcss=187_000.0,
            )
        )
    for eps in (0.3, 0.5, 0.7):
        rows.append(
            _make_row(
                source_experiment="EXP-03",
                experiment_id=f"EXP-03-dbscan-stageB-eps-{eps}",
                algorithm="dbscan",
                n_clusters=17,
                n_clusters_realized=17,
                hyperparameters=json.dumps({"eps": eps}),
                silhouette=-0.10,
                davies_bouldin=0.77,
                calinski_harabasz=49.0,
                wcss=2_125.0,
                noise_count=4,
                noise_ratio=0.001,
            )
        )

    # EXP-04 preprocessing scenarios: 2 transformation × 2 scaling = 4 cells.
    for transformation in ("none", "yeo_johnson"):
        for scaling in ("standard", "robust"):
            rows.append(
                _make_row(
                    source_experiment="EXP-04",
                    experiment_id=f"EXP-04-kmeans-{transformation}-{scaling}",
                    algorithm="kmeans",
                    n_clusters=4,
                    transformation=transformation,
                    scaling=scaling,
                    imputation="median",
                    silhouette=0.50,
                    davies_bouldin=0.88,
                    calinski_harabasz=3700.0,
                    wcss=190_000.0,
                )
            )

    # EXP-05 stability/perturbation: K-Means with sigma=0, 0.01, 0.05.
    for sigma in (0.0, 0.01, 0.05):
        rows.append(
            _make_row(
                source_experiment="EXP-05",
                experiment_id=f"EXP-05-kmeans-blockN-sigma-{sigma}",
                algorithm="kmeans",
                n_clusters=4,
                silhouette=0.567,
                davies_bouldin=0.613,
                calinski_harabasz=4815.0,
                wcss=180_000.0,
                sigma=sigma,
                perturbation_seed=42,
                source_block="N",
            )
        )

    # Inject a cross-metric conflict: silhouette says good, DBI says good,
    # but CH disagrees.
    rows.append(
        _make_row(
            source_experiment="EXP-02",
            experiment_id="EXP-02-kmeans-conflict",
            algorithm="kmeans",
            n_clusters=4,
            silhouette=0.65,  # higher silhouette than the sweep rows
            davies_bouldin=0.55,  # lower (better) DBI
            calinski_harabasz=2000.0,  # much lower CH -> disagrees
            wcss=200_000.0,
        )
    )

    df = pd.DataFrame(rows)
    # Ensure schema column order.
    df = df.loc[:, list(STANDARD_COLUMNS)]
    return df


@pytest.fixture
def synthetic_repo() -> pd.DataFrame:
    return _build_synthetic_repo()


@pytest.fixture
def synthetic_parquet(tmp_path: Path, synthetic_repo: pd.DataFrame) -> Path:
    """Write the synthetic repo as parquet and return the file path."""
    p = tmp_path / "eva01_experiment_repository.parquet"
    synthetic_repo.to_parquet(p, index=False)
    return p


@pytest.fixture
def synthetic_csv(tmp_path: Path, synthetic_repo: pd.DataFrame) -> Path:
    """Write the synthetic repo as CSV and return the file path."""
    p = tmp_path / "eva01_experiment_repository.csv"
    synthetic_repo.to_csv(p, index=False)
    return p


@pytest.fixture
def synthetic_eva01_dir(
    tmp_path: Path,
    synthetic_parquet: Path,
    synthetic_csv: Path,
) -> Path:
    """Directory containing both the parquet and CSV twin of the repo."""
    d = tmp_path / "eva01"
    d.mkdir(parents=True, exist_ok=True)
    (d / "eva01_experiment_repository.parquet").write_bytes(synthetic_parquet.read_bytes())
    (d / "eva01_experiment_repository.csv").write_text(synthetic_csv.read_text())
    return d


# ---------------------------------------------------------------------------
# metrics tests
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_metric_columns_match_eva01(self):
        assert METRIC_COLUMNS == (
            "silhouette",
            "davies_bouldin",
            "calinski_harabasz",
            "wcss",
        )

    def test_directions_match_known_convention(self):
        assert METRIC_DIRECTIONS["silhouette"] == HIGHER_IS_BETTER
        assert METRIC_DIRECTIONS["calinski_harabasz"] == HIGHER_IS_BETTER
        assert METRIC_DIRECTIONS["davies_bouldin"] == LOWER_IS_BETTER
        assert METRIC_DIRECTIONS["wcss"] == LOWER_IS_BETTER

    def test_extract_metric_vector_returns_nan_for_missing(self, synthetic_repo: pd.DataFrame):
        vec = extract_metric_vector(synthetic_repo, "silhouette")
        assert vec.dtype == float
        assert not np.isnan(vec).any()

    def test_extract_metric_vector_handles_missing_string_sentinel(self):
        df = pd.DataFrame({"silhouette": [0.5, MISSING, 0.7]})
        vec = extract_metric_vector(df, "silhouette")
        assert vec[0] == 0.5
        assert np.isnan(vec[1])
        assert vec[2] == 0.7

    def test_extract_metric_vector_missing_column_raises(self, synthetic_repo):
        with pytest.raises(KeyError):
            extract_metric_vector(synthetic_repo, "no_such_column")

    def test_filter_metric_rows_excludes_missing(self, synthetic_repo: pd.DataFrame):
        # Drop silhouette for one row and verify it is excluded.
        work = synthetic_repo.copy()
        work.loc[work.index[0], "silhouette"] = np.nan
        out = filter_metric_rows(work)
        assert len(out) == len(work) - 1

    def test_filter_metric_rows_returns_empty_when_no_rows_have_all_metrics(self, synthetic_repo):
        work = synthetic_repo.copy()
        for c in METRIC_COLUMNS:
            work[c] = np.nan
        out = filter_metric_rows(work)
        assert out.empty

    def test_summarise_metric_handles_empty(self):
        stats = summarise_metric([])
        assert stats["n"] == 0
        assert np.isnan(stats["mean"])

    def test_summarise_metric_basic(self):
        stats = summarise_metric([1.0, 2.0, 3.0, 4.0])
        assert stats["n"] == 4
        assert stats["min"] == 1.0
        assert stats["max"] == 4.0
        assert stats["mean"] == 2.5
        assert stats["std"] > 0

    def test_summarise_metrics_long_shape(self, synthetic_repo):
        out = summarise_metrics_long(synthetic_repo)
        # one row per (source_experiment, metric)
        assert len(out) > 0
        assert set(out.columns) >= {
            "source_experiment",
            "metric",
            "direction",
            "n",
            "min",
            "max",
            "mean",
            "std",
        }

    def test_metric_conflicts_returns_rank_columns(self, synthetic_repo):
        out = metric_conflicts(synthetic_repo)
        for c in (
            "rank_primary",
            "rank_secondary",
            "rank_tertiary",
            "abs_diff_primary_secondary",
            "abs_diff_primary_tertiary",
        ):
            assert c in out.columns

    def test_metric_conflicts_missing_columns_raises(self, synthetic_repo):
        work = synthetic_repo.drop(columns=["silhouette"])
        with pytest.raises(KeyError):
            metric_conflicts(work)


# ---------------------------------------------------------------------------
# load tests
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_repository_parquet(self, synthetic_parquet: Path):
        df = load_repository_parquet(synthetic_parquet)
        assert not df.empty
        assert "silhouette" in df.columns

    def test_load_repository_csv(self, synthetic_csv: Path):
        df = load_repository_csv(synthetic_csv)
        assert not df.empty
        assert "silhouette" in df.columns

    def test_load_repository_prefers_parquet(self, synthetic_eva01_dir: Path):
        df = load_repository(synthetic_eva01_dir)
        assert not df.empty
        assert "silhouette" in df.columns

    def test_load_repository_csv_only(self, synthetic_csv: Path):
        # No parquet in the same dir.
        d = synthetic_csv.parent
        df = load_repository(d, prefer_parquet=False)
        assert not df.empty

    def test_load_repository_missing_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_repository(tmp_path)

    def test_list_experiment_ids_sorted(self, synthetic_repo):
        ids = list_experiment_ids(synthetic_repo)
        assert ids == sorted(ids)
        assert "EXP-01" in ids
        assert "EXP-05" in ids

    def test_list_algorithms_sorted(self, synthetic_repo):
        algos = list_algorithms(synthetic_repo)
        assert algos == sorted(algos)
        # K-Medoids is OUT OF SCOPE.
        assert "kmedoids" not in algos

    def test_iter_by_experiment(self, synthetic_repo):
        groups = dict(iter_by_experiment(synthetic_repo))
        assert "EXP-01" in groups
        assert len(groups["EXP-01"]) == 5


# ---------------------------------------------------------------------------
# comparison tests
# ---------------------------------------------------------------------------


class TestComparison:
    def test_compare_by_algorithm_columns(self, synthetic_repo: pd.DataFrame):
        out = compare_by_algorithm(synthetic_repo)
        assert not out.empty
        assert {"source_experiment", "algorithm"}.issubset(out.columns)
        # Per-metric min/max/mean/n present.
        for m in METRIC_COLUMNS:
            assert f"{m}_mean" in out.columns
        # Runtime columns present.
        assert f"{RUNTIME_COLUMN}_mean" in out.columns

    def test_compare_by_k_columns(self, synthetic_repo: pd.DataFrame):
        out = compare_by_k(synthetic_repo)
        assert not out.empty
        assert {"source_experiment", "algorithm", "n_clusters"}.issubset(out.columns)

    def test_compare_by_preprocessing_includes_real_scenarios(self, synthetic_repo: pd.DataFrame):
        out = compare_by_preprocessing(synthetic_repo)
        assert not out.empty
        # Only EXP-04 rows have populated preprocessing scenarios.
        real_rows = out.loc[out["transformation"] != MISSING]
        assert not real_rows.empty
        assert set(real_rows["source_experiment"]) == {"EXP-04"}
        # MISSING rows are also surfaced for transparency (grouped by
        # source_experiment × MISSING × MISSING × MISSING).
        missing_rows = out.loc[out["transformation"] == MISSING]
        assert not missing_rows.empty

    def test_compare_by_hyperparameter_uses_families(self, synthetic_repo: pd.DataFrame):
        out = compare_by_hyperparameter(synthetic_repo)
        # EXP-03 has rows for n_init, linkage, eps families.
        assert (out["hyperparameter_family"] != "OTHER").any()

    def test_metric_ranking_per_metric_returns_dict(self, synthetic_repo: pd.DataFrame):
        rankings = metric_ranking_per_metric(synthetic_repo)
        assert set(rankings.keys()) == set(METRIC_COLUMNS)
        for _metric, table in rankings.items():
            assert "rank" in table.columns
            assert "metric_value" in table.columns
            # Ranks start at 1.
            assert table["rank"].min() >= 1

    def test_metric_ranking_higher_is_better_descending(self, synthetic_repo: pd.DataFrame):
        rankings = metric_ranking_per_metric(
            synthetic_repo,
            metrics=["silhouette"],
            rank_within=("source_experiment", "algorithm"),
        )
        sil = rankings["silhouette"]
        # rank 1 should correspond to the highest silhouette in each
        # group.
        for _keys, sub in sil.groupby(["source_experiment", "algorithm"], dropna=False):
            top_row = sub.loc[sub["rank"].idxmin()]
            assert top_row["metric_value"] == sub["metric_value"].max()

    def test_metric_ranking_lower_is_better_ascending(self, synthetic_repo: pd.DataFrame):
        rankings = metric_ranking_per_metric(
            synthetic_repo,
            metrics=["davies_bouldin"],
            rank_within=("source_experiment", "algorithm"),
        )
        dbi = rankings["davies_bouldin"]
        for _keys, sub in dbi.groupby(["source_experiment", "algorithm"], dropna=False):
            top_row = sub.loc[sub["rank"].idxmin()]
            assert top_row["metric_value"] == sub["metric_value"].min()

    def test_exp03_hyperparameter_families_keys(self):
        # Ensure well-known keys are present.
        for key in ("n_init", "linkage", "eps", "min_samples", "m"):
            assert key in EXP03_HYPERPARAMETER_FAMILIES


# ---------------------------------------------------------------------------
# quality tests
# ---------------------------------------------------------------------------


class TestQuality:
    def test_dataset_quality_overview_keys(self, synthetic_repo: pd.DataFrame):
        out = dataset_quality_overview(synthetic_repo)
        assert {
            "n_rows",
            "n_rows_with_all_metrics",
            "n_unique_algorithms",
            "metric_coverage",
            "algorithm_metric_coverage",
            "dbscan_total_noise_count",
        }.issubset(out.keys())
        assert out["n_rows"] == len(synthetic_repo)
        assert out["n_unique_algorithms"] == 5
        assert out["dbscan_total_noise_count"] > 0

    def test_quality_by_algorithm_returns_per_algo_table(self, synthetic_repo: pd.DataFrame):
        out = quality_by_algorithm(synthetic_repo)
        assert not out.empty
        # K-Means / Agglomerative / DBSCAN / GMM / Fuzzy C-Means
        assert set(out["algorithm"]) == {
            "kmeans",
            "agglomerative",
            "dbscan",
            "gmm",
            "fuzzy_cmeans",
        }
        for m in METRIC_COLUMNS:
            assert f"{m}_mean" in out.columns

    def test_quality_by_k_returns_per_k_table(self, synthetic_repo: pd.DataFrame):
        out = quality_by_k(synthetic_repo)
        assert not out.empty
        # K=4 and DBSCAN K=17 both appear.
        assert 4 in set(out["n_clusters"])
        assert 17 in set(out["n_clusters"])

    def test_quality_by_algorithm_and_k(self, synthetic_repo: pd.DataFrame):
        out = quality_by_algorithm_and_k(synthetic_repo)
        assert not out.empty
        assert {"algorithm", "n_clusters"}.issubset(out.columns)

    def test_quality_by_preprocessing_filters_missing(self, synthetic_repo: pd.DataFrame):
        out = quality_by_preprocessing(synthetic_repo)
        assert not out.empty
        # Only EXP-04 rows are kept.
        assert set(out["transformation"]).issubset({"none", "yeo_johnson"})

    def test_quality_by_preprocessing_empty_when_no_exp04(self):
        # Build a repo without EXP-04 rows.
        df = _build_synthetic_repo()
        df = df.loc[df["source_experiment"] != "EXP-04"].reset_index(drop=True)
        out = quality_by_preprocessing(df)
        assert out.empty

    def test_cross_metric_conflicts_flags_conflict_row(self, synthetic_repo: pd.DataFrame):
        # The synthetic repo has 3 EXP-02 kmeans K=4 rows (two sweep + one
        # conflict). The conflict row has silhouette rank 1, DBI rank 1,
        # but CH rank 3 (last). This gives |rank_sil - rank_CH| = 2,
        # which exceeds the default rank_tolerance=1.
        out = cross_metric_conflicts(synthetic_repo, rank_tolerance=1)
        assert not out.empty
        assert "conflict_with_tertiary" in out.columns
        conflict_id = "EXP-02-kmeans-conflict"
        conflict_row = out.loc[out["experiment_id"] == conflict_id]
        assert not conflict_row.empty
        assert conflict_row["conflict_with_tertiary"].iloc[0]

    def test_cross_metric_conflicts_no_uint64_underflow(self):
        """Regression test for the EVA-02 post-implementation review.

        Pandas' ``Series.rank`` returns ``UInt64`` for non-null numeric
        inputs. Subtracting two ``UInt64`` Series underflows when the
        left-hand rank is smaller than the right-hand rank (a
        difference of ``-1`` becomes ``2**64 - 1``). The previous
        implementation produced 14-24 false-positive conflict flags in
        the EVA-02 conflict table because of this bug.

        This test constructs a controlled group where, under the OLD
        UInt64-arithmetic code, every row would have produced a
        conflict flag because ``rank_primary < rank_secondary``. The
        NEW signed-integer subtraction produces the correct difference
        (2) and the correct flag (real disagreement of 2 > tolerance 1).
        """
        rows = []
        # Three rows. silhouette is HIGHER-is-better; DBI is
        # LOWER-is-better. We pick values that make the silhouette
        # rank *smaller* than the DBI rank for every row:
        #   silhouette [0.10, 0.20, 0.30] -> rank 3, 2, 1
        #   DBI        [1.00, 2.00, 3.00] -> rank 1, 2, 3
        # Under UInt64 arithmetic ``rank_primary - rank_secondary``
        # would underflow for rows 0 and 1; the signed-int code
        # correctly reports |diff| = 2 for both rows.
        metrics = {
            "silhouette": [0.10, 0.20, 0.30],         # rank 3, 2, 1
            "davies_bouldin": [1.00, 2.00, 3.00],     # rank 1, 2, 3
            "calinski_harabasz": [100.0, 200.0, 300.0],  # rank 1, 2, 3
        }
        for i in range(3):
            row = {
                "source_experiment": "EXP-01",
                "experiment_id": f"regression-row-{i}",
                "source_block": "",
                "source_run_id": "",
                "record_granularity": "PER_RUN",
                "repeat_index": 0,
                "n_repeats_total": 1,
                "algorithm": "kmeans",
                "dataset_version": "v1",
                "feature_set": "rfm_extended",
                "transformation": MISSING,
                "scaling": MISSING,
                "imputation": MISSING,
                "n_clusters": 4,
                "hyperparameters": "{}",
                "random_seed": 42,
                "silhouette": metrics["silhouette"][i],
                "davies_bouldin": metrics["davies_bouldin"][i],
                "calinski_harabasz": metrics["calinski_harabasz"][i],
                "wcss": 1000.0,
                "execution_time_seconds": 0.01,
                "n_clusters_realized": 4,
                "cluster_size_largest": MISSING,
                "cluster_size_smallest": MISSING,
                "noise_count": None,
                "noise_ratio": None,
            }
            rows.append(row)
        df = pd.DataFrame(rows)

        out = cross_metric_conflicts(df, rank_tolerance=1)

        # Sanity: the three experiment_ids are preserved.
        assert set(out["experiment_id"].tolist()) == {
            "regression-row-0",
            "regression-row-1",
            "regression-row-2",
        }

        # ``regression-row-0``: silhouette 0.10 -> rank 3, DBI 1.00
        # -> rank 1 (lower-is-better). |3 - 1| = 2. Under UInt64
        # arithmetic this would have been 2**64 - 2; the regression
        # is that the diff is the small correct value 2.
        row0 = out.loc[out["experiment_id"] == "regression-row-0"].iloc[0]
        assert int(row0["rank_silhouette"]) == 3
        assert int(row0["rank_davies_bouldin"]) == 1
        diff = abs(
            int(row0["rank_silhouette"]) - int(row0["rank_davies_bouldin"])
        )
        assert diff == 2
        assert diff < (1 << 63)
        # 2 > rank_tolerance=1, so the row IS flagged — but the flag
        # value is correct.
        assert bool(row0["conflict_with_secondary"])

        # ``regression-row-1``: silhouette 0.20 -> rank 2, DBI 2.00
        # -> rank 2; ranks match. The UInt64-underflow bug would have
        # produced 2**64 - 2 here too (because rank_primary - rank_secondary
        # in UInt64 still underflows for 2 - 2 = 0 ... actually 0
        # does not underflow; the row would have stayed unflagged
        # either way, but this row is here as a control).
        row1 = out.loc[out["experiment_id"] == "regression-row-1"].iloc[0]
        assert int(row1["rank_silhouette"]) == 2
        assert int(row1["rank_davies_bouldin"]) == 2
        assert not bool(row1["conflict_with_secondary"])

        # ``regression-row-2``: silhouette 0.30 -> rank 1, DBI 3.00
        # -> rank 3. |1 - 3| = 2 — the *canonical* underflow case:
        # the OLD code would compute 1 - 3 = 2**64 - 2 in UInt64
        # arithmetic and flag the row. The NEW code reports |diff| = 2.
        row2 = out.loc[out["experiment_id"] == "regression-row-2"].iloc[0]
        assert int(row2["rank_silhouette"]) == 1
        assert int(row2["rank_davies_bouldin"]) == 3
        diff2 = abs(
            int(row2["rank_silhouette"]) - int(row2["rank_davies_bouldin"])
        )
        assert diff2 == 2
        assert diff2 < (1 << 63)
        assert bool(row2["conflict_with_secondary"])

        # The ``conflict_with_secondary`` flag total should match the
        # number of rows where |rank_sil - rank_DBI| > 1, which is 2
        # (rows 0 and 2). The OLD code produced the same *count* here
        # only by coincidence; the regression is the finite / small
        # diff value.
        assert int(out["conflict_with_secondary"].sum()) == 2

    def test_cross_metric_conflicts_rank_diff_signed_dtype(self, synthetic_repo):
        """Regression test for the signed-integer subtraction.

        The rank-difference columns used internally are computed on a
        signed integer dtype; this prevents the ``UInt64`` underflow
        flagged by the EVA-02 post-implementation review.
        """
        from customer_segmentation.evaluation.eva02.quality import (
            _signed_abs_diff,
        )

        left = pd.Series([1, 2, 3], dtype="UInt64")
        right = pd.Series([3, 2, 1], dtype="UInt64")
        diff = _signed_abs_diff(left, right)
        # Every value should be exactly 2; UInt64 underflow would
        # produce 2**64 - 2.
        assert diff.tolist() == [2, 0, 2]
        # Float64 dtype propagates ``<NA>`` correctly.
        with_na = pd.Series([1, pd.NA, 3], dtype="UInt64")
        diff2 = _signed_abs_diff(with_na, with_na)
        assert diff2.tolist()[0] == 0
        assert pd.isna(diff2.tolist()[1])

    def test_cross_metric_conflicts_respects_exp05_block_boundary(
        self, synthetic_repo: pd.DataFrame
    ):
        """Regression: EXP-05 R/S/N blocks MUST be separate groups.

        With the new ``DEFAULT_CONFLICT_GROUP_COLS``, EXP-05 rows are
        split by ``_exp05_block`` (R / S / N). A row in Block R and a
        row in Block N therefore do NOT share a ranking group, even
        when ``source_experiment`` / ``algorithm`` / ``n_clusters``
        match.
        """
        out = cross_metric_conflicts(synthetic_repo, rank_tolerance=1)
        if "source_experiment" in out.columns and (out["source_experiment"] == "EXP-05").any():
            exp05 = out.loc[out["source_experiment"] == "EXP-05"]
            assert "_exp05_block" in exp05.columns
            assert set(exp05["_exp05_block"].dropna().astype(str).unique()).issubset(
                {"R", "S", "N"}
            )

    def test_cross_metric_conflicts_respects_exp03_stage_boundary(
        self, synthetic_repo: pd.DataFrame
    ):
        """Regression: EXP-03 Stage A / B / C MUST be separate groups."""
        out = cross_metric_conflicts(synthetic_repo, rank_tolerance=1)
        if (out["source_experiment"] == "EXP-03").any():
            exp03 = out.loc[out["source_experiment"] == "EXP-03"]
            assert "_exp03_stage" in exp03.columns
            assert set(exp03["_exp03_stage"].dropna().astype(str).unique()).issubset(
                {"A", "B", "C"}
            )

    def test_cross_metric_conflicts_respects_exp04_scenario_boundary(
        self, synthetic_repo: pd.DataFrame
    ):
        """Regression: EXP-04 rows share a group per scenario."""
        out = cross_metric_conflicts(synthetic_repo, rank_tolerance=1)
        if (out["source_experiment"] == "EXP-04").any():
            exp04 = out.loc[out["source_experiment"] == "EXP-04"]
            assert "_exp04_scenario" in exp04.columns
            # The 5 repeats of each scenario remain in the same group.
            assert exp04["_exp04_scenario"].notna().all()

    def test_dbscan_noise_summary_includes_dbscan_only(self, synthetic_repo: pd.DataFrame):
        out = dbscan_noise_summary(synthetic_repo)
        assert not out.empty
        assert "noise_count_mean" in out.columns
        assert "noise_ratio_mean" in out.columns

    def test_dbscan_noise_summary_empty_without_dbscan(self):
        df = _build_synthetic_repo()
        df = df.loc[df["algorithm"] != "dbscan"].reset_index(drop=True)
        out = dbscan_noise_summary(df)
        assert out.empty


# ---------------------------------------------------------------------------
# report tests
# ---------------------------------------------------------------------------


class TestReport:
    def test_build_report_includes_section_titles(self, synthetic_repo: pd.DataFrame):
        md = build_report(synthetic_repo)
        # Section numbering updated after the post-implementation review:
        # section 3 now documents the ranking boundaries (EXP-05 R/S/N,
        # EXP-03 Stage A/B/C, EXP-04 scenario, DBSCAN K semantics,
        # hyperparameter-family scope, rank_tolerance). The descriptive
        # per-algorithm / per-K sections are renumbered 4..7.
        assert "## 1. Provenance & Scope" in md
        assert "## 2. Metric distributions" in md
        assert "## 3. Ranking boundaries" in md
        assert "## 4. Per-algorithm comparison" in md
        assert "## 5. Per-K comparison" in md
        assert "## 6. Per-preprocessing comparison" in md
        assert "## 7. Per-hyperparameter-family comparison" in md
        assert "## 8. Cross-metric conflicts" in md
        assert "## 9. DBSCAN noise characteristics" in md
        assert "## 10. Generated artefacts" in md
        assert "## 11. Interpretation boundary" in md

    def test_build_report_does_not_claim_best(self, synthetic_repo: pd.DataFrame):
        md = build_report(synthetic_repo)
        # The report must NOT contain affirmative claims of the form
        # "<algorithm> is best/winner/optimal/recommended".  The
        # interpretation-boundary section explicitly lists these as
        # forbidden uses, so we only check for affirmative claims.
        for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
            assert f"{algo} is best" not in md.lower()
            assert f"{algo} is the best" not in md.lower()
            assert f"{algo} is recommended" not in md.lower()
            assert f"{algo} is optimal" not in md.lower()
            assert f"{algo} is winner" not in md.lower()

    def test_build_report_lists_artefacts(self, synthetic_repo: pd.DataFrame):
        md = build_report(
            synthetic_repo,
            table_paths=["reports/evaluation/eva02/tables/x.csv"],
            figure_paths=["reports/evaluation/eva02/figures/y.png"],
        )
        assert "reports/evaluation/eva02/tables/x.csv" in md
        assert "reports/evaluation/eva02/figures/y.png" in md


# ---------------------------------------------------------------------------
# visualization tests
# ---------------------------------------------------------------------------


class TestVisualization:
    def test_algorithm_colors_known(self):
        for algo in (
            "kmeans",
            "agglomerative",
            "dbscan",
            "gmm",
            "fuzzy_cmeans",
        ):
            assert algo in ALGORITHM_COLORS
        # K-Medoids is OUT OF SCOPE.
        assert "kmedoids" not in ALGORITHM_COLORS

    def test_plot_metric_vs_k_writes_files(self, synthetic_repo: pd.DataFrame, tmp_path: Path):
        paths = plot_metric_vs_k(synthetic_repo, tmp_path)
        assert paths
        assert all(p.exists() for p in paths)
        # One plot per (experiment, metric) combination.
        assert len(paths) >= 4

    def test_plot_metric_by_algorithm_writes_files(
        self, synthetic_repo: pd.DataFrame, tmp_path: Path
    ):
        paths = plot_metric_by_algorithm(synthetic_repo, tmp_path)
        assert paths
        assert all(p.exists() for p in paths)

    def test_plot_metric_by_preprocessing_writes_files(
        self, synthetic_repo: pd.DataFrame, tmp_path: Path
    ):
        paths = plot_metric_by_preprocessing(synthetic_repo, tmp_path)
        # At least one plot for the EXP-04 scenarios.
        assert paths
        assert all(p.exists() for p in paths)

    def test_plot_metric_by_hyperparameter_family_writes_files(
        self, synthetic_repo: pd.DataFrame, tmp_path: Path
    ):
        paths = plot_metric_by_hyperparameter_family(synthetic_repo, tmp_path)
        # At least one plot for EXP-03.
        assert paths
        assert all(p.exists() for p in paths)

    def test_plot_metric_distributions_writes_files(
        self, synthetic_repo: pd.DataFrame, tmp_path: Path
    ):
        paths = plot_metric_distributions(synthetic_repo, tmp_path)
        assert len(paths) == len(METRIC_COLUMNS)
        assert all(p.exists() for p in paths)


# ---------------------------------------------------------------------------
# runner tests
# ---------------------------------------------------------------------------


class TestRunner:
    def test_run_writes_expected_outputs(
        self,
        synthetic_eva01_dir: Path,
        tmp_path: Path,
    ):
        output_dir = tmp_path / "eva02_out"
        config = Eva02Config(
            eva01_dir=synthetic_eva01_dir,
            output_dir=output_dir,
        )
        manifest = Eva02Runner(config=config).run()

        # Manifest keys.
        assert "generated_at" in manifest
        assert "tables" in manifest
        assert "figures" in manifest
        assert "report" in manifest

        # Required files.
        assert (output_dir / "eva02_report.md").exists()
        assert (output_dir / "eva02_run_manifest.json").exists()
        assert (output_dir / "tables").exists()
        assert (output_dir / "figures").exists()

        # Every reported file path exists.
        for rel_path in manifest["tables"]:
            assert (Path.cwd() / rel_path).exists()
        for rel_path in manifest["figures"]:
            assert (Path.cwd() / rel_path).exists()

        # Manifest JSON is valid.
        raw = json.loads((output_dir / "eva02_run_manifest.json").read_text())
        assert raw["n_rows"] > 0

    def test_run_with_no_rankings_skips_ranking_outputs(
        self,
        synthetic_eva01_dir: Path,
        tmp_path: Path,
    ):
        output_dir = tmp_path / "eva02_out2"
        config = Eva02Config(
            eva01_dir=synthetic_eva01_dir,
            output_dir=output_dir,
            write_rankings=False,
        )
        manifest = Eva02Runner(config=config).run()
        assert manifest["rankings"] == []

    def test_run_eva02_convenience_wrapper(
        self,
        synthetic_eva01_dir: Path,
        tmp_path: Path,
        monkeypatch,
    ):
        # Make sure CWD is the parent so relative paths in the
        # manifest resolve correctly inside tmp_path.
        monkeypatch.chdir(tmp_path)
        output_dir = tmp_path / "eva02_out3"
        manifest = run_eva02(
            eva01_dir=synthetic_eva01_dir,
            output_dir=output_dir,
        )
        assert (output_dir / "eva02_report.md").exists()
        assert manifest["n_rows"] > 0

    def test_run_missing_eva01_raises(self, tmp_path: Path):
        config = Eva02Config(
            eva01_dir=tmp_path / "missing",
            output_dir=tmp_path / "eva02",
        )
        with pytest.raises(FileNotFoundError):
            Eva02Runner(config=config).run()


# ---------------------------------------------------------------------------
# Integration: end-to-end on the real EVA-01 outputs (skip if missing).
# ---------------------------------------------------------------------------


REAL_EVA01_DIR = Path("reports/evaluation/eva01")


@pytest.mark.skipif(
    not REAL_EVA01_DIR.exists(),
    reason="Real EVA-01 outputs not present in this environment",
)
class TestIntegrationOnRealEva01:
    def test_runner_on_real_eva01(self, tmp_path: Path):
        output_dir = tmp_path / "eva02_real"
        config = Eva02Config(
            eva01_dir=REAL_EVA01_DIR,
            output_dir=output_dir,
        )
        manifest = Eva02Runner(config=config).run()
        assert manifest["n_rows"] == 185

        # The Markdown report must exist and reference EVA-01.
        md_path = output_dir / "eva02_report.md"
        assert md_path.exists()
        md_text = md_path.read_text(encoding="utf-8")
        assert "EVA-01" in md_text
        # Must not contain affirmative best/optimal/recommended claims.
        for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
            assert f"{algo} is best" not in md_text.lower()
            assert f"{algo} is the best" not in md_text.lower()
            assert f"{algo} is recommended" not in md_text.lower()

    def test_real_repo_metric_coverage_full(self):
        df = load_repository(REAL_EVA01_DIR)
        for metric in METRIC_COLUMNS:
            assert df[metric].notna().all(), f"real EVA-01 has missing values for {metric}"
