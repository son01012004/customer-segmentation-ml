"""FE-05 feature engineering configuration loader.

Single source of truth for FE-05 candidate feature engineering pipeline.
Loads configs/feature_engineering.yaml and returns fully-typed dataclasses.

Based on the pattern from customer_segmentation.aggregation.config_loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH",
    "FeatureEngineeringConfig",
    "FeatureEngineeringConfigError",
    "FeatureEngineeringStatus",
    "LayerRole",
    "SelectionGateConfig",
    "SelectionDecision",
    "find_default_feature_engineering_config_path",
    "load_feature_engineering_config",
    "resolve_feature_engineering_config_path",
]


# Paths
# __file__ = src/customer_segmentation/features/config_loader.py
# parents[0] = features
# parents[1] = customer_segmentation
# parents[2] = src
# parents[3] = customer-segmentation-ml (REPO_ROOT)
_THIS_DIR = Path(__file__).resolve().parents[3] / "configs"
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "feature_engineering.yaml"


# Status markers
FEATURE_STATUS_WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
FEATURE_STATUS_PENDING_REVIEW = "PENDING_REVIEW"
FEATURE_STATUS_DIAGNOSTIC = "DIAGNOSTIC"
FEATURE_STATUS_MENTOR_REVIEW_PENDING = "MENTOR_REVIEW_PENDING"

VALID_STATUSES: frozenset[str] = frozenset(
    {
        FEATURE_STATUS_WORKING_ASSUMPTION,
        FEATURE_STATUS_PENDING_REVIEW,
        FEATURE_STATUS_DIAGNOSTIC,
        FEATURE_STATUS_MENTOR_REVIEW_PENDING,
    }
)


class FeatureEngineeringStatus(StrEnum):
    """Status markers for feature engineering decisions."""

    WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
    PENDING_REVIEW = "PENDING_REVIEW"
    DIAGNOSTIC = "DIAGNOSTIC"
    MENTOR_REVIEW_PENDING = "MENTOR_REVIEW_PENDING"


class LayerRole(StrEnum):
    """Feature layer classification."""

    IDENTIFIER_ONLY = "IDENTIFIER_ONLY"
    SOURCE_ONLY = "SOURCE_ONLY"
    BASE_REFERENCE = "BASE_REFERENCE"
    CANDIDATE = "CANDIDATE"
    UNSUPPORTED = "UNSUPPORTED"


class SelectionDecision(StrEnum):
    """Feature selection decision outcomes."""

    RETAIN_CANDIDATE = "RETAIN_CANDIDATE"
    EXCLUDE = "EXCLUDE"
    ADJUST = "ADJUST"
    PENDING_REVIEW = "PENDING_REVIEW"


# Gate status
GATE_STATUS_PASS = "PASS"
GATE_STATUS_FAIL = "FAIL"
GATE_STATUS_WARNING = "WARNING"
GATE_STATUS_NOT_APPLICABLE = "N/A"
GATE_STATUS_DIAGNOSTIC = "DIAGNOSTIC_ONLY"


class FeatureEngineeringConfigError(ValueError):
    """Raised when configs/feature_engineering.yaml is malformed or missing keys."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceConfig:
    """Source dataset paths."""

    customer_base_path: str
    transactions_clean_path: str


@dataclass(frozen=True)
class ReferenceDateConfig:
    """Reference date computation settings."""

    mode: str  # "snapshot_max" | "iso_date"
    status: str
    review: str


@dataclass(frozen=True)
class RFMConfig:
    """RFM feature configuration."""

    recency_enabled: bool
    recency_column: str
    recency_aggregation: str
    recency_status: str
    recency_note: str

    frequency_enabled: bool
    frequency_mode: str  # "by_invoice" | "by_transaction_line"
    frequency_status: str
    frequency_note: str
    frequency_output_column: str

    monetary_enabled: bool
    monetary_default_variant: str  # "signed" | "absolute" | "purchase_only" | "cancellation_only"
    monetary_status: str
    monetary_note: str
    monetary_output_column: str


