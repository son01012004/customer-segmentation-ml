"""ML-02 orchestrator: K-Means initial diagnostic run.

Stage: 06_clustering / ML-02 (K-Means)

This script runs a **single, value-neutral diagnostic K-Means
experiment** on the FE-06 final clustering dataset via the ML-01
Experiment Framework. It is intended as a smoke test and as the
initial evidence for the EPIC-06 Documentation Contract — it does
NOT sweep K, does NOT compare algorithms, and does NOT pick a
"best" cluster count.

Usage (from the repository root):

    python -m scripts.run_ml02_kmeans
    python -m scripts.run_ml02_kmeans --n-clusters 5 --seed 7

Outputs
-------

Written under ``data/processed/clustering_experiments/``:

- ``cluster_labels_{experiment_id}.parquet`` — CustomerID + ClusterLabel + IsNoise.
- ``experiment_log_{experiment_id}.json`` — full ExperimentResult payload.

Written under ``reports/ml02/``:

- ``ml02_run_summary.json`` — summary of the diagnostic run
  (input/output SHA, hyperparameters, status, n_clusters, ...).
- ``ml02_initial_diagnostic.md`` — Vietnamese narrative report of
  the diagnostic run (diagnostic-only; no "best" claims).

Hard constraints (AGENTS.md §2, EPIC06 contract):

- No algorithm comparison (EPIC-08).
- No sweep over K (EPIC-07).
- No segment profiling / naming (EPIC-09).
- No "best / optimal / recommended" claim.
- FE-06 outputs are READ-ONLY.
- Reproducibility metadata (SHA, seed, library versions) is recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from customer_segmentation.clustering import (  # noqa: E402
    ExperimentRunner,
    ExperimentSpec,
    compute_text_sha256,
    load_framework_config,
    resolve_framework_config_path,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PROCESSED_DIR: Path = _REPO_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "ml02"
DEFAULT_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "clustering.yaml"
DEFAULT_INPUT_PATH: Path = DEFAULT_PROCESSED_DIR / "final_clustering_dataset.parquet"
DEFAULT_METADATA_PATH: Path = DEFAULT_PROCESSED_DIR / "customer_metadata.parquet"
DEFAULT_ARTIFACTS_DIR: Path = DEFAULT_PROCESSED_DIR / "clustering_experiments"

# ML-02 working defaults — WORKING_ASSUMPTION, not final approved.
DEFAULT_N_CLUSTERS: int = 4
DEFAULT_INIT: str = "k-means++"
DEFAULT_N_INIT: int = 10
DEFAULT_MAX_ITER: int = 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    """Compute the SHA-256 of a file's contents."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "ML-02 K-Means initial diagnostic run. "
            "Reads data/processed/final_clustering_dataset.parquet and "
            "data/processed/customer_metadata.parquet. "
            "Writes artifacts under data/processed/clustering_experiments/ "
            "and reports under reports/ml02/."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to the clustering YAML. If omitted, auto-discovers "
        "'configs/clustering.yaml'.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to final_clustering_dataset.parquet (FE-06 output).",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA_PATH,
        help="Path to customer_metadata.parquet (FE-06 output).",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help="Output directory for cluster_labels + experiment_log.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Output directory for ML-02 reports.",
    )
    parser.add_argument(
        "--n-clusters",
        type=int,
        default=DEFAULT_N_CLUSTERS,
        help=f"Number of clusters K (working default: {DEFAULT_N_CLUSTERS}).",
    )
    parser.add_argument(
        "--init",
        type=str,
        default=DEFAULT_INIT,
        choices=["k-means++", "random"],
        help=f"Initialization strategy (working default: {DEFAULT_INIT}).",
    )
    parser.add_argument(
        "--n-init",
        type=int,
        default=DEFAULT_N_INIT,
        help=f"Number of random restarts (working default: {DEFAULT_N_INIT}).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=DEFAULT_MAX_ITER,
        help=f"Maximum iterations per restart (working default: {DEFAULT_MAX_ITER}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (overrides framework.random_seed.default). "
        "If omitted, the framework YAML default is used.",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment identifier. If omitted, an ID is generated from " "the hyperparameters.",
    )
    return parser


