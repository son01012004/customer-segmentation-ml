"""Per-experiment collectors that normalise EPIC-07 artifacts.

Each collector:

1. Reads a single source artifact (CSV / JSON / manifest) under
   ``reports/exp0X/`` without mutating it.
2. Emits a list of dictionaries, each matching the standardised
   schema in :mod:`schema`.
3. Records the **source artifact path** for every row so a
   downstream consumer can trace any row back to its origin.

The collectors NEVER invent values. If a source does not record a
field, the corresponding ``<field>_missing_reason`` is set and the
value itself is the literal sentinel :data:`schema.MISSING`.

Hard constraints (AGENTS.md §2):

- No ranking, no "best/winner/optimal/recommended/final" labels.
- No mutation of EPIC-07 artifacts.
- No new dependencies.
- All collected values traceable to the source file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.experiment_results.schema import (
    MISSING,
    MISSING_REASON_DIFFERENT_CONDITIONS,
    MISSING_REASON_FIELD_NOT_IN_SOURCE,
    MISSING_REASON_NOT_APPLICABLE,
    MISSING_REASON_NOT_RECORDED,
    SourceExperiment,
)

__all__ = [
    "collect_exp01",
    "collect_exp02",
    "collect_exp03",
    "collect_exp04",
    "collect_exp05",
    "_safe_load_json",
    "_empty_row_template",
    "_jsonify",
    "_maybe_int",
    "_maybe_float",
    "_make_missing_field_with_reason",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON file, returning ``None`` on parse error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _jsonify(value: Any) -> str:
    """Serialise a value to JSON; ``MISSING`` strings round-trip as-is."""
    if value is None:
        return MISSING
    if isinstance(value, str) and value == MISSING:
        return MISSING
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _maybe_int(value: Any) -> int | None:
    """Convert to int if not NaN/None; else return None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(f):
        return None
    return int(f)


