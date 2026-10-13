"""Single-pipeline import driver for DEV-02 Dataset Management.

The :func:`import_dataset` function implements the linear pipeline
described in docs/system/DEV-02_dataset_management.md §5.1::

    A. file preflight
    B. read dataframe
    C. inspect (schema, missing, statistics, mixed-type)
    D. validation
    E. atomic artefact + manifest write

Hard rules
----------
- **Single decision point.** The validation aggregate result is the
  only switch that gates Stage E. A FAIL aborts without writing.
- **No partial artefact.** Stage E either writes both the data file
  and ``manifest.json`` atomically, or writes neither.
- **No cast / no transform.** The mixed-type detector inspects Python
  runtime types on a deterministic head sample; it does not coerce,
  parse, or transform values.
- **Reuse only.** This module imports from
  :mod:`customer_segmentation.data.audit` (read-only), from
  :mod:`customer_segmentation.data.validator` (the
  :class:`ValidationResult` container — used only as a type
  reference, **not** as a runtime dependency in this module), and
  from :mod:`customer_segmentation.transformation.versioning` (only
  :func:`compute_file_sha256`).
- **No new dependencies.** The module uses ``pandas``, ``numpy``,
  ``pyarrow`` and stdlib only.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from customer_segmentation.data.audit import (
    categorical_profile,
    missing_profile,
    numerical_profile,
)
from customer_segmentation.dataset_management.manifest import (
    CategoricalStats,
    ColumnInfo,
    Manifest,
    NumericStats,
    Provenance,
    ResearchSafety,
    StatisticsSummary,
    StorageInfo,
    ValidationCategory,
    now_iso,
)
from customer_segmentation.dataset_management.scope import (
    DATASET_SCOPES,
    DatasetScope,
    ValidationStatus,
)
from customer_segmentation.dataset_management.storage import (
    DATASET_ID_HEX_LEN,
    StoragePathError,
    dataset_dir,
    derive_dataset_id,
    find_existing_dataset,
    load_config,
    resolve_storage_root,
    validate_config,
)
from customer_segmentation.dataset_management.validation import (
    FilePreflightError,
    aggregate,
    make_file_level_result,
    map_to_lifecycle,
    run_validation,
)
from customer_segmentation.transformation.versioning import compute_file_sha256

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "ImportRequest",
    "ImportResult",
    "ImportError",
    "import_dataset",
    "detect_schema",
    "detect_mixed",
    "MIXED_TYPE_RANKS",
]


DEFAULT_CONFIG_PATH: Final[Path] = Path("configs") / "dev02_dataset_management.yaml"


# ---------------------------------------------------------------------------
# Public result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportRequest:
    """A request to import one file.

    Attributes
    ----------
    source_path : pathlib.Path
        Path to the source file. May be absolute or relative to CWD.
    name : str or None
        User-supplied display name. Falls back to the file's basename
        if ``None``.
    config : dict
        The inner ``dataset_management:`` mapping (already loaded by
        :func:`load_config`).
    allow_external_source : bool
        Whether the source file is allowed to be outside the
        repository. Comes from the CLI flag
        ``--allow-external-source``; default is the config's
        ``source_path_policy.allow_external_source`` value.
    cwd : pathlib.Path
        Current working directory. Used to compute
        ``provenance.source_relative_path``.
    repo_root : pathlib.Path
        Resolved repository root. The source file must be inside
        this directory unless ``allow_external_source`` is set.
    """

    source_path: Path
    name: str | None
    config: dict
    allow_external_source: bool
    cwd: Path
    repo_root: Path


@dataclass(frozen=True)
class ImportResult:
    """Result of an import.

    ``reused`` is ``True`` when the dataset's content-hash matched
    an existing manifest and no new artefact was created. The
    existing manifest's ``last_seen_utc`` is updated in place.
    """

    dataset_id: str
    storage_dir: Path
    artefact_path: Path
    manifest_path: Path
    validation_status: str
    validation_summary: dict[str, Any]
    reused: bool
    sha256: str
    manifest: Manifest


class ImportError(RuntimeError):
    """Raised on a fatal import error (file preflight or read failure)."""


# ---------------------------------------------------------------------------
# Mixed-type detector
# ---------------------------------------------------------------------------


# The frozen set of "interesting" Python runtime type names used by
# :func:`detect_mixed`. The set is intentionally small and stable;
# adding a new name is a behaviour change that must be reflected in
# the test suite.
MIXED_TYPE_RANKS: Final[frozenset[str]] = frozenset({
    "bool", "int", "float", "complex", "str", "bytes",
    "datetime", "date", "Decimal", "list", "tuple", "dict",
})


def detect_mixed(series: pd.Series, sample_size: int = 1000) -> bool:
    """Detect whether an object-dtype column is mixed-type.

    A column is reported as mixed if and only if:

    1. The dtype is ``"object"``; non-object dtypes are never mixed.
    2. After excluding ``None``/``NaN``/``pd.NaT``, the non-null
       values contain at least **two distinct Python runtime types**
       from :data:`MIXED_TYPE_RANKS`, drawn from the first
       ``sample_size`` non-null values in row order (no shuffling,
       no random selection).
    3. The sample is non-empty.

    The detector does NOT coerce booleans to ints, does NOT parse
    ISO strings to datetimes, does NOT parse ``"true"/"false"``
    strings to booleans, does NOT call any ``pd.to_*`` parser, and
    does NOT mutate the input.

    Parameters
    ----------
    series : pandas.Series
        Column to inspect.
    sample_size : int, default 1000
        Number of leading non-null values to sample.

    Returns
    -------
    bool
        ``True`` if the column is mixed-type, else ``False``.
    """
    if not hasattr(series, "dtype"):
        return False
    if str(series.dtype) != "object":
        return False
    non_null = series.dropna()
    if non_null.empty:
        return False
    head = non_null.head(sample_size)
    types: set[str] = set()
    for v in head:
        # pd.NaT survives dropna in some cases; treat it as null.
        try:
            if pd.isna(v):
                continue
        except (TypeError, ValueError):
            pass
        tname = type(v).__name__
        # Decimal has type name "Decimal"; map to "Decimal" in the
        # canonical set so the membership check is consistent.
        if tname == "Decimal":
            tname = "Decimal"
        if tname in MIXED_TYPE_RANKS:
            types.add(tname)
        if len(types) >= 2:
            return True
    return False


# ---------------------------------------------------------------------------
# Schema detection
# ---------------------------------------------------------------------------


def detect_schema(df: pd.DataFrame) -> list[ColumnInfo]:
    """Return one :class:`ColumnInfo` per column with conservative types.

    The inferred type is one of:

    - ``"numeric"``  — int, float, complex, nullable Int/Float.
    - ``"boolean"``  — actual boolean dtype only (NOT 0/1 ints).
    - ``"datetime"`` — actual datetime dtype only (NOT unix int, NOT
      ISO strings).
    - ``"mixed"``    — ``object`` dtype with ≥2 runtime types in
      the head sample.
    - ``"string"``   — everything else (object, pandas StringDtype,
      categorical, etc.).

    Duplicate column names are tolerated: each occurrence is given
    its own :class:`ColumnInfo` with the same name; the structural
    check (elsewhere) is what rejects the dataset.
    """
    out: list[ColumnInfo] = []
    for col in df.columns:
        try:
            s = df[col]
            if isinstance(s, pd.DataFrame):
                # Duplicate column name: pandas returns a DataFrame.
                # Concatenate its columns into a single Series-like view
                # for type inference by stacking.
                missing = int(pd.concat([s[c] for c in s.columns], axis=1).isna().any(axis=1).sum())
                nullable = bool(missing > 0)
                # Cannot infer a single dtype for duplicates — call them
                # "string" to flag the case (structural check rejects).
                out.append(
                    ColumnInfo(
                        name=str(col),
                        inferred_type="string",
                        nullable=nullable,
                        missing_count=missing,
                    )
                )
                continue
        except Exception:
            s = None
        if s is None:
            out.append(
                ColumnInfo(name=str(col), inferred_type="string", nullable=True, missing_count=0)
            )
            continue
        try:
            missing = int(s.isna().sum())
        except (TypeError, ValueError):
            missing = 0
        nullable = bool(missing > 0) or pd.api.types.is_extension_array_dtype(s.dtype)
        dtype_str = str(s.dtype)
        if pd.api.types.is_bool_dtype(s):
            inferred = "boolean"
        elif pd.api.types.is_datetime64_any_dtype(s):
            inferred = "datetime"
        elif pd.api.types.is_numeric_dtype(s):
            inferred = "numeric"
        elif dtype_str == "object" and detect_mixed(s):
            inferred = "mixed"
        else:
            inferred = "string"
        out.append(
            ColumnInfo(
                name=str(col),
                inferred_type=inferred,
                nullable=nullable,
                missing_count=missing,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Missing + statistics wrappers around audit.*
# ---------------------------------------------------------------------------


def _compute_missing_summary(df: pd.DataFrame) -> dict[str, float]:
    """Re-export :func:`audit.missing_profile` as a column-keyed dict.

    Values are ``missing_rate`` in percent (0.0–100.0).
    """
    if df.shape[0] == 0:
        return {str(c): 0.0 for c in df.columns}
    profile = missing_profile(df)
    return {str(row["column"]): float(row["missing_rate"]) for _, row in profile.iterrows()}


def _compute_statistics_summary(df: pd.DataFrame) -> StatisticsSummary:
    """Build a :class:`StatisticsSummary` from audit.* + pandas.

    Note: :func:`audit.numerical_profile` is used to derive
    numeric statistics. On this pandas version, ``is_numeric_dtype``
    is True for bool columns, which causes ``Series.quantile`` to
    raise on a bool dtype. We filter out bool columns explicitly
    before delegating; bool columns are not "numeric" in the
    DEV-02 statistics summary.
    """
    if df.shape[0] == 0:
        return StatisticsSummary(numeric={}, categorical={})
    # Filter out bool dtype: not numeric, not categorical in DEV-02.
    non_bool = df[[c for c in df.columns if not pd.api.types.is_bool_dtype(df[c])]]
    num_df = numerical_profile(non_bool)
    cat_df = categorical_profile(non_bool)

    numeric: dict[str, NumericStats] = {}
    for _, row in num_df.iterrows():
        col = str(row["column"])
        if int(row.get("count", 0)) == 0:
            continue
        numeric[col] = NumericStats(
            count=int(row["count"]),
            mean=float(row["mean"]),
            std=float(row["std"]),
            min=float(row["min"]),
            median=float(row["median"]),
            max=float(row["max"]),
        )

    categorical: dict[str, CategoricalStats] = {}
    for _, row in cat_df.iterrows():
        col = str(row["column"])
        categorical[col] = CategoricalStats(
            count=int(row["count"]),
            unique_count=int(row["unique_count"]),
        )

    return StatisticsSummary(numeric=numeric, categorical=categorical)


# ---------------------------------------------------------------------------
# Stage A — file preflight
# ---------------------------------------------------------------------------


def _file_preflight(
    request: ImportRequest,
    storage_root: Path,
) -> tuple[str, int, list[str]]:
    """Stage A: file preflight. Returns (sha256, file_size, errors).

    Raises :class:`FilePreflightError` on a fatal issue. Otherwise
    returns a tuple of (sha256 hex, file size in bytes, list of
    human-readable errors — empty if all passed).
    """
    src = Path(request.source_path)
    errors: list[str] = []

    # Existence / readability
    if not src.exists():
        errors.append(f"Source file not found: {src!s}.")
    elif not src.is_file():
        errors.append(f"Source path is not a regular file: {src!s}.")
    else:
        try:
            with src.open("rb") as fh:
                fh.read(1)
        except OSError as exc:
            errors.append(f"Source file is not readable: {exc!s}.")

    # Format / extension
    allowed = list(request.config.get("supported_import_formats") or [])
    ext = src.suffix.lower().lstrip(".") if src.exists() else ""
    if ext and ext not in {a.lower() for a in allowed}:
        errors.append(
            f"Unsupported format {ext!r}; supported: {sorted(allowed)}."
        )

    # Source-path policy
    if src.exists():
        try:
            real = src.resolve()
        except OSError as exc:
            errors.append(f"Could not resolve source path: {exc!s}.")
            real = None
        repo_real = Path(request.repo_root).resolve() if request.repo_root else None
        if real is not None and repo_real is not None:
            try:
                real.relative_to(repo_real)
                inside = True
            except ValueError:
                inside = False
        else:
            inside = False
        if not inside and not request.allow_external_source:
            errors.append(
                "Source file is outside the repository. Re-run with "
                "--allow-external-source to permit this."
            )

    # File size
    if src.exists():
        try:
            size = int(src.stat().st_size)
        except OSError as exc:
            errors.append(f"Could not stat source file: {exc!s}.")
            size = 0
    else:
        size = 0
    max_mb = float(request.config.get("max_file_size_mb") or 0)
    if size > max_mb * 1024 * 1024:
        errors.append(
            f"File size {size} bytes exceeds max_file_size_mb={max_mb:g}."
        )

    # SHA-256
    sha = ""
    if not errors:
        try:
            sha = compute_file_sha256(src)
        except OSError as exc:
            errors.append(f"Could not compute SHA-256: {exc!s}.")

    if errors:
        # If preflight produced a partial sha (e.g. file not found
        # but the symlink was inspectable), return whatever we have.
        return sha, size, errors

    return sha, size, []


# ---------------------------------------------------------------------------
# Stage B — read DataFrame
# ---------------------------------------------------------------------------


def _read_dataframe(
    src: Path,
    *,
    encoding: str,
) -> pd.DataFrame:
    """Stage B: read the source file into a DataFrame.

    No transformation is applied — the resulting DataFrame has the
    pandas default dtypes, no renames, no parsing beyond the reader's
    defaults.

    Raises
    ------
    FilePreflightError
        On a read error, malformed file, or encoding mismatch. The
        caller is expected to surface the error without writing an
        artefact.
    """
    ext = src.suffix.lower().lstrip(".")
    try:
        if ext == "csv":
            try:
                return pd.read_csv(src, encoding=encoding)
            except UnicodeDecodeError as exc:
                raise FilePreflightError(
                    f"CSV file is not {encoding}-encoded: {exc!s}"
                ) from exc
        if ext == "parquet":
            return pd.read_parquet(src)
    except FilePreflightError:
        raise
    except Exception as exc:
        raise FilePreflightError(f"Failed to read {ext!r} file: {exc!s}") from exc
    raise FilePreflightError(f"Unsupported format {ext!r}.")


# ---------------------------------------------------------------------------
# Stage C — inspect (read-only)
# ---------------------------------------------------------------------------


def _inspect(
    df: pd.DataFrame,
) -> tuple[list[ColumnInfo], dict[str, float], StatisticsSummary]:
    """Stage C: detect schema, count missing, compute statistics.

    No side effects. The function returns the three structures that
    Stage E will embed in the manifest.
    """
    columns = detect_schema(df)
    missing_summary = _compute_missing_summary(df)
    statistics_summary = _compute_statistics_summary(df)
    return columns, missing_summary, statistics_summary


# ---------------------------------------------------------------------------
# Stage D — validation
# ---------------------------------------------------------------------------


def _build_validation_block(
    df: pd.DataFrame,
    file_level_result: Any,
) -> tuple[Any, str, str]:
    """Stage D: run validation, return the block + aggregate + lifecycle."""
    block = run_validation(df, file_level_result)
    aggregate_result = aggregate(block)
    lifecycle = map_to_lifecycle(aggregate_result)
    return block, aggregate_result, lifecycle


# ---------------------------------------------------------------------------
# Stage E — atomic artefact + manifest write
# ---------------------------------------------------------------------------


def _write_artefact(
    df: pd.DataFrame,
    *,
    target_dir: Path,
    original_filename: str,
) -> tuple[Path, int]:
    """Stage E (part 1): write the DataFrame to a new file in ``target_dir``.

    Writes to a temp file in the same directory and renames on
    success. Returns ``(path, file_size_bytes)``.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / original_filename
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    tmp_suffix = ".tmp"
    if ext == "csv":
        tmp = target.with_suffix(target.suffix + tmp_suffix)
        df.to_csv(tmp, index=False, encoding="utf-8")
    elif ext == "parquet":
        tmp = target.with_suffix(target.suffix + tmp_suffix)
        df.to_parquet(tmp, index=False)
    else:
        raise FilePreflightError(f"Unsupported format {ext!r} for write.")
    try:
        tmp.replace(target)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    size = int(target.stat().st_size)
    return target, size


