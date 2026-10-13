"""CLI for DEV-05 Prototype Evaluation.

Usage
-----

.. code-block:: bash

    python scripts/dev05_evaluate_clustering.py \\
        --dataset-id <ds_id> \\
        --preprocessed-id <pp_id> \\
        --clustering-id <cl_xxx> \\
        [--config configs/dev05_evaluation.yaml] \\
        [--noise-policy include|exclude] \\
        [--metrics silhouette,davies_bouldin,calinski_harabasz] \\
        [--force-recompute] \\
        [--compare <ev_xx> <ev_yy> ...]

In compute mode (default), the CLI runs the evaluation pipeline and
prints the metric table to stdout.

In ``--compare`` mode, the CLI loads existing evaluation manifests and
prints a side-by-side comparison (with compatibility check).

The CLI is **research-scope** strict: it never reads
``data/processed/final_clustering_dataset.parquet`` and never writes
to ``data/raw``, ``data/processed``, or ``reports``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from customer_segmentation.prototype.evaluation import (
    DEFAULT_DEV05_CONFIG_PATH,
    load_dev05_config,
)
from customer_segmentation.prototype.evaluation.compare import (
    DEFAULT_COMPARISON_DISCLAIMER,
    compare_evaluations,
)
from customer_segmentation.prototype.evaluation.display import (
    format_metrics_table,
    format_manifest_path,
)
from customer_segmentation.prototype.evaluation.pipeline import (
    run_evaluation_pipeline,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev05_evaluate_clustering",
        description=(
            "DEV-05 Prototype Evaluation. Compute / display / compare "
            "3 internal metrics (silhouette, DBI, CH) on a DEV-04 "
            "clustering run. NO ranking, NO recommendation, NO winner "
            "annotation is emitted (R-EVAL-08)."
        ),
    )
    parser.add_argument(
        "--dataset-id",
        type=str,
        default=None,
        help="DEV-02 dataset id (e.g. ds_xxx).",
    )
    parser.add_argument(
        "--preprocessed-id",
        type=str,
        default=None,
        help="DEV-03 preprocessed id (e.g. pp_xxx).",
    )
    parser.add_argument(
        "--clustering-id",
        type=str,
        default=None,
        help="DEV-04 clustering id (e.g. cl_<24-hex>).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_DEV05_CONFIG_PATH,
        help="Path to dev05_evaluation.yaml.",
    )
    parser.add_argument(
        "--noise-policy",
        type=str,
        choices=("include", "exclude"),
        default=None,
        help="Override noise_policy (default from config).",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        default=None,
        help=(
            "Comma-separated metric names to compute. "
            "Default = all 3 (silhouette,davies_bouldin,calinski_harabasz)."
        ),
    )
    parser.add_argument(
        "--force-recompute",
        action="store_true",
        help="Recompute even if a cached evaluation exists.",
    )
    parser.add_argument(
        "--compare",
        nargs="+",
        type=str,
        default=None,
        metavar="EVALUATION_ID",
        help=(
            "Compare mode: list of evaluation_manifest.json paths or "
            "evaluation_ids. If evaluation_ids, they are resolved under "
            "the canonical storage root."
        ),
    )
    return parser


def _parse_metric_set(metrics_arg: str | None) -> list[str] | None:
    if metrics_arg is None:
        return None
    return [m.strip() for m in metrics_arg.split(",") if m.strip()]


def _resolve_compare_paths(
    items: list[str], *, dataset_id: str, preprocessed_id: str, clustering_id: str,
) -> list[Path]:
    """Resolve evaluation ids to manifest paths under the storage root."""
    from customer_segmentation.prototype.evaluation.storage import (
        prototype_evaluation_base_dir,
        resolve_storage_root,
    )
    storage_root = resolve_storage_root()
    base_dir = prototype_evaluation_base_dir(
        storage_root, dataset_id, preprocessed_id, clustering_id
    )
    paths: list[Path] = []
    for item in items:
        p = Path(item)
        if p.exists() and p.is_file():
            paths.append(p)
            continue
        # Treat as evaluation_id under the base_dir.
        candidate = base_dir / item / "evaluation_manifest.json"
        if not candidate.exists():
            raise FileNotFoundError(
                f"Could not find evaluation manifest for {item!r} "
                f"(looked at {p} and {candidate})."
            )
        paths.append(candidate)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.compare is not None:
        # Compare mode.
        if not (args.dataset_id and args.preprocessed_id and args.clustering_id):
            print(
                "ERROR: --compare requires --dataset-id, "
                "--preprocessed-id, --clustering-id to resolve ids.",
                file=sys.stderr,
            )
            return 2
        try:
            paths = _resolve_compare_paths(
                args.compare,
                dataset_id=args.dataset_id,
                preprocessed_id=args.preprocessed_id,
                clustering_id=args.clustering_id,
            )
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        report = compare_evaluations(paths)
        # Render.
        out = report.to_dict()
        print(json.dumps(out, indent=2, default=str))
        print()
        print(DEFAULT_COMPARISON_DISCLAIMER)
        return 0

    # Compute mode.
    if not (args.dataset_id and args.preprocessed_id and args.clustering_id):
        print(
            "ERROR: --dataset-id, --preprocessed-id, --clustering-id are required "
            "for compute mode.",
            file=sys.stderr,
        )
        return 2
    try:
        config, _ = load_dev05_config(args.config)
    except Exception as exc:
        print(f"ERROR: failed to load config: {exc}", file=sys.stderr)
        return 2
    metric_set = _parse_metric_set(args.metrics)
    try:
        result = run_evaluation_pipeline(
            dataset_id=args.dataset_id,
            preprocessed_id=args.preprocessed_id,
            clustering_id=args.clustering_id,
            config=config,
            config_path=args.config,
            noise_policy=args.noise_policy,
            metric_set=metric_set,
            force_recompute=args.force_recompute,
        )
    except Exception as exc:
        print(f"ERROR: pipeline failed: {exc}", file=sys.stderr)
        return 2

    # Display.
    print(f"Clustering : {result.manifest.clustering_id}")
    print(
        f"Algorithm  : {result.manifest.algorithm} "
        f"(family={result.manifest.algorithm_family})"
    )
    print(
        f"Samples    : {result.manifest.n_samples_input}  "
        f"used_for_compute={result.manifest.n_samples_used_for_compute}"
    )
    if result.manifest.algorithm_family == "density_based":
        print(
            f"Noise      : {result.manifest.noise_count}  "
            f"(ratio={result.manifest.noise_ratio})"
        )
    print(f"Metrics    : {result.manifest.metric_set}")
    print()
    print(format_metrics_table(result.manifest.metrics))
    print()
    print(format_manifest_path(result.manifest))
    print(f"Lifecycle  : {result.lifecycle}  (duration: {result.duration_seconds:.3f}s)")
    if result.csv_path is not None:
        print(f"CSV        : {result.csv_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
