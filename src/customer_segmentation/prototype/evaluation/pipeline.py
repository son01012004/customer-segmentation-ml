"""End-to-end evaluation pipeline for DEV-05 Prototype Evaluation.

Stage A → G driver (mirror DEV-04 Stage 0 → 6 pattern):

- **A (preflight)** — load DEV-05 config; resolve dataset / preprocessed /
  clustering ids; read DEV-04 ``clustering_manifest.json``.
- **B (lookup)** — read DEV-04 ``cluster_labels_*.parquet`` and DEV-03
  ML Dataset parquet (for X). Validate paths inside storage root.
- **C (validation)** — X vs labels alignment; NaN/Inf; CustomerID leak;
  ClusterLabel dtype. Build :class:`EvaluationValidationReport`.
- **D (compute)** — call ``compute_internal_metrics`` (Stage C result
  decides whether to attempt).
- **E (manifest write)** — atomic write ``evaluation_manifest.json`` in
  staging.
- **F (publish)** — atomic ``os.rename(staging → final)``.
- **G (finalize)** — flush + close log handlers.

Output
------
- Per evaluation pass: writes
  ``<storage_root>/datasets/<ds>/preprocessed/<pp>/clustering/<cl>/
  evaluation/<ev_id>/evaluation_manifest.json`` and (when ``emit_metrics_csv``
  is true) ``metrics_long.csv``.

Side-effect discipline (R-EVAL-04..07, R-EVAL-13, R-EVAL-14):

- The pipeline NEVER mutates ``cluster_labels_*.parquet``,
  ``ml_dataset_*.parquet``, ``clustering_manifest.json``, or any
  research artefact. Reads only.
- The pipeline only writes into the
  ``evaluation/<ev_id>/`` subtree.
- All sklearn calls are wrapped in ``try/except``; on failure,
  manifest is still written with ``COMPUTATION_ERROR`` status so audit
  can inspect.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from customer_segmentation.prototype.clustering.manifest import (
    read_clustering_manifest,
)
from customer_segmentation.prototype.evaluation.config_loader import (
    Dev05Config,
    load_dev05_config,
)
from customer_segmentation.prototype.evaluation.logging_config import (
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.evaluation.manifest import (
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    ResearchSafetyBlock,
    ValidationCheck,
    build_evaluation_manifest,
    read_evaluation_manifest,
    write_evaluation_manifest,
)
from customer_segmentation.prototype.evaluation.metrics import (
    DBSCAN_NOISE_LABEL,
    compute_internal_metrics,
)
from customer_segmentation.prototype.evaluation.scope import (
    METRIC_NAMES,
    MetricReason,
    MetricStatus,
)
from customer_segmentation.prototype.evaluation.storage import (
    compute_config_sha256,
    compute_metric_set_hash,
    derive_evaluation_id,
    find_existing_evaluation,
    prototype_evaluation_base_dir,
    prototype_evaluation_run_dir,
)

__all__ = [
    "EvaluationPipelineResult",
    "Lifecycle",
    "run_evaluation_pipeline",
]


@dataclass(frozen=True)
class EvaluationPipelineResult:
    """Outcome of one evaluation pass."""

    evaluation_id: str
    manifest_path: Path
    csv_path: Path | None
    lifecycle: str  # "SUCCESS" | "FAILED" | "CACHED"
    manifest: EvaluationManifest
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Dev05PipelineError(RuntimeError):
    """Raised when the pipeline cannot proceed (fail-closed)."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CUSTOMER_KEYS_TO_STRIP: Final[frozenset[str]] = frozenset(
    {"CustomerID", "customer_id", "customerid"}
)

LIFECYCLE_SUCCESS: Final[str] = "SUCCESS"
LIFECYCLE_FAILED: Final[str] = "FAILED"
LIFECYCLE_CACHED: Final[str] = "CACHED"


# ---------------------------------------------------------------------------
# Library versions
# ---------------------------------------------------------------------------


