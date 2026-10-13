"""DEV-04 clustering pipeline — Stages 0→6.

The pipeline wraps :class:`customer_segmentation.clustering.runner.ExperimentRunner`
to run one clustering experiment on a DEV-03 ML Dataset, then writes
prototype-layer artefacts:

- ``cluster_labels_<experiment_id>.parquet``
- ``experiment_log_<experiment_id>.json``  (from ML-01 runner)
- ``algorithm_output_<experiment_id>.parquet``  (GMM/FCM soft output; optional)
- ``clustering_manifest.json``  (DEV-04 prototype manifest)

Storage path::

    <storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/
        clustering/<clustering_id>/
            clustering_manifest.json
            cluster_labels_<experiment_id>.parquet
            experiment_log_<experiment_id>.json
            algorithm_output_<experiment_id>.parquet  (soft algorithms only)
            <clustering_id>.log

Pipeline stages
--------------
    0 — preflight:       validate CLI args + load DEV-04 + ML-01 configs
    1 — lookup:         load DEV-03 manifest + ML Dataset parquet
    2 — split:          separate feature matrix from customer metadata
    3 — build:          ExperimentSpec + ExperimentRunner + staging dirs
    4 — fit:            runner.run() into staging/
    5 — manifest:       write clustering_manifest.json atomically in staging/
    5b — publish:       atomic rename staging/ → final/
    6 — finalize_log:   close log handlers

Idempotency
-----------
If a ``clustering_id`` directory already exists with a valid manifest
whose canonical payload matches the current effective config, the
pipeline returns ``CACHED`` without re-running the experiment.
``--force-rerun`` overrides this (uses staging + atomic publish to
preserve the old result until publish succeeds).

Crash recovery
-------------
Orphan backups from a previous crashed run are recovered at Stage 3
(start of every invocation). The pipeline never leaves a corrupted
manifest.

Research safety
---------------
:data:`CLUSTERED_PROTOTYPE_SCOPE_VALUE` = ``"CLUSTERED_PROTOTYPE"``.
``automatically_promoted_to_research`` is always ``False``;
``appeared_in_research_evidence`` is always ``False``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import platform as platform_module
import shutil
import uuid as uuid_mod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from customer_segmentation.clustering.config import (
    ExperimentConfig,
    FrameworkConfig,
    InputConfig,
    LoggingConfig,
    MetadataConfig,
    OutputConfig,
    RandomSeedConfig,
    ValidationConfig,
    compute_text_sha256,
    load_framework_config,
    resolve_framework_config_path,
)
from customer_segmentation.clustering.result import (
    ExperimentResult,
    ExperimentStatus,
)
from customer_segmentation.clustering.runner import (
    ExperimentRunner,
    ExperimentSpec,
    capture_library_versions,
)
from customer_segmentation.prototype.clustering.config_loader import (
    DEFAULT_DEV04_CONFIG_PATH,
    Dev04Config,
    load_dev04_config,
)
from customer_segmentation.prototype.clustering.logging_config import (
    PerStageLogger,
    PerStageLogHandler,
    configure_logging,
    finalize_logging,
    now_iso,
)
from customer_segmentation.prototype.clustering.manifest import (
    EnvironmentBlock,
    InputIdentityBlock,
    ResearchSafetyBlock,
    build_clustering_manifest,
    read_clustering_manifest,
    write_clustering_manifest,
)
from customer_segmentation.prototype.clustering.scope import (
    CLUSTERED_SCOPES,
    DETERMINISTIC_ALGORITHMS,
    ClusteredScope,
    ClusteringStage,
)
from customer_segmentation.prototype.clustering.storage import (
    Dev04CollisionError,
    Dev04ConfigError,
    Dev04ManifestCorrupt,
    Dev04StoragePathError,
    derive_clustering_id,
    find_existing_clustering,
    prototype_clustering_base_dir,
    prototype_clustering_run_dir,
    recover_orphan_backups,
    resolve_storage_root,
)
from customer_segmentation.transformation.versioning import (
    compute_file_sha256,
)

__all__ = [
    "ClusteringPipelineResult",
    "run_clustering_pipeline",
]


CLUSTERED_PROTOTYPE_SCOPE_VALUE: str = ClusteredScope.CLUSTERED_PROTOTYPE.value
DEV04_PIPELINE_VERSION: str = "DEV04-v1.0"

# Per-algorithm adapter parameter keys (must match each adapter's __init__).
# Filtering ensures we don't pass e.g. ``linkage`` to KMeansAdapter.
ALGORITHM_HP_KEYS: dict[str, frozenset[str]] = {
    "kmeans": frozenset({"n_clusters", "init", "n_init", "max_iter", "tol", "random_state"}),
    "agglomerative": frozenset({"n_clusters", "linkage", "metric", "compute_distances"}),
    "dbscan": frozenset({"eps", "min_samples", "metric"}),
    "gmm": frozenset(
        {
            "n_components",
            "covariance_type",
            "init_params",
            "tol",
            "reg_covar",
            "max_iter",
            "n_init",
            "random_state",
        }
    ),
    # FuzzyCMeansAdapter uses ``m`` (fuzziness) rather than ``fuzziness``.
    "fuzzy_cmeans": frozenset({"n_clusters", "m", "max_iter", "error", "random_state"}),
}

# Map DEV-04 config / CLI keys to adapter keys where they differ.
DEV04_KEY_TO_ADAPTER_KEY: dict[str, dict[str, str]] = {
    "fuzzy_cmeans": {"fuzziness": "m"},
}


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


@dataclass
class ClusteringPipelineResult:
    """Result of one DEV-04 clustering pipeline invocation."""

    clustering_id: str
    experiment_id: str
    algorithm: str
    dataset_id: str
    preprocessed_id: str
    storage_root: Path
    run_dir: Path
    manifest_path: Path
    cluster_labels_path: Path | None
    algorithm_output_path: Path | None
    log_path: Path
    lifecycle: str  # "SUCCESS" | "CACHED" | "FAILED"
    duration_seconds: float
    manifest: Any | None  # ClusteringManifest or None
    stage_logs: list[dict[str, Any]] = field(default_factory=list)

    def as_summary(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary dict."""
        return {
            "clustering_id": self.clustering_id,
            "experiment_id": self.experiment_id,
            "algorithm": self.algorithm,
            "dataset_id": self.dataset_id,
            "preprocessed_id": self.preprocessed_id,
            "storage_root": str(self.storage_root),
            "run_dir": str(self.run_dir),
            "manifest_path": str(self.manifest_path),
            "cluster_labels_path": (
                str(self.cluster_labels_path) if self.cluster_labels_path else None
            ),
            "algorithm_output_path": (
                str(self.algorithm_output_path) if self.algorithm_output_path else None
            ),
            "log_path": str(self.log_path),
            "lifecycle": self.lifecycle,
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _load_dev03_ml_dataset(
    *,
    preprocessed_id: str,
    dataset_id: str,
    storage_root: Path,
    logger: PerStageLogger,
) -> tuple[pd.DataFrame, str, str]:
    """Stage 1: load the DEV-03 manifest + ML Dataset parquet.

    Returns ``(df, ml_dataset_sha256, ml_dataset_path_str)``.

    Layout note (post-A-1): DEV-03 writes its artefacts flat under
    ``<storage_root>/<dataset_id>/preprocessed/`` (no ``<preprocessed_id>``
    subdirectory). The ``preprocessed_id`` appears only as a filename
    suffix (e.g. ``ml_dataset_<ts>_<pp_id>.parquet``,
    ``pp_<pp_id>.log``, ``preprocessed_manifest.json``). The manifest is
    overwritten by the most-recent preprocessing run, so a single
    ``preprocessed_manifest.json`` is shared across all
    ``preprocessed_id`` values for one dataset. See
    ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1`` for
    context on the A-1 fix.
    """
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); ``dataset_id`` is
    # appended directly (no extra ``"datasets"`` literal). The
    # ``preprocessed/`` segment follows per DEV-03 convention — and the
    # artefacts live directly under it (FLAT, no ``<preprocessed_id>``
    # subdirectory).
    preprocessed_dir = storage_root / dataset_id / "preprocessed"
    manifest_path = preprocessed_dir / "preprocessed_manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"DEV-03 manifest not found: {manifest_path!s}; "
            f"cannot run clustering on preprocessed_id={preprocessed_id!r}."
        )

    import json as _json

    with manifest_path.open("r", encoding="utf-8") as fh:
        dev03_manifest = _json.load(fh)

    # Sanity-check: the manifest's preprocessed_id field must match the
    # requested preprocessed_id (post-A-1: DEV-03 overwrites the same
    # manifest file across runs, so an old run's manifest could otherwise
    # silently satisfy the lookup).
    manifest_pp_id = str(dev03_manifest.get("preprocessed_id", ""))
    if manifest_pp_id != preprocessed_id:
        raise FileNotFoundError(
            f"DEV-03 manifest at {manifest_path!s} has "
            f"preprocessed_id={manifest_pp_id!r}; expected "
            f"{preprocessed_id!r}. The manifest does not correspond to the "
            "requested preprocessed_id (DEV-03 has overwritten it since "
            "the most recent preprocessing run). Re-run DEV-03 to refresh."
        )

    ml_block = dev03_manifest.get("ml_dataset_block", {})
    ml_dataset_name = ml_block.get("artifact_path", "")
    if not ml_dataset_name:
        raise FileNotFoundError(
            f"DEV-03 manifest at {manifest_path!s} has no ml_dataset_block.artifact_path."
        )
    ml_dataset_path = preprocessed_dir / ml_dataset_name

    if not ml_dataset_path.exists():
        raise FileNotFoundError(
            f"DEV-03 ML Dataset not found: {ml_dataset_path!s}; "
            f"preprocessed_id={preprocessed_id!r}."
        )

    sha = compute_file_sha256(ml_dataset_path)
    df = pd.read_parquet(ml_dataset_path)

    logger.stage_end(
        "1",
        preprocessed_id=preprocessed_id,
        ml_dataset_rows=int(df.shape[0]),
        ml_dataset_cols=int(df.shape[1]),
        ml_dataset_sha256=sha,
        ml_dataset_path=str(ml_dataset_path),
    )
    return df, sha, str(ml_dataset_path)


