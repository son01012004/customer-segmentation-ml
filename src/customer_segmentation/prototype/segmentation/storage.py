"""Storage, content-addressed identity, and idempotency helpers for DEV-06.

Responsibilities
----------------
1. Compute ``segmentation_id`` from a canonical JSON payload (8 fields).
2. Compute the per-segmentation ``segmentation/`` subdirectory under
   the DEV-04 ``<clustering_id>/`` run dir.
3. Resolve the DEV-02 storage root (shared with DEV-02/03/04/05).
4. Validate path containment (defence against path traversal).
5. Idempotency lookup (``find_existing_segmentation``) with collision
   detection and manifest-corruption handling.

Hard rules
----------
- Storage root is loaded from ``configs/dev02_dataset_management.yaml``
  via ``customer_segmentation.dataset_management.storage.resolve_storage_root``.
  CLI does NOT expose ``--storage-root``.
- ``segmentation_id`` is always ``"seg_" + first 24 hex chars`` of
  SHA-256 of a canonical JSON object with 8 logical fields.
- All computed paths are validated to remain inside the resolved
  storage root (via ``Path.resolve()`` + ``relative_to()``).
- ``segmentation_id`` format is validated with regex
  ``^seg_[0-9a-f]{24}$`` before use in filesystem operations.
- ``clustering_id`` format is validated with regex
  ``^cl_[0-9a-f]{24}$`` (delegated to caller; never re-derive).
- R-DEV-06-24: ``CompatibilityKey`` MUST NOT include
  ``preprocessing_config_sha256`` (avoid DEV-05 placeholder defect).
  However, ``segmentation_id`` CAN include it (read from
  ``PreprocessedManifest.config_hash`` which is the canonical value).

Canonical payload (8 fields for ``segmentation_id`` derivation)
------------------------------------------------------------
``segmentation_id = "seg_" + SHA256(JSON canonical(
    clustering_id,                  # ^cl_[0-9a-f]{24}$
    preprocessed_id,
    dataset_id,
    ml_dataset_sha256,
    feature_set_sha256,             # derived from sorted feature list
    preprocessing_config_sha256,    # from DEV-03 PreprocessedManifest.config_hash
    noise_policy,                   # "include" | "exclude"
    schema_version,                 # SEGMENTATION_MANIFEST_SCHEMA_VERSION
))[:24]``

``feature_set_sha256`` canonical value:
- 64-hex SHA-256 of the sorted feature names joined by ``"|"``.
- Order-independent: ``["a", "b"]`` and ``["b", "a"]`` produce the same value.

``preprocessing_config_sha256`` canonical value:
- 64-hex SHA-256 of the DEV-03 preprocessing config (read from
  ``PreprocessedManifest.config_hash``). DEV-06 does NOT use
  ``clustering_manifest.json`` for this field — that field is absent
  in ``ClusteringManifest`` v1.0.0 (per pre-existing DEV-05 defect,
  DEV-06 reads directly to sidestep the fallback placeholder).

``noise_policy`` canonical values:
- ``"exclude"`` (prototype default per ADR-0006) — DBSCAN noise rows
  filtered from X and labels before profile compute.
- ``"include"`` — no filter applied.

``schema_version`` canonical value:
- :data:`SEGMENTATION_MANIFEST_SCHEMA_VERSION` (currently ``"1.0.0"``).
  A schema bump invalidates all old ``segmentation_id``s and forces re-run.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.segmentation.scope import (
    NOISE_POLICIES,
    SEGMENTATION_MANIFEST_SCHEMA_VERSION,
)

__all__ = [
    "SEGMENTATION_ID_PREFIX",
    "SEGMENTATION_ID_HEX_LEN",
    "CANONICAL_PAYLOAD_KEYS",
    "Dev06CollisionError",
    "Dev06ManifestCorrupt",
    "Dev06StoragePathError",
    "compute_config_sha256",
    "compute_feature_set_sha256",
    "derive_segmentation_id",
    "find_existing_segmentation",
    "prototype_segmentation_base_dir",
    "prototype_segmentation_run_dir",
    "resolve_storage_root",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEGMENTATION_ID_PREFIX: Final[str] = "seg_"
SEGMENTATION_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy

# Canonical payload key order (must match ``derive_segmentation_id``).
# Per §4.3: 8 fields. NO metric_set (no metrics in DEV-06). NO evaluation_id
# (DEV-05 manifest is optional provenance, not canonical key).
# NOTE: the on-disk key is ``noise_policy_used`` (per manifest schema
# v1.0.0); for the canonical payload, we use ``noise_policy`` for
# short (used by ``derive_segmentation_id``). The ``find_existing_segmentation``
# helper extracts both ``noise_policy`` (from payload) and
# ``noise_policy_used`` (from manifest) into a normalised form for
# comparison.
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "clustering_id",
    "preprocessed_id",
    "dataset_id",
    "ml_dataset_sha256",
    "feature_set_sha256",
    "preprocessing_config_sha256",
    "noise_policy",
    "schema_version",
)

# Required types for round-trip validation.
# (Must be a strict subset of ``CANONICAL_PAYLOAD_KEYS``; ``config_sha256``
# is intentionally NOT a key — it is recorded as provenance in the
# manifest but excluded from the segmentation_id derivation per
# plan §4.3, so it has no payload entry.)
_CANONICAL_PAYLOAD_TYPES: dict[str, type | tuple[type, ...]] = {
    "clustering_id": str,
    "preprocessed_id": str,
    "dataset_id": str,
    "ml_dataset_sha256": str,
    "feature_set_sha256": str,
    "preprocessing_config_sha256": str,
    "noise_policy": str,
    "schema_version": str,
}

# Regex patterns for id validation.
_SEGMENTATION_ID_RE = re.compile(r"^seg_[0-9a-f]{24}$")
_CLUSTERING_ID_RE = re.compile(r"^cl_[0-9a-f]{24}$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev06StoragePathError(ValueError):
    """Raised on path / storage resolution failures."""


class Dev06ManifestCorrupt(ValueError):
    """Raised when a segmentation manifest exists but cannot be parsed.

    Fail-closed: the pipeline refuses to interpret a corrupt manifest
    as a valid idempotent hit or as a collision. The caller must
    abort (default) or use ``--force-rerun`` to recover.
    """


class Dev06CollisionError(ValueError):
    """Raised when a ``segmentation_id`` collision is detected.

    Two different effective configurations produced the same
    ``segmentation_id`` (extremely rare: ~10⁻¹⁸ probability at 10⁶ runs).
    The user must investigate manually.
    """


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------


def _validate_inputs(
    *,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    ml_dataset_sha256: str,
    feature_set_sha256: str,
    preprocessing_config_sha256: str,
    noise_policy: str,
) -> None:
    """Validate all 8 canonical inputs; raise Dev06StoragePathError on failure."""
    if not isinstance(clustering_id, str) or not _CLUSTERING_ID_RE.match(clustering_id):
        raise Dev06StoragePathError(
            f"clustering_id {clustering_id!r} does not match required format "
            f"^cl_[0-9a-f]{{24}}$."
        )
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise Dev06StoragePathError(
            f"preprocessed_id must be a non-empty str; got {type(preprocessed_id).__name__}."
        )
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev06StoragePathError(
            f"dataset_id must be a non-empty str; got {type(dataset_id).__name__}."
        )
    if not isinstance(ml_dataset_sha256, str) or not ml_dataset_sha256:
        raise Dev06StoragePathError(
            f"ml_dataset_sha256 must be a non-empty str; "
            f"got {type(ml_dataset_sha256).__name__}."
        )
    if not isinstance(feature_set_sha256, str) or not feature_set_sha256:
        raise Dev06StoragePathError(
            f"feature_set_sha256 must be a non-empty str; "
            f"got {type(feature_set_sha256).__name__}."
        )
    if not isinstance(preprocessing_config_sha256, str) or not preprocessing_config_sha256:
        raise Dev06StoragePathError(
            f"preprocessing_config_sha256 must be a non-empty str; "
            f"got {type(preprocessing_config_sha256).__name__}."
        )
    if noise_policy not in NOISE_POLICIES:
        raise Dev06StoragePathError(
            f"noise_policy {noise_policy!r} is not in the closed set " f"{sorted(NOISE_POLICIES)}."
        )


def _build_canonical_payload(
    *,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    ml_dataset_sha256: str,
    feature_set_sha256: str,
    preprocessing_config_sha256: str,
    noise_policy: str,
    schema_version: str = SEGMENTATION_MANIFEST_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return the canonical 8-field payload object used for segmentation_id.

    Raises :class:`Dev06StoragePathError` on invalid inputs.
    """
    return {
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "ml_dataset_sha256": ml_dataset_sha256,
        "feature_set_sha256": feature_set_sha256,
        "preprocessing_config_sha256": preprocessing_config_sha256,
        "noise_policy": noise_policy,
        "schema_version": schema_version,
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


def compute_config_sha256(config_text: str) -> str:
    """Return the SHA-256 hex digest of a config YAML's text content."""
    return hashlib.sha256(config_text.encode("utf-8")).hexdigest()


def compute_feature_set_sha256(feature_set) -> str:
    """Return the 64-hex SHA-256 of a feature set (sorted, ``|``-joined).

    The hash is order-independent (sort before joining) and content-only
    (no whitespace, no json envelope) so that ``["a", "b"]`` and
    ``["b", "a"]`` produce the same hash.

    Parameters
    ----------
    feature_set : iterable of str
        Any iterable of feature-name strings (typically the values of
        ``ClusteringManifest.feature_set``). Empty iterable raises.

    Returns
    -------
    str
        64-hex SHA-256.

    Raises
    ------
    Dev06StoragePathError
        If ``feature_set`` is empty or contains non-string items.
    """
    if isinstance(feature_set, (set, frozenset, list, tuple)):
        names = sorted(feature_set)
    else:
        raise Dev06StoragePathError(
            f"feature_set must be a list, tuple, set, or frozenset; "
            f"got {type(feature_set).__name__}."
        )
    if not names:
        raise Dev06StoragePathError("feature_set must be non-empty.")
    for n in names:
        if not isinstance(n, str):
            raise Dev06StoragePathError(
                f"feature_set entries must be strings; got {type(n).__name__}."
            )
    joined = "|".join(names)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def derive_segmentation_id(
    *,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    ml_dataset_sha256: str,
    feature_set_sha256: str,
    preprocessing_config_sha256: str,
    noise_policy: str,
    schema_version: str = SEGMENTATION_MANIFEST_SCHEMA_VERSION,
) -> str:
    """Return ``"seg_" + first 24 hex chars`` of SHA-256 of canonical payload.

    Parameters
    ----------
    clustering_id : str
        DEV-04 clustering id (must match ``^cl_[0-9a-f]{24}$``).
    preprocessed_id : str
        DEV-03 preprocessed id.
    dataset_id : str
        DEV-02 dataset id.
    ml_dataset_sha256 : str
        SHA-256 of the DEV-03 ML Dataset parquet.
    feature_set_sha256 : str
        SHA-256 of the sorted feature names (use
        :func:`compute_feature_set_sha256` to derive).
    preprocessing_config_sha256 : str
        SHA-256 of the DEV-03 preprocessing config (read from
        ``PreprocessedManifest.config_hash``).
    noise_policy : {"include", "exclude"}
        DBSCAN noise policy (per ADR-0006 prototype default = "exclude").
    schema_version : str, optional
        Manifest schema version (default
        :data:`SEGMENTATION_MANIFEST_SCHEMA_VERSION`).

    Returns
    -------
    str
        ``"seg_"`` + 24 hex characters.

    Raises
    ------
    Dev06StoragePathError
        If any input is invalid.
    """
    _validate_inputs(
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha256,
        feature_set_sha256=feature_set_sha256,
        preprocessing_config_sha256=preprocessing_config_sha256,
        noise_policy=noise_policy,
    )
    payload = _build_canonical_payload(
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha256,
        feature_set_sha256=feature_set_sha256,
        preprocessing_config_sha256=preprocessing_config_sha256,
        noise_policy=noise_policy,
        schema_version=schema_version,
    )
    payload_bytes = _canonical_payload_bytes(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    return SEGMENTATION_ID_PREFIX + digest[:SEGMENTATION_ID_HEX_LEN]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_storage_root(
    config_path: Path | str | None = None,
) -> Path:
    """Return DEV-06's storage root (shared with DEV-02/03/04/05).

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


def _validate_id_format(id_str: str, id_type: str) -> None:
    """Validate that an id matches the expected regex; raise otherwise."""
    if id_type == "segmentation":
        if not _SEGMENTATION_ID_RE.match(id_str):
            raise Dev06StoragePathError(
                f"segmentation_id {id_str!r} does not match required format "
                f"^seg_[0-9a-f]{{24}}$."
            )
    elif id_type == "clustering":
        if not _CLUSTERING_ID_RE.match(id_str):
            raise Dev06StoragePathError(
                f"clustering_id {id_str!r} does not match required format " f"^cl_[0-9a-f]{{24}}$."
            )
    else:
        raise Dev06StoragePathError(f"Unknown id_type: {id_type!r}")


def prototype_segmentation_base_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
) -> Path:
    """Return ``<storage_root>/.../clustering/<clustering_id>/segmentation/``.

    This is the container for all segmentation passes of one clustering run.
    It is NOT created by this function — callers use it to resolve
    individual ``segmentation_id`` subdirectories.

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root.
    dataset_id : str
        DEV-02 dataset id.
    preprocessed_id : str
        DEV-03 preprocessed id.
    clustering_id : str
        DEV-04 clustering id (must match ``^cl_[0-9a-f]{24}$``).

    Returns
    -------
    pathlib.Path
        Absolute path to the segmentation base directory.

    Raises
    ------
    Dev06StoragePathError
        If the resolved path escapes the storage root or id format invalid.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev06StoragePathError("dataset_id must be a non-empty string.")
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise Dev06StoragePathError("preprocessed_id must be a non-empty string.")
    _validate_id_format(clustering_id, "clustering")

    root = Path(storage_root).resolve()
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); append ``dataset_id``
    # directly (no extra ``"datasets"`` literal). Mirrors the canonical
    # layout produced by DEV-02/DEV-03/DEV-04 — see the regression test in
    # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    candidate = (
        root
        / dataset_id
        / "preprocessed"
        / preprocessed_id
        / "clustering"
        / clustering_id
        / "segmentation"
    ).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise Dev06StoragePathError(
            f"Computed segmentation base dir {candidate!s} is not inside " f"storage root {root!s}."
        ) from exc
    return candidate


