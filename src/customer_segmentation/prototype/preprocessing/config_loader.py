"""YAML configuration loader for DEV-03 Prototype Preprocessing.

Single source of truth: ``configs/dev03_preprocessing.yaml``.

The loader mirrors the frozenset + typed-error convention used by
:mod:`customer_segmentation.config.loader` and
:mod:`customer_segmentation.aggregation.config_loader`.

Top-level structure (all blocks required):

    dev03_preprocessing:
      preprocessing:
        cleaning: {...}
        transformation: {...}
        outlier: {...}
        logging: {...}
        storage: {...}
        research_safety: {...}
      feature_generation:
        aggregation: {...}
        features: {...}
        optional_transform: {...}
        reference_date: {...}

Failure modes
-------------
:func:`load_dev03_config` raises :class:`Dev03ConfigError` when the
YAML is malformed or a required key is missing. Strict mode is the
only mode (DEV-03 does not fall back silently).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from customer_segmentation.prototype.preprocessing.scope import (
    IMPUTATION_METHODS,
    OUTLIER_ACTIONS,
    OUTLIER_METHODS,
    CleaningRuleStatus,
    FeatureStatus,
    ScalingMethod,
    TransformationMethod,
)

__all__ = [
    "DEFAULT_DEV03_CONFIG_PATH",
    "DEV03_CONFIG_TOP_KEY",
    "Dev03ConfigError",
    "PreprocessingConfig",
    "PreprocessingCleaningConfig",
    "PreprocessingCleaningInvalidRecordsConfig",
    "PreprocessingTransformationConfig",
    "PreprocessingOutlierConfig",
    "PreprocessingLoggingConfig",
    "PreprocessingStorageConfig",
    "PreprocessingResearchSafetyConfig",
    "FeatureGenerationBlockConfig",
    "FeatureGenerationAggregationConfig",
    "FeatureGenerationFeaturesConfig",
    "FeatureGenerationOptionalTransformConfig",
    "FeatureGenerationReferenceDateConfig",
    "Dev03Config",
    "load_dev03_config",
    "find_default_dev03_config_path",
]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
DEFAULT_DEV03_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "dev03_preprocessing.yaml"
DEV03_CONFIG_TOP_KEY: str = "dev03_preprocessing"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev03ConfigError(ValueError):
    """Raised when ``configs/dev03_preprocessing.yaml`` is malformed."""


# ---------------------------------------------------------------------------
# Logging level enum helper
# ---------------------------------------------------------------------------

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# ---------------------------------------------------------------------------
# Cleaning-rule sub-block (mirrors FE-02 with status annotations)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreprocessingCleaningInvalidRecordsConfig:
    """Invalid-record rules (1:1 with FE-02 InvalidRecordRules).

    Status annotations are inherited verbatim from FE-02 (CL-01..CL-10).
    DEV-03 does **not** reclassify these. The single source of truth
    for status is :file:`configs/preprocessing.yaml` KEY_ANNOTATIONS;
    this dataclass simply mirrors the values.
    """

    drop_missing_invoice_no: bool = True  # CL-10   WORKING_ASSUMPTION
    drop_missing_customer_id: bool = True  # CL-01   WORKING_ASSUMPTION
    drop_missing_description: bool = True  # CL-03   WORKING_ASSUMPTION
    drop_unparseable_invoice_date: bool = True  # CL-04   WORKING_ASSUMPTION
    drop_zero_quantity: bool = True  # CL-05   WORKING_ASSUMPTION
    drop_non_positive_unit_price: bool = True  # CL-07   WORKING_ASSUMPTION
    flag_cancellations: bool = True  # CL-08   PENDING_MENTOR_REVIEW
    flag_returns: bool = True  # CL-06   PENDING_MENTOR_REVIEW
    cancellation_prefix: str = "C"

    def status_for(self, rule_id: str) -> str:
        """Return the inherited FE-02 status of a single rule_id.

        Per AGENTS.md §2.1 / §2.5 the status is a fact about the rule,
        not a property of the prototype layer. DEV-03 records it
        verbatim and never reclassifies.
        """
        per_rule_map = {
            "CL-01": CleaningRuleStatus.WORKING_ASSUMPTION.value,
            "CL-03": CleaningRuleStatus.WORKING_ASSUMPTION.value,
            "CL-04": CleaningRuleStatus.WORKING_ASSUMPTION.value,
            "CL-05": CleaningRuleStatus.WORKING_ASSUMPTION.value,
            "CL-06": CleaningRuleStatus.PENDING_MENTOR_REVIEW.value,
            "CL-07": CleaningRuleStatus.WORKING_ASSUMPTION.value,
            "CL-08": CleaningRuleStatus.PENDING_MENTOR_REVIEW.value,
            "CL-09": CleaningRuleStatus.WORKING_ASSUMPTION.value,
            "CL-10": CleaningRuleStatus.WORKING_ASSUMPTION.value,
        }
        if rule_id not in per_rule_map:
            return CleaningRuleStatus.REVIEW_REQUIRED.value
        return per_rule_map[rule_id]


@dataclass(frozen=True)
class PreprocessingCleaningConfig:
    """Cleaning sub-config; mirrors ``configs/preprocessing.yaml``."""

    duplicate_subset: list[str] | None = None
    duplicate_keep: str = "first"
    missing_strategy: str = "keep"
    missing_columns: list[str] = field(default_factory=list)
    invalid_records: PreprocessingCleaningInvalidRecordsConfig = field(
        default_factory=PreprocessingCleaningInvalidRecordsConfig
    )


@dataclass(frozen=True)
class PreprocessingTransformationConfig:
    """Stage D transformation sub-config.

    Mirrors EXP-04 / FE-06 options but each is a
    :class:`TransformationMethod` value. Default ``"none"``.
    """

    transformation: str = "none"
    numeric_columns: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.transformation not in {t.value for t in TransformationMethod}:
            raise Dev03ConfigError(
                f"preprocessing.transformation.transformation must be one of "
                f"{sorted(t.value for t in TransformationMethod)}; got {self.transformation!r}."
            )


@dataclass(frozen=True)
class PreprocessingOutlierConfig:
    """Stage C outlier sub-config; mirrors ``configs/preprocessing.yaml``."""

    action: str = "none"
    method: str = "iqr"
    columns: list[str] = field(default_factory=list)
    iqr_multiplier: float = 1.5
    zscore_threshold: float = 3.0

    def __post_init__(self) -> None:
        if self.action not in OUTLIER_ACTIONS:
            raise Dev03ConfigError(
                f"preprocessing.outlier.action must be one of {sorted(OUTLIER_ACTIONS)}; "
                f"got {self.action!r}."
            )
        if self.method not in OUTLIER_METHODS:
            raise Dev03ConfigError(
                f"preprocessing.outlier.method must be one of {sorted(OUTLIER_METHODS)}; "
                f"got {self.method!r}."
            )
        if self.iqr_multiplier <= 0:
            raise Dev03ConfigError(
                f"preprocessing.outlier.iqr_multiplier must be > 0; got {self.iqr_multiplier}."
            )
        if self.zscore_threshold <= 0:
            raise Dev03ConfigError(
                f"preprocessing.outlier.zscore_threshold must be > 0; "
                f"got {self.zscore_threshold}."
            )


@dataclass(frozen=True)
class PreprocessingLoggingConfig:
    """Per-stage logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    log_dir_relative: str = (
        "data/prototype/datasets"  # placeholder; <dataset_id>/preprocessed/<id>.log
    )
    emit_to_console: bool = True

    def __post_init__(self) -> None:
        if self.level not in VALID_LOG_LEVELS:
            raise Dev03ConfigError(
                f"preprocessing.logging.level must be one of {sorted(VALID_LOG_LEVELS)}; "
                f"got {self.level!r}."
            )


