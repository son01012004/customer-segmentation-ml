"""ClusteringManifest schema, JSON I/O, and stable/runtime classification.

A :class:`ClusteringManifest` is the on-disk sidecar of one DEV-04
clustering run. It records:

- ``clustering_id`` (content-addressed from 7 canonical fields),
- ``preprocessed_id`` + ``ml_dataset_sha256`` (DEV-03 pointer),
- ``algorithm`` + ``algorithm_version`` + ``algorithm_family``,
- ``experiment_id``,
- ``hyperparameters`` (effective, after CLI merge),
- ``seed_policy`` + ``seed`` (canonical),
- ``config_sha256``,
- artifact paths (relative),
- ``n_clusters`` + ``n_samples`` + ``feature_set``,
- ``input_identity``,
- ``environment``,
- ``research_safety`` (always
  ``automatically_promoted_to_research=false``,
  ``scope="CLUSTERED_PROTOTYPE"``).

The manifest is split into two field groups:

- **Stable** — equal across runs of the same input + same config.
- **Runtime** — may differ across runs
  (``created_utc``, ``last_seen_utc``, ``environment``).

Hard rules
----------
- A manifest is **only** written after a successful
  ``runner.run()`` (status = SUCCESS). Failed runs do NOT leave a
  manifest.
- The manifest writer uses **atomic write** (temp file + rename)
  to avoid partial writes.
- The ``clustering_id`` is always derived from the 7-field canonical
  payload (see :func:`storage.derive_clustering_id`).
- ``seed_policy`` canonical values: ``"stochastic"`` |
  ``"deterministic"`` (mirror ML-01 ``supports_random_state()``).
- ``seed`` is always ``null`` for deterministic algorithms.
- ``research_safety`` block is **always**:
  ``automatically_promoted_to_research=false``,
  ``scope="CLUSTERED_PROTOTYPE"``,
  ``appeared_in_research_evidence=false``.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from customer_segmentation.clustering.result import (
    AlgorithmFamily,
    ExperimentResult,
)

__all__ = [
    "CLUSTERING_MANIFEST_SCHEMA_VERSION",
    "ClusteringManifest",
    "ClusteringManifestError",
    "read_clustering_manifest",
    "stable_field_names",
    "runtime_field_names",
    "write_clustering_manifest",
    "now_utc_iso",
]


CLUSTERING_MANIFEST_SCHEMA_VERSION: Final[str] = "1.0.0"


class ClusteringManifestError(ValueError):
    """Raised on manifest construction / I/O failures."""


# ---------------------------------------------------------------------------
# Stable / runtime classification
# ---------------------------------------------------------------------------

_STABLE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "clustering_id",
        "scope",
        "preprocessed_id",
        "ml_dataset_sha256",
        "algorithm",
        "algorithm_version",
        "algorithm_family",
        "experiment_id",
        "experiment_log_path",
        "cluster_labels_path",
        "algorithm_output_path",
        "log_file",
        "n_clusters",
        "n_samples",
        "feature_set",
        "feature_count",
        "input_identity",
        "research_safety",
        # canonical fields also stable:
        "hyperparameters",
        "seed_policy",
        "seed",
        "config_sha256",
    }
)

_RUNTIME_FIELDS: Final[frozenset[str]] = frozenset({"created_utc", "last_seen_utc", "environment"})


def stable_field_names() -> frozenset[str]:
    """Return the set of stable field names."""
    return _STABLE_FIELDS


def runtime_field_names() -> frozenset[str]:
    """Return the set of runtime field names."""
    return _RUNTIME_FIELDS


# ---------------------------------------------------------------------------
# Sub-blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchSafetyBlock:
    """Research-safety markers (always prototype scope)."""

    automatically_promoted_to_research: bool
    scope: str
    appeared_in_research_evidence: bool
    read_only_paths_unmodified: list[str]


@dataclass(frozen=True)
class InputIdentityBlock:
    """Identity of the source ML Dataset."""

    dataset_sha256: str
    input_path: str
    metadata_path: str


@dataclass(frozen=True)
class EnvironmentBlock:
    """Runtime environment snapshot."""

    python: str
    platform: str
    release: str
    machine: str
    key_libraries: dict[str, str]


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClusteringManifest:
    """On-disk manifest of one DEV-04 clustering run."""

    schema_version: str
    clustering_id: str
    scope: str
    preprocessed_id: str
    ml_dataset_sha256: str
    algorithm: str
    algorithm_version: str
    algorithm_family: str
    experiment_id: str
    experiment_log_path: str
    cluster_labels_path: str
    algorithm_output_path: str | None
    hyperparameters: dict[str, Any]
    seed_policy: str
    seed: int | None
    config_sha256: str
    n_clusters: int | None
    n_samples: int
    feature_set: list[str]
    feature_count: int
    input_identity: InputIdentityBlock
    environment: EnvironmentBlock
    created_utc: str
    last_seen_utc: str
    log_file: str
    research_safety: ResearchSafetyBlock


# ---------------------------------------------------------------------------
# Manifest from ExperimentResult
# ---------------------------------------------------------------------------


def build_clustering_manifest(
    *,
    experiment_result: ExperimentResult,
    clustering_id: str,
    preprocessed_id: str,
    ml_dataset_sha256: str,
    config_sha256: str,
    experiment_log_path: str,
    cluster_labels_path: str,
    algorithm_output_path: str | None,
    log_file: str,
    input_identity: InputIdentityBlock,
    environment: EnvironmentBlock,
    readonly_paths: list[str],
) -> ClusteringManifest:
    """Build a :class:`ClusteringManifest` from an :class:`ExperimentResult`.

    Parameters
    ----------
    experiment_result : ExperimentResult
        The result returned by ``ExperimentRunner.run()``.
    clustering_id : str
        Content-addressed id derived from the 7-field canonical payload.
    preprocessed_id : str
        DEV-03 preprocessed id (canonical field 1/7).
    ml_dataset_sha256 : str
        SHA-256 of the DEV-03 ML Dataset parquet (canonical field 7/7).
    config_sha256 : str
        SHA-256 of the DEV-04 config YAML (canonical field 6/7).
    experiment_log_path : str
        Relative path to ``experiment_log_*.json``.
    cluster_labels_path : str
        Relative path to ``cluster_labels_*.parquet``.
    algorithm_output_path : str or None
        Relative path to ``algorithm_output_*.parquet`` (GMM/FCM only).
    log_file : str
        Relative path to the per-run log file.
    input_identity : InputIdentityBlock
        Source ML Dataset identity.
    environment : EnvironmentBlock
        Runtime environment snapshot.
    readonly_paths : list[str]
        Paths that DEV-04 must not modify.

    Returns
    -------
    ClusteringManifest
        Complete manifest ready to write.
    """
    from customer_segmentation.prototype.clustering.scope import (
        DETERMINISTIC_ALGORITHMS,
    )

    algorithm = experiment_result.algorithm
    seed_policy = "deterministic" if algorithm in DETERMINISTIC_ALGORITHMS else "stochastic"
    # Canonical seed: int for stochastic, null for deterministic.
    canonical_seed: int | None = (
        None if seed_policy == "deterministic" else experiment_result.random_seed_used
    )

    # Algorithm family from ExperimentResult cluster_result.
    algorithm_family = ""
    if experiment_result.cluster_result is not None:
        algorithm_family = experiment_result.cluster_result.algorithm_family

    return ClusteringManifest(
        schema_version=CLUSTERING_MANIFEST_SCHEMA_VERSION,
        clustering_id=clustering_id,
        scope="CLUSTERED_PROTOTYPE",
        preprocessed_id=preprocessed_id,
        ml_dataset_sha256=ml_dataset_sha256,
        algorithm=algorithm,
        algorithm_version=experiment_result.algorithm_version,
        algorithm_family=algorithm_family,
        experiment_id=experiment_result.experiment_id,
        experiment_log_path=experiment_log_path,
        cluster_labels_path=cluster_labels_path,
        algorithm_output_path=algorithm_output_path,
        hyperparameters=dict(experiment_result.hyperparameters),
        seed_policy=seed_policy,
        seed=canonical_seed,
        config_sha256=config_sha256,
        n_clusters=experiment_result.n_clusters,
        n_samples=experiment_result.n_samples,
        feature_set=list(experiment_result.feature_set),
        feature_count=experiment_result.feature_count,
        input_identity=input_identity,
        environment=environment,
        created_utc=now_utc_iso(),
        last_seen_utc=now_utc_iso(),
        log_file=log_file,
        research_safety=ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="CLUSTERED_PROTOTYPE",
            appeared_in_research_evidence=False,
            read_only_paths_unmodified=readonly_paths,
        ),
    )


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def _to_jsonable(value: Any) -> Any:
    """Convert a value to a JSON-serializable form."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return _to_jsonable(asdict(value))
    raise TypeError(f"Cannot serialise value of type {type(value).__name__}.")


