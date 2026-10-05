"""Run CP-01 — Customer Segment Size & Distribution Analysis.

This is the entry-point used by the EPIC-09 / CP-01 task. It writes:

- ``reports/profiling/cp01/cp01_cluster_size_table.csv``
- ``reports/profiling/cp01/cp01_noise_summary.csv``
- ``reports/profiling/cp01/cp01_distribution_indicators.csv``
- ``reports/profiling/cp01/cp01_unit_provenance.csv``
- ``reports/profiling/cp01/cp01_runner_manifest.json``
- ``reports/profiling/cp01/cp01_report.md``
- ``reports/profiling/cp01/figures/cp01_*.png``

Hard constraints (AGENTS.md §2):

- Read-only against EPIC-07 / EPIC-08 source artifacts.
- No ranking, no algorithm cross-comparison.
- No cluster naming, no marketing recommendation.
- No mutation of source artifacts.

Usage
-----

    python3 scripts/run_cp01.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from customer_segmentation.profiling.cp01 import run_cp01


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CP-01 — Customer Segment Size & Distribution Analysis"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the default output dir (default: reports/profiling/cp01).",
    )
    parser.add_argument(
        "--no-exp03",
        action="store_true",
        help="Disable inclusion of EXP-03 working-selected units.",
    )
    args = parser.parse_args()
    summary = run_cp01(
        repo_root=Path.cwd(),
        output_dir=args.output_dir,
        include_exp03=not args.no_exp03,
    )
    print("CP-01 complete.")
    print(f"  analysis units total: {summary['analysis_units_total']}")
    print(f"  units with labels:    {summary['units_with_labels']}")
    print(f"  units without labels: {summary['units_without_labels']}")
    print(f"  figures produced:     {len(summary['figures'])}")
    print(f"  report:               {summary['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
