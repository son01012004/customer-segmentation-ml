"""Manifest dataclass, JSON I/O, and stable/runtime field classification.

A :class:`Manifest` is the on-disk sidecar of an imported dataset
(``<storage_root>/<dataset_id>/manifest.json``). It records the
dataset's content-hash, schema, missing summary, statistics, and
provenance in a portable, content-keyed format.

The manifest is split into two field groups (per docs/system/DEV-02
§8.1):

- **Stable** — equal across re-imports of the same content.
- **Runtime** — may differ across re-imports (e.g. ``last_seen_utc``,
  ``environment.python``, ``config_hash``).

Tests for idempotency assert equality of stable fields across two
imports of the same content. They do not assert byte-for-byte
JSON equality.

Hard rules
----------
- A manifest is **only** ever written by
  :func:`customer_segmentation.dataset_management.importer.import_dataset`
  after a successful import. The CLI / driver never writes a manifest
  for a failed validation.
- The manifest never stores the **absolute** source path. It stores
  the filename (always) and the path relative to the CWD when the
  source is inside the repository, or ``None`` otherwise.
- The manifest's ``research_safety`` block is **always**:
  - ``automatically_promoted_to_research = false``
  - ``scope = "IMPORTED_PROTOTYPE"``
  - ``appeared_in_research_evidence = false``
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

__all__ = [
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
    "manifest_to_dict",
    "now_iso",
]


MANIFEST_SCHEMA_VERSION: Final[str] = "1.0.0"


class ManifestError(ValueError):
    """Raised on manifest construction / I/O failures."""


# ---------------------------------------------------------------------------
# Sub-blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StorageInfo:
    """On-disk location of the imported artefact."""

    directory: str
    artifact_path: str
    file_size_bytes: int


@dataclass(frozen=True)
class ColumnInfo:
    """One column in the imported DataFrame.

    ``inferred_type`` is one of: ``"numeric"``, ``"string"``,
    ``"boolean"``, ``"datetime"``, ``"mixed"``.
    """

    name: str
    inferred_type: str
    nullable: bool
    missing_count: int


@dataclass(frozen=True)
class NumericStats:
    """Numeric summary for one column."""

    count: int
    mean: float
    std: float
    min: float
    median: float
    max: float


@dataclass(frozen=True)
class CategoricalStats:
    """Categorical summary for one column."""

    count: int
    unique_count: int


@dataclass(frozen=True)
class StatisticsSummary:
    """Aggregate of numeric + categorical summaries keyed by column."""

    numeric: dict[str, NumericStats]
    categorical: dict[str, CategoricalStats]


@dataclass(frozen=True)
class ValidationCategory:
    """One category of validation result."""

    result: str  # "PASS" | "WARNING" | "FAIL"
    errors: list[str]
    warnings: list[str]
    stats: dict[str, int]


@dataclass(frozen=True)
class ValidationBlock:
    """Three-category validation block.

    ``file_level`` only has ``PASS``/``FAIL`` (no ``WARNING``). The
    ``structural`` and ``data_quality`` categories may also be
    ``WARNING``.
    """

    file_level: ValidationCategory
    structural: ValidationCategory
    data_quality: ValidationCategory


@dataclass(frozen=True)
class Provenance:
    """Portable provenance of the imported dataset.

    ``source_relative_path`` is the path relative to the CWD when
    the source is inside the repository, otherwise ``None``.
    ``source_filename`` is always the basename of the source file.
    """

    import_method: str
    source_filename: str
    source_relative_path: str | None
    license: str | None
    notes: str


@dataclass(frozen=True)
class ResearchSafety:
    """Research-safety markers for the dataset.

    All three markers are **always** set to the values shown here
    (an imported prototype dataset is never a research artefact).
    """

    automatically_promoted_to_research: bool
    scope: str
    appeared_in_research_evidence: bool
    read_only_paths_unmodified: list[str]


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Manifest:
    """On-disk manifest of an imported prototype dataset."""

    schema_version: str
    dataset_id: str
    dataset_scope: str
    name: str
    original_filename: str
    format: str
    storage: StorageInfo
    sha256: str
    row_count: int
    column_count: int
    columns: list[ColumnInfo]
    missing_summary: dict[str, float]
    statistics_summary: StatisticsSummary
    validation: ValidationBlock
    validation_status: str
    created_utc: str
    last_seen_utc: str
    provenance: Provenance
    research_safety: ResearchSafety
    environment: dict[str, str] = field(default_factory=dict)
    config_hash: str = ""


# ---------------------------------------------------------------------------
# Stable / runtime classification
# ---------------------------------------------------------------------------


_STABLE_FIELDS: Final[frozenset[str]] = frozenset({
    "schema_version",
    "dataset_id",
    "dataset_scope",
    "name",
    "original_filename",
    "format",
    "storage",
    "sha256",
    "row_count",
    "column_count",
    "columns",
    "missing_summary",
    "statistics_summary",
    "validation",
    "validation_status",
    "provenance",
    "research_safety",
})

_RUNTIME_FIELDS: Final[frozenset[str]] = frozenset({
    "created_utc",
    "last_seen_utc",
    "environment",
    "config_hash",
})


def stable_field_names() -> frozenset[str]:
    """Return the set of field names that are stable across re-imports."""
    return _STABLE_FIELDS


def runtime_field_names() -> frozenset[str]:
    """Return the set of field names that may differ across re-imports."""
    return _RUNTIME_FIELDS


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def manifest_to_dict(m: Manifest) -> dict[str, Any]:
    """Convert a :class:`Manifest` to a JSON-serialisable dict.

    Recursively converts nested dataclasses to dicts and
    ``frozenset``/``set`` to ``list``.
    """

    def _to_jsonable(value: Any) -> Any:
        if isinstance(value, Manifest):
            return _to_jsonable(asdict(value))
        if isinstance(value, list):
            return [_to_jsonable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        # Dataclass instances (StorageInfo, ColumnInfo, NumericStats, etc.).
        if hasattr(value, "__dataclass_fields__"):
            return _to_jsonable(asdict(value))
        raise TypeError(f"Cannot serialise value of type {type(value).__name__}.")

    return _to_jsonable(m)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def write_manifest(manifest: Manifest, path: Path) -> None:
    """Atomically write a manifest to ``path``.

    Writes to a temp file in the same directory and renames on
    success. On any exception the temp file is removed.

    Parameters
    ----------
    manifest : Manifest
        The manifest to write.
    path : pathlib.Path
        Destination path. The parent directory must already exist.
    """
    path = Path(path)
    if not path.parent.exists():
        raise ManifestError(
            f"Cannot write manifest to {path!s}: parent directory does not exist."
        )
    payload = manifest_to_dict(manifest)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        tmp.replace(path)
    except Exception:
        # Best-effort cleanup of partial temp.
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def read_manifest(path: Path) -> Manifest:
    """Read and reconstruct a :class:`Manifest` from a JSON file.

    Parameters
    ----------
    path : pathlib.Path
        Path to ``manifest.json``.

    Returns
    -------
    Manifest
        Reconstructed manifest.

    Raises
    ------
    ManifestError
        If the file is missing, the JSON is malformed, or the
        required fields are absent.
    """
    path = Path(path)
    if not path.exists():
        raise ManifestError(f"Manifest file not found: {path!s}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Failed to parse manifest JSON at {path!s}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(
            f"Manifest at {path!s} must be a JSON object; got {type(data).__name__}."
        )
    return _dict_to_manifest(data)


def _dict_to_manifest(data: Mapping[str, Any]) -> Manifest:
    """Build a :class:`Manifest` from a dict; raises :class:`ManifestError`."""
    required = (
        "schema_version", "dataset_id", "dataset_scope", "name", "original_filename",
        "format", "storage", "sha256", "row_count", "column_count", "columns",
        "missing_summary", "statistics_summary", "validation", "validation_status",
        "created_utc", "last_seen_utc", "provenance", "research_safety",
    )
    for key in required:
        if key not in data:
            raise ManifestError(f"Manifest is missing required field: {key!r}.")

    storage_raw = data["storage"]
    storage = StorageInfo(
        directory=str(storage_raw["directory"]),
        artifact_path=str(storage_raw["artifact_path"]),
        file_size_bytes=int(storage_raw["file_size_bytes"]),
    )

    columns = [
        ColumnInfo(
            name=str(c["name"]),
            inferred_type=str(c["inferred_type"]),
            nullable=bool(c["nullable"]),
            missing_count=int(c["missing_count"]),
        )
        for c in data["columns"]
    ]

    stats_raw = data["statistics_summary"]
    numeric = {
        str(col): NumericStats(
            count=int(s["count"]),
            mean=float(s["mean"]),
            std=float(s["std"]),
            min=float(s["min"]),
            median=float(s["median"]),
            max=float(s["max"]),
        )
        for col, s in stats_raw.get("numeric", {}).items()
    }
    categorical = {
        str(col): CategoricalStats(
            count=int(s["count"]),
            unique_count=int(s["unique_count"]),
        )
        for col, s in stats_raw.get("categorical", {}).items()
    }
    statistics_summary = StatisticsSummary(numeric=numeric, categorical=categorical)

    val_raw = data["validation"]

    def _category(d: Mapping[str, Any]) -> ValidationCategory:
        return ValidationCategory(
            result=str(d["result"]),
            errors=[str(e) for e in d.get("errors", [])],
            warnings=[str(w) for w in d.get("warnings", [])],
            stats={str(k): int(v) for k, v in d.get("stats", {}).items()},
        )

    validation = ValidationBlock(
        file_level=_category(val_raw["file_level"]),
        structural=_category(val_raw["structural"]),
        data_quality=_category(val_raw["data_quality"]),
    )

    prov_raw = data["provenance"]
    provenance = Provenance(
        import_method=str(prov_raw["import_method"]),
        source_filename=str(prov_raw["source_filename"]),
        source_relative_path=(
            str(prov_raw["source_relative_path"])
            if prov_raw.get("source_relative_path") is not None
            else None
        ),
        license=(
            str(prov_raw["license"]) if prov_raw.get("license") is not None else None
        ),
        notes=str(prov_raw["notes"]),
    )

    rs_raw = data["research_safety"]
    research_safety = ResearchSafety(
        automatically_promoted_to_research=bool(rs_raw["automatically_promoted_to_research"]),
        scope=str(rs_raw["scope"]),
        appeared_in_research_evidence=bool(rs_raw["appeared_in_research_evidence"]),
        read_only_paths_unmodified=[
            str(p) for p in rs_raw.get("read_only_paths_unmodified", [])
        ],
    )

    return Manifest(
        schema_version=str(data["schema_version"]),
        dataset_id=str(data["dataset_id"]),
        dataset_scope=str(data["dataset_scope"]),
        name=str(data["name"]),
        original_filename=str(data["original_filename"]),
        format=str(data["format"]),
        storage=storage,
        sha256=str(data["sha256"]),
        row_count=int(data["row_count"]),
        column_count=int(data["column_count"]),
        columns=columns,
        missing_summary={str(k): float(v) for k, v in data["missing_summary"].items()},
        statistics_summary=statistics_summary,
        validation=validation,
        validation_status=str(data["validation_status"]),
        created_utc=str(data["created_utc"]),
        last_seen_utc=str(data["last_seen_utc"]),
        provenance=provenance,
        research_safety=research_safety,
        environment={str(k): str(v) for k, v in data.get("environment", {}).items()},
        config_hash=str(data.get("config_hash", "")),
    )


# ---------------------------------------------------------------------------
# Time / idempotency helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a "Z" suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def update_last_seen(manifest: Manifest, *, now: str | None = None) -> Manifest:
    """Return a new :class:`Manifest` with ``last_seen_utc`` set to ``now``."""
    from dataclasses import replace

    return replace(manifest, last_seen_utc=now if now is not None else now_iso())
