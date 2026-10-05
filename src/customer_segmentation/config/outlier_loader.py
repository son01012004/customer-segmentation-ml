"""Configuration loader for the FE-03 outlier analysis pipeline.

This module mirrors :mod:`customer_segmentation.config.loader` but for
``configs/outlier.yaml``. The YAML is the **single source of truth** for
the FE-03 outlier analysis:

- Detection methods / thresholds (per transaction-level feature).
- Customer-level diagnostic aggregations (clearly marked diagnostic-only;
  **not** a substitute for FE-04 RFM / extended-behavioural features).
- Filter modes (so cancellation / return rows can be excluded from the
  customer-behavior analysis without being deleted from the dataset).
- Sensitivity-analysis thresholds.
- Output paths and the strict opt-in toggle for writing a treated
  dataset.

Failure modes
-------------
:func:`load_outlier_config` raises a typed
:class:`OutlierConfigError` when the YAML is malformed or when a
required key is missing. It never silently falls back to defaults in
strict mode.

Status markers
--------------
Each transaction-level feature and the customer-level diagnostic
carry a ``status`` marker (``WORKING_ASSUMPTION`` /
``PENDING_MENTOR_REVIEW``). ``PENDING_MENTOR_REVIEW`` means the
detection parameters are wired up but no treatment is applied until a
mentor approves the methodology.

Hard constraints (from AGENTS.md):
- Detection / treatment thresholds must come from a YAML file. Hard-
  coding thresholds in code is forbidden.
- FE-02 cleaning rules and ``configs/preprocessing.yaml`` are **not**
  modified by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

__all__ = [
    "DEFAULT_OUTLIER_CONFIG_PATH",
    "OUTLIER_STATUS_WORKING_ASSUMPTION",
    "OUTLIER_STATUS_PENDING_MENTOR_REVIEW",
    "OUTLIER_VALID_STATUSES",
    "OUTLIER_VALID_DETECTIONS",
    "OUTLIER_VALID_TREATMENTS",
    "OUTLIER_VALID_AGGREGATIONS",
    "ConfigAnnotation",
    "CustomerAggregationConfig",
    "CustomerDiagnosticConfig",
    "FeatureOutlierConfig",
    "FilterModeConfig",
    "OutlierAnalysisConfig",
    "OutlierConfigError",
    "SensitivityConfig",
    "SourceConfig",
    "OutputConfig",
    "KEY_ANNOTATIONS_OUTLIER",
    "find_default_outlier_config_path",
    "load_outlier_config",
    "outlier_config_to_dict",
    "resolve_outlier_config_path",
]


# ---------------------------------------------------------------------------
# Defaults & paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]
DEFAULT_OUTLIER_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "outlier.yaml"


# Status markers (mirror the FE-02 loader).
OUTLIER_STATUS_WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
OUTLIER_STATUS_PENDING_MENTOR_REVIEW = "PENDING_MENTOR_REVIEW"
OUTLIER_VALID_STATUSES: frozenset[str] = frozenset(
    {OUTLIER_STATUS_WORKING_ASSUMPTION, OUTLIER_STATUS_PENDING_MENTOR_REVIEW}
)


# Detection / treatment valid value sets.
OUTLIER_VALID_DETECTIONS: frozenset[str] = frozenset({"iqr", "zscore", "percentile"})
OUTLIER_VALID_TREATMENTS: frozenset[str] = frozenset(
    {"none", "keep", "flag", "clip", "remove", "log_transform"}
)
OUTLIER_VALID_AGGREGATIONS: frozenset[str] = frozenset(
    {"sum", "mean", "min", "max", "nunique", "nunique_date", "count"}
)
OUTLIER_VALID_FILTER_MODES: frozenset[str] = frozenset(
    {"all_rows", "clean_purchase", "non_cancellation", "non_return"}
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OutlierConfigError(ValueError):
    """Raised when ``configs/outlier.yaml`` is malformed or missing keys."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigAnnotation:
    """Per-key annotation: status, source, rule_id, rationale.

    Mirrors the FE-02 ``ConfigAnnotation``. Used to map YAML keys back to
    a status without re-reading the YAML.
    """

    status: str
    source: str
    rule_id: str | None
    rationale: str

    def __post_init__(self) -> None:
        if self.status not in OUTLIER_VALID_STATUSES:
            raise ValueError(
                f"Unknown status {self.status!r}; valid: {sorted(OUTLIER_VALID_STATUSES)}."
            )


