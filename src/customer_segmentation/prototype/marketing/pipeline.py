"""DEV-07 Prototype Marketing pipeline (Stage A → G orchestrator).

Mirrors the DEV-04/05/06 pipeline pattern.

Stages
------
- **A (preflight)** — load DEV-07 config; resolve storage root.
- **B (lookup)** — locate DEV-06 ``SegmentationManifest`` (by
  ``segmentation_id`` regex or explicit ``--manifest-path``).
- **C (validation)** — input contract + research_safety + noise
  exclusion gate. Build :class:`MarketingValidationReport`.
- **D (recommendation build)** — per-segment recommendation entry
  builder (Phase A: REVIEW_REQUIRED shell only).
- **E (manifest write)** — atomic write
  ``marketing_manifest.json`` (Phase A: only emit; CSV/JSONL are
  disabled per OQ-D07-08).
- **F (publish)** — atomic ``os.rename(staging → final)`` (no-op
  for single-file write; placeholder for future multi-file bundles).
- **G (finalize)** — flush + close log handlers.

Hard rules
----------
- The pipeline never modifies DEV-06 inputs.
- The pipeline never writes outside the resolved storage root.
- The pipeline never exposes research-promotion status.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.marketing.config_loader import (
    DEFAULT_DEV07_CONFIG_PATH,
    Dev07Config,
    load_dev07_config,
)
from customer_segmentation.prototype.marketing.exceptions import (
    MarketingInputError,
    MarketingValidationError,
)
from customer_segmentation.prototype.marketing.logging_config import (
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)
from customer_segmentation.prototype.marketing.manifest import (
    MarketingRecommendationManifest,
    build_marketing_manifest,
)
from customer_segmentation.prototype.marketing.mkt_framework_loader import (
    MktFrameworkRef,
    MktFrameworkStructure,
    framework_version_string,
    load_mkt_framework,
    load_mkt_framework_structure,
)
from customer_segmentation.prototype.marketing.recommendation import (
    build_recommendations_from_segmentation,
)
from customer_segmentation.prototype.marketing.scope import (
    MARKETING_LIMITATION_TEXT,
    MARKETING_MANIFEST_SCHEMA_VERSION,
)
from customer_segmentation.prototype.marketing.storage import (
    compute_config_sha256,
    derive_marketing_id,
    find_existing_marketing,
    prototype_marketing_base_dir,
    prototype_marketing_run_dir,
    resolve_storage_root,
)
from customer_segmentation.prototype.marketing.validation import (
    compute_file_sha256,
    validate_inputs,
)

__all__ = [
    "LIFECYCLE_CACHED",
    "LIFECYCLE_SUCCESS",
    "LIFECYCLE_FAILED",
    "MarketingPipelineResult",
    "compute_environment_block",
    "run_marketing_pipeline",
]


LIFECYCLE_CACHED: Final[str] = "CACHED"
LIFECYCLE_SUCCESS: Final[str] = "SUCCESS"
LIFECYCLE_FAILED: Final[str] = "FAILED"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketingPipelineResult:
    """Outcome of a DEV-07 pipeline run."""

    lifecycle: str
    manifest: MarketingRecommendationManifest
    run_dir: Path
    manifest_path: Path
    cached: bool
    validation_passed: bool
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Environment block
# ---------------------------------------------------------------------------


def compute_environment_block() -> dict[str, str]:
    """Capture a small environment snapshot for the manifest.

    Mirrors the DEV-06 ``EnvironmentBlock`` shape but keeps the dict
    minimal: ``python``, ``platform``, ``release``, ``machine``,
    ``key_libraries``.
    """
    key_libs: dict[str, str] = {}
    for mod_name in ("pandas", "numpy", "scipy", "scikit-learn", "yaml"):
        try:
            mod = __import__(mod_name)
            version = getattr(mod, "__version__", "unknown")
            key_libs[mod_name] = str(version)
        except Exception:  # pragma: no cover — defensive
            key_libs[mod_name] = "unavailable"
    return {
        "python": sys.version.split()[0] if sys.version else "",
        "platform": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "key_libraries": key_libs,  # type: ignore[dict-item]
    }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_marketing_pipeline(
    *,
    segmentation_id: str | None = None,
    manifest_path: Path | str | None = None,
    config_path: Path | str | None = None,
    force_rerun: bool = False,
    log_dir: Path | str | None = None,
) -> MarketingPipelineResult:
    """Run the DEV-07 marketing pipeline.

    Parameters
    ----------
    segmentation_id : str or None
        DEV-06 ``segmentation_id`` (``^seg_[0-9a-f]{24}$``). Mutually
        exclusive with ``manifest_path``.
    manifest_path : pathlib.Path or str or None
        Explicit path to a DEV-06 ``segmentation_manifest.json``.
    config_path : pathlib.Path or str or None
        Path to the DEV-07 config YAML (default:
        ``configs/dev07_marketing.yaml``).
    force_rerun : bool
        If True, ignore the idempotency cache and write a fresh
        manifest.
    log_dir : pathlib.Path or str or None
        Directory for the per-stage log file. If None, no file log
        is emitted (console only).

    Returns
    -------
    MarketingPipelineResult
        Outcome (lifecycle, manifest, paths, validation flag).

    Raises
    ------
    MarketingInputError
        On CLI arg / path errors.
    MarketingValidationError
        On Stage C validation failure (fail-closed).
    MarketingStoragePathError
        On storage path resolution failure.
    """
    # ---- Stage A: preflight --------------------------------------------------
    if segmentation_id is None and manifest_path is None:
        raise MarketingInputError("Either --segmentation-id or --manifest-path must be provided.")
    if segmentation_id is not None and manifest_path is not None:
        raise MarketingInputError("--segmentation-id and --manifest-path are mutually exclusive.")

    config: Dev07Config = load_dev07_config(config_path)
    storage_root = resolve_storage_root()

    log_file: Path | None = None
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "dev07_marketing.log"

    logger = configure_logging(
        level=config.logging.level,
        fmt=config.logging.format,
        log_file=log_file,
        emit_to_console=config.logging.emit_to_console,
    )
    psl = PerStageLogger(logger, stage="A")
    psl.stage_start("A")

    notes: list[str] = []

    # ---- Stage B: lookup ------------------------------------------------------
    psl.stage_start("B")
    seg_manifest_path: Path
    if manifest_path is not None:
        seg_manifest_path = Path(manifest_path)
    else:
        # Resolve by segmentation_id: search the storage root.
        if segmentation_id is None:
            raise MarketingInputError("Internal error: segmentation_id is None in lookup stage.")
        seg_manifest_path = _resolve_segmentation_manifest_path(
            storage_root=storage_root,
            segmentation_id=segmentation_id,
        )
    if not seg_manifest_path.exists():
        raise MarketingInputError(f"DEV-06 segmentation manifest not found: {seg_manifest_path!s}")
    psl.info(f"Located DEV-06 manifest: {seg_manifest_path!s}")

    try:
        with seg_manifest_path.open("r", encoding="utf-8") as fh:
            seg_manifest_data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise MarketingInputError(f"Failed to parse DEV-06 manifest JSON: {exc}") from exc
    if not isinstance(seg_manifest_data, dict):
        raise MarketingInputError(
            f"DEV-06 manifest must be a JSON object; got {type(seg_manifest_data).__name__}."
        )
    psl.stage_end("PASS")

    # ---- Stage C: validation -------------------------------------------------
    psl.stage_start("C")
    try:
        report = validate_inputs(manifest_data=seg_manifest_data, config=config)
    except MarketingValidationError as exc:
        psl.stage_end("FAIL")
        psl.error(f"Stage C failed: {exc}")
        raise
    psl.stage_end("PASS")

    # ---- Stage D: recommendation build --------------------------------------
    psl.stage_start("D")
    segmentation_manifest_sha256 = compute_file_sha256(seg_manifest_path)
    dataset_id = str(seg_manifest_data.get("dataset_id", ""))
    preprocessed_id = str(seg_manifest_data.get("preprocessed_id", ""))
    clustering_id = str(seg_manifest_data.get("clustering_id", ""))
    seg_id_str = str(seg_manifest_data.get("segmentation_id", ""))
    ml_dataset_sha256 = str(seg_manifest_data.get("ml_dataset_sha256", ""))
    feature_set_sha256 = str(seg_manifest_data.get("feature_set_sha256", ""))
    preprocessing_config_sha256 = str(seg_manifest_data.get("preprocessing_config_sha256", ""))
    noise_policy_used = str(seg_manifest_data.get("noise_policy_used", "n/a"))

    # Count input + noise from the manifest's segment_sizes.
    segment_sizes_raw = seg_manifest_data.get("segment_sizes", [])
    n_segments_input = sum(
        1 for s in segment_sizes_raw if isinstance(s, dict) and not bool(s.get("is_noise", False))
    )
    n_segments_noise = sum(
        1 for s in segment_sizes_raw if isinstance(s, dict) and bool(s.get("is_noise", False))
    )

    entries = build_recommendations_from_segmentation(
        segmentation_manifest_data=seg_manifest_data,
        config=config,
        mkt_framework_structure=None,  # wired in Phase B when MKT content exists
    )
    psl.info(f"Built {len(entries)} recommendation entries (Phase A: REVIEW_REQUIRED)")

    # ---- MKT framework discovery (Phase A: returns None) --------------------
    mkt_ref: MktFrameworkRef | None = load_mkt_framework(config)
    mkt_framework_found = mkt_ref is not None
    if mkt_ref is not None:
        mkt_framework_version = framework_version_string(mkt_ref)
        notes.append(f"MKT framework found: {mkt_ref.framework_dir}")
    else:
        mkt_framework_version = None
        notes.append("MKT-01..MKT-05 absent: Phase A REVIEW_REQUIRED shell only.")

    psl.stage_end("PASS")

    # ---- Derive marketing_id -------------------------------------------------
    marketing_id = derive_marketing_id(
        segmentation_id=seg_id_str,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        segmentation_manifest_sha256=segmentation_manifest_sha256,
        mkt_framework_version=mkt_framework_version,
        mkt_framework_found=mkt_framework_found,
        noise_policy_used=noise_policy_used,
        schema_version=MARKETING_MANIFEST_SCHEMA_VERSION,
    )
    config_sha256 = compute_config_sha256(_config_text_for_hash(config_path))
    run_dir = prototype_marketing_run_dir(
        storage_root=storage_root,
        dataset_id=dataset_id,
        preprocessed_id=preprocessed_id,
        clustering_id=clustering_id,
        segmentation_id=seg_id_str,
        marketing_id=marketing_id,
    )

    # ---- Idempotency lookup (skip when force_rerun) -------------------------
    psl.stage_start("E")
    expected_canonical = {
        "segmentation_id": seg_id_str,
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "segmentation_manifest_sha256": segmentation_manifest_sha256,
        "mkt_framework_version": mkt_framework_version,
        "mkt_framework_found": mkt_framework_found,
        "noise_policy_used": noise_policy_used,
        "schema_version": MARKETING_MANIFEST_SCHEMA_VERSION,
    }
    base_dir = prototype_marketing_base_dir(
        storage_root=storage_root,
        dataset_id=dataset_id,
        preprocessed_id=preprocessed_id,
        clustering_id=clustering_id,
        segmentation_id=seg_id_str,
    )

    cached = False
    lifecycle = LIFECYCLE_SUCCESS
    target_path = run_dir / "marketing_manifest.json"
    if not force_rerun:
        try:
            found, existing_path = find_existing_marketing(
                base_dir=base_dir,
                marketing_id=marketing_id,
                expected_canonical=expected_canonical,
            )
        except Exception as exc:
            psl.warning(f"Idempotency check failed: {exc}")
            found = False
            existing_path = None
        if found and existing_path is not None:
            cached = True
            lifecycle = LIFECYCLE_CACHED
            target_path = existing_path
            psl.info(f"Cache hit: reusing {existing_path}")
            psl.stage_end("PASS")
            psl.stage_start("G")
            psl.stage_end("PASS")
            finalize_logging(logger)
            # Re-read manifest to return a fresh dataclass instance.
            from customer_segmentation.prototype.marketing.manifest import (
                read_marketing_manifest,
            )

            return MarketingPipelineResult(
                lifecycle=lifecycle,
                manifest=read_marketing_manifest(existing_path),
                run_dir=run_dir,
                manifest_path=existing_path,
                cached=cached,
                validation_passed=True,
                notes=notes,
            )

    # ---- Build + write manifest ---------------------------------------------
    run_dir.mkdir(parents=True, exist_ok=True)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Use a staging path then atomic rename (R-DEV-07 write safety).
    staging_path = run_dir / f"marketing_manifest.json.tmp.{os.getpid()}"

    from customer_segmentation.prototype.marketing.manifest import (
        write_marketing_manifest,
    )

    n_segments_with_recommendation = len(entries)
    n_segments_not_available = 0  # Phase A: all entries are REVIEW_REQUIRED, not NOT_AVAILABLE.

    manifest = build_marketing_manifest(
        marketing_id=marketing_id,
        segmentation_id=seg_id_str,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        source_framework_version=mkt_framework_version,
        mkt_framework_found=mkt_framework_found,
        ml_dataset_sha256=ml_dataset_sha256,
        feature_set_sha256=feature_set_sha256,
        preprocessing_config_sha256=preprocessing_config_sha256,
        segmentation_manifest_sha256=segmentation_manifest_sha256,
        n_segments_input=n_segments_input,
        n_segments_with_recommendation=n_segments_with_recommendation,
        n_segments_noise=n_segments_noise,
        n_segments_not_available=n_segments_not_available,
        noise_policy_used=noise_policy_used,
        recommendations=entries,
        environment=compute_environment_block(),
        config_sha256=config_sha256,
        log_file=str(log_file) if log_file is not None else "",
        validation_report=report,
        readonly_paths=list(config.research_safety.readonly_paths),
        input_segmentation_manifest=str(seg_manifest_path),
        availability=config.availability_default,
        limitation=MARKETING_LIMITATION_TEXT,
    )

    write_marketing_manifest(manifest, staging_path)
    with contextlib.suppress(OSError):
        if target_path.exists():
            target_path.unlink()
    os.replace(staging_path, target_path)
    psl.info(f"Wrote {target_path}")
    psl.stage_end("PASS")

    # ---- Stage F: publish (atomic rename already done above) ----------------
    psl.stage_start("F")
    psl.stage_end("PASS")

    # ---- Stage G: finalize ---------------------------------------------------
    psl.stage_start("G")
    finalize_logging(logger)
    psl.stage_end("PASS")

    return MarketingPipelineResult(
        lifecycle=lifecycle,
        manifest=manifest,
        run_dir=run_dir,
        manifest_path=target_path,
        cached=cached,
        validation_passed=True,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_segmentation_manifest_path(
    *,
    storage_root: Path,
    segmentation_id: str,
) -> Path:
    """Resolve ``<storage_root>/.../segmentation/<seg_id>/segmentation_manifest.json``.

    Mirrors DEV-06 ``prototype_segmentation_run_dir`` layout. Does
    NOT scan subdirectories; the caller must ensure the path is
    correct. (Scanning would be O(N); we trust the canonical layout.)
    """
    import re

    if not re.match(r"^seg_[0-9a-f]{24}$", segmentation_id):
        raise MarketingInputError(
            f"segmentation_id {segmentation_id!r} does not match required format "
            f"^seg_[0-9a-f]{{24}}$."
        )
    # The DEV-06 layout is (post A-1):
    #   <storage_root>/<dataset_id>/preprocessed/<preprocessed_id>/
    #   clustering/<clustering_id>/segmentation/<segmentation_id>/
    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); the dataset id is
    # the first child of ``storage_root`` (no extra ``"datasets"``
    # literal). See the regression test in
    # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    candidates = list(
        storage_root.glob(
            f"*/preprocessed/*/clustering/*/segmentation/{segmentation_id}/segmentation_manifest.json"
        )
    )
    if not candidates:
        raise MarketingInputError(
            f"Could not locate DEV-06 segmentation_manifest.json for "
            f"{segmentation_id!r} under {storage_root!s}. Ensure the "
            f"DEV-06 manifest exists at the canonical path."
        )
    if len(candidates) > 1:
        raise MarketingInputError(
            f"Multiple DEV-06 segmentation manifests found for "
            f"{segmentation_id!r} under {storage_root!s}: {candidates}."
        )
    return candidates[0]


def _config_text_for_hash(config_path: Path | str | None) -> str:
    """Return the config YAML text for SHA-256 derivation."""
    path = Path(config_path) if config_path is not None else DEFAULT_DEV07_CONFIG_PATH
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
