#!/usr/bin/env python3
"""EXP-02 Cluster Number Survey Runner.

This script runs the EXP-02 cluster number K survey across the
K-parameterized algorithms (K-Means, Agglomerative, GMM, Fuzzy C-Means)
with a working range K=2..10 (step=1), and includes a single DBSCAN
diagnostic run (no K-sweep).

Output artifacts (under reports/exp02/):
- exp02_manifest.json (all results with provenance)
- exp02_run_summary.json (machine-readable summary)
- exp02_cluster_number_summary.csv (flat per-run summary)
- exp02_candidate_cluster_numbers.csv (candidate K with evidence)
- exp02_metric_curves.csv (per algorithm × K × metric)
- exp02_cluster_number_analysis.md (Vietnamese narrative report)
- figures/exp02_<algorithm>_wcss_vs_k.png
- figures/exp02_<algorithm>_silhouette_vs_k.png
- figures/exp02_<algorithm>_davies_bouldin_vs_k.png
- figures/exp02_<algorithm>_calinski_harabasz_vs_k.png

EXP-02 scope:
- Survey ảnh hưởng của K cho K-bearing algorithms.
- Tạo metric curves.
- Đề xuất tập candidate cluster numbers có evidence.

EXP-02 does NOT:
- Rank algorithms.
- Pick "best K" / "optimal K" / "final K" / "recommended K".
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

from customer_segmentation.clustering.cluster_number import (  # noqa: E402
    ALGORITHMS_WITH_K,
    CANONICAL_ORDER,
    DIAGNOSTIC_ALGORITHMS,
    ClusterNumberRunner,
)
from customer_segmentation.clustering.config import (  # noqa: E402
    compute_text_sha256,
    load_framework_config,
)

# ---------------------------------------------------------------------------
# Configuration paths
# ---------------------------------------------------------------------------

_EXP02_CONFIG_PATH = _REPO_ROOT / "configs" / "exp02_cluster_number.yaml"
_FRAMEWORK_CONFIG_PATH = _REPO_ROOT / "configs" / "clustering.yaml"
_FE06_DATASET_PATH = _REPO_ROOT / "data" / "processed" / "final_clustering_dataset.parquet"
_FE06_METADATA_PATH = _REPO_ROOT / "data" / "processed" / "customer_metadata.parquet"
_REPORTS_DIR = _REPO_ROOT / "reports" / "exp02"
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


def generate_manifest(
    sweep_result,
    config: dict[str, Any],
    config_sha: str,
    framework_versions: dict[str, str],
) -> dict[str, Any]:
    """Generate EXP-02 manifest JSON."""
    exp02_section = config.get("exp02", {})

    manifest = {
        "experiment_id": "EXP-02",
        "name": exp02_section.get("name", "EXP-02 Cluster Number Survey"),
        "description": exp02_section.get("description", ""),
        "timestamp": now_utc_iso(),
        "dataset_version": config.get("exp02", {}).get("dataset", {}).get("version", "FE06-v1.0"),
        "input_sha256": sweep_result.input_sha256,
        "config_sha256": config_sha,
        "k_range": list(sweep_result.k_range),
        "feature_set": sweep_result.feature_set,
        "feature_set_note": config.get("exp02", {})
        .get("feature_sets", [{}])[0]
        .get("description", ""),
        "n_total_runs": sweep_result.n_total_runs,
        "n_successful_runs": sweep_result.n_successful_runs,
        "algorithms_sweep": list(ALGORITHMS_WITH_K.keys()),
        "diagnostic_algorithms": list(DIAGNOSTIC_ALGORITHMS),
        "canonical_algorithm_order": CANONICAL_ORDER,
        "library_versions": framework_versions,
        "decision_status": config.get("exp02", {}).get("decision_status", {}),
        "scope_boundaries": config.get("exp02", {}).get("scope_boundaries", []),
        "pending_review_notes": config.get("exp02", {}).get("pending_review_notes", []),
        "assumptions": config.get("exp02", {}).get("assumptions", []),
        "results": [],
        "candidates": [],
    }

    # ---- Per-(algorithm, K) results ----
    for result in sweep_result.results:
        m = result.cluster_result.metrics if result.cluster_result else None
        extra = m.extra if m else {}
        entry = {
            "experiment_id": result.experiment_id,
            "algorithm": result.algorithm,
            "K": result.K,
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

    # ---- Candidates ----
    for cand in sweep_result.candidates:
        manifest["candidates"].append(
            {
                "algorithm": cand.algorithm,
                "feature_set": cand.feature_set,
                "K": cand.K,
                "silhouette": {
                    "value": cand.silhouette_value,
                    "status": cand.silhouette_status,
                },
                "davies_bouldin": {
                    "value": cand.davies_bouldin_value,
                    "status": cand.davies_bouldin_status,
                },
                "calinski_harabasz": {
                    "value": cand.calinski_harabasz_value,
                    "status": cand.calinski_harabasz_status,
                },
                "wcss": {
                    "value": cand.wcss_value,
                    "status": cand.wcss_status,
                },
                "evidence_indicators": cand.evidence_indicators,
                "agreement_count": cand.agreement_count,
            }
        )

    return manifest


def generate_run_summary(sweep_result, config_sha: str) -> dict[str, Any]:
    """Generate EXP-02 run summary JSON."""
    return {
        "experiment_id": "EXP-02",
        "timestamp": now_utc_iso(),
        "input_sha256": sweep_result.input_sha256,
        "config_sha256": config_sha,
        "feature_set": sweep_result.feature_set,
        "k_range": list(sweep_result.k_range),
        "n_total_runs": sweep_result.n_total_runs,
        "n_successful_runs": sweep_result.n_successful_runs,
        "all_success": sweep_result.n_successful_runs == sweep_result.n_total_runs,
        "results_by_status": {
            "SUCCESS": sum(1 for r in sweep_result.results if r.status == "SUCCESS"),
            "FAILED": sum(1 for r in sweep_result.results if r.status != "SUCCESS"),
        },
        "n_candidates": len(sweep_result.candidates),
        "candidates": [
            {
                "algorithm": c.algorithm,
                "K": c.K,
                "evidence_indicators": c.evidence_indicators,
                "agreement_count": c.agreement_count,
            }
            for c in sweep_result.candidates
        ],
        "library_versions": sweep_result.library_versions,
    }


def generate_summary_csv(sweep_result) -> pd.DataFrame:
    """Generate flat per-run summary CSV."""
    rows = []
    for result in sweep_result.results:
        m = result.cluster_result.metrics if result.cluster_result else None
        extra = m.extra if m else {}
        row = {
            "experiment_id": result.experiment_id,
            "algorithm": result.algorithm,
            "K": result.K,
            "n_clusters": result.n_clusters,
            "noise_count": result.noise_count,
            "noise_ratio": result.noise_ratio,
            "status": result.status,
            "silhouette": m.silhouette if m else None,
            "silhouette_status": extra.get("silhouette_status", "MISSING") if m else "MISSING",
            "silhouette_reason": extra.get("silhouette_reason") if m else None,
            "davies_bouldin": m.davies_bouldin if m else None,
            "davies_bouldin_status": (
                extra.get("davies_bouldin_status", "MISSING") if m else "MISSING"
            ),
            "davies_bouldin_reason": extra.get("davies_bouldin_reason") if m else None,
            "calinski_harabasz": m.calinski_harabasz if m else None,
            "calinski_harabasz_status": (
                extra.get("calinski_harabasz_status", "MISSING") if m else "MISSING"
            ),
            "calinski_harabasz_reason": extra.get("calinski_harabasz_reason") if m else None,
            "wcss": m.wcss if m else None,
            "wcss_status": extra.get("wcss_status", "MISSING") if m else "MISSING",
            "wcss_reason": extra.get("wcss_reason") if m else None,
            "runtime_mean_seconds": result.runtime_stats.get("mean_seconds"),
            "runtime_std_seconds": result.runtime_stats.get("std_seconds"),
            "runtime_min_seconds": result.runtime_stats.get("min_seconds"),
            "runtime_max_seconds": result.runtime_stats.get("max_seconds"),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def generate_metric_curves_csv(sweep_result) -> pd.DataFrame:
    """Generate metric curves CSV (long format)."""
    rows = []
    for algo, k_data in sweep_result.metric_curves.items():
        for k_val, d in sorted(k_data.items()):
            row = {
                "algorithm": algo,
                "K": k_val,
                "feature_set": sweep_result.feature_set,
                "silhouette": d["silhouette"],
                "silhouette_status": d["silhouette_status"],
                "davies_bouldin": d["davies_bouldin"],
                "davies_bouldin_status": d["davies_bouldin_status"],
                "calinski_harabasz": d["calinski_harabasz"],
                "calinski_harabasz_status": d["calinski_harabasz_status"],
                "wcss": d["wcss"],
                "wcss_status": d["wcss_status"],
                "n_clusters": d["n_clusters"],
                "noise_count": d["noise_count"],
                "noise_ratio": d["noise_ratio"],
                "runtime_mean_seconds": d["runtime_mean"],
                "runtime_std_seconds": d["runtime_std"],
            }
            rows.append(row)
    return pd.DataFrame(rows)


def generate_candidates_csv(sweep_result) -> pd.DataFrame:
    """Generate candidate cluster numbers CSV."""
    rows = []
    for cand in sweep_result.candidates:
        row = {
            "algorithm": cand.algorithm,
            "feature_set": cand.feature_set,
            "K": cand.K,
            "silhouette": cand.silhouette_value,
            "silhouette_status": cand.silhouette_status,
            "davies_bouldin": cand.davies_bouldin_value,
            "davies_bouldin_status": cand.davies_bouldin_status,
            "calinski_harabasz": cand.calinski_harabasz_value,
            "calinski_harabasz_status": cand.calinski_harabasz_status,
            "wcss": cand.wcss_value,
            "wcss_status": cand.wcss_status,
            "evidence_indicators": ";".join(cand.evidence_indicators),
            "agreement_count": cand.agreement_count,
            "decision_status": "CANDIDATE",  # NOT "best", NOT "recommended"
        }
        rows.append(row)
    return pd.DataFrame(rows)


def generate_markdown_report(sweep_result, config: dict[str, Any], input_sha: str) -> str:
    """Generate EXP-02 cluster number analysis markdown report (Vietnamese)."""
    md = f"""# EXP-02 Cluster Number Survey Report

