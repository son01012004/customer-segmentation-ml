"""DEV-02 Dataset Management — public API.

This package is the **prototype-layer** dataset-management surface.
It imports a user-supplied CSV or Parquet file, validates it, and
writes a content-keyed manifest under
``data/prototype/datasets/<dataset_id>/``.

It does **not** change the research methodology, does not modify
``data/raw/primary/``, ``data/raw/backup/``, ``data/processed/``, or
``reports/**``, and does not require any new third-party dependency.

Architecture
------------
- ADR-0005 Option A: offline, single-machine, file-based.
- No backend / API / database / worker / queue.
- Storage root fixed in ``configs/dev02_dataset_management.yaml``;
  the CLI has no ``--dest-root`` override.

Reuse
-----
- :mod:`customer_segmentation.data.audit` — read-only
  (``basic_overview``, ``missing_profile``, ``numerical_profile``,
  ``categorical_profile``).
- :mod:`customer_segmentation.data.validator` — only the
  :class:`ValidationResult` dataclass as a type reference.
- :mod:`customer_segmentation.transformation.versioning` — only
  :func:`compute_file_sha256`.

Public API
----------
The names re-exported here are the complete public surface of the
package. Anything not listed is considered internal.
"""

from __future__ import annotations

from customer_segmentation.dataset_management.importer import (
    DEFAULT_CONFIG_PATH,
    ImportError,
    ImportRequest,
    ImportResult,
    MIXED_TYPE_RANKS,
    build_request_from_args,
    detect_mixed,
    detect_schema,
    import_dataset,
)
from customer_segmentation.dataset_management.list import (
    DatasetNotFound,
    DatasetSummary,
    get_dataset,
    list_datasets,
)
from customer_segmentation.dataset_management.manifest import (
    MANIFEST_SCHEMA_VERSION,
    CategoricalStats,
    ColumnInfo,
    Manifest,
    ManifestError,
    NumericStats,
    Provenance,
    ResearchSafety,
    StatisticsSummary,
    StorageInfo,
    ValidationBlock,
    ValidationCategory,
    now_iso,
    read_manifest,
    runtime_field_names,
    stable_field_names,
    update_last_seen,
    write_manifest,
)
from customer_segmentation.dataset_management.scope import (
    DATASET_SCOPES,
    VALIDATION_RESULTS,
    VALIDATION_STATUSES,
    DatasetScope,
    ValidationResult,
    ValidationStatus,
)
from customer_segmentation.dataset_management.storage import (
    DATASET_ID_HEX_LEN,
    DATASET_ID_PREFIX,
    StoragePathError,
    dataset_dir,
    derive_dataset_id,
    find_existing_dataset,
    load_config,
    resolve_storage_root,
    validate_config,
)
from customer_segmentation.dataset_management.validation import (
    CategoryResult,
    FilePreflightError,
    aggregate,
    lifecycle_status_for_pass,
    map_to_lifecycle,
    run_validation,
)

__all__ = [
    # scope
    "DatasetScope",
    "ValidationStatus",
    "ValidationResult",
    "DATASET_SCOPES",
    "VALIDATION_STATUSES",
    "VALIDATION_RESULTS",
    # storage
    "DATASET_ID_PREFIX",
    "DATASET_ID_HEX_LEN",
    "StoragePathError",
    "derive_dataset_id",
    "dataset_dir",
    "find_existing_dataset",
    "load_config",
    "resolve_storage_root",
    "validate_config",
    # manifest
    "MANIFEST_SCHEMA_VERSION",
    "ManifestError",
    "StorageInfo",
    "ColumnInfo",
    "NumericStats",
    "CategoricalStats",
    "StatisticsSummary",
    "ValidationCategory",
    "ValidationBlock",
    "Provenance",
    "ResearchSafety",
    "Manifest",
    "stable_field_names",
    "runtime_field_names",
    "write_manifest",
    "read_manifest",
    "update_last_seen",
    "now_iso",
    # validation
    "CategoryResult",
    "FilePreflightError",
    "run_validation",
    "aggregate",
    "map_to_lifecycle",
    "lifecycle_status_for_pass",
    # importer
    "DEFAULT_CONFIG_PATH",
    "ImportRequest",
    "ImportResult",
    "ImportError",
    "import_dataset",
    "build_request_from_args",
    "detect_schema",
    "detect_mixed",
    "MIXED_TYPE_RANKS",
    # list
    "DatasetSummary",
    "DatasetNotFound",
    "list_datasets",
    "get_dataset",
]
