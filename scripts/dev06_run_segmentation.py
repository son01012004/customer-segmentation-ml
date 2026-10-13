"""CLI for DEV-06 Prototype Segmentation.

Usage
-----

.. code-block:: bash

    # Compute mode (Stage A → H):
    PYTHONPATH=src python3 scripts/dev06_run_segmentation.py profile \\
        --dataset-id <ds_id> \\
        --preprocessed-id <pp_id> \\
        --clustering-id <cl_xxx> \\
        [--config configs/dev06_segmentation.yaml] \\
        [--noise-policy include|exclude] \\
        [--evaluation-id <ev_xxx>] \\
        [--force-rerun]

    # Display mode (read existing segmentation manifest):
    PYTHONPATH=src python3 scripts/dev06_run_segmentation.py list \\
        --segmentation-manifest <path-to-segmentation_manifest.json>
    PYTHONPATH=src python3 scripts/dev06_run_segmentation.py sizes \\
        --segmentation-manifest <path>
    PYTHONPATH=src python3 scripts/dev06_run_segmentation.py profiles \\
        --segmentation-manifest <path> [--segment-id <id>]
    PYTHONPATH=src python3 scripts/dev06_run_segmentation.py characteristics \\
        --segmentation-manifest <path> [--segment-id <id>]

    # Compare mode:
    PYTHONPATH=src python3 scripts/dev06_run_segmentation.py compare \\
        --segmentation-manifest <path1> [<path2> ...]

The CLI is **research-scope** strict: it never reads
``data/processed/final_clustering_dataset.parquet`` and never writes
to ``data/raw``, ``data/processed``, or ``reports``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from customer_segmentation.prototype.segmentation import (
    DEFAULT_DEV06_CONFIG_PATH,
    load_dev06_config,
)
from customer_segmentation.prototype.segmentation.compare import (
    DEFAULT_COMPARISON_DISCLAIMER,
    compare_segmentations,
)
from customer_segmentation.prototype.segmentation.display import (
    DEFAULT_DISCLAIMER_TEXT,
    format_characteristics_table,
    format_comparison_table,
    format_manifest_path,
    format_profiles_table,
    format_segments_table,
    format_sizes_table,
)
from customer_segmentation.prototype.segmentation.manifest import (
    read_segmentation_manifest,
)
from customer_segmentation.prototype.segmentation.pipeline import (
    run_segmentation_pipeline,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev06_run_segmentation",
        description=(
            "DEV-06 Prototype Segmentation. Compute / display / compare "
            "descriptive segments, sizes, percentages, profiles, and "
            "characteristics for a DEV-04 clustering run. NO ranking, "
            "NO recommendation, NO winner annotation is emitted "
            "(R-DEV-06-08 / R-DEV-06-18 / R-DEV-06-19)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    # profile (compute).
    p_profile = sub.add_parser(
        "profile",
        help="Run the segmentation pipeline (compute).",
    )
    p_profile.add_argument("--dataset-id", type=str, required=True)
    p_profile.add_argument("--preprocessed-id", type=str, required=True)
    p_profile.add_argument("--clustering-id", type=str, required=True)
    p_profile.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_DEV06_CONFIG_PATH,
        help="Path to dev06_segmentation.yaml.",
    )
    p_profile.add_argument(
        "--noise-policy",
        type=str,
        choices=("include", "exclude"),
        default=None,
        help="Override noise_policy (default from config).",
    )
    p_profile.add_argument(
        "--evaluation-id",
        type=str,
        default=None,
        help=(
            "Optional DEV-05 evaluation id; cross-checked against the "
            "DEV-04 clustering manifest (optional L5 input)."
        ),
    )
    p_profile.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore cached segmentation and recompute.",
    )
    # list.
    p_list = sub.add_parser(
        "list",
        help="Display segment list (id, size, percentage).",
    )
    p_list.add_argument(
        "--segmentation-manifest",
        type=Path,
        required=True,
    )
    # sizes.
    p_sizes = sub.add_parser(
        "sizes",
        help="Display segment size (non-noise).",
    )
    p_sizes.add_argument(
        "--segmentation-manifest",
        type=Path,
        required=True,
    )
    # profiles.
    p_profiles = sub.add_parser(
        "profiles",
        help="Display per-segment feature profiles.",
    )
    p_profiles.add_argument(
        "--segmentation-manifest",
        type=Path,
        required=True,
    )
    p_profiles.add_argument(
        "--segment-id",
        type=int,
        default=None,
        help="If set, show only this segment.",
    )
    # characteristics.
    p_chars = sub.add_parser(
        "characteristics",
        help="Display per-segment characteristics.",
    )
    p_chars.add_argument(
        "--segmentation-manifest",
        type=Path,
        required=True,
    )
    # compare.
    p_compare = sub.add_parser(
        "compare",
        help="Compare multiple segmentation manifests.",
    )
    p_compare.add_argument(
        "--segmentation-manifest",
        nargs="+",
        type=Path,
        required=True,
    )
    return parser


def _resolve_evaluation_path(
    evaluation_id: str,
    *,
    dataset_id: str,
    preprocessed_id: str,
    clustering_id: str,
) -> Path:
    """Resolve an evaluation id to its manifest path under storage root."""
    from customer_segmentation.prototype.segmentation.storage import (
        prototype_segmentation_base_dir,
        resolve_storage_root,
    )

    storage_root = resolve_storage_root()
    base_dir = prototype_segmentation_base_dir(
        storage_root, dataset_id, preprocessed_id, clustering_id
    )
    # DEV-05 evaluation lives under the same clustering dir but at
    # evaluation/<ev_id>/evaluation_manifest.json (not under segmentation/).
    cl_base = base_dir.parent
    candidate = cl_base / "evaluation" / evaluation_id / "evaluation_manifest.json"
    if not candidate.exists():
        raise FileNotFoundError(
            f"Could not find evaluation manifest for {evaluation_id!r} " f"(looked at {candidate})."
        )
    return candidate


def _cmd_profile(args: argparse.Namespace) -> int:
    try:
        config, _ = load_dev06_config(args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load config: {exc}", file=sys.stderr)
        return 2
    ev_path: Path | None = None
    if args.evaluation_id is not None:
        try:
            ev_path = _resolve_evaluation_path(
                args.evaluation_id,
                dataset_id=args.dataset_id,
                preprocessed_id=args.preprocessed_id,
                clustering_id=args.clustering_id,
            )
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    try:
        result = run_segmentation_pipeline(
            dataset_id=args.dataset_id,
            preprocessed_id=args.preprocessed_id,
            clustering_id=args.clustering_id,
            config=config,
            config_path=args.config,
            noise_policy=args.noise_policy,
            evaluation_manifest_path=ev_path,
            force_rerun=args.force_rerun,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: pipeline failed: {exc}", file=sys.stderr)
        return 2
    # Display.
    print(f"Segmentation: {result.segmentation_id}")
    print(f"Clustering : {result.manifest.clustering_id}")
    print(
        f"Algorithm  : {result.manifest.algorithm} " f"(family={result.manifest.algorithm_family})"
    )
    print(
        f"Samples    : {result.manifest.n_samples_input}  "
        f"used_for_compute={result.manifest.n_samples_used_for_compute}"
    )
    if result.manifest.algorithm_family == "density_based":
        print(
            f"Noise      : {result.manifest.noise_count}  " f"(ratio={result.manifest.noise_ratio})"
        )
    print(f"Segments   : {result.manifest.n_segments}")
    print()
    print(format_segments_table(result.manifest))
    print()
    print(DEFAULT_DISCLAIMER_TEXT)
    print(f"Lifecycle  : {result.lifecycle}  (duration: {result.duration_seconds:.3f}s)")
    print(f"Manifest   : {result.manifest_path}")
    return 0


def _cmd_display(args: argparse.Namespace) -> int:
    try:
        manifest = read_segmentation_manifest(args.segmentation_manifest)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to read manifest: {exc}", file=sys.stderr)
        return 2
    print(format_manifest_path(manifest))
    print()
    cmd = args.command
    if cmd == "list":
        print(format_segments_table(manifest))
    elif cmd == "sizes":
        print(format_sizes_table(manifest.segment_sizes))
    elif cmd == "profiles":
        print(format_profiles_table(manifest.profiles, segment_id=args.segment_id))
    elif cmd == "characteristics":
        # Filter characteristics whose id has a segment prefix.
        # Characteristic ids do not carry segment_id (descriptive only).
        print(format_characteristics_table(manifest.characteristics))
    print()
    print(DEFAULT_DISCLAIMER_TEXT)
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    paths: list[Path] = []
    for p in args.segmentation_manifest:
        path = Path(p)
        if not path.exists():
            print(f"ERROR: manifest not found: {path}", file=sys.stderr)
            return 2
        paths.append(path)
    try:
        report = compare_segmentations(paths)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: comparison failed: {exc}", file=sys.stderr)
        return 2
    out = report.to_dict()
    print(json.dumps(out, indent=2, default=str))
    print()
    print(format_comparison_table(report))
    print()
    print(DEFAULT_COMPARISON_DISCLAIMER)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "profile":
        return _cmd_profile(args)
    if args.command in ("list", "sizes", "profiles", "characteristics"):
        return _cmd_display(args)
    if args.command == "compare":
        return _cmd_compare(args)
    print(f"ERROR: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
