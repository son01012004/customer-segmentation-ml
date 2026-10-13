"""CLI entry point for DEV-09 End-to-End Prototype Integration.

Mirrors the DEV-07 / DEV-08 CLI shape.

Subcommands
-----------
- ``run`` — run the full end-to-end pipeline once: UPLOAD → VALIDATION
  → PREPROCESSING → FEATURE_ENGINEERING → ALGORITHM_SELECT →
  CLUSTERING → EVALUATION → SEGMENTATION → CUSTOMER_PROFILE →
  MARKETING → VISUALIZATION. Persists an ``e2e_run.json`` summary.
- ``show`` — re-display an existing ``e2e_run.json`` summary.
- ``list`` — list existing e2e runs under the storage root.

Examples
--------
::

    # Run from a CSV file (default: configs/dev09_end_to_end.yaml).
    python scripts/dev09_run_pipeline.py run \\
        --source-file data/synthetic/customers_small.csv

    # Override algorithm.
    python scripts/dev09_run_pipeline.py run \\
        --source-file data/synthetic/customers_small.csv \\
        --algorithm agglomerative --seed 42

    # Reuse an existing DEV-02 dataset.
    python scripts/dev09_run_pipeline.py run \\
        --dataset-id ds_ba54033e45525bf5123c2d9d \\
        --algorithm kmeans

    # Custom output directory and config.
    python scripts/dev09_run_pipeline.py run \\
        --source-file data/synthetic/customers_small.csv \\
        --output-dir /tmp/e2e_run \\
        --config configs/dev09_end_to_end.yaml

    # Show an existing summary.
    python scripts/dev09_run_pipeline.py show \\
        --e2e-run /path/to/e2e_run.json

    # List existing runs.
    python scripts/dev09_run_pipeline.py list
    python scripts/dev09_run_pipeline.py list --dataset-id ds_xxxxxxxxx
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from customer_segmentation.prototype.end_to_end.config_loader import (
    DEFAULT_DEV09_CONFIG_PATH,
)
from customer_segmentation.prototype.end_to_end.exceptions import (
    Dev09ConfigError,
    Dev09Error,
    Dev09InputError,
    Dev09StoragePathError,
)
from customer_segmentation.prototype.end_to_end.logging_config import (
    configure_logging,
    finalize_logging,
)
from customer_segmentation.prototype.end_to_end.pipeline import (
    E2E_FAILED,
    E2E_SUCCESS,
    run_end_to_end_pipeline,
)
from customer_segmentation.prototype.end_to_end.show import (
    format_run_summary,
    load_run_summary,
)
from customer_segmentation.prototype.end_to_end.storage import (
    list_e2e_runs,
    resolve_storage_root,
)

__all__ = [
    "build_parser",
    "main",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the DEV-09 CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="dev09-end-to-end",
        description=(
            "DEV-09 End-to-End Prototype Integration. Orchestrates "
            "DEV-02..08 prototype pipelines and writes an e2e_run.json "
            "summary. Marketing review-required and blocked "
            "visualization states are preserved verbatim. See "
            "docs/system/DEV-09_*.md."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        type=Path,
        default=None,
        help=("Path to DEV-09 config YAML " f"(default: {DEFAULT_DEV09_CONFIG_PATH})."),
    )

    p_run = subparsers.add_parser(
        "run",
        parents=[common],
        help=("Run the full DEV-02..08 pipeline once and persist the " "e2e_run.json summary."),
    )
    src_vs_id = p_run.add_mutually_exclusive_group(required=True)
    src_vs_id.add_argument(
        "--source-file",
        type=Path,
        default=None,
        help="Path to a CSV/Parquet source file to import.",
    )
    src_vs_id.add_argument(
        "--dataset-id",
        type=str,
        default=None,
        help=(
            "Reuse an existing DEV-02 dataset by id " "(skips the UPLOAD stage; lifecycle=CACHED)."
        ),
    )
    p_run.add_argument(
        "--name",
        type=str,
        default=None,
        help="Display name override forwarded to DEV-02.",
    )
    p_run.add_argument(
        "--allow-external-source",
        action="store_true",
        help=(
            "Forwarded to DEV-02 to permit sources outside the "
            "repository (default: from config)."
        ),
    )
    p_run.add_argument(
        "--algorithm",
        type=str,
        default=None,
        choices=["kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"],
        help="Clustering algorithm (closed set; default: from config).",
    )
    p_run.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed override (forwarded to DEV-04).",
    )
    p_run.add_argument(
        "--skip-marketing",
        action="store_true",
        help="Skip the marketing stage entirely.",
    )
    p_run.add_argument(
        "--no-skip-marketing",
        action="store_true",
        help=(
            "Re-enable the marketing stage if it was disabled by the "
            "config (mirrors --skip-marketing)."
        ),
    )
    p_run.add_argument(
        "--skip-visualization",
        action="store_true",
        help="Skip the visualization stage entirely.",
    )
    p_run.add_argument(
        "--no-skip-visualization",
        action="store_true",
        help=(
            "Re-enable the visualization stage if it was disabled by "
            "the config (mirrors --skip-visualization)."
        ),
    )
    p_run.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory to write the e2e summary into. When omitted, "
            "the canonical per-dataset directory under the storage root "
            "is used."
        ),
    )
    p_run.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Directory for the per-stage log file (default: no file log).",
    )

    p_show = subparsers.add_parser(
        "show",
        parents=[common],
        help="Re-display an existing e2e_run.json summary.",
    )
    p_show.add_argument(
        "--e2e-run",
        type=Path,
        required=True,
        help="Path to an e2e_run.json file.",
    )

    p_list = subparsers.add_parser(
        "list",
        parents=[common],
        help="List existing e2e runs under the storage root.",
    )
    p_list.add_argument(
        "--dataset-id",
        type=str,
        default=None,
        help="Restrict listing to a specific dataset_id.",
    )
    p_list.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of text.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = configure_logging(
        level="INFO",
        log_file=None,
        emit_to_console=True,
    )
    try:
        if args.subcommand == "run":
            return _cmd_run(args, logger)
        if args.subcommand == "show":
            return _cmd_show(args, logger)
        if args.subcommand == "list":
            return _cmd_list(args, logger)
        parser.print_help()
        return 2
    except Dev09InputError as exc:
        logger.error("DEV-09 input error: %s", exc)
        return 2
    except Dev09ConfigError as exc:
        logger.error("DEV-09 config error: %s", exc)
        return 3
    except Dev09StoragePathError as exc:
        logger.error("DEV-09 storage error: %s", exc)
        return 4
    except Dev09Error as exc:
        logger.error("DEV-09 error: %s", exc)
        return 1
    finally:
        finalize_logging(logger)


def _resolve_skip_flag(skip_arg: bool, no_skip_arg: bool, default: bool) -> bool:
    """Reconcile mutually exclusive skip / no-skip flags against a config default."""
    if skip_arg and no_skip_arg:
        raise Dev09InputError("Cannot pass --skip-X and --no-skip-X simultaneously.")
    if skip_arg:
        return True
    if no_skip_arg:
        return False
    return default


def _cmd_run(args: argparse.Namespace, logger) -> int:
    source_file = getattr(args, "source_file", None)
    dataset_id = getattr(args, "dataset_id", None)
    name = getattr(args, "name", None)
    allow_external_source = bool(getattr(args, "allow_external_source", False))
    algorithm = getattr(args, "algorithm", None)
    seed = getattr(args, "seed", None)
    skip_marketing_arg = bool(getattr(args, "skip_marketing", False))
    no_skip_marketing_arg = bool(getattr(args, "no_skip_marketing", False))
    skip_visualization_arg = bool(getattr(args, "skip_visualization", False))
    no_skip_visualization_arg = bool(getattr(args, "no_skip_visualization", False))
    output_dir = getattr(args, "output_dir", None)
    log_dir = getattr(args, "log_dir", None)
    config_path = getattr(args, "config", None)

    # Load config to obtain defaults for skip flags.
    from customer_segmentation.prototype.end_to_end.config_loader import (
        load_dev09_config,
    )

    cfg = load_dev09_config(config_path)
    skip_marketing = _resolve_skip_flag(
        skip_marketing_arg, no_skip_marketing_arg, cfg.stage_selection.skip_marketing
    )
    skip_visualization = _resolve_skip_flag(
        skip_visualization_arg,
        no_skip_visualization_arg,
        cfg.stage_selection.skip_visualization,
    )

    summary = run_end_to_end_pipeline(
        source_file=source_file,
        algorithm=algorithm,
        seed=seed,
        dataset_id=dataset_id,
        name=name,
        allow_external_source=allow_external_source,
        config_path=config_path,
        output_dir=output_dir,
        skip_marketing=skip_marketing,
        skip_visualization=skip_visualization,
        log_dir=log_dir,
    )

    print(format_run_summary(summary))
    print()
    print(f"Wrote: {summary.run_dir}")
    print(f"e2e_run.json: {Path(summary.run_dir) / 'e2e_run.json'}")
    if summary.overall_status == E2E_SUCCESS:
        return 0
    if summary.overall_status == E2E_FAILED:
        return 1
    # CONDITIONAL/CACHED/BLOCKED: exit 0 to allow further inspection.
    return 0


def _cmd_show(args: argparse.Namespace, logger) -> int:
    summary_path = args.e2e_run
    if not summary_path.exists():
        logger.error("e2e_run.json not found: %s", summary_path)
        return 1
    summary = load_run_summary(summary_path)
    print(format_run_summary(summary))
    return 0


def _cmd_list(args: argparse.Namespace, logger) -> int:
    storage_root = resolve_storage_root()
    dataset_id = getattr(args, "dataset_id", None)
    records = list_e2e_runs(storage_root, dataset_id=dataset_id)
    if getattr(args, "json", False):
        out = [
            {
                "e2e_run_id": r.e2e_run_id,
                "dataset_id": r.dataset_id,
                "overall_status": r.overall_status,
                "lifecycle": r.lifecycle,
                "created_utc": r.created_utc,
                "run_dir": r.run_dir,
                "summary_path": r.summary_path,
            }
            for r in records
        ]
        print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if not records:
        print("(no end-to-end runs found)")
        return 0
    print(
        f"{'e2e_run_id':<32s}  {'dataset_id':<24s}  "
        f"{'overall_status':<14s}  {'created_utc':<22s}  run_dir"
    )
    for r in records:
        print(
            f"{r.e2e_run_id:<32s}  {r.dataset_id:<24s}  "
            f"{r.overall_status:<14s}  {r.created_utc:<22s}  {r.run_dir}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
