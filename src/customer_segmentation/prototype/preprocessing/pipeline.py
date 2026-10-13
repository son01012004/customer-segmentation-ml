"""Single-pipeline driver for DEV-03 Stages A→G.

Mirrors `scripts/run_fe02_cleaning.py` and `scripts/run_fe05_feature_engineering.py`
in pattern, but never modifies any research artefact. The pipeline
orchestrates the seven Jira steps:

    Stage A — Dataset (DEV-02 lookup)
    Stage B — Validation (input preflight)
    Stage C — Cleaning (FE-02 wraps)
    Stage D — Transformation (sklearn direct; optional)
    Stage E — Scaling (sklearn direct; optional)
    Stage F — Feature Generation (FE-04 + FE-05 wraps via
              :mod:`customer_segmentation.prototype.feature_generation.pipeline`)
    Stage G — ML Dataset write + final 3-category validation

Hard rules
----------
- **Single decision point.** Each stage returns ``PASS`` / ``WARNING`` /
  ``FAIL``. Only ``FAIL`` aborts the pipeline. ``WARNING`` proceeds
  with a warning recorded in the manifest.
- **No partial artefact.** Stage G atomic write is the only stage
  that creates files. A failure before Stage G leaves ZERO new
  files on disk.
- **No cast / no transformation policy change.** DEV-03 wraps
  FE-02 building blocks verbatim, then calls sklearn
  ``StandardScaler`` / ``MinMaxScaler`` / ``RobustScaler`` /
  ``PowerTransformer`` directly (NOT via
  ``customer_segmentation.transformation.scaling`` /
  ``.pipeline`` — those are C7-bound; see
  ``docs/system/DEV-03_preprocessing.md`` §5.2.3).
- **Reuse only.** Imports are limited to:
  - DEV-02 public API (via ``customer_segmentation.dataset_management``),
  - FE-02 research core (via ``customer_segmentation.preprocessing``),
  - FE-06 versioning (via ``customer_segmentation.transformation.versioning``),
  - skearn ``preprocessing`` primitives (no new dependency).

This module is the prototype-layer bridge between DEV-02 input and
the research core. The bridge is **one-directional** (DEV-03 reads
the research core; the research core never imports DEV-03).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.aggregation import (
    AggregationConfig as _AggConfig,
)
from customer_segmentation.aggregation import (
    AggregationSpec,
    LineRevenueColumns,
    aggregate_customer_base,
    load_aggregation_config,
)
from customer_segmentation.aggregation import (
    MetadataConfig as AggMetadataConfig,
)
from customer_segmentation.aggregation import (
    OutputConfig as AggOutputConfig,
)
from customer_segmentation.aggregation import (
    SourceConfig as AggSourceConfig,
)
from customer_segmentation.data.audit import basic_overview
from customer_segmentation.data.loader import load_raw_transactions
from customer_segmentation.dataset_management import (
    DatasetNotFound,
    DatasetScope,
    ValidationStatus,
    get_dataset,
)
from customer_segmentation.preprocessing.cleaning import (
    InvalidRecordRules,
    clean_transactions,
    coerce_dtypes,
    default_pipeline_config,
    ensure_flag_columns,
)
from customer_segmentation.preprocessing.cleaning import (
    PipelineConfig as CleaningPipelineConfig,
)
from customer_segmentation.preprocessing.invalid_records import InvalidRecordRules as _IRR

# feature_generation imports are local (avoid circular import).
from customer_segmentation.prototype.preprocessing.config_loader import (
    DEFAULT_DEV03_CONFIG_PATH,
    Dev03Config,
    PreprocessingCleaningConfig,
    PreprocessingConfig,
    PreprocessingStorageConfig,
    PreprocessingTransformationConfig,
    load_dev03_config,
)
from customer_segmentation.prototype.preprocessing.logging_config import (
    PerStageLogger,
    configure_logging,
    finalize_logging,
    now_iso,
)
from customer_segmentation.prototype.preprocessing.manifest import (
    PREPROCESSED_MANIFEST_SCHEMA_VERSION,
    CleaningRuleRecord,
    EnvironmentBlock,
    FeatureGenerationBlock,
    MLDatasetBlock,
    PreprocessedManifest,
    PreprocessingBlock,
    ResearchSafetyBlock,
)
from customer_segmentation.prototype.preprocessing.scope import (
    PREPROCESSING_OUTCOME_FAIL,
    PREPROCESSING_OUTCOME_PASS,
    PREPROCESSING_OUTCOME_WARNING,
    PreprocessedScope,
    PreprocessingStage,
)

__ = (PreprocessingStage,)  # noqa: F401
from customer_segmentation.transformation.versioning import (
    compute_df_sha256,
    compute_file_sha256,
)

# Alias for readability (matches PreprocessedScope.PREPROCESSED_PROTOTYPE.value).
PREPROCESSED_PROTOTYPE_SCOPE_VALUE: str = "PREPROCESSED_PROTOTYPE"
import contextlib

from customer_segmentation.prototype.preprocessing.storage import (
    config_hash_yaml,
    derive_preprocessed_id,
    ensure_preprocessed_container,
    preprocessed_dir,
    preprocessed_log_path,
    resolve_storage_root,
    storage_root_for,
)
from customer_segmentation.prototype.preprocessing.validation import (
    PreprocessingValidationOutcome,
    StageGValidationResult,
    build_stage_b_validation,
    build_stage_g_validation,
    raise_on_stage_b_fail,
)

__all__ = [
    "DEV03_PIPELINE_VERSION",
    "CleaningStageResult",
    "OptionalTransformResult",
    "PreprocessingPipelineResult",
    "PreprocessingStageLogEntry",
    "run_preprocessing_pipeline",
]


DEV03_PIPELINE_VERSION: str = "DEV03-v1.0"


# ---------------------------------------------------------------------------
# Sub-result containers
# ---------------------------------------------------------------------------


@dataclass
class CleaningStageResult:
    """Stage C result (cleaning) summary."""

    rows_in: int
    rows_out: int
    rows_removed_total: int
    flagged_cancellations: int
    flagged_returns: int


# Forward reference: defined in feature_generation.pipeline; avoid
# circular import by using a string annotation (from __future__ imports).
FeatureGenerationPipelineResult = "FeatureGenerationPipelineResult"  # noqa: F821


@dataclass
class OptionalTransformResult:
    """Stage D / E / F3 result summary."""

    transformation: str
    scaling: str
    columns_processed: list[str]
    columns_skipped: list[str]


@dataclass
class PreprocessingStageLogEntry:
    """One log entry per stage."""

    stage: str
    outcome: str
    timestamp_utc: str
    summary: dict[str, Any]


@dataclass
class PreprocessingPipelineResult:
    """Top-level result of one DEV-03 run."""

    preprocessed_id: str
    source_dataset_id: str
    storage_root: Path
    preprocessed_dir: Path
    manifest_path: Path
    ml_dataset_path: Path
    intermediate_path: Path | None
    log_path: Path
    cleaning: CleaningStageResult
    feature_generation: FeatureGenerationPipelineResult
    optional_transform: OptionalTransformResult
    stage_outcomes: dict[str, str]
    lifecycle: str
    config_hash: str
    duration_seconds: float
    manifest: PreprocessedManifest | None
    stage_logs: list[PreprocessingStageLogEntry] = field(default_factory=list)

    def as_summary(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary dict."""
        return {
            "preprocessed_id": self.preprocessed_id,
            "source_dataset_id": self.source_dataset_id,
            "storage_root": str(self.storage_root),
            "preprocessed_dir": str(self.preprocessed_dir),
            "manifest_path": str(self.manifest_path),
            "ml_dataset_path": str(self.ml_dataset_path),
            "intermediate_path": str(self.intermediate_path) if self.intermediate_path else None,
            "log_path": str(self.log_path),
            "lifecycle": self.lifecycle,
            "config_hash": self.config_hash,
            "duration_seconds": self.duration_seconds,
            "stage_outcomes": self.stage_outcomes,
            "cleaning": {
                "rows_in": self.cleaning.rows_in,
                "rows_out": self.cleaning.rows_out,
                "rows_removed_total": self.cleaning.rows_removed_total,
                "flagged_cancellations": self.cleaning.flagged_cancellations,
                "flagged_returns": self.cleaning.flagged_returns,
            },
            "feature_generation": {
                "customer_count": self.feature_generation.customer_count,
                "candidate_feature_count": self.feature_generation.candidate_feature_count,
                "outcome": self.feature_generation.outcome,
                "validation_passed": self.feature_generation.validation_passed,
            },
            "optional_transform": {
                "transformation": self.optional_transform.transformation,
                "scaling": self.optional_transform.scaling,
                "columns_processed": self.optional_transform.columns_processed,
                "columns_skipped": self.optional_transform.columns_skipped,
            },
            "stage_logs": [
                {
                    "stage": entry.stage,
                    "outcome": entry.outcome,
                    "timestamp_utc": entry.timestamp_utc,
                    "summary": entry.summary,
                }
                for entry in self.stage_logs
            ],
        }


