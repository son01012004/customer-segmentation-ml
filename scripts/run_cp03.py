"""Run CP-03 — Cluster Comparison and Distinguishing Feature Analysis.

This is the entry-point used by the EPIC-09 / CP-03 task. It writes:

- ``reports/profiling/cp03/cp03_segment_comparison_matrix.csv``
- ``reports/profiling/cp03/cp03_distinguishing_features.csv``
- ``reports/profiling/cp03/cp03_overlap_analysis.csv``
- ``reports/profiling/cp03/cp03_unit_provenance.csv``
- ``reports/profiling/cp03/cp03_runner_manifest.json``
- ``reports/profiling/cp03/cp03_report.md``
- ``reports/profiling/cp03/figures/cp03_*_violin.png``
- ``reports/profiling/cp03/figures/cp03_*_distinguishing.png``
- ``reports/profiling/cp03/figures/cp03_*_iqr_overlap.png``

Hard constraints (AGENTS.md §2):

- Read-only against EPIC-07 / EPIC-08 / FE-05 / CP-01 / CP-02 artifacts.
- No ranking, no algorithm cross-comparison.
- No cluster naming, no marketing recommendation.
- RAW interpretable feature values are used; transformed values are not
  diễn giải in business units.
- DBSCAN noise is tách riêng, không gộp vào cluster profiling.
- CP-03 reuses CP-02 functions (feature profiling, relative comparison,
  behavioural interpretation) to guarantee consistency.
- WORKING_ANALYTICAL_THRESHOLD explicitly labelled in report.

Usage
-----

    python3 scripts/run_cp03.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from customer_segmentation.profiling.cp03 import run_cp03


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("CP-03 — Cluster Comparison and Distinguishing Feature Analysis")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the default output dir (default: reports/profiling/cp03).",
    )
    parser.add_argument(
        "--no-exp03",
        action="store_true",
        help="Disable inclusion of EXP-03 working-selected units.",
    )
    args = parser.parse_args()
    summary = run_cp03(
        repo_root=Path.cwd(),
        output_dir=args.output_dir,
        include_exp03=not args.no_exp03,
    )
    print("CP-03 complete.")
    print(f"  analysis units total:    {summary['analysis_units_total']}")
    print(f"  units with labels:       {summary['units_with_labels']}")
    print(f"  units without labels:     {summary['units_without_labels']}")
    print(f"  figures produced:        {len(summary['figures'])}")
    print(f"  segment comparison csv:  {summary['segment_comparison_matrix_csv']}")
    print(f"  distinguishing csv:      {summary['distinguishing_features_csv']}")
    print(f"  overlap analysis csv:    {summary['overlap_analysis_csv']}")
    print(f"  report:                  {summary['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
