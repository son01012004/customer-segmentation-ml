"""Storage, content-addressed identity, and idempotency helpers for DEV-04.

Responsibilities
---------------
1. Compute ``clustering_id`` from a canonical JSON payload (7 fields).
2. Compute the per-clustering ``clustering/`` subdirectory.
3. Resolve the DEV-02 storage root (shared with DEV-02/DEV-03).
4. Validate path containment (defence against path traversal).
5. Idempotency lookup (``find_existing_clustering``) with collision
   detection and manifest-corruption handling.

Hard rules
-----------
- Storage root is loaded from ``configs/dev02_dataset_management.yaml``
  via ``customer_segmentation.dataset_management.storage.resolve_storage_root``.
  CLI does NOT expose ``--storage-root``.
- ``clustering_id`` is always ``"cl_" + first 24 hex chars`` of
  SHA-256 of a canonical JSON object with 7 logical fields.
- All computed paths are validated to remain inside the resolved
  storage root (via ``Path.resolve()`` + ``relative_to()``).
- ``clustering_id`` format is validated with regex
  ``^cl_[0-9a-f]{24}$`` before use in filesystem operations.

Canonical payload (7 fields for ``clustering_id`` derivation)
-----------------------------------------------------------
``clustering_id = "cl_" + SHA256(JSON canonical(
    preprocessed_id,
    algorithm,
    hyperparameters,   # sorted keys, values canonical-normalized
    seed_policy,      # "stochastic" | "deterministic"
    seed,            # int | null
    config_sha256,
    ml_dataset_sha256,
))[:24]``

``seed_policy`` canonical values:
- ``"stochastic"``: kmeans, gmm, fuzzy_cmeans (supports_random_state=True)
- ``"deterministic"``: agglomerative, dbscan (supports_random_state=False)

``seed`` canonical value:
- int for stochastic algorithms
- **always ``null`` for deterministic algorithms** (runner enforces None)
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import uuid as _uuid_mod
from pathlib import Path
from typing import Any, Final

from customer_segmentation.clustering.registry import AlgorithmRegistry

__all__ = [
    "CLUSTERING_ID_PREFIX",
    "CLUSTERING_ID_HEX_LEN",
    "DETERMINISTIC_ALGORITHMS",
    "STOCHASTIC_ALGORITHMS",
    "Dev04CollisionError",
    "Dev04ConfigError",
    "Dev04ExperimentIdConflictError",
    "Dev04ManifestCorrupt",
    "Dev04StoragePathError",
    "derive_clustering_id",
    "find_existing_clustering",
    "prototype_clustering_base_dir",
    "prototype_clustering_run_dir",
    "recover_orphan_backups",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLUSTERING_ID_PREFIX: Final[str] = "cl_"
CLUSTERING_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy

# Algorithm classification (mirror scope.py; defined here for storage logic).
DETERMINISTIC_ALGORITHMS: Final[frozenset[str]] = frozenset({"agglomerative", "dbscan"})
STOCHASTIC_ALGORITHMS: Final[frozenset[str]] = frozenset({"kmeans", "gmm", "fuzzy_cmeans"})

# Canonical payload key order (must match manifest schema + derive_clustering_id).
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "preprocessed_id",
    "algorithm",
    "hyperparameters",
    "seed_policy",
    "seed",
    "config_sha256",
    "ml_dataset_sha256",
)

# Required types for round-trip validation.
_CANONICAL_PAYLOAD_TYPES: dict[str, type | tuple[type, ...]] = {
    "preprocessed_id": str,
    "algorithm": str,
    "hyperparameters": dict,
    "seed_policy": str,
    "seed": (int, type(None)),
    "config_sha256": str,
    "ml_dataset_sha256": str,
}

# Regex patterns for directory name validation.
_CLUSTERING_ID_RE = re.compile(r"^cl_[0-9a-f]{24}$")
_STAGING_BACKUP_FAILED_RE = re.compile(r"^_(staging|backup|failed)_[A-Za-z0-9_-]+$")
_BACKUP_CORRUPT_SUFFIX = "_corrupt"
_BACKUP_PREFIX = "_backup_"

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev04StoragePathError(ValueError):
    """Raised on path / storage resolution failures."""


# Re-exported so tests can use a single class. Imported here to avoid
# circular imports at module load.
try:
    from customer_segmentation.prototype.clustering.config_loader import (
        Dev04ConfigError as _Dev04ConfigErrorFromLoader,
    )

    Dev04ConfigError = _Dev04ConfigErrorFromLoader
except ImportError:  # pragma: no cover - circular import fallback

    class Dev04ConfigError(ValueError):
        """Raised when DEV-04 config is malformed or invalid."""


class Dev04ManifestCorrupt(ValueError):
    """Raised when a clustering manifest exists but cannot be parsed.

    This is a fail-closed error: the pipeline refuses to interpret a
    corrupt manifest as a valid idempotent hit or as a collision.
    The caller must abort (default) or use ``--force-rerun`` to
    recover.
    """


class Dev04CollisionError(ValueError):
    """Raised when a ``clustering_id`` collision is detected.

    Two different effective configurations produced the same
    ``clustering_id`` (extremely rare: ~10⁻¹⁸ probability at 10⁶ runs).
    The user must investigate manually.
    """


class Dev04ExperimentIdConflictError(ValueError):
    """Raised when a run requests a different experiment_id from the
    existing manifest's experiment_id, without --force-rerun."""


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------


