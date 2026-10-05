#!/usr/bin/env python3
"""EXP-05 Stability & Reproducibility Runner.

CLI entry point for EXP-05. EXP-05 generates raw stability and
reproducibility evidence across three blocks:

- Block R — Reproducibility: 5 algorithms × n_repeat=5 × seed=42.
- Block S — Random Seed Stability: K-Means + GMM + FCM × 5 seeds.
- Block N — Feature Perturbation: in-memory Gaussian noise on
  the FE-06 final clustering matrix at sigma = 0, 0.01, 0.05 × std.

This script performs the FULL EXP-05 research execution only when
explicitly invoked. Implementation-only phases must call the
underlying module directly without invoking this CLI.

Hard constraints (AGENTS.md §2, EXP-05 Plan R1):

- FE-05 / FE-06 outputs are READ-ONLY. SHA-256 verified before
  and after the run.
- In-memory perturbation only. NO perturbed dataset on disk.
- EXP-05 does NOT compute ARI / AMI / Hungarian / statistical
  tests / confidence intervals (EPIC-08 scope).
- Decision status uses ONLY the taxonomy:
  REPRODUCIBILITY_VERIFIED, REPRODUCIBILITY_FAILED,
  STABILITY_EVIDENCE_GENERATED, PERTURBATION_EVIDENCE_GENERATED,
  SIGMA_ZERO_BASELINE_MATCH, SIGMA_ZERO_BASELINE_MISMATCH,
  PENDING_REVIEW.
- No "best/optimal/superior/winner/recommended/final" labels.
- No composite scoring, no algorithm ranking, no K-sweep.

Output artifacts (under reports/exp05/):

- exp05_manifest.json
- exp05_run_summary.json
- exp05_reproducibility_results.csv           (per algorithm × repeat)
- exp05_reproducibility_aggregate.csv        (per algorithm)
- exp05_seed_sweep_results.csv               (per algorithm × seed)
- exp05_seed_sweep_aggregate.csv             (per algorithm)
- exp05_noise_perturbation_results.csv       (per algorithm × sigma × pseed)
- exp05_noise_perturbation_aggregate.csv      (per algorithm × sigma)
- exp05_cluster_size_consistency.csv          (cluster size snapshot)
- exp05_cluster_labels.parquet               (REQUIRED for EPIC-08)
- exp05_pending_review.json
- exp05_analysis.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

# Add src to path
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.clustering.config import (  # noqa: E402
    compute_text_sha256,
    load_framework_config,
)
from customer_segmentation.clustering.stability import (  # noqa: E402
    BLOCK_N,
    BLOCK_R,
    BLOCK_S,
    FORBIDDEN_DECISION_LABELS,
    PERMITTED_DECISION_STATUSES,
    BlockNAggregate,
    BlockNRecord,
    BlockRAggregate,
    BlockRRecord,
    BlockSAggregate,
    BlockSRecord,
    LabelArtifactRow,
    StabilityReproducibilityRunner,
    StabilityResult,
)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_EXP05_CONFIG_PATH = _REPO_ROOT / "configs" / "exp05_stability_reproducibility.yaml"
_FRAMEWORK_CONFIG_PATH = _REPO_ROOT / "configs" / "clustering.yaml"
_FE06_DATASET_PATH = _REPO_ROOT / "data" / "processed" / "final_clustering_dataset.parquet"
_FE06_METADATA_PATH = _REPO_ROOT / "data" / "processed" / "customer_metadata.parquet"
_REPORTS_DIR = _REPO_ROOT / "reports" / "exp05"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _library_versions() -> dict[str, str]:
    """Snapshot versions of libraries EXP-05 depends on."""
    import numpy
    import pandas
    import pyarrow
    import scipy
    import sklearn

    return {
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "pyarrow": pyarrow.__version__,
    }


def _platform_info() -> dict[str, str]:
    """Snapshot Python / OS environment."""
    import platform as platform_module

    return {
        "python": platform_module.python_version(),
        "system": platform_module.system(),
        "release": platform_module.release(),
        "machine": platform_module.machine(),
    }


def _write_json(data: dict[str, Any], path: Path) -> None:
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=False, default=str)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def _write_markdown(content: str, path: Path) -> None:
    """Write Markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Per-record serialisation
# ---------------------------------------------------------------------------