@dataclass(frozen=True)
class QuantityFeatureSpec:
    """Quantity feature specification."""

    name: str
    source: str
    aggregation: str | None
    variant: str
    status: str
    description: str


@dataclass(frozen=True)
class QuantityConfig:
    """Quantity feature configuration."""

    enabled: bool
    default_variant: str
    status: str
    note: str
    features: list[QuantityFeatureSpec]


@dataclass(frozen=True)
class TransactionBehaviorFeatureSpec:
    """Transaction behavior feature specification."""

    name: str
    source: str
    aggregation: str
    status: str
    description: str


@dataclass(frozen=True)
class TransactionBehaviorConfig:
    """Transaction behavior feature configuration."""

    enabled: bool
    features: list[TransactionBehaviorFeatureSpec]


@dataclass(frozen=True)
class DiversityFeatureSpec:
    """Diversity feature specification."""

    name: str
    source: str
    aggregation: str
    status: str
    description: str


@dataclass(frozen=True)
class DiversityConfig:
    """Diversity feature configuration."""

    enabled: bool
    features: list[DiversityFeatureSpec]


@dataclass(frozen=True)
class UnsupportedFeatureSpec:
    """Unsupported feature specification."""

    name: str
    reason: str


@dataclass(frozen=True)
class CancellationFeatureSpec:
    """Cancellation/return feature specification."""

    name: str
    source: str
    aggregation: str
    status: str
    description: str


@dataclass(frozen=True)
class CancellationConfig:
    """Cancellation/return feature configuration."""

    enabled: bool
    features: list[CancellationFeatureSpec]


@dataclass(frozen=True)
class LayerClassification:
    """Feature layer classification."""

    IDENTIFIER_ONLY: list[str]
    SOURCE_ONLY: list[str]
    BASE_REFERENCE: list[str]
    CANDIDATE: list[str]
    UNSUPPORTED: list[str]


@dataclass(frozen=True)
class SelectionGateConfig:
    """Feature selection gate configuration."""

    enabled: bool
    status: str
    threshold: float | None = None
    max_missing_ratio: float | None = None
    n_bootstrap: int | None = None
    alpha: float | None = None
    note: str | None = None


@dataclass(frozen=True)
class SelectionConfig:
    """Feature selection gate configuration."""

    interpretability_gate: SelectionGateConfig
    data_quality_gate: SelectionGateConfig
    leakage_gate: SelectionGateConfig
    zero_variance_gate: SelectionGateConfig
    redundancy_gate: SelectionGateConfig
    stability_gate: SelectionGateConfig
    shapiro_wilk_gate: SelectionGateConfig


@dataclass(frozen=True)
class AnalysisScopeConfig:
    """Analysis scope configuration."""

    numeric_candidates_only: bool
    include_date_features: bool


@dataclass(frozen=True)
class OutputConfig:
    """Output path configuration."""

    processed_dir: str
    candidate_filename: str
    report_dir: str


@dataclass(frozen=True)
class MetadataConfig:
    """Metadata configuration."""

    stage: str
    task_description: str
    scope_boundaries: list[str]
    notes: list[str]