def _capture_library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    try:
        versions["numpy"] = np.__version__
    except Exception:  # noqa: BLE001
        pass
    try:
        versions["pandas"] = pd.__version__
    except Exception:  # noqa: BLE001
        pass
    try:
        import sklearn  # type: ignore[import-untyped]

        versions["scikit-learn"] = sklearn.__version__
    except Exception:  # noqa: BLE001
        pass
    return versions


# ---------------------------------------------------------------------------
# Validation primitive
# ---------------------------------------------------------------------------


def _validate_inputs(
    X: np.ndarray,
    cluster_labels_df: pd.DataFrame,
    *,
    config: Dev05Config,
    feature_cols: list[str] | None = None,
    customer_key: str = "CustomerID",
) -> EvaluationValidationReport:
    """Validate X vs cluster_labels_df and check for NaN/Inf/leakage.

    The CustomerID leak check (R-4 + plan §1.1) is performed on the
    **feature matrix** ``X`` (via ``feature_cols``), NOT on
    ``cluster_labels_df``. The cluster_labels parquet legitimately
    carries the customer key (it is the join key for downstream
    segmentation / visualisation / marketing), and ``cluster_labels_df``
    is the authoritative carrier of that key.

    ``feature_cols`` is the list of column names resolved to build
    ``X``. If ``feature_cols`` is provided, the leak check is run
    against it (the canonical case via the prototype pipeline). If
    not provided, the check is skipped (legacy / test convenience).

    The cluster_labels_df schema is positively verified to carry
    ``ClusterLabel`` and ``IsNoise`` (per the DEV-04 contract
    documented in ``src/customer_segmentation/clustering/artifacts.py``
    and consumed by DEV-06/07/08/09).
    """
    checks: list[ValidationCheck] = []
    # CustomerID leak check (R-4 + plan §1.1) — on the FEATURE MATRIX,
    # not on cluster_labels_df. cluster_labels_df legitimately carries
    # the customer key for downstream join.
    if config.validation.exclude_customer_id_from_features and feature_cols is not None:
        leak_cols = [
            c for c in feature_cols
            if c.lower() in {k.lower() for k in CUSTOMER_KEYS_TO_STRIP}
        ]
        if leak_cols:
            checks.append(
                ValidationCheck(
                    check_id="customer_id_leaked_into_features",
                    passed=False,
                    detail=(
                        f"CustomerID-like columns resolved into the feature matrix: "
                        f"{leak_cols}"
                    ),
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    check_id="customer_id_absent_from_features",
                    passed=True,
                )
            )
    # Positive schema check on cluster_labels_df (DEV-04 contract).
    for required_col in ("ClusterLabel", "IsNoise"):
        present = required_col in cluster_labels_df.columns
        checks.append(
            ValidationCheck(
                check_id=f"cluster_labels_has_{required_col}",
                passed=present,
                detail=f"columns={list(cluster_labels_df.columns)}",
            )
        )
    # Customer key presence is optional (positional cluster_labels work too).
    has_customer_key = customer_key in cluster_labels_df.columns
    checks.append(
        ValidationCheck(
            check_id=f"cluster_labels_has_{customer_key}_optional",
            passed=True,  # Optional; never blocks.
            detail=(
                f"present={has_customer_key} (optional, used for downstream join)"
            ),
        )
    )
    # Alignment.
    n_X = X.shape[0]
    n_labels = cluster_labels_df.shape[0]
    if n_X == n_labels:
        checks.append(
            ValidationCheck(check_id="alignment", passed=True)
        )
    else:
        checks.append(
            ValidationCheck(
                check_id="alignment",
                passed=False,
                detail=f"X.shape[0]={n_X} vs cluster_labels rows={n_labels}",
            )
        )
    # NaN / Inf on X.
    finite = bool(np.isfinite(X).all())
    checks.append(
        ValidationCheck(
            check_id="no_nan_or_inf_in_X",
            passed=finite,
            detail="OK" if finite else "X contains NaN or Inf",
        )
    )
    # ClusterLabel dtype.
    label_col = "ClusterLabel" if "ClusterLabel" in cluster_labels_df.columns else None
    if label_col is not None:
        labels = cluster_labels_df[label_col].to_numpy()
        passed = labels.dtype in (np.int32, np.int64)
        checks.append(
            ValidationCheck(
                check_id="cluster_label_dtype",
                passed=passed,
                detail=str(labels.dtype),
            )
        )
    all_passed = all(c.passed for c in checks)
    return EvaluationValidationReport(all_passed=all_passed, checks=checks)