def _record_to_dict(r: BlockRRecord | BlockSRecord | BlockNRecord) -> dict[str, Any]:
    """Serialise a per-record dataclass to JSON-friendly dict.

    ``cluster_labels`` is intentionally NOT serialised.
    """
    return {
        "run_id": r.run_id,
        "block": r.block,
        "algorithm": r.algorithm,
        "seed": int(r.seed),
        "repeat_index": int(r.repeat_index),
        "feature_set": r.feature_set,
        "feature_set_sha256": r.feature_set_sha256,
        "customer_metadata_sha256": r.customer_metadata_sha256,
        "config_sha256": r.config_sha256,
        "hyperparameters": r.hyperparameters,
        "status": r.status,
        "failure_reason": r.failure_reason,
        "silhouette": r.silhouette,
        "silhouette_status": r.silhouette_status,
        "davies_bouldin": r.davies_bouldin,
        "davies_bouldin_status": r.davies_bouldin_status,
        "calinski_harabasz": r.calinski_harabasz,
        "calinski_harabasz_status": r.calinski_harabasz_status,
        "wcss": r.wcss,
        "wcss_status": r.wcss_status,
        "runtime_seconds": r.runtime_seconds,
        "labels_hash": r.labels_hash,
        "n_clusters_realized": r.n_clusters_realized,
        "noise_count": r.noise_count,
        "noise_ratio": r.noise_ratio,
        "cluster_sizes": r.cluster_sizes,
        "sigma": getattr(r, "sigma", None),
        "perturbation_seed": getattr(r, "perturbation_seed", None),
        "library_versions": r.library_versions,
        "platform_info": r.platform_info,
    }


def _block_r_aggregate_to_dict(a: BlockRAggregate) -> dict[str, Any]:
    return {
        "algorithm": a.algorithm,
        "n_repeat": a.n_repeat,
        "n_successful": a.n_successful,
        "n_failed": a.n_failed,
        "silhouette_stats": a.silhouette_stats,
        "davies_bouldin_stats": a.davies_bouldin_stats,
        "calinski_harabasz_stats": a.calinski_harabasz_stats,
        "wcss_stats": a.wcss_stats,
        "runtime_stats": a.runtime_stats,
        "labels_hash_unique_count": a.labels_hash_unique_count,
        "n_clusters_unique_count": a.n_clusters_unique_count,
        "labels_hash_values": a.labels_hash_values,
        "decision_status": a.decision_status,
        "evidence_note": a.evidence_note,
    }


def _block_s_aggregate_to_dict(a: BlockSAggregate) -> dict[str, Any]:
    return {
        "algorithm": a.algorithm,
        "n_seeds": a.n_seeds,
        "n_successful": a.n_successful,
        "n_failed": a.n_failed,
        "silhouette_stats": a.silhouette_stats,
        "davies_bouldin_stats": a.davies_bouldin_stats,
        "calinski_harabasz_stats": a.calinski_harabasz_stats,
        "wcss_stats": a.wcss_stats,
        "runtime_stats": a.runtime_stats,
        "labels_hash_unique_count": a.labels_hash_unique_count,
        "n_clusters_unique_count": a.n_clusters_unique_count,
        "labels_hash_values": a.labels_hash_values,
        "cluster_size_distributions": a.cluster_size_distributions,
        "decision_status": a.decision_status,
        "evidence_note": a.evidence_note,
    }


def _block_n_aggregate_to_dict(a: BlockNAggregate) -> dict[str, Any]:
    return {
        "algorithm": a.algorithm,
        "sigma": a.sigma,
        "n_perturbation_seeds": a.n_perturbation_seeds,
        "n_successful": a.n_successful,
        "n_failed": a.n_failed,
        "silhouette_stats": a.silhouette_stats,
        "davies_bouldin_stats": a.davies_bouldin_stats,
        "calinski_harabasz_stats": a.calinski_harabasz_stats,
        "wcss_stats": a.wcss_stats,
        "runtime_stats": a.runtime_stats,
        "labels_hash_unique_count": a.labels_hash_unique_count,
        "n_clusters_unique_count": a.n_clusters_unique_count,
        "labels_hash_values": a.labels_hash_values,
        "sigma_zero_baseline_match": a.sigma_zero_baseline_match,
        "decision_status": a.decision_status,
        "evidence_note": a.evidence_note,
    }


# ---------------------------------------------------------------------------
# CSV dataframes
# ---------------------------------------------------------------------------


def _block_r_results_dataframe(records: list[BlockRRecord]) -> pd.DataFrame:
    """Block R per-repeat CSV."""
    rows = [_record_to_dict(r) for r in records]
    for r in rows:
        r.pop("library_versions", None)
        r.pop("platform_info", None)
        r.pop("hyperparameters", None)
    return pd.DataFrame(rows)


def _block_r_aggregate_dataframe(aggregates: list[BlockRAggregate]) -> pd.DataFrame:
    rows = [_block_r_aggregate_to_dict(a) for a in aggregates]
    return pd.DataFrame(rows)


def _block_s_results_dataframe(records: list[BlockSRecord]) -> pd.DataFrame:
    """Block S per-seed CSV."""
    rows = [_record_to_dict(r) for r in records]
    for r in rows:
        r.pop("library_versions", None)
        r.pop("platform_info", None)
        r.pop("hyperparameters", None)
    return pd.DataFrame(rows)


def _block_s_aggregate_dataframe(aggregates: list[BlockSAggregate]) -> pd.DataFrame:
    rows = [_block_s_aggregate_to_dict(a) for a in aggregates]
    return pd.DataFrame(rows)


