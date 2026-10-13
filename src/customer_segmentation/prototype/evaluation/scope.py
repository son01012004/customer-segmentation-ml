"""Scope, status, reason, and metric-name enums for DEV-05 Prototype Evaluation.

DEV-05 defines:
- :class:`EvaluatedScope`: the scope of an evaluation artefact
  (always ``EVALUATED_PROTOTYPE``).
- :class:`MetricName`: the closed set of internal metric names
  DEV-05 emits (silhouette / davies-bouldin / calinski-harabasz).
- :class:`MetricStatus`: the 4-value closed enum of metric status
  (mirror SYS-04 §12.2 metric applicability rules + EVA-01 reference).
- :class:`MetricReason`: the closed enum of metric reason codes
  (mirror ``MISSING_REASON_*`` taxonomy of research core evaluation;
  per SYS-04 §12.2).

Why an enum (and not a string)
--------------------------------
A string-valued :class:`Enum` (the ``str, Enum`` mixin) gives both
``==`` semantics of strings and the type-checkable membership in a
closed set. This mirrors the convention used by
:mod:`customer_segmentation.prototype.clustering.scope`,
:mod:`customer_segmentation.config.loader`, and
:mod:`customer_segmentation.evaluation.experiment_results.schema`.

Hard rules
----------
- :class:`EvaluatedScope` has exactly ONE value:
  ``EVALUATED_PROTOTYPE``. The pipeline never exposes a way to change it.
- :class:`MetricName` enumerates exactly 3 metric names: SILHOUETTE,
  DAVIES_BOULDIN, CALINSKI_HARABASZ. No WCSS, no ARI/AMI, no runtime.
- :class:`MetricStatus` is closed: 4 values, no additions.
- :class:`MetricReason` is closed: ~17 values. Subgrouped by status:
  - VALID_VALUE     → {COMPUTED, DBSCAN_NOISE_EXCLUDED}
  - NOT_APPLICABLE  → {ALL_NOISE, SINGLE_CLUSTER, INSUFFICIENT_CLUSTERS,
                       DEGENERATE_FEATURE_SPACE}
  - MISSING         → {ALGORITHM_FAMILY_NOT_SUPPORTED, DEV05_DISABLED,
                       PENDING_HUMAN_REVIEW, MANIFEST_MISSING}
  - COMPUTATION_ERROR → {ALIGNMENT_ERROR, NAN_OR_INF_INPUT, SCHEMA_CORRUPT,
                          SKLEARN_EXCEPTION, IO_ERROR, DEGENERATE_RESULT,
                          CLUSTER_DTYPE_INVALID}
- ``METRIC_REASON_BY_STATUS`` is the immutable mapping from status to its
  canonical reason set (used by ``EvaluationMetricEntry`` construction
  for invariant validation).
- ``NOISE_POLICIES`` is the closed Literal set of DBSCAN noise policy
  values. ``"exclude"`` is the prototype-layer default per ADR-0006.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

__all__ = [
    "EvaluatedScope",
    "EVALUATED_SCOPES",
    "MetricName",
    "METRIC_NAMES",
    "DEFAULT_METRIC_SET",
    "MetricStatus",
    "METRIC_STATUSES",
    "MetricReason",
    "METRIC_REASONS",
    "METRIC_REASON_BY_STATUS",
    "NoisePolicy",
    "NOISE_POLICIES",
    "DEFAULT_NOISE_POLICY",
    "EVALUATION_MANIFEST_SCHEMA_VERSION",
]


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class EvaluatedScope(StrEnum):
    """Scope of an evaluation artefact in the prototype storage layer.

    Attributes
    ----------
    EVALUATED_PROTOTYPE : str
        The only value currently in use. Implies that the artefact
        was produced by the DEV-05 pipeline on a DEV-04 clustering
        output. It is **not** a research artefact; it has not been
        promoted by the research methodology.
    """

    EVALUATED_PROTOTYPE = "EVALUATED_PROTOTYPE"


EVALUATED_SCOPES: Final[frozenset[str]] = frozenset(s.value for s in EvaluatedScope)


# ---------------------------------------------------------------------------
# Metric names
# ---------------------------------------------------------------------------


class MetricName(StrEnum):
    """The closed set of internal metric names DEV-05 emits.

    Attributes
    ----------
    SILHOUETTE : str
        Silhouette Score (sklearn ``silhouette_score``).
        Range [-1, 1]; higher = better.
    DAVIES_BOULDIN : str
        Davies-Bouldin Index (sklearn ``davies_bouldin_score``).
        Range [0, +inf); lower = better.
    CALINSKI_HARABASZ : str
        Calinski-Harabasz Index (sklearn ``calinski_harabasz_score``).
        Range [0, +inf); higher = better.
    """

    SILHOUETTE = "silhouette"
    DAVIES_BOULDIN = "davies_bouldin"
    CALINSKI_HARABASZ = "calinski_harabasz"


METRIC_NAMES: Final[frozenset[str]] = frozenset(m.value for m in MetricName)

# Default metric set: all 3 internal metrics (the only ones DEV-05 covers).
# Order is preserved as the canonical row order of ``metrics_long.csv``.
DEFAULT_METRIC_SET: Final[tuple[str, ...]] = (
    MetricName.SILHOUETTE.value,
    MetricName.DAVIES_BOULDIN.value,
    MetricName.CALINSKI_HARABASZ.value,
)


# ---------------------------------------------------------------------------
# Metric status (4-value closed enum, mirror SYS-04 §12.2)
# ---------------------------------------------------------------------------


class MetricStatus(StrEnum):
    """Closed enum of metric status (per SYS-04 §12.2 applicability rules).

    Attributes
    ----------
    VALID_VALUE : str
        Metric computed successfully; ``value`` is a finite float.
    NOT_APPLICABLE : str
        Input is valid but the metric does not apply to this data
        (e.g. all-noise, single cluster, insufficient clusters).
    MISSING : str
        Evaluation pass did not attempt the compute
        (e.g. wrong algorithm family, manifest invalid,
        pass aborted before compute).
    COMPUTATION_ERROR : str
        Input passed validation but the compute pipeline failed
        (sklearn exception, NaN/Inf, alignment, storage I/O, ...).
    """

    VALID_VALUE = "VALID_VALUE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    MISSING = "MISSING"
    COMPUTATION_ERROR = "COMPUTATION_ERROR"


METRIC_STATUSES: Final[frozenset[str]] = frozenset(s.value for s in MetricStatus)


# ---------------------------------------------------------------------------
# Metric reason (~17-value closed enum)
# ---------------------------------------------------------------------------


class MetricReason(StrEnum):
    """Closed enum of metric reason codes.

    Each metric entry has exactly one ``reason`` from this enum. The
    reason is the contract for failure diagnosis (no fake default
    numbers — see plan §5.5 rule 2).

    Subgrouping by status (enforced in :data:`METRIC_REASON_BY_STATUS`):

    - VALID_VALUE     → {COMPUTED, DBSCAN_NOISE_EXCLUDED}
    - NOT_APPLICABLE  → {ALL_NOISE, SINGLE_CLUSTER, INSUFFICIENT_CLUSTERS,
                        DEGENERATE_FEATURE_SPACE}
    - MISSING         → {ALGORITHM_FAMILY_NOT_SUPPORTED, DEV05_DISABLED,
                        PENDING_HUMAN_REVIEW, MANIFEST_MISSING}
    - COMPUTATION_ERROR → {ALIGNMENT_ERROR, NAN_OR_INF_INPUT, SCHEMA_CORRUPT,
                          SKLEARN_EXCEPTION, IO_ERROR, DEGENERATE_RESULT,
                          CLUSTER_DTYPE_INVALID}
    """

    # VALID_VALUE reasons
    COMPUTED = "COMPUTED"
    # NOT_APPLICABLE reasons
    ALL_NOISE = "ALL_NOISE"
    SINGLE_CLUSTER = "SINGLE_CLUSTER"
    INSUFFICIENT_CLUSTERS = "INSUFFICIENT_CLUSTERS"
    DEGENERATE_FEATURE_SPACE = "DEGENERATE_FEATURE_SPACE"
    # COMPUTATION_ERROR reasons
    ALIGNMENT_ERROR = "ALIGNMENT_ERROR"
    NAN_OR_INF_INPUT = "NAN_OR_INF_INPUT"
    SCHEMA_CORRUPT = "SCHEMA_CORRUPT"
    SKLEARN_EXCEPTION = "SKLEARN_EXCEPTION"
    IO_ERROR = "IO_ERROR"
    DEGENERATE_RESULT = "DEGENERATE_RESULT"
    CLUSTER_DTYPE_INVALID = "CLUSTER_DTYPE_INVALID"
    # MISSING reasons
    ALGORITHM_FAMILY_NOT_SUPPORTED = "ALGORITHM_FAMILY_NOT_SUPPORTED"
    DEV05_DISABLED = "DEV05_DISABLED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    MANIFEST_MISSING = "MANIFEST_MISSING"
    # Cross-status reason (audit annotation, not failure): DBSCAN noise
    # rows were filtered out before sklearn compute. The metric value
    # remains VALID_VALUE (when ≥ 2 cluster non-noise survives the
    # filter); this reason is for audit reproducibility.
    DBSCAN_NOISE_EXCLUDED = "DBSCAN_NOISE_EXCLUDED"


METRIC_REASONS: Final[frozenset[str]] = frozenset(r.value for r in MetricReason)


# Immutable mapping from MetricStatus → canonical set of MetricReason values.
# Used by ``EvaluationMetricEntry`` invariant validation.
METRIC_REASON_BY_STATUS: Final[dict[str, frozenset[str]]] = {
    MetricStatus.VALID_VALUE.value: frozenset(
        {
            MetricReason.COMPUTED.value,
            MetricReason.DBSCAN_NOISE_EXCLUDED.value,
        }
    ),
    MetricStatus.NOT_APPLICABLE.value: frozenset(
        {
            MetricReason.ALL_NOISE.value,
            MetricReason.SINGLE_CLUSTER.value,
            MetricReason.INSUFFICIENT_CLUSTERS.value,
            MetricReason.DEGENERATE_FEATURE_SPACE.value,
        }
    ),
    MetricStatus.MISSING.value: frozenset(
        {
            MetricReason.ALGORITHM_FAMILY_NOT_SUPPORTED.value,
            MetricReason.DEV05_DISABLED.value,
            MetricReason.PENDING_HUMAN_REVIEW.value,
            MetricReason.MANIFEST_MISSING.value,
        }
    ),
    MetricStatus.COMPUTATION_ERROR.value: frozenset(
        {
            MetricReason.ALIGNMENT_ERROR.value,
            MetricReason.NAN_OR_INF_INPUT.value,
            MetricReason.SCHEMA_CORRUPT.value,
            MetricReason.SKLEARN_EXCEPTION.value,
            MetricReason.IO_ERROR.value,
            MetricReason.DEGENERATE_RESULT.value,
            MetricReason.CLUSTER_DTYPE_INVALID.value,
        }
    ),
}


# ---------------------------------------------------------------------------
# Noise policy (Literal alias + closed set)
# ---------------------------------------------------------------------------

# Literal type for static type-checking.
NoisePolicy = Literal["include", "exclude"]

NOISE_POLICIES: Final[frozenset[str]] = frozenset({"include", "exclude"})

# Prototype-layer default per ADR-0006 (OQ-EVAL-NOISE resolved 2026-10-09).
# The CLI flag `--noise-policy` and YAML key ``noise_policy`` both default
# to this value. A non-default value (``"include"``) is a methodology
# decision reserved for the human researcher.
DEFAULT_NOISE_POLICY: Final[str] = "exclude"


# ---------------------------------------------------------------------------
# Manifest schema version
# ---------------------------------------------------------------------------

# Bump this when the manifest schema changes incompatibly. The
# ``evaluation_id`` derivation (storage.py) includes schema_version, so a
# bump automatically invalidates old ``evaluation_id``s and forces re-run
# (defence against silently reinterpreting old manifests).
EVALUATION_MANIFEST_SCHEMA_VERSION: Final[str] = "1.0.0"
