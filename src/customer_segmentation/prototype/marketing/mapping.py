"""DEV-07 Phase B mapping scaffolding.

This module implements the **scaffolding** for the Phase B
``Segment → MKT template`` mapping. It does NOT generate business
content; it provides:

- A closed set of template slot names (no synthesis).
- A function :func:`resolve_template_slots` that consumes:
    - a :class:`~customer_segmentation.prototype.marketing.tokenization.CP04TokenizationResult`
      (parsed segment name tokens from CP-04 §4.1-§4.3),
    - a :class:`~customer_segmentation.prototype.marketing.mkt_framework_loader.MktFrameworkStructure`
      (structural metadata; no business content),
- and returns a :class:`TemplateSlots` object describing **which
  slots would be filled by MKT-02/MKT-03/MKT-04/MKT-05 content** —
  but with ``None`` placeholders, awaiting owner-approved MKT
  framework content.

Hard rules
----------
- **No synthesis of objective / strategy / action / KPI / limitation
  text**. All such fields are explicitly ``None`` until owner approval
  + MKT framework content is available (OQ-D07-01).
- The scaffolding is a pure function of (tokenization, structure);
  no I/O, no datetime, no randomness.
- The slot-name closed set is part of the contract; additions
  require an ADR + schema version bump.
- This module does NOT populate :class:`MarketingRecommendationEntry`
  fields. The wiring lives in
  :mod:`customer_segmentation.prototype.marketing.recommendation`
  and is intentionally conservative (falls back to Phase A
  REVIEW_REQUIRED when MKT content is unavailable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from customer_segmentation.prototype.marketing.mkt_framework_loader import (
    MktFrameworkStructure,
)
from customer_segmentation.prototype.marketing.tokenization import (
    CP04TokenizationResult,
)

__all__ = [
    "TEMPLATE_SLOT_NAMES",
    "TemplateSlots",
    "resolve_template_slots",
    "is_template_resolved",
]


# ---------------------------------------------------------------------------
# Closed set of template slot names (matches SYS-03 §15.1 E-MKT fields)
# ---------------------------------------------------------------------------

# The 5 template-style fields in SYS-03 §15.1 E-MKT that map to MKT
# framework content (Objective / Strategy / Action / KPI / Limitation).
# Plus ``evidence_ref`` (auto-populated, no MKT lookup needed).
TEMPLATE_SLOT_NAMES: Final[frozenset[str]] = frozenset(
    {"marketing_objective", "strategy", "recommended_action", "kpi", "limitation"}
)


# ---------------------------------------------------------------------------
# Template slots dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemplateSlots:
    """Mapping scaffolding result.

    Each field is either:
    - ``None`` (slot unresolved — no MKT content available), OR
    - populated by MKT framework content (Phase B after owner approval).

    This dataclass carries the **slot structure** only. Business
    content (objective text, strategy text, KPI list, limitation
    text) is NOT synthesized here.

    Attributes
    ----------
    mkt_framework_version : str or None
        Framework version (e.g. ``"v1"``) when structure is loaded.
    cp04_segment_name : str
        The original CP-04 segment name (verbatim).
    cp04_tokens_match : bool
        Result of :class:`CP04TokenizationResult.tier_match` for the
        input. False for COMPARATIVE / NOISE / NOT_AVAILABLE
        segments.
    marketing_objective : str or None
        MKT-02 marketing objective slot. ``None`` when MKT content is
        absent (current state, awaiting OQ-D07-01).
    strategy : str or None
        MKT-03 strategy slot. ``None`` when MKT content is absent.
    recommended_action : str or None
        MKT-03 recommended-action slot. ``None`` when MKT content is
        absent.
    kpi : tuple of str or None
        MKT-04 KPI definitions slot. ``None`` when MKT content is
        absent (awaiting OQ-D07-04).
    limitation : str or None
        MKT-05 limitation framework slot. ``None`` when MKT content is
        absent.
    """

    mkt_framework_version: str | None
    cp04_segment_name: str
    cp04_tokens_match: bool
    marketing_objective: str | None
    strategy: str | None
    recommended_action: str | None
    kpi: tuple[str, ...] | None
    limitation: str | None

    def __post_init__(self) -> None:
        # All non-None fields MUST be valid types.
        if self.marketing_objective is not None and not isinstance(self.marketing_objective, str):
            raise ValueError(
                f"marketing_objective MUST be str or None; "
                f"got {type(self.marketing_objective).__name__}."
            )
        if self.strategy is not None and not isinstance(self.strategy, str):
            raise ValueError(f"strategy MUST be str or None; got {type(self.strategy).__name__}.")
        if self.recommended_action is not None and not isinstance(self.recommended_action, str):
            raise ValueError(
                f"recommended_action MUST be str or None; "
                f"got {type(self.recommended_action).__name__}."
            )
        if self.kpi is not None and (
            not isinstance(self.kpi, tuple) or not all(isinstance(k, str) for k in self.kpi)
        ):
            raise ValueError(f"kpi MUST be tuple of str or None; got {type(self.kpi).__name__}.")
        if self.limitation is not None and not isinstance(self.limitation, str):
            raise ValueError(
                f"limitation MUST be str or None; got {type(self.limitation).__name__}."
            )


# ---------------------------------------------------------------------------
# Resolution function (pure)
# ---------------------------------------------------------------------------


def resolve_template_slots(
    *,
    tokenization: CP04TokenizationResult,
    structure: MktFrameworkStructure | None,
) -> TemplateSlots:
    """Resolve template slots for one segment.

    Parameters
    ----------
    tokenization : CP04TokenizationResult
        Result of parsing the CP-04 segment name.
    structure : MktFrameworkStructure or None
        MKT framework structural metadata, or ``None`` if framework
        is absent (Phase A behaviour).

    Returns
    -------
    TemplateSlots
        Slot structure with all 5 template fields explicitly
        ``None``. The function does NOT generate any business
        content; it returns the unresolved slots. Owner approval +
        MKT framework content is required to populate them
        (OQ-D07-01, OQ-D07-04).

    Notes
    -----
    The function is intentionally **content-free**: even when
    ``structure`` is non-None, this function returns ``None`` for
    every business slot because the agent does NOT have authority to
    fabricate marketing content. The wiring code in
    :mod:`recommendation` uses the returned slots to decide whether
    to fall back to Phase A REVIEW_REQUIRED.
    """
    mkt_version = structure.version if structure is not None else None
    return TemplateSlots(
        mkt_framework_version=mkt_version,
        cp04_segment_name=tokenization.segment_name,
        cp04_tokens_match=tokenization.tier_match,
        marketing_objective=None,
        strategy=None,
        recommended_action=None,
        kpi=None,
        limitation=None,
    )


def is_template_resolved(slots: TemplateSlots) -> bool:
    """Return True iff at least one template slot is populated.

    A resolved template has at least one of
    ``marketing_objective / strategy / recommended_action / kpi /
    limitation`` populated. When this returns False, the mapping
    wiring code MUST fall back to the Phase A REVIEW_REQUIRED shell.
    """
    return (
        slots.marketing_objective is not None
        or slots.strategy is not None
        or slots.recommended_action is not None
        or slots.kpi is not None
        or slots.limitation is not None
    )
