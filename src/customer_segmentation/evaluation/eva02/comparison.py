"""Comparison tables for EVA-02 cluster-quality evaluation.

The comparison layer produces a family of descriptive tables that
aggregate the EVA-01 standardised repository along different axes:

1. ``compare_by_algorithm`` — per-(source_experiment, algorithm).
2. ``compare_by_k`` — per-(source_experiment, algorithm, K).
3. ``compare_by_preprocessing`` — per-(source_experiment, preprocessing).
   Only EXP-04 rows have populated preprocessing columns; for other
   experiments the table reports ``MISSING``.
4. ``compare_by_hyperparameter`` — for each algorithm, identify the
   hyperparameter families present in EXP-03 and report metric
   summaries per family.
5. ``metric_ranking_per_metric`` — for each metric AND each
   (algorithm, K, condition) group, list the rows sorted by that
   metric (rank-by-metric, not rank-by-algorithm).

All comparison tables are **descriptive**: they do not produce any
"best algorithm" claim or composite score. Where the data is not
sufficient (e.g. only one preprocessing scenario for a given
algorithm), the table reports ``n=0`` for that group and the
caller can interpret the absence of evidence.

Hard constraints (AGENTS.md §2):

- No ranking / "best/winner/optimal/recommended/final" labels.
- No composite score.
- Read-only against EVA-01.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from customer_segmentation.evaluation.eva02.metrics import (
    METRIC_COLUMNS,
    METRIC_DIRECTIONS,
    RUNTIME_COLUMN,
    extract_metric_vector,
    summarise_metric,
)
from customer_segmentation.evaluation.experiment_results.schema import MISSING

__all__ = [
    "compare_by_algorithm",
    "compare_by_k",
    "compare_by_preprocessing",
    "compare_by_hyperparameter",
    "metric_ranking_per_metric",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric_summary_columns(metrics: Iterable[str]) -> list[str]:
    """Return the ordered list of per-metric summary columns."""
    cols: list[str] = []
    for m in metrics:
        cols.extend([f"{m}_min", f"{m}_max", f"{m}_mean", f"{m}_n"])
    return cols


def _build_summary_row(
    group: pd.DataFrame,
    metrics: Iterable[str],
    include_runtime: bool = True,
) -> dict[str, object]:
    """Build a single summary row covering the requested metrics."""
    row: dict[str, object] = {}
    for m in metrics:
        vec = extract_metric_vector(group, m)
        stats = summarise_metric(vec)
        row[f"{m}_min"] = stats["min"]
        row[f"{m}_max"] = stats["max"]
        row[f"{m}_mean"] = stats["mean"]
        row[f"{m}_n"] = stats["n"]
    if include_runtime:
        vec = extract_metric_vector(group, RUNTIME_COLUMN)
        stats = summarise_metric(vec)
        row[f"{RUNTIME_COLUMN}_min"] = stats["min"]
        row[f"{RUNTIME_COLUMN}_max"] = stats["max"]
        row[f"{RUNTIME_COLUMN}_mean"] = stats["mean"]
    return row


# ---------------------------------------------------------------------------
# Public comparison builders
# ---------------------------------------------------------------------------


def compare_by_algorithm(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Per-(source_experiment, algorithm) metric summary table.

    Columns include per-metric min/max/mean/n and runtime statistics
    when available. Output is sorted by (source_experiment, algorithm).
    """
    metrics = list(metrics)
    rows: list[dict[str, object]] = []
    grouped = df.groupby(["source_experiment", "algorithm"], dropna=False)
    for (source_exp, algo), group in grouped:
        if not isinstance(algo, str) or not algo:
            continue
        row: dict[str, object] = {
            "source_experiment": source_exp,
            "algorithm": algo,
            "n_rows": len(group),
        }
        unique_k = sorted(
            {int(k) for k in group["n_clusters"].dropna().unique() if pd.notna(k)}
        )
        row["n_unique_n_clusters"] = len(unique_k)
        row["k_min"] = min(unique_k) if unique_k else MISSING
        row["k_max"] = max(unique_k) if unique_k else MISSING
        row.update(_build_summary_row(group, metrics, include_runtime=True))
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["source_experiment", "algorithm"]).reset_index(drop=True)