def _canonical_scalar(v: Any) -> Any:
    """Canonicalize a scalar value through JSON round-trip."""
    return json.loads(json.dumps(v, ensure_ascii=False, allow_nan=False))


def _canonical_hyperparameters(hp: dict[str, Any]) -> dict[str, Any]:
    """Return hyperparameters dict with sorted keys + canonical scalar values."""
    return {k: _canonical_scalar(v) for k, v in sorted(hp.items(), key=lambda kv: kv[0])}


def _seed_policy(algorithm: str) -> str:
    """Return the canonical seed_policy for an algorithm."""
    if algorithm in DETERMINISTIC_ALGORITHMS:
        return "deterministic"
    return "stochastic"


def _build_canonical_payload(
    *,
    preprocessed_id: str,
    algorithm: str,
    hyperparameters: dict[str, Any],
    effective_seed: int | None,
    ml_dataset_sha256: str,
    config_sha256: str,
) -> dict[str, Any]:
    """Return the canonical 7-field payload object used for clustering_id.

    Raises Dev04ConfigError on invalid inputs.
    """
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise Dev04ConfigError(
            f"preprocessed_id must be a non-empty str; got {type(preprocessed_id).__name__}."
        )
    if algorithm not in (DETERMINISTIC_ALGORITHMS | STOCHASTIC_ALGORITHMS):
        raise Dev04ConfigError(
            f"algorithm {algorithm!r} is not in the registry whitelist; "
            "refusing to derive clustering_id for an unknown algorithm."
        )
    if not isinstance(ml_dataset_sha256, str) or not ml_dataset_sha256:
        raise Dev04ConfigError(
            f"ml_dataset_sha256 must be a non-empty str; got {type(ml_dataset_sha256).__name__}."
        )
    if not isinstance(config_sha256, str) or not config_sha256:
        raise Dev04ConfigError(
            f"config_sha256 must be a non-empty str; got {type(config_sha256).__name__}."
        )
    if effective_seed is not None and not isinstance(effective_seed, int):
        raise Dev04ConfigError(
            f"effective_seed must be int or None; got {type(effective_seed).__name__}."
        )

    seed_policy = _seed_policy(algorithm)
    # Deterministic algorithms: canonical seed is always null (runner enforces None).
    canonical_seed: int | None = effective_seed if seed_policy == "stochastic" else None

    return {
        "preprocessed_id": preprocessed_id,
        "algorithm": algorithm,
        "hyperparameters": _canonical_hyperparameters(hyperparameters),
        "seed_policy": seed_policy,
        "seed": canonical_seed,
        "config_sha256": config_sha256,
        "ml_dataset_sha256": ml_dataset_sha256,
    }


def _canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    """Return the canonical UTF-8 bytes of a payload for hashing."""
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Content-addressed identity
# ---------------------------------------------------------------------------