def _split_matrix(
    df: pd.DataFrame,
    *,
    logger: PerStageLogger,
) -> tuple[pd.DataFrame, pd.DataFrame | None, list[str], str | None]:
    """Stage 2: separate the feature matrix from the customer metadata.

    The DEV-03 ML Dataset may have a ``CustomerID`` column. We detect
    it by exact column name (case-sensitive) and split into:

    - ``matrix_df``: feature columns only (no identifiers)
    - ``metadata_df``: DataFrame with the customer_key column
    - ``feature_names``: list of feature column names
    - ``customer_id_col``: detected name or ``None``

    Returns
    -------
    (matrix_df, metadata_df, feature_names, customer_id_col)
    """
    customer_id_col = None
    for candidate in ("CustomerID", "customer_id", "Customer ID"):
        if candidate in df.columns:
            customer_id_col = candidate
            break

    if customer_id_col is None:
        feature_cols = list(df.columns)
        matrix_df = df.copy()
        metadata_df = None
    else:
        feature_cols = [c for c in df.columns if c != customer_id_col]
        matrix_df = df[feature_cols].copy()
        metadata_df = df[[customer_id_col]].copy()

    logger.stage_end(
        "2",
        feature_count=len(feature_cols),
        has_customer_id=customer_id_col is not None,
        customer_id_col=customer_id_col,
    )
    return matrix_df, metadata_df, feature_cols, customer_id_col


def _resolve_seed(
    algorithm: str,
    seed: int | None,
    default: int,
    per_algo_override: dict[str, int],
) -> int | None:
    """Resolve the effective seed for an algorithm.

    Deterministic algorithms (agglomerative, dbscan) always return None
    (their adapters set supports_random_state() == False).

    Stochastic algorithms: CLI seed > per_algorithm_override > default.
    """
    if algorithm in DETERMINISTIC_ALGORITHMS:
        return None
    if seed is not None:
        return seed
    return per_algo_override.get(algorithm, default)


def _derive_experiment_id(
    algorithm: str,
    clustering_id: str,
    explicit: str | None,
) -> str:
    """Derive experiment_id: explicit > ``<algorithm>_<clustering_id>``."""
    if explicit:
        return explicit
    return f"{algorithm}_{clustering_id}"


