"""Scope, stage, and outcome enums for DEV-03 Prototype Preprocessing.

The package defines a small, closed set of enums and frozen sets that
describe what DEV-03 supports and what its outcomes mean.

Why an enum (and not a string)
------------------------------
A string-valued :class:`Enum` (the ``str, Enum`` mixin) gives both
``==`` semantics of strings and the type-checkable membership in a
closed set. This mirrors the convention used by
:mod:`customer_segmentation.config.loader` and
:mod:`customer_segmentation.dataset_management.scope`.

Hard rules
----------
- DEV-03 has **one** :class:`PreprocessedScope`: ``PREPROCESSED_PROTOTYPE``.
  The CLI / driver never exposes a way to change it.
- :class:`PreprocessingStage` enumerates the 7 Jira pipeline stages
  A→G; new stages must add an ADR.
- :class:`TransformationMethod`, :class:`ScalingMethod`,
  :class:`ImputationMethod`, :class:`OutlierAction`,
  :class:`OutlierMethod` enumerations are the only allowed
  combinations for the optional Steps D / E / F3 (see
  ``OPTIONAL_TRANSFORM_GRID``).
- :class:`CleaningRuleStatus` is one of three strict values; the
  FE-02 statuses are re-marked verbatim, **never reclassified**.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "PreprocessedScope",
    "PreprocessingOutcome",
    "PreprocessingStage",
    "CleaningRuleStatus",
    "DatasetProfileCategory",
    "FeatureStatus",
    "ImputationMethod",
    "OptionalTransformOutcome",
    "OutlierAction",
    "OutlierMethod",
    "ScalingMethod",
    "TransformationMethod",
    "PREPROCESSED_SCOPES",
    "PREPROCESSING_STAGES",
    "PREPROCESSING_OUTCOMES",
    "CLEANING_RULE_STATUSES",
    "DATASET_PROFILE_CATEGORIES",
    "FEATURE_STATUSES",
    "IMPUTATION_METHODS",
    "OUTLIER_ACTIONS",
    "OUTLIER_METHODS",
    "OPTIONAL_TRANSFORM_GRID",
    "OPTIONAL_TRANSFORM_OUTCOMES",
    "PREPROCESSING_OUTCOME_PASS",
    "PREPROCESSING_OUTCOME_FAIL",
    "PREPROCESSING_OUTCOME_WARNING",
    "preprocess_dataset",
]


# ---------------------------------------------------------------------------
# Scope and outcome (mirror DEV-02's pattern)
# ---------------------------------------------------------------------------


class PreprocessedScope(StrEnum):
    """Scope of a preprocessed artefact in the prototype storage layer.

    Attributes
    ----------
    PREPROCESSED_PROTOTYPE : str
        The only value currently in use. Implies that the artefact
        was produced by the DEV-03 pipeline on a user-supplied
        dataset imported via DEV-02. It is **not** a research
        artefact; it has not been promoted by the research
        methodology.
    """

    PREPROCESSED_PROTOTYPE = "PREPROCESSED_PROTOTYPE"


PREPROCESSED_SCOPES: Final[frozenset[str]] = frozenset(s.value for s in PreprocessedScope)


# ---------------------------------------------------------------------------
# 7-stage pipeline (Stage A → G, per Jira scope)
# ---------------------------------------------------------------------------


class PreprocessingStage(StrEnum):
    """The 7-stage Jira preprocessing pipeline.

    Stages are listed in execution order. Each stage corresponds to
    one optional / required step in DEV-03.

    The mapping is::

        A: Dataset     → Stage A
        B: Validation  → Stage B
        C: Cleaning    → Stage C
        D: Transform   → Stage D
        E: Scaling     → Stage E
        F: Features    → Stage F (delegated to
                         :mod:`customer_segmentation.prototype.feature_generation`)
        G: ML Dataset  → Stage G
    """

    STAGE_A = "A"
    STAGE_B = "B"
    STAGE_C = "C"
    STAGE_D = "D"
    STAGE_E = "E"
    STAGE_F = "F"
    STAGE_G = "G"


PREPROCESSING_STAGES: Final[frozenset[str]] = frozenset(s.value for s in PreprocessingStage)


class PreprocessingOutcome(StrEnum):
    """Per-stage outcome, mirrored from DEV-02's ValidationResult.

    Attributes
    ----------
    PASS : str
        No issues.
    WARNING : str
        Non-fatal issues; pipeline still proceeds.
    FAIL : str
        Fatal issue; pipeline aborts without writing.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


PREPROCESSING_OUTCOMES: Final[frozenset[str]] = frozenset(s.value for s in PreprocessingOutcome)


PREPROCESSING_OUTCOME_PASS: Final[str] = PreprocessingOutcome.PASS.value
PREPROCESSING_OUTCOME_WARNING: Final[str] = PreprocessingOutcome.WARNING.value
PREPROCESSING_OUTCOME_FAIL: Final[str] = PreprocessingOutcome.FAIL.value


# ---------------------------------------------------------------------------
# Status markers (verbatim from research core, never reclassified)
# ---------------------------------------------------------------------------


class CleaningRuleStatus(StrEnum):
    """Status of an individual cleaning rule, verbatim from FE-02.

    The three values mirror :class:`customer_segmentation.config.loader`
    KEY_ANNOTATIONS for FE-02 cleaning rules:

    - ``WORKING_ASSUMPTION`` for CL-01, CL-03, CL-04, CL-05, CL-07,
      CL-09, CL-10.
    - ``PENDING_MENTOR_REVIEW`` for CL-06, CL-08.

    A third value ``REVIEW_REQUIRED`` exists for downstream callers
    that want to flag a rule as needing an explicit ADR review.
    Promotion to ``RESEARCH_APPROVED_FINAL`` is reserved for mentor +
    ADR (out of DEV-03 scope).
    """

    WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
    PENDING_MENTOR_REVIEW = "PENDING_MENTOR_REVIEW"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


