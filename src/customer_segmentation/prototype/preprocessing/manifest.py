"""PreprocessedManifest schema, JSON I/O, and stable/runtime classification.

A :class:`PreprocessedManifest` is the on-disk sidecar of one DEV-03
preprocessed run. It records:

- ``preprocessed_id`` (content-addressed),
- ``source_dataset_id`` + ``source_dataset_sha256`` (DEV-02 pointer),
- ``config_hash`` (reproducibility contract per AGENTS.md §2.7),
- ``preprocessing_block`` (Stages A→E summary),
- ``feature_generation_block`` (Stage F summary; populated by the
  feature-generation sub-package, *not* by this module),
- ``ml_dataset_block`` (Stage G customer-level summary),
- ``environment`` (python / platform / libraries),
- ``research_safety`` (always ``automatically_promoted_to_research=false``,
  ``scope="PREPROCESSED_PROTOTYPE"``).

The manifest is split into two field groups:

- **Stable** — equal across runs of the same input + same config.
- **Runtime** — may differ across runs (``created_utc``,
  ``last_seen_utc``, ``environment``, ``config_hash``).

Hard rules
----------
- A manifest is **only** ever written after a successful Stage G
  atomic write. Failed runs do NOT leave a manifest on disk.
- The manifest never stores the **absolute** source path. It points
  to the DEV-02 dataset_id which carries its own provenance.
- The manifest's ``research_safety`` block is **always**:
  - ``automatically_promoted_to_research=false``
  - ``scope="PREPROCESSED_PROTOTYPE"``
  - ``appeared_in_research_evidence=false``
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

__all__ = [
    "PREPROCESSED_MANIFEST_SCHEMA_VERSION",
    "Dev03ManifestError",
    "CleaningRuleRecord",
    "EnvironmentBlock",
    "MLDatasetBlock",
    "FeatureGenerationBlock",
    "FeatureGenerationAggregationBlock",
    "FeatureGenerationRFMBlock",
    "FeatureGenerationBehaviorBlock",
    "FeatureGenerationQuantityBlock",
    "FeatureGenerationDiversityBlock",
    "FeatureGenerationCancellationBlock",
    "PreprocessingBlock",
    "PreprocessedManifest",
    "ResearchSafetyBlock",
    "manifest_to_dict",
    "read_preprocessed_manifest",
    "stable_field_names",
    "runtime_field_names",
    "write_preprocessed_manifest",
    "now_iso",
]


PREPROCESSED_MANIFEST_SCHEMA_VERSION: Final[str] = "1.0.0"


class Dev03ManifestError(ValueError):
    """Raised on manifest construction / I/O failures."""


# ---------------------------------------------------------------------------
# Sub-blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CleaningRuleRecord:
    """One cleaning rule's status, inherited verbatim from FE-02."""

    rule_id: str
    status: str  # CleaningRuleStatus.value


@dataclass(frozen=True)
class PreprocessingBlock:
    """Summary of Stages A→E (Dataset → Validation → Cleaning → Transform → Scale)."""

    enabled: bool
    input_row_count: int
    input_column_count: int
    output_row_count: int
    rows_removed_total: int
    rows_retained: int
    cancellation_prefix: str
    flag_cancellations: bool
    flag_returns: bool
    outlier_action: str
    outlier_method: str
    transformation: str
    scaling: str
    stage_outcomes: dict[str, str]  # Stage A→E -> "PASS"/"WARNING"/"FAIL"
    rules: list[CleaningRuleRecord]
    config_snapshot: dict[str, Any]
    status: str  # "WORKING_ASSUMPTION" — DEV-03 default status


@dataclass(frozen=True)
class MLDatasetBlock:
    """Summary of the customer-level ML Dataset (Stage G output)."""

    row_count: int
    column_count: int
    columns: list[str]
    sha256: str
    file_size_bytes: int
    artifact_path: str
    status: str  # "WORKING_ASSUMPTION"


@dataclass(frozen=True)
class FeatureGenerationAggregationBlock:
    """Stage F1 (FE-04) aggregation block (status inherited verbatim)."""

    enabled: bool
    customer_key: str
    status: str  # "WORKING_ASSUMPTION" per FE-04; DEV-03 inherits