@dataclass(frozen=True)
class PreprocessingStorageConfig:
    """Storage sub-config.

    ``output_format`` is always ``"parquet"`` (the prototype-layer
    canonical format, content-addressed). ``emit_intermediate`` is
    a per-run switch that controls whether the cleaned
    transaction-level parquet is written alongside the ML Dataset.
    """

    output_format: str = "parquet"
    emit_intermediate: bool = True
    csv_max_rows: int = 0  # 0 = no cap

    def __post_init__(self) -> None:
        if self.output_format not in {"parquet", "csv"}:
            raise Dev03ConfigError(
                f"preprocessing.storage.output_format must be 'parquet' or 'csv'; "
                f"got {self.output_format!r}."
            )
        if self.csv_max_rows < 0:
            raise Dev03ConfigError(
                f"preprocessing.storage.csv_max_rows must be >= 0; " f"got {self.csv_max_rows}."
            )


@dataclass(frozen=True)
class PreprocessingResearchSafetyConfig:
    """Research-safety sub-config (defence-in-depth)."""

    readonly_paths: list[str] = field(
        default_factory=lambda: [
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ]
    )


@dataclass(frozen=True)
class PreprocessingConfig:
    """Top-level preprocessing sub-config (Stages A→E defaults)."""

    enabled: bool = True
    cleaning: PreprocessingCleaningConfig = field(default_factory=PreprocessingCleaningConfig)
    transformation: PreprocessingTransformationConfig = field(
        default_factory=PreprocessingTransformationConfig
    )
    outlier: PreprocessingOutlierConfig = field(default_factory=PreprocessingOutlierConfig)
    logging: PreprocessingLoggingConfig = field(default_factory=PreprocessingLoggingConfig)
    storage: PreprocessingStorageConfig = field(default_factory=PreprocessingStorageConfig)
    research_safety: PreprocessingResearchSafetyConfig = field(
        default_factory=PreprocessingResearchSafetyConfig
    )


