"""Storage and path-resolution helpers for DEV-09 End-to-End Prototype.

Responsibilities
----------------
1. Resolve the DEV-02 storage root (shared with DEV-02..08).
2. Compute the per-run end-to-end directory
   (``<seg_dir>/end_to_end/<e2e_run_id>/``).
3. Derive the content-addressed ``e2e_run_id`` from the canonical
   payload (input ids + config hashes + seed + algorithm).
4. Validate id formats and path containment.
5. Enumerate existing end-to-end runs for a dataset (read-only).

Hard rules
----------
- The storage root is loaded from
  ``configs/dev02_dataset_management.yaml`` (shared with DEV-02..08).
- ``e2e_run_id`` is always ``"e2e_" + first 24 hex chars`` of
  SHA-256 of the canonical payload. Fields:
    ``(dataset_id, dataset_sha256, preprocessed_id, clustering_id,
       segmentation_id, algorithm, seed, dev09_schema_version,
       dev04_config_sha256, dev06_config_sha256)``.
  A schema bump invalidates old ``e2e_run_id``s.
- All computed paths are validated to remain inside the resolved
  storage root (via :func:`Path.resolve()` + :func:`Path.relative_to`).
- No filesystem mutation outside the resolved run_dir.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.end_to_end.scope import (
    E2E_ID_HEX_LEN,
    E2E_ID_PREFIX,
    END_TO_END_SCHEMA_VERSION,
)

# Single canonical exception definition. This module previously defined
# a SECOND ``Dev09StoragePathError`` class, which produced a class-
# identity mismatch with :mod:`scope`'s class. The CLI's
# ``except Dev09StoragePathError`` (imported from
# :mod:`customer_segmentation.prototype.end_to_end.exceptions`,
# which re-exports :mod:`scope`) then failed to catch the storage
# variant; the process crashed with an uncaught exception instead of
# returning the documented exit code ``4``. See
# ``docs/system/DEV-09_completion_report.md`` §19.
from customer_segmentation.prototype.end_to_end.scope import (
    Dev09StoragePathError as _CanonicalDev09StoragePathError,
)

__all__ = [
    "E2E_RUN_ID_REGEX",
    "CANONICAL_PAYLOAD_KEYS",
    "compute_config_sha256",
    "derive_e2e_run_id",
    "end_to_end_run_dir",
    "resolve_storage_root",
    "resolve_e2e_storage_root",
    "list_e2e_runs",
    "Dev09StoragePathError",
    "E2ERunRecord",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 24-hex-char content-addressed identifier under the END_TO_END storage.
E2E_RUN_ID_REGEX = re.compile(r"^e2e_[0-9a-f]{24}$")

# Canonical payload key order for ``derive_e2e_run_id``.
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "schema_version",
    "dataset_id",
    "dataset_sha256",
    "preprocessed_id",
    "clustering_id",
    "segmentation_id",
    "algorithm",
    "seed",
    "dev04_config_sha256",
    "dev06_config_sha256",
)


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

# Re-export the canonical class from :mod:`scope` under the public name.
# Any old call site that referenced the (now-removed) local definition
# resolves to the canonical class via this alias.
Dev09StoragePathError = _CanonicalDev09StoragePathError


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------


def _canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _validate_payload(payload: dict[str, Any]) -> None:
    missing = [k for k in CANONICAL_PAYLOAD_KEYS if k not in payload]
    if missing:
        raise Dev09StoragePathError(f"Canonical payload missing required keys: {missing}.")


def compute_config_sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a config YAML's text content."""
    if not isinstance(text, str):
        raise Dev09StoragePathError(f"text must be a str; got {type(text).__name__}.")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_e2e_run_id(
    *,
    dataset_id: str,
    dataset_sha256: str,
    preprocessed_id: str | None,
    clustering_id: str | None,
    segmentation_id: str | None,
    algorithm: str,
    seed: int | None,
    dev04_config_sha256: str,
    dev06_config_sha256: str,
    schema_version: str = END_TO_END_SCHEMA_VERSION,
) -> str:
    """Derive the content-addressed end-to-end run id.

    Returns ``"e2e_" + first 24 hex chars`` of SHA-256 of the canonical
    JSON payload.

    All string fields must be non-empty. ``None`` fields are encoded
    as the JSON literal ``null``. ``seed`` is encoded as ``null`` when
    ``None``.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev09StoragePathError("dataset_id must be a non-empty str.")
    if not isinstance(dataset_sha256, str) or not dataset_sha256:
        raise Dev09StoragePathError("dataset_sha256 must be a non-empty str.")
    if preprocessed_id is not None and (
        not isinstance(preprocessed_id, str) or not preprocessed_id
    ):
        raise Dev09StoragePathError("preprocessed_id must be None or a non-empty str.")
    if clustering_id is not None and (not isinstance(clustering_id, str) or not clustering_id):
        raise Dev09StoragePathError("clustering_id must be None or a non-empty str.")
    if segmentation_id is not None and (
        not isinstance(segmentation_id, str) or not segmentation_id
    ):
        raise Dev09StoragePathError("segmentation_id must be None or a non-empty str.")
    if not isinstance(algorithm, str) or not algorithm:
        raise Dev09StoragePathError("algorithm must be a non-empty str.")
    if not isinstance(dev04_config_sha256, str) or not dev04_config_sha256:
        raise Dev09StoragePathError("dev04_config_sha256 must be a non-empty str.")
    if not isinstance(dev06_config_sha256, str) or not dev06_config_sha256:
        raise Dev09StoragePathError("dev06_config_sha256 must be a non-empty str.")

    payload = {
        "schema_version": str(schema_version),
        "dataset_id": str(dataset_id),
        "dataset_sha256": str(dataset_sha256),
        "preprocessed_id": preprocessed_id,
        "clustering_id": clustering_id,
        "segmentation_id": segmentation_id,
        "algorithm": str(algorithm),
        "seed": seed,
        "dev04_config_sha256": str(dev04_config_sha256),
        "dev06_config_sha256": str(dev06_config_sha256),
    }
    _validate_payload(payload)
    digest = hashlib.sha256(_canonical_payload_bytes(payload)).hexdigest()
    return E2E_ID_PREFIX + digest[:E2E_ID_HEX_LEN]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_storage_root(
    config_path: Path | str | None = None,
) -> Path:
    """Return DEV-09's storage root (shared with DEV-02..08).

    Loaded from ``configs/dev02_dataset_management.yaml`` via the
    DEV-02 storage module. ``config_path`` may override the canonical
    config when a caller imported via ``--config <custom>``.
    """
    from customer_segmentation.dataset_management.storage import (
        load_config as load_dev02_config,
    )
    from customer_segmentation.dataset_management.storage import (
        resolve_storage_root as resolve_dev02_storage_root,
    )
    from customer_segmentation.prototype.preprocessing.storage import (
        DEFAULT_DEV02_CONFIG_PATH,
    )

    p = Path(config_path) if config_path else DEFAULT_DEV02_CONFIG_PATH
    cfg = load_dev02_config(p)
    return resolve_dev02_storage_root(cfg)


def resolve_e2e_storage_root(storage_root: Path, *, dataset_id: str) -> Path:
    """Return the per-dataset end-to-end container directory.

    Layout::

            <storage_root>/<dataset_id>/end_to_end/

    The ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    (per ``configs/dev02_dataset_management.yaml``); the dataset id is
    appended without an extra ``"datasets"`` literal. See the regression
    test in ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``
    for context.

    The directory is the canonical listing scope for all e2e runs of
    one dataset. The function does NOT create it.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev09StoragePathError("dataset_id must be a non-empty str.")
    root = Path(storage_root).resolve()
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); append ``dataset_id``
    # directly (no extra ``"datasets"`` literal). Mirrors the canonical
    # layout produced by DEV-02..08.
    candidate = (root / dataset_id / "end_to_end").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise Dev09StoragePathError(
            f"Computed e2e storage root {candidate!s} is not inside " f"storage root {root!s}."
        ) from exc
    return candidate