def prototype_segmentation_run_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    segmentation_id: str,
) -> Path:
    """Return ``<base>/<segmentation_id>/`` (final published directory).

    Parameters
    ----------
    storage_root : pathlib.Path
        Resolved (absolute) storage root.
    dataset_id : str
        DEV-02 dataset id.
    preprocessed_id : str
        DEV-03 preprocessed id.
    clustering_id : str
        DEV-04 clustering id (must match ``^cl_[0-9a-f]{24}$``).
    segmentation_id : str
        Content-addressed segmentation id (must match ``^seg_[0-9a-f]{24}$``).

    Returns
    -------
    pathlib.Path
        Absolute path to the per-segmentation run directory.

    Raises
    ------
    Dev06StoragePathError
        If id format is invalid or path escapes storage root.
    """
    _validate_id_format(segmentation_id, "segmentation")
    base = prototype_segmentation_base_dir(storage_root, dataset_id, preprocessed_id, clustering_id)
    candidate = (base / segmentation_id).resolve()
    try:
        candidate.relative_to(Path(storage_root).resolve())
    except ValueError as exc:
        raise Dev06StoragePathError(
            f"Computed segmentation run dir {candidate!s} is not inside "
            f"storage root {Path(storage_root).resolve()!s}."
        ) from exc
    return candidate


