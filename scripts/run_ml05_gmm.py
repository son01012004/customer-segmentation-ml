"""ML-05 orchestrator: Gaussian Mixture Model (GMM) initial diagnostic runs.

Stage: 06_clustering / ML-05 (GMM — Model-based / Probabilistic
Clustering)

This script runs **initial, value-neutral diagnostic GMM
experiments** on the FE-06 final clustering dataset via the ML-01
Experiment Framework. The script demonstrates:

- adapter registration and dispatch via the registry;
- compatibility of the adapter with the working default
  configuration in ``configs/clustering.yaml``;
- reproducibility under identical input / configuration / library
  version (GMM consumes ``random_state`` for EM initialisation);
- GMM-specific diagnostics (n_components, covariance_type,
  init_params, convergence, lower_bound, AIC, BIC, mixture
  weights, responsibility statistics);
- soft clustering output preservation
  (``algorithm_output_{experiment_id}.parquet`` containing the
  full responsibility matrix).

It is intended as a smoke test and as the initial evidence for
the EPIC-06 Documentation Contract — it does NOT sweep
``n_components``, does NOT sweep ``covariance_type``, does NOT
compare algorithms, does NOT pick a "best" ``n_components`` or
covariance type, and does NOT use AIC / BIC / log-likelihood to
declare a "best" configuration.

Usage (from the repository root):

    python -m scripts.run_ml05_gmm
    python -m scripts.run_ml05_gmm --n-components 5 --covariance-type tied
    python -m scripts.run_ml05_gmm --n-components 4 --covariance-type full  # working defaults

Outputs
-------

Written under ``data/processed/clustering_experiments/``:

- ``cluster_labels_{experiment_id}.parquet`` — CustomerID +
  ClusterLabel + IsNoise + Probability_k columns for each
  component.
- ``algorithm_output_{experiment_id}.parquet`` — CustomerID +
  Probability_k columns (the responsibility matrix as a separate
  artifact for downstream consumers that want soft clustering).
- ``experiment_log_{experiment_id}.json`` — full ExperimentResult
  payload.

Written under ``reports/ml05/``:

- ``ml05_run_summary.json`` — summary of the diagnostic runs
  (input/output SHA, hyperparameters, status, n_components,
  covariance_type, init_params, convergence, lower_bound, AIC,
  BIC, mixture weights, responsibility statistics).
- ``ml05_initial_diagnostic.md`` — Vietnamese narrative report of
  the diagnostic runs (diagnostic-only; no "best" claims).
- ``ml05_covariance_type_diagnostic.csv`` — per-covariance-type
  diagnostic table.

Hard constraints (AGENTS.md §2, EPIC06 contract):

- No algorithm comparison (EPIC-08).
- No sweep over ``n_components`` / ``covariance_type``
  (EPIC-07).
- No use of AIC / BIC / log-likelihood to declare a "best"
  configuration (EPIC-07/08 owns model-selection comparison).
- No segment profiling / naming (EPIC-09).
- No "best / optimal / recommended" claim about
  ``n_components``, ``covariance_type``, ``init_params``, or
  algorithm.
- FE-06 outputs are READ-ONLY.
- Reproducibility metadata (SHA, library versions, seed policy)
  is recorded. ``GMMAdapter.supports_random_state() == True``
  so the framework seed IS consumed.
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
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "ml05"
DEFAULT_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "clustering.yaml"
DEFAULT_INPUT_PATH: Path = DEFAULT_PROCESSED_DIR / "final_clustering_dataset.parquet"
DEFAULT_METADATA_PATH: Path = DEFAULT_PROCESSED_DIR / "customer_metadata.parquet"
DEFAULT_ARTIFACTS_DIR: Path = DEFAULT_PROCESSED_DIR / "clustering_experiments"

# ML-05 working defaults — WORKING_ASSUMPTION, not final approved.
# Mirrors configs/clustering.yaml algorithms.gmm.*.
DEFAULT_N_COMPONENTS: int = 4
DEFAULT_COVARIANCE_TYPE: str = "full"
DEFAULT_INIT_PARAMS: str = "kmeans"
DEFAULT_TOL: float = 1e-3
DEFAULT_REG_COVAR: float = 1e-6
DEFAULT_MAX_ITER: int = 100
DEFAULT_N_INIT: int = 1
DEFAULT_RANDOM_STATE: int = 42

# Covariance types advertised by GMMAdapter (mirrors gmm.SUPPORTED_COVARIANCE_TYPES).
SUPPORTED_COVARIANCE_TYPES: tuple[str, ...] = (
    "full",
    "tied",
    "diag",
    "spherical",
)

# Initialisation strategies advertised by GMMAdapter (mirrors gmm.SUPPORTED_INIT_PARAMS).
SUPPORTED_INIT_PARAMS: tuple[str, ...] = ("kmeans", "random")


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
            "ML-05 GMM initial diagnostic runs. "
            "Reads data/processed/final_clustering_dataset.parquet and "
            "data/processed/customer_metadata.parquet. "
            "Writes artifacts under data/processed/clustering_experiments/ "
            "and reports under reports/ml05/."
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
        help="Output directory for ML-05 reports.",
    )
    parser.add_argument(
        "--n-components",
        type=int,
        default=DEFAULT_N_COMPONENTS,
        help=f"Number of Gaussian components K (working default: {DEFAULT_N_COMPONENTS}).",
    )
    parser.add_argument(
        "--covariance-type",
        type=str,
        default=DEFAULT_COVARIANCE_TYPE,
        choices=list(SUPPORTED_COVARIANCE_TYPES),
        help=f"Shape of each component's covariance matrix "
        f"(working default: {DEFAULT_COVARIANCE_TYPE}).",
    )
    parser.add_argument(
        "--init-params",
        type=str,
        default=DEFAULT_INIT_PARAMS,
        choices=list(SUPPORTED_INIT_PARAMS),
        help=f"EM initialisation strategy (working default: {DEFAULT_INIT_PARAMS}).",
    )
    parser.add_argument(
        "--tol",
        type=float,
        default=DEFAULT_TOL,
        help=f"Convergence tolerance (working default: {DEFAULT_TOL}).",
    )
    parser.add_argument(
        "--reg-covar",
        type=float,
        default=DEFAULT_REG_COVAR,
        help=f"Regularisation added to covariance diagonals "
        f"(working default: {DEFAULT_REG_COVAR}).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=DEFAULT_MAX_ITER,
        help=f"Maximum EM iterations (working default: {DEFAULT_MAX_ITER}).",
    )
    parser.add_argument(
        "--n-init",
        type=int,
        default=DEFAULT_N_INIT,
        help=f"Number of initialisations (working default: {DEFAULT_N_INIT}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Requested random seed. GMM consumes ``random_state`` "
            "for EM initialisation (both kmeans-init and "
            "random-init paths). If omitted, the framework YAML "
            "default / per-algorithm override is used."
        ),
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment identifier. If omitted, an ID is generated from " "the hyperparameters.",
    )
    parser.add_argument(
        "--skip-covariance-diagnostic",
        action="store_true",
        help="Skip the per-covariance-type diagnostic runs (full, tied, "
        "diag, spherical). Default: run a small set of covariance "
        "diagnostics.",
    )
    return parser


def _build_experiment_id(
    *,
    n_components: int,
    covariance_type: str,
    init_params: str,
    seed: int | None,
    label: str | None = None,
) -> str:
    """Build a stable experiment identifier from the hyperparameters."""
    seed_token = f"seed{seed}" if seed is not None else "seedcfg"
    prefix = label if label is not None else "ML-05-GMM"
    return f"{prefix}-k{n_components}-{covariance_type}-{init_params}-{seed_token}"


def _run_single(
    args: argparse.Namespace,
    cfg_path: Path,
    cfg_text: str,
    config_sha: str,
    df: pd.DataFrame,
    md: pd.DataFrame,
    input_sha: str,
    metadata_sha: str,
    n_components: int,
    covariance_type: str,
    init_params: str,
    artifacts_dir: Path,
    *,
    experiment_id: str,
    seed: int | None = None,
) -> dict:
    """Run a single GMM experiment and return a summary dict."""
    cfg = load_framework_config(cfg_path)
    hyperparameters = {
        "n_components": int(n_components),
        "covariance_type": str(covariance_type),
        "init_params": str(init_params),
        "random_state": seed,
        "tol": float(args.tol),
        "reg_covar": float(args.reg_covar),
        "max_iter": int(args.max_iter),
        "n_init": int(args.n_init),
    }
    spec = ExperimentSpec(
        experiment_id=experiment_id,
        algorithm="gmm",
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
        "soft_probabilities_shape": (
            list(result.cluster_result.soft_probabilities.shape)
            if result.cluster_result is not None
            and result.cluster_result.soft_probabilities is not None
            else None
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
    """Build a flat row for the per-covariance-type diagnostic CSV."""
    result = entry["result"]
    extras = result.cluster_result.extra if result.cluster_result is not None else {}
    cluster_sizes = extras.get("cluster_sizes", {}) or {}
    sizes_str = (
        "; ".join(f"{k}:{v}" for k, v in sorted(cluster_sizes.items())) if cluster_sizes else ""
    )
    weights = extras.get("mixture_weights", []) or []
    weights_str = "; ".join(f"{w:.4f}" for w in weights) if weights else ""
    return {
        "experiment_label": primary_label,
        "experiment_id": entry["experiment_id"],
        "n_components": entry["hyperparameters"]["n_components"],
        "covariance_type": entry["hyperparameters"]["covariance_type"],
        "init_params": entry["hyperparameters"]["init_params"],
        "random_state": entry["hyperparameters"]["random_state"],
        "tol": entry["hyperparameters"]["tol"],
        "reg_covar": entry["hyperparameters"]["reg_covar"],
        "max_iter": entry["hyperparameters"]["max_iter"],
        "n_init": entry["hyperparameters"]["n_init"],
        "status": result.status,
        "n_clusters_found": result.n_clusters,
        "n_samples": result.n_samples,
        "converged": extras.get("converged"),
        "n_iter": extras.get("n_iter"),
        "lower_bound": extras.get("lower_bound"),
        "aic": extras.get("aic"),
        "bic": extras.get("bic"),
        "mixture_weights": weights_str,
        "cluster_sizes": sizes_str,
        "row_sum_min": extras.get("soft_probabilities_row_sum_min"),
        "row_sum_max": extras.get("soft_probabilities_row_sum_max"),
        "max_prob_min": extras.get("responsibility_max_probability_min"),
        "max_prob_max": extras.get("responsibility_max_probability_max"),
        "max_prob_mean": extras.get("responsibility_max_probability_mean"),
        "execution_time_s": result.execution_time,
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

    print(f"[ML-05] config:           {cfg_path}")
    print(f"[ML-05] config SHA-256:   {config_sha[:16]}...")
    print(f"[ML-05] dataset version:  {cfg.input.dataset_version}")

    # ---- Validate registry ----
    if not AlgorithmRegistry.is_registered("gmm"):
        raise RuntimeError(
            "Algorithm 'gmm' is not registered. "
            "Ensure customer_segmentation.clustering is imported so "
            "GMMAdapter's @register decorator runs."
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
    print(f"[ML-05] input SHA-256:    {input_sha[:16]}...")
    print(f"[ML-05] metadata SHA-256: {metadata_sha[:16]}...")
    print(f"[ML-05] matrix shape:     {df.shape}")

    # ---- Prepare output dirs ----
    artifacts_dir = args.artifacts_dir
    report_dir = args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    # ---- Resolve seed ----
    # Default behaviour: honour --seed if given, otherwise use the
    # framework default from YAML (the runner will resolve it).
    resolved_seed = args.seed if args.seed is not None else cfg.random_seed.default

    # ---- Run primary experiment (working defaults) ----
    primary_experiment_id = args.experiment_id or _build_experiment_id(
        n_components=args.n_components,
        covariance_type=args.covariance_type,
        init_params=args.init_params,
        seed=resolved_seed,
    )
    print(f"[ML-05] primary experiment id: {primary_experiment_id}")
    print(
        f"[ML-05] primary hyperparameters: "
        f"n_components={args.n_components}, covariance_type={args.covariance_type}, "
        f"init_params={args.init_params}, random_state={resolved_seed}, "
        f"max_iter={args.max_iter}, n_init={args.n_init}"
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
        n_components=args.n_components,
        covariance_type=args.covariance_type,
        init_params=args.init_params,
        artifacts_dir=artifacts_dir,
        experiment_id=primary_experiment_id,
        seed=resolved_seed,
    )

    # ---- Run per-covariance-type diagnostic experiments ----
    # These are *initial diagnostic* runs to verify the adapter
    # supports each covariance type on the FE-06 dataset. They are
    # NOT a controlled sweep (EPIC-07 owns that). Default: run all
    # four covariance types.
    per_cov_summaries: list[dict] = []
    if not args.skip_covariance_diagnostic:
        # Always include the working-default covariance type so the
        # diagnostic CSV has a complete set.
        diagnostic_covariances: list[str] = list(SUPPORTED_COVARIANCE_TYPES)
        if args.covariance_type not in diagnostic_covariances:
            diagnostic_covariances.insert(0, args.covariance_type)
        print("[ML-05] running per-covariance-type diagnostic experiments " "(initial only)...")
        for cov in diagnostic_covariances:
            cov_experiment_id = _build_experiment_id(
                n_components=args.n_components,
                covariance_type=cov,
                init_params=args.init_params,
                seed=resolved_seed,
                label="ML-05-GMM-diag",
            )
            cov_summary = _run_single(
                args=args,
                cfg_path=cfg_path,
                cfg_text=cfg_text,
                config_sha=config_sha,
                df=df,
                md=md,
                input_sha=input_sha,
                metadata_sha=metadata_sha,
                n_components=args.n_components,
                covariance_type=cov,
                init_params=args.init_params,
                artifacts_dir=artifacts_dir,
                experiment_id=cov_experiment_id,
                seed=resolved_seed,
            )
            per_cov_summaries.append(cov_summary)

    # ---- Build ML-05 run summary ----
    primary_result = primary["result"]
    summary: dict = {
        "stage": "ML-05",
        "stage_version": "ML05-v1.0",
        "stage_status": "TECHNICALLY_IMPLEMENTED",
        "scope_boundaries": [
            "GMM model-based clustering adapter implementation only.",
            "Initial diagnostic runs with one (n_components, covariance_type, "
            "init_params) per run; not a controlled sweep.",
            "GMM-specific diagnostics recorded (n_components, covariance_type, "
            "init_params, convergence, lower_bound, AIC, BIC, mixture weights, "
            "responsibility statistics).",
            "Soft clustering output preserved via algorithm_output_*.parquet "
            "(CustomerID + Probability_k columns) and Probability_k columns in "
            "cluster_labels_*.parquet.",
            "No algorithm comparison (EPIC-08).",
            "No sweep over (n_components, covariance_type, init_params) (EPIC-07).",
            "AIC / BIC / log-likelihood recorded as diagnostics only; "
            "no claim of 'best' configuration based on them.",
            "No segment profiling / naming (EPIC-09).",
            "FE-06 outputs are READ-ONLY.",
            "GMM consumes random_state for EM initialisation; " "supports_random_state=True.",
        ],
        "pending_review_notes": [
            "Working default n_components=4 is WORKING_ASSUMPTION, not final approved.",
            "Working default covariance_type='full' is WORKING_ASSUMPTION, not final approved.",
            "Working default init_params='kmeans' is WORKING_ASSUMPTION, not final approved.",
            "Working default tol=1e-3 / reg_covar=1e-6 / max_iter=100 / n_init=1 are "
            "WORKING_ASSUMPTION, not final approved.",
            "Initial per-covariance-type diagnostics are NOT a controlled sweep; "
            "EPIC-07 owns that.",
            "Soft clustering output (responsibility matrix) is preserved in "
            "algorithm_output_*.parquet and cluster_labels_*.parquet; EPIC-07/08/09 "
            "will consume it.",
            "No claim of 'best n_components' / 'best covariance_type' / "
            "'best init_params' / 'best algorithm' anywhere in this run.",
        ],
        "assumptions": [
            "GMMAdapter wraps sklearn.mixture.GaussianMixture with the "
            "(n_components, covariance_type, init_params, random_state, tol, "
            "reg_covar, max_iter, n_init) hyperparameters.",
            "CustomerID lives in metadata, never in matrix.",
            "Seed policy: framework.random_seed.default OR per-algorithm override "
            "OR --seed. The seed IS consumed by GMM for EM initialisation "
            "(supports_random_state=True).",
            "Hard cluster label is derived as argmax over the responsibility "
            "matrix (sklearn GaussianMixture.predict uses posterior "
            "probabilities; we record both hard labels and the full "
            "responsibility matrix).",
            "AIC / BIC are recorded as algorithm-specific diagnostics only; "
            "model-selection comparison is OUT OF SCOPE for ML-05.",
            "Label permutation between components across runs is a known GMM "
            "property; reproducibility checks use responsibilities, mixture "
            "weights, lower_bound, AIC, BIC (NOT raw labels).",
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
        "per_covariance_type_diagnostic": [_summarize_one(s) for s in per_cov_summaries],
        "artifacts": {
            "artifact_paths": dict(primary_result.artifact_paths),
        },
    }
    if primary_result.status == "FAILED":
        summary["primary_experiment"]["error"] = primary_result.error

    summary_path = report_dir / "ml05_run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=False, default=str),
        encoding="utf-8",
    )

    # ---- Build per-covariance-type diagnostic CSV ----
    csv_path = report_dir / "ml05_covariance_type_diagnostic.csv"
    rows = [_csv_row(primary, primary_label="primary")]
    for cov_summary in per_cov_summaries:
        rows.append(
            _csv_row(
                cov_summary,
                primary_label=(f"diagnostic-{cov_summary['hyperparameters']['covariance_type']}"),
            )
        )
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    # ---- Build Vietnamese narrative report (diagnostic only) ----
    status_vi = "THÀNH CÔNG" if primary_result.status == "SUCCESS" else "THẤT BẠI"
    extras = (
        primary_result.cluster_result.extra if primary_result.cluster_result is not None else {}
    )

    md_lines: list[str] = []
    md_lines.append("# ML-05 — Gaussian Mixture Model (GMM) Initial Diagnostic Runs")
    md_lines.append("")
    md_lines.append("> **Tài liệu này là báo cáo vận hành (diagnostic report) cho lần chạy")
    md_lines.append("> GMM đầu tiên trên Final Clustering Dataset của FE-06.**")
    md_lines.append("> Đây KHÔNG phải evaluation phase, KHÔNG so sánh thuật toán,")
    md_lines.append("> KHÔNG so sánh n_components / covariance_type / init_params,")
    md_lines.append("> KHÔNG chọn best K, KHÔNG chọn best covariance, KHÔNG chọn best algorithm.")
    md_lines.append("> Working configuration là WORKING_ASSUMPTION, chưa được mentor approve.")
    md_lines.append("")
    md_lines.append("## 1. Tổng quan")
    md_lines.append("")
    md_lines.append(f"- Trạng thái primary run: **{status_vi}**")
    md_lines.append(f"- Primary experiment ID: `{primary_experiment_id}`")
    md_lines.append(f"- Algorithm: `gmm` (sklearn, version `{primary_result.algorithm_version}`)")
    md_lines.append("- Algorithm family: `model_based` (hard label + soft posterior probabilities)")
    md_lines.append(f"- Dataset version: `{cfg.input.dataset_version}`")
    md_lines.append(f"- Số customers: **{primary_result.n_samples}**")
    md_lines.append(f"- Số features: **{df.shape[1]}**")
    md_lines.append("")
    md_lines.append("## 2. Configuration (working defaults; WORKING_ASSUMPTION)")
    md_lines.append("")
    md_lines.append(f"- `n_components = {args.n_components}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(
        f"- `covariance_type = {args.covariance_type}` (working default; WORKING_ASSUMPTION)"
    )
    md_lines.append(f"- `init_params = {args.init_params}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(
        f"- `tol = {args.tol}`, `reg_covar = {args.reg_covar}`, "
        f"`max_iter = {args.max_iter}`, `n_init = {args.n_init}` (working defaults)"
    )
    md_lines.append(
        f"- `random_state` requested = "
        f"`{args.seed if args.seed is not None else cfg.random_seed.default}`"
    )
    md_lines.append(
        f"- `random_state` used = `{primary_result.random_seed_used}` "
        f"(GMM consumes random_state for EM initialisation; supports_random_state=True)"
    )
    md_lines.append("")
    md_lines.append("## 3. GMM theory recap (documentation)")
    md_lines.append("")
    md_lines.append("- Mỗi cluster/component được mô hình hóa bằng một Gaussian distribution:")
    md_lines.append("  `N(x | μ_k, Σ_k)` với `μ_k` là mean vector và `Σ_k` là covariance matrix.")
    md_lines.append("- Mixture distribution: `p(x) = Σ_{k=1..K} π_k · N(x | μ_k, Σ_k)`.")
    md_lines.append(
        "- Posterior responsibility (soft assignment): "
        "`γ_ik = P(z_i = k | x_i) = [π_k · N(x_i | μ_k, Σ_k)] / "
        "[Σ_j π_j · N(x_i | μ_j, Σ_j)]`."
    )
    md_lines.append(
        "- Hard label = `argmax_k γ_ik` (sklearn `predict` chính là argmax của " "`predict_proba`)."
    )
    md_lines.append(
        "- Expectation-Maximization (EM) lặp lại E-step (tính `γ_ik` theo "
        "parameters hiện tại) và M-step (update `π_k`, `μ_k`, `Σ_k` để tối đa "
        "expected complete-data log-likelihood dưới `γ_ik` hiện tại) cho đến "
        "khi hội tụ hoặc đạt `max_iter`."
    )
    md_lines.append(
        "- `init_params`: `kmeans` chạy một pass K-Means để seed means; "
        "`random` sample responsibilities từ Dirichlet đều rồi derive "
        "means / covariances / weights."
    )
    md_lines.append("")
    md_lines.append("## 4. Covariance type")
    md_lines.append("")
    md_lines.append(
        "- `full`: mỗi component có covariance matrix riêng (linh hoạt nhất, "
        "nhiều parameter nhất)."
    )
    md_lines.append("- `tied`: tất cả components dùng chung một covariance matrix " "(trung gian).")
    md_lines.append(
        "- `diag`: mỗi component có covariance diagonal (bỏ correlation giữa " "features)."
    )
    md_lines.append("- `spherical`: mỗi component có một variance scalar (ít parameter nhất).")
    md_lines.append("- KHÔNG có covariance type nào được kết luận là 'best' trong tài liệu này.")
    md_lines.append("")
    md_lines.append("## 5. Kết quả primary run")
    md_lines.append("")
    n_clusters_text = (
        f"{primary_result.n_clusters}"
        if primary_result.n_clusters is not None
        else "(không xác định)"
    )
    md_lines.append(f"- Số components: **{extras.get('n_components', 'n/a')}**")
    md_lines.append(f"- Số clusters tìm được (hard label): **{n_clusters_text}**")
    md_lines.append(f"- `covariance_type`: **{extras.get('covariance_type', 'n/a')}**")
    md_lines.append(f"- `init_params`: **{extras.get('init_params', 'n/a')}**")
    md_lines.append(f"- `converged`: **{extras.get('converged')}**")
    md_lines.append(f"- `n_iter`: **{extras.get('n_iter')}**")
    md_lines.append(f"- `lower_bound`: **{extras.get('lower_bound'):.6f}**")
    md_lines.append(f"- AIC: **{extras.get('aic'):.4f}** (diagnostic only)")
    md_lines.append(f"- BIC: **{extras.get('bic'):.4f}** (diagnostic only)")
    weights = extras.get("mixture_weights", [])
    if weights:
        md_lines.append(f"- Mixture weights (π_k): `{weights}`")
    cluster_sizes = extras.get("cluster_sizes", {})
    md_lines.append(f"- Component sizes (từ hard label): `{cluster_sizes}`")
    md_lines.append(f"- Execution time: **{primary_result.execution_time:.4f} s**")
    md_lines.append("")
    md_lines.append("### 5.1 Soft clustering (responsibility matrix)")
    md_lines.append("")
    sp_shape = extras.get("soft_probabilities_shape")
    if sp_shape is not None:
        md_lines.append(f"- Responsibility matrix shape: `{sp_shape}`")
    md_lines.append(
        f"- Row-sum min/max: **{extras.get('soft_probabilities_row_sum_min'):.12f}** / "
        f"**{extras.get('soft_probabilities_row_sum_max'):.12f}** "
        "(kỳ vọng xấp xỉ 1.0)"
    )
    md_lines.append(
        f"- Max-probability per row min/max/mean: "
        f"**{extras.get('responsibility_max_probability_min'):.6f}** / "
        f"**{extras.get('responsibility_max_probability_max'):.6f}** / "
        f"**{extras.get('responsibility_max_probability_mean'):.6f}**"
    )
    md_lines.append("")
    md_lines.append("## 6. Per-covariance-type diagnostic runs")
    md_lines.append("")
    md_lines.append(
        "Bốn initial diagnostic runs đã chạy (một cho mỗi covariance type), "
        "cùng `n_components` và `init_params`. Đây KHÔNG phải controlled "
        "sweep — chỉ để verify adapter hỗ trợ đầy đủ các covariance type đã "
        "quảng cáo và thu thập GMM-specific diagnostics."
    )
    md_lines.append("")
    md_lines.append(
        "| Label | Covariance | Status | converged | n_iter | lower_bound | "
        "AIC | BIC | Execution time (s) |"
    )
    md_lines.append(
        "|-------|------------|--------|-----------|-------:|------------:|"
        "----:|----:|-------------------:|"
    )
    if per_cov_summaries:
        for s in per_cov_summaries:
            r = s["result"]
            e = r.cluster_result.extra if r.cluster_result is not None else {}
            cov = s["hyperparameters"]["covariance_type"]
            lb = e.get("lower_bound")
            aic = e.get("aic")
            bic = e.get("bic")
            lb_s = f"{lb:.4f}" if isinstance(lb, (int, float)) else "n/a"
            aic_s = f"{aic:.2f}" if isinstance(aic, (int, float)) else "n/a"
            bic_s = f"{bic:.2f}" if isinstance(bic, (int, float)) else "n/a"
            md_lines.append(
                f"| diagnostic | {cov} | {r.status} | {e.get('converged')} | "
                f"{e.get('n_iter')} | {lb_s} | {aic_s} | {bic_s} | "
                f"{r.execution_time:.4f} |"
            )
    else:
        md_lines.append("| (skipped via --skip-covariance-diagnostic) | | | | | | | | |")
    md_lines.append("")
    md_lines.append("## 7. Provenance")
    md_lines.append("")
    md_lines.append(f"- Input SHA-256: `{input_sha}`")
    md_lines.append(f"- Metadata SHA-256: `{metadata_sha}`")
    md_lines.append(f"- Config SHA-256: `{config_sha}`")
    md_lines.append(f"- Input path: `{input_path}`")
    md_lines.append(f"- Metadata path: `{metadata_path}`")
    md_lines.append(f"- Config path: `{cfg_path}`")
    md_lines.append("")
    md_lines.append("## 8. Artifacts")
    md_lines.append("")
    md_lines.append("### 8.1 Primary run")
    md_lines.append("")
    for name, path in primary_result.artifact_paths.items():
        md_lines.append(f"- `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("### 8.2 Per-covariance-type diagnostic runs")
    md_lines.append("")
    for s in per_cov_summaries:
        md_lines.append(
            f"- covariance `{s['hyperparameters']['covariance_type']}` — "
            f"`{s['experiment_id']}`:"
        )
        for name, path in s["result"].artifact_paths.items():
            md_lines.append(f"    - `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("## 9. Decision status")
    md_lines.append("")
    md_lines.append("- `TECHNICALLY_IMPLEMENTED`: GMM adapter và diagnostic runs đã chạy.")
    md_lines.append(
        "- `WORKING_ASSUMPTION`: `n_components = 4`, "
        "`covariance_type = 'full'`, `init_params = 'kmeans'`, "
        "`tol = 1e-3`, `reg_covar = 1e-6`, `max_iter = 100`, `n_init = 1`."
    )
    md_lines.append(
        "- `OUT_OF_SCOPE`: evaluation metric, algorithm comparison, "
        "(n_components, covariance_type, init_params) sweep, "
        "AIC/BIC/log-likelihood model-selection, segment profiling, "
        "research comparison viz."
    )
    md_lines.append(
        "- `OUT_OF_SCOPE`: chọn `best n_components` / "
        "`best covariance_type` / `best init_params` / `best algorithm`."
    )
    md_lines.append("")
    md_lines.append("## 10. Notes")
    md_lines.append("")
    md_lines.append(
        "- GMM consume `random_state` cho EM initialisation; "
        "`supports_random_state()` trả về `True`. Framework runner "
        "pass seed vào adapter."
    )
    md_lines.append(
        "- Soft clustering output được bảo toàn: "
        "`cluster_labels_{experiment_id}.parquet` chứa `Probability_k` "
        "columns cho mỗi component; `algorithm_output_{experiment_id}.parquet` "
        "chứa ma trận responsibility đầy đủ cho downstream consumers."
    )
    md_lines.append(
        "- Hard label = `argmax` của responsibility matrix "
        "(sklearn GaussianMixture.predict chính là argmax của predict_proba). "
        "Adapter ghi nhận cả hard label và full soft probabilities."
    )
    md_lines.append(
        "- `lower_bound` (negative variational lower bound), `AIC`, `BIC` "
        "được ghi nhận trong `cluster_result.extra` là **diagnostics only**. "
        "Không dùng để tuyên bố một configuration là 'best'."
    )
    md_lines.append(
        "- Per-covariance-type diagnostics KHÔNG được dùng để kết luận "
        "'best covariance_type' — đó là EPIC-07 scope."
    )
    md_lines.append(
        "- Reproducibility: cùng input + config + random_state + library "
        "version → responsibilities / mixture weights / lower_bound / AIC / "
        "BIC / converged / n_iter giống nhau. Raw label equality KHÔNG được "
        "dùng làm reproducibility check vì component permutation có thể xảy "
        "ra giữa các lần chạy (cùng seed nhưng local maxima khác nhau)."
    )
    md_lines.append(
        '- KHÔNG kết luận "best n_components", "best covariance_type", '
        '"best init_params", "best algorithm" trong tài liệu này.'
    )
    md_lines.append("")
    md_lines.append(
        f"_Báo cáo này được sinh tự động từ execution thực tế. SHA-256 và "
        f"execution_time lấy trực tiếp từ "
        f"`experiment_log_{primary_experiment_id}.json`._"
    )

    narrative_path = report_dir / "ml05_initial_diagnostic.md"
    narrative_path.write_text("\n".join(md_lines), encoding="utf-8")

    # ---- Print summary to stdout ----
    print(f"[ML-05] primary status:    {primary_result.status}")
    print(f"[ML-05] primary n_clusters: {primary_result.n_clusters}")
    if primary_result.cluster_result is not None:
        e = primary_result.cluster_result.extra
        print(
            f"[ML-05] n_components={e.get('n_components')}, "
            f"cov={e.get('covariance_type')}, "
            f"init={e.get('init_params')}, "
            f"converged={e.get('converged')}, "
            f"n_iter={e.get('n_iter')}, "
            f"lower_bound={e.get('lower_bound'):.4f}"
        )
    print(f"[ML-05] primary exec time: {primary_result.execution_time:.4f} s")
    print(f"[ML-05] per-covariance runs: {len(per_cov_summaries)}")
    for s in per_cov_summaries:
        r = s["result"]
        e = r.cluster_result.extra if r.cluster_result is not None else {}
        print(
            f"[ML-05]   cov={s['hyperparameters']['covariance_type']}: "
            f"status={r.status}, converged={e.get('converged')}, "
            f"lower_bound={e.get('lower_bound'):.4f}, "
            f"exec={r.execution_time:.4f}s"
        )
    print(f"[ML-05] summary written:   {summary_path}")
    print(f"[ML-05] narrative written: {narrative_path}")
    print(f"[ML-05] csv written:       {csv_path}")
    print(f"[ML-05] artifacts dir:     {artifacts_dir}")


if __name__ == "__main__":
    main()