def end_to_end_run_dir(storage_root: Path, *, dataset_id: str, e2e_run_id: str) -> Path:
    """Return the per-run directory for one end-to-end run.

    Layout::

            <storage_root>/datasets/<dataset_id>/end_to_end/<e2e_run_id>/

    The directory is NOT created by this function.
    """
    if not E2E_RUN_ID_REGEX.match(e2e_run_id):
        raise Dev09StoragePathError(
            f"e2e_run_id {e2e_run_id!r} does not match required format " f"^e2e_[0-9a-f]{{24}}$."
        )
    base = resolve_e2e_storage_root(storage_root, dataset_id=dataset_id)
    candidate = (base / e2e_run_id).resolve()
    try:
        candidate.relative_to(Path(storage_root).resolve())
    except ValueError as exc:
        raise Dev09StoragePathError(
            f"Computed e2e run dir {candidate!s} is not inside "
            f"storage root {Path(storage_root).resolve()!s}."
        ) from exc
    return candidate


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E2ERunRecord:
    """Lightweight enumeration record for one existing e2e run."""

    e2e_run_id: str
    dataset_id: str
    overall_status: str
    lifecycle: str
    created_utc: str
    run_dir: str
    summary_path: str


def list_e2e_runs(storage_root: Path, *, dataset_id: str | None = None) -> list[E2ERunRecord]:
    """List existing e2e runs under ``<storage_root>/datasets/.../end_to_end/``.

    If ``dataset_id`` is provided, restrict to that dataset's
    ``end_to_end/`` directory. Returns an empty list when the directory
    does not exist.

    The function is read-only and never mutates the filesystem.
    """
    root = Path(storage_root).resolve()
    if dataset_id is not None:
        candidates = [resolve_e2e_storage_root(root, dataset_id=dataset_id)]
    else:
        # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
        # (per ``configs/dev02_dataset_management.yaml``); dataset
        # directories are immediate children (no extra ``"datasets"``
        # literal). Mirrors the canonical layout produced by DEV-02..08.
        candidates = [d / "end_to_end" for d in root.glob("*/") if d.is_dir()]
    records: list[E2ERunRecord] = []
    for c in candidates:
        if not c.exists():
            continue
        for run_dir in sorted(c.iterdir()):
            if not run_dir.is_dir():
                continue
            if not E2E_RUN_ID_REGEX.match(run_dir.name):
                continue
            summary_path = run_dir / "e2e_run.json"
            if not summary_path.exists():
                # Skeleton dir without summary — still surface a record.
                records.append(
                    E2ERunRecord(
                        e2e_run_id=run_dir.name,
                        dataset_id=dataset_id or "",
                        overall_status="UNKNOWN",
                        lifecycle="UNKNOWN",
                        created_utc="",
                        run_dir=str(run_dir),
                        summary_path=str(summary_path),
                    )
                )
                continue
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            records.append(
                E2ERunRecord(
                    e2e_run_id=str(payload.get("e2e_run_id", run_dir.name)),
                    dataset_id=str(payload.get("dataset_id", "")),
                    overall_status=str(payload.get("overall_status", "UNKNOWN")),
                    lifecycle=str(payload.get("lifecycle", "UNKNOWN")),
                    created_utc=str(payload.get("created_utc", "")),
                    run_dir=str(run_dir),
                    summary_path=str(summary_path),
                )
            )
    return records
