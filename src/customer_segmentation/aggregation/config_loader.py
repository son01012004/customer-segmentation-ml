"""Configuration loader for the FE-04 aggregation pipeline.

Single source of truth: ``configs/aggregation.yaml``.

Dataclass pattern follows ``customer_segmentation.config.outlier_loader``
(FE-03). Keeping the loader separate from the dataclass means the
aggregation module can be imported without a YAML parser in tests.

Failure modes
-------------
:func:`load_aggregation_config` raises :class:`AggregationConfigError`
when the YAML is malformed or a required key is missing. It never
silently falls back to defaults in strict mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

__all__ = [
    "DEFAULT_AGGREGATION_CONFIG_PATH",
    "AGGREGATION_STATUS_WORKING_ASSUMPTION",
    "AGGREGATION_STATUS_PENDING_MENTOR_REVIEW",
    "AggregationConfigError",
    "AggregationSpec",
    "AggregationConfig",
    "LineRevenueColumns",
    "SourceConfig",
    "OutputConfig",
    "MetadataConfig",
    "load_aggregation_config",
    "find_default_aggregation_config_path",
    "resolve_aggregation_config_path",
    "aggregation_config_to_dict",
]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]
DEFAULT_AGGREGATION_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "aggregation.yaml"


# Status markers.
AGGREGATION_STATUS_WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
AGGREGATION_STATUS_PENDING_MENTOR_REVIEW = "PENDING_MENTOR_REVIEW"

# Supported aggregation functions.
VALID_FNS: frozenset[str] = frozenset(
    {
        "sum",
        "nunique",
        "min",
        "max",
        "count",
        "nunique_date",
        "avg_by_invoice",
        "conditional_nunique_cancellation",
        "conditional_nunique_return",
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AggregationConfigError(ValueError):
    """Raised when ``configs/aggregation.yaml`` is malformed or missing keys."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceConfig:
    """Input dataset reference."""

    role: str
    cleaned_dataset_path: str
    raw_dataset_path: str


@dataclass(frozen=True)
class LineRevenueColumns:
    """Column names for LineRevenue derivation."""

    quantity: str
    unit_price: str
    output: str


@dataclass(frozen=True)
class AggregationSpec:
    """One named aggregation output column."""

    name: str
    source: str
    fn: str
    status: str
    description: str

    def __post_init__(self) -> None:
        if self.status not in {
            AGGREGATION_STATUS_WORKING_ASSUMPTION,
            AGGREGATION_STATUS_PENDING_MENTOR_REVIEW,
        }:
            raise AggregationConfigError(
                f"AggregationSpec {self.name!r}: unknown status {self.status!r}; "
                f"valid: [{AGGREGATION_STATUS_WORKING_ASSUMPTION!r}, "
                f"{AGGREGATION_STATUS_PENDING_MENTOR_REVIEW!r}]."
            )
        if self.fn not in VALID_FNS:
            raise AggregationConfigError(
                f"AggregationSpec {self.name!r}: unknown fn {self.fn!r}; "
                f"valid: {sorted(VALID_FNS)}."
            )


@dataclass(frozen=True)
class OutputConfig:
    """Output paths."""

    processed_dir: str
    customer_base_filename: str
    report_dir: str


@dataclass
class MetadataConfig:
    """Informational metadata."""

    stage: str
    task_description: str
    scope_boundaries: list[str]
    notes: list[str]


