"""YAML configuration loader for DEV-08 Prototype Visualization Dashboard.

Single source of truth: ``configs/dev08_visualization.yaml``.

The loader mirrors the frozenset + typed-error convention used by
DEV-04/05/06/07 packages.

Top-level structure::

    dev08_visualization:
      schema_version: "1.0.0"
      output_format: "png"
      dpi: 120
      max_runs_per_chart: 30
      max_features_per_heatmap: 30
      include_noise_in_charts: false
      include_noise_in_text: true
      marketing_section: "placeholder"
      display:
        missing_value_placeholder: "--"
        disclaimer_text: "..."
        separator: "  "
      storage:
        output_dir_relative: "visualization"
      logging:
        level: "INFO"
        format: "%(asctime)s | ..."
        emit_to_console: true
      research_safety:
        never_promote_to_research: true
        visualization_scope: "DASHBOARD_PROTOTYPE"

Hard rules
----------
- ``storage.storage_root`` is NOT a key here. The storage root is
  always loaded from ``configs/dev02_dataset_management.yaml``.
  CLI does NOT expose ``--storage-root``.
- ``output_format`` is restricted to a closed set (``png``, ``svg``).
- ``marketing_section`` is restricted to ``{"placeholder", "hidden"}``.
- ``logging.level`` must be in :data:`VALID_LOG_LEVELS`.
- All dataclasses are frozen.
- ``research_safety.never_promote_to_research`` is always True.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationConfigError,
)
from customer_segmentation.prototype.visualization.scope import (
    VISUALIZATION_SCHEMA_VERSION,
)

__all__ = [
    "DEFAULT_DEV08_CONFIG_PATH",
    "DEV08_CONFIG_TOP_KEY",
    "VALID_LOG_LEVELS",
    "VALID_OUTPUT_FORMATS",
    "VALID_MARKETING_SECTIONS",
    "Dev08DisplayConfig",
    "Dev08StorageConfig",
    "Dev08LoggingConfig",
    "Dev08ResearchSafetyConfig",
    "Dev08Config",
    "load_dev08_config",
    "find_default_dev08_config_path",
]


# ---------------------------------------------------------------------------
# Paths / closed sets
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
DEFAULT_DEV08_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "dev08_visualization.yaml"
DEV08_CONFIG_TOP_KEY: str = "dev08_visualization"

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({"png", "svg"})
VALID_MARKETING_SECTIONS: frozenset[str] = frozenset({"placeholder", "hidden"})


# ---------------------------------------------------------------------------
# Sub-config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev08DisplayConfig:
    """Display conventions."""

    missing_value_placeholder: str
    disclaimer_text: str
    separator: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.missing_value_placeholder, str)
            or not self.missing_value_placeholder
        ):
            raise VisualizationConfigError(
                "display.missing_value_placeholder MUST be a non-empty str; "
                f"got {self.missing_value_placeholder!r}."
            )
        if not isinstance(self.disclaimer_text, str) or not self.disclaimer_text:
            raise VisualizationConfigError(
                "display.disclaimer_text MUST be a non-empty str; " f"got {self.disclaimer_text!r}."
            )
        if not isinstance(self.separator, str):
            raise VisualizationConfigError(
                f"display.separator MUST be a str; got {type(self.separator).__name__}."
            )


@dataclass(frozen=True)
class Dev08StorageConfig:
    """Storage layout config (per-segmentation subdirectory)."""

    output_dir_relative: str

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir_relative, str) or not self.output_dir_relative:
            raise VisualizationConfigError(
                f"storage.output_dir_relative must be a non-empty str; "
                f"got {self.output_dir_relative!r}."
            )


@dataclass(frozen=True)
class Dev08LoggingConfig:
    """Logging conventions."""

    level: str
    format: str
    emit_to_console: bool

    def __post_init__(self) -> None:
        if self.level not in VALID_LOG_LEVELS:
            raise VisualizationConfigError(
                f"logging.level {self.level!r} is not in the closed set "
                f"{sorted(VALID_LOG_LEVELS)}."
            )


@dataclass(frozen=True)
class Dev08ResearchSafetyConfig:
    """Research-safety config (always prototype scope)."""

    never_promote_to_research: bool
    visualization_scope: str

    def __post_init__(self) -> None:
        if self.never_promote_to_research is not True:
            raise VisualizationConfigError(
                "research_safety.never_promote_to_research MUST be True; "
                f"got {self.never_promote_to_research!r}."
            )
        # Scope value is informational here (no closed set in scope.py
        # for this layer yet); we only validate it's a non-empty str.
        if not isinstance(self.visualization_scope, str) or not self.visualization_scope:
            raise VisualizationConfigError(
                "research_safety.visualization_scope MUST be a non-empty str; "
                f"got {self.visualization_scope!r}."
            )


@dataclass(frozen=True)
class Dev08Config:
    """Top-level DEV-08 config object."""

    schema_version: str
    output_format: str
    dpi: int
    max_runs_per_chart: int
    max_features_per_heatmap: int
    include_noise_in_charts: bool
    include_noise_in_text: bool
    marketing_section: str
    display: Dev08DisplayConfig
    storage: Dev08StorageConfig
    logging: Dev08LoggingConfig
    research_safety: Dev08ResearchSafetyConfig
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != VISUALIZATION_SCHEMA_VERSION:
            raise VisualizationConfigError(
                f"schema_version {self.schema_version!r} does not match pinned "
                f"version {VISUALIZATION_SCHEMA_VERSION!r}."
            )
        if self.output_format not in VALID_OUTPUT_FORMATS:
            raise VisualizationConfigError(
                f"output_format {self.output_format!r} is not in the closed set "
                f"{sorted(VALID_OUTPUT_FORMATS)}."
            )
        if not isinstance(self.dpi, int) or self.dpi <= 0:
            raise VisualizationConfigError(f"dpi MUST be a positive int; got {self.dpi!r}.")
        if not isinstance(self.max_runs_per_chart, int) or self.max_runs_per_chart <= 0:
            raise VisualizationConfigError(
                f"max_runs_per_chart MUST be a positive int; " f"got {self.max_runs_per_chart!r}."
            )
        if not isinstance(self.max_features_per_heatmap, int) or self.max_features_per_heatmap <= 0:
            raise VisualizationConfigError(
                f"max_features_per_heatmap MUST be a positive int; "
                f"got {self.max_features_per_heatmap!r}."
            )
        if self.marketing_section not in VALID_MARKETING_SECTIONS:
            raise VisualizationConfigError(
                f"marketing_section {self.marketing_section!r} is not in the closed "
                f"set {sorted(VALID_MARKETING_SECTIONS)}."
            )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def find_default_dev08_config_path() -> Path:
    """Return the canonical path to the DEV-08 config (resolved)."""
    return DEFAULT_DEV08_CONFIG_PATH


def load_dev08_config(path: Path | str | None = None) -> Dev08Config:
    """Load and validate the DEV-08 config from YAML.

    Parameters
    ----------
    path : pathlib.Path or str or None
        Path to the config YAML. If None, use the default
        ``configs/dev08_visualization.yaml``.

    Returns
    -------
    Dev08Config
        Validated, frozen config object.

    Raises
    ------
    VisualizationConfigError
        On any structural / value error.
    """
    if path is None:
        path = DEFAULT_DEV08_CONFIG_PATH
    path = Path(path)
    if not path.exists():
        raise VisualizationConfigError(f"DEV-08 config file not found: {path!s}")
    config_text = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(config_text)
    except yaml.YAMLError as exc:
        raise VisualizationConfigError(
            f"Failed to parse DEV-08 config YAML at {path!s}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise VisualizationConfigError(
            f"DEV-08 config at {path!s} must be a YAML mapping; " f"got {type(raw).__name__}."
        )
    if DEV08_CONFIG_TOP_KEY not in raw:
        raise VisualizationConfigError(
            f"DEV-08 config at {path!s} missing top-level key " f"{DEV08_CONFIG_TOP_KEY!r}."
        )
    cfg = raw[DEV08_CONFIG_TOP_KEY]
    if not isinstance(cfg, dict):
        raise VisualizationConfigError(
            f"DEV-08 config top-level key {DEV08_CONFIG_TOP_KEY!r} must be a "
            f"mapping; got {type(cfg).__name__}."
        )

    schema_version = cfg.get("schema_version")
    output_format = str(cfg.get("output_format", "png")).lower()
    dpi = int(cfg.get("dpi", 120))
    max_runs_per_chart = int(cfg.get("max_runs_per_chart", 30))
    max_features_per_heatmap = int(cfg.get("max_features_per_heatmap", 30))
    include_noise_in_charts = bool(cfg.get("include_noise_in_charts", False))
    include_noise_in_text = bool(cfg.get("include_noise_in_text", True))
    marketing_section = str(cfg.get("marketing_section", "placeholder"))

    disp_raw = cfg.get("display", {})
    display = Dev08DisplayConfig(
        missing_value_placeholder=str(disp_raw.get("missing_value_placeholder", "--")),
        disclaimer_text=str(
            disp_raw.get(
                "disclaimer_text",
                "no ranking, recommendation, or winner annotation is emitted; "
                "values are post-preprocessing (scaled/transformed) — "
                "not directly interpretable in original business units",
            )
        ),
        separator=str(disp_raw.get("separator", "  ")),
    )

    stor_raw = cfg.get("storage", {})
    storage = Dev08StorageConfig(
        output_dir_relative=str(stor_raw.get("output_dir_relative", "visualization")),
    )

    log_raw = cfg.get("logging", {})
    logging_cfg = Dev08LoggingConfig(
        level=str(log_raw.get("level", "INFO")).upper(),
        format=str(
            log_raw.get(
                "format",
                "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s",
            )
        ),
        emit_to_console=bool(log_raw.get("emit_to_console", True)),
    )

    rs_raw = cfg.get("research_safety", {})
    research_safety = Dev08ResearchSafetyConfig(
        never_promote_to_research=bool(rs_raw.get("never_promote_to_research", True)),
        visualization_scope=str(rs_raw.get("visualization_scope", "DASHBOARD_PROTOTYPE")),
    )

    return Dev08Config(
        schema_version=str(schema_version),
        output_format=output_format,
        dpi=dpi,
        max_runs_per_chart=max_runs_per_chart,
        max_features_per_heatmap=max_features_per_heatmap,
        include_noise_in_charts=include_noise_in_charts,
        include_noise_in_text=include_noise_in_text,
        marketing_section=marketing_section,
        display=display,
        storage=storage,
        logging=logging_cfg,
        research_safety=research_safety,
        raw=raw,
    )
