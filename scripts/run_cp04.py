"""Run CP-04 — Customer Profiles and Segment Naming.

This is the entry-point used by the EPIC-09 / CP-04 task. It writes:

- ``reports/profiling/cp04/cp04_segment_profiles.csv``
- ``reports/profiling/cp04/cp04_segment_naming.csv``
- ``reports/profiling/cp04/cp04_segment_evidence.csv``
- ``reports/profiling/cp04/cp04_unit_provenance.csv``
- ``reports/profiling/cp04/cp04_cp01_consistency.csv``
- ``reports/profiling/cp04/cp04_runner_manifest.json``
- ``reports/profiling/cp04/cp04_report.md``

CP-04 reuses CP-01 / CP-02 / CP-03 chart artifacts via the report
metadata; CP-04 itself does NOT produce new visualisation.

Hard constraints (AGENTS.md §2):

- Read-only against EPIC-07 / EPIC-08 / FE-05 / CP-01 / CP-02 / CP-03
  artifacts.
- No marketing recommendation, no campaign targeting.
- No algorithm ranking / cluster ranking / "best algorithm".
- No segment naming unless evidence supports it.
- DBSCAN noise is separated; noise is NOT a Customer Segment.
- EXP-03 working-selected units = ``NOT_AVAILABLE`` (per ``EV03-HP-01``).
- CancellationRate / ReturnRate (``NOT_ASSESSABLE``) NOT used as
  primary naming evidence.
- AverageQuantity / BasketSize redundancy handled — not used as two
  independent evidence.
- K-Medoids OUT OF SCOPE (per ADR-0003).

Usage
-----

    python3 scripts/run_cp04.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from customer_segmentation.profiling.cp04 import run_cp04


def main() -> int:
    parser = argparse.ArgumentParser(description=("CP-04 — Customer Profiles and Segment Naming"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the default output dir (default: reports/profiling/cp04).",
    )
    parser.add_argument(
        "--no-exp03",
        action="store_true",
        help="Disable inclusion of EXP-03 working-selected units.",
    )
    args = parser.parse_args()
    summary = run_cp04(
        repo_root=Path.cwd(),
        output_dir=args.output_dir,
        include_exp03=not args.no_exp03,
    )
    print("CP-04 complete.")
    print(f"  analysis units total:    {summary['analysis_units_total']}")
    print(f"  units with labels:       {summary['units_with_labels']}")
    print(f"  units without labels:    {summary['units_without_labels']}")
    print(f"  segment profiles csv:    {summary['segment_profiles_csv']}")
    print(f"  segment naming csv:      {summary['segment_naming_csv']}")
    print(f"  segment evidence csv:    {summary['segment_evidence_csv']}")
    print(f"  cp01 consistency csv:    {summary['cp01_consistency_csv']}")
    print(f"  report:                  {summary['report_md']}")
    print(f"  manifest json:           {summary['manifest_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
