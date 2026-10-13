"""CLI entry point for DEV-07 Prototype Marketing.

Mirrors the DEV-06 ``scripts/dev06_run_segmentation.py`` shape.

Subcommands
-----------
- ``profile`` — run the full pipeline once; emit marketing_manifest.json
  only (no CSV / JSONL — OQ-D07-08 read-only).
- ``summary`` — re-display the existing manifest at the given path.

Examples
--------
::

    python scripts/dev07_run_marketing.py profile \\
        --segmentation-id seg_aaaaaaaaaaaaaaaaaaaaaaaa

    python scripts/dev07_run_marketing.py profile \\
        --manifest-path /path/to/segmentation_manifest.json

    python scripts/dev07_run_marketing.py summary \\
        --manifest-path /path/to/marketing_manifest.json
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from customer_segmentation.prototype.marketing.display import (
    format_marketing_summary,
    format_recommendations_table,
)
from customer_segmentation.prototype.marketing.exceptions import MarketingError
from customer_segmentation.prototype.marketing.logging_config import (
    configure_logging,
    finalize_logging,
)
from customer_segmentation.prototype.marketing.manifest import read_marketing_manifest
from customer_segmentation.prototype.marketing.pipeline import run_marketing_pipeline

__all__ = [
    "build_parser",
    "main",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the DEV-07 CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="dev07-marketing",
        description=(
            "DEV-07 Prototype Marketing pipeline (Phase A: REVIEW_REQUIRED "
            "shell). Reads a DEV-06 SegmentationManifest and writes a "
            "MarketingRecommendationManifest; does not generate "
            "recommendation content. See docs/system/DEV-07_*.md."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to DEV-07 config YAML (default: configs/dev07_marketing.yaml).",
    )
    common.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Directory for the per-stage log file (default: no file log).",
    )

    p_profile = subparsers.add_parser(
        "profile",
        parents=[common],
        help="Run the DEV-07 pipeline and write marketing_manifest.json.",
    )
    seg_id_vs_path = p_profile.add_mutually_exclusive_group(required=True)
    seg_id_vs_path.add_argument(
        "--segmentation-id",
        type=str,
        default=None,
        help="DEV-06 segmentation_id (^seg_[0-9a-f]{24}$).",
    )
    seg_id_vs_path.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Explicit path to DEV-06 segmentation_manifest.json.",
    )
    p_profile.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore the idempotency cache and write a fresh manifest.",
    )

    p_summary = subparsers.add_parser(
        "summary",
        parents=[common],
        help="Re-display an existing marketing_manifest.json.",
    )
    p_summary.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
        help="Path to a DEV-07 marketing_manifest.json.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Configure root logger early so that errors are visible.
    logger = configure_logging(
        level="INFO",
        log_file=None,
        emit_to_console=True,
    )
    try:
        if args.subcommand == "profile":
            return _cmd_profile(args, logger)
        if args.subcommand == "summary":
            return _cmd_summary(args, logger)
        parser.print_help()
        return 2
    except MarketingError as exc:
        logger.error("DEV-07 error: %s", exc)
        return 1
    finally:
        finalize_logging(logger)


def _cmd_profile(args: argparse.Namespace, logger) -> int:
    seg_id = getattr(args, "segmentation_id", None)
    manifest_path = getattr(args, "manifest_path", None)
    config = getattr(args, "config", None)
    log_dir = getattr(args, "log_dir", None)
    force_rerun = bool(getattr(args, "force_rerun", False))

    result = run_marketing_pipeline(
        segmentation_id=seg_id,
        manifest_path=manifest_path,
        config_path=config,
        force_rerun=force_rerun,
        log_dir=log_dir,
    )
    # Display summary to stdout.
    print(format_marketing_summary(result.manifest))
    print()
    print(format_recommendations_table(result.manifest))
    print()
    print(f"Wrote: {result.manifest_path}")
    print(f"Lifecycle: {result.lifecycle}")
    if result.notes:
        for note in result.notes:
            print(f"Note: {note}")
    return 0


def _cmd_summary(args: argparse.Namespace, logger) -> int:
    manifest_path = args.manifest_path
    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        return 1
    manifest = read_marketing_manifest(manifest_path)
    print(format_marketing_summary(manifest))
    print()
    print(format_recommendations_table(manifest))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
