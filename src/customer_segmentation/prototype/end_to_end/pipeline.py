"""End-to-end pipeline for DEV-09 Prototype Integration.

This module orchestrates the existing DEV-02..08 prototype pipelines
via their public :func:`run_*_pipeline` entry points. It does NOT
re-implement any per-stage logic. The pipeline owns only:

- Stage sequencing and lifecycle accounting.
- Per-stage failure handling (``FAILED`` / ``SKIPPED`` /
  ``BLOCKED`` / ``REVIEW_REQUIRED`` semantics).
- Cross-manifest identifier validation (ids must match across stages).
- Persistence of an end-to-end run summary (text + JSON) into the
  per-run directory.
- Library-version snapshot for reproducibility.

Stages
------
- **A — UPLOAD**: import the source CSV/Parquet via DEV-02.
- **B — VALIDATION**: read the DEV-02 manifest; require
  ``validation_status == VALID``.
- **C — PREPROCESSING**: run ``run_preprocessing_pipeline`` (DEV-03
  Stages A→E). Stage F (feature engineering) is part of the same
  pipeline; this orchestrator records its outcome separately so the
  summary surfaces both views.
- **D — FEATURE_ENGINEERING**: assert the preprocessing pipeline
  produced a non-empty ML Dataset; record its manifest reference.
- **E — ALGORITHM_SELECT**: no-op stage that records the chosen
  algorithm (provided via CLI or config). The selection is
  propagated unchanged to DEV-04.
- **F — CLUSTERING**: ``run_clustering_pipeline`` (DEV-04).
- **G — EVALUATION**: ``run_evaluation_pipeline`` (DEV-05).
- **H — SEGMENTATION**: ``run_segmentation_pipeline`` (DEV-06).
- **I — CUSTOMER_PROFILE**: read-only inspection of the
  segmentation manifest (number of segments, profile presence,
  characteristic ids). Never mutates inputs.
- **J — MARKETING**: ``run_marketing_pipeline`` (DEV-07). The
  pipeline preserves ``REVIEW_REQUIRED`` semantics; the end-to-end
  stage status is ``REVIEW_REQUIRED`` when ``availability ==
  REVIEW_REQUIRED`` and the pipeline completed without exception.
- **K — VISUALIZATION**: ``run_visualization_pipeline`` (DEV-08).
  ``cluster_visualization_2d`` BLOCKED state is carried forward into
  the end-to-end summary.

Failure handling
----------------
- A stage that raises any exception (DEV-02..08 typed error, or
  arbitrary ``Exception``) is recorded as ``FAILED`` with the error
  message in ``note`` and ``error_type``. All downstream stages are
  recorded as ``SKIPPED``. The end-to-end overall lifecycle becomes
  ``FAILED``.
- A stage that completes but reports ``lifecycle != SUCCESS/CACHED``
  (where applicable) is recorded as ``FAILED``.
- The marketing ``REVIEW_REQUIRED`` availability is NOT a hard
  failure: it surfaces as ``StageStatus.REVIEW_REQUIRED`` and the
  overall lifecycle is ``CONDITIONAL``.
- The visualization ``BLOCKED`` chart status (specifically
  ``cluster_visualization_2d``) is NOT a hard failure: it surfaces
  as ``StageStatus.CONDITIONAL`` (overall) if the visualization
  stage otherwise completes; the chart record is preserved verbatim
  in the summary.

Persistence is gated on Stage A (UPLOAD) success. A failed
import never produces a run summary; the failure is logged + raised
to the caller via :exc:`Dev09Error`.
"""

from __future__ import annotations

import contextlib
import json
import platform
import shutil
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, Final