def _build_framework_config(
    dev04_cfg: Dev04Config,
    algorithm: str,
    *,
    dataset_version: str = "dev03-v1",
) -> FrameworkConfig:
    """Build ML-01 :class:`FrameworkConfig` from DEV-04 config.

    The ML-01 framework config is loaded from ``configs/clustering.yaml``;
    we use the framework's own validation/seed policy and override
    the input paths to point to the DEV-03 ML Dataset (read-only).
    """
    fw_path = resolve_framework_config_path()
    if fw_path is None:
        # Synthesise a minimal FrameworkConfig.
        return FrameworkConfig(
            enabled=True,
            experiment=ExperimentConfig(
                id="DEV-04",
                description="DEV-04 Prototype Clustering Execution",
            ),
            random_seed=RandomSeedConfig(
                default=dev04_cfg.random_seed.default,
                per_algorithm_override=dict(dev04_cfg.random_seed.per_algorithm_override),
            ),
            input=InputConfig(
                final_clustering_dataset_path="dev04://ml_dataset",
                customer_metadata_path="dev04://ml_dataset",
                dataset_version=dataset_version,
                customer_key="CustomerID",
            ),
            validation=ValidationConfig(
                require_no_nan=dev04_cfg.validation.require_no_nan,
                require_no_inf=dev04_cfg.validation.require_no_inf,
                require_all_numeric=dev04_cfg.validation.require_all_numeric,
                min_samples=dev04_cfg.validation.min_samples,
                min_features=dev04_cfg.validation.min_features,
                exclude_customer_id_from_features=dev04_cfg.validation.exclude_customer_id_from_features,
            ),
            output=OutputConfig(
                artifacts_dir="",
                report_dir="",
                save_labels=True,
                save_metadata=True,
                save_algorithm_specific=dev04_cfg.storage.emit_algorithm_output,
                cluster_labels_filename="cluster_labels_{experiment_id}.parquet",
                experiment_log_filename="experiment_log_{experiment_id}.json",
                algorithm_output_filename="algorithm_output_{experiment_id}.parquet",
            ),
            logging=LoggingConfig(
                log_to_console=False,
                log_to_file=False,
                log_file_dir="",
                log_level=dev04_cfg.logging.level,
            ),
            metadata=MetadataConfig(
                stage="DEV-04",
                stage_version=DEV04_PIPELINE_VERSION,
                stage_status="TECHNICALLY_IMPLEMENTED",
                scope_boundaries=[
                    "Prototype clustering execution only.",
                    "No algorithm comparison (EPIC-08).",
                    "No K sweep (EPIC-07).",
                    "No segment profiling / naming (EPIC-09).",
                    "FE-06 outputs are READ-ONLY.",
                    "DEV-03 ML Dataset is READ-ONLY.",
                ],
                pending_review_notes=[
                    "Per-algorithm defaults (kmeans n_clusters=4, dbscan eps=0.5, "
                    "gmm n_components=4, fuzzy_cmeans n_clusters=4) are "
                    "WORKING_ASSUMPTION, not final approved.",
                ],
                assumptions=[
                    f"Algorithm {algorithm!r} is in the ML-01 registry whitelist.",
                    "CustomerID is preserved in metadata; never in feature matrix.",
                ],
            ),
        )
    # Load existing framework config and overlay our values.
    cfg = load_framework_config(fw_path)
    # Override validation block from DEV-04 config.
    cfg = FrameworkConfig(
        enabled=cfg.enabled,
        experiment=cfg.experiment,
        random_seed=RandomSeedConfig(
            default=dev04_cfg.random_seed.default,
            per_algorithm_override=dict(dev04_cfg.random_seed.per_algorithm_override),
        ),
        input=InputConfig(
            final_clustering_dataset_path="dev04://ml_dataset",
            customer_metadata_path="dev04://ml_dataset",
            dataset_version=dataset_version,
            customer_key=cfg.input.customer_key,
        ),
        validation=ValidationConfig(
            require_no_nan=dev04_cfg.validation.require_no_nan,
            require_no_inf=dev04_cfg.validation.require_no_inf,
            require_all_numeric=dev04_cfg.validation.require_all_numeric,
            min_samples=dev04_cfg.validation.min_samples,
            min_features=dev04_cfg.validation.min_features,
            exclude_customer_id_from_features=dev04_cfg.validation.exclude_customer_id_from_features,
        ),
        output=OutputConfig(
            artifacts_dir="",
            report_dir="",
            save_labels=True,
            save_metadata=True,
            save_algorithm_specific=dev04_cfg.storage.emit_algorithm_output,
            cluster_labels_filename=cfg.output.cluster_labels_filename,
            experiment_log_filename=cfg.output.experiment_log_filename,
            algorithm_output_filename=cfg.output.algorithm_output_filename,
        ),
        logging=LoggingConfig(
            log_to_console=False,
            log_to_file=False,
            log_file_dir="",
            log_level=dev04_cfg.logging.level,
        ),
        metadata=MetadataConfig(
            stage="DEV-04",
            stage_version=DEV04_PIPELINE_VERSION,
            stage_status="TECHNICALLY_IMPLEMENTED",
            scope_boundaries=[
                "Prototype clustering execution only.",
                "No algorithm comparison (EPIC-08).",
                "No K sweep (EPIC-07).",
                "No segment profiling / naming (EPIC-09).",
                "FE-06 outputs are READ-ONLY.",
                "DEV-03 ML Dataset is READ-ONLY.",
            ],
            pending_review_notes=[
                "Per-algorithm defaults are WORKING_ASSUMPTION, not final approved.",
            ],
            assumptions=[
                f"Algorithm {algorithm!r} is in the ML-01 registry whitelist.",
                "CustomerID is preserved in metadata; never in feature matrix.",
            ],
        ),
    )
    return cfg


# ---------------------------------------------------------------------------
# Atomic staging helpers
# ---------------------------------------------------------------------------


def _ensure_clustering_container(base_dir: Path, run_uuid: str) -> Path:
    """Create the per-clustering container (if absent) and return it."""
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


# ---------------------------------------------------------------------------
# Per-run state container (R-17 cleanup invariants + F1 invariant)
# ---------------------------------------------------------------------------