@dataclass(frozen=True)
class FeatureEngineeringConfig:
    """Top-level feature engineering configuration."""

    enabled: bool
    random_seed: int
    customer_key: str
    source: SourceConfig
    reference_date: ReferenceDateConfig
    rfm: RFMConfig
    quantity: QuantityConfig
    transaction_behavior: TransactionBehaviorConfig
    diversity: DiversityConfig
    cancellation: CancellationConfig
    unsupported: list[UnsupportedFeatureSpec]
    layer_classification: LayerClassification
    selection: SelectionConfig
    analysis_scope: AnalysisScopeConfig
    output: OutputConfig
    metadata: MetadataConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file as a nested dict."""
    if not path.exists():
        raise FeatureEngineeringConfigError(f"Feature engineering config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise FeatureEngineeringConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if data is None:
        raise FeatureEngineeringConfigError(f"Feature engineering config file {path} is empty.")
    if not isinstance(data, dict):
        raise FeatureEngineeringConfigError(
            f"Feature engineering config file {path} must be a YAML mapping; "
            f"got {type(data).__name__}."
        )
    return data


def _require_str(container: dict[str, Any], key: str, *, container_name: str) -> str:
    """Look up key, expecting a string."""
    value = container.get(key)
    if value is None:
        raise FeatureEngineeringConfigError(
            f"Missing required key {key!r} under {container_name!r}."
        )
    if not isinstance(value, str):
        raise FeatureEngineeringConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_bool(container: dict[str, Any], key: str, *, container_name: str) -> bool:
    """Look up key, expecting a bool."""
    value = container.get(key)
    if value is None:
        raise FeatureEngineeringConfigError(
            f"Missing required key {key!r} under {container_name!r}."
        )
    if not isinstance(value, bool):
        raise FeatureEngineeringConfigError(
            f"Expected {key!r} under {container_name!r} to be a boolean; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_number(container: dict[str, Any], key: str, *, container_name: str) -> float:
    """Look up key, expecting an int or float."""
    value = container.get(key)
    if value is None:
        raise FeatureEngineeringConfigError(
            f"Missing required key {key!r} under {container_name!r}."
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FeatureEngineeringConfigError(
            f"Expected {key!r} under {container_name!r} to be a number; "
            f"got {type(value).__name__}={value!r}."
        )
    return float(value)


def _optional_number(
    container: dict[str, Any],
    key: str,
    *,
    default: float,
) -> float:
    """Look up key, returning default if missing."""
    value = container.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FeatureEngineeringConfigError(
            f"Expected {key!r} to be a number; got {type(value).__name__}={value!r}."
        )
    return float(value)


def _optional_str(container: dict[str, Any], key: str, *, default: str) -> str:
    """Look up key, returning default if missing."""
    value = container.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise FeatureEngineeringConfigError(
            f"Expected {key!r} to be a string; got {type(value).__name__}={value!r}."
        )
    return value


def _optional_str_or_none(container: dict[str, Any], key: str) -> str | None:
    """Look up key, returning None if missing."""
    value = container.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise FeatureEngineeringConfigError(
            f"Expected {key!r} to be a string or null; got {type(value).__name__}={value!r}."
        )
    return value


def _require_list(container: dict[str, Any], key: str, *, container_name: str) -> list[Any]:
    """Look up key, expecting a list."""
    value = container.get(key)
    if value is None:
        raise FeatureEngineeringConfigError(
            f"Missing required key {key!r} under {container_name!r}."
        )
    if not isinstance(value, list):
        raise FeatureEngineeringConfigError(
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
        raise FeatureEngineeringConfigError(
            f"Expected {key!r} to be a list; got {type(value).__name__}={value!r}."
        )
    return value


# ---------------------------------------------------------------------------
# Config parsers
# ---------------------------------------------------------------------------


def _parse_source_config(data: dict[str, Any]) -> SourceConfig:
    """Parse source dataset configuration."""
    source = data.get("source", {})
    return SourceConfig(
        customer_base_path=_require_str(source, "customer_base_path", container_name="source"),
        transactions_clean_path=_require_str(
            source, "transactions_clean_path", container_name="source"
        ),
    )


def _parse_reference_date_config(data: dict[str, Any]) -> ReferenceDateConfig:
    """Parse reference date configuration."""
    ref_date = data.get("reference_date", {})
    return ReferenceDateConfig(
        mode=_require_str(ref_date, "mode", container_name="reference_date"),
        status=_require_str(ref_date, "status", container_name="reference_date"),
        review=_require_str(ref_date, "review", container_name="reference_date"),
    )


def _parse_rfm_config(data: dict[str, Any]) -> RFMConfig:
    """Parse RFM configuration."""
    rfm = data.get("rfm", {})

    recency = rfm.get("recency", {})
    frequency = rfm.get("frequency", {})
    monetary = rfm.get("monetary", {})

    return RFMConfig(
        recency_enabled=_require_bool(recency, "enabled", container_name="rfm.recency"),
        recency_column=_require_str(recency, "column", container_name="rfm.recency"),
        recency_aggregation=_require_str(recency, "aggregation", container_name="rfm.recency"),
        recency_status=_require_str(recency, "status", container_name="rfm.recency"),
        recency_note=_optional_str(recency, "note", default=""),
        frequency_enabled=_require_bool(frequency, "enabled", container_name="rfm.frequency"),
        frequency_mode=_require_str(frequency, "mode", container_name="rfm.frequency"),
        frequency_status=_require_str(frequency, "status", container_name="rfm.frequency"),
        frequency_note=_optional_str(frequency, "note", default=""),
        frequency_output_column=_require_str(
            frequency, "output_column", container_name="rfm.frequency"
        ),
        monetary_enabled=_require_bool(monetary, "enabled", container_name="rfm.monetary"),
        monetary_default_variant=_require_str(
            monetary, "default_variant", container_name="rfm.monetary"
        ),
        monetary_status=_require_str(monetary, "status", container_name="rfm.monetary"),
        monetary_note=_optional_str(monetary, "note", default=""),
        monetary_output_column=_require_str(
            monetary, "output_column", container_name="rfm.monetary"
        ),
    )


def _parse_quantity_feature_spec(data: dict[str, Any]) -> QuantityFeatureSpec:
    """Parse quantity feature specification."""
    return QuantityFeatureSpec(
        name=_require_str(data, "name", container_name="quantity.features"),
        source=_require_str(data, "source", container_name="quantity.features"),
        aggregation=_optional_str_or_none(data, "aggregation"),
        variant=_require_str(data, "variant", container_name="quantity.features"),
        status=_require_str(data, "status", container_name="quantity.features"),
        description=_require_str(data, "description", container_name="quantity.features"),
    )


def _parse_quantity_config(data: dict[str, Any]) -> QuantityConfig:
    """Parse quantity configuration."""
    quantity = data.get("quantity", {})
    features_data = _optional_list(quantity, "features", default=[])
    return QuantityConfig(
        enabled=_require_bool(quantity, "enabled", container_name="quantity"),
        default_variant=_require_str(quantity, "default_variant", container_name="quantity"),
        status=_require_str(quantity, "status", container_name="quantity"),
        note=_optional_str(quantity, "note", default=""),
        features=[_parse_quantity_feature_spec(f) for f in features_data],
    )


def _parse_transaction_behavior_feature_spec(
    data: dict[str, Any],
) -> TransactionBehaviorFeatureSpec:
    """Parse transaction behavior feature specification."""
    return TransactionBehaviorFeatureSpec(
        name=_require_str(data, "name", container_name="transaction_behavior.features"),
        source=_require_str(data, "source", container_name="transaction_behavior.features"),
        aggregation=_require_str(
            data, "aggregation", container_name="transaction_behavior.features"
        ),
        status=_require_str(data, "status", container_name="transaction_behavior.features"),
        description=_require_str(
            data, "description", container_name="transaction_behavior.features"
        ),
    )


def _parse_transaction_behavior_config(data: dict[str, Any]) -> TransactionBehaviorConfig:
    """Parse transaction behavior configuration."""
    tb = data.get("transaction_behavior", {})
    features_data = _optional_list(tb, "features", default=[])
    return TransactionBehaviorConfig(
        enabled=_require_bool(tb, "enabled", container_name="transaction_behavior"),
        features=[_parse_transaction_behavior_feature_spec(f) for f in features_data],
    )


def _parse_diversity_feature_spec(data: dict[str, Any]) -> DiversityFeatureSpec:
    """Parse diversity feature specification."""
    return DiversityFeatureSpec(
        name=_require_str(data, "name", container_name="diversity.features"),
        source=_require_str(data, "source", container_name="diversity.features"),
        aggregation=_require_str(data, "aggregation", container_name="diversity.features"),
        status=_require_str(data, "status", container_name="diversity.features"),
        description=_require_str(data, "description", container_name="diversity.features"),
    )


def _parse_diversity_config(data: dict[str, Any]) -> DiversityConfig:
    """Parse diversity configuration."""
    div = data.get("diversity", {})
    features_data = _optional_list(div, "features", default=[])
    return DiversityConfig(
        enabled=_require_bool(div, "enabled", container_name="diversity"),
        features=[_parse_diversity_feature_spec(f) for f in features_data],
    )


def _parse_unsupported_feature_spec(data: dict[str, Any]) -> UnsupportedFeatureSpec:
    """Parse unsupported feature specification."""
    return UnsupportedFeatureSpec(
        name=_require_str(data, "name", container_name="unsupported"),
        reason=_require_str(data, "reason", container_name="unsupported"),
    )


def _parse_cancellation_feature_spec(data: dict[str, Any]) -> CancellationFeatureSpec:
    """Parse cancellation feature specification."""
    return CancellationFeatureSpec(
        name=_require_str(data, "name", container_name="cancellation.features"),
        source=_require_str(data, "source", container_name="cancellation.features"),
        aggregation=_require_str(data, "aggregation", container_name="cancellation.features"),
        status=_require_str(data, "status", container_name="cancellation.features"),
        description=_require_str(data, "description", container_name="cancellation.features"),
    )


def _parse_cancellation_config(data: dict[str, Any]) -> CancellationConfig:
    """Parse cancellation configuration."""
    cancel = data.get("cancellation", {})
    features_data = _optional_list(cancel, "features", default=[])
    return CancellationConfig(
        enabled=_require_bool(cancel, "enabled", container_name="cancellation"),
        features=[_parse_cancellation_feature_spec(f) for f in features_data],
    )


def _parse_layer_classification(data: dict[str, Any]) -> LayerClassification:
    """Parse layer classification."""
    lc = data.get("layer_classification", {})
    return LayerClassification(
        IDENTIFIER_ONLY=_optional_list(lc, "IDENTIFIER_ONLY", default=[]),
        SOURCE_ONLY=_optional_list(lc, "SOURCE_ONLY", default=[]),
        BASE_REFERENCE=_optional_list(lc, "BASE_REFERENCE", default=[]),
        CANDIDATE=_optional_list(lc, "CANDIDATE", default=[]),
        UNSUPPORTED=_optional_list(lc, "UNSUPPORTED", default=[]),
    )


def _parse_gate_config(data: dict[str, Any], name: str) -> SelectionGateConfig:
    """Parse selection gate configuration."""
    gate_data = data.get(name, {})
    return SelectionGateConfig(
        enabled=_require_bool(gate_data, "enabled", container_name=f"selection.{name}"),
        status=_require_str(gate_data, "status", container_name=f"selection.{name}"),
        threshold=(
            _optional_number(gate_data, "threshold", default=0.95)
            if "threshold" in gate_data
            else None
        ),
        max_missing_ratio=(
            _optional_number(gate_data, "max_missing_ratio", default=0.5)
            if "max_missing_ratio" in gate_data
            else None
        ),
        n_bootstrap=_int_or_none(gate_data.get("n_bootstrap")),
        alpha=_optional_number(gate_data, "alpha", default=0.05) if "alpha" in gate_data else None,
        note=_optional_str_or_none(gate_data, "note"),
    )


def _int_or_none(value: Any) -> int | None:
    """Convert to int or return None."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise FeatureEngineeringConfigError(f"Expected integer; got {type(value).__name__}={value!r}.")