@dataclass
class AggregationConfig:
    """Typed configuration for the FE-04 aggregation pipeline.

    Attributes
    ----------
    enabled : bool
        Whether the FE-04 stage is enabled.
    random_seed : int
        Seed reserved for downstream helpers (FE-04 is deterministic; informational).
    source : SourceConfig
        Input dataset references.
    aggregations : list[AggregationSpec]
        List of named aggregation specifications.
    customer_key : str
        Customer identifier column.
    line_revenue_columns : LineRevenueColumns
        Column names for LineRevenue derivation.
    output : OutputConfig
        Output paths.
    metadata : MetadataConfig
        Informational metadata.
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
    aggregations: list[AggregationSpec] = field(default_factory=list)
    customer_key: str = "CustomerID"
    line_revenue_columns: LineRevenueColumns = field(
        default_factory=lambda: LineRevenueColumns(
            quantity="Quantity",
            unit_price="UnitPrice",
            output="LineRevenue",
        )
    )
    output: OutputConfig = field(
        default_factory=lambda: OutputConfig(
            processed_dir="./data/processed",
            customer_base_filename="customer_base.parquet",
            report_dir="./reports/fe04",
        )
    )
    metadata: MetadataConfig = field(default_factory=MetadataConfig)


# ---------------------------------------------------------------------------
# YAML I/O helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read YAML; raise typed errors for IO / parse failures."""
    if not path.exists():
        raise AggregationConfigError(f"Aggregation config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # type: ignore[misc]
        raise AggregationConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if data is None:
        raise AggregationConfigError(f"Aggregation config file {path} is empty.")
    if not isinstance(data, dict):
        raise AggregationConfigError(
            f"Aggregation config file {path} must be a YAML mapping; got " f"{type(data).__name__}."
        )
    return data


def _require(container: dict[str, Any], key: str, *, container_name: str) -> Any:
    if key not in container:
        raise AggregationConfigError(
            f"Missing required key {key!r} under {container_name!r} in aggregation config."
        )
    return container[key]


def _require_str(container: dict[str, Any], key: str, *, container_name: str) -> str:
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, str):
        raise AggregationConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_bool(container: dict[str, Any], key: str, *, container_name: str) -> bool:
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, bool):
        raise AggregationConfigError(
            f"Expected {key!r} under {container_name!r} to be a boolean; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_list(container: dict[str, Any], key: str, *, container_name: str) -> list[Any]:
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, list):
        raise AggregationConfigError(
            f"Expected {key!r} under {container_name!r} to be a list; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


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
        raise AggregationConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def find_default_aggregation_config_path() -> Path:
    """Return the canonical path to ``configs/aggregation.yaml``."""
    return DEFAULT_AGGREGATION_CONFIG_PATH


def resolve_aggregation_config_path(
    explicit: Path | None = None,
) -> Path | None:
    """Pick the aggregation config path.

    Parameters
    ----------
    explicit : pathlib.Path, optional
        If provided, always returned (caller handles missing files).
    """
    if explicit is not None:
        return explicit
    if DEFAULT_AGGREGATION_CONFIG_PATH.exists():
        return DEFAULT_AGGREGATION_CONFIG_PATH
    return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_source(raw: dict[str, Any] | None) -> SourceConfig:
    if raw is None:
        return SourceConfig(
            role="primary",
            cleaned_dataset_path="./data/processed/transactions_clean.parquet",
            raw_dataset_path="./data/raw/primary/Online Retail.xlsx",
        )
    if not isinstance(raw, dict):
        raise AggregationConfigError(
            f"Expected 'source' to be a mapping; got {type(raw).__name__}."
        )
    return SourceConfig(
        role=_optional_str(raw, "role", container_name="source", default="primary"),
        cleaned_dataset_path=_optional_str(
            raw,
            "cleaned_dataset_path",
            container_name="source",
            default="./data/processed/transactions_clean.parquet",
        ),
        raw_dataset_path=_optional_str(
            raw,
            "raw_dataset_path",
            container_name="source",
            default="./data/raw/primary/Online Retail.xlsx",
        ),
    )


def _parse_line_revenue_columns(raw: dict[str, Any] | None) -> LineRevenueColumns:
    if raw is None:
        return LineRevenueColumns(quantity="Quantity", unit_price="UnitPrice", output="LineRevenue")
    if not isinstance(raw, dict):
        raise AggregationConfigError(
            f"Expected 'line_revenue_columns' to be a mapping; got {type(raw).__name__}."
        )
    return LineRevenueColumns(
        quantity=_require_str(raw, "quantity", container_name="line_revenue_columns"),
        unit_price=_require_str(raw, "unit_price", container_name="line_revenue_columns"),
        output=_require_str(raw, "output", container_name="line_revenue_columns"),
    )


def _parse_aggregation_spec(raw: dict[str, Any], *, idx: int) -> AggregationSpec:
    if not isinstance(raw, dict):
        raise AggregationConfigError(
            f"Expected aggregations[{idx}] to be a mapping; got {type(raw).__name__}."
        )
    name = _require_str(raw, "name", container_name=f"aggregations[{idx}]")
    source = _require_str(raw, "source", container_name=f"aggregations[{idx}]")
    fn = _require_str(raw, "fn", container_name=f"aggregations[{idx}]")
    status = _optional_str(
        raw,
        "status",
        container_name=f"aggregations[{idx}]",
        default=AGGREGATION_STATUS_WORKING_ASSUMPTION,
    )
    description = _optional_str(
        raw,
        "description",
        container_name=f"aggregations[{idx}]",
        default="",
    )
    try:
        return AggregationSpec(
            name=name, source=source, fn=fn, status=status, description=description
        )
    except AggregationConfigError:
        raise


def _parse_output(raw: dict[str, Any] | None) -> OutputConfig:
    if raw is None:
        return OutputConfig(
            processed_dir="./data/processed",
            customer_base_filename="customer_base.parquet",
            report_dir="./reports/fe04",
        )
    if not isinstance(raw, dict):
        raise AggregationConfigError(
            f"Expected 'output' to be a mapping; got {type(raw).__name__}."
        )
    return OutputConfig(
        processed_dir=_require_str(raw, "processed_dir", container_name="output"),
        customer_base_filename=_require_str(raw, "customer_base_filename", container_name="output"),
        report_dir=_require_str(raw, "report_dir", container_name="output"),
    )


def _parse_metadata(raw: dict[str, Any] | None) -> MetadataConfig:
    if raw is None:
        return MetadataConfig(
            stage="FE-04",
            task_description="",
            scope_boundaries=[],
            notes=[],
        )
    if not isinstance(raw, dict):
        raise AggregationConfigError(
            f"Expected 'metadata' to be a mapping; got {type(raw).__name__}."
        )
    stage = _optional_str(raw, "stage", container_name="metadata", default="FE-04")
    task_description = _optional_str(raw, "task_description", container_name="metadata", default="")
    scope_raw = raw.get("scope_boundaries", [])
    if not isinstance(scope_raw, list):
        raise AggregationConfigError(
            f"Expected 'scope_boundaries' under metadata to be a list; "
            f"got {type(scope_raw).__name__}."
        )
    scope_boundaries: list[str] = [str(s) for s in scope_raw]
    notes_raw = raw.get("notes", [])
    if not isinstance(notes_raw, list):
        raise AggregationConfigError(
            f"Expected 'notes' under metadata to be a list; " f"got {type(notes_raw).__name__}."
        )
    notes: list[str] = [str(n) for n in notes_raw]
    return MetadataConfig(
        stage=stage,
        task_description=task_description,
        scope_boundaries=scope_boundaries,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Public API: load_aggregation_config
# ---------------------------------------------------------------------------


def load_aggregation_config(
    path: Path | None = None,
    *,
    strict: bool = True,
) -> AggregationConfig:
    """Load ``configs/aggregation.yaml`` and return a typed config.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit YAML path. ``None`` uses
        :data:`DEFAULT_AGGREGATION_CONFIG_PATH`.
    strict : bool, default True
        If ``True``, missing keys raise :class:`AggregationConfigError`.
        If ``False``, dataclass defaults fill in gaps (intended for
        partial overrides).

    Returns
    -------
    AggregationConfig
        Typed config ready to pass to the FE-04 orchestrator.

    Raises
    ------
    AggregationConfigError
        If the YAML cannot be read, parsed, or is missing required
        keys under ``strict=True``.
    """
    if path is None:
        path = DEFAULT_AGGREGATION_CONFIG_PATH

    raw = _read_yaml(path)
    if "aggregation" not in raw or not isinstance(raw["aggregation"], dict):
        raise AggregationConfigError(
            f"Aggregation config file {path} must have a top-level " f"'aggregation' mapping."
        )
    top: dict[str, Any] = raw["aggregation"]

    if strict:
        for required in ("source", "aggregations", "output"):
            if required not in top:
                raise AggregationConfigError(
                    f"Missing required key 'aggregation.{required}' in {path}."
                )

    enabled = top.get("enabled", True)
    if not isinstance(enabled, bool):
        raise AggregationConfigError(
            f"'aggregation.enabled' must be a bool; got {type(enabled).__name__}."
        )

    random_seed = top.get("random_seed", 42)
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise AggregationConfigError(
            f"'aggregation.random_seed' must be an int; got {type(random_seed).__name__}."
        )

    source = _parse_source(top.get("source"))

    agg_raw = _require_list(top, "aggregations", container_name="aggregation")
    aggregations: list[AggregationSpec] = []
    for i, item in enumerate(agg_raw):
        aggregations.append(_parse_aggregation_spec(item, idx=i))

    customer_key = _optional_str(
        top, "customer_key", container_name="aggregation", default="CustomerID"
    )

    line_revenue_columns = _parse_line_revenue_columns(top.get("line_revenue_columns"))

    output = _parse_output(top.get("output"))

    metadata = _parse_metadata(top.get("metadata"))

    return AggregationConfig(
        enabled=enabled,
        random_seed=random_seed,
        source=source,
        aggregations=aggregations,
        customer_key=customer_key,
        line_revenue_columns=line_revenue_columns,
        output=output,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Serialisation (for fe04_run.json)
# ---------------------------------------------------------------------------


def aggregation_config_to_dict(config: AggregationConfig) -> dict[str, Any]:
    """Serialise an :class:`AggregationConfig` to a JSON-friendly dict."""
    return {
        "enabled": config.enabled,
        "random_seed": config.random_seed,
        "source": {
            "role": config.source.role,
            "cleaned_dataset_path": config.source.cleaned_dataset_path,
            "raw_dataset_path": config.source.raw_dataset_path,
        },
        "aggregations": [
            {
                "name": spec.name,
                "source": spec.source,
                "fn": spec.fn,
                "status": spec.status,
                "description": spec.description,
            }
            for spec in config.aggregations
        ],
        "customer_key": config.customer_key,
        "line_revenue_columns": {
            "quantity": config.line_revenue_columns.quantity,
            "unit_price": config.line_revenue_columns.unit_price,
            "output": config.line_revenue_columns.output,
        },
        "output": {
            "processed_dir": config.output.processed_dir,
            "customer_base_filename": config.output.customer_base_filename,
            "report_dir": config.output.report_dir,
        },
        "metadata": {
            "stage": config.metadata.stage,
            "task_description": config.metadata.task_description,
            "scope_boundaries": config.metadata.scope_boundaries,
            "notes": config.metadata.notes,
        },
    }
