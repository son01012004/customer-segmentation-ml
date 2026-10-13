"""DEV-04 orchestrator: run one prototype clustering experiment.

Stage: 06_clustering / DEV-04 (Prototype Clustering Execution)

This script runs a **single, value-neutral clustering experiment** on
the DEV-03 ML Dataset via the ML-01 Experiment Framework wrapped by
the DEV-04 prototype layer. It mirrors the patterns of
``scripts/run_ml02_kmeans.py`` etc. but:

- reads the DEV-04 YAML config (``configs/dev04_clustering.yaml``),
- consumes a DEV-03 preprocessed id instead of the FE-06 final matrix,
- writes a DEV-04 prototype manifest alongside ML-01 artefacts,
- supports all 5 algorithms in one CLI,
- never invents or picks a "best" algorithm.

Usage (from the repository root)::

    python -m scripts.dev04_run_clustering \
        --dataset-id ds_ba54033e45525bf5123c2d9d \
        --preprocessed-id pp_abc123... \
        --algorithm kmeans

    python -m scripts.dev04_run_clustering \
        --dataset-id ds_ba54033e45525bf5123c2d9d \
        --preprocessed-id pp_abc123... \
        --algorithm gmm \
        --n-components 5 \
        --seed 123

Outputs
-------

Written under
``<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/clustering/<clustering_id>/``:

- ``clustering_manifest.json``  (DEV-04 prototype manifest)
- ``cluster_labels_<experiment_id>.parquet``
- ``experiment_log_<experiment_id>.json``  (ML-01 payload)
- ``algorithm_output_<experiment_id>.parquet``  (GMM/FCM soft output only)
- ``<clustering_id>.log``  (per-stage log)

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No algorithm comparison.
- No K sweep.
- No segment profiling / naming.
- No "best / optimal / recommended" claim.
- DEV-02/DEV-03/FE-06 outputs are READ-ONLY.
- Reproducibility metadata (SHA, seed, library versions) is recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev04_run_clustering",
        description=(
            "DEV-04 Prototype Clustering Execution: run a single experiment "
            "on a DEV-03 preprocessed ML Dataset. Writes to "
            "<storage_root>/datasets/<dataset_id>/preprocessed/<preprocessed_id>/"
            "clustering/<clustering_id>/."
        ),
    )
    # --- Required ---
    parser.add_argument(
        "--dataset-id",
        type=str,
        required=True,
        help="DEV-02 dataset id (e.g. ds_ba54033e45525bf5123c2d9d).",
    )
    parser.add_argument(
        "--preprocessed-id",
        type=str,
        required=True,
        help="DEV-03 preprocessed id (e.g. pp_abc123...).",
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        required=True,
        choices=["kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"],
        help="Clustering algorithm. One of 5 supported (kmeans, agglomerative, "
        "dbscan, gmm, fuzzy_cmeans).",
    )

    # --- Optional (config + flags) ---
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to the DEV-04 YAML. If omitted, auto-discovers "
        "'configs/dev04_clustering.yaml'.",
    )
    parser.add_argument(
        "--dev02-config",
        type=Path,
        default=None,
        help="Path to the DEV-02 dataset-management config YAML. "
        "Required when the dataset was imported with a non-default "
        "--config (i.e. the storage root differs from the canonical one).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (overrides config default for stochastic algorithms).",
    )
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Experiment identifier. If omitted, derived from algorithm + clustering_id.",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Re-run even if a clustering with the same clustering_id already exists.",
    )

    # --- Per-algorithm hyperparameter overrides (K-Means / Agglomerative) ---
    parser.add_argument(
        "--n-clusters",
        type=int,
        default=None,
        help="Number of clusters (K-Means, Agglomerative, Fuzzy C-Means).",
    )
    parser.add_argument(
        "--init",
        type=str,
        default=None,
        choices=["k-means++", "random"],
        help="K-Means init.",
    )
    parser.add_argument(
        "--n-init",
        type=int,
        default=None,
        help="K-Means n_init.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=None,
        help="K-Means max_iter.",
    )
    parser.add_argument(
        "--tol",
        type=float,
        default=None,
        help="K-Means tol.",
    )

    # --- Agglomerative ---
    parser.add_argument(
        "--linkage",
        type=str,
        default=None,
        choices=["ward", "complete", "average", "single"],
        help="Agglomerative linkage.",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default=None,
        help="Agglomerative / DBSCAN distance metric.",
    )

    # --- DBSCAN ---
    parser.add_argument(
        "--eps",
        type=float,
        default=None,
        help="DBSCAN eps.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=None,
        help="DBSCAN min_samples.",
    )

    # --- GMM ---
    parser.add_argument(
        "--n-components",
        type=int,
        default=None,
        help="GMM n_components.",
    )
    parser.add_argument(
        "--covariance-type",
        type=str,
        default=None,
        choices=["full", "tied", "diag", "spherical"],
        help="GMM covariance_type.",
    )

    # --- Fuzzy C-Means ---
    parser.add_argument(
        "--fuzziness",
        type=float,
        default=None,
        help="Fuzzy C-Means fuzziness (m).",
    )
    parser.add_argument(
        "--error",
        type=float,
        default=None,
        help="Fuzzy C-Means convergence error.",
    )

    return parser


def _collect_hyperparameters(args: argparse.Namespace) -> dict:
    """Collect non-None hyperparameter overrides from CLI flags."""
    keys = [
        "n_clusters",
        "init",
        "n_init",
        "max_iter",
        "tol",
        "linkage",
        "metric",
        "eps",
        "min_samples",
        "n_components",
        "covariance_type",
        "fuzziness",
        "error",
    ]
    out: dict = {}
    for k in keys:
        v = getattr(args, k, None)
        if v is not None:
            out[k] = v
    return out


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)

    # Lazy import (after sys.path setup).
    from customer_segmentation.prototype.clustering import (
        run_clustering_pipeline,
    )

    hyperparameters = _collect_hyperparameters(args)

    print(f"[DEV-04] dataset_id:        {args.dataset_id}")
    print(f"[DEV-04] preprocessed_id:   {args.preprocessed_id}")
    print(f"[DEV-04] algorithm:         {args.algorithm}")
    print(f"[DEV-04] config:            {args.config or '<default>'}")
    print(f"[DEV-04] seed:              {args.seed}")
    print(f"[DEV-04] force_rerun:       {args.force_rerun}")
    if hyperparameters:
        print(f"[DEV-04] hyperparameter overrides: {hyperparameters}")

    result = run_clustering_pipeline(
        dataset_id=args.dataset_id,
        preprocessed_id=args.preprocessed_id,
        algorithm=args.algorithm,
        config_path=args.config,
        dev02_config_path=args.dev02_config,
        hyperparameters=hyperparameters,
        seed=args.seed,
        experiment_id=args.experiment_id,
        force_rerun=args.force_rerun,
    )

    summary = result.as_summary()
    print("[DEV-04] === Result ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))

    print(f"[DEV-04] lifecycle:         {result.lifecycle}")
    print(f"[DEV-04] clustering_id:     {result.clustering_id}")
    print(f"[DEV-04] manifest:          {result.manifest_path}")
    print(f"[DEV-04] cluster_labels:    {result.cluster_labels_path}")
    print(f"[DEV-04] algorithm_output:  {result.algorithm_output_path}")
    print(f"[DEV-04] log:               {result.log_path}")


if __name__ == "__main__":
    main()