def _block_n_results_dataframe(records: list[BlockNRecord]) -> pd.DataFrame:
    """Block N per-(algorithm × sigma × perturbation_seed) CSV."""
    rows = [_record_to_dict(r) for r in records]
    for r in rows:
        r.pop("library_versions", None)
        r.pop("platform_info", None)
        r.pop("hyperparameters", None)
    return pd.DataFrame(rows)


def _block_n_aggregate_dataframe(aggregates: list[BlockNAggregate]) -> pd.DataFrame:
    rows = [_block_n_aggregate_to_dict(a) for a in aggregates]
    return pd.DataFrame(rows)


def _cluster_size_consistency_dataframe(
    result: StabilityResult,
) -> pd.DataFrame:
    """Build a flat cross-block cluster size distribution snapshot."""
    rows: list[dict[str, Any]] = []
    for records, block in (
        (result.block_r_records, BLOCK_R),
        (result.block_s_records, BLOCK_S),
        (result.block_n_records, BLOCK_N),
    ):
        for r in records:
            if r.status != "SUCCESS":
                continue
            for cluster_id, count in r.cluster_sizes.items():
                rows.append(
                    {
                        "block": block,
                        "run_id": r.run_id,
                        "algorithm": r.algorithm,
                        "seed": r.seed,
                        "sigma": (
                            float(r.sigma) if getattr(r, "sigma", None) is not None else None
                        ),
                        "perturbation_seed": getattr(r, "perturbation_seed", None),
                        "repeat_index": r.repeat_index,
                        "cluster_id": cluster_id,
                        "customer_count": int(count),
                    }
                )
    return pd.DataFrame(rows)


def _label_artifact_dataframe(rows: list[LabelArtifactRow]) -> pd.DataFrame:
    """Build the parquet-ready DataFrame from LabelArtifactRow objects."""
    data = [
        {
            "run_id": r.run_id,
            "block": r.block,
            "algorithm": r.algorithm,
            "seed": int(r.seed),
            "sigma": (
                float(r.sigma)
                if r.sigma is not None and not (isinstance(r.sigma, float) and pd.isna(r.sigma))
                else None
            ),
            "perturbation_seed": (
                int(r.perturbation_seed) if r.perturbation_seed is not None else None
            ),
            "repeat_index": int(r.repeat_index),
            "CustomerID": int(r.customer_id),
            "cluster_label": int(r.cluster_label),
        }
        for r in rows
    ]
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Manifest / run summary / pending review
# ---------------------------------------------------------------------------


