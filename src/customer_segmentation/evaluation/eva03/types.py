"""Internal type definitions for EVA-03.

These dataclasses are the in-memory data structures that flow
between the EVA-03 submodules. They are intentionally
internal — public callers should use :class:`Eva03Runner` rather
than constructing these directly.

Hard constraints (AGENTS.md §2 / EVA-03 PENDING_REVIEW notes):

- No composite stability score field.
- No "best" / "winner" / "winner algorithm" field.
- Decision_status fields use the permitted taxonomy only.
- All row types carry traceability back to source experiment / run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Forward imports kept minimal to avoid circular dependencies at import time.


@dataclass(frozen=True)
class BlockRPairwiseRow:
    """One pairwise comparison between two Block R repeats."""

    algorithm: str
    run_id_a: str
    run_id_b: str
    repeat_index_a: int
    repeat_index_b: int
    ari: float
    ami: float
    nmi: float
    n_customers: int


@dataclass(frozen=True)
class PairwiseMatrix:
    """Symmetric pairwise similarity matrix for one (algorithm, block)."""

    algorithm: str
    run_ids: tuple[str, ...]
    ari: list[list[float]]
    ami: list[list[float]]
    nmi: list[list[float]]
    # Number of distinct off-diagonal values (a coarse uniqueness score).
    off_diagonal_unique_count: int


@dataclass(frozen=True)
class EXP01ReferenceRow:
    """One EXP-01 reference (cluster labels per CustomerID, last repetition)."""

    algorithm: str
    customer_ids: list[int]
    cluster_labels: list[int]
    noise_mask: list[bool]


@dataclass(frozen=True)
class EXP03ComparisonRow:
    """Descriptive EXP-01 vs EXP-03 working-selected comparison per algorithm."""

    algorithm: str
    # EXP-01 default (working defaults, K=4 baseline)
    exp01_decision_status: str
    exp01_n_clusters: int | None
    exp01_silhouette: float | None
    exp01_davies_bouldin: float | None
    exp01_calinski_harabasz: float | None
    exp01_wcss: float | None
    # EXP-03 working-selected
    exp03_decision_status: str
    exp03_experiment_id: str
    exp03_stage: str
    exp03_hyperparameters: str
    exp03_n_clusters: int | None
    exp03_silhouette: float | None
    exp03_davies_bouldin: float | None
    exp03_calinski_harabasz: float | None
    exp03_wcss: float | None
    exp03_sweep_parameter: str
    exp03_sweep_value: str
    exp03_baseline_k: int | None
    exp03_primary_criterion: str
    exp03_selection_evidence_note: str
    # Source evidence classification
    source_evidence: str = "METRIC_BASED_ONLY"


@dataclass
class ClusterSizeRow:
    """One per-cluster customer-count row for cluster size variation analysis."""

    block: str
    algorithm: str
    seed: int | None
    sigma: float | None
    perturbation_seed: int | None
    repeat_index: int
    run_id: str
    cluster_id: str
    customer_count: int


@dataclass
class HungarianAssignment:
    """One cluster-label alignment result across two runs."""

    algorithm: str
    run_id_a: str
    run_id_b: str
    # Both arrays are in matching index order: source_label[i] -> target_label[i]
    source_labels: list[int]
    target_labels: list[int]
    overlap_counts: list[int]
    total_customers: int
    # NOTE: Hungarian matching is DESCRIPTIVE only — no stability score derived.
