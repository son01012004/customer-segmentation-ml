"""ML-06 orchestrator: Fuzzy C-Means (FCM) initial diagnostic runs.

Stage: 06_clustering / ML-06 (Fuzzy C-Means — Fuzzy Clustering +
Algorithm Baseline Completion)

This script runs **initial, value-neutral diagnostic FCM
experiments** on the FE-06 final clustering dataset via the ML-01
Experiment Framework. The script demonstrates:

- adapter registration and dispatch via the registry;
- compatibility of the adapter with the working default
  configuration in ``configs/clustering.yaml``;
- reproducibility under identical input / configuration / library
  version (the custom Bezdek FCM core consumes ``random_state``
  for the membership-matrix Dirichlet initialisation, with a
  fixed seed yielding a deterministic FCM run);
- FCM-specific diagnostics (n_clusters, m, max_iter, error,
  convergence, n_iter, final_objective, objective history,
  centroid shape, membership shape, membership integrity,
  per-row confidence summary, cluster sizes);
- soft clustering output preservation
  (``algorithm_output_{experiment_id}.parquet`` containing the
  full fuzzy membership matrix as ``Membership_k`` columns).

It is intended as a smoke test and as the initial evidence for the
EPIC-06 Documentation Contract — it does NOT sweep ``n_clusters``
or ``m``, does NOT compare FCM to other algorithms, does NOT pick
a "best" ``c`` or ``m``, and does NOT use the final objective /
confidence diagnostics to declare a "best" configuration.

Usage (from the repository root):

    python -m scripts.run_ml06_fuzzy_cmeans
    python -m scripts.run_ml06_fuzzy_cmeans --n-clusters 5 --m 1.7
    python -m scripts.run_ml06_fuzzy_cmeans --n-clusters 4 --m 2.0  # working defaults

Outputs
-------

Written under ``data/processed/clustering_experiments/``:

- ``cluster_labels_{experiment_id}.parquet`` — CustomerID +
  ClusterLabel + IsNoise + ``Membership_k`` columns for each
  fuzzy cluster.
- ``algorithm_output_{experiment_id}.parquet`` — CustomerID +
  ``Membership_k`` columns (the membership matrix as a separate
  artifact for downstream consumers that want soft clustering).
- ``experiment_log_{experiment_id}.json`` — full ExperimentResult
  payload.

Written under ``reports/ml06/``:

- ``ml06_run_summary.json`` — summary of the diagnostic runs
  (input/output SHA, hyperparameters, status, n_clusters,
  fuzziness, convergence, n_iter, final_objective, objective-
  history summary, centroid/membership shapes, membership
  integrity, per-row confidence summary, cluster sizes).
- ``ml06_initial_diagnostic.md`` — Vietnamese narrative report of
  the diagnostic runs (diagnostic-only; no "best" claims).
- ``ml06_fuzziness_diagnostic.csv`` — per-fuzziness diagnostic
  table.

Hard constraints (AGENTS.md §2, EPIC06 contract):

- No algorithm comparison (EPIC-08).
- No sweep over ``n_clusters`` or ``m`` (EPIC-07).
- No use of the final objective / per-row confidence to declare a
  "best" configuration (EPIC-07/08 owns model-selection
  comparison).
- No segment profiling / naming (EPIC-09).
- No "best / optimal / recommended" claim about
  ``n_clusters``, ``m``, or algorithm.
- FE-06 outputs are READ-ONLY.
- Reproducibility metadata (SHA, library versions, seed policy)
  is recorded. ``FuzzyCMeansAdapter.supports_random_state() ==
  True`` so the framework seed IS consumed.
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
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "ml06"
DEFAULT_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "clustering.yaml"
DEFAULT_INPUT_PATH: Path = DEFAULT_PROCESSED_DIR / "final_clustering_dataset.parquet"
DEFAULT_METADATA_PATH: Path = DEFAULT_PROCESSED_DIR / "customer_metadata.parquet"
DEFAULT_ARTIFACTS_DIR: Path = DEFAULT_PROCESSED_DIR / "clustering_experiments"

# ML-06 working defaults — WORKING_ASSUMPTION, not final approved.
# Mirrors configs/clustering.yaml algorithms.fuzzy_cmeans.*.
DEFAULT_N_CLUSTERS: int = 4
DEFAULT_M: float = 2.0
DEFAULT_MAX_ITER: int = 300
DEFAULT_ERROR: float = 1e-4
DEFAULT_RANDOM_STATE: int = 42

# Fuzziness values advertised by the diagnostic CSV (initial only;
# not a controlled sweep). Mirrors configs/clustering.yaml
# algorithms.fuzzy_cmeans.fuzziness_options.
DEFAULT_FUZZINESS_OPTIONS: tuple[float, ...] = (1.5, 2.0, 2.5, 3.0)


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
            "ML-06 Fuzzy C-Means initial diagnostic runs. "
            "Reads data/processed/final_clustering_dataset.parquet and "
            "data/processed/customer_metadata.parquet. "
            "Writes artifacts under data/processed/clustering_experiments/ "
            "and reports under reports/ml06/."
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
        help="Output directory for ML-06 reports.",
    )
    parser.add_argument(
        "--n-clusters",
        type=int,
        default=DEFAULT_N_CLUSTERS,
        help=f"Number of fuzzy clusters c (working default: {DEFAULT_N_CLUSTERS}).",
    )
    parser.add_argument(
        "--m",
        type=float,
        default=DEFAULT_M,
        help=f"Fuzziness parameter m; must be > 1 " f"(working default: {DEFAULT_M}).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=DEFAULT_MAX_ITER,
        help=f"Maximum FCM iterations (working default: {DEFAULT_MAX_ITER}).",
    )
    parser.add_argument(
        "--error",
        type=float,
        default=DEFAULT_ERROR,
        help=f"Convergence threshold on membership-matrix max-norm "
        f"(working default: {DEFAULT_ERROR}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Requested random seed. The custom Bezdek FCM core "
            "consumes ``random_state`` for the membership-matrix "
            "Dirichlet initialisation. If omitted, the framework "
            "YAML default / per-algorithm override is used."
        ),
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment identifier. If omitted, an ID is generated from " "the hyperparameters.",
    )
    parser.add_argument(
        "--skip-fuzziness-diagnostic",
        action="store_true",
        help="Skip the per-fuzziness-value diagnostic runs. "
        "Default: run a small set of fuzziness diagnostics.",
    )
    return parser


def _build_experiment_id(
    *,
    n_clusters: int,
    m: float,
    max_iter: int,
    error: float,
    seed: int | None,
    label: str | None = None,
) -> str:
    """Build a stable experiment identifier from the hyperparameters."""
    seed_token = f"seed{seed}" if seed is not None else "seedcfg"
    prefix = label if label is not None else "ML-06-FCM"
    # Format m with a stable short representation to keep experiment
    # ids readable across runs.
    m_token = f"m{m:g}"
    err_token = f"err{error:g}"
    return f"{prefix}-c{n_clusters}-{m_token}-{err_token}-mi{max_iter}-{seed_token}"


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
    m: float,
    max_iter: int,
    error: float,
    artifacts_dir: Path,
    *,
    experiment_id: str,
    seed: int | None = None,
) -> dict:
    """Run a single FCM experiment and return a summary dict."""
    cfg = load_framework_config(cfg_path)
    hyperparameters = {
        "n_clusters": int(n_clusters),
        "m": float(m),
        "max_iter": int(max_iter),
        "error": float(error),
        "random_state": seed,
    }
    spec = ExperimentSpec(
        experiment_id=experiment_id,
        algorithm="fuzzy_cmeans",
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
        "soft_membership_shape": (
            list(result.cluster_result.soft_membership.shape)
            if result.cluster_result is not None
            and result.cluster_result.soft_membership is not None
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
    """Build a flat row for the per-fuzziness diagnostic CSV."""
    result = entry["result"]
    extras = result.cluster_result.extra if result.cluster_result is not None else {}
    cluster_sizes = extras.get("cluster_sizes", {}) or {}
    sizes_str = (
        "; ".join(f"{k}:{v}" for k, v in sorted(cluster_sizes.items())) if cluster_sizes else ""
    )
    obj_first_5 = extras.get("objective_history_first_5", []) or []
    obj_first_5_str = "; ".join(f"{x:.6f}" for x in obj_first_5) if obj_first_5 else ""
    obj_last_5 = extras.get("objective_history_last_5", []) or []
    obj_last_5_str = "; ".join(f"{x:.6f}" for x in obj_last_5) if obj_last_5 else ""
    return {
        "experiment_label": primary_label,
        "experiment_id": entry["experiment_id"],
        "n_clusters": entry["hyperparameters"]["n_clusters"],
        "m": entry["hyperparameters"]["m"],
        "max_iter": entry["hyperparameters"]["max_iter"],
        "error": entry["hyperparameters"]["error"],
        "random_state": entry["hyperparameters"]["random_state"],
        "status": result.status,
        "converged": extras.get("converged"),
        "n_iter": extras.get("n_iter"),
        "final_objective": extras.get("final_objective"),
        "objective_history_length": extras.get("objective_history_length"),
        "objective_history_first_5": obj_first_5_str,
        "objective_history_last_5": obj_last_5_str,
        "centroid_shape": (
            ";".join(str(s) for s in extras.get("centroid_shape", []))
            if extras.get("centroid_shape")
            else ""
        ),
        "membership_shape": (
            ";".join(str(s) for s in extras.get("membership_shape", []))
            if extras.get("membership_shape")
            else ""
        ),
        "membership_min": extras.get("membership_min"),
        "membership_max": extras.get("membership_max"),
        "membership_row_sum_min": extras.get("membership_row_sum_min"),
        "membership_row_sum_max": extras.get("membership_row_sum_max"),
        "membership_confidence_min": extras.get("membership_confidence_min"),
        "membership_confidence_max": extras.get("membership_confidence_max"),
        "membership_confidence_mean": extras.get("membership_confidence_mean"),
        "cluster_sizes": sizes_str,
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

    print(f"[ML-06] config:           {cfg_path}")
    print(f"[ML-06] config SHA-256:   {config_sha[:16]}...")
    print(f"[ML-06] dataset version:  {cfg.input.dataset_version}")

    # ---- Validate registry ----
    if not AlgorithmRegistry.is_registered("fuzzy_cmeans"):
        raise RuntimeError(
            "Algorithm 'fuzzy_cmeans' is not registered. "
            "Ensure customer_segmentation.clustering is imported so "
            "FuzzyCMeansAdapter's @register decorator runs."
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
    print(f"[ML-06] input SHA-256:    {input_sha[:16]}...")
    print(f"[ML-06] metadata SHA-256: {metadata_sha[:16]}...")
    print(f"[ML-06] matrix shape:     {df.shape}")

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
        n_clusters=args.n_clusters,
        m=args.m,
        max_iter=args.max_iter,
        error=args.error,
        seed=resolved_seed,
    )
    print(f"[ML-06] primary experiment id: {primary_experiment_id}")
    print(
        f"[ML-06] primary hyperparameters: "
        f"n_clusters={args.n_clusters}, m={args.m}, "
        f"max_iter={args.max_iter}, error={args.error}, "
        f"random_state={resolved_seed}"
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
        m=args.m,
        max_iter=args.max_iter,
        error=args.error,
        artifacts_dir=artifacts_dir,
        experiment_id=primary_experiment_id,
        seed=resolved_seed,
    )

    # ---- Run per-fuzziness diagnostic experiments ----
    # These are *initial diagnostic* runs to verify the adapter
    # supports the configured fuzziness values on the FE-06
    # dataset. They are NOT a controlled sweep (EPIC-07 owns
    # that). Default: run all four fuzziness values listed in the
    # config.
    per_fuzziness_summaries: list[dict] = []
    if not args.skip_fuzziness_diagnostic:
        diagnostic_m_values: list[float] = list(DEFAULT_FUZZINESS_OPTIONS)
        # Always include the working-default m so the diagnostic
        # CSV has the canonical row even if it is already in the
        # list.
        if args.m not in diagnostic_m_values:
            diagnostic_m_values.insert(0, args.m)
        print("[ML-06] running per-fuzziness diagnostic experiments (initial only)...")
        for m_val in diagnostic_m_values:
            m_experiment_id = _build_experiment_id(
                n_clusters=args.n_clusters,
                m=m_val,
                max_iter=args.max_iter,
                error=args.error,
                seed=resolved_seed,
                label="ML-06-FCM-diag",
            )
            m_summary = _run_single(
                args=args,
                cfg_path=cfg_path,
                cfg_text=cfg_text,
                config_sha=config_sha,
                df=df,
                md=md,
                input_sha=input_sha,
                metadata_sha=metadata_sha,
                n_clusters=args.n_clusters,
                m=m_val,
                max_iter=args.max_iter,
                error=args.error,
                artifacts_dir=artifacts_dir,
                experiment_id=m_experiment_id,
                seed=resolved_seed,
            )
            per_fuzziness_summaries.append(m_summary)

    # ---- Build ML-06 run summary ----
    primary_result = primary["result"]
    summary: dict = {
        "stage": "ML-06",
        "stage_version": "ML06-v1.0",
        "stage_status": "TECHNICALLY_IMPLEMENTED",
        "scope_boundaries": [
            "Fuzzy C-Means fuzzy clustering adapter implementation only.",
            "Initial diagnostic runs with one (n_clusters, m, max_iter, error) "
            "per run; not a controlled sweep.",
            "FCM-specific diagnostics recorded (n_clusters, fuzziness, "
            "max_iter, error, converged, n_iter, final_objective, "
            "objective_history summary, centroid / membership shape, "
            "membership integrity, per-row confidence summary, "
            "cluster_sizes from hard labels).",
            "Soft clustering output (full fuzzy membership matrix) preserved "
            "via algorithm_output_*.parquet (CustomerID + Membership_k "
            "columns) and Membership_k columns in cluster_labels_*.parquet.",
            "No algorithm comparison (EPIC-08).",
            "No sweep over (n_clusters, m, max_iter, error) (EPIC-07).",
            "Final objective / per-row confidence recorded as diagnostics "
            "only; no claim of 'best' configuration based on them.",
            "Hard cluster label derived as argmax over the membership matrix "
            "and recorded alongside the membership matrix itself (lossy "
            "projection; downstream consumers needing soft partition MUST "
            "read Membership_k columns).",
            "No segment profiling / naming (EPIC-09).",
            "FE-06 outputs are READ-ONLY.",
            "FCM consumes random_state for the membership-matrix Dirichlet "
            "initialisation; supports_random_state=True.",
        ],
        "pending_review_notes": [
            "Working default n_clusters=4 is WORKING_ASSUMPTION, not final approved.",
            "Working default m=2.0 is WORKING_ASSUMPTION, not final approved.",
            "Working default max_iter=300 is WORKING_ASSUMPTION, not final approved.",
            "Working default error=1e-4 is WORKING_ASSUMPTION, not final approved.",
            "Initial per-fuzziness diagnostics are NOT a controlled sweep; " "EPIC-07 owns that.",
            "Soft clustering output (membership matrix) is preserved in "
            "algorithm_output_*.parquet and cluster_labels_*.parquet; "
            "EPIC-07/08/09 will consume it.",
            "No claim of 'best n_clusters' / 'best m' / 'best algorithm' " "anywhere in this run.",
        ],
        "assumptions": [
            "FuzzyCMeansAdapter wraps a custom numpy-based Bezdek / Dunn FCM "
            "core (no external scikit-fuzzy dependency) with the "
            "(n_clusters, m, max_iter, error, random_state) hyperparameters.",
            "CustomerID lives in metadata, never in matrix.",
            "Seed policy: framework.random_seed.default OR per-algorithm "
            "override OR --seed. The seed IS consumed by the FCM core for "
            "the membership-matrix Dirichlet initialisation "
            "(supports_random_state=True).",
            "Hard cluster label is derived as argmax over the membership "
            "matrix; the membership matrix itself is the primary output and "
            "is preserved verbatim.",
            "FCM final objective J_m is recorded as algorithm-specific "
            "diagnostic only; model-selection comparison is OUT OF SCOPE "
            "for ML-06.",
            "The custom Bezdek FCM core has no external FCM dependency, so "
            "floating-point determinism holds within the same numpy version.",
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
        "per_fuzziness_diagnostic": [_summarize_one(s) for s in per_fuzziness_summaries],
        "artifacts": {
            "artifact_paths": dict(primary_result.artifact_paths),
        },
    }
    if primary_result.status == "FAILED":
        summary["primary_experiment"]["error"] = primary_result.error

    summary_path = report_dir / "ml06_run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=False, default=str),
        encoding="utf-8",
    )

    # ---- Build per-fuzziness diagnostic CSV ----
    csv_path = report_dir / "ml06_fuzziness_diagnostic.csv"
    rows = [_csv_row(primary, primary_label="primary")]
    for fuzz_summary in per_fuzziness_summaries:
        rows.append(
            _csv_row(
                fuzz_summary,
                primary_label=(f"diagnostic-m{fuzz_summary['hyperparameters']['m']:g}"),
            )
        )
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    # ---- Build EPIC-06 baseline configuration matrix CSV ----
    # The baseline matrix documents, for every algorithm in
    # ML-01 → ML-06, the family, working parameters, random-state
    # support, and output type. It is intentionally value-neutral:
    # no "best/winner/optimal" column by construction.
    from customer_segmentation.clustering import (  # noqa: E402 - local import
        AgglomerativeAdapter,
        DBSCANAdapter,
        FuzzyCMeansAdapter,
        GMMAdapter,
        KMeansAdapter,
    )

    working_hyperparameters: dict[str, dict] = {
        "kmeans": {
            "n_clusters": 4,
            "init": "k-means++",
            "n_init": 10,
            "max_iter": 300,
            "random_state": 42,
        },
        "agglomerative": {
            "n_clusters": 4,
            "linkage": "ward",
            "metric": "euclidean",
        },
        "dbscan": {
            "eps": 0.5,
            "min_samples": 5,
            "metric": "euclidean",
        },
        "gmm": {
            "n_components": 4,
            "covariance_type": "full",
            "init_params": "kmeans",
            "random_state": 42,
            "tol": 1e-3,
            "reg_covar": 1e-6,
            "max_iter": 100,
            "n_init": 1,
        },
        "fuzzy_cmeans": {
            "n_clusters": 4,
            "m": 2.0,
            "max_iter": 300,
            "error": 1e-4,
            "random_state": 42,
        },
    }
    family_label: dict[str, str] = {
        "kmeans": "hard",
        "agglomerative": "hard",
        "dbscan": "density_based",
        "gmm": "model_based",
        "fuzzy_cmeans": "fuzzy",
    }
    framework_module: dict[str, str] = {
        "kmeans": "ML-02 (sklearn.cluster.KMeans)",
        "agglomerative": "ML-03 (sklearn.cluster.AgglomerativeClustering)",
        "dbscan": "ML-04 (sklearn.cluster.DBSCAN)",
        "gmm": "ML-05 (sklearn.mixture.GaussianMixture)",
        "fuzzy_cmeans": "ML-06 (custom numpy-based Bezdek FCM core)",
    }
    soft_output: dict[str, str] = {
        "kmeans": "cluster_labels (hard)",
        "agglomerative": "cluster_labels (hard)",
        "dbscan": "cluster_labels (hard; preserves noise label -1)",
        "gmm": (
            "cluster_labels + soft_probabilities " "(posterior responsibilities, shape (n, K))"
        ),
        "fuzzy_cmeans": (
            "cluster_labels + soft_membership " "(fuzzy membership matrix, shape (n, c))"
        ),
    }
    random_state_policy: dict[str, str] = {
        "kmeans": "supported",
        "agglomerative": "not used (deterministic)",
        "dbscan": "not used (deterministic)",
        "gmm": "supported (EM initialisation)",
        "fuzzy_cmeans": "supported (membership-matrix initialisation)",
    }

    # Instantiate each adapter once to read the live
    # ``adapter_version`` (e.g. sklearn_<version>).
    baseline_rows: list[dict] = []
    for algo in (
        "kmeans",
        "agglomerative",
        "dbscan",
        "gmm",
        "fuzzy_cmeans",
    ):
        hp = working_hyperparameters[algo]
        # K-Means, Agglo, GMM, FCM are constructed directly;
        # DBSCAN takes eps + min_samples (already in hp).
        if algo == "kmeans":
            inst = KMeansAdapter(**hp)
        elif algo == "agglomerative":
            inst = AgglomerativeAdapter(**hp)
        elif algo == "dbscan":
            inst = DBSCANAdapter(**hp)
        elif algo == "gmm":
            inst = GMMAdapter(**hp)
        elif algo == "fuzzy_cmeans":
            inst = FuzzyCMeansAdapter(**hp)
        else:  # pragma: no cover - defensive
            continue
        hyper_str = "; ".join(f"{k}={v}" for k, v in sorted(hp.items()))
        baseline_rows.append(
            {
                "algorithm": algo,
                "framework_module": framework_module[algo],
                "algorithm_family": family_label[algo],
                "adapter_version": inst.version,
                "working_parameters": hyper_str,
                "random_state_policy": random_state_policy[algo],
                "supports_random_state": str(inst.supports_random_state()),
                "primary_output": soft_output[algo],
            }
        )
    baseline_csv_path = report_dir / "ml06_baseline_matrix.csv"
    pd.DataFrame(baseline_rows).to_csv(baseline_csv_path, index=False)

    # ---- Build Vietnamese narrative report (diagnostic only) ----
    status_vi = "THÀNH CÔNG" if primary_result.status == "SUCCESS" else "THẤT BẠI"
    extras = (
        primary_result.cluster_result.extra if primary_result.cluster_result is not None else {}
    )

    md_lines: list[str] = []
    md_lines.append("# ML-06 — Fuzzy C-Means (FCM) Initial Diagnostic Runs")
    md_lines.append("")
    md_lines.append("> **Tài liệu này là báo cáo vận hành (diagnostic report) cho")
    md_lines.append("> lần chạy Fuzzy C-Means đầu tiên trên Final Clustering Dataset của FE-06.**")
    md_lines.append("> Đây KHÔNG phải evaluation phase, KHÔNG so sánh thuật toán,")
    md_lines.append("> KHÔNG so sánh n_clusters / m / max_iter / error, KHÔNG chọn best c,")
    md_lines.append("> KHÔNG chọn best m, KHÔNG chọn best algorithm.")
    md_lines.append("> Working configuration là WORKING_ASSUMPTION, chưa được mentor")
    md_lines.append("> approve.")
    md_lines.append("")
    md_lines.append("## 1. Tổng quan")
    md_lines.append("")
    md_lines.append(f"- Trạng thái primary run: **{status_vi}**")
    md_lines.append(f"- Primary experiment ID: `{primary_experiment_id}`")
    md_lines.append(
        f"- Algorithm: `fuzzy_cmeans` (custom numpy-based Bezdek FCM core, "
        f"version `{primary_result.algorithm_version}`)"
    )
    md_lines.append("- Algorithm family: `fuzzy` (soft membership matrix + derived hard label)")
    md_lines.append(f"- Dataset version: `{cfg.input.dataset_version}`")
    md_lines.append(f"- Số customers: **{primary_result.n_samples}**")
    md_lines.append(f"- Số features: **{df.shape[1]}**")
    md_lines.append("")
    md_lines.append("## 2. Configuration (working defaults; WORKING_ASSUMPTION)")
    md_lines.append("")
    md_lines.append(
        f"- `n_clusters = {args.n_clusters}` (working default; WORKING_ASSUMPTION; cũng gọi là `c`)"
    )
    md_lines.append(f"- `m = {args.m}` (working default; WORKING_ASSUMPTION; fuzziness parameter)")
    md_lines.append(f"- `max_iter = {args.max_iter}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(f"- `error = {args.error}` (working default; WORKING_ASSUMPTION)")
    md_lines.append(
        f"- `random_state` requested = "
        f"`{args.seed if args.seed is not None else cfg.random_seed.default}`"
    )
    md_lines.append(
        f"- `random_state` used = `{primary_result.random_seed_used}` "
        f"(custom Bezdek FCM core consumes random_state for the "
        f"membership-matrix Dirichlet initialisation; supports_random_state=True)"
    )
    md_lines.append("")
    md_lines.append("## 3. Fuzzy C-Means theory recap (documentation)")
    md_lines.append("")
    md_lines.append(
        "- Mỗi observation `x_i` có một *membership degree* `u_ik ∈ [0, 1]` "
        "đối với mỗi fuzzy cluster `k`."
    )
    md_lines.append(
        "- Constraints: `Σ_{k=1..c} u_ik = 1` cho mỗi observation (row "
        "sum = 1); `u_ik ∈ [0, 1]`."
    )
    md_lines.append("- **Objective function**: `J_m(U, V) = Σ_i Σ_k (u_ik)^m · ||x_i - v_k||²`.")
    md_lines.append(
        "- **Fuzzy centroid**: `v_k = [Σ_i (u_ik)^m · x_i] / [Σ_i (u_ik)^m]` " "(weighted mean)."
    )
    md_lines.append(
        "- **Membership update** (canonical Bezdek form, Euclidean distance): "
        "`u_ik = 1 / Σ_j (d_ik / d_ij)^(2/(m-1))`. Exponent `p = 2/(m-1)` "
        "positive vì `m > 1`."
    )
    md_lines.append(
        "- **Iterative**: initialize U → compute V → compute distances → "
        "update U → check convergence → repeat."
    )
    md_lines.append(
        "- **Convergence criterion**: max-norm change của membership matrix "
        "|u_ik_new - u_ik_old| < `error`. (Final objective J_m được ghi nhận "
        "làm diagnostic, không dùng làm convergence trigger.)"
    )
    md_lines.append(
        "- **Hard label**: `label_i = argmax_k u_ik` (lossy projection của " "fuzzy membership)."
    )
    md_lines.append("")
    md_lines.append("## 4. Implementation")
    md_lines.append("")
    md_lines.append(
        "- Custom Bezdek FCM core trên numpy (không thêm dependency "
        "`scikit-fuzzy` vì AGENTS.md §5 cấm thêm dependency mới không qua "
        "ADR). Implementation deterministic dưới fixed `random_state`."
    )
    md_lines.append(
        "- Edge cases được xử lý: empty cluster (denominator floor), "
        "zero-distance observations (full membership cho cluster trùng), "
        "numerical clipping để row sum luôn ≈ 1, negative squared distance "
        "(clip về 0)."
    )
    md_lines.append("- `n_clusters <= n_samples` được enforce (giống sklearn K-Means).")
    md_lines.append("")
    md_lines.append("## 5. Kết quả primary run")
    md_lines.append("")
    n_clusters_text = (
        f"{primary_result.n_clusters}"
        if primary_result.n_clusters is not None
        else "(không xác định)"
    )
    md_lines.append(f"- Số clusters (hard label): **{n_clusters_text}**")
    md_lines.append(f"- Fuzziness m: **{extras.get('fuzziness')}**")
    md_lines.append(f"- max_iter: **{extras.get('max_iter')}**")
    md_lines.append(f"- error: **{extras.get('error')}**")
    md_lines.append(f"- converged: **{extras.get('converged')}**")
    md_lines.append(f"- n_iter: **{extras.get('n_iter')}**")
    final_obj = extras.get("final_objective")
    if isinstance(final_obj, (int, float)):
        md_lines.append(f"- final_objective J_m: **{final_obj:.6f}**")
    md_lines.append(f"- objective_history_length: **{extras.get('objective_history_length')}**")
    md_lines.append(f"- Execution time: **{primary_result.execution_time:.4f} s**")
    md_lines.append("")
    md_lines.append("### 5.1 Membership matrix integrity")
    md_lines.append("")
    md_lines.append(f"- centroid_shape: `{extras.get('centroid_shape')}`")
    md_lines.append(f"- membership_shape: `{extras.get('membership_shape')}`")
    md_lines.append(
        f"- membership min/max: **{extras.get('membership_min'):.6f}** / "
        f"**{extras.get('membership_max'):.6f}** (kỳ vọng trong `[0, 1]`)"
    )
    md_lines.append(
        f"- row-sum min/max: **{extras.get('membership_row_sum_min'):.12f}** / "
        f"**{extras.get('membership_row_sum_max'):.12f}** (kỳ vọng xấp xỉ 1.0)"
    )
    md_lines.append("")
    md_lines.append("### 5.2 Soft clustering (membership confidence summary)")
    md_lines.append("")
    md_lines.append(
        f"- per-row max-membership min/max/mean: "
        f"**{extras.get('membership_confidence_min'):.6f}** / "
        f"**{extras.get('membership_confidence_max'):.6f}** / "
        f"**{extras.get('membership_confidence_mean'):.6f}**"
    )
    md_lines.append(
        "- Higher mean → partition closer to hard (clear cluster "
        "boundaries); lower mean → partition closer to uniform 1/c "
        "(fuzzy boundary)."
    )
    md_lines.append("")
    md_lines.append("### 5.3 Cluster sizes từ hard label")
    md_lines.append("")
    cluster_sizes = extras.get("cluster_sizes", {})
    md_lines.append(f"- Cluster sizes: `{cluster_sizes}`")
    md_lines.append("")
    md_lines.append("## 6. Per-fuzziness diagnostic runs")
    md_lines.append("")
    md_lines.append(
        "Bốn initial diagnostic runs đã chạy với các giá trị `m` khác nhau "
        "(cùng `n_clusters`, `max_iter`, `error`). Đây KHÔNG phải controlled "
        "sweep — chỉ để verify adapter hỗ trợ đầy đủ các giá trị `m` đã "
        "quảng cáo và thu thập FCM-specific diagnostics."
    )
    md_lines.append("")
    md_lines.append(
        "| Label | m | Status | converged | n_iter | final_objective | "
        "row_sum_min | mean_confidence | Execution time (s) |"
    )
    md_lines.append(
        "|-------|--:|--------|-----------|-------:|---------------:|"
        "------------:|----------------:|-------------------:|"
    )
    if per_fuzziness_summaries:
        for s in per_fuzziness_summaries:
            r = s["result"]
            e = r.cluster_result.extra if r.cluster_result is not None else {}
            m_val = s["hyperparameters"]["m"]
            fo = e.get("final_objective")
            fo_s = f"{fo:.4f}" if isinstance(fo, (int, float)) else "n/a"
            rs_min = e.get("membership_row_sum_min")
            rs_min_s = f"{rs_min:.12f}" if isinstance(rs_min, (int, float)) else "n/a"
            conf_mean = e.get("membership_confidence_mean")
            conf_mean_s = f"{conf_mean:.6f}" if isinstance(conf_mean, (int, float)) else "n/a"
            md_lines.append(
                f"| diagnostic | {m_val:g} | {r.status} | {e.get('converged')} | "
                f"{e.get('n_iter')} | {fo_s} | {rs_min_s} | {conf_mean_s} | "
                f"{r.execution_time:.4f} |"
            )
    else:
        md_lines.append("| (skipped via --skip-fuzziness-diagnostic) | | | | | | | | |")
    md_lines.append("")
    md_lines.append(
        "Quan sát: cùng `random_state` và cùng input, các `m` khác nhau "
        "cho objective và confidence khác nhau (m lớn → partition mềm hơn "
        "→ confidence mean thấp hơn; m gần 1 → partition cứng hơn → "
        "confidence mean cao hơn). KHÔNG kết luận 'best m' trong tài liệu "
        "này — đó là EPIC-07 scope."
    )
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
    md_lines.append("### 8.2 Per-fuzziness diagnostic runs")
    md_lines.append("")
    for s in per_fuzziness_summaries:
        md_lines.append(f"- m `{s['hyperparameters']['m']:g}` — `{s['experiment_id']}`:")
        for name, path in s["result"].artifact_paths.items():
            md_lines.append(f"    - `{name}`: `{path}`")
    md_lines.append("")
    md_lines.append("## 9. Decision status")
    md_lines.append("")
    md_lines.append("- `TECHNICALLY_IMPLEMENTED`: FCM adapter và diagnostic runs đã chạy.")
    md_lines.append(
        "- `WORKING_ASSUMPTION`: `n_clusters = 4`, `m = 2.0`, `max_iter = 300`, " "`error = 1e-4`."
    )
    md_lines.append(
        "- `OUT_OF_SCOPE`: evaluation metric, algorithm comparison, "
        "(n_clusters, m, max_iter, error) sweep, model-selection "
        "comparison, segment profiling, research comparison viz."
    )
    md_lines.append("- `OUT_OF_SCOPE`: chọn `best n_clusters` / `best m` / " "`best algorithm`.")
    md_lines.append("")
    md_lines.append("## 10. Notes")
    md_lines.append("")
    md_lines.append(
        "- FCM consume `random_state` cho membership-matrix Dirichlet "
        "initialisation; `supports_random_state()` trả về `True`. "
        "Framework runner pass seed vào adapter."
    )
    md_lines.append(
        "- Soft clustering output được bảo toàn: "
        "`cluster_labels_{experiment_id}.parquet` chứa `Membership_k` "
        "columns cho mỗi cluster; `algorithm_output_{experiment_id}.parquet` "
        "chứa ma trận membership đầy đủ cho downstream consumers."
    )
    md_lines.append(
        "- Hard label = `argmax` của membership matrix. Adapter ghi nhận "
        "cả hard label và full soft membership matrix."
    )
    md_lines.append(
        "- `final_objective` (J_m), `converged`, `n_iter`, "
        "membership confidence summary được ghi nhận trong "
        "`cluster_result.extra` là **diagnostics only**. Không dùng để "
        "tuyên bố một configuration là 'best'."
    )
    md_lines.append(
        "- Per-fuzziness diagnostics KHÔNG được dùng để kết luận " "'best m' — đó là EPIC-07 scope."
    )
    md_lines.append(
        "- Reproducibility: cùng input + config + random_state + library "
        "version → membership matrix / centroids / final objective / "
        "converged / n_iter giống nhau. Raw label equality KHÔNG được "
        "dùng làm reproducibility check vì cluster permutation có thể xảy "
        "ra giữa các lần chạy (cùng seed nhưng FCM partition có thể khác)."
    )
    md_lines.append(
        '- KHÔNG kết luận "best n_clusters", "best m", "best algorithm" ' "trong tài liệu này."
    )
    md_lines.append("")
    md_lines.append(
        f"_Báo cáo này được sinh tự động từ execution thực tế. SHA-256 và "
        f"execution_time lấy trực tiếp từ "
        f"`experiment_log_{primary_experiment_id}.json`._"
    )

    narrative_path = report_dir / "ml06_initial_diagnostic.md"
    narrative_path.write_text("\n".join(md_lines), encoding="utf-8")

    # ---- Print summary to stdout ----
    print(f"[ML-06] primary status:    {primary_result.status}")
    print(f"[ML-06] primary n_clusters: {primary_result.n_clusters}")
    if primary_result.cluster_result is not None:
        e = primary_result.cluster_result.extra
        print(
            f"[ML-06] m={e.get('fuzziness')}, "
            f"converged={e.get('converged')}, "
            f"n_iter={e.get('n_iter')}, "
            f"final_objective={e.get('final_objective'):.4f}"
        )
    print(f"[ML-06] primary exec time: {primary_result.execution_time:.4f} s")
    print(f"[ML-06] per-fuzziness runs: {len(per_fuzziness_summaries)}")
    for s in per_fuzziness_summaries:
        r = s["result"]
        e = r.cluster_result.extra if r.cluster_result is not None else {}
        fo = e.get("final_objective")
        fo_s = f"{fo:.4f}" if isinstance(fo, (int, float)) else "n/a"
        print(
            f"[ML-06]   m={s['hyperparameters']['m']:g}: status={r.status}, "
            f"converged={e.get('converged')}, "
            f"final_objective={fo_s}, "
            f"exec={r.execution_time:.4f}s"
        )
    print(f"[ML-06] summary written:   {summary_path}")
    print(f"[ML-06] narrative written: {narrative_path}")
    print(f"[ML-06] csv written:       {csv_path}")
    print(f"[ML-06] baseline matrix:   {baseline_csv_path}")
    print(f"[ML-06] artifacts dir:     {artifacts_dir}")


if __name__ == "__main__":
    main()
