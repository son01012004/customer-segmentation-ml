#!/usr/bin/env python3
"""EXP-03 Hyperparameter Search Runner.

This script runs the EXP-03 hyperparameter search across the
five EPIC-06 benchmark algorithms:

- K-Means: sensitivity on init, n_init, max_iter
- Agglomerative: sensitivity on linkage
- DBSCAN: sensitivity on eps, min_samples
- GMM: sensitivity on covariance_type, init_params
- Fuzzy C-Means: sensitivity on m, max_iter

Plus Stage C selected interactions (K from EXP-02 candidates × parameter).

Output artifacts (under reports/exp03/):
- exp03_manifest.json (all results with provenance)
- exp03_run_summary.json (machine-readable summary)
- exp03_hyperparameter_results.csv (all per-config results)
- exp03_parameter_sensitivity.csv (sensitivity evidence per algorithm × parameter)
- exp03_selected_configurations.csv (per-algorithm working selected config)
- exp03_hyperparameter_analysis.md (Vietnamese narrative report)
- figures/exp03_<algo>_sensitivity_<param>.png (metric vs param value curves)

EXP-03 scope:
- Single-parameter sensitivity sweeps per algorithm.
- Three Stage C selected interactions using EXP-02 candidate K.
- Per-algorithm working selected configuration via multi-metric evidence.
- NOT cross-algorithm ranking.

EXP-03 does NOT:
- Rank algorithms.
- Pick "best algorithm" / "winning algorithm" / "final algorithm".
- Re-sweep K (K reused from EXP-02).
- Do stability analysis.
- Do customer profiling.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
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
from customer_segmentation.clustering.hyperparameter_search import (  # noqa: E402
    CANONICAL_ORDER,
    HyperparameterSearchRunner,
)

# ---------------------------------------------------------------------------
# Configuration paths
# ---------------------------------------------------------------------------

_EXP03_CONFIG_PATH = _REPO_ROOT / "configs" / "exp03_hyperparameter_search.yaml"
_FRAMEWORK_CONFIG_PATH = _REPO_ROOT / "configs" / "clustering.yaml"
_EXP02_CANDIDATES_PATH = _REPO_ROOT / "reports" / "exp02" / "exp02_candidate_cluster_numbers.csv"
_FE06_DATASET_PATH = _REPO_ROOT / "data" / "processed" / "final_clustering_dataset.parquet"
_FE06_METADATA_PATH = _REPO_ROOT / "data" / "processed" / "customer_metadata.parquet"
_REPORTS_DIR = _REPO_ROOT / "reports" / "exp03"
_FIGURES_DIR = _REPORTS_DIR / "figures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def write_json(data: dict[str, Any], path: Path) -> None:
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=False, default=str)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def write_markdown(content: str, path: Path) -> None:
    """Write Markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Report generators
# ---------------------------------------------------------------------------


def _metric_extra(result) -> dict[str, Any]:
    """Extract metrics.extra from a HyperparameterResult."""
    if result.cluster_result is None:
        return {}
    return result.cluster_result.metrics.extra


def _metrics(result) -> Any:
    """Extract metrics from a HyperparameterResult."""
    if result.cluster_result is None:
        return None
    return result.cluster_result.metrics