# ---------------------------------------------------------------------------
# Feature generation sub-config (Stage F)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureGenerationAggregationConfig:
    """Aggregation sub-config (Stage F1)."""

    customer_key: str = "CustomerID"
    line_revenue_quantity_column: str = "Quantity"
    line_revenue_unit_price_column: str = "UnitPrice"
    line_revenue_output_column: str = "LineRevenue"
    source: dict[str, str] = field(
        default_factory=lambda: {
            "role": "primary",
            "cleaned_dataset_path": "",  # resolved at runtime from DEV-03 cleaned intermediate
            "raw_dataset_path": "",  # informational only
        }
    )


@dataclass(frozen=True)
class FeatureGenerationReferenceDateConfig:
    """Reference-date computation method.

    ``from_data_max`` uses ``max(InvoiceDate) + 1 day`` (deterministic,
    matches FE-05 default). ``from_config`` lets the user override
    with a fixed ISO date.
    """

    mode: str = "from_data_max"
    fixed_iso_date: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"from_config", "from_data_max"}:
            raise Dev03ConfigError(
                f"feature_generation.reference_date.mode must be one of "
                f"['from_config', 'from_data_max']; got {self.mode!r}."
            )
        if self.mode == "from_config" and not self.fixed_iso_date:
            raise Dev03ConfigError(
                "feature_generation.reference_date.fixed_iso_date must be set when "
                "mode == 'from_config'."
            )


@dataclass(frozen=True)
class FeatureGenerationFeaturesConfig:
    """Per-feature strategy selection (Stage F2).

    Choices mirror FE-05 defaults:
    - ``MonetarySigned`` (default),
    - ``Frequency_ByInvoice`` (default),
    - ``Signed`` quantity variant (default),
    - ``products_per_invoice`` diversity (default; CategoryCount NOT materialized),
    - ``enabled=True`` for cancellation/return.
    """

    monetary_strategy: str = "signed"  # signed | absolute | purchase_only | cancellation_only
    monetary_status: str = "WORKING_ASSUMPTION"
    frequency_mode: str = "by_invoice"  # by_invoice | by_transaction_line
    frequency_status: str = "WORKING_ASSUMPTION"
    quantity_strategy: str = "signed"  # signed | purchase_only
    quantity_status: str = "WORKING_ASSUMPTION"
    purchase_interval_ddof: int = 1
    diversity_enabled: bool = True
    diversity_strategy: str = "products_per_invoice"
    cancellation_enabled: bool = True
    return_enabled: bool = True

    def __post_init__(self) -> None:
        for status_value in (
            self.monetary_status,
            self.frequency_status,
            self.quantity_status,
        ):
            if status_value not in {s.value for s in FeatureStatus}:
                raise Dev03ConfigError(
                    f"feature_generation.features.*.status must be one of "
                    f"{sorted(s.value for s in FeatureStatus)}; got {status_value!r}."
                )
        if self.purchase_interval_ddof not in {0, 1}:
            raise Dev03ConfigError(
                f"feature_generation.features.purchase_interval_ddof must be 0 or 1; "
                f"got {self.purchase_interval_ddof}."
            )