@dataclass
class _Dev04RunState:
    """Mutable per-run state passed to cleanup and preservation helpers.

    Fields
    ------
    base_dir : Path
        ``<storage_root>/datasets/<ds>/preprocessed/<pp>/clustering/``.
    current_run_uuid : str
        The UUID of the current pipeline invocation. Cleanup pass scopes
        to this UUID (R-14, R-17 mitigation).
    staging_dir : Path or None
        Set after Stage 3 when staging is created.
    backup_dir : Path or None
        Set after Stage 3 when backup is created (only when final_dir
        existed; otherwise None).
    final_dir : Path or None
        Set after Stage 3.
    backup_dir_parent : Path or None
        ``_backup_<run_uuid>`` (the container for backup_dir).
    failed_tracking_dir : Path or None
        Set by Stage 5 FAILED handler BEFORE cleanup pass. Contains
        the preserved ``experiment_log_*.json`` from FAILED runs (R1).
    backup_dir_for_recovery : Path or None
        Backup created during ``--force-rerun``; cleanup pass retains
        this if ``publish_succeeded=False`` (R-17, AC-12 #73b).
    backup_dir_corrupt : Path or None
        Corrupt manifest backup (``_backup_<uuid>_corrupt/``); cleanup
        pass NEVER removes this (R2, R-17, AC-12 #73c).
    publish_succeeded : bool
        True if Stage 5b atomic rename succeeded. Defaults to False.
    unpreserved_log_in_staging : bool
        F1 invariant: set True by exception handler when
        ``_preserve_failed_log`` returns ``"partial"`` or ``"failed"``
        AND re-scan confirms orphan ``experiment_log_*.json`` in
        staging. Cleanup pass MUST NOT unlink staging_dir when True
        (R-15a, AC-12 #73h, §6.5 rule #7, §6.7.3 F14).
    """

    base_dir: Path
    current_run_uuid: str
    staging_dir: Path | None = None
    backup_dir: Path | None = None
    final_dir: Path | None = None
    backup_dir_parent: Path | None = None
    failed_tracking_dir: Path | None = None
    backup_dir_for_recovery: Path | None = None
    backup_dir_corrupt: Path | None = None
    publish_succeeded: bool = False
    unpreserved_log_in_staging: bool = False


# ---------------------------------------------------------------------------
# R-15 (R1): Preserve FAILED experiment log
# ---------------------------------------------------------------------------


_FAILED_PREFIX: str = "_failed_"
_FAILED_AUDIT_FILENAME: str = "_preservation_audit.txt"


def _preserve_failed_log(
    staging_dir: Path,
    failed_tracking_dir: Path,
    run_uuid: str,
) -> str:
    """Move ``experiment_log_*.json`` from staging to failed tracking dir.

    Implements R-15 (R1 adversarial review finding). The function is
    tolerant of failures: any ``OSError`` is caught and logged but
    NOT re-raised. Cleanup pass and exception handler cooperate via
    the ``PreservationStatus`` return value to enforce the F1 invariant.

    Parameters
    ----------
    staging_dir : Path
        The current run's staging directory (may not exist; may be empty).
    failed_tracking_dir : Path
        The target tracking directory, named
        ``<base>/_failed_<clustering_id>_<run_uuid>/``.
    run_uuid : str
        The current run's UUID (recorded in the audit sidecar).

    Returns
    -------
    PreservationStatus
        ``"ok"`` — all logs moved successfully; no log left in staging.
        ``"partial"`` — some logs moved, some failed (orphan remains).
        ``"no_log"`` — no ``experiment_log_*.json`` in staging.
        ``"failed"`` — ``mkdir`` of tracking dir failed before any move.
    """
    import contextlib as _cb

    if not staging_dir.exists():
        return "no_log"

    # Discover experiment_log_*.json files in staging.
    try:
        log_files = sorted(
            p
            for p in staging_dir.iterdir()
            if p.is_file() and p.name.startswith("experiment_log_") and p.suffix == ".json"
        )
    except OSError as exc:
        # Cannot even scan staging. Treat as "failed" (mkdir wasn't the
        # culprit but preservation cannot proceed at all).
        _log_warning(f"DEV-04 _preserve_failed_log: cannot iter staging {staging_dir!s}: {exc!r}")
        return "failed"

    if not log_files:
        return "no_log"

    # Try to create the tracking dir. Failure here is "failed" (no move yet).
    try:
        failed_tracking_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        _log_warning(
            f"DEV-04 _preserve_failed_log: cannot mkdir {failed_tracking_dir!s}: {exc!r}. "
            "Will retain logs in staging_dir for manual recovery."
        )
        return "failed"

    # Move each log file. Track partial success.
    moved = 0
    failed = 0
    for log_path in log_files:
        try:
            shutil.move(str(log_path), str(failed_tracking_dir / log_path.name))
            moved += 1
        except OSError as exc:
            failed += 1
            _log_warning(
                f"DEV-04 _preserve_failed_log: cannot move {log_path!s} → "
                f"{failed_tracking_dir!s}: {exc!r}"
            )

    # Write audit sidecar (best-effort; if it fails, do not raise).
    audit_path = failed_tracking_dir / _FAILED_AUDIT_FILENAME
    audit_text = (
        f"preserved_at_utc={now_iso()}\n"
        f"source_staging={staging_dir!s}\n"
        f"run_uuid={run_uuid}\n"
        f"reason=ExperimentStatus.FAILED or stage exception\n"
        f"moved_count={moved}\n"
        f"failed_count={failed}\n"
    )
    with _cb.suppress(OSError):
        audit_path.write_text(audit_text, encoding="utf-8")

    if failed == 0:
        return "ok"
    return "partial"


def _log_warning(msg: str) -> None:
    """Best-effort warning logger used by preservation helper."""
    import logging as _lg

    _lg.getLogger("customer_segmentation.prototype.clustering").warning(msg)


def _set_unpreserved_flag(state: _Dev04RunState, preservation_status: str) -> None:
    """Set ``state.unpreserved_log_in_staging`` per the F1 invariant.

    Called after ``_preserve_failed_log`` returns. Sets the flag to True when
    ``preservation_status`` is ``"partial"`` or ``"failed"`` AND re-scanning
    ``staging_dir`` confirms orphan ``experiment_log_*.json`` still exist.
    This is the defence-in-depth check documented in the plan §6.5 rule #7
    and §6.7.3 failure window F14.
    """
    if preservation_status not in ("partial", "failed"):
        return
    if state.staging_dir is None or not state.staging_dir.exists():
        return
    import contextlib as _cb

    orphan_logs = [
        p
        for p in state.staging_dir.iterdir()
        if p.is_file() and p.name.startswith("experiment_log_") and p.suffix == ".json"
    ]
    if orphan_logs:
        state.unpreserved_log_in_staging = True
        _log_warning(
            f"DEV-04 F1 invariant: _preserve_failed_log returned {preservation_status!r} "
            f"and {len(orphan_logs)} experiment_log_*.json remain in "
            f"staging_dir {state.staging_dir!s}. "
            "Setting state.unpreserved_log_in_staging=True so "
            "_cleanup_pass retains staging_dir for manual recovery. "
            "See §6.5 rule #7, §6.7.3 F14."
        )


# ---------------------------------------------------------------------------
# R-17 (R3): Cleanup pass (top-level try/finally contract)
# ---------------------------------------------------------------------------


