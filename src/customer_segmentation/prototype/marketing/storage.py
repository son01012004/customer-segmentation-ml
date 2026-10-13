"""Storage, content-addressed identity, and idempotency helpers for DEV-07.

Responsibilities
----------------
1. Compute ``marketing_id`` from a canonical JSON payload (9 fields).
2. Compute the per-recommendation ``marketing/<marketing_id>/``
   subdirectory under the DEV-06 ``<segmentation_id>/`` run dir.
3. Resolve the DEV-02 storage root (shared with DEV-02/03/04/05/06).
4. Validate path containment (defence against path traversal).
5. Idempotency lookup (``find_existing_marketing``) with collision
   detection and manifest-corruption handling.

Hard rules
----------
- Storage root is loaded from ``configs/dev02_dataset_management.yaml``
  via ``customer_segmentation.dataset_management.storage.resolve_storage_root``.
  CLI does NOT expose ``--storage-root``.
- ``marketing_id`` is always ``"mkt_" + first 24 hex chars`` of
  SHA-256 of a canonical JSON object with 9 logical fields.
- All computed paths are validated to remain inside the resolved
  storage root (via ``Path.resolve()`` + ``relative_to()``).
- ``marketing_id`` format is validated with regex
  ``^mkt_[0-9a-f]{24}$`` before use in filesystem operations.
- ``segmentation_id`` format is validated with regex
  ``^seg_[0-9a-f]{24}$`` (delegated to caller; never re-derive).
- :data:`CANONICAL_PAYLOAD_KEYS` lists the 9 fields that determine
  ``marketing_id``. Bumping the schema version invalidates all
  previous ``marketing_id``s (defence against silently reinterpreting
  old manifests).

Canonical payload (9 fields for ``marketing_id`` derivation)
------------------------------------------------------------
``marketing_id = "mkt_" + SHA256(JSON canonical(
    segmentation_id,                # ^seg_[0-9a-f]{24}$
    clustering_id,                  # ^cl_[0-9a-f]{24}$
    preprocessed_id,
    dataset_id,
    segmentation_manifest_sha256,   # SHA of the DEV-06 manifest file
    mkt_framework_version,          # null (Phase A) | "MKT-01..05__vN" (Phase B)
    mkt_framework_found,            # bool
    noise_policy_used,              # inherited from DEV-06 manifest
    schema_version,                 # MARKETING_MANIFEST_SCHEMA_VERSION
))[:24]``
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.marketing.exceptions import (
    MarketingCollisionError,
    MarketingManifestCorrupt,
    MarketingStoragePathError,
)
from customer_segmentation.prototype.marketing.scope import (
    AVAILABILITY_STATUSES,
    MARKETING_MANIFEST_SCHEMA_VERSION,
    NOISE_POLICIES,
)

__all__ = [
    "MARKETING_ID_PREFIX",
    "MARKETING_ID_HEX_LEN",
    "CANONICAL_PAYLOAD_KEYS",
    "compute_config_sha256",
    "derive_marketing_id",
    "find_existing_marketing",
    "prototype_marketing_base_dir",
    "prototype_marketing_run_dir",
    "resolve_storage_root",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKETING_ID_PREFIX: Final[str] = "mkt_"
MARKETING_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy

# Canonical payload key order (must match ``derive_marketing_id``).
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "segmentation_id",
    "clustering_id",
    "preprocessed_id",
    "dataset_id",
    "segmentation_manifest_sha256",
    "mkt_framework_version",
    "mkt_framework_found",
    "noise_policy_used",
    "schema_version",
)

# Required types for round-trip validation.
_CANONICAL_PAYLOAD_TYPES: dict[str, type | tuple[type, ...]] = {
    "segmentation_id": str,
    "clustering_id": str,
    "preprocessed_id": str,
    "dataset_id": str,
    "segmentation_manifest_sha256": str,
    "mkt_framework_version": (str, type(None)),
    "mkt_framework_found": bool,
    "noise_policy_used": str,
    "schema_version": str,
}

# Regex patterns for id validation.
_MARKETING_ID_RE = re.compile(r"^mkt_[0-9a-f]{24}$")
_SEGMENTATION_ID_RE = re.compile(r"^seg_[0-9a-f]{24}$")
_CLUSTERING_ID_RE = re.compile(r"^cl_[0-9a-f]{24}$")


# ---------------------------------------------------------------------------
# Errors (re-exported via exceptions module; raised here directly)
# ---------------------------------------------------------------------------

# Errors are imported above; names re-exported for documentation only.


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------


def _validate_inputs(
    *,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    segmentation_manifest_sha256: str,
    mkt_framework_version: str | None,
    mkt_framework_found: bool,
    noise_policy_used: str,
) -> None:
    """Validate all 9 canonical inputs; raise ``MarketingStoragePathError`` on failure."""
    if not isinstance(segmentation_id, str) or not _SEGMENTATION_ID_RE.match(segmentation_id):
        raise MarketingStoragePathError(
            f"segmentation_id {segmentation_id!r} does not match required format "
            f"^seg_[0-9a-f]{{24}}$."
        )
    if not isinstance(clustering_id, str) or not _CLUSTERING_ID_RE.match(clustering_id):
        raise MarketingStoragePathError(
            f"clustering_id {clustering_id!r} does not match required format "
            f"^cl_[0-9a-f]{{24}}$."
        )
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise MarketingStoragePathError(
            f"preprocessed_id must be a non-empty str; got {type(preprocessed_id).__name__}."
        )
    if not isinstance(dataset_id, str) or not dataset_id:
        raise MarketingStoragePathError(
            f"dataset_id must be a non-empty str; got {type(dataset_id).__name__}."
        )
    if not isinstance(segmentation_manifest_sha256, str) or not segmentation_manifest_sha256:
        raise MarketingStoragePathError(
            f"segmentation_manifest_sha256 must be a non-empty str; "
            f"got {type(segmentation_manifest_sha256).__name__}."
        )
    if mkt_framework_version is not None and (
        not isinstance(mkt_framework_version, str) or not mkt_framework_version
    ):
        raise MarketingStoragePathError(
            f"mkt_framework_version must be a non-empty str or None; "
            f"got {type(mkt_framework_version).__name__}."
        )
    if not isinstance(mkt_framework_found, bool):
        raise MarketingStoragePathError(
            f"mkt_framework_found must be a bool; got {type(mkt_framework_found).__name__}."
        )
    if not isinstance(noise_policy_used, str) or noise_policy_used not in NOISE_POLICIES:
        raise MarketingStoragePathError(
            f"noise_policy_used {noise_policy_used!r} is not in the closed set "
            f"{sorted(NOISE_POLICIES)}."
        )


def _build_canonical_payload(
    *,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    segmentation_manifest_sha256: str,
    mkt_framework_version: str | None,
    mkt_framework_found: bool,
    noise_policy_used: str,
    schema_version: str = MARKETING_MANIFEST_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return the canonical 9-field payload object used for marketing_id."""
    return {
        "segmentation_id": segmentation_id,
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "segmentation_manifest_sha256": segmentation_manifest_sha256,
        "mkt_framework_version": mkt_framework_version,
        "mkt_framework_found": mkt_framework_found,
        "noise_policy_used": noise_policy_used,
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


def derive_marketing_id(
    *,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    segmentation_manifest_sha256: str,
    mkt_framework_version: str | None,
    mkt_framework_found: bool,
    noise_policy_used: str,
    schema_version: str = MARKETING_MANIFEST_SCHEMA_VERSION,
) -> str:
    """Return ``"mkt_" + first 24 hex chars`` of SHA-256 of canonical payload.

    Parameters
    ----------
    segmentation_id : str
        DEV-06 segmentation id (must match ``^seg_[0-9a-f]{24}$``).
    clustering_id : str
        DEV-04 clustering id (must match ``^cl_[0-9a-f]{24}$``).
    preprocessed_id : str
        DEV-03 preprocessed id.
    dataset_id : str
        DEV-02 dataset id.
    segmentation_manifest_sha256 : str
        SHA-256 of the DEV-06 ``segmentation_manifest.json`` file.
    mkt_framework_version : str or None
        MKT framework version (None for Phase A; populated in Phase B).
    mkt_framework_found : bool
        Whether MKT framework was located in the expected path.
    noise_policy_used : str
        Noise policy inherited from DEV-06 manifest
        (``"include"`` / ``"exclude"`` / ``"n/a"``).
    schema_version : str, optional
        Manifest schema version (default
        :data:`MARKETING_MANIFEST_SCHEMA_VERSION`).

    Returns
    -------
    str
        ``"mkt_"`` + 24 hex characters.

    Raises
    ------
    MarketingStoragePathError
        If any input is invalid.
    """
    _validate_inputs(
        segmentation_id=segmentation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        segmentation_manifest_sha256=segmentation_manifest_sha256,
        mkt_framework_version=mkt_framework_version,
        mkt_framework_found=mkt_framework_found,
        noise_policy_used=noise_policy_used,
    )
    payload = _build_canonical_payload(
        segmentation_id=segmentation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        segmentation_manifest_sha256=segmentation_manifest_sha256,
        mkt_framework_version=mkt_framework_version,
        mkt_framework_found=mkt_framework_found,
        noise_policy_used=noise_policy_used,
        schema_version=schema_version,
    )
    payload_bytes = _canonical_payload_bytes(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    return MARKETING_ID_PREFIX + digest[:MARKETING_ID_HEX_LEN]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_storage_root() -> Path:
    """Return DEV-07's storage root (shared with DEV-02/03/04/05/06).

    The storage root is loaded from ``configs/dev02_dataset_management.yaml``
    via the DEV-02 storage module.
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

    cfg = load_dev02_config(DEFAULT_DEV02_CONFIG_PATH)
    return resolve_dev02_storage_root(cfg)


def _validate_id_format(id_str: str, id_type: str) -> None:
    """Validate that an id matches the expected regex; raise otherwise."""
    if id_type == "marketing":
        if not _MARKETING_ID_RE.match(id_str):
            raise MarketingStoragePathError(
                f"marketing_id {id_str!r} does not match required format " f"^mkt_[0-9a-f]{{24}}$."
            )
    elif id_type == "segmentation":
        if not _SEGMENTATION_ID_RE.match(id_str):
            raise MarketingStoragePathError(
                f"segmentation_id {id_str!r} does not match required format "
                f"^seg_[0-9a-f]{{24}}$."
            )
    elif id_type == "clustering":
        if not _CLUSTERING_ID_RE.match(id_str):
            raise MarketingStoragePathError(
                f"clustering_id {id_str!r} does not match required format " f"^cl_[0-9a-f]{{24}}$."
            )
    else:
        raise MarketingStoragePathError(f"Unknown id_type: {id_type!r}")


def prototype_marketing_base_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    segmentation_id: str,
) -> Path:
    """Return ``<seg_dir>/marketing/`` (container for all marketing passes).

    This is the container for all marketing recommendation passes of
    one segmentation. It is NOT created by this function — callers
    use it to resolve individual ``marketing_id`` subdirectories.

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
        DEV-06 segmentation id (must match ``^seg_[0-9a-f]{24}$``).

    Returns
    -------
    pathlib.Path
        Absolute path to the marketing base directory.

    Raises
    ------
    MarketingStoragePathError
        If the resolved path escapes the storage root or id format invalid.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise MarketingStoragePathError("dataset_id must be a non-empty string.")
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise MarketingStoragePathError("preprocessed_id must be a non-empty string.")
    _validate_id_format(clustering_id, "clustering")
    _validate_id_format(segmentation_id, "segmentation")

    root = Path(storage_root).resolve()
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); the dataset id is
    # appended directly (no extra ``"datasets"`` literal). Mirrors the
    # canonical on-disk layout produced by DEV-02..08 — see the regression
    # test in ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    candidate = (
        root
        / dataset_id
        / "preprocessed"
        / preprocessed_id
        / "clustering"
        / clustering_id
        / "segmentation"
        / segmentation_id
        / "marketing"
    ).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MarketingStoragePathError(
            f"Computed marketing base dir {candidate!s} is not inside " f"storage root {root!s}."
        ) from exc
    return candidate