**Generated:** {now_utc_iso()}

## Mục tiêu

Khảo sát ảnh hưởng của số lượng cluster/component (K) đối với 4 thuật
toán có tham số K trong EPIC-06:

- K-Means (K = n_clusters)
- Agglomerative (K = n_clusters)
- GMM (K = n_components)
- Fuzzy C-Means (K = n_clusters)

DBSCAN được ghi nhận như một diagnostic entry đơn lẻ (không có K parameter),
không nằm trong K-sweep.

EXP-02 cung cấp:

- **Metric curves**: silhouette, Davies-Bouldin, Calinski-Harabasz, WCSS
  theo K cho mỗi thuật toán.
- **Evidence-based candidate cluster numbers**: tập K được đề xuất dựa trên
  evidence từ metrics (top-N cho silhouette/CH, bottom-N cho DBI, WCSS elbow).
- **Bảo toàn provenance**: input SHA, config SHA, hyperparameters, seed,
  library versions cho mỗi (algorithm, K) combination.
- **Hỗ trợ EPIC-08** với evidence thay vì ranking hoặc so sánh thuật toán.

## Cấu hình

| Tham số | Giá trị |
|---------|---------|
| Dataset version | {config.get('exp02', {}).get('dataset', {}).get('version', 'FE06-v1.0')} |
| Feature set | {sweep_result.feature_set} (FE-06 Extended RFM 14 features) |
| K range | {sweep_result.k_range[0]}..{sweep_result.k_range[1]} (step=1) |
| Baseline seed | {config.get('exp02', {}).get('runtime', {}).get('seed', 42)} |
| Runtime repeat | {config.get('exp02', {}).get('runtime', {}).get('repeat', 5)} |
| DBSCAN policy | Exclude noise: {config.get('exp02', {}).get('metrics', {}).get('status_policy', 'exp01_mirror')} |
| Candidate heuristic | top_n={config.get('exp02', {}).get('candidate_heuristic', {}).get('top_n_per_indicator', 3)}, min_agreement={config.get('exp02', {}).get('candidate_heuristic', {}).get('min_agreement_count', 2)} |