@dataclass(frozen=True)
class FeatureGenerationRFMBlock:
    """Stage F2 RFM block."""

    monetary_strategy: str
    monetary_status: str
    frequency_mode: str
    frequency_status: str
    reference_date_mode: str
    reference_date_value: str


@dataclass(frozen=True)
class FeatureGenerationQuantityBlock:
    """Stage F2 quantity working-set block."""

    default_variant: str  # "signed" | "purchase_only"
    status: str


@dataclass(frozen=True)
class FeatureGenerationBehaviorBlock:
    """Stage F2 transaction-behavior block."""

    tenure_enabled: bool
    purchase_interval_ddof: int
    active_days_enabled: bool
    average_invoice_value_enabled: bool


@dataclass(frozen=True)
class FeatureGenerationDiversityBlock:
    """Stage F2 diversity block.

    ``CategoryCount_NOT_materialized=True`` documents the FE-05 hard
    constraint: CategoryCount is never produced by DEV-03.
    """

    strategy: str
    category_count_not_materialized: bool


@dataclass(frozen=True)
class FeatureGenerationCancellationBlock:
    """Stage F2 cancellation/return block."""

    cancellation_enabled: bool
    return_enabled: bool
    status: str


@dataclass(frozen=True)
class FeatureGenerationBlock:
    """Stage F summary; populated by the feature-generation sub-package."""

    enabled: bool
    aggregation: FeatureGenerationAggregationBlock
    rfm: FeatureGenerationRFMBlock
    quantity: FeatureGenerationQuantityBlock
    behavior: FeatureGenerationBehaviorBlock
    diversity: FeatureGenerationDiversityBlock
    cancellation: FeatureGenerationCancellationBlock
    optional_transform_transformation: str
    optional_transform_scaling: str
    optional_transform_imputation: str
    status: str


@dataclass(frozen=True)
class EnvironmentBlock:
    """5-field reproducibility contract (SYS-02 §9.2 style).

    Attributes
    ----------
    python : str
        Python version, e.g. ``"3.11.9"``.
    platform : str
        OS identifier, e.g. ``"Linux"``.
    release : str
        OS release string.
    machine : str
        Architecture identifier.
    key_libraries : dict[str, str]
        Mapping of pinned library names to their installed versions
        (numpy, pandas, scikit-learn, pyarrow).
    """

    python: str
    platform: str
    release: str
    machine: str
    key_libraries: dict[str, str]


@dataclass(frozen=True)
class ResearchSafetyBlock:
    """Research-safety markers for the preprocessed artefact."""

    automatically_promoted_to_research: bool
    scope: str
    appeared_in_research_evidence: bool
    read_only_paths_unmodified: list[str]


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreprocessedManifest:
    """On-disk manifest of one DEV-03 preprocessed run."""

    schema_version: str
    preprocessed_id: str
    preprocessed_scope: str
    source_dataset_id: str
    source_dataset_sha256: str
    config_hash: str
    preprocessing_block: PreprocessingBlock
    feature_generation_block: FeatureGenerationBlock
    ml_dataset_block: MLDatasetBlock
    environment: EnvironmentBlock
    research_safety: ResearchSafetyBlock
    created_utc: str
    last_seen_utc: str
    log_file: str
    intermediate_artifact_path: str | None = None


# ---------------------------------------------------------------------------
# Stable / runtime classification
# ---------------------------------------------------------------------------


_STABLE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "preprocessed_id",
        "preprocessed_scope",
        "source_dataset_id",
        "source_dataset_sha256",
        "preprocessing_block",
        "feature_generation_block",
        "ml_dataset_block",
        "research_safety",
        "log_file",
        "intermediate_artifact_path",
    }
)

_RUNTIME_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "config_hash",
        "environment",
        "created_utc",
        "last_seen_utc",
    }
)


def stable_field_names() -> frozenset[str]:
    """Return the set of top-level field names that are stable across runs."""
    return _STABLE_FIELDS