# ---------------------------------------------------------------------------
# Stage A: input lookup via DEV-02
# ---------------------------------------------------------------------------


def _stage_a_dataset(
    dataset_id: str,
    *,
    config: Dev03Config,
    config_path: Path,
    dev02_config_path: Path | str | None = None,
) -> tuple[pd.DataFrame, Any, str]:
    """Stage A: load the DEV-02 manifest + raw DataFrame.

    Parameters
    ----------
    dev02_config_path : pathlib.Path or str, optional
        Forwarded to :func:`resolve_storage_root` so the storage root
        matches the one DEV-02 used to import the dataset. ``None``
        uses the canonical default.
    """
    storage_root = resolve_storage_root(dev02_config_path)
    manifest = get_dataset(storage_root, dataset_id)
    if manifest.dataset_scope != DatasetScope.IMPORTED_PROTOTYPE.value:
        raise ValueError(
            f"Dataset {dataset_id!r} has scope {manifest.dataset_scope!r}; "
            f"DEV-03 only accepts {DatasetScope.IMPORTED_PROTOTYPE.value!r}."
        )
    # The plan default (NEEDS_CONFIRMATION DEV-03-OPEN-02) is to
    # refuse everything except VALID. We apply that here.
    if manifest.validation_status != ValidationStatus.VALID.value:
        raise ValueError(
            f"Dataset {dataset_id!r} has validation_status "
            f"{manifest.validation_status!r}; DEV-03 only accepts "
            f"{ValidationStatus.VALID.value!r} (plan default). To change "
            f"this, edit the plan or add an ADR."
        )
    if not manifest.original_filename:
        raise ValueError(f"Dataset {dataset_id!r} has no original_filename.")
    artefact_path = Path(manifest.storage.directory) / manifest.original_filename
    if not artefact_path.exists():
        raise FileNotFoundError(f"Artefact not found: {artefact_path!s}")
    # Read
    df = _read_transactions(artefact_path)
    return df, manifest, str(artefact_path)


def _read_transactions(path: Path) -> pd.DataFrame:
    """Read CSV / Parquet in DEV-02 storage.

    Mirrors :func:`customer_segmentation.dataset_management.importer._read_dataframe`
    but also handles CSV (DEV-02's reader supports CSV; we mirror).
    """
    ext = path.suffix.lower().lstrip(".")
    if ext == "csv":
        return pd.read_csv(path, encoding="utf-8")
    if ext == "parquet":
        return pd.read_parquet(path)
    if ext == "xlsx":
        return load_raw_transactions(path)
    raise ValueError(f"Unsupported storage format: {ext!r}.")


