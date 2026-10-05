"""Clustering algorithms: K-Means, K-Medoids, Agglomerative, DBSCAN.

ML-01 — Clustering Experiment Framework
=======================================

This module exposes the **experiment framework** that ML-02 → ML-06
plug into. ML-01 itself does **NOT** implement K-Means, K-Medoids,
Agglomerative, DBSCAN, GMM, or Fuzzy C-Means; it only defines the
abstractions they MUST satisfy.

Architecture (YAGNI-friendly):

- :class:`BaseClusterAlgorithm` — abstract base class for algorithm
  adapters. See :mod:`customer_segmentation.clustering.base`.
- :class:`AlgorithmRegistry` — in-process registry mapping
  ``name → adapter class``. See :mod:`customer_segmentation.clustering.registry`.
- :class:`ClusterResult` / :class:`ExperimentResult` — unified schema
  supporting hard labels, noise labels (DBSCAN), soft probabilities
  (GMM), soft membership (Fuzzy C-Means), and metrics placeholders for
  EPIC-07/08. See :mod:`customer_segmentation.clustering.result`.
- :func:`validate_clustering_matrix` and
  :func:`validate_customer_alignment` — fail-fast input validation.
  See :mod:`customer_segmentation.clustering.validation`.
- :class:`FrameworkConfig` — typed configuration loader for
  ``configs/clustering.yaml``. See
  :mod:`customer_segmentation.clustering.config`.
- :class:`ExperimentRunner` — single entry point that runs an
  experiment end-to-end (validate → fit → write artifacts → log).
  See :mod:`customer_segmentation.clustering.runner`.
- Artifact writers (:func:`write_cluster_labels`,
  :func:`write_algorithm_output`, :func:`write_experiment_artifacts`)
  — never mutate the FE-06 final clustering dataset or the customer
  metadata parquet. See :mod:`customer_segmentation.clustering.artifacts`.
- :func:`get_logger` / :func:`write_experiment_log` — experiment
  logging helpers. See :mod:`customer_segmentation.clustering.logging_utils`.

Algorithm adapter status (EPIC-06 / ML-02 onwards):

- ML-02 K-Means adapter — TECHNICALLY_IMPLEMENTED (see
  :class:`customer_segmentation.clustering.kmeans.KMeansAdapter`).
- ML-03 Agglomerative adapter — TECHNICALLY_IMPLEMENTED (see
  :class:`customer_segmentation.clustering.agglomerative.AgglomerativeAdapter`).
- ML-04 DBSCAN adapter — TECHNICALLY_IMPLEMENTED (see
  :class:`customer_segmentation.clustering.dbscan.DBSCANAdapter`).
- ML-05 GMM adapter — TECHNICALLY_IMPLEMENTED (see
  :class:`customer_segmentation.clustering.gmm.GMMAdapter`).
- ML-06 Fuzzy C-Means adapter — TECHNICALLY_IMPLEMENTED (see
  :class:`customer_segmentation.clustering.fuzzy_cmeans.FuzzyCMeansAdapter`).

Hard constraints (AGENTS.md §2-§3):

- ML-01 builds the framework only. No algorithm implementation here.
- No clustering experiment is launched by importing this module.
  Callers must build an :class:`ExperimentSpec` and pass it to
  :class:`ExperimentRunner`.
- No evaluation metrics are computed in ML-01; the schema has
  placeholders that EPIC-07/08 will populate.
- No "best/recommended/optimal/winner" language anywhere.
- The framework never mutates the FE-06 final clustering dataset.
"""

from customer_segmentation.clustering.agglomerative import AgglomerativeAdapter  # noqa: F401
from customer_segmentation.clustering.base import (
    BaseClusterAlgorithm,
    ClusterAlgorithmError,
)
from customer_segmentation.clustering.config import (
    DEFAULT_CLUSTERING_CONFIG_PATH,
    ExperimentConfig,
    FrameworkConfig,
    FrameworkConfigError,
    InputConfig,
    LoggingConfig,
    MetadataConfig,
    OutputConfig,
    RandomSeedConfig,
    ValidationConfig,
    compute_text_sha256,
    framework_config_to_dict,
    load_framework_config,
    resolve_framework_config_path,
)
from customer_segmentation.clustering.dbscan import DBSCANAdapter  # noqa: F401
from customer_segmentation.clustering.fuzzy_cmeans import FuzzyCMeansAdapter  # noqa: F401
from customer_segmentation.clustering.gmm import GMMAdapter  # noqa: F401
from customer_segmentation.clustering.kmeans import KMeansAdapter  # noqa: F401
from customer_segmentation.clustering.kmedoids import fit_kmedoids  # noqa: F401
from customer_segmentation.clustering.logging_utils import (
    get_logger,
    now_utc_iso,
    setup_file_logging,
    write_experiment_log,
)
from customer_segmentation.clustering.registry import (
    AlgorithmRegistry,
    AlgorithmRegistryError,
)
from customer_segmentation.clustering.result import (
    AlgorithmFamily,
    ClusterResult,
    ClusterResultEncoder,
    ExperimentResult,
    ExperimentStatus,
    MetricsResult,
    cluster_result_to_dict,
)
from customer_segmentation.clustering.runner import (
    ExperimentRunner,
    ExperimentSpec,
    RunnerError,
    capture_library_versions,
    capture_platform_info,
    resolve_random_seed,
)
from customer_segmentation.clustering.validation import (
    ClusteringInputError,
    IdentifierLeakageError,
    ValidationCheck,
    ValidationReport,
    validate_clustering_matrix,
    validate_customer_alignment,
)

__all__ = [
    # Base / registry
    "BaseClusterAlgorithm",
    "ClusterAlgorithmError",
    "AlgorithmRegistry",
    "AlgorithmRegistryError",
    # ML-02 algorithm adapter
    "KMeansAdapter",
    # ML-03 algorithm adapter
    "AgglomerativeAdapter",
    # ML-04 algorithm adapter
    "DBSCANAdapter",
    # ML-05 algorithm adapter
    "GMMAdapter",
    # ML-06 algorithm adapter
    "FuzzyCMeansAdapter",
    # Result schema
    "AlgorithmFamily",
    "ClusterResult",
    "ClusterResultEncoder",
    "cluster_result_to_dict",
    "ExperimentResult",
    "ExperimentStatus",
    "MetricsResult",
    # Validation
    "ValidationCheck",
    "ValidationReport",
    "validate_clustering_matrix",
    "validate_customer_alignment",
    "ClusteringInputError",
    "IdentifierLeakageError",
    # Config
    "DEFAULT_CLUSTERING_CONFIG_PATH",
    "FrameworkConfig",
    "FrameworkConfigError",
    "ExperimentConfig",
    "InputConfig",
    "LoggingConfig",
    "MetadataConfig",
    "OutputConfig",
    "RandomSeedConfig",
    "ValidationConfig",
    "compute_text_sha256",
    "framework_config_to_dict",
    "load_framework_config",
    "resolve_framework_config_path",
    # Runner
    "ExperimentRunner",
    "ExperimentSpec",
    "RunnerError",
    "capture_library_versions",
    "capture_platform_info",
    "resolve_random_seed",
    # Logging
    "get_logger",
    "now_utc_iso",
    "setup_file_logging",
    "write_experiment_log",
]
