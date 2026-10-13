"""Display helpers for DEV-06 Prototype Segmentation.

Provides printable text tables for:

- :func:`format_segments_table` — AC-1 (segment list)
- :func:`format_sizes_table` — AC-2 (segment size)
- :func:`format_profiles_table` — AC-4 (per-segment feature profile)
- :func:`format_characteristics_table` — AC-3 (per-segment characteristics)
- :func:`format_comparison_table` — AC-5 (side-by-side comparison)

Display discipline
-------------------
- No new dependencies (OQ-SEG-DEPENDENCY-01). Stdlib ``textwrap`` only.
- No "best" / "winner" / "optimal" / "recommended" / "ranking" /
  "composite_score" / "VIP" / "champion" / "loyal" / "high-value" /
  "at-risk" / "churn" / "marketing" outside the disclaimer
  (R-DEV-06-08 / R-DEV-06-18 / R-DEV-06-19).
- The mandatory disclaimer phrase is the single allowed occurrence of
  those substrings in DEV-06 output.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any, Final

from customer_segmentation.prototype.segmentation.compare import (
    ComparisonReport,
)
from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    FeatureProfile,
    SegmentationManifest,
    SegmentSize,
)

__all__ = [
    "DEFAULT_DISCLAIMER_TEXT",
    "BANNED_SUBSTRINGS",
    "BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER",
    "check_no_banned_substrings",
    "format_segments_table",
    "format_sizes_table",
    "format_profiles_table",
    "format_characteristics_table",
    "format_comparison_table",
    "format_manifest_path",
]


DEFAULT_DISCLAIMER_TEXT: Final[str] = (
    "no ranking, recommendation, or winner annotation is emitted; "
    "descriptive comparison only; values are post-preprocessing"
)


# Words / phrases that MUST NOT appear in DEV-06 display output
# (R-DEV-06-08, R-DEV-06-18, R-DEV-06-19).
# The disclaimer phrase is the single allowed occurrence (negation pattern).
BANNED_SUBSTRINGS: Final[tuple[str, ...]] = (
    # Research-decision / composite language
    "best",
    "winner",
    "optimal",
    "recommended",
    "ranking",
    "composite_score",
    "aggregate",
    # Business / segment naming
    "champion",
    "loyal",
    "high-value",
    "at-risk",
    "vip",
    "churn",
    "marketing",
)


# Backwards-compatible alias.
BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER: Final[tuple[str, ...]] = BANNED_SUBSTRINGS


def _strip_disclaimer(text: str, disclaimer: str) -> str:
    """Remove all occurrences of ``disclaimer`` from ``text`` (case-insensitive)."""
    if not disclaimer:
        return text
    lower = text.lower()
    dl_lower = disclaimer.lower()
    out = text
    while dl_lower in lower:
        idx = lower.index(dl_lower)
        out = out[:idx] + out[idx + len(dl_lower) :]
        lower = out.lower()
    return out


def check_no_banned_substrings(
    text: str,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
) -> list[str]:
    """Return the list of banned substrings present in ``text``.

    The disclaimer phrase is excluded from the check. Any other
    occurrence of a banned word (case-insensitive, word-boundary) is
    reported. Per R-DEV-06-08 / R-DEV-06-18 / R-DEV-06-19.
    """
    found: list[str] = []
    check_text = _strip_disclaimer(text, disclaimer)
    for banned in BANNED_SUBSTRINGS:
        # \b matches at word boundaries; handle "-" within "high-value" /
        # "at-risk" by treating them as part of the word.
        # Replace "-" with optional whitespace in pattern.
        pattern = r"\b" + re.escape(banned).replace("\\-", r"[-\s]") + r"\b"
        if re.search(pattern, check_text, flags=re.IGNORECASE):
            found.append(banned)
    return found


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _row(*cells: str) -> str:
    return "  ".join(cells)


def format_segments_table(
    manifest: SegmentationManifest,
    *,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable table of segments (id, size, percentage, is_noise).

    Per AC-1 (Display segments). Includes both non-noise and noise
    rows; noise row uses ``is_noise=True`` flag.
    """
    lines: list[str] = []
    lines.append(
        _row(
            "segment_id".ljust(12),
            "count".rjust(8),
            "pct".rjust(10),
            "pct_of_non_noise".rjust(18),
            "is_noise".rjust(10),
        )
    )
    lines.append("-" * 70)
    for s in manifest.segment_sizes:
        # Compute secondary percentage (non-noise) on the fly.
        if s.is_noise:
            pct_nn_str = missing_value_placeholder
        else:
            denom = manifest.n_samples_used_for_compute
            if denom > 0:
                pct_nn = round(s.count / denom * 100.0, 2)
                pct_nn_str = f"{pct_nn:.2f}"
            else:
                pct_nn_str = missing_value_placeholder
        lines.append(
            _row(
                str(s.segment_id).ljust(12),
                str(s.count).rjust(8),
                f"{s.percentage:.2f}".rjust(10),
                pct_nn_str.rjust(18),
                str(s.is_noise).rjust(10),
            )
        )
    lines.append("")
    lines.append(f"n_samples_input={manifest.n_samples_input}")
    lines.append(f"n_samples_used_for_compute={manifest.n_samples_used_for_compute}")
    lines.append(f"n_clusters_input={manifest.n_clusters_input}")
    lines.append(f"n_segments={manifest.n_segments}")
    if manifest.noise_count is not None:
        lines.append(f"noise_count={manifest.noise_count}")
    if manifest.noise_ratio is not None:
        lines.append(f"noise_ratio={manifest.noise_ratio:.4f}")
    return "\n".join(lines)


