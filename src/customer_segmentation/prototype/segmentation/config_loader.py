"""YAML configuration loader for DEV-06 Prototype Segmentation.

Single source of truth: ``configs/dev06_segmentation.yaml``.

The loader mirrors the frozenset + typed-error convention used by
:mod:`customer_segmentation.prototype.evaluation.config_loader`,
:mod:`customer_segmentation.prototype.clustering.config_loader`,
:mod:`customer_segmentation.config.loader`, and
:mod:`customer_segmentation.prototype.preprocessing.config_loader`.

Top-level structure::

    dev06_segmentation:
      noise_policy:                    # "exclude" (default per ADR-0006) | "include"
        default: "exclude"
      statistics:                       # Descriptive statistics (NO research metrics)
        numerical: [mean, median, std, q1, q3, min, max]
        categorical_topk: 10            # per OQ-SEG-DISPLAY-01
        categorical_uniqueness_threshold: 50
      characteristic_rules:             # per OQ-SEG-CHAR-01 (4-rule reduced set)
        enabled: ["mean_high_<feature>", ...]
        z_threshold: 1.0
      display:
        percentage_decimals: 2
        missing_value_placeholder: "--"
        csv_missing_value: ""
        disclaimer_text: "no ranking, recommendation, or winner annotation is emitted"
      storage:
        output_dir_relative: "segmentation"
        emit_profiles_csv: true
        emit_profiles_json: true
        emit_characteristics_json: true
        emit_sizes_long_csv: true
      logging:
        level: "INFO"
        format: ...
        log_dir_relative: "data/prototype/datasets"
        emit_to_console: true
      research_safety:
        readonly_paths: [...]
        never_promote_to_research: true
        segmentation_scope: "PROFILED_PROTOTYPE"
      validation:
        min_samples: 2
        min_features: 1
        require_no_nan: false
        exclude_customer_id_from_features: true
      compare:
        emit_singleton_group: true
        show_provenance_per_row: true
        disclaimer_text: "no ranking, recommendation, or winner annotation is emitted"

Hard rules
----------
- ``storage.storage_root`` is NOT a key here. The storage root is always
  loaded from ``configs/dev02_dataset_management.yaml`` (shared with
  DEV-02/03/04/05). CLI does NOT expose ``--storage-root``.
- ``noise_policy.default`` is restricted to :data:`NOISE_POLICIES`.
- ``statistics.numerical`` is restricted to a subset of
  :data:`PROFILING_STATISTICS_SET` (no research metrics allowed).
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

from customer_segmentation.prototype.segmentation.scope import (
    DEFAULT_STATISTICS_SET,
    NOISE_POLICIES,
    PROFILING_STATISTICS_SET,
)

__all__ = [
    "DEFAULT_DEV06_CONFIG_PATH",
    "DEV06_CONFIG_TOP_KEY",
    "Dev06ConfigError",
    "Dev06NoisePolicyConfig",
    "Dev06StatisticsConfig",
    "Dev06CharacteristicRulesConfig",
    "Dev06DisplayConfig",
    "Dev06StorageConfig",
    "Dev06LoggingConfig",
    "Dev06ResearchSafetyConfig",
    "Dev06ValidationConfig",
    "Dev06CompareConfig",
    "Dev06Config",
    "VALID_LOG_LEVELS",
    "load_dev06_config",
    "find_default_dev06_config_path",
]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
DEFAULT_DEV06_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "dev06_segmentation.yaml"
DEV06_CONFIG_TOP_KEY: str = "dev06_segmentation"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev06ConfigError(ValueError):
    """Raised when ``configs/dev06_segmentation.yaml`` is malformed."""


# ---------------------------------------------------------------------------
# Logging level (shared with DEV-04 / DEV-05 convention)
# ---------------------------------------------------------------------------

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# ---------------------------------------------------------------------------
# Noise policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06NoisePolicyConfig:
    """DBSCAN noise handling config (per ADR-0006 prototype-scope decision).

    Per ADR-0006, the prototype-layer default is ``"exclude"``. The CLI
    flag ``--noise-policy`` and this config field provide per-call
    override. Research-layer status of CON-15 / WA-08 / EXP01-MET-01 is
    unaffected.
    """

    default: str = "exclude"

    def __post_init__(self) -> None:
        if self.default not in NOISE_POLICIES:
            raise Dev06ConfigError(
                f"noise_policy.default must be one of {sorted(NOISE_POLICIES)}; "
                f"got {self.default!r}."
            )


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06StatisticsConfig:
    """Descriptive-statistics config (no research metrics).

    ``numerical`` is a subset of :data:`PROFILING_STATISTICS_SET`. The
    default is the full closed set of 7 numerical statistics. Categorical
    statistics (``topk_categories``, ``value_counts``) are always
    emitted when a feature is categorical (controlled per-feature by
    dtype detection in profile.py, not by config).

    ``categorical_topk`` is per OQ-SEG-DISPLAY-01 (default 10).

    ``categorical_uniqueness_threshold`` controls when an ``object`` dtype
    column is treated as ``text_or_id`` (skipped from profile) instead of
    ``categorical``. Default 50.
    """

    numerical: tuple[str, ...] = DEFAULT_STATISTICS_SET
    categorical_topk: int = 10
    categorical_uniqueness_threshold: int = 50

    def __post_init__(self) -> None:
        if not isinstance(self.numerical, tuple):
            raise Dev06ConfigError(
                f"statistics.numerical must be a list/tuple; "
                f"got {type(self.numerical).__name__}."
            )
        if len(self.numerical) == 0:
            raise Dev06ConfigError("statistics.numerical must contain at least one statistic name.")
        for name in self.numerical:
            if not isinstance(name, str):
                raise Dev06ConfigError(
                    f"statistics.numerical entries must be strings; " f"got {type(name).__name__}."
                )
            if name not in PROFILING_STATISTICS_SET:
                raise Dev06ConfigError(
                    f"statistic name {name!r} is not in the closed set "
                    f"{sorted(PROFILING_STATISTICS_SET)}; DEV-06 covers only "
                    f"descriptive statistics (no research metrics)."
                )
        if len(set(self.numerical)) != len(self.numerical):
            raise Dev06ConfigError("statistics.numerical contains duplicate entries.")
        if not isinstance(self.categorical_topk, int) or self.categorical_topk <= 0:
            raise Dev06ConfigError(
                f"statistics.categorical_topk must be a positive int; "
                f"got {self.categorical_topk!r}."
            )
        if not isinstance(self.categorical_uniqueness_threshold, int) or (
            self.categorical_uniqueness_threshold <= 0
        ):
            raise Dev06ConfigError(
                f"statistics.categorical_uniqueness_threshold must be a positive int; "
                f"got {self.categorical_uniqueness_threshold!r}."
            )


# ---------------------------------------------------------------------------
# Characteristic rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06CharacteristicRulesConfig:
    """Characteristic-rules config (per OQ-SEG-CHAR-01, 4-rule reduced set).

    The default rule set is the reduced 4-rule set (per Phase 1.5
    owner-authorized decision): ``mean_high_<feature>``,
    ``mean_low_<feature>``,
    ``median_above_dataset_median_<feature>``, and
    ``top_category_<feature>_<value>``. The two removed rules
    (``category_diversity_low_<feature>`` and
    ``missing_share_high_<feature>``) are profile-quality indicators,
    not customer characteristics.
    """

    enabled: tuple[str, ...] = (
        "mean_high_<feature>",
        "mean_low_<feature>",
        "median_above_dataset_median_<feature>",
        "top_category_<feature>_<value>",
    )
    z_threshold: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, tuple):
            raise Dev06ConfigError(
                f"characteristic_rules.enabled must be a list/tuple; "
                f"got {type(self.enabled).__name__}."
            )
        if len(self.enabled) == 0:
            raise Dev06ConfigError("characteristic_rules.enabled must contain at least one rule.")
        for rule in self.enabled:
            if not isinstance(rule, str):
                raise Dev06ConfigError(
                    f"characteristic_rules.enabled entries must be strings; "
                    f"got {type(rule).__name__}."
                )
            if not rule:
                raise Dev06ConfigError(
                    "characteristic_rules.enabled entries must be non-empty strings."
                )
        if len(set(self.enabled)) != len(self.enabled):
            raise Dev06ConfigError("characteristic_rules.enabled contains duplicate entries.")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06DisplayConfig:
    """Display conventions.

    Per OQ-SEG-DISPLAY-01 (resolved at Phase 1.5): display ``--``
    (em-dash) in CLI/display for missing values; blank in
    ``segment_sizes_long.csv``. ``percentage_decimals`` controls
    rounding of percentage columns (per OQ-SEG-DENOM-01).
    """

    percentage_decimals: int = 2
    missing_value_placeholder: str = "--"
    csv_missing_value: str = ""
    disclaimer_text: str = (
        "no ranking, recommendation, or winner annotation is emitted; "
        "descriptive comparison only; values are post-preprocessing"
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.percentage_decimals, int)
            or self.percentage_decimals < 0
            or self.percentage_decimals > 10
        ):
            raise Dev06ConfigError(
                f"display.percentage_decimals must be an int in [0, 10]; "
                f"got {self.percentage_decimals!r}."
            )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06StorageConfig:
    """Storage sub-config (relative paths; root comes from DEV-02)."""

    output_dir_relative: str = "segmentation"
    emit_profiles_csv: bool = True
    emit_profiles_json: bool = True
    emit_characteristics_json: bool = True
    emit_sizes_long_csv: bool = True

    def __post_init__(self) -> None:
        if self.output_dir_relative != "segmentation":
            # Per OQ-SEG-LAYOUT-01: only `segmentation/` allowed.
            raise Dev06ConfigError(
                f"storage.output_dir_relative must be 'segmentation' "
                f"(per OQ-SEG-LAYOUT-01); got {self.output_dir_relative!r}."
            )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06LoggingConfig:
    """Per-stage logging configuration (mirrors DEV-04 / DEV-05)."""

    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
    log_dir_relative: str = "data/prototype/datasets"
    emit_to_console: bool = True

    def __post_init__(self) -> None:
        if self.level not in VALID_LOG_LEVELS:
            raise Dev06ConfigError(
                f"logging.level must be one of {sorted(VALID_LOG_LEVELS)}; " f"got {self.level!r}."
            )


# ---------------------------------------------------------------------------
# Research safety
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06ResearchSafetyConfig:
    """Research-safety sub-config (defence-in-depth).

    Always sets ``segmentation_scope = "PROFILED_PROTOTYPE"`` to mirror
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
    segmentation_scope: str = "PROFILED_PROTOTYPE"

    def __post_init__(self) -> None:
        if self.segmentation_scope != "PROFILED_PROTOTYPE":
            raise Dev06ConfigError(
                f"research_safety.segmentation_scope must be "
                f"'PROFILED_PROTOTYPE' (got {self.segmentation_scope!r}); "
                "the prototype layer never auto-promotes."
            )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06ValidationConfig:
    """Input validation policy (mirrors DEV-04 / DEV-05 pattern).

    DEV-06 re-reads the DEV-04 ``cluster_labels_*.parquet`` and the
    DEV-03 ``ml_dataset_*.parquet``. These settings mirror ML-01's
    validation policy. The CustomerID leak check
    (``exclude_customer_id_from_features``) is critical because the
    profile is computed on a feature matrix that must not include the
    customer identifier.

    Unlike DEV-05, ``require_no_nan`` defaults to ``False`` — DEV-06
    computes profile statistics that handle NaN gracefully (pandas
    ``describe()`` skips NaN by default), and a strict no-NaN check
    would force upstream imputation decisions that are out of DEV-06's
    scope.
    """

    min_samples: int = 2
    min_features: int = 1
    require_no_nan: bool = False
    exclude_customer_id_from_features: bool = True


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06CompareConfig:
    """Compare-segmentations display policy (per OQ-SEG-COMPARE-01)."""

    emit_singleton_group: bool = True
    show_provenance_per_row: bool = True
    disclaimer_text: str = "no ranking, recommendation, or winner annotation is emitted"


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev06Config:
    """The complete DEV-06 configuration."""

    noise_policy: Dev06NoisePolicyConfig = field(default_factory=Dev06NoisePolicyConfig)
    statistics: Dev06StatisticsConfig = field(default_factory=Dev06StatisticsConfig)
    characteristic_rules: Dev06CharacteristicRulesConfig = field(
        default_factory=Dev06CharacteristicRulesConfig
    )
    display: Dev06DisplayConfig = field(default_factory=Dev06DisplayConfig)
    storage: Dev06StorageConfig = field(default_factory=Dev06StorageConfig)
    logging: Dev06LoggingConfig = field(default_factory=Dev06LoggingConfig)
    research_safety: Dev06ResearchSafetyConfig = field(default_factory=Dev06ResearchSafetyConfig)
    validation: Dev06ValidationConfig = field(default_factory=Dev06ValidationConfig)
    compare: Dev06CompareConfig = field(default_factory=Dev06CompareConfig)


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Dev06ConfigError(f"DEV-06 config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise Dev06ConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise Dev06ConfigError(
            f"DEV-06 config file {path} must be a YAML mapping; " f"got {type(data).__name__}."
        )
    return data


