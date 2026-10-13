"""EvaluationManifest schema, JSON I/O, and stable/runtime classification.

A :class:`EvaluationManifest` is the on-disk sidecar of one DEV-05
evaluation pass. It records:

- ``evaluation_id`` (content-addressed from 8 canonical fields, see
  :mod:`customer_segmentation.prototype.evaluation.storage`),
- ``clustering_id`` + ``preprocessed_id`` + ``dataset_id`` (DEV-04/03/02
  pointers, all canonical),
- ``ml_dataset_sha256`` (canonical), ``feature_set_sha256`` (derived),
  ``preprocessing_config_sha256`` (from DEV-03 manifest ``config_hash``),
- ``algorithm`` + ``algorithm_version`` + ``algorithm_family``,
- ``noise_policy_used`` (per ADR-0006 prototype default = "exclude"),
- ``metric_set`` (list of metric names computed),
- ``metrics`` (per-metric entries: value / status / reason /
  is_diagnostic_only / lower_is_better / computation_time_seconds),
- ``n_samples_input`` + ``n_samples_used_for_compute`` +
  ``n_clusters_realized`` + ``noise_count`` + ``noise_ratio`` (DBSCAN
  provenance audit; per plan §5.4.4),
- ``hyperparameters`` (verbatim from upstream DEV-04 manifest),
- ``environment``,
- ``research_safety`` (always
  ``automatically_promoted_to_research=false``,
  ``scope="EVALUATED_PROTOTYPE"``,
  ``appeared_in_research_evidence=false``).

The manifest is split into two field groups:

- **Stable** — equal across runs of the same input + same config.
- **Runtime** — may differ across runs
  (``created_utc``, ``last_seen_utc``, ``environment``).

Hard rules
----------
- A manifest is **only** written after Stage E (compute done). If the
  pipeline aborts at Stage A/B/C/D, the manifest is still written
  with ``status`` per metric set to ``COMPUTATION_ERROR`` /
  ``MISSING`` as appropriate. The manifest is the source of truth for
  audit: a partially-valid evaluation is more useful than no record.
- The manifest writer uses **atomic write** (temp file + rename) to
  avoid partial writes (R-EVAL-17).
- ``metric_value = None`` iff ``metric_status != VALID_VALUE`` (no fake
  defaults per plan §5.5 rule 2).
- ``research_safety`` block is **always**:
  ``automatically_promoted_to_research=false``,
  ``scope="EVALUATED_PROTOTYPE"``,
  ``appeared_in_research_evidence=false``.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.evaluation.scope import (
    DEFAULT_METRIC_SET,
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    METRIC_REASON_BY_STATUS,
    METRIC_STATUSES,
    MetricName,
    MetricStatus,
    MetricReason,
)

__all__ = [
    "EVALUATION_MANIFEST_SCHEMA_VERSION",
    "EvaluationManifestError",
    "EvaluationManifest",
    "EvaluationMetricEntry",
    "EvaluationMetricsResult",
    "EvaluationValidationReport",
    "ValidationCheck",
    "ResearchSafetyBlock",
    "InputIdentityBlock",
    "EnvironmentBlock",
    "read_evaluation_manifest",
    "stable_field_names",
    "runtime_field_names",
    "write_evaluation_manifest",
    "manifest_to_dict",
    "now_utc_iso",
    "build_evaluation_manifest",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default order for metrics_long.csv rows (canonical row order).
DEFAULT_METRIC_NAMES_ORDERED: Final[tuple[str, ...]] = DEFAULT_METRIC_SET

# Per-metric static metadata: which direction is "better", and whether
# the metric is "diagnostic only" (DEV-05 = all False per plan §5.5 rule 8).
_METRIC_METADATA: Final[dict[str, dict[str, bool]]] = {
    MetricName.SILHOUETTE.value: {
        "lower_is_better": False,
        "is_diagnostic_only": False,
    },
    MetricName.DAVIES_BOULDIN.value: {
        "lower_is_better": True,
        "is_diagnostic_only": False,
    },
    MetricName.CALINSKI_HARABASZ.value: {
        "lower_is_better": False,
        "is_diagnostic_only": False,
    },
}


# ---------------------------------------------------------------------------
# Stable / runtime classification
# ---------------------------------------------------------------------------

_STABLE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "evaluation_id",
        "scope",
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "ml_dataset_sha256",
        "feature_set_sha256",
        "preprocessing_config_sha256",
        "algorithm",
        "algorithm_version",
        "algorithm_family",
        "noise_policy_used",
        "metric_set",
        "metrics",
        "n_samples_input",
        "n_samples_used_for_compute",
        "n_clusters_realized",
        "noise_count",
        "noise_ratio",
        "n_samples",
        "n_features",
        "feature_set",
        "feature_count",
        "hyperparameters",
        "seed_policy",
        "seed",
        "config_sha256",
        "log_file",
        "validation_report",
        "research_safety",
    }
)

_RUNTIME_FIELDS: Final[frozenset[str]] = frozenset(
    {"created_utc", "last_seen_utc", "environment"}
)


def stable_field_names() -> frozenset[str]:
    """Return the set of stable field names."""
    return _STABLE_FIELDS


def runtime_field_names() -> frozenset[str]:
    """Return the set of runtime field names."""
    return _RUNTIME_FIELDS


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EvaluationManifestError(ValueError):
    """Raised on manifest construction / I/O / invariant failures."""


# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------


def now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string (suffix ``Z``)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Sub-blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchSafetyBlock:
    """Research-safety markers (always prototype scope).

    Per R-EVAL-01..03:
    - ``automatically_promoted_to_research = False`` always
    - ``scope = "EVALUATED_PROTOTYPE"`` always
    - ``appeared_in_research_evidence = False`` always
    """

    automatically_promoted_to_research: bool
    scope: str
    appeared_in_research_evidence: bool
    read_only_paths_unmodified: list[str]

    def __post_init__(self) -> None:
        if self.automatically_promoted_to_research is not False:
            raise EvaluationManifestError(
                "research_safety.automatically_promoted_to_research MUST be False; "
                f"got {self.automatically_promoted_to_research!r}."
            )
        if self.scope != "EVALUATED_PROTOTYPE":
            raise EvaluationManifestError(
                "research_safety.scope MUST be 'EVALUATED_PROTOTYPE'; "
                f"got {self.scope!r}."
            )
        if self.appeared_in_research_evidence is not False:
            raise EvaluationManifestError(
                "research_safety.appeared_in_research_evidence MUST be False; "
                f"got {self.appeared_in_research_evidence!r}."
            )


@dataclass(frozen=True)
class InputIdentityBlock:
    """Identity of the source ML Dataset and cluster_labels parquet."""

    ml_dataset_sha256: str
    ml_dataset_path: str
    cluster_labels_sha256: str
    cluster_labels_path: str


@dataclass(frozen=True)
class EnvironmentBlock:
    """Runtime environment snapshot."""

    python: str
    platform: str
    release: str
    machine: str
    key_libraries: dict[str, str]


@dataclass(frozen=True)
class ValidationCheck:
    """A single validation check (id + outcome)."""

    check_id: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class EvaluationValidationReport:
    """Outcome of input validation (Stage C of the pipeline).

    Mirrors the validation pattern from
    :class:`customer_segmentation.clustering.validation.ValidationReport`.
    """

    all_passed: bool
    checks: list[ValidationCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "checks": [
                {"check_id": c.check_id, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Metric entry + result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationMetricEntry:
    """One metric row: numeric value, status, reason, metadata.

    Invariants (per plan §5.5):
    - ``value`` is ``None`` iff ``status != VALID_VALUE``.
    - ``status`` is a closed enum value (4-value).
    - ``reason`` is a closed enum value (in the ``status`` subgroup).
    - For ``VALID_VALUE`` status, the only valid reasons are
      ``COMPUTED`` or ``DBSCAN_NOISE_EXCLUDED``.
    - ``is_diagnostic_only`` is always ``False`` for DEV-05 metrics.
    - ``lower_is_better`` is ``True`` only for DBI; ``False`` for
      silhouette and CH (per sklearn convention).
    - ``computation_time_seconds`` is always set (None if unknown).
    """

    metric_name: str
    value: float | None
    status: str
    reason: str
    is_diagnostic_only: bool
    lower_is_better: bool
    computation_time_seconds: float | None

    def __post_init__(self) -> None:
        if self.metric_name not in {m.value for m in MetricName}:
            raise EvaluationManifestError(
                f"metric_name {self.metric_name!r} is not in the closed set "
                f"of MetricName."
            )
        if self.status not in METRIC_STATUSES:
            raise EvaluationManifestError(
                f"status {self.status!r} is not in the closed set {sorted(METRIC_STATUSES)}."
            )
        # Reason must belong to the status subgroup.
        allowed_reasons = METRIC_REASON_BY_STATUS.get(self.status, frozenset())
        if self.reason not in allowed_reasons:
            raise EvaluationManifestError(
                f"reason {self.reason!r} is not valid for status {self.status!r}; "
                f"allowed: {sorted(allowed_reasons)}."
            )
        # value ↔ status invariant: value is None iff status != VALID_VALUE.
        if self.status == MetricStatus.VALID_VALUE.value and self.value is None:
            raise EvaluationManifestError(
                f"metric {self.metric_name!r} has status VALID_VALUE but value is None."
            )
        if self.status != MetricStatus.VALID_VALUE.value and self.value is not None:
            raise EvaluationManifestError(
                f"metric {self.metric_name!r} has non-None value {self.value!r} "
                f"but status is {self.status!r} (must be None when status != VALID_VALUE)."
            )
        # is_diagnostic_only invariant: always False for DEV-05.
        if self.is_diagnostic_only is not False:
            raise EvaluationManifestError(
                f"is_diagnostic_only MUST be False for DEV-05 metrics; got "
                f"{self.is_diagnostic_only!r} for {self.metric_name!r}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "status": self.status,
            "reason": self.reason,
            "is_diagnostic_only": self.is_diagnostic_only,
            "lower_is_better": self.lower_is_better,
            "computation_time_seconds": self.computation_time_seconds,
        }


@dataclass(frozen=True)
class EvaluationMetricsResult:
    """The 3-metric result for one evaluation pass (silhouette/DBI/CH).

    Always contains exactly the 3 metric names; missing metrics
    are surfaced as ``MISSING / MANIFEST_MISSING`` entries.
    """

    entries: dict[str, EvaluationMetricEntry]

    def __post_init__(self) -> None:
        if not isinstance(self.entries, dict):
            raise EvaluationManifestError(
                f"entries must be a dict; got {type(self.entries).__name__}."
            )
        expected = {m.value for m in MetricName}
        actual = set(self.entries.keys())
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            raise EvaluationManifestError(
                f"entries keys must be exactly {sorted(expected)}; "
                f"missing={sorted(missing)}, extra={sorted(extra)}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {name: entry.to_dict() for name, entry in self.entries.items()}

    def as_flat_rows(self) -> list[dict[str, Any]]:
        """Return rows for ``metrics_long.csv`` (in canonical order)."""
        rows = []
        for metric_name in DEFAULT_METRIC_NAMES_ORDERED:
            e = self.entries[metric_name]
            rows.append(
                {
                    "metric_name": metric_name,
                    "value": e.value if e.value is not None else "",
                    "status": e.status,
                    "reason": e.reason,
                    "is_diagnostic_only": e.is_diagnostic_only,
                    "lower_is_better": e.lower_is_better,
                    "computation_time_seconds": (
                        e.computation_time_seconds
                        if e.computation_time_seconds is not None
                        else ""
                    ),
                }
            )
        return rows


# ---------------------------------------------------------------------------
# Top-level manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationManifest:
    """On-disk manifest of one DEV-05 evaluation pass.

    ``metric_set`` is the list of metric names actually computed
    (subset of :data:`DEFAULT_METRIC_SET`). ``metrics`` always has
    one entry per name in :data:`DEFAULT_METRIC_SET` (3 entries).
    """

    schema_version: str
    evaluation_id: str
    scope: str
    clustering_id: str
    preprocessed_id: str
    dataset_id: str
    ml_dataset_sha256: str
    feature_set_sha256: str
    preprocessing_config_sha256: str
    algorithm: str
    algorithm_version: str
    algorithm_family: str
    n_samples: int
    n_features: int
    feature_set: list[str]
    feature_count: int
    hyperparameters: dict[str, Any]
    seed_policy: str
    seed: int | None
    noise_policy_used: str
    metric_set: list[str]
    metrics: EvaluationMetricsResult
    n_samples_input: int
    n_samples_used_for_compute: int
    n_clusters_realized: int
    noise_count: int | None
    noise_ratio: float | None
    environment: EnvironmentBlock
    config_sha256: str
    created_utc: str
    last_seen_utc: str
    log_file: str
    validation_report: EvaluationValidationReport
    research_safety: ResearchSafetyBlock

    def __post_init__(self) -> None:
        if self.scope != "EVALUATED_PROTOTYPE":
            raise EvaluationManifestError(
                f"scope MUST be 'EVALUATED_PROTOTYPE'; got {self.scope!r}."
            )
        if self.schema_version != EVALUATION_MANIFEST_SCHEMA_VERSION:
            raise EvaluationManifestError(
                f"schema_version MUST be "
                f"{EVALUATION_MANIFEST_SCHEMA_VERSION!r}; got {self.schema_version!r}."
            )
        if self.noise_policy_used not in {"include", "exclude"}:
            raise EvaluationManifestError(
                f"noise_policy_used MUST be 'include' or 'exclude'; "
                f"got {self.noise_policy_used!r}."
            )
        # n_samples_used_for_compute must be <= n_samples_input.
        if self.n_samples_used_for_compute > self.n_samples_input:
            raise EvaluationManifestError(
                f"n_samples_used_for_compute ({self.n_samples_used_for_compute}) "
                f"cannot exceed n_samples_input ({self.n_samples_input})."
            )
        # noise_count / noise_ratio: present iff algorithm_family == density_based.
        if self.algorithm_family == "density_based":
            if self.noise_count is None:
                raise EvaluationManifestError(
                    "noise_count MUST be set when algorithm_family is 'density_based'."
                )
            if self.noise_ratio is None:
                raise EvaluationManifestError(
                    "noise_ratio MUST be set when algorithm_family is 'density_based'."
                )
        else:
            if self.noise_count is not None:
                raise EvaluationManifestError(
                    f"noise_count MUST be None for non-density algorithm "
                    f"({self.algorithm_family!r}); got {self.noise_count!r}."
                )
            if self.noise_ratio is not None:
                raise EvaluationManifestError(
                    f"noise_ratio MUST be None for non-density algorithm "
                    f"({self.algorithm_family!r}); got {self.noise_ratio!r}."
                )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _make_metric_entry(
    metric_name: str,
    value: float | None,
    status: str,
    reason: str,
    computation_time_seconds: float | None = None,
) -> EvaluationMetricEntry:
    """Construct an :class:`EvaluationMetricEntry` with canonical metadata."""
    meta = _METRIC_METADATA[metric_name]
    return EvaluationMetricEntry(
        metric_name=metric_name,
        value=value,
        status=status,
        reason=reason,
        is_diagnostic_only=meta["is_diagnostic_only"],
        lower_is_better=meta["lower_is_better"],
        computation_time_seconds=computation_time_seconds,
    )


def make_missing_entry(metric_name: str, reason: str = MetricReason.MANIFEST_MISSING.value) -> EvaluationMetricEntry:
    """Construct a ``MISSING / <reason>`` entry for one metric."""
    return _make_metric_entry(
        metric_name=metric_name,
        value=None,
        status=MetricStatus.MISSING.value,
        reason=reason,
    )


def make_not_applicable_entry(
    metric_name: str,
    reason: str,
) -> EvaluationMetricEntry:
    """Construct a ``NOT_APPLICABLE / <reason>`` entry for one metric."""
    return _make_metric_entry(
        metric_name=metric_name,
        value=None,
        status=MetricStatus.NOT_APPLICABLE.value,
        reason=reason,
    )


def make_computation_error_entry(
    metric_name: str,
    reason: str,
    computation_time_seconds: float | None = None,
) -> EvaluationMetricEntry:
    """Construct a ``COMPUTATION_ERROR / <reason>`` entry for one metric."""
    return _make_metric_entry(
        metric_name=metric_name,
        value=None,
        status=MetricStatus.COMPUTATION_ERROR.value,
        reason=reason,
        computation_time_seconds=computation_time_seconds,
    )


def make_valid_entry(
    metric_name: str,
    value: float,
    reason: str = MetricReason.COMPUTED.value,
    computation_time_seconds: float | None = None,
) -> EvaluationMetricEntry:
    """Construct a ``VALID_VALUE / <reason>`` entry for one metric."""
    return _make_metric_entry(
        metric_name=metric_name,
        value=float(value),
        status=MetricStatus.VALID_VALUE.value,
        reason=reason,
        computation_time_seconds=computation_time_seconds,
    )


def build_evaluation_manifest(
    *,
    evaluation_id: str,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    ml_dataset_sha256: str,
    feature_set_sha256: str,
    preprocessing_config_sha256: str,
    algorithm: str,
    algorithm_version: str,
    algorithm_family: str,
    n_samples: int,
    n_features: int,
    feature_set: list[str],
    hyperparameters: dict[str, Any],
    seed_policy: str,
    seed: int | None,
    noise_policy_used: str,
    metric_set: list[str],
    metrics: EvaluationMetricsResult,
    n_samples_input: int,
    n_samples_used_for_compute: int,
    n_clusters_realized: int,
    noise_count: int | None,
    noise_ratio: float | None,
    config_sha256: str,
    environment: EnvironmentBlock,
    log_file: str,
    validation_report: EvaluationValidationReport,
    readonly_paths: list[str],
) -> EvaluationManifest:
    """Build an :class:`EvaluationManifest` with all invariants enforced."""
    return EvaluationManifest(
        schema_version=EVALUATION_MANIFEST_SCHEMA_VERSION,
        evaluation_id=evaluation_id,
        scope="EVALUATED_PROTOTYPE",
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha256,
        feature_set_sha256=feature_set_sha256,
        preprocessing_config_sha256=preprocessing_config_sha256,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
        algorithm_family=algorithm_family,
        n_samples=n_samples,
        n_features=n_features,
        feature_set=feature_set,
        feature_count=len(feature_set),
        hyperparameters=dict(hyperparameters),
        seed_policy=seed_policy,
        seed=seed,
        noise_policy_used=noise_policy_used,
        metric_set=list(metric_set),
        metrics=metrics,
        n_samples_input=n_samples_input,
        n_samples_used_for_compute=n_samples_used_for_compute,
        n_clusters_realized=n_clusters_realized,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        environment=environment,
        config_sha256=config_sha256,
        created_utc=now_utc_iso(),
        last_seen_utc=now_utc_iso(),
        log_file=log_file,
        validation_report=validation_report,
        research_safety=ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="EVALUATED_PROTOTYPE",
            appeared_in_research_evidence=False,
            read_only_paths_unmodified=readonly_paths,
        ),
    )


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def _to_jsonable(value: Any) -> Any:
    """Convert a value to a JSON-serializable form."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return _to_jsonable(asdict(value))
    raise TypeError(f"Cannot serialise value of type {type(value).__name__}.")


