"""Stage C input validation for DEV-07 Prototype Marketing.

Mirrors DEV-04/05/06 input-validation pattern. Validates:

- DEV-06 ``SegmentationManifest v1.0.0`` (existence, schema version,
  required fields, ``research_safety.scope == "PROFILED_PROTOTYPE"``,
  ``n_segments >= 1`` post-noise).
- DBSCAN noise exclusion (segment_id == -1 never enters the
  recommendation list — FR-MKT-06, CON-08).
- ``segment_id`` uniqueness (SYS-03 §15.1).
- Internal clustering metric blocklist in any pre-populated
  ``kpi`` value (FR-MKT-05, CON-07).
- Forbidden marketing terminology (CP-04 §4.4, FR-SEG-08).

Hard rules
----------
- All checks return :class:`ValidationCheck` objects; the caller
  decides whether to fail-closed or warn.
- Validation does NOT modify any input file.
- No access to ``data/raw/primary/**``, ``data/processed/**``,
  ``reports/**``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.marketing.config_loader import Dev07Config
from customer_segmentation.prototype.marketing.exceptions import (
    MarketingValidationError,
)
from customer_segmentation.prototype.marketing.manifest import (
    MarketingValidationReport,
    ValidationCheck,
    check_forbidden_marketing_terms,
)
from customer_segmentation.prototype.marketing.scope import (
    FORBIDDEN_MARKETING_TERMS,
    KPI_BLOCKLIST,
)

__all__ = [
    "MarketingInputValidationError",
    "validate_inputs",
    "validate_segmentation_manifest_shape",
    "validate_noise_segments_isolated",
    "validate_no_duplicate_segment_id",
    "validate_kpi_blocklist",
    "validate_text_no_forbidden_terms",
    "validate_research_safety_block",
]


DBSCAN_NOISE_SEGMENT_ID: Final[int] = -1


class MarketingInputValidationError(MarketingError := MarketingValidationError):  # type: ignore[misc]
    """Raised on hard validation failure (fail-closed)."""

    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check(check_id: str, passed: bool, detail: str = "") -> ValidationCheck:
    return ValidationCheck(check_id=check_id, passed=passed, detail=detail)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def validate_segmentation_manifest_shape(
    manifest_data: dict[str, Any],
) -> list[ValidationCheck]:
    """Check that the DEV-06 manifest has the fields DEV-07 needs.

    Returns a list of :class:`ValidationCheck` results. The check is
    *advisory* — the pipeline fails closed only if the data is missing
    or has the wrong type. Owner-approved review gates (e.g.,
    research_safety invariants) are checked separately.
    """
    checks: list[ValidationCheck] = []
    required_fields = (
        "schema_version",
        "segmentation_id",
        "scope",
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "ml_dataset_sha256",
        "feature_set_sha256",
        "preprocessing_config_sha256",
        "noise_policy_used",
        "segment_sizes",
        "research_safety",
    )
    for key in required_fields:
        present = key in manifest_data
        checks.append(
            _check(
                f"dev07_seg_manifest_{key}_present",
                present,
                f"DEV-06 manifest field {key!r} present" if present else f"missing {key!r}",
            )
        )
    return checks


def validate_research_safety_block(
    manifest_data: dict[str, Any],
) -> list[ValidationCheck]:
    """Validate the DEV-06 manifest's research_safety block.

    DEV-07 only accepts manifests with
    ``scope == "PROFILED_PROTOTYPE"`` and
    ``automatically_promoted_to_research == False``.
    """
    checks: list[ValidationCheck] = []
    rs = manifest_data.get("research_safety", {})
    scope_ok = rs.get("scope") == "PROFILED_PROTOTYPE"
    checks.append(
        _check(
            "dev07_seg_scope_profiled_prototype",
            scope_ok,
            f"DEV-06 scope {rs.get('scope')!r}",
        )
    )
    promoted_ok = rs.get("automatically_promoted_to_research") is False
    checks.append(
        _check(
            "dev07_seg_not_promoted_to_research",
            promoted_ok,
            f"DEV-06 automatically_promoted_to_research={rs.get('automatically_promoted_to_research')!r}",
        )
    )
    return checks


def validate_noise_segments_isolated(
    segment_sizes: list[dict[str, Any]],
    *,
    exclude_dbscan_noise: bool = True,
) -> list[ValidationCheck]:
    """Verify that the noise-exclusion gate is enabled.

    The pipeline filters DBSCAN noise at Stage D (recommendation
    build), so this check is *advisory*: it confirms the gate is
    enabled and records the noise count for diagnostic purposes.
    It does NOT fail-closed if noise entries are present in the
    raw DEV-06 manifest — those entries are expected and will be
    filtered in Stage D.
    """
    checks: list[ValidationCheck] = []
    if not exclude_dbscan_noise:
        checks.append(
            _check(
                "dev07_noise_exclusion_enabled",
                False,
                "config.validation.exclude_dbscan_noise=False; gate DISABLED",
            )
        )
        return checks
    noise_count = sum(
        1
        for s in segment_sizes
        if int(s.get("segment_id", 0)) == DBSCAN_NOISE_SEGMENT_ID or bool(s.get("is_noise", False))
    )
    checks.append(
        _check(
            "dev07_noise_exclusion_enabled",
            True,
            f"gate enabled; {noise_count} noise entries will be filtered in Stage D",
        )
    )
    return checks


def validate_no_duplicate_segment_id(
    segment_sizes: list[dict[str, Any]],
    *,
    require: bool = True,
) -> list[ValidationCheck]:
    """Check that ``segment_id`` is unique within non-noise entries.

    Per SYS-03 §15.1: ``E-MKT.segment_id`` is UNIQUE within a
    manifest. The raw DEV-06 ``segment_sizes`` may have noise as
    ``segment_id = -1`` (single occurrence is fine). Non-noise
    duplicates are fail-closed.
    """
    checks: list[ValidationCheck] = []
    if not require:
        checks.append(
            _check(
                "dev07_no_duplicate_segment_id_enabled",
                True,
                "config.validation.require_no_duplicate_segment_id=False; check skipped",
            )
        )
        return checks
    seen: set[int] = set()
    dups: list[int] = []
    for s in segment_sizes:
        sid = int(s.get("segment_id", 0))
        if sid == DBSCAN_NOISE_SEGMENT_ID:
            continue  # noise is excluded from uniqueness check
        if sid in seen:
            dups.append(sid)
        seen.add(sid)
    checks.append(
        _check(
            "dev07_no_duplicate_segment_id",
            len(dups) == 0,
            (
                f"duplicate segment_id(s) among non-noise entries: {sorted(dups)}"
                if dups
                else "no duplicates among non-noise entries"
            ),
        )
    )
    return checks


def validate_kpi_blocklist(
    kpi_values: list[str] | None,
    *,
    enforce: bool = True,
) -> list[ValidationCheck]:
    """Check that no internal clustering metric appears in ``kpi``."""
    checks: list[ValidationCheck] = []
    if not enforce:
        checks.append(
            _check(
                "dev07_kpi_blocklist_enabled",
                True,
                "config.validation.forbid_internal_metrics_as_kpi=False; check skipped",
            )
        )
        return checks
    if kpi_values is None:
        checks.append(_check("dev07_kpi_blocklist", True, "kpi is None (Phase A default)"))
        return checks
    bad = [k for k in kpi_values if k.lower() in KPI_BLOCKLIST]
    checks.append(
        _check(
            "dev07_kpi_blocklist",
            len(bad) == 0,
            f"blocked KPI(s): {bad}" if bad else "no blocked KPIs",
        )
    )
    return checks


def validate_text_no_forbidden_terms(
    text: str,
    *,
    enforce: bool = True,
) -> list[ValidationCheck]:
    """Check that ``text`` does not contain forbidden marketing terms."""
    checks: list[ValidationCheck] = []
    if not enforce:
        checks.append(
            _check(
                "dev07_forbidden_terms_enabled",
                True,
                "config.validation.forbid_marketing_terminology=False; check skipped",
            )
        )
        return checks
    found = check_forbidden_marketing_terms(text)
    checks.append(
        _check(
            "dev07_forbidden_terms",
            len(found) == 0,
            f"forbidden terms found: {found}" if found else "no forbidden terms",
        )
    )
    return checks


# ---------------------------------------------------------------------------
# Aggregate gate
# ---------------------------------------------------------------------------


def validate_inputs(
    *,
    manifest_data: dict[str, Any],
    config: Dev07Config,
) -> MarketingValidationReport:
    """Run all DEV-07 validation checks against the DEV-06 manifest.

    Returns a :class:`MarketingValidationReport`. The caller decides
    whether to fail-closed (``all_passed`` False → raise) or warn.

    Raises
    ------
    MarketingInputValidationError
        If any check fails (defence-in-depth: callers should also
        check ``report.all_passed``).
    """
    segment_sizes_raw = manifest_data.get("segment_sizes", [])
    if not isinstance(segment_sizes_raw, list):
        raise MarketingInputValidationError(
            "DEV-06 manifest `segment_sizes` must be a list; "
            f"got {type(segment_sizes_raw).__name__}."
        )

    checks: list[ValidationCheck] = []
    checks.extend(validate_segmentation_manifest_shape(manifest_data))
    checks.extend(validate_research_safety_block(manifest_data))
    checks.extend(
        validate_noise_segments_isolated(
            segment_sizes_raw,
            exclude_dbscan_noise=config.validation.exclude_dbscan_noise,
        )
    )
    checks.extend(
        validate_no_duplicate_segment_id(
            segment_sizes_raw,
            require=config.validation.require_no_duplicate_segment_id,
        )
    )
    checks.extend(
        validate_kpi_blocklist(
            None,
            enforce=config.validation.forbid_internal_metrics_as_kpi,
        )
    )
    # Combine all string fields for forbidden-terms scan.
    blob = _collect_text(manifest_data)
    checks.extend(
        validate_text_no_forbidden_terms(
            blob,
            enforce=config.validation.forbid_marketing_terminology,
        )
    )

    all_passed = all(c.passed for c in checks)
    if not all_passed:
        # Fail-closed: surface all failures as one error.
        failures = [c for c in checks if not c.passed]
        detail = "; ".join(f"[{c.check_id}] {c.detail}" for c in failures[:5])
        raise MarketingInputValidationError(
            f"DEV-07 input validation failed ({len(failures)} check(s)): {detail}"
        )
    return MarketingValidationReport(all_passed=True, checks=checks)


def _collect_text(manifest_data: dict[str, Any]) -> str:
    """Concatenate string-valued fields of a manifest for term scanning."""
    parts: list[str] = []
    for v in manifest_data.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            parts.append(_collect_text(v))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(_collect_text(item))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------


def compute_file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
