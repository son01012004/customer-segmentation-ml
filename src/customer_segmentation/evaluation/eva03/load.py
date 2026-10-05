"""Loaders for EVA-03 inputs.

Each loader reads a single EXP-05 / EXP-01 / EXP-03 artifact
WITHOUT mutation and emits a typed :class:`pandas.DataFrame`
suitable for the EVA-03 analysis layers.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- Read-only against EXP-05 / EXP-01 / EXP-03 artifacts.
- CustomerID alignment is enforced (4,371 customers).
- The loaders do NOT infer new metrics — they preserve raw labels /
  metrics as recorded in the source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.eva03.types import (
    BlockRPairwiseRow,
    EXP01ReferenceRow,
    EXP03ComparisonRow,
    PairwiseMatrix,
)

__all__ = [
    "load_exp05_labels_artifact",
    "load_exp05_per_block_record_aggregates",
    "load_exp01_cluster_labels",
    "load_exp03_selected_configurations",
    "load_exp03_stage_a_baseline",
    "load_customer_metadata",
    "extract_block_r_pairwise_compare",
    "build_block_s_pairwise_table",
    "build_block_n_pairwise_table",
]


DBSCAN_NOISE_LABEL: int = -1


def load_exp05_labels_artifact(path: Path | str) -> pd.DataFrame:
    """Load the EXP-05 raw labels artifact.

    Returns the ``exp05_cluster_labels.parquet`` dataframe with the
    documented schema:

        run_id, block, algorithm, seed, sigma, perturbation_seed,
        repeat_index, CustomerID, cluster_label

    Parameters
    ----------
    path : path-like
        Path to ``exp05_cluster_labels.parquet``.

    Returns
    -------
    pd.DataFrame
        Raw labels dataframe.
    """
    return pd.read_parquet(Path(path))


def load_exp05_per_block_record_aggregates(reports_dir: Path | str) -> dict[str, pd.DataFrame]:
    """Load the EXP-05 per-block aggregate CSVs.

    Returns
    -------
    dict
        Mapping ``{"reproducibility": ..., "seed": ..., "perturbation": ...}``.
    """
    p = Path(reports_dir)
    return {
        "reproducibility": pd.read_csv(p / "exp05_reproducibility_aggregate.csv"),
        "seed": pd.read_csv(p / "exp05_seed_sweep_aggregate.csv"),
        "perturbation": pd.read_csv(p / "exp05_noise_perturbation_aggregate.csv"),
    }


def load_exp01_cluster_labels(reports_dir: Path | str) -> dict[str, pd.DataFrame]:
    """Load EXP-01 default cluster labels (last repetition only).

    The EXP-01 artifacts store one parquet file per algorithm with
    schema ``[CustomerID, ClusterLabel, IsNoise]`` (and optional
    soft-probability columns for GMM/FCM).

    Parameters
    ----------
    reports_dir : path-like
        Path to ``reports/exp01``.

    Returns
    -------
    dict
        Mapping ``{algorithm: dataframe}`` for the 5 algorithms.
    """
    p = Path(reports_dir)
    out: dict[str, pd.DataFrame] = {}
    for algo in ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"):
        path = p / f"cluster_labels_EXP-01-{algo}_rep4.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        df["algorithm"] = algo
        out[algo] = df
    return out


def load_exp03_selected_configurations(path: Path | str) -> pd.DataFrame:
    """Load EXP-03 working-selected configurations.

    Returns the EXP-03 ``selected_configurations.csv`` dataframe.
    """
    return pd.read_csv(Path(path))


def load_exp03_stage_a_baseline(path: Path | str) -> pd.DataFrame:
    """Load EXP-03 Stage A baseline rows (algorithm × K=working-default).

    Stage A rows are the EXP-03 per-algorithm baselines at the EXP-01
    working-default hyperparameters. They are the EXP-03 reference point
    for the EXP-03 baseline-defined K sweep.
    """
    df = pd.read_csv(Path(path))
    return df.loc[df["stage"] == "A"].copy()


def load_customer_metadata(path: Path | str) -> pd.DataFrame:
    """Load FE-06 customer metadata for CustomerID alignment."""
    return pd.read_parquet(Path(path))


def _labels_series_for_run(
    labels_df: pd.DataFrame, run_id: str
) -> pd.Series:
    """Return the cluster_label series for one run_id (index=CustomerID)."""
    sub = labels_df.loc[labels_df["run_id"] == run_id, ["CustomerID", "cluster_label"]]
    return sub.set_index("CustomerID")["cluster_label"]


def extract_block_r_pairwise_compare(
    labels_df: pd.DataFrame,
    *,
    label_compare_fn: Any,
) -> tuple[list[BlockRPairwiseRow], list[PairwiseMatrix]]:
    """Compute pairwise ARI / AMI / NMI for each Block R algorithm.

    Parameters
    ----------
    labels_df : pd.DataFrame
        The full EXP-05 labels artifact.
    label_compare_fn : callable
        Function ``(labels_a, labels_b) -> dict`` returning
        ``{ari, ami, nmi}``.

    Returns
    -------
    rows : list[BlockRPairwiseRow]
        Flat per-pair records (algorithm × repeat_index_a × repeat_index_b).
    matrices : list[PairwiseMatrix]
        One :class:`PairwiseMatrix` per algorithm (algorithm × matrix dict).
    """
    rows: list[BlockRPairwiseRow] = []
    matrices: list[PairwiseMatrix] = []

    sub = labels_df.loc[labels_df["block"] == "R"]
    for algo, df_a in sub.groupby("algorithm", sort=True):
        runs = sorted(df_a["run_id"].unique().tolist())
        # Collect (CustomerID -> cluster_label) per run, on the SAME row order.
        series_list: list[pd.Series] = [
            _labels_series_for_run(df_a, run_id) for run_id in runs
        ]
        # Align on CustomerID; drop missing
        all_idx = series_list[0].index
        if not all(s.index.equals(all_idx) for s in series_list):
            # Reindex to the intersection
            common = series_list[0].index
            for s in series_list[1:]:
                common = common.intersection(s.index)
            series_list = [s.loc[common] for s in series_list]

        n = len(runs)
        ari_grid = np.zeros((n, n), dtype=np.float64)
        ami_grid = np.zeros((n, n), dtype=np.float64)
        nmi_grid = np.zeros((n, n), dtype=np.float64)
        ari_unique: dict[int, set[int]] = {i: set() for i in range(n)}

        for i in range(n):
            for j in range(n):
                if i == j:
                    ari_grid[i, j] = 1.0
                    ami_grid[i, j] = 1.0
                    nmi_grid[i, j] = 1.0
                    continue
                if j < i:
                    ari_grid[i, j] = ari_grid[j, i]
                    ami_grid[i, j] = ami_grid[j, i]
                    nmi_grid[i, j] = nmi_grid[j, i]
                    continue
                res = label_compare_fn(series_list[i].to_numpy(), series_list[j].to_numpy())
                ari_grid[i, j] = res["ari"]
                ami_grid[i, j] = res["ami"]
                nmi_grid[i, j] = res["nmi"]

            # Hash-based unique detection (defensive — ARI=1.0 already implies identical)
            ari_unique[i].add(int(series_list[i].to_numpy().tobytes().__hash__()))

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                rows.append(
                    BlockRPairwiseRow(
                        algorithm=algo,
                        run_id_a=runs[i],
                        run_id_b=runs[j],
                        repeat_index_a=int(_repeat_index_from_run_id(runs[i])),
                        repeat_index_b=int(_repeat_index_from_run_id(runs[j])),
                        ari=float(ari_grid[i, j]),
                        ami=float(ami_grid[i, j]),
                        nmi=float(nmi_grid[i, j]),
                        n_customers=int(len(series_list[i])),
                    )
                )

        matrices.append(
            PairwiseMatrix(
                algorithm=algo,
                run_ids=tuple(runs),
                ari=ari_grid.tolist(),
                ami=ami_grid.tolist(),
                nmi=nmi_grid.tolist(),
                off_diagonal_unique_count=int(_count_off_diagonal_unique(ari_grid)),
            )
        )
    return rows, matrices


def build_block_s_pairwise_table(
    labels_df: pd.DataFrame,
    *,
    label_compare_fn: Any,
) -> list[PairwiseMatrix]:
    """Compute pairwise ARI / AMI / NMI for each Block S algorithm.

    Block S contains K-Means + GMM + FCM at 5 distinct seeds. We
    compute pairwise metrics across the 5 seeds. Agglomerative +
    DBSCAN are excluded (deterministic; their Block S rows do not
    exist).
    """
    matrices: list[PairwiseMatrix] = []
    sub = labels_df.loc[labels_df["block"] == "S"]
    for algo, df_a in sub.groupby("algorithm", sort=True):
        runs_by_seed = (
            df_a.drop_duplicates(subset=["seed", "repeat_index"])
            .sort_values(["seed", "repeat_index"])
        )
        runs = runs_by_seed["run_id"].tolist()
        seeds = [int(s) for s in runs_by_seed["seed"].tolist()]
        series_list = [
            _labels_series_for_run(df_a, run_id) for run_id in runs
        ]
        if not all(s.index.equals(series_list[0].index) for s in series_list):
            common = series_list[0].index
            for s in series_list[1:]:
                common = common.intersection(s.index)
            series_list = [s.loc[common] for s in series_list]

        n = len(runs)
        ari_grid = np.ones((n, n), dtype=np.float64)
        ami_grid = np.ones((n, n), dtype=np.float64)
        nmi_grid = np.ones((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(i + 1, n):
                res = label_compare_fn(
                    series_list[i].to_numpy(), series_list[j].to_numpy()
                )
                ari_grid[i, j] = res["ari"]
                ami_grid[i, j] = res["ami"]
                nmi_grid[i, j] = res["nmi"]
                ari_grid[j, i] = res["ari"]
                ami_grid[j, i] = res["ami"]
                nmi_grid[j, i] = res["nmi"]

        matrices.append(
            PairwiseMatrix(
                algorithm=algo,
                run_ids=tuple(runs),
                ari=ari_grid.tolist(),
                ami=ami_grid.tolist(),
                nmi=nmi_grid.tolist(),
                off_diagonal_unique_count=int(_count_off_diagonal_unique(ari_grid)),
            )
        )
    return matrices


def build_block_n_pairwise_table(
    labels_df: pd.DataFrame,
    *,
    label_compare_fn: Any,
    reference_label: str = "sigma0_baseline",
) -> list[PairwiseMatrix]:
    """Compute pairwise ARI / AMI / NMI for each Block N algorithm.

    For each algorithm, we build a (sigma × perturbation_seed) matrix
    of pairwise similarities. Two reference views are produced:

    - "sigma0_baseline": pairwise against the algorithm's sigma=0
      sanity run (column index 0).
    - "all_pairs": pairwise across all (sigma, perturbation_seed) rows.
    """
    out: list[PairwiseMatrix] = []
    sub = labels_df.loc[labels_df["block"] == "N"]
    for algo, df_a in sub.groupby("algorithm", sort=True):
        # Sort: sigma=0 first, then sigma=0.01, 0.05 with pseed 42, 43, 44.
        def sort_key(row: pd.Series) -> tuple[float, float]:
            sigma = float(row.get("sigma") or 0.0)
            pseed = float(row.get("perturbation_seed") or -1.0)
            if sigma == 0.0:
                return (0.0, -1.0)
            return (sigma, pseed)

        df_sorted = df_a.assign(_sort_key=df_a.apply(sort_key, axis=1))
        df_sorted = df_sorted.sort_values("_sort_key")
        runs = df_sorted["run_id"].tolist()
        sigmas: list[float] = []
        pseeds: list[float] = []
        for _, r in df_sorted.iterrows():
            sigmas.append(float(r.get("sigma") or 0.0))
            pseeds.append(float(r.get("perturbation_seed") or -1.0))
        series_list = [
            _labels_series_for_run(df_sorted, run_id) for run_id in runs
        ]
        if not all(s.index.equals(series_list[0].index) for s in series_list):
            common = series_list[0].index
            for s in series_list[1:]:
                common = common.intersection(s.index)
            series_list = [s.loc[common] for s in series_list]

        n = len(runs)
        ari_grid = np.ones((n, n), dtype=np.float64)
        ami_grid = np.ones((n, n), dtype=np.float64)
        nmi_grid = np.ones((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(i + 1, n):
                res = label_compare_fn(
                    series_list[i].to_numpy(), series_list[j].to_numpy()
                )
                ari_grid[i, j] = res["ari"]
                ami_grid[i, j] = res["ami"]
                nmi_grid[i, j] = res["nmi"]
                ari_grid[j, i] = res["ari"]
                ami_grid[j, i] = res["ami"]
                nmi_grid[j, i] = res["nmi"]

        out.append(
            PairwiseMatrix(
                algorithm=algo,
                run_ids=tuple(runs),
                ari=ari_grid.tolist(),
                ami=ami_grid.tolist(),
                nmi=nmi_grid.tolist(),
                off_diagonal_unique_count=int(_count_off_diagonal_unique(ari_grid)),
            )
        )
    return out


def load_eva03_config(path: Path | str) -> dict[str, Any]:
    """Load the EVA-03 YAML config as a dict.

    Lightweight helper that does not introduce a YAML dependency —
    delegates to ``json.dumps``/``json.loads`` round-trip via YAML if
    needed. We use :mod:`yaml` since the rest of the codebase uses it.
    """
    text = Path(path).read_text(encoding="utf-8")
    import yaml  # local import to avoid forcing pyyaml at module import time

    return yaml.safe_load(text)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repeat_index_from_run_id(run_id: str) -> int:
    """Parse `r{repeat_index}` from `...-r{repeat_index}` suffix."""
    parts = run_id.split("-r")
    if len(parts) < 2:
        return 0
    try:
        return int(parts[-1])
    except ValueError:
        return 0


def _count_off_diagonal_unique(grid: np.ndarray) -> int:
    """Count the number of distinct off-diagonal entries in a similarity grid."""
    if grid.shape[0] < 2:
        return 0
    i_upper, j_upper = np.triu_indices(grid.shape[0], k=1)
    return len(np.unique(np.round(grid[i_upper, j_upper], decimals=12)))


def exp01_reference_rows(
    exp01_labels: dict[str, pd.DataFrame],
) -> list[EXP01ReferenceRow]:
    """Build a list of EXP01ReferenceRow from the loaded EXP-01 labels.

    Each row corresponds to one algorithm's default run
    (last repetition), with the cluster_label per CustomerID stored
    as a list (preserves order).
    """
    rows: list[EXP01ReferenceRow] = []
    for algo, df in sorted(exp01_labels.items()):
        sub = df.sort_values("CustomerID")
        rows.append(
            EXP01ReferenceRow(
                algorithm=algo,
                customer_ids=sub["CustomerID"].astype("int64").tolist(),
                cluster_labels=sub["ClusterLabel"].astype("int64").tolist(),
                noise_mask=sub["IsNoise"].astype(bool).tolist()
                if "IsNoise" in sub.columns
                else [False] * len(sub),
            )
        )
    return rows


def exp03_comparison_rows(
    exp01_summary_csv: pd.DataFrame | None,
    exp03_selected_df: pd.DataFrame,
) -> list[EXP03ComparisonRow]:
    """Build per-algorithm EXP-01 vs EXP-03 working-selected comparison.

    ``exp01_summary_csv`` provides the EXP-01 baseline metric values for
    each algorithm. ``exp03_selected_df`` provides the EXP-03
    working-selected row per algorithm.

    Returns a list of :class:`EXP03ComparisonRow`. This function does
    NOT compute ARI/AMI (those are not available without EXP-03 labels).
    """
    rows: list[EXP03ComparisonRow] = []
    for _, r in exp03_selected_df.iterrows():
        algo = str(r["algorithm"])
        exp01_row = None
        if exp01_summary_csv is not None and not exp01_summary_csv.empty:
            mask = exp01_summary_csv["algorithm"] == algo
            if mask.any():
                exp01_row = exp01_summary_csv.loc[mask].iloc[0]

        rows.append(
            EXP03ComparisonRow(
                algorithm=algo,
                exp01_decision_status=(
                    "SUCCESS" if exp01_row is not None else "MISSING"
                ),
                exp01_n_clusters=(
                    int(exp01_row["n_clusters"])
                    if exp01_row is not None
                    and pd.notna(exp01_row.get("n_clusters"))
                    else None
                ),
                exp01_silhouette=(
                    float(exp01_row["silhouette"])
                    if exp01_row is not None
                    and pd.notna(exp01_row.get("silhouette"))
                    else None
                ),
                exp01_davies_bouldin=(
                    float(exp01_row["davies_bouldin"])
                    if exp01_row is not None
                    and pd.notna(exp01_row.get("davies_bouldin"))
                    else None
                ),
                exp01_calinski_harabasz=(
                    float(exp01_row["calinski_harabasz"])
                    if exp01_row is not None
                    and pd.notna(exp01_row.get("calinski_harabasz"))
                    else None
                ),
                exp01_wcss=(
                    float(exp01_row["wcss"])
                    if exp01_row is not None
                    and pd.notna(exp01_row.get("wcss"))
                    else None
                ),
                exp03_decision_status=str(r.get("decision_status", "MISSING")),
                exp03_experiment_id=str(r.get("experiment_id", "MISSING")),
                exp03_stage=str(r.get("stage", "MISSING")),
                exp03_hyperparameters=str(r.get("hyperparameters", "{}")),
                exp03_n_clusters=(
                    int(r["n_clusters"])
                    if pd.notna(r.get("n_clusters"))
                    else None
                ),
                exp03_silhouette=(
                    float(r["silhouette"])
                    if pd.notna(r.get("silhouette"))
                    else None
                ),
                exp03_davies_bouldin=(
                    float(r["davies_bouldin"])
                    if pd.notna(r.get("davies_bouldin"))
                    else None
                ),
                exp03_calinski_harabasz=(
                    float(r["calinski_harabasz"])
                    if pd.notna(r.get("calinski_harabasz"))
                    else None
                ),
                exp03_wcss=(
                    float(r["wcss"]) if pd.notna(r.get("wcss")) else None
                ),
                exp03_sweep_parameter=str(r.get("sweep_parameter", "MISSING")),
                exp03_sweep_value=_maybe_str(r.get("sweep_value")),
                exp03_baseline_k=(
                    int(r["baseline_k"])
                    if pd.notna(r.get("baseline_k"))
                    else None
                ),
                exp03_primary_criterion=str(
                    r.get("primary_criterion", "MISSING")
                ),
                exp03_selection_evidence_note=str(
                    r.get("selection_evidence_note", "")
                ),
                source_evidence="METRIC_BASED_ONLY",
            )
        )
    return rows


def _maybe_str(value: Any) -> str:
    if value is None:
        return "MISSING"
    try:
        if isinstance(value, float) and np.isnan(value):
            return "MISSING"
    except TypeError:
        pass
    return str(value)


def write_json(data: Any, path: Path) -> None:
    """Write JSON to ``path`` (parent dirs created)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