def generate_manifest(
    sweep_result,
    config: dict[str, Any],
    config_sha: str,
) -> dict[str, Any]:
    """Generate EXP-03 manifest JSON."""
    exp03_section = config.get("exp03", {})

    manifest = {
        "experiment_id": "EXP-03",
        "name": exp03_section.get("name", "EXP-03 Hyperparameter Search"),
        "description": exp03_section.get("description", ""),
        "timestamp": now_utc_iso(),
        "dataset_version": config.get("exp03", {}).get("dataset", {}).get("version", "FE06-v1.0"),
        "input_sha256": sweep_result.input_sha256,
        "config_sha256": config_sha,
        "feature_set": sweep_result.feature_set,
        "n_total_runs": sweep_result.n_total_runs,
        "n_successful_runs": sweep_result.n_successful_runs,
        "canonical_algorithm_order": CANONICAL_ORDER,
        "library_versions": sweep_result.library_versions,
        "decision_status": config.get("exp03", {}).get("decision_status", {}),
        "scope_boundaries": config.get("exp03", {}).get("scope_boundaries", []),
        "pending_review_notes": config.get("exp03", {}).get("pending_review_notes", []),
        "assumptions": config.get("exp03", {}).get("assumptions", []),
        "results": [],
        "sensitivity_table": [],
        "selected_configurations": [],
    }

    for result in sweep_result.results:
        m = _metrics(result)
        extra = _metric_extra(result)
        entry = {
            "experiment_id": result.experiment_id,
            "algorithm": result.algorithm,
            "stage": result.stage,
            "sweep_parameter": result.sweep_parameter,
            "sweep_value": result.sweep_value,
            "baseline_k": result.baseline_k,
            "hyperparameters": result.hyperparameters,
            "n_clusters": result.n_clusters,
            "noise_count": result.noise_count,
            "noise_ratio": result.noise_ratio,
            "status": result.status,
            "runtime": {
                "mean_seconds": result.runtime_stats.get("mean_seconds"),
                "std_seconds": result.runtime_stats.get("std_seconds"),
                "min_seconds": result.runtime_stats.get("min_seconds"),
                "max_seconds": result.runtime_stats.get("max_seconds"),
            },
            "metrics": {
                "silhouette": {
                    "value": m.silhouette if m else None,
                    "status": extra.get("silhouette_status", "MISSING") if m else "MISSING",
                    "reason": extra.get("silhouette_reason") if m else None,
                },
                "davies_bouldin": {
                    "value": m.davies_bouldin if m else None,
                    "status": extra.get("davies_bouldin_status", "MISSING") if m else "MISSING",
                    "reason": extra.get("davies_bouldin_reason") if m else None,
                },
                "calinski_harabasz": {
                    "value": m.calinski_harabasz if m else None,
                    "status": extra.get("calinski_harabasz_status", "MISSING") if m else "MISSING",
                    "reason": extra.get("calinski_harabasz_reason") if m else None,
                },
                "wcss": {
                    "value": m.wcss if m else None,
                    "status": extra.get("wcss_status", "MISSING") if m else "MISSING",
                    "reason": extra.get("wcss_reason") if m else None,
                },
            },
            "input_sha256": result.input_sha256,
            "config_sha256": result.config_sha256,
            "library_versions": result.library_versions,
            "error": result.error,
        }
        manifest["results"].append(entry)

    # Sensitivity table
    for rec in sweep_result.sensitivity_table:
        manifest["sensitivity_table"].append(
            {
                "algorithm": rec.algorithm,
                "parameter": rec.parameter,
                "baseline_value": rec.baseline_value,
                "value": rec.value,
                "K": rec.K,
                "silhouette": {"value": rec.silhouette, "status": rec.silhouette_status},
                "davies_bouldin": {
                    "value": rec.davies_bouldin,
                    "status": rec.davies_bouldin_status,
                },
                "calinski_harabasz": {
                    "value": rec.calinski_harabasz,
                    "status": rec.calinski_harabasz_status,
                },
                "wcss": {"value": rec.wcss, "status": rec.wcss_status},
                "runtime_mean": rec.runtime_mean,
                "runtime_std": rec.runtime_std,
                "n_clusters": rec.n_clusters,
                "noise_count": rec.noise_count,
                "noise_ratio": rec.noise_ratio,
                "status": rec.status,
                "experiment_id": rec.experiment_id,
            }
        )

    # Selected configurations
    for sel in sweep_result.selected_configurations:
        manifest["selected_configurations"].append(
            {
                "algorithm": sel.algorithm,
                "hyperparameters": sel.hyperparameters,
                "baseline_k": sel.baseline_k,
                "decision_status": sel.decision_status,
                "selection_evidence": sel.selection_evidence,
                "pending_review_notes": sel.pending_review_notes,
                "experiment_id": sel.experiment_id,
                "stage": sel.stage,
                "sweep_parameter": sel.sweep_parameter,
                "sweep_value": sel.sweep_value,
                "silhouette": {
                    "value": sel.silhouette,
                    "status": sel.silhouette_status,
                    "rank": sel.silhouette_rank,
                },
                "davies_bouldin": {
                    "value": sel.davies_bouldin,
                    "status": sel.davies_bouldin_status,
                    "rank": sel.davies_bouldin_rank,
                },
                "calinski_harabasz": {
                    "value": sel.calinski_harabasz,
                    "status": sel.calinski_harabasz_status,
                    "rank": sel.calinski_harabasz_rank,
                },
                "wcss": {"value": sel.wcss, "status": sel.wcss_status},
                "runtime_mean": sel.runtime_mean,
                "runtime_std": sel.runtime_std,
                "n_clusters": sel.n_clusters,
                "noise_count": sel.noise_count,
                "noise_ratio": sel.noise_ratio,
                "tied_alternates": sel.tied_alternates,
            }
        )

    return manifest


