"""Validation and anomaly detection for the EVA-01 repository.

This module categorises every row into one of five buckets:

- ``OK`` — row passes all checks.
- ``MISSING`` — required field is missing without a documented
  ``missing_reason``. The repository distinguishes this from the
  sentinel value ``MISSING`` used to mark "not applicable" fields.
- ``INVALID`` — metric value is NaN, run_status is FAILED but
  metrics are non-null, etc.
- ``DUPLICATE_EXACT`` — two rows are byte-identical on a fixed
  identity key.
- ``DUPLICATE_BY_INTENT`` — two rows have the same configuration
  (algorithm, K, preprocessing, hyperparameters, seed) but
  different metric values or different labels_hash. These are
  duplicates **by experimental intent** that produced different
  outputs.
- ``INCONSISTENT_CONDITIONS`` — the same configuration was run
  under different feature sets, different preprocessing, or
  different dataset versions. These are NOT errors per se; they
  are evidence that two experiments shared a configuration but
  varied one of the controlled variables. The repository flags
  them for human review.

Scope
-----

EVA-01 explicitly does **NOT**:

- Invent missing values.
- Re-run any clustering.
- Drop rows from the repository. Flagged rows are tagged in the
  validation report but kept in the canonical dataset so the
  human researcher can decide what to do.

The categories are mutually exclusive at the row level (a row has
exactly one validation status). At the **pair** level, two rows
may trigger one or more cross-row flags (duplicate / inconsistent
conditions).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import StrEnum
from typing import Any

import pandas as pd

from customer_segmentation.evaluation.experiment_results.schema import (
    MINIMAL_REQUIRED_FIELDS,
    MISSING,
    MISSING_INT_REASON_FIELDS,
    MISSING_REASON_DEFERRED,
    MISSING_REASON_DIFFERENT_CONDITIONS,
    MISSING_REASON_FIELD_NOT_IN_SOURCE,
    MISSING_REASON_NOT_APPLICABLE,
    MISSING_REASON_NOT_RECORDED,
    REQUIRED_FIELDS,
    STANDARD_COLUMNS,
)

__all__ = [
    "RowStatus",
    "AnomalyCategory",
    "RowValidation",
    "ValidationReport",
    "validate_repository",
    "_make_canonical_identity_key",
    "_check_duplicate_intent",
    "_check_inconsistent_conditions",
]


class RowStatus(StrEnum):
    """Status of a single row against the schema."""

    OK = "OK"
    MISSING = "MISSING"
    INVALID = "INVALID"


class AnomalyCategory(StrEnum):
    """Categories of cross-row anomalies."""

    DUPLICATE_EXACT = "DUPLICATE_EXACT"
    DUPLICATE_BY_INTENT = "DUPLICATE_BY_INTENT"
    INCONSISTENT_CONDITIONS = "INCONSISTENT_CONDITIONS"


# Identity key used to detect exact duplicates (one row == another row).
# Includes all the values that together fully describe the run.
_DUPLICATE_KEY_FIELDS: tuple[str, ...] = (
    "source_experiment",
    "source_run_id",
    "repeat_index",
    "experiment_id",
    "algorithm",
    "n_clusters",
    "random_seed",
    "transformation",
    "scaling",
    "imputation",
    "feature_set",
    "dataset_version",
    "hyperparameters",
    "sigma",
    "perturbation_seed",
)


# Intent key — excludes provenance-only fields. Two rows with the same
# intent key but different metric values are DUPLICATE_BY_INTENT.
_INTENT_KEY_FIELDS: tuple[str, ...] = (
    "source_experiment",
    "algorithm",
    "n_clusters",
    "random_seed",
    "transformation",
    "scaling",
    "imputation",
    "feature_set",
    "dataset_version",
    "hyperparameters",
    "sigma",
    "perturbation_seed",
)


# Fields whose differences trigger INCONSISTENT_CONDITIONS (not
# duplicate-by-intent). Two rows are inconsistent when their
# (algorithm, n_clusters, hyperparameters, random_seed) match but
# feature_set / dataset_version / preprocessing differ.
_INCONSISTENT_KEY_FIELDS: tuple[str, ...] = (
    "algorithm",
    "n_clusters",
    "random_seed",
    "hyperparameters",
)


@dataclass
class RowValidation:
    """Per-row validation outcome."""

    source_experiment: str
    experiment_id: str
    source_run_id: str
    status: RowStatus
    missing_fields: list[str] = dc_field(default_factory=list)
    invalid_fields: list[str] = dc_field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_experiment": self.source_experiment,
            "experiment_id": self.experiment_id,
            "source_run_id": self.source_run_id,
            "status": self.status.value,
            "missing_fields": list(self.missing_fields),
            "invalid_fields": list(self.invalid_fields),
        }


@dataclass
class ValidationReport:
    """Top-level EVA-01 validation report."""

    row_validations: list[RowValidation]
    n_ok: int
    n_missing: int
    n_invalid: int
    n_total: int
    duplicate_exact: list[dict[str, Any]]  # {key, run_ids: [...]}
    duplicate_by_intent: list[dict[str, Any]]
    inconsistent_conditions: list[dict[str, Any]]
    field_coverage: dict[
        str, dict[str, int]
    ]  # field -> {"present": N, "missing_with_reason": N, "missing_no_reason": N}

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_total": self.n_total,
            "n_ok": self.n_ok,
            "n_missing": self.n_missing,
            "n_invalid": self.n_invalid,
            "duplicate_exact": self.duplicate_exact,
            "duplicate_by_intent": self.duplicate_by_intent,
            "inconsistent_conditions": self.inconsistent_conditions,
            "field_coverage": self.field_coverage,
            "rows": [r.to_dict() for r in self.row_validations],
        }


def _is_missing_sentinel(value: Any) -> bool:
    """Return True if the value is the literal ``MISSING`` sentinel."""
    return value == MISSING


def _is_nan_value(value: Any) -> bool:
    """Return True if the value is a numeric NaN."""
    try:
        return bool(pd.isna(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _is_missing_field(field: str, value: Any, row: dict[str, Any]) -> tuple[bool, str]:
    """Return ``(is_missing, reason_or_empty)``.

    ``is_missing`` is True if:

    - The value is the literal ``MISSING`` sentinel, OR
    - The value is NaN / None, OR
    - The value is missing-from-source (e.g. string empty after coercion).

    The reason is the ``<field>_missing_reason`` annotation, or empty
    if the field is not ``MISSING``.
    """
    if _is_missing_sentinel(value):
        reason_field = f"{field}_missing_reason"
        reason = row.get(reason_field, MISSING)
        if isinstance(reason, str) and reason and reason != MISSING:
            return True, reason
        return True, MISSING_REASON_NOT_RECORDED
    if _is_nan_value(value):
        reason_field = f"{field}_missing_reason"
        reason = row.get(reason_field, MISSING)
        if isinstance(reason, str) and reason and reason != MISSING:
            return True, reason
        return True, MISSING_REASON_NOT_RECORDED
    return False, ""


def _validate_row(row: dict[str, Any]) -> RowValidation:
    """Validate a single row against the schema.

    Returns a :class:`RowValidation` with status OK / MISSING / INVALID.
    """
    missing_fields: list[str] = []
    invalid_fields: list[str] = []

    # --- Check minimal_required_fields (cannot be MISSING) ---
    for field in MINIMAL_REQUIRED_FIELDS:
        v = row.get(field)
        if v is None or _is_nan_value(v) or _is_missing_sentinel(v):
            missing_fields.append(field)

    # --- Check REQUIRED_FIELDS (cannot be MISSING) ---
    for field in REQUIRED_FIELDS:
        is_missing, _reason = _is_missing_field(field, row.get(field), row)
        if is_missing:
            missing_fields.append(field)

    # --- Check that ``MISSING`` integer fields carry a reason ---
    # Allowed reasons are the four "by design" sentinels. ``NOT_RECORDED`` is
    # treated as a legitimate gap and raises MISSING for the row.
    allowed_missing_reasons: frozenset[str] = frozenset(
        {
            MISSING_REASON_NOT_APPLICABLE,
            MISSING_REASON_DIFFERENT_CONDITIONS,
            MISSING_REASON_FIELD_NOT_IN_SOURCE,
            MISSING_REASON_DEFERRED,
        }
    )
    for field_name in MISSING_INT_REASON_FIELDS:
        v = row.get(field_name)
        is_missing, _ = _is_missing_field(field_name, v, row)
        if not is_missing:
            continue
        reason = row.get(f"{field_name}_missing_reason")
        # Flag as missing if no valid documented reason is provided.
        # Valid reasons: "" (field has a value), NOT_APPLICABLE, DIFFERENT_CONDITIONS,
        # FIELD_NOT_IN_SOURCE, DEFERRED.
        # Invalid: None, "", MISSING sentinel, NOT_RECORDED, or unknown string.
        if (  # noqa: SIM109 — simplification would incorrectly flag valid reasons
            reason is None  # noqa: SIM109            or reason == ""
            or reason == MISSING
            or reason == MISSING_REASON_NOT_RECORDED
            or reason not in allowed_missing_reasons
        ):
            missing_fields.append(field_name)

    # --- Check INVALID rules ---
    # Rule 1: numeric metric fields must not be NaN if silhouette_status
    # is VALID_VALUE.
    for field in (
        "silhouette",
        "davies_bouldin",
        "calinski_harabasz",
        "wcss",
        "execution_time_seconds",
        "noise_ratio",
    ):
        v = row.get(field)
        status_v = row.get(f"{field}_status", "")
        is_missing, _ = _is_missing_field(field, v, row)
        if is_missing:
            continue
        if _is_nan_value(v):
            invalid_fields.append(field)
            continue
        # Status says VALID_VALUE but value is None / not a number.
        if status_v == "VALID_VALUE" and v is None:
            invalid_fields.append(field)

    # Rule 2: run_status FAILED implies metric values should be missing.
    run_status = row.get("run_status", "SUCCESS")
    if run_status == "FAILED":
        for field in (
            "silhouette",
            "davies_bouldin",
            "calinski_harabasz",
            "wcss",
        ):
            v = row.get(field)
            is_missing, _ = _is_missing_field(field, v, row)
            if not is_missing:
                invalid_fields.append(f"{field}_non_null_for_failed_run")

    # --- Determine status ---
    if not missing_fields and not invalid_fields:
        status = RowStatus.OK
    elif invalid_fields:
        status = RowStatus.INVALID
    else:
        status = RowStatus.MISSING

    return RowValidation(
        source_experiment=str(row.get("source_experiment", MISSING)),
        experiment_id=str(row.get("experiment_id", MISSING)),
        source_run_id=str(row.get("source_run_id", MISSING)),
        status=status,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
    )


def _make_canonical_identity_key(row: dict[str, Any]) -> str:
    """Build a canonical string identity key for duplicate detection."""
    parts: list[str] = []
    for key_field in _DUPLICATE_KEY_FIELDS:
        v = row.get(key_field, MISSING)
        if v is None:
            v = MISSING
        parts.append(f"{key_field}={v}")
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _make_intent_key(row: dict[str, Any]) -> str:
    """Build a configuration-intent key (excludes provenance)."""
    parts: list[str] = []
    for key_field in _INTENT_KEY_FIELDS:
        v = row.get(key_field, MISSING)
        if v is None:
            v = MISSING
        parts.append(f"{key_field}={v}")
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _make_inconsistent_key(row: dict[str, Any]) -> str:
    """Build a key for INCONSISTENT_CONDITIONS detection.

    Same as intent key but ONLY considers (algorithm, n_clusters,
    hyperparameters, random_seed). Two rows that share this key
    but differ on (feature_set, dataset_version, transformation,
    scaling, imputation, sigma, perturbation_seed) are flagged
    as INCONSISTENT_CONDITIONS.
    """
    parts: list[str] = []
    for key_field in _INCONSISTENT_KEY_FIELDS:
        v = row.get(key_field, MISSING)
        if v is None:
            v = MISSING
        parts.append(f"{key_field}={v}")
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _check_duplicate_exact(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect rows that are byte-identical on the duplicate key."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = _make_canonical_identity_key(r)
        buckets.setdefault(key, []).append(r)

    duplicates = []
    for key, group in buckets.items():
        if len(group) > 1:
            duplicates.append(
                {
                    "identity_key": key,
                    "n_rows": len(group),
                    "run_ids": [
                        {
                            "source_experiment": str(r.get("source_experiment", MISSING)),
                            "experiment_id": str(r.get("experiment_id", MISSING)),
                            "source_run_id": str(r.get("source_run_id", MISSING)),
                        }
                        for r in group
                    ],
                }
            )
    return duplicates


def _check_duplicate_intent(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect rows with the same configuration intent but different outputs."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = _make_intent_key(r)
        buckets.setdefault(key, []).append(r)

    duplicates = []
    for key, group in buckets.items():
        if len(group) < 2:
            continue
        # Compare metric values and labels_hash. If any differs, this is
        # a duplicate-by-intent (same config, different output).
        first = group[0]
        differing_fields: list[str] = []
        differing_run_ids: list[dict[str, str]] = []
        for other in group[1:]:
            for metric in (
                "silhouette",
                "davies_bouldin",
                "calinski_harabasz",
                "wcss",
                "labels_hash",
                "execution_time_seconds",
                "n_clusters_realized",
            ):
                if first.get(metric) != other.get(metric):
                    differing_fields.append(metric)
            differing_run_ids.append(
                {
                    "source_experiment": str(other.get("source_experiment", MISSING)),
                    "experiment_id": str(other.get("experiment_id", MISSING)),
                    "source_run_id": str(other.get("source_run_id", MISSING)),
                }
            )
        if differing_fields:
            duplicates.append(
                {
                    "intent_key": key,
                    "n_rows": len(group),
                    "differing_fields": sorted(set(differing_fields)),
                    "run_ids": [
                        {
                            "source_experiment": str(r.get("source_experiment", MISSING)),
                            "experiment_id": str(r.get("experiment_id", MISSING)),
                            "source_run_id": str(r.get("source_run_id", MISSING)),
                        }
                        for r in group
                    ],
                }
            )
    return duplicates


def _check_inconsistent_conditions(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect rows that share (algorithm, K, HP, seed) but differ in conditions."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = _make_inconsistent_key(r)
        buckets.setdefault(key, []).append(r)

    anomalies = []
    for key, group in buckets.items():
        if len(group) < 2:
            continue
        # Collect the unique values of condition fields across the group.
        condition_summary: dict[str, set[str]] = {
            "feature_set": set(),
            "dataset_version": set(),
            "transformation": set(),
            "scaling": set(),
            "imputation": set(),
            "sigma": set(),
            "perturbation_seed": set(),
        }
        for r in group:
            for cond_field in condition_summary:
                v = r.get(cond_field, MISSING)
                if v is None:
                    v = MISSING
                condition_summary[cond_field].add(str(v))
        # A row is INCONSISTENT only if at least one condition field has
        # more than one distinct value across the group.
        differing_fields = [fld for fld, values in condition_summary.items() if len(values) > 1]
        if differing_fields:
            anomalies.append(
                {
                    "inconsistent_key": key,
                    "n_rows": len(group),
                    "differing_condition_fields": differing_fields,
                    "condition_values": {k: sorted(v) for k, v in condition_summary.items()},
                    "run_ids": [
                        {
                            "source_experiment": str(r.get("source_experiment", MISSING)),
                            "experiment_id": str(r.get("experiment_id", MISSING)),
                            "source_run_id": str(r.get("source_run_id", MISSING)),
                            "feature_set": str(r.get("feature_set", MISSING)),
                            "dataset_version": str(r.get("dataset_version", MISSING)),
                            "transformation": str(r.get("transformation", MISSING)),
                            "scaling": str(r.get("scaling", MISSING)),
                            "imputation": str(r.get("imputation", MISSING)),
                        }
                        for r in group
                    ],
                }
            )
    return anomalies


def _compute_field_coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Compute per-field coverage statistics.

    For each field, count:
    - ``present``: how many rows have a real (non-MISSING, non-NaN) value
    - ``missing_with_reason``: how many rows are MISSING with a documented reason
    - ``missing_no_reason``: how many rows are MISSING without a reason
    """
    coverage: dict[str, dict[str, int]] = {}
    for col in STANDARD_COLUMNS:
        present = 0
        missing_with_reason = 0
        missing_no_reason = 0
        for r in rows:
            v = r.get(col, MISSING)
            if _is_missing_sentinel(v) or _is_nan_value(v) or v is None:
                reason = r.get(f"{col}_missing_reason")
                if reason and isinstance(reason, str) and reason != MISSING and reason != "":
                    missing_with_reason += 1
                else:
                    missing_no_reason += 1
            else:
                present += 1
        coverage[col] = {
            "present": present,
            "missing_with_reason": missing_with_reason,
            "missing_no_reason": missing_no_reason,
        }
    return coverage