def format_sizes_table(
    segment_sizes: list[SegmentSize],
    *,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable table of segment sizes (AC-2).

    Filters out noise (per AC-2 — Display size of real segments).
    """
    lines: list[str] = []
    lines.append(_row("segment_id".ljust(12), "count".rjust(8)))
    lines.append("-" * 22)
    for s in segment_sizes:
        if s.is_noise:
            continue
        lines.append(_row(str(s.segment_id).ljust(12), str(s.count).rjust(8)))
    if not any(not s.is_noise for s in segment_sizes):
        lines.append(missing_value_placeholder)
    return "\n".join(lines)


def format_profiles_table(
    profiles: list[FeatureProfile],
    *,
    segment_id: int | None = None,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable table of per-segment feature profiles (AC-4).

    Parameters
    ----------
    profiles : list[FeatureProfile]
        Per-segment feature profiles.
    segment_id : int, optional
        If set, only rows for that segment are shown.
    missing_value_placeholder : str
        Placeholder for None values.
    """
    selected = (
        [p for p in profiles if p.segment_id == segment_id]
        if segment_id is not None
        else list(profiles)
    )
    lines: list[str] = []
    lines.append(
        _row(
            "segment_id".ljust(12),
            "feature_name".ljust(24),
            "statistic".ljust(20),
            "value".rjust(20),
        )
    )
    lines.append("-" * 80)
    for p in selected:
        for stat_name, stat_value in p.statistics.items():
            if isinstance(stat_value, list):
                value_str = "|".join(f"{cat}:{count}" for cat, count in stat_value)
            elif isinstance(stat_value, dict):
                value_str = ";".join(f"{k}:{v}" for k, v in stat_value.items())
            elif stat_value is None:
                value_str = missing_value_placeholder
            else:
                value_str = str(stat_value)
            lines.append(
                _row(
                    str(p.segment_id).ljust(12),
                    p.feature_name.ljust(24),
                    stat_name.ljust(20),
                    value_str.rjust(20),
                )
            )
    return "\n".join(lines)


def format_characteristics_table(
    characteristics: list[CharacteristicEntry],
    *,
    segment_id: int | None = None,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable table of per-segment characteristics (AC-3).

    Per R-DEV-06-19, characteristic IDs and descriptions are
    descriptive only — never business labels. The table structure
    explicitly shows the rule + supporting stats.
    """
    lines: list[str] = []
    lines.append(
        _row(
            "characteristic_id".ljust(36),
            "description".ljust(50),
            "source_features".ljust(20),
        )
    )
    lines.append("-" * 110)
    for c in characteristics:
        desc = textwrap.shorten(c.description, width=48, placeholder="...")
        lines.append(
            _row(
                c.characteristic_id.ljust(36),
                desc.ljust(50),
                ",".join(c.source_features).ljust(20),
            )
        )
    if not characteristics:
        lines.append(missing_value_placeholder)
    return "\n".join(lines)


def format_comparison_table(
    report: ComparisonReport,
    *,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable summary of a comparison report (AC-5).

    Per P1-3 resolution (2026-10-10), the summary surfaces:

    - Top-level metadata: ``total_input_count``,
      ``total_compared_count``, ``total_excluded_count`` (R-DEV-06-27).
    - Multi-member comparison groups (groups with ≥2 manifests, plus
      the singleton group from a single-manifest call).
    - Per-row ``incompatibility_reasons`` (within-group field diffs).
    - ``exclusion_reasons`` (manifests excluded because their key
      has no sharing partner; R-DEV-06-26).

    The mandatory disclaimer is included at the end.
    """
    lines: list[str] = []
    lines.append("Comparison report")
    lines.append("=" * 60)
    lines.append(f"schema_version: {report.schema_version}")
    lines.append(f"compared_at_utc: {report.compared_at_utc or '(unset)'}")
    lines.append(f"disclaimer: {report.disclaimer}")
    lines.append("")
    lines.append("Summary")
    lines.append("-" * 60)
    lines.append(f"  total_input_count    : {report.total_input_count}")
    lines.append(f"  total_compared_count : {report.total_compared_count}")
    lines.append(f"  total_excluded_count : {report.total_excluded_count}")
    lines.append("")
    lines.append(f"groups: {len(report.groups)}")
    lines.append(f"incompatibility_reasons: {len(report.incompatibility_reasons)}")
    lines.append(f"exclusion_reasons: {len(report.exclusion_reasons)}")
    lines.append("")
    for i, g in enumerate(report.groups, start=1):
        lines.append(f"--- Group {i} (singleton={g.is_singleton}) ---")
        k = g.compatibility_key
        lines.append(f"  dataset_id: {k.dataset_id}")
        lines.append(f"  preprocessed_id: {k.preprocessed_id}")
        lines.append(f"  ml_dataset_sha256: {k.ml_dataset_sha256[:16]}...")
        lines.append(f"  feature_set_sha256: {k.feature_set_sha256[:16]}...")
        lines.append(f"  segmentations: {[s.segmentation_id for s in g.segmentations]}")
        if g.note:
            lines.append(f"  note: {g.note}")
        for prov in g.per_row_provenance:
            lines.append(
                f"    [{prov.segmentation_id}] algorithm={prov.algorithm}, "
                f"family={prov.algorithm_family}, "
                f"n_segments={prov.n_segments}, "
                f"noise_policy={prov.noise_policy_used}"
            )
        if g.size_distribution:
            lines.append("    size_distribution (first 5):")
            for entry in g.size_distribution[:5]:
                lines.append(
                    f"      [{entry.segmentation_id}] segment={entry.segment_id} "
                    f"count={entry.count} pct={entry.percentage:.2f} "
                    f"is_noise={entry.is_noise}"
                )
    if report.incompatibility_reasons:
        lines.append("")
        lines.append("--- Incompatibility reasons (per-row) ---")
        for r in report.incompatibility_reasons:
            lines.append(
                f"  [{r.segmentation_id}] {r.field_name}: "
                f"stored={r.stored_value!r} compared={r.compared_value!r}"
            )
    if report.exclusion_reasons:
        lines.append("")
        lines.append("--- Exclusion reasons (no shared key) ---")
        for r in report.exclusion_reasons:
            lines.append(
                f"  [{r.excluded_segmentation_id}] reason={r.reason_code} "
                f"no_retained_group={r.no_retained_group} "
                f"differing={list(r.differing_key_field_names)}"
            )
            if r.no_retained_group:
                lines.append(
                    f"      excluded_key: dataset_id={r.excluded_key['dataset_id']}, "
                    f"preprocessed_id={r.excluded_key['preprocessed_id']}, "
                    f"ml_dataset_sha256={r.excluded_key['ml_dataset_sha256'][:16]}..., "
                    f"feature_set_sha256={r.excluded_key['feature_set_sha256'][:16]}..."
                )
    return "\n".join(lines)


def format_manifest_path(manifest: SegmentationManifest) -> str:
    """Return a one-line summary of a segmentation manifest."""
    return (
        f"segmentation_id={manifest.segmentation_id}  "
        f"clustering_id={manifest.clustering_id}  "
        f"algorithm={manifest.algorithm}  "
        f"family={manifest.algorithm_family}  "
        f"n_samples_used={manifest.n_samples_used_for_compute}/"
        f"{manifest.n_samples_input}  "
        f"n_segments={manifest.n_segments}  "
        f"noise_policy={manifest.noise_policy_used}"
    )
