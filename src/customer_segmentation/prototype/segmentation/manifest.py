"""SegmentationManifest schema, JSON I/O, and stable/runtime classification.

A :class:`SegmentationManifest` is the on-disk sidecar of one DEV-06
segmentation pass. It records:

- ``segmentation_id`` (content-addressed from 8 canonical fields, see
  :mod:`customer_segmentation.prototype.segmentation.storage`),
- ``clustering_id`` + ``preprocessed_id`` + ``dataset_id`` (DEV-04/03/02
  pointers, all canonical),
- ``evaluation_id`` (DEV-05 pointer, OPTIONAL per OQ-SEG-INHERIT-01),
- ``algorithm`` + ``algorithm_version`` + ``algorithm_family``,
- ``ml_dataset_sha256`` (canonical), ``feature_set_sha256`` (derived),
  ``preprocessing_config_sha256`` (from DEV-03 ``config_hash``),
- ``noise_policy_used`` (per ADR-0006 prototype default = "exclude"),
- ``n_samples_input`` + ``n_samples_used_for_compute`` +
  ``n_clusters_input`` + ``n_segments`` + ``noise_count`` + ``noise_ratio``
  (DBSCAN provenance audit; per plan §4.2),
- ``segment_sizes`` (per-segment count / percentage / percentage_base /
  is_noise; per OQ-SEG-DENOM-01 + OQ-SEG-NOISE-01),
- ``profiles`` (per-segment descriptive profile; per OQ-SEG-PROFILE-01),
- ``characteristics`` (per-segment characteristics; per OQ-SEG-CHAR-01),
- ``config_sha256``,
- ``environment``,
- ``research_safety`` (always
  ``automatically_promoted_to_research=false``,
  ``scope="PROFILED_PROTOTYPE"``,
  ``appeared_in_research_evidence=false``).

Hard rules
----------
- The manifest writer uses **atomic write** (temp file + rename) to
  avoid partial writes.
- ``scope`` is **always** ``"PROFILED_PROTOTYPE"`` (1-value enum).
- ``schema_version`` is **always** the pinned
  :data:`SEGMENTATION_MANIFEST_SCHEMA_VERSION`.
- ``noise_count`` / ``noise_ratio`` are present iff
  ``algorithm_family == "density_based"``; for non-density algorithms
  both fields MUST be ``None`` (no fabricated value per R-DEV-06-22).
- ``percentage_base`` is **always** in the closed set
  ``{"n_samples_input", "n_samples_used_for_compute"}`` — no other
  denominator allowed (R-DEV-06-21).
- The 4 characteristic rules in :class:`CharacteristicEntry` MUST match
  the allowlist (per OQ-SEG-CHAR-01: ``mean_high_<feature>``,
  ``mean_low_<feature>``,
  ``median_above_dataset_median_<feature>``,
  ``top_category_<feature>_<value>``).
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

from customer_segmentation.prototype.segmentation.scope import (
    PROFILED_SCOPES,
    SEGMENTATION_MANIFEST_SCHEMA_VERSION,
)

__all__ = [
    "SEGMENTATION_MANIFEST_SCHEMA_VERSION",
    "SegmentationManifestError",
    "ResearchSafetyBlock",
    "SegmentationValidationReport",
    "ValidationCheck",
    "SegmentSize",
    "FeatureProfile",
    "CharacteristicEntry",
    "EnvironmentBlock",
    "SegmentationManifest",
    "read_segmentation_manifest",
    "write_segmentation_manifest",
    "manifest_to_dict",
    "now_utc_iso",
    "build_segmentation_manifest",
    "ALLOWED_CHARACTERISTIC_RULES",
    "ALLOWED_PERCENTAGE_BASES",
]


# ---------------------------------------------------------------------------
# Constants / closed sets
# ---------------------------------------------------------------------------

# Allowed percentage_base values (R-DEV-06-21).
ALLOWED_PERCENTAGE_BASES: Final[frozenset[str]] = frozenset(
    {"n_samples_input", "n_samples_used_for_compute"}
)

# Allowed algorithm_family values (mirror clustering contract).
ALLOWED_ALGORITHM_FAMILIES: Final[frozenset[str]] = frozenset(
    {"hard", "density_based", "model_based", "fuzzy", "other"}
)

# Allowed noise_policy_used values (mirror DEV-05).
# Includes "n/a" for non-density algorithms per §6.4.
ALLOWED_NOISE_POLICIES: Final[frozenset[str]] = frozenset({"include", "exclude", "n/a"})

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Mandatory post-preprocessing warning (R-DEV-06-23 / plan §14.2.4).
# Per plan §14.2.4: "Feature profile uses scaled/transformed values; not
# directly interpretable in original business units (per DEV-03
# preprocessing)."
POST_PREPROCESSING_WARNING: Final[str] = (
    "Feature profile uses scaled/transformed values; not directly "
    "interpretable in original business units (per DEV-03 preprocessing)."
)

# Allowed characteristic_id prefixes (per OQ-SEG-CHAR-01, 4-rule set).
# The placeholder ``<feature>`` is filled in at runtime; the literal
# ``<value>`` is the category value.
ALLOWED_CHARACTERISTIC_RULES: Final[frozenset[str]] = frozenset(
    {
        "mean_high_<feature>",
        "mean_low_<feature>",
        "median_above_dataset_median_<feature>",
        "top_category_<feature>_<value>",
    }
)

# Regex matching the 4 allowed characteristic_id templates.
_CHARACTERISTIC_ID_TEMPLATE_RE = re.compile(
    r"^(?P<rule>mean_high_(?P<f1>[A-Za-z0-9_]+)"
    r"|mean_low_(?P<f2>[A-Za-z0-9_]+)"
    r"|median_above_dataset_median_(?P<f3>[A-Za-z0-9_]+)"
    r"|top_category_(?P<f4>[A-Za-z0-9_]+)_(?P<v>.+))$"
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SegmentationManifestError(ValueError):
    """Raised on manifest construction / I/O / invariant failures."""


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

    Per R-DEV-06-01..03:
    - ``automatically_promoted_to_research = False`` always
    - ``scope = "PROFILED_PROTOTYPE"`` always
    - ``appeared_in_research_evidence = False`` always
    """

    automatically_promoted_to_research: bool
    scope: str
    appeared_in_research_evidence: bool
    read_only_paths_unmodified: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.automatically_promoted_to_research is not False:
            raise SegmentationManifestError(
                "research_safety.automatically_promoted_to_research MUST be False; "
                f"got {self.automatically_promoted_to_research!r}."
            )
        if self.scope not in PROFILED_SCOPES:
            raise SegmentationManifestError(
                f"research_safety.scope MUST be one of {sorted(PROFILED_SCOPES)}; "
                f"got {self.scope!r}."
            )
        if self.appeared_in_research_evidence is not False:
            raise SegmentationManifestError(
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
class SegmentationValidationReport:
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
# Per-segment data blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentSize:
    """Per-segment size row in ``segment_sizes.csv`` + ``segment_sizes_long.csv``.

    Per OQ-SEG-DENOM-01: ``percentage`` is the proportion under
    ``percentage_base``. The two bases are exclusive:

    - ``"n_samples_input"`` — denominator = total rows in cluster_labels
      (includes noise if DBSCAN).
    - ``"n_samples_used_for_compute"`` — denominator = rows after noise
      exclusion (only meaningful for ``is_noise=False`` segments).

    Per OQ-SEG-NOISE-01: ``segment_id == -1`` is reserved for noise
    (DBSCAN only); ``is_noise=True`` MUST be set iff ``segment_id == -1``.
    """

    segment_id: int
    count: int
    percentage: float
    percentage_base: str
    is_noise: bool

    def __post_init__(self) -> None:
        if self.count < 0:
            raise SegmentationManifestError(f"SegmentSize.count MUST be >= 0; got {self.count!r}.")
        if not (0.0 <= self.percentage <= 100.0):
            raise SegmentationManifestError(
                f"SegmentSize.percentage MUST be in [0, 100]; got {self.percentage!r}."
            )
        if self.percentage_base not in ALLOWED_PERCENTAGE_BASES:
            raise SegmentationManifestError(
                f"SegmentSize.percentage_base MUST be one of "
                f"{sorted(ALLOWED_PERCENTAGE_BASES)}; got {self.percentage_base!r}."
            )
        # segment_id MUST be >= 0 or exactly -1 (noise marker).
        if self.segment_id < -1:
            raise SegmentationManifestError(
                f"SegmentSize.segment_id MUST be >= -1 (only -1 reserved for noise); "
                f"got {self.segment_id!r}."
            )
        if self.is_noise and self.segment_id != -1:
            raise SegmentationManifestError(
                f"is_noise=True requires segment_id == -1; got segment_id={self.segment_id!r}."
            )
        if not self.is_noise and self.segment_id == -1:
            raise SegmentationManifestError(
                "is_noise=False requires segment_id != -1; got segment_id=-1."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "count": self.count,
            "percentage": self.percentage,
            "percentage_base": self.percentage_base,
            "is_noise": self.is_noise,
        }


@dataclass(frozen=True)
class FeatureProfile:
    """Per-segment feature profile row (one row per segment_id × feature_name).

    ``statistics`` is a dict of ``{statistic_name: value}`` where
    ``statistic_name`` is a member of
    :data:`PROFILING_STATISTICS_SET` (closed set; no research metrics).
    """

    segment_id: int
    feature_name: str
    statistics: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.feature_name, str) or not self.feature_name:
            raise SegmentationManifestError(
                f"FeatureProfile.feature_name MUST be a non-empty str; "
                f"got {self.feature_name!r}."
            )
        from customer_segmentation.prototype.segmentation.scope import (
            PROFILING_STATISTICS_SET,
        )

        for name in self.statistics:
            if name not in PROFILING_STATISTICS_SET:
                raise SegmentationManifestError(
                    f"FeatureProfile.statistics contains unknown name {name!r}; "
                    f"only {sorted(PROFILING_STATISTICS_SET)} are allowed."
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "feature_name": self.feature_name,
            "statistics": dict(self.statistics),
        }