def _parse_selection_config(data: dict[str, Any]) -> SelectionConfig:
    """Parse selection configuration."""
    selection = data.get("selection", {})
    return SelectionConfig(
        interpretability_gate=_parse_gate_config(selection, "interpretability_gate"),
        data_quality_gate=_parse_gate_config(selection, "data_quality_gate"),
        leakage_gate=_parse_gate_config(selection, "leakage_gate"),
        zero_variance_gate=_parse_gate_config(selection, "zero_variance_gate"),
        redundancy_gate=_parse_gate_config(selection, "redundancy_gate"),
        stability_gate=_parse_gate_config(selection, "stability_gate"),
        shapiro_wilk_gate=_parse_gate_config(selection, "shapiro_wilk_gate"),
    )


def _parse_analysis_scope_config(data: dict[str, Any]) -> AnalysisScopeConfig:
    """Parse analysis scope configuration."""
    scope = data.get("analysis_scope", {})
    return AnalysisScopeConfig(
        numeric_candidates_only=_require_bool(
            scope, "numeric_candidates_only", container_name="analysis_scope"
        ),
        include_date_features=_require_bool(
            scope, "include_date_features", container_name="analysis_scope"
        ),
    )


def _parse_output_config(data: dict[str, Any]) -> OutputConfig:
    """Parse output configuration."""
    output = data.get("output", {})
    return OutputConfig(
        processed_dir=_require_str(output, "processed_dir", container_name="output"),
        candidate_filename=_require_str(output, "candidate_filename", container_name="output"),
        report_dir=_require_str(output, "report_dir", container_name="output"),
    )


