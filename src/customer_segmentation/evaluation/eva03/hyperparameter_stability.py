"""EXP-01 default vs EXP-03 working-selected metadata comparison for EVA-03.

Methodology notes
-----------------

The task brief asks for a comparison between EXP-01 default configurations
and EXP-03 working-selected configurations.

The repository evidence is:

- EXP-01 baseline summary contains metric values for each of the 5
  algorithms at K=4 with EXP-01 working default hyperparameters.
- EXP-03 ``selected_configurations.csv`` contains per-algorithm
  working-selected metric values, but DOES NOT contain per-customer
  cluster labels.

A label-level (ARI / AMI / NMI) comparison between EXP-01 and EXP-03
working-selected CANNOT be computed from the current artifacts. This
module surfaces:

- Per-algorithm metric values side-by-side (silhouette, DBI, CH, WCSS,
  n_clusters).
- The EXP-03 selection metadata (decision_status, sweep parameter,
  primary criterion, evidence note).
- An explicit note that ``source_evidence = METRIC_BASED_ONLY``.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- NO promotion of WORKING_SELECTED to RESEARCH_APPROVED.
- NO composite score / weighted ranking.
- NO "better" / "best" / "winner" comparisons.
- Each algorithm reported independently.
- Decision status uses ONLY the permitted taxonomy.
- If a methodology is pending, report it; do not invent.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from customer_segmentation.evaluation.eva03.types import EXP03ComparisonRow

__all__ = ["analyze_hyperparameter_stability"]


DECISION_STATUS = "HYPERPARAMETER_COMPARISON_METADATA"


def analyze_hyperparameter_stability(
    exp01_summary_csv: pd.DataFrame,
    exp03_selected_df: pd.DataFrame,
    *,
    exp01_cluster_labels_dir: str | None = None,
) -> dict[str, Any]:
    """Compute the EXP-01 vs EXP-03 working-selected comparison.

    Parameters
    ----------
    exp01_summary_csv : pd.DataFrame
        The EXP-01 ``exp01_baseline_summary.csv`` (per-algorithm metrics).
    exp03_selected_df : pd.DataFrame
        The EXP-03 ``exp03_selected_configurations.csv``.
    exp01_cluster_labels_dir : str, optional
        Path to ``reports/exp01`` for verifying EXP-01 default labels
        exist. If labels for EXP-03 working-selected configurations
        are not provided as input, no label-level comparison is
        possible.

    Returns
    -------
    dict
        ``{"per_algorithm": pd.DataFrame,
           "decision_status": dict[str, str],
           "limitations": list[str],
           "evidence_summary": dict[str, str]}``
    """
    rows: list[EXP03ComparisonRow] = []
    evidence_summary: dict[str, str] = {}
    limitations: list[str] = []
    limitations.append(
        "EXP-03 working-selected cluster labels are NOT persisted in the "
        "current EXP-05 artifact. Label-level (ARI/AMI/NMI) comparison "
        "between EXP-01 default and EXP-03 working-selected is therefore "
        "NOT computable from the existing evidence."
    )
    for _, r in exp03_selected_df.iterrows():
        algo = str(r["algorithm"])
        exp01_row = None
        if not exp01_summary_csv.empty:
            mask = exp01_summary_csv["algorithm"] == algo
            if mask.any():
                exp01_row = exp01_summary_csv.loc[mask].iloc[0]
        rows.append(
            EXP03ComparisonRow(
                algorithm=algo,
                exp01_decision_status=(
                    str(exp01_row.get("status", "SUCCESS"))
                    if exp01_row is not None
                    else "MISSING"
                ),
                exp01_n_clusters=(
                    int(exp01_row["n_clusters"])
                    if exp01_row is not None
                    and "n_clusters" in exp01_row.index
                    and pd.notna(exp01_row.get("n_clusters"))
                    else None
                ),
                exp01_silhouette=(
                    float(exp01_row["silhouette"])
                    if exp01_row is not None
                    and "silhouette" in exp01_row.index
                    and pd.notna(exp01_row.get("silhouette"))
                    else None
                ),
                exp01_davies_bouldin=(
                    float(exp01_row["davies_bouldin"])
                    if exp01_row is not None
                    and "davies_bouldin" in exp01_row.index
                    and pd.notna(exp01_row.get("davies_bouldin"))
                    else None
                ),
                exp01_calinski_harabasz=(
                    float(exp01_row["calinski_harabasz"])
                    if exp01_row is not None
                    and "calinski_harabasz" in exp01_row.index
                    and pd.notna(exp01_row.get("calinski_harabasz"))
                    else None
                ),
                exp01_wcss=(
                    float(exp01_row["wcss"])
                    if exp01_row is not None
                    and "wcss" in exp01_row.index
                    and pd.notna(exp01_row.get("wcss"))
                    else None
                ),
                exp03_decision_status=str(r.get("decision_status", "MISSING")),
                exp03_experiment_id=str(r.get("experiment_id", "MISSING")),
                exp03_stage=str(r.get("stage", "MISSING")),
                exp03_hyperparameters=str(r.get("hyperparameters", "{}")),
                exp03_n_clusters=(
                    int(r["n_clusters"])
                    if "n_clusters" in r.index and pd.notna(r.get("n_clusters"))
                    else None
                ),
                exp03_silhouette=(
                    float(r["silhouette"])
                    if "silhouette" in r.index and pd.notna(r.get("silhouette"))
                    else None
                ),
                exp03_davies_bouldin=(
                    float(r["davies_bouldin"])
                    if "davies_bouldin" in r.index and pd.notna(r.get("davies_bouldin"))
                    else None
                ),
                exp03_calinski_harabasz=(
                    float(r["calinski_harabasz"])
                    if "calinski_harabasz" in r.index and pd.notna(r.get("calinski_harabasz"))
                    else None
                ),
                exp03_wcss=(
                    float(r["wcss"])
                    if "wcss" in r.index and pd.notna(r.get("wcss"))
                    else None
                ),
                exp03_sweep_parameter=str(r.get("sweep_parameter") or "MISSING"),
                exp03_sweep_value=(
                    "MISSING"
                    if pd.isna(r.get("sweep_value"))
                    else str(r.get("sweep_value"))
                ),
                exp03_baseline_k=(
                    int(r["baseline_k"])
                    if "baseline_k" in r.index and pd.notna(r.get("baseline_k"))
                    else None
                ),
                exp03_primary_criterion=str(r.get("primary_criterion", "MISSING")),
                exp03_selection_evidence_note=str(r.get("selection_evidence_note", "")),
                source_evidence="METRIC_BASED_ONLY",
            )
        )
        evidence_summary[algo] = (
            "METRIC_BASED_ONLY: silhouette/DBI/CH/WCSS reported; no "
            "label-level comparison (EXP-03 working-selected labels "
            "are not in any persisted artifact)."
        )

    df = pd.DataFrame([r.__dict__ for r in rows])
    decision_status = {row.algorithm: DECISION_STATUS for row in rows}
    return {
        "per_algorithm": df,
        "decision_status": decision_status,
        "limitations": limitations,
        "evidence_summary": evidence_summary,
    }
