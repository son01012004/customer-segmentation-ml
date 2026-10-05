"""CP-01 per-cluster size analysis.

For each analysis unit, this module computes:

- ``ClusterSizeRow`` — one row per cluster (cluster ID, count, %
  of eligible customers, relative size ratio).
- ``NoiseRow`` — one row per unit for DBSCAN noise (separate from
  customer segments).

Denominator policy
------------------

Percentage is computed against the **eligible** denominator, i.e., the
number of unique CustomerIDs in the unit's labels frame. For DBSCAN we
report two percentages:

- ``pct_of_assigned`` — share among the assigned customers
  (excluding noise from the denominator).
- ``pct_of_total`` — share among ALL 4,371 customers
  (including noise in the denominator).

This is documented in the row so a reader can clearly see whether the
denominator is the eligible subset or the full population.

Ranking and naming
------------------

CP-01 does NOT rank algorithms and does NOT name customer segments. Each
cluster row is reported by its integer ClusterLabel exactly as it
appears in the source artifact (no relabelling).

Hard constraints (AGENTS.md §2):

- No ranking, no "best / winner / optimal / recommended" labels.
- No segment naming.
- No claim about cluster quality from sizes alone.
- No mutation of source artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
    AnalysisUnit,
)


@dataclass(frozen=True)
class ClusterSizeRow:
    """One cluster-row of the size table."""

    unit_id: str
    algorithm: str
    algorithm_family: str
    source_experiment: str
    configuration_id: str
    configuration_status: str
    cluster_id: int  # -1 for noise (DBSCAN only)
    is_noise: bool
    customer_count: int
    pct_of_assigned: float  # vs eligible (non-noise) denominator
    pct_of_total: float  # vs full unit customer count (noise in denom)
    relative_size_ratio: float  # cluster_count / largest_cluster_count


@dataclass(frozen=True)
class NoiseRow:
    """A single noise summary row for DBSCAN."""

    unit_id: str
    algorithm: str
    noise_count: int
    pct_of_total: float


def _normalise_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean labels DataFrame with required columns."""
    cols = set(df.columns)
    if {"CustomerID", "ClusterLabel", "IsNoise"}.issubset(cols):
        return df.loc[:, ["CustomerID", "ClusterLabel", "IsNoise"]].copy()
    # adapt alternative schemas
    if "CustomerID" in cols and "ClusterLabel" in cols:
        out = df.loc[:, ["CustomerID", "ClusterLabel"]].copy()
        out["IsNoise"] = out["ClusterLabel"] == -1
        return out
    raise ValueError(
        f"labels frame missing required columns CustomerID / ClusterLabel / IsNoise"
    )


def compute_cluster_size_table(units: list[AnalysisUnit]) -> list[ClusterSizeRow]:
    """Return per-cluster size rows for every analysis unit.

    For EXP-01 / 5 algorithms this produces actual cluster-size rows.
    For EXP-03 units without persisted labels, an empty list is returned
    (the runner is responsible for surfacing this as ``NOT_AVAILABLE``).
    """
    rows: list[ClusterSizeRow] = []
    for unit in units:
        if not unit.labels_persisted:
            continue
        df = _normalise_labels(unit.labels_frame())
        # Eligible denominator = unique CustomerIDs
        n_total = int(df["CustomerID"].nunique())
        # DBSCAN: noise excluded from segments but reported separately.
        noise_mask = df["IsNoise"].astype(bool) | (df["ClusterLabel"] == -1)
        n_noise = int(noise_mask.sum())
        assigned = df.loc[~noise_mask].copy()
        n_assigned = int(assigned["CustomerID"].nunique())
        # Largest segment count (excludes noise)
        if n_assigned == 0:
            # all-noise DBSCAN edge case
            largest = 1
        else:
            counts = assigned["ClusterLabel"].value_counts()
            largest = int(counts.max()) if not counts.empty else 1
        # One row per cluster including the noise "cluster" for DBSCAN
        for cl, sub in df.groupby("ClusterLabel", sort=True):
            is_noise = bool((sub["ClusterLabel"] == -1).iloc[0] or
                            sub["IsNoise"].astype(bool).all())
            n = int(sub["CustomerID"].nunique())
            pct_assigned = (
                (n / n_assigned * 100.0) if n_assigned > 0 and not is_noise
                else float("nan")
            )
            pct_total = (n / n_total * 100.0) if n_total > 0 else 0.0
            rel = (n / largest) if largest > 0 else 0.0
            row = ClusterSizeRow(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                algorithm_family=unit.algorithm_family,
                source_experiment=unit.source_experiment,
                configuration_id=unit.configuration_id,
                configuration_status=unit.configuration_status,
                cluster_id=int(cl),
                is_noise=is_noise,
                customer_count=n,
                pct_of_assigned=pct_assigned,
                pct_of_total=pct_total,
                relative_size_ratio=rel,
            )
            rows.append(row)
        # no separate NoiseRow for non-DBSCAN (n_noise = 0)
        if unit.algorithm == "dbscan" and n_noise > 0:
            # The noise row in the loop already covers DBSCAN
            pass
    return rows


def compute_noise_summary(units: list[AnalysisUnit]) -> list[NoiseRow]:
    """Return one noise row per DBSCAN unit (no non-DBSCAN rows)."""
    out: list[NoiseRow] = []
    for unit in units:
        if not unit.labels_persisted:
            continue
        if unit.algorithm != "dbscan":
            continue
        df = _normalise_labels(unit.labels_frame())
        n_total = int(df["CustomerID"].nunique())
        n_noise = int(((df["ClusterLabel"] == -1) | df["IsNoise"].astype(bool)).sum())
        out.append(
            NoiseRow(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                noise_count=n_noise,
                pct_of_total=(n_noise / n_total * 100.0) if n_total > 0 else 0.0,
            )
        )
    return out


# Restored for re-export
__all__ = [
    "ClusterSizeRow",
    "NoiseRow",
    "compute_cluster_size_table",
    "compute_noise_summary",
    "ALGORITHMS",
    "AnalysisUnit",
]
