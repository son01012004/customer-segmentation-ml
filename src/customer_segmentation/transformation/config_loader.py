"""FE-06 transformation configuration loader.

Single source of truth for FE-06 transformation pipeline.
Loads configs/transformation.yaml and returns fully-typed dataclasses.

Pattern mirrors customer_segmentation.features.config_loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "DEFAULT_TRANSFORMATION_CONFIG_PATH",
    "TransformationConfig",
    "TransformationConfigError",
    "TransformationStatus",
    "ImputationMethod",
    "TransformationMethod",
    "ScalingMethod",
    "ExperimentalConfig",
    "load_transformation_config",
    "resolve_transformation_config_path",
]


# Paths
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRANSFORMATION_CONFIG_PATH = _REPO_ROOT / "configs" / "transformation.yaml"


# Status markers
STATUS_WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
STATUS_PENDING_REVIEW = "PENDING_REVIEW"
STATUS_MENTOR_REVIEW_PENDING = "MENTOR_REVIEW_PENDING"


class TransformationStatus(StrEnum):
    """Status markers for FE-06 decisions."""

    WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
    PENDING_REVIEW = "PENDING_REVIEW"
    MENTOR_REVIEW_PENDING = "MENTOR_REVIEW_PENDING"


class ImputationMethod(StrEnum):
    """Imputation method."""

    MEDIAN = "median"
    NONE = "none"


class TransformationMethod(StrEnum):
    """Transformation method."""

    NONE = "none"
    LOG1P = "log1p"
    YEO_JOHNSON = "yeo_johnson"


class ScalingMethod(StrEnum):
    """Scaling method."""

    NONE = "none"
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"


class TransformationConfigError(ValueError):
    """Raised when configs/transformation.yaml is malformed or missing keys."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceConfig:
    """Source dataset paths."""

    customer_candidates_path: str
    customer_key: str


@dataclass(frozen=True)
class OutputConfig:
    """Output path configuration."""

    processed_dir: str
    final_clustering_filename: str
    customer_metadata_filename: str
    fitted_pipeline_filename: str
    report_dir: str


@dataclass(frozen=True)
class ImputationWorkingConfig:
    """Imputation working configuration."""

    method: str
    status: str
    review: str
    applied_features: list[str]
    rationale: str


@dataclass(frozen=True)
class ImputationConfig:
    """Imputation configuration."""

    candidates: list[str]
    working: ImputationWorkingConfig


@dataclass(frozen=True)
class TransformationPerFeatureConfig:
    """Per-feature transformation applicability."""

    # Map feature name -> list of applicable methods
    recency: list[str]
    frequency: list[str]
    monetary: list[str]
    total_quantity: list[str]
    average_quantity: list[str]
    basket_size: list[str]
    tenure_days: list[str]
    purchase_interval_mean: list[str]
    purchase_interval_std: list[str]
    active_days: list[str]
    average_invoice_value: list[str]
    products_per_invoice: list[str]
    cancellation_rate: list[str]
    return_rate: list[str]

    def get_for_feature(self, feature: str) -> list[str]:
        """Get applicable transformation methods for a feature."""
        mapping = {
            "Recency": self.recency,
            "Frequency": self.frequency,
            "Monetary": self.monetary,
            "TotalQuantity": self.total_quantity,
            "AverageQuantity": self.average_quantity,
            "BasketSize": self.basket_size,
            "TenureDays": self.tenure_days,
            "PurchaseIntervalMean": self.purchase_interval_mean,
            "PurchaseIntervalStd": self.purchase_interval_std,
            "ActiveDays": self.active_days,
            "AverageInvoiceValue": self.average_invoice_value,
            "ProductsPerInvoice": self.products_per_invoice,
            "CancellationRate": self.cancellation_rate,
            "ReturnRate": self.return_rate,
        }
        return mapping.get(feature, ["none"])


@dataclass(frozen=True)
class TransformationWorkingConfig:
    """Transformation working configuration."""

    method: str
    status: str
    review: str
    rationale: str