def prototype_marketing_run_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    segmentation_id: str,
    marketing_id: str,
) -> Path:
    """Return ``<base>/<marketing_id>/`` (final published directory)."""
    _validate_id_format(marketing_id, "marketing")
    base = prototype_marketing_base_dir(
        storage_root, dataset_id, preprocessed_id, clustering_id, segmentation_id
    )
    candidate = (base / marketing_id).resolve()
    try:
        candidate.relative_to(Path(storage_root).resolve())
    except ValueError as exc:
        raise MarketingStoragePathError(
            f"Computed marketing run dir {candidate!s} is not inside "
            f"storage root {Path(storage_root).resolve()!s}."
        ) from exc
    return candidate


# ---------------------------------------------------------------------------
# Idempotency lookup
# ---------------------------------------------------------------------------


def _extract_canonical_fields(manifest_data: dict[str, Any]) -> dict[str, Any]:
    """Extract the 9 canonical fields from a stored marketing manifest.

    Maps between the on-disk schema name (``source_framework_version``)
    and the canonical payload name (``mkt_framework_version``). The
    on-disk schema is the source of truth for the manifest; the
    canonical payload name is used for the ``marketing_id`` derivation.

    Raises :class:`MarketingManifestCorrupt` if any required key is
    missing or has the wrong type.
    """
    # On-disk key for mkt_framework_version is "source_framework_version";
    # map to canonical "mkt_framework_version" (used in
    # derive_marketing_id). Similarly, mkt_framework_found has no
    # schema-level alias; use the manifest's own field directly.
    source = dict(manifest_data)
    if "mkt_framework_version" not in source and "source_framework_version" in source:
        source["mkt_framework_version"] = source["source_framework_version"]
    out: dict[str, Any] = {}
    for key in CANONICAL_PAYLOAD_KEYS:
        if key not in source:
            raise MarketingManifestCorrupt(
                f"Stored marketing manifest is missing canonical key {key!r}."
            )
        value = source[key]
        expected = _CANONICAL_PAYLOAD_TYPES[key]
        if not isinstance(value, expected):
            raise MarketingManifestCorrupt(
                f"Stored marketing manifest has wrong type for {key!r}: "
                f"expected {expected!r}, got {type(value).__name__}."
            )
        out[key] = value
    if out["noise_policy_used"] not in NOISE_POLICIES:
        raise MarketingManifestCorrupt(
            f"Stored marketing manifest has invalid noise_policy_used: "
            f"{out['noise_policy_used']!r}."
        )
    if out["schema_version"] != MARKETING_MANIFEST_SCHEMA_VERSION:
        raise MarketingManifestCorrupt(
            f"Stored marketing manifest schema_version is {out['schema_version']!r}; "
            f"current version is {MARKETING_MANIFEST_SCHEMA_VERSION!r}. "
            f"Re-run to migrate."
        )
    return out