def _build_experiment_id(args: argparse.Namespace) -> str:
    """Build a stable experiment identifier from the hyperparameters."""
    return (
        f"ML-02-KMeans-k{args.n_clusters}-"
        f"{args.init.replace('+', 'plus').replace('-', '_')}-"
        f"ninit{args.n_init}-maxiter{args.max_iter}-seed{args.seed if args.seed is not None else 'cfg'}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)

    # ---- Load framework config ----
    cfg_path = args.config or resolve_framework_config_path()
    if cfg_path is None:
        raise FileNotFoundError(
            "Could not resolve configs/clustering.yaml. " "Pass --config explicitly."
        )
    cfg = load_framework_config(cfg_path)
    cfg_text = cfg_path.read_text(encoding="utf-8")
    config_sha = compute_text_sha256(cfg_text)

    print(f"[ML-02] config:           {cfg_path}")
    print(f"[ML-02] config SHA-256:   {config_sha[:16]}...")
    print(f"[ML-02] dataset version:  {cfg.input.dataset_version}")

    # ---- Load FE-06 inputs ----
    input_path: Path = args.input
    metadata_path: Path = args.metadata
    if not input_path.exists():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Customer metadata not found: {metadata_path}")

    df = pd.read_parquet(input_path)
    md = pd.read_parquet(metadata_path)
    input_sha = _file_sha256(input_path)
    metadata_sha = _file_sha256(metadata_path)
    print(f"[ML-02] input SHA-256:    {input_sha[:16]}...")
    print(f"[ML-02] metadata SHA-256: {metadata_sha[:16]}...")
    print(f"[ML-02] matrix shape:     {df.shape}")

    # ---- Build experiment spec ----
    experiment_id = args.experiment_id or _build_experiment_id(args)
    hyperparameters = {
        "n_clusters": args.n_clusters,
        "init": args.init,
        "n_init": args.n_init,
        "max_iter": args.max_iter,
    }
    spec = ExperimentSpec(
        experiment_id=experiment_id,
        algorithm="kmeans",
        hyperparameters=hyperparameters,
        seed_override=args.seed,
    )
    print(f"[ML-02] experiment id:    {experiment_id}")
    print(f"[ML-02] hyperparameters:  {hyperparameters}")

    # ---- Run ----
    artifacts_dir = args.artifacts_dir
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    runner = ExperimentRunner(
        cfg,
        spec,
        config_source=f"yaml:{cfg_path}",
        config_text=cfg_text,
    )
    result = runner.run(
        df,
        md,
        input_sha256=input_sha,
        input_path=str(input_path),
        metadata_path=str(metadata_path),
        output_dir=artifacts_dir,
    )

    # ---- Build ML-02 run summary ----
    summary: dict = {
        "stage": "ML-02",
        "stage_version": "ML02-v1.0",
        "stage_status": "TECHNICALLY_IMPLEMENTED",
        "scope_boundaries": [
            "K-Means adapter implementation only.",
            "Single initial diagnostic run with one (algorithm, K, seed).",
            "Diagnostic WCSS recorded in cluster_result.extra; no formal metric.",
            "No algorithm comparison (EPIC-08).",
            "No K sweep (EPIC-07).",
            "No segment profiling / naming (EPIC-09).",
            "FE-06 outputs are READ-ONLY.",
        ],
        "pending_review_notes": [
            "Working default n_clusters=4 is WORKING_ASSUMPTION, not final approved.",
            "Working init='k-means++' is WORKING_ASSUMPTION; no claim of best init.",
            "Diagnostic WCSS is not a formal evaluation metric.",
        ],
        "assumptions": [
            "K-Means uses sklearn.cluster.KMeans with default tol=1e-4.",
            "CustomerID lives in metadata, never in matrix.",
            "Random seed policy: framework.random_seed.default OR per-algorithm override OR --seed.",
        ],
        "input": {
            "path": str(input_path),
            "sha256": input_sha,
            "shape": list(df.shape),
            "feature_set": list(df.columns),
        },
        "metadata": {
            "path": str(metadata_path),
            "sha256": metadata_sha,
            "shape": list(md.shape),
        },
        "config": {
            "path": str(cfg_path),
            "sha256": config_sha,
        },
        "experiment": {
            "experiment_id": experiment_id,
            "algorithm": "kmeans",
            "algorithm_version": result.algorithm_version,
            "hyperparameters": hyperparameters,
            "seed_requested": (args.seed if args.seed is not None else cfg.random_seed.default),
            "seed_used": result.random_seed_used,
        },
        "result": {
            "status": result.status,
            "n_clusters": result.n_clusters,
            "n_samples": result.n_samples,
            "execution_time": result.execution_time,
            "timestamp": result.timestamp,
            "platform": result.platform,
            "library_versions": result.library_versions,
            "metrics_placeholder": result.metrics.to_dict(),
            "cluster_result_extra": (
                result.cluster_result.extra if result.cluster_result is not None else None
            ),
        },
        "artifacts": {
            "artifact_paths": dict(result.artifact_paths),
        },
    }
    if result.status == "FAILED":
        summary["result"]["error"] = result.error

    summary_path = report_dir / "ml02_run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=False, default=str),
        encoding="utf-8",
    )

    # ---- Build Vietnamese narrative report (diagnostic only) ----
    status_vi = "THÀNH CÔNG" if result.status == "SUCCESS" else "THẤT BẠI"
    n_clusters_text = (
        f"{result.n_clusters}" if result.n_clusters is not None else "(không xác định)"
    )
    wcss_value = (
        result.cluster_result.extra.get("wcss")
        if result.cluster_result is not None and result.cluster_result.extra
        else None
    )
    n_iter_value = (
        result.cluster_result.extra.get("n_iter")
        if result.cluster_result is not None and result.cluster_result.extra
        else None
    )
    converged_value = (
        result.cluster_result.extra.get("converged")
        if result.cluster_result is not None and result.cluster_result.extra
        else None
    )
    cluster_sizes = (
        result.cluster_result.extra.get("cluster_sizes")
        if result.cluster_result is not None and result.cluster_result.extra
        else None
    )

    md_lines: list[str] = []
    md_lines.append("# ML-02 — K-Means Initial Diagnostic Run")
    md_lines.append("")
    md_lines.append("> **Tài liệu này là báo cáo vận hành (diagnostic report) cho")
    md_lines.append("> lần chạy K-Means đầu tiên trên Final Clustering Dataset của FE-06.**")
    md_lines.append("> Đây KHÔNG phải evaluation phase, KHÔNG so sánh thuật toán,")
    md_lines.append("> KHÔNG chọn best K, KHÔNG chọn best algorithm.")
    md_lines.append("> Working configuration là WORKING_ASSUMPTION, chưa được mentor")
    md_lines.append("> approve.")
    md_lines.append("")
    md_lines.append("## 1. Tổng quan")
    md_lines.append("")
    md_lines.append(f"- Trạng thái: **{status_vi}**")
    md_lines.append(f"- Experiment ID: `{experiment_id}`")
    md_lines.append(f"- Algorithm: `kmeans` (sklearn, version `{result.algorithm_version}`)")
    md_lines.append(f"- Dataset version: `{cfg.input.dataset_version}`")
    md_lines.append(f"- Số customers: **{result.n_samples}**")
    md_lines.append(f"- Số features: **{df.shape[1]}**")
    md_lines.append("")
    md_lines.append("## 2. Configuration")
    md_lines.append("")
    md_lines.append(f"- `n_clusters = {args.n_clusters}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `init = {args.init}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `n_init = {args.n_init}`")
    md_lines.append(f"- `max_iter = {args.max_iter}`")
    md_lines.append(
        f"- `random_state` requested = `{args.seed if args.seed is not None else cfg.random_seed.default}`"
    )
    md_lines.append(f"- `random_state` used = `{result.random_seed_used}`")
    md_lines.append("")
    md_lines.append("## 3. Kết quả")
    md_lines.append("")
    md_lines.append(f"- Số cluster tìm được: **{n_clusters_text}**")
    md_lines.append(f"- Execution time: **{result.execution_time:.4f} s**")
    if wcss_value is not None:
        md_lines.append(f"- WCSS (inertia, diagnostic only): **{wcss_value:.4f}**")
    if n_iter_value is not None:
        md_lines.append(f"- Số iteration: **{n_iter_value}**")
    if converged_value is not None:
        md_lines.append(f"- Converged: **{converged_value}**")
    if cluster_sizes is not None:
        md_lines.append(f"- Cluster sizes: `{cluster_sizes}`")
    md_lines.append("")
    md_lines.append("## 4. Provenance")
    md_lines.append("")
    md_lines.append(f"- Input SHA-256: `{input_sha}`")
    md_lines.append(f"- Metadata SHA-256: `{metadata_sha}`")
    md_lines.append(f"- Config SHA-256: `{config_sha}`")
    md_lines.append(f"- Input path: `{input_path}`")
    md_lines.append(f"- Metadata path: `{metadata_path}`")
    md_lines.append(f"- Config path: `{cfg_path}`")
    md_lines.append("")
    md_lines.append("## 5. Artifacts")
    md_lines.append("")
    for name, path in result.artifact_paths.items():
        md_lines.append(f"- `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("## 6. Decision status")
    md_lines.append("")
    md_lines.append("- `TECHNICALLY_IMPLEMENTED`: K-Means adapter và diagnostic run đã chạy.")
    md_lines.append("- `WORKING_ASSUMPTION`: `n_clusters = 4`, `init = 'k-means++'`.")
    md_lines.append(
        "- `OUT_OF_SCOPE`: evaluation metric, algorithm comparison, K sweep, segment profiling."
    )
    md_lines.append("")
    md_lines.append("## 7. Notes")
    md_lines.append("")
    md_lines.append(
        "- WCSS (inertia) chỉ là diagnostic; EPIC-08 sẽ compute silhouette, DBI, CH chính thức."
    )
    md_lines.append(
        "- Cluster sizes chỉ là diagnostic; EPIC-09 sẽ phân tích segment dựa trên labels."
    )
    md_lines.append('- KHÔNG kết luận "best K" hay "best algorithm" trong tài liệu này.')
    md_lines.append("")
    md_lines.append(
        f"_Báo cáo này được sinh tự động từ execution thực tế. SHA-256 và execution_time "
        f"lấy trực tiếp từ `experiment_log_{experiment_id}.json`._"
    )

    narrative_path = report_dir / "ml02_initial_diagnostic.md"
    narrative_path.write_text("\n".join(md_lines), encoding="utf-8")

    # ---- Print summary to stdout ----
    print(f"[ML-02] status:           {result.status}")
    print(f"[ML-02] n_clusters:       {result.n_clusters}")
    print(f"[ML-02] execution time:   {result.execution_time:.4f} s")
    if result.cluster_result is not None:
        print(f"[ML-02] WCSS (diagnostic): {result.cluster_result.extra.get('wcss')}")
    print(f"[ML-02] summary written:  {summary_path}")
    print(f"[ML-02] narrative written:{narrative_path}")
    print(f"[ML-02] artifacts dir:    {artifacts_dir}")


if __name__ == "__main__":
    main()
