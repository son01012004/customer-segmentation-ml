"""Storage and content-addressed identity for DEV-03 Prototype Preprocessing.

Responsibilities
----------------
1. Compute ``preprocessed_id`` from a SHA-256 (24 hex prefix).
2. Compute the per-dataset ``preprocessed/`` sub-directory.
3. Compute the on-disk log file path.
4. Validate the storage root resolution (mirror DEV-02 convention).

Hard rules
----------
- Storage root is loaded from
  ``configs/dev03_preprocessing.yaml::dev03_preprocessing.preprocessing.logging.log_dir_relative``
  and resolved against the current working directory (the repo root
  when the CLI is invoked normally).
- ``preprocessed_id`` is **always** ``"pp_" + first 24 hex chars`` of
  a SHA-256 derived from the concatenation of (source ``dataset_id``
  + config_hash + cleaned-content sha). See :func:`derive_preprocessed_id`
  for the canonical construction.
- ``preprocessed/`` is the canonical sub-directory; no other path is
  writable for DEV-03.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from customer_segmentation.dataset_management.importer import (
    DEFAULT_CONFIG_PATH as DEFAULT_DEV02_CONFIG_PATH,
)
from customer_segmentation.prototype.preprocessing.config_loader import (
    DEFAULT_DEV03_CONFIG_PATH,
    load_dev03_config,
)

__all__ = [
    "PREPROCESSED_DIR_SUFFIX",
    "PREPROCESSED_ID_HEX_LEN",
    "PREPROCESSED_ID_PREFIX",
    "Dev03StoragePathError",
    "derive_preprocessed_id",
    "ensure_preprocessed_container",
    "preprocessed_dir",
    "preprocessed_log_path",
    "resolve_storage_root",
    "storage_root_for",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREPROCESSED_DIR_SUFFIX: Final[str] = "preprocessed"
PREPROCESSED_ID_PREFIX: Final[str] = "pp_"
PREPROCESSED_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy


class Dev03StoragePathError(ValueError):
    """Raised on path / storage resolution failures."""


# ---------------------------------------------------------------------------
# Content-addressed identity
# ---------------------------------------------------------------------------


def derive_preprocessed_id(
    source_dataset_id: str,
    config_hash: str,
    content_sha256: str,
) -> str:
    """Return ``pp_<24-hex>`` derived from (dataset_id + config_hash + content).

    Parameters
    ----------
    source_dataset_id : str
        The DEV-02 dataset_id (e.g. ``"ds_ba54033e45525bf5123c2d9d"``).
    config_hash : str
        The SHA-256 of the DEV-03 config YAML at run time.
    content_sha256 : str
        The SHA-256 of the cleaned transaction-level content produced
        by Stage C. Pass the **input** content hash if Stage C
        produces the same bytes (idempotency).

    Returns
    -------
    str
        ``"pp_<24-hex>"``.
    """
    import hashlib

    if not isinstance(source_dataset_id, str) or not source_dataset_id:
        raise Dev03StoragePathError(
            f"source_dataset_id must be a non-empty string; got {type(source_dataset_id).__name__}."
        )
    if not isinstance(config_hash, str) or not config_hash:
        raise Dev03StoragePathError(
            f"config_hash must be a non-empty string; got {type(config_hash).__name__}."
        )
    if not isinstance(content_sha256, str) or not content_sha256:
        raise Dev03StoragePathError(
            f"content_sha256 must be a non-empty string; got {type(content_sha256).__name__}."
        )

    canonical = f"{source_dataset_id}\n{config_hash}\n{content_sha256}".encode()
    digest = hashlib.sha256(canonical).hexdigest()
    return PREPROCESSED_ID_PREFIX + digest[:PREPROCESSED_ID_HEX_LEN]


def config_hash_yaml(path: Path) -> str:
    """Return the SHA-256 hex digest of the YAML file's bytes."""
    import hashlib

    p = Path(path)
    if not p.exists():
        raise Dev03StoragePathError(f"Config file not found: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def preprocessed_dir(storage_root: Path, dataset_id: str) -> Path:
    """Return ``<storage_root>/<dataset_id>/preprocessed/``.

    The container is NOT created here — use :func:`ensure_preprocessed_container`
    for that. This function only resolves the canonical path.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev03StoragePathError("dataset_id must be a non-empty string.")
    root = Path(storage_root).resolve()
    candidate = (root / dataset_id / PREPROCESSED_DIR_SUFFIX).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise Dev03StoragePathError(
            f"Computed preprocessed dir {candidate!s} is not inside storage root {root!s}."
        ) from exc
    return candidate


def ensure_preprocessed_container(storage_root: Path, dataset_id: str) -> Path:
    """Create the per-dataset ``preprocessed/`` container if missing.

    Idempotent: returns the existing path if it already exists.
    """
    target = preprocessed_dir(storage_root, dataset_id)
    target.mkdir(parents=True, exist_ok=True)
    return target


def preprocessed_log_path(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
) -> Path:
    """Return the canonical log path: ``<dir>/<preprocessed_id>.log``."""
    ensure_preprocessed_container(storage_root, dataset_id)
    return preprocessed_dir(storage_root, dataset_id) / f"{preprocessed_id}.log"


# ---------------------------------------------------------------------------
# Storage-root resolution
# ---------------------------------------------------------------------------


def resolve_storage_root_for_dataset(
    dataset_id: str,
    config_path: Path | None = None,
) -> Path:
    """Resolve the per-dataset storage root using DEV-02's contract.

    DEV-03 stores artefacts under the SAME dataset directory that
    DEV-02 wrote. The container layout is::

        <DEV-02 storage_root>/<dataset_id>/<original_filename>
        <DEV-02 storage_root>/<dataset_id>/manifest.json
        <DEV-02 storage_root>/<dataset_id>/preprocessed/...   <-- DEV-03 writes here

    The DEV-02 storage root is loaded from
    ``configs/dev02_dataset_management.yaml::dataset_management.storage_root``.
    """
    from customer_segmentation.dataset_management.storage import (  # local import to avoid cycles
        load_config as load_dev02_config,
    )
    from customer_segmentation.dataset_management.storage import (
        resolve_storage_root as resolve_dev02_storage_root,
    )

    config = load_dev02_config(config_path) if config_path else load_dev02_config()
    root = resolve_dev02_storage_root(config)
    return root


def resolve_storage_root(
    config_path: Path | str | None = None,
) -> Path:
    """Return DEV-03 storage root from the DEV-02 config.

    DEV-03's canonical storage root is shared with DEV-02 (the
    preprocessed artefact lives under the same per-dataset folder).
    For convenience, this function returns the DEV-02 storage root
    (where DEV-02 wrote ``manifest.json``).

    Parameters
    ----------
    config_path : pathlib.Path or str, optional
        Path to ``configs/dev02_dataset_management.yaml``. ``None``
        falls back to the canonical default.
    """
    from customer_segmentation.dataset_management.storage import (  # local import to avoid cycles
        load_config as load_dev02_config,
    )
    from customer_segmentation.dataset_management.storage import (
        resolve_storage_root as resolve_dev02_storage_root,
    )

    p = Path(config_path) if config_path else DEFAULT_DEV02_CONFIG_PATH
    inner = load_dev02_config(p)
    return resolve_dev02_storage_root(inner)


def storage_root_for(
    config_path: Path | None = None,
    dev02_config_path: Path | None = None,
) -> Path:
    """Convenience: read DEV-03 YAML and resolve storage root from the
    DEV-02 config (shared).

    Parameters
    ----------
    config_path : pathlib.Path, optional
        Path to ``configs/dev03_preprocessing.yaml``; for symmetry.
        DEV-02's storage root is independent of this config.
    dev02_config_path : pathlib.Path, optional
        Path to ``configs/dev02_dataset_management.yaml``. ``None``
        falls back to the canonical default.
    """
    cfg = load_dev03_config(config_path)
    _ = cfg  # DEV-03 config is read for side-effects; root comes from DEV-02.
    return resolve_storage_root(dev02_config_path)


__ = (
    Mapping,
    Any,
    DEFAULT_DEV03_CONFIG_PATH,
)
