"""List / detail helpers for DEV-02 Dataset Management.

This module scans the storage root for manifests and exposes a
typed, filterable summary list plus a per-dataset detail loader.

The scan is filesystem-only — no in-memory index, no caching. The
list is rebuilt on each call. For the prototype scale (a handful of
imported datasets), this is fine.

Hard rules
----------
- The scanner only reads files inside the configured storage root.
  It MUST NOT recurse into other directories.
- Manifests that fail to parse (corrupted JSON, missing required
  fields) are silently skipped — they do not break the listing. The
  caller can re-import the same content to overwrite a corrupted
  manifest (same content-hash → same dataset_id → same directory).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from customer_segmentation.dataset_management.manifest import (
    Manifest,
    ManifestError,
    read_manifest,
)

__all__ = [
    "DatasetSummary",
    "DatasetNotFound",
    "list_datasets",
    "get_dataset",
]


@dataclass(frozen=True)
class DatasetSummary:
    """One row in :func:`list_datasets`'s output."""

    dataset_id: str
    name: str
    scope: str
    validation_status: str
    sha256: str
    created_utc: str
    last_seen_utc: str
    row_count: int
    column_count: int
    artefact_path: Path


class DatasetNotFound(LookupError):
    """Raised when :func:`get_dataset` cannot find a manifest."""


def list_datasets(
    storage_root: Path,
    *,
    scope: str | None = None,
    status: str | None = None,
    name_substring: str | None = None,
) -> list[DatasetSummary]:
    """Enumerate manifests under ``storage_root``.

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root.
    scope : str, optional
        If given, only manifests whose ``dataset_scope`` matches are
        returned.
    status : str, optional
        If given, only manifests whose ``validation_status`` matches
        are returned.
    name_substring : str, optional
        If given, only manifests whose ``name`` contains this
        substring (case-sensitive) are returned.

    Returns
    -------
    list[DatasetSummary]
        Sorted by ``dataset_id`` ascending.
    """
    root = Path(storage_root)
    if not root.exists():
        return []

    out: list[DatasetSummary] = []
    for manifest_path in sorted(root.glob("*/manifest.json")):
        try:
            m = read_manifest(manifest_path)
        except ManifestError:
            continue
        if scope is not None and m.dataset_scope != scope:
            continue
        if status is not None and m.validation_status != status:
            continue
        if name_substring is not None and name_substring not in m.name:
            continue
        out.append(
            DatasetSummary(
                dataset_id=m.dataset_id,
                name=m.name,
                scope=m.dataset_scope,
                validation_status=m.validation_status,
                sha256=m.sha256,
                created_utc=m.created_utc,
                last_seen_utc=m.last_seen_utc,
                row_count=m.row_count,
                column_count=m.column_count,
                artefact_path=Path(m.storage.directory) / m.original_filename,
            )
        )
    return out


def get_dataset(storage_root: Path, dataset_id: str) -> Manifest:
    """Load a single :class:`Manifest` by id.

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root.
    dataset_id : str
        The dataset id (e.g. ``"ds_ba54033e45525bf5123c2d9d"``).

    Returns
    -------
    Manifest
        The loaded manifest.

    Raises
    ------
    DatasetNotFound
        If no manifest exists with this id under the storage root.
    ManifestError
        If the manifest file exists but cannot be parsed.
    """
    root = Path(storage_root)
    candidate = root / dataset_id / "manifest.json"
    if not candidate.exists():
        raise DatasetNotFound(
            f"No manifest for dataset_id={dataset_id!r} under {root!s}."
        )
    return read_manifest(candidate)
