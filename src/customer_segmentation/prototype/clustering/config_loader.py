"""YAML configuration loader for DEV-04 Prototype Clustering.

Single source of truth: ``configs/dev04_clustering.yaml``.

The loader mirrors the frozenset + typed-error convention used by
:mod:`customer_segmentation.config.loader`,
:mod:`customer_segmentation.prototype.preprocessing.config_loader`, and
:mod:`customer_segmentation.clustering.config`.

Top-level structure::

    dev04_clustering:
      algorithms:
        kmeans: {...}
        agglomerative: {...}
        dbscan: {...}
        gmm: {...}
        fuzzy_cmeans: {...}
      random_seed:
        default: 42
        per_algorithm_override: {}
      logging:
        level: "INFO"
        format: ...
        log_dir_relative: "data/prototype/datasets"
        emit_to_console: true
      storage:
        output_dir_relative: "clustering"
        emit_algorithm_output: true
      research_safety:
        readonly_paths: [...]
        never_promote_to_research: true
      validation:
        min_samples: 2
        min_features: 1
        require_no_nan: true
        require_no_inf: true
        require_all_numeric: true
        exclude_customer_id_from_features: true

Hard rules
----------
- ``storage.storage_root`` is NOT a key here. The storage root is always
  loaded from ``configs/dev02_dataset_management.yaml`` (shared with
  DEV-02/DEV-03). CLI does NOT expose ``--storage-root``.
- Validation settings mirror ``ML-01 FrameworkConfig.validation``.
- ``algorithms`` keys must be a subset of the 5 supported names.
- Logging level must be in ``VALID_LOG_LEVELS``.
- All dataclasses are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from customer_segmentation.prototype.clustering.scope import (
    DETERMINISTIC_ALGORITHMS,
    STOCHASTIC_ALGORITHMS,
    SUPPORTED_ALGORITHMS,
)

__all__ = [
    "DEFAULT_DEV04_CONFIG_PATH",
    "DEV04_CONFIG_TOP_KEY",
    "Dev04ConfigError",
    "Dev04AlgorithmHyperparameterConfig",
    "Dev04RandomSeedConfig",
    "Dev04LoggingConfig",
    "Dev04StorageConfig",
    "Dev04ResearchSafetyConfig",
    "Dev04ValidationConfig",
    "Dev04Config",
    "load_dev04_config",
    "find_default_dev04_config_path",
]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
DEFAULT_DEV04_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "dev04_clustering.yaml"
DEV04_CONFIG_TOP_KEY: str = "dev04_clustering"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev04ConfigError(ValueError):
    """Raised when ``configs/dev04_clustering.yaml`` is malformed."""


# ---------------------------------------------------------------------------
# Logging level
# ---------------------------------------------------------------------------

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# ---------------------------------------------------------------------------
# Per-algorithm hyperparameter blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev04AlgorithmHyperparameterConfig:
    """Per-algorithm hyperparameter defaults (mirrors configs/clustering.yaml)."""

    enabled: bool = True
    # K-Means
    n_clusters: int = 4
    init: str = "k-means++"
    n_init: int = 10
    max_iter: int = 300
    tol: float = 1.0e-4
    # Agglomerative
    linkage: str = "ward"
    metric: str = "euclidean"
    compute_distances: bool = True
    # DBSCAN
    eps: float = 0.5
    min_samples: int = 5
    # GMM
    n_components: int = 4
    covariance_type: str = "full"
    init_params: str = "kmeans"
    reg_covar: float = 1.0e-6
    # FCM
    fuzziness: float = 2.0
    error: float = 1.0e-4


# ---------------------------------------------------------------------------
# Random seed
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev04RandomSeedConfig:
    """Random seed policy for DEV-04."""

    default: int = 42
    per_algorithm_override: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev04LoggingConfig:
    """Per-stage logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
    log_dir_relative: str = "data/prototype/datasets"
    emit_to_console: bool = True

    def __post_init__(self) -> None:
        if self.level not in VALID_LOG_LEVELS:
            raise Dev04ConfigError(
                f"logging.level must be one of {sorted(VALID_LOG_LEVELS)}; " f"got {self.level!r}."
            )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev04StorageConfig:
    """Storage sub-config (relative paths; root comes from DEV-02)."""

    output_dir_relative: str = "clustering"
    emit_algorithm_output: bool = True


# ---------------------------------------------------------------------------
# Research safety
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev04ResearchSafetyConfig:
    """Research-safety sub-config (defence-in-depth)."""

    readonly_paths: list[str] = field(
        default_factory=lambda: [
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ]
    )
    never_promote_to_research: bool = True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev04ValidationConfig:
    """Input validation policy (mirrors ML-01 FrameworkConfig.validation)."""

    min_samples: int = 2
    min_features: int = 1
    require_no_nan: bool = True
    require_no_inf: bool = True
    require_all_numeric: bool = True
    exclude_customer_id_from_features: bool = True


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev04Config:
    """The complete DEV-04 configuration."""

    algorithms: dict[str, Dev04AlgorithmHyperparameterConfig] = field(default_factory=dict)
    random_seed: Dev04RandomSeedConfig = field(default_factory=Dev04RandomSeedConfig)
    logging: Dev04LoggingConfig = field(default_factory=Dev04LoggingConfig)
    storage: Dev04StorageConfig = field(default_factory=Dev04StorageConfig)
    research_safety: Dev04ResearchSafetyConfig = field(default_factory=Dev04ResearchSafetyConfig)
    validation: Dev04ValidationConfig = field(default_factory=Dev04ValidationConfig)


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Dev04ConfigError(f"DEV-04 config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise Dev04ConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise Dev04ConfigError(
            f"DEV-04 config file {path} must be a YAML mapping; " f"got {type(data).__name__}."
        )
    return data