def derive_clustering_id(
    *,
    preprocessed_id: str,
    algorithm: str,
    hyperparameters: dict[str, Any],
    effective_seed: int | None,
    ml_dataset_sha256: str,
    config_sha256: str,
) -> str:
    """Return ``"cl_" + first 24 hex chars`` of SHA-256 of canonical payload.

    The canonical payload is a JSON object with 7 logical fields
    (see module docstring). Serialization uses
    ``json.dumps(sort_keys=True, ensure_ascii=False,
    separators=(",", ":"), allow_nan=False)`` → UTF-8 bytes → SHA-256 →
    first 24 hex chars.

    Parameters
    ----------
    preprocessed_id : str
        DEV-03 preprocessed id.
    algorithm : str
        Algorithm name (one of the 5 supported).
    hyperparameters : dict
        Effective hyperparameters (after CLI merge).
    effective_seed : int or None
        The seed value the runner resolved (None for deterministic
        algorithms).
    ml_dataset_sha256 : str
        SHA-256 of the DEV-03 ML Dataset parquet.
    config_sha256 : str
        SHA-256 of the DEV-04 config YAML at run time.

    Returns
    -------
    str
        ``"cl_"`` + 24 hex characters.

    Raises
    ------
    Dev04ConfigError
        If any input is invalid.
    """
    payload = _build_canonical_payload(
        preprocessed_id=preprocessed_id,
        algorithm=algorithm,
        hyperparameters=hyperparameters,
        effective_seed=effective_seed,
        ml_dataset_sha256=ml_dataset_sha256,
        config_sha256=config_sha256,
    )
    payload_bytes = _canonical_payload_bytes(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    return CLUSTERING_ID_PREFIX + digest[:CLUSTERING_ID_HEX_LEN]


def compute_config_sha256(config_text: str) -> str:
    """Return the SHA-256 hex digest of a config YAML's text content."""
    return hashlib.sha256(config_text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_storage_root(
    config_path: Path | str | None = None,
) -> Path:
    """Return DEV-04's storage root (shared with DEV-02/DEV-03).

    The storage root is loaded from ``configs/dev02_dataset_management.yaml``
    via the DEV-02 storage module. ``config_path`` may override the
    canonical config when a caller imported via ``--config <custom>``.
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


def prototype_clustering_base_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
) -> Path:
    """Return ``<storage_root>/<dataset_id>/preprocessed/<preprocessed_id>/clustering/``.

    This is the container for all clustering runs of one preprocessed id.
    It is NOT created by this function — callers use it to resolve
    individual ``clustering_id`` subdirectories.

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root. The DEV-02 config sets this
        to ``data/prototype/datasets``; the dataset id and
        ``preprocessed/`` segment are appended directly (no extra
        ``"datasets"`` literal). See ``configs/dev02_dataset_management.yaml``
        and the DEV-02/DEV-03 on-disk layout for context.
    dataset_id : str
        DEV-02 dataset id.
    preprocessed_id : str
        DEV-03 preprocessed id.

    Returns
    -------
    pathlib.Path
        Absolute path to the clustering base directory.

    Raises
    ------
    Dev04StoragePathError
        If the resolved path escapes the storage root.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev04StoragePathError("dataset_id must be a non-empty string.")
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise Dev04StoragePathError("preprocessed_id must be a non-empty string.")

    root = Path(storage_root).resolve()
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``). The DEV-02
    # ``dataset_dir()`` and DEV-03 ``preprocessed_dir()`` helpers both
    # append ``dataset_id`` directly under ``storage_root``, so the
    # canonical on-disk tree is::
    #
    #     <storage_root>/<dataset_id>/preprocessed/<pp_id>/clustering/
    #
    # Pre-A-1 this function prepended an extra ``"datasets"`` literal
    # which doubled the segment (``datasets/datasets/...``) and broke
    # DEV-09's CLUSTERING lookup against the on-disk artefacts.
    candidate = (root / dataset_id / "preprocessed" / preprocessed_id / "clustering").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise Dev04StoragePathError(
            f"Computed clustering base dir {candidate!s} is not inside " f"storage root {root!s}."
        ) from exc
    return candidate


def prototype_clustering_run_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
) -> Path:
    """Return ``<base>/<clustering_id>/`` (final published directory).

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root.
    dataset_id : str
        DEV-02 dataset id.
    preprocessed_id : str
        DEV-03 preprocessed id.
    clustering_id : str
        Content-addressed clustering id (must match ``^cl_[0-9a-f]{24}$``).

    Returns
    -------
    pathlib.Path
        Absolute path to the per-clustering run directory.

    Raises
    ------
    Dev04StoragePathError
        If ``clustering_id`` format is invalid or path escapes storage root.
    """
    if not _CLUSTERING_ID_RE.match(clustering_id):
        raise Dev04StoragePathError(
            f"clustering_id {clustering_id!r} does not match "
            f"required format ^cl_[0-9a-f]{{24}}$."
        )
    base = prototype_clustering_base_dir(storage_root, dataset_id, preprocessed_id)
    candidate = (base / clustering_id).resolve()
    try:
        candidate.relative_to(Path(storage_root).resolve())
    except ValueError as exc:
        raise Dev04StoragePathError(
            f"Computed clustering run dir {candidate!s} is not inside "
            f"storage root {Path(storage_root).resolve()!s}."
        ) from exc
    return candidate


