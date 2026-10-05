#!/usr/bin/env python3
"""EVA-03 — Stability & Reproducibility Evaluation Runner.

CLI entry point for EVA-03 (RQ3 / EPIC-08 analysis phase).

Reads:
  - reports/exp05/exp05_cluster_labels.parquet  (REQUIRED, 75 runs)
  - reports/exp05/exp05_*_aggregate.csv          (per-block aggregates)
  - reports/exp01/cluster_labels_EXP-01-{algo}_rep4.parquet
  - reports/exp01/exp01_baseline_summary.csv
  - reports/exp03/exp03_selected_configurations.csv

Writes:
  - reports/evaluation/eva03/tables/*.csv
  - reports/evaluation/eva03/eva03_stability_report.md
  - reports/evaluation/eva03/eva03_reproducibility_report.md
  - reports/evaluation/eva03/eva03_comparison_report.md
  - reports/evaluation/eva03/eva03_run_manifest.json

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- Read-only against EXP-05 / EXP-01 / EXP-03 artifacts.
- No "best / winner / optimal / recommended / final" claims.
- No composite stability score.
- No promotion of WORKING_SELECTED to RESEARCH_APPROVED.
- No commit / push / PR.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure ``src/`` is importable.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.evaluation.eva03 import (  # noqa: E402
    Eva03Config,
    Eva03Runner,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EVA-03 — Stability & Reproducibility Evaluation Runner"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_REPO_ROOT / "configs" / "eva03_stability_evaluation.yaml",
        help="Path to EVA-03 YAML config.",
    )
    parser.add_argument(
        "--exp05-dir",
        type=Path,
        default=_REPO_ROOT / "reports" / "exp05",
        help="Path to EXP-05 reports directory (containing the labels artifact).",
    )
    parser.add_argument(
        "--exp01-dir",
        type=Path,
        default=_REPO_ROOT / "reports" / "exp01",
        help="Path to EXP-01 reports directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "reports" / "evaluation" / "eva03",
        help="Path to EVA-03 output directory.",
    )
    parser.add_argument(
        "--no-hungarian",
        action="store_true",
        help="Skip Hungarian matching (descriptive cluster alignment).",
    )
    args = parser.parse_args()

    print("[EVA-03] Starting stability & reproducibility evaluation...")
    print(f"[EVA-03] Repository root: {_REPO_ROOT}")

    if not (args.exp05_dir / "exp05_cluster_labels.parquet").exists():
        print(
            "[EVA-03] ERROR: Missing EXP-05 labels artifact at expected path. "
            f"({args.exp05_dir / 'exp05_cluster_labels.parquet'})"
        )
        return 1

    config = Eva03Config(
        config_path=args.config,
        exp05_reports_dir=args.exp05_dir,
        exp01_reports_dir=args.exp01_dir,
        output_dir=args.output_dir,
        include_hungarian=not args.no_hungarian,
    )
    runner = Eva03Runner(config=config)
    result = runner.run()

    print("\n[EVA-03] Outputs written:")
    print(f"  Generated at: {result['generated_at']}")
    print(f"  Output dir: {result['output_dir']}")
    print(f"  Tables ({len(result['tables'])}):")
    for p in result["tables"]:
        print(f"    - {p}")
    print("  Reports:")
    for k, p in result["reports"].items():
        print(f"    - {p} ({k})")
    print("\n[EVA-03] Decision status per analysis block:")
    for k, v in result["decision_status"].items():
        print(f"  {k}: {v}")
    print("\n[EVA-03] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