## Dữ liệu đầu vào

- **Dataset:** `{_FE06_DATASET_PATH}`
- **Input SHA-256:** `{input_sha}`

## Kết quả tổng hợp

| Algorithm | K range | Successful runs | Total runs |
|-----------|---------|-----------------|------------|
"""

    algo_run_count = {}
    for r in sweep_result.results:
        algo_run_count.setdefault(r.algorithm, [0, 0])
        algo_run_count[r.algorithm][0] += 1
        if r.status == "SUCCESS":
            algo_run_count[r.algorithm][1] += 1

    for algo in CANONICAL_ORDER:
        if algo in algo_run_count:
            total, success = algo_run_count[algo]
            k_range_str = (
                f"{sweep_result.k_range[0]}..{sweep_result.k_range[1]}"
                if algo in ALGORITHMS_WITH_K
                else "(diagnostic)"
            )
            md += f"| {algo} | {k_range_str} | {success} | {total} |\n"

    md += f"""
**Tổng số runs:** {sweep_result.n_total_runs}
**Successful:** {sweep_result.n_successful_runs}

## Metric curves theo từng thuật toán

"""

    # Per-algorithm metric tables
    for algo in CANONICAL_ORDER:
        if algo not in sweep_result.metric_curves and algo not in DIAGNOSTIC_ALGORITHMS:
            continue

        md += f"### {algo}\n\n"

        if algo in DIAGNOSTIC_ALGORITHMS:
            # Diagnostic algorithm
            results = [r for r in sweep_result.results if r.algorithm == algo]
            if results:
                r = results[0]
                md += f"- **Status:** {r.status}\n"
                md += f"- **Cluster count phát hiện được:** {r.n_clusters}\n"
                md += f"- **Noise count:** {r.noise_count}\n"
                md += f"- **Noise ratio:** {r.noise_ratio:.4f}\n"
                md += f"- **Hyperparameters:** {json.dumps(r.hyperparameters, indent=2, default=str)}\n"

                if r.cluster_result is not None:
                    m = r.cluster_result.metrics
                    extra = m.extra
                    md += f"- **Silhouette:** {m.silhouette} ({extra.get('silhouette_status', 'MISSING')})\n"
                    md += f"- **DBI:** {m.davies_bouldin} ({extra.get('davies_bouldin_status', 'MISSING')})\n"
                    md += f"- **CH:** {m.calinski_harabasz} ({extra.get('calinski_harabasz_status', 'MISSING')})\n"
                    md += f"- **WCSS:** {m.wcss} ({extra.get('wcss_status', 'MISSING')})\n"
            md += "\n"
            continue

        k_data = sweep_result.metric_curves.get(algo, {})
        if not k_data:
            md += "(Không có data)\n\n"
            continue

        md += "| K | n_clusters | Silhouette | Status | DBI | Status | CH | Status | WCSS | Status | Runtime Mean (s) |\n"
        md += "|---|------------|------------|--------|-----|--------|----|--------|------|--------|------------------|\n"

        for k_val in sorted(k_data):
            d = k_data[k_val]
            sil_str = f"{d['silhouette']:.4f}" if d.get("silhouette") is not None else "N/A"
            dbi_str = f"{d['davies_bouldin']:.4f}" if d.get("davies_bouldin") is not None else "N/A"
            ch_str = (
                f"{d['calinski_harabasz']:.2f}" if d.get("calinski_harabasz") is not None else "N/A"
            )
            wcss_str = f"{d['wcss']:.2f}" if d.get("wcss") is not None else "N/A"
            rt_str = f"{d['runtime_mean']:.4f}" if d.get("runtime_mean") is not None else "N/A"
            md += (
                f"| {k_val} | {d['n_clusters']} | "
                f"{sil_str} | {d['silhouette_status']} | "
                f"{dbi_str} | {d['davies_bouldin_status']} | "
                f"{ch_str} | {d['calinski_harabasz_status']} | "
                f"{wcss_str} | {d['wcss_status']} | {rt_str} |\n"
            )
        md += "\n"

    md += """## Candidate cluster numbers (evidence-based)