def generate_run_summary(sweep_result, config_sha: str) -> dict[str, Any]:
    """Generate EXP-03 run summary JSON."""
    return {
        "experiment_id": "EXP-03",
        "timestamp": now_utc_iso(),
        "input_sha256": sweep_result.input_sha256,
        "config_sha256": config_sha,
        "feature_set": sweep_result.feature_set,
        "n_total_runs": sweep_result.n_total_runs,
        "n_successful_runs": sweep_result.n_successful_runs,
        "all_success": sweep_result.n_successful_runs == sweep_result.n_total_runs,
        "results_by_status": {
            "SUCCESS": sum(1 for r in sweep_result.results if r.status == "SUCCESS"),
            "FAILED": sum(1 for r in sweep_result.results if r.status != "SUCCESS"),
        },
        "selected_configurations": [
            {
                "algorithm": sel.algorithm,
                "decision_status": sel.decision_status,
                "experiment_id": sel.experiment_id,
                "stage": sel.stage,
                "sweep_parameter": sel.sweep_parameter,
                "sweep_value": sel.sweep_value,
                "silhouette": sel.silhouette,
                "davies_bouldin": sel.davies_bouldin,
                "calinski_harabasz": sel.calinski_harabasz,
            }
            for sel in sweep_result.selected_configurations
        ],
        "library_versions": sweep_result.library_versions,
    }


def generate_results_csv(sweep_result) -> pd.DataFrame:
    """Generate per-config results CSV."""
    rows = []
    for result in sweep_result.results:
        m = _metrics(result)
        extra = _metric_extra(result)
        row = {
            "experiment_id": result.experiment_id,
            "algorithm": result.algorithm,
            "stage": result.stage,
            "sweep_parameter": result.sweep_parameter,
            "sweep_value": result.sweep_value,
            "baseline_k": result.baseline_k,
            "n_clusters": result.n_clusters,
            "noise_count": result.noise_count,
            "noise_ratio": result.noise_ratio,
            "status": result.status,
            "silhouette": m.silhouette if m else None,
            "silhouette_status": extra.get("silhouette_status", "MISSING") if m else "MISSING",
            "davies_bouldin": m.davies_bouldin if m else None,
            "davies_bouldin_status": (
                extra.get("davies_bouldin_status", "MISSING") if m else "MISSING"
            ),
            "calinski_harabasz": m.calinski_harabasz if m else None,
            "calinski_harabasz_status": (
                extra.get("calinski_harabasz_status", "MISSING") if m else "MISSING"
            ),
            "wcss": m.wcss if m else None,
            "wcss_status": extra.get("wcss_status", "MISSING") if m else "MISSING",
            "runtime_mean_seconds": result.runtime_stats.get("mean_seconds"),
            "runtime_std_seconds": result.runtime_stats.get("std_seconds"),
        }
        # Add hyperparameters as separate columns
        for k, v in sorted(result.hyperparameters.items()):
            row[f"hp_{k}"] = v
        rows.append(row)
    return pd.DataFrame(rows)