# ---------------------------------------------------------------------------
# File hashes
# ---------------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Feature set SHA (deterministic from sorted feature names)
# ---------------------------------------------------------------------------


def _feature_set_sha256(feature_set: list[str]) -> str:
    joined = "|".join(sorted(feature_set))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Algorithm family detection
# ---------------------------------------------------------------------------


_FAMILY_BY_ALGORITHM: Final[dict[str, str]] = {
    "kmeans": "hard",
    "agglomerative": "hard",
    "dbscan": "density_based",
    "gmm": "model_based",
    "fuzzy_cmeans": "fuzzy",
}


def _infer_algorithm_family(algorithm: str) -> str:
    return _FAMILY_BY_ALGORITHM.get(algorithm, "hard")


def _compute_n_clusters_realized(
    *,
    labels: np.ndarray,
    noise_label: int,
    is_density_based: bool,
    noise_policy: str,
) -> int:
    """Return the number of clusters actually used in the metric context.

    Per plan §5.4.4 and ADR-0006 (DEV-05 prototype-layer uniform
    DBSCAN-noise exclusion):

    - For non-density algorithms: count all unique labels. There is no
      ``-1`` row in the input, so the answer is the same regardless of
      ``noise_policy``.
    - For density_based + ``noise_policy="exclude"``: count unique
      **non-noise** labels. This is the size of the point set
      actually passed to ``compute_internal_metrics`` after the
      in-memory noise filter, so ``n_clusters_realized`` matches the
      data used to compute the metrics. Returns 0 when all rows are
      noise (after the filter, the array is empty — ``np.unique`` on
      an empty array returns the empty array, whose size is 0).
    - For density_based + ``noise_policy="include"``: count unique
      labels INCLUDING ``-1``. The ``-1`` is treated as a regular
      cluster by sklearn's DBI / CH defaults under include; reporting
      it as a cluster makes the manifest consistent with the metric
      context.

    This helper never mutates the input ``labels`` array (in-memory
    filtering only).
    """
    if is_density_based and noise_policy == "exclude":
        non_noise_mask = labels != noise_label
        if not non_noise_mask.any():
            return 0
        return int(np.unique(labels[non_noise_mask]).size)
    return int(np.unique(labels).size)


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    *,
    evaluation_id: str,
    dataset_id: str,
    clustering_id: str,
    clustering_manifest_data: dict[str, Any],
    config: Dev05Config,
    config_text: str,
    metric_set: list[str],
    metrics: EvaluationMetricsResult,
    X: np.ndarray,
    cluster_labels_df: pd.DataFrame,
    noise_count: int | None,
    noise_ratio: float | None,
    n_samples_used_for_compute: int,
    n_clusters_realized: int,
    validation_report: EvaluationValidationReport,
    log_file: str,
) -> EvaluationManifest:
    """Build an EvaluationManifest from clustering data + computed metrics.

    Parameters
    ----------
    dataset_id : str
        DEV-02 dataset id (passed through from the pipeline input; the
        DEV-04 ``clustering_manifest.json`` schema does not carry
        ``dataset_id``, so it must come from the caller's validated
        input — see plan §4.1 / §4.3).
    """
    algorithm = str(clustering_manifest_data.get("algorithm", "unknown"))
    algorithm_family = str(
        clustering_manifest_data.get("algorithm_family")
        or _infer_algorithm_family(algorithm)
    )
    feature_set = list(clustering_manifest_data.get("feature_set", []))
    feature_set_sha = _feature_set_sha256(feature_set)
    preprocessed_id = str(clustering_manifest_data.get("preprocessed_id", ""))
    # dataset_id is supplied by the caller (DEV-04 manifest does not
    # contain it; per plan §4.1 it is not a required field of the
    # clustering_manifest_data). Do NOT re-derive it from
    # clustering_manifest_data — that would yield an empty string for
    # every valid DEV-04 run.
    dataset_id_str = str(dataset_id)
    ml_dataset_sha = str(clustering_manifest_data.get("ml_dataset_sha256", ""))
    preprocessing_config_sha = str(
        clustering_manifest_data.get("preprocessing_config_sha256", "f" * 64)
    )
    hyperparameters = dict(clustering_manifest_data.get("hyperparameters", {}))
    seed_policy = str(clustering_manifest_data.get("seed_policy", "stochastic"))
    seed = clustering_manifest_data.get("seed", None)
    env = EnvironmentBlock(
        python=sys.version.split()[0],
        platform=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        key_libraries=_capture_library_versions(),
    )
    return build_evaluation_manifest(
        evaluation_id=evaluation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id_str,
        ml_dataset_sha256=ml_dataset_sha,
        feature_set_sha256=feature_set_sha,
        preprocessing_config_sha256=preprocessing_config_sha,
        algorithm=algorithm,
        algorithm_version=str(
            clustering_manifest_data.get("algorithm_version", "unknown")
        ),
        algorithm_family=algorithm_family,
        n_samples=int(X.shape[0]),
        n_features=int(X.shape[1]),
        feature_set=feature_set,
        hyperparameters=hyperparameters,
        seed_policy=seed_policy,
        seed=int(seed) if isinstance(seed, int) else None,
        noise_policy_used=config.noise_policy.default,
        metric_set=metric_set,
        metrics=metrics,
        n_samples_input=int(X.shape[0]),
        n_samples_used_for_compute=n_samples_used_for_compute,
        n_clusters_realized=n_clusters_realized,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        config_sha256=compute_config_sha256(config_text),
        environment=env,
        log_file=log_file,
        validation_report=validation_report,
        readonly_paths=list(config.research_safety.readonly_paths),
    )


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------


