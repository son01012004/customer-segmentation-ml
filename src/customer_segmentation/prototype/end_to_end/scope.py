"""Scope, constants, and error types for DEV-09 End-to-End Prototype.

Defines the closed-set lifecycle + stage-status vocabulary used by
:mod:`customer_segmentation.prototype.end_to_end` so that every layer
(exceptions, storage, pipeline, display) speaks the same dialect.

Lifecycle vs. stage status
---------------------------
- :class:`Lifecycle` — the top-level end-to-end run lifecycle.
  Closed set: ``SUCCESS`` / ``CACHED`` / ``FAILED`` /
  ``CONDITIONAL`` / ``BLOCKED``.
- :class:`StageStatus` — the per-stage outcome. Closed set:
  ``SUCCESS`` / ``CACHED`` / ``FAILED`` / ``SKIPPED`` / ``BLOCKED``
  / ``REVIEW_REQUIRED``.

Hard rules
----------
- ``END_TO_END_SCHEMA_VERSION`` is pinned to ``"1.0.0"``. A bump
  invalidates persisted ``e2e_run.json`` files (they must be
  re-generated).
- Stage order is canonical: ``UPLOAD -> VALIDATION -> PREPROCESSING
  -> FEATURE_ENGINEERING -> ALGORITHM_SELECT -> CLUSTERING ->
  EVALUATION -> SEGMENTATION -> CUSTOMER_PROFILE -> MARKETING ->
  VISUALIZATION``.
- Marketing's ``REVIEW_REQUIRED`` semantics from DEV-07 Phase A are
  preserved as ``StageStatus.REVIEW_REQUIRED``; the end-to-end
  pipeline does NOT auto-relax this default.
- ``BANNED_SUBSTRINGS`` is the closed set of forbidden terms (per
  AGENTS.md §2.5, mirrored from the visualization package).
"""

from __future__ import annotations

from enum import Enum
from typing import Final

__all__ = [
    "END_TO_END_SCHEMA_VERSION",
    "E2E_ID_PREFIX",
    "E2E_ID_HEX_LEN",
    "E2E_STAGE_ORDER",
    "E2EStage",
    "Lifecycle",
    "StageStatus",
    "BANNED_SUBSTRINGS",
    "DEFAULT_DISCLAIMER_TEXT",
    "Dev09Error",
    "Dev09InputError",
    "Dev09ConfigError",
    "Dev09StoragePathError",
]


# ---------------------------------------------------------------------------
# Schema version (pinned)
# ---------------------------------------------------------------------------

END_TO_END_SCHEMA_VERSION: Final[str] = "1.0.0"


# ---------------------------------------------------------------------------
# e2e_run_id derivation
# ---------------------------------------------------------------------------

E2E_ID_PREFIX: Final[str] = "e2e_"
E2E_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy


# ---------------------------------------------------------------------------
# Stage enum and canonical order
# ---------------------------------------------------------------------------


class E2EStage(str, Enum):
    """Canonical end-to-end pipeline stages (close set)."""

    UPLOAD = "UPLOAD"
    VALIDATION = "VALIDATION"
    PREPROCESSING = "PREPROCESSING"
    FEATURE_ENGINEERING = "FEATURE_ENGINEERING"
    ALGORITHM_SELECT = "ALGORITHM_SELECT"
    CLUSTERING = "CLUSTERING"
    EVALUATION = "EVALUATION"
    SEGMENTATION = "SEGMENTATION"
    CUSTOMER_PROFILE = "CUSTOMER_PROFILE"
    MARKETING = "MARKETING"
    VISUALIZATION = "VISUALIZATION"


E2E_STAGE_ORDER: Final[tuple[E2EStage, ...]] = (
    E2EStage.UPLOAD,
    E2EStage.VALIDATION,
    E2EStage.PREPROCESSING,
    E2EStage.FEATURE_ENGINEERING,
    E2EStage.ALGORITHM_SELECT,
    E2EStage.CLUSTERING,
    E2EStage.EVALUATION,
    E2EStage.SEGMENTATION,
    E2EStage.CUSTOMER_PROFILE,
    E2EStage.MARKETING,
    E2EStage.VISUALIZATION,
)


# ---------------------------------------------------------------------------
# Lifecycle (overall end-to-end run outcome)
# ---------------------------------------------------------------------------


class Lifecycle(str, Enum):
    """Top-level lifecycle of an end-to-end run."""

    SUCCESS = "SUCCESS"
    CACHED = "CACHED"
    FAILED = "FAILED"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# Stage status (per-stage outcome)
# ---------------------------------------------------------------------------


class StageStatus(str, Enum):
    """Per-stage outcome status.

    - ``SUCCESS`` — stage completed successfully.
    - ``CACHED`` — stage returned a cached / reusable result.
    - ``FAILED`` — stage raised an unrecoverable error; downstream
      stages were skipped.
    - ``SKIPPED`` — stage was deliberately not executed because a
      mandatory predecessor failed or was skipped.
    - ``BLOCKED`` — stage could not produce its full output because
      an upstream methodology decision or owned data dependency remains
      unresolved (e.g. cluster visualization 2D projection).
    - ``REVIEW_REQUIRED`` — stage emitted a manifest with an explicit
      review-required status (e.g. marketing availability ==
      REVIEW_REQUIRED).
    """

    SUCCESS = "SUCCESS"
    CACHED = "CACHED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Display discipline (banned-word guardrail)
# ---------------------------------------------------------------------------

DEFAULT_DISCLAIMER_TEXT: Final[str] = (
    "no ranking, recommendation, or winner annotation is emitted; "
    "values are post-preprocessing (scaled/transformed) — "
    "not directly interpretable in original business units"
)

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


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev09Error(RuntimeError):
    """Generic DEV-09 end-to-end pipeline failure."""


class Dev09InputError(ValueError):
    """Raised on invalid CLI / user-supplied input."""


class Dev09ConfigError(ValueError):
    """Raised on invalid or missing DEV-09 config payloads."""


class Dev09StoragePathError(ValueError):
    """Raised on storage path / id-format / containment failures."""
