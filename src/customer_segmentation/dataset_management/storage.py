"""Path resolution and content-addressed storage helpers for DEV-02.

Responsibilities
----------------
1. Compute a stable :func:`derive_dataset_id` from a SHA-256 hex.
2. Compute the on-disk dataset directory and verify it remains inside
   the storage root (defence against path traversal).
3. Look up an existing manifest by content-hash for idempotent
   re-imports.
4. Resolve the storage root from the YAML config.

Hard rules
----------
- The storage root is **always** loaded from
  ``configs/dev02_dataset_management.yaml`` (resolved against the
  current working directory). The CLI does **not** expose
  ``--dest-root`` or any equivalent.
- The dataset id is **always** ``"ds_" + first 24 hex chars`` of the
  file's SHA-256. The first 24 hex chars (12 bytes / 96 bits) give
  ~10^28 distinct values, more than enough for a prototype.
- A dataset directory is always computed as
  ``storage_root / dataset_id`` and is verified to live inside the
  resolved storage root.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

__all__ = [
    "DATASET_ID_PREFIX",
    "DATASET_ID_HEX_LEN",
    "StoragePathError",
    "derive_dataset_id",
    "dataset_dir",
    "find_existing_dataset",
    "resolve_storage_root",
    "load_config",
    "validate_config",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATASET_ID_PREFIX: Final[str] = "ds_"
DATASET_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy


class StoragePathError(ValueError):
    """Raised on path / storage resolution failures."""


# ---------------------------------------------------------------------------
# Dataset identity
# ---------------------------------------------------------------------------


def derive_dataset_id(sha256_hex: str) -> str:
    """Return ``"ds_" + first 24 hex chars`` of the SHA-256.

    Parameters
    ----------
    sha256_hex : str
        A 64-character hexadecimal string.

    Returns
    -------
    str
        The dataset id, e.g. ``"ds_ba54033e45525bf5123c2d9d"``.

    Raises
    ------
    StoragePathError
        If ``sha256_hex`` is not a non-empty hex string of at least
        24 characters.
    """
    if not isinstance(sha256_hex, str) or not sha256_hex:
        raise StoragePathError(
            f"sha256_hex must be a non-empty string; got {type(sha256_hex).__name__}."
        )
    s = sha256_hex.lower()
    if not all(c in "0123456789abcdef" for c in s):
        raise StoragePathError(
            f"sha256_hex must be lowercase hex; got {sha256_hex!r}."
        )
    if len(s) < DATASET_ID_HEX_LEN:
        raise StoragePathError(
            f"sha256_hex must be at least {DATASET_ID_HEX_LEN} hex chars; "
            f"got length {len(s)}."
        )
    return DATASET_ID_PREFIX + s[:DATASET_ID_HEX_LEN]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def dataset_dir(storage_root: Path, dataset_id: str) -> Path:
    """Return ``storage_root / dataset_id``.

    Verifies the resolved directory is inside ``storage_root`` (after
    symlink resolution). Raises :class:`StoragePathError` if the
    computed path would escape the storage root.

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root. Callers are expected to
        have passed this through :func:`resolve_storage_root` first.
    dataset_id : str
        A non-empty dataset id (must start with ``"ds_"``).

    Returns
    -------
    pathlib.Path
        Absolute path to the dataset directory.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise StoragePathError("dataset_id must be a non-empty string.")
    if not dataset_id.startswith(DATASET_ID_PREFIX):
        raise StoragePathError(
            f"dataset_id must start with {DATASET_ID_PREFIX!r}; got {dataset_id!r}."
        )
    candidate = (Path(storage_root) / dataset_id).resolve()
    root_resolved = Path(storage_root).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise StoragePathError(
            f"Computed dataset dir {candidate!s} is not inside storage root "
            f"{root_resolved!s}."
        ) from exc
    return candidate


# ---------------------------------------------------------------------------
# Idempotency lookup
# ---------------------------------------------------------------------------


def find_existing_dataset(storage_root: Path, sha256_hex: str) -> Path | None:
    """Locate an existing manifest with this content-hash.

    Scans every ``manifest.json`` directly under
    ``<storage_root>/<dataset_id>/``. Returns the manifest path of
    the first match (the scan is sorted for determinism), or ``None``
    if no manifest exists for this hash.

    This is a *content-keyed* lookup — two CSV files with identical
    bytes are the same dataset, even if their on-disk filenames
    differ.

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root.
    sha256_hex : str
        Lowercase hex SHA-256 to look up.

    Returns
    -------
    pathlib.Path or None
        Path to the matching ``manifest.json``, or ``None`` if no
        match.
    """
    root = Path(storage_root)
    if not root.exists():
        return None
    target = sha256_hex.lower()
    for manifest_path in sorted(root.glob(f"*/manifest.json")):
        try:
            with manifest_path.open("r", encoding="utf-8") as fh:
                data = _safe_load_json(fh.read())
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        existing = str(data.get("sha256", "")).lower()
        if existing == target:
            return manifest_path
    return None


