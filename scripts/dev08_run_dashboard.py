"""CLI entry point for DEV-08 Prototype Visualization Dashboard.

Mirrors the DEV-07 ``scripts/dev07_run_marketing.py`` shape.

Subcommands
-----------
- ``render`` — run the full dashboard pipeline once; emit chart files
  + text artefacts + ``dashboard_summary.txt`` + ``dashboard_summary.json``.
- ``summary`` — re-display the existing ``dashboard_summary.json``
  produced by a previous ``render`` invocation.

Examples
--------
::

    python scripts/dev08_run_dashboard.py render \\
        --segmentation-id seg_aaaaaaaaaaaaaaaaaaaaaaaa \\
        --evaluation-manifest /path/to/ev.json

    python scripts/dev08_run_dashboard.py render \\
        --segmentation-manifest /path/to/segmentation_manifest.json \\
        --output-dir /tmp/my_dashboard

    python scripts/dev08_run_dashboard.py summary \\
        --dashboard-summary /path/to/dashboard_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from customer_segmentation.prototype.visualization.display import (
    format_dashboard_run_report,
    format_dashboard_summary,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationConfigError,
    VisualizationError,
    VisualizationInputError,
    VisualizationStoragePathError,
)
from customer_segmentation.prototype.visualization.logging_config import (
    configure_logging,
    finalize_logging,
)
from customer_segmentation.prototype.visualization.pipeline import (
    run_visualization_pipeline,
)

__all__ = [
    "build_parser",
    "main",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the DEV-08 CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="dev08-visualization",
        description=(
            "DEV-08 Prototype Visualization Dashboard pipeline. Reads "
            "DEV-06/05/07 manifests and emits chart files + text artefacts "
            "+ dashboard summary under a run directory. Cluster "
            "Visualization 2D is BLOCKED until a projection methodology is "
            "approved. Marketing section is REVIEW_REQUIRED by default. See "
            "docs/system/DEV-08_*.md."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to DEV-08 config YAML (default: configs/dev08_visualization.yaml).",
    )
    common.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Directory for the per-stage log file (default: no file log).",
    )

    p_render = subparsers.add_parser(
        "render",
        parents=[common],
        help="Run the DEV-08 pipeline and write the dashboard to a directory.",
    )
    seg_id_vs_path = p_render.add_mutually_exclusive_group(required=True)
    seg_id_vs_path.add_argument(
        "--segmentation-id",
        type=str,
        default=None,
        help="DEV-06 segmentation_id (^seg_[0-9a-f]{24}$).",
    )
    seg_id_vs_path.add_argument(
        "--segmentation-manifest",
        type=Path,
        default=None,
        help="Explicit path to DEV-06 segmentation_manifest.json.",
    )
    p_render.add_argument(
        "--evaluation-manifest",
        type=Path,
        action="append",
        default=[],
        help=(
            "Path to a DEV-05 evaluation_manifest.json. Repeat the flag to "
            "compare multiple evaluation runs (max is configured by "
            "max_runs_per_chart). Optional."
        ),
    )
    p_render.add_argument(
        "--marketing-manifest",
        type=Path,
        default=None,
        help="Optional path to DEV-07 marketing_manifest.json.",
    )
    p_render.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory to write the dashboard into. When omitted, the canonical "
            "per-segmentation directory under the storage root is used "
            "(one subdirectory per dashboard_id)."
        ),
    )
    p_render.add_argument(
        "--output-format",
        type=str,
        choices=["png", "svg"],
        default=None,
        help="Override chart output format (default: from config).",
    )
    p_render.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore the idempotency cache and write a fresh dashboard.",
    )

    p_summary = subparsers.add_parser(
        "summary",
        parents=[common],
        help="Re-display an existing dashboard_summary.json.",
    )
    p_summary.add_argument(
        "--dashboard-summary",
        type=Path,
        required=True,
        help="Path to a DEV-08 dashboard_summary.json (or .txt).",
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
        if args.subcommand == "render":
            return _cmd_render(args, logger)
        if args.subcommand == "summary":
            return _cmd_summary(args, logger)
        parser.print_help()
        return 2
    except VisualizationInputError as exc:
        logger.error("DEV-08 input error: %s", exc)
        return 2
    except VisualizationConfigError as exc:
        logger.error("DEV-08 config error: %s", exc)
        return 3
    except VisualizationStoragePathError as exc:
        logger.error("DEV-08 storage error: %s", exc)
        return 4
    except VisualizationError as exc:
        logger.error("DEV-08 error: %s", exc)
        return 1
    finally:
        finalize_logging(logger)


def _cmd_render(args: argparse.Namespace, logger) -> int:
    seg_id = getattr(args, "segmentation_id", None)
    seg_path = getattr(args, "segmentation_manifest", None)
    eval_paths = list(getattr(args, "evaluation_manifest", []) or [])
    mkt_path = getattr(args, "marketing_manifest", None)
    config = getattr(args, "config", None)
    log_dir = getattr(args, "log_dir", None)
    output_dir = getattr(args, "output_dir", None)
    output_format = getattr(args, "output_format", None)
    force_rerun = bool(getattr(args, "force_rerun", False))

    result = run_visualization_pipeline(
        segmentation_id=seg_id,
        segmentation_manifest_path=seg_path,
        evaluation_manifest_paths=eval_paths,
        marketing_manifest_path=mkt_path,
        output_dir=output_dir,
        config_path=config,
        output_format=output_format,
        force_rerun=force_rerun,
        log_dir=log_dir,
    )
    print(format_dashboard_summary(result.result))
    print()
    print(format_dashboard_run_report(result.result))
    print()
    print(f"Wrote: {result.run_dir}")
    print(f"Lifecycle: {result.lifecycle}")
    print(f"Summary text: {result.summary_text_path}")
    print(f"Summary JSON: {result.summary_json_path}")
    if result.notes:
        for note in result.notes:
            print(f"Note: {note}")
    return 0


def _cmd_summary(args: argparse.Namespace, logger) -> int:
    summary_path = args.dashboard_summary
    if not summary_path.exists():
        logger.error("Dashboard summary not found: %s", summary_path)
        return 1
    if summary_path.suffix.lower() == ".json":
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse dashboard_summary.json: %s", exc)
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    # Plain text rendering.
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
