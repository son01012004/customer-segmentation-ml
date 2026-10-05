"""Run CP-02 — Per-Cluster Feature Profile & Behavioural Analysis.

This is the entry-point used by the EPIC-09 / CP-02 task. It writes:

- ``reports/profiling/cp02/cp02_feature_profile_table.csv``
- ``reports/profiling/cp02/cp02_relative_comparison.csv``
- ``reports/profiling/cp02/cp02_behavioral_interpretation.csv``
- ``reports/profiling/cp02/cp02_unit_provenance.csv``
- ``reports/profiling/cp02/cp02_cp01_consistency.csv``
- ``reports/profiling/cp02/cp02_runner_manifest.json``
- ``reports/profiling/cp02/cp02_report.md``
- ``reports/profiling/cp02/figures/cp02_*_boxplot.png``
- ``reports/profiling/cp02/figures/cp02_*_heatmap.png``

Hard constraints (AGENTS.md §2):

- Read-only against EPIC-07 / EPIC-08 / FE-05 source artifacts.
- No ranking, no algorithm cross-comparison.
- No cluster naming, no marketing recommendation.
- RAW interpretable feature values are used; transformed values are
  not diễn giải trong business units.
- DBSCAN noise is tách riêng, không gộp vào cluster profiling.

Usage
-----

    python3 scripts/run_cp02.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from customer_segmentation.profiling.cp02 import run_cp02


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("CP-02 — Per-Cluster Feature Profile & Behavioural Analysis")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the default output dir (default: reports/profiling/cp02).",
    )
    parser.add_argument(
        "--no-exp03",
        action="store_true",
        help="Disable inclusion of EXP-03 working-selected units.",
    )
    args = parser.parse_args()
    summary = run_cp02(
        repo_root=Path.cwd(),
        output_dir=args.output_dir,
        include_exp03=not args.no_exp03,
    )
    print("CP-02 complete.")
    print(f"  analysis units total:    {summary['analysis_units_total']}")
    print(f"  units with labels:       {summary['units_with_labels']}")
    print(f"  units without labels:    {summary['units_without_labels']}")
    print(f"  figures produced:        {len(summary['figures'])}")
    print(f"  feature profile csv:     {summary['feature_profile_table_csv']}")
    print(f"  relative comparison csv: {summary['relative_comparison_csv']}")
    print(f"  behavioral interp csv:   {summary['behavioral_interpretation_csv']}")
    print(f"  report:                  {summary['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
