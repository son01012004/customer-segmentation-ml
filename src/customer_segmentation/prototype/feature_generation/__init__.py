"""Feature generation prototype-layer package for DEV-03 Stage F.

This sub-package is the prototype-layer bridge to the research core
FE-04 (aggregation) and FE-05 (feature engineering). It WRAPS
research-core APIs verbatim; it does NOT fork and does NOT
introduce new feature definitions.

Architecture
------------
- ``prototype.feature_generation.pipeline`` is the single driver
  function (:func:`run_feature_generation_pipeline`).
- ``prototype.feature_generation.manifest_block`` owns the
  :class:`FeatureGenerationBlock` dataclass which is embedded in
  the parent :class:`PreprocessedManifest`.

Public API
----------
- :func:`generate_features` - top-level public entry point (re-export).
- :func:`run_feature_generation_pipeline` - the actual orchestrator.
"""

from __future__ import annotations

from customer_segmentation.prototype.feature_generation.manifest_block import (
    build_feature_generation_block,
)
from customer_segmentation.prototype.feature_generation.pipeline import (
    FeatureGenerationPipelineResult,
    FeatureGenerationStageLogEntry,
    run_feature_generation_pipeline,
)
from customer_segmentation.prototype.feature_generation.scope import (
    FEATURE_GENERATION_STATUSES,
    FEATURE_OUTCOMES,
    FeatureGenerationOutcome,
    FeatureGenerationScope,
    FeatureGenerationStatus,
    generate_features,
)

__all__ = [
    # scope
    "FeatureGenerationScope",
    "FeatureGenerationOutcome",
    "FeatureGenerationStatus",
    "FEATURE_GENERATION_STATUSES",
    "FEATURE_OUTCOMES",
    "generate_features",
    # pipeline
    "FeatureGenerationPipelineResult",
    "FeatureGenerationStageLogEntry",
    "run_feature_generation_pipeline",
    # manifest_block
    "build_feature_generation_block",
]