def _generate_manifest(
    result: StabilityResult,
    config_sha: str,
    input_sha: str,
    metadata_sha: str,
    input_integrity_ok: bool,
    pre_run_shas: dict[str, str],
    post_run_shas: dict[str, str],
) -> dict[str, Any]:
    """Generate the EXP-05 manifest JSON."""
    return {
        "experiment_id": "EXP-05",
        "name": "EXP-05 Stability & Reproducibility",
        "description": (
            "Generate raw stability and reproducibility evidence across "
            "Block R (reproducibility), Block S (random seed stability), "
            "and Block N (feature perturbation) for the five EPIC-06 "
            "benchmark algorithms on the FE-06 final clustering matrix."
        ),
        "plan_revision": "R1",
        "timestamp": _now_utc_iso(),
        "feature_set": result.feature_set,
        "feature_set_sha256": result.feature_set_sha256,
        "customer_metadata_sha256": result.customer_metadata_sha256,
        "input_sha256": input_sha,
        "config_sha256": config_sha,
        "exp05_config_sha256": result.exp05_config_sha256,
        "library_versions": result.library_versions,
        "platform_info": result.platform_info,
        "input_integrity_verified": input_integrity_ok,
        "pre_run_shas": pre_run_shas,
        "post_run_shas": post_run_shas,
        "block_r": {
            "algorithms": sorted({r.algorithm for r in result.block_r_records}),
            "seed": result.block_r_seed,
            "n_repeat": result.block_r_n_repeat,
            "n_records": len(result.block_r_records),
            "n_successful_records": sum(1 for r in result.block_r_records if r.status == "SUCCESS"),
            "n_aggregates": len(result.block_r_aggregates),
        },
        "block_s": {
            "algorithms": sorted({r.algorithm for r in result.block_s_records}),
            "seeds": list(result.block_s_seeds),
            "n_repeat_per_seed": result.block_s_n_repeat,
            "n_records": len(result.block_s_records),
            "n_successful_records": sum(1 for r in result.block_s_records if r.status == "SUCCESS"),
            "n_aggregates": len(result.block_s_aggregates),
        },
        "block_n": {
            "algorithms": sorted({r.algorithm for r in result.block_n_records}),
            "algorithm_seed": result.block_n_algorithm_seed,
            "sigma_grid": list(result.block_n_sigma_grid),
            "perturbation_seeds": list(result.block_n_perturbation_seeds),
            "n_records": len(result.block_n_records),
            "n_successful_records": sum(1 for r in result.block_n_records if r.status == "SUCCESS"),
            "n_aggregates": len(result.block_n_aggregates),
        },
        "labels_artifact": {
            "filename": "exp05_cluster_labels.parquet",
            "rows": len(result.label_artifact_rows),
            "schema": [
                "run_id",
                "block",
                "algorithm",
                "seed",
                "sigma",
                "perturbation_seed",
                "repeat_index",
                "CustomerID",
                "cluster_label",
            ],
        },
        "decision_status_options": sorted(PERMITTED_DECISION_STATUSES),
        "forbidden_decision_labels": sorted(FORBIDDEN_DECISION_LABELS),
        "scope_boundaries": [
            "Block R = REPRODUCIBILITY_VERIFICATION (5 algorithms × n_repeat=5, seed=42). NOT stability analysis.",
            "Block S = STABILITY_EVIDENCE_GENERATION (K-Means + GMM + FCM × 5 seeds). Agglomerative + DBSCAN are deterministic and NOT included.",
            "Block N = PERTURBATION_EVIDENCE_GENERATION (5 algorithms × sigma=[0, 0.01, 0.05] × std). In-memory only. NO persistence of perturbed X.",
            "sigma=0 is sanity run; must reproduce EXP-01 baseline cluster_labels.",
            "sigma=0.01, 0.05 with 3 perturbation seeds; sigma=0 only has 1 sanity run.",
            "Labels artifact (exp05_cluster_labels.parquet) is REQUIRED for EPIC-08.",
            "ARI/AMI / Hungarian / statistical tests / confidence intervals belong to EPIC-08.",
            "NO 'best/optimal/winner/recommended/final' labels in EXP-05 outputs.",
            "NO composite score / cross-algorithm ranking.",
            "NO sampling / subsampling.",
            "NO K sweep (EXP-02 owns).",
            "NO re-sweep hyperparameters (EXP-03 owns).",
            "NO re-sweep preprocessing (EXP-04 owns).",
            "FE-05 / FE-06 outputs READ-ONLY (SHA verified pre/post).",
        ],
        "records": [_record_to_dict(r) for r in result.block_r_records],
        "seed_sweep_records": [_record_to_dict(r) for r in result.block_s_records],
        "perturbation_records": [_record_to_dict(r) for r in result.block_n_records],
        "reproducibility_aggregates": [
            _block_r_aggregate_to_dict(a) for a in result.block_r_aggregates
        ],
        "seed_sweep_aggregates": [_block_s_aggregate_to_dict(a) for a in result.block_s_aggregates],
        "perturbation_aggregates": [
            _block_n_aggregate_to_dict(a) for a in result.block_n_aggregates
        ],
        "sigma_zero_baseline_labels_hash": result.sigma_zero_baseline_labels_hash,
    }


def _generate_run_summary(
    result: StabilityResult,
    config_sha: str,
    input_sha: str,
    metadata_sha: str,
) -> dict[str, Any]:
    """Generate machine-readable run summary."""
    return {
        "experiment_id": "EXP-05",
        "timestamp": _now_utc_iso(),
        "input_sha256": input_sha,
        "customer_metadata_sha256": metadata_sha,
        "config_sha256": config_sha,
        "exp05_config_sha256": result.exp05_config_sha256,
        "feature_set": result.feature_set,
        "feature_set_sha256": result.feature_set_sha256,
        "library_versions": result.library_versions,
        "platform_info": result.platform_info,
        "block_r": {
            "seed": result.block_r_seed,
            "n_repeat": result.block_r_n_repeat,
            "n_records": len(result.block_r_records),
            "n_successful_records": sum(1 for r in result.block_r_records if r.status == "SUCCESS"),
            "n_failed_records": sum(1 for r in result.block_r_records if r.status != "SUCCESS"),
            "aggregates": [
                {
                    "algorithm": a.algorithm,
                    "decision_status": a.decision_status,
                    "labels_hash_unique_count": a.labels_hash_unique_count,
                    "n_clusters_unique_count": a.n_clusters_unique_count,
                    "silhouette_mean": a.silhouette_stats.get("mean"),
                    "silhouette_std": a.silhouette_stats.get("std"),
                    "runtime_mean_seconds": a.runtime_stats.get("mean_seconds"),
                }
                for a in result.block_r_aggregates
            ],
        },
        "block_s": {
            "seeds": list(result.block_s_seeds),
            "n_repeat_per_seed": result.block_s_n_repeat,
            "n_records": len(result.block_s_records),
            "n_successful_records": sum(1 for r in result.block_s_records if r.status == "SUCCESS"),
            "n_failed_records": sum(1 for r in result.block_s_records if r.status != "SUCCESS"),
            "aggregates": [
                {
                    "algorithm": a.algorithm,
                    "decision_status": a.decision_status,
                    "labels_hash_unique_count": a.labels_hash_unique_count,
                    "n_clusters_unique_count": a.n_clusters_unique_count,
                    "silhouette_mean": a.silhouette_stats.get("mean"),
                    "silhouette_std": a.silhouette_stats.get("std"),
                    "runtime_mean_seconds": a.runtime_stats.get("mean_seconds"),
                }
                for a in result.block_s_aggregates
            ],
        },
        "block_n": {
            "algorithm_seed": result.block_n_algorithm_seed,
            "sigma_grid": list(result.block_n_sigma_grid),
            "perturbation_seeds": list(result.block_n_perturbation_seeds),
            "n_records": len(result.block_n_records),
            "n_successful_records": sum(1 for r in result.block_n_records if r.status == "SUCCESS"),
            "n_failed_records": sum(1 for r in result.block_n_records if r.status != "SUCCESS"),
            "aggregates": [
                {
                    "algorithm": a.algorithm,
                    "sigma": a.sigma,
                    "decision_status": a.decision_status,
                    "sigma_zero_baseline_match": a.sigma_zero_baseline_match,
                    "labels_hash_unique_count": a.labels_hash_unique_count,
                    "n_clusters_unique_count": a.n_clusters_unique_count,
                    "silhouette_mean": a.silhouette_stats.get("mean"),
                    "silhouette_std": a.silhouette_stats.get("std"),
                    "runtime_mean_seconds": a.runtime_stats.get("mean_seconds"),
                }
                for a in result.block_n_aggregates
            ],
        },
        "labels_artifact_rows": len(result.label_artifact_rows),
        "reproducibility_note": (
            "Block R = REPRODUCIBILITY_VERIFICATION (NOT stability analysis). "
            "Block S = STABILITY_EVIDENCE_GENERATION (NOT stability analysis). "
            "Block N = PERTURBATION_EVIDENCE_GENERATION (NOT stability analysis). "
            "ARI/AMI / Hungarian / statistical tests / confidence intervals belong to EPIC-08."
        ),
    }