@dataclass(frozen=True)
class FeatureGenerationOptionalTransformConfig:
    """Stage F3 optional transform/scale (post-aggregation).

    Applies to the customer-level feature matrix only. Mirrors
    :class:`PreprocessingTransformationConfig` style: ``none``
    (default) means identity; ``yeo_johnson × robust`` is the
    C7-like combo (each is ``WORKING_ASSUMPTION``); ``log1p × *
    is allowed for the FE-06 A2 inherit.
    """

    transformation: str = "none"
    scaling: str = "none"
    imputation: str = "median"
    numeric_columns: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.transformation not in {t.value for t in TransformationMethod}:
            raise Dev03ConfigError(
                f"feature_generation.optional_transform.transformation must be one of "
                f"{sorted(t.value for t in TransformationMethod)}; got {self.transformation!r}."
            )
        if self.scaling not in {s.value for s in ScalingMethod}:
            raise Dev03ConfigError(
                f"feature_generation.optional_transform.scaling must be one of "
                f"{sorted(s.value for s in ScalingMethod)}; got {self.scaling!r}."
            )
        if self.imputation not in IMPUTATION_METHODS:
            raise Dev03ConfigError(
                f"feature_generation.optional_transform.imputation must be one of "
                f"{sorted(IMP_METHODS := IMPUTATION_METHODS)}; got {self.imputation!r}."
            )


@dataclass(frozen=True)
class FeatureGenerationBlockConfig:
    """Top-level feature-generation sub-config (Stage F)."""

    aggregation: FeatureGenerationAggregationConfig = field(
        default_factory=FeatureGenerationAggregationConfig
    )
    features: FeatureGenerationFeaturesConfig = field(
        default_factory=FeatureGenerationFeaturesConfig
    )
    optional_transform: FeatureGenerationOptionalTransformConfig = field(
        default_factory=FeatureGenerationOptionalTransformConfig
    )
    reference_date: FeatureGenerationReferenceDateConfig = field(
        default_factory=FeatureGenerationReferenceDateConfig
    )


# ---------------------------------------------------------------------------
# Top-level DEV-03 config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dev03Config:
    """The complete DEV-03 configuration."""

    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    feature_generation: FeatureGenerationBlockConfig = field(
        default_factory=FeatureGenerationBlockConfig
    )


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Dev03ConfigError(f"DEV-03 config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # type: ignore[misc]
        raise Dev03ConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise Dev03ConfigError(
            f"DEV-03 config file {path} must be a YAML mapping; got {type(data).__name__}."
        )
    return data


def _require(container: dict[str, Any], key: str, *, container_name: str) -> Any:
    if key not in container:
        raise Dev03ConfigError(
            f"Missing required key {key!r} under {container_name!r} in DEV-03 config."
        )
    return container[key]


def _require_str(container: dict[str, Any], key: str, *, container_name: str) -> str:
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, str):
        raise Dev03ConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_bool(container: dict[str, Any], key: str, *, container_name: str) -> bool:
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, bool):
        raise Dev03ConfigError(
            f"Expected {key!r} under {container_name!r} to be a boolean; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _optional(container: dict[str, Any], key: str, default: Any = None) -> Any:
    return container.get(key, default)


def _optional_str(container: dict[str, Any], key: str, *, default: str) -> str:
    if key not in container:
        return default
    value = container[key]
    if not isinstance(value, str):
        raise Dev03ConfigError(
            f"Expected {key!r} to be a string; got {type(value).__name__}={value!r}."
        )
    return value


def _optional_list(container: dict[str, Any], key: str) -> list[str]:
    if key not in container:
        return []
    value = container[key]
    if not isinstance(value, list):
        raise Dev03ConfigError(
            f"Expected {key!r} to be a list; got {type(value).__name__}={value!r}."
        )
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise Dev03ConfigError(
                f"Expected all elements of {key!r} to be strings; "
                f"got {type(item).__name__}={item!r}."
            )
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Sub-parsers
# ---------------------------------------------------------------------------


def _parse_invalid_records(raw: dict[str, Any] | None) -> PreprocessingCleaningInvalidRecordsConfig:
    if raw is None:
        return PreprocessingCleaningInvalidRecordsConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'invalid_records' to be a mapping; got {type(raw).__name__}."
        )
    prefix = _optional_str(raw, "cancellation_prefix", default="C")
    return PreprocessingCleaningInvalidRecordsConfig(
        drop_missing_invoice_no=_require_bool(
            raw, "drop_missing_invoice_no", container_name="invalid_records"
        ),
        drop_missing_customer_id=_require_bool(
            raw, "drop_missing_customer_id", container_name="invalid_records"
        ),
        drop_missing_description=_require_bool(
            raw, "drop_missing_description", container_name="invalid_records"
        ),
        drop_unparseable_invoice_date=_require_bool(
            raw, "drop_unparseable_invoice_date", container_name="invalid_records"
        ),
        drop_zero_quantity=_require_bool(
            raw, "drop_zero_quantity", container_name="invalid_records"
        ),
        drop_non_positive_unit_price=_require_bool(
            raw, "drop_non_positive_unit_price", container_name="invalid_records"
        ),
        flag_cancellations=_require_bool(
            raw, "flag_cancellations", container_name="invalid_records"
        ),
        flag_returns=_require_bool(raw, "flag_returns", container_name="invalid_records"),
        cancellation_prefix=prefix,
    )