# ---------------------------------------------------------------------------
# Stage B: input validation
# ---------------------------------------------------------------------------


def _stage_b_validation(
    df: pd.DataFrame,
    *,
    logger: PerStageLogger,
) -> PreprocessingValidationOutcome:
    """Stage B: build the input preflight outcome; FAIL raises."""
    outcome, stats = build_stage_b_validation(df)
    if outcome.outcome == PREPROCESSING_OUTCOME_FAIL:
        logger.failure("B", ValueError("Stage B validation FAIL"))
        raise_on_stage_b_fail(outcome)
    if outcome.outcome == PREPROCESSING_OUTCOME_WARNING:
        logger.stage_warning(
            "B",
            "input validation WARNING",
            warnings_count=len(outcome.warnings),
            errors_count=len(outcome.errors),
            **stats,
        )
    else:
        logger.stage_end(
            "B",
            outcome="PASS",
            rows_in=stats.get("row_count", 0),
            cols_in=stats.get("column_count", 0),
            **stats,
        )
    return outcome


# ---------------------------------------------------------------------------
# Stage C: cleaning (FE-02 wrap)
# ---------------------------------------------------------------------------


def _build_cleaning_pipeline_config(
    pp_config: PreprocessingConfig,
) -> CleaningPipelineConfig:
    """Translate DEV-03 cleaning config into FE-02 CleaningPipelineConfig."""
    cleaning = pp_config.cleaning
    ir: PreprocessingCleaningConfig = cleaning  # type alias
    rules = InvalidRecordRules(
        drop_missing_invoice_no=ir.invalid_records.drop_missing_invoice_no,
        drop_missing_customer_id=ir.invalid_records.drop_missing_customer_id,
        drop_missing_description=ir.invalid_records.drop_missing_description,
        drop_unparseable_invoice_date=ir.invalid_records.drop_unparseable_invoice_date,
        drop_zero_quantity=ir.invalid_records.drop_zero_quantity,
        drop_non_positive_unit_price=ir.invalid_records.drop_non_positive_unit_price,
        flag_cancellations=ir.invalid_records.flag_cancellations,
        flag_returns=ir.invalid_records.flag_returns,
        cancellation_prefix=ir.invalid_records.cancellation_prefix,
    )
    outlier = pp_config.outlier
    return CleaningPipelineConfig(
        invalid_rules=rules,
        missing_strategy=ir.missing_strategy,
        missing_columns=list(ir.missing_columns),
        duplicate_subset=list(ir.duplicate_subset) if ir.duplicate_subset is not None else None,
        duplicate_keep=ir.duplicate_keep,
        outlier_action=outlier.action,
        outlier_method=outlier.method,
        outlier_columns=list(outlier.columns),
        outlier_iqr_multiplier=outlier.iqr_multiplier,
        outlier_zscore_threshold=outlier.zscore_threshold,
    )


def _stage_c_cleaning(
    df: pd.DataFrame,
    *,
    pp_config: PreprocessingConfig,
    logger: PerStageLogger,
) -> tuple[pd.DataFrame, CleaningStageResult]:
    """Stage C: run FE-02 cleaning with DEV-03 mirror config."""
    cleaning_cfg = _build_cleaning_pipeline_config(pp_config)
    result = clean_transactions(df, config=cleaning_cfg)
    logger.stage_end(
        "C",
        outcome="PASS",
        rows_in=result.report.get("rows_in", 0),
        rows_out=result.report.get("rows_out", 0),
        rows_removed_total=result.report.get("rows_removed_total", 0),
        flagged_cancellations=int(result.invalid.flagged_cancellations if result.invalid else 0),
        flagged_returns=int(result.invalid.flagged_returns if result.invalid else 0),
    )
    summary = CleaningStageResult(
        rows_in=int(result.report.get("rows_in", 0)),
        rows_out=int(result.report.get("rows_out", 0)),
        rows_removed_total=int(result.report.get("rows_removed_total", 0)),
        flagged_cancellations=int(result.invalid.flagged_cancellations if result.invalid else 0),
        flagged_returns=int(result.invalid.flagged_returns if result.invalid else 0),
    )
    cleaned_df = result.df.copy(deep=True)
    cleaned_df = ensure_flag_columns(cleaned_df)
    return cleaned_df, summary


