"""MarketingRecommendationManifest schema, JSON I/O, and integrity checks.

A :class:`MarketingRecommendationManifest` is the on-disk sidecar of
one DEV-07 marketing recommendation pass. It records:

- ``marketing_id`` (content-addressed from 9 canonical fields, see
  :mod:`customer_segmentation.prototype.marketing.storage`),
- ``segmentation_id`` + ``clustering_id`` + ``preprocessed_id`` +
  ``dataset_id`` (DEV-06/04/03/02 pointers),
- ``availability`` (Literal per SYS-03 §15.1),
- ``source_framework_version`` (null Phase A; populated Phase B),
- ``mkt_framework_found`` (False Phase A; True Phase B when MKT-01..05
  present),
- SHA-256 chain from DEV-06 (``ml_dataset_sha256``,
  ``feature_set_sha256``, ``preprocessing_config_sha256``,
  ``segmentation_manifest_sha256``),
- ``noise_policy_used`` (inherited from DEV-06 manifest),
- per-segment counts (``n_segments_input``,
  ``n_segments_with_recommendation``, ``n_segments_noise``,
  ``n_segments_not_available``),
- ``recommendations`` (list of :class:`MarketingRecommendationEntry`),
- ``environment``,
- ``config_sha256``,
- ``research_safety`` (always
  ``automatically_promoted_to_research=False``,
  ``scope="MARKETING_PROTOTYPE"``,
  ``appeared_in_research_evidence=False``).

Hard rules
----------
- The manifest writer uses **atomic write** (temp file + rename) to
  avoid partial writes.
- ``scope`` is **always** ``"MARKETING_PROTOTYPE"`` (1-value enum).
- ``schema_version`` is **always** the pinned
  :data:`MARKETING_MANIFEST_SCHEMA_VERSION`.
- DBSCAN noise (``segment_id == -1``) MUST NOT be in
  ``recommendations`` (FR-MKT-06, CON-08). Noise count is reported
  in ``n_segments_noise``.
- ``E-MKT.segment_id`` is UNIQUE within ``recommendations`` per
  SYS-03 §15.1.
- The 6 characteristic/template fields (marketing_objective,
  strategy, recommended_action, kpi, evidence_ref, limitation) MUST
  be either None (when not applicable) or non-empty.
- Phase A: every entry's ``availability`` is ``REVIEW_REQUIRED``
  (per SYS-01 §6.7 FR-MKT-01 + SYS-04 §15.1 gate). The pipeline
  does NOT silently relax this default.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.marketing.exceptions import (
    MarketingManifestError,
    MarketingScopeError,
    MarketingValidationError,
)
from customer_segmentation.prototype.marketing.scope import (
    AVAILABILITY_STATUSES,
    DEFAULT_AVAILABILITY,
    FORBIDDEN_MARKETING_TERMS,
    KPI_BLOCKLIST,
    MARKETING_LIMITATION_TEXT,
    MARKETING_MANIFEST_SCHEMA_VERSION,
    MARKETING_PENDING_PLACEHOLDER,
    MARKETING_SCOPES,
    NOISE_POLICIES,
)

__all__ = [
    "MARKETING_MANIFEST_SCHEMA_VERSION",
    "MarketingManifestError",
    "ResearchSafetyBlock",
    "MarketingValidationReport",
    "ValidationCheck",
    "MarketingRecommendationEntry",
    "EnvironmentBlock",
    "MarketingRecommendationManifest",
    "read_marketing_manifest",
    "write_marketing_manifest",
    "manifest_to_dict",
    "now_utc_iso",
    "build_marketing_manifest",
    "build_recommendation_entry_review_required",
    "ALLOWED_AVAILABILITY",
    "ALLOWED_NOISE_POLICIES",
]


# ---------------------------------------------------------------------------
# Constants / closed sets
# ---------------------------------------------------------------------------

ALLOWED_AVAILABILITY: Final[frozenset[str]] = AVAILABILITY_STATUSES
ALLOWED_NOISE_POLICIES: Final[frozenset[str]] = NOISE_POLICIES

# Regex for ``recommendation_id``: ``mkt_`` + segment_id(1+digits) +
# underscore + 16 hex chars.
_RECOMMENDATION_ID_RE = re.compile(r"^mkt_seg_[0-9]+_[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------


def now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string (suffix ``Z``)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Sub-blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchSafetyBlock:
    """Research-safety markers (always prototype scope).

    Per R-DEV-07-01..03:
    - ``automatically_promoted_to_research = False`` always
    - ``scope = "MARKETING_PROTOTYPE"`` always
    - ``appeared_in_research_evidence = False`` always
    """

    automatically_promoted_to_research: bool
    scope: str
    appeared_in_research_evidence: bool
    read_only_paths_unmodified: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.automatically_promoted_to_research is not False:
            raise MarketingScopeError(
                "research_safety.automatically_promoted_to_research MUST be False; "
                f"got {self.automatically_promoted_to_research!r}."
            )
        if self.scope not in MARKETING_SCOPES:
            raise MarketingScopeError(
                f"research_safety.scope MUST be one of {sorted(MARKETING_SCOPES)}; "
                f"got {self.scope!r}."
            )
        if self.appeared_in_research_evidence is not False:
            raise MarketingScopeError(
                "research_safety.appeared_in_research_evidence MUST be False; "
                f"got {self.appeared_in_research_evidence!r}."
            )


@dataclass(frozen=True)
class ValidationCheck:
    """A single validation check (id + outcome)."""

    check_id: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class MarketingValidationReport:
    """Outcome of input validation (Stage C of the pipeline)."""

    all_passed: bool
    checks: list[ValidationCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "checks": [
                {"check_id": c.check_id, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Per-segment entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketingRecommendationEntry:
    """One per-segment marketing recommendation entry.

    Per SYS-03 §15.1: every field in
    ``(marketing_objective, strategy, recommended_action, kpi,
    evidence_ref, limitation)`` MUST be either None or non-empty.

    Phase A values (MKT framework absent): all five template fields =
    None or the ``MARKETING_PENDING_PLACEHOLDER`` string;
    ``kpi = None`` always.

    Per FR-MKT-06 / CON-08: ``segment_id`` MUST be >= 0 (DBSCAN noise
    is excluded; noise count is recorded in
    :class:`MarketingRecommendationManifest.n_segments_noise`).

    Per SYS-03 §15.1: ``segment_id`` is UNIQUE within the manifest
    (enforced by the manifest builder).
    """

    segment_id: int
    cluster_label: int
    availability: str
    recommendation_id: str
    marketing_objective: str | None
    strategy: str | None
    recommended_action: str | None
    kpi: list[str] | None
    evidence_ref: list[str]
    limitation: str | None
    limitation_note: str
    interpretation_readiness: str | None
    is_interpretation_ready: bool | None

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, int) or self.segment_id < 0:
            # segment_id=-1 is reserved for DBSCAN noise (excluded entirely
            # from recommendations). Reject if present.
            raise MarketingManifestError(
                f"MarketingRecommendationEntry.segment_id MUST be >= 0 "
                f"(DBSCAN noise excluded); got {self.segment_id!r}."
            )
        if self.availability not in ALLOWED_AVAILABILITY:
            raise MarketingManifestError(
                f"availability {self.availability!r} MUST be one of "
                f"{sorted(ALLOWED_AVAILABILITY)}."
            )
        if not isinstance(self.recommendation_id, str) or not _RECOMMENDATION_ID_RE.match(
            self.recommendation_id
        ):
            raise MarketingManifestError(
                f"recommendation_id {self.recommendation_id!r} does not match "
                f"required format {_RECOMMENDATION_ID_RE.pattern}."
            )
        # Validate non-None template fields are non-empty.
        for name, val in (
            ("marketing_objective", self.marketing_objective),
            ("strategy", self.strategy),
            ("recommended_action", self.recommended_action),
            ("limitation", self.limitation),
        ):
            if val is not None and (not isinstance(val, str) or not val):
                raise MarketingManifestError(f"{name} MUST be None or non-empty str; got {val!r}.")
        # KPI blocklist (FR-MKT-05, CON-07) — applies even to None / empty.
        if self.kpi is not None:
            if not isinstance(self.kpi, list):
                raise MarketingManifestError(
                    f"kpi MUST be a list or None; got {type(self.kpi).__name__}."
                )
            for k in self.kpi:
                if not isinstance(k, str):
                    raise MarketingManifestError(
                        f"kpi entries MUST be str; got {type(k).__name__}."
                    )
                if k.lower() in KPI_BLOCKLIST:
                    raise MarketingManifestError(
                        f"kpi {k!r} is an internal clustering metric and is "
                        f"NOT allowed as a business KPI (FR-MKT-05, CON-07)."
                    )
        # evidence_ref: must be a list of non-empty strings.
        if not isinstance(self.evidence_ref, list):
            raise MarketingManifestError(
                f"evidence_ref MUST be a list; got {type(self.evidence_ref).__name__}."
            )
        for ref in self.evidence_ref:
            if not isinstance(ref, str) or not ref:
                raise MarketingManifestError(
                    f"evidence_ref entries MUST be non-empty str; got {ref!r}."
                )
        # limitation_note: mandatory non-empty string (carry-over).
        if not isinstance(self.limitation_note, str) or not self.limitation_note:
            raise MarketingManifestError(
                f"limitation_note MUST be a non-empty str; got {self.limitation_note!r}."
            )


@dataclass(frozen=True)
class EnvironmentBlock:
    """Runtime environment snapshot (mirrors DEV-06 schema)."""

    python: str
    platform: str
    release: str
    machine: str
    key_libraries: dict[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.python, str) or not self.python:
            raise MarketingManifestError(
                f"EnvironmentBlock.python MUST be a non-empty str; got {self.python!r}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "python": self.python,
            "platform": self.platform,
            "release": self.release,
            "machine": self.machine,
            "key_libraries": dict(self.key_libraries),
        }


# ---------------------------------------------------------------------------
# Top-level manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketingRecommendationManifest:
    """On-disk manifest of one DEV-07 marketing recommendation pass."""

    schema_version: str
    marketing_id: str
    segmentation_id: str
    clustering_id: str
    preprocessed_id: str
    dataset_id: str
    availability: str
    source_framework_version: str | None
    mkt_framework_found: bool
    ml_dataset_sha256: str
    feature_set_sha256: str
    preprocessing_config_sha256: str
    segmentation_manifest_sha256: str
    n_segments_input: int
    n_segments_with_recommendation: int
    n_segments_noise: int
    n_segments_not_available: int
    noise_policy_used: str
    recommendations: list[MarketingRecommendationEntry]
    environment: EnvironmentBlock
    config_sha256: str
    created_utc: str
    last_modified_utc: str
    log_file: str
    validation_report: MarketingValidationReport
    research_safety: ResearchSafetyBlock
    input_segmentation_manifest: str
    limitation: str

    def __post_init__(self) -> None:
        if self.schema_version != MARKETING_MANIFEST_SCHEMA_VERSION:
            raise MarketingManifestError(
                f"schema_version MUST be {MARKETING_MANIFEST_SCHEMA_VERSION!r}; "
                f"got {self.schema_version!r}."
            )
        if self.availability not in ALLOWED_AVAILABILITY:
            raise MarketingManifestError(
                f"availability {self.availability!r} MUST be one of "
                f"{sorted(ALLOWED_AVAILABILITY)}."
            )
        if self.noise_policy_used not in ALLOWED_NOISE_POLICIES:
            raise MarketingManifestError(
                f"noise_policy_used {self.noise_policy_used!r} MUST be one of "
                f"{sorted(ALLOWED_NOISE_POLICIES)}."
            )
        # Count invariants.
        if self.n_segments_input < 0:
            raise MarketingManifestError(
                f"n_segments_input MUST be >= 0; got {self.n_segments_input!r}."
            )
        if self.n_segments_noise < 0:
            raise MarketingManifestError(
                f"n_segments_noise MUST be >= 0; got {self.n_segments_noise!r}."
            )
        if self.n_segments_with_recommendation < 0:
            raise MarketingManifestError(
                f"n_segments_with_recommendation MUST be >= 0; got "
                f"{self.n_segments_with_recommendation!r}."
            )
        if self.n_segments_not_available < 0:
            raise MarketingManifestError(
                f"n_segments_not_available MUST be >= 0; got " f"{self.n_segments_not_available!r}."
            )
        # n_segments_with_recommendation + n_segments_not_available MUST equal
        # number of recommendations; n_segments_noise MUST be excluded.
        if self.n_segments_with_recommendation + self.n_segments_not_available != len(
            self.recommendations
        ):
            raise MarketingManifestError(
                f"n_segments_with_recommendation + n_segments_not_available "
                f"({self.n_segments_with_recommendation} + "
                f"{self.n_segments_not_available}) MUST equal "
                f"len(recommendations) ({len(self.recommendations)})."
            )
        # segment_id uniqueness (SYS-03 §15.1).
        seg_ids = [r.segment_id for r in self.recommendations]
        if len(seg_ids) != len(set(seg_ids)):
            raise MarketingManifestError(
                "E-MKT.segment_id MUST be UNIQUE within recommendations "
                "(SYS-03 §15.1); found duplicate segment_id."
            )
        if not isinstance(self.limitation, str) or not self.limitation:
            raise MarketingManifestError(
                f"limitation MUST be a non-empty str; got {self.limitation!r}."
            )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _validate_environment(env: dict[str, Any] | EnvironmentBlock) -> EnvironmentBlock:
    if isinstance(env, EnvironmentBlock):
        return env
    if not isinstance(env, dict):
        raise MarketingManifestError(
            f"environment MUST be a dict or EnvironmentBlock; got {type(env).__name__}."
        )
    key_libs_raw = env.get("key_libraries", {})
    if not isinstance(key_libs_raw, dict):
        raise MarketingManifestError(
            f"environment.key_libraries MUST be a dict; " f"got {type(key_libs_raw).__name__}."
        )
    return EnvironmentBlock(
        python=str(env.get("python", "")),
        platform=str(env.get("platform", "")),
        release=str(env.get("release", "")),
        machine=str(env.get("machine", "")),
        key_libraries={str(k): str(v) for k, v in key_libs_raw.items()},
    )


def _validate_validation_report(
    vr: Any,
) -> MarketingValidationReport:
    if isinstance(vr, MarketingValidationReport):
        return vr
    if not isinstance(vr, dict):
        raise MarketingManifestError(
            f"validation_report MUST be a dict or MarketingValidationReport; "
            f"got {type(vr).__name__}."
        )
    checks_raw = vr.get("checks", [])
    if not isinstance(checks_raw, list):
        raise MarketingManifestError(
            f"validation_report.checks MUST be a list; " f"got {type(checks_raw).__name__}."
        )
    checks = [
        ValidationCheck(
            check_id=str(c["check_id"]),
            passed=bool(c["passed"]),
            detail=str(c.get("detail", "")),
        )
        for c in checks_raw
    ]
    return MarketingValidationReport(
        all_passed=bool(vr.get("all_passed", False)),
        checks=checks,
    )


def build_recommendation_entry_review_required(
    *,
    segment_id: int,
    cluster_label: int,
    evidence_ref: list[str],
    limitation_note: str = MARKETING_LIMITATION_TEXT,
    interpretation_readiness: str | None = None,
    is_interpretation_ready: bool | None = None,
) -> MarketingRecommendationEntry:
    """Construct a Phase A ``REVIEW_REQUIRED`` entry for one segment.

    All five template fields are set to
    :data:`MARKETING_PENDING_PLACEHOLDER`; ``kpi`` is None; the
    limitation field carries the carry-over text.
    """
    rec_id = f"mkt_seg_{segment_id}_{_short_hex(16)}"
    return MarketingRecommendationEntry(
        segment_id=int(segment_id),
        cluster_label=int(cluster_label),
        availability=DEFAULT_AVAILABILITY,
        recommendation_id=rec_id,
        marketing_objective=MARKETING_PENDING_PLACEHOLDER,
        strategy=MARKETING_PENDING_PLACEHOLDER,
        recommended_action=MARKETING_PENDING_PLACEHOLDER,
        kpi=None,
        evidence_ref=list(evidence_ref),
        limitation=MARKETING_LIMITATION_TEXT,
        limitation_note=str(limitation_note),
        interpretation_readiness=interpretation_readiness,
        is_interpretation_ready=is_interpretation_ready,
    )


def _short_hex(n_hex_chars: int) -> str:
    """Return a random hex string of length ``n_hex_chars`` (used for
    :attr:`MarketingRecommendationEntry.recommendation_id`)."""
    import secrets

    return secrets.token_hex(n_hex_chars // 2)


def build_marketing_manifest(
    *,
    marketing_id: str,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    source_framework_version: str | None,
    mkt_framework_found: bool,
    ml_dataset_sha256: str,
    feature_set_sha256: str,
    preprocessing_config_sha256: str,
    segmentation_manifest_sha256: str,
    n_segments_input: int,
    n_segments_with_recommendation: int,
    n_segments_noise: int,
    n_segments_not_available: int,
    noise_policy_used: str,
    recommendations: list[MarketingRecommendationEntry],
    environment: dict[str, Any] | EnvironmentBlock,
    config_sha256: str,
    log_file: str,
    validation_report: dict[str, Any] | MarketingValidationReport,
    readonly_paths: list[str],
    input_segmentation_manifest: str,
    availability: str = DEFAULT_AVAILABILITY,
    limitation: str = MARKETING_LIMITATION_TEXT,
) -> MarketingRecommendationManifest:
    """Build a :class:`MarketingRecommendationManifest` with all invariants.

    Per R-DEV-07-01..03: ``research_safety`` block is constructed with
    fixed prototype-scope values (not exposed to caller).
    """
    env_block = _validate_environment(
        environment if isinstance(environment, dict) else environment.to_dict()
    )
    val_block = _validate_validation_report(validation_report)

    return MarketingRecommendationManifest(
        schema_version=MARKETING_MANIFEST_SCHEMA_VERSION,
        marketing_id=marketing_id,
        segmentation_id=segmentation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        availability=str(availability),
        source_framework_version=(
            str(source_framework_version) if source_framework_version is not None else None
        ),
        mkt_framework_found=bool(mkt_framework_found),
        ml_dataset_sha256=str(ml_dataset_sha256),
        feature_set_sha256=str(feature_set_sha256),
        preprocessing_config_sha256=str(preprocessing_config_sha256),
        segmentation_manifest_sha256=str(segmentation_manifest_sha256),
        n_segments_input=int(n_segments_input),
        n_segments_with_recommendation=int(n_segments_with_recommendation),
        n_segments_noise=int(n_segments_noise),
        n_segments_not_available=int(n_segments_not_available),
        noise_policy_used=str(noise_policy_used),
        recommendations=list(recommendations),
        environment=env_block,
        config_sha256=str(config_sha256),
        created_utc=now_utc_iso(),
        last_modified_utc=now_utc_iso(),
        log_file=str(log_file),
        validation_report=val_block,
        research_safety=ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="MARKETING_PROTOTYPE",
            appeared_in_research_evidence=False,
            read_only_paths_unmodified=list(readonly_paths),
        ),
        input_segmentation_manifest=str(input_segmentation_manifest),
        limitation=str(limitation),
    )


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def _to_jsonable(value: Any) -> Any:
    """Convert a value to a JSON-serializable form."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        return _to_jsonable(value.to_dict())
    if hasattr(value, "__dataclass_fields__"):
        return _to_jsonable(asdict(value))
    raise TypeError(f"Cannot serialise value of type {type(value).__name__}.")


