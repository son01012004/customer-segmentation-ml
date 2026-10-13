"""YAML configuration loader for DEV-05 Prototype Evaluation.

Single source of truth: ``configs/dev05_evaluation.yaml``.

The loader mirrors the frozenset + typed-error convention used by
:mod:`customer_segmentation.prototype.clustering.config_loader`,
:mod:`customer_segmentation.config.loader`, and
:mod:`customer_segmentation.prototype.preprocessing.config_loader`.

Top-level structure::

    dev05_evaluation:
      metrics:                         # Closed set of metric names
        enabled: [silhouette, davies_bouldin, calinski_harabasz]
      noise_policy:                    # "exclude" (default per ADR-0006) | "include"
        default: "exclude"
      display:
        missing_value_placeholder: "--"  # for CLI/display
        csv_missing_value: ""            # for metrics_long.csv
      logging:
        level: "INFO"
        format: ...
        log_dir_relative: "data/prototype/datasets"
        emit_to_console: true
      storage:
        output_dir_relative: "evaluation"
        emit_metrics_csv: true
      research_safety:
        readonly_paths: [...]
        never_promote_to_research: true
        evaluation_scope: "EVALUATED_PROTOTYPE"
      validation:
        min_samples: 2
        min_features: 1
        require_no_nan: true
        require_no_inf: true
        require_all_numeric: true
        exclude_customer_id_from_features: true
      compare:
        emit_singleton_group: true        # OQ-EVAL-04 (B)
        show_provenance_per_row: true
        disclaimer_text: "no ranking, recommendation, or winner annotation is emitted"

Hard rules
----------
- ``storage.storage_root`` is NOT a key here. The storage root is always
  loaded from ``configs/dev02_dataset_management.yaml`` (shared with
  DEV-02/DEV-03/DEV-04). CLI does NOT expose ``--storage-root``.
- ``metrics.enabled`` is restricted to the 3 names in
  :data:`customer_segmentation.prototype.evaluation.scope.METRIC_NAMES`.
- ``noise_policy.default`` is restricted to :data:`NOISE_POLICIES`.
- ``logging.level`` must be in :data:`VALID_LOG_LEVELS`.
- All dataclasses are frozen.
- Per ADR-0006: ``noise_policy.default`` is ``"exclude"`` for prototype
  layer. Changing the default is a methodology change that requires a
  new ADR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from customer_segmentation.prototype.evaluation.scope import (
    DEFAULT_METRIC_SET,
    METRIC_NAMES,
    NOISE_POLICIES,
)

__all__ = [
    "DEFAULT_DEV05_CONFIG_PATH",
    "DEV05_CONFIG_TOP_KEY",
    "Dev05ConfigError",
    "Dev05MetricsConfig",
    "Dev05NoisePolicyConfig",
    "Dev05DisplayConfig",
    "Dev05LoggingConfig",
    "Dev05StorageConfig",
    "Dev05ResearchSafetyConfig",
    "Dev05ValidationConfig",
    "Dev05CompareConfig",
    "Dev05Config",
    "VALID_LOG_LEVELS",
    "load_dev05_config",
    "find_default_dev05_config_path",
]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
DEFAULT_DEV05_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "dev05_evaluation.yaml"
DEV05_CONFIG_TOP_KEY: str = "dev05_evaluation"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev05ConfigError(ValueError):
    """Raised when ``configs/dev05_evaluation.yaml`` is malformed."""


# ---------------------------------------------------------------------------
# Logging level (shared with DEV-04 convention)
# ---------------------------------------------------------------------------

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# ---------------------------------------------------------------------------
# Metrics config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05MetricsConfig:
    """Closed set of metric names DEV-05 emits.

    The default is the full closed set of 3 internal metrics
    (silhouette, davies-bouldin, calinski-harabasz).
    """

    enabled: tuple[str, ...] = DEFAULT_METRIC_SET

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, tuple):
            raise Dev05ConfigError(
                f"metrics.enabled must be a list/tuple; got {type(self.enabled).__name__}."
            )
        if len(self.enabled) == 0:
            raise Dev05ConfigError("metrics.enabled must contain at least one metric name.")
        for name in self.enabled:
            if not isinstance(name, str):
                raise Dev05ConfigError(
                    f"metrics.enabled entries must be strings; got {type(name).__name__}."
                )
            if name not in METRIC_NAMES:
                raise Dev05ConfigError(
                    f"metric name {name!r} is not in the closed set "
                    f"{sorted(METRIC_NAMES)}; DEV-05 covers only these 3 internal metrics."
                )
        # Reject duplicates.
        if len(set(self.enabled)) != len(self.enabled):
            raise Dev05ConfigError("metrics.enabled contains duplicate entries.")


# ---------------------------------------------------------------------------
# Noise policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05NoisePolicyConfig:
    """DBSCAN noise handling config (per ADR-0006 prototype-scope decision).

    Per ADR-0006 (OQ-EVAL-NOISE resolved 2026-10-09), the prototype-layer
    default is ``"exclude"``. The CLI flag ``--noise-policy`` and this
    config field provide per-call override. Research-layer status of
    CON-15 / WA-08 / EXP01-MET-01 is unaffected.
    """

    default: str = "exclude"

    def __post_init__(self) -> None:
        if self.default not in NOISE_POLICIES:
            raise Dev05ConfigError(
                f"noise_policy.default must be one of {sorted(NOISE_POLICIES)}; "
                f"got {self.default!r}."
            )


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05DisplayConfig:
    """Display conventions (per OQ-EVAL-06 resolved decision).

    Per OQ-EVAL-06 (resolved at Phase 2 start): display ``--`` (em-dash)
    in CLI/display for non-VALID_VALUE rows; blank in
    ``metrics_long.csv``.
    """

    missing_value_placeholder: str = "--"
    csv_missing_value: str = ""


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05LoggingConfig:
    """Per-stage logging configuration (mirrors DEV-04)."""

    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
    log_dir_relative: str = "data/prototype/datasets"
    emit_to_console: bool = True

    def __post_init__(self) -> None:
        if self.level not in VALID_LOG_LEVELS:
            raise Dev05ConfigError(
                f"logging.level must be one of {sorted(VALID_LOG_LEVELS)}; "
                f"got {self.level!r}."
            )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05StorageConfig:
    """Storage sub-config (relative paths; root comes from DEV-02)."""

    output_dir_relative: str = "evaluation"
    emit_metrics_csv: bool = True


# ---------------------------------------------------------------------------
# Research safety
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05ResearchSafetyConfig:
    """Research-safety sub-config (defence-in-depth).

    Always sets ``evaluation_scope = "EVALUATED_PROTOTYPE"`` to mirror
    DEV-04's ``scope = "CLUSTERED_PROTOTYPE"``. Changing this is a
    methodology change requiring an ADR.
    """

    readonly_paths: list[str] = field(
        default_factory=lambda: [
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ]
    )
    never_promote_to_research: bool = True
    evaluation_scope: str = "EVALUATED_PROTOTYPE"

    def __post_init__(self) -> None:
        if self.evaluation_scope != "EVALUATED_PROTOTYPE":
            raise Dev05ConfigError(
                f"research_safety.evaluation_scope must be "
                f"'EVALUATED_PROTOTYPE' (got {self.evaluation_scope!r}); "
                "the prototype layer never auto-promotes."
            )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05ValidationConfig:
    """Input validation policy (mirrors ML-01 FrameworkConfig.validation).

    DEV-05 re-reads the DEV-04 cluster_labels parquet and the DEV-03
    ML Dataset parquet for X. These settings mirror ML-01's validation
    policy. The CustomerID leak check (``exclude_customer_id_from_features``)
    is critical because the metric is computed on a feature matrix that
    must not include the customer identifier.
    """

    min_samples: int = 2
    min_features: int = 1
    require_no_nan: bool = True
    require_no_inf: bool = True
    require_all_numeric: bool = True
    exclude_customer_id_from_features: bool = True


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05CompareConfig:
    """Compare-experiments display policy (per OQ-EVAL-04, 05, 06)."""

    emit_singleton_group: bool = True  # OQ-EVAL-04 (B)
    show_provenance_per_row: bool = True
    disclaimer_text: str = (
        "no ranking, recommendation, or winner annotation is emitted"
    )


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev05Config:
    """The complete DEV-05 configuration."""

    metrics: Dev05MetricsConfig = field(default_factory=Dev05MetricsConfig)
    noise_policy: Dev05NoisePolicyConfig = field(default_factory=Dev05NoisePolicyConfig)
    display: Dev05DisplayConfig = field(default_factory=Dev05DisplayConfig)
    logging: Dev05LoggingConfig = field(default_factory=Dev05LoggingConfig)
    storage: Dev05StorageConfig = field(default_factory=Dev05StorageConfig)
    research_safety: Dev05ResearchSafetyConfig = field(
        default_factory=Dev05ResearchSafetyConfig
    )
    validation: Dev05ValidationConfig = field(default_factory=Dev05ValidationConfig)
    compare: Dev05CompareConfig = field(default_factory=Dev05CompareConfig)


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Dev05ConfigError(f"DEV-05 config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise Dev05ConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise Dev05ConfigError(
            f"DEV-05 config file {path} must be a YAML mapping; "
            f"got {type(data).__name__}."
        )
    return data


def _optional_str(container: dict[str, Any], key: str, default: str) -> str:
    if key not in container:
        return default
    v = container[key]
    if not isinstance(v, str):
        raise Dev05ConfigError(f"Expected {key!r} to be a string; got {type(v).__name__}.")
    return v


def _optional_bool(container: dict[str, Any], key: str, default: bool) -> bool:
    if key not in container:
        return default
    v = container[key]
    if not isinstance(v, bool):
        raise Dev05ConfigError(f"Expected {key!r} to be a bool; got {type(v).__name__}.")
    return v


def _optional_int(container: dict[str, Any], key: str, default: int) -> int:
    if key not in container:
        return default
    v = container[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise Dev05ConfigError(f"Expected {key!r} to be an int; got {type(v).__name__}.")
    return int(v)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_metrics(raw: dict[str, Any] | None) -> Dev05MetricsConfig:
    if raw is None:
        return Dev05MetricsConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(f"Expected 'metrics' to be a mapping; got {type(raw).__name__}.")
    enabled_raw = raw.get("enabled", list(DEFAULT_METRIC_SET))
    if not isinstance(enabled_raw, list):
        raise Dev05ConfigError(
            f"metrics.enabled must be a list; got {type(enabled_raw).__name__}."
        )
    return Dev05MetricsConfig(enabled=tuple(enabled_raw))


def _parse_noise_policy(raw: dict[str, Any] | None) -> Dev05NoisePolicyConfig:
    if raw is None:
        return Dev05NoisePolicyConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(
            f"Expected 'noise_policy' to be a mapping; got {type(raw).__name__}."
        )
    return Dev05NoisePolicyConfig(default=_optional_str(raw, "default", "exclude"))


def _parse_display(raw: dict[str, Any] | None) -> Dev05DisplayConfig:
    if raw is None:
        return Dev05DisplayConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(
            f"Expected 'display' to be a mapping; got {type(raw).__name__}."
        )
    return Dev05DisplayConfig(
        missing_value_placeholder=_optional_str(raw, "missing_value_placeholder", "--"),
        csv_missing_value=_optional_str(raw, "csv_missing_value", ""),
    )


def _parse_logging(raw: dict[str, Any] | None) -> Dev05LoggingConfig:
    if raw is None:
        return Dev05LoggingConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(
            f"Expected 'logging' to be a mapping; got {type(raw).__name__}."
        )
    return Dev05LoggingConfig(
        level=_optional_str(raw, "level", "INFO"),
        format=_optional_str(
            raw,
            "format",
            "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s",
        ),
        log_dir_relative=_optional_str(raw, "log_dir_relative", "data/prototype/datasets"),
        emit_to_console=_optional_bool(raw, "emit_to_console", True),
    )


def _parse_storage(raw: dict[str, Any] | None) -> Dev05StorageConfig:
    if raw is None:
        return Dev05StorageConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(
            f"Expected 'storage' to be a mapping; got {type(raw).__name__}."
        )
    return Dev05StorageConfig(
        output_dir_relative=_optional_str(raw, "output_dir_relative", "evaluation"),
        emit_metrics_csv=_optional_bool(raw, "emit_metrics_csv", True),
    )


def _parse_research_safety(raw: dict[str, Any] | None) -> Dev05ResearchSafetyConfig:
    if raw is None:
        return Dev05ResearchSafetyConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(
            f"Expected 'research_safety' to be a mapping; got {type(raw).__name__}."
        )
    paths_raw = raw.get("readonly_paths", None)
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
        raise Dev05ConfigError("research_safety.readonly_paths must be a list.")
    return Dev05ResearchSafetyConfig(
        readonly_paths=readonly_paths,
        never_promote_to_research=_optional_bool(raw, "never_promote_to_research", True),
        evaluation_scope=_optional_str(raw, "evaluation_scope", "EVALUATED_PROTOTYPE"),
    )


def _parse_validation(raw: dict[str, Any] | None) -> Dev05ValidationConfig:
    if raw is None:
        return Dev05ValidationConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(
            f"Expected 'validation' to be a mapping; got {type(raw).__name__}."
        )
    return Dev05ValidationConfig(
        min_samples=_optional_int(raw, "min_samples", 2),
        min_features=_optional_int(raw, "min_features", 1),
        require_no_nan=_optional_bool(raw, "require_no_nan", True),
        require_no_inf=_optional_bool(raw, "require_no_inf", True),
        require_all_numeric=_optional_bool(raw, "require_all_numeric", True),
        exclude_customer_id_from_features=_optional_bool(
            raw, "exclude_customer_id_from_features", True
        ),
    )


def _parse_compare(raw: dict[str, Any] | None) -> Dev05CompareConfig:
    if raw is None:
        return Dev05CompareConfig()
    if not isinstance(raw, dict):
        raise Dev05ConfigError(
            f"Expected 'compare' to be a mapping; got {type(raw).__name__}."
        )
    return Dev05CompareConfig(
        emit_singleton_group=_optional_bool(raw, "emit_singleton_group", True),
        show_provenance_per_row=_optional_bool(raw, "show_provenance_per_row", True),
        disclaimer_text=_optional_str(
            raw,
            "disclaimer_text",
            "no ranking, recommendation, or winner annotation is emitted",
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_default_dev05_config_path() -> Path:
    """Return the canonical path to ``configs/dev05_evaluation.yaml``."""
    return DEFAULT_DEV05_CONFIG_PATH


def load_dev05_config(path: Path | None = None) -> tuple[Dev05Config, str]:
    """Load ``configs/dev05_evaluation.yaml`` and return typed config + raw text.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit YAML path. ``None`` uses
        :data:`DEFAULT_DEV05_CONFIG_PATH`.

    Returns
    -------
    tuple[Dev05Config, str]
        Typed config dataclass and the raw YAML text (for config_sha256).

    Raises
    ------
    Dev05ConfigError
        If the YAML is missing, malformed, or a required block is absent.
    """
    if path is None:
        path = DEFAULT_DEV05_CONFIG_PATH

    p = Path(path)
    if not p.exists():
        raise Dev05ConfigError(f"DEV-05 config file not found: {p}")

    raw_text = p.read_text(encoding="utf-8")
    raw = _read_yaml(p)

    if DEV05_CONFIG_TOP_KEY not in raw:
        raise Dev05ConfigError(
            f"DEV-05 config {path} must contain top-level {DEV05_CONFIG_TOP_KEY!r} mapping."
        )
    top = raw[DEV05_CONFIG_TOP_KEY]
    if not isinstance(top, dict):
        raise Dev05ConfigError(
            f"DEV-05 config top-level {DEV05_CONFIG_TOP_KEY!r} must be a mapping; "
            f"got {type(top).__name__}."
        )

    return (
        Dev05Config(
            metrics=_parse_metrics(top.get("metrics")),
            noise_policy=_parse_noise_policy(top.get("noise_policy")),
            display=_parse_display(top.get("display")),
            logging=_parse_logging(top.get("logging")),
            storage=_parse_storage(top.get("storage")),
            research_safety=_parse_research_safety(top.get("research_safety")),
            validation=_parse_validation(top.get("validation")),
            compare=_parse_compare(top.get("compare")),
        ),
        raw_text,
    )
