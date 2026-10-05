"""Cluster quality analysis for EVA-02.

The quality layer takes the standardised EVA-01 repository and
produces *descriptive* analyses. It does NOT claim any algorithm
is better than another; it only surfaces patterns (e.g. metric
ranges, dispersion, conflicts) that the human reviewer can use to
write their own conclusions.

The module exposes:

- :func:`dataset_quality_overview` — high-level sanity counts.
- :func:`quality_by_algorithm` — per-algorithm metric distribution.
- :func:`quality_by_k` — K vs metric trends (where data exists).
- :func:`quality_by_preprocessing` — EXP-04 only.
- :func:`cross_metric_conflicts` — rows whose per-group rank for
  Silhouette disagrees with their rank for DBI / CH.
- :func:`dbscan_noise_summary` — DBSCAN noise characteristics.

Hard constraints (AGENTS.md §2):

- No ranking, no composite scores, no best/winner/optimal labels.
- No synthetic metric values; NaN is preserved.
- Read-only against EVA-01.
"""

from __future__ import annotations

import math
import re
from typing import Iterable

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.eva02.metrics import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    METRIC_COLUMNS,
    METRIC_DIRECTIONS,
    RUNTIME_COLUMN,
    extract_metric_vector,
    filter_metric_rows,
    summarise_metric,
)
from customer_segmentation.evaluation.experiment_results.schema import MISSING

__all__ = [
    "dataset_quality_overview",
    "quality_by_algorithm",
    "quality_by_k",
    "quality_by_preprocessing",
    "cross_metric_conflicts",
    "dbscan_noise_summary",
    "add_ranking_boundary_columns",
    "default_conflict_group_cols",
]


# ---------------------------------------------------------------------------
# Top-level overview
# ---------------------------------------------------------------------------


def dataset_quality_overview(df: pd.DataFrame) -> dict[str, object]:
    """High-level overview of the EVA-01 repository's quality dimensions.

    Returns a dictionary with:

    - ``n_rows``: total rows.
    - ``n_rows_with_metrics``: rows that have all four primary
      metrics populated (silhouette, DBI, CH, WCSS).
    - ``n_unique_algorithms``: distinct algorithm values.
    - ``metric_coverage``: per-metric n / fraction of rows.
    - ``algorithm_metric_coverage``: per-algorithm fraction of
      rows with all four metrics.
    - ``noise_total_dbscan``: total DBSCAN noise customers.
    """
    primary = list(METRIC_COLUMNS)
    n_rows = int(len(df))
    n_full = int(len(filter_metric_rows(df, require=primary)))

    metric_coverage: dict[str, dict[str, float]] = {}
    for m in primary:
        vec = extract_metric_vector(df, m)
        present = int((~pd.isna(vec)).sum()) if vec.size else 0
        metric_coverage[m] = {
            "n_present": present,
            "fraction": (present / n_rows) if n_rows else math.nan,
        }

    # Per-algorithm coverage.
    algo_coverage: dict[str, float] = {}
    for algo, sub in df.groupby("algorithm", dropna=False):
        if not isinstance(algo, str) or not algo:
            continue
        sub_full = filter_metric_rows(sub, require=primary)
        algo_coverage[algo] = (
            (len(sub_full) / len(sub)) if len(sub) else math.nan
        )

    # DBSCAN noise total.
    if "noise_count" in df.columns:
        dbscan = df.loc[df["algorithm"] == "dbscan"]
        if not dbscan.empty and "noise_count" in dbscan.columns:
            total_noise = int(
                pd.to_numeric(dbscan["noise_count"], errors="coerce").fillna(0).sum()
            )
        else:
            total_noise = 0
    else:
        total_noise = 0

    return {
        "n_rows": n_rows,
        "n_rows_with_all_metrics": n_full,
        "n_unique_algorithms": int(df["algorithm"].dropna().astype(str).nunique()),
        "metric_coverage": metric_coverage,
        "algorithm_metric_coverage": algo_coverage,
        "dbscan_total_noise_count": total_noise,
    }


# ---------------------------------------------------------------------------
# Per-dimension quality tables
# ---------------------------------------------------------------------------


