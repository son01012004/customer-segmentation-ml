"""Prototype-layer marketing recommendation package for DEV-07.

This package provides prototype-layer marketing recommendation
capability for the DEV-06 segmentation output, reading
``SegmentationManifest v1.0.0`` and emitting a
``MarketingRecommendationManifest v1.0.0``.

The package is **the prototype layer**. It does not change research
methodology and does not modify any research artefact.

Phase A scope (current; per owner decision 2026-10-10):
  - Read DEV-06 ``SegmentationManifest`` (read-only).
  - Exclude DBSCAN noise (``segment_id == -1``).
  - Emit one ``REVIEW_REQUIRED`` entry per non-noise segment with
    template fields set to ``"PENDING_MKT_FRAMEWORK"`` and ``kpi=None``.
  - Write ``marketing_manifest.json`` (read-only — no CSV / JSONL
    export per OQ-D07-08).
  - Do not modify HTML placeholder (OQ-D07-06).
  - Do not create new ADR (OQ-D07-07).
  - Enforce methodology gates (FR-MKT-05 KPI blocklist,
    FR-MKT-06 noise exclusion, FR-SEG-08 no marketing terms).

Phase B scope (BLOCKED — waiting on MKT-01..MKT-05):
  - Template-driven recommendation generation.
  - CP-04 §4.1-§4.3 tokenization → MKT template mapping.
  - KPI blocklist enforcement per FR-MKT-05.

Public API is re-exported at the bottom; anything not listed is
internal.
"""

from __future__ import annotations

