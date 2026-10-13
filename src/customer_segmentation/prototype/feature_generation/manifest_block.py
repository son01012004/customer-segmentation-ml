"""FeatureGenerationBlock dataclass + helper (DEV-03).

The block is embedded under ``PreprocessedManifest.feature_generation_block``.
Module-level dataclasses mirror those used by
:mod:`customer_segmentation.prototype.preprocessing.manifest`,
but live here for clean ownership: feature_generation owns the
feature_generation_block field, preprocessing owns the parent
:mod:`manifest` schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from customer_segmentation.prototype.feature_generation.scope import (
    FeatureGenerationOutcome,
    FeatureGenerationStatus,
)
from customer_segmentation.prototype.preprocessing.config_loader import (
    FeatureGenerationBlockConfig,
)
from customer_segmentation.prototype.preprocessing.manifest import (
    FeatureGenerationAggregationBlock,
    FeatureGenerationBehaviorBlock,
    FeatureGenerationBlock,
    FeatureGenerationCancellationBlock,
    FeatureGenerationDiversityBlock,
    FeatureGenerationQuantityBlock,
    FeatureGenerationRFMBlock,
)

__all__ = [
    "build_feature_generation_block",
]


def build_feature_generation_block(
    cfg: FeatureGenerationBlockConfig,
    *,
    reference_date_iso: str,
    customer_count: int,
    candidate_feature_count: int,
    outcome: str,
) -> FeatureGenerationBlock:
    """Construct a :class:`FeatureGenerationBlock` from a Stage F run.

    Per-feature status is ``WORKING_ASSUMPTION`` by default; this
    matches FE-05's "RFM/behavioral/cancellation = WORKING_ASSUMPTION"
    semantics. The block does NOT introduce score/rank/weight
    (per AGENTS.md §2.6).
    """
    f = cfg.features
    return FeatureGenerationBlock(
        enabled=True,
        aggregation=FeatureGenerationAggregationBlock(
            enabled=True,
            customer_key=cfg.aggregation.customer_key or "CustomerID",
            status=FeatureGenerationStatus.WORKING_ASSUMPTION.value,
        ),
        rfm=FeatureGenerationRFMBlock(
            monetary_strategy=f.monetary_strategy,
            monetary_status=FeatureGenerationStatus.WORKING_ASSUMPTION.value,
            frequency_mode=f.frequency_mode,
            frequency_status=FeatureGenerationStatus.WORKING_ASSUMPTION.value,
            reference_date_mode=cfg.reference_date.mode,
            reference_date_value=(
                cfg.reference_date.fixed_iso_date
                if cfg.reference_date.mode == "from_config"
                else reference_date_iso
            ),
        ),
        quantity=FeatureGenerationQuantityBlock(
            default_variant=f.quantity_strategy,
            status=FeatureGenerationStatus.WORKING_ASSUMPTION.value,
        ),
        behavior=FeatureGenerationBehaviorBlock(
            tenure_enabled=True,
            purchase_interval_ddof=f.purchase_interval_ddof,
            active_days_enabled=True,
            average_invoice_value_enabled=True,
        ),
        diversity=FeatureGenerationDiversityBlock(
            strategy=f.diversity_strategy,
            category_count_not_materialized=True,
        ),
        cancellation=FeatureGenerationCancellationBlock(
            cancellation_enabled=f.cancellation_enabled,
            return_enabled=f.return_enabled,
            status=FeatureGenerationStatus.WORKING_ASSUMPTION.value,
        ),
        optional_transform_transformation=cfg.optional_transform.transformation,
        optional_transform_scaling=cfg.optional_transform.scaling,
        optional_transform_imputation=cfg.optional_transform.imputation,
        status=outcome,
    )


__ = (dataclass, field, Any, FeatureGenerationOutcome)