@dataclass(frozen=True)
class CharacteristicEntry:
    """Per-segment characteristic (one row per segment_id × characteristic_id).

    Per OQ-SEG-CHAR-01: ``characteristic_id`` MUST match one of the 4
    approved rule templates in :data:`ALLOWED_CHARACTERISTIC_RULES`.

    Per R-DEV-06-23 (plan §4.2): ``segment_id`` is recorded so the
    JSON output can be nested by segment_id (plan §4.2 nested
    schema). ``is_invariant=False`` is a fixed invariant per
    OQ-SEG-CHAR-01 (characteristics are descriptive, not business
    labels). Default ``segment_id=-1`` preserves backward
    compatibility with manifests written before the field was
    added — those entries will be treated as noise (and excluded
    from per-segment grouping when the JSON is rebuilt).
    """

    characteristic_id: str
    description: str
    source_features: list[str]
    derived_stats: dict[str, Any]
    segment_id: int = -1

    def __post_init__(self) -> None:
        if not isinstance(self.characteristic_id, str) or not self.characteristic_id:
            raise SegmentationManifestError(
                f"CharacteristicEntry.characteristic_id MUST be a non-empty str; "
                f"got {self.characteristic_id!r}."
            )
        if not _CHARACTERISTIC_ID_TEMPLATE_RE.match(self.characteristic_id):
            raise SegmentationManifestError(
                f"characteristic_id {self.characteristic_id!r} does not match any "
                f"of the 4 approved rule templates "
                f"{sorted(ALLOWED_CHARACTERISTIC_RULES)} "
                "(per OQ-SEG-CHAR-01)."
            )
        if not isinstance(self.source_features, list) or not self.source_features:
            raise SegmentationManifestError(
                f"CharacteristicEntry.source_features MUST be a non-empty list; "
                f"got {self.source_features!r}."
            )
        if not isinstance(self.segment_id, int):
            raise SegmentationManifestError(
                f"CharacteristicEntry.segment_id MUST be an int; "
                f"got {type(self.segment_id).__name__}."
            )
        if self.segment_id < -1:
            raise SegmentationManifestError(
                f"CharacteristicEntry.segment_id MUST be >= -1 (only -1 reserved "
                f"for noise); got {self.segment_id!r}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "characteristic_id": self.characteristic_id,
            "description": self.description,
            "source_features": list(self.source_features),
            "derived_stats": dict(self.derived_stats),
            "segment_id": self.segment_id,
        }