Các K dưới đây được flag bởi evidence heuristics (transparent, deterministic).
Đây KHÔNG phải "best K", "optimal K", "final K", hay "recommended K" — chỉ
là tập K worth inspecting cho các giai đoạn sau (EPIC-08 / mentor review).

| Algorithm | K | Silhouette | DBI | CH | WCSS | Evidence | Agreement |
|-----------|---|------------|-----|-----|------|----------|-----------|
"""

    if sweep_result.candidates:
        for cand in sweep_result.candidates:
            sil_str = f"{cand.silhouette_value:.4f}" if cand.silhouette_value is not None else "N/A"
            dbi_str = (
                f"{cand.davies_bouldin_value:.4f}"
                if cand.davies_bouldin_value is not None
                else "N/A"
            )
            ch_str = (
                f"{cand.calinski_harabasz_value:.2f}"
                if cand.calinski_harabasz_value is not None
                else "N/A"
            )
            wcss_str = f"{cand.wcss_value:.2f}" if cand.wcss_value is not None else "N/A"
            evidence_str = ", ".join(cand.evidence_indicators)
            md += f"| {cand.algorithm} | {cand.K} | {sil_str} | {dbi_str} | {ch_str} | {wcss_str} | {evidence_str} | {cand.agreement_count} |\n"
    else:
        md += "*(Không có candidate nào được flag — min_agreement threshold chưa đạt)*\n"

    md += f"""
