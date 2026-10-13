"""DEV-02 import CLI.

Run the single import pipeline on a user-supplied CSV or Parquet
file. The output is a content-keyed manifest under
``data/prototype/datasets/<dataset_id>/``.

Usage
-----

    python scripts/dev02_import_dataset.py --file /path/to/data.csv
    python scripts/dev02_import_dataset.py --file data.csv --name "my-data"
    python scripts/dev02_import_dataset.py --file /tmp/x.csv --allow-external-source

Exit codes
----------
- 0: success — a new dataset was written, or a re-import found an
  existing dataset (REUSED_EXISTING_DATASET).
- 2: validation failed (Stage D or upstream). No artefact written.
- 3: file preflight failed (Stage A). No reads.
- 1: unexpected error.

Architecture
------------
Per docs/system/DEV-02_dataset_management.md and ADR-0005 Option A.

Hard rules
----------
- The storage root is **always** loaded from
  ``configs/dev02_dataset_management.yaml`` (the ``--config`` flag
  may point to a different file; there is no ``--dest-root``).
- The dataset ``scope`` is **always** ``IMPORTED_PROTOTYPE``.
- No re-implementation of FE-06 / RFM / transformation / clustering /
  evaluation / profiling logic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from customer_segmentation.dataset_management import (
    DEFAULT_CONFIG_PATH,
    ImportError,
    build_request_from_args,
    import_dataset,
)
from customer_segmentation.dataset_management.importer import build_request_from_args
from customer_segmentation.dataset_management.validation import FilePreflightError

# `build_request_from_args` is re-exported via __init__; the explicit
# import above is kept for type-hint clarity in the docstring. The
# `import_dataset` reference below keeps the importer module on the
# import path; the canonical entry point is the re-export.
_ = import_dataset
_ = DEFAULT_CONFIG_PATH


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="dev02_import_dataset",
        description=(
            "Import a CSV or Parquet file as a DEV-02 prototype dataset."
        ),
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the source CSV or Parquet file.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Optional display name. Defaults to the file's basename.",
    )
    parser.add_argument(
        "--allow-external-source",
        action="store_true",
        help=(
            "Permit the source file to be outside the repository. "
            "Default is off; the config file's "
            "source_path_policy.allow_external_source is the "
            "secondary source."
        ),
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=(
            "Path to the DEV-02 dataset-management config YAML. "
            f"Default: {DEFAULT_CONFIG_PATH}."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    args = parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    cwd = Path.cwd()

    try:
        request = build_request_from_args(args, repo_root=repo_root, cwd=cwd)
    except Exception as exc:
        print(f"[dev02] error: failed to build request: {exc}", file=sys.stderr)
        return 3

    try:
        result = import_dataset(request)
    except FilePreflightError as exc:
        # Stage A fatal error: no reads, no artefact.
        print(f"[dev02] file preflight failed: {exc}", file=sys.stderr)
        return 3
    except ImportError as exc:
        # Stage B read error, Stage D validation FAIL, or other
        # fatal: no artefact written.
        print(f"[dev02] import failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[dev02] unexpected error: {exc}", file=sys.stderr)
        return 1

    status_word = "REUSED_EXISTING_DATASET" if result.reused else "WRITTEN"
    print(
        f"[dev02] {status_word} dataset_id={result.dataset_id} "
        f"status={result.validation_status} "
        f"rows={result.manifest.row_count} "
        f"cols={result.manifest.column_count} "
        f"sha256={result.sha256[:12]}... "
        f"path={result.storage_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