CLEANING_RULE_STATUSES: Final[frozenset[str]] = frozenset(s.value for s in CleaningRuleStatus)


class DatasetProfileCategory(StrEnum):
    """Top-level dataset-profile category.

    Used by ``basic_overview`` and structural validation to label the
    three DEV-02 + DEV-03 validation groups.
    """

    FILE_LEVEL = "file_level"
    STRUCTURAL = "structural"
    DATA_QUALITY = "data_quality"


DATASET_PROFILE_CATEGORIES: Final[frozenset[str]] = frozenset(
    s.value for s in DatasetProfileCategory
)


class FeatureStatus(StrEnum):
    """Status of an engineered feature, verbatim from FE-05.

    The default value is ``WORKING_ASSUMPTION``. Other values mirror
    the FE-05 selection decisions (``RETAIN_CANDIDATE``,
    ``PENDING_REVIEW``, ``EXCLUDE``, ``UNSUPPORTED``).
    """

    WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
    RETAIN_CANDIDATE = "RETAIN_CANDIDATE"
    PENDING_REVIEW = "PENDING_REVIEW"
    EXCLUDE = "EXCLUDE"
    UNSUPPORTED = "UNSUPPORTED"


FEATURE_STATUSES: Final[frozenset[str]] = frozenset(s.value for s in FeatureStatus)


# ---------------------------------------------------------------------------
# Optional transform / scale / imputation (Stages D, E, F3)
# ---------------------------------------------------------------------------


class TransformationMethod(StrEnum):
    """Stage D / F3 transformation method.

    ``NONE`` is the prototype default; it means "identity" — no
    transformation. ``LOG1P`` and ``YEO_JOHNSON`` mirror the FE-06 A2
    rule (log1p on negative-valued columns → reject).
    """

    NONE = "none"
    LOG1P = "log1p"
    YEO_JOHNSON = "yeo_johnson"


class ScalingMethod(StrEnum):
    """Stage E / F3 scaling method.

    ``NONE`` is the prototype default; it means "identity" — no
    scaling. The other three mirror the FE-06 EXP-04 sweep options
    Standard / MinMax / Robust.
    """

    NONE = "none"
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"


class ImputationMethod(StrEnum):
    """Imputation strategy applied AFTER validation, BEFORE transform/scale.

    Only three strategies are allowed for the prototype layer
    (matching the FE-06 fill policy): ``NONE`` (no imputation),
    ``MEDIAN``, ``MEAN``. Imputation is for the customer-level
    matrix (Stage F3) only; transaction-level missing values are
    handled by Stage C (cleaning).
    """

    NONE = "none"
    MEDIAN = "median"
    MEAN = "mean"


class OutlierAction(StrEnum):
    """Stage C outlier handling action. Mirrors FE-02.

    The default is ``NONE`` (skip outlier stage), matching FE-02
    default. ``PENDING_MENTOR_REVIEW`` per AGENTS.md §2.9.
    """

    NONE = "none"
    CLIP = "clip"
    REMOVE = "remove"
    FLAG = "flag"


class OutlierMethod(StrEnum):
    """Stage C outlier detection method. Mirrors FE-02."""

    IQR = "iqr"
    ZSCORE = "zscore"


OUTLIER_ACTIONS: Final[frozenset[str]] = frozenset(s.value for s in OutlierAction)
OUTLIER_METHODS: Final[frozenset[str]] = frozenset(s.value for s in OutlierMethod)
IMPUTATION_METHODS: Final[frozenset[str]] = frozenset(s.value for s in ImputationMethod)


# ---------------------------------------------------------------------------
# Optional transform × scaling grid (Stage D/E and F3)
# ---------------------------------------------------------------------------


OPTIONAL_TRANSFORM_GRID: Final[tuple[tuple[str, str], ...]] = tuple(
    (t.value, s.value) for t in TransformationMethod for s in ScalingMethod
)


class OptionalTransformOutcome(StrEnum):
    """Optional transform/scale stage outcome.

    Identical semantics to :class:`PreprocessingOutcome` but
    distinguishes the optional step from the always-on cleaning
    step.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


OPTIONAL_TRANSFORM_OUTCOMES: Final[frozenset[str]] = frozenset(
    s.value for s in OptionalTransformOutcome
)


# ---------------------------------------------------------------------------
# Public top-level driver (re-exported in pipeline.py for ergonomics)
# ---------------------------------------------------------------------------


def preprocess_dataset(
    dataset_id: str,
    *,
    config_path: str | None = None,
) -> dict:
    """Top-level public entry point for DEV-03 preprocessing.

    Re-export of :func:`customer_segmentation.prototype.preprocessing.pipeline
    .run_preprocessing_pipeline` for ergonomic imports. Returns a
    JSON-serialisable summary dict so the caller can dump it directly.

    See :func:`run_preprocessing_pipeline` for full documentation.

    Parameters
    ----------
    dataset_id : str
        DEV-02 dataset id (e.g. ``"ds_ba54033e45525bf5123c2d9d"``).
    config_path : str, optional
        Path to ``configs/dev03_preprocessing.yaml``. ``None`` uses
        the canonical default.

    Returns
    -------
    dict
        Run summary (preprocessed_id, ml_dataset_path, manifest_path,
        log_path, ...).
    """
    from customer_segmentation.prototype.preprocessing.pipeline import (  # local import to avoid cycles
        run_preprocessing_pipeline,
    )

    result = run_preprocessing_pipeline(dataset_id, config_path=config_path)
    return result.as_summary()