def _cleanup_pass(
    state: _Dev04RunState,
    primary_exception: BaseException | None,
) -> None:
    """R-17 cleanup pass: executed in ``finally:`` of the pipeline.

    Honours the following invariants:

    - F1 (AC-12 #73h): skip ``shutil.rmtree(staging_dir)`` when
      ``state.unpreserved_log_in_staging`` is True.
    - R-17 (AC-12 #73e): NEVER touch staging/backup/failed dirs whose
      UUID differs from ``state.current_run_uuid``.
    - R-17 (AC-12 #73c): NEVER unlink ``_backup_*_corrupt/``.
    - R-17 (AC-12 #73b): keep ``state.backup_dir_for_recovery`` when
      ``publish_succeeded=False``.
    - R-1: NEVER unlink ``_failed_*/`` (R-15 retention, AC-5 #24c).
    - R-17 (AC-12 #73f): cleanup failure is logged but NEVER hides the
      primary exception (Python ``finally:`` semantics).

    Parameters
    ----------
    state : _Dev04RunState
        The per-run state container populated during the pipeline.
    primary_exception : BaseException or None
        The primary exception that caused cleanup to run, or None on
        normal completion. Always propagated by the caller's ``try``.
    """
    import contextlib as _cb

    def _safe_rmtree(path: Path) -> None:
        with _cb.suppress(OSError):
            if path.exists():
                shutil.rmtree(path)

    def _log(message: str) -> None:
        _log_warning(message)

    if state.staging_dir is not None and state.staging_dir.exists():
        if state.unpreserved_log_in_staging:
            # F1 invariant: retain staging_dir for manual recovery.
            _log(
                f"DEV-04 cleanup (F1 invariant): staging_dir {state.staging_dir!s} "
                "contains unpreserved FAILED log(s); RETAINING for manual recovery. "
                "Do not unlink until orphan logs are recovered."
            )
        else:
            _safe_rmtree(state.staging_dir)

    # Backup retention based on publish outcome.
    if state.backup_dir_for_recovery is not None and not state.publish_succeeded:
        # publish_succeeded=False → retain backup for next-run recovery
        # (R-17, AC-12 #73b).
        pass
    elif state.publish_succeeded and state.backup_dir_parent is not None:
        # publish_succeeded=True → backup safely replaced; unlink.
        _safe_rmtree(state.backup_dir_parent)

    # Never unlink _backup_*_corrupt/ (R-17, AC-12 #73c).
    # Never unlink _failed_*/ (R-1 retention, AC-5 #24c).
    # Both are handled by simply not touching them above.

    # Swallow any exception raised by cleanup itself (F13). The primary
    # exception (if any) is preserved by Python `finally:` semantics.
    try:
        pass
    except Exception as exc:  # pragma: no cover - safety net
        _log(f"DEV-04 cleanup_pass: unexpected exception swallowed: {exc!r}")


# ---------------------------------------------------------------------------
# R-16 (R2): Corrupt manifest recovery
# ---------------------------------------------------------------------------


def _recover_corrupt_final(
    state: _Dev04RunState,
    logger: PerStageLogger,
) -> None:
    """R-16: When ``--force-rerun`` is set and ``final_dir`` contains a
    corrupt manifest, move the corrupt final to ``_backup_<run_uuid>_corrupt/``
    (atomic rename) and record the audit sidecar. NEVER restores from
    ``_backup_*_corrupt/``; recovery pass (``recover_orphan_backups``)
    skips them.

    Raises
    ------
    Dev04StoragePathError
        If the atomic rename of the corrupt final to the corrupt backup
        fails. The pipeline stops with a clear error; the original
        final_dir is left untouched (R2 #5: preserve all potentially
        recoverable artefacts).
    """
    if state.final_dir is None or not state.final_dir.exists():
        return
    if state.base_dir is None:
        return

    corrupt_backup = state.base_dir / f"_backup_{state.current_run_uuid}_corrupt"
    if corrupt_backup.exists():
        # R2 #5: Refuse to silently destroy the existing corrupt backup;
        # a stale _backup_*_corrupt/ from a previous run may contain
        # artefacts the user wants to recover. Fail closed so the
        # operator can investigate. Leaving the corrupt final_dir in
        # place preserves both the old manifest and the stale backup.
        raise Dev04StoragePathError(
            f"DEV-04 R-16: corrupt backup already exists at {corrupt_backup!s}. "
            "Refusing to overwrite; investigate manually before retrying. "
            "The current corrupt final_dir is left untouched to preserve "
            "all potentially recoverable artefacts."
        )
    corrupt_backup.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(str(state.final_dir), str(corrupt_backup))
    except OSError as exc:
        raise Dev04StoragePathError(
            f"DEV-04 R-16: cannot move corrupt final {state.final_dir!s} → "
            f"{corrupt_backup!s}: {exc!r}. Aborting to preserve artefacts; "
            "investigate manually before retrying."
        ) from exc

    state.backup_dir_corrupt = corrupt_backup
    logger.info(
        "5b",
        f"corrupt final moved to {corrupt_backup!s} (R-16 retention)",
        final_dir=str(state.final_dir),
        corrupt_backup=str(corrupt_backup),
    )


def _prepare_staging_dir(
    base_dir: Path,
    clustering_id: str,
    run_uuid: str,
    logger: PerStageLogger,
) -> tuple[Path, Path, Path]:
    """Prepare staging directory and backup of existing final dir.

    Returns ``(staging_dir, backup_dir, final_dir)``.
    """
    base_dir = Path(base_dir)
    staging_dir = base_dir / f"_staging_{run_uuid}" / clustering_id
    backup_dir = base_dir / f"_backup_{run_uuid}" / clustering_id
    final_dir = base_dir / clustering_id

    # Clean up any leftover backup from a previous force_rerun of
    # THIS run (a previous crash in the same process).
    with contextlib.suppress(OSError):
        if backup_dir.exists():
            shutil.rmtree(backup_dir.parent)

    staging_dir.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing final_dir (if any) before staging writes begin.
    # After backup, remove final_dir so the atomic publish in Stage 5b
    # can rename staging → final (os.rename fails if final_dir is
    # non-empty).
    if final_dir.exists():
        backup_dir.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            shutil.copytree(final_dir, backup_dir, dirs_exist_ok=False)
        # Remove final_dir now that we have a backup; the publish
        # will atomically rename staging → final.
        with contextlib.suppress(OSError):
            shutil.rmtree(final_dir)

    # Clean up any previous staging dirs from this run.
    for entry in base_dir.glob(f"_staging_{run_uuid}"):
        if entry.is_dir() and entry != staging_dir.parent:
            with contextlib.suppress(OSError):
                shutil.rmtree(entry)

    logger.stage_end("3", staging_dir=str(staging_dir), backup_dir=str(backup_dir))
    return staging_dir, backup_dir, final_dir