def _parse_cleaning(raw: dict[str, Any] | None) -> PreprocessingCleaningConfig:
    if raw is None:
        return PreprocessingCleaningConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(f"Expected 'cleaning' to be a mapping; got {type(raw).__name__}.")
    duplicate_subset_raw = _optional(raw, "duplicate_subset")
    duplicate_subset: list[str] | None
    if duplicate_subset_raw is None:
        duplicate_subset = None
    elif isinstance(duplicate_subset_raw, list):
        duplicate_subset = [str(x) for x in duplicate_subset_raw]
    else:
        raise Dev03ConfigError(
            f"Expected 'duplicate_subset' to be a list or null; "
            f"got {type(duplicate_subset_raw).__name__}={duplicate_subset_raw!r}."
        )
    return PreprocessingCleaningConfig(
        duplicate_subset=duplicate_subset,
        duplicate_keep=_optional_str(raw, "duplicate_keep", default="first"),
        missing_strategy=_optional_str(raw, "missing_strategy", default="keep"),
        missing_columns=_optional_list(raw, "missing_columns"),
        invalid_records=_parse_invalid_records(raw.get("invalid_records")),
    )


def _parse_transformation(
    raw: dict[str, Any] | None,
) -> PreprocessingTransformationConfig:
    if raw is None:
        return PreprocessingTransformationConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'transformation' to be a mapping; got {type(raw).__name__}."
        )
    return PreprocessingTransformationConfig(
        transformation=_optional_str(raw, "transformation", default="none"),
        numeric_columns=_optional_list(raw, "numeric_columns"),
    )


def _parse_outlier(raw: dict[str, Any] | None) -> PreprocessingOutlierConfig:
    if raw is None:
        return PreprocessingOutlierConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(f"Expected 'outlier' to be a mapping; got {type(raw).__name__}.")
    iqr = float(_optional(raw, "iqr_multiplier", 1.5))
    zthr = float(_optional(raw, "zscore_threshold", 3.0))
    return PreprocessingOutlierConfig(
        action=_optional_str(raw, "action", default="none"),
        method=_optional_str(raw, "method", default="iqr"),
        columns=_optional_list(raw, "columns"),
        iqr_multiplier=iqr,
        zscore_threshold=zthr,
    )