def _require(container: dict[str, Any], key: str, *, container_name: str) -> Any:
    if key not in container:
        raise Dev04ConfigError(
            f"Missing required key {key!r} under {container_name!r} in DEV-04 config."
        )
    return container[key]


def _optional(container: dict[str, Any], key: str, default: Any = None) -> Any:
    return container.get(key, default)


def _optional_str(container: dict[str, Any], key: str, default: str) -> str:
    if key not in container:
        return default
    v = container[key]
    if not isinstance(v, str):
        raise Dev04ConfigError(f"Expected {key!r} to be a string; got {type(v).__name__}.")
    return v


def _optional_bool(container: dict[str, Any], key: str, default: bool) -> bool:
    if key not in container:
        return default
    v = container[key]
    if not isinstance(v, bool):
        raise Dev04ConfigError(f"Expected {key!r} to be a bool; got {type(v).__name__}.")
    return v


def _optional_int(container: dict[str, Any], key: str, default: int) -> int:
    if key not in container:
        return default
    v = container[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise Dev04ConfigError(f"Expected {key!r} to be an int; got {type(v).__name__}.")
    return int(v)


def _optional_float(container: dict[str, Any], key: str, default: float) -> float:
    if key not in container:
        return default
    v = container[key]
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise Dev04ConfigError(f"Expected {key!r} to be a number; got {type(v).__name__}.")
    return float(v)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_algorithms(raw: dict[str, Any] | None) -> dict[str, Dev04AlgorithmHyperparameterConfig]:
    """Parse the algorithms block.

    Only the 5 supported algorithm names are accepted.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise Dev04ConfigError(f"Expected 'algorithms' to be a mapping; got {type(raw).__name__}.")
    out: dict[str, Dev04AlgorithmHyperparameterConfig] = {}
    for name, cfg_raw in raw.items():
        if name not in SUPPORTED_ALGORITHMS:
            raise Dev04ConfigError(
                f"algorithm name {name!r} is not supported; "
                f"supported: {sorted(SUPPORTED_ALGORITHMS)}."
            )
        if not isinstance(cfg_raw, dict):
            raise Dev04ConfigError(
                f"Expected algorithm {name!r} config to be a mapping; "
                f"got {type(cfg_raw).__name__}."
            )
        cfg = Dev04AlgorithmHyperparameterConfig(
            enabled=_optional_bool(cfg_raw, "enabled", True),
            n_clusters=_optional_int(cfg_raw, "n_clusters", 4),
            init=_optional_str(cfg_raw, "init", "k-means++"),
            n_init=_optional_int(cfg_raw, "n_init", 10),
            max_iter=_optional_int(cfg_raw, "max_iter", 300),
            tol=_optional_float(cfg_raw, "tol", 1.0e-4),
            linkage=_optional_str(cfg_raw, "linkage", "ward"),
            metric=_optional_str(cfg_raw, "metric", "euclidean"),
            compute_distances=_optional_bool(cfg_raw, "compute_distances", True),
            eps=_optional_float(cfg_raw, "eps", 0.5),
            min_samples=_optional_int(cfg_raw, "min_samples", 5),
            n_components=_optional_int(cfg_raw, "n_components", 4),
            covariance_type=_optional_str(cfg_raw, "covariance_type", "full"),
            init_params=_optional_str(cfg_raw, "init_params", "kmeans"),
            reg_covar=_optional_float(cfg_raw, "reg_covar", 1.0e-6),
            fuzziness=_optional_float(cfg_raw, "fuzziness", 2.0),
            error=_optional_float(cfg_raw, "error", 1.0e-4),
        )
        out[name] = cfg
    # Fill defaults for missing algorithm names.
    for name in SUPPORTED_ALGORITHMS:
        if name not in out:
            out[name] = Dev04AlgorithmHyperparameterConfig()
    return out


def _parse_random_seed(raw: dict[str, Any] | None) -> Dev04RandomSeedConfig:
    if raw is None:
        return Dev04RandomSeedConfig()
    if not isinstance(raw, dict):
        raise Dev04ConfigError(f"Expected 'random_seed' to be a mapping; got {type(raw).__name__}.")
    default = _optional_int(raw, "default", 42)
    override_raw = _optional(raw, "per_algorithm_override", {})
    if not isinstance(override_raw, dict):
        raise Dev04ConfigError("random_seed.per_algorithm_override must be a mapping.")
    override: dict[str, int] = {}
    for k, v in override_raw.items():
        if not isinstance(k, str) or k not in SUPPORTED_ALGORITHMS:
            continue  # silently ignore unknown keys
        if not isinstance(v, int) or isinstance(v, bool):
            raise Dev04ConfigError(
                f"random_seed.per_algorithm_override[{k!r}] must be an int; "
                f"got {type(v).__name__}."
            )
        override[k] = int(v)
    return Dev04RandomSeedConfig(default=default, per_algorithm_override=override)


def _parse_logging(raw: dict[str, Any] | None) -> Dev04LoggingConfig:
    if raw is None:
        return Dev04LoggingConfig()
    if not isinstance(raw, dict):
        raise Dev04ConfigError(f"Expected 'logging' to be a mapping; got {type(raw).__name__}.")
    return Dev04LoggingConfig(
        level=_optional_str(raw, "level", "INFO"),
        format=_optional_str(
            raw,
            "format",
            "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s",
        ),
        log_dir_relative=_optional_str(raw, "log_dir_relative", "data/prototype/datasets"),
        emit_to_console=_optional_bool(raw, "emit_to_console", True),
    )


def _parse_storage(raw: dict[str, Any] | None) -> Dev04StorageConfig:
    if raw is None:
        return Dev04StorageConfig()
    if not isinstance(raw, dict):
        raise Dev04ConfigError(f"Expected 'storage' to be a mapping; got {type(raw).__name__}.")
    return Dev04StorageConfig(
        output_dir_relative=_optional_str(raw, "output_dir_relative", "clustering"),
        emit_algorithm_output=_optional_bool(raw, "emit_algorithm_output", True),
    )


def _parse_research_safety(raw: dict[str, Any] | None) -> Dev04ResearchSafetyConfig:
    if raw is None:
        return Dev04ResearchSafetyConfig()
    if not isinstance(raw, dict):
        raise Dev04ConfigError(
            f"Expected 'research_safety' to be a mapping; got {type(raw).__name__}."
        )
    paths_raw = _optional(raw, "readonly_paths", None)
    readonly_paths: list[str]
    if paths_raw is None:
        readonly_paths = [
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ]
    elif isinstance(paths_raw, list):
        readonly_paths = [str(p) for p in paths_raw]
    else:
        raise Dev04ConfigError("research_safety.readonly_paths must be a list.")
    return Dev04ResearchSafetyConfig(
        readonly_paths=readonly_paths,
        never_promote_to_research=_optional_bool(raw, "never_promote_to_research", True),
    )


def _parse_validation(raw: dict[str, Any] | None) -> Dev04ValidationConfig:
    if raw is None:
        return Dev04ValidationConfig()
    if not isinstance(raw, dict):
        raise Dev04ConfigError(f"Expected 'validation' to be a mapping; got {type(raw).__name__}.")
    return Dev04ValidationConfig(
        min_samples=_optional_int(raw, "min_samples", 2),
        min_features=_optional_int(raw, "min_features", 1),
        require_no_nan=_optional_bool(raw, "require_no_nan", True),
        require_no_inf=_optional_bool(raw, "require_no_inf", True),
        require_all_numeric=_optional_bool(raw, "require_all_numeric", True),
        exclude_customer_id_from_features=_optional_bool(
            raw, "exclude_customer_id_from_features", True
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_default_dev04_config_path() -> Path:
    """Return the canonical path to ``configs/dev04_clustering.yaml``."""
    return DEFAULT_DEV04_CONFIG_PATH


def load_dev04_config(path: Path | None = None) -> tuple[Dev04Config, str]:
    """Load ``configs/dev04_clustering.yaml`` and return typed config + raw text.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit YAML path. ``None`` uses
        :data:`DEFAULT_DEV04_CONFIG_PATH`.

    Returns
    -------
    tuple[Dev04Config, str]
        Typed config dataclass and the raw YAML text (for config_sha256).

    Raises
    ------
    Dev04ConfigError
        If the YAML is missing, malformed, or a required block is absent.
    """
    if path is None:
        path = DEFAULT_DEV04_CONFIG_PATH

    p = Path(path)
    if not p.exists():
        raise Dev04ConfigError(f"DEV-04 config file not found: {p}")

    raw_text = p.read_text(encoding="utf-8")
    raw = _read_yaml(p)

    if DEV04_CONFIG_TOP_KEY not in raw:
        raise Dev04ConfigError(
            f"DEV-04 config {path} must contain top-level {DEV04_CONFIG_TOP_KEY!r} mapping."
        )
    top = raw[DEV04_CONFIG_TOP_KEY]
    if not isinstance(top, dict):
        raise Dev04ConfigError(
            f"DEV-04 config top-level {DEV04_CONFIG_TOP_KEY!r} must be a mapping; "
            f"got {type(top).__name__}."
        )

    return (
        Dev04Config(
            algorithms=_parse_algorithms(top.get("algorithms")),
            random_seed=_parse_random_seed(top.get("random_seed")),
            logging=_parse_logging(top.get("logging")),
            storage=_parse_storage(top.get("storage")),
            research_safety=_parse_research_safety(top.get("research_safety")),
            validation=_parse_validation(top.get("validation")),
        ),
        raw_text,
    )