# ---------------------------------------------------------------------------
# Canonical payload extraction from stored manifest
# ---------------------------------------------------------------------------


def _extract_canonical_payload_from_manifest(
    manifest_data: dict[str, Any],
) -> dict[str, Any]:
    """Extract the 7 canonical fields from a stored manifest.

    This is a pure subset selection — no renaming, no transformation.
    Raises Dev04ManifestCorrupt if any required key is missing or
    has the wrong type.

    Raises
    ------
    Dev04ManifestCorrupt
        If manifest is missing a canonical key, has wrong type, or
        ``seed_policy`` is not in the canonical whitelist.
    """
    if not isinstance(manifest_data, dict):
        raise Dev04ManifestCorrupt(
            f"manifest must be a JSON object; got {type(manifest_data).__name__}."
        )
    for key in CANONICAL_PAYLOAD_KEYS:
        if key not in manifest_data:
            raise Dev04ManifestCorrupt(
                f"manifest is missing required canonical key {key!r}; "
                f"available keys: {sorted(manifest_data.keys())}."
            )
    for key, expected in _CANONICAL_PAYLOAD_TYPES.items():
        value = manifest_data[key]
        if not isinstance(value, expected):
            raise Dev04ManifestCorrupt(
                f"manifest field {key!r} has wrong type "
                f"{type(value).__name__}; expected {expected}."
            )
    sp = manifest_data["seed_policy"]
    if sp not in ("stochastic", "deterministic"):
        raise Dev04ManifestCorrupt(
            f"manifest seed_policy={sp!r} is not in canonical whitelist "
            f"('stochastic', 'deterministic'); refuse to round-trip."
        )
    if sp == "deterministic" and manifest_data["seed"] is not None:
        raise Dev04ManifestCorrupt(
            f"manifest has seed_policy='deterministic' but seed="
            f"{manifest_data['seed']!r} (must be null); manifest is "
            "internally inconsistent."
        )
    return {
        "preprocessed_id": manifest_data["preprocessed_id"],
        "algorithm": manifest_data["algorithm"],
        "hyperparameters": manifest_data["hyperparameters"],
        "seed_policy": sp,
        "seed": manifest_data["seed"],
        "config_sha256": manifest_data["config_sha256"],
        "ml_dataset_sha256": manifest_data["ml_dataset_sha256"],
    }