@dataclass(frozen=True)
class TransformationPolicyConfig:
    """Transformation policy configuration."""

    candidates: list[str]
    per_feature_applicability: TransformationPerFeatureConfig
    working: TransformationWorkingConfig


@dataclass(frozen=True)
class ScalingWorkingConfig:
    """Scaling working configuration."""

    method: str
    status: str
    review: str
    rationale: str


@dataclass(frozen=True)
class ScalingPolicyConfig:
    """Scaling policy configuration."""

    candidates: list[str]
    working: ScalingWorkingConfig


@dataclass(frozen=True)
class ExperimentalConfig:
    """Experimental configuration entry."""

    id: str
    transformation: str
    scaling: str
    is_full_matrix: bool


@dataclass(frozen=True)
class WorkingConfigurationConfig:
    """Working configuration (C7)."""

    id: str
    transformation: str
    scaling: str
    imputation: str
    status: str
    review: str
    features_affected: str
    notes: list[str]


@dataclass(frozen=True)
class FeatureEligibilityConfig:
    """Feature eligibility gate configuration."""

    include_layers: list[str]
    exclude_identifiers: bool
    exclude_unsupported: bool
    exclude_base_reference: bool
    max_missing_ratio: float
    redundancy_threshold: float
    auto_drop_redundant: bool


@dataclass(frozen=True)
class MetadataConfig:
    """Metadata configuration."""

    stage: str
    dataset_version: str
    dataset_version_meaning: str
    task_description: str
    scope_boundaries: list[str]
    notes: list[str]


