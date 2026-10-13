"""Prototype-layer clustering execution package for DEV-04.

This package provides prototype-layer clustering execution capability for
downstream prototype DEVs (DEV-05 → DEV-09). It wraps the research core
(ML-01 framework + ML-02..06 adapters) and adds per-stage pipeline
driver, manifest, and storage helpers.

The package is **the prototype layer**. It does not change research
methodology and does not modify any research artefact.

Public API (re-exported at the bottom; anything not listed is internal).
"""

from __future__ import annotations

from customer_segmentation.prototype.clustering.config_loader import (
    DEFAULT_DEV04_CONFIG_PATH,
    Dev04AlgorithmHyperparameterConfig,
    Dev04Config,
    Dev04ConfigError,
    Dev04LoggingConfig,
    Dev04RandomSeedConfig,
    Dev04ResearchSafetyConfig,
    Dev04StorageConfig,
    Dev04ValidationConfig,
    find_default_dev04_config_path,
    load_dev04_config,
)
from customer_segmentation.prototype.clustering.logging_config import (
    DEV04_LOGGER_NAME,
    PerStageLogger,
    PerStageLogHandler,
    configure_logging,
    finalize_logging,
    now_iso,
)
from customer_segmentation.prototype.clustering.manifest import (
    CLUSTERING_MANIFEST_SCHEMA_VERSION,
    ClusteringManifest,
    ClusteringManifestError,
    EnvironmentBlock,
    InputIdentityBlock,
    ResearchSafetyBlock,
    build_clustering_manifest,
    read_clustering_manifest,
    runtime_field_names,
    stable_field_names,
    write_clustering_manifest,
)
from customer_segmentation.prototype.clustering.pipeline import (
    ClusteringPipelineResult,
    run_clustering_pipeline,
)
from customer_segmentation.prototype.clustering.scope import (
    CLUSTERED_SCOPES,
    CLUSTERING_STAGES,
    DETERMINISTIC_ALGORITHMS,
    STOCHASTIC_ALGORITHMS,
    SUPPORTED_ALGORITHMS,
    ClusteredScope,
    ClusteringStage,
    run_clustering_experiment,
)
from customer_segmentation.prototype.clustering.storage import (
    CLUSTERING_ID_HEX_LEN,
    CLUSTERING_ID_PREFIX,
    Dev04CollisionError,
    Dev04ManifestCorrupt,
    Dev04StoragePathError,
    derive_clustering_id,
    find_existing_clustering,
    prototype_clustering_base_dir,
    prototype_clustering_run_dir,
    recover_orphan_backups,
    resolve_storage_root,
)

__all__ = [
    # Config
    "DEFAULT_DEV04_CONFIG_PATH",
    "Dev04AlgorithmHyperparameterConfig",
    "Dev04Config",
    "Dev04ConfigError",
    "Dev04LoggingConfig",
    "Dev04RandomSeedConfig",
    "Dev04ResearchSafetyConfig",
    "Dev04StorageConfig",
    "Dev04ValidationConfig",
    "find_default_dev04_config_path",
    "load_dev04_config",
    # Logging
    "DEV04_LOGGER_NAME",
    "PerStageLogHandler",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "now_iso",
    # Manifest
    "CLUSTERING_MANIFEST_SCHEMA_VERSION",
    "ClusteringManifest",
    "ClusteringManifestError",
    "EnvironmentBlock",
    "InputIdentityBlock",
    "ResearchSafetyBlock",
    "build_clustering_manifest",
    "read_clustering_manifest",
    "runtime_field_names",
    "stable_field_names",
    "write_clustering_manifest",
    # Pipeline
    "ClusteringPipelineResult",
    "run_clustering_pipeline",
    # Scope
    "CLUSTERED_SCOPES",
    "CLUSTERING_STAGES",
    "ClusteredScope",
    "ClusteringStage",
    "DETERMINISTIC_ALGORITHMS",
    "STOCHASTIC_ALGORITHMS",
    "SUPPORTED_ALGORITHMS",
    "run_clustering_experiment",
    # Storage
    "CLUSTERING_ID_HEX_LEN",
    "CLUSTERING_ID_PREFIX",
    "Dev04CollisionError",
    "Dev04ManifestCorrupt",
    "Dev04StoragePathError",
    "derive_clustering_id",
    "find_existing_clustering",
    "prototype_clustering_base_dir",
    "prototype_clustering_run_dir",
    "recover_orphan_backups",
    "resolve_storage_root",
]
