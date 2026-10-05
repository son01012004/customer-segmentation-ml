#!/usr/bin/env python3
"""EXP-01 Baseline Experiment Runner.

This script runs the EXP-01 baseline experiment across 5 clustering
algorithms:
1. K-Means
2. Agglomerative Clustering
3. DBSCAN
4. Gaussian Mixture Model
5. Fuzzy C-Means

Output artifacts:
- reports/exp01/exp01_baseline_manifest.json
- reports/exp01/exp01_baseline_summary.csv
- reports/exp01/exp01_initial_baseline.md
- reports/exp01/exp01_run_summary.json

EXP-01 Scope:
- Run 5 algorithms on the same FE-06 dataset.
- Compute unified evaluation metrics (silhouette, DBI, CH, WCSS).
- Measure algorithm execution runtime with repetition statistics.
- Record all metrics with applicability status.

EXP-01 does NOT:
- Rank or compare algorithms.
- Perform stability analysis.
- Profile customer segments.
"""

from __future__ import annotations

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

from customer_segmentation.clustering.baseline import (  # noqa: E402
    CANONICAL_ALGORITHMS,
    BaselineRunner,
)
from customer_segmentation.clustering.config import (  # noqa: E402
    compute_text_sha256,
    load_framework_config,
)

# ---------------------------------------------------------------------------
# Configuration paths
# ---------------------------------------------------------------------------

_EXP01_CONFIG_PATH = _REPO_ROOT / "configs" / "exp01_baseline.yaml"
_FRAMEWORK_CONFIG_PATH = _REPO_ROOT / "configs" / "clustering.yaml"
_FE06_DATASET_PATH = _REPO_ROOT / "data" / "processed" / "final_clustering_dataset.parquet"
_FE06_METADATA_PATH = _REPO_ROOT / "data" / "processed" / "customer_metadata.parquet"
_REPORTS_DIR = _REPO_ROOT / "reports" / "exp01"


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


def generate_manifest(results: list, config: dict[str, Any]) -> dict[str, Any]:
    """Generate baseline manifest JSON."""
    manifest = {
        "experiment_id": "EXP-01",
        "name": config.get("exp01", {}).get("name", "EXP-01 Baseline"),
        "description": config.get("exp01", {}).get("description", ""),
        "timestamp": now_utc_iso(),
        "algorithms": [],
        "config": {
            "baseline_seed": config.get("exp01", {}).get("baseline_seed", 42),
            "runtime_repeat": config.get("exp01", {}).get("runtime", {}).get("repeat", 5),
            "dbscan_exclude_noise": config.get("exp01", {})
            .get("dbscan", {})
            .get("exclude_noise_from_metrics", True),
            "wcss_exclude_noise": config.get("exp01", {})
            .get("wcss", {})
            .get("exclude_noise", True),
        },
        "canonical_order": CANONICAL_ALGORITHMS,
    }

    for result in results:
        entry = {
            "experiment_id": result.experiment_id,
            "algorithm": result.algorithm,
            "algorithm_version": result.algorithm_version,
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
                    "value": result.cluster_result.metrics.silhouette,
                    "status": result.cluster_result.metrics.extra.get(
                        "silhouette_status", "MISSING"
                    ),
                    "reason": result.cluster_result.metrics.extra.get("silhouette_reason"),
                },
                "davies_bouldin": {
                    "value": result.cluster_result.metrics.davies_bouldin,
                    "status": result.cluster_result.metrics.extra.get(
                        "davies_bouldin_status", "MISSING"
                    ),
                    "reason": result.cluster_result.metrics.extra.get("davies_bouldin_reason"),
                },
                "calinski_harabasz": {
                    "value": result.cluster_result.metrics.calinski_harabasz,
                    "status": result.cluster_result.metrics.extra.get(
                        "calinski_harabasz_status", "MISSING"
                    ),
                    "reason": result.cluster_result.metrics.extra.get("calinski_harabasz_reason"),
                },
                "wcss": {
                    "value": result.cluster_result.metrics.wcss,
                    "status": result.cluster_result.metrics.extra.get("wcss_status", "MISSING"),
                    "reason": result.cluster_result.metrics.extra.get("wcss_reason"),
                },
            },
            "input_sha256": result.input_sha256,
            "config_sha256": result.config_sha256,
            "library_versions": result.library_versions,
            "error": result.error,
        }
        manifest["algorithms"].append(entry)

    return manifest