@dataclass(frozen=True)
class TransformationConfig:
    """Top-level transformation configuration."""

    enabled: bool
    random_seed: int | None
    random_seed_reason: str
    source: SourceConfig
    output: OutputConfig
    feature_eligibility: FeatureEligibilityConfig
    imputation: ImputationConfig
    transformation_policy: TransformationPolicyConfig
    scaling_policy: ScalingPolicyConfig
    experimental_configurations: list[ExperimentalConfig]
    working_configuration: WorkingConfigurationConfig
    metadata: MetadataConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file as a nested dict."""
    if not path.exists():
        raise TransformationConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise TransformationConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if data is None:
        raise TransformationConfigError(f"Config file {path} is empty.")
    if not isinstance(data, dict):
        raise TransformationConfigError(
            f"Config file {path} must be a YAML mapping; got {type(data).__name__}."
        )
    return data


def _require_str(container: dict[str, Any], key: str, *, container_name: str) -> str:
    """Look up key, expecting a string."""
    value = container.get(key)
    if value is None:
        raise TransformationConfigError(f"Missing required key {key!r} under {container_name!r}.")
    if not isinstance(value, str):
        raise TransformationConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_bool(container: dict[str, Any], key: str, *, container_name: str) -> bool:
    """Look up key, expecting a bool."""
    value = container.get(key)
    if value is None:
        raise TransformationConfigError(f"Missing required key {key!r} under {container_name!r}.")
    if not isinstance(value, bool):
        raise TransformationConfigError(
            f"Expected {key!r} under {container_name!r} to be a boolean; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_number(container: dict[str, Any], key: str, *, container_name: str) -> float:
    """Look up key, expecting an int or float."""
    value = container.get(key)
    if value is None:
        raise TransformationConfigError(f"Missing required key {key!r} under {container_name!r}.")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransformationConfigError(
            f"Expected {key!r} under {container_name!r} to be a number; "
            f"got {type(value).__name__}={value!r}."
        )
    return float(value)


def _optional_str(container: dict[str, Any], key: str, *, default: str) -> str:
    """Look up key, returning default if missing."""
    value = container.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise TransformationConfigError(
            f"Expected {key!r} to be a string; got {type(value).__name__}={value!r}."
        )
    return value


def _optional_str_or_none(container: dict[str, Any], key: str) -> str | None:
    """Look up key, returning None if missing."""
    value = container.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TransformationConfigError(
            f"Expected {key!r} to be a string or null; got {type(value).__name__}={value!r}."
        )
    return value


def _optional_number(container: dict[str, Any], key: str, *, default: float) -> float:
    """Look up key, returning default if missing."""
    value = container.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransformationConfigError(
            f"Expected {key!r} to be a number; got {type(value).__name__}={value!r}."
        )
    return float(value)


def _require_list(container: dict[str, Any], key: str, *, container_name: str) -> list[Any]:
    """Look up key, expecting a list."""
    value = container.get(key)
    if value is None:
        raise TransformationConfigError(f"Missing required key {key!r} under {container_name!r}.")
    if not isinstance(value, list):
        raise TransformationConfigError(
            f"Expected {key!r} under {container_name!r} to be a list; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _optional_list(
    container: dict[str, Any], key: str, *, default: list[Any] | None = None
) -> list[Any]:
    """Look up key, returning default if missing."""
    value = container.get(key)
    if value is None:
        return default if default is not None else []
    if not isinstance(value, list):
        raise TransformationConfigError(
            f"Expected {key!r} to be a list; got {type(value).__name__}={value!r}."
        )
    return value


def _optional_bool(container: dict[str, Any], key: str, *, default: bool) -> bool:
    """Look up key, returning default if missing."""
    value = container.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise TransformationConfigError(
            f"Expected {key!r} to be a bool; got {type(value).__name__}={value!r}."
        )
    return value


def _optional_int_or_none(container: dict[str, Any], key: str) -> int | None:
    """Look up key, returning None if missing or null."""
    value = container.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lower() == "null":
        return None
    raise TransformationConfigError(
        f"Expected {key!r} to be an integer or null; got {type(value).__name__}={value!r}."
    )


# ---------------------------------------------------------------------------
# Config parsers
# ---------------------------------------------------------------------------


def _parse_source_config(data: dict[str, Any]) -> SourceConfig:
    """Parse source dataset configuration."""
    source = data.get("source", {})
    return SourceConfig(
        customer_candidates_path=_require_str(
            source, "customer_candidates_path", container_name="source"
        ),
        customer_key=_require_str(source, "customer_key", container_name="source"),
    )


def _parse_output_config(data: dict[str, Any]) -> OutputConfig:
    """Parse output configuration."""
    output = data.get("output", {})
    return OutputConfig(
        processed_dir=_require_str(output, "processed_dir", container_name="output"),
        final_clustering_filename=_require_str(
            output, "final_clustering_filename", container_name="output"
        ),
        customer_metadata_filename=_require_str(
            output, "customer_metadata_filename", container_name="output"
        ),
        fitted_pipeline_filename=_require_str(
            output, "fitted_pipeline_filename", container_name="output"
        ),
        report_dir=_require_str(output, "report_dir", container_name="output"),
    )


def _parse_feature_eligibility(data: dict[str, Any]) -> FeatureEligibilityConfig:
    """Parse feature eligibility gate configuration."""
    fe = data.get("feature_eligibility", {})
    return FeatureEligibilityConfig(
        include_layers=_optional_list(fe, "include_layers", default=["CANDIDATE"]),
        exclude_identifiers=_optional_bool(fe, "exclude_identifiers", default=True),
        exclude_unsupported=_optional_bool(fe, "exclude_unsupported", default=True),
        exclude_base_reference=_optional_bool(fe, "exclude_base_reference", default=True),
        max_missing_ratio=_optional_number(fe, "max_missing_ratio", default=0.5),
        redundancy_threshold=_optional_number(fe, "redundancy_threshold", default=0.95),
        auto_drop_redundant=_optional_bool(fe, "auto_drop_redundant", default=False),
    )


def _parse_imputation_working(data: dict[str, Any]) -> ImputationWorkingConfig:
    """Parse imputation working configuration."""
    return ImputationWorkingConfig(
        method=_require_str(data, "method", container_name="imputation.working"),
        status=_require_str(data, "status", container_name="imputation.working"),
        review=_require_str(data, "review", container_name="imputation.working"),
        applied_features=_optional_list(data, "applied_features", default=[]),
        rationale=_optional_str(data, "rationale", default=""),
    )


def _parse_imputation_config(data: dict[str, Any]) -> ImputationConfig:
    """Parse imputation configuration."""
    imp = data.get("imputation", {})
    return ImputationConfig(
        candidates=_optional_list(imp, "candidates", default=["median"]),
        working=_parse_imputation_working(imp.get("working", {})),
    )


def _parse_per_feature_applicability(data: dict[str, Any]) -> TransformationPerFeatureConfig:
    """Parse per-feature transformation applicability."""
    pf = data.get("per_feature_applicability", {})
    return TransformationPerFeatureConfig(
        recency=_optional_list(pf, "Recency", default=["none", "log1p", "yeo_johnson"]),
        frequency=_optional_list(pf, "Frequency", default=["none", "log1p", "yeo_johnson"]),
        monetary=_optional_list(pf, "Monetary", default=["none", "yeo_johnson"]),
        total_quantity=_optional_list(pf, "TotalQuantity", default=["none", "yeo_johnson"]),
        average_quantity=_optional_list(pf, "AverageQuantity", default=["none", "yeo_johnson"]),
        basket_size=_optional_list(pf, "BasketSize", default=["none", "yeo_johnson"]),
        tenure_days=_optional_list(pf, "TenureDays", default=["none", "log1p", "yeo_johnson"]),
        purchase_interval_mean=_optional_list(
            pf, "PurchaseIntervalMean", default=["none", "log1p", "yeo_johnson"]
        ),
        purchase_interval_std=_optional_list(
            pf, "PurchaseIntervalStd", default=["none", "log1p", "yeo_johnson"]
        ),
        active_days=_optional_list(pf, "ActiveDays", default=["none", "log1p", "yeo_johnson"]),
        average_invoice_value=_optional_list(
            pf, "AverageInvoiceValue", default=["none", "yeo_johnson"]
        ),
        products_per_invoice=_optional_list(
            pf, "ProductsPerInvoice", default=["none", "log1p", "yeo_johnson"]
        ),
        cancellation_rate=_optional_list(pf, "CancellationRate", default=["none", "yeo_johnson"]),
        return_rate=_optional_list(pf, "ReturnRate", default=["none", "yeo_johnson"]),
    )


def _parse_transformation_working(data: dict[str, Any]) -> TransformationWorkingConfig:
    """Parse transformation working configuration."""
    return TransformationWorkingConfig(
        method=_require_str(data, "method", container_name="transformation_policy.working"),
        status=_require_str(data, "status", container_name="transformation_policy.working"),
        review=_require_str(data, "review", container_name="transformation_policy.working"),
        rationale=_optional_str(data, "rationale", default=""),
    )


def _parse_transformation_policy(data: dict[str, Any]) -> TransformationPolicyConfig:
    """Parse transformation policy configuration."""
    tp = data.get("transformation_policy", {})
    return TransformationPolicyConfig(
        candidates=_optional_list(tp, "candidates", default=["none", "log1p", "yeo_johnson"]),
        per_feature_applicability=_parse_per_feature_applicability(
            tp.get("per_feature_applicability", {})
        ),
        working=_parse_transformation_working(tp.get("working", {})),
    )


def _parse_scaling_working(data: dict[str, Any]) -> ScalingWorkingConfig:
    """Parse scaling working configuration."""
    return ScalingWorkingConfig(
        method=_require_str(data, "method", container_name="scaling_policy.working"),
        status=_require_str(data, "status", container_name="scaling_policy.working"),
        review=_require_str(data, "review", container_name="scaling_policy.working"),
        rationale=_optional_str(data, "rationale", default=""),
    )


def _parse_scaling_policy(data: dict[str, Any]) -> ScalingPolicyConfig:
    """Parse scaling policy configuration."""
    sp = data.get("scaling_policy", {})
    return ScalingPolicyConfig(
        candidates=_optional_list(
            sp, "candidates", default=["none", "standard", "minmax", "robust"]
        ),
        working=_parse_scaling_working(sp.get("working", {})),
    )


def _parse_experimental_config(entry: dict[str, Any]) -> ExperimentalConfig:
    """Parse an experimental configuration entry."""
    return ExperimentalConfig(
        id=_require_str(entry, "id", container_name="experimental_configurations.entry"),
        transformation=_require_str(
            entry, "transformation", container_name="experimental_configurations.entry"
        ),
        scaling=_require_str(entry, "scaling", container_name="experimental_configurations.entry"),
        is_full_matrix=_optional_bool(entry, "is_full_matrix", default=True),
    )


def _parse_working_configuration(data: dict[str, Any]) -> WorkingConfigurationConfig:
    """Parse working configuration."""
    return WorkingConfigurationConfig(
        id=_require_str(data, "id", container_name="working_configuration"),
        transformation=_require_str(data, "transformation", container_name="working_configuration"),
        scaling=_require_str(data, "scaling", container_name="working_configuration"),
        imputation=_require_str(data, "imputation", container_name="working_configuration"),
        status=_require_str(data, "status", container_name="working_configuration"),
        review=_require_str(data, "review", container_name="working_configuration"),
        features_affected=_require_str(
            data, "features_affected", container_name="working_configuration"
        ),
        notes=_optional_list(data, "notes", default=[]),
    )


def _parse_metadata_config(data: dict[str, Any]) -> MetadataConfig:
    """Parse metadata configuration."""
    meta = data.get("metadata", {})
    return MetadataConfig(
        stage=_require_str(meta, "stage", container_name="metadata"),
        dataset_version=_require_str(meta, "dataset_version", container_name="metadata"),
        dataset_version_meaning=_require_str(
            meta, "dataset_version_meaning", container_name="metadata"
        ),
        task_description=_optional_str(meta, "task_description", default=""),
        scope_boundaries=_optional_list(meta, "scope_boundaries", default=[]),
        notes=_optional_list(meta, "notes", default=[]),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_transformation_config_path(explicit: Path | None = None) -> Path | None:
    """Pick the transformation config path.

    Parameters
    ----------
    explicit : pathlib.Path, optional
        If provided, this path is always returned.

    Returns
    -------
    pathlib.Path or None
        Resolved path or None if neither explicit nor default exists.
    """
    if explicit is not None:
        return explicit
    if DEFAULT_TRANSFORMATION_CONFIG_PATH.exists():
        return DEFAULT_TRANSFORMATION_CONFIG_PATH
    return None


def load_transformation_config(
    path: Path | None = None,
    *,
    strict: bool = True,
) -> TransformationConfig:
    """Load configs/transformation.yaml and return a TransformationConfig.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit path to the YAML file. If None, defaults to
        DEFAULT_TRANSFORMATION_CONFIG_PATH.
    strict : bool, default True
        If True, every required key must be present.

    Returns
    -------
    TransformationConfig
        Fully-typed dataclass instance.

    Raises
    ------
    TransformationConfigError
        If the YAML cannot be read, parsed, or is missing required keys.
    """
    if path is None:
        path = DEFAULT_TRANSFORMATION_CONFIG_PATH

    raw = _read_yaml(path)
    if "transformation" not in raw or not isinstance(raw["transformation"], dict):
        raise TransformationConfigError(
            f"Config file {path} must have a top-level 'transformation' mapping."
        )
    data: dict[str, Any] = raw["transformation"]

    experimental_raw = _optional_list(data, "experimental_configurations", default=[])
    experimental_configs = [_parse_experimental_config(e) for e in experimental_raw]

    return TransformationConfig(
        enabled=_require_bool(data, "enabled", container_name="transformation"),
        random_seed=_optional_int_or_none(data, "random_seed"),
        random_seed_reason=_optional_str(
            data, "random_seed_reason", default="deterministic_pipeline"
        ),
        source=_parse_source_config(data),
        output=_parse_output_config(data),
        feature_eligibility=_parse_feature_eligibility(data),
        imputation=_parse_imputation_config(data),
        transformation_policy=_parse_transformation_policy(data),
        scaling_policy=_parse_scaling_policy(data),
        experimental_configurations=experimental_configs,
        working_configuration=_parse_working_configuration(data.get("working_configuration", {})),
        metadata=_parse_metadata_config(data),
    )