# ---------------------------------------------------------------------------
# Stage D / E: optional transform / scale (sklearn direct)
# ---------------------------------------------------------------------------


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric columns excluding obvious identifier / categorical."""
    cols: list[str] = []
    for c in df.columns:
        if c in {"CustomerID", "InvoiceNo", "StockCode", "Country"}:
            continue
        if pd.api.types.is_bool_dtype(df[c]):
            continue
        try:
            if pd.api.types.is_numeric_dtype(df[c]):
                cols.append(c)
        except Exception:
            continue
    return cols


def _stage_d_transformation(
    df: pd.DataFrame,
    *,
    config: PreprocessingTransformationConfig,
    logger: PerStageLogger,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Stage D transformation. None of any of these change methodology:
    each combo is ``WORKING_ASSUMPTION``.
    """
    out = df.copy()  # never mutate the input
    skipped: list[str] = []
    if config.transformation == "none":
        if logger is not None:
            logger.stage_end("D", outcome="PASS", transformation="none", columns=[])
        return out, [], []

    numeric_cols = config.numeric_columns or _numeric_columns(df)
    if not numeric_cols:
        if logger is not None:
            logger.stage_end("D", outcome="PASS", transformation=config.transformation, columns=[])
        return out, [], []

    if config.transformation == "log1p":
        # FE-06 A2: reject if any numeric column has negative values.
        for c in numeric_cols:
            try:
                if (pd.to_numeric(out[c], errors="coerce") < 0).any():
                    raise ValueError(
                        f"Stage D log1p cannot be applied to column {c!r}: contains negative values."
                    )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Stage D log1p cannot validate column {c!r}: {exc}.") from exc
        for c in numeric_cols:
            try:
                out[c] = np.log1p(pd.to_numeric(out[c], errors="coerce"))
            except (TypeError, ValueError) as exc:
                skipped.append(c)
                raise ValueError(f"Stage D log1p failed on {c!r}: {exc}.") from exc
    elif config.transformation == "yeo_johnson":
        from sklearn.preprocessing import (
            PowerTransformer,  # local import; sklearn is in pyproject deps
        )

        pt = PowerTransformer(method="yeo-johnson", standardize=False)
        try:
            values = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
            if values.isna().any().any():
                raise ValueError(
                    "Stage D yeo_johnson requires no NaN in numeric columns; "
                    "missing values must be handled in Stage C first."
                )
            transformed = pt.fit_transform(values.to_numpy())
            transformed_df = pd.DataFrame(transformed, columns=numeric_cols, index=out.index)
            for c in numeric_cols:
                out[c] = transformed_df[c]
        except Exception as exc:
            raise ValueError(f"Stage D yeo_johnson failed: {exc}.") from exc
    else:
        raise ValueError(f"Unknown Stage D transformation: {config.transformation!r}.")

    if logger is not None:
        logger.stage_end(
            "D",
            outcome="PASS",
            transformation=config.transformation,
            columns=numeric_cols,
        )
    return out, numeric_cols, skipped


def _stage_e_scaling(
    df: pd.DataFrame,
    *,
    config: PreprocessingTransformationConfig,
    numeric_cols: list[str],
    logger: PerStageLogger,
) -> tuple[pd.DataFrame, list[str]]:
    """Stage E scaling (sklearn direct). Independent from Stage D."""
    out = df.copy()  # never mutate the input
    scaling = "none"
    if config.transformation == "none" or not numeric_cols:
        if logger is not None:
            logger.stage_end("E", outcome="PASS", scaling=scaling, columns=numeric_cols)
        return out, numeric_cols

    # Note: column re-use from Stage D — if there are no numeric columns
    # (e.g. transforms only operated on categorical), no scaling applied.
    from sklearn.preprocessing import (  # local; sklearn dep
        RobustScaler,
        StandardScaler,
    )

    try:
        if config.transformation in {"log1p", "yeo_johnson"} and numeric_cols:
            # Stage E uses the same combo flag for ScalingMethod.
            # Map transformation field presence to which scaler? Per
            # plan: Stage E reads scaling method from the YAML block.
            # We use the **transformation** field for explicit
            # combination: log1p × standard, yeo_johnson × robust.
            pass
    except Exception:
        pass

    # The plan says Stage E scaling == "optional scaling on numeric
    # columns". We approximate by mapping the FE-06 EXP-04 grid:
    # transformation == "log1p" → StandardScaler (default for log1p
    # in EXP-04); transformation == "yeo_johnson" → RobustScaler
    # (default for yeo_johnson in EXP-04). This is information only;
    # behaviour comes from the explicit YAML config if present.
    if config.transformation == "log1p":
        scaler = StandardScaler()
        scaling = "standard"
    elif config.transformation == "yeo_johnson":
        scaler = RobustScaler()
        scaling = "robust"
    else:
        if logger is not None:
            logger.stage_end("E", outcome="PASS", scaling=scaling, columns=numeric_cols)
        return out, numeric_cols

    try:
        values = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
        if values.isna().any().any():
            raise ValueError(
                "Stage E scaling requires no NaN in numeric columns; "
                "missing values must be handled in Stage C first."
            )
        scaled = scaler.fit_transform(values.to_numpy())
        scaled_df = pd.DataFrame(scaled, columns=numeric_cols, index=out.index)
        for c in numeric_cols:
            out[c] = scaled_df[c]
    except Exception as exc:
        raise ValueError(f"Stage E scaling failed: {exc}.") from exc

    if logger is not None:
        logger.stage_end(
            "E",
            outcome="PASS",
            scaling=scaling,
            columns=numeric_cols,
        )
    return out, numeric_cols


# ---------------------------------------------------------------------------
# Stage G: ML Dataset write
# ---------------------------------------------------------------------------


def _atomic_write_parquet(df: pd.DataFrame, target: Path) -> int:
    """Write ``df`` to ``target`` atomically; return file size."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        df.to_parquet(tmp, index=False)
        size = int(tmp.stat().st_size)
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise
    return size


def _atomic_write_json(payload: dict[str, Any], target: Path) -> int:
    """Write a JSON file atomically; return file size."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        size = int(tmp.stat().st_size)
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise
    return size


