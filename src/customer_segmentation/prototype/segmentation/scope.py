"""Scope, stage, and statistic-name enums for DEV-06 Prototype Segmentation.

DEV-06 defines:
- :class:`ProfiledScope`: the scope of a segmentation artefact (always
  ``PROFILED_PROTOTYPE``).
- :class:`SegmentationStage`: the closed 8-value enum of pipeline stages
  (A → H) for per-stage logging + observability.
- :class:`NoisePolicy`: the Literal alias for DBSCAN noise policy values.
- :data:`PROFILING_STATISTICS_SET`: the closed set of descriptive statistic
  names DEV-06 may emit. **No** silhouette / Davies-Bouldin / Calinski-Harabasz
  / ARI / AMI / runtime — those are research-core metrics owned by
  DEV-05 / EPIC-08/09.
- :data:`SEGMENTATION_MANIFEST_SCHEMA_VERSION`: pinned manifest schema version.

Hard rules
----------
- :class:`ProfiledScope` has exactly ONE value: ``PROFILED_PROTOTYPE``.
  The pipeline never exposes a way to change it.
- :class:`SegmentationStage` enumerates exactly 8 stages ``A`` → ``H``
  in canonical order (mirror DEV-05 Stage A → G + one extra for
  characteristics compute).
- :data:`PROFILING_STATISTICS_SET` is closed: 9 descriptive names only.
  No research-only metric may be added without one of:
    (a) a new ADR, or
    (b) a schema-version bump that invalidates old ``segmentation_id``s.
- :data:`DEFAULT_NOISE_POLICY` is ``"exclude"`` per ADR-0006 (mirrors
  DEV-05 default).
- :data:`SEGMENTATION_MANIFEST_SCHEMA_VERSION` is pinned to ``"1.0.0"``;
  bumping it invalidates all old ``segmentation_id``s and forces re-run
  (defence against silently reinterpreting old manifests).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

__all__ = [
    "ProfiledScope",
    "PROFILED_SCOPES",
    "SegmentationStage",
    "SEGMENTATION_STAGES",
    "NoisePolicy",
    "NOISE_POLICIES",
    "DEFAULT_NOISE_POLICY",
    "PROFILING_STATISTIC_NAMES",
    "PROFILING_STATISTICS_SET",
    "DEFAULT_STATISTICS_SET",
    "SEGMENTATION_MANIFEST_SCHEMA_VERSION",
    "ALLOWED_CHARACTERISTIC_RULES",
]


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class ProfiledScope(StrEnum):
    """Scope of a segmentation artefact in the prototype storage layer.

    Attributes
    ----------
    PROFILED_PROTOTYPE : str
        The only value currently in use. Implies that the artefact was
        produced by the DEV-06 pipeline on a DEV-04 clustering output.
        It is **not** a research artefact; it has not been promoted by
        the research methodology.
    """

    PROFILED_PROTOTYPE = "PROFILED_PROTOTYPE"


PROFILED_SCOPES: Final[frozenset[str]] = frozenset(s.value for s in ProfiledScope)


# ---------------------------------------------------------------------------
# Segmentation pipeline stages (8-value closed enum, mirror DEV-05 Stage A→G)
# ---------------------------------------------------------------------------


class SegmentationStage(StrEnum):
    """The closed 8-value enum of pipeline stages (per-stage logging).

    Canonical order A → H:

    - **A (preflight)** — load DEV-06 config; resolve dataset /
      preprocessed / clustering ids; read DEV-04 ``clustering_manifest.json``.
    - **B (lookup)** — read DEV-04 ``cluster_labels_*.parquet`` and DEV-03
      ML Dataset parquet. Read DEV-05 evaluation manifest if provided.
    - **C (validation)** — alignment between cluster labels and ML
      Dataset; NaN / Inf checks; CustomerID leak; ClusterLabel dtype.
      Build :class:`SegmentationValidationReport`.
    - **D (profile compute)** — per-segment feature profile statistics
      (numerical stats + categorical top-K).
    - **E (characteristics compute)** — per-segment characteristics
      derivation from profile stats (rule engine).
    - **F (manifest write)** — atomic write ``segmentation_manifest.json``
      in staging + emit CSVs / JSONs.
    - **G (publish)** — atomic ``os.rename(staging → final)``.
    - **H (finalize)** — flush + close log handlers.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"


SEGMENTATION_STAGES: Final[frozenset[str]] = frozenset(s.value for s in SegmentationStage)


# ---------------------------------------------------------------------------
# Noise policy (Literal alias + closed set) — mirror DEV-05
# ---------------------------------------------------------------------------

# Literal type for static type-checking.
NoisePolicy = Literal["include", "exclude"]

NOISE_POLICIES: Final[frozenset[str]] = frozenset({"include", "exclude", "n/a"})

# Prototype-layer default per ADR-0006 (OQ-EVAL-NOISE resolved 2026-10-09).
# The CLI flag ``--noise-policy`` and YAML key ``noise_policy`` both
# default to this value. A non-default value (``"include"``) is a
# methodology decision reserved for the human researcher.
DEFAULT_NOISE_POLICY: Final[str] = "exclude"


# ---------------------------------------------------------------------------
# Descriptive statistic names (closed set; NO research metrics)
# ---------------------------------------------------------------------------

# Closed set of statistic names DEV-06 may emit in profile outputs.
# This is intentionally disjoint from ``customer_segmentation.prototype.
# evaluation.scope.METRIC_NAMES`` — DEV-06 covers descriptive
# statistics only, never internal clustering-quality metrics.
PROFILING_STATISTIC_NAMES: Final[frozenset[str]] = frozenset(
    {
        # Numerical statistics (7)
        "mean",
        "median",
        "std",
        "q1",
        "q3",
        "min",
        "max",
        # Categorical statistics (2)
        "topk_categories",
        "value_counts",
        # Categorical auxiliary metadata (2, per OQ-SEG-DISPLAY-01)
        "other_count",
        "missing_count",
    }
)

# Public alias (mirrors DEV-05 METRIC_NAMES naming).
PROFILING_STATISTICS_SET: Final[frozenset[str]] = PROFILING_STATISTIC_NAMES

# Default statistic set: all 7 numerical statistics. Categorical
# statistics are emitted on-demand (per-feature type detection).
# Order is preserved as the canonical row order of ``segment_profiles.csv``.
DEFAULT_STATISTICS_SET: Final[tuple[str, ...]] = (
    "mean",
    "median",
    "std",
    "q1",
    "q3",
    "min",
    "max",
)


# ---------------------------------------------------------------------------
# Manifest schema version
# ---------------------------------------------------------------------------

# Bump this when the manifest schema changes incompatibly. The
# ``segmentation_id`` derivation (storage.py) includes schema_version,
# so a bump automatically invalidates old ``segmentation_id``s and
# forces re-run (defence against silently reinterpreting old manifests).
SEGMENTATION_MANIFEST_SCHEMA_VERSION: Final[str] = "1.0.0"

# Re-export of the closed characteristic-rule set from manifest.py
# (kept here for discoverability in OQ-SEG-CHAR-01 documentation).
ALLOWED_CHARACTERISTIC_RULES: Final[frozenset[str]] = frozenset(
    {
        "mean_high_<feature>",
        "mean_low_<feature>",
        "median_above_dataset_median_<feature>",
        "top_category_<feature>_<value>",
    }
)