def _generate_pending_review(exp05_config: dict[str, Any]) -> dict[str, Any]:
    """Generate exp05_pending_review.json."""
    notes = (
        exp05_config.get("exp05", {}).get("metadata", {}).get("pending_review_notes", [])
        if "metadata" in exp05_config.get("exp05", {})
        else exp05_config.get("exp05", {}).get("pending_review_notes", [])
    )
    return {
        "experiment_id": "EXP-05",
        "timestamp": _now_utc_iso(),
        "pending_review": notes,
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def _generate_markdown_report(
    result: StabilityResult,
    config_sha: str,
    input_sha: str,
    metadata_sha: str,
) -> str:
    """Generate the EXP-05 analysis markdown."""
    n_records_r = len(result.block_r_records)
    n_records_s = len(result.block_s_records)
    n_records_n = len(result.block_n_records)
    n_succ_r = sum(1 for r in result.block_r_records if r.status == "SUCCESS")
    n_succ_s = sum(1 for r in result.block_s_records if r.status == "SUCCESS")
    n_succ_n = sum(1 for r in result.block_n_records if r.status == "SUCCESS")

    parts: list[str] = []
    parts.append("# EXP-05 Stability & Reproducibility Report\n")
    parts.append(f"**Generated:** {_now_utc_iso()}\n")
    parts.append("**Plan revision:** R1\n")

    parts.append("## 1. Mục tiêu\n")
    parts.append(
        "EXP-05 sinh ra evidence (không phải analysis) cho:\n\n"
        "- **Block R — Reproducibility**: 5 thuật toán × n_repeat=5 × seed=42.\n"
        "- **Block S — Random Seed Stability**: K-Means + GMM + FCM × 5 seeds.\n"
        "- **Block N — Feature Perturbation**: in-memory Gaussian noise trên FE-06 matrix; sigma = [0, 0.01, 0.05] × std.\n\n"
        "EXP-05 KHÔNG phải stability analysis. ARI/AMI / Hungarian / statistical tests / confidence intervals thuộc EPIC-08.\n"
    )

    parts.append("\n## 2. Run counts\n")
    parts.append(
        "| Block | Records | Successful | Failed | Aggregates |\n"
        "|-------|---------|------------|--------|------------|\n"
        f"| R (Reproducibility) | {n_records_r} | {n_succ_r} | {n_records_r - n_succ_r} | {len(result.block_r_aggregates)} |\n"
        f"| S (Seed stability) | {n_records_s} | {n_succ_s} | {n_records_s - n_succ_s} | {len(result.block_s_aggregates)} |\n"
        f"| N (Perturbation) | {n_records_n} | {n_succ_n} | {n_records_n - n_succ_n} | {len(result.block_n_aggregates)} |\n"
    )

    parts.append(
        "\n## 3. Block R — Reproducibility evidence\n\n"
        "Block R là REPRODUCIBILITY_VERIFICATION, KHÔNG phải stability analysis.\n"
        "Determinism expectation: với seed=42 + EXP-01 working defaults, labels_hash\n"
        "và metric values phải identical across n_repeat=5.\n\n"
        "| Algorithm | n_repeat | n_successful | labels_hash_unique | n_clusters_unique | Decision |\n"
        "|-----------|----------|--------------|--------------------|-------------------|----------|\n"
    )
    for a in result.block_r_aggregates:
        parts.append(
            f"| {a.algorithm} | {a.n_repeat} | {a.n_successful} | "
            f"{a.labels_hash_unique_count} | {a.n_clusters_unique_count} | "
            f"{a.decision_status} |\n"
        )

    parts.append(
        "\n## 4. Block S — Random seed stability evidence\n\n"
        "Block S gồm K-Means + GMM + FCM × 5 seeds. Agglomerative + DBSCAN\n"
        "deterministic nên KHÔNG seed sweep. Records metric values, cluster sizes,\n"
        "labels_hash across seeds. KHÔNG ranking algorithm.\n\n"
        "| Algorithm | n_seeds | labels_hash_unique | n_clusters_unique | Decision |\n"
        "|-----------|---------|--------------------|-------------------|----------|\n"
    )
    for a in result.block_s_aggregates:
        parts.append(
            f"| {a.algorithm} | {a.n_seeds} | {a.labels_hash_unique_count} | "
            f"{a.n_clusters_unique_count} | {a.decision_status} |\n"
        )

    parts.append(
        "\n## 5. Block N — Feature perturbation evidence\n\n"
        "Block N: in-memory Gaussian noise; sigma × perturbation_seeds. KHÔNG\n"
        "persist perturbed dataset. sigma=0 là sanity run (reproduce baseline).\n"
        "KHÔNG assert labels phải thay đổi với sigma=1% hoặc 5% — đó là kết\n"
        "quả thực nghiệm.\n\n"
        "| Algorithm | sigma | n_seeds | labels_hash_unique | n_clusters_unique | sigma_zero_match | Decision |\n"
        "|-----------|-------|---------|--------------------|-------------------|------------------|----------|\n"
    )
    for a in result.block_n_aggregates:
        szm = (
            "N/A"
            if a.sigma_zero_baseline_match is None
            else ("True" if a.sigma_zero_baseline_match else "False")
        )
        parts.append(
            f"| {a.algorithm} | {a.sigma} | {a.n_perturbation_seeds} | "
            f"{a.labels_hash_unique_count} | {a.n_clusters_unique_count} | "
            f"{szm} | {a.decision_status} |\n"
        )

    parts.append(
        "\n## 6. Labels artifact\n\n"
        "EXP-05 xuất raw label-level artifact tại\n"
        "`reports/exp05/exp05_cluster_labels.parquet`. Schema (REQUIRED):\n\n"
        "- run_id, block, algorithm, seed, sigma, perturbation_seed,\n"
        "  repeat_index, CustomerID, cluster_label\n\n"
        f"Tổng số rows: **{len(result.label_artifact_rows)}**.\n\n"
        "CustomerID alignment với FE-06 metadata.\n"
    )

    parts.append("\n## 7. Provenance\n")
    parts.append(
        "| Field | Value |\n"
        "|-------|-------|\n"
        f"| Feature set | {result.feature_set} |\n"
        f"| FE-06 final_clustering_dataset SHA-256 | `{input_sha}` |\n"
        f"| customer_metadata.parquet SHA-256 | `{metadata_sha}` |\n"
        f"| Framework config SHA-256 | `{config_sha}` |\n"
        f"| EXP-05 config SHA-256 | `{result.exp05_config_sha256}` |\n"
        f"| Library versions | {json.dumps(result.library_versions, sort_keys=True)} |\n"
        f"| Platform | {json.dumps(result.platform_info, sort_keys=True)} |\n"
    )

    parts.append(
        "\n## 8. Decision status taxonomy\n\n"
        "Allowed labels (only these):\n\n"
        "- `REPRODUCIBILITY_VERIFIED` / `REPRODUCIBILITY_FAILED`\n"
        "- `STABILITY_EVIDENCE_GENERATED`\n"
        "- `PERTURBATION_EVIDENCE_GENERATED`\n"
        "- `SIGMA_ZERO_BASELINE_MATCH` / `SIGMA_ZERO_BASELINE_MISMATCH`\n"
        "- `PENDING_REVIEW`\n\n"
        "Forbidden: BEST, OPTIMAL, WINNER, SUPERIOR, RECOMMENDED, FINAL.\n"
    )

    parts.append(
        "\n## 9. EPIC-08 boundary (cumulative)\n\n"
        "EXP-05 chỉ generate evidence. EPIC-08 owns:\n\n"
        "- ARI / AMI computation (across Block S seeds; across Block N perturbation seeds).\n"
        "- Hungarian matching.\n"
        "- Statistical tests (across seeds / perturbation).\n"
        "- Confidence intervals.\n"
        "- Cross-algorithm stability analysis.\n"
        '- "Most stable algorithm" / "best stability" claims (if any).\n'
    )

    parts.append(
        "\n## 10. Scope boundaries\n\n"
        "EXP-05 THỰC HIỆN:\n\n"
        "- Block R: 5 algorithms × n_repeat=5 × seed=42. Verify determinism.\n"
        "- Block S: K-Means + GMM + FCM × 5 seeds. Fixed hyperparameters.\n"
        "- Block N: 5 algorithms × (sigma=0 sanity + sigma=1%/5% × 3 perturbation seeds).\n"
        "- In-memory perturbation only. NO persistence of perturbed X.\n"
        "- Pre/post SHA check for FE-06 input.\n"
        "- Labels artifact (`exp05_cluster_labels.parquet`) for EPIC-08.\n"
        "- Decision status taxonomy as listed in §8.\n\n"
        "EXP-05 KHÔNG THỰC HIỆN:\n\n"
        "- ARI / AMI / Hungarian / statistical tests / confidence intervals.\n"
        "- Composite score / cross-algorithm ranking.\n"
        '- "Best / most stable / optimal / winner / recommended / final" claim.\n'
        "- Sampling / subsampling.\n"
        "- Re-sweep K (EXP-02 owns).\n"
        "- Re-sweep hyperparameters (EXP-03 owns).\n"
        "- Re-sweep preprocessing (EXP-04 owns).\n"
        "- Persistence of perturbed dataset.\n"
        "- Customer profiling / segment naming.\n"
    )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _load_yaml_text(path: Path) -> str:
    """Read YAML file as text."""
    with path.open("r", encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    """Run EXP-05 stability & reproducibility sweep."""
    parser = argparse.ArgumentParser(description="EXP-05 Stability & Reproducibility Runner")
    parser.add_argument(
        "--config",
        type=Path,
        default=_EXP05_CONFIG_PATH,
        help="Path to EXP-05 YAML config.",
    )
    parser.add_argument(
        "--framework-config",
        type=Path,
        default=_FRAMEWORK_CONFIG_PATH,
        help="Path to ML-01 framework config (clustering.yaml).",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS_DIR,
        help="Where to write EXP-05 artifacts.",
    )
    args = parser.parse_args()

    print("[EXP-05] Starting stability & reproducibility sweep...")
    print(f"[EXP-05] Repository root: {_REPO_ROOT}")

    # Verify config files
    if not args.config.exists():
        print(f"[EXP-05] ERROR: Config not found: {args.config}")
        return 1
    if not args.framework_config.exists():
        print(f"[EXP-05] ERROR: Framework config not found: {args.framework_config}")
        return 1

    # Load configurations
    exp05_config_text = _load_yaml_text(args.config)
    framework_config_text = _load_yaml_text(args.framework_config)
    exp05_config = yaml.safe_load(exp05_config_text)
    framework_config = load_framework_config(args.framework_config)

    config_sha = compute_text_sha256(framework_config_text)

    # Verify FE-06 inputs (READ-ONLY)
    if not _FE06_DATASET_PATH.exists():
        print(f"[EXP-05] ERROR: FE-06 dataset not found: {_FE06_DATASET_PATH}")
        return 1
    if not _FE06_METADATA_PATH.exists():
        print(f"[EXP-05] ERROR: FE-06 metadata not found: {_FE06_METADATA_PATH}")
        return 1

    print("[EXP-05] Computing input SHAs (READ-ONLY)...")
    input_sha = _compute_file_sha256(_FE06_DATASET_PATH)
    metadata_sha = _compute_file_sha256(_FE06_METADATA_PATH)
    print(f"[EXP-05] final_clustering_dataset.parquet SHA-256: {input_sha}")
    print(f"[EXP-05] customer_metadata.parquet SHA-256: {metadata_sha}")
    print(f"[EXP-05] Framework config SHA-256: {config_sha}")

    pre_run_shas = {
        "final_clustering_dataset.parquet": input_sha,
        "customer_metadata.parquet": metadata_sha,
    }

    # Load inputs
    print("[EXP-05] Loading FE-06 inputs (READ-ONLY)...")
    matrix_df = pd.read_parquet(_FE06_DATASET_PATH)
    metadata_df = pd.read_parquet(_FE06_METADATA_PATH)
    print(f"[EXP-05] matrix: {len(matrix_df)} rows × {len(matrix_df.columns)} features")
    print(f"[EXP-05] customer_metadata: {len(metadata_df)} rows")

    # Initialize runner
    runner = StabilityReproducibilityRunner(
        framework_config,
        exp05_config,
        framework_config_text=framework_config_text,
        exp05_config_text=exp05_config_text,
    )

    # Run all three blocks
    print("[EXP-05] Running Block R / S / N...")
    result = runner.run(
        matrix_df,
        metadata_df,
        input_sha256=input_sha,
        metadata_sha256=metadata_sha,
    )

    # Print summary
    print("\n[EXP-05] Sweep summary:")
    print("-" * 78)
    print(
        f"  Block R: {len(result.block_r_records)} records "
        f"({sum(1 for r in result.block_r_records if r.status == 'SUCCESS')} SUCCESS)"
    )
    for a in result.block_r_aggregates:
        print(
            f"    {a.algorithm}: status={a.decision_status} "
            f"labels_hash_unique={a.labels_hash_unique_count}"
        )
    print(
        f"  Block S: {len(result.block_s_records)} records "
        f"({sum(1 for r in result.block_s_records if r.status == 'SUCCESS')} SUCCESS)"
    )
    for a in result.block_s_aggregates:
        print(
            f"    {a.algorithm}: status={a.decision_status} "
            f"labels_hash_unique={a.labels_hash_unique_count}"
        )
    print(
        f"  Block N: {len(result.block_n_records)} records "
        f"({sum(1 for r in result.block_n_records if r.status == 'SUCCESS')} SUCCESS)"
    )
    for a in result.block_n_aggregates:
        szm = (
            "N/A"
            if a.sigma_zero_baseline_match is None
            else ("True" if a.sigma_zero_baseline_match else "False")
        )
        print(
            f"    {a.algorithm} σ={a.sigma}: status={a.decision_status} "
            f"labels_hash_unique={a.labels_hash_unique_count} σ0_baseline_match={szm}"
        )
    print(f"  Labels artifact rows: {len(result.label_artifact_rows)}")
    print("-" * 78)

    # Verify post-run SHAs
    post_run_shas = {
        "final_clustering_dataset.parquet": _compute_file_sha256(_FE06_DATASET_PATH),
        "customer_metadata.parquet": _compute_file_sha256(_FE06_METADATA_PATH),
    }
    input_integrity_ok = pre_run_shas == post_run_shas
    if not input_integrity_ok:
        print("[EXP-05] ERROR: FE-06 inputs were mutated during run. Aborting.")
        return 1
    print("[EXP-05] Input integrity verified: NO mutation of FE-06 outputs.")

    # Write artifacts
    print(f"\n[EXP-05] Writing artifacts to {args.reports_dir}...")
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    manifest = _generate_manifest(
        result,
        config_sha,
        input_sha,
        metadata_sha,
        input_integrity_ok,
        pre_run_shas,
        post_run_shas,
    )
    _write_json(manifest, args.reports_dir / "exp05_manifest.json")
    print("  - Written: exp05_manifest.json")

    run_summary = _generate_run_summary(result, config_sha, input_sha, metadata_sha)
    _write_json(run_summary, args.reports_dir / "exp05_run_summary.json")
    print("  - Written: exp05_run_summary.json")

    # Block R
    _write_csv(
        _block_r_results_dataframe(result.block_r_records),
        args.reports_dir / "exp05_reproducibility_results.csv",
    )
    print("  - Written: exp05_reproducibility_results.csv")
    _write_csv(
        _block_r_aggregate_dataframe(result.block_r_aggregates),
        args.reports_dir / "exp05_reproducibility_aggregate.csv",
    )
    print("  - Written: exp05_reproducibility_aggregate.csv")

    # Block S
    _write_csv(
        _block_s_results_dataframe(result.block_s_records),
        args.reports_dir / "exp05_seed_sweep_results.csv",
    )
    print("  - Written: exp05_seed_sweep_results.csv")
    _write_csv(
        _block_s_aggregate_dataframe(result.block_s_aggregates),
        args.reports_dir / "exp05_seed_sweep_aggregate.csv",
    )
    print("  - Written: exp05_seed_sweep_aggregate.csv")

    # Block N
    _write_csv(
        _block_n_results_dataframe(result.block_n_records),
        args.reports_dir / "exp05_noise_perturbation_results.csv",
    )
    print("  - Written: exp05_noise_perturbation_results.csv")
    _write_csv(
        _block_n_aggregate_dataframe(result.block_n_aggregates),
        args.reports_dir / "exp05_noise_perturbation_aggregate.csv",
    )
    print("  - Written: exp05_noise_perturbation_aggregate.csv")

    # Cluster size consistency
    _write_csv(
        _cluster_size_consistency_dataframe(result),
        args.reports_dir / "exp05_cluster_size_consistency.csv",
    )
    print("  - Written: exp05_cluster_size_consistency.csv")

    # Labels artifact (REQUIRED for EPIC-08)
    label_artifact_df = _label_artifact_dataframe(result.label_artifact_rows)
    label_artifact_path = args.reports_dir / "exp05_cluster_labels.parquet"
    label_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    label_artifact_df.to_parquet(label_artifact_path, index=False)
    print(f"  - Written: {label_artifact_path.name} ({len(label_artifact_df)} rows)")

    # Pending review
    _write_json(
        _generate_pending_review(exp05_config),
        args.reports_dir / "exp05_pending_review.json",
    )
    print("  - Written: exp05_pending_review.json")

    # Analysis markdown
    md_report = _generate_markdown_report(result, config_sha, input_sha, metadata_sha)
    _write_markdown(md_report, args.reports_dir / "exp05_analysis.md")
    print("  - Written: exp05_analysis.md")

    print("\n[EXP-05] Stability & reproducibility sweep completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
