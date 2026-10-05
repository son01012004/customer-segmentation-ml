"""FE-06 orchestrator: transformation + scaling + final clustering dataset.

Stage: 06_transformation (FE-06)

Usage (from the repository root):

    python -m scripts.run_fe06_transformation
    python -m scripts.run_fe06_transformation --config PATH

Outputs
-------
Written under ``data/processed/``:

- ``final_clustering_dataset.parquet`` — the final clustering matrix
  (4371 rows × 14 features, no CustomerID, numeric only, no NaN, no Inf).
- ``customer_metadata.parquet`` — CustomerID metadata (4371 rows × 1 col).
- ``fitted_preprocessing_pipeline.pkl`` — fitted imputation + transformation + scaling.

Written under ``reports/fe06/``:

- ``fe06_run.json`` — full reproducibility metadata + SHA-256
- ``feature_eligibility.csv`` — feature eligibility decisions
- ``feature_dictionary.csv`` — extended feature dictionary
- ``distribution_pre_transformation.csv`` — T0 baseline distribution
- ``distribution_post_transformation.csv`` — after Yeo-Johnson
- ``distribution_post_scaling.csv`` — after RobustScaler
- ``correlation_pre_transformation_pearson.csv`` — Pearson pre
- ``correlation_pre_transformation_spearman.csv`` — Spearman pre
- ``correlation_post_transformation_pearson.csv`` — Pearson post transform
- ``correlation_post_transformation_spearman.csv`` — Spearman post transform
- ``correlation_post_scaling_pearson.csv`` — Pearson post scale
- ``correlation_post_scaling_spearman.csv`` — Spearman post scale
- ``redundancy_report.csv`` — high-correlation pairs (diagnostic only)
- ``outlier_analysis.csv`` — IQR outlier detection post-scaling
- ``comparison_matrix.csv`` — candidate configs × diagnostics
- ``data_quality_report.csv`` — validation checks
- ``leakage_check.csv`` — identifier leakage verification
- ``narrative_report.md`` — Vietnamese narrative report

Working configuration (C7):
- transformation: yeo_johnson (all 14 eligible features)
- scaling: robust (all 14 eligible features)
- imputation: median (PurchaseIntervalMean, PurchaseIntervalStd)
- Status: WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING

Hard constraints (AGENTS.md / Plan V2):
- Input customer_candidates.parquet is READ-ONLY.
- SHA-256 input verified before/after pipeline.
- CustomerID NEVER in clustering matrix.
- No clustering, no evaluation, no tuning.
- No "best/recommended/optimal" claim.
- Redundancy is DIAGNOSTIC ONLY — no auto-drop.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from customer_segmentation.transformation.pipeline import run_fe06_pipeline  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PROCESSED_DIR: Path = _REPO_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "fe06"
DEFAULT_CANDIDATES_PATH: Path = DEFAULT_PROCESSED_DIR / "customer_candidates.parquet"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "FE-06 transformation pipeline. "
            "Reads data/processed/customer_candidates.parquet. "
            "Writes final_clustering_dataset.parquet, customer_metadata.parquet, "
            "fitted_preprocessing_pipeline.pkl, and reports under reports/fe06/."
        ),
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to the transformation YAML. "
        "If omitted, auto-discovers 'configs/transformation.yaml'.",
    )
    p.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_CANDIDATES_PATH,
        help="Path to the FE-05 customer_candidates.parquet.",
    )
    p.add_argument(
        "--processed-dir",
        type=Path,
        default=DEFAULT_PROCESSED_DIR,
        help="Output directory for final dataset and metadata.",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Output directory for FE-06 reports.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)
    print(f"[FE-06] input:          {args.input}")
    print(f"[FE-06] output dir:    {args.processed_dir}")
    print(f"[FE-06] report dir:    {args.report_dir}")

    result = run_fe06_pipeline(
        customer_candidates_path=args.input,
        processed_dir=args.processed_dir,
        report_dir=args.report_dir,
        config_path=args.config,
    )

    print(f"[FE-06] FE-06 version:        {result.fe06_version}")
    print(f"[FE-06] working config:      {result.working_config_id}")
    print(f"[FE-06] transformation:     {result.working_transformation}")
    print(f"[FE-06] scaling:            {result.working_scaling}")
    print(f"[FE-06] imputation:          {result.working_imputation}")
    print(f"[FE-06] eligible features:   {len(result.eligible_features)}")
    print(f"[FE-06] excluded features:   {len(result.excluded_features)}")
    print(f"[FE-06] final matrix shape: {result.final_matrix.shape}")
    print(f"[FE-06] input SHA-256:      {result.input_sha256[:16]}...")
    print(f"[FE-06] output matrix SHA:   {result.output_matrix_sha256[:16]}...")
    print(f"[FE-06] metadata SHA:        {result.output_metadata_sha256[:16]}...")
    print(f"[FE-06] pipeline SHA:        {result.output_pipeline_sha256[:16]}...")
    print(
        f"[FE-06] VALIDATION:         {'PASS' if result.validation_result.all_passed else 'FAIL'}"
    )
    print(f"[FE-06] MEDIAN VALUES: {result.median_values}")


if __name__ == "__main__":
    main()
