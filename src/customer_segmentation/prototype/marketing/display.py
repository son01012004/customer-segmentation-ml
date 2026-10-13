"""Display helpers for DEV-07 Prototype Marketing.

Provides printable text tables for:

- :func:`format_recommendations_table` — per-segment recommendation
  view (Phase A read-only manifest).
- :func:`format_marketing_summary` — manifest-level summary.
- :func:`format_manifest_path` — run directory display.

Display discipline
-------------------
- Stdlib ``textwrap`` only — no new dependencies.
- The mandatory disclaimer phrase is the single allowed occurrence
  of any of the banned substrings in DEV-07 output. The disclaimer
  may only be embedded in the summary table footer; per-segment
  rows MUST NOT contain banned marketing terms.
- No internal clustering metric names appear anywhere (FR-MKT-05).
"""

from __future__ import annotations

import re
import textwrap
from typing import Any, Final

from customer_segmentation.prototype.marketing.manifest import (
    MarketingRecommendationManifest,
    check_forbidden_marketing_terms,
)

__all__ = [
    "DEFAULT_DISCLAIMER_TEXT",
    "BANNED_SUBSTRINGS",
    "BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER",
    "check_no_banned_substrings",
    "format_recommendations_table",
    "format_marketing_summary",
    "format_manifest_path",
]


DEFAULT_DISCLAIMER_TEXT: Final[str] = (
    "no marketing recommendation, ranking, or winner annotation is emitted; "
    "descriptive view only"
)

# Words / phrases that MUST NOT appear in DEV-07 display output
# (per AGENTS.md §2.5, CP-04 §4.4, FR-SEG-08, FR-MKT-05). The
# disclaimer phrase is the single allowed occurrence.
BANNED_SUBSTRINGS: Final[tuple[str, ...]] = (
    # Research-decision / composite language
    "best",
    "winner",
    "optimal",
    "ranking",
    "composite_score",
    "aggregate",
    # Business / segment naming
    "champion",
    "loyal",
    "vip",
    "at-risk",
    "at risk",
    "churn",
    "ltv",
    "clv",
    # Internal clustering metrics
    "silhouette",
    "davies_bouldin",
    "calinski_harabasz",
    "wcss",
    "inertia",
    "ari",
    "ami",
    # Priority / campaign language
    "campaign target",
    "priority band",
)


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
    reported.
    """
    found: list[str] = []
    check_text = _strip_disclaimer(text, disclaimer)
    for banned in BANNED_SUBSTRINGS:
        pattern = r"\b" + re.escape(banned).replace("\\-", r"[-\s]") + r"\b"
        if re.search(pattern, check_text, flags=re.IGNORECASE):
            found.append(banned)
    return found


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _row(*cells: str) -> str:
    return "  ".join(cells)


def format_recommendations_table(
    manifest: MarketingRecommendationManifest,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
) -> str:
    """Format a human-readable per-segment recommendation table.

    Returns a multi-line string. No banned substrings appear outside
    the disclaimer footer.
    """
    lines: list[str] = []
    lines.append(
        f"Marketing recommendations (manifest {manifest.marketing_id}, "
        f"availability={manifest.availability}, mkt_framework_found="
        f"{manifest.mkt_framework_found})"
    )
    lines.append("")
    lines.append(
        _row(
            "seg_id",
            "cluster_label",
            "recommendation_id",
            "availability",
            "kpi",
            "is_interp_ready",
        )
    )
    lines.append(_row("-" * 6, "-" * 12, "-" * 50, "-" * 16, "-" * 6, "-" * 16))
    for r in manifest.recommendations:
        kpi_str = "None" if r.kpi is None else ",".join(r.kpi)
        is_ready = "n/a" if r.is_interpretation_ready is None else str(r.is_interpretation_ready)
        lines.append(
            _row(
                str(r.segment_id),
                str(r.cluster_label),
                r.recommendation_id,
                r.availability,
                kpi_str,
                is_ready,
            )
        )
    lines.append("")
    lines.append(f"Disclaimer: {disclaimer}")
    text = "\n".join(lines)
    # Defence-in-depth: ensure no banned substrings outside disclaimer.
    bad = check_no_banned_substrings(text, disclaimer=disclaimer)
    if bad:
        raise ValueError(
            f"DEV-07 display output contains banned substrings: {bad}. "
            f"This is a programming error; check display code for "
            f"forbidden-term leakage."
        )
    return text


def format_marketing_summary(
    manifest: MarketingRecommendationManifest,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
) -> str:
    """Format a manifest-level summary table."""
    lines: list[str] = []
    lines.append(_row("field", "value"))
    lines.append(_row("-" * 24, "-" * 64))
    lines.append(_row("marketing_id", manifest.marketing_id))
    lines.append(_row("segmentation_id", manifest.segmentation_id))
    lines.append(_row("clustering_id", manifest.clustering_id))
    lines.append(_row("dataset_id", manifest.dataset_id))
    lines.append(_row("availability", manifest.availability))
    lines.append(
        _row(
            "source_framework_version",
            str(manifest.source_framework_version) if manifest.source_framework_version else "null",
        )
    )
    lines.append(_row("mkt_framework_found", str(manifest.mkt_framework_found)))
    lines.append(_row("n_segments_input", str(manifest.n_segments_input)))
    lines.append(
        _row("n_segments_with_recommendation", str(manifest.n_segments_with_recommendation))
    )
    lines.append(_row("n_segments_noise", str(manifest.n_segments_noise)))
    lines.append(_row("n_segments_not_available", str(manifest.n_segments_not_available)))
    lines.append(_row("noise_policy_used", manifest.noise_policy_used))
    lines.append(_row("schema_version", manifest.schema_version))
    lines.append(
        _row(
            "research_safety.scope",
            manifest.research_safety.scope,
        )
    )
    lines.append(
        _row(
            "research_safety.promoted",
            str(manifest.research_safety.automatically_promoted_to_research),
        )
    )
    lines.append(
        _row(
            "research_safety.in_evidence",
            str(manifest.research_safety.appeared_in_research_evidence),
        )
    )
    lines.append("")
    lines.append(f"Disclaimer: {disclaimer}")
    text = "\n".join(lines)
    bad = check_no_banned_substrings(text, disclaimer=disclaimer)
    if bad:
        raise ValueError(
            f"DEV-07 display output contains banned substrings: {bad}. "
            f"This is a programming error."
        )
    return text


def format_manifest_path(
    manifest: MarketingRecommendationManifest,
) -> str:
    """Return the canonical on-disk path string for the manifest."""
    return (
        f"{manifest.input_segmentation_manifest}::marketing/{manifest.marketing_id}/"
        f"marketing_manifest.json"
    )