def _write_metrics_csv(
    metrics: EvaluationMetricsResult,
    csv_path: Path,
    *,
    missing_value: str = "",
) -> None:
    """Write ``metrics_long.csv`` (3 rows + header)."""
    fieldnames = [
        "metric_name",
        "value",
        "status",
        "reason",
        "is_diagnostic_only",
        "lower_is_better",
        "computation_time_seconds",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in metrics.as_flat_rows():
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Staging / publish
# ---------------------------------------------------------------------------


def _prepare_staging(
    run_dir: Path, *, run_uuid: str
) -> Path:
    """Create a staging subdirectory under run_dir."""
    staging = run_dir / f"_staging_{run_uuid}"
    staging.mkdir(parents=True, exist_ok=True)
    return staging


# ---------------------------------------------------------------------------
# Pipeline driver
# ---------------------------------------------------------------------------


def run_evaluation_pipeline(
    *,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    config: Dev05Config | None = None,
    config_path: Path | None = None,
    dev02_config_path: Path | None = None,
    noise_policy: str | None = None,
    metric_set: list[str] | None = None,
    force_recompute: bool = False,
) -> EvaluationPipelineResult:
    """Run the DEV-05 evaluation pipeline end-to-end.

    Parameters
    ----------
    dataset_id, preprocessed_id, clustering_id : str
        Identifiers resolving the DEV-04 clustering run.
    config : Dev05Config, optional
        Pre-loaded config; if None, load from
        :func:`load_dev05_config`.
    config_path : Path, optional
        Explicit config YAML path (overrides default).
    dev02_config_path : Path, optional
        Forwarded to the evaluation storage root resolution so DEV-05
        reads the same storage root that DEV-02/03/04 used. ``None``
        uses the canonical default.
    noise_policy : {"include", "exclude"}, optional
        Override config default for this run.
    metric_set : list[str], optional
        Subset of metric names to compute (default = all 3).
    force_recompute : bool, default False
        If True, ignore cached evaluation and recompute.

    Returns
    -------
    EvaluationPipelineResult
    """
    import time as _time
    import uuid

    start = _time.perf_counter()
    run_uuid = uuid.uuid4().hex

    # Stage A: preflight.
    if config is None:
        config, config_text = load_dev05_config(config_path)
    else:
        # Re-read text for SHA; we need the raw text.
        from customer_segmentation.prototype.evaluation.config_loader import (
            DEFAULT_DEV05_CONFIG_PATH,
        )

        path = config_path or DEFAULT_DEV05_CONFIG_PATH
        config_text = Path(path).read_text(encoding="utf-8")

    effective_noise_policy = noise_policy or config.noise_policy.default
    effective_metric_set = list(metric_set) if metric_set else list(config.metrics.enabled)

    # Validate metric_set.
    unknown = set(effective_metric_set) - METRIC_NAMES
    if unknown:
        raise Dev05PipelineError(
            f"Unknown metric names in metric_set: {sorted(unknown)}; "
            f"allowed: {sorted(METRIC_NAMES)}."
        )

    # Resolve storage root.
    from customer_segmentation.prototype.evaluation.storage import (
        resolve_storage_root,
    )

    storage_root = resolve_storage_root(dev02_config_path)
    base_dir = prototype_evaluation_base_dir(
        storage_root, dataset_id, preprocessed_id, clustering_id
    )
    if not base_dir.parent.exists():
        raise Dev05PipelineError(
            f"Clustering run directory does not exist: {base_dir.parent}. "
            f"DEV-04 must publish before DEV-05 can evaluate."
        )

    # Read upstream clustering manifest.
    clustering_manifest_path = base_dir.parent / "clustering_manifest.json"
    if not clustering_manifest_path.exists():
        raise Dev05PipelineError(
            f"DEV-04 clustering_manifest.json not found at {clustering_manifest_path}."
        )
    try:
        clustering_manifest = read_clustering_manifest(clustering_manifest_path)
    except Exception as exc:
        raise Dev05PipelineError(
            f"Failed to read DEV-04 clustering_manifest.json: {exc}"
        ) from exc
    clustering_manifest_data = json.loads(clustering_manifest_path.read_text(encoding="utf-8"))

    # Look up the experiment_log to confirm status.
    experiment_log_path = (
        base_dir.parent / clustering_manifest_data.get("experiment_log_path", "")
    )

    # Stage B: read cluster_labels and DEV-03 ML Dataset.
    cluster_labels_path = base_dir.parent / clustering_manifest_data.get(
        "cluster_labels_path", ""
    )
    if not cluster_labels_path.exists():
        raise Dev05PipelineError(
            f"cluster_labels parquet not found: {cluster_labels_path}."
        )
    cluster_labels_df = pd.read_parquet(cluster_labels_path)

    # Find DEV-03 ML Dataset via preprocessed_id dir.
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); ``dataset_id`` is
    # appended directly (no extra ``"datasets"`` literal). Post-A-1:
    # DEV-03 writes artefacts FLAT under
    # ``<storage_root>/<dataset_id>/preprocessed/`` (no
    # ``<preprocessed_id>`` subdirectory). See
    # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    pp_dir = storage_root / dataset_id / "preprocessed"
    pp_manifest_path = pp_dir / "preprocessed_manifest.json"
    if not pp_manifest_path.exists():
        raise Dev05PipelineError(
            f"DEV-03 preprocessed_manifest.json not found at {pp_manifest_path}."
        )
    pp_manifest_data = json.loads(pp_manifest_path.read_text(encoding="utf-8"))
    ml_dataset_block = pp_manifest_data.get("ml_dataset_block", {})
    ml_dataset_name = ml_dataset_block.get("artifact_path", "")
    if not ml_dataset_name:
        raise Dev05PipelineError(
            "DEV-03 preprocessed_manifest.json has no ml_dataset_block.artifact_path."
        )
    ml_dataset_path = pp_dir / ml_dataset_name
    if not ml_dataset_path.exists():
        raise Dev05PipelineError(
            f"DEV-03 ML Dataset parquet not found: {ml_dataset_path}."
        )
    ml_dataset_df = pd.read_parquet(ml_dataset_path)
    feature_set = list(clustering_manifest_data.get("feature_set", []))
    if not feature_set:
        # Fallback: drop CustomerID.
        candidate_cols = [
            c for c in ml_dataset_df.columns
            if c.lower() not in {k.lower() for k in CUSTOMER_KEYS_TO_STRIP}
        ]
        feature_set = candidate_cols
    # X: subset to feature_set, drop CustomerID columns.
    feature_cols = [
        c for c in feature_set
        if c in ml_dataset_df.columns
        and c.lower() not in {k.lower() for k in CUSTOMER_KEYS_TO_STRIP}
    ]
    if not feature_cols:
        raise Dev05PipelineError(
            f"Could not resolve any feature columns from feature_set {feature_set}."
        )
    X = ml_dataset_df[feature_cols].to_numpy(dtype=np.float64, copy=True)

    # Set up logging.
    log_file = f"{run_uuid}.log"
    logger = configure_logging(
        level=config.logging.level,
        fmt=config.logging.format,
        log_file=None,  # Per-stage log file in final dir (set after publish).
        emit_to_console=config.logging.emit_to_console,
    )
    psl = PerStageLogger(logger, stage="A")

    # Stage C: validation.
    psl.stage_start("C")
    validation_report = _validate_inputs(
        X, cluster_labels_df, config=config, feature_cols=feature_cols
    )
    if not validation_report.all_passed:
        psl.error(f"Validation failed: {validation_report.to_dict()}")
        psl.stage_end("FAIL")
        finalize_logging(logger)
        raise Dev05PipelineError(
            f"Input validation failed: "
            f"{[c.check_id for c in validation_report.checks if not c.passed]}"
        )
    psl.stage_end("PASS")

    # Compute labels.
    labels = cluster_labels_df["ClusterLabel"].to_numpy() if "ClusterLabel" in cluster_labels_df.columns else None
    if labels is None:
        raise Dev05PipelineError(
            "cluster_labels parquet has no ClusterLabel column."
        )
    n_samples_input = int(X.shape[0])
    noise_count: int | None = None
    noise_ratio: float | None = None
    is_density_based = (
        clustering_manifest_data.get("algorithm_family") == "density_based"
        or clustering_manifest_data.get("algorithm", "") == "dbscan"
    )
    if is_density_based:
        noise_mask = labels == DBSCAN_NOISE_LABEL
        noise_count = int(noise_mask.sum())
        noise_ratio = float(noise_count) / float(n_samples_input) if n_samples_input else None

    # n_clusters_realized semantics (plan §5.4.4, ADR-0006):
    #   - For non-density algorithms: count all unique labels (no -1 possible).
    #   - For density_based + noise_policy="exclude": count unique NON-NOISE
    #     labels (this is the point set actually used to compute the
    #     metrics; matches `compute_internal_metrics` internal filter).
    #   - For density_based + noise_policy="include": count unique labels
    #     INCLUDING -1 (sklearn default — -1 is treated as a regular
    #     cluster for DBI/CH under include).
    # This MUST be computed after the noise-filter decision so that
    # `n_clusters_realized` matches the metric compute context; otherwise
    # the comparison table may surface a `n_clusters_realized` value
    # that does not correspond to the data used for the metric value.
    n_clusters_realized = _compute_n_clusters_realized(
        labels=labels,
        noise_label=DBSCAN_NOISE_LABEL,
        is_density_based=is_density_based,
        noise_policy=effective_noise_policy,
    )

    # Stage D: compute metrics.
    psl.stage_start("D")
    algorithm_family = _infer_algorithm_family(
        str(clustering_manifest_data.get("algorithm", ""))
    )
    result = compute_internal_metrics(
        X,
        labels,
        algorithm_family=algorithm_family,
        noise_policy=effective_noise_policy,
        noise_label=DBSCAN_NOISE_LABEL,
        metric_set=frozenset(effective_metric_set),
    )
    psl.stage_end("PASS")

    # Compute n_samples_used_for_compute.
    if algorithm_family == "density_based" and effective_noise_policy == "exclude" \
            and noise_count is not None and noise_count > 0:
        n_samples_used_for_compute = n_samples_input - noise_count
    else:
        n_samples_used_for_compute = n_samples_input

    # Derive evaluation_id.
    metric_set_hash = compute_metric_set_hash(frozenset(effective_metric_set))
    evaluation_id = derive_evaluation_id(
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=clustering_manifest_data.get("ml_dataset_sha256", ""),
        config_sha256=compute_config_sha256(config_text),
        noise_policy=effective_noise_policy,
        metric_set=frozenset(effective_metric_set),
    )

    # Check for cached evaluation.
    canonical_expected = {
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "ml_dataset_sha256": clustering_manifest_data.get("ml_dataset_sha256", ""),
        "config_sha256": compute_config_sha256(config_text),
        "noise_policy": effective_noise_policy,
        "metric_set_hash": metric_set_hash,
        "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
    }
    found, manifest_path_existing = find_existing_evaluation(
        base_dir=base_dir,
        evaluation_id=evaluation_id,
        expected_canonical=canonical_expected,
    )
    if found and not force_recompute:
        existing = read_evaluation_manifest(manifest_path_existing)
        return EvaluationPipelineResult(
            evaluation_id=evaluation_id,
            manifest_path=manifest_path_existing,
            csv_path=base_dir / evaluation_id / "metrics_long.csv",
            lifecycle=LIFECYCLE_CACHED,
            manifest=existing,
            duration_seconds=_time.perf_counter() - start,
        )

    # Stage E: build + atomic write manifest in staging.
    psl.stage_start("E")
    run_dir = base_dir / evaluation_id
    staging = _prepare_staging(base_dir, run_uuid=run_uuid)
    manifest = _make_manifest(
        evaluation_id=evaluation_id,
        dataset_id=dataset_id,
        clustering_id=clustering_id,
        clustering_manifest_data=clustering_manifest_data,
        config=config,
        config_text=config_text,
        metric_set=effective_metric_set,
        metrics=result,
        X=X,
        cluster_labels_df=cluster_labels_df,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        n_samples_used_for_compute=n_samples_used_for_compute,
        n_clusters_realized=n_clusters_realized,
        validation_report=validation_report,
        log_file=log_file,
    )
    staging_manifest_path = staging / "evaluation_manifest.json"
    write_evaluation_manifest(manifest, staging_manifest_path)

    csv_path = None
    if config.storage.emit_metrics_csv:
        csv_path = staging / "metrics_long.csv"
        _write_metrics_csv(
            result,
            csv_path,
            missing_value=config.display.csv_missing_value,
        )
    psl.stage_end("PASS")

    # Stage F: publish (staging → final).
    psl.stage_start("F")
    run_dir_final = base_dir / evaluation_id
    if run_dir_final.exists():
        # Force-rerun case: backup the old run.
        backup = base_dir / f"_backup_{run_uuid}"
        shutil.move(str(run_dir_final), str(backup))
    try:
        os.rename(str(staging), str(run_dir_final))
    except Exception as exc:
        psl.error(f"Publish failed: {exc}")
        # Try to restore backup.
        backup = base_dir / f"_backup_{run_uuid}"
        if backup.exists():
            shutil.move(str(backup), str(run_dir_final))
        raise
    psl.stage_end("PASS")

    # Stage G: finalize log.
    psl.stage_start("G")
    finalize_logging(logger)
    psl.stage_end("PASS")

    final_manifest_path = run_dir_final / "evaluation_manifest.json"
    final_csv_path = (
        run_dir_final / "metrics_long.csv"
        if config.storage.emit_metrics_csv
        else None
    )

    return EvaluationPipelineResult(
        evaluation_id=evaluation_id,
        manifest_path=final_manifest_path,
        csv_path=final_csv_path,
        lifecycle=LIFECYCLE_SUCCESS,
        manifest=manifest,
        duration_seconds=_time.perf_counter() - start,
    )
