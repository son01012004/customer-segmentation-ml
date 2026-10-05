"""Report generation for FE-06.

Writes all reports under reports/fe06/.

Reports (FE-06 v1.1):
- fe06_run.json (reproducibility metadata)
- feature_eligibility.csv
- feature_dictionary.csv
- distribution_pre_transformation.csv
- distribution_post_transformation.csv
- distribution_post_scaling.csv
- correlation_pre_transformation.csv (pearson + spearman)
- correlation_post_transformation.csv (pearson + spearman)
- correlation_post_scaling.csv (pearson + spearman)
- redundancy_analysis.csv (3-category classification)
- redundancy_report.csv (high-correlation pairs, |Pearson|>=threshold)
- outlier_analysis.csv
- comparison_matrix.csv
- data_quality_report.csv
- leakage_check.csv
- imputation_semantics.csv
- narrative_report.md

Hard constraints:
- No "best/recommended/optimal" language.
- No clustering/evaluation metrics.
- All working decisions marked WORKING_ASSUMPTION.
- TECHNICALLY_GENERATED != RESEARCH_APPROVED_FINAL.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

__all__ = [
    "write_fe06_reports",
    "write_fe06_run_json",
    "write_narrative_report",
    "write_comparison_matrix",
]


def write_fe06_reports(
    report_dir: Path,
    distribution_pre: pd.DataFrame,
    distribution_post_trans: pd.DataFrame,
    distribution_post_scale: pd.DataFrame,
    correlation_pre_pearson: pd.DataFrame,
    correlation_pre_spearman: pd.DataFrame,
    correlation_post_trans_pearson: pd.DataFrame,
    correlation_post_trans_spearman: pd.DataFrame,
    correlation_post_scale_pearson: pd.DataFrame,
    correlation_post_scale_spearman: pd.DataFrame,
    redundancy_pre: pd.DataFrame,
    redundancy_post: pd.DataFrame,
    outlier_pre: pd.DataFrame,
    outlier_post_scale: pd.DataFrame,
    feature_eligibility_df: pd.DataFrame,
    feature_dictionary_df: pd.DataFrame,
    comparison_matrix: pd.DataFrame,
    data_quality_df: pd.DataFrame,
    leakage_df: pd.DataFrame,
    run_metadata: dict,
    redundancy_analysis_df: pd.DataFrame | None = None,
    imputation_semantics_df: pd.DataFrame | None = None,
) -> dict[str, Path]:
    """Write all FE-06 reports.

    Parameters
    ----------
    report_dir : pathlib.Path
        Output directory for reports.
    ... (all report DataFrames)
    run_metadata : dict
        Run metadata for fe06_run.json.
    redundancy_analysis_df : pandas.DataFrame, optional
        3-category redundancy analysis (FE-06 v1.1). If None, an empty
        report is written.
    imputation_semantics_df : pandas.DataFrame, optional
        Per-feature imputation semantics (FE-06 v1.1). If None, an empty
        report is written.

    Returns
    -------
    dict[str, pathlib.Path]
        Map of report name to path.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    # CSV reports
    csv_reports: dict[str, pd.DataFrame | None] = {
        "feature_eligibility": feature_eligibility_df,
        "feature_dictionary": feature_dictionary_df,
        "distribution_pre_transformation": distribution_pre,
        "distribution_post_transformation": distribution_post_trans,
        "distribution_post_scaling": distribution_post_scale,
        "correlation_pre_transformation_pearson": correlation_pre_pearson,
        "correlation_pre_transformation_spearman": correlation_pre_spearman,
        "correlation_post_transformation_pearson": correlation_post_trans_pearson,
        "correlation_post_transformation_spearman": correlation_post_trans_spearman,
        "correlation_post_scaling_pearson": correlation_post_scale_pearson,
        "correlation_post_scaling_spearman": correlation_post_scale_spearman,
        "redundancy_report": redundancy_post,
        "redundancy_analysis": redundancy_analysis_df,
        "imputation_semantics": imputation_semantics_df,
        "outlier_analysis": outlier_post_scale,
        "comparison_matrix": comparison_matrix,
        "data_quality_report": data_quality_df,
        "leakage_check": leakage_df,
    }

    for name, df in csv_reports.items():
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            # Write empty CSV with just header
            path = report_dir / f"{name}.csv"
            pd.DataFrame(columns=["_placeholder"]).to_csv(path, index=False)
        else:
            path = report_dir / f"{name}.csv"
            if isinstance(df, pd.DataFrame):
                df.to_csv(path, index=False)
            else:
                # Correlation matrices need index
                df.to_csv(path)
        paths[name] = path

    # fe06_run.json
    run_json_path = report_dir / "fe06_run.json"
    with run_json_path.open("w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2, default=str)
    paths["fe06_run_json"] = run_json_path

    return paths


def write_fe06_run_json(
    report_dir: Path,
    metadata: dict,
) -> Path:
    """Write fe06_run.json separately."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "fe06_run.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    return path


def write_narrative_report(
    report_dir: Path,
    narrative: str,
) -> Path:
    """Write narrative_report.md."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "narrative_report.md"
    path.write_text(narrative, encoding="utf-8")
    return path


def write_comparison_matrix(
    report_dir: Path,
    matrix: pd.DataFrame,
) -> Path:
    """Write comparison_matrix.csv."""
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "comparison_matrix.csv"
    matrix.to_csv(path, index=False)
    return path
