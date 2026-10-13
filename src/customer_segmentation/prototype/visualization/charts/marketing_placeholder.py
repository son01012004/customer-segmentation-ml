"""Marketing placeholder chart for DEV-08 Prototype Visualization.

The marketing section of the dashboard is a **placeholder** by design
(per the DEV-07 Phase A contract and the DEV-08 implementation plan).
This module renders only:

- A "REVIEW_REQUIRED" banner in text output when
  ``manifest.availability == "REVIEW_REQUIRED"`` (Phase A default).
- A "NOT_AVAILABLE" banner when ``manifest.availability ==
  "NOT_AVAILABLE"`` for any segment.
- A short status block when ``manifest.availability ==
  "AVAILABLE"`` (Phase B future).

The dashboard MUST NOT generate actual marketing content. The
placeholder only reflects the availability status of the input
manifest and never infers recommendations, KPIs, or business
actions.

Hard rules
----------
- Only fields present in the existing DEV-07
  :class:`MarketingRecommendationManifest` are read.
- No banned word appears outside the disclaimer phrase.
- No composite ranking, no "best segment", no recommendation content.
- The Phase A behavior is preserved when the marketing manifest is
  absent or when ``availability == REVIEW_REQUIRED``.
- When ``marketing_section == "hidden"`` is selected in the DEV-08
  config, the chart returns an empty string and a SKIPPED status;
  no marketing output is emitted at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    DEFAULT_DISCLAIMER_TEXT,
)

if TYPE_CHECKING:
    from customer_segmentation.prototype.marketing.manifest import (
        MarketingRecommendationManifest,
    )


__all__ = [
    "REVIEW_REQUIRED_PLACEHOLDER",
    "NOT_AVAILABLE_PLACEHOLDER",
    "AVAILABLE_PLACEHOLDER",
    "format_marketing_placeholder",
    "is_marketing_placeholder_visible",
]


# ---------------------------------------------------------------------------
# Placeholder texts (Phase A defaults)
# ---------------------------------------------------------------------------

# Single-line placeholder used as the section banner when the
# marketing manifest is absent OR availability == REVIEW_REQUIRED.
REVIEW_REQUIRED_PLACEHOLDER: Final[str] = (
    "Marketing recommendations: REVIEW_REQUIRED "
    "(per DEV-07 Phase A contract; MKT-01..05 framework pending; "
    "see docs/system/DEV-07_phase_b_decision_memo.md)."
)

# Placeholder used when availability == NOT_AVAILABLE (per-segment).
NOT_AVAILABLE_PLACEHOLDER: Final[str] = (
    "Marketing recommendations: NOT_AVAILABLE "
    "(per-segment; see manifest.availability for details)."
)

# Placeholder used when availability == AVAILABLE (Phase B future;
# never auto-populated in DEV-08).
AVAILABLE_PLACEHOLDER: Final[str] = (
    "Marketing recommendations: AVAILABLE "
    "(Phase B; content is owned by DEV-07 and surfaced read-only by DEV-08)."
)


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


def is_marketing_placeholder_visible(availability_status: str) -> bool:
    """Return True if the placeholder should be rendered for this availability.

    All availability statuses yield a visible placeholder; this helper
    exists so callers can decide whether to render the section at all
    (when the marketing manifest is absent) versus emit the placeholder
    (when the manifest exists but content is gated).
    """
    if not isinstance(availability_status, str) or not availability_status:
        raise VisualizationError(
            "availability_status must be a non-empty str; " f"got {availability_status!r}."
        )
    return True


def format_marketing_placeholder(
    manifest: MarketingRecommendationManifest | None,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
    marketing_section: str = "placeholder",
    separator: str = "  ",
) -> str:
    """Return the marketing placeholder text for the dashboard.

    Parameters
    ----------
    manifest : MarketingRecommendationManifest or None
        The DEV-07 marketing manifest. ``None`` is permitted and
        triggers the REVIEW_REQUIRED branch (Phase A behavior).
    disclaimer : str
        Disclaimer text appended at the end. Must contain the banned
        substrings.
    marketing_section : str
        Config setting: ``"placeholder"`` (default; render the banner)
        or ``"hidden"`` (emit nothing).
    separator : str
        Column separator for the table.

    Returns
    -------
    str
        Multi-line plain-text table.

    Raises
    ------
    VisualizationError
        If ``marketing_section`` is not a recognised value.

    Notes
    -----
    - When the marketing manifest is ``None`` (DEV-07 never ran), the
      placeholder reads ``REVIEW_REQUIRED`` (the most conservative
      status) — same as DEV-07 Phase A behavior.
    - When the manifest exists with ``availability ==
      REVIEW_REQUIRED``, the placeholder echoes it.
    - When the manifest exists with ``availability == NOT_AVAILABLE``
      or ``availability == AVAILABLE``, the corresponding placeholder
      is emitted. The dashboard NEVER emits actual recommendation
      content (objective, strategy, action, KPI) — that is owned by
      DEV-07 and only surfaced read-only when DEV-08 marketing
      integration is added in a future Phase B extension.
    """
    if marketing_section not in {"placeholder", "hidden"}:
        raise VisualizationError(
            f"marketing_section {marketing_section!r} is not in the closed set "
            f"{sorted(['placeholder', 'hidden'])}."
        )

    if marketing_section == "hidden":
        return ""

    if manifest is None:
        banner = REVIEW_REQUIRED_PLACEHOLDER
        availability = "REVIEW_REQUIRED"
        n_recommendations = 0
        n_with = 0
        n_noise = 0
        n_not_available = 0
        mkt_framework_found = False
    else:
        availability = str(manifest.availability)
        if availability == "REVIEW_REQUIRED":
            banner = REVIEW_REQUIRED_PLACEHOLDER
        elif availability == "NOT_AVAILABLE":
            banner = NOT_AVAILABLE_PLACEHOLDER
        elif availability == "AVAILABLE":
            banner = AVAILABLE_PLACEHOLDER
        else:
            # Unknown availability: render REVIEW_REQUIRED as the safe default.
            banner = REVIEW_REQUIRED_PLACEHOLDER
        n_recommendations = len(manifest.recommendations)
        n_with = int(manifest.n_segments_with_recommendation)
        n_noise = int(manifest.n_segments_noise)
        n_not_available = int(manifest.n_segments_not_available)
        mkt_framework_found = bool(manifest.mkt_framework_found)

    lines: list[str] = []
    lines.append("# Marketing Section")
    lines.append("# " + "=" * 78)
    lines.append(f"# status          : {availability}")
    lines.append(f"# mkt_framework_found : {mkt_framework_found}")
    lines.append(
        f"# n_recommendations : {n_recommendations}  "
        f"(n_with={n_with}, n_not_available={n_not_available}, "
        f"n_noise={n_noise})"
    )
    lines.append("# " + "-" * 78)
    lines.append(banner)
    lines.append("# " + "-" * 78)
    lines.append(
        "The dashboard does not generate marketing content. The DEV-08 "
        "placeholder reflects only the marketing manifest's availability "
        "status; no per-segment recommendation, KPI, or business action "
        "is emitted. Per AGENTS.md §3 the dashboard does not run DEV-07 "
        "Phase B mapping."
    )
    lines.append("")
    lines.append(f"Disclaimer: {disclaimer}")
    return "\n".join(lines)
