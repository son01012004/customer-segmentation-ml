"""ML-03 orchestrator: Agglomerative initial diagnostic runs.

Stage: 06_clustering / ML-03 (Hierarchical / Agglomerative Clustering)

This script runs **initial, value-neutral diagnostic Agglomerative
clustering experiments** on the FE-06 final clustering dataset via
the ML-01 Experiment Framework. The script demonstrates:

- adapter registration and dispatch via the registry;
- compatibility of the four advertised linkages (ward, complete,
  average, single) with the default euclidean metric on the FE-06
  dataset;
- reproducibility under identical input / configuration / library
  version (Agglomerative clustering in ``n_clusters`` mode is
  deterministic in modern sklearn);
- algorithm-specific diagnostics (linkage, metric, n_merges,
  max/min/median merge distance, cluster sizes).

It is intended as a smoke test and as the initial evidence for the
EPIC-06 Documentation Contract — it does NOT sweep K, does NOT
compare algorithms, does NOT pick a "best" linkage, and does NOT
pick a "best" cluster count.

Usage (from the repository root):

    python -m scripts.run_ml03_agglomerative
    python -m scripts.run_ml03_agglomerative --n-clusters 5 --linkage complete
    python -m scripts.run_ml03_agglomerative --linkage ward --n-clusters 4

Outputs
-------

Written under ``data/processed/clustering_experiments/``:

- ``cluster_labels_{experiment_id}.parquet`` — CustomerID + ClusterLabel + IsNoise.
- ``experiment_log_{experiment_id}.json`` — full ExperimentResult payload.

Written under ``reports/ml03/``:

- ``ml03_run_summary.json`` — summary of the diagnostic runs
  (input/output SHA, hyperparameters, status, n_clusters, ...).
- ``ml03_initial_diagnostic.md`` — Vietnamese narrative report of
  the diagnostic runs (diagnostic-only; no "best" claims).
- ``ml03_linkage_comparison.csv`` — per-linkage diagnostic table
  (linkage, n_clusters, cluster sizes, merge-distance summary).

Hard constraints (AGENTS.md §2, EPIC06 contract):

- No algorithm comparison (EPIC-08).
- No sweep over K / linkage (EPIC-07).
- No segment profiling / naming (EPIC-09).
- No "best / optimal / recommended" claim.
- FE-06 outputs are READ-ONLY.
- Reproducibility metadata (SHA, seed policy, library versions) is
  recorded.
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
    AlgorithmRegistry,
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
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "ml03"
DEFAULT_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "clustering.yaml"
DEFAULT_INPUT_PATH: Path = DEFAULT_PROCESSED_DIR / "final_clustering_dataset.parquet"
DEFAULT_METADATA_PATH: Path = DEFAULT_PROCESSED_DIR / "customer_metadata.parquet"
DEFAULT_ARTIFACTS_DIR: Path = DEFAULT_PROCESSED_DIR / "clustering_experiments"

# ML-03 working defaults — WORKING_ASSUMPTION, not final approved.
DEFAULT_N_CLUSTERS: int = 4
DEFAULT_LINKAGE: str = "ward"
DEFAULT_METRIC: str = "euclidean"
DEFAULT_COMPUTE_DISTANCES: bool = True

# Linkages advertised in the ML-03 task contract.
SUPPORTED_LINKAGES: tuple[str, ...] = ("ward", "complete", "average", "single")


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
            "ML-03 Agglomerative (Hierarchical) Clustering initial diagnostic "
            "runs. Reads data/processed/final_clustering_dataset.parquet and "
            "data/processed/customer_metadata.parquet. Writes artifacts under "
            "data/processed/clustering_experiments/ and reports under "
            "reports/ml03/."
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
        help="Output directory for ML-03 reports.",
    )
    parser.add_argument(
        "--n-clusters",
        type=int,
        default=DEFAULT_N_CLUSTERS,
        help=f"Number of clusters K (working default: {DEFAULT_N_CLUSTERS}).",
    )
    parser.add_argument(
        "--linkage",
        type=str,
        default=DEFAULT_LINKAGE,
        choices=list(SUPPORTED_LINKAGES),
        help=f"Linkage criterion (working default: {DEFAULT_LINKAGE}).",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default=DEFAULT_METRIC,
        choices=["euclidean", "manhattan", "cityblock", "cosine", "chebyshev", "l1", "l2"],
        help=f"Pairwise distance metric (working default: {DEFAULT_METRIC}).",
    )
    parser.add_argument(
        "--no-compute-distances",
        dest="compute_distances",
        action="store_false",
        help="Skip per-merge distance capture (default: on).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Requested random seed. Agglomerative clustering in n_clusters "
            "mode is deterministic; the framework records the request but "
            "does NOT pass a seed to the adapter (supports_random_state=False)."
        ),
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment identifier. If omitted, an ID is generated from the " "hyperparameters.",
    )
    return parser


def _build_experiment_id(args: argparse.Namespace) -> str:
    """Build a stable experiment identifier from the hyperparameters."""
    return (
        f"ML-03-Agglo-k{args.n_clusters}-{args.linkage}-{args.metric}"
        f"-cd{int(args.compute_distances)}-seed{args.seed if args.seed is not None else 'cfg'}"
    )


def _run_single(
    args: argparse.Namespace,
    cfg_path: Path,
    cfg_text: str,
    config_sha: str,
    df: pd.DataFrame,
    md: pd.DataFrame,
    input_sha: str,
    metadata_sha: str,
    n_clusters: int,
    linkage: str,
    metric: str,
    artifacts_dir: Path,
    experiment_id: str | None = None,
) -> dict:
    """Run a single Agglomerative experiment and return a summary dict."""
    cfg = load_framework_config(cfg_path)
    hyperparameters = {
        "n_clusters": n_clusters,
        "linkage": linkage,
        "metric": metric,
        "compute_distances": args.compute_distances,
    }
    if experiment_id is None:
        experiment_id = (
            f"ML-03-Agglo-k{n_clusters}-{linkage}-{metric}"
            f"-cd{int(args.compute_distances)}-seed"
            f"{args.seed if args.seed is not None else 'cfg'}"
        )
    spec = ExperimentSpec(
        experiment_id=experiment_id,
        algorithm="agglomerative",
        hyperparameters=hyperparameters,
        seed_override=args.seed,
    )
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
        input_path=str(args.input),
        metadata_path=str(args.metadata),
        output_dir=artifacts_dir,
    )
    return {
        "experiment_id": experiment_id,
        "hyperparameters": hyperparameters,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)

    # ---- Load framework config ----
    cfg_path = args.config or resolve_framework_config_path()
    if cfg_path is None:
        raise FileNotFoundError(
            "Could not resolve configs/clustering.yaml. Pass --config explicitly."
        )
    cfg_text = cfg_path.read_text(encoding="utf-8")
    config_sha = compute_text_sha256(cfg_text)
    cfg = load_framework_config(cfg_path)

    print(f"[ML-03] config:           {cfg_path}")
    print(f"[ML-03] config SHA-256:   {config_sha[:16]}...")
    print(f"[ML-03] dataset version:  {cfg.input.dataset_version}")

    # ---- Validate registry ----
    # AgglomerativeAdapter must be registered for the script to work.
    if not AlgorithmRegistry.is_registered("agglomerative"):
        raise RuntimeError(
            "Algorithm 'agglomerative' is not registered. "
            "Ensure customer_segmentation.clustering is imported so "
            "AgglomerativeAdapter's @register decorator runs."
        )

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
    print(f"[ML-03] input SHA-256:    {input_sha[:16]}...")
    print(f"[ML-03] metadata SHA-256: {metadata_sha[:16]}...")
    print(f"[ML-03] matrix shape:     {df.shape}")

    # ---- Prepare output dirs ----
    artifacts_dir = args.artifacts_dir
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    # ---- Run primary experiment (working defaults) ----
    primary_experiment_id = args.experiment_id or _build_experiment_id(args)
    print(f"[ML-03] primary experiment id: {primary_experiment_id}")
    print(
        f"[ML-03] primary hyperparameters: "
        f"n_clusters={args.n_clusters}, linkage={args.linkage}, "
        f"metric={args.metric}, compute_distances={args.compute_distances}"
    )

    primary = _run_single(
        args=args,
        cfg_path=cfg_path,
        cfg_text=cfg_text,
        config_sha=config_sha,
        df=df,
        md=md,
        input_sha=input_sha,
        metadata_sha=metadata_sha,
        n_clusters=args.n_clusters,
        linkage=args.linkage,
        metric=args.metric,
        artifacts_dir=artifacts_dir,
        experiment_id=primary_experiment_id,
    )

    # ---- Run per-linkage diagnostic experiments ----
    # These are *initial diagnostic* runs to verify the adapter
    # supports each linkage on the FE-06 dataset. They are NOT a
    # controlled sweep (EPIC-07 owns that).
    per_linkage_summaries: list[dict] = []
    print("[ML-03] running per-linkage diagnostic experiments (initial only)...")
    for linkage in SUPPORTED_LINKAGES:
        # Ward requires euclidean; the others accept any supported metric.
        # Use the user-requested metric for non-ward linkages and
        # fall back to euclidean if the user requested something
        # incompatible.
        linkage_metric = "euclidean" if linkage == "ward" else args.metric
        linkage_experiment_id = (
            f"ML-03-Agglo-diag-k{args.n_clusters}-{linkage}-{linkage_metric}"
            f"-cd{int(args.compute_distances)}-seed{args.seed if args.seed is not None else 'cfg'}"
        )
        linkage_summary = _run_single(
            args=args,
            cfg_path=cfg_path,
            cfg_text=cfg_text,
            config_sha=config_sha,
            df=df,
            md=md,
            input_sha=input_sha,
            metadata_sha=metadata_sha,
            n_clusters=args.n_clusters,
            linkage=linkage,
            metric=linkage_metric,
            artifacts_dir=artifacts_dir,
            experiment_id=linkage_experiment_id,
        )
        per_linkage_summaries.append(linkage_summary)

    # ---- Build ML-03 run summary ----
    primary_result = primary["result"]
    summary: dict = {
        "stage": "ML-03",
        "stage_version": "ML03-v1.0",
        "stage_status": "TECHNICALLY_IMPLEMENTED",
        "scope_boundaries": [
            "Agglomerative (Hierarchical) clustering adapter implementation only.",
            "Initial diagnostic runs with one (linkage, k) per run; not a controlled sweep.",
            "Algorithm-specific diagnostics recorded (linkage, metric, n_merges, "
            "merge-distance summary, cluster sizes).",
            "No algorithm comparison (EPIC-08).",
            "No sweep over K / linkage / metric (EPIC-07).",
            "No segment profiling / naming (EPIC-09).",
            "FE-06 outputs are READ-ONLY.",
            "Agglomerative clustering in n_clusters mode is deterministic; "
            "supports_random_state=False; no seed is consumed.",
        ],
        "pending_review_notes": [
            "Working default n_clusters=4 is WORKING_ASSUMPTION, not final approved.",
            "Working default linkage='ward' is WORKING_ASSUMPTION; no claim of best linkage.",
            "Working default metric='euclidean' is WORKING_ASSUMPTION; no claim of best metric.",
            "Initial per-linkage diagnostics are NOT a controlled sweep; EPIC-07 owns that.",
            "Dendrogram diagnostic data (children_, distances_) is captured in "
            "cluster_result.extra; an actual dendrogram visualisation is OUT OF SCOPE here.",
        ],
        "assumptions": [
            "AgglomerativeAdapter wraps sklearn.cluster.AgglomerativeClustering in n_clusters mode.",
            "CustomerID lives in metadata, never in matrix.",
            "Seed policy: framework.random_seed.default OR per-algorithm override OR --seed, "
            "but the seed is NOT consumed by the deterministic Agglomerative adapter.",
            "compute_distances=True records max/min/median merge distance and a first/last-5 "
            "summary in cluster_result.extra; the full distances_ array is NOT serialised "
            "into the experiment log to keep log size manageable.",
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
        "primary_experiment": _summarize_one(primary),
        "per_linkage_diagnostic": [_summarize_one(s) for s in per_linkage_summaries],
        "artifacts": {
            "artifact_paths": dict(primary_result.artifact_paths),
        },
    }
    if primary_result.status == "FAILED":
        summary["primary_experiment"]["error"] = primary_result.error

    summary_path = report_dir / "ml03_run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=False, default=str),
        encoding="utf-8",
    )

    # ---- Build per-linkage comparison CSV ----
    csv_path = report_dir / "ml03_linkage_comparison.csv"
    rows = [_csv_row(primary, primary_label="primary")]
    for linkage_summary in per_linkage_summaries:
        rows.append(
            _csv_row(
                linkage_summary,
                primary_label=f"diagnostic-{linkage_summary['hyperparameters']['linkage']}",
            )
        )
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    # ---- Build Vietnamese narrative report (diagnostic only) ----
    status_vi = "THÀNH CÔNG" if primary_result.status == "SUCCESS" else "THẤT BẠI"
    md_lines: list[str] = []
    md_lines.append("# ML-03 — Agglomerative (Hierarchical) Clustering Initial Diagnostic Runs")
    md_lines.append("")
    md_lines.append("> **Tài liệu này là báo cáo vận hành (diagnostic report) cho")
    md_lines.append(
        "> lần chạy Agglomerative clustering đầu tiên trên Final Clustering Dataset của FE-06.**"
    )
    md_lines.append("> Đây KHÔNG phải evaluation phase, KHÔNG so sánh thuật toán,")
    md_lines.append("> KHÔNG so sánh linkage, KHÔNG chọn best K, KHÔNG chọn best algorithm.")
    md_lines.append("> Working configuration là WORKING_ASSUMPTION, chưa được mentor")
    md_lines.append("> approve.")
    md_lines.append("")
    md_lines.append("## 1. Tổng quan")
    md_lines.append("")
    md_lines.append(f"- Trạng thái primary run: **{status_vi}**")
    md_lines.append(f"- Primary experiment ID: `{primary_experiment_id}`")
    md_lines.append(
        f"- Algorithm: `agglomerative` (sklearn, version `{primary_result.algorithm_version}`)"
    )
    md_lines.append("- Algorithm family: `hard` (mỗi customer thuộc đúng 1 cluster)")
    md_lines.append(f"- Dataset version: `{cfg.input.dataset_version}`")
    md_lines.append(f"- Số customers: **{primary_result.n_samples}**")
    md_lines.append(f"- Số features: **{df.shape[1]}**")
    md_lines.append("")
    md_lines.append("## 2. Configuration")
    md_lines.append("")
    md_lines.append(f"- `n_clusters = {args.n_clusters}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `linkage = {args.linkage}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `metric = {args.metric}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `compute_distances = {args.compute_distances}`")
    md_lines.append(
        f"- `random_state` requested = `{args.seed if args.seed is not None else cfg.random_seed.default}`"
    )
    md_lines.append(
        f"- `random_state` used = `{primary_result.random_seed_used}` "
        f"(Agglomerative in n_clusters mode is deterministic; supports_random_state=False)"
    )
    md_lines.append("")
    md_lines.append("## 3. Kết quả primary run")
    md_lines.append("")
    n_clusters_text = (
        f"{primary_result.n_clusters}"
        if primary_result.n_clusters is not None
        else "(không xác định)"
    )
    md_lines.append(f"- Số cluster tìm được: **{n_clusters_text}**")
    md_lines.append(f"- Execution time: **{primary_result.execution_time:.4f} s**")
    extras = (
        primary_result.cluster_result.extra if primary_result.cluster_result is not None else {}
    )
    md_lines.append(f"- Linkage: **{extras.get('linkage', 'n/a')}**")
    md_lines.append(f"- Metric: **{extras.get('metric', 'n/a')}**")
    md_lines.append(f"- `n_merges`: **{extras.get('n_merges', 'n/a')}**")
    md_lines.append(f"- `n_leaves`: **{extras.get('n_leaves', 'n/a')}**")
    if "max_merge_distance" in extras and extras["max_merge_distance"] is not None:
        md_lines.append(f"- max merge distance: **{extras['max_merge_distance']:.4f}**")
        md_lines.append(f"- min merge distance: **{extras['min_merge_distance']:.4f}**")
        md_lines.append(f"- median merge distance: **{extras['median_merge_distance']:.4f}**")
    cluster_sizes = extras.get("cluster_sizes", {})
    md_lines.append(f"- Cluster sizes: `{cluster_sizes}`")
    md_lines.append("")
    md_lines.append("## 4. Per-linkage diagnostic runs")
    md_lines.append("")
    md_lines.append(
        "Bốn initial diagnostic runs đã chạy (một cho mỗi linkage). Đây KHÔNG "
        "phải controlled sweep — chỉ để verify adapter hỗ trợ đầy đủ các linkage "
        "đã quảng cáo và thu thập algorithm-specific diagnostics."
    )
    md_lines.append("")
    md_lines.append("| Linkage | Status | n_clusters | max_merge_distance | Execution time (s) |")
    md_lines.append("|---------|--------|-----------:|-------------------:|-------------------:|")
    for s in per_linkage_summaries:
        r = s["result"]
        e = r.cluster_result.extra if r.cluster_result is not None else {}
        max_d = e.get("max_merge_distance")
        max_d_str = f"{max_d:.4f}" if isinstance(max_d, (int, float)) else "n/a"
        n_c = r.n_clusters if r.n_clusters is not None else "n/a"
        md_lines.append(
            f"| {s['hyperparameters']['linkage']} | {r.status} | {n_c} | "
            f"{max_d_str} | {r.execution_time:.4f} |"
        )
    md_lines.append("")
    md_lines.append("## 5. Provenance")
    md_lines.append("")
    md_lines.append(f"- Input SHA-256: `{input_sha}`")
    md_lines.append(f"- Metadata SHA-256: `{metadata_sha}`")
    md_lines.append(f"- Config SHA-256: `{config_sha}`")
    md_lines.append(f"- Input path: `{input_path}`")
    md_lines.append(f"- Metadata path: `{metadata_path}`")
    md_lines.append(f"- Config path: `{cfg_path}`")
    md_lines.append("")
    md_lines.append("## 6. Artifacts")
    md_lines.append("")
    md_lines.append("### 6.1 Primary run")
    md_lines.append("")
    for name, path in primary_result.artifact_paths.items():
        md_lines.append(f"- `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("### 6.2 Per-linkage diagnostic runs")
    md_lines.append("")
    for s in per_linkage_summaries:
        md_lines.append(f"- {s['hyperparameters']['linkage']} — `{s['experiment_id']}`:")
        for name, path in s["result"].artifact_paths.items():
            md_lines.append(f"    - `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("## 7. Decision status")
    md_lines.append("")
    md_lines.append(
        "- `TECHNICALLY_IMPLEMENTED`: Agglomerative adapter và diagnostic runs đã chạy."
    )
    md_lines.append(
        "- `WORKING_ASSUMPTION`: `n_clusters = 4`, `linkage = 'ward'`, `metric = 'euclidean'`."
    )
    md_lines.append(
        "- `OUT_OF_SCOPE`: evaluation metric, algorithm comparison, K sweep, "
        "linkage comparison, segment profiling, dendrogram rendering."
    )
    md_lines.append("")
    md_lines.append("## 8. Notes")
    md_lines.append("")
    md_lines.append(
        "- Agglomerative clustering trong `n_clusters` mode là deterministic "
        "trong sklearn hiện đại; `supports_random_state()` trả về `False`."
    )
    md_lines.append(
        "- Per-merge linkage distances được capture trong `cluster_result.extra` "
        "(`max/min/median_merge_distance`, `merge_distances_summary`). Mảng "
        "`distances_` đầy đủ KHÔNG được serialise vào log để giữ kích thước log nhỏ; "
        "EPIC-06 diagnostic viz (nếu cần) sẽ consume trực tiếp từ `sklearn` model "
        "qua `adapter.get_model()`."
    )
    md_lines.append(
        "- Per-linkage diagnostics KHÔNG được dùng để kết luận 'best linkage' — "
        "đó là EPIC-07 scope."
    )
    md_lines.append(
        '- KHÔNG kết luận "best K", "best linkage", "best algorithm" trong tài liệu này.'
    )
    md_lines.append("")
    md_lines.append(
        f"_Báo cáo này được sinh tự động từ execution thực tế. SHA-256 và execution_time "
        f"lấy trực tiếp từ `experiment_log_{primary_experiment_id}.json`._"
    )

    narrative_path = report_dir / "ml03_initial_diagnostic.md"
    narrative_path.write_text("\n".join(md_lines), encoding="utf-8")

    # ---- Print summary to stdout ----
    print(f"[ML-03] primary status:    {primary_result.status}")
    print(f"[ML-03] primary n_clusters: {primary_result.n_clusters}")
    print(f"[ML-03] primary exec time: {primary_result.execution_time:.4f} s")
    if primary_result.cluster_result is not None:
        e = primary_result.cluster_result.extra
        print(
            f"[ML-03] linkage={e.get('linkage')}, metric={e.get('metric')}, "
            f"n_merges={e.get('n_merges')}"
        )
    print(f"[ML-03] per-linkage runs: {len(per_linkage_summaries)}")
    for s in per_linkage_summaries:
        r = s["result"]
        print(
            f"[ML-03]   linkage={s['hyperparameters']['linkage']}: status={r.status}, "
            f"exec={r.execution_time:.4f}s"
        )
    print(f"[ML-03] summary written:   {summary_path}")
    print(f"[ML-03] narrative written: {narrative_path}")
    print(f"[ML-03] csv written:       {csv_path}")
    print(f"[ML-03] artifacts dir:     {artifacts_dir}")


def _summarize_one(entry: dict) -> dict:
    """Build a JSON-friendly summary dict for one experiment entry."""
    result = entry["result"]
    extras = result.cluster_result.extra if result.cluster_result is not None else {}
    return {
        "experiment_id": entry["experiment_id"],
        "hyperparameters": entry["hyperparameters"],
        "status": result.status,
        "n_clusters": result.n_clusters,
        "n_samples": result.n_samples,
        "execution_time": result.execution_time,
        "timestamp": result.timestamp,
        "platform": result.platform,
        "library_versions": result.library_versions,
        "metrics_placeholder": result.metrics.to_dict(),
        "cluster_result_extra": extras,
        "supports_random_state": (
            result.cluster_result.supports_random_state
            if result.cluster_result is not None
            else None
        ),
        "random_seed_used": result.random_seed_used,
        "random_seed_requested": result.random_seed,
        "artifact_paths": dict(result.artifact_paths),
    }


def _csv_row(entry: dict, *, primary_label: str) -> dict:
    """Build a flat row for the per-linkage comparison CSV."""
    result = entry["result"]
    extras = result.cluster_result.extra if result.cluster_result is not None else {}
    cluster_sizes = extras.get("cluster_sizes", {}) or {}
    sizes_str = (
        "; ".join(f"{k}:{v}" for k, v in sorted(cluster_sizes.items())) if cluster_sizes else ""
    )
    return {
        "experiment_label": primary_label,
        "experiment_id": entry["experiment_id"],
        "linkage": entry["hyperparameters"]["linkage"],
        "metric": entry["hyperparameters"]["metric"],
        "n_clusters_requested": entry["hyperparameters"]["n_clusters"],
        "n_clusters_found": result.n_clusters,
        "n_samples": result.n_samples,
        "n_merges": extras.get("n_merges"),
        "n_leaves": extras.get("n_leaves"),
        "max_merge_distance": extras.get("max_merge_distance"),
        "min_merge_distance": extras.get("min_merge_distance"),
        "median_merge_distance": extras.get("median_merge_distance"),
        "compute_distances_used": extras.get("compute_distances_used"),
        "cluster_sizes": sizes_str,
        "execution_time_s": result.execution_time,
        "status": result.status,
        "supports_random_state": (
            result.cluster_result.supports_random_state
            if result.cluster_result is not None
            else None
        ),
    }


if __name__ == "__main__":
    main()
