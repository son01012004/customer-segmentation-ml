"""Comparison of multiple segmentation manifests (DEV-06).

Per OQ-SEG-COMPARE-01 (Phase 1.5) and P1-3 resolution (2026-10-10),
DEV-06 uses a NARROWER compatibility key than DEV-05. Specifically:

- 4 fields: ``dataset_id``, ``preprocessed_id``, ``ml_dataset_sha256``,
  ``feature_set_sha256``.
- ``preprocessing_config_sha256`` is recorded as provenance in
  ``segmentation_manifest.json`` but is NOT in the comparison key
  (R-DEV-06-24 — avoid the DEV-05 ``"f" * 64`` placeholder defect,
  see plan §19.6, §20.5).

Per-row provenance fields (recorded in the group output but not in the
key): ``algorithm``, ``algorithm_family``, ``noise_policy_used``,
``n_segments``, ``noise_count``, ``noise_ratio``.

Per Owner-approved target behavior (P1-3 resolution, 2026-10-10):

- A :class:`ComparisonGroup` represents a set of at least two manifests
  sharing the same :class:`CompatibilityKey`, except for a call
  containing exactly one input manifest (which produces a singleton
  group with the existing ``singleton — no comparison possible`` note).
- Manifests whose key has no other matching manifest in a multi-manifest
  call are **excluded** from ``groups`` and reported through
  :class:`ExclusionReason` entries in ``exclusion_reasons``.
- All-incompatible multi-manifest call → ``groups = []``; populated
  ``exclusion_reasons``.
- Mixed call → retain every multi-member compatible group; report
  every excluded singleton manifest. No arbitrary anchor is chosen.
- Same-key manifests with differing per-row provenance remain grouped,
  with the existing per-row ``incompatibility_reasons`` semantics
  preserved (R-DEV-06-26 separates the two reason concepts).

The comparison module is RESEARCH-SAFE: it NEVER emits "best", "winner",
"ranking", "recommended", "optimal", "composite_score", "aggregate",
"VIP", "champion", "loyal", "high-value", "at-risk", "churn", or
"marketing". The single allowed occurrence of those substrings is
inside the mandatory disclaimer phrase (R-DEV-06-08 / R-DEV-06-19).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.segmentation.manifest import (
    SegmentationManifest,
    read_segmentation_manifest,
)

__all__ = [
    "CompatibilityKey",
    "ComparisonGroup",
    "ComparisonReport",
    "ExclusionReason",
    "IncompatibilityReason",
    "PerRowProvenance",
    "SizeDistributionEntry",
    "compare_segmentations",
    "DEFAULT_COMPARISON_DISCLAIMER",
    "EXCLUSION_REASON_CODE_NO_SHARED_KEY",
    "COMPATIBILITY_KEY_FIELDS",
]


# Mandatory disclaimer (negation form; the only allowed occurrence of
# ranking / recommendation / winner in DEV-06 output).
DEFAULT_COMPARISON_DISCLAIMER: Final[str] = (
    "no ranking, recommendation, or winner annotation is emitted"
)


# Stable reason code for manifest-exclusion entries (R-DEV-06-26).
EXCLUSION_REASON_CODE_NO_SHARED_KEY: Final[str] = "excluded_no_shared_key"


# Closed set of fields allowed in the DEV-06 CompatibilityKey.
# R-DEV-06-24: must NOT include ``preprocessing_config_sha256`` (avoid
# DEV-05 placeholder defect).
COMPATIBILITY_KEY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "dataset_id",
        "preprocessed_id",
        "ml_dataset_sha256",
        "feature_set_sha256",
    }
)


# Per-row provenance fields (recorded alongside each segmentation row,
# not in the key). When manifests share a key but differ in any of
# these, an ``IncompatibilityReason`` is emitted.
PER_ROW_PROVENANCE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "algorithm",
        "algorithm_family",
        "noise_policy_used",
        "n_segments",
        "noise_count",
        "noise_ratio",
    }
)


@dataclass(frozen=True)
class CompatibilityKey:
    """The 4 fields that must match for two segmentations to be compared.

    Per R-DEV-06-24: ``preprocessing_config_sha256`` is deliberately
    excluded (the ``ClusteringManifest`` v1.0.0 does not carry this
    field, and the DEV-05 fallback ``"f" * 64`` placeholder would
    produce a fabricated value).
    """

    dataset_id: str
    preprocessed_id: str
    ml_dataset_sha256: str
    feature_set_sha256: str

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (
            self.dataset_id,
            self.preprocessed_id,
            self.ml_dataset_sha256,
            self.feature_set_sha256,
        )

    def __hash__(self) -> int:
        return hash(self.as_tuple())

    def to_dict(self) -> dict[str, str]:
        return {
            "dataset_id": self.dataset_id,
            "preprocessed_id": self.preprocessed_id,
            "ml_dataset_sha256": self.ml_dataset_sha256,
            "feature_set_sha256": self.feature_set_sha256,
        }


def _extract_key(m: SegmentationManifest) -> CompatibilityKey:
    return CompatibilityKey(
        dataset_id=m.dataset_id,
        preprocessed_id=m.preprocessed_id,
        ml_dataset_sha256=m.ml_dataset_sha256,
        feature_set_sha256=m.feature_set_sha256,
    )


def _extract_per_row_provenance(
    m: SegmentationManifest,
) -> PerRowProvenance:
    """Return per-row provenance fields for a manifest (not part of key)."""
    return PerRowProvenance(
        segmentation_id=m.segmentation_id,
        algorithm=m.algorithm,
        algorithm_family=m.algorithm_family,
        noise_policy_used=m.noise_policy_used,
        n_segments=m.n_segments,
        noise_count=m.noise_count,
        noise_ratio=m.noise_ratio,
    )


@dataclass(frozen=True)
class PerRowProvenance:
    """Per-segmentation provenance fields (recorded alongside the key).

    Two manifests with the same CompatibilityKey but different
    per-row fields are still grouped, but emit
    ``IncompatibilityReason`` for each differing field.
    """

    segmentation_id: str
    algorithm: str
    algorithm_family: str
    noise_policy_used: str
    n_segments: int
    noise_count: int | None
    noise_ratio: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "segmentation_id": self.segmentation_id,
            "algorithm": self.algorithm,
            "algorithm_family": self.algorithm_family,
            "noise_policy_used": self.noise_policy_used,
            "n_segments": self.n_segments,
            "noise_count": self.noise_count,
            "noise_ratio": self.noise_ratio,
        }


@dataclass(frozen=True)
class IncompatibilityReason:
    """Why two segmentations in the same group differ on per-row fields.

    Per R-DEV-06-26: this dataclass is reserved for per-row provenance
    differences within a shared compatibility group. Excluded
    manifests (no shared key) are reported via
    :class:`ExclusionReason` instead, in the separate
    ``exclusion_reasons`` field of :class:`ComparisonReport`.
    """

    segmentation_id: str
    field_name: str
    stored_value: str
    compared_value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "segmentation_id": self.segmentation_id,
            "field_name": self.field_name,
            "stored_value": self.stored_value,
            "compared_value": self.compared_value,
        }


@dataclass(frozen=True)
class ExclusionReason:
    """Why a manifest was excluded from the comparison groups.

    Per P1-3 resolution (2026-10-10): emitted in a multi-manifest call
    when a manifest's :class:`CompatibilityKey` has no other manifest
    in the call sharing it. The reason is a stable, machine-readable
    record of which key fields caused the incompatibility, and whether
    the call has any retained group at all.

    Fields
    ------
    excluded_segmentation_id : str
        The ``segmentation_id`` of the excluded manifest.
    excluded_key : dict[str, str]
        The full 4-field :class:`CompatibilityKey` of the excluded
        manifest. Readers can verify the exact values that failed to
        match any retained group.
    reason_code : str
        Stable reason code, always
        :data:`EXCLUSION_REASON_CODE_NO_SHARED_KEY` (``"excluded_no_shared_key"``).
    differing_key_field_names : tuple[str, ...]
        The key field names where the excluded manifest's value does
        NOT match any retained group's value. For all-incompatible
        calls (``no_retained_group=True``), this lists the key fields
        that the excluded manifest does not share with any other
        manifest in the call (a strict subset of the full key).
        For mixed calls, this lists the key fields that are unique
        to the excluded manifest vs every retained group. Empty
        tuples are not produced (an excluded manifest must differ
        on at least one key field by construction).
    no_retained_group : bool
        True iff the call is all-incompatible (no other manifest in
        the call forms a multi-member group). When True, the
        ``excluded_key`` itself is the only "compared" reference; no
        retained key exists to anchor against.
    """

    excluded_segmentation_id: str
    excluded_key: dict[str, str]
    reason_code: str
    differing_key_field_names: tuple[str, ...]
    no_retained_group: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "excluded_segmentation_id": self.excluded_segmentation_id,
            "excluded_key": dict(self.excluded_key),
            "reason_code": self.reason_code,
            "differing_key_field_names": list(self.differing_key_field_names),
            "no_retained_group": self.no_retained_group,
        }


@dataclass(frozen=True)
class SizeDistributionEntry:
    """One row of size distribution inside a comparison group."""

    segmentation_id: str
    segment_id: int
    count: int
    percentage: float
    is_noise: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "segmentation_id": self.segmentation_id,
            "segment_id": self.segment_id,
            "count": self.count,
            "percentage": self.percentage,
            "is_noise": self.is_noise,
        }


@dataclass(frozen=True)
class ComparisonGroup:
    """A group of segmentations that share the same CompatibilityKey.

    Per P1-3 resolution: a group contains at least two manifests except
    in the special case of a call with exactly one input manifest
    (which produces a singleton group with the existing singleton note).
    All other singleton-by-key groupings are routed to
    :class:`ExclusionReason` instead.
    """

    compatibility_key: CompatibilityKey
    segmentations: list[SegmentationManifest] = field(default_factory=list)
    per_row_provenance: list[PerRowProvenance] = field(default_factory=list)
    size_distribution: list[SizeDistributionEntry] = field(default_factory=list)
    note: str = ""

    @property
    def is_singleton(self) -> bool:
        return len(self.segmentations) == 1


@dataclass(frozen=True)
class ComparisonReport:
    """Output of ``compare_segmentations``.

    Per P1-3 resolution: the report separates the two reason concepts:

    - ``incompatibility_reasons`` — per-row provenance diffs within a
      shared compatibility group (R-DEV-06-26).
    - ``exclusion_reasons`` — manifests excluded because their key
      has no other matching manifest in the call (R-DEV-06-26).

    Summary metadata (R-DEV-06-27):

    - ``total_input_count`` — number of unique manifests accepted by
      the call (after duplicate-input dedup by ``segmentation_id``).
    - ``total_compared_count`` — number of input manifests included in
      emitted multi-member groups (or the singleton group for a
      single-manifest call), counted once per manifest.
    - ``total_excluded_count`` — number of input manifests excluded
      from ``groups`` due to having no matching key in the call.

    Invariant (R-DEV-06-27):
    ``total_input_count == total_compared_count + total_excluded_count``.
    """

    schema_version: str
    compared_at_utc: str
    groups: list[ComparisonGroup]
    incompatibility_reasons: list[IncompatibilityReason]
    exclusion_reasons: list[ExclusionReason]
    total_input_count: int
    total_compared_count: int
    total_excluded_count: int
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "compared_at_utc": self.compared_at_utc,
            "groups": [
                {
                    "compatibility_key": g.compatibility_key.to_dict(),
                    "segmentations": [s.segmentation_id for s in g.segmentations],
                    "per_row_provenance": [p.to_dict() for p in g.per_row_provenance],
                    "size_distribution": [e.to_dict() for e in g.size_distribution],
                    "note": g.note,
                }
                for g in self.groups
            ],
            "incompatibility_reasons": [r.to_dict() for r in self.incompatibility_reasons],
            "exclusion_reasons": [r.to_dict() for r in self.exclusion_reasons],
            "total_input_count": self.total_input_count,
            "total_compared_count": self.total_compared_count,
            "total_excluded_count": self.total_excluded_count,
            "disclaimer": self.disclaimer,
        }


def _build_size_distribution(
    m: SegmentationManifest,
) -> list[SizeDistributionEntry]:
    """Build the size distribution rows for a single manifest."""
    out: list[SizeDistributionEntry] = []
    for s in m.segment_sizes:
        out.append(
            SizeDistributionEntry(
                segmentation_id=m.segmentation_id,
                segment_id=s.segment_id,
                count=s.count,
                percentage=s.percentage,
                is_noise=s.is_noise,
            )
        )
    return out


def _dedupe_manifests(
    manifests: list[SegmentationManifest],
) -> list[SegmentationManifest]:
    """Dedupe manifests by ``segmentation_id`` (preserve first occurrence).

    Duplicate paths pointing to the same manifest are common in tests
    and operator workflows; counting them once keeps the summary
    counts exact (R-DEV-06-27). Input order is preserved; the first
    occurrence of a given ``segmentation_id`` wins.
    """
    seen: set[str] = set()
    out: list[SegmentationManifest] = []
    for m in manifests:
        if m.segmentation_id in seen:
            continue
        seen.add(m.segmentation_id)
        out.append(m)
    return out


def _compute_differing_key_field_names(
    excluded_key: CompatibilityKey,
    retained_keys: list[CompatibilityKey],
) -> tuple[str, ...]:
    """List key fields where the excluded key does not match any retained key.

    A field is "differing" iff for every retained key, the value for
    that field differs from the excluded key's value. This produces an
    unambiguous, anchor-free explanation: it identifies the key
    fields that are unique to the excluded manifest vs every retained
    group. Deterministic: the order follows ``COMPATIBILITY_KEY_FIELDS``.
    """
    differing: list[str] = []
    for fname in COMPATIBILITY_KEY_FIELDS:
        excluded_val = getattr(excluded_key, fname)
        any_match = any(getattr(k, fname) == excluded_val for k in retained_keys)
        if not any_match:
            differing.append(fname)
    return tuple(differing)


def compare_segmentations(
    manifest_paths: list[Path],
    *,
    disclaimer: str = DEFAULT_COMPARISON_DISCLAIMER,
) -> ComparisonReport:
    """Partition ``manifest_paths`` by compatibility and emit groups + reasons.

    Per P1-3 resolution (2026-10-10):

    - Single-manifest call → one singleton group (existing note).
    - Multi-manifest call, ≥1 shared key (≥2 manifests share that
      key) → only multi-member groups are emitted; remaining
      manifests (with no sharing partner) are reported via
      ``exclusion_reasons``.
    - All-incompatible call (no shared key) → ``groups = []``;
      every manifest produces an ``exclusion_reason`` with
      ``no_retained_group=True``.
    - Mixed call → multi-member groups are retained; excluded
      manifests are reported via ``exclusion_reasons``; no arbitrary
      anchor is selected.
    - Per-row ``incompatibility_reasons`` continue to record
      per-row provenance diffs within a shared group (R-DEV-06-26).

    Determinism: input order is preserved; the first occurrence of a
    duplicate ``segmentation_id`` wins. Group and exclusion order
    follow input order.

    The function never ranks manifests, segments, or algorithms, and
    never emits "best", "winner", "ranking", "recommended",
    "optimal", "composite_score", "aggregate", or any banned
    business term (R-DEV-06-08 / R-DEV-06-19).

    Parameters
    ----------
    manifest_paths : list[Path]
        Paths to ``segmentation_manifest.json`` files. May contain
        duplicates (same ``segmentation_id``); duplicates are deduped
        before partitioning.
    disclaimer : str
        Mandatory disclaimer text (default
        :data:`DEFAULT_COMPARISON_DISCLAIMER`).

    Returns
    -------
    ComparisonReport
    """
    manifests: list[SegmentationManifest] = []
    for p in manifest_paths:
        manifests.append(read_segmentation_manifest(Path(p)))

    # Duplicate handling: dedupe by segmentation_id, preserve first occurrence.
    manifests = _dedupe_manifests(manifests)

    # Group by key. group_order preserves the order in which the first
    # manifest of each key was encountered (input order).
    group_order: list[CompatibilityKey] = []
    groups_dict: dict[CompatibilityKey, list[SegmentationManifest]] = {}
    for m in manifests:
        k = _extract_key(m)
        if k not in groups_dict:
            groups_dict[k] = []
            group_order.append(k)
        groups_dict[k].append(m)

    # Partition: single-manifest call keeps the singleton group; multi-manifest
    # call only keeps groups with ≥2 members.
    is_singleton_call = len(manifests) == 1
    multi_member_groups: list[tuple[CompatibilityKey, list[SegmentationManifest]]] = []
    excluded_manifests: list[SegmentationManifest] = []
    for k in group_order:
        ms = groups_dict[k]
        if len(ms) >= 2 or is_singleton_call:
            multi_member_groups.append((k, ms))
        else:
            excluded_manifests.extend(ms)

    # Build ComparisonGroup instances.
    groups: list[ComparisonGroup] = []
    for k, ms in multi_member_groups:
        per_row = [_extract_per_row_provenance(m) for m in ms]
        size_dist: list[SizeDistributionEntry] = []
        for m in ms:
            size_dist.extend(_build_size_distribution(m))
        note = "singleton — no comparison possible" if len(ms) == 1 else ""
        groups.append(
            ComparisonGroup(
                compatibility_key=k,
                segmentations=list(ms),
                per_row_provenance=per_row,
                size_distribution=size_dist,
                note=note,
            )
        )

    # Incompatibility reasons: per-row field differences WITHIN a multi-member
    # group only (R-DEV-06-26: keep distinct from exclusion reasons).
    incompat: list[IncompatibilityReason] = []
    for g in groups:
        if len(g.segmentations) < 2:
            continue
        ref = g.per_row_provenance[0]
        for prov in g.per_row_provenance[1:]:
            for fname in PER_ROW_PROVENANCE_FIELDS:
                ref_val = getattr(ref, fname)
                cand_val = getattr(prov, fname)
                if ref_val != cand_val:
                    incompat.append(
                        IncompatibilityReason(
                            segmentation_id=prov.segmentation_id,
                            field_name=fname,
                            stored_value=str(cand_val),
                            compared_value=str(ref_val),
                        )
                    )

    # Exclusion reasons: manifests without a sharing partner in a multi-manifest
    # call. Anchor-free: the ``differing_key_field_names`` field lists the
    # key fields that are unique to the excluded manifest vs every retained
    # group (or vs every other manifest when all-incompatible).
    retained_keys: list[CompatibilityKey] = [k for k, _ in multi_member_groups]
    no_retained_group = len(retained_keys) == 0
    exclusion_reasons: list[ExclusionReason] = []
    for excluded in excluded_manifests:
        excluded_key_obj = _extract_key(excluded)
        differing = _compute_differing_key_field_names(excluded_key_obj, retained_keys)
        exclusion_reasons.append(
            ExclusionReason(
                excluded_segmentation_id=excluded.segmentation_id,
                excluded_key=excluded_key_obj.to_dict(),
                reason_code=EXCLUSION_REASON_CODE_NO_SHARED_KEY,
                differing_key_field_names=differing,
                no_retained_group=no_retained_group,
            )
        )

    # Summary counts (R-DEV-06-27).
    total_input_count = len(manifests)
    total_compared_count = sum(len(g.segmentations) for g in groups)
    total_excluded_count = len(excluded_manifests)

    return ComparisonReport(
        schema_version="1.0.0",
        compared_at_utc="",
        groups=groups,
        incompatibility_reasons=incompat,
        exclusion_reasons=exclusion_reasons,
        total_input_count=total_input_count,
        total_compared_count=total_compared_count,
        total_excluded_count=total_excluded_count,
        disclaimer=disclaimer,
    )
