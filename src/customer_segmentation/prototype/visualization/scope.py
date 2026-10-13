"""Scope, constants, and color-palette definitions for DEV-08 Prototype Visualization.

DEV-08 defines:
- :data:`VISUALIZATION_SCHEMA_VERSION`: pinned schema version for any
  future on-disk artefacts.
- :data:`DEFAULT_COLOR_PALETTE`: single color source for cluster
  visualization, replacing per-chart hard-coded colour choices
  (per AGENTS.md §3 "Visualization" guardrail).
- :data:`BANNED_SUBSTRINGS`: words that must not appear in
  visualization output outside the mandatory disclaimer.
- :data:`DEFAULT_DISCLAIMER_TEXT`: the single allowed occurrence
  of banned terms in DEV-08 output.

Hard rules
----------
- ``DEFAULT_COLOR_PALETTE`` is the **only** colour source for cluster
  charts. Chart modules must import from here, not hard-code hex codes.
- No banned word may appear in chart titles, axis labels, legend text,
  or table cells outside the disclaimer phrase.
- ``VISUALIZATION_SCHEMA_VERSION`` is pinned to ``"1.0.0"``. A bump
  invalidates any artefacts that depend on it.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "VISUALIZATION_SCHEMA_VERSION",
    "DEFAULT_COLOR_PALETTE",
    "BANNED_SUBSTRINGS",
    "BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER",
    "DEFAULT_DISCLAIMER_TEXT",
    "VisualizationError",
    "VisualizationStoragePathError",
    "VisualizationInputError",
    "VisualizationConfigError",
]


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

# Pin to "1.0.0" for Task 1.1 foundation. A bump will be required when
# the package emits on-disk artefacts that need content-addressing.
VISUALIZATION_SCHEMA_VERSION: Final[str] = "1.0.0"


# ---------------------------------------------------------------------------
# Colour palette (single source; replaces per-chart hard-coding)
#
# Palette is matplotlib Tab10 — perceptually uniform, colourblind-safe,
# distinct across up to 10 clusters without requiring custom mapping.
# The AGENTS.md §3 Visualization guardrail forbids hard-coding colours
# in multiple chart modules; importing from here satisfies that constraint.
# ---------------------------------------------------------------------------

DEFAULT_COLOR_PALETTE: Final[tuple[str, ...]] = (
    "#4C72B0",  # cluster 0 — blue
    "#DD8452",  # cluster 1 — orange
    "#55A868",  # cluster 2 — green
    "#C44E52",  # cluster 3 — red
    "#8172B3",  # cluster 4 — purple
    "#937860",  # cluster 5 — brown
    "#DA8BC3",  # cluster 6 — pink
    "#8C8C8C",  # cluster 7 — grey
    "#CCB974",  # cluster 8 — olive
    "#64B5CD",  # cluster 9 — cyan
)

# Noise colour for DBSCAN scatter overlays — distinct from all cluster colours.
NOISE_COLOR: Final[str] = "#AAAAAA"


# ---------------------------------------------------------------------------
# Display discipline (banned-word guardrail)
#
# Mirror the pattern established in evaluation/display.py and
# segmentation/display.py: a closed tuple of banned substrings and a
# mandatory disclaimer phrase. The disclaimer is the single allowed
# occurrence of banned terms.
# ---------------------------------------------------------------------------

DEFAULT_DISCLAIMER_TEXT: Final[str] = (
    "no ranking, recommendation, or winner annotation is emitted; "
    "values are post-preprocessing (scaled/transformed) — "
    "not directly interpretable in original business units"
)

# Words / phrases that MUST NOT appear in DEV-08 display output
# (per AGENTS.md §2.5, §3). The disclaimer phrase is the single
# allowed occurrence (negation pattern).
BANNED_SUBSTRINGS: Final[tuple[str, ...]] = (
    "best",
    "winner",
    "optimal",
    "recommended",
    "ranking",
    "composite_score",
    "aggregate",
    "champion",
    "loyal",
    "high-value",
    "at-risk",
    "vip",
    "churn",
)

# Backwards-compatible alias.
BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER: Final[tuple[str, ...]] = BANNED_SUBSTRINGS


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class VisualizationError(ValueError):
    """Raised on visualization construction, I/O, or invariant failures."""


class VisualizationStoragePathError(ValueError):
    """Raised on path / storage resolution failures (DEV-08 storage layer)."""


class VisualizationInputError(ValueError):
    """Raised on invalid CLI / user-supplied input for DEV-08."""


class VisualizationConfigError(ValueError):
    """Raised on invalid or missing DEV-08 config payloads."""