def _maybe_float(value: Any) -> float | None:
    """Convert to float if not NaN/None; else return None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _empty_row_template(source_experiment: SourceExperiment) -> dict[str, Any]:
    """Build a row with every column initialised to ``MISSING``.

    The caller populates only the fields it has evidence for. Missing
    columns remain as ``MISSING`` and are flagged by the validator.

    By default, every MISSING-reason field is set to ``NOT_APPLICABLE``
    (the validator's "by design" sentinel) rather than left empty. This
    means the validator only flags rows where the gap is a true data
    issue rather than the typical "this experiment does not use this
    field" case. Callers can override the reason with a more specific
    ``DIFFERENT_CONDITIONS``, ``FIELD_NOT_IN_SOURCE``, or ``DEFERRED``
    value where appropriate.
    """
    row: dict[str, Any] = dict.fromkeys(_ALL_COLUMNS, MISSING)
    row["source_experiment"] = source_experiment.value
    # Default missing-reason annotations.
    for col in _ALL_COLUMNS:
        if col.endswith("_missing_reason"):
            row[col] = MISSING_REASON_NOT_APPLICABLE
    return row


# Import lazily to avoid an import cycle between schema and collectors.
def _all_columns() -> tuple[str, ...]:
    from customer_segmentation.evaluation.experiment_results.schema import STANDARD_COLUMNS

    return STANDARD_COLUMNS


_ALL_COLUMNS = _all_columns()


def _make_missing_field_with_reason(field: str, reason: str) -> tuple[Any, str]:
    """Return ``(MISSING, reason)`` and validate the field name is in scope.

    This is purely a convenience wrapper to keep collector code tidy.
    """
    if field not in _ALL_COLUMNS:
        raise ValueError(f"Unknown schema field: {field!r}")
    return MISSING, reason


def _set_with_reason(
    row: dict[str, Any],
    field: str,
    value: Any,
    *,
    missing_reason_if_absent: str | None = None,
) -> None:
    """Set ``row[field]`` to ``value``; if ``value`` is None, mark missing.

    When ``value`` is ``None``:
    - ``row[field]`` becomes ``MISSING``.
    - ``row[f"{field}_missing_reason"]`` becomes ``missing_reason_if_absent``
      if provided, otherwise :data:`MISSING_REASON_NOT_RECORDED`.
    """
    if value is None:
        row[field] = MISSING
        row[f"{field}_missing_reason"] = (
            missing_reason_if_absent
            if missing_reason_if_absent is not None
            else MISSING_REASON_NOT_RECORDED
        )
    else:
        row[field] = value
        row[f"{field}_missing_reason"] = ""


def _extract_cluster_sizes(
    cluster_sizes: Any,
) -> tuple[int | None, int | None, int | None, float | None]:
    """Extract (n_clusters_realized, largest, smallest, noise_ratio) from a dict.

    The cluster_sizes column in EXP-05 is a serialised Python dict mapping
    cluster label ("0", "1", ..., "noise") to integer count. DBSCAN may
    include "noise"; for non-DBSCAN algorithms no noise entry exists.

    Returns
    -------
    tuple
        (n_clusters_realized, cluster_size_largest, cluster_size_smallest,
        noise_ratio). Each element is ``None`` when not applicable /
        unknown.
    """
    if cluster_sizes is None:
        return None, None, None, None
    if isinstance(cluster_sizes, str):
        try:
            cluster_sizes = json.loads(cluster_sizes)
        except (json.JSONDecodeError, TypeError):
            return None, None, None, None
    if not isinstance(cluster_sizes, dict):
        return None, None, None, None
    noise_count = _maybe_int(cluster_sizes.get("noise"))
    non_noise = {
        int(k): int(v) for k, v in cluster_sizes.items() if str(k) != "noise" and v is not None
    }
    n_clusters_realized = len(non_noise) if non_noise else None
    if not non_noise:
        return n_clusters_realized, None, None, _maybe_float(noise_count)
    largest = max(non_noise.values())
    smallest = min(non_noise.values())
    return n_clusters_realized, largest, smallest, _maybe_float(noise_count)


# ---------------------------------------------------------------------------
# Common metadata used across all EXP collectors
# ---------------------------------------------------------------------------

# SHA-256 hashes verified in the EPIC-07 review documents. These are
# documentation constants; the actual values are validated by reading
# the manifest files. Listed here so collectors can fall back if a
# manifest is missing.
FE06_DATASET_SHA = "ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c"
FE06_METADATA_SHA = "c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2"
FE05_CANDIDATES_SHA = "df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649"
FRAMEWORK_CONFIG_SHA = "d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79"
EXP05_CONFIG_SHA = "3dec62060a5a6d1c09443debc51802f6f321e91f7dbbd792962e9b519afcda9e"

FEATURE_SET_RFM_EXTENDED = "rfm_extended"
FEATURE_SET_VERSION_FE06 = "FE06-v1.0"


def _common_exp_meta(manifest: dict[str, Any] | None) -> dict[str, Any]:
    """Pull common provenance fields from a manifest dict (if present)."""
    if not manifest:
        return {}
    return {
        "feature_set_sha256": manifest.get("input_sha256", MISSING),
        "customer_metadata_sha256": manifest.get("customer_metadata_sha256", MISSING),
        "config_sha256": manifest.get("config_sha256", MISSING),
        "input_sha256": manifest.get("input_sha256", MISSING),
        "library_versions": _jsonify(manifest.get("library_versions", {})),
        "platform": _jsonify(manifest.get("platform_info") or manifest.get("platform") or {}),
        "timestamp": (
            manifest.get("timestamp")
            or manifest.get("generated_at")
            or manifest.get("started_at")
            or manifest.get("completed_at")
            or MISSING
        ),
    }


def _common_preprocessing_meta() -> dict[str, str]:
    """Return the EXP-01/02/03 preprocessing default annotation.

    EXP-01/02/03 all operate on the already-prepared FE-06 final
    clustering dataset, so transformation/scaling/imputation are
    not re-applied at experiment time. The fields are marked as
    ``DIFFERENT_CONDITIONS`` with a documented reason pointing to
    FE-06 C7 (the upstream preprocessing layer).
    """
    return {
        "transformation": MISSING,
        "transformation_missing_reason": MISSING_REASON_DIFFERENT_CONDITIONS,
        "scaling": MISSING,
        "scaling_missing_reason": MISSING_REASON_DIFFERENT_CONDITIONS,
        "imputation": MISSING,
        "imputation_missing_reason": MISSING_REASON_DIFFERENT_CONDITIONS,
    }


# ---------------------------------------------------------------------------
# EXP-01 collector
# ---------------------------------------------------------------------------


def collect_exp01(reports_dir: Path) -> list[dict[str, Any]]:
    """Collect rows from EXP-01 baseline artifacts.

    Reads:
    - ``reports/exp01/exp01_baseline_summary.csv`` (per-algorithm summary)
    - ``reports/exp01/exp01_baseline_manifest.json`` (provenance)

    Granularity: PER_AGGREGATE — one row per algorithm (5 rows total).
    The summary CSV already aggregates over ``n_repeat=5`` runtime
    repeats and reports a single ``silhouette``/``DBI``/``CH``/``WCSS``
    per algorithm because the seeds are fixed.
    """
    reports_dir = Path(reports_dir)
    summary_csv = reports_dir / "exp01_baseline_summary.csv"
    manifest_json = reports_dir / "exp01_baseline_manifest.json"
    summary_path = summary_csv.relative_to(reports_dir.parent.parent).as_posix()

    if not summary_csv.exists():
        return []

    manifest = _safe_load_json(manifest_json) or {}
    common_meta = _common_exp_meta(manifest)
    preprocessing_meta = _common_preprocessing_meta()

    df = pd.read_csv(summary_csv)
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        algo = str(r.get("algorithm", ""))
        if not algo:
            continue
        row = _empty_row_template(SourceExperiment.EXP_01)
        row["record_granularity"] = "PER_AGGREGATE"
        row["repeat_index"] = 0
        row["n_repeats_total"] = _maybe_int(r.get("n_repeats_total")) or _maybe_int(
            manifest.get("config", {}).get("runtime_repeat")
        )
        row["experiment_id"] = f"EXP-01-{algo}"
        row["source_run_id"] = row["experiment_id"]
        row["source_block"] = ""

        row["algorithm"] = algo
        row["algorithm_missing_reason"] = ""

        row["dataset_version"] = FEATURE_SET_VERSION_FE06
        row["dataset_version_missing_reason"] = ""
        row["feature_set"] = FEATURE_SET_RFM_EXTENDED
        row["feature_set_missing_reason"] = ""

        row.update(preprocessing_meta)

        # n_clusters / n_clusters_realized
        n_clusters = _maybe_int(r.get("n_clusters"))
        row["n_clusters"] = n_clusters
        row["n_clusters_missing_reason"] = (
            "" if n_clusters is not None else MISSING_REASON_NOT_APPLICABLE
        )
        row["n_clusters_realized"] = n_clusters
        row["n_clusters_realized_missing_reason"] = (
            "" if n_clusters is not None else MISSING_REASON_NOT_APPLICABLE
        )

        # Cluster sizes — not separately recorded in EXP-01 baseline summary.
        # We have noise_count only for DBSCAN.
        if algo == "dbscan":
            noise_count = _maybe_int(r.get("noise_count")) or 0
            noise_ratio = _maybe_float(r.get("noise_ratio")) or 0.0
            row["noise_count"] = noise_count
            row["noise_count_missing_reason"] = ""
            row["noise_ratio"] = noise_ratio
            row["noise_ratio_missing_reason"] = ""
            # For DBSCAN we cannot derive cluster_size_largest/smallest from
            # the summary alone; mark as missing with appropriate reason.
            row["cluster_size_largest"] = MISSING
            row["cluster_size_largest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE
            row["cluster_size_smallest"] = MISSING
            row["cluster_size_smallest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE
        else:
            row["noise_count"] = 0
            row["noise_count_missing_reason"] = ""
            row["noise_ratio"] = 0.0
            row["noise_ratio_missing_reason"] = ""
            row["cluster_size_largest"] = MISSING
            row["cluster_size_largest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE
            row["cluster_size_smallest"] = MISSING
            row["cluster_size_smallest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE

        # random_seed — fixed at 42 in EXP-01 working defaults.
        random_seed = _maybe_int(r.get("random_seed")) or _maybe_int(
            manifest.get("config", {}).get("baseline_seed")
        )
        row["random_seed"] = random_seed
        row["random_seed_missing_reason"] = ""

        # Hyperparameters — pull from manifest's per-algorithm entry.
        hp_dict: dict[str, Any] = {}
        for entry in manifest.get("algorithms", []):
            if str(entry.get("algorithm", "")) == algo:
                hp_dict = dict(entry.get("hyperparameters", {}))
                break
        row["hyperparameters"] = _jsonify(hp_dict)
        row["hyperparameters_missing_reason"] = (
            "" if hp_dict else MISSING_REASON_FIELD_NOT_IN_SOURCE
        )

        # Metrics
        for metric, status_field in (
            ("silhouette", "silhouette_status"),
            ("davies_bouldin", "davies_bouldin_status"),
            ("calinski_harabasz", "calinski_harabasz_status"),
            ("wcss", "wcss_status"),
        ):
            v = _maybe_float(r.get(metric))
            row[metric] = v
            row[metric + "_missing_reason"] = "" if v is not None else MISSING_REASON_NOT_RECORDED
            row[status_field] = str(r.get(status_field) or MISSING)

        # Runtime — summary CSV stores runtime_mean/... columns; we use
        # the mean seconds value (consistent with ``execution_time_seconds``
        # semantics).
        runtime = _maybe_float(r.get("runtime_mean_seconds"))
        row["execution_time_seconds"] = runtime
        row["execution_time_seconds_missing_reason"] = (
            "" if runtime is not None else MISSING_REASON_NOT_RECORDED
        )

        row["run_status"] = str(r.get("status") or "SUCCESS")
        row["failure_reason"] = ""
        row["labels_hash"] = MISSING
        row["labels_hash_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["sigma"] = MISSING
        row["sigma_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["perturbation_seed"] = MISSING
        row["perturbation_seed_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["decision_status"] = "SUCCESS"
        row["evidence_note"] = ""

        # Provenance
        row.update(common_meta)
        row["source_artifact"] = summary_path
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# EXP-02 collector
# ---------------------------------------------------------------------------


def collect_exp02(reports_dir: Path) -> list[dict[str, Any]]:
    """Collect rows from EXP-02 cluster-number survey artifacts.

    Reads:
    - ``reports/exp02/exp02_cluster_number_summary.csv`` (per-config summary)
    - ``reports/exp02/exp02_manifest.json`` (provenance)

    Granularity: PER_AGGREGATE — one row per (algorithm, K).
    The summary CSV contains 37 rows (4 K-bearing algorithms × 9 K
    values + 1 DBSCAN diagnostic).
    """
    reports_dir = Path(reports_dir)
    summary_csv = reports_dir / "exp02_cluster_number_summary.csv"
    manifest_json = reports_dir / "exp02_manifest.json"
    summary_path = summary_csv.relative_to(reports_dir.parent.parent).as_posix()

    if not summary_csv.exists():
        return []

    manifest = _safe_load_json(manifest_json) or {}
    common_meta = _common_exp_meta(manifest)
    preprocessing_meta = _common_preprocessing_meta()

    df = pd.read_csv(summary_csv)
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        algo = str(r.get("algorithm", ""))
        if not algo:
            continue

        # EXP-02 row schema: experiment_id, algorithm, K, n_clusters, ...
        exp_id = str(r.get("experiment_id") or "")
        k_value = _maybe_int(r.get("K"))
        n_clusters_value = _maybe_int(r.get("n_clusters"))

        row = _empty_row_template(SourceExperiment.EXP_02)
        row["record_granularity"] = "PER_AGGREGATE"
        row["repeat_index"] = 0
        row["n_repeats_total"] = _maybe_int(manifest.get("config", {}).get("runtime_repeat"))
        row["experiment_id"] = exp_id
        row["source_run_id"] = exp_id
        row["source_block"] = ""

        row["algorithm"] = algo
        row["algorithm_missing_reason"] = ""

        row["dataset_version"] = FEATURE_SET_VERSION_FE06
        row["dataset_version_missing_reason"] = ""
        row["feature_set"] = FEATURE_SET_RFM_EXTENDED
        row["feature_set_missing_reason"] = ""

        row.update(preprocessing_meta)

        # n_clusters
        if n_clusters_value is not None:
            row["n_clusters"] = n_clusters_value
            row["n_clusters_missing_reason"] = ""
        elif k_value is not None:
            row["n_clusters"] = k_value
            row["n_clusters_missing_reason"] = ""
        else:
            row["n_clusters"] = MISSING
            row["n_clusters_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        # n_clusters_realized
        if n_clusters_value is not None:
            row["n_clusters_realized"] = n_clusters_value
            row["n_clusters_realized_missing_reason"] = ""
        else:
            row["n_clusters_realized"] = MISSING
            row["n_clusters_realized_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        # Cluster sizes / noise
        if algo == "dbscan":
            noise_count = _maybe_int(r.get("noise_count"))
            noise_ratio = _maybe_float(r.get("noise_ratio"))
            row["noise_count"] = noise_count if noise_count is not None else MISSING
            row["noise_count_missing_reason"] = (
                "" if noise_count is not None else MISSING_REASON_NOT_RECORDED
            )
            row["noise_ratio"] = noise_ratio if noise_ratio is not None else MISSING
            row["noise_ratio_missing_reason"] = (
                "" if noise_ratio is not None else MISSING_REASON_NOT_RECORDED
            )
        else:
            noise_count = _maybe_int(r.get("noise_count"))
            noise_ratio = _maybe_float(r.get("noise_ratio"))
            row["noise_count"] = noise_count if noise_count is not None else 0
            row["noise_count_missing_reason"] = "" if noise_count is not None else ""
            row["noise_ratio"] = noise_ratio if noise_ratio is not None else 0.0
            row["noise_ratio_missing_reason"] = "" if noise_ratio is not None else ""

        row["cluster_size_largest"] = MISSING
        row["cluster_size_largest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE
        row["cluster_size_smallest"] = MISSING
        row["cluster_size_smallest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE

        # random_seed (fixed at 42)
        random_seed = _maybe_int(r.get("random_seed")) or _maybe_int(
            manifest.get("config", {}).get("baseline_seed")
        )
        row["random_seed"] = random_seed if random_seed is not None else 42
        row["random_seed_missing_reason"] = (
            "" if random_seed is not None else MISSING_REASON_NOT_RECORDED
        )

        # Hyperparameters
        hp_dict: dict[str, Any] = {}
        for entry in manifest.get("results", []):
            if str(entry.get("experiment_id", "")) == exp_id:
                hp_dict = dict(entry.get("hyperparameters", {}))
                break
        # K-Means K is in hyperparameters.n_clusters; Agglomerative also.
        # Some EXP-02 entries store the K parameter as ``K`` instead of
        # ``n_clusters`` in the manifest; we add it explicitly.
        if k_value is not None and "n_clusters" not in hp_dict and "n_components" not in hp_dict:
            if algo in ("kmeans", "agglomerative", "fuzzy_cmeans"):
                hp_dict["n_clusters"] = k_value
            elif algo == "gmm":
                hp_dict["n_components"] = k_value
        row["hyperparameters"] = _jsonify(hp_dict)
        row["hyperparameters_missing_reason"] = (
            "" if hp_dict else MISSING_REASON_FIELD_NOT_IN_SOURCE
        )

        # Metrics
        for metric, status_field in (
            ("silhouette", "silhouette_status"),
            ("davies_bouldin", "davies_bouldin_status"),
            ("calinski_harabasz", "calinski_harabasz_status"),
            ("wcss", "wcss_status"),
        ):
            v = _maybe_float(r.get(metric))
            row[metric] = v
            row[metric + "_missing_reason"] = "" if v is not None else MISSING_REASON_NOT_RECORDED
            row[status_field] = str(r.get(status_field) or MISSING)

        runtime = _maybe_float(r.get("runtime_mean_seconds"))
        row["execution_time_seconds"] = runtime
        row["execution_time_seconds_missing_reason"] = (
            "" if runtime is not None else MISSING_REASON_NOT_RECORDED
        )

        row["run_status"] = str(r.get("status") or "SUCCESS")
        row["failure_reason"] = ""
        row["labels_hash"] = MISSING
        row["labels_hash_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["sigma"] = MISSING
        row["sigma_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["perturbation_seed"] = MISSING
        row["perturbation_seed_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["decision_status"] = "SUCCESS"
        row["evidence_note"] = ""

        # Provenance
        row.update(common_meta)
        row["source_artifact"] = summary_path
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# EXP-03 collector
# ---------------------------------------------------------------------------


def collect_exp03(reports_dir: Path) -> list[dict[str, Any]]:
    """Collect rows from EXP-03 hyperparameter-search artifacts.

    Reads:
    - ``reports/exp03/exp03_hyperparameter_results.csv`` (per-run results)
    - ``reports/exp03/exp03_manifest.json`` (provenance)

    Granularity: PER_RUN — one row per (algorithm, stage, sweep_parameter,
    sweep_value, repeat_index). Stage A is a single repeat; Stage B/C are
    per parameter-value.
    """
    reports_dir = Path(reports_dir)
    summary_csv = reports_dir / "exp03_hyperparameter_results.csv"
    manifest_json = reports_dir / "exp03_manifest.json"
    summary_path = summary_csv.relative_to(reports_dir.parent.parent).as_posix()

    if not summary_csv.exists():
        return []

    manifest = _safe_load_json(manifest_json) or {}
    common_meta = _common_exp_meta(manifest)
    preprocessing_meta = _common_preprocessing_meta()

    df = pd.read_csv(summary_csv)
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        algo = str(r.get("algorithm", ""))
        if not algo:
            continue
        exp_id = str(r.get("experiment_id") or "")
        stage = str(r.get("stage") or "")
        sweep_parameter = r.get("sweep_parameter")
        sweep_value = r.get("sweep_value")
        baseline_k = _maybe_int(r.get("baseline_k"))
        n_clusters = _maybe_int(r.get("n_clusters"))

        row = _empty_row_template(SourceExperiment.EXP_03)
        row["record_granularity"] = "PER_RUN"
        row["repeat_index"] = 0  # EXP-03 reports aggregated per config
        row["n_repeats_total"] = _maybe_int(manifest.get("config", {}).get("runtime_repeat"))
        row["experiment_id"] = exp_id
        row["source_run_id"] = exp_id
        row["source_block"] = ""

        row["algorithm"] = algo
        row["algorithm_missing_reason"] = ""

        row["dataset_version"] = FEATURE_SET_VERSION_FE06
        row["dataset_version_missing_reason"] = ""
        row["feature_set"] = FEATURE_SET_RFM_EXTENDED
        row["feature_set_missing_reason"] = ""

        row.update(preprocessing_meta)

        # n_clusters
        if n_clusters is not None:
            row["n_clusters"] = n_clusters
            row["n_clusters_missing_reason"] = ""
        elif baseline_k is not None:
            row["n_clusters"] = baseline_k
            row["n_clusters_missing_reason"] = ""
        else:
            row["n_clusters"] = MISSING
            row["n_clusters_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        row["n_clusters_realized"] = n_clusters if n_clusters is not None else MISSING
        row["n_clusters_realized_missing_reason"] = (
            "" if n_clusters is not None else MISSING_REASON_NOT_APPLICABLE
        )

        # Cluster sizes
        row["cluster_size_largest"] = MISSING
        row["cluster_size_largest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE
        row["cluster_size_smallest"] = MISSING
        row["cluster_size_smallest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE

        # Noise (none in EXP-03 by design)
        row["noise_count"] = 0
        row["noise_count_missing_reason"] = ""
        row["noise_ratio"] = 0.0
        row["noise_ratio_missing_reason"] = ""

        # random_seed
        random_seed = _maybe_int(r.get("hp_random_state"))
        row["random_seed"] = random_seed if random_seed is not None else 42
        row["random_seed_missing_reason"] = (
            "" if random_seed is not None else MISSING_REASON_NOT_RECORDED
        )

        # Hyperparameters — EXP-03 results CSV has individual hp_* columns.
        hp_keys = [
            "hp_init",
            "hp_max_iter",
            "hp_n_clusters",
            "hp_n_init",
            "hp_random_state",
            "hp_tol",
            "hp_compute_distances",
            "hp_linkage",
            "hp_metric",
            "hp_eps",
            "hp_min_samples",
            "hp_covariance_type",
            "hp_init_params",
            "hp_n_components",
            "hp_reg_covar",
            "hp_error",
            "hp_m",
        ]
        hp_dict: dict[str, Any] = {}
        for k in hp_keys:
            v = r.get(k)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                hp_dict[k.replace("hp_", "")] = v
        if sweep_parameter is not None and not (
            isinstance(sweep_parameter, float) and np.isnan(sweep_parameter)
        ):
            hp_dict["_sweep_parameter"] = str(sweep_parameter)
            if sweep_value is not None and not (
                isinstance(sweep_value, float) and np.isnan(sweep_value)
            ):
                hp_dict["_sweep_value"] = sweep_value
            hp_dict["_stage"] = stage
        row["hyperparameters"] = _jsonify(hp_dict)
        row["hyperparameters_missing_reason"] = (
            "" if hp_dict else MISSING_REASON_FIELD_NOT_IN_SOURCE
        )

        # Metrics
        for metric, status_field in (
            ("silhouette", "silhouette_status"),
            ("davies_bouldin", "davies_bouldin_status"),
            ("calinski_harabasz", "calinski_harabasz_status"),
            ("wcss", "wcss_status"),
        ):
            v = _maybe_float(r.get(metric))
            row[metric] = v
            row[metric + "_missing_reason"] = "" if v is not None else MISSING_REASON_NOT_RECORDED
            row[status_field] = str(r.get(status_field) or MISSING)

        runtime = _maybe_float(r.get("runtime_mean_seconds"))
        row["execution_time_seconds"] = runtime
        row["execution_time_seconds_missing_reason"] = (
            "" if runtime is not None else MISSING_REASON_NOT_RECORDED
        )

        row["run_status"] = str(r.get("status") or "SUCCESS")
        row["failure_reason"] = ""
        row["labels_hash"] = MISSING
        row["labels_hash_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["sigma"] = MISSING
        row["sigma_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["perturbation_seed"] = MISSING
        row["perturbation_seed_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        row["decision_status"] = "SUCCESS"
        row["evidence_note"] = ""

        row.update(common_meta)
        row["source_artifact"] = summary_path
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# EXP-04 collector
# ---------------------------------------------------------------------------


def collect_exp04(reports_dir: Path) -> list[dict[str, Any]]:
    """Collect rows from EXP-04 preprocessing sensitivity artifacts.

    Reads:
    - ``reports/exp04/exp04_scenario_results.csv`` (per-run results)
    - ``reports/exp04/exp04_manifest.json`` (provenance)

    Granularity: PER_RUN — 30 rows (6 scenarios × 5 repeats).
    """
    reports_dir = Path(reports_dir)
    summary_csv = reports_dir / "exp04_scenario_results.csv"
    manifest_json = reports_dir / "exp04_manifest.json"
    summary_path = summary_csv.relative_to(reports_dir.parent.parent).as_posix()

    if not summary_csv.exists():
        return []

    manifest = _safe_load_json(manifest_json) or {}
    common_meta = _common_exp_meta(manifest)
    # EXP-04 uses the pre-transform dataset (FE-05 candidate output)
    # so dataset_version / feature_set_sha256 in the manifest differ
    # from EXP-01/02/03/05.
    feature_set_sha = (
        manifest.get("feature_set_sha256") or manifest.get("input_sha256") or FE05_CANDIDATES_SHA
    )
    common_meta["feature_set_sha256"] = feature_set_sha
    common_meta["input_sha256"] = manifest.get("input_sha256", feature_set_sha)

    df = pd.read_csv(summary_csv)
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        algo = str(r.get("algorithm", ""))
        if not algo:
            continue
        scenario_id = str(r.get("scenario_id") or "")
        config_id = str(r.get("config_id") or "")
        repeat_index = _maybe_int(r.get("repeat_index"))
        n_clusters = _maybe_int(r.get("n_clusters"))
        n_clusters_realized = _maybe_int(r.get("n_clusters_realized"))

        transformation = r.get("transformation")
        scaling = r.get("scaling")
        imputation = r.get("imputation")

        row = _empty_row_template(SourceExperiment.EXP_04)
        row["record_granularity"] = "PER_RUN"
        row["repeat_index"] = repeat_index if repeat_index is not None else 0
        row["n_repeats_total"] = _maybe_int(r.get("n_total_repeats")) or 5
        row["experiment_id"] = (
            f"{scenario_id}-r{row['repeat_index']:02d}" if scenario_id else MISSING
        )
        row["experiment_id_missing_reason"] = "" if scenario_id else MISSING_REASON_NOT_RECORDED
        row["source_run_id"] = row["experiment_id"]
        row["source_block"] = ""

        row["algorithm"] = algo
        row["algorithm_missing_reason"] = ""
        row["dataset_version"] = FEATURE_SET_VERSION_FE06
        row["dataset_version_missing_reason"] = ""
        row["feature_set"] = str(r.get("feature_set") or FEATURE_SET_RFM_EXTENDED)
        row["feature_set_missing_reason"] = (
            "" if r.get("feature_set") is not None else MISSING_REASON_FIELD_NOT_IN_SOURCE
        )

        # Preprocessing fields — EXP-04 actually records these.
        _set_with_reason(row, "transformation", transformation)
        _set_with_reason(row, "scaling", scaling)
        _set_with_reason(row, "imputation", imputation)

        # n_clusters
        if n_clusters is not None:
            row["n_clusters"] = n_clusters
            row["n_clusters_missing_reason"] = ""
        else:
            row["n_clusters"] = MISSING
            row["n_clusters_missing_reason"] = MISSING_REASON_NOT_RECORDED

        if n_clusters_realized is not None:
            row["n_clusters_realized"] = n_clusters_realized
            row["n_clusters_realized_missing_reason"] = ""
        else:
            row["n_clusters_realized"] = MISSING
            row["n_clusters_realized_missing_reason"] = MISSING_REASON_NOT_RECORDED

        # Cluster sizes are NOT recorded per-run in EXP-04. The aggregate
        # CSV contains per-scenario n_successful_repeats but not the
        # individual cluster sizes.
        row["cluster_size_largest"] = MISSING
        row["cluster_size_largest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE
        row["cluster_size_smallest"] = MISSING
        row["cluster_size_smallest_missing_reason"] = MISSING_REASON_FIELD_NOT_IN_SOURCE

        row["noise_count"] = 0
        row["noise_count_missing_reason"] = ""
        row["noise_ratio"] = 0.0
        row["noise_ratio_missing_reason"] = ""

        random_seed = _maybe_int(r.get("random_seed"))
        row["random_seed"] = random_seed if random_seed is not None else 42
        row["random_seed_missing_reason"] = (
            "" if random_seed is not None else MISSING_REASON_NOT_RECORDED
        )

        # EXP-04 K-Means hyperparameters are EXP-01 working defaults.
        hp_dict: dict[str, Any] = {
            "n_clusters": n_clusters,
            "init": "k-means++",
            "n_init": 10,
            "max_iter": 300,
            "tol": 0.0001,
            "random_state": random_seed,
            "_config_id": config_id,
            "_role": str(r.get("role") or ""),
        }
        row["hyperparameters"] = _jsonify(hp_dict)
        row["hyperparameters_missing_reason"] = ""

        # Metrics
        for metric, status_field in (
            ("silhouette", "silhouette_status"),
            ("davies_bouldin", "davies_bouldin_status"),
            ("calinski_harabasz", "calinski_harabasz_status"),
            ("wcss", "wcss_status"),
        ):
            v = _maybe_float(r.get(metric))
            row[metric] = v
            row[metric + "_missing_reason"] = "" if v is not None else MISSING_REASON_NOT_RECORDED
            row[status_field] = str(r.get(status_field) or MISSING)

        runtime = _maybe_float(r.get("runtime_seconds"))
        row["execution_time_seconds"] = runtime
        row["execution_time_seconds_missing_reason"] = (
            "" if runtime is not None else MISSING_REASON_NOT_RECORDED
        )

        row["run_status"] = str(r.get("status") or "SUCCESS")
        row["failure_reason"] = str(r.get("failure_reason") or "")
        row["labels_hash"] = str(r.get("labels_hash") or MISSING)
        row["labels_hash_missing_reason"] = (
            "" if r.get("labels_hash") else MISSING_REASON_NOT_RECORDED
        )
        row["sigma"] = MISSING
        row["sigma_missing_reason"] = MISSING_REASON_NOT_APPLICABLE
        row["perturbation_seed"] = MISSING
        row["perturbation_seed_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        row["decision_status"] = str(r.get("decision_status") or "CANDIDATE_SCENARIO")
        row["evidence_note"] = str(r.get("evidence_note") or "")

        row.update(common_meta)
        row["source_artifact"] = summary_path
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# EXP-05 collector
# ---------------------------------------------------------------------------


def _collect_exp05_block(
    df: pd.DataFrame,
    *,
    block: str,
    source_path: str,
) -> list[dict[str, Any]]:
    """Internal helper to convert an EXP-05 per-block CSV to schema rows."""
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        algo = str(r.get("algorithm", ""))
        if not algo:
            continue

        repeat_index = _maybe_int(r.get("repeat_index"))
        seed = _maybe_int(r.get("seed"))
        sigma = _maybe_float(r.get("sigma"))
        perturbation_seed = _maybe_int(r.get("perturbation_seed"))

        # Compute cluster sizes from the cluster_sizes JSON dict.
        n_clusters_realized, cluster_size_largest, cluster_size_smallest, noise_count = (
            _extract_cluster_sizes(r.get("cluster_sizes"))
        )
        # Some EXP-05 rows also have explicit noise_count / noise_ratio columns.
        if r.get("noise_count") is not None and not (
            isinstance(r.get("noise_count"), float) and np.isnan(r.get("noise_count"))
        ):
            noise_count = _maybe_int(r.get("noise_count"))
        noise_ratio = _maybe_float(r.get("noise_ratio"))

        run_id = str(r.get("run_id") or "")
        exp_id = run_id
        n_clusters_input = _maybe_int(r.get("n_clusters_realized"))

        row = _empty_row_template(SourceExperiment.EXP_05)
        row["record_granularity"] = "PER_RUN"
        row["repeat_index"] = repeat_index if repeat_index is not None else 0
        row["n_repeats_total"] = _maybe_int(r.get("n_repeat")) or (5 if block == "R" else 1)
        row["experiment_id"] = exp_id
        row["experiment_id_missing_reason"] = ""
        row["source_run_id"] = run_id
        row["source_block"] = block

        row["algorithm"] = algo
        row["algorithm_missing_reason"] = ""
        row["dataset_version"] = str(r.get("feature_set") or FEATURE_SET_VERSION_FE06)
        row["dataset_version_missing_reason"] = ""
        row["feature_set"] = FEATURE_SET_RFM_EXTENDED
        row["feature_set_missing_reason"] = ""

        # EXP-05 operates on the FE-06 final clustering dataset.
        row["transformation"] = MISSING
        row["transformation_missing_reason"] = MISSING_REASON_DIFFERENT_CONDITIONS
        row["scaling"] = MISSING
        row["scaling_missing_reason"] = MISSING_REASON_DIFFERENT_CONDITIONS
        row["imputation"] = MISSING
        row["imputation_missing_reason"] = MISSING_REASON_DIFFERENT_CONDITIONS

        # n_clusters
        if n_clusters_input is not None:
            row["n_clusters"] = n_clusters_input
            row["n_clusters_missing_reason"] = ""
        else:
            row["n_clusters"] = MISSING
            row["n_clusters_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        if n_clusters_realized is not None:
            row["n_clusters_realized"] = n_clusters_realized
            row["n_clusters_realized_missing_reason"] = ""
        else:
            row["n_clusters_realized"] = MISSING
            row["n_clusters_realized_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        row["cluster_size_largest"] = (
            cluster_size_largest if cluster_size_largest is not None else MISSING
        )
        row["cluster_size_largest_missing_reason"] = (
            "" if cluster_size_largest is not None else MISSING_REASON_FIELD_NOT_IN_SOURCE
        )
        row["cluster_size_smallest"] = (
            cluster_size_smallest if cluster_size_smallest is not None else MISSING
        )
        row["cluster_size_smallest_missing_reason"] = (
            "" if cluster_size_smallest is not None else MISSING_REASON_FIELD_NOT_IN_SOURCE
        )

        if noise_count is not None:
            row["noise_count"] = noise_count
            row["noise_count_missing_reason"] = ""
        else:
            row["noise_count"] = MISSING
            row["noise_count_missing_reason"] = MISSING_REASON_NOT_RECORDED

        if noise_ratio is not None:
            row["noise_ratio"] = noise_ratio
            row["noise_ratio_missing_reason"] = ""
        else:
            row["noise_ratio"] = MISSING
            row["noise_ratio_missing_reason"] = MISSING_REASON_NOT_RECORDED

        row["random_seed"] = seed if seed is not None else MISSING
        row["random_seed_missing_reason"] = (
            "" if seed is not None else MISSING_REASON_NOT_APPLICABLE
        )

        # Hyperparameters — pull from per-record hp dict (if available).
        hp_str = r.get("hyperparameters")
        if hp_str is None or (isinstance(hp_str, float) and np.isnan(hp_str)):
            hp_dict: dict[str, Any] = {}
        elif isinstance(hp_str, dict):
            hp_dict = dict(hp_str)
        else:
            try:
                hp_dict = json.loads(str(hp_str))
            except (json.JSONDecodeError, TypeError):
                hp_dict = {}
        row["hyperparameters"] = _jsonify(hp_dict)
        row["hyperparameters_missing_reason"] = (
            "" if hp_dict else MISSING_REASON_FIELD_NOT_IN_SOURCE
        )

        # Metrics
        for metric, status_field in (
            ("silhouette", "silhouette_status"),
            ("davies_bouldin", "davies_bouldin_status"),
            ("calinski_harabasz", "calinski_harabasz_status"),
            ("wcss", "wcss_status"),
        ):
            v = _maybe_float(r.get(metric))
            row[metric] = v
            row[metric + "_missing_reason"] = "" if v is not None else MISSING_REASON_NOT_RECORDED
            row[status_field] = str(r.get(status_field) or MISSING)

        runtime = _maybe_float(r.get("runtime_seconds"))
        row["execution_time_seconds"] = runtime
        row["execution_time_seconds_missing_reason"] = (
            "" if runtime is not None else MISSING_REASON_NOT_RECORDED
        )

        row["run_status"] = str(r.get("status") or "SUCCESS")
        row["failure_reason"] = str(r.get("failure_reason") or "")
        row["labels_hash"] = str(r.get("labels_hash") or MISSING)
        row["labels_hash_missing_reason"] = (
            "" if r.get("labels_hash") else MISSING_REASON_NOT_RECORDED
        )

        if sigma is not None:
            row["sigma"] = sigma
            row["sigma_missing_reason"] = ""
        else:
            row["sigma"] = MISSING
            row["sigma_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        if perturbation_seed is not None:
            row["perturbation_seed"] = perturbation_seed
            row["perturbation_seed_missing_reason"] = ""
        else:
            row["perturbation_seed"] = MISSING
            row["perturbation_seed_missing_reason"] = MISSING_REASON_NOT_APPLICABLE

        # Provenance
        row["feature_set_sha256"] = str(r.get("feature_set_sha256") or MISSING)
        row["customer_metadata_sha256"] = str(r.get("customer_metadata_sha256") or MISSING)
        row["config_sha256"] = str(r.get("config_sha256") or MISSING)
        row["input_sha256"] = str(r.get("feature_set_sha256") or MISSING)
        row["library_versions"] = _jsonify(r.get("library_versions") or {})
        row["platform"] = _jsonify(r.get("platform_info") or {})
        row["timestamp"] = MISSING
        row["decision_status"] = ""
        row["evidence_note"] = ""
        row["source_artifact"] = source_path
        rows.append(row)
    return rows


def collect_exp05(reports_dir: Path) -> list[dict[str, Any]]:
    """Collect rows from EXP-05 reproducibility / stability evidence.

    Reads:
    - ``reports/exp05/exp05_reproducibility_results.csv`` (Block R)
    - ``reports/exp05/exp05_seed_sweep_results.csv`` (Block S)
    - ``reports/exp05/exp05_noise_perturbation_results.csv`` (Block N)

    Granularity: PER_RUN — 75 rows total.
    """
    reports_dir = Path(reports_dir)
    sources = [
        ("R", "exp05_reproducibility_results.csv"),
        ("S", "exp05_seed_sweep_results.csv"),
        ("N", "exp05_noise_perturbation_results.csv"),
    ]
    rows: list[dict[str, Any]] = []
    for block, filename in sources:
        path = reports_dir / filename
        if not path.exists():
            continue
        df = pd.read_csv(path)
        rel = path.relative_to(reports_dir.parent.parent).as_posix()
        rows.extend(
            _collect_exp05_block(
                df,
                block=block,
                source_path=rel,
            )
        )
    return rows