def _parse_logging(raw: dict[str, Any] | None) -> PreprocessingLoggingConfig:
    if raw is None:
        return PreprocessingLoggingConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(f"Expected 'logging' to be a mapping; got {type(raw).__name__}.")
    emit_console_raw = _optional(raw, "emit_to_console", True)
    if not isinstance(emit_console_raw, bool):
        raise Dev03ConfigError(
            f"Expected 'emit_to_console' to be a bool; got {type(emit_console_raw).__name__}."
        )
    return PreprocessingLoggingConfig(
        level=_optional_str(raw, "level", default="INFO"),
        format=_optional_str(
            raw, "format", default="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ),
        log_dir_relative=_optional_str(raw, "log_dir_relative", default="data/prototype/datasets"),
        emit_to_console=emit_console_raw,
    )


def _parse_storage(raw: dict[str, Any] | None) -> PreprocessingStorageConfig:
    if raw is None:
        return PreprocessingStorageConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(f"Expected 'storage' to be a mapping; got {type(raw).__name__}.")
    emit_raw = _optional(raw, "emit_intermediate", True)
    if not isinstance(emit_raw, bool):
        raise Dev03ConfigError(
            f"Expected 'emit_intermediate' to be a bool; got {type(emit_raw).__name__}."
        )
    csv_max_rows = int(_optional(raw, "csv_max_rows", 0))
    return PreprocessingStorageConfig(
        output_format=_optional_str(raw, "output_format", default="parquet"),
        emit_intermediate=emit_raw,
        csv_max_rows=csv_max_rows,
    )


def _parse_research_safety(
    raw: dict[str, Any] | None,
) -> PreprocessingResearchSafetyConfig:
    if raw is None:
        return PreprocessingResearchSafetyConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'research_safety' to be a mapping; got {type(raw).__name__}."
        )
    return PreprocessingResearchSafetyConfig(
        readonly_paths=_optional_list(raw, "readonly_paths"),
    )


def _parse_preprocessing(raw: dict[str, Any] | None) -> PreprocessingConfig:
    if raw is None:
        return PreprocessingConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'preprocessing' to be a mapping; got {type(raw).__name__}."
        )
    enabled = _optional(raw, "enabled", True)
    if not isinstance(enabled, bool):
        raise Dev03ConfigError(
            f"Expected 'preprocessing.enabled' to be a bool; got {type(enabled).__name__}."
        )
    return PreprocessingConfig(
        enabled=enabled,
        cleaning=_parse_cleaning(raw.get("cleaning")),
        transformation=_parse_transformation(raw.get("transformation")),
        outlier=_parse_outlier(raw.get("outlier")),
        logging=_parse_logging(raw.get("logging")),
        storage=_parse_storage(raw.get("storage")),
        research_safety=_parse_research_safety(raw.get("research_safety")),
    )


def _parse_aggregation(
    raw: dict[str, Any] | None,
) -> FeatureGenerationAggregationConfig:
    if raw is None:
        return FeatureGenerationAggregationConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'aggregation' under feature_generation to be a mapping; "
            f"got {type(raw).__name__}."
        )
    src_raw = raw.get("source") or {}
    if not isinstance(src_raw, dict):
        raise Dev03ConfigError(
            f"Expected 'aggregation.source' to be a mapping; got {type(src_raw).__name__}."
        )
    source: dict[str, str] = {}
    for k in ("role", "cleaned_dataset_path", "raw_dataset_path"):
        v = src_raw.get(k)
        if v is None:
            v = ""
        if not isinstance(v, str):
            raise Dev03ConfigError(
                f"aggregation.source.{k} must be a string; got {type(v).__name__}={v!r}."
            )
        source[k] = v

    return FeatureGenerationAggregationConfig(
        customer_key=_optional_str(raw, "customer_key", default="CustomerID"),
        line_revenue_quantity_column=_optional_str(
            raw, "line_revenue_quantity_column", default="Quantity"
        ),
        line_revenue_unit_price_column=_optional_str(
            raw, "line_revenue_unit_price_column", default="UnitPrice"
        ),
        line_revenue_output_column=_optional_str(
            raw, "line_revenue_output_column", default="LineRevenue"
        ),
        source=source,
    )


def _parse_reference_date(
    raw: dict[str, Any] | None,
) -> FeatureGenerationReferenceDateConfig:
    if raw is None:
        return FeatureGenerationReferenceDateConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'reference_date' to be a mapping; got {type(raw).__name__}."
        )
    return FeatureGenerationReferenceDateConfig(
        mode=_optional_str(raw, "mode", default="from_data_max"),
        fixed_iso_date=raw.get("fixed_iso_date"),
    )


