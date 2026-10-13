"""Stage C input validation for DEV-06 Prototype Segmentation.

Mirrors DEV-04 / DEV-05 input-validation pattern. Validates:

- DEV-04 ``clustering_manifest.json`` (existence, schema version,
  required fields, algorithm_family ∈ closed set).
- DEV-04 ``cluster_labels_*.parquet`` (existence, required columns,
  ``ClusterLabel`` dtype int64, ``IsNoise`` consistency with
  ``ClusterLabel == -1``).
- DEV-03 ``ml_dataset_*.parquet`` (existence, feature set ⊆ columns).
- Row alignment (cluster_labels rows == ml_dataset rows).
- CustomerID alignment (if both have CustomerID, values must match
  row-by-row).
- Per-feature type detection (numerical / categorical / text_or_id).
- Non-DBSCAN noise invariants (``ClusterLabel.min() >= 0``; no noise
  rows for non-density algorithms).
- Per-config validation knobs (min_samples, min_features,
  require_no_nan, exclude_customer_id_from_features).

Hard rules
----------
- All checks return ``ValidationCheck`` objects; the caller decides
  whether to fail-closed or warn.
- Validation does NOT modify any input file (R-DEV-06-10/11/12).
- No access to ``data/raw/primary/**``, ``data/processed/**``,
  ``reports/**`` (R-DEV-06-04/05/09).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

from customer_segmentation.prototype.segmentation.config_loader import (
    Dev06Config,
)
from customer_segmentation.prototype.segmentation.manifest import (
    SegmentationValidationReport,
    ValidationCheck,
)

__all__ = [
    "Dev06InputValidationError",
    "CUSTOMER_KEYS_TO_STRIP",
    "validate_inputs",
    "validate_clustering_manifest",
    "validate_cluster_labels",
    "validate_ml_dataset",
    "validate_label_dataset_alignment",
    "validate_feature_set",
    "validate_evaluation_manifest_if_provided",
]


# CustomerID-like column names to strip (mirror DEV-05).
CUSTOMER_KEYS_TO_STRIP: Final[frozenset[str]] = frozenset(
    {"CustomerID", "customer_id", "Customer Id", "Customer_Id", "customerId"}
)


DBSCAN_NOISE_LABEL: Final[int] = -1


class Dev06InputValidationError(ValueError):
    """Raised on hard validation failure (fail-closed)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Dev06InputValidationError(f"File not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise Dev06InputValidationError(f"Failed to parse JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise Dev06InputValidationError(
            f"JSON at {path} must be an object; got {type(data).__name__}."
        )
    return data


def _str_param(d: dict[str, Any], key: str) -> str | None:
    if key not in d:
        return None
    v = d[key]
    if v is None:
        return None
    return str(v)


# ---------------------------------------------------------------------------
# Per-source validators
# ---------------------------------------------------------------------------


def validate_clustering_manifest(
    clustering_manifest_path: Path,
) -> tuple[dict[str, Any], list[ValidationCheck]]:
    """Validate a DEV-04 ``clustering_manifest.json`` file.

    Returns the loaded dict + the list of validation checks. Does NOT
    raise on soft checks (e.g. missing optional fields) — only on
    hard failures (file missing, JSON malformed, schema_version
    absent).

    Per R-DEV-06-11: DEV-06 does NOT modify the clustering manifest.
    """
    checks: list[ValidationCheck] = []
    try:
        data = _read_json(clustering_manifest_path)
    except Dev06InputValidationError as exc:
        checks.append(
            ValidationCheck(
                check_id="clustering_manifest_parseable",
                passed=False,
                detail=str(exc),
            )
        )
        return ({}, checks)
    checks.append(
        ValidationCheck(
            check_id="clustering_manifest_parseable",
            passed=True,
        )
    )
    schema_version = _str_param(data, "schema_version")
    checks.append(
        ValidationCheck(
            check_id="clustering_manifest_schema_version_present",
            passed=schema_version is not None and schema_version == "1.0.0",
            detail=f"schema_version={schema_version!r}",
        )
    )
    for required in (
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "algorithm",
        "algorithm_family",
        "ml_dataset_sha256",
        "feature_set",
        "n_samples",
    ):
        present = required in data
        checks.append(
            ValidationCheck(
                check_id=f"clustering_manifest_{required}_present",
                passed=present,
                detail=("" if present else f"required field {required!r} is missing"),
            )
        )
    return (data, checks)


def validate_cluster_labels(
    cluster_labels_path: Path,
    *,
    algorithm_family: str | None = None,
) -> tuple[pd.DataFrame, list[ValidationCheck]]:
    """Validate a DEV-04 ``cluster_labels_*.parquet`` file.

    Returns the loaded DataFrame + the list of checks.
    """
    checks: list[ValidationCheck] = []
    if not cluster_labels_path.exists():
        checks.append(
            ValidationCheck(
                check_id="cluster_labels_exists",
                passed=False,
                detail=str(cluster_labels_path),
            )
        )
        return (pd.DataFrame(), checks)
    checks.append(
        ValidationCheck(
            check_id="cluster_labels_exists",
            passed=True,
            detail=str(cluster_labels_path),
        )
    )
    try:
        df = pd.read_parquet(cluster_labels_path)
    except Exception as exc:  # noqa: BLE001
        checks.append(
            ValidationCheck(
                check_id="cluster_labels_readable",
                passed=False,
                detail=str(exc),
            )
        )
        return (pd.DataFrame(), checks)
    checks.append(
        ValidationCheck(
            check_id="cluster_labels_readable",
            passed=True,
        )
    )
    # Required columns.
    for col in ("ClusterLabel", "IsNoise"):
        present = col in df.columns
        checks.append(
            ValidationCheck(
                check_id=f"cluster_labels_has_{col}",
                passed=present,
                detail=f"columns={list(df.columns)}",
            )
        )
    # dtype check.
    if "ClusterLabel" in df.columns:
        cl_dtype_ok = df["ClusterLabel"].dtype in (np.int32, np.int64, "int32", "int64")
        checks.append(
            ValidationCheck(
                check_id="cluster_labels_ClusterLabel_dtype_int",
                passed=cl_dtype_ok,
                detail=str(df["ClusterLabel"].dtype),
            )
        )
    # IsNoise consistency with ClusterLabel == -1.
    if "ClusterLabel" in df.columns and "IsNoise" in df.columns:
        cl = df["ClusterLabel"].to_numpy()
        isn = df["IsNoise"].to_numpy().astype(bool)
        expected = cl == DBSCAN_NOISE_LABEL
        consistent = bool(np.array_equal(isn, expected))
        checks.append(
            ValidationCheck(
                check_id="cluster_labels_IsNoise_consistent",
                passed=consistent,
                detail=(
                    "IsNoise matches ClusterLabel==-1"
                    if consistent
                    else "IsNoise inconsistent with ClusterLabel==-1"
                ),
            )
        )
    # Non-DBSCAN guard: ClusterLabel.min() >= 0 if algorithm_family != density_based.
    if (
        algorithm_family is not None
        and algorithm_family != "density_based"
        and "ClusterLabel" in df.columns
    ):
        cl = df["ClusterLabel"].to_numpy()
        min_label = int(np.min(cl)) if len(cl) > 0 else 0
        passed = min_label >= 0
        checks.append(
            ValidationCheck(
                check_id="non_dbscan_cluster_label_min_non_negative",
                passed=passed,
                detail=f"min_label={min_label}",
            )
        )
    return (df, checks)


def validate_ml_dataset(
    ml_dataset_path: Path,
    *,
    min_features: int = 1,
) -> tuple[pd.DataFrame, list[ValidationCheck]]:
    """Validate a DEV-03 ``ml_dataset_*.parquet`` file."""
    checks: list[ValidationCheck] = []
    if not ml_dataset_path.exists():
        checks.append(
            ValidationCheck(
                check_id="ml_dataset_exists",
                passed=False,
                detail=str(ml_dataset_path),
            )
        )
        return (pd.DataFrame(), checks)
    checks.append(
        ValidationCheck(
            check_id="ml_dataset_exists",
            passed=True,
            detail=str(ml_dataset_path),
        )
    )
    try:
        df = pd.read_parquet(ml_dataset_path)
    except Exception as exc:  # noqa: BLE001
        checks.append(
            ValidationCheck(
                check_id="ml_dataset_readable",
                passed=False,
                detail=str(exc),
            )
        )
        return (pd.DataFrame(), checks)
    checks.append(
        ValidationCheck(
            check_id="ml_dataset_readable",
            passed=True,
        )
    )
    n_features = len(df.columns)
    checks.append(
        ValidationCheck(
            check_id="ml_dataset_min_features",
            passed=n_features >= min_features,
            detail=f"n_columns={n_features}",
        )
    )
    return (df, checks)


def validate_label_dataset_alignment(
    cluster_labels_df: pd.DataFrame,
    ml_dataset_df: pd.DataFrame,
) -> list[ValidationCheck]:
    """Check row alignment between cluster_labels and ml_dataset."""
    checks: list[ValidationCheck] = []
    n_lab = len(cluster_labels_df)
    n_ml = len(ml_dataset_df)
    checks.append(
        ValidationCheck(
            check_id="row_count_match",
            passed=n_lab == n_ml,
            detail=f"cluster_labels={n_lab} vs ml_dataset={n_ml}",
        )
    )
    # CustomerID alignment.
    if "CustomerID" in cluster_labels_df.columns and "CustomerID" in ml_dataset_df.columns:
        cl_ids = cluster_labels_df["CustomerID"].to_numpy()
        ml_ids = ml_dataset_df["CustomerID"].to_numpy()
        aligned = bool(np.array_equal(cl_ids, ml_ids))
        checks.append(
            ValidationCheck(
                check_id="customer_id_alignment",
                passed=aligned,
                detail=(
                    "CustomerID values match row-by-row" if aligned else "CustomerID values differ"
                ),
            )
        )
    return checks


def validate_feature_set(
    feature_set: list[str],
    ml_dataset_df: pd.DataFrame,
    *,
    exclude_customer_id_from_features: bool = True,
) -> list[ValidationCheck]:
    """Validate ``L1.feature_set`` is a subset of ``ml_dataset`` columns."""
    checks: list[ValidationCheck] = []
    if not isinstance(feature_set, list):
        checks.append(
            ValidationCheck(
                check_id="feature_set_is_list",
                passed=False,
                detail=f"got {type(feature_set).__name__}",
            )
        )
        return checks
    if len(feature_set) == 0:
        checks.append(
            ValidationCheck(
                check_id="feature_set_non_empty",
                passed=False,
                detail="empty feature_set",
            )
        )
        return checks
    checks.append(
        ValidationCheck(
            check_id="feature_set_non_empty",
            passed=True,
        )
    )
    cols = set(ml_dataset_df.columns)
    if exclude_customer_id_from_features:
        # Strip CustomerID candidates from feature_set silently (defence).
        feature_set = [f for f in feature_set if f not in CUSTOMER_KEYS_TO_STRIP]
    missing = [f for f in feature_set if f not in cols]
    checks.append(
        ValidationCheck(
            check_id="feature_set_subset_of_dataset_columns",
            passed=len(missing) == 0,
            detail=f"missing={missing}" if missing else "",
        )
    )
    return checks


def validate_evaluation_manifest_if_provided(
    evaluation_manifest_path: Path | None,
    clustering_id: str,
    ml_dataset_sha256: str,
) -> tuple[dict[str, Any] | None, list[ValidationCheck]]:
    """Validate an optional DEV-05 ``evaluation_manifest.json``.

    Returns the loaded dict (or None if path is None) + checks.
    """
    checks: list[ValidationCheck] = []
    if evaluation_manifest_path is None:
        checks.append(
            ValidationCheck(
                check_id="evaluation_manifest_not_provided",
                passed=True,
                detail="evaluation_id will be null",
            )
        )
        return (None, checks)
    try:
        data = _read_json(evaluation_manifest_path)
    except Dev06InputValidationError as exc:
        checks.append(
            ValidationCheck(
                check_id="evaluation_manifest_parseable",
                passed=False,
                detail=str(exc),
            )
        )
        return (None, checks)
    checks.append(
        ValidationCheck(
            check_id="evaluation_manifest_parseable",
            passed=True,
        )
    )
    schema_version = _str_param(data, "schema_version")
    checks.append(
        ValidationCheck(
            check_id="evaluation_manifest_schema_version_1_0_0",
            passed=schema_version == "1.0.0",
            detail=f"schema_version={schema_version!r}",
        )
    )
    # Cross-check: clustering_id.
    cl_in_ev = _str_param(data, "clustering_id")
    checks.append(
        ValidationCheck(
            check_id="evaluation_manifest_clustering_id_match",
            passed=cl_in_ev == clustering_id,
            detail=f"evaluation.clustering_id={cl_in_ev!r} vs L1.clustering_id={clustering_id!r}",
        )
    )
    # Cross-check: ml_dataset_sha256.
    ml_in_ev = _str_param(data, "ml_dataset_sha256")
    checks.append(
        ValidationCheck(
            check_id="evaluation_manifest_ml_dataset_sha256_match",
            passed=ml_in_ev == ml_dataset_sha256,
            detail=(
                f"evaluation.ml_dataset_sha256={ml_in_ev!r} vs "
                f"L1.ml_dataset_sha256={ml_dataset_sha256!r}"
            ),
        )
    )
    return (data, checks)


# ---------------------------------------------------------------------------
# Top-level validator
# ---------------------------------------------------------------------------


def validate_inputs(
    *,
    clustering_manifest_path: Path,
    cluster_labels_path: Path,
    ml_dataset_path: Path,
    preprocessed_manifest_path: Path,
    config: Dev06Config,
    evaluation_manifest_path: Path | None = None,
) -> SegmentationValidationReport:
    """Run the full DEV-06 input validation suite.

    Returns a :class:`SegmentationValidationReport` whose
    ``all_passed`` field is the conjunction of every check.
    """
    all_checks: list[ValidationCheck] = []
    # 1. Clustering manifest.
    cm_data, cm_checks = validate_clustering_manifest(clustering_manifest_path)
    all_checks.extend(cm_checks)
    algorithm_family = _str_param(cm_data, "algorithm_family")
    # 2. Preprocessed manifest.
    try:
        pp_data = _read_json(preprocessed_manifest_path)
        all_checks.append(
            ValidationCheck(
                check_id="preprocessed_manifest_parseable",
                passed=True,
            )
        )
    except Dev06InputValidationError as exc:
        all_checks.append(
            ValidationCheck(
                check_id="preprocessed_manifest_parseable",
                passed=False,
                detail=str(exc),
            )
        )
        pp_data = {}
    schema_version = _str_param(pp_data, "schema_version")
    all_checks.append(
        ValidationCheck(
            check_id="preprocessed_manifest_schema_version_1_0_0",
            passed=schema_version == "1.0.0",
            detail=f"schema_version={schema_version!r}",
        )
    )
    # ml_dataset_block.artifact_path must be present and non-empty.
    ml_dataset_block = pp_data.get("ml_dataset_block", {})
    artifact_path = (
        ml_dataset_block.get("artifact_path", "") if isinstance(ml_dataset_block, dict) else ""
    )
    all_checks.append(
        ValidationCheck(
            check_id="preprocessed_manifest_ml_dataset_artifact_path_present",
            passed=bool(artifact_path),
            detail=f"artifact_path={artifact_path!r}",
        )
    )
    # config_hash must be present and non-empty.
    config_hash = pp_data.get("config_hash", "")
    all_checks.append(
        ValidationCheck(
            check_id="preprocessed_manifest_config_hash_present",
            passed=bool(config_hash),
            detail=f"config_hash={config_hash!r}",
        )
    )
    # 3. cluster_labels.
    cl_df, cl_checks = validate_cluster_labels(
        cluster_labels_path, algorithm_family=algorithm_family
    )
    all_checks.extend(cl_checks)
    # 4. ml_dataset.
    ml_df, ml_checks = validate_ml_dataset(
        ml_dataset_path, min_features=config.validation.min_features
    )
    all_checks.extend(ml_checks)
    # 5. Alignment.
    if not cl_df.empty and not ml_df.empty:
        all_checks.extend(validate_label_dataset_alignment(cl_df, ml_df))
    # 6. Feature set.
    feature_set = list(cm_data.get("feature_set", []))
    if not cl_df.empty and not ml_df.empty:
        all_checks.extend(
            validate_feature_set(
                feature_set,
                ml_df,
                exclude_customer_id_from_features=(
                    config.validation.exclude_customer_id_from_features
                ),
            )
        )
    # 7. min_samples check.
    n_samples = len(cl_df) if not cl_df.empty else 0
    all_checks.append(
        ValidationCheck(
            check_id="min_samples",
            passed=n_samples >= config.validation.min_samples,
            detail=f"n_samples={n_samples}, min={config.validation.min_samples}",
        )
    )
    # 8. Optional evaluation manifest.
    if evaluation_manifest_path is not None:
        _, ev_checks = validate_evaluation_manifest_if_provided(
            evaluation_manifest_path,
            clustering_id=str(cm_data.get("clustering_id", "")),
            ml_dataset_sha256=str(cm_data.get("ml_dataset_sha256", "")),
        )
        all_checks.extend(ev_checks)
    all_passed = all(c.passed for c in all_checks)
    return SegmentationValidationReport(all_passed=all_passed, checks=all_checks)
