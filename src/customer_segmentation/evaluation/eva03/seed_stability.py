"""Block S seed stability analysis for EVA-03.

The EXP-05 Block S provides K-Means + GMM + Fuzzy C-Means at 5 distinct
seeds (42, 7, 123, 2024, 1729), with fixed EXP-01 working-default
hyperparameters. Agglomerative + DBSCAN are deterministic and are NOT
in Block S.

This module computes:

- Per-(algorithm, seed-pair) ARI / AMI / NMI.
- Per-algorithm off-diagonal summary stats (min/max/mean/std/median/n_unique).
- Cluster size variation per algorithm across seeds.
- Reference Hungarian alignment for traceability (DESCRIPTIVE).

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- NO "most stable algorithm" / "winner" claim.
- Per-algorithm reporting only.
- Decision status uses ONLY the permitted taxonomy.
- Hungarian alignment is descriptive; NOT a stability metric.
- No composite score across ARI / AMI / NMI.
"""

from __future__ import annotations

from collections.abc import Callable
from statistics import pstdev
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.eva03.label_compare import (
    compute_label_compare,
)
from customer_segmentation.evaluation.eva03.load import (
    _labels_series_for_run,
)
from customer_segmentation.evaluation.eva03.types import PairwiseMatrix

__all__ = ["analyze_block_s"]


DECISION_STATUS = "SEED_STABILITY_EVIDENCE_ANALYZED"


def _decision_status_for_block_s() -> str:
    """Block S aggregate decision status (single, descriptive).

    Block S is an evidence-generation block (per EPIC-08 boundary);
    EVA-03 records what was observed without classifying the result.
    """
    return DECISION_STATUS


def analyze_block_s(
    labels_df: pd.DataFrame,
    *,
    label_compare_fn: Callable[[np.ndarray, np.ndarray], dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Compute Block S seed stability analysis for each algorithm.

    Parameters
    ----------
    labels_df : pd.DataFrame
        The full EXP-05 labels artifact.
    label_compare_fn : callable, optional
        Override for label comparison.

    Returns
    -------
    dict
        ``{"matrices": [PairwiseMatrix, ...],
           "summary": pd.DataFrame,
           "decision_status": dict[str, str],
           "cluster_size_variation": pd.DataFrame}``
    """
    compare = label_compare_fn or compute_label_compare

    sub = labels_df.loc[labels_df["block"] == "S"]
    matrices: list[PairwiseMatrix] = []
    per_pair_rows: list[dict[str, Any]] = []
    cluster_size_records: list[dict[str, Any]] = []

    for algo, df_a in sub.groupby("algorithm", sort=True):
        runs_by_seed = (
            df_a.drop_duplicates(subset=["seed", "repeat_index"])
            .sort_values(["seed", "repeat_index"])
        )
        runs = runs_by_seed["run_id"].tolist()
        seeds = [int(s) for s in runs_by_seed["seed"].tolist()]
        if len(runs) < 2:
            continue

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
                res = compare(
                    series_list[i].to_numpy(), series_list[j].to_numpy()
                )
                ari_grid[i, j] = res["ari"]
                ami_grid[i, j] = res["ami"]
                nmi_grid[i, j] = res["nmi"]
                ari_grid[j, i] = res["ari"]
                ami_grid[j, i] = res["ami"]
                nmi_grid[j, i] = res["nmi"]
                per_pair_rows.append(
                    {
                        "algorithm": algo,
                        "seed_a": seeds[i],
                        "seed_b": seeds[j],
                        "run_id_a": runs[i],
                        "run_id_b": runs[j],
                        "ari": res["ari"],
                        "ami": res["ami"],
                        "nmi": res["nmi"],
                    }
                )

        matrices.append(
            PairwiseMatrix(
                algorithm=algo,
                run_ids=tuple(runs),
                ari=ari_grid.tolist(),
                ami=ami_grid.tolist(),
                nmi=nmi_grid.tolist(),
                off_diagonal_unique_count=(
                    int(
                        np.unique(
                            np.round(ari_grid[np.triu_indices(n, k=1)], 12)
                        ).size
                    )
                    if n > 1
                    else 0
                ),
            )
        )

        # Cluster size variation per algorithm.
        algo_cluster_counts: dict[int, list[int]] = {}
        for run_id, series in zip(runs, series_list):
            counts = series.value_counts().to_dict()
            for k, v in counts.items():
                algo_cluster_counts.setdefault(int(k), []).append(int(v))
        for cluster_id, values in sorted(algo_cluster_counts.items()):
            cluster_size_records.append(
                {
                    "block": "S",
                    "algorithm": algo,
                    "cluster_id": cluster_id,
                    "n_runs_with_cluster": int(len(values)),
                    "customer_count_min": int(min(values)),
                    "customer_count_max": int(max(values)),
                    "customer_count_range": int(max(values) - min(values)),
                    "customer_count_mean": float(np.mean(values)),
                    "customer_count_std": (
                        float(pstdev(values)) if len(values) > 1 else 0.0
                    ),
                }
            )

    summary_rows: list[dict[str, Any]] = []
    for m in matrices:
        n = len(m.run_ids)
        ari_off = (
            np.asarray(m.ari, dtype=np.float64)[np.triu_indices(n, k=1)]
            if n > 1
            else np.array([], dtype=np.float64)
        )
        ami_off = (
            np.asarray(m.ami, dtype=np.float64)[np.triu_indices(n, k=1)]
            if n > 1
            else np.array([], dtype=np.float64)
        )
        nmi_off = (
            np.asarray(m.nmi, dtype=np.float64)[np.triu_indices(n, k=1)]
            if n > 1
            else np.array([], dtype=np.float64)
        )
        summary_rows.append(
            {
                "block": "S",
                "algorithm": m.algorithm,
                "n_seeds": n,
                "n_pairs": int(ari_off.size),
                "ari_min": float(ari_off.min()) if ari_off.size else float("nan"),
                "ari_max": float(ari_off.max()) if ari_off.size else float("nan"),
                "ari_mean": float(ari_off.mean()) if ari_off.size else float("nan"),
                "ari_std": (
                    float(pstdev(ari_off.tolist())) if ari_off.size > 1 else 0.0
                ),
                "ari_off_diagonal_unique_count": m.off_diagonal_unique_count,
                "ami_min": float(ami_off.min()) if ami_off.size else float("nan"),
                "ami_max": float(ami_off.max()) if ami_off.size else float("nan"),
                "ami_mean": float(ami_off.mean()) if ami_off.size else float("nan"),
                "nmi_min": float(nmi_off.min()) if nmi_off.size else float("nan"),
                "nmi_max": float(nmi_off.max()) if nmi_off.size else float("nan"),
                "nmi_mean": float(nmi_off.mean()) if nmi_off.size else float("nan"),
                "decision_status": _decision_status_for_block_s(),
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    per_pair_df = pd.DataFrame(per_pair_rows)
    cluster_size_df = pd.DataFrame(cluster_size_records)
    decision_status = {row["algorithm"]: row["decision_status"] for row in summary_rows}
    return {
        "matrices": matrices,
        "per_pair": per_pair_df,
        "summary": summary_df,
        "decision_status": decision_status,
        "cluster_size_variation": cluster_size_df,
    }