def _parse_features(raw: dict[str, Any] | None) -> FeatureGenerationFeaturesConfig:
    if raw is None:
        return FeatureGenerationFeaturesConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'features' under feature_generation to be a mapping; "
            f"got {type(raw).__name__}."
        )
    diversity_enabled = bool(_optional(raw, "diversity_enabled", True))
    cancellation_enabled = bool(_optional(raw, "cancellation_enabled", True))
    return_raw = _optional(raw, "return_enabled", True)
    return FeatureGenerationFeaturesConfig(
        monetary_strategy=_optional_str(raw, "monetary_strategy", default="signed"),
        monetary_status=_optional_str(raw, "monetary_status", default="WORKING_ASSUMPTION"),
        frequency_mode=_optional_str(raw, "frequency_mode", default="by_invoice"),
        frequency_status=_optional_str(raw, "frequency_status", default="WORKING_ASSUMPTION"),
        quantity_strategy=_optional_str(raw, "quantity_strategy", default="signed"),
        quantity_status=_optional_str(raw, "quantity_status", default="WORKING_ASSUMPTION"),
        purchase_interval_ddof=int(_optional(raw, "purchase_interval_ddof", 1)),
        diversity_enabled=diversity_enabled,
        diversity_strategy=_optional_str(raw, "diversity_strategy", default="products_per_invoice"),
        cancellation_enabled=cancellation_enabled,
        return_enabled=bool(return_raw),
    )


def _parse_optional_transform(
    raw: dict[str, Any] | None,
) -> FeatureGenerationOptionalTransformConfig:
    if raw is None:
        return FeatureGenerationOptionalTransformConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'optional_transform' under feature_generation to be a mapping; "
            f"got {type(raw).__name__}."
        )
    return FeatureGenerationOptionalTransformConfig(
        transformation=_optional_str(raw, "transformation", default="none"),
        scaling=_optional_str(raw, "scaling", default="none"),
        imputation=_optional_str(raw, "imputation", default="median"),
        numeric_columns=_optional_list(raw, "numeric_columns"),
    )


def _parse_feature_generation(
    raw: dict[str, Any] | None,
) -> FeatureGenerationBlockConfig:
    if raw is None:
        return FeatureGenerationBlockConfig()
    if not isinstance(raw, dict):
        raise Dev03ConfigError(
            f"Expected 'feature_generation' to be a mapping; got {type(raw).__name__}."
        )
    return FeatureGenerationBlockConfig(
        aggregation=_parse_aggregation(raw.get("aggregation")),
        features=_parse_features(raw.get("features")),
        optional_transform=_parse_optional_transform(raw.get("optional_transform")),
        reference_date=_parse_reference_date(raw.get("reference_date")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_default_dev03_config_path() -> Path:
    """Return the canonical path to ``configs/dev03_preprocessing.yaml``."""
    return DEFAULT_DEV03_CONFIG_PATH


def load_dev03_config(path: Path | None = None) -> Dev03Config:
    """Load ``configs/dev03_preprocessing.yaml`` and return a typed config.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit YAML path. ``None`` uses
        :data:`DEFAULT_DEV03_CONFIG_PATH`.

    Returns
    -------
    Dev03Config
        Typed config ready to pass to ``run_preprocessing_pipeline``
        and the feature-generation pipeline.

    Raises
    ------
    Dev03ConfigError
        If the YAML is missing / malformed or a required block
        is absent.
    """
    if path is None:
        path = DEFAULT_DEV03_CONFIG_PATH

    raw = _read_yaml(path)
    if DEV03_CONFIG_TOP_KEY not in raw:
        raise Dev03ConfigError(
            f"DEV-03 config {path} must contain a top-level {DEV03_CONFIG_TOP_KEY!r} mapping."
        )
    top = raw[DEV03_CONFIG_TOP_KEY]
    if not isinstance(top, dict):
        raise Dev03ConfigError(
            f"DEV-03 config {path} top-level {DEV03_CONFIG_TOP_KEY!r} must be a mapping; "
            f"got {type(top).__name__}."
        )

    for required in ("preprocessing", "feature_generation"):
        if required not in top:
            raise Dev03ConfigError(
                f"Missing required block {DEV03_CONFIG_TOP_KEY!r}.{required!r} in {path}."
            )

    return Dev03Config(
        preprocessing=_parse_preprocessing(top.get("preprocessing")),
        feature_generation=_parse_feature_generation(top.get("feature_generation")),
    )
