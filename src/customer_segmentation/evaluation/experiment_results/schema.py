"""Standardized schema for the EVA-01 Experiment Result Repository.

This module defines the column schema that every row in the unified
repository MUST satisfy. It is the single source of truth for column
names, types, and semantics.

Design rationale
----------------

The EPIC-07 experiments (EXP-01 .. EXP-05) were written by
separate scripts, so their CSVs / JSONs have different columns,
naming conventions, and granularity. To make a unified table we
need a fixed schema. The schema in this module is the result of
mapping every EPIC-07 source field onto a single canonical column.

Granularity choice
------------------

EVA-01 uses **per-run** granularity (one row = one clustering run),
not per-experiment or per-configuration:

- EXP-01 / EXP-02 / EXP-03 use ``n_repeat=5`` for runtime statistics
  only; per-run rows are emitted with ``repeat_index=0`` (the run is
  already summary-aggregated) and the per-run metric values come
  from the per-algorithm summary CSV (silhouette/DBI/CH/WCSS are
  identical across repeats for fixed-seed deterministic algorithms).
- EXP-04 and EXP-05 already store per-run rows in their CSVs; each
  repeat is materialised as its own row in the unified repository.

Semantic conventions
--------------------

- ``MISSING`` is a literal string used to mark a value that is
  not applicable to a particular (algorithm, experiment) pair
  (NOT a value that "was not recorded"). For example, K is missing
  for DBSCAN; transformation is missing for EXP-01 because EXP-01
  operates on the already-prepared ``final_clustering_dataset.parquet``.
  The string ``MISSING`` is paired with ``missing_reason`` so a
  reader can distinguish between ``NA`` by design and ``NA`` due
  to a recording gap.
- Boolean fields use ``True`` / ``False`` (Python bool).
- SHA-256 fields are 64-character lowercase hex strings, or
  ``MISSING`` when not recorded.
- Timestamp fields are ISO-8601 strings (e.g. ``"2026-09-22T00:00:00+00:00"``).
- Integer-like numerics are cast to ``Int64`` (nullable) when
  sourced from CSV; some DBSCAN fields are nullable.

Forbidden language
------------------

No field in this schema uses ``"best"``, ``"winner"``, ``"optimal"``,
``"recommended"``, ``"final"``, ``"superior"``. The schema is
intentionally descriptive, not evaluative.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "SourceExperiment",
    "MISSING",
    "MISSING_REASON_NOT_APPLICABLE",
    "MISSING_REASON_NOT_RECORDED",
    "MISSING_REASON_DIFFERENT_CONDITIONS",
    "MISSING_REASON_FIELD_NOT_IN_SOURCE",
    "MISSING_REASON_DEFERRED",
    "STANDARD_COLUMNS",
    "REQUIRED_FIELDS",
    "MINIMAL_REQUIRED_FIELDS",
    "FIELD_TYPES",
    "MISSING_INT_REASON_FIELDS",
    "NULLABLE_INT_FIELDS",
    "NULLABLE_FLOAT_FIELDS",
]


class SourceExperiment(StrEnum):
    """Source EPIC-07 experiment identifier.

    Each EVA-01 row MUST carry exactly one of these values in the
    ``source_experiment`` column. They form the provenance tag that
    ties every row back to a specific EPIC-07 artifact.
    """

    EXP_01 = "EXP-01"
    EXP_02 = "EXP-02"
    EXP_03 = "EXP-03"
    EXP_04 = "EXP-04"
    EXP_05 = "EXP-05"


# ---------------------------------------------------------------------------
# Missing-value conventions
# ---------------------------------------------------------------------------

# Literal sentinel used for fields that are not applicable to a particular
# row. NEVER invent a value; if the source did not record it, leave it as
# ``MISSING`` and provide a ``missing_reason``.
MISSING: str = "MISSING"

# Reasons that justify a ``MISSING`` value. The repository distinguishes
# four cases so a downstream consumer can tell apart "by design" vs.
# "data gap" without guessing.
MISSING_REASON_NOT_APPLICABLE: str = "NOT_APPLICABLE"  # The field has no meaning for this row
MISSING_REASON_NOT_RECORDED: str = "NOT_RECORDED"  # The source did not record the value
MISSING_REASON_DIFFERENT_CONDITIONS: str = (
    "DIFFERENT_CONDITIONS"  # Source was a different preprocessing / family
)
MISSING_REASON_FIELD_NOT_IN_SOURCE: str = (
    "FIELD_NOT_IN_SOURCE"  # The source CSV/JSON did not include this column
)
MISSING_REASON_DEFERRED: str = "DEFERRED"  # Family A EXP-04 / RFM-only / future work


# ---------------------------------------------------------------------------
# Column schema
# ---------------------------------------------------------------------------


# Complete list of columns in the unified repository. Order is chosen for
# readability: identifiers → configuration → metrics → provenance.
STANDARD_COLUMNS: tuple[str, ...] = (
    # ---- Identity / provenance (required) ----
    "source_experiment",  # SourceExperiment value
    "experiment_id",  # Stable identifier for the (experiment, run)
    "source_block",  # For EXP-05: "R" / "S" / "N"; "" otherwise
    "source_run_id",  # EXP-05 run_id; otherwise a constructed id
    "record_granularity",  # "PER_RUN" or "PER_AGGREGATE"
    "repeat_index",  # 0..n_repeat-1
    "n_repeats_total",  # Total repeats for the same configuration
    # ---- Required minimum fields per task brief ----
    "algorithm",
    "dataset_version",
    "feature_set",
    "transformation",
    "scaling",
    "imputation",
    "n_clusters",  # Realized n_clusters (matches K for K-bearing algos)
    "hyperparameters",  # Serialised JSON string of the HP dict
    "random_seed",  # ``MISSING`` if deterministic / not applicable
    "silhouette",
    "davies_bouldin",
    "calinski_harabasz",
    "wcss",
    "execution_time_seconds",
    "n_clusters_realized",  # Mirrors n_clusters; kept for backward compat with EXP-05
    "cluster_size_largest",  # Largest single-cluster customer count
    "cluster_size_smallest",  # Smallest single-cluster customer count
    "noise_count",
    "noise_ratio",
    # ---- Metric status / applicability ----
    "silhouette_status",
    "davies_bouldin_status",
    "calinski_harabasz_status",
    "wcss_status",
    # ---- Missing-reason annotations (one per nullable field) ----
    # Format: ``{field}_missing_reason``; value is one of MISSING_REASON_*.
    # Only populated for fields where the value is "MISSING".
    "algorithm_missing_reason",
    "dataset_version_missing_reason",
    "feature_set_missing_reason",
    "transformation_missing_reason",
    "scaling_missing_reason",
    "imputation_missing_reason",
    "n_clusters_missing_reason",
    "hyperparameters_missing_reason",
    "random_seed_missing_reason",
    "silhouette_missing_reason",
    "davies_bouldin_missing_reason",
    "calinski_harabasz_missing_reason",
    "wcss_missing_reason",
    "execution_time_seconds_missing_reason",
    "n_clusters_realized_missing_reason",
    "cluster_size_largest_missing_reason",
    "cluster_size_smallest_missing_reason",
    "noise_count_missing_reason",
    "noise_ratio_missing_reason",
    "repeat_index_missing_reason",
    "n_repeats_total_missing_reason",
    "sigma_missing_reason",
    "perturbation_seed_missing_reason",
    # ---- Provenance / reproducibility (optional) ----
    "run_status",  # "SUCCESS" / "FAILED"
    "failure_reason",
    "labels_hash",  # SHA-256 of cluster_labels vector (per-run)
    "feature_set_sha256",
    "customer_metadata_sha256",
    "config_sha256",
    "input_sha256",
    "sigma",  # EXP-05 Block N
    "perturbation_seed",  # EXP-05 Block N
    "library_versions",  # Serialised JSON
    "platform",  # Serialised JSON
    "timestamp",  # ISO-8601 string
    "source_artifact",  # Path to the source CSV/JSON file (relative)
    # ---- Decision status (per-experiment schema) ----
    "decision_status",
    "evidence_note",
)


# The minimum required fields per the task brief. If any of these is
# missing the row is INVALID (or partially invalid if the missing field
# has a documented ``missing_reason``).
REQUIRED_FIELDS: tuple[str, ...] = (
    "source_experiment",
    "experiment_id",
    "algorithm",
    "dataset_version",
    "feature_set",
    "n_clusters",
    "silhouette",
    "davies_bouldin",
    "calinski_harabasz",
    "wcss",
    "execution_time_seconds",
)


# A *truly* minimal subset that MUST never be ``MISSING`` (an aggregator
# cannot meaningfully join / dedup without these). These are checked
# before MISSING-reason exemptions are honoured.
MINIMAL_REQUIRED_FIELDS: tuple[str, ...] = (
    "source_experiment",
    "experiment_id",
    "algorithm",
)


# Loose dtype mapping used by the validator. The string values are
# pandas-friendly type names. The actual cast happens in collectors.
FIELD_TYPES: dict[str, str] = {
    # Identity
    "source_experiment": "str",
    "experiment_id": "str",
    "source_block": "str",
    "source_run_id": "str",
    "record_granularity": "str",
    "repeat_index": "Int64",
    "n_repeats_total": "Int64",
    # Required minimum
    "algorithm": "str",
    "dataset_version": "str",
    "feature_set": "str",
    "transformation": "str",
    "scaling": "str",
    "imputation": "str",
    "n_clusters": "Int64",
    "hyperparameters": "str",  # JSON-serialised
    "random_seed": "Int64",
    "silhouette": "Float64",
    "davies_bouldin": "Float64",
    "calinski_harabasz": "Float64",
    "wcss": "Float64",
    "execution_time_seconds": "Float64",
    "n_clusters_realized": "Int64",
    "cluster_size_largest": "Int64",
    "cluster_size_smallest": "Int64",
    "noise_count": "Int64",
    "noise_ratio": "Float64",
    # Status
    "silhouette_status": "str",
    "davies_bouldin_status": "str",
    "calinski_harabasz_status": "str",
    "wcss_status": "str",
    # Missing reasons
    "algorithm_missing_reason": "str",
    "dataset_version_missing_reason": "str",
    "feature_set_missing_reason": "str",
    "transformation_missing_reason": "str",
    "scaling_missing_reason": "str",
    "imputation_missing_reason": "str",
    "n_clusters_missing_reason": "str",
    "hyperparameters_missing_reason": "str",
    "random_seed_missing_reason": "str",
    "silhouette_missing_reason": "str",
    "davies_bouldin_missing_reason": "str",
    "calinski_harabasz_missing_reason": "str",
    "wcss_missing_reason": "str",
    "execution_time_seconds_missing_reason": "str",
    "n_clusters_realized_missing_reason": "str",
    "cluster_size_largest_missing_reason": "str",
    "cluster_size_smallest_missing_reason": "str",
    "noise_count_missing_reason": "str",
    "noise_ratio_missing_reason": "str",
    "repeat_index_missing_reason": "str",
    "n_repeats_total_missing_reason": "str",
    "sigma_missing_reason": "str",
    "perturbation_seed_missing_reason": "str",
    # Provenance
    "run_status": "str",
    "failure_reason": "str",
    "labels_hash": "str",
    "feature_set_sha256": "str",
    "customer_metadata_sha256": "str",
    "config_sha256": "str",
    "input_sha256": "str",
    "sigma": "Float64",
    "perturbation_seed": "Int64",
    "library_versions": "str",  # JSON-serialised
    "platform": "str",  # JSON-serialised
    "timestamp": "str",
    "source_artifact": "str",
    "decision_status": "str",
    "evidence_note": "str",
}


# Integer-typed fields where ``MISSING`` is acceptable but requires an
# accompanying ``<field>_missing_reason`` annotation. The validator
# enforces this.
MISSING_INT_REASON_FIELDS: tuple[str, ...] = (
    "n_clusters",
    "random_seed",
    "n_clusters_realized",
    "cluster_size_largest",
    "cluster_size_smallest",
    "noise_count",
    "repeat_index",
    "n_repeats_total",
    "perturbation_seed",
)


NULLABLE_INT_FIELDS: tuple[str, ...] = MISSING_INT_REASON_FIELDS

NULLABLE_FLOAT_FIELDS: tuple[str, ...] = (
    "silhouette",
    "davies_bouldin",
    "calinski_harabasz",
    "wcss",
    "execution_time_seconds",
    "noise_ratio",
    "sigma",
)


# Decision statuses used by EPIC-07. Listed here for the validator;
# these are taken verbatim from the EPIC-07 manifests. The repository
# does NOT add or remove statuses.
ALLOWED_DECISION_STATUSES: frozenset[str] = frozenset(
    {
        # EXP-01 / EXP-02 / EXP-03
        "SUCCESS",
        "FAILED",
        # EXP-04
        "CANDIDATE_SCENARIO",
        "TIED_SCENARIOS",
        "PENDING_REVIEW",
        "DEFERRED",
        # EXP-05
        "REPRODUCIBILITY_VERIFIED",
        "REPRODUCIBILITY_FAILED",
        "STABILITY_EVIDENCE_GENERATED",
        "PERTURBATION_EVIDENCE_GENERATED",
        "SIGMA_ZERO_BASELINE_MATCH",
        "SIGMA_ZERO_BASELINE_MISMATCH",
        # Generic
        "NOT_RECORDED",
    }
)


# Forbidden decision-status labels per AGENTS.md §2.5 / EXP-04 / EXP-05.
FORBIDDEN_DECISION_LABELS: frozenset[str] = frozenset(
    {"BEST", "OPTIMAL", "WINNER", "SUPERIOR", "RECOMMENDED", "FINAL"}
)
