"""Prototype-layer end-to-end pipeline package for DEV-09.

This package orchestrates the existing DEV-02..08 prototype pipelines
into a single reproducible end-to-end run:

    Upload → Validation → Preprocessing → Feature Engineering →
    Select Algorithm → Clustering → Evaluation → Customer
    Segmentation → Customer Profile → Marketing Recommendation →
    Visualization

It does NOT re-implement any DEV-02..08 logic. Each stage is delegated
to its existing public API via the established :func:`run_*_pipeline`
entry points. The package owns only the orchestration, stage-status
tracking, persistence, and reload logic.

Hard rules (per AGENTS.md §2 and the canonical prototype contract)
-----------------------------------------------------------------
- **Read-only on existing contracts.** No frozen manifest schema is
  modified. The end-to-end package introduces its OWN schema
  (``e2e_run.json``) for the run summary only.
- **Methodology untouched.** No algorithm selection, ranking, or
  composite scoring is performed by this package. The selected
  algorithm is passed through to the DEV-04 pipeline which remains
  the source of truth.
- **Research safety.** No prototype artefact is promoted to research
  evidence; ``automatically_promoted_to_research`` is enforced at
  every stage.
- **Cluster Visualization 2D remains BLOCKED.** The end-to-end
  pipeline does NOT pre-pick a projection methodology. If DEV-08
  emits BLOCKED, the end-to-end summary records it as such.
- **Marketing REVIEW_REQUIRED is preserved.** The end-to-end
  pipeline does NOT auto-promote DEV-07 Phase B content. The
  marketing manifest's ``availability`` is carried through
  faithfully; the end-to-end status is BLOCKED or REVIEW_REQUIRED
  if DEV-07 surfaces one of those states.
- **Idempotency.** The ``e2e_run_id`` is content-addressed from the
  canonical payload (input ids + config hashes + seed). The same
  inputs yield the same ``e2e_run_id``; re-running with identical
  inputs is a no-op (``lifecycle = CACHED``).
- **No silent overwrites.** Per-stage manifests are READ into the
  end-to-end summary; they are NEVER overwritten in place. Source
  datasets, prior runs, and unrelated artefacts are never modified.

Public API (re-exported at the bottom; anything not listed is internal).
"""

from __future__ import annotations

from customer_segmentation.prototype.end_to_end.config_loader import (
    DEFAULT_DEV09_CONFIG_PATH,
    DEV09_CONFIG_TOP_KEY,
    Dev09Config,
    Dev09DisplayConfig,
    Dev09LoggingConfig,
    Dev09PersistenceConfig,
    Dev09ResearchSafetyConfig,
    Dev09StageSelectionConfig,
    Dev09StorageConfig,
    load_dev09_config,
)
from customer_segmentation.prototype.end_to_end.exceptions import (
    Dev09ConfigError,
    Dev09Error,
    Dev09InputError,
    Dev09StoragePathError,
)
from customer_segmentation.prototype.end_to_end.logging_config import (
    DEV09_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.end_to_end.pipeline import (
    E2E_BLOCKED,
    E2E_CACHED,
    E2E_CONDITIONAL,
    E2E_FAILED,
    E2E_STAGE_BLOCKED,
    E2E_STAGE_CACHED,
    E2E_STAGE_FAILED,
    E2E_STAGE_REVIEW_REQUIRED,
    E2E_STAGE_SKIPPED,
    E2E_STAGE_SUCCESS,
    E2E_SUCCESS,
    E2ERunSummary,
    E2EStageOutcome,
    compute_environment_block,
    run_end_to_end_pipeline,
)
from customer_segmentation.prototype.end_to_end.scope import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
    E2E_ID_HEX_LEN,
    E2E_ID_PREFIX,
    E2E_STAGE_ORDER,
    END_TO_END_SCHEMA_VERSION,
    E2EStage,
    Lifecycle,
    StageStatus,
)
from customer_segmentation.prototype.end_to_end.show import (
    format_run_summary,
    load_run_summary,
)
from customer_segmentation.prototype.end_to_end.storage import (
    derive_e2e_run_id,
    end_to_end_run_dir,
    list_e2e_runs,
    resolve_e2e_storage_root,
    resolve_storage_root,
)

__all__ = [
    # Scope / constants
    "END_TO_END_SCHEMA_VERSION",
    "E2E_ID_PREFIX",
    "E2E_ID_HEX_LEN",
    "E2E_STAGE_ORDER",
    "E2EStage",
    "Lifecycle",
    "StageStatus",
    "BANNED_SUBSTRINGS",
    "DEFAULT_DISCLAIMER_TEXT",
    # Errors
    "Dev09Error",
    "Dev09InputError",
    "Dev09ConfigError",
    "Dev09StoragePathError",
    # Config
    "DEFAULT_DEV09_CONFIG_PATH",
    "DEV09_CONFIG_TOP_KEY",
    "Dev09DisplayConfig",
    "Dev09StageSelectionConfig",
    "Dev09StorageConfig",
    "Dev09LoggingConfig",
    "Dev09PersistenceConfig",
    "Dev09ResearchSafetyConfig",
    "Dev09Config",
    "load_dev09_config",
    # Storage / persistence
    "derive_e2e_run_id",
    "end_to_end_run_dir",
    "list_e2e_runs",
    "resolve_e2e_storage_root",
    "resolve_storage_root",
    # Pipeline
    "E2E_SUCCESS",
    "E2E_CACHED",
    "E2E_FAILED",
    "E2E_CONDITIONAL",
    "E2E_BLOCKED",
    "E2E_STAGE_SUCCESS",
    "E2E_STAGE_CACHED",
    "E2E_STAGE_FAILED",
    "E2E_STAGE_SKIPPED",
    "E2E_STAGE_BLOCKED",
    "E2E_STAGE_REVIEW_REQUIRED",
    "E2EStageOutcome",
    "E2ERunSummary",
    "compute_environment_block",
    "run_end_to_end_pipeline",
    # Show / reload
    "format_run_summary",
    "load_run_summary",
    # Logging
    "DEV09_LOGGER_NAME",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "get_logger",
]