def generate_sensitivity_csv(sweep_result) -> pd.DataFrame:
    """Generate parameter sensitivity CSV."""
    rows = []
    for rec in sweep_result.sensitivity_table:
        row = {
            "algorithm": rec.algorithm,
            "parameter": rec.parameter,
            "baseline_value": rec.baseline_value,
            "value": rec.value,
            "K": rec.K,
            "silhouette": rec.silhouette,
            "silhouette_status": rec.silhouette_status,
            "davies_bouldin": rec.davies_bouldin,
            "davies_bouldin_status": rec.davies_bouldin_status,
            "calinski_harabasz": rec.calinski_harabasz,
            "calinski_harabasz_status": rec.calinski_harabasz_status,
            "wcss": rec.wcss,
            "wcss_status": rec.wcss_status,
            "runtime_mean_seconds": rec.runtime_mean,
            "runtime_std_seconds": rec.runtime_std,
            "n_clusters": rec.n_clusters,
            "noise_count": rec.noise_count,
            "noise_ratio": rec.noise_ratio,
            "status": rec.status,
            "experiment_id": rec.experiment_id,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def generate_selected_csv(sweep_result) -> pd.DataFrame:
    """Generate per-algorithm selected configuration CSV."""
    rows = []
    for sel in sweep_result.selected_configurations:
        row = {
            "algorithm": sel.algorithm,
            "decision_status": sel.decision_status,
            "experiment_id": sel.experiment_id,
            "stage": sel.stage,
            "sweep_parameter": sel.sweep_parameter,
            "sweep_value": sel.sweep_value,
            "baseline_k": sel.baseline_k,
            "hyperparameters": json.dumps(sel.hyperparameters, default=str),
            "n_clusters": sel.n_clusters,
            "noise_count": sel.noise_count,
            "noise_ratio": sel.noise_ratio,
            "silhouette": sel.silhouette,
            "silhouette_status": sel.silhouette_status,
            "silhouette_rank": sel.silhouette_rank,
            "davies_bouldin": sel.davies_bouldin,
            "davies_bouldin_status": sel.davies_bouldin_status,
            "davies_bouldin_rank": sel.davies_bouldin_rank,
            "calinski_harabasz": sel.calinski_harabasz,
            "calinski_harabasz_status": sel.calinski_harabasz_status,
            "calinski_harabasz_rank": sel.calinski_harabasz_rank,
            "wcss": sel.wcss,
            "wcss_status": sel.wcss_status,
            "runtime_mean_seconds": sel.runtime_mean,
            "runtime_std_seconds": sel.runtime_std,
            "tied_alternates_count": len(sel.tied_alternates),
            "primary_criterion": sel.selection_evidence.get("primary_criterion"),
            "selection_evidence_note": "multi-metric, NOT single-metric",
        }
        rows.append(row)
    return pd.DataFrame(rows)


def generate_markdown_report(
    sweep_result,
    config: dict[str, Any],
    input_sha: str,
    config_sha: str,
) -> str:
    """Generate EXP-03 hyperparameter analysis markdown report (Vietnamese)."""
    exp03_section = config.get("exp03", {})
    protocol_cfg = exp03_section.get("selection_protocol", {})

    md = f"""# EXP-03 Hyperparameter Search Report

**Generated:** {now_utc_iso()}

## Mục tiêu

Xác định search space có căn cứ cho từng clustering algorithm,
khảo sát ảnh hưởng của hyperparameters, và xác định working selected
configuration trong phạm vi từng algorithm dựa trên multi-metric evidence.

**QUAN TRỌNG:** "Working Selected Configuration" trong EXP-03 KHÔNG có nghĩa:
- best algorithm
- final optimal model
- final research selection
- winner
- recommendation giữa các thuật toán

Nó chỉ có nghĩa: trong search space của từng algorithm, configuration
được chọn theo protocol đa tiêu chí đã document, status = WORKING/PENDING_REVIEW.

## Cấu hình

| Tham số | Giá trị |
|---------|---------|
| Dataset version | {exp03_section.get('dataset', {}).get('version', 'FE06-v1.0')} |
| Feature set | {sweep_result.feature_set} (FE-06 Extended RFM 14 features) |
| Baseline seed | {exp03_section.get('runtime', {}).get('seed', 42)} |
| Runtime repeat | {exp03_section.get('runtime', {}).get('repeat', 5)} |
| Primary criterion | {protocol_cfg.get('primary_criterion', 'silhouette')} |
| Tiebreaker 1 | {protocol_cfg.get('tie_breaker_1', 'davies_bouldin')} |
| Tiebreaker 2 | {protocol_cfg.get('tie_breaker_2', 'calinski_harabasz')} |
| K reuse | EXP-02 candidates (CONTROLLED_REUSE_OF_EXP02_EVIDENCE) |

## Dữ liệu đầu vào

- **Dataset:** `{_FE06_DATASET_PATH}`
- **Input SHA-256:** `{input_sha}`
- **Config SHA-256:** `{config_sha}`

## Search Space từng thuật toán

### K-Means (Stage A baseline: n_clusters=4, Stage B: init, n_init, max_iter)

| Stage | N_run | Mô tả |
|-------|-------|--------|
| A | 1 | Baseline: kmeans++, n_init=10, max_iter=300 |
| B | 6 | init=random; n_init=1/5/20; max_iter=100/500 |
| C | 3 | K=3 (EXP-02) × n_init=1/10/20 |

### Agglomerative (Stage A baseline: n_clusters=4, linkage=ward)

| Stage | N_run | Mô tả |
|-------|-------|--------|
| A | 1 | Baseline: linkage=ward, metric=euclidean |
| B | 3 | linkage=complete/average/single |
| C | 3 | K=3 (EXP-02) × linkage=ward/complete/average |

### DBSCAN (Stage A baseline: eps=0.5, min_samples=5)

| Stage | N_run | Mô tả |
|-------|-------|--------|
| A | 1 | Baseline: eps=0.5, min_samples=5, metric=euclidean |
| B | 6 | eps=0.3/0.7/1.0; min_samples=3/10/15 |

### GMM (Stage A baseline: n_components=4, covariance_type=full)

| Stage | N_run | Mô tả |
|-------|-------|--------|
| A | 1 | Baseline: full, kmeans init |
| B | 4 | covariance_type=tied/diag/spherical; init_params=random |

### Fuzzy C-Means (Stage A baseline: n_clusters=4, m=2.0)

| Stage | N_run | Mô tả |
|-------|-------|--------|
| A | 1 | Baseline: m=2.0, max_iter=300 |
| B | 5 | m=1.5/2.5/3.0; max_iter=100/500 |
| C | 3 | K=3 (EXP-02) × m=1.5/2.0/2.5 |

## Kết quả tổng hợp

| Algorithm | Successful | Total | Success Rate |
|-----------|-----------|-------|-------------|
"""

    for algo in CANONICAL_ORDER:
        algo_results = [r for r in sweep_result.results if r.algorithm == algo]
        success = sum(1 for r in algo_results if r.status == "SUCCESS")
        total = len(algo_results)
        rate = f"{100*success/total:.0f}%" if total > 0 else "N/A"
        md += f"| {algo} | {success} | {total} | {rate} |\n"

    md += f"""
**Tổng số runs:** {sweep_result.n_total_runs}
**Successful:** {sweep_result.n_successful_runs}
**Sensitivity records:** {len(sweep_result.sensitivity_table)}

## Selected Configurations (per-algorithm)

| Algorithm | Decision Status | Experiment ID | K | Silhouette | DBI | CH | WCSS |
|-----------|---------------|--------------|---|------------|-----|-----|------|
"""

    for sel in sweep_result.selected_configurations:
        sel_str = sel.silhouette
        dbi_str = sel.davies_bouldin
        ch_str = sel.calinski_harabasz
        wcss_str = sel.wcss
        if sel_str is not None:
            sel_str = f"{sel_str:.4f}"
        if dbi_str is not None:
            dbi_str = f"{dbi_str:.4f}"
        if ch_str is not None:
            ch_str = f"{ch_str:.2f}"
        if wcss_str is not None:
            wcss_str = f"{wcss_str:.2f}"
        md += f"| {sel.algorithm} | {sel.decision_status} | {sel.experiment_id} | {sel.baseline_k} | {sel_str} | {dbi_str} | {ch_str} | {wcss_str} |\n"

    md += """
**Ghi chú về selection protocol:**

- Primary criterion: **Silhouette** (cao hơn = clusters compact và tách biệt tốt hơn)
- Tiebreaker 1: **Davies-Bouldin** (thấp hơn = compact hơn)
- Tiebreaker 2: **Calinski-Harabasz** (cao hơn = compact và tách biệt tốt hơn)
- WCSS: **diagnostic only** (quan sát elbow, KHÔNG dùng để rank)
- Runtime: **diagnostic only** (KHÔNG dùng để rank)

**KHÔNG có composite score với trọng số tùy ý.**

## Parameter Sensitivity Evidence

"""

    # Group sensitivity records by (algorithm, parameter)
    sensitivity_by_algo_param: dict[tuple, list] = {}
    for rec in sweep_result.sensitivity_table:
        key = (rec.algorithm, rec.parameter)
        sensitivity_by_algo_param.setdefault(key, []).append(rec)

    for (algo, param), recs in sorted(sensitivity_by_algo_param.items()):
        md += f"### {algo} — {param}\n\n"
        md += "| Value | K | Silhouette | DBI | CH | WCSS | Runtime (s) | Status |\n"
        md += "|-------|---|------------|-----|-----|------|--------------|--------|\n"
        for rec in sorted(recs, key=lambda r: str(r.value)):
            sil_str = f"{rec.silhouette:.4f}" if rec.silhouette is not None else "N/A"
            dbi_str = f"{rec.davies_bouldin:.4f}" if rec.davies_bouldin is not None else "N/A"
            ch_str = f"{rec.calinski_harabasz:.2f}" if rec.calinski_harabasz is not None else "N/A"
            wcss_str = f"{rec.wcss:.2f}" if rec.wcss is not None else "N/A"
            rt_str = f"{rec.runtime_mean:.4f}" if rec.runtime_mean is not None else "N/A"
            val_str = str(rec.value)
            k_str = str(rec.K) if rec.K is not None else "-"
            md += f"| {val_str} | {k_str} | {sil_str} | {dbi_str} | {ch_str} | {wcss_str} | {rt_str} | {rec.status} |\n"
        md += "\n"

    md += """## PENDING_REVIEW decisions

"""
    for note in exp03_section.get("pending_review_notes", []):
        md += f"- {note}\n"

    md += """
## Scope boundaries

### EXP-03 THỰC HIỆN
- Stage A baseline per algorithm (EXP-01 working defaults).
- Stage B single-parameter sensitivity sweeps.
- Stage C selected interactions (K from EXP-02 candidates).
- Multi-criteria selection protocol per algorithm (NOT cross-algorithm).
- Reuse EXP-02 K candidates (CONTROLLED_REUSE_OF_EXP02_EVIDENCE).

### EXP-03 KHÔNG THỰC HIỆN
- Rank algorithms / pick "best algorithm" / "winning algorithm".
- Re-sweep K = 2..10 (K reused from EXP-02).
- Stability analysis (EXP-05 / EPIC-08 scope).
- Customer profiling / segment naming.
- Business interpretation.
- Composite scoring with arbitrary weights.
"""
    return md


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------


def generate_sensitivity_plots(
    sweep_result,
    figures_dir: Path,
    image_format: str = "png",
    dpi: int = 110,
) -> list[str]:
    """Generate parameter sensitivity plots.

    For each (algorithm, parameter) with ≥2 data points, plot
    metric values vs parameter value.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    metrics_map = [
        ("silhouette", "Silhouette"),
        ("davies_bouldin", "Davies-Bouldin Index"),
        ("calinski_harabasz", "Calinski-Harabasz Index"),
        ("wcss", "WCSS"),
    ]

    # Group sensitivity records by (algorithm, parameter)
    by_algo_param: dict[tuple, list] = {}
    for rec in sweep_result.sensitivity_table:
        key = (rec.algorithm, rec.parameter)
        by_algo_param.setdefault(key, []).append(rec)

    for (algo, param), recs in sorted(by_algo_param.items()):
        if len(recs) < 2:
            continue

        # Sort by parameter value (numeric if possible)
        def sort_key(r):
            v = r.value
            if isinstance(v, (int, float)):
                return float(v)
            return str(v)

        sorted_recs = sorted(recs, key=sort_key)

        for metric_key, metric_label in metrics_map:
            values = []
            labels = []
            statuses = []
            for rec in sorted_recs:
                v = getattr(rec, metric_key)
                st = getattr(rec, f"{metric_key}_status")
                if v is not None and st == "VALID_VALUE":
                    values.append(float(v))
                    labels.append(str(rec.value))
                    statuses.append(st)

            if len(values) < 2:
                continue

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(
                range(len(values)),
                values,
                marker="o",
                linewidth=1.5,
                markersize=5,
                color="#1f77b4",
            )
            ax.set_xticks(range(len(values)))
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ax.set_xlabel(f"{param} value")
            ax.set_ylabel(metric_label)
            ax.set_title(f"{algo} — {param}: {metric_label} vs value")
            ax.grid(True, alpha=0.3)

            filename = f"exp03_{algo}_sensitivity_{param}_{metric_key}.{image_format}"
            output_path = figures_dir / filename
            fig.tight_layout()
            fig.savefig(output_path, dpi=dpi)
            plt.close(fig)
            written.append(str(output_path))

    return written


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run EXP-03 hyperparameter search."""
    print("[EXP-03] Starting hyperparameter search...")
    print(f"[EXP-03] Repository root: {_REPO_ROOT}")

    # Check config files
    if not _EXP03_CONFIG_PATH.exists():
        print(f"[EXP-03] ERROR: Config file not found: {_EXP03_CONFIG_PATH}")
        return 1

    if not _FRAMEWORK_CONFIG_PATH.exists():
        print(f"[EXP-03] ERROR: Framework config not found: {_FRAMEWORK_CONFIG_PATH}")
        return 1

    # Load configurations
    print("[EXP-03] Loading configurations...")
    with _EXP03_CONFIG_PATH.open("r", encoding="utf-8") as f:
        exp03_config = yaml.safe_load(f)

    with _FRAMEWORK_CONFIG_PATH.open("r", encoding="utf-8") as f:
        framework_config_text = f.read()

    framework_config = load_framework_config(_FRAMEWORK_CONFIG_PATH)
    config_sha = compute_text_sha256(framework_config_text)

    # Check FE-06 dataset
    if not _FE06_DATASET_PATH.exists():
        print(f"[EXP-03] ERROR: FE-06 dataset not found: {_FE06_DATASET_PATH}")
        return 1

    if not _FE06_METADATA_PATH.exists():
        print(f"[EXP-03] ERROR: FE-06 metadata not found: {_FE06_METADATA_PATH}")
        return 1

    # Compute input SHA
    print("[EXP-03] Computing input SHA...")
    input_sha = compute_file_sha256(_FE06_DATASET_PATH)
    expected_sha = "ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c"
    if input_sha != expected_sha:
        print("[EXP-03] WARNING: Input SHA mismatch.")
        print(f"[EXP-03]   Expected: {expected_sha}")
        print(f"[EXP-03]   Got:      {input_sha}")
    print(f"[EXP-03] Input SHA-256: {input_sha}")

    # Load data
    print("[EXP-03] Loading FE-06 dataset...")
    matrix_df = pd.read_parquet(_FE06_DATASET_PATH)
    metadata_df = pd.read_parquet(_FE06_METADATA_PATH)
    print(f"[EXP-03] Loaded {len(matrix_df)} samples, {len(matrix_df.columns)} features")
    print(f"[EXP-03] Customer metadata: {len(metadata_df)} rows")

    # Initialize runner
    exp03_section = exp03_config.get("exp03", {})
    runtime_cfg = exp03_section.get("runtime", {})
    baseline_seed = int(runtime_cfg.get("seed", 42))
    n_repeat = int(runtime_cfg.get("repeat", 5))

    print(f"[EXP-03] Baseline seed: {baseline_seed}")
    print(f"[EXP-03] Runtime repeat: {n_repeat}")

    runner = HyperparameterSearchRunner(
        framework_config,
        exp03_config,
        baseline_seed=baseline_seed,
        n_repeat=n_repeat,
        exclude_noise=True,
        noise_label=-1,
        exp02_candidates_csv_path=_EXP02_CANDIDATES_PATH,
    )

    # Run search
    print("[EXP-03] Running hyperparameter search...")
    print(f"[EXP-03] Total configurations: {len(runner._build_all_specs())}")

    sweep_result = runner.run(
        matrix_df,
        metadata_df,
        input_sha256=input_sha,
        input_path=str(_FE06_DATASET_PATH),
        metadata_path=str(_FE06_METADATA_PATH),
        config_text=framework_config_text,
        feature_set="rfm_extended",
    )

    # Print summary
    print("\n[EXP-03] Run summary:")
    print("-" * 60)
    for algo in CANONICAL_ORDER:
        algo_results = [r for r in sweep_result.results if r.algorithm == algo]
        if not algo_results:
            continue
        success = sum(1 for r in algo_results if r.status == "SUCCESS")
        total = len(algo_results)
        print(f"  {algo:15} {success}/{total} successful")
    print("-" * 60)

    failures = [r for r in sweep_result.results if r.status != "SUCCESS"]
    if failures:
        print(f"[EXP-03] WARNING: {len(failures)} run(s) failed:")
        for f in failures[:5]:
            print(f"  - {f.experiment_id}: {f.error}")

    # Generate reports
    print("\n[EXP-03] Generating reports...")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Manifest
    manifest = generate_manifest(sweep_result, exp03_config, config_sha)
    write_json(manifest, _REPORTS_DIR / "exp03_manifest.json")
    print(f"  - Written: {_REPORTS_DIR / 'exp03_manifest.json'}")

    # Run summary
    run_summary = generate_run_summary(sweep_result, config_sha)
    write_json(run_summary, _REPORTS_DIR / "exp03_run_summary.json")
    print(f"  - Written: {_REPORTS_DIR / 'exp03_run_summary.json'}")

    # Results CSV
    results_csv = generate_results_csv(sweep_result)
    write_csv(results_csv, _REPORTS_DIR / "exp03_hyperparameter_results.csv")
    print(f"  - Written: {_REPORTS_DIR / 'exp03_hyperparameter_results.csv'}")

    # Sensitivity CSV
    sensitivity_csv = generate_sensitivity_csv(sweep_result)
    write_csv(sensitivity_csv, _REPORTS_DIR / "exp03_parameter_sensitivity.csv")
    print(f"  - Written: {_REPORTS_DIR / 'exp03_parameter_sensitivity.csv'}")

    # Selected configurations CSV
    selected_csv = generate_selected_csv(sweep_result)
    write_csv(selected_csv, _REPORTS_DIR / "exp03_selected_configurations.csv")
    print(f"  - Written: {_REPORTS_DIR / 'exp03_selected_configurations.csv'}")

    # Markdown report
    md_report = generate_markdown_report(sweep_result, exp03_config, input_sha, config_sha)
    write_markdown(md_report, _REPORTS_DIR / "exp03_hyperparameter_analysis.md")
    print(f"  - Written: {_REPORTS_DIR / 'exp03_hyperparameter_analysis.md'}")

    # Visualization
    print("[EXP-03] Generating sensitivity plots...")
    image_format = "png"
    dpi = 110
    written_plots = generate_sensitivity_plots(
        sweep_result, _FIGURES_DIR, image_format=image_format, dpi=dpi
    )
    print(f"  - Written {len(written_plots)} plot(s) to {_FIGURES_DIR}")

    print("\n[EXP-03] Hyperparameter search completed!")
    print(f"[EXP-03] Total runs: {sweep_result.n_total_runs}")
    print(f"[EXP-03] Successful: {sweep_result.n_successful_runs}")
    print(f"[EXP-03] Sensitivity records: {len(sweep_result.sensitivity_table)}")
    print(f"[EXP-03] Selected configurations: {len(sweep_result.selected_configurations)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
