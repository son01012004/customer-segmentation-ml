"""Enumerate preprocessed artefacts for a DEV-02 dataset_id.

Reads ``preprocessed_manifest.json`` files directly under
``<storage_root>/<dataset_id>/preprocessed/``. Mirrors the DEV-02
``list_datasets`` pattern: filesystem-only scan, no in-memory
index, sort for determinism.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from customer_segmentation.dataset_management.manifest import ManifestError as _ManifestError
from customer_segmentation.prototype.preprocessing.manifest import (
    Dev03ManifestError,
    read_preprocessed_manifest,
)

__all__ = [
    "PreprocessedNotFound",
    "PreprocessedSummary",
    "list_preprocessed",
]


@dataclass(frozen=True)
class PreprocessedSummary:
    """One row in :func:`list_preprocessed`."""

    preprocessed_id: str
    source_dataset_id: str
    source_dataset_sha256: str
    lifecycle: str
    preprocessed_scope: str
    created_utc: str
    last_seen_utc: str
    ml_dataset_row_count: int
    ml_dataset_column_count: int
    ml_dataset_path: Path
    manifest_path: Path


class PreprocessedNotFound(LookupError):
    """Raised when a request for a specific ``preprocessed_id`` fails."""


def list_preprocessed(
    storage_root: Path,
    dataset_id: str,
) -> list[PreprocessedSummary]:
    """List preprocessed manifests under one dataset's container.

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root (DEV-02's).
    dataset_id : str
        The DEV-02 dataset id.

    Returns
    -------
    list[PreprocessedSummary]
        Sorted by ``preprocessed_id`` ascending.
    """
    root = Path(storage_root)
    container = root / dataset_id / "preprocessed"
    if not container.exists():
        return []

    out: list[PreprocessedSummary] = []
    for manifest_path in sorted(container.glob("preprocessed_manifest.json")):
        try:
            m = read_preprocessed_manifest(manifest_path)
        except Dev03ManifestError:
            continue
        out.append(
            PreprocessedSummary(
                preprocessed_id=m.preprocessed_id,
                source_dataset_id=m.source_dataset_id,
                source_dataset_sha256=m.source_dataset_sha256,
                lifecycle=(
                    "VALID"
                    if m.research_safety.automatically_promoted_to_research is False
                    else "UNKNOWN"
                ),
                preprocessed_scope=m.preprocessed_scope,
                created_utc=m.created_utc,
                last_seen_utc=m.last_seen_utc,
                ml_dataset_row_count=m.ml_dataset_block.row_count,
                ml_dataset_column_count=m.ml_dataset_block.column_count,
                ml_dataset_path=Path(m.ml_dataset_block.artifact_path),
                manifest_path=Path(manifest_path),
            )
        )
    return out


__ = _ManifestError