def generate_summary_csv(results: list) -> pd.DataFrame:
    """Generate baseline summary CSV."""
    rows = []
    for result in results:
        row = {
            "algorithm": result.algorithm,
            "algorithm_version": result.algorithm_version,
            "n_clusters": result.n_clusters,
            "noise_count": result.noise_count,
            "noise_ratio": result.noise_ratio,
            "status": result.status,
            "silhouette": result.cluster_result.metrics.silhouette,
            "silhouette_status": result.cluster_result.metrics.extra.get(
                "silhouette_status", "MISSING"
            ),
            "silhouette_reason": result.cluster_result.metrics.extra.get("silhouette_reason"),
            "davies_bouldin": result.cluster_result.metrics.davies_bouldin,
            "davies_bouldin_status": result.cluster_result.metrics.extra.get(
                "davies_bouldin_status", "MISSING"
            ),
            "davies_bouldin_reason": result.cluster_result.metrics.extra.get(
                "davies_bouldin_reason"
            ),
            "calinski_harabasz": result.cluster_result.metrics.calinski_harabasz,
            "calinski_harabasz_status": result.cluster_result.metrics.extra.get(
                "calinski_harabasz_status", "MISSING"
            ),
            "calinski_harabasz_reason": result.cluster_result.metrics.extra.get(
                "calinski_harabasz_reason"
            ),
            "wcss": result.cluster_result.metrics.wcss,
            "wcss_status": result.cluster_result.metrics.extra.get("wcss_status", "MISSING"),
            "wcss_reason": result.cluster_result.metrics.extra.get("wcss_reason"),
            "runtime_mean_seconds": result.runtime_stats.get("mean_seconds"),
            "runtime_std_seconds": result.runtime_stats.get("std_seconds"),
            "runtime_min_seconds": result.runtime_stats.get("min_seconds"),
            "runtime_max_seconds": result.runtime_stats.get("max_seconds"),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def generate_markdown_report(results: list, config: dict[str, Any], input_sha: str) -> str:
    """Generate EXP-01 baseline markdown report."""
    md = f"""# EXP-01 Baseline Experiment Report

**Generated:** {now_utc_iso()}

## Mục tiêu

Thực thi baseline experiment thống nhất cho 5 thuật toán clustering:
K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means.

Baseline cung cấp:
- Mốc tham chiếu thống nhất cho EPIC-07 sweep.
- Bảo toàn evidence: input SHA, config SHA, hyperparameters, seed,
  library versions, evaluation metrics (value + status), runtime statistics.
- Hỗ trợ EPIC-07/EPIC-08 với unified metric schema.

## Cấu hình

| Tham số | Giá trị |
|---------|---------|
| Baseline seed | {config.get('exp01', {}).get('baseline_seed', 42)} |
| Runtime repeat | {config.get('exp01', {}).get('runtime', {}).get('repeat', 5)} |
| DBSCAN noise policy | Exclude noise: {config.get('exp01', {}).get('dbscan', {}).get('exclude_noise_from_metrics', True)} |
| WCSS noise policy | Exclude noise: {config.get('exp01', {}).get('wcss', {}).get('exclude_noise', True)} |

## Dữ liệu đầu vào

- **Dataset:** `{_FE06_DATASET_PATH}`
- **Input SHA-256:** `{input_sha}`

## Kết quả

### Bảng tổng hợp

| Algorithm | Version | Clusters | Noise | Silhouette | Silhouette Status | DBI | DBI Status | CH | CH Status | WCSS | WCSS Status | Runtime Mean (s) | Runtime Std (s) |
|-----------|---------|----------|-------|------------|-------------------|-----|------------|-----|-----------|------|-------------|-----------------|----------------|
"""

    for result in results:
        sil = result.cluster_result.metrics.silhouette
        dbi = result.cluster_result.metrics.davies_bouldin
        ch = result.cluster_result.metrics.calinski_harabasz
        wcss = result.cluster_result.metrics.wcss

        sil_str = f"{sil:.4f}" if sil is not None else "N/A"
        dbi_str = f"{dbi:.4f}" if dbi is not None else "N/A"
        ch_str = f"{ch:.2f}" if ch is not None else "N/A"
        wcss_str = f"{wcss:.2f}" if wcss is not None else "N/A"

        runtime_mean = result.runtime_stats.get("mean_seconds", 0)
        runtime_std = result.runtime_stats.get("std_seconds", 0)
        runtime_mean_str = f"{runtime_mean:.4f}" if runtime_mean is not None else "N/A"
        runtime_std_str = f"{runtime_std:.4f}" if runtime_std is not None else "N/A"

        noise_count = result.noise_count if result.noise_count is not None else 0

        md += f"| {result.algorithm} | {result.algorithm_version} | {result.n_clusters} | {noise_count} | {sil_str} | {result.cluster_result.metrics.extra.get('silhouette_status', 'MISSING')} | {dbi_str} | {result.cluster_result.metrics.extra.get('davies_bouldin_status', 'MISSING')} | {ch_str} | {result.cluster_result.metrics.extra.get('calinski_harabasz_status', 'MISSING')} | {wcss_str} | {result.cluster_result.metrics.extra.get('wcss_status', 'MISSING')} | {runtime_mean_str} | {runtime_std_str} |\n"

    md += """
## Chi tiết từng thuật toán

"""

    for result in results:
        md += f"""### {result.algorithm}

- **Experiment ID:** {result.experiment_id}
- **Version:** {result.algorithm_version}
- **Status:** {result.status}
- **Clusters discovered:** {result.n_clusters}
- **Noise count:** {result.noise_count if result.noise_count is not None else 'N/A'}
- **Noise ratio:** {result.noise_ratio if result.noise_ratio is not None else 'N/A'}
- **Hyperparameters:** {json.dumps(result.hyperparameters, indent=2)}

#### Metrics

| Metric | Value | Status | Reason |
|--------|-------|--------|--------|
| Silhouette | {result.cluster_result.metrics.silhouette} | {result.cluster_result.metrics.extra.get('silhouette_status', 'MISSING')} | {result.cluster_result.metrics.extra.get('silhouette_reason')} |
| Davies-Bouldin | {result.cluster_result.metrics.davies_bouldin} | {result.cluster_result.metrics.extra.get('davies_bouldin_status', 'MISSING')} | {result.cluster_result.metrics.extra.get('davies_bouldin_reason')} |
| Calinski-Harabasz | {result.cluster_result.metrics.calinski_harabasz} | {result.cluster_result.metrics.extra.get('calinski_harabasz_status', 'MISSING')} | {result.cluster_result.metrics.extra.get('calinski_harabasz_reason')} |
| WCSS | {result.cluster_result.metrics.wcss} | {result.cluster_result.metrics.extra.get('wcss_status', 'MISSING')} | {result.cluster_result.metrics.extra.get('wcss_reason')} |

#### Runtime Statistics

| Statistic | Value |
|-----------|-------|
| Mean | {result.runtime_stats.get('mean_seconds')}s |
| Std | {result.runtime_stats.get('std_seconds')}s |
| Min | {result.runtime_stats.get('min_seconds')}s |
| Max | {result.runtime_stats.get('max_seconds')}s |

"""

    md += """
## Scope Boundaries

### EXP-01 THỰC HIỆN

- Chạy 5 algorithms trên cùng input.
- Ghi nhận unified metrics (silhouette, DBI, CH, WCSS) với status rõ ràng.
- Bảo toàn reproducibility metadata.
- Đo runtime algorithm execution.
- Tạo aggregate baseline report.

### EXP-01 KHÔNG THỰC HIỆN

- Rank algorithm hoặc declare winner.
- Stability analysis (EXP-05 / EPIC-08 scope).
- Hyperparameter tuning (EPIC-07 scope).
- Customer profiling (EPIC-09 scope).

## Ghi chú quan trọng

- Các giá trị metric trong bảng trên là **observed evidence**, không phải
  comparative conclusion.
- Không có "best algorithm" hoặc "winner" trong report này.
- Metric status: VALID_VALUE (compute thành công), NOT_APPLICABLE
  (không áp dụng cho configuration hiện tại), COMPUTATION_ERROR
  (sklearn raise exception).
- Runtime đo chỉ algorithm execution, không gồm metric computation hoặc I/O.
"""

    return md


def generate_run_summary(results: list, config: dict[str, Any], input_sha: str) -> dict[str, Any]:
    """Generate run summary JSON."""
    return {
        "experiment_id": "EXP-01",
        "timestamp": now_utc_iso(),
        "input_sha256": input_sha,
        "config_sha256": None,  # Will be filled by runner
        "algorithms_run": len(results),
        "all_success": all(r.status == "SUCCESS" for r in results),
        "algorithms": [r.algorithm for r in results],
        "status_summary": {r.algorithm: r.status for r in results},
        "n_clusters_summary": {r.algorithm: r.n_clusters for r in results},
        "noise_summary": {
            r.algorithm: {"count": r.noise_count, "ratio": r.noise_ratio} for r in results
        },
        "metrics_summary": {
            r.algorithm: {
                "silhouette": {
                    "value": r.cluster_result.metrics.silhouette,
                    "status": r.cluster_result.metrics.extra.get("silhouette_status", "MISSING"),
                },
                "davies_bouldin": {
                    "value": r.cluster_result.metrics.davies_bouldin,
                    "status": r.cluster_result.metrics.extra.get(
                        "davies_bouldin_status", "MISSING"
                    ),
                },
                "calinski_harabasz": {
                    "value": r.cluster_result.metrics.calinski_harabasz,
                    "status": r.cluster_result.metrics.extra.get(
                        "calinski_harabasz_status", "MISSING"
                    ),
                },
                "wcss": {
                    "value": r.cluster_result.metrics.wcss,
                    "status": r.cluster_result.metrics.extra.get("wcss_status", "MISSING"),
                },
            }
            for r in results
        },
        "runtime_summary": {
            r.algorithm: {
                "mean_seconds": r.runtime_stats.get("mean_seconds"),
                "std_seconds": r.runtime_stats.get("std_seconds"),
                "min_seconds": r.runtime_stats.get("min_seconds"),
                "max_seconds": r.runtime_stats.get("max_seconds"),
            }
            for r in results
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run EXP-01 baseline experiment."""
    print("[EXP-01] Starting baseline experiment...")
    print(f"[EXP-01] Repository root: {_REPO_ROOT}")

    # Check config files
    if not _EXP01_CONFIG_PATH.exists():
        print(f"[EXP-01] ERROR: Config file not found: {_EXP01_CONFIG_PATH}")
        return 1

    if not _FRAMEWORK_CONFIG_PATH.exists():
        print(f"[EXP-01] ERROR: Framework config not found: {_FRAMEWORK_CONFIG_PATH}")
        return 1

    # Load configurations
    print("[EXP-01] Loading configurations...")
    with _EXP01_CONFIG_PATH.open("r", encoding="utf-8") as f:
        exp01_config = yaml.safe_load(f)

    with _FRAMEWORK_CONFIG_PATH.open("r", encoding="utf-8") as f:
        framework_config_text = f.read()

    framework_config = load_framework_config(_FRAMEWORK_CONFIG_PATH)
    config_sha = compute_text_sha256(framework_config_text)

    # Check FE-06 dataset
    if not _FE06_DATASET_PATH.exists():
        print(f"[EXP-01] ERROR: FE-06 dataset not found: {_FE06_DATASET_PATH}")
        print("[EXP-01] Please run FE-06 pipeline first.")
        return 1

    if not _FE06_METADATA_PATH.exists():
        print(f"[EXP-01] ERROR: FE-06 metadata not found: {_FE06_METADATA_PATH}")
        print("[EXP-01] Please run FE-06 pipeline first.")
        return 1

    # Compute input SHA
    print("[EXP-01] Computing input SHA...")
    input_sha = compute_file_sha256(_FE06_DATASET_PATH)
    print(f"[EXP-01] Input SHA-256: {input_sha}")

    # Load data
    print("[EXP-01] Loading FE-06 dataset...")
    matrix_df = pd.read_parquet(_FE06_DATASET_PATH)
    metadata_df = pd.read_parquet(_FE06_METADATA_PATH)
    print(f"[EXP-01] Loaded {len(matrix_df)} samples, {len(matrix_df.columns)} features")
    print(f"[EXP-01] Customer metadata: {len(metadata_df)} rows")

    # Verify alignment
    if len(matrix_df) != len(metadata_df):
        print(
            f"[EXP-01] WARNING: Matrix rows ({len(matrix_df)}) != metadata rows ({len(metadata_df)})"
        )

    # Initialize runner
    exp01_section = exp01_config.get("exp01", {})
    baseline_seed = exp01_section.get("baseline_seed", 42)
    n_repeat = exp01_section.get("runtime", {}).get("repeat", 5)
    exclude_noise = exp01_section.get("dbscan", {}).get("exclude_noise_from_metrics", True)
    noise_label = exp01_section.get("dbscan", {}).get("noise_label", -1)

    print(f"[EXP-01] Baseline seed: {baseline_seed}")
    print(f"[EXP-01] Runtime repeat: {n_repeat}")
    print(f"[EXP-01] Exclude noise: {exclude_noise}")

    runner = BaselineRunner(
        framework_config,
        exp01_config,
        baseline_seed=baseline_seed,
        n_repeat=n_repeat,
        exclude_noise=exclude_noise,
        noise_label=noise_label,
    )

    # Run all algorithms
    print("[EXP-01] Running all algorithms...")
    results = runner.run_all(
        matrix_df,
        metadata_df,
        input_sha256=input_sha,
        input_path=str(_FE06_DATASET_PATH),
        metadata_path=str(_FE06_METADATA_PATH),
        config_text=framework_config_text,
        output_dir=_REPORTS_DIR,
    )

    # Print summary
    print("\n[EXP-01] Results summary:")
    print("-" * 60)
    for result in results:
        status_icon = "✓" if result.status == "SUCCESS" else "✗"
        sil = result.cluster_result.metrics.silhouette
        sil_str = f"{sil:.4f}" if sil is not None else "N/A"
        noise_str = f"noise={result.noise_count}" if result.noise_count else ""
        print(
            f"  {status_icon} {result.algorithm:15} clusters={result.n_clusters:3} {noise_str:15} silhouette={sil_str}"
        )
    print("-" * 60)

    # Check for failures
    failures = [r for r in results if r.status != "SUCCESS"]
    if failures:
        print(f"[EXP-01] WARNING: {len(failures)} algorithm(s) failed:")
        for f in failures:
            print(f"  - {f.algorithm}: {f.error}")

    # Generate reports
    print("\n[EXP-01] Generating reports...")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Manifest
    manifest = generate_manifest(results, exp01_config)
    manifest["config_sha256"] = config_sha
    write_json(manifest, _REPORTS_DIR / "exp01_baseline_manifest.json")
    print(f"  - Written: {_REPORTS_DIR / 'exp01_baseline_manifest.json'}")

    # Summary CSV
    summary_csv = generate_summary_csv(results)
    write_csv(summary_csv, _REPORTS_DIR / "exp01_baseline_summary.csv")
    print(f"  - Written: {_REPORTS_DIR / 'exp01_baseline_summary.csv'}")

    # Markdown report
    md_report = generate_markdown_report(results, exp01_config, input_sha)
    write_markdown(md_report, _REPORTS_DIR / "exp01_initial_baseline.md")
    print(f"  - Written: {_REPORTS_DIR / 'exp01_initial_baseline.md'}")

    # Run summary
    run_summary = generate_run_summary(results, exp01_config, input_sha)
    run_summary["config_sha256"] = config_sha
    write_json(run_summary, _REPORTS_DIR / "exp01_run_summary.json")
    print(f"  - Written: {_REPORTS_DIR / 'exp01_run_summary.json'}")

    print("\n[EXP-01] Baseline experiment completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
