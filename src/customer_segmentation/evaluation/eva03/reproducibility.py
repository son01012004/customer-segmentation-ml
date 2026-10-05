"""Block R reproducibility analysis for EVA-03.

The EXP-05 Block R provides 5 algorithms × n_repeat=5 × seed=42 runs.
The expected outcome under fixed-seed determinism is that all pairs of
repeats within the same algorithm yield ARI = AMI = NMI = 1.0 (perfectly
identical labels up to permutation).

This module computes:

- Per-(algorithm, repeat-pair) ARI / AMI / NMI (flat CSV-shape rows).
- Per-algorithm off-diagonal uniqueness (number of distinct values).
- Hungarian alignment for traceability (DESCRIPTIVE; NOT a metric).
- Aggregate per-algorithm decision status.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- No "best reproducibility" / "winner algorithm" claims.
- Decision status uses ONLY the permitted taxonomy.
- Hungarian matching is recorded for traceability; it is NOT used to
  rank algorithms.
"""

from __future__ import annotations

from collections.abc import Callable
from statistics import mean, median, pstdev
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.eva03.label_compare import (
    DBSCAN_NOISE_LABEL,
    compute_label_compare,
    run_hungarian_for_pair,
)
from customer_segmentation.evaluation.eva03.load import (
    _labels_series_for_run,
)
from customer_segmentation.evaluation.eva03.types import (
    BlockRPairwiseRow,
    PairwiseMatrix,
)

__all__ = [
    "analyze_block_r",
    "decision_status_for_block_r",
]