@dataclass(frozen=True)
class EnvironmentBlock:
    """Runtime environment snapshot."""

    python: str
    platform: str
    release: str
    machine: str
    key_libraries: dict[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.python, str) or not self.python:
            raise SegmentationManifestError(
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
class SegmentationManifest:
    """On-disk manifest of one DEV-06 segmentation pass."""

    schema_version: str
    segmentation_id: str
    scope: str
    clustering_id: str
    preprocessed_id: str
    dataset_id: str
    evaluation_id: str | None
    algorithm: str
    algorithm_version: str
    algorithm_family: str
    ml_dataset_sha256: str
    feature_set_sha256: str
    preprocessing_config_sha256: str
    feature_set: list[str]
    feature_count: int
    n_samples_input: int
    n_samples_used_for_compute: int
    n_clusters_input: int
    n_segments: int
    noise_count: int | None
    noise_ratio: float | None
    noise_policy_used: str
    segment_sizes: list[SegmentSize]
    profiles: list[FeatureProfile]
    characteristics: list[CharacteristicEntry]
    environment: EnvironmentBlock
    config_sha256: str
    created_utc: str
    last_seen_utc: str
    log_file: str
    validation_report: SegmentationValidationReport
    research_safety: ResearchSafetyBlock
    input_clustering_manifest: str
    input_cluster_labels: str
    input_ml_dataset: str
    input_evaluation_manifest: str | None
    # New in DEV-06-remediation (R-DEV-06-23 / plan §14.2.4).
    # Default is the canonical MANDATORY text; manifest I/O is backward
    # compatible (old manifests reading this field default to "").
    preprocessing_applied: dict[str, str] = field(default_factory=dict)
    preprocessing_warning: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != SEGMENTATION_MANIFEST_SCHEMA_VERSION:
            raise SegmentationManifestError(
                f"schema_version MUST be {SEGMENTATION_MANIFEST_SCHEMA_VERSION!r}; "
                f"got {self.schema_version!r}."
            )
        if self.scope not in PROFILED_SCOPES:
            raise SegmentationManifestError(
                f"scope MUST be one of {sorted(PROFILED_SCOPES)}; got {self.scope!r}."
            )
        if self.algorithm_family not in ALLOWED_ALGORITHM_FAMILIES:
            raise SegmentationManifestError(
                f"algorithm_family MUST be one of {sorted(ALLOWED_ALGORITHM_FAMILIES)}; "
                f"got {self.algorithm_family!r}."
            )
        if self.noise_policy_used not in ALLOWED_NOISE_POLICIES:
            raise SegmentationManifestError(
                f"noise_policy_used MUST be one of {sorted(ALLOWED_NOISE_POLICIES)}; "
                f"got {self.noise_policy_used!r}."
            )
        if self.n_samples_used_for_compute > self.n_samples_input:
            raise SegmentationManifestError(
                f"n_samples_used_for_compute ({self.n_samples_used_for_compute}) "
                f"cannot exceed n_samples_input ({self.n_samples_input})."
            )
        if self.feature_count != len(self.feature_set):
            raise SegmentationManifestError(
                f"feature_count ({self.feature_count}) must equal "
                f"len(feature_set) ({len(self.feature_set)})."
            )
        # R-DEV-06-22: noise fields only for density_based algorithms.
        if self.algorithm_family == "density_based":
            if self.noise_count is None:
                raise SegmentationManifestError(
                    "noise_count MUST be set when algorithm_family is 'density_based'."
                )
            if self.noise_ratio is None:
                raise SegmentationManifestError(
                    "noise_ratio MUST be set when algorithm_family is 'density_based'."
                )
            if self.noise_policy_used == "n/a":
                raise SegmentationManifestError(
                    "noise_policy_used='n/a' is not valid for density_based algorithms."
                )
        else:
            if self.noise_count is not None:
                raise SegmentationManifestError(
                    f"noise_count MUST be None for non-density algorithm "
                    f"({self.algorithm_family!r}); got {self.noise_count!r}."
                )
            if self.noise_ratio is not None:
                raise SegmentationManifestError(
                    f"noise_ratio MUST be None for non-density algorithm "
                    f"({self.algorithm_family!r}); got {self.noise_ratio!r}."
                )
        if self.noise_count is not None and self.n_samples_input > 0:
            expected_used = self.n_samples_input - self.noise_count
            if self.n_samples_used_for_compute != expected_used:
                raise SegmentationManifestError(
                    f"n_samples_used_for_compute ({self.n_samples_used_for_compute}) "
                    f"must equal n_samples_input - noise_count "
                    f"({self.n_samples_input} - {self.noise_count} = {expected_used})."
                )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _validate_environment(env: dict[str, Any]) -> EnvironmentBlock:
    if not isinstance(env, dict):
        raise SegmentationManifestError(f"environment MUST be a dict; got {type(env).__name__}.")
    key_libs_raw = env.get("key_libraries", {})
    if not isinstance(key_libs_raw, dict):
        raise SegmentationManifestError(
            f"environment.key_libraries MUST be a dict; " f"got {type(key_libs_raw).__name__}."
        )
    return EnvironmentBlock(
        python=str(env.get("python", "")),
        platform=str(env.get("platform", "")),
        release=str(env.get("release", "")),
        machine=str(env.get("machine", "")),
        key_libraries={str(k): str(v) for k, v in key_libs_raw.items()},
    )


def _validate_validation_report(vr: Any) -> SegmentationValidationReport:
    if isinstance(vr, SegmentationValidationReport):
        return vr
    if not isinstance(vr, dict):
        raise SegmentationManifestError(
            f"validation_report MUST be a dict or SegmentationValidationReport; "
            f"got {type(vr).__name__}."
        )
    checks_raw = vr.get("checks", [])
    if not isinstance(checks_raw, list):
        raise SegmentationManifestError(
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
    return SegmentationValidationReport(
        all_passed=bool(vr.get("all_passed", False)),
        checks=checks,
    )


def build_segmentation_manifest(
    *,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    evaluation_id: str | None,
    algorithm: str,
    algorithm_version: str,
    algorithm_family: str,
    ml_dataset_sha256: str,
    feature_set_sha256: str,
    preprocessing_config_sha256: str,
    feature_set: list[str],
    n_samples_input: int,
    n_samples_used_for_compute: int,
    n_clusters_input: int,
    n_segments: int,
    noise_count: int | None,
    noise_ratio: float | None,
    noise_policy_used: str,
    segment_sizes: list[SegmentSize],
    profiles: list[FeatureProfile],
    characteristics: list[CharacteristicEntry],
    config_sha256: str,
    environment: dict[str, Any] | EnvironmentBlock,
    log_file: str,
    validation_report: dict[str, Any] | SegmentationValidationReport,
    readonly_paths: list[str],
    input_clustering_manifest: str,
    input_cluster_labels: str,
    input_ml_dataset: str,
    input_evaluation_manifest: str | None,
    preprocessing_applied: dict[str, str] | None = None,
    preprocessing_warning: str = "",
) -> SegmentationManifest:
    """Build a :class:`SegmentationManifest` with all invariants enforced.

    Per R-DEV-06-01..03: ``research_safety`` block is constructed with
    fixed prototype-scope values (not exposed to caller).

    Per R-DEV-06-23 / plan §14.2.4: ``preprocessing_warning`` records
    the mandatory disclaimer about post-preprocessing values;
    ``preprocessing_applied`` records the transformation/scaling
    settings that produced those values.
    """
    env_block = _validate_environment(
        environment if isinstance(environment, dict) else environment.to_dict()
    )
    val_block = _validate_validation_report(validation_report)
    pa_dict: dict[str, str] = (
        {str(k): str(v) for k, v in preprocessing_applied.items()}
        if preprocessing_applied is not None
        else {}
    )

    return SegmentationManifest(
        schema_version=SEGMENTATION_MANIFEST_SCHEMA_VERSION,
        segmentation_id=segmentation_id,
        scope="PROFILED_PROTOTYPE",
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        evaluation_id=evaluation_id,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
        algorithm_family=algorithm_family,
        ml_dataset_sha256=ml_dataset_sha256,
        feature_set_sha256=feature_set_sha256,
        preprocessing_config_sha256=preprocessing_config_sha256,
        feature_set=list(feature_set),
        feature_count=len(feature_set),
        n_samples_input=n_samples_input,
        n_samples_used_for_compute=n_samples_used_for_compute,
        n_clusters_input=n_clusters_input,
        n_segments=n_segments,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        noise_policy_used=noise_policy_used,
        segment_sizes=list(segment_sizes),
        profiles=list(profiles),
        characteristics=list(characteristics),
        environment=env_block,
        config_sha256=config_sha256,
        created_utc=now_utc_iso(),
        last_seen_utc=now_utc_iso(),
        log_file=log_file,
        validation_report=val_block,
        research_safety=ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="PROFILED_PROTOTYPE",
            appeared_in_research_evidence=False,
            read_only_paths_unmodified=list(readonly_paths),
        ),
        input_clustering_manifest=input_clustering_manifest,
        input_cluster_labels=input_cluster_labels,
        input_ml_dataset=input_ml_dataset,
        input_evaluation_manifest=input_evaluation_manifest,
        preprocessing_applied=pa_dict,
        preprocessing_warning=str(preprocessing_warning),
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


def manifest_to_dict(m: SegmentationManifest) -> dict[str, Any]:
    """Convert a :class:`SegmentationManifest` to a JSON-serialisable dict."""
    return _to_jsonable(asdict(m))


# ---------------------------------------------------------------------------
# I/O (atomic write)
# ---------------------------------------------------------------------------


def write_segmentation_manifest(manifest: SegmentationManifest, path: Path) -> None:
    """Atomically write a :class:`SegmentationManifest` to ``path``.

    Uses temp file + rename. The parent directory must already exist.
    """
    path = Path(path)
    if not path.parent.exists():
        raise SegmentationManifestError(
            f"Cannot write segmentation manifest to {path!s}: " f"parent directory does not exist."
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


def read_segmentation_manifest(path: Path) -> SegmentationManifest:
    """Read and reconstruct a :class:`SegmentationManifest` from JSON."""
    path = Path(path)
    if not path.exists():
        raise SegmentationManifestError(f"Manifest file not found: {path!s}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SegmentationManifestError(
            f"Failed to parse segmentation manifest JSON at {path!s}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SegmentationManifestError(
            f"Manifest at {path!s} must be a JSON object; " f"got {type(data).__name__}."
        )
    return _dict_to_manifest(data)


def _dict_to_manifest(data: Mapping[str, Any]) -> SegmentationManifest:
    """Build a SegmentationManifest from a JSON object (round-trip)."""
    required = (
        "schema_version",
        "segmentation_id",
        "scope",
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "algorithm",
        "algorithm_version",
        "algorithm_family",
        "ml_dataset_sha256",
        "feature_set_sha256",
        "preprocessing_config_sha256",
        "feature_set",
        "n_samples_input",
        "n_samples_used_for_compute",
        "n_clusters_input",
        "n_segments",
        "noise_count",
        "noise_ratio",
        "noise_policy_used",
        "segment_sizes",
        "profiles",
        "characteristics",
        "environment",
        "config_sha256",
        "created_utc",
        "last_seen_utc",
        "log_file",
        "validation_report",
        "research_safety",
        "input_clustering_manifest",
        "input_cluster_labels",
        "input_ml_dataset",
    )
    for key in required:
        if key not in data:
            raise SegmentationManifestError(f"Manifest is missing required field: {key!r}.")

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
        raise SegmentationManifestError("validation_report.checks must be a list.")
    checks = [
        ValidationCheck(
            check_id=str(c["check_id"]),
            passed=bool(c["passed"]),
            detail=str(c.get("detail", "")),
        )
        for c in checks_raw
    ]
    validation_report = SegmentationValidationReport(
        all_passed=bool(vr_raw.get("all_passed", False)),
        checks=checks,
    )

    # Segment sizes.
    sizes_raw = data["segment_sizes"]
    if not isinstance(sizes_raw, list):
        raise SegmentationManifestError("segment_sizes must be a list.")
    segment_sizes = [
        SegmentSize(
            segment_id=int(s["segment_id"]),
            count=int(s["count"]),
            percentage=float(s["percentage"]),
            percentage_base=str(s["percentage_base"]),
            is_noise=bool(s["is_noise"]),
        )
        for s in sizes_raw
    ]

    # Profiles.
    profiles_raw = data["profiles"]
    if not isinstance(profiles_raw, list):
        raise SegmentationManifestError("profiles must be a list.")
    profiles = [
        FeatureProfile(
            segment_id=int(p["segment_id"]),
            feature_name=str(p["feature_name"]),
            statistics={str(k): v for k, v in p["statistics"].items()},
        )
        for p in profiles_raw
    ]

    # Characteristics.
    chars_raw = data["characteristics"]
    if not isinstance(chars_raw, list):
        raise SegmentationManifestError("characteristics must be a list.")
    characteristics = [
        CharacteristicEntry(
            characteristic_id=str(c["characteristic_id"]),
            description=str(c.get("description", "")),
            source_features=[str(f) for f in c.get("source_features", [])],
            derived_stats={str(k): v for k, v in c.get("derived_stats", {}).items()},
            # Backward compat: pre-DEV-06-remediation manifests do not
            # have segment_id on each characteristic. Default to -1
            # (noise sentinel) — the nested-grouping write path will
            # skip noise segments, so old characteristics are silently
            # dropped on re-write (deterministic, no silent fabrication).
            segment_id=int(c.get("segment_id", -1)),
        )
        for c in chars_raw
    ]

    return SegmentationManifest(
        schema_version=str(data["schema_version"]),
        segmentation_id=str(data["segmentation_id"]),
        scope=str(data["scope"]),
        clustering_id=str(data["clustering_id"]),
        preprocessed_id=str(data["preprocessed_id"]),
        dataset_id=str(data["dataset_id"]),
        evaluation_id=(
            str(data["evaluation_id"]) if data.get("evaluation_id") is not None else None
        ),
        algorithm=str(data["algorithm"]),
        algorithm_version=str(data["algorithm_version"]),
        algorithm_family=str(data["algorithm_family"]),
        ml_dataset_sha256=str(data["ml_dataset_sha256"]),
        feature_set_sha256=str(data["feature_set_sha256"]),
        preprocessing_config_sha256=str(data["preprocessing_config_sha256"]),
        feature_set=[str(f) for f in data["feature_set"]],
        feature_count=int(data.get("feature_count", len(data["feature_set"]))),
        n_samples_input=int(data["n_samples_input"]),
        n_samples_used_for_compute=int(data["n_samples_used_for_compute"]),
        n_clusters_input=int(data["n_clusters_input"]),
        n_segments=int(data["n_segments"]),
        noise_count=(int(data["noise_count"]) if data.get("noise_count") is not None else None),
        noise_ratio=(float(data["noise_ratio"]) if data.get("noise_ratio") is not None else None),
        noise_policy_used=str(data["noise_policy_used"]),
        segment_sizes=segment_sizes,
        profiles=profiles,
        characteristics=characteristics,
        environment=environment,
        config_sha256=str(data["config_sha256"]),
        created_utc=str(data["created_utc"]),
        last_seen_utc=str(data["last_seen_utc"]),
        log_file=str(data["log_file"]),
        validation_report=validation_report,
        research_safety=research_safety,
        input_clustering_manifest=str(data["input_clustering_manifest"]),
        input_cluster_labels=str(data["input_cluster_labels"]),
        input_ml_dataset=str(data["input_ml_dataset"]),
        input_evaluation_manifest=(
            str(data["input_evaluation_manifest"])
            if data.get("input_evaluation_manifest") is not None
            else None
        ),
        # New fields (R-DEV-06-23 / plan §14.2.4). Backward compat:
        # missing → defaults; readers must NOT fail on legacy manifests.
        preprocessing_applied={
            str(k): str(v) for k, v in data.get("preprocessing_applied", {}).items()
        },
        preprocessing_warning=str(data.get("preprocessing_warning", "")),
    )
