"""YAML configuration loader for DEV-09 End-to-End Prototype.

Single source of truth: ``configs/dev09_end_to_end.yaml``.

Top-level structure::

    dev09_end_to_end:
      schema_version: "1.0.0"
      stage_selection:
        algorithm: "kmeans"             # closed set; default per ADR-0003
        skip_visualization: false
        skip_marketing: false
      display:
        disclaimer_text: "..."
        separator: "  "
      storage:
        output_dir_relative: "end_to_end"
        copy_manifests: true
      logging:
        level: "INFO"
        format: "%(asctime)s | ..."
        emit_to_console: true
      research_safety:
        never_promote_to_research: true
        end_to_end_scope: "END_TO_END_PROTOTYPE"

Hard rules
----------
- Stage selection is closed-set: the ``algorithm`` value MUST be one
  of ``kmeans``, ``agglomerative``, ``dbscan``, ``gmm``,
  ``fuzzy_cmeans`` (matching DEV-04's accepted set).
- All dataclasses are frozen.
- ``research_safety.never_promote_to_research`` is always True.
- The DEV-09 config does NOT override per-stage configs; each stage
  loads its own canonical config. ``configs/dev09_end_to_end.yaml``
  only controls orchestration-level choices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from customer_segmentation.prototype.end_to_end.exceptions import Dev09ConfigError
from customer_segmentation.prototype.end_to_end.scope import END_TO_END_SCHEMA_VERSION

__all__ = [
    "DEFAULT_DEV09_CONFIG_PATH",
    "DEV09_CONFIG_TOP_KEY",
    "VALID_LOG_LEVELS",
    "VALID_ALGORITHMS",
    "Dev09DisplayConfig",
    "Dev09StageSelectionConfig",
    "Dev09StorageConfig",
    "Dev09LoggingConfig",
    "Dev09PersistenceConfig",
    "Dev09ResearchSafetyConfig",
    "Dev09Config",
    "load_dev09_config",
]


# ---------------------------------------------------------------------------
# Paths / closed sets
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
DEFAULT_DEV09_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "dev09_end_to_end.yaml"
DEV09_CONFIG_TOP_KEY: str = "dev09_end_to_end"

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
# Closed set mirroring DEV-04's algorithm choices (ADR-0003).
VALID_ALGORITHMS: frozenset[str] = frozenset(
    {"kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"}
)


# ---------------------------------------------------------------------------
# Sub-config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev09DisplayConfig:
    """Display conventions for the end-to-end summary."""

    disclaimer_text: str
    separator: str

    def __post_init__(self) -> None:
        if not isinstance(self.disclaimer_text, str) or not self.disclaimer_text:
            raise Dev09ConfigError(
                f"display.disclaimer_text MUST be a non-empty str; "
                f"got {self.disclaimer_text!r}."
            )
        if not isinstance(self.separator, str):
            raise Dev09ConfigError(
                f"display.separator MUST be a str; got {type(self.separator).__name__}."
            )


@dataclass(frozen=True)
class Dev09StageSelectionConfig:
    """Stage selection (which algorithm + optional skips)."""

    algorithm: str
    skip_visualization: bool
    skip_marketing: bool

    def __post_init__(self) -> None:
        if not isinstance(self.algorithm, str) or self.algorithm not in VALID_ALGORITHMS:
            raise Dev09ConfigError(
                f"stage_selection.algorithm {self.algorithm!r} is not in the closed "
                f"set {sorted(VALID_ALGORITHMS)}."
            )
        if not isinstance(self.skip_visualization, bool):
            raise Dev09ConfigError(
                f"stage_selection.skip_visualization MUST be a bool; "
                f"got {type(self.skip_visualization).__name__}."
            )
        if not isinstance(self.skip_marketing, bool):
            raise Dev09ConfigError(
                f"stage_selection.skip_marketing MUST be a bool; "
                f"got {type(self.skip_marketing).__name__}."
            )


@dataclass(frozen=True)
class Dev09StorageConfig:
    """Storage layout for the end-to-end run summary."""

    output_dir_relative: str

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir_relative, str) or not self.output_dir_relative:
            raise Dev09ConfigError(
                f"storage.output_dir_relative MUST be a non-empty str; "
                f"got {self.output_dir_relative!r}."
            )


@dataclass(frozen=True)
class Dev09LoggingConfig:
    """Logging conventions."""

    level: str
    format: str
    emit_to_console: bool

    def __post_init__(self) -> None:
        if self.level not in VALID_LOG_LEVELS:
            raise Dev09ConfigError(
                f"logging.level {self.level!r} is not in the closed set "
                f"{sorted(VALID_LOG_LEVELS)}."
            )


@dataclass(frozen=True)
class Dev09PersistenceConfig:
    """Persistence behaviour flags."""

    copy_manifests: bool

    def __post_init__(self) -> None:
        if not isinstance(self.copy_manifests, bool):
            raise Dev09ConfigError(
                f"persistence.copy_manifests MUST be a bool; "
                f"got {type(self.copy_manifests).__name__}."
            )


@dataclass(frozen=True)
class Dev09ResearchSafetyConfig:
    """Research-safety config (always prototype scope)."""

    never_promote_to_research: bool
    end_to_end_scope: str

    def __post_init__(self) -> None:
        if self.never_promote_to_research is not True:
            raise Dev09ConfigError(
                f"research_safety.never_promote_to_research MUST be True; "
                f"got {self.never_promote_to_research!r}."
            )
        if not isinstance(self.end_to_end_scope, str) or not self.end_to_end_scope:
            raise Dev09ConfigError(
                f"research_safety.end_to_end_scope MUST be a non-empty str; "
                f"got {self.end_to_end_scope!r}."
            )


@dataclass(frozen=True)
class Dev09Config:
    """Top-level DEV-09 config object."""

    schema_version: str
    stage_selection: Dev09StageSelectionConfig
    display: Dev09DisplayConfig
    storage: Dev09StorageConfig
    logging: Dev09LoggingConfig
    persistence: Dev09PersistenceConfig
    research_safety: Dev09ResearchSafetyConfig
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != END_TO_END_SCHEMA_VERSION:
            raise Dev09ConfigError(
                f"schema_version {self.schema_version!r} does not match pinned "
                f"version {END_TO_END_SCHEMA_VERSION!r}."
            )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_dev09_config(path: Path | str | None = None) -> Dev09Config:
    """Load and validate the DEV-09 config from YAML.

    Parameters
    ----------
    path : pathlib.Path or str or None
        Path to the config YAML. If None, use the default
        ``configs/dev09_end_to_end.yaml``.

    Returns
    -------
    Dev09Config
        Validated, frozen config object.

    Raises
    ------
    Dev09ConfigError
        On any structural / value error.
    """
    if path is None:
        path = DEFAULT_DEV09_CONFIG_PATH
    path = Path(path)
    if not path.exists():
        raise Dev09ConfigError(f"DEV-09 config file not found: {path!s}")
    config_text = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(config_text)
    except yaml.YAMLError as exc:
        raise Dev09ConfigError(f"Failed to parse DEV-09 config YAML at {path!s}: {exc}") from exc
    if not isinstance(raw, dict):
        raise Dev09ConfigError(
            f"DEV-09 config at {path!s} must be a YAML mapping; " f"got {type(raw).__name__}."
        )
    if DEV09_CONFIG_TOP_KEY not in raw:
        raise Dev09ConfigError(
            f"DEV-09 config at {path!s} missing top-level key " f"{DEV09_CONFIG_TOP_KEY!r}."
        )
    cfg = raw[DEV09_CONFIG_TOP_KEY]
    if not isinstance(cfg, dict):
        raise Dev09ConfigError(
            f"DEV-09 config top-level key {DEV09_CONFIG_TOP_KEY!r} must be a "
            f"mapping; got {type(cfg).__name__}."
        )

    schema_version = cfg.get("schema_version")
    if not isinstance(schema_version, str):
        raise Dev09ConfigError(
            f"schema_version MUST be a str; got {type(schema_version).__name__}."
        )

    stage_raw = cfg.get("stage_selection", {})
    stage_selection = Dev09StageSelectionConfig(
        algorithm=str(stage_raw.get("algorithm", "kmeans")).lower(),
        skip_visualization=bool(stage_raw.get("skip_visualization", False)),
        skip_marketing=bool(stage_raw.get("skip_marketing", False)),
    )

    disp_raw = cfg.get("display", {})
    display = Dev09DisplayConfig(
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
    storage = Dev09StorageConfig(
        output_dir_relative=str(stor_raw.get("output_dir_relative", "end_to_end")),
    )

    log_raw = cfg.get("logging", {})
    logging_cfg = Dev09LoggingConfig(
        level=str(log_raw.get("level", "INFO")).upper(),
        format=str(
            log_raw.get(
                "format",
                "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s",
            )
        ),
        emit_to_console=bool(log_raw.get("emit_to_console", True)),
    )

    persist_raw = cfg.get("persistence", {})
    persistence = Dev09PersistenceConfig(
        copy_manifests=bool(persist_raw.get("copy_manifests", True)),
    )

    rs_raw = cfg.get("research_safety", {})
    research_safety = Dev09ResearchSafetyConfig(
        never_promote_to_research=bool(rs_raw.get("never_promote_to_research", True)),
        end_to_end_scope=str(rs_raw.get("end_to_end_scope", "END_TO_END_PROTOTYPE")),
    )

    return Dev09Config(
        schema_version=schema_version,
        stage_selection=stage_selection,
        display=display,
        storage=storage,
        logging=logging_cfg,
        persistence=persistence,
        research_safety=research_safety,
        raw=raw,
    )