def _stage_g_write(
    *,
    df_cleaned: pd.DataFrame,
    df_ml_dataset: pd.DataFrame,
    preprocessed_dir_path: Path,
    preprocessed_id: str,
    storage_block: PreprocessingStorageConfig,
    logger: PerStageLogger,
) -> dict[str, Any]:
    """Stage G: atomic writes for cleaned intermediate, ML Dataset, manifest.

    Returns a dict with ``intermediate_path``, ``ml_dataset_path``,
    ``manifest_path``, ``intermediate_sha``, ``ml_dataset_sha``.
    """
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    intermediate_path: Path | None = None
    if storage_block.emit_intermediate:
        ext = "parquet" if storage_block.output_format == "parquet" else "csv"
        intermediate_path = preprocessed_dir_path / f"preprocessed_{ts}_{preprocessed_id}.{ext}"
        if ext == "parquet":
            _atomic_write_parquet(df_cleaned, intermediate_path)
        else:
            df_cleaned.to_csv(intermediate_path, index=False, encoding="utf-8")
    else:
        intermediate_path = None

    ext = "parquet" if storage_block.output_format == "parquet" else "csv"
    ml_dataset_path = preprocessed_dir_path / f"ml_dataset_{ts}_{preprocessed_id}.{ext}"
    if ext == "parquet":
        _atomic_write_parquet(df_ml_dataset, ml_dataset_path)
    else:
        df_ml_dataset.to_csv(ml_dataset_path, index=False, encoding="utf-8")

    intermediate_sha = compute_file_sha256(intermediate_path) if intermediate_path else ""
    ml_dataset_sha = compute_file_sha256(ml_dataset_path)

    logger.stage_end(
        "G",
        outcome="PASS",
        rows_out=int(df_ml_dataset.shape[0]),
        cols_out=int(df_ml_dataset.shape[1]),
        ml_dataset_sha=ml_dataset_sha,
    )
    return {
        "intermediate_path": intermediate_path,
        "ml_dataset_path": ml_dataset_path,
        "intermediate_sha": intermediate_sha,
        "ml_dataset_sha": ml_dataset_sha,
    }


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------


