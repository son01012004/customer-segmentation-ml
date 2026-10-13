"""DEV-03 preprocess CLI.

Run the single preprocessing pipeline on a DEV-02 imported dataset.

Usage
-----
    python scripts/dev03_preprocess_dataset.py --dataset-id <id>
    python scripts/dev03_preprocess_dataset.py --dataset-id <id> --config <path>

Exit codes
----------
- 0: success — a new preprocessed artefact was written, or a
  re-preprocess found an existing ``preprocessed_id`` (REUSED).
- 2: validation FAIL (Stage B / F2 / G1). No artefact written.
- 3: file preflight failed (Stage A). No reads.
- 1: unexpected error.

Architecture
------------
Per docs/system/DEV-03_preprocessing.md and ADR-0005 Option A.

Hard rules
----------
- The storage root is shared with DEV-02 (no ``--dest-root``).
- The ``preprocessed_scope`` is **always** ``PREPROCESSED_PROTOTYPE``.
- The CLI never modifies ``data/raw/primary/``, ``data/raw/backup/``,
  ``data/processed/``, or ``reports/``.
- No commit / no push / no PR / no merge performed by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from customer_segmentation.prototype.preprocessing import (
    DEFAULT_DEV03_CONFIG_PATH,
    run_preprocessing_pipeline,
)

__all__ = ["parse_args", "main"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="dev03_preprocess_dataset",
        description=(
            "Run the DEV-03 prototype preprocessing pipeline on a " "DEV-02 imported dataset."
        ),
    )
    parser.add_argument(
        "--dataset-id",
        required=True,
        help="DEV-02 dataset id (e.g. 'ds_ba54033e45525bf5123c2d9d').",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_DEV03_CONFIG_PATH),
        help=(
            "Path to the DEV-03 preprocessing config YAML. "
            f"Default: {DEFAULT_DEV03_CONFIG_PATH}."
        ),
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help=("Print a JSON-serialisable summary to stdout at the end " "of the run."),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    args = parse_args(argv)

    try:
        result = run_preprocessing_pipeline(
            args.dataset_id,
            config_path=Path(args.config),
        )
    except ValueError as exc:
        print(f"[dev03] validation failed: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"[dev03] file preflight failed: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[dev03] unexpected error: {exc}", file=sys.stderr)
        return 1

    summary = result.as_summary()
    print(
        f"[dev03] WRITTEN preprocessed_id={result.preprocessed_id} "
        f"lifecycle={result.lifecycle} "
        f"ml_dataset={result.ml_dataset_path}"
    )
    print(f"[dev03] manifest:           {result.manifest_path}")
    print(f"[dev03] log:                {result.log_path}")
    print(
        f"[dev03] cleaning: rows_in={summary['cleaning']['rows_in']} "
        f"rows_out={summary['cleaning']['rows_out']} "
        f"removed={summary['cleaning']['rows_removed_total']}"
    )
    print(
        f"[dev03] stage F: customer_count={summary['feature_generation']['customer_count']} "
        f"candidate_features={summary['feature_generation']['candidate_feature_count']} "
        f"outcome={summary['feature_generation']['outcome']}"
    )

    if args.json_summary:
        print(json.dumps(summary, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
