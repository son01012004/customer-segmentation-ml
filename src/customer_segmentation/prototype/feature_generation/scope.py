"""Scope and outcome enums for DEV-03 Stage F (feature generation).

The package defines a small, closed set of enums / frozen sets:

- :class:`FeatureGenerationScope` - the scope of the artefact (only
  ``GENERATED_PROTOTYPE`` is used).
- :class:`FeatureGenerationStatus` - the per-feature status mirrored
  from FE-05; DEV-03 inherits verbatim.
- :class:`FeatureGenerationOutcome` - per-stage outcome.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final

__all__ = [
    "FeatureGenerationScope",
    "FeatureGenerationOutcome",
    "FeatureGenerationStatus",
    "FEATURE_GENERATION_STATUSES",
    "FEATURE_OUTCOMES",
    "generate_features",
]


class FeatureGenerationScope(StrEnum):
    """Scope of a feature-generation artefact in the prototype layer.

    Attributes
    ----------
    GENERATED_PROTOTYPE : str
        The only value currently in use; the artefact is part of the
        DEV-03 preprocessed run and is **not** research evidence.
    """

    GENERATED_PROTOTYPE = "GENERATED_PROTOTYPE"


class FeatureGenerationOutcome(StrEnum):
    """Per-stage outcome for Stage F.

    Same semantics as :class:`customer_segmentation.prototype.preprocessing.scope.PreprocessingOutcome`.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


FEATURE_OUTCOMES: Final[frozenset[str]] = frozenset(s.value for s in FeatureGenerationOutcome)


class FeatureGenerationStatus(StrEnum):
    """Per-feature status, mirrored from FE-05 selection outcomes.

    DEV-03 inherits the FE-05 status verbatim for the default
    configuration. The default for every emitted feature is
    ``WORKING_ASSUMPTION``.
    """

    WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
    RETAIN_CANDIDATE = "RETAIN_CANDIDATE"
    PENDING_REVIEW = "PENDING_REVIEW"
    EXCLUDE = "EXCLUDE"
    UNSUPPORTED = "UNSUPPORTED"


FEATURE_GENERATION_STATUSES: Final[frozenset[str]] = frozenset(
    s.value for s in FeatureGenerationStatus
)


def generate_features(
    df_transactions: Any,
    *,
    config: object | None = None,
) -> Any:
    """Top-level public entry point for Stage F (Feature Generation).

    Re-exports :func:`customer_segmentation.prototype.feature_generation
    .pipeline.run_feature_generation_pipeline` but returns only the
    candidate DataFrame (not the full result). For the full result,
    use :func:`run_feature_generation_pipeline` directly.

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Cleaned transaction-level DataFrame (output of Stage C).
    config : FeatureGenerationBlockConfig, optional
        Stage F config; ``None`` uses the canonical default.

    Returns
    -------
    pandas.DataFrame
        The customer-level candidate feature matrix (CustomerID + 14
        candidate features when the FE-05 defaults are used).
    """
    from customer_segmentation.prototype.feature_generation.pipeline import (
        run_feature_generation_pipeline,
    )

    result = run_feature_generation_pipeline(
        df_transactions=df_transactions,
        config=config,
    )
    return result.candidate_df