**Tổng số candidates:** {len(sweep_result.candidates)}

### Boundary về "candidate" semantics

- "candidate" = K được flag bởi ít nhất {config.get('exp02', {}).get('candidate_heuristic', {}).get('min_agreement_count', 2)} indicator(s)
  trong số: silhouette top-N, DBI bottom-N, CH top-N, WCSS elbow drop.
- Không có "best K" / "optimal K" / "final K" / "recommended K" trong report này.
- Việc chọn K cuối cùng thuộc về EPIC-08 và mentor/human researcher.
- Nếu các indicator disagreement (mỗi indicator flag K khác nhau), điều đó
  được ghi nhận trong evidence_indicators — không tự resolve.

## Visualization

Factual diagnostic plots (không có business interpretation). Đã sinh ra:

"""

    if _FIGURES_DIR.exists():
        png_files = sorted(_FIGURES_DIR.glob("*.png"))
        for png in png_files:
            md += f"- `reports/exp02/figures/{png.name}`\n"

    md += """
## PENDING_REVIEW decisions

"""

    for note in config.get("exp02", {}).get("pending_review_notes", []):
        md += f"- {note}\n"

    md += """
## Scope boundaries

### EXP-02 THỰC HIỆN

- K-sweep cho K-Means, Agglomerative, GMM, Fuzzy C-Means (K=2..10, step=1).
- Diagnostic run cho DBSCAN (không sweep).
- Reuse EXP-01 metrics layer (silhouette / DBI / CH / WCSS) verbatim.
- WCSS dùng arithmetic centroid từ hard labels (GMM/FCM dùng argmax).
- DBSCAN noise bị exclude khỏi internal metrics và WCSS (mirror EXP-01).
- Đo runtime algorithm execution (n_repeat × mean/std/min/max) cho mỗi (algorithm, K).
- Tạo metric curves, evidence-based candidates, diagnostic plots.

### EXP-02 KHÔNG THỰC HIỆN

- Rank algorithms.
- Chọn "best K", "optimal K", "final K", "recommended K".
- Stability analysis across seeds (EXP-05 / EPIC-08 scope).
- Sweep non-K hyperparameters (linkage, covariance_type, fuzziness, ...).
- Customer profiling / segment naming.
- Business interpretation.

### PENDING_REVIEW

- **EXP02-FS-01 (gap):** Repo currently exposes FE-06 final clustering matrix only
  as the full Extended RFM (14-feature) matrix. No RFM-only parquet artifact is
  present. EXP-02 therefore runs on RFM Extended only. RQ2 dimension requires
  separate FE-06 sub-artifact.
