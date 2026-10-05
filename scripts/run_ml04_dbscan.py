"""ML-04 orchestrator: DBSCAN initial diagnostic runs.

Stage: 06_clustering / ML-04 (DBSCAN — Density-Based Spatial
Clustering of Applications with Noise)

This script runs **initial, value-neutral diagnostic DBSCAN
experiments** on the FE-06 final clustering dataset via the ML-01
Experiment Framework. The script demonstrates:

- adapter registration and dispatch via the registry;
- compatibility of the adapter with the working default
  configuration in ``configs/clustering.yaml``;
- reproducibility under identical input / configuration / library
  version (DBSCAN in sklearn is deterministic);
- DBSCAN-specific diagnostics (eps, min_samples, metric, noise
  count / ratio, core sample count, cluster sizes, label
  distribution, all-noise / has-single-cluster flags).

It is intended as a smoke test and as the initial evidence for the
EPIC-06 Documentation Contract — it does NOT sweep
``(eps, min_samples)``, does NOT compare algorithms, does NOT pick a
"best" ``eps`` or ``min_samples``, and does NOT pick a "best"
algorithm.

Usage (from the repository root):

    python -m scripts.run_ml04_dbscan
    python -m scripts.run_ml04_dbscan --eps 0.7 --min-samples 4 --metric manhattan
    python -m scripts.run_ml04_dbscan --eps 0.5 --min-samples 5  # working defaults

Outputs
-------

Written under ``data/processed/clustering_experiments/``:

- ``cluster_labels_{experiment_id}.parquet`` — CustomerID +
  ClusterLabel + IsNoise.
- ``experiment_log_{experiment_id}.json`` — full ExperimentResult
  payload.

Written under ``reports/ml04/``:

- ``ml04_run_summary.json`` — summary of the diagnostic runs
  (input/output SHA, hyperparameters, status, n_clusters,
  noise_count/ratio, core sample count, ...).
- ``ml04_initial_diagnostic.md`` — Vietnamese narrative report of
  the diagnostic runs (diagnostic-only; no "best" claims).
- ``ml04_parameter_diagnostic.csv`` — per-configuration diagnostic
  table (eps, min_samples, metric, n_clusters, noise_count,
  noise_ratio, core_sample_count, execution time).

Hard constraints (AGENTS.md §2, EPIC06 contract):

- No algorithm comparison (EPIC-08).
- No sweep over ``(eps, min_samples)`` (EPIC-07).
- No segment profiling / naming (EPIC-09).
- No "best / optimal / recommended" claim about ``eps``,
  ``min_samples``, metric, or algorithm.
- FE-06 outputs are READ-ONLY.
- Reproducibility metadata (SHA, library versions, seed policy) is
  recorded. ``DBSCANAdapter.supports_random_state() == False`` so
  no seed is consumed.
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
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "ml04"
DEFAULT_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "clustering.yaml"
DEFAULT_INPUT_PATH: Path = DEFAULT_PROCESSED_DIR / "final_clustering_dataset.parquet"
DEFAULT_METADATA_PATH: Path = DEFAULT_PROCESSED_DIR / "customer_metadata.parquet"
DEFAULT_ARTIFACTS_DIR: Path = DEFAULT_PROCESSED_DIR / "clustering_experiments"

# ML-04 working defaults — WORKING_ASSUMPTION, not final approved.
# Mirrors configs/clustering.yaml algorithms.dbscan.*.
DEFAULT_EPS: float = 0.5
DEFAULT_MIN_SAMPLES: int = 5
DEFAULT_METRIC: str = "euclidean"

# Metrics advertised by DBSCANAdapter (mirrors dbscan.SUPPORTED_METRICS).
SUPPORTED_METRICS: tuple[str, ...] = (
    "euclidean",
    "manhattan",
    "cityblock",
    "cosine",
    "chebyshev",
    "l1",
    "l2",
)


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
            "ML-04 DBSCAN initial diagnostic runs. "
            "Reads data/processed/final_clustering_dataset.parquet and "
            "data/processed/customer_metadata.parquet. "
            "Writes artifacts under data/processed/clustering_experiments/ "
            "and reports under reports/ml04/."
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
        help="Output directory for ML-04 reports.",
    )
    parser.add_argument(
        "--eps",
        type=float,
        default=DEFAULT_EPS,
        help=f"Epsilon-neighbourhood radius (working default: {DEFAULT_EPS}).",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help=f"Minimum samples in eps neighbourhood to form a core point "
        f"(working default: {DEFAULT_MIN_SAMPLES}).",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default=DEFAULT_METRIC,
        choices=list(SUPPORTED_METRICS),
        help=f"Pairwise distance metric (working default: {DEFAULT_METRIC}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Requested random seed. DBSCAN is deterministic in sklearn; "
            "the framework records the request but does NOT pass a seed to "
            "the adapter (supports_random_state=False)."
        ),
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment identifier. If omitted, an ID is generated from " "the hyperparameters.",
    )
    parser.add_argument(
        "--skip-metric-diagnostic",
        action="store_true",
        help="Skip the per-metric diagnostic runs (manhattan, cosine). "
        "Default: run a small set of metric diagnostics.",
    )
    return parser


def _build_experiment_id(
    *,
    eps: float,
    min_samples: int,
    metric: str,
    seed: int | None,
    label: str | None = None,
) -> str:
    """Build a stable experiment identifier from the hyperparameters."""
    seed_token = f"seed{seed}" if seed is not None else "seedcfg"
    prefix = label if label is not None else "ML-04-DBSCAN"
    return f"{prefix}-eps{eps:g}-ms{min_samples}-{metric}-{seed_token}"


def _run_single(
    args: argparse.Namespace,
    cfg_path: Path,
    cfg_text: str,
    config_sha: str,
    df: pd.DataFrame,
    md: pd.DataFrame,
    input_sha: str,
    metadata_sha: str,
    eps: float,
    min_samples: int,
    metric: str,
    artifacts_dir: Path,
    *,
    experiment_id: str,
    seed: int | None = None,
) -> dict:
    """Run a single DBSCAN experiment and return a summary dict."""
    cfg = load_framework_config(cfg_path)
    hyperparameters = {
        "eps": float(eps),
        "min_samples": int(min_samples),
        "metric": str(metric),
    }
    spec = ExperimentSpec(
        experiment_id=experiment_id,
        algorithm="dbscan",
        hyperparameters=hyperparameters,
        seed_override=seed,
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
# Summary helpers
# ---------------------------------------------------------------------------


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
        "cluster_result": (
            result.cluster_result.to_dict() if result.cluster_result is not None else None
        ),
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
    """Build a flat row for the per-configuration diagnostic CSV."""
    result = entry["result"]
    extras = result.cluster_result.extra if result.cluster_result is not None else {}
    cluster_sizes = extras.get("cluster_sizes", {}) or {}
    sizes_str = (
        "; ".join(f"{k}:{v}" for k, v in sorted(cluster_sizes.items())) if cluster_sizes else ""
    )
    return {
        "experiment_label": primary_label,
        "experiment_id": entry["experiment_id"],
        "eps": entry["hyperparameters"]["eps"],
        "min_samples": entry["hyperparameters"]["min_samples"],
        "metric": entry["hyperparameters"]["metric"],
        "n_clusters_found": result.n_clusters,
        "n_samples": result.n_samples,
        "noise_count": extras.get("noise_count"),
        "noise_ratio": extras.get("noise_ratio"),
        "has_noise": extras.get("has_noise"),
        "all_noise": extras.get("all_noise"),
        "has_single_cluster": extras.get("has_single_cluster"),
        "core_sample_count": extras.get("core_sample_count"),
        "core_sample_ratio": extras.get("core_sample_ratio"),
        "cluster_sizes": sizes_str,
        "execution_time_s": result.execution_time,
        "status": result.status,
        "supports_random_state": (
            result.cluster_result.supports_random_state
            if result.cluster_result is not None
            else None
        ),
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

    print(f"[ML-04] config:           {cfg_path}")
    print(f"[ML-04] config SHA-256:   {config_sha[:16]}...")
    print(f"[ML-04] dataset version:  {cfg.input.dataset_version}")

    # ---- Validate registry ----
    if not AlgorithmRegistry.is_registered("dbscan"):
        raise RuntimeError(
            "Algorithm 'dbscan' is not registered. "
            "Ensure customer_segmentation.clustering is imported so "
            "DBSCANAdapter's @register decorator runs."
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
    print(f"[ML-04] input SHA-256:    {input_sha[:16]}...")
    print(f"[ML-04] metadata SHA-256: {metadata_sha[:16]}...")
    print(f"[ML-04] matrix shape:     {df.shape}")

    # ---- Prepare output dirs ----
    artifacts_dir = args.artifacts_dir
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    # ---- Run primary experiment (working defaults) ----
    primary_experiment_id = args.experiment_id or _build_experiment_id(
        eps=args.eps,
        min_samples=args.min_samples,
        metric=args.metric,
        seed=args.seed,
    )
    print(f"[ML-04] primary experiment id: {primary_experiment_id}")
    print(
        f"[ML-04] primary hyperparameters: "
        f"eps={args.eps}, min_samples={args.min_samples}, metric={args.metric}"
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
        eps=args.eps,
        min_samples=args.min_samples,
        metric=args.metric,
        artifacts_dir=artifacts_dir,
        experiment_id=primary_experiment_id,
        seed=args.seed,
    )

    # ---- Run per-metric diagnostic experiments ----
    # These are *initial diagnostic* runs to verify the adapter
    # supports each metric on the FE-06 dataset. They are NOT a
    # controlled sweep (EPIC-07 owns that). Default: run the
    # working-default metric; opt-in additional metrics.
    per_metric_summaries: list[dict] = []
    if not args.skip_metric_diagnostic:
        # The "diagnostic" set runs the same (eps, min_samples) but
        # varies the metric. This is purely diagnostic — no claim of
        # "best metric" is made anywhere.
        diagnostic_metrics: list[str] = ["euclidean", "manhattan", "cosine"]
        # Always include the working-default metric even if it is
        # already the primary metric, so the diagnostic CSV has a
        # complete set.
        if "euclidean" not in diagnostic_metrics:
            diagnostic_metrics.insert(0, args.metric)
        print("[ML-04] running per-metric diagnostic experiments (initial only)...")
        for metric in diagnostic_metrics:
            metric_experiment_id = _build_experiment_id(
                eps=args.eps,
                min_samples=args.min_samples,
                metric=metric,
                seed=args.seed,
                label="ML-04-DBSCAN-diag",
            )
            metric_summary = _run_single(
                args=args,
                cfg_path=cfg_path,
                cfg_text=cfg_text,
                config_sha=config_sha,
                df=df,
                md=md,
                input_sha=input_sha,
                metadata_sha=metadata_sha,
                eps=args.eps,
                min_samples=args.min_samples,
                metric=metric,
                artifacts_dir=artifacts_dir,
                experiment_id=metric_experiment_id,
                seed=args.seed,
            )
            per_metric_summaries.append(metric_summary)

    # ---- Build ML-04 run summary ----
    primary_result = primary["result"]
    summary: dict = {
        "stage": "ML-04",
        "stage_version": "ML04-v1.0",
        "stage_status": "TECHNICALLY_IMPLEMENTED",
        "scope_boundaries": [
            "DBSCAN density-based clustering adapter implementation only.",
            "Initial diagnostic runs with one (eps, min_samples, metric) per run; "
            "not a controlled sweep.",
            "DBSCAN-specific diagnostics recorded (noise_count, noise_ratio, "
            "core_sample_count, core_sample_ratio, cluster_sizes, "
            "labels_value_counts, all_noise, has_single_cluster, has_noise).",
            "No algorithm comparison (EPIC-08).",
            "No sweep over (eps, min_samples) (EPIC-07).",
            "No segment profiling / naming (EPIC-09).",
            "FE-06 outputs are READ-ONLY.",
            "DBSCAN is deterministic in sklearn; supports_random_state=False; "
            "no seed is consumed.",
            "Noise label -1 is preserved verbatim per sklearn convention; "
            "noise is NOT removed or relabelled.",
        ],
        "pending_review_notes": [
            "Working default eps=0.5 is WORKING_ASSUMPTION, not final approved.",
            "Working default min_samples=5 is WORKING_ASSUMPTION, not final approved.",
            "Working default metric='euclidean' is WORKING_ASSUMPTION, not final approved.",
            "Initial per-metric diagnostics are NOT a controlled sweep; EPIC-07 owns that.",
            "K-distance diagnostic visualisation is OUT OF SCOPE here "
            "(optional EPIC-06 diagnostic viz).",
            "No claim of 'best eps' or 'best min_samples' anywhere in this run.",
        ],
        "assumptions": [
            "DBSCANAdapter wraps sklearn.cluster.DBSCAN with the (eps, "
            "min_samples, metric) hyperparameters.",
            "CustomerID lives in metadata, never in matrix.",
            "Seed policy: framework.random_seed.default OR per-algorithm override "
            "OR --seed, but the seed is NOT consumed by the deterministic DBSCAN adapter.",
            "Noise label -1 is preserved verbatim; no relabelling to a positive " "cluster ID.",
            "Cluster count is computed from unique non-noise labels, not "
            "max(labels) + 1, to remain correct under arbitrary label conventions.",
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
        "per_metric_diagnostic": [_summarize_one(s) for s in per_metric_summaries],
        "artifacts": {
            "artifact_paths": dict(primary_result.artifact_paths),
        },
    }
    if primary_result.status == "FAILED":
        summary["primary_experiment"]["error"] = primary_result.error

    summary_path = report_dir / "ml04_run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=False, default=str),
        encoding="utf-8",
    )

    # ---- Build per-configuration diagnostic CSV ----
    csv_path = report_dir / "ml04_parameter_diagnostic.csv"
    rows = [_csv_row(primary, primary_label="primary")]
    for metric_summary in per_metric_summaries:
        rows.append(
            _csv_row(
                metric_summary,
                primary_label=(f"diagnostic-{metric_summary['hyperparameters']['metric']}"),
            )
        )
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    # ---- Build Vietnamese narrative report (diagnostic only) ----
    status_vi = "THÀNH CÔNG" if primary_result.status == "SUCCESS" else "THẤT BẠI"
    extras = (
        primary_result.cluster_result.extra if primary_result.cluster_result is not None else {}
    )

    md_lines: list[str] = []
    md_lines.append("# ML-04 — DBSCAN Initial Diagnostic Runs")
    md_lines.append("")
    md_lines.append("> **Tài liệu này là báo cáo vận hành (diagnostic report) cho")
    md_lines.append("> lần chạy DBSCAN đầu tiên trên Final Clustering Dataset của FE-06.**")
    md_lines.append("> Đây KHÔNG phải evaluation phase, KHÔNG so sánh thuật toán,")
    md_lines.append("> KHÔNG so sánh eps/min_samples/metric, KHÔNG chọn best eps,")
    md_lines.append("> KHÔNG chọn best min_samples, KHÔNG chọn best algorithm.")
    md_lines.append("> Working configuration là WORKING_ASSUMPTION, chưa được mentor")
    md_lines.append("> approve.")
    md_lines.append("")
    md_lines.append("## 1. Tổng quan")
    md_lines.append("")
    md_lines.append(f"- Trạng thái primary run: **{status_vi}**")
    md_lines.append(f"- Primary experiment ID: `{primary_experiment_id}`")
    md_lines.append(
        f"- Algorithm: `dbscan` (sklearn, version `{primary_result.algorithm_version}`)"
    )
    md_lines.append("- Algorithm family: `density_based` (hard labels + noise label `-1`)")
    md_lines.append(f"- Dataset version: `{cfg.input.dataset_version}`")
    md_lines.append(f"- Số customers: **{primary_result.n_samples}**")
    md_lines.append(f"- Số features: **{df.shape[1]}**")
    md_lines.append("")
    md_lines.append("## 2. Configuration (working defaults; WORKING_ASSUMPTION)")
    md_lines.append("")
    md_lines.append(f"- `eps = {args.eps}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `min_samples = {args.min_samples}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `metric = {args.metric}` (working default; WORKING_ASSUMPTION)")
    md_lines.append("- `noise_label = -1` (sklearn convention; preserved verbatim)")
    md_lines.append(
        f"- `random_state` requested = "
        f"`{args.seed if args.seed is not None else cfg.random_seed.default}`"
    )
    md_lines.append(
        f"- `random_state` used = `{primary_result.random_seed_used}` "
        f"(DBSCAN in sklearn is deterministic; supports_random_state=False)"
    )
    md_lines.append("")
    md_lines.append("## 3. DBSCAN theory recap (documentation)")
    md_lines.append("")
    md_lines.append(
        "- **Epsilon-neighbourhood** của điểm `x`: " "`N_eps(x) = {x_j | d(x, x_j) <= eps}`."
    )
    md_lines.append(
        "- **Core point**: điểm `x` là core nếu "
        "`|N_eps(x)| >= min_samples` (đếm cả chính nó, theo sklearn)."
    )
    md_lines.append(
        "- **Border point**: không phải core nhưng nằm trong "
        "eps-neighbourhood của một core point."
    )
    md_lines.append("- **Noise point**: không phải core, không phải border → label `-1`.")
    md_lines.append("- **Cluster**: tập density-connected tối đại mà không phải noise.")
    md_lines.append("")
    md_lines.append("## 4. Kết quả primary run")
    md_lines.append("")
    n_clusters_text = (
        f"{primary_result.n_clusters}"
        if primary_result.n_clusters is not None
        else "(không xác định)"
    )
    md_lines.append(f"- Số cluster tìm được (loại trừ noise): **{n_clusters_text}**")
    md_lines.append(f"- Execution time: **{primary_result.execution_time:.4f} s**")
    noise_count = extras.get("noise_count")
    noise_ratio = extras.get("noise_ratio")
    if noise_count is not None:
        md_lines.append(f"- Noise count: **{noise_count}**")
    if noise_ratio is not None:
        md_lines.append(f"- Noise ratio: **{noise_ratio:.6f}**")
    md_lines.append(
        f"- `has_noise`: **{extras.get('has_noise')}**, "
        f"`all_noise`: **{extras.get('all_noise')}**, "
        f"`has_single_cluster`: **{extras.get('has_single_cluster')}**"
    )
    md_lines.append(
        f"- Core sample count: **{extras.get('core_sample_count')}**, "
        f"core sample ratio: **{extras.get('core_sample_ratio'):.6f}**"
    )
    cluster_sizes = extras.get("cluster_sizes", {})
    md_lines.append(f"- Cluster sizes (loại trừ noise): `{cluster_sizes}`")
    labels_vc = extras.get("labels_value_counts", {})
    md_lines.append(f"- Label distribution (bao gồm noise `-1`): `{labels_vc}`")
    md_lines.append("")
    md_lines.append("## 5. Per-metric diagnostic runs")
    md_lines.append("")
    md_lines.append(
        "Một số diagnostic runs đã chạy với các metric khác nhau (cùng "
        "`eps`, `min_samples`). Đây KHÔNG phải controlled sweep — chỉ để "
        "verify adapter hỗ trợ đầy đủ các metric đã quảng cáo và thu thập "
        "DBSCAN-specific diagnostics."
    )
    md_lines.append("")
    md_lines.append(
        "| Label | Metric | Status | n_clusters | noise_count | "
        "noise_ratio | core_sample_count | Execution time (s) |"
    )
    md_lines.append(
        "|-------|--------|--------|-----------:|------------:|"
        "------------:|------------------:|-------------------:|"
    )
    if per_metric_summaries:
        for s in per_metric_summaries:
            r = s["result"]
            e = r.cluster_result.extra if r.cluster_result is not None else {}
            n_c = r.n_clusters if r.n_clusters is not None else "n/a"
            n_count = e.get("noise_count")
            n_ratio = e.get("noise_ratio")
            core_count = e.get("core_sample_count")
            n_ratio_str = f"{n_ratio:.4f}" if isinstance(n_ratio, (int, float)) else "n/a"
            md_lines.append(
                f"| diagnostic | {s['hyperparameters']['metric']} | {r.status} | "
                f"{n_c} | {n_count} | {n_ratio_str} | {core_count} | "
                f"{r.execution_time:.4f} |"
            )
    else:
        md_lines.append("| (skipped via --skip-metric-diagnostic) | | | | | | | |")
    md_lines.append("")
    md_lines.append("## 6. Provenance")
    md_lines.append("")
    md_lines.append(f"- Input SHA-256: `{input_sha}`")
    md_lines.append(f"- Metadata SHA-256: `{metadata_sha}`")
    md_lines.append(f"- Config SHA-256: `{config_sha}`")
    md_lines.append(f"- Input path: `{input_path}`")
    md_lines.append(f"- Metadata path: `{metadata_path}`")
    md_lines.append(f"- Config path: `{cfg_path}`")
    md_lines.append("")
    md_lines.append("## 7. Artifacts")
    md_lines.append("")
    md_lines.append("### 7.1 Primary run")
    md_lines.append("")
    for name, path in primary_result.artifact_paths.items():
        md_lines.append(f"- `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("### 7.2 Per-metric diagnostic runs")
    md_lines.append("")
    for s in per_metric_summaries:
        md_lines.append(f"- metric `{s['hyperparameters']['metric']}` — `{s['experiment_id']}`:")
        for name, path in s["result"].artifact_paths.items():
            md_lines.append(f"    - `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("## 8. Decision status")
    md_lines.append("")
    md_lines.append("- `TECHNICALLY_IMPLEMENTED`: DBSCAN adapter và diagnostic runs đã chạy.")
    md_lines.append(
        "- `WORKING_ASSUMPTION`: `eps = 0.5`, `min_samples = 5`, `metric = 'euclidean'`."
    )
    md_lines.append(
        "- `OUT_OF_SCOPE`: evaluation metric, algorithm comparison, "
        "(eps, min_samples) sweep, segment profiling, K-distance viz, "
        "research comparison viz."
    )
    md_lines.append("- `OUT_OF_SCOPE`: chọn `best eps` / `best min_samples` / `best metric`.")
    md_lines.append("")
    md_lines.append("## 9. Notes")
    md_lines.append("")
    md_lines.append(
        "- DBSCAN trong sklearn là deterministic; `supports_random_state()` trả "
        "về `False`. Framework runner KHÔNG pass seed vào adapter."
    )
    md_lines.append(
        "- Noise label `-1` được bảo toàn verbatim trong "
        "`cluster_result.cluster_labels` và trong file "
        "`cluster_labels_*.parquet` (`IsNoise = ClusterLabel == -1`)."
    )
    md_lines.append(
        "- `cluster_result.extra` ghi `noise_count`, `noise_ratio`, "
        "`core_sample_count`, `core_sample_ratio`, `cluster_sizes`, "
        "`labels_value_counts`, `all_noise`, `has_noise`, `has_single_cluster`."
    )
    md_lines.append(
        "- K-distance plot là diagnostic optional cho EPIC-06; ML-04 chưa sinh "
        "viz này. EPIC-06 diagnostic viz (nếu cần) sẽ consume trực tiếp từ "
        "sklearn model qua `adapter.get_model()`."
    )
    md_lines.append(
        '- KHÔNG kết luận "best eps", "best min_samples", "best metric", '
        '"best algorithm" trong tài liệu này.'
    )
    md_lines.append("")
    md_lines.append(
        f"_Báo cáo này được sinh tự động từ execution thực tế. SHA-256 và execution_time "
        f"lấy trực tiếp từ `experiment_log_{primary_experiment_id}.json`._"
    )

    narrative_path = report_dir / "ml04_initial_diagnostic.md"
    narrative_path.write_text("\n".join(md_lines), encoding="utf-8")

    # ---- Print summary to stdout ----
    print(f"[ML-04] primary status:    {primary_result.status}")
    print(f"[ML-04] primary n_clusters: {primary_result.n_clusters}")
    if primary_result.cluster_result is not None:
        e = primary_result.cluster_result.extra
        print(
            f"[ML-04] noise_count={e.get('noise_count')}, "
            f"noise_ratio={e.get('noise_ratio'):.4f}, "
            f"core_sample_count={e.get('core_sample_count')}"
        )
    print(f"[ML-04] primary exec time: {primary_result.execution_time:.4f} s")
    print(f"[ML-04] per-metric runs:   {len(per_metric_summaries)}")
    for s in per_metric_summaries:
        r = s["result"]
        e = r.cluster_result.extra if r.cluster_result is not None else {}
        print(
            f"[ML-04]   metric={s['hyperparameters']['metric']}: status={r.status}, "
            f"n_clusters={r.n_clusters}, noise_count={e.get('noise_count')}, "
            f"exec={r.execution_time:.4f}s"
        )
    print(f"[ML-04] summary written:   {summary_path}")
    print(f"[ML-04] narrative written: {narrative_path}")
    print(f"[ML-04] csv written:       {csv_path}")
    print(f"[ML-04] artifacts dir:     {artifacts_dir}")


if __name__ == "__main__":
    main()