def find_existing_marketing(
    *,
    base_dir: Path,
    marketing_id: str,
    expected_canonical: dict[str, Any],
) -> tuple[bool, Path | None]:
    """Look for an existing marketing manifest at ``<base_dir>/<marketing_id>/``.

    Parameters
    ----------
    base_dir : pathlib.Path
        Path returned by :func:`prototype_marketing_base_dir`.
    marketing_id : str
        Content-addressed id to look up.
    expected_canonical : dict
        9-field canonical payload expected to match the stored manifest.

    Returns
    -------
    tuple[bool, Path | None]
        ``(True, manifest_path)`` if found and canonical match
        (``CACHED``); ``(False, None)`` if directory does not exist
        (new run); raises :class:`MarketingManifestCorrupt` on a
        manifest with wrong canonical payload (corruption), and
        :class:`MarketingCollisionError` on a stored id whose
        canonical payload differs from the expected one.

    Raises
    ------
    MarketingStoragePathError
        If id format invalid.
    MarketingManifestCorrupt
        If manifest exists but is malformed.
    MarketingCollisionError
        If manifest exists, parses, but its canonical payload
        differs from ``expected_canonical`` (fail-closed).
    """
    _validate_id_format(marketing_id, "marketing")
    run_dir = base_dir / marketing_id
    manifest_path = run_dir / "marketing_manifest.json"
    if not manifest_path.exists():
        return (False, None)
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketingManifestCorrupt(
            f"Failed to read marketing manifest at {manifest_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise MarketingManifestCorrupt(
            f"Marketing manifest at {manifest_path} is not a JSON object."
        )
    stored_canonical = _extract_canonical_fields(data)
    for key in CANONICAL_PAYLOAD_KEYS:
        if stored_canonical[key] != expected_canonical[key]:
            raise MarketingCollisionError(
                f"marketing_id {marketing_id!r} already exists at {run_dir} with "
                f"a different {key!r}: stored={stored_canonical[key]!r}, "
                f"expected={expected_canonical[key]!r}. Refusing to silently overwrite."
            )
    return (True, manifest_path)