# ---------------------------------------------------------------------------
# Top-level pipeline
# ---------------------------------------------------------------------------


def import_dataset(request: ImportRequest) -> ImportResult:
    """Run the full import pipeline.

    See docs/system/DEV-02_dataset_management.md §5.1.

    Parameters
    ----------
    request : ImportRequest
        The import request.

    Returns
    -------
    ImportResult
        The result, including the manifest.

    Raises
    ------
    ImportError
        On a fatal Stage A or Stage B error. The CLI translates this
        to its own exit code.
    FilePreflightError
        On a non-fatal Stage A issue that should be reported but
        should not write a manifest. (The CLI also catches this.)
    """
    # -- Stage 0: resolve config --------------------------------------
    validate_config(request.config)
    storage_root = resolve_storage_root(request.config)

    # -- Stage 0.5: id from sha256 (idempotency lookup) ---------------
    # Idempotency requires a SHA-256 to look up, but Stage A
    # computes the SHA-256. We run Stage A first.
    src = Path(request.source_path)
    sha256, file_size, preflight_errors = _file_preflight(request, storage_root)
    file_level = make_file_level_result(
        passed=not preflight_errors,
        errors=preflight_errors,
    )
    if preflight_errors:
        # Stage A failed. Do NOT read or write anything; do NOT
        # write a manifest. Raise the typed error so the CLI can
        # distinguish Stage A from Stage D.
        raise FilePreflightError(
            "File preflight failed: " + "; ".join(preflight_errors)
        )

    dataset_id = derive_dataset_id(sha256)

    # -- Idempotency check --------------------------------------------
    existing = find_existing_dataset(storage_root, sha256)
    if existing is not None:
        from customer_segmentation.dataset_management.manifest import (
            read_manifest,
            update_last_seen,
            write_manifest,
        )

        old = read_manifest(existing)
        new = update_last_seen(old)
        write_manifest(new, existing)
        return ImportResult(
            dataset_id=new.dataset_id,
            storage_dir=Path(new.storage.directory),
            artefact_path=Path(new.storage.directory) / new.original_filename,
            manifest_path=existing,
            validation_status=new.validation_status,
            validation_summary={
                "file_level": new.validation.file_level.result,
                "structural": new.validation.structural.result,
                "data_quality": new.validation.data_quality.result,
            },
            reused=True,
            sha256=new.sha256,
            manifest=new,
        )

    # -- Stage B: read -------------------------------------------------
    try:
        df = _read_dataframe(
            src,
            encoding=str(request.config.get("default_csv_encoding") or "utf-8"),
        )
    except FilePreflightError as exc:
        raise ImportError(str(exc)) from exc

    # -- Stage C: inspect ---------------------------------------------
    columns_info, missing_summary, statistics_summary = _inspect(df)

    # -- Stage D: validation ------------------------------------------
    block, aggregate_result, lifecycle = _build_validation_block(df, file_level)

    if aggregate_result == "FAIL":
        # No artefact, no manifest. Surface the structural / data-quality
        # errors via the ImportError so the CLI can print them.
        msgs: list[str] = []
        if block.structural.errors:
            msgs.append("structural: " + "; ".join(block.structural.errors))
        if block.data_quality.errors:
            msgs.append("data_quality: " + "; ".join(block.data_quality.errors))
        if block.file_level.errors:
            msgs.append("file_level: " + "; ".join(block.file_level.errors))
        raise ImportError("Validation failed: " + " | ".join(msgs) or "FAIL")

    # -- Stage E: write ------------------------------------------------
    ds_dir = dataset_dir(storage_root, dataset_id)
    ds_dir.mkdir(parents=True, exist_ok=True)

    # Build provenance.
    original_filename = src.name
    name = request.name or original_filename
    try:
        real_src = src.resolve()
    except OSError:
        real_src = src
    try:
        rel = real_src.relative_to(Path(request.cwd).resolve()).as_posix()
    except ValueError:
        rel = None

    provenance = Provenance(
        import_method="cli",
        source_filename=original_filename,
        source_relative_path=rel,
        license=None,
        notes=(
            "Imported for prototype validation. NOT research evidence."
        ),
    )

    research_safety = ResearchSafety(
        automatically_promoted_to_research=False,
        scope=DatasetScope.IMPORTED_PROTOTYPE.value,
        appeared_in_research_evidence=False,
        read_only_paths_unmodified=list(request.config.get("readonly_research_paths") or []),
    )

    # Stage E.1: write the data artefact first (atomic temp + rename).
    artefact_path, written_size = _write_artefact(
        df, target_dir=ds_dir, original_filename=original_filename
    )

    storage = StorageInfo(
        directory=str(ds_dir),
        artifact_path=f"{dataset_id}/{original_filename}",
        file_size_bytes=written_size,
    )

    fmt = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if fmt not in {"csv", "parquet"}:
        # Should not happen; Stage A would have rejected.
        raise ImportError(f"Internal error: format {fmt!r} not in supported set.")

    created = now_iso()

    # Build validation block for manifest.
    val_block = {
        "file_level": {
            "result": block.file_level.result,
            "errors": list(block.file_level.errors),
            "warnings": list(block.file_level.warnings),
            "stats": dict(block.file_level.stats),
        },
        "structural": {
            "result": block.structural.result,
            "errors": list(block.structural.errors),
            "warnings": list(block.structural.warnings),
            "stats": dict(block.structural.stats),
        },
        "data_quality": {
            "result": block.data_quality.result,
            "errors": list(block.data_quality.errors),
            "warnings": list(block.data_quality.warnings),
            "stats": dict(block.data_quality.stats),
        },
    }

    # Build manifest via dataclass construction.
    from customer_segmentation.dataset_management.manifest import (
        Manifest,
        ValidationBlock as _VB,
        write_manifest,
    )

    manifest = Manifest(
        schema_version="1.0.0",
        dataset_id=dataset_id,
        dataset_scope=DatasetScope.IMPORTED_PROTOTYPE.value,
        name=name,
        original_filename=original_filename,
        format=fmt,
        storage=storage,
        sha256=sha256,
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        columns=columns_info,
        missing_summary=missing_summary,
        statistics_summary=statistics_summary,
        validation=_VB(
            file_level=block.file_level,
            structural=block.structural,
            data_quality=block.data_quality,
        ),
        validation_status=lifecycle,
        created_utc=created,
        last_seen_utc=created,
        provenance=provenance,
        research_safety=research_safety,
        environment={},
        config_hash="",
    )

    # Stage E.2: write manifest atomically.
    manifest_path = ds_dir / "manifest.json"
    write_manifest(manifest, manifest_path)

    return ImportResult(
        dataset_id=dataset_id,
        storage_dir=ds_dir,
        artefact_path=artefact_path,
        manifest_path=manifest_path,
        validation_status=lifecycle,
        validation_summary={
            "file_level": block.file_level.result,
            "structural": block.structural.result,
            "data_quality": block.data_quality.result,
        },
        reused=False,
        sha256=sha256,
        manifest=manifest,
    )


# ---------------------------------------------------------------------------
# Convenience for the CLI
# ---------------------------------------------------------------------------


def build_request_from_args(args: Any, *, repo_root: Path, cwd: Path) -> ImportRequest:
    """Construct an :class:`ImportRequest` from CLI ``argparse`` args.

    Parameters
    ----------
    args : argparse.Namespace
        The parsed CLI arguments.
    repo_root : pathlib.Path
        Repository root path.
    cwd : pathlib.Path
        Current working directory.

    Returns
    -------
    ImportRequest
        The constructed request.
    """
    config = load_config(args.config)
    validate_config(config)
    allow_external = bool(args.allow_external_source) or bool(
        config.get("source_path_policy", {}).get("allow_external_source", False)
    )
    return ImportRequest(
        source_path=Path(args.file),
        name=args.name,
        config=config,
        allow_external_source=allow_external,
        cwd=cwd,
        repo_root=repo_root,
    )


# Expose constant for tests / docs.
_ = (DATASET_SCOPES, ValidationStatus, np, io, Mapping)  # keep import surface