def validate_repository(rows: list[dict[str, Any]]) -> ValidationReport:
    """Validate a list of normalized rows.

    Returns a :class:`ValidationReport` containing:

    - Per-row validation outcomes (``MISSING``, ``INVALID``, ``OK``).
    - Cross-row duplicate detection (``DUPLICATE_EXACT`` and
      ``DUPLICATE_BY_INTENT``).
    - Cross-row condition-inconsistency detection
      (``INCONSISTENT_CONDITIONS``).
    - Per-field coverage statistics.
    """
    row_validations = [_validate_row(r) for r in rows]
    n_ok = sum(1 for v in row_validations if v.status == RowStatus.OK)
    n_missing = sum(1 for v in row_validations if v.status == RowStatus.MISSING)
    n_invalid = sum(1 for v in row_validations if v.status == RowStatus.INVALID)

    duplicates_exact = _check_duplicate_exact(rows)
    duplicates_intent = _check_duplicate_intent(rows)
    inconsistencies = _check_inconsistent_conditions(rows)
    coverage = _compute_field_coverage(rows)

    return ValidationReport(
        row_validations=row_validations,
        n_ok=n_ok,
        n_missing=n_missing,
        n_invalid=n_invalid,
        n_total=len(rows),
        duplicate_exact=duplicates_exact,
        duplicate_by_intent=duplicates_intent,
        inconsistent_conditions=inconsistencies,
        field_coverage=coverage,
    )


# ---------------------------------------------------------------------------
# JSON encoder for ValidationReport (numpy / pandas safe)
# ---------------------------------------------------------------------------


def _to_json_safe(obj: Any) -> Any:
    """Convert numpy / pandas scalars to JSON-friendly types."""
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    try:
        if obj is pd.NA:
            return None
    except NameError:
        pass
    return obj


def validation_report_to_json(report: ValidationReport) -> str:
    """Serialise a :class:`ValidationReport` to JSON-friendly string."""
    return json.dumps(_to_json_safe(report.to_dict()), ensure_ascii=False, indent=2)
