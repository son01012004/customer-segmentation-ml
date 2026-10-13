"""End-to-end segmentation pipeline for DEV-06 Prototype Segmentation.

Stage A → H driver (mirror DEV-05 Stage A → G pattern):

- **A (preflight)** — load DEV-06 config; resolve dataset /
  preprocessed / clustering ids; read DEV-04 ``clustering_manifest.json``.
- **B (lookup)** — read DEV-04 ``cluster_labels_*.parquet`` and DEV-03
  ML Dataset parquet; resolve DEV-05 evaluation manifest path if
  provided.
- **C (validation)** — alignment between cluster labels and ML
  Dataset; NaN/Inf checks; CustomerID leak; ClusterLabel dtype; per-row
  IsNoise consistency. Build :class:`SegmentationValidationReport`.
- **D (profile compute)** — per-segment feature profile statistics
  (numerical stats + categorical top-K).
- **E (characteristics compute)** — per-segment characteristics
  derivation from profile stats (4-rule engine, per OQ-SEG-CHAR-01).
- **F (manifest write)** — atomic write ``segmentation_manifest.json``
  in staging + emit CSVs / JSONs.
- **G (publish)** — atomic ``os.rename(staging → final)``.
- **H (finalize)** — flush + close log handlers.

Output
------
Per segmentation pass: writes
``<storage_root>/datasets/<ds>/preprocessed/<pp>/clustering/<cl>/
segmentation/<seg_id>/segmentation_manifest.json`` + per-segment CSVs/JSONs.

Side-effect discipline (R-DEV-06-04..07, R-DEV-06-09, R-DEV-06-10..12):
- The pipeline NEVER mutates ``cluster_labels_*.parquet``,
  ``ml_dataset_*.parquet``, ``clustering_manifest.json``,
  ``preprocessed_manifest.json``, or any research artefact. Reads only.
- The pipeline only writes into the
  ``segmentation/<seg_id>/`` subtree.
- All compute calls are wrapped in ``try/except``; on hard failure,
  no manifest is published and a fail-closed error is raised.
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
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from customer_segmentation.prototype.segmentation.characteristics import (
    derive_segment_characteristics,
)
from customer_segmentation.prototype.segmentation.config_loader import (
    Dev06Config,
    load_dev06_config,
)
from customer_segmentation.prototype.segmentation.logging_config import (
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.segmentation.manifest import (
    SEGMENTATION_MANIFEST_SCHEMA_VERSION,
    CharacteristicEntry,
    FeatureProfile,
    SegmentationManifest,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
    write_segmentation_manifest,
)
from customer_segmentation.prototype.segmentation.profile import (
    compute_feature_profiles,
    compute_segment_sizes,
    format_profiles_csv_rows,
)
from customer_segmentation.prototype.segmentation.scope import (
    PROFILING_STATISTICS_SET,
    SegmentationStage,
)
from customer_segmentation.prototype.segmentation.storage import (
    compute_config_sha256,
    compute_feature_set_sha256,
    derive_segmentation_id,
    find_existing_segmentation,
    prototype_segmentation_base_dir,
    prototype_segmentation_run_dir,
    resolve_storage_root,
)
from customer_segmentation.prototype.segmentation.validation import (
    DBSCAN_NOISE_LABEL,
    validate_inputs,
)

__all__ = [
    "SegmentationPipelineResult",
    "run_segmentation_pipeline",
    "compute_dataset_stats",
]


LIFECYCLE_SUCCESS: Final[str] = "SUCCESS"
LIFECYCLE_FAILED: Final[str] = "FAILED"
LIFECYCLE_CACHED: Final[str] = "CACHED"


# Mandatory post-preprocessing warning emitted on disk (R-DEV-06-23).
# This is the canonical text per plan §14.2.4. It is written into:
#   - ``segmentation_manifest.json`` (``preprocessing_warning`` field)
#   - the first-line of every CSV file (as a ``# preprocessing_warning: ...``
#     comment; see R-DEV-06-23 / plan §14.2.4 "MANDATORY in every output
#     file's first-line comment").
POST_PREPROCESSING_WARNING: Final[str] = (
    "Feature profile uses scaled/transformed values; not directly "
    "interpretable in original business units (per DEV-03 preprocessing)."
)


@dataclass(frozen=True)
class SegmentationPipelineResult:
    """Outcome of one segmentation pass."""

    segmentation_id: str
    manifest_path: Path
    lifecycle: str  # "SUCCESS" | "FAILED" | "CACHED"
    manifest: SegmentationManifest
    duration_seconds: float = 0.0


class Dev06PipelineError(RuntimeError):
    """Raised when the pipeline cannot proceed (fail-closed)."""


# ---------------------------------------------------------------------------
# Library versions
# ---------------------------------------------------------------------------


def _capture_library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    with contextlib.suppress(Exception):
        versions["numpy"] = np.__version__
    with contextlib.suppress(Exception):
        versions["pandas"] = pd.__version__
    with contextlib.suppress(Exception):
        import sklearn  # type: ignore[import-untyped]

        versions["scikit-learn"] = sklearn.__version__
    return versions


# ---------------------------------------------------------------------------
# Dataset stats for characteristic rules
# ---------------------------------------------------------------------------


def compute_dataset_stats(
    ml_dataset_df: pd.DataFrame, feature_set: list[str]
) -> dict[str, dict[str, float]]:
    """Compute dataset-wide statistics (mean / median / std) per feature.

    Returned as ``{feature_name: {"mean": ..., "median": ..., "std": ...}}``.
    Numeric features only. Categorical features are omitted (the
    characteristic engine does not consume them).
    """
    out: dict[str, dict[str, float]] = {}
    for f in feature_set:
        if f not in ml_dataset_df.columns:
            continue
        s = ml_dataset_df[f]
        if not pd.api.types.is_numeric_dtype(s):
            continue
        s_clean = s.dropna()
        if len(s_clean) == 0:
            continue
        out[f] = {
            "mean": float(s_clean.mean()),
            "median": float(s_clean.quantile(0.5)),
            "std": float(s_clean.std()),
        }
    return out


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _build_segment_sizes(
    *,
    sizes: dict[int, int],
    n_samples_input: int,
    n_samples_used_for_compute: int,
    decimals: int,
) -> list[SegmentSize]:
    """Build the per-segment ``SegmentSize`` records.

    Per OQ-SEG-DENOM-01:
    - Primary percentage = count / n_samples_input * 100 (rounded).
    - Noise segment (``-1``) only appears in long CSV with
      ``is_noise=True``. Under ``n_samples_used_for_compute`` base,
      noise percentage = 0.0 (denominator excludes noise).

    Per OQ-SEG-NOISE-01: the noise label ``-1`` is preserved verbatim
    in the segment_sizes records (R-DEV-06-22 enforcement at manifest
    build time).
    """
    out: list[SegmentSize] = []
    for seg_id, count in sizes.items():
        is_noise = seg_id == DBSCAN_NOISE_LABEL
        # Primary percentage = n_samples_input base.
        pct = round(count / n_samples_input * 100.0, decimals) if n_samples_input > 0 else 0.0
        # Determine percentage_base: for noise segment, base is
        # n_samples_input; for non-noise, also n_samples_input (the
        # primary). The secondary base is reflected in
        # ``n_samples_used_for_compute`` and is emitted in the
        # long-format CSV column, not in the SegmentSize record.
        base = "n_samples_input"
        out.append(
            SegmentSize(
                segment_id=seg_id,
                count=count,
                percentage=pct,
                percentage_base=base,
                is_noise=is_noise,
            )
        )
    return out


def _write_sizes_long_csv(
    segment_sizes: list[SegmentSize],
    *,
    n_samples_input: int,
    n_samples_used_for_compute: int,
    decimals: int,
    csv_path: Path,
    missing_value: str = "",
) -> None:
    """Write ``segment_sizes_long.csv`` (id, count, percentages, is_noise).

    Per R-DEV-06-23 / plan §14.2.4: the first line of every CSV
    output file is a ``# preprocessing_warning: ...`` comment so the
    disclaimer is preserved independent of Python warnings emitted at
    compute time.
    """
    fieldnames = [
        "segment_id",
        "count",
        "percentage_input",
        "percentage_of_non_noise",
        "is_noise",
        "percentage_rounding_decimals",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(f"# preprocessing_warning: {POST_PREPROCESSING_WARNING}\n")
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for s in segment_sizes:
            if s.is_noise:
                # Noise: percentage_of_non_noise = 0 (denominator excludes).
                pct_nn_str = missing_value
            else:
                if n_samples_used_for_compute > 0:
                    pct_nn = round(s.count / n_samples_used_for_compute * 100.0, decimals)
                    pct_nn_str = f"{pct_nn:.{decimals}f}"
                else:
                    pct_nn_str = missing_value
            writer.writerow(
                {
                    "segment_id": s.segment_id,
                    "count": s.count,
                    "percentage_input": f"{s.percentage:.{decimals}f}",
                    "percentage_of_non_noise": pct_nn_str,
                    "is_noise": s.is_noise,
                    "percentage_rounding_decimals": decimals,
                }
            )


def _write_sizes_csv(
    segment_sizes: list[SegmentSize],
    csv_path: Path,
) -> None:
    """Write ``segment_sizes.csv`` (non-noise segments only, AC-2).

    Per R-DEV-06-23 / plan §14.2.4: first-line comment carries the
    mandatory post-preprocessing warning.
    """
    fieldnames = ["segment_id", "count", "is_noise"]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(f"# preprocessing_warning: {POST_PREPROCESSING_WARNING}\n")
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for s in segment_sizes:
            if s.is_noise:
                continue
            writer.writerow(
                {
                    "segment_id": s.segment_id,
                    "count": s.count,
                    "is_noise": s.is_noise,
                }
            )


def _write_profiles_csv(
    profiles: list[FeatureProfile],
    csv_path: Path,
) -> None:
    """Write ``segment_profiles.csv`` (long-format).

    Per R-DEV-06-23 / plan §14.2.4: first-line comment carries the
    mandatory post-preprocessing warning.
    """
    rows = format_profiles_csv_rows(profiles)
    fieldnames = [
        "segment_id",
        "feature_name",
        "statistic",
        "value",
        "value_str",
        "is_diagnostic_only",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(f"# preprocessing_warning: {POST_PREPROCESSING_WARNING}\n")
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _write_profiles_json(
    profiles: list[FeatureProfile],
    json_path: Path,
) -> None:
    """Write ``segment_profiles.json`` (nested)."""
    nested: dict[str, dict[str, dict[str, Any]]] = {}
    for p in profiles:
        seg_dict = nested.setdefault(str(p.segment_id), {})
        feat_dict = seg_dict.setdefault(p.feature_name, {})
        for k, v in p.statistics.items():
            feat_dict[k] = v
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(nested, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        fh.write("\n")


def _write_characteristics_json(
    characteristics: list[CharacteristicEntry],
    json_path: Path,
) -> None:
    """Write ``segment_characteristics.json`` (nested per segment_id).

    Per plan §4.2, the on-disk schema is a nested dict keyed by
    ``segment_id`` (as string), each value being a dict keyed by
    ``characteristic_id``:

    .. code-block:: json

        {
          "0": {
            "mean_high_Recency": {
              "characteristic_id": "mean_high_Recency",
              "description": "...",
              "source_features": ["Recency"],
              "derived_stats": {...},
              "is_invariant": false
            }
          }
        }

    Noise segments (``segment_id == -1``) are EXCLUDED from the output
    (plan §5: characteristics do not compute for noise).

    ``is_invariant=False`` is the fixed invariant per OQ-SEG-CHAR-01
    (descriptive characteristics are never business claims).

    Segments with no characteristics are OMITTED from the output
    (no empty ``{}`` placeholders).
    """
    nested: dict[str, dict[str, dict[str, Any]]] = {}
    for c in characteristics:
        # Skip noise: characteristics do not apply to noise segments
        # (OQ-SEG-NOISE-01, plan §5).
        if c.segment_id == -1:
            continue
        seg_key = str(c.segment_id)
        seg_dict = nested.setdefault(seg_key, {})
        seg_dict[c.characteristic_id] = {
            "characteristic_id": c.characteristic_id,
            "description": c.description,
            "source_features": list(c.source_features),
            "derived_stats": dict(c.derived_stats),
            "is_invariant": False,
        }
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump(nested, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def _prepare_staging(run_dir: Path, *, run_uuid: str) -> Path:
    """Create a staging subdirectory under run_dir."""
    staging = run_dir / f"_staging_{run_uuid}"
    staging.mkdir(parents=True, exist_ok=True)
    return staging


# ---------------------------------------------------------------------------
# Top-level pipeline driver
# ---------------------------------------------------------------------------


def run_segmentation_pipeline(
    *,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
    config: Dev06Config | None = None,
    config_path: Path | None = None,
    dev02_config_path: Path | None = None,
    noise_policy: str | None = None,
    evaluation_manifest_path: Path | None = None,
    force_rerun: bool = False,
) -> SegmentationPipelineResult:
    """Run the DEV-06 segmentation pipeline end-to-end.

    Parameters
    ----------
    dataset_id, preprocessed_id, clustering_id : str
        Identifiers resolving the DEV-04 clustering run.
    config : Dev06Config, optional
        Pre-loaded config; if None, load from
        :func:`load_dev06_config`.
    config_path : Path, optional
        Explicit config YAML path (overrides default).
    dev02_config_path : Path, optional
        Forwarded to the segmentation storage root resolution so
        DEV-06 reads the same storage root that DEV-02/03/04 used.
        ``None`` uses the canonical default.
    noise_policy : {"include", "exclude"}, optional
        Override config default for this run.
    evaluation_manifest_path : Path, optional
        Optional DEV-05 ``evaluation_manifest.json`` for cross-check.
    force_rerun : bool, default False
        If True, ignore cached segmentation and recompute.
    """
    start = time.perf_counter()
    run_uuid = uuid.uuid4().hex

    # Stage A: preflight.
    if config is None:
        config, config_text = load_dev06_config(config_path)
    else:
        from customer_segmentation.prototype.segmentation.config_loader import (
            DEFAULT_DEV06_CONFIG_PATH,
        )

        path = config_path or DEFAULT_DEV06_CONFIG_PATH
        config_text = Path(path).read_text(encoding="utf-8")

    effective_noise_policy = noise_policy or config.noise_policy.default
    if effective_noise_policy not in ("include", "exclude", "n/a"):
        raise Dev06PipelineError(
            f"Invalid noise_policy {effective_noise_policy!r}; " f"allowed: include, exclude, n/a."
        )

    # Resolve storage root.
    storage_root = resolve_storage_root(dev02_config_path)
    base_dir = prototype_segmentation_base_dir(
        storage_root, dataset_id, preprocessed_id, clustering_id
    )
    if not base_dir.parent.exists():
        raise Dev06PipelineError(
            f"Clustering run directory does not exist: {base_dir.parent}. "
            f"DEV-04 must publish before DEV-06 can segment."
        )

    # Read upstream clustering manifest.
    clustering_manifest_path = base_dir.parent / "clustering_manifest.json"
    if not clustering_manifest_path.exists():
        raise Dev06PipelineError(
            f"DEV-04 clustering_manifest.json not found at {clustering_manifest_path}."
        )
    clustering_manifest_data = json.loads(clustering_manifest_path.read_text(encoding="utf-8"))

    # Stage B: read cluster_labels + ML dataset + preprocessed manifest.
    cluster_labels_relpath = clustering_manifest_data.get("cluster_labels_path", "")
    cluster_labels_path = (
        base_dir.parent / cluster_labels_relpath if cluster_labels_relpath else None
    )
    if cluster_labels_path is None or not cluster_labels_path.exists():
        raise Dev06PipelineError(
            f"DEV-04 cluster_labels parquet not found at {cluster_labels_path}."
        )
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
        raise Dev06PipelineError(
            f"DEV-03 preprocessed_manifest.json not found at {pp_manifest_path}."
        )
    pp_manifest_data = json.loads(pp_manifest_path.read_text(encoding="utf-8"))
    ml_dataset_block = pp_manifest_data.get("ml_dataset_block", {})
    ml_dataset_name = ml_dataset_block.get("artifact_path", "")
    if not ml_dataset_name:
        raise Dev06PipelineError(
            "DEV-03 preprocessed_manifest.json has no ml_dataset_block.artifact_path."
        )
    ml_dataset_path = pp_dir / ml_dataset_name
    if not ml_dataset_path.exists():
        raise Dev06PipelineError(f"DEV-03 ML Dataset parquet not found: {ml_dataset_path}.")

    # Set up logging.
    log_file = f"{run_uuid}.log"
    logger = configure_logging(
        level=config.logging.level,
        fmt=config.logging.format,
        log_file=None,
        emit_to_console=config.logging.emit_to_console,
    )
    psl = PerStageLogger(logger, stage=SegmentationStage.A.value)

    # Stage C: validation.
    psl.stage_start(SegmentationStage.C.value)
    validation_report = validate_inputs(
        clustering_manifest_path=clustering_manifest_path,
        cluster_labels_path=cluster_labels_path,
        ml_dataset_path=ml_dataset_path,
        preprocessed_manifest_path=pp_manifest_path,
        config=config,
        evaluation_manifest_path=evaluation_manifest_path,
    )
    if not validation_report.all_passed:
        psl.error(f"Validation failed: {validation_report.to_dict()}")
        psl.stage_end("FAIL")
        finalize_logging(logger)
        raise Dev06PipelineError(
            f"Input validation failed: "
            f"{[c.check_id for c in validation_report.checks if not c.passed]}"
        )
    psl.stage_end("PASS")

    # Read DataFrames (validation already confirmed they parse).
    cluster_labels_df = pd.read_parquet(cluster_labels_path)
    ml_dataset_df = pd.read_parquet(ml_dataset_path)

    # Resolve feature set.
    feature_set = list(clustering_manifest_data.get("feature_set", []))
    if not feature_set:
        candidate_cols = [
            c
            for c in ml_dataset_df.columns
            if c not in ("CustomerID", "customer_id", "Customer Id", "Customer_Id", "customerId")
        ]
        feature_set = candidate_cols
    # Re-strip CustomerID candidates (defence-in-depth).
    feature_set = [
        f
        for f in feature_set
        if f not in ("CustomerID", "customer_id", "Customer Id", "Customer_Id", "customerId")
    ]
    if not feature_set:
        raise Dev06PipelineError("Could not resolve any feature columns from feature_set.")

    # Derive segmentation_id and check idempotency.
    ml_dataset_sha = str(clustering_manifest_data.get("ml_dataset_sha256", ""))
    if not ml_dataset_sha:
        raise Dev06PipelineError("DEV-04 clustering_manifest.json has empty ml_dataset_sha256.")
    feature_set_sha = compute_feature_set_sha256(feature_set)
    pp_config_hash = str(pp_manifest_data.get("config_hash", ""))
    if not pp_config_hash:
        raise Dev06PipelineError("DEV-03 preprocessed_manifest.json has empty config_hash.")
    # Extract preprocessing_block transformation/scaling to compute
    # the mandatory post-preprocessing warning (R-DEV-06-23 /
    # plan §14.2.4). Defensive defaults if the block is missing.
    pp_block = pp_manifest_data.get("preprocessing_block", {}) or {}
    transformation = str(pp_block.get("transformation", "unknown"))
    scaling = str(pp_block.get("scaling", "unknown"))
    preprocessing_applied = {"transformation": transformation, "scaling": scaling}
    # Defer segmentation_id derivation to after Stage D (we need
    # is_density_based to compute the canonical noise_policy).
    canonical_noise_policy = "n/a"  # placeholder; reassigned in Stage D
    segmentation_id = ""
    canonical_expected: dict[str, Any] = {}
    found = False
    manifest_path_existing: Path | None = None
    # Stage D: profile compute.
    psl.stage_start(SegmentationStage.D.value)
    sizes = compute_segment_sizes(cluster_labels_df)
    algorithm_family = str(clustering_manifest_data.get("algorithm_family", "other"))
    algorithm = str(clustering_manifest_data.get("algorithm", "unknown"))
    algorithm_version = str(clustering_manifest_data.get("algorithm_version", "unknown"))
    is_density_based = algorithm_family == "density_based"
    n_samples_input = int(len(cluster_labels_df))
    noise_count: int | None = None
    noise_ratio: float | None = None
    if is_density_based:
        noise_count = int((cluster_labels_df["ClusterLabel"] == DBSCAN_NOISE_LABEL).sum())
        noise_ratio = float(noise_count) / float(n_samples_input) if n_samples_input > 0 else None
    if is_density_based and effective_noise_policy == "exclude":
        n_samples_used_for_compute = n_samples_input - (noise_count or 0)
    else:
        n_samples_used_for_compute = n_samples_input
    # Build per-segment SegmentSize records.
    segment_sizes = _build_segment_sizes(
        sizes=sizes,
        n_samples_input=n_samples_input,
        n_samples_used_for_compute=n_samples_used_for_compute,
        decimals=config.display.percentage_decimals,
    )
    n_segments = sum(1 for s in segment_sizes if not s.is_noise)
    n_clusters_input = int(clustering_manifest_data.get("n_clusters", 0)) or len(sizes)
    # Per-feature profiles.
    exclude_noise_for_profile = is_density_based and effective_noise_policy == "exclude"
    profiles: list[FeatureProfile] = compute_feature_profiles(
        ml_dataset=ml_dataset_df,
        cluster_labels=cluster_labels_df,
        feature_set=feature_set,
        statistics=list(config.statistics.numerical),
        categorical_topk=config.statistics.categorical_topk,
        uniqueness_threshold=config.statistics.categorical_uniqueness_threshold,
        exclude_noise=exclude_noise_for_profile,
    )
    psl.stage_end("PASS")

    # Derive segmentation_id now that we know is_density_based.
    # The canonical noise_policy must match the manifest's
    # noise_policy_used exactly: for non-density algorithms, the
    # manifest uses "n/a", so the canonical hash must also use "n/a"
    # (otherwise the cached lookup would falsely report a collision).
    canonical_noise_policy = effective_noise_policy if is_density_based else "n/a"
    segmentation_id = derive_segmentation_id(
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha,
        feature_set_sha256=feature_set_sha,
        preprocessing_config_sha256=pp_config_hash,
        noise_policy=canonical_noise_policy,
    )
    canonical_expected = {
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "ml_dataset_sha256": ml_dataset_sha,
        "feature_set_sha256": feature_set_sha,
        "preprocessing_config_sha256": pp_config_hash,
        "noise_policy": canonical_noise_policy,
        "schema_version": SEGMENTATION_MANIFEST_SCHEMA_VERSION,
    }
    found, manifest_path_existing = find_existing_segmentation(
        base_dir=base_dir,
        segmentation_id=segmentation_id,
        expected_canonical=canonical_expected,
    )
    if found and not force_rerun:
        from customer_segmentation.prototype.segmentation.manifest import (
            read_segmentation_manifest,
        )

        existing = read_segmentation_manifest(manifest_path_existing)
        finalize_logging(logger)
        return SegmentationPipelineResult(
            segmentation_id=segmentation_id,
            manifest_path=manifest_path_existing,
            lifecycle=LIFECYCLE_CACHED,
            manifest=existing,
            duration_seconds=time.perf_counter() - start,
        )

    # Stage E: characteristics compute.
    psl.stage_start(SegmentationStage.E.value)
    dataset_stats = compute_dataset_stats(ml_dataset_df, feature_set)
    # Filter characteristic rules to enabled ones.
    enabled_rules = set(config.characteristic_rules.enabled)
    characteristics: list[CharacteristicEntry] = []
    all_chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
        z_threshold=config.characteristic_rules.z_threshold,
    )
    for c in all_chars:
        # Determine the rule template (without feature name) for filtering.
        template = c.characteristic_id
        for k in (
            "mean_high_",
            "mean_low_",
            "median_above_dataset_median_",
            "top_category_",
        ):
            if template.startswith(k):
                tpl = (
                    k + "<feature>"
                    if not template.startswith("top_category_")
                    else k + "<feature>_<value>"
                )
                if tpl in enabled_rules:
                    characteristics.append(c)
                break
    psl.stage_end("PASS")

    # Stage F: manifest write + CSV/JSON output in staging.
    psl.stage_start(SegmentationStage.F.value)
    run_dir = base_dir / segmentation_id
    staging = _prepare_staging(base_dir, run_uuid=run_uuid)
    environment = {
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "key_libraries": _capture_library_versions(),
    }
    # evaluation_id resolution: only if L5 present and validation passed.
    evaluation_id: str | None = None
    if evaluation_manifest_path is not None:
        try:
            ev_data = json.loads(evaluation_manifest_path.read_text(encoding="utf-8"))
            evaluation_id = ev_data.get("evaluation_id")
        except Exception:  # noqa: BLE001
            evaluation_id = None

    # Compute relative paths for input_* fields in manifest (for human
    # readers; absolute paths are not stored).
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(storage_root))
        except ValueError:
            return str(path)

    manifest = build_segmentation_manifest(
        segmentation_id=segmentation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        evaluation_id=evaluation_id,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
        algorithm_family=algorithm_family,
        ml_dataset_sha256=ml_dataset_sha,
        feature_set_sha256=feature_set_sha,
        preprocessing_config_sha256=pp_config_hash,
        feature_set=feature_set,
        n_samples_input=n_samples_input,
        n_samples_used_for_compute=n_samples_used_for_compute,
        n_clusters_input=n_clusters_input,
        n_segments=n_segments,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        noise_policy_used=(effective_noise_policy if is_density_based else "n/a"),
        segment_sizes=segment_sizes,
        profiles=profiles,
        characteristics=characteristics,
        config_sha256=compute_config_sha256(config_text),
        environment=environment,
        log_file=log_file,
        validation_report=validation_report,
        readonly_paths=list(config.research_safety.readonly_paths),
        input_clustering_manifest=_rel(clustering_manifest_path),
        input_cluster_labels=_rel(cluster_labels_path),
        input_ml_dataset=_rel(ml_dataset_path),
        input_evaluation_manifest=(
            _rel(evaluation_manifest_path) if evaluation_manifest_path else None
        ),
        preprocessing_applied=preprocessing_applied,
        preprocessing_warning=POST_PREPROCESSING_WARNING,
    )
    staging_manifest_path = staging / "segmentation_manifest.json"
    write_segmentation_manifest(manifest, staging_manifest_path)

    # Emit CSVs/JSONs.
    if config.storage.emit_sizes_long_csv:
        sizes_long_csv_path = staging / "segment_sizes_long.csv"
        _write_sizes_long_csv(
            segment_sizes,
            n_samples_input=n_samples_input,
            n_samples_used_for_compute=n_samples_used_for_compute,
            decimals=config.display.percentage_decimals,
            csv_path=sizes_long_csv_path,
            missing_value=config.display.csv_missing_value,
        )
    # segment_sizes.csv (non-noise only).
    sizes_csv_path = staging / "segment_sizes.csv"
    _write_sizes_csv(segment_sizes, sizes_csv_path)
    if config.storage.emit_profiles_csv:
        profiles_csv_path = staging / "segment_profiles.csv"
        _write_profiles_csv(profiles, profiles_csv_path)
    if config.storage.emit_profiles_json:
        profiles_json_path = staging / "segment_profiles.json"
        _write_profiles_json(profiles, profiles_json_path)
    if config.storage.emit_characteristics_json:
        chars_json_path = staging / "segment_characteristics.json"
        _write_characteristics_json(characteristics, chars_json_path)
    psl.stage_end("PASS")

    # Stage G: publish (staging → final).
    psl.stage_start(SegmentationStage.G.value)
    run_dir_final = base_dir / segmentation_id
    if run_dir_final.exists():
        # Force-rerun case: backup the old run.
        backup = base_dir / f"_backup_{run_uuid}"
        with contextlib.suppress(OSError):
            shutil.move(str(run_dir_final), str(backup))
    try:
        os.rename(str(staging), str(run_dir_final))
    except Exception as exc:
        psl.error(f"Publish failed: {exc}")
        backup = base_dir / f"_backup_{run_uuid}"
        if backup.exists():
            with contextlib.suppress(OSError):
                shutil.move(str(backup), str(run_dir_final))
        raise
    psl.stage_end("PASS")

    # Stage H: finalize log.
    psl.stage_start(SegmentationStage.H.value)
    finalize_logging(logger)
    psl.stage_end("PASS")

    final_manifest_path = run_dir_final / "segmentation_manifest.json"

    return SegmentationPipelineResult(
        segmentation_id=segmentation_id,
        manifest_path=final_manifest_path,
        lifecycle=LIFECYCLE_SUCCESS,
        manifest=manifest,
        duration_seconds=time.perf_counter() - start,
    )