def _parse_metadata_config(data: dict[str, Any]) -> MetadataConfig:
    """Parse metadata configuration."""
    meta = data.get("metadata", {})
    return MetadataConfig(
        stage=_require_str(meta, "stage", container_name="metadata"),
        task_description=_require_str(meta, "task_description", container_name="metadata"),
        scope_boundaries=_optional_list(meta, "scope_boundaries", default=[]),
        notes=_optional_list(meta, "notes", default=[]),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_default_feature_engineering_config_path() -> Path:
    """Return the canonical path to configs/feature_engineering.yaml."""
    return DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH


def resolve_feature_engineering_config_path(
    explicit: Path | None = None,
) -> Path | None:
    """Pick the feature engineering config path.

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
    if DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH.exists():
        return DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH
    return None


def load_feature_engineering_config(
    path: Path | None = None,
    *,
    strict: bool = True,
) -> FeatureEngineeringConfig:
    """Load configs/feature_engineering.yaml and return a FeatureEngineeringConfig.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit path to the YAML file. If None, defaults to
        DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH.
    strict : bool, default True
        If True, every required key must be present.

    Returns
    -------
    FeatureEngineeringConfig
        Fully-typed dataclass instance.

    Raises
    ------
    FeatureEngineeringConfigError
        If the YAML cannot be read, parsed, or is missing required keys.
    """
    if path is None:
        path = DEFAULT_FEATURE_ENGINEERING_CONFIG_PATH

    raw = _read_yaml(path)
    if "features" not in raw or not isinstance(raw["features"], dict):
        raise FeatureEngineeringConfigError(
            f"Config file {path} must have a top-level 'features' mapping."
        )
    data: dict[str, Any] = raw["features"]

    # Parse unsupported features
    unsupported_data = _optional_list(data, "unsupported", default=[])

    return FeatureEngineeringConfig(
        enabled=_require_bool(data, "enabled", container_name="features"),
        random_seed=int(_require_number(data, "random_seed", container_name="features")),
        customer_key=_require_str(data, "customer_key", container_name="features"),
        source=_parse_source_config(data),
        reference_date=_parse_reference_date_config(data),
        rfm=_parse_rfm_config(data),
        quantity=_parse_quantity_config(data),
        transaction_behavior=_parse_transaction_behavior_config(data),
        diversity=_parse_diversity_config(data),
        cancellation=_parse_cancellation_config(data),
        unsupported=[_parse_unsupported_feature_spec(f) for f in unsupported_data],
        layer_classification=_parse_layer_classification(data),
        selection=_parse_selection_config(data),
        analysis_scope=_parse_analysis_scope_config(data),
        output=_parse_output_config(data),
        metadata=_parse_metadata_config(data),
    )