def runtime_field_names() -> frozenset[str]:
    """Return the set of top-level field names that may differ across runs."""
    return _RUNTIME_FIELDS


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def manifest_to_dict(m: PreprocessedManifest) -> dict[str, Any]:
    """Convert a :class:`PreprocessedManifest` to a JSON-serialisable dict."""

    def _to_jsonable(value: Any) -> Any:
        if isinstance(value, PreprocessedManifest):
            return _to_jsonable(asdict(value))
        if isinstance(value, list):
            return [_to_jsonable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if hasattr(value, "__dataclass_fields__"):
            return _to_jsonable(asdict(value))
        raise TypeError(f"Cannot serialise value of type {type(value).__name__}.")

    return _to_jsonable(m)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def write_preprocessed_manifest(manifest: PreprocessedManifest, path: Path) -> None:
    """Atomically write a :class:`PreprocessedManifest` to ``path``.

    Writes to a temp file in the same directory and renames on success.
    """
    path = Path(path)
    if not path.parent.exists():
        raise Dev03ManifestError(
            f"Cannot write manifest to {path!s}: parent directory does not exist."
        )
    payload = manifest_to_dict(manifest)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


def read_preprocessed_manifest(path: Path) -> PreprocessedManifest:
    """Read and reconstruct a :class:`PreprocessedManifest` from JSON."""
    path = Path(path)
    if not path.exists():
        raise Dev03ManifestError(f"Manifest file not found: {path!s}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise Dev03ManifestError(f"Failed to parse manifest JSON at {path!s}: {exc}") from exc
    if not isinstance(data, dict):
        raise Dev03ManifestError(
            f"Manifest at {path!s} must be a JSON object; got {type(data).__name__}."
        )
    return _dict_to_manifest(data)


def _dict_to_manifest(data: Mapping[str, Any]) -> PreprocessedManifest:
    """Build a :class:`PreprocessedManifest` from a JSON object."""
    required = (
        "schema_version",
        "preprocessed_id",
        "preprocessed_scope",
        "source_dataset_id",
        "source_dataset_sha256",
        "preprocessing_block",
        "feature_generation_block",
        "ml_dataset_block",
        "environment",
        "research_safety",
        "created_utc",
        "last_seen_utc",
        "log_file",
    )
    for key in required:
        if key not in data:
            raise Dev03ManifestError(f"Manifest is missing required field: {key!r}.")

    pb_raw = data["preprocessing_block"]
    rules = [
        CleaningRuleRecord(rule_id=str(r["rule_id"]), status=str(r["status"]))
        for r in pb_raw.get("rules", [])
    ]
    preprocessing_block = PreprocessingBlock(
        enabled=bool(pb_raw["enabled"]),
        input_row_count=int(pb_raw["input_row_count"]),
        input_column_count=int(pb_raw["input_column_count"]),
        output_row_count=int(pb_raw["output_row_count"]),
        rows_removed_total=int(pb_raw["rows_removed_total"]),
        rows_retained=int(pb_raw["rows_retained"]),
        cancellation_prefix=str(pb_raw["cancellation_prefix"]),
        flag_cancellations=bool(pb_raw["flag_cancellations"]),
        flag_returns=bool(pb_raw["flag_returns"]),
        outlier_action=str(pb_raw["outlier_action"]),
        outlier_method=str(pb_raw["outlier_method"]),
        transformation=str(pb_raw["transformation"]),
        scaling=str(pb_raw["scaling"]),
        stage_outcomes={str(k): str(v) for k, v in pb_raw["stage_outcomes"].items()},
        rules=rules,
        config_snapshot=dict(pb_raw["config_snapshot"]),
        status=str(pb_raw["status"]),
    )

    fg_raw = data["feature_generation_block"]
    ag_raw = fg_raw["aggregation"]
    rfm_raw = fg_raw["rfm"]
    qty_raw = fg_raw["quantity"]
    beh_raw = fg_raw["behavior"]
    div_raw = fg_raw["diversity"]
    can_raw = fg_raw["cancellation"]
    feature_generation_block = FeatureGenerationBlock(
        enabled=bool(fg_raw["enabled"]),
        aggregation=FeatureGenerationAggregationBlock(
            enabled=bool(ag_raw["enabled"]),
            customer_key=str(ag_raw["customer_key"]),
            status=str(ag_raw["status"]),
        ),
        rfm=FeatureGenerationRFMBlock(
            monetary_strategy=str(rfm_raw["monetary_strategy"]),
            monetary_status=str(rfm_raw["monetary_status"]),
            frequency_mode=str(rfm_raw["frequency_mode"]),
            frequency_status=str(rfm_raw["frequency_status"]),
            reference_date_mode=str(rfm_raw["reference_date_mode"]),
            reference_date_value=str(rfm_raw["reference_date_value"]),
        ),
        quantity=FeatureGenerationQuantityBlock(
            default_variant=str(qty_raw["default_variant"]),
            status=str(qty_raw["status"]),
        ),
        behavior=FeatureGenerationBehaviorBlock(
            tenure_enabled=bool(beh_raw["tenure_enabled"]),
            purchase_interval_ddof=int(beh_raw["purchase_interval_ddof"]),
            active_days_enabled=bool(beh_raw["active_days_enabled"]),
            average_invoice_value_enabled=bool(beh_raw["average_invoice_value_enabled"]),
        ),
        diversity=FeatureGenerationDiversityBlock(
            strategy=str(div_raw["strategy"]),
            category_count_not_materialized=bool(div_raw["category_count_not_materialized"]),
        ),
        cancellation=FeatureGenerationCancellationBlock(
            cancellation_enabled=bool(can_raw["cancellation_enabled"]),
            return_enabled=bool(can_raw["return_enabled"]),
            status=str(can_raw["status"]),
        ),
        optional_transform_transformation=str(fg_raw["optional_transform_transformation"]),
        optional_transform_scaling=str(fg_raw["optional_transform_scaling"]),
        optional_transform_imputation=str(fg_raw["optional_transform_imputation"]),
        status=str(fg_raw["status"]),
    )

    ml_raw = data["ml_dataset_block"]
    ml_dataset_block = MLDatasetBlock(
        row_count=int(ml_raw["row_count"]),
        column_count=int(ml_raw["column_count"]),
        columns=[str(c) for c in ml_raw["columns"]],
        sha256=str(ml_raw["sha256"]),
        file_size_bytes=int(ml_raw["file_size_bytes"]),
        artifact_path=str(ml_raw["artifact_path"]),
        status=str(ml_raw["status"]),
    )

    env_raw = data["environment"]
    environment = EnvironmentBlock(
        python=str(env_raw["python"]),
        platform=str(env_raw["platform"]),
        release=str(env_raw["release"]),
        machine=str(env_raw["machine"]),
        key_libraries={str(k): str(v) for k, v in env_raw.get("key_libraries", {}).items()},
    )

    rs_raw = data["research_safety"]
    research_safety = ResearchSafetyBlock(
        automatically_promoted_to_research=bool(rs_raw["automatically_promoted_to_research"]),
        scope=str(rs_raw["scope"]),
        appeared_in_research_evidence=bool(rs_raw["appeared_in_research_evidence"]),
        read_only_paths_unmodified=[str(p) for p in rs_raw.get("read_only_paths_unmodified", [])],
    )

    return PreprocessedManifest(
        schema_version=str(data["schema_version"]),
        preprocessed_id=str(data["preprocessed_id"]),
        preprocessed_scope=str(data["preprocessed_scope"]),
        source_dataset_id=str(data["source_dataset_id"]),
        source_dataset_sha256=str(data["source_dataset_sha256"]),
        config_hash=str(data["config_hash"]),
        preprocessing_block=preprocessing_block,
        feature_generation_block=feature_generation_block,
        ml_dataset_block=ml_dataset_block,
        environment=environment,
        research_safety=research_safety,
        created_utc=str(data["created_utc"]),
        last_seen_utc=str(data["last_seen_utc"]),
        log_file=str(data["log_file"]),
        intermediate_artifact_path=(
            str(data["intermediate_artifact_path"])
            if data.get("intermediate_artifact_path") is not None
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a "Z" suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