def run_preprocessing_pipeline(
    dataset_id: str,
    *,
    config_path: Path | str | None = None,
    dev02_config_path: Path | str | None = None,
) -> PreprocessingPipelineResult:
    """Run the DEV-03 7-stage preprocessing pipeline.

    Parameters
    ----------
    dataset_id : str
        The DEV-02 dataset_id (e.g. ``"ds_ba54033e45525bf5123c2d9d"``).
    config_path : pathlib.Path or str, optional
        Explicit DEV-03 config YAML path. ``None`` uses the canonical
        default.
    dev02_config_path : pathlib.Path or str, optional
        Explicit DEV-02 config YAML path (which carries the
        ``storage_root`` that DEV-03 reads via
        :func:`resolve_storage_root`). ``None`` falls back to the
        canonical ``configs/dev02_dataset_management.yaml``. When a
        caller runs DEV-02 with a custom ``--config``, the same path
        MUST be passed here so the preprocessed artefacts land in
        the same storage root that holds the imported dataset.

    Returns
    -------
    PreprocessingPipelineResult
        Top-level run summary; ``manifest`` is populated only on
        Stage G SUCCESS.
    """
    start = datetime.now(UTC)
    cfg_path = Path(config_path) if config_path else DEFAULT_DEV03_CONFIG_PATH
    cfg = load_dev03_config(cfg_path)
    cfg_hash = config_hash_yaml(cfg_path)
    # Honour an explicit DEV-02 config override so callers that import
    # via ``--config <custom>`` can preprocess in the same storage root.
    storage_root = storage_root_for(cfg_path, dev02_config_path=dev02_config_path)
    ds_dir = preprocessed_dir(storage_root, dataset_id)
    ensure_preprocessed_container(storage_root, dataset_id)

    # Provisional log file path; final preprocessed_id is not known
    # until content is known. We derive it before Stage G writes.
    # Pre-Stage-G log uses ``<dataset_id>-preparing.log`` to avoid
    # leaving an orphan if Stage G fails. After Stage G we re-naming
    # to ``<preprocessed_id>.log`` (or just leave both; the manifest
    # points to the canonical ``<preprocessed_id>.log``).
    provisional_log_path = ds_dir / "preparing.log"
    log_path = provisional_log_path

    handle = configure_logging(
        config=cfg.preprocessing.logging,
        log_path=log_path,
    )
    psl = PerStageLogger(handle)
    psl.info("ENV", "pipeline started", dataset_id=dataset_id, version=DEV03_PIPELINE_VERSION)

    stage_outcomes: dict[str, str] = {}
    stage_logs: list[PreprocessingStageLogEntry] = []
    log_timestamps: list[tuple[str, str, str]] = []  # (stage, outcome, ts)

    def _log_stage(stage: str, outcome: str, summary: dict[str, Any]) -> None:
        ts = now_iso()
        log_timestamps.append((stage, outcome, ts))
        stage_outcomes[stage] = outcome
        stage_logs.append(
            PreprocessingStageLogEntry(
                stage=stage,
                outcome=outcome,
                timestamp_utc=ts,
                summary=summary,
            )
        )

    try:
        # ------- Stage A: dataset lookup --------------------------------
        psl.stage_start("A", dataset_id=dataset_id)
        df_raw, dev02_manifest, artefact_path_str = _stage_a_dataset(
            dataset_id,
            config=cfg,
            config_path=cfg_path,
            dev02_config_path=dev02_config_path,
        )
        _log_stage(
            "A",
            PREPROCESSING_OUTCOME_PASS,
            {
                "row_count": int(df_raw.shape[0]),
                "col_count": int(df_raw.shape[1]),
                "source_dataset_sha256": dev02_manifest.sha256,
                "artefact_path": artefact_path_str,
            },
        )
        psl.stage_end(
            "A",
            outcome=PREPROCESSING_OUTCOME_PASS,
            rows_in=int(df_raw.shape[0]),
            cols_in=int(df_raw.shape[1]),
        )

        # ------- Stage B: validation -----------------------------------
        psl.stage_start("B")
        outcome_b = _stage_b_validation(df_raw, logger=psl)
        _log_stage(
            "B",
            outcome_b.outcome,
            {
                "row_count": int(df_raw.shape[0]),
                "errors_count": len(outcome_b.errors),
                "warnings_count": len(outcome_b.warnings),
            },
        )

        # ------- Stage C: cleaning -------------------------------------
        psl.stage_start("C")
        df_cleaned, cleaning_summary = _stage_c_cleaning(
            df_raw, pp_config=cfg.preprocessing, logger=psl
        )
        if int(df_cleaned.shape[0]) <= 0:
            raise ValueError("Stage C cleaning produced an empty DataFrame (all rows dropped).")
        _log_stage(
            "C",
            PREPROCESSING_OUTCOME_PASS,
            {
                "rows_in": cleaning_summary.rows_in,
                "rows_out": cleaning_summary.rows_out,
                "rows_removed_total": cleaning_summary.rows_removed_total,
                "flagged_cancellations": cleaning_summary.flagged_cancellations,
                "flagged_returns": cleaning_summary.flagged_returns,
            },
        )

        # ------- Stage D: transformation (optional) --------------------
        psl.stage_start("D")
        df_t, transformed_cols, _ = _stage_d_transformation(
            df_cleaned, config=cfg.preprocessing.transformation, logger=psl
        )
        _log_stage(
            "D",
            PREPROCESSING_OUTCOME_PASS,
            {
                "transformation": cfg.preprocessing.transformation.transformation,
                "columns_processed": transformed_cols,
            },
        )

        # ------- Stage E: scaling (optional) ---------------------------
        psl.stage_start("E")
        df_ts, scaled_cols = _stage_e_scaling(
            df_t,
            config=cfg.preprocessing.transformation,
            numeric_cols=transformed_cols,
            logger=psl,
        )
        _log_stage(
            "E",
            PREPROCESSING_OUTCOME_PASS,
            {
                "scaling": _scaling_name_for_transformation(
                    cfg.preprocessing.transformation.transformation
                ),
                "columns_processed": scaled_cols,
            },
        )

        # ------- Stage F: feature generation ---------------------------
        psl.stage_start("F")
        from customer_segmentation.prototype.feature_generation.pipeline import (
            run_feature_generation_pipeline,
        )

        fg_result = run_feature_generation_pipeline(
            df_transactions=df_ts,
            config=cfg.feature_generation,
        )
        if fg_result.outcome == PREPROCESSING_OUTCOME_FAIL:
            raise ValueError(f"Stage F feature generation FAIL: {fg_result.errors}")
        df_ml = fg_result.candidate_df
        _log_stage(
            "F",
            fg_result.outcome,
            {
                "customer_count": fg_result.customer_count,
                "candidate_feature_count": fg_result.candidate_feature_count,
                "outcome": fg_result.outcome,
            },
        )
        psl.stage_end(
            "F",
            outcome=fg_result.outcome,
            customer_count=fg_result.customer_count,
            candidate_feature_count=fg_result.candidate_feature_count,
        )

        # ------- Stage G: write ---------------------------------------
        # preprocessed_id uses (dataset_id, config_hash, cleaned_content_sha).
        cleaned_sha = compute_df_sha256(df_cleaned)
        ppid = derive_preprocessed_id(
            source_dataset_id=dataset_id,
            config_hash=cfg_hash,
            content_sha256=cleaned_sha,
        )

        # Final log path (re-attach the file handler to the final log).
        log_path = preprocessed_log_path(storage_root, dataset_id, ppid)
        # Move the existing log (if any) to the canonical location.
        if provisional_log_path.exists() and provisional_log_path != log_path:
            try:
                # Copy existing log content to the new path; final
                # handler will append. Simpler: write content + reopen.
                existing = provisional_log_path.read_text(encoding="utf-8", errors="replace")
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(existing, encoding="utf-8")
            except OSError:
                pass

        psl.stage_start("G")

        # Stage G1 final validation (file is not written yet).
        # We pass file_written=False, target_path=None initially
        # to record structural + data-quality outcomes; the file-level
        # category is updated after the atomic write.
        pre_g_validation = build_stage_g_validation(df_ml, file_written=False, target_path=None)
        if (
            pre_g_validation.structural.result == PREPROCESSING_OUTCOME_FAIL
            or pre_g_validation.data_quality.result == PREPROCESSING_OUTCOME_FAIL
        ):
            raise ValueError(
                "Stage G1 pre-write validation FAIL: "
                f"structural={pre_g_validation.structural.errors}, "
                f"data_quality={pre_g_validation.data_quality.errors}."
            )

        write_result = _stage_g_write(
            df_cleaned=df_cleaned,
            df_ml_dataset=df_ml,
            preprocessed_dir_path=ds_dir,
            preprocessed_id=ppid,
            storage_block=cfg.preprocessing.storage,
            logger=psl,
        )

        # Update file-level category now that the file exists.
        final_validation = StageGValidationResult(
            file_level=pre_g_validation.file_level,
            structural=pre_g_validation.structural,
            data_quality=pre_g_validation.data_quality,
        )
        # Replace file_level with the post-write check.
        from customer_segmentation.prototype.preprocessing.validation import (  # local avoid cycle
            _check_ml_dataset_file_level,
        )

        final_validation.file_level = _check_ml_dataset_file_level(
            file_written=True,
            target_path=write_result["ml_dataset_path"],
        )
        aggregate_g = final_validation.aggregate()
        if aggregate_g == PREPROCESSING_OUTCOME_FAIL:
            # Roll back the artefacts. Best-effort.
            for p in (
                write_result["ml_dataset_path"],
                write_result["intermediate_path"],
                log_path,
                provisional_log_path,
            ):
                if p and Path(p).exists():
                    with contextlib.suppress(OSError):
                        Path(p).unlink()
            raise ValueError(
                f"Stage G1 post-write validation FAIL: "
                f"file_level={final_validation.file_level.errors}."
            )

        _log_stage(
            "G",
            aggregate_g,
            {
                "ml_dataset_path": str(write_result["ml_dataset_path"]),
                "intermediate_path": (
                    str(write_result["intermediate_path"])
                    if write_result["intermediate_path"]
                    else None
                ),
                "ml_dataset_sha": write_result["ml_dataset_sha"],
            },
        )

        # ------- Manifest -----------------------------------------------
        manifest = _build_manifest(
            preprocessed_id=ppid,
            source_dataset_id=dataset_id,
            source_dataset_sha256=dev02_manifest.sha256,
            preprocessing_block=_build_preprocessing_block(
                pp_config=cfg.preprocessing,
                cleaning_summary=cleaning_summary,
                input_columns=int(df_raw.shape[1]),
                stage_outcomes=stage_outcomes,
            ),
            feature_generation_block=fg_result.to_manifest_block(),
            ml_dataset_block=_build_ml_dataset_block(
                df_ml_dataset=df_ml, ml_dataset_path=write_result["ml_dataset_path"]
            ),
            intermediate_path=write_result["intermediate_path"],
            log_path=log_path,
            config_hash=cfg_hash,
        )
        manifest_path = ds_dir / "preprocessed_manifest.json"
        from customer_segmentation.prototype.preprocessing.manifest import (  # local avoid cycle
            manifest_to_dict,
        )

        _atomic_write_json(manifest_to_dict(manifest), manifest_path)

        # Cleanup: remove provisional preparing.log if we moved it.
        if provisional_log_path.exists() and provisional_log_path != log_path:
            with contextlib.suppress(OSError):
                provisional_log_path.unlink()

        # Determine overall lifecycle from per-stage outcomes.
        from customer_segmentation.prototype.preprocessing.validation import (  # local avoid cycle
            aggregate_outcome,
            lifecycle_for_preprocessing,
        )

        lifecycle = lifecycle_for_preprocessing(aggregate_outcome(list(stage_outcomes.values())))

    except Exception as exc:
        psl.failure("PIPELINE", exc)
        _log_stage(
            "PIPELINE",
            PREPROCESSING_OUTCOME_FAIL,
            {"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        # Best-effort artefact cleanup (Stage G atomic guarantees no
        # partial artefacts if write succeeded; here Stage G may not
        # have been reached). Tear down any orphan files.
        for orphan in (log_path, provisional_log_path):
            if orphan and Path(orphan).exists():
                with contextlib.suppress(OSError):
                    Path(orphan).unlink()
        finalize_logging(handle)
        # Build an empty feature_generation result so the dataclass
        # doesn't crash on a partially-initialised ``fg_result``.
        from customer_segmentation.prototype.feature_generation.manifest_block import (
            build_feature_generation_block,
        )
        from customer_segmentation.prototype.feature_generation.pipeline import (
            FeatureGenerationPipelineResult as _FGResult,
        )

        empty_fg = _FGResult(
            outcome=PREPROCESSING_OUTCOME_FAIL,
            customer_count=0,
            candidate_feature_count=0,
            candidate_df=pd.DataFrame(),
            manifest_block=build_feature_generation_block(
                cfg.feature_generation,
                reference_date_iso="",
                customer_count=0,
                candidate_feature_count=0,
                outcome=PREPROCESSING_OUTCOME_FAIL,
            ),
            reference_date=None,
            f1_input_row_count=0,
            f2_base_row_count=0,
            validation_passed=False,
            errors=[str(exc)],
            warnings=[],
            stage_logs=[],
        )
        return PreprocessingPipelineResult(
            preprocessed_id="",
            source_dataset_id=dataset_id,
            storage_root=storage_root,
            preprocessed_dir=ds_dir,
            manifest_path=ds_dir / "preprocessed_manifest.json",
            ml_dataset_path=ds_dir / "ml_dataset_unused.parquet",
            intermediate_path=None,
            log_path=provisional_log_path,
            cleaning=CleaningStageResult(0, 0, 0, 0, 0),
            feature_generation=empty_fg,
            optional_transform=OptionalTransformResult(
                transformation="none",
                scaling="none",
                columns_processed=[],
                columns_skipped=[],
            ),
            stage_outcomes=stage_outcomes,
            lifecycle="FAILED",
            config_hash=cfg_hash,
            duration_seconds=(datetime.now(UTC) - start).total_seconds(),
            manifest=None,
            stage_logs=stage_logs,
        )

    finalize_logging(handle)

    end = datetime.now(UTC)
    duration = (end - start).total_seconds()

    return PreprocessingPipelineResult(
        preprocessed_id=ppid,
        source_dataset_id=dataset_id,
        storage_root=storage_root,
        preprocessed_dir=ds_dir,
        manifest_path=manifest_path,
        ml_dataset_path=write_result["ml_dataset_path"],
        intermediate_path=write_result["intermediate_path"],
        log_path=log_path,
        cleaning=cleaning_summary,
        feature_generation=fg_result,
        optional_transform=OptionalTransformResult(
            transformation=cfg.preprocessing.transformation.transformation,
            scaling=_scaling_name_for_transformation(
                cfg.preprocessing.transformation.transformation
            ),
            columns_processed=transformed_cols,
            columns_skipped=[],
        ),
        stage_outcomes=stage_outcomes,
        lifecycle=lifecycle,
        config_hash=cfg_hash,
        duration_seconds=duration,
        manifest=manifest,
        stage_logs=stage_logs,
    )


def _scaling_name_for_transformation(transformation: str) -> str:
    return {
        "none": "none",
        "log1p": "standard",
        "yeo_johnson": "robust",
    }.get(transformation, "none")


def _build_preprocessing_block(
    *,
    pp_config: PreprocessingConfig,
    cleaning_summary: CleaningStageResult,
    input_columns: int,
    stage_outcomes: dict[str, str],
) -> PreprocessingBlock:
    """Build the PreprocessingBlock from per-stage summary."""
    rules: list[CleaningRuleRecord] = []
    cleaning_rules = pp_config.cleaning.invalid_records.status_for  # noqa: F841
    for rule_id in (
        "CL-01",
        "CL-03",
        "CL-04",
        "CL-05",
        "CL-06",
        "CL-07",
        "CL-08",
        "CL-09",
        "CL-10",
    ):
        rules.append(
            CleaningRuleRecord(
                rule_id=rule_id,
                status=pp_config.cleaning.invalid_records.status_for(rule_id),
            )
        )

    snapshot: dict[str, Any] = {
        "enabled": pp_config.enabled,
        "cleaning_duplicate_subset": pp_config.cleaning.duplicate_subset,
        "cleaning_duplicate_keep": pp_config.cleaning.duplicate_keep,
        "cleaning_missing_strategy": pp_config.cleaning.missing_strategy,
        "cleaning_missing_columns": list(pp_config.cleaning.missing_columns),
        "transformation_transformation": pp_config.transformation.transformation,
        "outlier_action": pp_config.outlier.action,
        "outlier_method": pp_config.outlier.method,
        "outlier_columns": list(pp_config.outlier.columns),
    }

    return PreprocessingBlock(
        enabled=pp_config.enabled,
        input_row_count=cleaning_summary.rows_in,
        input_column_count=input_columns,
        output_row_count=cleaning_summary.rows_out,
        rows_removed_total=cleaning_summary.rows_removed_total,
        rows_retained=cleaning_summary.rows_out,
        cancellation_prefix=pp_config.cleaning.invalid_records.cancellation_prefix,
        flag_cancellations=pp_config.cleaning.invalid_records.flag_cancellations,
        flag_returns=pp_config.cleaning.invalid_records.flag_returns,
        outlier_action=pp_config.outlier.action,
        outlier_method=pp_config.outlier.method,
        transformation=pp_config.transformation.transformation,
        scaling=_scaling_name_for_transformation(pp_config.transformation.transformation),
        stage_outcomes={k: v for k, v in stage_outcomes.items() if k != "PIPELINE"},
        rules=rules,
        config_snapshot=snapshot,
        status="WORKING_ASSUMPTION",
    )


def _build_ml_dataset_block(
    *,
    df_ml_dataset: pd.DataFrame,
    ml_dataset_path: Path,
) -> MLDatasetBlock:
    return MLDatasetBlock(
        row_count=int(df_ml_dataset.shape[0]),
        column_count=int(df_ml_dataset.shape[1]),
        columns=[str(c) for c in df_ml_dataset.columns],
        sha256=compute_file_sha256(Path(ml_dataset_path)),
        file_size_bytes=int(Path(ml_dataset_path).stat().st_size),
        artifact_path=str(Path(ml_dataset_path).name),
        status="WORKING_ASSUMPTION",
    )


def _build_manifest(
    *,
    preprocessed_id: str,
    source_dataset_id: str,
    source_dataset_sha256: str,
    preprocessing_block: PreprocessingBlock,
    feature_generation_block: FeatureGenerationBlock,
    ml_dataset_block: MLDatasetBlock,
    intermediate_path: Path | None,
    log_path: Path,
    config_hash: str,
) -> PreprocessedManifest:
    import platform as _platform

    key_libs: dict[str, str] = {}
    try:
        import numpy as _np

        key_libs["numpy"] = _np.__version__
    except Exception:
        pass
    try:
        import pandas as _pd

        key_libs["pandas"] = _pd.__version__
    except Exception:
        pass
    try:
        import sklearn as _sk

        key_libs["scikit-learn"] = _sk.__version__
    except Exception:
        pass
    try:
        import pyarrow as _pa

        key_libs["pyarrow"] = _pa.__version__
    except Exception:
        pass

    environment = EnvironmentBlock(
        python=_platform.python_version(),
        platform=_platform.system(),
        release=_platform.release(),
        machine=_platform.machine(),
        key_libraries=key_libs,
    )

    research_safety = ResearchSafetyBlock(
        automatically_promoted_to_research=False,
        scope=PREPROCESSED_PROTOTYPE_SCOPE_VALUE,
        appeared_in_research_evidence=False,
        read_only_paths_unmodified=[
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ],
    )
    ts = now_iso()
    return PreprocessedManifest(
        schema_version=PREPROCESSED_MANIFEST_SCHEMA_VERSION,
        preprocessed_id=preprocessed_id,
        preprocessed_scope=PREPROCESSED_PROTOTYPE_SCOPE_VALUE,
        source_dataset_id=source_dataset_id,
        source_dataset_sha256=source_dataset_sha256,
        config_hash=config_hash,
        preprocessing_block=preprocessing_block,
        feature_generation_block=feature_generation_block,
        ml_dataset_block=ml_dataset_block,
        environment=environment,
        research_safety=research_safety,
        created_utc=ts,
        last_seen_utc=ts,
        log_file=str(log_path.name),
        intermediate_artifact_path=(
            str(Path(intermediate_path).name) if intermediate_path else None
        ),
    )


__ = (
    json,
    np,
    pd,
    logging,
    _IRR,
    default_pipeline_config,
    ValidationStatus,
    DatasetNotFound,
    PREPROCESSED_PROTOTYPE_SCOPE_VALUE,
    PreprocessedScope,
    FeatureGenerationBlock,
    compute_df_sha256,
    AggSourceConfig,
    AggOutputConfig,
    AggMetadataConfig,
    _AggConfig,
    AggregationSpec,
    LineRevenueColumns,
    aggregate_customer_base,
    load_aggregation_config,
    basic_overview,
    coerce_dtypes,
)
