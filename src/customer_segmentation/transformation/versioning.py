"""Versioning and SHA-256 utilities for FE-06.

Provides:
- SHA-256 computation for files
- Dataset version information
- Reproducibility metadata helpers

Hard constraints:
- Pipeline is deterministic (no random state).
- SHA-256 is used for integrity verification, NOT for ranking.
- Pickle SHA is recorded but NOT used for byte-level cross-environment equality.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

__all__ = [
    "compute_sha256",
    "compute_file_sha256",
    "FE06_VERSION",
    "FE06Version",
]

FE06_VERSION = "FE06-v1.0"


@dataclass
class FE06Version:
    """FE-06 dataset version information."""

    version: str
    meaning: str
    status: str  # "TECHNICALLY_GENERATED"


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 of bytes data.

    Parameters
    ----------
    data : bytes
        Data to hash.

    Returns
    -------
    str
        SHA-256 hex digest.
    """
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute SHA-256 of a file by streaming chunks.

    Parameters
    ----------
    path : pathlib.Path
        Path to the file.
    chunk_size : int
        Chunk size in bytes (default 1 MB).

    Returns
    -------
    str
        SHA-256 hex digest.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_df_sha256(df: pd.DataFrame) -> str:
    """Compute SHA-256 of a DataFrame via its Parquet bytes.

    Uses Parquet serialization for consistent hashing.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame to hash.

    Returns
    -------
    str
        SHA-256 hex digest.
    """
    import io

    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)
    return compute_sha256(buffer.read())