def compare_by_k(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Per-(source_experiment, algorithm, K) metric summary table.

    Rows are sorted by (source_experiment, algorithm, n_clusters).
    DBSCAN rows appear under ``n_clusters=actual_n_clusters_realized``
    (which is 17 for the EXP-01 baseline); K-Means rows span K=2..10
    per EXP-02.
    """
    metrics = list(metrics)
    rows: list[dict[str, object]] = []
    grouped = df.groupby(
        ["source_experiment", "algorithm", "n_clusters"], dropna=False
    )
    for (source_exp, algo, k), group in grouped:
        if pd.isna(k):
            continue
        if not isinstance(algo, str) or not algo:
            continue
        row: dict[str, object] = {
            "source_experiment": source_exp,
            "algorithm": algo,
            "n_clusters": int(k),
            "n_rows": len(group),
        }
        row.update(_build_summary_row(group, metrics, include_runtime=True))
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["source_experiment", "algorithm", "n_clusters"]).reset_index(
        drop=True
    )


def compare_by_preprocessing(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Per-(source_experiment, transformation, scaling, imputation) summary.

    Only EXP-04 has fully-populated preprocessing columns; other
    experiments contribute ``MISSING`` rows that are kept for
    transparency (grouped under the ``MISSING`` sentinel for all three
    preprocessing fields).
    """
    metrics = list(metrics)
    rows: list[dict[str, object]] = []
    grouped = df.groupby(
        [
            "source_experiment",
            "transformation",
            "scaling",
            "imputation",
        ],
        dropna=False,
    )
    for (source_exp, transformation, scaling, imputation), group in grouped:
        row: dict[str, object] = {
            "source_experiment": source_exp,
            "transformation": transformation,
            "scaling": scaling,
            "imputation": imputation,
            "n_rows": len(group),
            "n_unique_algorithms": int(
                group["algorithm"].dropna().astype(str).nunique()
            ),
        }
        if group["algorithm"].dropna().astype(str).nunique() == 1:
            row["algorithm"] = str(group["algorithm"].dropna().astype(str).iloc[0])
        else:
            row["algorithm"] = "mixed"
        row.update(_build_summary_row(group, metrics, include_runtime=False))
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        ["source_experiment", "transformation", "scaling", "imputation"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Hyperparameter comparison
# ---------------------------------------------------------------------------


# Common EXP-03 hyperparameter "families" used by AGENTS.md / the
# methodology. Each family is identified by a key (sub-string) that
# appears in the experiment_id of the EXP-03 rows.
EXP03_HYPERPARAMETER_FAMILIES: dict[str, str] = {
    "init": "init_method",
    "n_init": "n_init",
    "max_iter": "max_iter",
    "linkage": "linkage",
    "eps": "eps",
    "min_samples": "min_samples",
    "covariance_type": "covariance_type",
    "init_params": "init_params",
    "m": "fuzziness_m",
}

# Aggregate bucket label used by :func:`compare_by_hyperparameter` for
# rows that come from a different experimental condition than EXP-03
# (baseline, K-sweep, preprocessing, stability). The label is *not* a
# hyperparameter family — it is the catch-all for "rows that do not
# belong to a single hyperparameter sweep". Reviewers MUST treat it as
# a separate analytical section, never as a hyperparameter family.
HP_AGGREGATE_LABEL: str = "non_exp03_aggregate"


def _family_of_experiment_id(experiment_id: str) -> str | None:
    """Map an EXP-03 experiment_id like ``EXP-03-kmeans-stageB-n_init-1``
    to the family ``n_init``.

    Returns ``None`` if the experiment_id does not match any known
    family key. The function does NOT return a placeholder label —
    callers decide how to handle the ``None``.
    """
    if not isinstance(experiment_id, str):
        return None
    parts = experiment_id.split("-")
    for token in parts[3:]:  # skip EXP-03-<algo>-<stage>
        if token in EXP03_HYPERPARAMETER_FAMILIES:
            return EXP03_HYPERPARAMETER_FAMILIES[token]
    return None


def compare_by_hyperparameter(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
    include_non_exp03_aggregate: bool = False,
) -> pd.DataFrame:
    """Per-(algorithm, hyperparameter_family) metric summary table.

    The function returns ONE row per (algorithm, family) combination
    drawn exclusively from EXP-03 rows. EXP-03 is the only experiment
    whose rows form a single-axis hyperparameter sweep; rows from
    EXP-01 (baseline), EXP-02 (K sweep), EXP-04 (preprocessing) and
    EXP-05 (stability) carry different independent variables and MUST
    NOT be merged into the hyperparameter sensitivity comparison.

    Parameters
    ----------
    df : pandas.DataFrame
        Standardised repository. Non-EXP-03 rows are dropped by
        default.
    metrics : iterable of str
        Metrics to summarise.
    include_non_exp03_aggregate : bool, default False
        When ``True``, an additional row per algorithm labelled
        :data:`HP_AGGREGATE_LABEL` (``"non_exp03_aggregate"``) is
        appended that aggregates the non-EXP-03 rows for the same
        algorithm. The label is *descriptive*: it is NOT a
        hyperparameter family. Callers / report writers should keep
        it visually separate from the per-family rows.

    Returns
    -------
    pandas.DataFrame
        Per-(algorithm, family) metric summary. Sorted by
        (algorithm, hyperparameter_family).
    """
    metrics = list(metrics)
    work = df.copy()

    exp03 = work.loc[work["source_experiment"] == "EXP-03"].copy()
    if exp03.empty:
        out_exp03 = pd.DataFrame(
            columns=["algorithm", "hyperparameter_family", "n_rows", "n_unique_values"]
        )
    else:
        exp03["_hp_family"] = exp03["experiment_id"].apply(_family_of_experiment_id)
        # Rows without a recognised family token stay unlabelled —
        # they are surfaced for review but NOT collapsed into a single
        # family bucket.
        rows: list[dict[str, object]] = []
        grouped = exp03.groupby(["algorithm", "_hp_family"], dropna=False)
        for (algo, family), group in grouped:
            if not isinstance(algo, str) or not algo:
                continue
            if not isinstance(family, str) or not family:
                # Skip rows whose experiment_id does not match any
                # known EXP-03 family token. Reviewers can find them
                # via the EXP-03 source artifacts.
                continue
            row: dict[str, object] = {
                "algorithm": algo,
                "hyperparameter_family": family,
                "n_rows": len(group),
                "n_unique_values": int(
                    group["hyperparameters"].dropna().astype(str).nunique()
                ),
                "k_min": (
                    int(group["n_clusters"].dropna().astype(int).min())
                    if group["n_clusters"].notna().any()
                    else MISSING
                ),
                "k_max": (
                    int(group["n_clusters"].dropna().astype(int).max())
                    if group["n_clusters"].notna().any()
                    else MISSING
                ),
            }
            row.update(_build_summary_row(group, metrics, include_runtime=True))
            rows.append(row)
        out_exp03 = pd.DataFrame(rows)
        if out_exp03.empty:
            out_exp03 = out_exp03.sort_values(
                ["algorithm", "hyperparameter_family"]
            ).reset_index(drop=True)

    if include_non_exp03_aggregate:
        non_exp03 = work.loc[work["source_experiment"] != "EXP-03"].copy()
        rows_agg: list[dict[str, object]] = []
        for algo, group in non_exp03.groupby("algorithm", dropna=False):
            if not isinstance(algo, str) or not algo:
                continue
            row = {
                "algorithm": algo,
                "hyperparameter_family": HP_AGGREGATE_LABEL,
                "n_rows": len(group),
                "n_unique_values": int(
                    group["hyperparameters"].dropna().astype(str).nunique()
                ),
                "k_min": (
                    int(group["n_clusters"].dropna().astype(int).min())
                    if group["n_clusters"].notna().any()
                    else MISSING
                ),
                "k_max": (
                    int(group["n_clusters"].dropna().astype(int).max())
                    if group["n_clusters"].notna().any()
                    else MISSING
                ),
            }
            row.update(_build_summary_row(group, metrics, include_runtime=True))
            rows_agg.append(row)
        out_agg = pd.DataFrame(rows_agg)
        out = pd.concat([out_exp03, out_agg], axis=0, ignore_index=True)
    else:
        out = out_exp03

    if out.empty:
        return out
    return out.sort_values(
        ["algorithm", "hyperparameter_family"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Per-metric ranking (rank-by-metric, NOT a final algorithm ranking)
# ---------------------------------------------------------------------------


# Default per-experiment ranking boundary. The keys are the
# ``source_experiment`` value; the values are the tuple of columns
# used to define the ranking group for rows from that experiment.
# This enforces the boundary rules from the EVA-02 review:
#
# * EXP-05 rows are split by ``source_block`` (R / S / N).
# * EXP-03 rows are split by their Stage tag (A / B / C) *and* K.
# * EXP-04 rows are split by scenario (transformation / scaling /
#   imputation) — the five repeats of the same scenario remain in
#   the same group.
# * EXP-01 / EXP-02 rows are ranked per algorithm only.
DEFAULT_RANK_WITHIN_BY_EXPERIMENT: dict[str, tuple[str, ...]] = {
    "EXP-01": ("source_experiment", "algorithm"),
    "EXP-02": ("source_experiment", "algorithm", "n_clusters"),
    "EXP-03": (
        "source_experiment",
        "algorithm",
        "_exp03_stage",
        "n_clusters",
    ),
    "EXP-04": (
        "source_experiment",
        "algorithm",
        "_exp04_scenario",
    ),
    "EXP-05": (
        "source_experiment",
        "algorithm",
        "_exp05_block",
    ),
}


def metric_ranking_per_metric(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
    rank_within: tuple[str, ...] | None = None,
) -> dict[str, pd.DataFrame]:
    """Return one ranking table per metric, ranked within the chosen group.

    The function does **not** claim a "best algorithm". It only ranks
    rows by the metric value within the chosen ranking group so a
    reader can see how stable the per-(K, hyperparameter) comparison
    is across metrics.

    Parameters
    ----------
    df : pandas.DataFrame
        Standardised repository (ideally pre-filtered via
        :func:`filter_metric_rows`).
    metrics : iterable of str
        Metrics to rank by. One output table per metric.
    rank_within : tuple of str, optional
        Columns that define the ranking group. When ``None``, the
        boundary depends on the row's ``source_experiment`` and
        follows :data:`DEFAULT_RANK_WITHIN_BY_EXPERIMENT`:

        * EXP-01 → ``(source_experiment, algorithm)``
        * EXP-02 → ``(source_experiment, algorithm, n_clusters)``
        * EXP-03 → ``(source_experiment, algorithm, _exp03_stage, n_clusters)``
        * EXP-04 → ``(source_experiment, algorithm, _exp04_scenario)``
        * EXP-05 → ``(source_experiment, algorithm, _exp05_block)``

        A single tuple passed as ``rank_within`` applies to every
        row regardless of source experiment (legacy behaviour,
        preserved for tests).

    Returns
    -------
    dict[str, pandas.DataFrame]
        Mapping ``metric -> ranking DataFrame`` with columns
        ``rank, <boundary>, experiment_id, algorithm, n_clusters,
        metric_value``.
    """
    metrics = list(metrics)
    work = df.copy()
    # Add the auxiliary boundary columns used by the per-experiment
    # default. They are no-ops when rank_within is provided explicitly.
    if rank_within is None or any(
        c in {"_exp03_stage", "_exp04_scenario", "_exp05_block"}
        for c in (rank_within or ())
    ):
        from customer_segmentation.evaluation.eva02.quality import (
            add_ranking_boundary_columns,
        )

        work = add_ranking_boundary_columns(work)

    out: dict[str, pd.DataFrame] = {}
    for metric in metrics:
        if metric not in work.columns:
            continue
        direction = METRIC_DIRECTIONS.get(metric, "higher_is_better")
        ascending = direction == "lower_is_better"

        # Decide the per-row ranking boundary.
        if rank_within is not None:
            # Caller provided a single tuple for all rows.
            rank_pieces: list[pd.DataFrame] = []
            for keys, sub in work.groupby(list(rank_within), dropna=False):
                sub_sorted = sub.copy()
                # Signed rank keeps downstream rank-difference maths
                # free of UInt64 underflow.
                sub_sorted["rank"] = sub_sorted[metric].rank(
                    method="min", ascending=ascending
                )
                rank_pieces.append(sub_sorted)
            if not rank_pieces:
                continue
            ranked = pd.concat(rank_pieces, axis=0, ignore_index=False)
            keep_cols: list[str] = ["rank"]
            keep_cols.extend(list(rank_within))
            if "algorithm" not in rank_within:
                keep_cols.append("algorithm")
            keep_cols.extend(["experiment_id", "n_clusters", metric])
            sub = ranked.loc[:, keep_cols].sort_values(
                list(rank_within) + ["rank"]
            ).reset_index(drop=True)
            sub = sub.rename(columns={metric: "metric_value"})
            out[metric] = sub
            continue

        # Per-experiment default boundary.
        per_exp_pieces: list[pd.DataFrame] = []
        for exp, sub in work.groupby("source_experiment", dropna=False):
            boundary = DEFAULT_RANK_WITHIN_BY_EXPERIMENT.get(
                str(exp),
                ("source_experiment", "algorithm"),
            )
            # Only use boundary columns that actually exist in `sub`.
            usable_boundary = [c for c in boundary if c in sub.columns]
            sub_sorted = sub.copy()
            if len(usable_boundary) >= 1:
                # ``DataFrame.groupby.rank`` keeps the boundary columns
                # in scope; this avoids the ``Series.groupby`` column-
                # lookup error that surfaces when the boundary column
                # belongs to the parent DataFrame.
                sub_sorted["rank"] = sub_sorted.groupby(
                    usable_boundary, dropna=False
                )[metric].rank(method="min", ascending=ascending)
            else:
                sub_sorted["rank"] = sub_sorted[metric].rank(
                    method="min", ascending=ascending
                )
            per_exp_pieces.append(sub_sorted)
        if not per_exp_pieces:
            continue
        ranked = pd.concat(per_exp_pieces, axis=0, ignore_index=False)
        keep_cols = ["rank", "source_experiment", "experiment_id", "n_clusters"]
        keep_cols.append("algorithm")
        # Include the boundary columns used.
        for c in ("_exp03_stage", "_exp04_scenario", "_exp05_block"):
            if c in ranked.columns:
                keep_cols.append(c)
        keep_cols.append(metric)
        sub = ranked.loc[:, list(dict.fromkeys(keep_cols))].sort_values(
            ["source_experiment", "algorithm", "rank"]
        ).reset_index(drop=True)
        sub = sub.rename(columns={metric: "metric_value"})
        out[metric] = sub
    return out
