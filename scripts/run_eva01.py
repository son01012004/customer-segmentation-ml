#!/usr/bin/env python3
"""CLI entry point for EVA-01 — Experiment Result Repository.

This script:

1. Reads EPIC-07 artifacts (EXP-01 through EXP-05) from the local
   ``reports/`` directory.
2. Normalises every per-run record into the standardised schema
   defined in
   :mod:`customer_segmentation.evaluation.experiment_results.schema`.
3. Validates the repository (missing / invalid / duplicate /
   inconsistent conditions).
4. Emits the standardised dataset (parquet + CSV), summary tables,
   validation report, and Markdown summary under
   ``reports/evaluation/eva01/``.

The script does NOT mutate any EPIC-07 artifact. It also does NOT
push, commit, or open a PR (per AGENTS.md §2.11).

Usage
-----

::

    python scripts/run_eva01.py
    python scripts/run_eva01.py --reports-dir reports --output-dir reports/evaluation/eva01
    python scripts/run_eva01.py --experiments EXP-01 EXP-02 EXP-03 EXP-04 EXP-05

Exit codes
----------

- ``0`` — success.
- ``1`` — unrecoverable error (e.g. reports directory missing,
  pandas/pyarrow import failure).
- ``2`` — validation produced anomalies that the human reviewer
  must inspect (anomalies are still written to disk).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

# Ensure ``src/`` is on sys.path so ``customer_segmentation`` is importable
# when running directly via ``python scripts/run_eva01.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from customer_segmentation.evaluation.experiment_results.repository import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORTS_DIR,
    ExperimentResultRepository,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="run_eva01",
        description=(
            "EVA-01 — Build the unified experiment-result repository from "
            "EPIC-07 (EXP-01..EXP-05) artifacts. Emits standardised dataset, "
            "summary tables, and a validation report."
        ),
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help=(
            "Path to the ``reports/`` directory containing exp01/..exp05/. "
            f"Defaults to ``{DEFAULT_REPORTS_DIR}``."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "eva01",
        help=(
            "Where to write the standardised dataset, summary tables, "
            "validation report, and Markdown summary. "
            f"Defaults to ``{DEFAULT_OUTPUT_DIR / 'eva01'}``."
        ),
    )
    parser.add_argument(
        "--experiments",
        nargs="+",
        default=("EXP-01", "EXP-02", "EXP-03", "EXP-04", "EXP-05"),
        help="Subset of source experiments to include (default: all five).",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip writing the standardized dataset as CSV (parquet only).",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Skip writing the Markdown summary report.",
    )
    parser.add_argument(
        "--no-validation-json",
        action="store_true",
        help="Skip writing the validation report as JSON.",
    )
    parser.add_argument(
        "--no-summary-csv",
        action="store_true",
        help="Skip writing the summary tables as CSV.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit with code 2 if any row is flagged MISSING / INVALID, "
            "or if DUPLICATE_EXACT / DUPLICATE_BY_INTENT / "
            "INCONSISTENT_CONDITIONS groups are detected."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (errors still printed).",
    )
    return parser.parse_args(argv)


def _log(message: str, *, quiet: bool) -> None:
    """Log a message to stdout unless ``quiet`` is set."""
    if not quiet:
        print(message)


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint for the EVA-01 CLI.

    Returns the process exit code (0 success, 1 unrecoverable, 2 strict-fail).
    """
    args = parse_args(argv)

    if not args.reports_dir.exists():
        print(
            f"[ERROR] reports directory not found: {args.reports_dir}",
            file=sys.stderr,
        )
        return 1

    _log(f"[EVA-01] Reading from: {args.reports_dir}", quiet=args.quiet)
    _log(f"[EVA-01] Output dir : {args.output_dir}", quiet=args.quiet)
    _log(
        f"[EVA-01] Including  : {' '.join(args.experiments)}",
        quiet=args.quiet,
    )

    # --- Build the repository ---
    try:
        repo = ExperimentResultRepository.build_from_reports_dir(
            args.reports_dir,
            experiments=tuple(args.experiments),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] failed to build repository: {exc}", file=sys.stderr)
        return 1

    _log(f"[EVA-01] Collected  : {repo.n_rows} rows", quiet=args.quiet)
    counts = repo.n_rows_by_experiment
    for exp in args.experiments:
        _log(f"             - {exp}: {counts.get(exp, 0)}", quiet=args.quiet)

    # --- Validate ---
    report = repo.validate()
    _log(
        f"[EVA-01] Validation : OK={report.n_ok} "
        f"MISSING={report.n_missing} INVALID={report.n_invalid}",
        quiet=args.quiet,
    )
    _log(
        f"[EVA-01] Anomalies  : DUPLICATE_EXACT={len(report.duplicate_exact)} "
        f"DUPLICATE_BY_INTENT={len(report.duplicate_by_intent)} "
        f"INCONSISTENT_CONDITIONS={len(report.inconsistent_conditions)}",
        quiet=args.quiet,
    )

    # --- Write outputs ---
    try:
        paths = repo.write_outputs(
            args.output_dir,
            also_csv=not args.no_csv,
            also_markdown=not args.no_markdown,
            also_validation=not args.no_validation_json,
            also_summary_csv=not args.no_summary_csv,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] failed to write outputs: {exc}", file=sys.stderr)
        return 1

    _log("[EVA-01] Wrote:", quiet=args.quiet)
    for name, path in paths.items():
        _log(f"             - {name}: {path}", quiet=args.quiet)

    # --- Strict check ---
    if args.strict:
        anomalies = (
            report.n_missing + report.n_invalid
            + len(report.duplicate_exact)
            + len(report.duplicate_by_intent)
            + len(report.inconsistent_conditions)
        )
        if anomalies > 0:
            print(
                f"[EVA-01] Strict mode: {anomalies} anomaly/anomalies detected; "
                "review validation report and decide.",
                file=sys.stderr,
            )
            return 2

    _log("[EVA-01] Done.", quiet=args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