@dataclass(frozen=True)
class SourceConfig:
    """Input dataset reference."""

    role: str
    cleaned_dataset_path: str
    raw_dataset_path: str


@dataclass(frozen=True)
class FeatureOutlierConfig:
    """Per-feature outlier configuration (transaction level)."""

    column: str
    detection: str
    iqr_multiplier: float = 1.5
    percentile_thresholds: tuple[float, ...] = (99.0, 99.5, 99.9)
    zscore_threshold: float = 3.0
    treatment: str = "none"
    status: str = OUTLIER_STATUS_PENDING_MENTOR_REVIEW


@dataclass(frozen=True)
class CustomerAggregationConfig:
    """One named customer-level aggregation."""

    source: str
    fn: str


@dataclass
class CustomerDiagnosticConfig:
    """Configuration for the customer-level diagnostic block.

    Attributes
    ----------
    enabled : bool
        Whether to compute the customer-level diagnostic.
    customer_key : str
        Identifier column. Defaults to ``"CustomerID"``.
    aggregations : dict[str, CustomerAggregationConfig]
        Mapping of output column → (source column, aggregation fn).
    detection_iqr_multiplier : float
        IQR multiplier used by the diagnostic outlier scan.
    detection_percentile_thresholds : tuple[float, ...]
        Percentile thresholds used by the diagnostic outlier scan.
    treatment : str
        Treatment for diagnostic outliers. Defaults to ``"none"``.
    status : str
        Status marker; default PENDING_MENTOR_REVIEW.
    """

    enabled: bool = False
    customer_key: str = "CustomerID"
    aggregations: dict[str, CustomerAggregationConfig] = field(default_factory=dict)
    detection_iqr_multiplier: float = 1.5
    detection_percentile_thresholds: tuple[float, ...] = (95.0, 99.0, 99.5)
    treatment: str = "none"
    status: str = OUTLIER_STATUS_PENDING_MENTOR_REVIEW


@dataclass(frozen=True)
class FilterModeConfig:
    """A named filter mode used to subset the cleaned dataset for analysis.

    Attributes
    ----------
    name : str
        One of ``all_rows``, ``clean_purchase``, ``non_cancellation``,
        ``non_return``.
    where : str
        Human-readable description of the predicate; not parsed.
    """

    name: str
    where: str


@dataclass(frozen=True)
class SensitivityConfig:
    """Configuration for the sensitivity analysis."""

    enabled: bool = True
    thresholds: tuple[float, ...] = (1.5, 3.0)
    percentiles: tuple[float, ...] = (99.0, 99.5, 99.9)


@dataclass(frozen=True)
class OutputConfig:
    """Output paths and opt-in toggles."""

    processed_dir: str = "./data/processed"
    report_dir: str = "./reports/fe03"
    treated_filename: str = "transactions_outlier_treated.parquet"
    write_treated_dataset: bool = False
    plots_dir: str = "./reports/fe03/plots"
    write_plots: bool = True