def quality_by_algorithm(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Per-algorithm quality summary across all rows (not split by K)."""
    metrics = list(metrics)
    rows: list[dict[str, object]] = []
    for algo, sub in df.groupby("algorithm", dropna=False):
        if not isinstance(algo, str) or not algo:
            continue
        row: dict[str, object] = {
            "algorithm": algo,
            "n_rows": int(len(sub)),
            "n_rows_with_metrics": int(
                len(filter_metric_rows(sub, require=list(METRIC_COLUMNS)))
            ),
            "k_min": (
                int(sub["n_clusters"].dropna().astype(int).min())
                if sub["n_clusters"].notna().any()
                else MISSING
            ),
            "k_max": (
                int(sub["n_clusters"].dropna().astype(int).max())
                if sub["n_clusters"].notna().any()
                else MISSING
            ),
        }
        for m in metrics:
            stats = summarise_metric(extract_metric_vector(sub, m))
            row[f"{m}_min"] = stats["min"]
            row[f"{m}_max"] = stats["max"]
            row[f"{m}_mean"] = stats["mean"]
            row[f"{m}_std"] = stats["std"]
        runtime_stats = summarise_metric(extract_metric_vector(sub, RUNTIME_COLUMN))
        row[f"{RUNTIME_COLUMN}_mean"] = runtime_stats["mean"]
        row[f"{RUNTIME_COLUMN}_std"] = runtime_stats["std"]
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("algorithm").reset_index(drop=True)


def quality_by_k(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Per-K quality summary across all algorithms.

    Aggregates per ``n_clusters`` regardless of source experiment.
    Use :func:`quality_by_algorithm_and_k` if you need the per-algorithm
    breakdown.
    """
    metrics = list(metrics)
    rows: list[dict[str, object]] = []
    for k, sub in df.groupby("n_clusters", dropna=False):
        if pd.isna(k):
            continue
        row: dict[str, object] = {
            "n_clusters": int(k),
            "n_rows": int(len(sub)),
            "algorithms": sorted(sub["algorithm"].dropna().astype(str).unique().tolist()),
        }
        for m in metrics:
            stats = summarise_metric(extract_metric_vector(sub, m))
            row[f"{m}_min"] = stats["min"]
            row[f"{m}_max"] = stats["max"]
            row[f"{m}_mean"] = stats["mean"]
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("n_clusters").reset_index(drop=True)


def quality_by_algorithm_and_k(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Per-(algorithm, K) quality summary (descriptive)."""
    metrics = list(metrics)
    rows: list[dict[str, object]] = []
    for (algo, k), sub in df.groupby(["algorithm", "n_clusters"], dropna=False):
        if pd.isna(k) or not isinstance(algo, str) or not algo:
            continue
        row: dict[str, object] = {
            "algorithm": algo,
            "n_clusters": int(k),
            "n_rows": int(len(sub)),
        }
        for m in metrics:
            stats = summarise_metric(extract_metric_vector(sub, m))
            row[f"{m}_min"] = stats["min"]
            row[f"{m}_max"] = stats["max"]
            row[f"{m}_mean"] = stats["mean"]
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["algorithm", "n_clusters"]).reset_index(drop=True)


def quality_by_preprocessing(
    df: pd.DataFrame,
    *,
    metrics: Iterable[str] = METRIC_COLUMNS,
) -> pd.DataFrame:
    """Preprocessing-sensitivity quality table (EXP-04 only).

    Other experiments contribute rows with ``MISSING`` preprocessing
    values; those rows are dropped so the table only describes
    EXP-04 preprocessing scenarios.
    """
    metrics = list(metrics)
    work = df.copy()
    # Keep only rows with non-MISSING preprocessing values.
    work = work.loc[
        (work["transformation"] != MISSING)
        & (work["scaling"] != MISSING)
        & (work["imputation"] != MISSING)
    ]
    if work.empty:
        return work

    rows: list[dict[str, object]] = []
    for (transformation, scaling, imputation), sub in work.groupby(
        ["transformation", "scaling", "imputation"], dropna=False
    ):
        row: dict[str, object] = {
            "transformation": transformation,
            "scaling": scaling,
            "imputation": imputation,
            "n_rows": int(len(sub)),
            "n_rows_with_metrics": int(
                len(filter_metric_rows(sub, require=list(METRIC_COLUMNS)))
            ),
        }
        for m in metrics:
            stats = summarise_metric(extract_metric_vector(sub, m))
            row[f"{m}_min"] = stats["min"]
            row[f"{m}_max"] = stats["max"]
            row[f"{m}_mean"] = stats["mean"]
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        ["transformation", "scaling", "imputation"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Cross-metric conflict detection
# ---------------------------------------------------------------------------


# Default conflict / ranking group columns. These encode the boundary
# decisions documented in the post-implementation review:
#
# * EXP-05 R / S / N blocks are NEVER merged into a single
#   clustering-quality comparison condition. They differ in their
#   *experimental design* (Reproducibility vs Stability vs Noise
#   perturbation) and combining them produces a meaningless
#   aggregate.
# * EXP-03 Stage A (baseline at fixed K), Stage B (single-axis
#   hyperparameter sweep at fixed K) and Stage C (K sweep combined
#   with one hyperparameter value) are NEVER merged. The independent
#   variable differs between stages.
# * EXP-04 keeps the scenario dimension (transformation × scaling ×
#   imputation). The five repeats of the same scenario are NOT
#   independent configurations and remain in the same group.
#
# ``source_experiment`` itself is kept so cross-experiment rows are
# never accidentally merged.
DEFAULT_CONFLICT_GROUP_COLS: tuple[str, ...] = (
    "source_experiment",
    "algorithm",
    "_exp05_block",
    "_exp03_stage",
    "_exp04_scenario",
    "n_clusters",
)


# EXP-03 stage tag pattern: tokens like ``stageA`` / ``stageB`` / ``stageC``
# appear in every EXP-03 experiment_id (see :mod:`comparison`).
_EXP03_STAGE_RE = re.compile(r"stage([ABC])")


def _parse_exp03_stage(experiment_id: object) -> str:
    """Return ``A`` / ``B`` / ``C`` for EXP-03 ids, otherwise ``""``."""
    if not isinstance(experiment_id, str):
        return ""
    m = _EXP03_STAGE_RE.search(experiment_id)
    return m.group(1) if m else ""


def _scenario_label(row: pd.Series) -> str:
    """Build the EXP-04 scenario label from preprocessing columns.

    Falls back to ``""`` for rows outside EXP-04.
    """
    transformation = row.get("transformation", MISSING)
    scaling = row.get("scaling", MISSING)
    imputation = row.get("imputation", MISSING)
    if (
        not isinstance(transformation, str)
        or transformation == MISSING
        or not isinstance(scaling, str)
        or scaling == MISSING
        or not isinstance(imputation, str)
        or imputation == MISSING
    ):
        return ""
    return f"{transformation}|{scaling}|{imputation}"


def add_ranking_boundary_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add the auxiliary columns used by ranking / conflict detection.

    The added columns are:

    * ``_exp05_block`` — ``"R"`` / ``"S"`` / ``"N"`` for EXP-05 rows,
      otherwise ``""``.
    * ``_exp03_stage`` — ``"A"`` / ``"B"`` / ``"C"`` for EXP-03 rows,
      otherwise ``""``.
    * ``_exp04_scenario`` — ``"{transformation}|{scaling}|{imputation}"``
      for EXP-04 rows; otherwise ``""``.

    The columns are *deterministic* functions of the input columns;
    no inference or ranking is performed here.
    """
    work = df.copy()

    if "source_block" in work.columns:
        block = work["source_block"].astype(str).where(
            work["source_block"].notna()
            & (work["source_block"].astype(str) != "nan"),
            other="",
        )
    else:
        block = pd.Series([""] * len(work), index=work.index)
    # Empty string means "not EXP-05"; both are safe grouping values.
    work["_exp05_block"] = block.fillna("").astype(str)

    work["_exp03_stage"] = work["experiment_id"].apply(_parse_exp03_stage)

    if {"transformation", "scaling", "imputation"}.issubset(work.columns):
        work["_exp04_scenario"] = work.apply(_scenario_label, axis=1)
    else:
        work["_exp04_scenario"] = ""

    return work


def default_conflict_group_cols() -> tuple[str, ...]:
    """Return the default conflict group columns.

    Small accessor so callers (tests, runners) can introspect the
    canonical group boundary without duplicating the tuple literal.
    """
    return DEFAULT_CONFLICT_GROUP_COLS


# Note documenting the rank_tolerance threshold semantics. The number
# itself is unchanged from the previous implementation; the note
# records that it is a WORKING_ANALYTICAL_THRESHOLD pending mentor /
# methodology sign-off.
RANK_TOLERANCE_NOTE: str = (
    "rank_tolerance=1 is a WORKING_ANALYTICAL_THRESHOLD. A row is "
    "flagged only when its primary (silhouette) rank disagrees with "
    "the secondary / tertiary rank by more than 1 position within the "
    "ranking group. The threshold is intentionally small: it surfaces "
    "ranks that are visibly inconsistent while accepting ties (min "
    "rank) and trivial reorderings. Any change to this value requires "
    "an ADR documenting the chosen interpretation; this implementation "
    "does NOT change it to match a desired conflict count."
)


def _signed_abs_diff(left: pd.Series, right: pd.Series) -> pd.Series:
    """Return ``abs(left - right)`` using signed-integer arithmetic.

    Pandas' :meth:`Series.rank` returns ``UInt64`` for non-null numeric
    inputs. Subtracting two ``UInt64`` Series underflows when the
    left-hand rank is smaller than the right-hand rank (a difference of
    ``-1`` becomes ``2**64 - 1``). The downstream ``> rank_tolerance``
    check then produces a *false positive* conflict flag.

    Casting to ``Int64`` *before* the subtraction eliminates the
    underflow. ``<NA>`` entries are preserved (the resulting column
    stays nullable).
    """
    left_signed = left.astype("Int64")
    right_signed = right.astype("Int64")
    diff = (left_signed - right_signed).abs()
    # ``Int64`` -> Float64 keeps NaN propagation explicit for the
    # downstream ``> rank_tolerance`` comparison.
    return diff.astype("Float64")


def cross_metric_conflicts(
    df: pd.DataFrame,
    *,
    primary: str = "silhouette",
    secondary: str = "davies_bouldin",
    tertiary: str = "calinski_harabasz",
    rank_tolerance: int = 1,
    group_cols: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Identify rows where Silhouette rank differs from DBI / CH rank.

    For each ranking group the rows are ranked by each metric; a row
    is flagged if its primary rank differs from the secondary or
    tertiary rank by more than ``rank_tolerance`` positions.

    Parameters
    ----------
    df : pandas.DataFrame
        Standardised repository (will be filtered for the required metrics).
    primary, secondary, tertiary : str
        Metric columns.
    rank_tolerance : int, default 1
        Maximum allowed rank difference. Working analytical threshold
        — see :data:`RANK_TOLERANCE_NOTE`.
    group_cols : iterable of str, optional
        Columns defining the ranking group. When ``None``, defaults to
        :data:`DEFAULT_CONFLICT_GROUP_COLS`, which enforces the
        EXP-05 R/S/N, EXP-03 Stage A/B/C and EXP-04 scenario
        boundaries documented above.

    Returns
    -------
    pandas.DataFrame
        One row per ranking-group combination with the per-metric
        ranks and conflict flags.

    Notes
    -----
    The rank difference is computed on a **signed-integer** dtype to
    avoid the ``UInt64`` underflow documented in the EVA-02 post-
    implementation review (see EVA-02 review, item "Critical — FIX
    UInt64 underflow").
    """
    for col in (primary, secondary, tertiary):
        if col not in df.columns:
            raise KeyError(f"missing required metric column: {col}")

    work = filter_metric_rows(df, require=[primary, secondary, tertiary])
    if work.empty:
        return work

    work = add_ranking_boundary_columns(work)

    if group_cols is None:
        cols = list(DEFAULT_CONFLICT_GROUP_COLS)
    else:
        cols = list(group_cols)

    # Drop the auxiliary boundary columns if the caller passed their
    # own group_cols.
    keep_aux = {"_exp05_block", "_exp03_stage", "_exp04_scenario"}.intersection(cols)
    if not keep_aux:
        work = work.drop(
            columns=[
                c
                for c in ("_exp05_block", "_exp03_stage", "_exp04_scenario")
                if c in work.columns
            ]
        )

    ranked = work.copy()
    # Compute ranks in one shot per column using groupby + rank (avoids
    # late-binding closure issues with deferred transform execution).
    ranked["_rank_primary"] = ranked.groupby(cols, dropna=False)[primary].transform(
        lambda s: s.rank(
            method="min",
            ascending=(
                METRIC_DIRECTIONS.get(primary, HIGHER_IS_BETTER) == LOWER_IS_BETTER
            ),
        )
    )
    ranked["_rank_secondary"] = ranked.groupby(cols, dropna=False)[secondary].transform(
        lambda s: s.rank(
            method="min",
            ascending=(
                METRIC_DIRECTIONS.get(secondary, HIGHER_IS_BETTER) == LOWER_IS_BETTER
            ),
        )
    )
    ranked["_rank_tertiary"] = ranked.groupby(cols, dropna=False)[tertiary].transform(
        lambda s: s.rank(
            method="min",
            ascending=(
                METRIC_DIRECTIONS.get(tertiary, HIGHER_IS_BETTER) == LOWER_IS_BETTER
            ),
        )
    )
    # Signed-integer subtraction avoids UInt64 underflow when the
    # primary rank is *smaller* than the secondary / tertiary rank.
    ranked["conflict_with_secondary"] = (
        _signed_abs_diff(ranked["_rank_primary"], ranked["_rank_secondary"])
        > rank_tolerance
    )
    ranked["conflict_with_tertiary"] = (
        _signed_abs_diff(ranked["_rank_primary"], ranked["_rank_tertiary"])
        > rank_tolerance
    )
    keep = [
        "source_experiment",
        "algorithm",
        "n_clusters",
        "experiment_id",
        "hyperparameters",
        primary,
        secondary,
        tertiary,
        "_rank_primary",
        "_rank_secondary",
        "_rank_tertiary",
        "conflict_with_secondary",
        "conflict_with_tertiary",
    ]
    # Add boundary columns if the caller requested them so reviewers
    # can verify the grouping.
    for c in cols:
        if c not in keep and c in ranked.columns:
            keep.append(c)
    out = ranked.loc[:, keep].copy()
    out = out.rename(
        columns={
            "_rank_primary": f"rank_{primary}",
            "_rank_secondary": f"rank_{secondary}",
            "_rank_tertiary": f"rank_{tertiary}",
        }
    )
    return out.sort_values(cols).reset_index(drop=True)


# ---------------------------------------------------------------------------
# DBSCAN-specific noise summary
# ---------------------------------------------------------------------------


def dbscan_noise_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-(source_experiment, n_clusters_realized) DBSCAN noise summary.

    ``silhouette`` is computed over non-noise points; ``noise_count``
    and ``noise_ratio`` describe how many / what fraction of customers
    fell outside any cluster.
    """
    work = df.loc[df["algorithm"] == "dbscan"].copy()
    if work.empty:
        return work

    rows: list[dict[str, object]] = []
    for (source_exp, n_clus), sub in work.groupby(
        ["source_experiment", "n_clusters_realized"], dropna=False
    ):
        noise_count_stats = summarise_metric(
            pd.to_numeric(sub["noise_count"], errors="coerce").tolist()
        )
        noise_ratio_stats = summarise_metric(
            pd.to_numeric(sub["noise_ratio"], errors="coerce").tolist()
        )
        sil_stats = summarise_metric(extract_metric_vector(sub, "silhouette"))
        dbi_stats = summarise_metric(extract_metric_vector(sub, "davies_bouldin"))
        rows.append(
            {
                "source_experiment": source_exp,
                "n_clusters_realized": (
                    int(n_clus) if pd.notna(n_clus) else MISSING
                ),
                "n_rows": int(len(sub)),
                "noise_count_min": noise_count_stats["min"],
                "noise_count_max": noise_count_stats["max"],
                "noise_count_mean": noise_count_stats["mean"],
                "noise_ratio_min": noise_ratio_stats["min"],
                "noise_ratio_max": noise_ratio_stats["max"],
                "noise_ratio_mean": noise_ratio_stats["mean"],
                "silhouette_mean": sil_stats["mean"],
                "davies_bouldin_mean": dbi_stats["mean"],
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["source_experiment", "n_clusters_realized"]).reset_index(
        drop=True
    )
