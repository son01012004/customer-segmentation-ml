"""Scope, stage, and closed-set constants for DEV-07 Prototype Marketing.

DEV-07 defines:

- :class:`MarketingScope`: the scope of a marketing artefact (always
  ``MARKETING_PROTOTYPE``).
- :class:`MarketingStage`: the closed 7-value enum of pipeline stages
  (A → G) for per-stage logging + observability. (One fewer than
  DEV-06's 8 stages because DEV-07 has no characteristics step.)
- :class:`AvailabilityStatus`: the closed 3-value enum for
  ``availability`` per SYS-03 §15.1 (AVAILABLE / NOT_AVAILABLE /
  REVIEW_REQUIRED).
- :data:`MARKETING_MANIFEST_SCHEMA_VERSION`: pinned manifest schema
  version.
- :data:`KPI_BLOCKLIST`: internal clustering metrics that MUST NOT
  appear in ``kpi`` (FR-MKT-05, CON-07).
- :data:`FORBIDDEN_MARKETING_TERMS`: terminology that MUST NOT appear
  in DEV-07 output text (CP-04 §4.4, FR-SEG-08, AGENTS.md §2.5).

Hard rules
----------
- :class:`MarketingScope` has exactly ONE value:
  ``MARKETING_PROTOTYPE``. The pipeline never exposes a way to change
  it.
- :class:`MarketingStage` enumerates exactly 7 stages ``A`` → ``G``
  in canonical order.
- :class:`AvailabilityStatus` mirrors SYS-03 §15.1 closed set.
- :data:`KPI_BLOCKLIST` is closed; do NOT add entries without an ADR
  + a schema-version bump.
- :data:`FORBIDDEN_MARKETING_TERMS` is closed; do NOT add entries
  without an ADR (per CP-04 §4.4, FR-SEG-08).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

__all__ = [
    "MarketingScope",
    "MARKETING_SCOPES",
    "MarketingStage",
    "MARKETING_STAGES",
    "AvailabilityStatus",
    "AVAILABILITY_STATUSES",
    "DEFAULT_AVAILABILITY",
    "NOISE_POLICIES",
    "MARKETING_MANIFEST_SCHEMA_VERSION",
    "KPI_BLOCKLIST",
    "KPI_BLOCKLIST_DISPLAY",
    "FORBIDDEN_MARKETING_TERMS",
    "MARKETING_PENDING_PLACEHOLDER",
    "MARKETING_LIMITATION_TEXT",
]


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class MarketingScope(StrEnum):
    """Scope of a marketing artefact in the prototype storage layer.

    Attributes
    ----------
    MARKETING_PROTOTYPE : str
        The only value currently in use. Implies that the artefact was
        produced by the DEV-07 pipeline on a DEV-06 segmentation
        output. It is **not** a research artefact; it has not been
        promoted by the research methodology.
    """

    MARKETING_PROTOTYPE = "MARKETING_PROTOTYPE"


MARKETING_SCOPES: Final[frozenset[str]] = frozenset(s.value for s in MarketingScope)


# ---------------------------------------------------------------------------
# Marketing pipeline stages (7-value closed enum)
# ---------------------------------------------------------------------------


class MarketingStage(StrEnum):
    """The closed 7-value enum of pipeline stages (per-stage logging).

    Canonical order A → G:

    - **A (preflight)** — load DEV-07 config; resolve storage root.
    - **B (lookup)** — locate DEV-06 ``SegmentationManifest`` (by
      ``segmentation_id`` regex or explicit path).
    - **C (validation)** — input contract + research_safety + noise
      exclusion gate. Build :class:`MarketingValidationReport`.
    - **D (recommendation build)** — per-segment recommendation entry
      builder (Phase A: REVIEW_REQUIRED shell only).
    - **E (manifest write)** — atomic write
      ``marketing_manifest.json``.
    - **F (publish)** — atomic ``os.rename(staging → final)``.
    - **G (finalize)** — flush + close log handlers.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


MARKETING_STAGES: Final[frozenset[str]] = frozenset(s.value for s in MarketingStage)