@dataclass
class OutlierAnalysisConfig:
    """Typed configuration for the FE-03 outlier analysis pipeline.

    Attributes
    ----------
    enabled : bool
        Whether the FE-03 stage is enabled. Defaults to ``True``.
    random_seed : int
        Seed reserved for downstream stochastic helpers (none used in
        FE-03 currently; informational).
    source : SourceConfig
        Input dataset references.
    transaction_features : list[FeatureOutlierConfig]
        Per-feature (transaction-level) outlier configuration.
    customer_diagnostic : CustomerDiagnosticConfig
        Customer-level diagnostic configuration.
    filter_modes : list[FilterModeConfig]
        Filter modes applied to the cleaned dataset.
    sensitivity : SensitivityConfig
        Sensitivity analysis configuration.
    output : OutputConfig
        Output paths and toggles.
    """

    enabled: bool = True
    random_seed: int = 42
    source: SourceConfig = field(
        default_factory=lambda: SourceConfig(
            role="primary",
            cleaned_dataset_path="./data/processed/transactions_clean.parquet",
            raw_dataset_path="./data/raw/primary/Online Retail.xlsx",
        )
    )
    transaction_features: list[FeatureOutlierConfig] = field(default_factory=list)
    customer_diagnostic: CustomerDiagnosticConfig = field(default_factory=CustomerDiagnosticConfig)
    filter_modes: list[FilterModeConfig] = field(default_factory=list)
    sensitivity: SensitivityConfig = field(default_factory=SensitivityConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


# ---------------------------------------------------------------------------
# YAML I/O helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read YAML; raise typed errors for IO / parse failures."""
    if not path.exists():
        raise OutlierConfigError(f"Outlier config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # type: ignore[misc]
        raise OutlierConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if data is None:
        raise OutlierConfigError(f"Outlier config file {path} is empty.")
    if not isinstance(data, dict):
        raise OutlierConfigError(
            f"Outlier config file {path} must be a YAML mapping; got " f"{type(data).__name__}."
        )
    return data


def _require(container: dict[str, Any], key: str, *, container_name: str) -> Any:
    if key not in container:
        raise OutlierConfigError(
            f"Missing required key {key!r} under {container_name!r} in outlier config."
        )
    return container[key]


def _require_str(container: dict[str, Any], key: str, *, container_name: str) -> str:
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, str):
        raise OutlierConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_bool(container: dict[str, Any], key: str, *, container_name: str) -> bool:
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, bool):
        raise OutlierConfigError(
            f"Expected {key!r} under {container_name!r} to be a boolean; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_number(container: dict[str, Any], key: str, *, container_name: str) -> float:
    value = _require(container, key, container_name=container_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OutlierConfigError(
            f"Expected {key!r} under {container_name!r} to be a number; "
            f"got {type(value).__name__}={value!r}."
        )
    return float(value)


def _optional_number(
    container: dict[str, Any],
    key: str,
    *,
    container_name: str,
    default: float,
) -> float:
    if key not in container:
        return default
    return _require_number(container, key, container_name=container_name)


def _optional_str(
    container: dict[str, Any],
    key: str,
    *,
    container_name: str,
    default: str,
) -> str:
    if key not in container:
        return default
    value = container[key]
    if not isinstance(value, str):
        raise OutlierConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_list_of_numbers(
    container: dict[str, Any],
    key: str,
    *,
    container_name: str,
) -> list[float]:
    if key not in container:
        return []
    value = container[key]
    if not isinstance(value, list):
        raise OutlierConfigError(
            f"Expected {key!r} under {container_name!r} to be a list; "
            f"got {type(value).__name__}={value!r}."
        )
    out: list[float] = []
    for i, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise OutlierConfigError(
                f"Expected {key!r}[{i}] under {container_name!r} to be a number; "
                f"got {type(item).__name__}={item!r}."
            )
        out.append(float(item))
    return out


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def find_default_outlier_config_path() -> Path:
    """Return the canonical path to ``configs/outlier.yaml``."""
    return DEFAULT_OUTLIER_CONFIG_PATH


def resolve_outlier_config_path(
    explicit: Path | None = None,
    *,
    search_paths: tuple[Path, ...] = (DEFAULT_OUTLIER_CONFIG_PATH,),
) -> Path | None:
    """Pick the first existing outlier config path.

    Parameters
    ----------
    explicit : pathlib.Path, optional
        If provided, always returned (caller handles missing files).
    search_paths : tuple[pathlib.Path, ...]
        Ordered fallback paths. First existing path returned; ``None``
        if none exist.
    """
    if explicit is not None:
        return explicit
    for p in search_paths:
        if p.exists():
            return p
    return None


def _parse_source(raw: dict[str, Any] | None) -> SourceConfig:
    if raw is None:
        return SourceConfig(
            role="primary",
            cleaned_dataset_path="./data/processed/transactions_clean.parquet",
            raw_dataset_path="./data/raw/primary/Online Retail.xlsx",
        )
    if not isinstance(raw, dict):
        raise OutlierConfigError(f"Expected 'source' to be a mapping; got {type(raw).__name__}.")
    role = _optional_str(raw, "role", container_name="source", default="primary")
    cleaned = _optional_str(
        raw,
        "cleaned_dataset_path",
        container_name="source",
        default="./data/processed/transactions_clean.parquet",
    )
    raw_path = _optional_str(
        raw,
        "raw_dataset_path",
        container_name="source",
        default="./data/raw/primary/Online Retail.xlsx",
    )
    return SourceConfig(role=role, cleaned_dataset_path=cleaned, raw_dataset_path=raw_path)


def _parse_feature(raw: dict[str, Any], *, container_name: str) -> FeatureOutlierConfig:
    if not isinstance(raw, dict):
        raise OutlierConfigError(
            f"Expected a feature mapping under {container_name!r}; got {type(raw).__name__}."
        )
    column = _require_str(raw, "column", container_name=container_name)
    detection = _require_str(raw, "detection", container_name=container_name)
    if detection not in OUTLIER_VALID_DETECTIONS:
        raise OutlierConfigError(
            f"Feature {column!r}: unknown detection {detection!r}; "
            f"valid: {sorted(OUTLIER_VALID_DETECTIONS)}."
        )
    iqr_multiplier = _optional_number(
        raw, "iqr_multiplier", container_name=container_name, default=1.5
    )
    if iqr_multiplier <= 0:
        raise OutlierConfigError(
            f"Feature {column!r}: iqr_multiplier must be > 0; got {iqr_multiplier}."
        )
    zscore_threshold = _optional_number(
        raw, "zscore_threshold", container_name=container_name, default=3.0
    )
    if zscore_threshold <= 0:
        raise OutlierConfigError(
            f"Feature {column!r}: zscore_threshold must be > 0; got {zscore_threshold}."
        )
    percentile_thresholds = tuple(
        _require_list_of_numbers(
            raw,
            "percentile_thresholds",
            container_name=container_name,
        )
    )
    treatment = _optional_str(raw, "treatment", container_name=container_name, default="none")
    if treatment not in OUTLIER_VALID_TREATMENTS:
        raise OutlierConfigError(
            f"Feature {column!r}: unknown treatment {treatment!r}; "
            f"valid: {sorted(OUTLIER_VALID_TREATMENTS)}."
        )
    status = _optional_str(
        raw,
        "status",
        container_name=container_name,
        default=OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
    )
    if status not in OUTLIER_VALID_STATUSES:
        raise OutlierConfigError(
            f"Feature {column!r}: unknown status {status!r}; "
            f"valid: {sorted(OUTLIER_VALID_STATUSES)}."
        )
    return FeatureOutlierConfig(
        column=column,
        detection=detection,
        iqr_multiplier=iqr_multiplier,
        percentile_thresholds=percentile_thresholds,
        zscore_threshold=zscore_threshold,
        treatment=treatment,
        status=status,
    )


def _parse_customer_diagnostic(raw: dict[str, Any] | None) -> CustomerDiagnosticConfig:
    if raw is None:
        return CustomerDiagnosticConfig()
    if not isinstance(raw, dict):
        raise OutlierConfigError(
            f"Expected 'customer_diagnostic' to be a mapping; got {type(raw).__name__}."
        )
    enabled = _require_bool(raw, "enabled", container_name="customer_diagnostic")
    customer_key = _optional_str(
        raw, "customer_key", container_name="customer_diagnostic", default="CustomerID"
    )
    aggregations_raw = raw.get("aggregations", {})
    if not isinstance(aggregations_raw, dict):
        raise OutlierConfigError(
            "Expected 'customer_diagnostic.aggregations' to be a mapping; got "
            f"{type(aggregations_raw).__name__}."
        )
    aggregations: dict[str, CustomerAggregationConfig] = {}
    for name, spec in aggregations_raw.items():
        if not isinstance(spec, dict):
            raise OutlierConfigError(
                f"customer_diagnostic.aggregations[{name!r}] must be a mapping; "
                f"got {type(spec).__name__}."
            )
        source = _require_str(
            spec, "source", container_name=f"customer_diagnostic.aggregations.{name}"
        )
        fn = _require_str(spec, "fn", container_name=f"customer_diagnostic.aggregations.{name}")
        if fn not in OUTLIER_VALID_AGGREGATIONS:
            raise OutlierConfigError(
                f"customer_diagnostic.aggregations[{name!r}].fn={fn!r} is not "
                f"recognised; valid: {sorted(OUTLIER_VALID_AGGREGATIONS)}."
            )
        aggregations[name] = CustomerAggregationConfig(source=source, fn=fn)
    detection_raw = raw.get("detection", {})
    if not isinstance(detection_raw, dict):
        raise OutlierConfigError(
            "Expected 'customer_diagnostic.detection' to be a mapping; got "
            f"{type(detection_raw).__name__}."
        )
    iqr_mult = _optional_number(
        detection_raw,
        "iqr_multiplier",
        container_name="customer_diagnostic.detection",
        default=1.5,
    )
    pcts = tuple(
        _require_list_of_numbers(
            detection_raw,
            "percentile_thresholds",
            container_name="customer_diagnostic.detection",
        )
    )
    treatment = _optional_str(
        raw,
        "treatment",
        container_name="customer_diagnostic",
        default="none",
    )
    if treatment not in OUTLIER_VALID_TREATMENTS:
        raise OutlierConfigError(
            f"customer_diagnostic.treatment={treatment!r} is not recognised; "
            f"valid: {sorted(OUTLIER_VALID_TREATMENTS)}."
        )
    status = _optional_str(
        raw,
        "status",
        container_name="customer_diagnostic",
        default=OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
    )
    if status not in OUTLIER_VALID_STATUSES:
        raise OutlierConfigError(
            f"customer_diagnostic.status={status!r} is not recognised; "
            f"valid: {sorted(OUTLIER_VALID_STATUSES)}."
        )
    return CustomerDiagnosticConfig(
        enabled=enabled,
        customer_key=customer_key,
        aggregations=aggregations,
        detection_iqr_multiplier=iqr_mult,
        detection_percentile_thresholds=pcts,
        treatment=treatment,
        status=status,
    )


def _parse_filter_modes(raw: Any) -> list[FilterModeConfig]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise OutlierConfigError(f"Expected 'filter_modes' to be a list; got {type(raw).__name__}.")
    modes: list[FilterModeConfig] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise OutlierConfigError(
                f"filter_modes[{i}] must be a mapping; got {type(item).__name__}."
            )
        name = _require_str(item, "name", container_name=f"filter_modes[{i}]")
        if name not in OUTLIER_VALID_FILTER_MODES:
            raise OutlierConfigError(
                f"filter_modes[{i}].name={name!r} is not recognised; "
                f"valid: {sorted(OUTLIER_VALID_FILTER_MODES)}."
            )
        where = _optional_str(item, "where", container_name=f"filter_modes[{i}]", default="")
        modes.append(FilterModeConfig(name=name, where=where))
    return modes


def _parse_sensitivity(raw: dict[str, Any] | None) -> SensitivityConfig:
    if raw is None:
        return SensitivityConfig()
    if not isinstance(raw, dict):
        raise OutlierConfigError(
            f"Expected 'sensitivity' to be a mapping; got {type(raw).__name__}."
        )
    enabled = _require_bool(raw, "enabled", container_name="sensitivity")
    thresholds = tuple(_require_list_of_numbers(raw, "thresholds", container_name="sensitivity"))
    percentiles = tuple(_require_list_of_numbers(raw, "percentiles", container_name="sensitivity"))
    return SensitivityConfig(
        enabled=enabled,
        thresholds=thresholds,
        percentiles=percentiles,
    )


def _parse_output(raw: dict[str, Any] | None) -> OutputConfig:
    if raw is None:
        return OutputConfig()
    if not isinstance(raw, dict):
        raise OutlierConfigError(f"Expected 'output' to be a mapping; got {type(raw).__name__}.")
    return OutputConfig(
        processed_dir=_optional_str(
            raw, "processed_dir", container_name="output", default="./data/processed"
        ),
        report_dir=_optional_str(
            raw, "report_dir", container_name="output", default="./reports/fe03"
        ),
        treated_filename=_optional_str(
            raw,
            "treated_filename",
            container_name="output",
            default="transactions_outlier_treated.parquet",
        ),
        write_treated_dataset=_require_bool(raw, "write_treated_dataset", container_name="output"),
        plots_dir=_optional_str(
            raw, "plots_dir", container_name="output", default="./reports/fe03/plots"
        ),
        write_plots=_require_bool(raw, "write_plots", container_name="output"),
    )


# ---------------------------------------------------------------------------
# Public API: load_outlier_config
# ---------------------------------------------------------------------------


def load_outlier_config(
    path: Path | None = None,
    *,
    strict: bool = True,
) -> OutlierAnalysisConfig:
    """Load ``configs/outlier.yaml`` and return a typed config.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit YAML path. ``None`` uses
        :data:`DEFAULT_OUTLIER_CONFIG_PATH`.
    strict : bool, default True
        If ``True``, missing keys raise :class:`OutlierConfigError`. If
        ``False``, dataclass defaults fill in any gaps (intended only
        for partial YAML overrides).

    Returns
    -------
    OutlierAnalysisConfig
        Typed config ready to pass to the FE-03 orchestrator.

    Raises
    ------
    OutlierConfigError
        If the YAML cannot be read, parsed, or is missing required
        keys under ``strict=True``.
    """
    if path is None:
        path = DEFAULT_OUTLIER_CONFIG_PATH

    raw = _read_yaml(path)
    if "outlier_analysis" not in raw or not isinstance(raw["outlier_analysis"], dict):
        raise OutlierConfigError(
            f"Outlier config file {path} must have a top-level 'outlier_analysis' mapping."
        )
    pp: dict[str, Any] = raw["outlier_analysis"]

    if strict:
        for required in (
            "enabled",
            "random_seed",
            "source",
            "transaction_features",
            "customer_diagnostic",
            "filter_modes",
            "sensitivity",
            "output",
        ):
            if required not in pp:
                raise OutlierConfigError(
                    f"Missing required key 'outlier_analysis.{required}' in {path}."
                )

    enabled = pp.get("enabled", True)
    if not isinstance(enabled, bool):
        raise OutlierConfigError(
            f"'outlier_analysis.enabled' must be a bool; got {type(enabled).__name__}."
        )
    random_seed = pp.get("random_seed", 42)
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise OutlierConfigError(
            f"'outlier_analysis.random_seed' must be an int; got " f"{type(random_seed).__name__}."
        )

    source = _parse_source(pp.get("source"))
    customer_diag = _parse_customer_diagnostic(pp.get("customer_diagnostic"))

    tf_raw = pp.get("transaction_features", [])
    if not isinstance(tf_raw, list):
        raise OutlierConfigError(
            f"'outlier_analysis.transaction_features' must be a list; "
            f"got {type(tf_raw).__name__}."
        )
    transaction_features = [
        _parse_feature(item, container_name=f"transaction_features[{i}]")
        for i, item in enumerate(tf_raw)
    ]

    filter_modes = _parse_filter_modes(pp.get("filter_modes"))
    sensitivity = _parse_sensitivity(pp.get("sensitivity"))
    output = _parse_output(pp.get("output"))

    return OutlierAnalysisConfig(
        enabled=enabled,
        random_seed=random_seed,
        source=source,
        transaction_features=transaction_features,
        customer_diagnostic=customer_diag,
        filter_modes=filter_modes,
        sensitivity=sensitivity,
        output=output,
    )


# ---------------------------------------------------------------------------
# Annotations (FE-03 rule / key → status mapping)
# ---------------------------------------------------------------------------


KEY_ANNOTATIONS_OUTLIER: dict[str, ConfigAnnotation] = {
    "transaction_features[*].treatment": ConfigAnnotation(
        status=OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
        source="transaction_features[*].treatment",
        rule_id=None,
        rationale=(
            "Treatment defaults to 'none'. Any non-KEEP treatment requires "
            "mentor approval AND an explicit opt-in via the orchestrator."
        ),
    ),
    "customer_diagnostic.treatment": ConfigAnnotation(
        status=OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
        source="customer_diagnostic.treatment",
        rule_id=None,
        rationale=(
            "Customer-level diagnostic outputs are exploratory; treatment "
            "must be deferred to FE-04."
        ),
    ),
    "output.write_treated_dataset": ConfigAnnotation(
        status=OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
        source="output.write_treated_dataset",
        rule_id=None,
        rationale=(
            "Opt-in toggle. When False, no treated dataset is written " "regardless of CLI flags."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Serialisation (used by fe03_run.json)
# ---------------------------------------------------------------------------


def outlier_config_to_dict(config: OutlierAnalysisConfig) -> dict[str, Any]:
    """Serialise a :class:`OutlierAnalysisConfig` to a JSON-friendly dict.

    Mirrors the YAML shape so the JSON can be diffed against the YAML.

    Parameters
    ----------
    config : OutlierAnalysisConfig
        Config to serialise.

    Returns
    -------
    dict
        JSON-serialisable dict matching the YAML schema.
    """
    return {
        "enabled": config.enabled,
        "random_seed": config.random_seed,
        "source": {
            "role": config.source.role,
            "cleaned_dataset_path": config.source.cleaned_dataset_path,
            "raw_dataset_path": config.source.raw_dataset_path,
        },
        "transaction_features": [
            {
                "column": f.column,
                "detection": f.detection,
                "iqr_multiplier": f.iqr_multiplier,
                "percentile_thresholds": list(f.percentile_thresholds),
                "zscore_threshold": f.zscore_threshold,
                "treatment": f.treatment,
                "status": f.status,
            }
            for f in config.transaction_features
        ],
        "customer_diagnostic": {
            "enabled": config.customer_diagnostic.enabled,
            "customer_key": config.customer_diagnostic.customer_key,
            "aggregations": {
                name: {"source": spec.source, "fn": spec.fn}
                for name, spec in config.customer_diagnostic.aggregations.items()
            },
            "detection": {
                "iqr_multiplier": config.customer_diagnostic.detection_iqr_multiplier,
                "percentile_thresholds": list(
                    config.customer_diagnostic.detection_percentile_thresholds
                ),
            },
            "treatment": config.customer_diagnostic.treatment,
            "status": config.customer_diagnostic.status,
        },
        "filter_modes": [{"name": m.name, "where": m.where} for m in config.filter_modes],
        "sensitivity": {
            "enabled": config.sensitivity.enabled,
            "thresholds": list(config.sensitivity.thresholds),
            "percentiles": list(config.sensitivity.percentiles),
        },
        "output": {
            "processed_dir": config.output.processed_dir,
            "report_dir": config.output.report_dir,
            "treated_filename": config.output.treated_filename,
            "write_treated_dataset": config.output.write_treated_dataset,
            "plots_dir": config.output.plots_dir,
            "write_plots": config.output.write_plots,
        },
    }
