"""Storage, content-addressed identity, and idempotency helpers for DEV-05.

Responsibilities
---------------
1. Compute ``evaluation_id`` from a canonical JSON payload (8 fields).
2. Compute the per-evaluation ``evaluation/`` subdirectory under
   the DEV-04 ``<clustering_id>/`` run dir.
3. Resolve the DEV-02 storage root (shared with DEV-02/03/04).
4. Validate path containment (defence against path traversal).
5. Idempotency lookup (``find_existing_evaluation``) with collision
   detection and manifest-corruption handling.

Hard rules
-----------
- Storage root is loaded from ``configs/dev02_dataset_management.yaml``
  via ``customer_segmentation.dataset_management.storage.resolve_storage_root``.
  CLI does NOT expose ``--storage-root``.
- ``evaluation_id`` is always ``"ev_" + first 24 hex chars`` of
  SHA-256 of a canonical JSON object with 8 logical fields.
- All computed paths are validated to remain inside the resolved
  storage root (via ``Path.resolve()`` + ``relative_to()``).
- ``evaluation_id`` format is validated with regex
  ``^ev_[0-9a-f]{24}$`` before use in filesystem operations.
- ``clustering_id`` format is validated with regex
  ``^cl_[0-9a-f]{24}$`` (delegated to caller; never re-derive).

Canonical payload (8 fields for ``evaluation_id`` derivation)
-----------------------------------------------------------
``evaluation_id = "ev_" + SHA256(JSON canonical(
    clustering_id,            # ^cl_[0-9a-f]{24}$
    preprocessed_id,
    dataset_id,
    ml_dataset_sha256,
    config_sha256,           # DEV-05 config hash
    noise_policy,            # "include" | "exclude"
    metric_set_hash,         # SHA256 of sorted metric names
    schema_version,          # EVALUATION_MANIFEST_SCHEMA_VERSION
))[:24]``

``noise_policy`` canonical values:
- ``"exclude"`` (prototype default per ADR-0006) — DBSCAN noise rows
  filtered from X and labels before sklearn compute.
- ``"include"`` — no filter applied (sklearn default).

``metric_set_hash`` canonical value:
- 64-hex SHA-256 of ``frozenset(metric_names)`` joined in sorted order
  with a delimiter (e.g. ``"|"``). Default set = {silhouette,
  davies_bouldin, calinski_harabasz}.

``schema_version`` canonical value:
- :data:`EVALUATION_MANIFEST_SCHEMA_VERSION` (currently ``"1.0.0"``).
  A schema bump invalidates all old ``evaluation_id``s and forces re-run.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.evaluation.scope import (
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    METRIC_NAMES,
    NOISE_POLICIES,
)

__all__ = [
    "EVALUATION_ID_PREFIX",
    "EVALUATION_ID_HEX_LEN",
    "CANONICAL_PAYLOAD_KEYS",
    "Dev05CollisionError",
    "Dev05ManifestCorrupt",
    "Dev05StoragePathError",
    "compute_config_sha256",
    "compute_metric_set_hash",
    "derive_evaluation_id",
    "find_existing_evaluation",
    "prototype_evaluation_base_dir",
    "prototype_evaluation_run_dir",
    "resolve_storage_root",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVALUATION_ID_PREFIX: Final[str] = "ev_"
EVALUATION_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy

# Canonical payload key order (must match ``derive_evaluation_id``).
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "clustering_id",
    "preprocessed_id",
    "dataset_id",
    "ml_dataset_sha256",
    "config_sha256",
    "noise_policy",
    "metric_set_hash",
    "schema_version",
)

# Required types for round-trip validation.
_CANONICAL_PAYLOAD_TYPES: dict[str, type | tuple[type, ...]] = {
    "clustering_id": str,
    "preprocessed_id": str,
    "dataset_id": str,
    "ml_dataset_sha256": str,
    "config_sha256": str,
    "noise_policy": str,
    "metric_set_hash": str,
    "schema_version": str,
}

# Regex patterns for id validation.
_EVALUATION_ID_RE = re.compile(r"^ev_[0-9a-f]{24}$")
_CLUSTERING_ID_RE = re.compile(r"^cl_[0-9a-f]{24}$")

# Staging / backup / failed-tracking directory name patterns (mirror DEV-04).
_STAGING_BACKUP_FAILED_RE = re.compile(r"^_(staging|backup|failed)_[A-Za-z0-9_-]+$")
_BACKUP_CORRUPT_SUFFIX = "_corrupt"
_BACKUP_PREFIX = "_backup_"
_STAGING_PREFIX = "_staging_"
_FAILED_PREFIX = "_failed_"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev05StoragePathError(ValueError):
    """Raised on path / storage resolution failures."""


class Dev05ManifestCorrupt(ValueError):
    """Raised when an evaluation manifest exists but cannot be parsed.

    Fail-closed: the pipeline refuses to interpret a corrupt manifest
    as a valid idempotent hit or as a collision. The caller must
    abort (default) or use ``--force-recompute`` to recover.
    """


class Dev05CollisionError(ValueError):
    """Raised when an ``evaluation_id`` collision is detected.

    Two different effective configurations produced the same
    ``evaluation_id`` (extremely rare: ~10⁻¹⁸ probability at 10⁶ runs).
    The user must investigate manually.
    """


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------


def _canonical_scalar(v: Any) -> Any:
    """Canonicalize a scalar value through JSON round-trip."""
    return json.loads(json.dumps(v, ensure_ascii=False, allow_nan=False))


def _validate_inputs(
    *,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    ml_dataset_sha256: str,
    config_sha256: str,
    noise_policy: str,
    metric_set,
) -> None:
    """Validate all 8 canonical inputs; raise Dev05StoragePathError on failure."""
    if not isinstance(clustering_id, str) or not _CLUSTERING_ID_RE.match(clustering_id):
        raise Dev05StoragePathError(
            f"clustering_id {clustering_id!r} does not match required format "
            f"^cl_[0-9a-f]{{24}}$."
        )
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise Dev05StoragePathError(
            f"preprocessed_id must be a non-empty str; got {type(preprocessed_id).__name__}."
        )
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev05StoragePathError(
            f"dataset_id must be a non-empty str; got {type(dataset_id).__name__}."
        )
    if not isinstance(ml_dataset_sha256, str) or not ml_dataset_sha256:
        raise Dev05StoragePathError(
            f"ml_dataset_sha256 must be a non-empty str; "
            f"got {type(ml_dataset_sha256).__name__}."
        )
    if not isinstance(config_sha256, str) or not config_sha256:
        raise Dev05StoragePathError(
            f"config_sha256 must be a non-empty str; " f"got {type(config_sha256).__name__}."
        )
    if noise_policy not in NOISE_POLICIES:
        raise Dev05StoragePathError(
            f"noise_policy {noise_policy!r} is not in the closed set " f"{sorted(NOISE_POLICIES)}."
        )
    # metric_set must be subset of METRIC_NAMES and non-empty.
    if isinstance(metric_set, (set, frozenset)):
        ms: frozenset[str] = frozenset(metric_set)
    elif isinstance(metric_set, (list, tuple)):
        if not metric_set:
            raise Dev05StoragePathError("metric_set must be non-empty.")
        ms = frozenset(metric_set)
    else:
        raise Dev05StoragePathError(
            f"metric_set must be a list, tuple, set, or frozenset; "
            f"got {type(metric_set).__name__}."
        )
    if not ms:
        raise Dev05StoragePathError("metric_set must be non-empty.")
    unknown = ms - METRIC_NAMES
    if unknown:
        raise Dev05StoragePathError(
            f"metric_set contains unknown names: {sorted(unknown)}; "
            f"only {sorted(METRIC_NAMES)} are allowed."
        )


def _build_canonical_payload(
    *,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    ml_dataset_sha256: str,
    config_sha256: str,
    noise_policy: str,
    metric_set_hash: str,
    schema_version: str = EVALUATION_MANIFEST_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return the canonical 8-field payload object used for evaluation_id.

    Raises :class:`Dev05StoragePathError` on invalid inputs.
    """
    return {
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "ml_dataset_sha256": ml_dataset_sha256,
        "config_sha256": config_sha256,
        "noise_policy": noise_policy,
        "metric_set_hash": metric_set_hash,
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


def compute_metric_set_hash(metric_set) -> str:
    """Return the 64-hex SHA-256 of a metric set (sorted, ``|``-joined).

    The hash is order-independent (sort before joining) and content-only
    (no whitespace, no json envelope) so that {silhouette, davies_bouldin,
    calinski_harabasz} and {calinski_harabasz, davies_bouldin, silhouette}
    produce the same hash.

    Parameters
    ----------
    metric_set : iterable of str
        Any iterable of metric-name strings (subset of :data:`METRIC_NAMES`).
    """
    if isinstance(metric_set, (set, frozenset)):
        names = sorted(metric_set)
    elif isinstance(metric_set, (list, tuple)):
        names = sorted(metric_set)
    else:
        raise Dev05StoragePathError(
            f"metric_set must be a list, tuple, set, or frozenset; "
            f"got {type(metric_set).__name__}."
        )
    if not names:
        raise Dev05StoragePathError("metric_set must be non-empty.")
    for n in names:
        if n not in METRIC_NAMES:
            raise Dev05StoragePathError(
                f"metric name {n!r} is not in the closed set " f"{sorted(METRIC_NAMES)}."
            )
    joined = "|".join(names)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def derive_evaluation_id(
    *,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    ml_dataset_sha256: str,
    config_sha256: str,
    noise_policy: str,
    metric_set,
    schema_version: str = EVALUATION_MANIFEST_SCHEMA_VERSION,
) -> str:
    """Return ``"ev_" + first 24 hex chars`` of SHA-256 of canonical payload.

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
    config_sha256 : str
        SHA-256 of the DEV-05 config YAML at run time.
    noise_policy : {"include", "exclude"}
        DBSCAN noise policy (per ADR-0006 prototype default = "exclude").
    metric_set : iterable of str
        Closed set of metric names to compute (subset of
        :data:`METRIC_NAMES`).
    schema_version : str, optional
        Manifest schema version (default
        :data:`EVALUATION_MANIFEST_SCHEMA_VERSION`).

    Returns
    -------
    str
        ``"ev_"`` + 24 hex characters.

    Raises
    ------
    Dev05StoragePathError
        If any input is invalid.
    """
    _validate_inputs(
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha256,
        config_sha256=config_sha256,
        noise_policy=noise_policy,
        metric_set=metric_set,
    )
    metric_set_hash = compute_metric_set_hash(metric_set)
    payload = _build_canonical_payload(
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha256,
        config_sha256=config_sha256,
        noise_policy=noise_policy,
        metric_set_hash=metric_set_hash,
        schema_version=schema_version,
    )
    payload_bytes = _canonical_payload_bytes(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    return EVALUATION_ID_PREFIX + digest[:EVALUATION_ID_HEX_LEN]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_storage_root(
    config_path: Path | str | None = None,
) -> Path:
    """Return DEV-05's storage root (shared with DEV-02/03/04).

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
    if id_type == "evaluation":
        if not _EVALUATION_ID_RE.match(id_str):
            raise Dev05StoragePathError(
                f"evaluation_id {id_str!r} does not match required format " f"^ev_[0-9a-f]{{24}}$."
            )
    elif id_type == "clustering":
        if not _CLUSTERING_ID_RE.match(id_str):
            raise Dev05StoragePathError(
                f"clustering_id {id_str!r} does not match required format " f"^cl_[0-9a-f]{{24}}$."
            )
    else:
        raise Dev05StoragePathError(f"Unknown id_type: {id_type!r}")


def prototype_evaluation_base_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
) -> Path:
    """Return ``<storage_root>/.../clustering/<clustering_id>/evaluation/``.

    This is the container for all evaluation passes of one clustering run.
    It is NOT created by this function — callers use it to resolve
    individual ``evaluation_id`` subdirectories.

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
        Absolute path to the evaluation base directory.

    Raises
    ------
    Dev05StoragePathError
        If the resolved path escapes the storage root or id format invalid.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Dev05StoragePathError("dataset_id must be a non-empty string.")
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise Dev05StoragePathError("preprocessed_id must be a non-empty string.")
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
        / "evaluation"
    ).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise Dev05StoragePathError(
            f"Computed evaluation base dir {candidate!s} is not inside " f"storage root {root!s}."
        ) from exc
    return candidate


def prototype_evaluation_run_dir(
    storage_root: Path,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    evaluation_id: str,
) -> Path:
    """Return ``<base>/<evaluation_id>/`` (final published directory).

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
    evaluation_id : str
        Content-addressed evaluation id (must match ``^ev_[0-9a-f]{24}$``).

    Returns
    -------
    pathlib.Path
        Absolute path to the per-evaluation run directory.

    Raises
    ------
    Dev05StoragePathError
        If id format is invalid or path escapes storage root.
    """
    _validate_id_format(evaluation_id, "evaluation")
    base = prototype_evaluation_base_dir(storage_root, dataset_id, preprocessed_id, clustering_id)
    candidate = (base / evaluation_id).resolve()
    try:
        candidate.relative_to(Path(storage_root).resolve())
    except ValueError as exc:
        raise Dev05StoragePathError(
            f"Computed evaluation run dir {candidate!s} is not inside "
            f"storage root {Path(storage_root).resolve()!s}."
        ) from exc
    return candidate


def prototype_evaluation_metrics_path(
    run_dir: Path,
) -> Path:
    """Return the canonical ``metrics_long.csv`` path inside an evaluation run dir."""
    if not isinstance(run_dir, Path):
        raise Dev05StoragePathError("run_dir must be a Path.")
    return run_dir / "metrics_long.csv"


# ---------------------------------------------------------------------------
# Idempotency lookup
# ---------------------------------------------------------------------------


def _extract_canonical_fields(
    manifest_data: dict[str, Any],
) -> dict[str, Any]:
    """Extract the 8 canonical fields from a stored evaluation manifest.

    Pure subset selection — no renaming, no transformation. Raises
    :class:`Dev05ManifestCorrupt` if any required key is missing or
    has the wrong type.

    Raises
    ------
    Dev05ManifestCorrupt
        If manifest is missing a canonical key, has wrong type, or
        ``noise_policy`` / ``schema_version`` is not canonical.
    """
    out: dict[str, Any] = {}
    for key in CANONICAL_PAYLOAD_KEYS:
        if key not in manifest_data:
            raise Dev05ManifestCorrupt(
                f"Stored evaluation manifest is missing canonical key {key!r}."
            )
        value = manifest_data[key]
        expected = _CANONICAL_PAYLOAD_TYPES[key]
        if not isinstance(value, expected):
            raise Dev05ManifestCorrupt(
                f"Stored evaluation manifest has wrong type for {key!r}: "
                f"expected {expected!r}, got {type(value).__name__}."
            )
        out[key] = value
    # Validate noise_policy is in the closed set.
    if out["noise_policy"] not in NOISE_POLICIES:
        raise Dev05ManifestCorrupt(
            f"Stored evaluation manifest has invalid noise_policy: " f"{out['noise_policy']!r}."
        )
    # Validate schema_version is current.
    if out["schema_version"] != EVALUATION_MANIFEST_SCHEMA_VERSION:
        raise Dev05ManifestCorrupt(
            f"Stored evaluation manifest schema_version is {out['schema_version']!r}; "
            f"current version is {EVALUATION_MANIFEST_SCHEMA_VERSION!r}. "
            f"Re-run with --force-recompute to migrate."
        )
    return out


def find_existing_evaluation(
    *,
    base_dir: Path,
    evaluation_id: str,
    expected_canonical: dict[str, Any],
) -> tuple[bool, Path | None]:
    """Look for an existing evaluation at ``<base_dir>/<evaluation_id>/``.

    Parameters
    ----------
    base_dir : pathlib.Path
        Path returned by :func:`prototype_evaluation_base_dir`.
    evaluation_id : str
        Content-addressed id to look up.
    expected_canonical : dict
        8-field canonical payload expected to match the stored manifest.

    Returns
    -------
    tuple[bool, Path | None]
        ``(True, manifest_path)`` if found and canonical match
        (``CACHED``); ``(False, None)`` if directory does not exist
        (new run); raises :class:`Dev05ManifestCorrupt` on a manifest
        with wrong canonical payload (collision vs corruption), and
        :class:`Dev05CollisionError` on a stored id whose canonical
        payload differs from the expected one.

    Raises
    ------
    Dev05StoragePathError
        If id format invalid.
    Dev05ManifestCorrupt
        If manifest exists but is malformed (missing key / wrong type /
        invalid enum).
    Dev05CollisionError
        If manifest exists, parses, but its canonical payload differs
        from ``expected_canonical`` (fail-closed per R-16).
    """
    _validate_id_format(evaluation_id, "evaluation")
    run_dir = base_dir / evaluation_id
    manifest_path = run_dir / "evaluation_manifest.json"
    if not manifest_path.exists():
        return (False, None)
    try:
        with manifest_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise Dev05ManifestCorrupt(
            f"Failed to read evaluation manifest at {manifest_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise Dev05ManifestCorrupt(f"Evaluation manifest at {manifest_path} is not a JSON object.")
    stored_canonical = _extract_canonical_fields(data)
    # Compare canonical fields 1-by-1 (set equality with type check).
    for key in CANONICAL_PAYLOAD_KEYS:
        if stored_canonical[key] != expected_canonical[key]:
            raise Dev05CollisionError(
                f"evaluation_id {evaluation_id!r} already exists at "
                f"{run_dir} with a different {key!r}: stored="
                f"{stored_canonical[key]!r}, expected={expected_canonical[key]!r}. "
                f"Refusing to silently overwrite."
            )
    return (True, manifest_path)
