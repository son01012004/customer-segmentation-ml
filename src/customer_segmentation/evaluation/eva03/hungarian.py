"""Cluster Hungarian alignment summary for EVA-03.

Computes the Hungarian cluster-label alignment between two selected
runs per algorithm, per block. The result is recorded for
traceability — it is NOT a stability metric.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- Hungarian matching is DESCRIPTIVE ONLY; no scoring.
- The output records per-cluster correspondence count and overlap
  fraction. No composite score is computed.
- DBSCAN noise (-1) is excluded from the contingency matrix because
  Hungarian matching assumes positive overlap counts.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.eva03.label_compare import (
    DBSCAN_NOISE_LABEL,
    run_hungarian_for_pair,
)
from customer_segmentation.evaluation.eva03.load import (
    _labels_series_for_run,
)

__all__ = ["compute_hungarian_summary"]


def compute_hungarian_summary(
    labels_df: pd.DataFrame,
    *,
    pair_selector: str = "first_two",
) -> pd.DataFrame:
    """Compute Hungarian cluster-label alignments per (block, algorithm).

    Parameters
    ----------
    labels_df : pd.DataFrame
        The full EXP-05 labels artifact.
    pair_selector : str, default "first_two"
        How to pick a pair within each (block, algorithm):

        - ``"first_two"``: compare the first two run_ids (after
          sorting by sigma / seed as appropriate).

        Other selectors can be added later.

    Returns
    -------
    pd.DataFrame
        One row per (block, algorithm, source_label) with columns:

        ``block, algorithm, run_id_a, run_id_b, source_label, target_label,
        overlap_count, total_customers, overlap_fraction``.

    Notes
    -----
    Hungarian matching is DESCRIPTIVE ONLY. The output is reported in
    the comparison report with an explicit "Hungarian alignment is
    descriptive, not a stability metric" caption.
    """
    rows: list[dict[str, Any]] = []
    if pair_selector != "first_two":
        raise ValueError(
            f"Unsupported pair_selector {pair_selector!r}. Use 'first_two'."
        )

    for (block, algo), df_a in labels_df.groupby(
        ["block", "algorithm"], sort=True
    ):
        if block not in ("R", "S", "N"):
            continue
        if len(df_a["run_id"].unique()) < 2:
            continue

        if block == "N":
            # Order: sigma=0 first, then (sigma, pseed).
            df_sorted = df_a.copy()
            df_sorted["_sort"] = df_a.apply(
                lambda r: (
                    float(r.get("sigma") or 0.0)
                    if pd.notna(r.get("sigma"))
                    else 0.0,
                    float(r.get("perturbation_seed") or -1.0)
                    if pd.notna(r.get("perturbation_seed"))
                    else -1.0,
                ),
                axis=1,
            )
            df_sorted = df_sorted.sort_values("_sort")
            run_ids = df_sorted["run_id"].unique().tolist()
        else:
            run_ids = sorted(df_a["run_id"].unique().tolist())

        if len(run_ids) < 2:
            continue
        run_a, run_b = run_ids[0], run_ids[1]
        s_a = _labels_series_for_run(df_a, run_a)
        s_b = _labels_series_for_run(df_a, run_b)
        common = s_a.index.intersection(s_b.index)
        s_a = s_a.loc[common]
        s_b = s_b.loc[common]
        exclude = DBSCAN_NOISE_LABEL if algo == "dbscan" else None
        assign = run_hungarian_for_pair(
            algo,
            run_a,
            run_b,
            s_a.to_numpy(),
            s_b.to_numpy(),
            exclude_noise_label=exclude,
        )
        total = max(assign.total_customers, 1)
        for src, tgt, ovr in zip(
            assign.source_labels, assign.target_labels, assign.overlap_counts
        ):
            rows.append(
                {
                    "block": block,
                    "algorithm": algo,
                    "run_id_a": run_a,
                    "run_id_b": run_b,
                    "source_label": int(src),
                    "target_label": int(tgt),
                    "overlap_count": int(ovr),
                    "total_customers": int(total),
                    "overlap_fraction": float(ovr / total),
                }
            )
    return pd.DataFrame(rows)