def manifest_to_dict(m: MarketingRecommendationManifest) -> dict[str, Any]:
    """Convert a :class:`MarketingRecommendationManifest` to a JSON-serialisable dict."""
    return _to_jsonable(asdict(m))


# ---------------------------------------------------------------------------
# I/O (atomic write)
# ---------------------------------------------------------------------------


def write_marketing_manifest(manifest: MarketingRecommendationManifest, path: Path) -> None:
    """Atomically write a :class:`MarketingRecommendationManifest` to ``path``.

    Uses temp file + rename. The parent directory must already exist.
    """
    path = Path(path)
    if not path.parent.exists():
        raise MarketingManifestError(
            f"Cannot write marketing manifest to {path!s}: " f"parent directory does not exist."
        )
    payload = manifest_to_dict(manifest)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


def read_marketing_manifest(path: Path) -> MarketingRecommendationManifest:
    """Read and reconstruct a :class:`MarketingRecommendationManifest` from JSON."""
    path = Path(path)
    if not path.exists():
        raise MarketingManifestError(f"Manifest file not found: {path!s}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise MarketingManifestError(
            f"Failed to parse marketing manifest JSON at {path!s}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise MarketingManifestError(
            f"Manifest at {path!s} must be a JSON object; " f"got {type(data).__name__}."
        )
    return _dict_to_manifest(data)