def _optional_str(container: dict[str, Any], key: str, default: str) -> str:
    if key not in container:
        return default
    v = container[key]
    if not isinstance(v, str):
        raise Dev06ConfigError(f"Expected {key!r} to be a string; got {type(v).__name__}.")
    return v


def _optional_bool(container: dict[str, Any], key: str, default: bool) -> bool:
    if key not in container:
        return default
    v = container[key]
    if not isinstance(v, bool):
        raise Dev06ConfigError(f"Expected {key!r} to be a bool; got {type(v).__name__}.")
    return v


def _optional_int(container: dict[str, Any], key: str, default: int) -> int:
    if key not in container:
        return default
    v = container[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise Dev06ConfigError(f"Expected {key!r} to be an int; got {type(v).__name__}.")
    return int(v)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_noise_policy(raw: dict[str, Any] | None) -> Dev06NoisePolicyConfig:
    if raw is None:
        return Dev06NoisePolicyConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(
            f"Expected 'noise_policy' to be a mapping; got {type(raw).__name__}."
        )
    return Dev06NoisePolicyConfig(default=_optional_str(raw, "default", "exclude"))


def _parse_statistics(raw: dict[str, Any] | None) -> Dev06StatisticsConfig:
    if raw is None:
        return Dev06StatisticsConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(f"Expected 'statistics' to be a mapping; got {type(raw).__name__}.")
    numerical_raw = raw.get("numerical", list(DEFAULT_STATISTICS_SET))
    if not isinstance(numerical_raw, list):
        raise Dev06ConfigError(
            f"statistics.numerical must be a list; got {type(numerical_raw).__name__}."
        )
    return Dev06StatisticsConfig(
        numerical=tuple(numerical_raw),
        categorical_topk=_optional_int(raw, "categorical_topk", 10),
        categorical_uniqueness_threshold=_optional_int(raw, "categorical_uniqueness_threshold", 50),
    )


def _parse_characteristic_rules(
    raw: dict[str, Any] | None,
) -> Dev06CharacteristicRulesConfig:
    if raw is None:
        return Dev06CharacteristicRulesConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(
            f"Expected 'characteristic_rules' to be a mapping; got {type(raw).__name__}."
        )
    enabled_raw = raw.get("enabled", None)
    enabled: tuple[str, ...]
    if enabled_raw is None:
        enabled = Dev06CharacteristicRulesConfig().enabled
    elif isinstance(enabled_raw, list):
        enabled = tuple(str(r) for r in enabled_raw)
    else:
        raise Dev06ConfigError(
            f"characteristic_rules.enabled must be a list; got {type(enabled_raw).__name__}."
        )
    return Dev06CharacteristicRulesConfig(
        enabled=enabled,
        z_threshold=float(raw.get("z_threshold", 1.0)),
    )


def _parse_display(raw: dict[str, Any] | None) -> Dev06DisplayConfig:
    if raw is None:
        return Dev06DisplayConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(f"Expected 'display' to be a mapping; got {type(raw).__name__}.")
    return Dev06DisplayConfig(
        percentage_decimals=_optional_int(raw, "percentage_decimals", 2),
        missing_value_placeholder=_optional_str(raw, "missing_value_placeholder", "--"),
        csv_missing_value=_optional_str(raw, "csv_missing_value", ""),
        disclaimer_text=_optional_str(
            raw,
            "disclaimer_text",
            Dev06DisplayConfig().disclaimer_text,
        ),
    )


def _parse_storage(raw: dict[str, Any] | None) -> Dev06StorageConfig:
    if raw is None:
        return Dev06StorageConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(f"Expected 'storage' to be a mapping; got {type(raw).__name__}.")
    return Dev06StorageConfig(
        output_dir_relative=_optional_str(raw, "output_dir_relative", "segmentation"),
        emit_profiles_csv=_optional_bool(raw, "emit_profiles_csv", True),
        emit_profiles_json=_optional_bool(raw, "emit_profiles_json", True),
        emit_characteristics_json=_optional_bool(raw, "emit_characteristics_json", True),
        emit_sizes_long_csv=_optional_bool(raw, "emit_sizes_long_csv", True),
    )


def _parse_logging(raw: dict[str, Any] | None) -> Dev06LoggingConfig:
    if raw is None:
        return Dev06LoggingConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(f"Expected 'logging' to be a mapping; got {type(raw).__name__}.")
    return Dev06LoggingConfig(
        level=_optional_str(raw, "level", "INFO"),
        format=_optional_str(
            raw,
            "format",
            "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s",
        ),
        log_dir_relative=_optional_str(raw, "log_dir_relative", "data/prototype/datasets"),
        emit_to_console=_optional_bool(raw, "emit_to_console", True),
    )


def _parse_research_safety(raw: dict[str, Any] | None) -> Dev06ResearchSafetyConfig:
    if raw is None:
        return Dev06ResearchSafetyConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(
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
        raise Dev06ConfigError("research_safety.readonly_paths must be a list.")
    return Dev06ResearchSafetyConfig(
        readonly_paths=readonly_paths,
        never_promote_to_research=_optional_bool(raw, "never_promote_to_research", True),
        segmentation_scope=_optional_str(raw, "segmentation_scope", "PROFILED_PROTOTYPE"),
    )


def _parse_validation(raw: dict[str, Any] | None) -> Dev06ValidationConfig:
    if raw is None:
        return Dev06ValidationConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(f"Expected 'validation' to be a mapping; got {type(raw).__name__}.")
    return Dev06ValidationConfig(
        min_samples=_optional_int(raw, "min_samples", 2),
        min_features=_optional_int(raw, "min_features", 1),
        require_no_nan=_optional_bool(raw, "require_no_nan", False),
        exclude_customer_id_from_features=_optional_bool(
            raw, "exclude_customer_id_from_features", True
        ),
    )


def _parse_compare(raw: dict[str, Any] | None) -> Dev06CompareConfig:
    if raw is None:
        return Dev06CompareConfig()
    if not isinstance(raw, dict):
        raise Dev06ConfigError(f"Expected 'compare' to be a mapping; got {type(raw).__name__}.")
    return Dev06CompareConfig(
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


def find_default_dev06_config_path() -> Path:
    """Return the canonical path to ``configs/dev06_segmentation.yaml``."""
    return DEFAULT_DEV06_CONFIG_PATH


def load_dev06_config(path: Path | None = None) -> tuple[Dev06Config, str]:
    """Load ``configs/dev06_segmentation.yaml`` and return typed config + raw text.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit YAML path. ``None`` uses
        :data:`DEFAULT_DEV06_CONFIG_PATH`.

    Returns
    -------
    tuple[Dev06Config, str]
        Typed config dataclass and the raw YAML text (for config_sha256).

    Raises
    ------
    Dev06ConfigError
        If the YAML is missing, malformed, or a required block is absent.
    """
    if path is None:
        path = DEFAULT_DEV06_CONFIG_PATH

    p = Path(path)
    if not p.exists():
        raise Dev06ConfigError(f"DEV-06 config file not found: {p}")

    raw_text = p.read_text(encoding="utf-8")
    raw = _read_yaml(p)

    if DEV06_CONFIG_TOP_KEY not in raw:
        raise Dev06ConfigError(
            f"DEV-06 config {path} must contain top-level {DEV06_CONFIG_TOP_KEY!r} mapping."
        )
    top = raw[DEV06_CONFIG_TOP_KEY]
    if not isinstance(top, dict):
        raise Dev06ConfigError(
            f"DEV-06 config top-level {DEV06_CONFIG_TOP_KEY!r} must be a mapping; "
            f"got {type(top).__name__}."
        )

    return (
        Dev06Config(
            noise_policy=_parse_noise_policy(top.get("noise_policy")),
            statistics=_parse_statistics(top.get("statistics")),
            characteristic_rules=_parse_characteristic_rules(top.get("characteristic_rules")),
            display=_parse_display(top.get("display")),
            storage=_parse_storage(top.get("storage")),
            logging=_parse_logging(top.get("logging")),
            research_safety=_parse_research_safety(top.get("research_safety")),
            validation=_parse_validation(top.get("validation")),
            compare=_parse_compare(top.get("compare")),
        ),
        raw_text,
    )