"""

    return md


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------


def generate_metric_curve_plots(
    sweep_result,
    figures_dir: Path,
    image_format: str = "png",
    dpi: int = 110,
) -> list[str]:
    """Generate metric curve plots for each algorithm.

    Parameters
    ----------
    sweep_result : ClusterNumberSweepResult
        Sweep result with metric curves.
    figures_dir : Path
        Output directory for plots.
    image_format : str
        Image format (png, pdf, svg).
    dpi : int
        Resolution.

    Returns
    -------
    written : list of str
        List of file paths written.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    metrics_to_plot = [
        ("wcss", "WCSS"),
        ("silhouette", "Silhouette"),
        ("davies_bouldin", "Davies-Bouldin Index"),
        ("calinski_harabasz", "Calinski-Harabasz Index"),
    ]

    for algo, k_data in sweep_result.metric_curves.items():
        k_values = sorted(k_data.keys())
        if not k_values:
            continue

        for metric_key, metric_label in metrics_to_plot:
            values = []
            valid_ks = []
            statuses = []
            for k_val in k_values:
                d = k_data[k_val]
                v = d.get(metric_key)
                status = d.get(f"{metric_key}_status", "MISSING")
                if v is not None and status == "VALID_VALUE":
                    values.append(float(v))
                    valid_ks.append(k_val)
                    statuses.append(status)

            if not valid_ks:
                continue

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(
                valid_ks,
                values,
                marker="o",
                linewidth=1.5,
                markersize=5,
                color="#1f77b4",
            )
            ax.set_xlabel("K (number of clusters / components)")
            ax.set_ylabel(metric_label)
            ax.set_title(f"{algo} — {metric_label} vs K")
            ax.set_xticks(valid_ks)
            ax.grid(True, alpha=0.3)

            filename = f"exp02_{algo}_{metric_key}_vs_k.{image_format}"
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
    """Run EXP-02 cluster number survey."""
    print("[EXP-02] Starting cluster number survey...")
    print(f"[EXP-02] Repository root: {_REPO_ROOT}")

    # Check config files
    if not _EXP02_CONFIG_PATH.exists():
        print(f"[EXP-02] ERROR: Config file not found: {_EXP02_CONFIG_PATH}")
        return 1

    if not _FRAMEWORK_CONFIG_PATH.exists():
        print(f"[EXP-02] ERROR: Framework config not found: {_FRAMEWORK_CONFIG_PATH}")
        return 1

    # Load configurations
    print("[EXP-02] Loading configurations...")
    with _EXP02_CONFIG_PATH.open("r", encoding="utf-8") as f:
        exp02_config = yaml.safe_load(f)

    with _FRAMEWORK_CONFIG_PATH.open("r", encoding="utf-8") as f:
        framework_config_text = f.read()

    framework_config = load_framework_config(_FRAMEWORK_CONFIG_PATH)
    config_sha = compute_text_sha256(framework_config_text)

    # Check FE-06 dataset
    if not _FE06_DATASET_PATH.exists():
        print(f"[EXP-02] ERROR: FE-06 dataset not found: {_FE06_DATASET_PATH}")
        print("[EXP-02] Please run FE-06 pipeline first.")
        return 1

    if not _FE06_METADATA_PATH.exists():
        print(f"[EXP-02] ERROR: FE-06 metadata not found: {_FE06_METADATA_PATH}")
        print("[EXP-02] Please run FE-06 pipeline first.")
        return 1

    # Compute input SHA
    print("[EXP-02] Computing input SHA...")
    input_sha = compute_file_sha256(_FE06_DATASET_PATH)
    expected_sha = "ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c"
    if input_sha != expected_sha:
        print("[EXP-02] WARNING: Input SHA mismatch.")
        print(f"[EXP-02]   Expected: {expected_sha}")
        print(f"[EXP-02]   Got:      {input_sha}")
    print(f"[EXP-02] Input SHA-256: {input_sha}")

    # Load data
    print("[EXP-02] Loading FE-06 dataset...")
    matrix_df = pd.read_parquet(_FE06_DATASET_PATH)
    metadata_df = pd.read_parquet(_FE06_METADATA_PATH)
    print(f"[EXP-02] Loaded {len(matrix_df)} samples, {len(matrix_df.columns)} features")
    print(f"[EXP-02] Customer metadata: {len(metadata_df)} rows")

    # Initialize runner
    exp02_section = exp02_config.get("exp02", {})
    runtime_cfg = exp02_section.get("runtime", {})
    baseline_seed = runtime_cfg.get("seed", 42)
    n_repeat = runtime_cfg.get("repeat", 5)

    print(f"[EXP-02] Baseline seed: {baseline_seed}")
    print(f"[EXP-02] Runtime repeat: {n_repeat}")

    runner = ClusterNumberRunner(
        framework_config,
        exp02_config,
        baseline_seed=baseline_seed,
        n_repeat=n_repeat,
        exclude_noise=True,
        noise_label=-1,
    )

    # Run full sweep
    print("[EXP-02] Running K-sweep...")
    sweep_result = runner.run_sweep(
        matrix_df,
        metadata_df,
        input_sha256=input_sha,
        input_path=str(_FE06_DATASET_PATH),
        metadata_path=str(_FE06_METADATA_PATH),
        config_text=framework_config_text,
        feature_set="rfm_extended",
    )

    # Print summary
    print("\n[EXP-02] Run summary:")
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
        print(f"[EXP-02] WARNING: {len(failures)} run(s) failed:")
        for f in failures:
            print(f"  - {f.experiment_id}: {f.error}")

    # Generate reports
    print("\n[EXP-02] Generating reports...")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # Manifest
    framework_versions = sweep_result.library_versions if sweep_result.library_versions else {}
    manifest = generate_manifest(sweep_result, exp02_config, config_sha, framework_versions)
    write_json(manifest, _REPORTS_DIR / "exp02_manifest.json")
    print(f"  - Written: {_REPORTS_DIR / 'exp02_manifest.json'}")

    # Run summary
    run_summary = generate_run_summary(sweep_result, config_sha)
    write_json(run_summary, _REPORTS_DIR / "exp02_run_summary.json")
    print(f"  - Written: {_REPORTS_DIR / 'exp02_run_summary.json'}")

    # Cluster number summary CSV
    summary_csv = generate_summary_csv(sweep_result)
    write_csv(summary_csv, _REPORTS_DIR / "exp02_cluster_number_summary.csv")
    print(f"  - Written: {_REPORTS_DIR / 'exp02_cluster_number_summary.csv'}")

    # Metric curves CSV
    curves_csv = generate_metric_curves_csv(sweep_result)
    write_csv(curves_csv, _REPORTS_DIR / "exp02_metric_curves.csv")
    print(f"  - Written: {_REPORTS_DIR / 'exp02_metric_curves.csv'}")

    # Candidates CSV
    candidates_csv = generate_candidates_csv(sweep_result)
    write_csv(candidates_csv, _REPORTS_DIR / "exp02_candidate_cluster_numbers.csv")
    print(f"  - Written: {_REPORTS_DIR / 'exp02_candidate_cluster_numbers.csv'}")

    # Markdown report
    md_report = generate_markdown_report(sweep_result, exp02_config, input_sha)
    write_markdown(md_report, _REPORTS_DIR / "exp02_cluster_number_analysis.md")
    print(f"  - Written: {_REPORTS_DIR / 'exp02_cluster_number_analysis.md'}")

    # Visualization
    viz_cfg = exp02_section.get("visualization", {})
    if viz_cfg.get("enabled", True):
        print("[EXP-02] Generating diagnostic plots...")
        figures_dir = _REPO_ROOT / viz_cfg.get("figures_dir", "./reports/exp02/figures").lstrip(
            "./"
        )
        figures_dir = _REPO_ROOT / "reports" / "exp02" / "figures"
        image_format = viz_cfg.get("image_format", "png")
        dpi = viz_cfg.get("dpi", 110)
        written_plots = generate_metric_curve_plots(
            sweep_result, figures_dir, image_format=image_format, dpi=dpi
        )
        print(f"  - Written {len(written_plots)} plot(s) to {figures_dir}")

    print("\n[EXP-02] Cluster number survey completed successfully!")
    print(f"[EXP-02] Total runs: {sweep_result.n_total_runs}")
    print(f"[EXP-02] Successful: {sweep_result.n_successful_runs}")
    print(f"[EXP-02] Candidates: {len(sweep_result.candidates)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