def manifest_to_dict(m: ClusteringManifest) -> dict[str, Any]:
    """Convert a :class:`ClusteringManifest` to a JSON-serialisable dict."""
    return _to_jsonable(asdict(m))


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def write_clustering_manifest(manifest: ClusteringManifest, path: Path) -> None:
    """Atomically write a :class:`ClusteringManifest` to ``path``.

    Writes to a temp file in the same directory and renames on success.
    """
    path = Path(path)
    if not path.parent.exists():
        raise ClusteringManifestError(
            f"Cannot write manifest to {path!s}: parent directory does not exist."
        )
    payload = manifest_to_dict(manifest)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


def read_clustering_manifest(path: Path) -> ClusteringManifest:
    """Read and reconstruct a :class:`ClusteringManifest` from JSON."""
    path = Path(path)
    if not path.exists():
        raise ClusteringManifestError(f"Manifest file not found: {path!s}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ClusteringManifestError(f"Failed to parse manifest JSON at {path!s}: {exc}") from exc
    if not isinstance(data, dict):
        raise ClusteringManifestError(
            f"Manifest at {path!s} must be a JSON object; got {type(data).__name__}."
        )
    return _dict_to_manifest(data)


def _dict_to_manifest(data: Mapping[str, Any]) -> ClusteringManifest:
    """Build a ClusteringManifest from a JSON object."""
    required = (
        "schema_version",
        "clustering_id",
        "scope",
        "preprocessed_id",
        "ml_dataset_sha256",
        "algorithm",
        "algorithm_version",
        "algorithm_family",
        "experiment_id",
        "experiment_log_path",
        "cluster_labels_path",
        "hyperparameters",
        "seed_policy",
        "seed",
        "config_sha256",
        "n_samples",
        "feature_set",
        "feature_count",
        "input_identity",
        "environment",
        "created_utc",
        "last_seen_utc",
        "log_file",
        "research_safety",
    )
    for key in required:
        if key not in data:
            raise ClusteringManifestError(f"Manifest is missing required field: {key!r}.")

    ii_raw = data["input_identity"]
    input_identity = InputIdentityBlock(
        dataset_sha256=str(ii_raw["dataset_sha256"]),
        input_path=str(ii_raw["input_path"]),
        metadata_path=str(ii_raw["metadata_path"]),
    )

    env_raw = data["environment"]
    key_libs = {}
    for k, v in env_raw.get("key_libraries", {}).items():
        key_libs[str(k)] = str(v)
    environment = EnvironmentBlock(
        python=str(env_raw["python"]),
        platform=str(env_raw["platform"]),
        release=str(env_raw["release"]),
        machine=str(env_raw["machine"]),
        key_libraries=key_libs,
    )

    rs_raw = data["research_safety"]
    research_safety = ResearchSafetyBlock(
        automatically_promoted_to_research=bool(rs_raw["automatically_promoted_to_research"]),
        scope=str(rs_raw["scope"]),
        appeared_in_research_evidence=bool(rs_raw["appeared_in_research_evidence"]),
        read_only_paths_unmodified=[str(p) for p in rs_raw.get("read_only_paths_unmodified", [])],
    )

    return ClusteringManifest(
        schema_version=str(data["schema_version"]),
        clustering_id=str(data["clustering_id"]),
        scope=str(data["scope"]),
        preprocessed_id=str(data["preprocessed_id"]),
        ml_dataset_sha256=str(data["ml_dataset_sha256"]),
        algorithm=str(data["algorithm"]),
        algorithm_version=str(data["algorithm_version"]),
        algorithm_family=str(data["algorithm_family"]),
        experiment_id=str(data["experiment_id"]),
        experiment_log_path=str(data["experiment_log_path"]),
        cluster_labels_path=str(data["cluster_labels_path"]),
        algorithm_output_path=(
            str(data["algorithm_output_path"])
            if data.get("algorithm_output_path") is not None
            else None
        ),
        hyperparameters=dict(data["hyperparameters"]),
        seed_policy=str(data["seed_policy"]),
        seed=data["seed"],
        config_sha256=str(data["config_sha256"]),
        n_clusters=int(data["n_clusters"]) if data.get("n_clusters") is not None else None,
        n_samples=int(data["n_samples"]),
        feature_set=[str(c) for c in data["feature_set"]],
        feature_count=int(data["feature_count"]),
        input_identity=input_identity,
        environment=environment,
        created_utc=str(data["created_utc"]),
        last_seen_utc=str(data["last_seen_utc"]),
        log_file=str(data["log_file"]),
        research_safety=research_safety,
    )


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a "Z" suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