def _canonical_payload_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Compare two canonical payloads by JSON bytes."""
    a_bytes = _canonical_payload_bytes(a)
    b_bytes = _canonical_payload_bytes(b)
    return a_bytes == b_bytes


# ---------------------------------------------------------------------------
# Idempotency lookup
# ---------------------------------------------------------------------------


def find_existing_clustering(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    *,
    algorithm: str,
    hyperparameters: dict[str, Any],
    effective_seed: int | None,
    ml_dataset_sha256: str,
    config_sha256: str,
) -> Path | None:
    """Locate an existing clustering manifest.

    Returns the path to ``clustering_manifest.json`` if the run directory
    exists AND the canonical payload matches the current effective config.
    Returns ``None`` if no manifest exists for this ``clustering_id``.

    Raises
    ------
    Dev04ManifestCorrupt
        If a manifest file exists but cannot be parsed or is missing
        required canonical fields.
    Dev04CollisionError
        If the ``clustering_id`` matches but the canonical payload
        differs (collision or tamper). The user must investigate.
    """
    # Format check before touching filesystem.
    if not _CLUSTERING_ID_RE.match(clustering_id):
        return None

    base = prototype_clustering_base_dir(storage_root, dataset_id, preprocessed_id)
    run_dir = base / clustering_id
    manifest_path = run_dir / "clustering_manifest.json"

    if not manifest_path.exists():
        return None

    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise Dev04ManifestCorrupt(
            f"manifest at {manifest_path!s} is unreadable or corrupt JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise Dev04ManifestCorrupt(
            f"manifest at {manifest_path!s} must be a JSON object; " f"got {type(data).__name__}."
        )

    # Manifest self-reference check (tamper detection).
    if data.get("clustering_id") != clustering_id:
        raise Dev04ManifestCorrupt(
            f"manifest clustering_id field {data.get('clustering_id')!r} "
            f"!= directory name {clustering_id!r}; manifest is "
            "inconsistent with its path (possible tamper or rename). "
            "Refusing to interpret."
        )

    expected_payload = _build_canonical_payload(
        preprocessed_id=preprocessed_id,
        algorithm=algorithm,
        hyperparameters=hyperparameters,
        effective_seed=effective_seed,
        ml_dataset_sha256=ml_dataset_sha256,
        config_sha256=config_sha256,
    )
    try:
        stored_payload = _extract_canonical_payload_from_manifest(data)
    except Dev04ManifestCorrupt:
        raise

    if not _canonical_payload_equal(expected_payload, stored_payload):
        raise Dev04CollisionError(
            f"clustering_id collision or manifest tamper detected: "
            f"clustering_id={clustering_id}, "
            f"expected_payload={expected_payload}, "
            f"stored_payload={stored_payload}. "
            "Refusing to proceed; investigate manually. "
            "If this is a benign collision (probability ~6.3e-18 at "
            "1e6 IDs), bump CLUSTERING_ID_HEX_LEN. "
            "If manifest was tampered, restore from backup."
        )

    return manifest_path


# ---------------------------------------------------------------------------
# Recovery pass for orphan backups
# ---------------------------------------------------------------------------


def recover_orphan_backups(base_dir: Path, current_run_uuid: str) -> int:
    """Restore final_dir from orphan backup_dir of a previous crashed run.

    This function runs at the start of each pipeline invocation to
    recover from a crash that occurred between the
    ``final_dir → backup_dir`` rename and the
    ``staging_dir → final_dir`` rename.

    Scans ``base_dir/_backup_*/`` directories whose uuid differs from
    ``current_run_uuid``. For each valid backup (exactly 1 inner
    subdirectory matching ``^cl_[0-9a-f]{24}$``):

    - If ``final_dir`` does NOT exist: atomic restore
      ``backup_dir/<clustering_id>`` → ``final_dir``.
    - If ``final_dir`` already exists: skip (manifest already valid or
      restored by a previous recovery pass).

    NEVER restores from ``_backup_<uuid>_corrupt/`` directories.
    Skips malformed backups (wrong number of inner subdirs, wrong naming).

    Returns the number of orphan backups successfully restored.
    This function NEVER raises — errors are logged and swallowed.
    """
    import logging

    log = logging.getLogger("customer_segmentation.prototype.clustering")
    recovered = 0

    if not base_dir.exists():
        return 0

    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name

        # Only handle backup directories.
        if not name.startswith(_BACKUP_PREFIX):
            continue

        # Skip current run's own backup (handled by main pipeline).
        run_uuid = name[len(_BACKUP_PREFIX) :]
        if run_uuid == current_run_uuid:
            continue

        # Skip corrupt-manifest backups (R2 marker).
        if name.endswith(_BACKUP_CORRUPT_SUFFIX):
            log.debug(
                "DEV-04 recovery: skipping corrupt backup %s (R2 marker).",
                entry,
            )
            continue

        # Scan inner subdirectories.
        try:
            subdirs = [p for p in entry.iterdir() if p.is_dir()]
        except OSError as exc:
            log.warning(
                "DEV-04 recovery: iterdir failed on %s: %s; skipping.",
                entry,
                exc,
            )
            continue

        if len(subdirs) != 1:
            log.warning(
                "DEV-04 recovery: backup_dir %s has %d inner subdirs "
                "(expected 1); leaving for manual cleanup.",
                entry,
                len(subdirs),
            )
            continue

        inner = subdirs[0]
        if not _CLUSTERING_ID_RE.match(inner.name):
            log.warning(
                "DEV-04 recovery: inner subdir %r in %s does not match "
                "clustering_id regex; leaving for manual cleanup.",
                inner.name,
                entry,
            )
            continue

        clustering_id = inner.name
        final_dir = base_dir / clustering_id

        # Skip if final_dir already exists.
        if final_dir.exists():
            log.debug(
                "DEV-04 recovery: final_dir %s already exists; skipping restore.",
                final_dir,
            )
            continue

        # Atomic restore.
        try:
            os.rename(inner, final_dir)
        except OSError as exc:
            log.warning(
                "DEV-04 recovery: rename %s -> %s failed: %s; skipping.",
                inner,
                final_dir,
                exc,
            )
            continue

        # Cleanup empty backup container if possible.
        with contextlib.suppress(OSError):
            entry.rmdir()

        log.info(
            "DEV-04 recovery: restored %s from orphan backup %s.",
            final_dir,
            entry,
        )
        recovered += 1

    return recovered


# ---------------------------------------------------------------------------
# Run UUID (process-scoped singleton)
# ---------------------------------------------------------------------------

# Set once per process; used by cleanup pass to scope its operations.
_RUN_UUID: str = _uuid_mod.uuid4().hex