def manifest_to_dict(m: EvaluationManifest) -> dict[str, Any]:
    """Convert an :class:`EvaluationManifest` to a JSON-serialisable dict."""
    return _to_jsonable(asdict(m))


# ---------------------------------------------------------------------------
# I/O (atomic write)
# ---------------------------------------------------------------------------


def write_evaluation_manifest(manifest: EvaluationManifest, path: Path) -> None:
    """Atomically write an :class:`EvaluationManifest` to ``path``.

    Uses temp file + rename (R-EVAL-17). The parent directory must
    already exist.
    """
    path = Path(path)
    if not path.parent.exists():
        raise EvaluationManifestError(
            f"Cannot write evaluation manifest to {path!s}: "
            f"parent directory does not exist."
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


def read_evaluation_manifest(path: Path) -> EvaluationManifest:
    """Read and reconstruct an :class:`EvaluationManifest` from JSON."""
    path = Path(path)
    if not path.exists():
        raise EvaluationManifestError(f"Manifest file not found: {path!s}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise EvaluationManifestError(
            f"Failed to parse evaluation manifest JSON at {path!s}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise EvaluationManifestError(
            f"Manifest at {path!s} must be a JSON object; "
            f"got {type(data).__name__}."
        )
    return _dict_to_manifest(data)


def _dict_to_manifest(data: Mapping[str, Any]) -> EvaluationManifest:
    """Build an EvaluationManifest from a JSON object (round-trip)."""
    required = (
        "schema_version",
        "evaluation_id",
        "scope",
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "ml_dataset_sha256",
        "feature_set_sha256",
        "preprocessing_config_sha256",
        "algorithm",
        "algorithm_version",
        "algorithm_family",
        "n_samples",
        "n_features",
        "feature_set",
        "hyperparameters",
        "seed_policy",
        "seed",
        "noise_policy_used",
        "metric_set",
        "metrics",
        "n_samples_input",
        "n_samples_used_for_compute",
        "n_clusters_realized",
        "environment",
        "config_sha256",
        "created_utc",
        "last_seen_utc",
        "log_file",
        "validation_report",
        "research_safety",
    )
    for key in required:
        if key not in data:
            raise EvaluationManifestError(
                f"Manifest is missing required field: {key!r}."
            )

    # Research safety.
    rs_raw = data["research_safety"]
    research_safety = ResearchSafetyBlock(
        automatically_promoted_to_research=bool(rs_raw["automatically_promoted_to_research"]),
        scope=str(rs_raw["scope"]),
        appeared_in_research_evidence=bool(rs_raw["appeared_in_research_evidence"]),
        read_only_paths_unmodified=[
            str(p) for p in rs_raw.get("read_only_paths_unmodified", [])
        ],
    )

    # Environment.
    env_raw = data["environment"]
    key_libs = {}
    for k, v in env_raw.get("key_libraries", {}).items():
        key_libs[str(k)] = str(v)
    environment = EnvironmentBlock(
        python=str(env_raw["python"]),
        platform=str(env_raw["platform"]),
        release=str(env_raw["release"]),
        machine=str(env_raw["machine"]),
        key_libraries=key_libs,
    )

    # Validation report.
    vr_raw = data["validation_report"]
    checks_raw = vr_raw.get("checks", [])
    checks = [
        ValidationCheck(
            check_id=str(c["check_id"]),
            passed=bool(c["passed"]),
            detail=str(c.get("detail", "")),
        )
        for c in checks_raw
    ]
    validation_report = EvaluationValidationReport(
        all_passed=bool(vr_raw.get("all_passed", False)),
        checks=checks,
    )

    # Metrics.
    metrics_raw = data["metrics"]
    if not isinstance(metrics_raw, dict):
        raise EvaluationManifestError(
            f"metrics must be a dict; got {type(metrics_raw).__name__}."
        )
    entries_raw = metrics_raw.get("entries", metrics_raw)
    if not isinstance(entries_raw, dict):
        raise EvaluationManifestError(
            f"metrics.entries must be a dict; got {type(entries_raw).__name__}."
        )
    entries: dict[str, EvaluationMetricEntry] = {}
    for name, entry_raw in entries_raw.items():
        entries[str(name)] = _dict_to_metric_entry(str(name), entry_raw)
    metrics = EvaluationMetricsResult(entries=entries)

    return EvaluationManifest(
        schema_version=str(data["schema_version"]),
        evaluation_id=str(data["evaluation_id"]),
        scope=str(data["scope"]),
        clustering_id=str(data["clustering_id"]),
        preprocessed_id=str(data["preprocessed_id"]),
        dataset_id=str(data["dataset_id"]),
        ml_dataset_sha256=str(data["ml_dataset_sha256"]),
        feature_set_sha256=str(data["feature_set_sha256"]),
        preprocessing_config_sha256=str(data["preprocessing_config_sha256"]),
        algorithm=str(data["algorithm"]),
        algorithm_version=str(data["algorithm_version"]),
        algorithm_family=str(data["algorithm_family"]),
        n_samples=int(data["n_samples"]),
        n_features=int(data["n_features"]),
        feature_set=[str(f) for f in data["feature_set"]],
        feature_count=int(data.get("feature_count", len(data["feature_set"]))),
        hyperparameters=dict(data["hyperparameters"]),
        seed_policy=str(data["seed_policy"]),
        seed=data["seed"],
        noise_policy_used=str(data["noise_policy_used"]),
        metric_set=[str(m) for m in data["metric_set"]],
        metrics=metrics,
        n_samples_input=int(data["n_samples_input"]),
        n_samples_used_for_compute=int(data["n_samples_used_for_compute"]),
        n_clusters_realized=int(data["n_clusters_realized"]),
        noise_count=(
            int(data["noise_count"])
            if data.get("noise_count") is not None
            else None
        ),
        noise_ratio=(
            float(data["noise_ratio"])
            if data.get("noise_ratio") is not None
            else None
        ),
        environment=environment,
        config_sha256=str(data["config_sha256"]),
        created_utc=str(data["created_utc"]),
        last_seen_utc=str(data["last_seen_utc"]),
        log_file=str(data["log_file"]),
        validation_report=validation_report,
        research_safety=research_safety,
    )


def _dict_to_metric_entry(name: str, raw: Mapping[str, Any]) -> EvaluationMetricEntry:
    """Reconstruct one :class:`EvaluationMetricEntry` from a JSON object."""
    required = (
        "value",
        "status",
        "reason",
        "is_diagnostic_only",
        "lower_is_better",
        "computation_time_seconds",
    )
    for key in required:
        if key not in raw:
            raise EvaluationManifestError(
                f"Metric entry for {name!r} is missing required key {key!r}."
            )
    return _make_metric_entry(
        metric_name=name,
        value=(
            float(raw["value"]) if raw["value"] is not None else None
        ),
        status=str(raw["status"]),
        reason=str(raw["reason"]),
        computation_time_seconds=(
            float(raw["computation_time_seconds"])
            if raw["computation_time_seconds"] is not None
            else None
        ),
    )