def _safe_load_json(text: str) -> Any:
    """Minimal JSON parse that raises :class:`ValueError` on failure."""
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Storage-root resolution
# ---------------------------------------------------------------------------


def resolve_storage_root(config: Mapping[str, Any]) -> Path:
    """Return the storage root as an absolute path.

    The config is the inner ``dataset_management:`` mapping of
    :file:`configs/dev02_dataset_management.yaml`. The
    ``storage_root`` value is resolved against the current working
    directory (which is the repository root when the CLI is invoked
    normally).

    Parameters
    ----------
    config : Mapping[str, Any]
        Inner config mapping.

    Returns
    -------
    pathlib.Path
        Absolute path to the storage root.
    """
    raw = config.get("storage_root")
    if not isinstance(raw, str) or not raw:
        raise StoragePathError(
            "Config is missing 'storage_root' (must be a non-empty string)."
        )
    return Path(raw).resolve()


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(path: Path | str) -> dict[str, Any]:
    """Load :file:`configs/dev02_dataset_management.yaml`.

    Returns the inner ``dataset_management`` mapping as a plain dict.

    Parameters
    ----------
    path : pathlib.Path or str
        Path to the YAML config file.

    Returns
    -------
    dict
        The ``dataset_management:`` mapping.

    Raises
    ------
    StoragePathError
        If the file is missing, the YAML is malformed, the top-level
        is not a mapping, or the ``dataset_management`` key is
        missing or not a mapping.
    """
    import yaml  # type: ignore[import-untyped]

    p = Path(path)
    if not p.exists():
        raise StoragePathError(f"Config file not found: {p}")
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # type: ignore[misc]
        raise StoragePathError(f"Failed to parse YAML at {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise StoragePathError(
            f"Config file {p} must be a YAML mapping; got {type(data).__name__}."
        )
    inner = data.get("dataset_management")
    if not isinstance(inner, dict):
        raise StoragePathError(
            f"Config file {p} must contain a top-level 'dataset_management' mapping."
        )
    return inner


def validate_config(config: Mapping[str, Any]) -> None:
    """Validate the inner config mapping.

    Checks:

    - ``storage_root`` is a non-empty string.
    - ``max_file_size_mb`` is a positive number.
    - ``supported_import_formats`` is a non-empty list of lowercase
      strings without a leading dot.
    - ``default_csv_encoding`` is a non-empty string.
    - ``source_path_policy`` is a mapping containing
      ``allow_external_source`` as a bool.
    - ``readonly_research_paths`` is a list of non-empty strings.

    Raises
    ------
    StoragePathError
        If any check fails.
    """
    storage_root = config.get("storage_root")
    if not isinstance(storage_root, str) or not storage_root:
        raise StoragePathError("'storage_root' must be a non-empty string.")

    max_size = config.get("max_file_size_mb")
    if isinstance(max_size, bool) or not isinstance(max_size, (int, float)):
        raise StoragePathError("'max_file_size_mb' must be a positive number.")
    if float(max_size) <= 0:
        raise StoragePathError("'max_file_size_mb' must be a positive number.")

    fmts = config.get("supported_import_formats")
    if not isinstance(fmts, list) or not fmts:
        raise StoragePathError("'supported_import_formats' must be a non-empty list.")
    for i, f in enumerate(fmts):
        if not isinstance(f, str) or not f:
            raise StoragePathError(
                f"'supported_import_formats'[{i}] must be a non-empty string."
            )
        if f.startswith("."):
            raise StoragePathError(
                f"'supported_import_formats'[{i}] must not start with a dot; got {f!r}."
            )
        if f != f.lower():
            raise StoragePathError(
                f"'supported_import_formats'[{i}] must be lowercase; got {f!r}."
            )

    enc = config.get("default_csv_encoding")
    if not isinstance(enc, str) or not enc:
        raise StoragePathError("'default_csv_encoding' must be a non-empty string.")

    spp = config.get("source_path_policy")
    if not isinstance(spp, dict):
        raise StoragePathError("'source_path_policy' must be a mapping.")
    aes = spp.get("allow_external_source")
    if not isinstance(aes, bool):
        raise StoragePathError(
            "'source_path_policy.allow_external_source' must be a boolean."
        )

    readonly = config.get("readonly_research_paths")
    if not isinstance(readonly, list):
        raise StoragePathError("'readonly_research_paths' must be a list.")
    for i, p in enumerate(readonly):
        if not isinstance(p, str) or not p:
            raise StoragePathError(
                f"'readonly_research_paths'[{i}] must be a non-empty string."
            )