def _dict_to_manifest(data: Mapping[str, Any]) -> MarketingRecommendationManifest:
    """Build a MarketingRecommendationManifest from a JSON object (round-trip)."""
    required = (
        "schema_version",
        "marketing_id",
        "segmentation_id",
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "availability",
        "source_framework_version",
        "mkt_framework_found",
        "ml_dataset_sha256",
        "feature_set_sha256",
        "preprocessing_config_sha256",
        "segmentation_manifest_sha256",
        "n_segments_input",
        "n_segments_with_recommendation",
        "n_segments_noise",
        "n_segments_not_available",
        "noise_policy_used",
        "recommendations",
        "environment",
        "config_sha256",
        "created_utc",
        "last_modified_utc",
        "log_file",
        "validation_report",
        "research_safety",
        "input_segmentation_manifest",
        "limitation",
    )
    for key in required:
        if key not in data:
            raise MarketingManifestError(f"Manifest is missing required field: {key!r}.")

    # Research safety.
    rs_raw = data["research_safety"]
    research_safety = ResearchSafetyBlock(
        automatically_promoted_to_research=bool(rs_raw["automatically_promoted_to_research"]),
        scope=str(rs_raw["scope"]),
        appeared_in_research_evidence=bool(rs_raw["appeared_in_research_evidence"]),
        read_only_paths_unmodified=[str(p) for p in rs_raw.get("read_only_paths_unmodified", [])],
    )

    # Environment.
    env_raw = data["environment"]
    key_libs = {str(k): str(v) for k, v in env_raw.get("key_libraries", {}).items()}
    environment = EnvironmentBlock(
        python=str(env_raw.get("python", "")),
        platform=str(env_raw.get("platform", "")),
        release=str(env_raw.get("release", "")),
        machine=str(env_raw.get("machine", "")),
        key_libraries=key_libs,
    )

    # Validation report.
    vr_raw = data["validation_report"]
    checks_raw = vr_raw.get("checks", [])
    if not isinstance(checks_raw, list):
        raise MarketingManifestError("validation_report.checks must be a list.")
    checks = [
        ValidationCheck(
            check_id=str(c["check_id"]),
            passed=bool(c["passed"]),
            detail=str(c.get("detail", "")),
        )
        for c in checks_raw
    ]
    validation_report = MarketingValidationReport(
        all_passed=bool(vr_raw.get("all_passed", False)),
        checks=checks,
    )

    # Recommendations.
    recs_raw = data["recommendations"]
    if not isinstance(recs_raw, list):
        raise MarketingManifestError("recommendations must be a list.")
    recommendations = [
        MarketingRecommendationEntry(
            segment_id=int(r["segment_id"]),
            cluster_label=int(r["cluster_label"]),
            availability=str(r["availability"]),
            recommendation_id=str(r["recommendation_id"]),
            marketing_objective=(
                str(r["marketing_objective"]) if r.get("marketing_objective") is not None else None
            ),
            strategy=str(r["strategy"]) if r.get("strategy") is not None else None,
            recommended_action=(
                str(r["recommended_action"]) if r.get("recommended_action") is not None else None
            ),
            kpi=([str(k) for k in r["kpi"]] if r.get("kpi") is not None else None),
            evidence_ref=[str(p) for p in r.get("evidence_ref", [])],
            limitation=str(r["limitation"]) if r.get("limitation") is not None else None,
            limitation_note=str(r.get("limitation_note", "")),
            interpretation_readiness=(
                str(r["interpretation_readiness"])
                if r.get("interpretation_readiness") is not None
                else None
            ),
            is_interpretation_ready=(
                bool(r["is_interpretation_ready"])
                if r.get("is_interpretation_ready") is not None
                else None
            ),
        )
        for r in recs_raw
    ]

    return MarketingRecommendationManifest(
        schema_version=str(data["schema_version"]),
        marketing_id=str(data["marketing_id"]),
        segmentation_id=str(data["segmentation_id"]),
        clustering_id=str(data["clustering_id"]),
        preprocessed_id=str(data["preprocessed_id"]),
        dataset_id=str(data["dataset_id"]),
        availability=str(data["availability"]),
        source_framework_version=(
            str(data["source_framework_version"])
            if data.get("source_framework_version") is not None
            else None
        ),
        mkt_framework_found=bool(data["mkt_framework_found"]),
        ml_dataset_sha256=str(data["ml_dataset_sha256"]),
        feature_set_sha256=str(data["feature_set_sha256"]),
        preprocessing_config_sha256=str(data["preprocessing_config_sha256"]),
        segmentation_manifest_sha256=str(data["segmentation_manifest_sha256"]),
        n_segments_input=int(data["n_segments_input"]),
        n_segments_with_recommendation=int(data["n_segments_with_recommendation"]),
        n_segments_noise=int(data["n_segments_noise"]),
        n_segments_not_available=int(data["n_segments_not_available"]),
        noise_policy_used=str(data["noise_policy_used"]),
        recommendations=recommendations,
        environment=environment,
        config_sha256=str(data["config_sha256"]),
        created_utc=str(data["created_utc"]),
        last_modified_utc=str(data["last_modified_utc"]),
        log_file=str(data["log_file"]),
        validation_report=validation_report,
        research_safety=research_safety,
        input_segmentation_manifest=str(data["input_segmentation_manifest"]),
        limitation=str(data["limitation"]),
    )


# ---------------------------------------------------------------------------
# Forbidden marketing terminology check (re-exported for display module)
# ---------------------------------------------------------------------------


def check_forbidden_marketing_terms(text: str) -> list[str]:
    """Return the list of forbidden marketing terms present in ``text``.

    Per CP-04 §4.4, FR-SEG-08, AGENTS.md §2.5.
    """
    if not isinstance(text, str):
        return []
    found: list[str] = []
    lowered = text.lower()
    for term in FORBIDDEN_MARKETING_TERMS:
        if term.lower() in lowered:
            found.append(term)
    return found