# ---------------------------------------------------------------------------
# Availability status (SYS-03 §15.1 E-MKT.availability closed set)
# ---------------------------------------------------------------------------


# Literal type for static type-checking.
AvailabilityStatus = Literal["AVAILABLE", "NOT_AVAILABLE", "REVIEW_REQUIRED"]

AVAILABILITY_STATUSES: Final[frozenset[str]] = frozenset(
    {"AVAILABLE", "NOT_AVAILABLE", "REVIEW_REQUIRED"}
)

# Phase A default (MKT-01..05 absent → gate active per SYS-01 §6.7
# FR-MKT-01, SYS-04 §15.1).
DEFAULT_AVAILABILITY: Final[str] = "REVIEW_REQUIRED"

# Mirror DEV-04/05/06 closed set: include / exclude / n/a.
NOISE_POLICIES: Final[frozenset[str]] = frozenset({"include", "exclude", "n/a"})


# ---------------------------------------------------------------------------
# Manifest schema version
# ---------------------------------------------------------------------------

# Bump this when the manifest schema changes incompatibly. The
# ``marketing_id`` derivation includes schema_version, so a bump
# automatically invalidates old ``marketing_id``s and forces re-run.
MARKETING_MANIFEST_SCHEMA_VERSION: Final[str] = "1.0.0"


# ---------------------------------------------------------------------------
# KPI blocklist (FR-MKT-05, CON-07)
# ---------------------------------------------------------------------------

# Internal clustering metrics that MUST NOT appear in the ``kpi`` field
# of any :class:`MarketingRecommendationEntry`. Phase A: ``kpi=None``
# so the blocklist is automatically respected; enforcement remains in
# validation so it carries over to Phase B.
#
# Both canonical and common aliases are listed.
KPI_BLOCKLIST: Final[frozenset[str]] = frozenset(
    {
        # Silhouette
        "silhouette_score",
        "silhouette",
        # Davies-Bouldin
        "davies_bouldin_index",
        "davies_bouldin",
        "dbi",
        # Calinski-Harabasz
        "calinski_harabasz_index",
        "calinski_harabasz",
        "ch",
        "vrc",
        # WCSS / inertia
        "wcss",
        "inertia",
        # ARI / AMI
        "ari",
        "adjusted_rand_index",
        "ami",
        "adjusted_mutual_info_score",
        # Runtime
        "runtime",
        "execution_time",
        "fit_time",
        # Catch-all
        "internal_metrics",
    }
)

KPI_BLOCKLIST_DISPLAY: Final[str] = (
    "silhouette, davies_bouldin, calinski_harabasz, wcss, ari, ami, " "runtime, fit_time, inertia"
)


# ---------------------------------------------------------------------------
# Forbidden marketing terminology (CP-04 §4.4, FR-SEG-08, AGENTS.md §2.5)
# ---------------------------------------------------------------------------

# Words that MUST NOT appear in DEV-07 output text. The mandatory
# disclaimer phrase is the single allowed occurrence of any
# overlapping tokens.
FORBIDDEN_MARKETING_TERMS: Final[frozenset[str]] = frozenset(
    {
        # Business / segment naming (CP-04 §4.4 hard NO)
        "champion",
        "loyal",
        "vip",
        "at-risk",
        "at risk",
        "churn",
        # Customer-lifetime metrics
        "ltv",
        "clv",
        # Composite business labels
        "high-value customer",  # beyond the standard "high-value" term
        # Promotion / campaign language (CP-05 §10.4)
        "target campaign",
        "campaign target",
        # Priority / ranking language
        "priority band",
        "priority segment",
    }
)


# ---------------------------------------------------------------------------
# Placeholder text (Phase A only)
# ---------------------------------------------------------------------------

# Used in marketing_objective / strategy / recommended_action /
# limitation fields when MKT framework is absent.
MARKETING_PENDING_PLACEHOLDER: Final[str] = "PENDING_MKT_FRAMEWORK"

# Carry-over limitation text for Phase A.
MARKETING_LIMITATION_TEXT: Final[str] = (
    "Marketing framework (MKT-01..MKT-05) not implemented in this "
    "prototype scope. Recommendation is descriptive only; do not "
    "interpret as a business action."
)