# ---------------------------------------------------------------------------
# Idempotency lookup
# ---------------------------------------------------------------------------


def _extract_canonical_fields(
    manifest_data: dict[str, Any],
) -> dict[str, Any]:
    """Extract the 8 canonical fields from a stored segmentation manifest.

    The on-disk key for the noise policy is ``noise_policy_used``; the
    canonical payload uses ``noise_policy`` (per
    :func:`derive_segmentation_id`). We map between the two here so
    the storage layer never has to know about the manifest schema
    detail.

    Pure subset selection — no renaming beyond the noise_policy
    mapping. Raises :class:`Dev06ManifestCorrupt` if any required key
    is missing or has the wrong type.

    Raises
    ------
    Dev06ManifestCorrupt
        If manifest is missing a canonical key, has wrong type, or
        ``noise_policy`` / ``schema_version`` is not canonical.
    """
    # On-disk key for noise policy is "noise_policy_used"; map to canonical "noise_policy".
    source = dict(manifest_data)
    if "noise_policy" not in source and "noise_policy_used" in source:
        source["noise_policy"] = source["noise_policy_used"]
    out: dict[str, Any] = {}
    for key in CANONICAL_PAYLOAD_KEYS:
        if key not in source:
            raise Dev06ManifestCorrupt(
                f"Stored segmentation manifest is missing canonical key {key!r}."
            )
        value = source[key]
        expected = _CANONICAL_PAYLOAD_TYPES[key]
        if not isinstance(value, expected):
            raise Dev06ManifestCorrupt(
                f"Stored segmentation manifest has wrong type for {key!r}: "
                f"expected {expected!r}, got {type(value).__name__}."
            )
        out[key] = value
    # Validate noise_policy is in the closed set.
    if out["noise_policy"] not in NOISE_POLICIES:
        raise Dev06ManifestCorrupt(
            f"Stored segmentation manifest has invalid noise_policy: " f"{out['noise_policy']!r}."
        )
    # Validate schema_version is current.
    if out["schema_version"] != SEGMENTATION_MANIFEST_SCHEMA_VERSION:
        raise Dev06ManifestCorrupt(
            f"Stored segmentation manifest schema_version is {out['schema_version']!r}; "
            f"current version is {SEGMENTATION_MANIFEST_SCHEMA_VERSION!r}. "
            f"Re-run with --force-rerun to migrate."
        )
    return out


