"""YAML configuration loader for DEV-07 Prototype Marketing.

Single source of truth: ``configs/dev07_marketing.yaml``.

The loader mirrors the frozenset + typed-error convention used by
DEV-04/05/06 packages.

Top-level structure::

    dev07_marketing:
      schema_version: "1.0.0"
      availability_default: "REVIEW_REQUIRED"
      mkt_framework:
        path_relative: "docs/marketing"
        version_pattern: "^MKT-0[1-5]__v[0-9]+$"
      display:
        percentage_decimals: 2
        missing_value_placeholder: "--"
        csv_missing_value: ""
        disclaimer_text: "no marketing recommendation, ranking, or winner annotation is emitted; descriptive view only"
      storage:
        output_dir_relative: "marketing"
        emit_manifest_json: true
        emit_recommendations_csv: false
        emit_recommendations_jsonl: false
      logging:
        level: "INFO"
        format: "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
        log_dir_relative: "data/prototype/datasets"
        emit_to_console: true
      research_safety:
        readonly_paths: [...]
        never_promote_to_research: true
        marketing_scope: "MARKETING_PROTOTYPE"
      validation:
        forbid_internal_metrics_as_kpi: true
        forbid_marketing_terminology: true
        require_no_duplicate_segment_id: true
        exclude_dbscan_noise: true

Hard rules
----------
- ``storage.storage_root`` is NOT a key here. The storage root is
  always loaded from ``configs/dev02_dataset_management.yaml``
  (shared with DEV-02/03/04/05/06). CLI does NOT expose
  ``--storage-root``.
- ``availability_default`` is restricted to :data:`AVAILABILITY_STATUSES`.
- ``logging.level`` must be in :data:`VALID_LOG_LEVELS`.
- All dataclasses are frozen.
- Phase A: ``storage.emit_recommendations_csv = false`` and
  ``emit_recommendations_jsonl = false`` per OQ-D07-08 (read-only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from customer_segmentation.prototype.marketing.exceptions import (
    MarketingConfigError,
)
from customer_segmentation.prototype.marketing.scope import (
    AVAILABILITY_STATUSES,
    MARKETING_MANIFEST_SCHEMA_VERSION,
    MARKETING_SCOPES,
)

__all__ = [
    "DEFAULT_DEV07_CONFIG_PATH",
    "DEV07_CONFIG_TOP_KEY",
    "MarketingConfigError",
    "Dev07MktFrameworkConfig",
    "Dev07DisplayConfig",
    "Dev07StorageConfig",
    "Dev07LoggingConfig",
    "Dev07ResearchSafetyConfig",
    "Dev07ValidationConfig",
    "Dev07Config",
    "VALID_LOG_LEVELS",
    "load_dev07_config",
    "find_default_dev07_config_path",
]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
DEFAULT_DEV07_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "dev07_marketing.yaml"
DEV07_CONFIG_TOP_KEY: str = "dev07_marketing"

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# ---------------------------------------------------------------------------
# Sub-config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev07MktFrameworkConfig:
    """MKT framework discovery config (Phase B trigger; ignored ở Phase A)."""

    path_relative: str
    version_pattern: str


@dataclass(frozen=True)
class Dev07DisplayConfig:
    """Display conventions."""

    percentage_decimals: int
    missing_value_placeholder: str
    csv_missing_value: str
    disclaimer_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.percentage_decimals, int) or self.percentage_decimals < 0:
            raise MarketingConfigError(
                f"display.percentage_decimals MUST be a non-negative int; "
                f"got {self.percentage_decimals!r}."
            )


@dataclass(frozen=True)
class Dev07StorageConfig:
    """Storage layout config (Phase A: chỉ emit manifest JSON)."""

    output_dir_relative: str
    emit_manifest_json: bool
    emit_recommendations_csv: bool
    emit_recommendations_jsonl: bool

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir_relative, str) or not self.output_dir_relative:
            raise MarketingConfigError(
                f"storage.output_dir_relative must be a non-empty str; "
                f"got {self.output_dir_relative!r}."
            )


@dataclass(frozen=True)
class Dev07LoggingConfig:
    """Logging conventions."""

    level: str
    format: str
    log_dir_relative: str
    emit_to_console: bool

    def __post_init__(self) -> None:
        if self.level not in VALID_LOG_LEVELS:
            raise MarketingConfigError(
                f"logging.level {self.level!r} is not in the closed set "
                f"{sorted(VALID_LOG_LEVELS)}."
            )


@dataclass(frozen=True)
class Dev07ResearchSafetyConfig:
    """Research-safety config (always prototype scope)."""

    readonly_paths: list[str]
    never_promote_to_research: bool
    marketing_scope: str

    def __post_init__(self) -> None:
        if self.marketing_scope not in MARKETING_SCOPES:
            raise MarketingConfigError(
                f"research_safety.marketing_scope {self.marketing_scope!r} is not "
                f"in the closed set {sorted(MARKETING_SCOPES)}."
            )
        if self.never_promote_to_research is not True:
            raise MarketingConfigError(
                f"research_safety.never_promote_to_research MUST be True; "
                f"got {self.never_promote_to_research!r}."
            )


@dataclass(frozen=True)
class Dev07ValidationConfig:
    """Validation gate knobs (per AGENTS.md §2 + FR-MKT-05/06)."""

    forbid_internal_metrics_as_kpi: bool
    forbid_marketing_terminology: bool
    require_no_duplicate_segment_id: bool
    exclude_dbscan_noise: bool


@dataclass(frozen=True)
class Dev07Config:
    """Top-level DEV-07 config object."""

    schema_version: str
    availability_default: str
    mkt_framework: Dev07MktFrameworkConfig
    display: Dev07DisplayConfig
    storage: Dev07StorageConfig
    logging: Dev07LoggingConfig
    research_safety: Dev07ResearchSafetyConfig
    validation: Dev07ValidationConfig
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != MARKETING_MANIFEST_SCHEMA_VERSION:
            raise MarketingConfigError(
                f"schema_version {self.schema_version!r} does not match pinned "
                f"version {MARKETING_MANIFEST_SCHEMA_VERSION!r}."
            )
        if self.availability_default not in AVAILABILITY_STATUSES:
            raise MarketingConfigError(
                f"availability_default {self.availability_default!r} is not in the "
                f"closed set {sorted(AVAILABILITY_STATUSES)}."
            )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def find_default_dev07_config_path() -> Path:
    """Return the canonical path to the DEV-07 config (resolved)."""
    return DEFAULT_DEV07_CONFIG_PATH


def load_dev07_config(path: Path | str | None = None) -> Dev07Config:
    """Load and validate the DEV-07 config from YAML.

    Parameters
    ----------
    path : pathlib.Path or str or None
        Path to the config YAML. If None, use the default
        ``configs/dev07_marketing.yaml``.

    Returns
    -------
    Dev07Config
        Validated, frozen config object.

    Raises
    ------
    MarketingConfigError
        On any structural / value error.
    """
    if path is None:
        path = DEFAULT_DEV07_CONFIG_PATH
    path = Path(path)
    if not path.exists():
        raise MarketingConfigError(f"DEV-07 config file not found: {path!s}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise MarketingConfigError(
            f"Failed to parse DEV-07 config YAML at {path!s}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise MarketingConfigError(
            f"DEV-07 config at {path!s} must be a YAML mapping; " f"got {type(raw).__name__}."
        )
    if DEV07_CONFIG_TOP_KEY not in raw:
        raise MarketingConfigError(
            f"DEV-07 config at {path!s} missing top-level key " f"{DEV07_CONFIG_TOP_KEY!r}."
        )
    cfg = raw[DEV07_CONFIG_TOP_KEY]
    if not isinstance(cfg, dict):
        raise MarketingConfigError(
            f"DEV-07 config top-level key {DEV07_CONFIG_TOP_KEY!r} must be a mapping; "
            f"got {type(cfg).__name__}."
        )

    # Sub-configs.
    schema_version = cfg.get("schema_version")
    availability_default = cfg.get("availability_default")

    mkt_raw = cfg.get("mkt_framework", {})
    mkt_framework = Dev07MktFrameworkConfig(
        path_relative=str(mkt_raw.get("path_relative", "docs/marketing")),
        version_pattern=str(mkt_raw.get("version_pattern", "^MKT-0[1-5]__v[0-9]+$")),
    )

    disp_raw = cfg.get("display", {})
    display = Dev07DisplayConfig(
        percentage_decimals=int(disp_raw.get("percentage_decimals", 2)),
        missing_value_placeholder=str(disp_raw.get("missing_value_placeholder", "--")),
        csv_missing_value=str(disp_raw.get("csv_missing_value", "")),
        disclaimer_text=str(
            disp_raw.get(
                "disclaimer_text",
                "no marketing recommendation, ranking, or winner annotation is emitted; descriptive view only",
            )
        ),
    )

    stor_raw = cfg.get("storage", {})
    storage = Dev07StorageConfig(
        output_dir_relative=str(stor_raw.get("output_dir_relative", "marketing")),
        emit_manifest_json=bool(stor_raw.get("emit_manifest_json", True)),
        # Phase A: OQ-D07-08 forces read-only; CSV/JSONL emit defaults to False.
        emit_recommendations_csv=bool(stor_raw.get("emit_recommendations_csv", False)),
        emit_recommendations_jsonl=bool(stor_raw.get("emit_recommendations_jsonl", False)),
    )

    log_raw = cfg.get("logging", {})
    logging_cfg = Dev07LoggingConfig(
        level=str(log_raw.get("level", "INFO")).upper(),
        format=str(
            log_raw.get(
                "format",
                "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s",
            )
        ),
        log_dir_relative=str(log_raw.get("log_dir_relative", "data/prototype/datasets")),
        emit_to_console=bool(log_raw.get("emit_to_console", True)),
    )

    rs_raw = cfg.get("research_safety", {})
    research_safety = Dev07ResearchSafetyConfig(
        readonly_paths=[str(p) for p in rs_raw.get("readonly_paths", [])],
        never_promote_to_research=bool(rs_raw.get("never_promote_to_research", True)),
        marketing_scope=str(rs_raw.get("marketing_scope", "MARKETING_PROTOTYPE")),
    )

    val_raw = cfg.get("validation", {})
    validation = Dev07ValidationConfig(
        forbid_internal_metrics_as_kpi=bool(val_raw.get("forbid_internal_metrics_as_kpi", True)),
        forbid_marketing_terminology=bool(val_raw.get("forbid_marketing_terminology", True)),
        require_no_duplicate_segment_id=bool(val_raw.get("require_no_duplicate_segment_id", True)),
        exclude_dbscan_noise=bool(val_raw.get("exclude_dbscan_noise", True)),
    )

    return Dev07Config(
        schema_version=str(schema_version),
        availability_default=str(availability_default),
        mkt_framework=mkt_framework,
        display=display,
        storage=storage,
        logging=logging_cfg,
        research_safety=research_safety,
        validation=validation,
        raw=raw,
    )