from customer_segmentation.prototype.marketing.config_loader import (
    DEFAULT_DEV07_CONFIG_PATH,
    DEV07_CONFIG_TOP_KEY,
    VALID_LOG_LEVELS,
    Dev07Config,
    Dev07DisplayConfig,
    Dev07LoggingConfig,
    Dev07MktFrameworkConfig,
    Dev07ResearchSafetyConfig,
    Dev07StorageConfig,
    Dev07ValidationConfig,
    find_default_dev07_config_path,
    load_dev07_config,
)
from customer_segmentation.prototype.marketing.display import (
    BANNED_SUBSTRINGS,
    BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER,
    DEFAULT_DISCLAIMER_TEXT,
    check_no_banned_substrings,
    format_manifest_path,
    format_marketing_summary,
    format_recommendations_table,
)
from customer_segmentation.prototype.marketing.exceptions import (
    MarketingCollisionError,
    MarketingConfigError,
    MarketingError,
    MarketingInputError,
    MarketingManifestCorrupt,
    MarketingManifestError,
    MarketingScopeError,
    MarketingStoragePathError,
    MarketingValidationError,
)
from customer_segmentation.prototype.marketing.logging_config import (
    DEV07_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.marketing.manifest import (
    ALLOWED_AVAILABILITY,
    ALLOWED_NOISE_POLICIES,
    MARKETING_MANIFEST_SCHEMA_VERSION,
    EnvironmentBlock,
    MarketingRecommendationEntry,
    MarketingRecommendationManifest,
    MarketingValidationReport,
    ResearchSafetyBlock,
    ValidationCheck,
    build_marketing_manifest,
    build_recommendation_entry_review_required,
    check_forbidden_marketing_terms,
    manifest_to_dict,
    now_utc_iso,
    read_marketing_manifest,
    write_marketing_manifest,
)
from customer_segmentation.prototype.marketing.mapping import (
    TEMPLATE_SLOT_NAMES,
    TemplateSlots,
    is_template_resolved,
    resolve_template_slots,
)
from customer_segmentation.prototype.marketing.mkt_framework_loader import (
    MktDocRef,
    MktFrameworkRef,
    MktFrameworkStructure,
    framework_version_string,
    load_mkt_framework,
    load_mkt_framework_structure,
)
from customer_segmentation.prototype.marketing.pipeline import (
    LIFECYCLE_CACHED,
    LIFECYCLE_FAILED,
    LIFECYCLE_SUCCESS,
    MarketingPipelineResult,
    compute_environment_block,
    run_marketing_pipeline,
)
from customer_segmentation.prototype.marketing.recommendation import (
    build_recommendation_entry,
    build_recommendation_entry_with_scaffolding,
    build_recommendations_from_segmentation,
)
from customer_segmentation.prototype.marketing.scope import (
    AVAILABILITY_STATUSES,
    DEFAULT_AVAILABILITY,
    FORBIDDEN_MARKETING_TERMS,
    KPI_BLOCKLIST,
    KPI_BLOCKLIST_DISPLAY,
    MARKETING_LIMITATION_TEXT,
    MARKETING_PENDING_PLACEHOLDER,
    MARKETING_SCOPES,
    MARKETING_STAGES,
    NOISE_POLICIES,
    AvailabilityStatus,
    MarketingScope,
    MarketingStage,
)
from customer_segmentation.prototype.marketing.storage import (
    CANONICAL_PAYLOAD_KEYS,
    MARKETING_ID_HEX_LEN,
    MARKETING_ID_PREFIX,
    compute_config_sha256,
    derive_marketing_id,
    find_existing_marketing,
    prototype_marketing_base_dir,
    prototype_marketing_run_dir,
    resolve_storage_root,
)
from customer_segmentation.prototype.marketing.tokenization import (
    ALL_VALID_TOKENS,
    BEHAVIOURAL_MODIFIERS,
    FREQUENCY_TIERS,
    MONETARY_TIERS,
    RECENCY_TIERS,
    CP04TokenizationResult,
    parse_cp04_segment_name,
)
from customer_segmentation.prototype.marketing.validation import (
    DBSCAN_NOISE_SEGMENT_ID,
    MarketingInputValidationError,
    compute_file_sha256,
    validate_inputs,
    validate_kpi_blocklist,
    validate_no_duplicate_segment_id,
    validate_noise_segments_isolated,
    validate_research_safety_block,
    validate_segmentation_manifest_shape,
    validate_text_no_forbidden_terms,
)

__all__ = [
    # Scope / stage / closed sets
    "AVAILABILITY_STATUSES",
    "DEFAULT_AVAILABILITY",
    "FORBIDDEN_MARKETING_TERMS",
    "KPI_BLOCKLIST",
    "KPI_BLOCKLIST_DISPLAY",
    "MARKETING_LIMITATION_TEXT",
    "MARKETING_PENDING_PLACEHOLDER",
    "MARKETING_SCOPES",
    "MARKETING_STAGES",
    "NOISE_POLICIES",
    "AvailabilityStatus",
    "MarketingScope",
    "MarketingStage",
    # Manifest
    "ALLOWED_AVAILABILITY",
    "ALLOWED_NOISE_POLICIES",
    "EnvironmentBlock",
    "MARKETING_MANIFEST_SCHEMA_VERSION",
    "MarketingManifestError",
    "MarketingRecommendationEntry",
    "MarketingRecommendationManifest",
    "MarketingValidationReport",
    "ResearchSafetyBlock",
    "ValidationCheck",
    "build_marketing_manifest",
    "build_recommendation_entry",
    "build_recommendation_entry_with_scaffolding",
    "build_recommendation_entry_review_required",
    "build_recommendations_from_segmentation",
    "check_forbidden_marketing_terms",
    "manifest_to_dict",
    "now_utc_iso",
    "read_marketing_manifest",
    "write_marketing_manifest",
    # Storage
    "CANONICAL_PAYLOAD_KEYS",
    "MARKETING_ID_HEX_LEN",
    "MARKETING_ID_PREFIX",
    "compute_config_sha256",
    "derive_marketing_id",
    "find_existing_marketing",
    "prototype_marketing_base_dir",
    "prototype_marketing_run_dir",
    "resolve_storage_root",
    # Config
    "DEFAULT_DEV07_CONFIG_PATH",
    "DEV07_CONFIG_TOP_KEY",
    "Dev07Config",
    "Dev07DisplayConfig",
    "Dev07LoggingConfig",
    "Dev07MktFrameworkConfig",
    "Dev07ResearchSafetyConfig",
    "Dev07StorageConfig",
    "Dev07ValidationConfig",
    "VALID_LOG_LEVELS",
    "find_default_dev07_config_path",
    "load_dev07_config",
    # MKT framework loader
    "MktDocRef",
    "MktFrameworkRef",
    "MktFrameworkStructure",
    "framework_version_string",
    "load_mkt_framework",
    "load_mkt_framework_structure",
    # Display
    "BANNED_SUBSTRINGS",
    "BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER",
    "DEFAULT_DISCLAIMER_TEXT",
    "check_no_banned_substrings",
    "format_marketing_summary",
    "format_manifest_path",
    "format_recommendations_table",
    # Logging
    "DEV07_LOGGER_NAME",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "get_logger",
    # Exceptions
    "MarketingCollisionError",
    "MarketingConfigError",
    "MarketingError",
    "MarketingInputError",
    "MarketingManifestCorrupt",
    "MarketingScopeError",
    "MarketingStoragePathError",
    "MarketingValidationError",
    # Validation
    "DBSCAN_NOISE_SEGMENT_ID",
    "MarketingInputValidationError",
    "compute_file_sha256",
    "validate_inputs",
    "validate_kpi_blocklist",
    "validate_no_duplicate_segment_id",
    "validate_noise_segments_isolated",
    "validate_research_safety_block",
    "validate_segmentation_manifest_shape",
    "validate_text_no_forbidden_terms",
    # Pipeline
    "LIFECYCLE_CACHED",
    "LIFECYCLE_FAILED",
    "LIFECYCLE_SUCCESS",
    "MarketingPipelineResult",
    "compute_environment_block",
    "run_marketing_pipeline",
    # Mapping (Phase B scaffolding)
    "TEMPLATE_SLOT_NAMES",
    "TemplateSlots",
    "is_template_resolved",
    "resolve_template_slots",
    # Tokenization (CP-04 §4.1-§4.3)
    "ALL_VALID_TOKENS",
    "BEHAVIOURAL_MODIFIERS",
    "CP04TokenizationResult",
    "FREQUENCY_TIERS",
    "MONETARY_TIERS",
    "RECENCY_TIERS",
    "parse_cp04_segment_name",
]