def find_existing_segmentation(
    *,
    base_dir: Path,
    segmentation_id: str,
    expected_canonical: dict[str, Any],
) -> tuple[bool, Path | None]:
    """Look for an existing segmentation at ``<base_dir>/<segmentation_id>/``.

    Parameters
    ----------
    base_dir : pathlib.Path
        Path returned by :func:`prototype_segmentation_base_dir`.
    segmentation_id : str
        Content-addressed id to look up.
    expected_canonical : dict
        8-field canonical payload expected to match the stored manifest.

    Returns
    -------
    tuple[bool, Path | None]
        ``(True, manifest_path)`` if found and canonical match
        (``CACHED``); ``(False, None)`` if directory does not exist
        (new run); raises :class:`Dev06ManifestCorrupt` on a manifest
        with wrong canonical payload (collision vs corruption), and
        :class:`Dev06CollisionError` on a stored id whose canonical
        payload differs from the expected one.

    Raises
    ------
    Dev06StoragePathError
        If id format invalid.
    Dev06ManifestCorrupt
        If manifest exists but is malformed (missing key / wrong type /
        invalid enum).
    Dev06CollisionError
        If manifest exists, parses, but its canonical payload differs
        from ``expected_canonical`` (fail-closed).
    """
    _validate_id_format(segmentation_id, "segmentation")
    run_dir = base_dir / segmentation_id
    manifest_path = run_dir / "segmentation_manifest.json"
    if not manifest_path.exists():
        return (False, None)
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise Dev06ManifestCorrupt(
            f"Failed to read segmentation manifest at {manifest_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise Dev06ManifestCorrupt(
            f"Segmentation manifest at {manifest_path} is not a JSON object."
        )
    stored_canonical = _extract_canonical_fields(data)
    # Compare canonical fields 1-by-1 (set equality with type check).
    for key in CANONICAL_PAYLOAD_KEYS:
        if stored_canonical[key] != expected_canonical[key]:
            raise Dev06CollisionError(
                f"segmentation_id {segmentation_id!r} already exists at "
                f"{run_dir} with a different {key!r}: stored="
                f"{stored_canonical[key]!r}, expected={expected_canonical[key]!r}. "
                f"Refusing to silently overwrite."
            )
    return (True, manifest_path)