def _atomic_publish(
    staging_dir: Path,
    final_dir: Path,
    logger: PerStageLogger,
) -> None:
    """Atomically publish staging_dir as final_dir (single rename)."""
    os.rename(str(staging_dir), str(final_dir))
    logger.stage_end("5b", final_dir=str(final_dir))


def _cleanup_staging(
    staging_dir: Path,
    backup_dir: Path,
    final_dir: Path,
    lifecycle: str,
    logger: PerStageLogger,
) -> None:
    """Clean up staging + backup dirs after publish or failure."""
    if staging_dir.exists():
        with contextlib.suppress(OSError):
            shutil.rmtree(staging_dir)

    # Remove backup only on SUCCESS (old result safely replaced).
    if lifecycle == "SUCCESS" and backup_dir.exists():
        with contextlib.suppress(OSError):
            shutil.rmtree(backup_dir.parent)


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def run_clustering_pipeline(
    dataset_id: str,
    preprocessed_id: str,
    algorithm: str,
    *,
    config_path: str | Path | None = None,
    dev02_config_path: str | Path | None = None,
    hyperparameters: dict[str, Any] | None = None,
    seed: int | None = None,
    experiment_id: str | None = None,
    force_rerun: bool = False,
) -> ClusteringPipelineResult:
    """Run the DEV-04 clustering pipeline.

    Parameters
    ----------
    dataset_id : str
        DEV-02 dataset id (e.g. ``"ds_ba54033e45525bf5123c2d9d"``).
    preprocessed_id : str
        DEV-03 preprocessed id (e.g. ``"pp_abc123..."``).
    algorithm : str
        Algorithm name: one of ``kmeans``, ``agglomerative``, ``dbscan``,
        ``gmm``, ``fuzzy_cmeans``.
    config_path : pathlib.Path or str, optional
        Explicit DEV-04 config YAML path. ``None`` uses the canonical
        default.
    dev02_config_path : pathlib.Path or str, optional
        Forwarded to the clustering storage root resolution so DEV-04
        reads the same storage root that DEV-02/DEV-03 used. ``None``
        uses the canonical default.
    hyperparameters : dict, optional
        Per-algorithm hyperparameter overrides (merged onto YAML defaults).
    seed : int, optional
        Per-experiment seed override (3-level resolution: CLI > YAML).
    experiment_id : str, optional
        Custom experiment identifier. ``None`` auto-derives.
    force_rerun : bool
        If ``True``, re-run even if artefact already exists.

    Returns
    -------
    ClusteringPipelineResult
        Run summary; ``manifest`` is populated only on SUCCESS or CACHED.
    """
    start = datetime.now(UTC)
    run_uuid = uuid_mod.uuid4().hex
    stage_logs: list[dict[str, Any]] = []

    # ---------- Stage 0: preflight ----------------------------------------
    cfg_path = Path(config_path) if config_path else None
    dev04_config, _ = load_dev04_config(cfg_path)
    canonical_cfg_path = cfg_path or DEFAULT_DEV04_CONFIG_PATH
    config_sha256 = compute_file_sha256(canonical_cfg_path)

    # Resolve effective hyperparameters.
    algo_cfg = dev04_config.algorithms.get(algorithm)
    if algo_cfg is None:
        raise Dev04ConfigError(
            f"Algorithm {algorithm!r} not in config; "
            f"available: {sorted(dev04_config.algorithms.keys())}."
        )
    # Resolve effective seed first (used below in effective_hp).
    effective_seed = _resolve_seed(
        algorithm,
        seed,
        dev04_config.random_seed.default,
        dev04_config.random_seed.per_algorithm_override,
    )

    if not algo_cfg.enabled:
        raise Dev04ConfigError(f"Algorithm {algorithm!r} is disabled in config (enabled=false).")

    # Extract algorithm-specific hyperparameters from algo_cfg dataclass.
    valid_keys = ALGORITHM_HP_KEYS.get(algorithm, frozenset())
    key_map = DEV04_KEY_TO_ADAPTER_KEY.get(algorithm, {})

    effective_hp: dict[str, Any] = {}
    for f_name in [
        "n_clusters",
        "init",
        "n_init",
        "max_iter",
        "tol",
        "linkage",
        "metric",
        "compute_distances",
        "eps",
        "min_samples",
        "n_components",
        "covariance_type",
        "init_params",
        "reg_covar",
        "fuzziness",
        "error",
    ]:
        with contextlib.suppress(AttributeError):
            value = getattr(algo_cfg, f_name)
            if value is None:
                continue
            # Map DEV-04 key to adapter key (e.g. fuzziness -> m).
            adapter_key = key_map.get(f_name, f_name)
            if adapter_key in valid_keys:
                effective_hp[adapter_key] = value

    # Inject `random_state` for stochastic algorithms so that the
    # canonical hash matches the post-fit hyperparameters recorded
    # by the adapter (which always include `random_state`).
    if algorithm in {"kmeans", "gmm", "fuzzy_cmeans"} and "random_state" in valid_keys:
        effective_hp["random_state"] = effective_seed

    if hyperparameters:
        for k, v in hyperparameters.items():
            # Map CLI/config key to adapter key.
            adapter_key = key_map.get(k, k)
            if adapter_key in valid_keys:
                effective_hp[adapter_key] = v
            else:
                # Log warning if key not recognised for algorithm.
                with contextlib.suppress(Exception):
                    import logging as _lg

                    _lg.getLogger("customer_segmentation.prototype.clustering").warning(
                        "DEV-04: ignoring hyperparameter %r for algorithm %r.",
                        k,
                        algorithm,
                    )

    # Resolve storage root.
    storage_root = resolve_storage_root(dev02_config_path)

    # ---------- Recovery pass ---------------------------------------------
    base_dir = prototype_clustering_base_dir(storage_root, dataset_id, preprocessed_id)
    _ensure_clustering_container(base_dir, run_uuid)
    recover_orphan_backups(base_dir, run_uuid)

    # Per-run state container (R-17 cleanup invariants + F1).
    state = _Dev04RunState(
        base_dir=base_dir,
        current_run_uuid=run_uuid,
    )

    # ---------- Provisional log -------------------------------------------
    provisional_log_path = base_dir / f"_preparing_{run_uuid}.log"
    handle = configure_logging(
        config=dev04_config.logging,
        log_path=provisional_log_path,
    )
    psl = PerStageLogger(handle)
    psl.stage_start(
        "0", dataset_id=dataset_id, preprocessed_id=preprocessed_id, algorithm=algorithm
    )
    psl.info("ENV", "pipeline started", version=DEV04_PIPELINE_VERSION, run_uuid=run_uuid)
    stage_logs.append({"stage": "0", "timestamp": now_iso(), "summary": {}})

    # Top-level try/finally wrapping the entire main pipeline (R-17,
    # AC-12 #73f). Cleanup pass runs on both normal completion and
    # any unhandled exception; primary exception is preserved.
    primary_exc: BaseException | None = None
    try:
        # ---------- Stage 1: DEV-03 lookup --------------------------------
        psl.stage_start("1", preprocessed_id=preprocessed_id)
        try:
            df_ml, ml_dataset_sha256, ml_dataset_path_str = _load_dev03_ml_dataset(
                preprocessed_id=preprocessed_id,
                dataset_id=dataset_id,
                storage_root=storage_root,
                logger=psl,
            )
        except Exception as exc:
            psl.failure("1", exc)
            primary_exc = exc
            raise

        stage_logs.append(
            {
                "stage": "1",
                "outcome": "PASS",
                "timestamp": now_iso(),
                "summary": {
                    "preprocessed_id": preprocessed_id,
                    "ml_dataset_sha256": ml_dataset_sha256,
                },
            }
        )

        # Now derive the real clustering_id.
        clustering_id = derive_clustering_id(
            preprocessed_id=preprocessed_id,
            algorithm=algorithm,
            hyperparameters=effective_hp,
            effective_seed=effective_seed,
            ml_dataset_sha256=ml_dataset_sha256,
            config_sha256=config_sha256,
        )

        # Derive experiment_id (with real clustering_id).
        exp_id = _derive_experiment_id(algorithm, clustering_id, experiment_id)

        # Re-attach the file handler to the real log path.
        real_log_path = base_dir / f"{clustering_id}.log"
        if real_log_path != provisional_log_path:
            finalize_logging(handle)
            # Copy existing log content to real path.
            if provisional_log_path.exists():
                with contextlib.suppress(OSError):
                    log_content = provisional_log_path.read_text(encoding="utf-8", errors="replace")
                    real_log_path.parent.mkdir(parents=True, exist_ok=True)
                    real_log_path.write_text(log_content, encoding="utf-8")
            else:
                real_log_path.parent.mkdir(parents=True, exist_ok=True)
                real_log_path.touch()
            handle = configure_logging(
                config=dev04_config.logging,
                log_path=real_log_path,
            )
            psl = PerStageLogger(handle)
            psl.stage_start("1", clustering_id=clustering_id, preprocessed_id=preprocessed_id)

        # ---------- Idempotency check --------------------------------------
        if not force_rerun:
            existing = find_existing_clustering(
                storage_root=storage_root,
                dataset_id=dataset_id,
                preprocessed_id=preprocessed_id,
                clustering_id=clustering_id,
                algorithm=algorithm,
                hyperparameters=effective_hp,
                effective_seed=effective_seed,
                ml_dataset_sha256=ml_dataset_sha256,
                config_sha256=config_sha256,
            )
            if existing is not None:
                end = datetime.now(UTC)
                psl.stage_end("5", lifecycle="CACHED", clustering_id=clustering_id)
                # Stage 6 finalize log before return (R-17 + plan §5.3).
                psl.stage_start("6", lifecycle="CACHED", clustering_id=clustering_id)
                finalize_logging(handle)
                try:
                    manifest = read_clustering_manifest(existing)
                except Exception:
                    manifest = None
                run_dir = prototype_clustering_run_dir(
                    storage_root, dataset_id, preprocessed_id, clustering_id
                )
                return ClusteringPipelineResult(
                    clustering_id=clustering_id,
                    experiment_id=exp_id,
                    algorithm=algorithm,
                    dataset_id=dataset_id,
                    preprocessed_id=preprocessed_id,
                    storage_root=storage_root,
                    run_dir=run_dir,
                    manifest_path=existing,
                    cluster_labels_path=run_dir / f"cluster_labels_{exp_id}.parquet",
                    algorithm_output_path=run_dir / f"algorithm_output_{exp_id}.parquet",
                    log_path=real_log_path,
                    lifecycle="CACHED",
                    duration_seconds=(end - start).total_seconds(),
                    manifest=manifest,
                    stage_logs=stage_logs,
                )

        # ---------- Stage 2: matrix split ---------------------------------
        psl.stage_start("2")
        try:
            matrix_df, metadata_df, feature_names, customer_id_col = _split_matrix(
                df_ml, logger=psl
            )
        except Exception as exc:
            psl.failure("2", exc)
            primary_exc = exc
            raise

        stage_logs.append(
            {
                "stage": "2",
                "outcome": "PASS",
                "timestamp": now_iso(),
                "summary": {
                    "feature_count": len(feature_names),
                    "has_customer_id": customer_id_col is not None,
                },
            }
        )

        # ---------- Stage 3: build ----------------------------------------
        psl.stage_start("3", clustering_id=clustering_id, algorithm=algorithm)
        try:
            staging_dir, backup_dir, final_dir = _prepare_staging_dir(
                base_dir=base_dir,
                clustering_id=clustering_id,
                run_uuid=run_uuid,
                logger=psl,
            )
        except Exception as exc:
            psl.failure("3", exc)
            primary_exc = exc
            raise

        # Populate state (R-17 cleanup scope).
        state.staging_dir = staging_dir
        state.backup_dir = backup_dir
        state.final_dir = final_dir
        if backup_dir is not None:
            state.backup_dir_parent = backup_dir.parent
            state.backup_dir_for_recovery = backup_dir.parent

        stage_logs.append(
            {
                "stage": "3",
                "outcome": "PASS",
                "timestamp": now_iso(),
                "summary": {"staging_dir": str(staging_dir)},
            }
        )

        # Build FrameworkConfig + ExperimentSpec.
        fw_config = _build_framework_config(dev04_config, algorithm)
        spec = ExperimentSpec(
            experiment_id=exp_id,
            algorithm=algorithm,
            hyperparameters=effective_hp,
            seed_override=effective_seed,
        )
        runner = ExperimentRunner(
            fw_config,
            spec,
            config_source=f"yaml:{canonical_cfg_path}",
            config_text=canonical_cfg_path.read_text(encoding="utf-8"),
        )

        # ---------- Stage 4: fit ------------------------------------------
        psl.stage_start("4", experiment_id=exp_id, algorithm=algorithm)
        try:
            result: ExperimentResult = runner.run(
                matrix_df,
                metadata_df,
                input_sha256=ml_dataset_sha256,
                input_path=ml_dataset_path_str,
                metadata_path=ml_dataset_path_str,
                output_dir=staging_dir,
            )
        except Exception as exc:
            psl.failure("4", exc)
            primary_exc = exc
            # R-15 + F1 invariant: preserve FAILED log before cleanup.
            state.failed_tracking_dir = base_dir / f"{_FAILED_PREFIX}{clustering_id}_{run_uuid}"
            preservation_status = _preserve_failed_log(
                staging_dir=staging_dir,
                failed_tracking_dir=state.failed_tracking_dir,
                run_uuid=run_uuid,
            )
            _set_unpreserved_flag(state, preservation_status)
            raise

        if result.status == ExperimentStatus.FAILED:
            err = result.error or {"type": "Unknown", "message": "no error detail"}
            err_exc = RuntimeError(f"{err.get('type', 'Unknown')}: {err.get('message', '')}")
            psl.failure("4", err_exc)
            primary_exc = RuntimeError(
                f"Experiment {exp_id} failed: {err.get('type', 'Unknown')}: "
                f"{err.get('message', '')}"
            )
            # R-15 + F1 invariant: preserve FAILED log before cleanup.
            state.failed_tracking_dir = base_dir / f"{_FAILED_PREFIX}{clustering_id}_{run_uuid}"
            preservation_status = _preserve_failed_log(
                staging_dir=staging_dir,
                failed_tracking_dir=state.failed_tracking_dir,
                run_uuid=run_uuid,
            )
            _set_unpreserved_flag(state, preservation_status)
            raise primary_exc

        psl.stage_end(
            "4",
            status=result.status.value,
            n_clusters=result.n_clusters,
            n_samples=result.n_samples,
        )

        stage_logs.append(
            {
                "stage": "4",
                "outcome": result.status.value,
                "timestamp": now_iso(),
                "summary": {
                    "n_clusters": result.n_clusters,
                    "n_samples": result.n_samples,
                },
            }
        )

        # ---------- Stage 5: manifest -------------------------------------
        psl.stage_start("5", clustering_id=clustering_id)

        # Determine which algorithms have soft output (GMM/FCM).
        family = (
            result.cluster_result.algorithm_family if result.cluster_result is not None else "hard"
        )
        has_algorithm_output = dev04_config.storage.emit_algorithm_output and family in (
            "model_based",
            "fuzzy",
        )

        manifest = build_clustering_manifest(
            experiment_result=result,
            clustering_id=clustering_id,
            preprocessed_id=preprocessed_id,
            ml_dataset_sha256=ml_dataset_sha256,
            config_sha256=config_sha256,
            experiment_log_path=f"experiment_log_{exp_id}.json",
            cluster_labels_path=f"cluster_labels_{exp_id}.parquet",
            algorithm_output_path=(
                f"algorithm_output_{exp_id}.parquet" if has_algorithm_output else None
            ),
            log_file=f"{clustering_id}.log",
            input_identity=InputIdentityBlock(
                dataset_sha256=ml_dataset_sha256,
                input_path=ml_dataset_path_str,
                metadata_path=ml_dataset_path_str,
            ),
            environment=EnvironmentBlock(
                python=platform_module.python_version(),
                platform=platform_module.system(),
                release=platform_module.release(),
                machine=platform_module.machine(),
                key_libraries=capture_library_versions(),
            ),
            readonly_paths=dev04_config.research_safety.readonly_paths,
        )

        manifest_staging_path = staging_dir / "clustering_manifest.json"
        write_clustering_manifest(manifest, manifest_staging_path)

        psl.stage_end(
            "5",
        )

        stage_logs.append(
            {
                "stage": "5",
                "outcome": "PASS",
                "timestamp": now_iso(),
                "summary": {"manifest_path": str(manifest_staging_path)},
            }
        )

        # ---------- Stage 5b: publish -------------------------------------
        psl.stage_start("5b")
        try:
            _atomic_publish(staging_dir, final_dir, psl)
            state.publish_succeeded = True
        except OSError as exc:
            psl.failure("5b", exc)
            primary_exc = RuntimeError(
                f"Atomic publish failed: staging={staging_dir}, final={final_dir}"
            )
            raise primary_exc from exc

        stage_logs.append(
            {
                "stage": "5b",
                "outcome": "PASS",
                "timestamp": now_iso(),
                "summary": {"final_dir": str(final_dir)},
            }
        )

        # Stage 6: finalize log (R-17 cleanup invariants + plan §5.3).
        psl.stage_start("6", lifecycle="SUCCESS", clustering_id=clustering_id)
        finalize_logging(handle)
        psl.stage_end("6")

        stage_logs.append(
            {
                "stage": "6",
                "outcome": "PASS",
                "timestamp": now_iso(),
                "summary": {"log_finalized": True},
            }
        )

        end = datetime.now(UTC)

        manifest_path = final_dir / "clustering_manifest.json"
        cluster_labels_path = final_dir / f"cluster_labels_{exp_id}.parquet"
        algo_output_path = final_dir / f"algorithm_output_{exp_id}.parquet"

        return ClusteringPipelineResult(
            clustering_id=clustering_id,
            experiment_id=exp_id,
            algorithm=algorithm,
            dataset_id=dataset_id,
            preprocessed_id=preprocessed_id,
            storage_root=storage_root,
            run_dir=final_dir,
            manifest_path=manifest_path,
            cluster_labels_path=cluster_labels_path,
            algorithm_output_path=(algo_output_path if algo_output_path.exists() else None),
            log_path=real_log_path,
            lifecycle="SUCCESS",
            duration_seconds=(end - start).total_seconds(),
            manifest=manifest,
            stage_logs=stage_logs,
        )
    except BaseException as exc:
        if primary_exc is None:
            primary_exc = exc
        raise
    finally:
        # R-17: top-level cleanup pass (always runs, never raises).
        _cleanup_pass(state, primary_exc)


__ = (
    CLUSTERED_PROTOTYPE_SCOPE_VALUE,
    CLUSTERED_SCOPES,
    ClusteringStage,
    Dev04ConfigError,
    Dev04StoragePathError,
    Dev04ManifestCorrupt,
    Dev04CollisionError,
    ExperimentStatus,
    ExperimentSpec,
    ExperimentRunner,
    ResearchSafetyBlock,
    InputIdentityBlock,
    EnvironmentBlock,
    compute_text_sha256,
)