def _off_diagonal_stats(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return {
            "n_pairs": 0,
            "min": float("nan"),
            "max": float("nan"),
            "mean": float("nan"),
            "median": float("nan"),
            "std": float("nan"),
            "n_unique": 0,
        }
    rounded = np.round(arr, decimals=12)
    return {
        "n_pairs": int(arr.size),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
        "median": float(median(arr.tolist())),
        "std": float(pstdev(arr.tolist())) if arr.size > 1 else 0.0,
        "n_unique": int(np.unique(rounded).size),
    }


def decision_status_for_block_r(
    matrix: PairwiseMatrix,
    *,
    verified_threshold: float = 1.0 - 1e-9,
) -> str:
    """Choose a decision status for one Block R algorithm.

    A Block R algorithm is ``REPRODUCIBILITY_VERIFIED_LABEL_LEVEL`` if
    every off-diagonal ARI entry is at least ``1 - 1e-9``. Otherwise
    it is ``REPRODUCIBILITY_FAILED_LABEL_LEVEL``.

    The threshold is set to ``1.0 - 1e-9`` to absorb floating-point
    drift (Float64 operations can introduce sub-1.0 noise); it is NOT
    a flexibility window for "approximate reproducibility".
    """
    ari = np.asarray(matrix.ari, dtype=np.float64)
    n = ari.shape[0]
    if n < 2:
        return "REPRODUCIBILITY_VERIFIED_LABEL_LEVEL"
    triu = ari[np.triu_indices(n, k=1)]
    if np.all(triu >= verified_threshold):
        return "REPRODUCIBILITY_VERIFIED_LABEL_LEVEL"
    return "REPRODUCIBILITY_FAILED_LABEL_LEVEL"


def analyze_block_r(
    labels_df: pd.DataFrame,
    *,
    label_compare_fn: Callable[[np.ndarray, np.ndarray], dict[str, float]] | None = None,
    include_hungarian: bool = True,
) -> dict[str, Any]:
    """Compute the Block R reproducibility analysis.

    Parameters
    ----------
    labels_df : pd.DataFrame
        The full EXP-05 labels artifact.
    label_compare_fn : callable, optional
        Override for label comparison. Defaults to
        :func:`eva03.label_compare.compute_label_compare`.
    include_hungarian : bool, default True
        If True, also compute a Hungarian-matching alignment for one
        reference pair per algorithm (descriptive only).

    Returns
    -------
    dict
        ``{"per_pair": [BlockRPairwiseRow, ...],
           "matrices": [PairwiseMatrix, ...],
           "summary": pd.DataFrame,
           "decision_status": dict[str, str],
           "hungarian": [HungarianAssignment, ...]}``
    """
    compare = label_compare_fn or compute_label_compare

    pairwise_rows: list[BlockRPairwiseRow] = []
    matrices: list[PairwiseMatrix] = []
    decisions: dict[str, str] = {}

    sub = labels_df.loc[labels_df["block"] == "R"]
    for algo, df_a in sub.groupby("algorithm", sort=True):
        runs = sorted(df_a["run_id"].unique().tolist())
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
        ari_grid = np.zeros((n, n), dtype=np.float64)
        ami_grid = np.zeros((n, n), dtype=np.float64)
        nmi_grid = np.zeros((n, n), dtype=np.float64)
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
                res = compare(series_list[i].to_numpy(), series_list[j].to_numpy())
                ari_grid[i, j] = res["ari"]
                ami_grid[i, j] = res["ami"]
                nmi_grid[i, j] = res["nmi"]

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                pairwise_rows.append(
                    BlockRPairwiseRow(
                        algorithm=algo,
                        run_id_a=runs[i],
                        run_id_b=runs[j],
                        repeat_index_a=int(runs[i].split("-r")[-1])
                        if "-r" in runs[i]
                        else 0,
                        repeat_index_b=int(runs[j].split("-r")[-1])
                        if "-r" in runs[j]
                        else 0,
                        ari=float(ari_grid[i, j]),
                        ami=float(ami_grid[i, j]),
                        nmi=float(nmi_grid[i, j]),
                        n_customers=int(len(series_list[i])),
                    )
                )

        matrix = PairwiseMatrix(
            algorithm=algo,
            run_ids=tuple(runs),
            ari=ari_grid.tolist(),
            ami=ami_grid.tolist(),
            nmi=nmi_grid.tolist(),
            off_diagonal_unique_count=(
                int(np.unique(np.round(ari_grid[np.triu_indices(n, k=1)], 12)).size)
                if n > 1
                else 0
            ),
        )
        matrices.append(matrix)
        decisions[algo] = decision_status_for_block_r(matrix)

    # Hungarian alignments (descriptive): one pair per algorithm (first two runs).
    hungarians: list[Any] = []
    if include_hungarian:
        for matrix in matrices:
            run_ids = matrix.run_ids
            if len(run_ids) < 2:
                continue
            df_alg = labels_df.loc[
                (labels_df["block"] == "R") & (labels_df["algorithm"] == matrix.algorithm)
            ]
            s_a = _labels_series_for_run(df_alg, run_ids[0])
            s_b = _labels_series_for_run(df_alg, run_ids[1])
            common = s_a.index.intersection(s_b.index)
            s_a = s_a.loc[common]
            s_b = s_b.loc[common]
            exclude_noise = (
                DBSCAN_NOISE_LABEL if matrix.algorithm == "dbscan" else None
            )
            hungarians.append(
                run_hungarian_for_pair(
                    matrix.algorithm,
                    run_ids[0],
                    run_ids[1],
                    s_a.to_numpy(),
                    s_b.to_numpy(),
                    exclude_noise_label=exclude_noise,
                )
            )

    summary_rows: list[dict[str, Any]] = []
    for matrix in matrices:
        ari_off = (
            np.asarray(matrix.ari, dtype=np.float64)[
                np.triu_indices(matrix.ari.__len__() if matrix.ari else 1, k=1)
            ]
            if matrix.ari
            else np.array([], dtype=np.float64)
        )
        n = matrix.ari.__len__() if matrix.ari else 0
        ari_off = np.asarray(matrix.ari, dtype=np.float64)[np.triu_indices(n, k=1)] if n > 1 else np.array([])
        ami_off = np.asarray(matrix.ami, dtype=np.float64)[np.triu_indices(n, k=1)] if n > 1 else np.array([])
        nmi_off = np.asarray(matrix.nmi, dtype=np.float64)[np.triu_indices(n, k=1)] if n > 1 else np.array([])
        summary_rows.append(
            {
                "algorithm": matrix.algorithm,
                "n_runs": n,
                "n_pairs": int(ari_off.size),
                "ari_min": float(ari_off.min()) if ari_off.size else float("nan"),
                "ari_max": float(ari_off.max()) if ari_off.size else float("nan"),
                "ari_mean": float(ari_off.mean()) if ari_off.size else float("nan"),
                "ari_std": float(pstdev(ari_off.tolist())) if ari_off.size > 1 else 0.0,
                "ami_min": float(ami_off.min()) if ami_off.size else float("nan"),
                "ami_max": float(ami_off.max()) if ami_off.size else float("nan"),
                "ami_mean": float(ami_off.mean()) if ami_off.size else float("nan"),
                "nmi_min": float(nmi_off.min()) if nmi_off.size else float("nan"),
                "nmi_max": float(nmi_off.max()) if nmi_off.size else float("nan"),
                "nmi_mean": float(nmi_off.mean()) if nmi_off.size else float("nan"),
                "off_diagonal_unique_count": matrix.off_diagonal_unique_count,
                "decision_status": decisions[matrix.algorithm],
            }
        )
    summary_df = pd.DataFrame(summary_rows)

    return {
        "per_pair": pairwise_rows,
        "matrices": matrices,
        "decision_status": decisions,
        "summary": summary_df,
        "hungarian": hungarians,
    }
