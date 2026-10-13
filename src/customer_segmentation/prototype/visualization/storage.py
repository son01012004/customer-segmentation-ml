"""Storage and path-resolution helpers for DEV-08 Prototype Visualization.

Responsibilities
----------------
1. Resolve the DEV-02 storage root (shared with DEV-02..07).
2. Compute the per-segmentation visualization subdirectory
   (``<seg_dir>/visualization/<dashboard_id>/``).
3. Resolve the parent ``visualization/`` container directory (for
   scans).
4. Validate path containment (defence against path traversal).
5. Validate id formats for content-addressed identifiers.

Hard rules
----------
- The storage root is loaded from ``configs/dev02_dataset_management.yaml``
  via ``customer_segmentation.dataset_management.storage``.
  CLI does NOT expose ``--storage-root``.
- ``dashboard_id`` is always ``"viz_" + first 24 hex chars`` of
  SHA-256 of a canonical JSON object. The fields that determine the
  id are:
    ``(segmentation_id, clustering_id, preprocessed_id, dataset_id,
       schema_version, config_sha256)``.
  A schema bump invalidates old ``dashboard_id``s and forces re-run.
- All computed paths are validated to remain inside the resolved
  storage root (via ``Path.resolve()`` + ``relative_to()``).
- ``dashboard_id`` format is validated with regex
  ``^viz_[0-9a-f]{24}$`` before use in filesystem operations.
- ``segmentation_id`` / ``clustering_id`` formats are inherited from
  the DEV-06 / DEV-04 contracts; the regexes here are the single
  source of truth for visualization-layer validation.

Canonical payload (6 fields for ``dashboard_id`` derivation)
-----------------------------------------------------------
``dashboard_id = "viz_" + SHA256(JSON canonical(
    segmentation_id,            # ^seg_[0-9a-f]{24}$
    clustering_id,              # ^cl_[0-9a-f]{24}$
    preprocessed_id,
    dataset_id,
    schema_version,             # VISUALIZATION_SCHEMA_VERSION
    config_sha256,              # SHA of the DEV-08 config YAML
))[:24]``
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationStoragePathError,
)
from customer_segmentation.prototype.visualization.scope import (
    VISUALIZATION_SCHEMA_VERSION,
)

__all__ = [
    "DASHBOARD_ID_PREFIX",
    "DASHBOARD_ID_HEX_LEN",
    "CANONICAL_PAYLOAD_KEYS",
    "compute_config_sha256",
    "derive_dashboard_id",
    "prototype_visualization_base_dir",
    "prototype_visualization_run_dir",
    "resolve_storage_root",
    "VisualizationConfigError",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DASHBOARD_ID_PREFIX: Final[str] = "viz_"
DASHBOARD_ID_HEX_LEN: Final[int] = 24  # 96 bits of content-addressed entropy

# Canonical payload key order (must match ``derive_dashboard_id``).
CANONICAL_PAYLOAD_KEYS: tuple[str, ...] = (
    "segmentation_id",
    "clustering_id",
    "preprocessed_id",
    "dataset_id",
    "schema_version",
    "config_sha256",
)

# Required types for round-trip validation.
_CANONICAL_PAYLOAD_TYPES: dict[str, type | tuple[type, ...]] = {
    "segmentation_id": str,
    "clustering_id": str,
    "preprocessed_id": str,
    "dataset_id": str,
    "schema_version": str,
    "config_sha256": str,
}

# Regex patterns for id validation.
_DASHBOARD_ID_RE = re.compile(r"^viz_[0-9a-f]{24}$")
_SEGMENTATION_ID_RE = re.compile(r"^seg_[0-9a-f]{24}$")
_CLUSTERING_ID_RE = re.compile(r"^cl_[0-9a-f]{24}$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VisualizationConfigError(ValueError):
    """Raised on invalid DEV-08 visualization config payloads."""


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------


def _validate_inputs(
    *,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    config_sha256: str,
) -> None:
    """Validate all 6 canonical inputs; raise on failure."""
    if not isinstance(segmentation_id, str) or not _SEGMENTATION_ID_RE.match(segmentation_id):
        raise VisualizationStoragePathError(
            f"segmentation_id {segmentation_id!r} does not match required format "
            f"^seg_[0-9a-f]{{24}}$."
        )
    if not isinstance(clustering_id, str) or not _CLUSTERING_ID_RE.match(clustering_id):
        raise VisualizationStoragePathError(
            f"clustering_id {clustering_id!r} does not match required format "
            f"^cl_[0-9a-f]{{24}}$."
        )
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise VisualizationStoragePathError(
            f"preprocessed_id must be a non-empty str; got {type(preprocessed_id).__name__}."
        )
    if not isinstance(dataset_id, str) or not dataset_id:
        raise VisualizationStoragePathError(
            f"dataset_id must be a non-empty str; got {type(dataset_id).__name__}."
        )
    if not isinstance(config_sha256, str) or not config_sha256:
        raise VisualizationStoragePathError(
            f"config_sha256 must be a non-empty str; got {type(config_sha256).__name__}."
        )


def _build_canonical_payload(
    *,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    config_sha256: str,
    schema_version: str = VISUALIZATION_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return the canonical 6-field payload object used for dashboard_id."""
    return {
        "segmentation_id": segmentation_id,
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "schema_version": schema_version,
        "config_sha256": config_sha256,
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
    if not isinstance(config_text, str):
        raise VisualizationStoragePathError(
            f"config_text must be a str; got {type(config_text).__name__}."
        )
    return hashlib.sha256(config_text.encode("utf-8")).hexdigest()


def derive_dashboard_id(
    *,
    segmentation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    config_sha256: str,
    schema_version: str = VISUALIZATION_SCHEMA_VERSION,
) -> str:
    """Return ``"viz_" + first 24 hex chars`` of SHA-256 of canonical payload.

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
    config_sha256 : str
        SHA-256 of the DEV-08 config YAML (use
        :func:`compute_config_sha256` to derive).
    schema_version : str, optional
        Manifest schema version (default
        :data:`VISUALIZATION_SCHEMA_VERSION`).

    Returns
    -------
    str
        ``"viz_"`` + 24 hex characters.

    Raises
    ------
    VisualizationStoragePathError
        If any input is invalid.
    """
    _validate_inputs(
        segmentation_id=segmentation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        config_sha256=config_sha256,
    )
    payload = _build_canonical_payload(
        segmentation_id=segmentation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        config_sha256=config_sha256,
        schema_version=schema_version,
    )
    payload_bytes = _canonical_payload_bytes(payload)
    digest = hashlib.sha256(payload_bytes).hexdigest()
    return DASHBOARD_ID_PREFIX + digest[:DASHBOARD_ID_HEX_LEN]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_storage_root(
    config_path: Path | str | None = None,
) -> Path:
    """Return DEV-08's storage root (shared with DEV-02..07).

    The storage root is loaded from
    ``configs/dev02_dataset_management.yaml`` via the DEV-02 storage
    module. ``config_path`` may override the canonical config when a
    caller imported via ``--config <custom>``.
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
    if id_type == "dashboard":
        if not _DASHBOARD_ID_RE.match(id_str):
            raise VisualizationStoragePathError(
                f"dashboard_id {id_str!r} does not match required format " f"^viz_[0-9a-f]{{24}}$."
            )
    elif id_type == "segmentation":
        if not _SEGMENTATION_ID_RE.match(id_str):
            raise VisualizationStoragePathError(
                f"segmentation_id {id_str!r} does not match required format "
                f"^seg_[0-9a-f]{{24}}$."
            )
    elif id_type == "clustering":
        if not _CLUSTERING_ID_RE.match(id_str):
            raise VisualizationStoragePathError(
                f"clustering_id {id_str!r} does not match required format " f"^cl_[0-9a-f]{{24}}$."
            )
    else:
        raise VisualizationStoragePathError(f"Unknown id_type: {id_type!r}")


def prototype_visualization_base_dir(
    storage_root: Path,
    *,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    segmentation_id: str,
) -> Path:
    """Return ``<seg_dir>/visualization/`` (container for all dashboards).

    This is the container for all visualization dashboard passes of
    one segmentation. It is NOT created by this function — callers
    use it to resolve individual ``dashboard_id`` subdirectories.

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
        Absolute path to the visualization base directory.

    Raises
    ------
    VisualizationStoragePathError
        If the resolved path escapes the storage root or id format invalid.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise VisualizationStoragePathError("dataset_id must be a non-empty string.")
    if not isinstance(preprocessed_id, str) or not preprocessed_id:
        raise VisualizationStoragePathError("preprocessed_id must be a non-empty string.")
    _validate_id_format(clustering_id, "clustering")
    _validate_id_format(segmentation_id, "segmentation")

    root = Path(storage_root).resolve()
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); append ``dataset_id``
    # directly (no extra ``"datasets"`` literal). Mirrors the canonical
    # layout produced by DEV-02/DEV-03/DEV-04/DEV-08 — see the regression
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
        / "visualization"
    ).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise VisualizationStoragePathError(
            f"Computed visualization base dir {candidate!s} is not inside "
            f"storage root {root!s}."
        ) from exc
    return candidate


def prototype_visualization_run_dir(
    storage_root: Path,
    *,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    segmentation_id: str,
    dashboard_id: str,
) -> Path:
    """Return ``<base>/<dashboard_id>/`` (final published directory).

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
    dashboard_id : str
        Content-addressed dashboard id (must match
        ``^viz_[0-9a-f]{24}$``).

    Returns
    -------
    pathlib.Path
        Absolute path to the per-dashboard run directory.

    Raises
    ------
    VisualizationStoragePathError
        If id format is invalid or path escapes storage root.
    """
    _validate_id_format(dashboard_id, "dashboard")
    base = prototype_visualization_base_dir(
        storage_root,
        dataset_id=dataset_id,
        preprocessed_id=preprocessed_id,
        clustering_id=clustering_id,
        segmentation_id=segmentation_id,
    )
    candidate = (base / dashboard_id).resolve()
    try:
        candidate.relative_to(Path(storage_root).resolve())
    except ValueError as exc:
        raise VisualizationStoragePathError(
            f"Computed visualization run dir {candidate!s} is not inside "
            f"storage root {Path(storage_root).resolve()!s}."
        ) from exc
    return candidate