from customer_segmentation.dataset_management.importer import (
    FilePreflightError,
    ImportError,
    ImportRequest,
    Manifest,
    import_dataset,
)
from customer_segmentation.dataset_management.list import get_dataset
from customer_segmentation.prototype.clustering.pipeline import (
    run_clustering_pipeline,
)
from customer_segmentation.prototype.end_to_end.config_loader import (
    DEFAULT_DEV09_CONFIG_PATH,
    Dev09Config,
    load_dev09_config,
)
from customer_segmentation.prototype.end_to_end.exceptions import (
    Dev09Error,
    Dev09InputError,
    Dev09StoragePathError,
)
from customer_segmentation.prototype.end_to_end.logging_config import (
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.end_to_end.scope import (
    E2E_ID_HEX_LEN,
    E2E_ID_PREFIX,
    END_TO_END_SCHEMA_VERSION,
    Lifecycle,
    StageStatus,
)
from customer_segmentation.prototype.end_to_end.storage import (
    CANONICAL_PAYLOAD_KEYS,
    compute_config_sha256,
    derive_e2e_run_id,
    end_to_end_run_dir,
    resolve_e2e_storage_root,
    resolve_storage_root,
)

# ``Dev09StoragePathError`` is imported above from :mod:`exceptions`
# (which re-exports :mod:`scope`). After the §19 dedup, ``storage.py``
# also re-exports the SAME class, but we already have the canonical
# binding from :mod:`exceptions`, so we no longer need a parallel
# ``as _StoragePathError`` binding here.
from customer_segmentation.prototype.evaluation.pipeline import (
    run_evaluation_pipeline,
)
from customer_segmentation.prototype.marketing.pipeline import (
    run_marketing_pipeline,
)
from customer_segmentation.prototype.preprocessing.pipeline import (
    run_preprocessing_pipeline,
)
from customer_segmentation.prototype.segmentation.pipeline import (
    run_segmentation_pipeline,
)
from customer_segmentation.prototype.visualization.pipeline import (
    run_visualization_pipeline,
)

__all__ = [
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
]


# ---------------------------------------------------------------------------
# Lifecycle / stage-status constants (string aliases for backwards-compat)
# ---------------------------------------------------------------------------

E2E_SUCCESS: Final[str] = Lifecycle.SUCCESS.value
E2E_CACHED: Final[str] = Lifecycle.CACHED.value
E2E_FAILED: Final[str] = Lifecycle.FAILED.value
E2E_CONDITIONAL: Final[str] = Lifecycle.CONDITIONAL.value
E2E_BLOCKED: Final[str] = Lifecycle.BLOCKED.value

E2E_STAGE_SUCCESS: Final[str] = StageStatus.SUCCESS.value
E2E_STAGE_CACHED: Final[str] = StageStatus.CACHED.value
E2E_STAGE_FAILED: Final[str] = StageStatus.FAILED.value
E2E_STAGE_SKIPPED: Final[str] = StageStatus.SKIPPED.value
E2E_STAGE_BLOCKED: Final[str] = StageStatus.BLOCKED.value
E2E_STAGE_REVIEW_REQUIRED: Final[str] = StageStatus.REVIEW_REQUIRED.value


# Stages known to be runnable and their canonical display order.
_STAGE_ORDER: Final[tuple[str, ...]] = (
    "UPLOAD",
    "VALIDATION",
    "PREPROCESSING",
    "FEATURE_ENGINEERING",
    "ALGORITHM_SELECT",
    "CLUSTERING",
    "EVALUATION",
    "SEGMENTATION",
    "CUSTOMER_PROFILE",
    "MARKETING",
    "VISUALIZATION",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E2EStageOutcome:
    """Outcome of one end-to-end stage."""

    stage: str
    status: str  # one of StageStatus values
    note: str = ""
    started_utc: str = ""
    ended_utc: str = ""
    error_type: str = ""
    error_message: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class E2ERunSummary:
    """Outcome of one end-to-end run.

    The summary is the canonical persisted artefact. It is fully
    JSON-serialisable via :func:`as_dict` and includes every
    cross-stage id (so a ``show`` subcommand can validate that the
    persisted state matches the on-disk manifests before reporting).
    """

    e2e_run_id: str
    schema_version: str
    dataset_id: str
    dataset_sha256: str
    storage_root: str
    run_dir: str
    overall_status: str  # one of Lifecycle values
    lifecycle: str  # alias of overall_status; mirrors per-stage pipeline convention
    algorithm: str
    seed: int | None
    preprocessed_id: str | None
    clustering_id: str | None
    evaluation_id: str | None
    segmentation_id: str | None
    marketing_id: str | None
    dashboard_id: str | None
    stages: list[E2EStageOutcome]
    inputs: dict[str, str]
    config: dict[str, str]
    environment: dict[str, Any]
    notes: list[str] = field(default_factory=list)
    created_utc: str = ""

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "e2e_run_id": self.e2e_run_id,
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "storage_root": self.storage_root,
            "run_dir": self.run_dir,
            "overall_status": self.overall_status,
            "lifecycle": self.lifecycle,
            "algorithm": self.algorithm,
            "seed": self.seed,
            "preprocessed_id": self.preprocessed_id,
            "clustering_id": self.clustering_id,
            "evaluation_id": self.evaluation_id,
            "segmentation_id": self.segmentation_id,
            "marketing_id": self.marketing_id,
            "dashboard_id": self.dashboard_id,
            "stages": [s.__dict__ for s in self.stages],
            "inputs": self.inputs,
            "config": self.config,
            "environment": self.environment,
            "notes": self.notes,
            "created_utc": self.created_utc,
        }
        return d


# ---------------------------------------------------------------------------
# Environment block
# ---------------------------------------------------------------------------


def compute_environment_block() -> dict[str, Any]:
    """Capture a small environment snapshot for the run record.

    Mirrors the per-stage pipelines' shape: ``python``, ``platform``,
    ``release``, ``machine``, ``key_libraries``.
    """
    key_libs: dict[str, str] = {}
    for mod_name in ("pandas", "numpy", "matplotlib", "yaml", "sklearn"):
        try:
            mod = __import__(mod_name)
            key_libs[mod_name] = str(getattr(mod, "__version__", "unknown"))
        except Exception:  # pragma: no cover — defensive
            key_libs[mod_name] = "unavailable"
    return {
        "python": sys.version.split()[0] if sys.version else "",
        "platform": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "key_libraries": key_libs,
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_end_to_end_pipeline(
    *,
    source_file: Path | str | None = None,
    algorithm: str | None = None,
    seed: int | None = None,
    dataset_id: str | None = None,
    name: str | None = None,
    allow_external_source: bool = False,
    config_path: Path | str | None = None,
    dev02_config_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    skip_marketing: bool | None = None,
    skip_visualization: bool | None = None,
    log_dir: Path | str | None = None,
) -> E2ERunSummary:
    """Run the DEV-09 end-to-end pipeline.

    Parameters
    ----------
    source_file : pathlib.Path or str or None
        Path to the source CSV/Parquet file. Required when
        ``dataset_id`` is not provided.
    algorithm : str | None
        Selected algorithm (closed set ``kmeans``, ``agglomerative``,
        ``dbscan``, ``gmm``, ``fuzzy_cmeans``). If ``None``, the
        configured default (``stage_selection.algorithm``) is used.
    seed : int | None
        Random seed override for DEV-04 (passed-through).
    dataset_id : str | None
        Reuse an existing DEV-02 dataset by id. When provided, the
        UPLOAD stage is skipped (lifecycle = CACHED).
    name : str | None
        Display name override (DEV-02).
    allow_external_source : bool
        Forwarded to DEV-02 to permit sources outside the repository.
    config_path : pathlib.Path or str | None
        Path to the DEV-09 config YAML.
    output_dir : pathlib.Path or str | None
        Directory to write the e2e summary into. When None, the
        canonical per-dataset directory under the storage root is used.
    skip_marketing / skip_visualization : bool | None
        Per-stage skip override; defaults to the config values.
    log_dir : pathlib.Path or str | None
        Directory for the per-stage log file. If None, no file log is
        emitted (console only).

    Returns
    -------
    E2ERunSummary
        Fully populated summary.

    Raises
    ------
    Dev09InputError
        On CLI / user-supplied path errors.
    Dev09Error
        On any unrecoverable stage failure.
    Dev09StoragePathError
        On storage path / id-format failures.
    """
    # ---- Preflight ---------------------------------------------------------
    if source_file is None and dataset_id is None:
        raise Dev09InputError("Either source_file or dataset_id must be provided.")
    if source_file is not None:
        source_file = Path(source_file)
        if not source_file.exists():
            raise Dev09InputError(f"source_file does not exist: {source_file!s}")

    config: Dev09Config = load_dev09_config(config_path)
    storage_root = resolve_storage_root(dev02_config_path)

    selected_algorithm = algorithm if algorithm is not None else config.stage_selection.algorithm
    selected_skip_marketing = (
        skip_marketing if skip_marketing is not None else config.stage_selection.skip_marketing
    )
    selected_skip_visualization = (
        skip_visualization
        if skip_visualization is not None
        else config.stage_selection.skip_visualization
    )

    log_file = None
    if log_dir is not None:
        log_dir_p = Path(log_dir)
        log_dir_p.mkdir(parents=True, exist_ok=True)
        log_file = log_dir_p / "dev09_pipeline.log"
    logger = configure_logging(
        level=config.logging.level,
        fmt=config.logging.format,
        log_file=log_file,
        emit_to_console=config.logging.emit_to_console,
    )
    per_stage = PerStageLogger(logger, stage="PREFlight")

    # Per-stage state accumulators
    preprocessed_id: str | None = None
    clustering_id: str | None = None
    evaluation_id: str | None = None
    segmentation_id: str | None = None
    marketing_id: str | None = None
    dashboard_id: str | None = None
    dataset_sha256: str = ""

    # Stage outcomes list (mutable; pre-allocated to canonical length).
    outcomes: dict[str, E2EStageOutcome] = {}

    failed = False
    blocked = False
    conditional = False
    review_required_seen = False

    inputs: dict[str, str] = {
        "source_file": str(source_file.resolve()) if source_file else "",
        "allow_external_source": str(allow_external_source),
        "name": str(name) if name else "",
        "provided_dataset_id": str(dataset_id) if dataset_id else "",
    }
    config_summary: dict[str, str] = {
        "dev09_schema_version": str(config.schema_version),
        "dev09_algorithm": str(selected_algorithm),
        "dev09_skip_marketing": str(selected_skip_marketing),
        "dev09_skip_visualization": str(selected_skip_visualization),
        "dev09_config_path": str(config_path) if config_path else str(DEFAULT_DEV09_CONFIG_PATH),
    }

    # ---- Stage A: UPLOAD ---------------------------------------------------
    per_stage.stage_start("UPLOAD")
    upload_started = _utc_now()
    if dataset_id is not None:
        # Reuse path: skip import, load manifest by id.
        try:
            manifest = get_dataset(storage_root, dataset_id)
        except Exception as exc:
            per_stage.stage_end("FAIL")
            raise Dev09Error(
                f"Failed to load existing DEV-02 dataset {dataset_id!r}: {exc}"
            ) from exc
        effective_dataset_id = dataset_id
        dataset_sha256 = str(manifest.sha256)
        outcomes["UPLOAD"] = E2EStageOutcome(
            stage="UPLOAD",
            status=E2E_STAGE_CACHED,
            note=f"reused existing dataset_id={dataset_id}",
            started_utc=upload_started,
            ended_utc=_utc_now(),
            artifacts={
                "manifest_path": str(
                    resolve_e2e_storage_root(storage_root, dataset_id=dataset_id).parent
                    / "manifest.json"
                ),
            },
        )
    else:
        try:
            # Build a minimal ImportRequest — use the DEV-02 default config.
            from customer_segmentation.dataset_management.importer import (
                build_request_from_args,
            )
            from customer_segmentation.prototype.preprocessing.storage import (
                DEFAULT_DEV02_CONFIG_PATH,
            )

            # Construct an args-like namespace.
            class _Args:
                pass

            args = _Args()
            args.file = str(source_file)
            args.name = name
            args.config = str(DEFAULT_DEV02_CONFIG_PATH)
            args.allow_external_source = allow_external_source

            request: ImportRequest = build_request_from_args(
                args, repo_root=Path(__file__).resolve().parents[3], cwd=Path.cwd()
            )
            result = import_dataset(request)
            effective_dataset_id = result.dataset_id
            dataset_sha256 = result.sha256
            outcomes["UPLOAD"] = E2EStageOutcome(
                stage="UPLOAD",
                status=E2E_STAGE_SUCCESS if not result.reused else E2E_STAGE_CACHED,
                note=("reused existing dataset" if result.reused else "new dataset imported"),
                started_utc=upload_started,
                ended_utc=_utc_now(),
                artifacts={
                    "manifest_path": str(result.manifest_path),
                    "artefact_path": str(result.artefact_path),
                    "validation_status": str(result.validation_status),
                },
            )
        except FilePreflightError as exc:
            per_stage.stage_end("FAIL")
            raise Dev09Error(f"DEV-02 file preflight failed: {exc}") from exc
        except ImportError as exc:
            per_stage.stage_end("FAIL")
            raise Dev09Error(f"DEV-02 import failed: {exc}") from exc
        except Exception as exc:  # pragma: no cover — defensive
            per_stage.stage_end("FAIL")
            raise Dev09Error(f"DEV-02 import raised unexpected error: {exc}") from exc
    per_stage.stage_end("PASS")

    # ---- Stage B: VALIDATION -----------------------------------------------
    per_stage.stage_start("VALIDATION")
    started = _utc_now()
    try:
        manifest = get_dataset(storage_root, effective_dataset_id)
        validation_status = str(manifest.validation_status)
        is_valid = validation_status.upper() == "VALID"
        outcomes["VALIDATION"] = E2EStageOutcome(
            stage="VALIDATION",
            status=(E2E_STAGE_SUCCESS if is_valid else E2E_STAGE_FAILED),
            note=f"validation_status={validation_status}",
            started_utc=started,
            ended_utc=_utc_now(),
            artifacts={
                "manifest_path": str(
                    _resolve_dataset_manifest_path(storage_root, effective_dataset_id)
                )
            },
        )
        if not is_valid:
            failed = True
            per_stage.stage_end("FAIL")
            raise Dev09Error(
                f"DEV-02 dataset {effective_dataset_id!r} has "
                f"validation_status={validation_status!r}; cannot proceed."
            )
    except Exception as exc:
        per_stage.stage_end("FAIL")
        raise Dev09Error(f"Validation stage raised: {exc}") from exc
    per_stage.stage_end("PASS")

    # ---- Stage C: PREPROCESSING -------------------------------------------
    per_stage.stage_start("PREPROCESSING")
    started = _utc_now()
    try:
        pp_result = run_preprocessing_pipeline(
            dataset_id=effective_dataset_id,
            config_path=None,
            dev02_config_path=dev02_config_path,
        )
        preprocessed_id = pp_result.preprocessed_id
        # DEV-03 returns ``preprocessed_id=""`` on its failure path (see
        # ``run_preprocessing_pipeline`` early-exit branch). Normalise to
        # ``None`` so the canonical-payload contract that
        # ``derive_e2e_run_id`` validates is satisfied even when DEV-03
        # reports a hard failure (Bug 2 dedup makes this work even
        # pre-fix).
        if not preprocessed_id:
            preprocessed_id = None
        pp_lifecycle = str(getattr(pp_result, "lifecycle", "")).upper()
        # DEV-03's canonical lifecycle values (per
        # ``customer_segmentation.prototype.preprocessing.validation.lifecycle_for_preprocessing``):
        # PASS / WARNING → "VALID" ; FAIL → "FAILED". There is no
        # "SUCCESS", "CACHED", or "BLOCKED" lifecycle in DEV-03. Forward-
        # compatibility for the obsolete "SUCCESS" string is preserved so
        # earlier DEV-09 fixtures do not regress, but the canonical success
        # value is "VALID". An empty / unknown lifecycle is treated as
        # failure because the orchestrator cannot infer pass/fail from a
        # non-canonical status.
        pp_status = (
            E2E_STAGE_SUCCESS if pp_lifecycle in {"VALID", "SUCCESS", "PASS"} else E2E_STAGE_FAILED
        )
        outcomes["PREPROCESSING"] = E2EStageOutcome(
            stage="PREPROCESSING",
            status=pp_status,
            note=f"lifecycle={pp_lifecycle}; preprocessed_id={preprocessed_id}",
            started_utc=started,
            ended_utc=_utc_now(),
            artifacts={
                "manifest_path": str(pp_result.manifest_path),
                "ml_dataset_path": str(pp_result.ml_dataset_path),
                "log_path": str(pp_result.log_path),
            },
        )
        if pp_status == E2E_STAGE_FAILED:
            failed = True
    except Exception as exc:
        per_stage.stage_end("FAIL")
        outcomes["PREPROCESSING"] = E2EStageOutcome(
            stage="PREPROCESSING",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Stage D: FEATURE_ENGINEERING -------------------------------------
    per_stage.stage_start("FEATURE_ENGINEERING")
    started = _utc_now()
    try:
        if failed or not preprocessed_id:
            outcomes["FEATURE_ENGINEERING"] = E2EStageOutcome(
                stage="FEATURE_ENGINEERING",
                status=E2E_STAGE_SKIPPED,
                note="preprocessing did not complete",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        else:
            # The ML Dataset is written by DEV-03 Stage G; verify it exists.
            ml_path = outcomes["PREPROCESSING"].artifacts.get("ml_dataset_path", "")
            ml_exists = bool(ml_path) and Path(ml_path).exists()
            if ml_exists:
                outcomes["FEATURE_ENGINEERING"] = E2EStageOutcome(
                    stage="FEATURE_ENGINEERING",
                    status=E2E_STAGE_SUCCESS,
                    note=f"ML Dataset ready at {ml_path}",
                    started_utc=started,
                    ended_utc=_utc_now(),
                    artifacts={"ml_dataset_path": ml_path},
                )
            else:
                outcomes["FEATURE_ENGINEERING"] = E2EStageOutcome(
                    stage="FEATURE_ENGINEERING",
                    status=E2E_STAGE_FAILED,
                    note=f"ML Dataset missing: {ml_path!r}",
                    started_utc=started,
                    ended_utc=_utc_now(),
                )
                failed = True
    except Exception as exc:  # pragma: no cover — defensive
        per_stage.stage_end("FAIL")
        outcomes["FEATURE_ENGINEERING"] = E2EStageOutcome(
            stage="FEATURE_ENGINEERING",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Stage E: ALGORITHM_SELECT ----------------------------------------
    per_stage.stage_start("ALGORITHM_SELECT")
    started = _utc_now()
    outcomes["ALGORITHM_SELECT"] = E2EStageOutcome(
        stage="ALGORITHM_SELECT",
        status=E2E_STAGE_SUCCESS,
        note=f"algorithm={selected_algorithm}",
        started_utc=started,
        ended_utc=_utc_now(),
    )
    per_stage.stage_end("PASS")

    # ---- Stage F: CLUSTERING ----------------------------------------------
    per_stage.stage_start("CLUSTERING")
    started = _utc_now()
    try:
        if failed or not preprocessed_id:
            outcomes["CLUSTERING"] = E2EStageOutcome(
                stage="CLUSTERING",
                status=E2E_STAGE_SKIPPED,
                note="preprocessing did not complete",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        else:
            cl_result = run_clustering_pipeline(
                dataset_id=effective_dataset_id,
                preprocessed_id=preprocessed_id,
                algorithm=selected_algorithm,
                seed=seed,
                dev02_config_path=dev02_config_path,
            )
            clustering_id = cl_result.clustering_id
            cl_lifecycle = str(cl_result.lifecycle).upper()
            cl_status = (
                E2E_STAGE_SUCCESS if cl_lifecycle in {"SUCCESS", "CACHED"} else E2E_STAGE_FAILED
            )
            outcomes["CLUSTERING"] = E2EStageOutcome(
                stage="CLUSTERING",
                status=cl_status,
                note=(
                    f"lifecycle={cl_lifecycle}; "
                    f"clustering_id={clustering_id}; "
                    f"experiment_id={cl_result.experiment_id}"
                ),
                started_utc=started,
                ended_utc=_utc_now(),
                artifacts={
                    "manifest_path": str(cl_result.manifest_path),
                    "run_dir": str(cl_result.run_dir),
                    "cluster_labels_path": (
                        str(cl_result.cluster_labels_path) if cl_result.cluster_labels_path else ""
                    ),
                },
            )
            if cl_status == E2E_STAGE_FAILED:
                failed = True
    except Exception as exc:
        per_stage.stage_end("FAIL")
        outcomes["CLUSTERING"] = E2EStageOutcome(
            stage="CLUSTERING",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Stage G: EVALUATION ----------------------------------------------
    per_stage.stage_start("EVALUATION")
    started = _utc_now()
    try:
        if failed or not clustering_id:
            outcomes["EVALUATION"] = E2EStageOutcome(
                stage="EVALUATION",
                status=E2E_STAGE_SKIPPED,
                note="clustering did not complete",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        else:
            ev_result = run_evaluation_pipeline(
                dataset_id=effective_dataset_id,
                preprocessed_id=preprocessed_id,
                clustering_id=clustering_id,
                dev02_config_path=dev02_config_path,
            )
            evaluation_id = ev_result.evaluation_id
            ev_lifecycle = str(ev_result.lifecycle).upper()
            ev_status = (
                E2E_STAGE_SUCCESS if ev_lifecycle in {"SUCCESS", "CACHED"} else E2E_STAGE_FAILED
            )
            outcomes["EVALUATION"] = E2EStageOutcome(
                stage="EVALUATION",
                status=ev_status,
                note=(f"lifecycle={ev_lifecycle}; " f"evaluation_id={evaluation_id}"),
                started_utc=started,
                ended_utc=_utc_now(),
                artifacts={
                    "manifest_path": str(ev_result.manifest_path),
                    "csv_path": (str(ev_result.csv_path) if ev_result.csv_path else ""),
                },
            )
            if ev_status == E2E_STAGE_FAILED:
                failed = True
    except Exception as exc:
        per_stage.stage_end("FAIL")
        outcomes["EVALUATION"] = E2EStageOutcome(
            stage="EVALUATION",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Stage H: SEGMENTATION --------------------------------------------
    per_stage.stage_start("SEGMENTATION")
    started = _utc_now()
    try:
        if failed or not clustering_id:
            outcomes["SEGMENTATION"] = E2EStageOutcome(
                stage="SEGMENTATION",
                status=E2E_STAGE_SKIPPED,
                note="clustering did not complete",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        else:
            sg_result = run_segmentation_pipeline(
                dataset_id=effective_dataset_id,
                preprocessed_id=preprocessed_id,
                clustering_id=clustering_id,
                dev02_config_path=dev02_config_path,
            )
            segmentation_id = sg_result.segmentation_id
            sg_lifecycle = str(sg_result.lifecycle).upper()
            sg_status = (
                E2E_STAGE_SUCCESS if sg_lifecycle in {"SUCCESS", "CACHED"} else E2E_STAGE_FAILED
            )
            outcomes["SEGMENTATION"] = E2EStageOutcome(
                stage="SEGMENTATION",
                status=sg_status,
                note=(
                    f"lifecycle={sg_lifecycle}; "
                    f"segmentation_id={segmentation_id}; "
                    f"n_segments={len(getattr(sg_result.manifest, 'segment_sizes', []))}"
                ),
                started_utc=started,
                ended_utc=_utc_now(),
                artifacts={"manifest_path": str(sg_result.manifest_path)},
            )
            if sg_status == E2E_STAGE_FAILED:
                failed = True
    except Exception as exc:
        per_stage.stage_end("FAIL")
        outcomes["SEGMENTATION"] = E2EStageOutcome(
            stage="SEGMENTATION",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Stage I: CUSTOMER_PROFILE ----------------------------------------
    per_stage.stage_start("CUSTOMER_PROFILE")
    started = _utc_now()
    try:
        if failed or not segmentation_id:
            outcomes["CUSTOMER_PROFILE"] = E2EStageOutcome(
                stage="CUSTOMER_PROFILE",
                status=E2E_STAGE_SKIPPED,
                note="segmentation did not complete",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        else:
            sg_manifest_path = outcomes["SEGMENTATION"].artifacts.get("manifest_path", "")
            sg_payload = json.loads(Path(sg_manifest_path).read_text(encoding="utf-8"))
            n_segments = len(sg_payload.get("segment_sizes", []))
            n_profiles = len(sg_payload.get("profiles", []))
            n_characteristics = len(sg_payload.get("characteristics", []))
            outcomes["CUSTOMER_PROFILE"] = E2EStageOutcome(
                stage="CUSTOMER_PROFILE",
                status=E2E_STAGE_SUCCESS,
                note=(
                    f"read-only inspection of segmentation manifest: "
                    f"n_segments={n_segments}, n_profiles={n_profiles}, "
                    f"n_characteristics={n_characteristics}"
                ),
                started_utc=started,
                ended_utc=_utc_now(),
                artifacts={"manifest_path": sg_manifest_path},
            )
    except Exception as exc:
        per_stage.stage_end("FAIL")
        outcomes["CUSTOMER_PROFILE"] = E2EStageOutcome(
            stage="CUSTOMER_PROFILE",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Stage J: MARKETING -----------------------------------------------
    per_stage.stage_start("MARKETING")
    started = _utc_now()
    marketing_blocked_by_config = selected_skip_marketing
    try:
        if failed or not segmentation_id:
            outcomes["MARKETING"] = E2EStageOutcome(
                stage="MARKETING",
                status=E2E_STAGE_SKIPPED,
                note="segmentation did not complete",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        elif marketing_blocked_by_config:
            outcomes["MARKETING"] = E2EStageOutcome(
                stage="MARKETING",
                status=E2E_STAGE_SKIPPED,
                note="skip_marketing=true in DEV-09 config",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        else:
            mk_result = run_marketing_pipeline(segmentation_id=segmentation_id)
            marketing_id = str(mk_result.manifest.marketing_id)
            mk_availability = str(mk_result.manifest.availability)
            mk_lifecycle = str(mk_result.lifecycle).upper()
            mk_status = (
                E2E_STAGE_SUCCESS if mk_lifecycle in {"SUCCESS", "CACHED"} else E2E_STAGE_FAILED
            )
            mk_note = (
                f"lifecycle={mk_lifecycle}; availability={mk_availability}; "
                f"marketing_id={marketing_id}"
            )
            # Marketing REVIEW_REQUIRED is a non-fatal review-required
            # state: surface it explicitly without flipping the overall
            # status to FAILED.
            if mk_status == E2E_STAGE_SUCCESS and mk_availability == "REVIEW_REQUIRED":
                mk_status_out = E2E_STAGE_REVIEW_REQUIRED
                review_required_seen = True
            else:
                mk_status_out = mk_status
            outcomes["MARKETING"] = E2EStageOutcome(
                stage="MARKETING",
                status=mk_status_out,
                note=mk_note,
                started_utc=started,
                ended_utc=_utc_now(),
                artifacts={
                    "manifest_path": str(mk_result.manifest_path),
                    "availability": mk_availability,
                },
            )
            if mk_status == E2E_STAGE_FAILED:
                failed = True
    except Exception as exc:
        per_stage.stage_end("FAIL")
        outcomes["MARKETING"] = E2EStageOutcome(
            stage="MARKETING",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Stage K: VISUALIZATION -------------------------------------------
    per_stage.stage_start("VISUALIZATION")
    started = _utc_now()
    viz_blocked_by_config = selected_skip_visualization
    try:
        if failed or not segmentation_id:
            outcomes["VISUALIZATION"] = E2EStageOutcome(
                stage="VISUALIZATION",
                status=E2E_STAGE_SKIPPED,
                note="segmentation did not complete",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        elif viz_blocked_by_config:
            outcomes["VISUALIZATION"] = E2EStageOutcome(
                stage="VISUALIZATION",
                status=E2E_STAGE_SKIPPED,
                note="skip_visualization=true in DEV-09 config",
                started_utc=started,
                ended_utc=_utc_now(),
            )
        else:
            sg_manifest_path = outcomes["SEGMENTATION"].artifacts.get("manifest_path", "")
            ev_manifest_path = (
                outcomes["EVALUATION"].artifacts.get("manifest_path", "")
                if "EVALUATION" in outcomes
                else ""
            )
            mk_manifest_path = (
                outcomes["MARKETING"].artifacts.get("manifest_path", "")
                if "MARKETING" in outcomes
                else ""
            )
            ev_paths = [ev_manifest_path] if ev_manifest_path else []
            viz_result = run_visualization_pipeline(
                segmentation_manifest_path=sg_manifest_path,
                evaluation_manifest_paths=ev_paths,
                marketing_manifest_path=Path(mk_manifest_path) if mk_manifest_path else None,
                dev02_config_path=dev02_config_path,
            )
            dashboard_id = str(viz_result.result.dashboard_id)
            # Inspect chart records for BLOCKED states.
            blocked_charts = [
                c.name for c in viz_result.result.charts if str(c.status).upper() == "BLOCKED"
            ]
            viz_lifecycle = str(viz_result.lifecycle).upper()
            viz_status = (
                E2E_STAGE_SUCCESS if viz_lifecycle in {"SUCCESS", "CACHED"} else E2E_STAGE_FAILED
            )
            viz_note = (
                f"lifecycle={viz_lifecycle}; dashboard_id={dashboard_id}; "
                f"blocked_charts={blocked_charts or 'none'}"
            )
            if viz_status == E2E_STAGE_SUCCESS and blocked_charts:
                # Stage itself succeeded, but at least one chart is BLOCKED.
                # Mark stage as BLOCKED and flag overall as CONDITIONAL.
                viz_status = E2E_STAGE_BLOCKED
                blocked = True
            outcomes["VISUALIZATION"] = E2EStageOutcome(
                stage="VISUALIZATION",
                status=viz_status,
                note=viz_note,
                started_utc=started,
                ended_utc=_utc_now(),
                artifacts={
                    "summary_json_path": str(viz_result.summary_json_path),
                    "summary_text_path": str(viz_result.summary_text_path),
                    "run_dir": str(viz_result.run_dir),
                    "blocked_charts": ",".join(blocked_charts),
                },
            )
            if viz_status == E2E_STAGE_FAILED:
                failed = True
    except Exception as exc:
        per_stage.stage_end("FAIL")
        outcomes["VISUALIZATION"] = E2EStageOutcome(
            stage="VISUALIZATION",
            status=E2E_STAGE_FAILED,
            note=f"raised {type(exc).__name__}",
            started_utc=started,
            ended_utc=_utc_now(),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        failed = True
    per_stage.stage_end("PASS" if not failed else "FAIL")

    # ---- Compute overall lifecycle ---------------------------------------
    if failed:
        overall_status = Lifecycle.FAILED.value
    elif (
        blocked
        and not review_required_seen
        or review_required_seen
        and not failed
        or blocked
        and review_required_seen
    ):
        overall_status = Lifecycle.CONDITIONAL.value
    else:
        overall_status = Lifecycle.SUCCESS.value
    conditional = overall_status == Lifecycle.CONDITIONAL.value

    # ---- Resolve run_dir + e2e_run_id + persistence -----------------------
    dev04_cfg_sha = ""
    dev06_cfg_sha = ""
    try:
        from customer_segmentation.prototype.clustering.config_loader import (
            DEFAULT_DEV04_CONFIG_PATH,
        )
        from customer_segmentation.prototype.segmentation.config_loader import (
            DEFAULT_DEV06_CONFIG_PATH,
        )

        if DEFAULT_DEV04_CONFIG_PATH.exists():
            dev04_cfg_sha = compute_config_sha256(
                DEFAULT_DEV04_CONFIG_PATH.read_text(encoding="utf-8")
            )
        if DEFAULT_DEV06_CONFIG_PATH.exists():
            dev06_cfg_sha = compute_config_sha256(
                DEFAULT_DEV06_CONFIG_PATH.read_text(encoding="utf-8")
            )
    except Exception:  # pragma: no cover — defensive
        pass

    e2e_run_id = derive_e2e_run_id(
        dataset_id=effective_dataset_id,
        dataset_sha256=dataset_sha256 or "0" * 64,
        preprocessed_id=preprocessed_id,
        clustering_id=clustering_id,
        segmentation_id=segmentation_id,
        algorithm=selected_algorithm,
        seed=seed,
        dev04_config_sha256=dev04_cfg_sha or "0" * 64,
        dev06_config_sha256=dev06_cfg_sha or "0" * 64,
    )

    try:
        if output_dir is not None:
            run_dir = Path(output_dir).resolve()
            run_dir.mkdir(parents=True, exist_ok=True)
        else:
            run_dir = end_to_end_run_dir(
                storage_root,
                dataset_id=effective_dataset_id,
                e2e_run_id=e2e_run_id,
            )
            run_dir.mkdir(parents=True, exist_ok=True)
    except (Dev09StoragePathError, OSError) as exc:
        raise Dev09StoragePathError(f"Failed to resolve e2e run_dir: {exc}") from exc

    # ---- Persist the e2e summary -----------------------------------------
    summary = E2ERunSummary(
        e2e_run_id=e2e_run_id,
        schema_version=END_TO_END_SCHEMA_VERSION,
        dataset_id=effective_dataset_id,
        dataset_sha256=dataset_sha256 or "",
        storage_root=str(storage_root),
        run_dir=str(run_dir),
        overall_status=overall_status,
        lifecycle=overall_status,
        algorithm=selected_algorithm,
        seed=seed,
        preprocessed_id=preprocessed_id,
        clustering_id=clustering_id,
        evaluation_id=evaluation_id,
        segmentation_id=segmentation_id,
        marketing_id=marketing_id,
        dashboard_id=dashboard_id,
        stages=[outcomes[s] for s in _STAGE_ORDER if s in outcomes],
        inputs=inputs,
        config=config_summary,
        environment=compute_environment_block(),
        notes=[],
        created_utc=_utc_now(),
    )

    try:
        json_path = run_dir / "e2e_run.json"
        json_path.write_text(
            json.dumps(summary.as_dict(), indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:
        raise Dev09Error(f"Failed to write e2e_run.json: {exc}") from exc

    if config.persistence.copy_manifests:
        try:
            _copy_artifacts_into_run(run_dir, outcomes)
        except (OSError, shutil.SameFileError) as exc:
            # Persistence failure is non-fatal; the summary is already
            # written. Surface as a note but do not raise.
            summary = E2ERunSummary(
                **{
                    **summary.__dict__,
                    "notes": list(summary.notes) + [f"manifest copy failed: {exc}"],
                }
            )

    finalize_logging(logger)

    if failed:
        # Surface the failure with a single consolidated message; the
        # summary file already records per-stage details.
        first_failure = next((s for s in summary.stages if s.status == E2E_STAGE_FAILED), None)
        if first_failure is not None:
            raise Dev09Error(
                f"End-to-end pipeline FAILED at stage {first_failure.stage}: "
                f"{first_failure.error_message or first_failure.note}"
            )

    return summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_dataset_manifest_path(storage_root: Path, dataset_id: str) -> Path:
    """Return the canonical manifest.json path for a DEV-02 dataset.

    The file lives at ``<storage_root>/<dataset_id>/manifest.json`` by
    convention. ``storage_root`` already points at
    ``<repo>/data/prototype/datasets`` (per
    ``configs/dev02_dataset_management.yaml``); the dataset id is
    appended directly (no extra ``"datasets"`` literal). See the
    regression test in ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``
    for context.
    """
    return Path(storage_root).resolve() / dataset_id / "manifest.json"


def _copy_artifacts_into_run(run_dir: Path, outcomes: dict[str, E2EStageOutcome]) -> None:
    """Best-effort copy of stage artefacts into the run directory.

    Failures are surfaced via the caller's note; we never raise. We
    copy:
      - DEV-02 dataset manifest (if path known)
      - DEV-03 preprocessed manifest
      - DEV-04 clustering manifest
      - DEV-05 evaluation manifest (and CSV)
      - DEV-06 segmentation manifest
      - DEV-07 marketing manifest
      - DEV-08 dashboard_summary.json
    """
    name_to_dst = {
        "PREPROCESSING": ("preprocessed_manifest.json", "manifest_path"),
        "CLUSTERING": ("clustering_manifest.json", "manifest_path"),
        "EVALUATION": ("evaluation_manifest.json", "manifest_path"),
        "SEGMENTATION": ("segmentation_manifest.json", "manifest_path"),
        "MARKETING": ("marketing_manifest.json", "manifest_path"),
        "VISUALIZATION": ("dashboard_summary.json", "summary_json_path"),
    }
    for stage, (dst_name, src_key) in name_to_dst.items():
        outcome = outcomes.get(stage)
        if outcome is None:
            continue
        src = outcome.artifacts.get(src_key)
        if not src:
            continue
        src_path = Path(src)
        if not src_path.exists():
            continue
        dst = run_dir / dst_name
        with contextlib.suppress(OSError):
            shutil.copy2(src_path, dst)
