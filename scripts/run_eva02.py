#!/usr/bin/env python3
"""CLI entry point for EVA-02 — Cluster Quality Evaluation.

This script:

1. Reads the EVA-01 standardised repository from
   ``reports/evaluation/eva01/`` (parquet preferred, CSV fallback).
2. Builds descriptive comparison / quality / cross-metric / DBSCAN-noise
   tables.
3. Renders the comparison / distribution plots (PNG) into
   ``reports/evaluation/eva02/figures/``.
4. Writes per-metric ranking tables into
   ``reports/evaluation/eva02/tables/``.
5. Writes a Markdown narrative report ``eva02_report.md``.
6. Writes a JSON run manifest with provenance information.

The script does NOT mutate any EVA-01 artifact, does NOT compute
or write a "best/winner/optimal/recommended" label, and does NOT
push, commit, or open a PR (per AGENTS.md §2.11).

Usage
-----

::

    python scripts/run_eva02.py
    python scripts/run_eva02.py --eva01-dir reports/evaluation/eva01
    python scripts/run_eva02.py --output-dir reports/evaluation/eva02
    python scripts/run_eva02.py --rank-tolerance 1 --prefer-csv
    python scripts/run_eva02.py --no-rankings

Exit codes
----------

- ``0`` — success.
- ``1`` — unrecoverable error (e.g. EVA-01 outputs missing, import
  failure).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure ``src/`` is on sys.path so ``customer_segmentation`` is importable
# when running directly via ``python scripts/run_eva02.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from customer_segmentation.evaluation.eva02.runner import (  # noqa: E402  (after sys.path tweak)
    Eva02Config,
    Eva02Runner,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_eva02",
        description=(
            "EVA-02 — Cluster Quality Evaluation. "
            "Reads EVA-01 outputs and produces descriptive tables, "
            "figures, and a Markdown report."
        ),
    )
    parser.add_argument(
        "--eva01-dir",
        type=Path,
        default=Path("reports/evaluation/eva01"),
        help="Directory containing EVA-01 outputs (default: %(default)s).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/evaluation/eva02"),
        help="Directory where EVA-02 outputs are written (default: %(default)s).",
    )
    parser.add_argument(
        "--rank-tolerance",
        type=int,
        default=1,
        help=(
            "Maximum allowed rank difference before a row is flagged "
            "as a cross-metric conflict (default: %(default)s)."
        ),
    )
    prefer_group = parser.add_mutually_exclusive_group()
    prefer_group.add_argument(
        "--prefer-parquet",
        action="store_true",
        default=True,
        help="Prefer parquet when loading EVA-01 (default).",
    )
    prefer_group.add_argument(
        "--prefer-csv",
        action="store_true",
        default=False,
        help="Force CSV loading of EVA-01 (skip parquet).",
    )
    parser.add_argument(
        "--no-rankings",
        action="store_true",
        default=False,
        help="Skip writing per-metric ranking tables.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    prefer_parquet = not args.prefer_csv
    config = Eva02Config(
        eva01_dir=args.eva01_dir,
        output_dir=args.output_dir,
        rank_tolerance=args.rank_tolerance,
        prefer_parquet=prefer_parquet,
        write_rankings=not args.no_rankings,
    )

    runner = Eva02Runner(config=config)
    try:
        manifest = runner.run()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[ERROR] EVA-02 run failed: {exc}", file=sys.stderr)
        return 1

    # Friendly summary on stdout for the human reviewer.
    print("EVA-02 completed.")
    print(f"  repository rows:        {manifest['n_rows']}")
    print(f"  output_dir:             {manifest['output_dir']}")
    print(f"  tables written:         {len(manifest['tables'])}")
    print(f"  rankings written:       {len(manifest['rankings'])}")
    print(f"  figures written:        {len(manifest['figures'])}")
    print(f"  report:                 {manifest['report']}")
    print(f"  manifest:               {manifest['output_dir']}/eva02_run_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
