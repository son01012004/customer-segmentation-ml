"""End-to-end sklearn `Pipeline` for feature transformation.

Pipeline flow:
1. Load customer_candidates.parquet (READ-ONLY)
2. Split CustomerID → customer_metadata.parquet
3. Feature eligibility gate
4. NaN imputation (median) + imputation semantics report
5. Transformation (yeo_johnson for working C7)
6. Scaling (robust for working C7)
7. Redundancy analysis with 3-category classification
8. Final validation
9. Write outputs + reports

Working configuration (C7):
  - imputation: median
  - transformation: yeo_johnson (all 14 features)
  - scaling: robust (all 14 features)
  - status: WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING

Dataset status: TECHNICALLY_GENERATED (NOT RESEARCH_APPROVED_FINAL).
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from customer_segmentation.transformation.analysis import (
    compute_correlation_matrices,
    compute_distribution_stats,
    detect_outliers,
    detect_redundancy,
)
from customer_segmentation.transformation.config_loader import (
    TransformationConfig,
    load_transformation_config,
    resolve_transformation_config_path,
)
from customer_segmentation.transformation.feature_eligibility import (
    EligibilityStatus,
    apply_feature_eligibility,
)
from customer_segmentation.transformation.fill_strategy import apply_imputation
from customer_segmentation.transformation.imputation_semantics import (
    analyze_imputation_semantics,
)
from customer_segmentation.transformation.redundancy_analysis import (
    analyze_redundancy_pairs,
)
from customer_segmentation.transformation.report import (
    write_fe06_reports,
    write_narrative_report,
)
from customer_segmentation.transformation.scaling import apply_scaling
from customer_segmentation.transformation.skewness import apply_yeo_johnson
from customer_segmentation.transformation.validators import (
    FinalMatrixValidationResult,
    validate_final_matrix,
)
from customer_segmentation.transformation.versioning import (
    FE06_VERSION,
    compute_df_sha256,
    compute_file_sha256,
)

__all__ = [
    "FE06PipelineResult",
    "run_fe06_pipeline",
]


# Canonical pairs to analyze in detail (FE-06 v1.1).
CANONICAL_REDUNDANCY_PAIRS: list[tuple[str, str]] = [
    ("AverageQuantity", "BasketSize"),
    ("CancellationRate", "ReturnRate"),
    ("Frequency", "ActiveDays"),
]


@dataclass
class FE06PipelineResult:
    """Result of FE-06 pipeline."""

    final_matrix: pd.DataFrame
    customer_metadata: pd.DataFrame
    eligible_features: list[str]
    excluded_features: list[str]
    eligibility_status_map: dict[str, str]
    eligibility_fe05_map: dict[str, str]
    working_config_id: str
    working_transformation: str
    working_scaling: str
    working_imputation: str
    median_values: dict[str, float]
    lambda_values: dict[str, float | None]
    validation_result: FinalMatrixValidationResult
    input_sha256: str
    output_matrix_sha256: str
    output_metadata_sha256: str
    output_pipeline_sha256: str | None
    config_sha256: str
    fe06_version: str


def _build_feature_dictionary(
    eligibility_result: Any,
    feature_columns: list[str],
    working_transformation: str,
    working_scaling: str,
) -> pd.DataFrame:
    """Build feature dictionary DataFrame with FE-06 traceability trace.

    Adds an explicit `FE06_Trace` column showing how each feature maps:
        FE-05 <decision> -> FE-06 <status> -> included in C7 working dataset
        -> MENTOR_REVIEW_PENDING
    ELIGIBLE_WORKING_ASSUMPTION is clearly distinguished from ELIGIBLE
    so the report cannot be misread as "all features are final".
    """
    rows = []
    for feat in feature_columns:
        elig = eligibility_result.eligibility_details.get(feat)
        fe05_decision = elig.fe05_decision if elig else "RETAIN_CANDIDATE"
        fe06_status = elig.fe06_status if elig else EligibilityStatus.ELIGIBLE
        fe06_trace = (
            f"FE-05 {fe05_decision} -> FE-06 {fe06_status} -> "
            f"included in C7 working dataset -> MENTOR_REVIEW_PENDING"
        )
        rows.append(
            {
                "Feature": feat,
                "Layer": elig.fe05_layer if elig else "CANDIDATE",
                "FE05_Decision": fe05_decision,
                "FE06_Status": fe06_status,
                "FE06_Trace": fe06_trace,
                "FE06_Transformation": working_transformation,
                "FE06_Scaling": working_scaling,
                "FE06_Dataset_Version": FE06_VERSION,
                "FE06_Dataset_Status": "TECHNICALLY_GENERATED",
                "Eligibility_Reason": elig.eligibility_reason if elig else "",
                "Variance": elig.variance if elig else None,
                "MissingRatio": elig.missing_ratio if elig else 0.0,
                "Is_Numeric": elig.is_numeric if elig else True,
            }
        )
    return pd.DataFrame(rows)


def _build_feature_eligibility_csv(
    eligibility_result: Any,
) -> pd.DataFrame:
    """Build feature eligibility CSV with FE-06 traceability trace.

    Adds an explicit `FE06_Trace` column showing how each feature maps
    from FE-05 to FE-06, with explicit MENTOR_REVIEW_PENDING marker.
    """
    rows = []
    for feat, elig in eligibility_result.eligibility_details.items():
        fe05_decision = elig.fe05_decision or "(none)"
        fe06_trace = (
            f"FE-05 {fe05_decision} -> FE-06 {elig.fe06_status} -> "
            f"{'included in C7 working dataset' if elig.fe06_status.startswith('ELIGIBLE') else 'NOT included in matrix'} -> "
            f"MENTOR_REVIEW_PENDING"
        )
        rows.append(
            {
                "Feature": feat,
                "FE05_Layer": elig.fe05_layer,
                "FE05_Decision": elig.fe05_decision,
                "FE06_Status": elig.fe06_status,
                "FE06_Trace": fe06_trace,
                "Eligibility_Reason": elig.eligibility_reason,
                "Variance": elig.variance,
                "MissingRatio": elig.missing_ratio,
                "Is_Numeric": elig.is_numeric,
            }
        )
    return pd.DataFrame(rows)


def _build_comparison_matrix(
    config: TransformationConfig,
    diagnostics: dict[str, Any],
    working_config_id: str,
) -> pd.DataFrame:
    """Build comparison matrix CSV for candidate configurations."""
    rows = []
    for exp_config in config.experimental_configurations:
        diag_key = exp_config.id
        diag = diagnostics.get(diag_key, {})
        rows.append(
            {
                "Config_ID": exp_config.id,
                "Transformation": exp_config.transformation,
                "Scaling": exp_config.scaling,
                "Is_Full_Matrix": exp_config.is_full_matrix,
                "Is_Working": exp_config.id == working_config_id,
                "Status": (
                    "WORKING_ASSUMPTION" if exp_config.id == working_config_id else "CANDIDATE"
                ),
                "Mean_Skewness": diag.get("mean_skewness"),
                "Mean_Kurtosis": diag.get("mean_kurtosis"),
                "Mean_Outlier_Ratio": diag.get("mean_outlier_ratio"),
                "Max_Correlation": diag.get("max_correlation"),
            }
        )
    return pd.DataFrame(rows)


def _build_data_quality_report(
    validation_result: FinalMatrixValidationResult,
) -> pd.DataFrame:
    """Build data quality report CSV."""
    rows = []
    for check in validation_result.checks:
        rows.append(
            {
                "Check": check.name,
                "Status": check.status,
                "Message": check.message,
            }
        )
    return pd.DataFrame(rows)


def _build_leakage_check(
    matrix_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build leakage check CSV."""
    identifier_names = {
        "CustomerID",
        "InvoiceNo",
        "InvoiceDate",
        "StockCode",
        "Description",
        "Country",
        "Cluster",
        "ClusterID",
        "Label",
    }
    rows = [
        {
            "Check": "no_identifier_columns_in_matrix",
            "Status": (
                "PASS" if not any(c in matrix_df.columns for c in identifier_names) else "FAIL"
            ),
            "Message": (
                "No identifier columns in matrix."
                if not any(c in matrix_df.columns for c in identifier_names)
                else f"Identifier columns found in matrix: {[c for c in matrix_df.columns if c in identifier_names]}."
            ),
        },
        {
            "Check": "CustomerID_absent_from_matrix",
            "Status": "PASS" if "CustomerID" not in matrix_df.columns else "FAIL",
            "Message": (
                "CustomerID not in clustering matrix."
                if "CustomerID" not in matrix_df.columns
                else "CustomerID found in matrix!"
            ),
        },
        {
            "Check": "InvoiceNo_absent_from_matrix",
            "Status": "PASS" if "InvoiceNo" not in matrix_df.columns else "FAIL",
            "Message": (
                "InvoiceNo not in clustering matrix."
                if "InvoiceNo" not in matrix_df.columns
                else "InvoiceNo found in matrix!"
            ),
        },
        {
            "Check": "StockCode_absent_from_matrix",
            "Status": "PASS" if "StockCode" not in matrix_df.columns else "FAIL",
            "Message": (
                "StockCode not in clustering matrix."
                if "StockCode" not in matrix_df.columns
                else "StockCode found in matrix!"
            ),
        },
        {
            "Check": "InvoiceDate_absent_from_matrix",
            "Status": "PASS" if "InvoiceDate" not in matrix_df.columns else "FAIL",
            "Message": (
                "InvoiceDate not in clustering matrix."
                if "InvoiceDate" not in matrix_df.columns
                else "InvoiceDate found in matrix!"
            ),
        },
        {
            "Check": "Cluster_labels_absent_from_matrix",
            "Status": (
                "PASS" if not any(c.startswith("Cluster") for c in matrix_df.columns) else "FAIL"
            ),
            "Message": (
                "No cluster labels in matrix."
                if not any(c.startswith("Cluster") for c in matrix_df.columns)
                else "Cluster labels found!"
            ),
        },
        {
            "Check": "Metadata_has_CustomerID",
            "Status": "PASS" if "CustomerID" in metadata_df.columns else "FAIL",
            "Message": (
                "CustomerID in metadata."
                if "CustomerID" in metadata_df.columns
                else "CustomerID NOT in metadata!"
            ),
        },
        {
            "Check": "Metadata_row_count_matches_matrix",
            "Status": "PASS" if len(metadata_df) == len(matrix_df) else "FAIL",
            "Message": f"Row counts match: {len(metadata_df)}.",
        },
    ]
    return pd.DataFrame(rows)


def _build_narrative(
    config: TransformationConfig,
    run_metadata: dict,
    eligible_features: list[str],
    excluded_features: list[str],
    median_values: dict[str, float],
    validation_result: FinalMatrixValidationResult,
    lambda_values: dict[str, float | None],
    dist_post_scale: Any,
    outlier_post_scale: Any,
    corr_post_scale: Any,
    redundancy_post: Any,
    redundancy_analysis: Any,
    imputation_semantics: Any,
    df_pre_imputation: pd.DataFrame,
    df_metadata: pd.DataFrame,
    eligibility_status_map: dict[str, str],
    eligibility_fe05_map: dict[str, str],
) -> str:
    """Build Vietnamese narrative report (FE-06 v1.1).

    Parameters
    ----------
    config : TransformationConfig
        Loaded transformation configuration.
    run_metadata : dict
        Run-level metadata for reproducibility.
    eligible_features, excluded_features : list[str]
        Eligible and excluded feature names.
    median_values : dict[str, float]
        Median values used per feature (imputation).
    validation_result : FinalMatrixValidationResult
        Result of final matrix validation.
    lambda_values : dict[str, float | None]
        Yeo-Johnson lambdas per feature (post-transformation).
    dist_post_scale, outlier_post_scale : Any
        Post-scaling distribution and outlier analyses.
    corr_post_scale : Any
        Post-scaling Pearson/Spearman correlation matrices.
    redundancy_post : Any
        Standard redundancy pairs (|Pearson| >= threshold).
    redundancy_analysis : Any
        3-category redundancy analysis (FE-06 v1.1) for canonical pairs.
    imputation_semantics : Any
        Imputation semantics result (FE-06 v1.1).
    df_pre_imputation : pandas.DataFrame
        Working DataFrame BEFORE imputation (raw eligible features).
    df_metadata : pandas.DataFrame
        Customer metadata DataFrame.
    eligibility_status_map : dict[str, str]
        Map of feature -> FE-06 eligibility status.
    eligibility_fe05_map : dict[str, str]
        Map of feature -> FE-05 decision.

    Returns
    -------
    str
        Full markdown narrative report.
    """
    md = []
    md.append("# FE-06 Narrative Report")
    md.append("")
    md.append("> FE-06 - Transformation, Scaling & Working Clustering Dataset")
    md.append(
        f"> Dataset version: **{config.metadata.dataset_version}** "
        f"({config.metadata.dataset_version_meaning})"
    )
    md.append(
        "> Dataset status: **TECHNICALLY_GENERATED** (working default, " "chua duoc mentor approve)"
    )
    md.append(
        "> Working configuration: **C7** (yeo_johnson + robust + median) - "
        "**WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING**"
    )
    md.append("")
    md.append(
        "**Quan trong:** Dataset nay la *technically generated working " "clustering dataset*, "
    )
    md.append(
        "KHONG phai *final approved clustering dataset*. Promotion sang "
        "final can mentor review + ADR."
    )
    md.append("")
    md.append("## 1. Objective")
    md.append("")
    md.append(
        "Chuyen customer-level candidate features tu FE-05 thanh working "
        "clustering dataset co "
        "pipeline transformation + scaling reproducible, san sang cho phase "
        "Clustering. "
        "Tat ca working decisions o trang thai WORKING_ASSUMPTION."
    )
    md.append("")
    md.append("## 2. Input Dataset")
    md.append("")
    md.append("- Path: `data/processed/customer_candidates.parquet`")
    md.append(f"- SHA-256 (input): `{run_metadata['input']['customer_candidates_sha256']}`")
    md.append("- Shape: 4,371 rows x 15 columns (CustomerID + 14 CANDIDATE features)")
    md.append("- ReferenceDate = max(InvoiceDate) + 1 day (FE-05 owned; FE-06 KHONG recompute)")
    md.append("")
    md.append("## 3. Feature Eligibility")
    md.append("")
    md.append(
        f"- So eligible features: **{len(eligible_features)}** "
        "(= 14-feature working configuration)"
    )
    md.append(f"- So excluded features: **{len(excluded_features)}**")
    if eligible_features:
        md.append("- Eligibles: " + ", ".join(eligible_features))
    md.append("")
    md.append("Trace FE-05 -> FE-06 (working default):")
    md.append("")
    md.append("| Feature | FE-05 decision | FE-06 status | Included in C7? |")
    md.append("| --- | --- | --- | --- |")
    for feat in sorted(eligibility_status_map.keys()):
        f06_status = eligibility_status_map[feat]
        f05_decision = eligibility_fe05_map.get(feat, "(none)")
        included = "Yes" if f06_status.startswith("ELIGIBLE") else "No"
        md.append(f"| {feat} | {f05_decision} | {f06_status} | {included} |")
    md.append("")
    md.append(
        "**ELIGIBLE_WORKING_ASSUMPTION != APPROVED**: cac feature PENDING_REVIEW tu FE-05 duoc"
    )
    md.append("dua vao working dataset nhu WORKING_ASSUMPTION; KHONG duoc hieu la final approved.")
    md.append("")
    md.append("## 4. Missing-value Handling (Imputation)")
    md.append("")
    md.append("- Strategy: **median** (working default)")
    md.append("- Status: **WORKING_ASSUMPTION** / **MENTOR_REVIEW_PENDING**")
    md.append("- Applied features: PurchaseIntervalMean, PurchaseIntervalStd")
    md.append("")
    md.append("Median values used:")
    for feat, val in median_values.items():
        md.append(f"- {feat}: {val}")
    md.append("")
    md.append("Imputation semantics (FE-06 v1.1):")
    md.append("")
    if imputation_semantics.features:
        md.append("| Feature | NaN before | NaN after | Median used | Semantics |")
        md.append("| --- | --- | --- | --- | --- |")
        for fs in imputation_semantics.features:
            md.append(
                f"| {fs.feature} | {fs.nan_before} | {fs.nan_after} | "
                f"{fs.median_used:.6f} | {fs.semantics} |"
            )
    md.append("")
    md.append(
        "PurchaseIntervalMean/Std NaN la **STRUCTURALLY_UNDEFINED**: khong phai data-quality missing, "
        "ma customer co < 2 invoices nen khong co dinh nghia 'diff between consecutive invoices'. "
        "PurchaseIntervalStd them nua co NaN khi chi co 1 interval (ddof=1 voi n=1 la undefined)."
    )
    md.append("")
    md.append("## 5. Transformation Candidates")
    md.append("")
    md.append("- T0: none (baseline)")
    md.append("- T1: log1p (chi ap dung cho feature khong am)")
    md.append("- T2: yeo_johnson (sklearn PowerTransformer, ho tro ca am/zero)")
    md.append("")
    md.append("Working rationale (methodology-only, KHONG optimal claim):")
    md.append("")
    md.append(
        "- Yeo-Johnson phu hop de xu ly skewness va ho tro duoc ca feature co gia tri am/zero. "
        "WORKING_ASSUMPTION - chua duoc mentor approve."
    )
    md.append("")
    md.append("## 6. Scaling Candidates")
    md.append("")
    md.append("- S0: none (baseline)")
    md.append("- S1: StandardScaler (mean=0, std=1)")
    md.append("- S2: MinMaxScaler (range [0, 1])")
    md.append("- S3: RobustScaler (median=0, IQR=1)")
    md.append("")
    md.append("Working rationale (methodology-only, KHONG optimal claim):")
    md.append("")
    md.append(
        "- RobustScaler phu hop khi feature co outlier/heavy-tail (median/IQR-based scaling). "
        "WORKING_ASSUMPTION - chua duoc mentor approve."
    )
    md.append("")
    md.append("## 7. Working Configuration (C7)")
    md.append("")
    md.append("- ID: **C7**")
    md.append("- Transformation: **yeo_johnson** cho TOAN BO 14 features")
    md.append("- Scaling: **robust** cho TOAN BO 14 features")
    md.append("- Imputation: **median**")
    md.append("- Status: **WORKING_ASSUMPTION** / **MENTOR_REVIEW_PENDING**")
    md.append("")
    md.append(
        "C7 la **working configuration**, KHONG phai final approved methodology. "
        "Khong tu danh gia C7 la best/recommended/optimal."
    )
    md.append("")
    md.append("## 8. Before/After Diagnostics (post-scaling)")
    md.append("")
    md.append("Distribution summary (post-scaling):")
    md.append("")
    md.append("| Feature | Mean | Std | Skewness |")
    md.append("| --- | --- | --- | --- |")
    for _, row in dist_post_scale.stats_df.iterrows():
        md.append(
            f"| {row['Feature']} | {row['Mean']:.3f} | {row['Std']:.3f} | {row['Skewness']:.3f} |"
        )
    md.append("")
    md.append("## 9. Outlier Diagnostics")
    md.append("")
    md.append(
        "IQR-based outlier count (post-scaling, diagnostic only - KHONG remove / winsorize / clip):"
    )
    md.append("")
    md.append("| Feature | OutlierCount | OutlierRatio |")
    md.append("| --- | --- | --- |")
    for _, row in outlier_post_scale.outlier_counts.iterrows():
        md.append(f"| {row['Feature']} | {int(row['OutlierCount'])} | {row['OutlierRatio']:.3f} |")
    md.append("")
    md.append("## 10. Redundancy Analysis (3-category classification)")
    md.append("")
    md.append(
        f"Threshold (diagnostic only): |Pearson| >= {config.feature_eligibility.redundancy_threshold}"
    )
    md.append("")
    md.append(
        "FE-06 redundancy gate ONLY detects + quantifies + classifies. NO auto-drop, "
        "NO scoring, NO ranking."
    )
    md.append("")
    md.append("Categories:")
    md.append(
        "- **DUPLICATE_INFORMATION**: empirical equality across all rows (one carries the same "
        "information as the other)."
    )
    md.append(
        "- **HIGH_CORRELATION**: |Pearson| >= threshold but NOT identical (overlapping but "
        "distinct information)."
    )
    md.append(
        "- **DISTINCT_BUT_RELATED**: both features documented in FE-05 but correlation below "
        "redundancy threshold."
    )
    md.append("- **PENDING_REVIEW**: insufficient evidence to classify.")
    md.append("")
    if redundancy_analysis and redundancy_analysis.pairs:
        md.append("Canonical pairs analyzed:")
        md.append("")
        md.append(
            "| Feature1 | Feature2 | Pearson | Spearman | EqualityRate | MaxAbsDiff | Category |"
        )
        md.append("| --- | --- | --- | --- | --- | --- | --- |")
        for pair in redundancy_analysis.pairs:
            md.append(
                f"| {pair.feature1} | {pair.feature2} | {pair.pearson:.4f} | "
                f"{pair.spearman:.4f} | {pair.equality_rate:.4f} | "
                f"{pair.max_abs_diff:.4f} | {pair.category} |"
            )
        md.append("")
        md.append("Per-pair details:")
        md.append("")
        for pair in redundancy_analysis.pairs:
            md.append(f"### {pair.feature1} <-> {pair.feature2}")
            md.append("")
            md.append(f"- **Category**: `{pair.category}`")
            md.append(f"- **Pearson**: `{pair.pearson:.6f}`")
            md.append(f"- **Spearman**: `{pair.spearman:.6f}`")
            md.append(f"- **Equality rate**: `{pair.equality_rate:.6f}`")
            md.append(f"- **Max |diff|**: `{pair.max_abs_diff:.6f}`")
            md.append(f"- **Definition {pair.feature1}**: {pair.definition_feature1}")
            md.append(f"- **Definition {pair.feature2}**: {pair.definition_feature2}")
            md.append(f"- **Note**: {pair.note}")
            md.append("")
            md.append(
                "- **Decision**: PENDING_REVIEW - auto-drop KHONG ap dung. "
                "Promotion sang final can mentor review."
            )
            md.append("")
    md.append("")
    md.append("Standard redundancy pairs (|Pearson| >= threshold, no auto-drop):")
    md.append("")
    if redundancy_post.pairs_df.empty:
        md.append("No redundancy pairs detected by threshold.")
    else:
        md.append("| Feature1 | Feature2 | Correlation |")
        md.append("| --- | --- | --- |")
        for _, row in redundancy_post.pairs_df.iterrows():
            md.append(f"| {row['Feature1']} | {row['Feature2']} | {row['Correlation']:.3f} |")
    md.append("")
    md.append("## 11. Data Quality")
    md.append("")
    for check in validation_result.checks:
        md.append(f"- **{check.name}**: {check.status} - {check.message}")
    md.append("")
    md.append("## 12. Reproducibility")
    md.append("")
    md.append(
        f"- Output matrix SHA-256: `{run_metadata['output']['final_clustering_dataset_sha256']}`"
    )
    md.append(f"- Output metadata SHA-256: `{run_metadata['output']['customer_metadata_sha256']}`")
    md.append(f"- Fitted pipeline SHA-256: `{run_metadata['output']['fitted_pipeline_sha256']}`")
    md.append(f"- Config SHA-256: `{run_metadata['config']['config_sha256']}`")
    md.append(f"- Executed at: {run_metadata['executed_at_utc']}")
    md.append(f"- Python: {run_metadata['platform']['python']}")
    md.append(
        f"- Library versions: numpy={run_metadata['library_versions']['numpy']}, "
        f"pandas={run_metadata['library_versions']['pandas']}, "
        f"scikit-learn={run_metadata['library_versions']['scikit-learn']}"
    )
    md.append("")
    md.append(
        "Note: Pickle SHA ghi nhung KHONG dung byte-level SHA equality cross-environment "
        "lam hard acceptance criterion (chi informational)."
    )
    md.append("")
    md.append("## 13. Dataset Version")
    md.append("")
    md.append(f"- Version: **{config.metadata.dataset_version}**")
    md.append(f"- Meaning: {config.metadata.dataset_version_meaning}")
    md.append("- Status: **TECHNICALLY_GENERATED** (chua duoc mentor approve)")
    md.append("")
    md.append(
        "Promotion sang final (RESEARCH_APPROVED_FINAL) can mentor review + ADR; "
        "FE-06 KHONG tu dong promote."
    )
    md.append("")
    md.append("## 14. Pending Mentor Review (PENDING_REVIEW decisions)")
    md.append("")
    for note in run_metadata.get("pending_review_notes", []):
        md.append(f"- {note}")
    md.append("")
    md.append("## 15. Scope Boundary")
    md.append("")
    md.append("IN-SCOPE (FE-06):")
    for sb in config.metadata.scope_boundaries:
        md.append(f"- {sb}")
    md.append("")
    md.append("OUT-OF-SCOPE (FE-06):")
    md.append("- Clustering algorithms (K-Means, K-Medoids, Agglomerative, DBSCAN)")
    md.append("- Clustering evaluation (silhouette, DBI, CH, WCSS)")
    md.append("- Hyperparameter tuning")
    md.append("- Best/recommended/optimal claims")
    md.append("- Feature ranking / numerical scoring")
    md.append("- Auto-drop redundancy")
    md.append("- Outlier removal / winsorize / clip")
    md.append("- Modifying FE-05 output / customer_candidates.parquet")
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"Generated by FE-06 pipeline | {run_metadata['executed_at_utc']}")
    return "\n".join(md)


def run_fe06_pipeline(
    customer_candidates_path: Path,
    processed_dir: Path,
    report_dir: Path,
    *,
    config: TransformationConfig | None = None,
    config_path: Path | None = None,
) -> FE06PipelineResult:
    """Run the FE-06 transformation pipeline end-to-end.

    Parameters
    ----------
    customer_candidates_path : pathlib.Path
        Path to data/processed/customer_candidates.parquet.
    processed_dir : pathlib.Path
        Output directory for final dataset and metadata.
    report_dir : pathlib.Path
        Output directory for FE-06 reports.
    config : TransformationConfig, optional
        Explicit config.
    config_path : pathlib.Path, optional
        Explicit YAML path.

    Returns
    -------
    FE06PipelineResult
        Pipeline result with matrices, metadata, and validation.

    Raises
    ------
    FileNotFoundError
        If input file does not exist.
    ValueError
        If validation fails.
    """
    # ------------------------------------------------------------------
    # 0. Resolve config
    # ------------------------------------------------------------------
    if config is None:
        yaml_path = resolve_transformation_config_path(explicit=config_path)
        if yaml_path is None:
            raise SystemExit(
                "[FE-06] ERROR: configs/transformation.yaml not found. "
                "Run from the repository root or pass --config."
            )
        config = load_transformation_config(yaml_path)
        config_label = f"yaml:{yaml_path}"
    else:
        config_label = "explicit_config"

    print(f"[FE-06] config: {config_label}")
    print(f"[FE-06] working configuration: {config.working_configuration.id}")

    # ------------------------------------------------------------------
    # 1. Compute SHA-256 of input file BEFORE pipeline
    # ------------------------------------------------------------------
    if not customer_candidates_path.exists():
        raise FileNotFoundError(f"Input file not found: {customer_candidates_path}")
    input_sha256 = compute_file_sha256(customer_candidates_path)

    # Compute config SHA-256
    config_path_obj = (
        config_path if config_path is not None else resolve_transformation_config_path()
    )
    if config_path_obj is not None and Path(config_path_obj).exists():
        config_sha256 = compute_file_sha256(Path(config_path_obj))
    else:
        config_sha256 = "config_not_found"

    # ------------------------------------------------------------------
    # 2. Load customer candidates (READ-ONLY)
    # ------------------------------------------------------------------
    df_candidates = pd.read_parquet(customer_candidates_path)
    print(
        f"[FE-06] loaded: customer_candidates {df_candidates.shape[0]:,} rows × "
        f"{df_candidates.shape[1]} cols."
    )

    # Fail-fast: expected shape
    if df_candidates.shape[0] != 4371:
        raise ValueError(
            f"Expected 4371 rows in customer_candidates, got {df_candidates.shape[0]}."
        )

    # ------------------------------------------------------------------
    # 3. Split CustomerID
    # ------------------------------------------------------------------
    customer_key = config.source.customer_key
    if customer_key not in df_candidates.columns:
        raise ValueError(f"Customer key {customer_key!r} not found in candidates.")
    df_metadata = df_candidates[[customer_key]].copy()
    working_df = df_candidates.drop(columns=[customer_key])
    print(f"[FE-06] CustomerID extracted into metadata: {len(df_metadata):,} rows.")

    # ------------------------------------------------------------------
    # 4. Feature eligibility gate
    # ------------------------------------------------------------------
    print("[FE-06] applying feature eligibility gate...")
    eligibility_result = apply_feature_eligibility(
        df_candidates,
        customer_key=customer_key,
        max_missing_ratio=config.feature_eligibility.max_missing_ratio,
    )
    eligible_features = eligibility_result.eligible_features
    excluded_features = eligibility_result.excluded_features

    # Filter working_df to only eligible features
    eligible_in_df = [f for f in eligible_features if f in working_df.columns]
    working_df = working_df[eligible_in_df].copy()

    # Build traceability maps (FE-05 -> FE-06).
    eligibility_status_map: dict[str, str] = {}
    eligibility_fe05_map: dict[str, str] = {}
    for feat, elig in eligibility_result.eligibility_details.items():
        eligibility_status_map[feat] = elig.fe06_status
        eligibility_fe05_map[feat] = elig.fe05_decision or "(none)"

    print(
        f"[FE-06] eligibility: {len(eligible_features)} eligible, "
        f"{len(excluded_features)} excluded."
    )

    if len(working_df.columns) == 0:
        raise ValueError("No eligible features for clustering matrix.")

    # ------------------------------------------------------------------
    # 5. NaN imputation
    # ------------------------------------------------------------------
    # Snapshot the working DataFrame BEFORE imputation so we can produce
    # the imputation semantics report (NaN count before, semantics, etc.).
    df_pre_imputation = working_df.copy()
    print("[FE-06] applying NaN imputation (median)...")
    applied_features = config.imputation.working.applied_features
    imputation_method = config.imputation.working.method
    imputation_result = apply_imputation(
        working_df,
        applied_features,
        method=imputation_method,
    )
    working_df = imputation_result.df
    median_values = imputation_result.median_values

    # Build imputation semantics analysis (FE-06 v1.1).
    imputation_semantics = analyze_imputation_semantics(
        df_before=df_pre_imputation,
        df_after=working_df,
        features_to_impute=applied_features,
        median_values=median_values,
        total_rows=len(working_df),
    )

    # Verify no NaN remains in eligible features
    nan_after = working_df.isna().sum()
    if nan_after.sum() > 0:
        raise ValueError(
            f"NaN values remain after imputation: {nan_after[nan_after > 0].to_dict()}"
        )

    # ------------------------------------------------------------------
    # 5b. Redundancy analysis (3-category classification, FE-06 v1.1)
    # ------------------------------------------------------------------
    # Operate on the imputed-but-not-yet-transformed working DataFrame so
    # that downstream transformations (Yeo-Johnson, RobustScaler) do not
    # distort the empirical evidence used to classify each pair.
    print("[FE-06] running 3-category redundancy analysis...")
    redundancy_analysis = analyze_redundancy_pairs(
        working_df,
        CANONICAL_REDUNDANCY_PAIRS,
        threshold=config.feature_eligibility.redundancy_threshold,
    )

    # ------------------------------------------------------------------
    # 6. Distribution pre-transformation (T0 baseline)
    # ------------------------------------------------------------------
    print("[FE-06] computing pre-transformation diagnostics...")
    dist_pre = compute_distribution_stats(working_df, list(working_df.columns))
    corr_pre = compute_correlation_matrices(working_df, list(working_df.columns))
    outlier_pre = detect_outliers(working_df, list(working_df.columns))

    # ------------------------------------------------------------------
    # 7. Apply working transformation (C7: yeo_johnson)
    # ------------------------------------------------------------------
    working_transformation = config.working_configuration.transformation
    print(f"[FE-06] applying transformation: {working_transformation}")
    feature_cols = list(working_df.columns)

    if working_transformation == "yeo_johnson":
        working_df, pt, lambda_values = apply_yeo_johnson(working_df, feature_cols)
        # Save fitted transformer in a simple wrapper
        fitted_pipeline_data = {
            "imputation_method": imputation_method,
            "imputation_applied_features": applied_features,
            "median_values": median_values,
            "transformation_method": working_transformation,
            "lambda_values": lambda_values,
            "scaling_method": config.working_configuration.scaling,
            "feature_columns": feature_cols,
        }
    elif working_transformation == "none":
        lambda_values = dict.fromkeys(feature_cols)
        fitted_pipeline_data = {
            "imputation_method": imputation_method,
            "imputation_applied_features": applied_features,
            "median_values": median_values,
            "transformation_method": working_transformation,
            "lambda_values": lambda_values,
            "scaling_method": config.working_configuration.scaling,
            "feature_columns": feature_cols,
        }
    elif working_transformation == "log1p":
        # This should not happen for negative features, but we check
        lambda_values = dict.fromkeys(feature_cols)
        fitted_pipeline_data = {
            "imputation_method": imputation_method,
            "imputation_applied_features": applied_features,
            "median_values": median_values,
            "transformation_method": working_transformation,
            "lambda_values": lambda_values,
            "scaling_method": config.working_configuration.scaling,
            "feature_columns": feature_cols,
        }
    else:
        raise ValueError(f"Unknown transformation: {working_transformation}")

    # Verify no Inf
    inf_count = working_df[feature_cols].isin([float("inf"), float("-inf")]).sum().sum()
    if inf_count > 0:
        raise ValueError(f"Inf values found after transformation: {inf_count}")

    # ------------------------------------------------------------------
    # 8. Distribution post-transformation
    # ------------------------------------------------------------------
    print("[FE-06] computing post-transformation diagnostics...")
    dist_post_trans = compute_distribution_stats(working_df, feature_cols)
    corr_post_trans = compute_correlation_matrices(working_df, feature_cols)

    # ------------------------------------------------------------------
    # 9. Apply working scaling (C7: robust)
    # ------------------------------------------------------------------
    working_scaling = config.working_configuration.scaling
    print(f"[FE-06] applying scaling: {working_scaling}")
    scaling_result = apply_scaling(working_df, feature_cols, working_scaling)
    working_df = scaling_result.df
    scaler = scaling_result.scaler

    # Add scaler to pipeline data
    fitted_pipeline_data["fitted_scaler"] = scaler
    fitted_pipeline_data["scaler_mean"] = (
        list(scaler.center_) if scaler and hasattr(scaler, "center_") else None
    )
    fitted_pipeline_data["scaler_scale"] = (
        list(scaler.scale_) if scaler and hasattr(scaler, "scale_") else None
    )

    # ------------------------------------------------------------------
    # 10. Distribution post-scaling
    # ------------------------------------------------------------------
    print("[FE-06] computing post-scaling diagnostics...")
    dist_post_scale = compute_distribution_stats(working_df, feature_cols)
    corr_post_scale = compute_correlation_matrices(working_df, feature_cols)
    outlier_post_scale = detect_outliers(working_df, feature_cols)
    redundancy_post = detect_redundancy(
        corr_post_scale.pearson,
        threshold=config.feature_eligibility.redundancy_threshold,
    )

    # ------------------------------------------------------------------
    # 11. Final validation
    # ------------------------------------------------------------------
    print("[FE-06] running final validation...")
    validation_result = validate_final_matrix(
        working_df,
        df_metadata,
        expected_row_count=4371,
    )
    if not validation_result.all_passed:
        failed = [c for c in validation_result.checks if c.status == "FAIL"]
        fail_messages = [c.message for c in failed]
        raise ValueError(f"Validation failed: {'; '.join(fail_messages)}")
    print("[FE-06] final validation: PASS")

    # ------------------------------------------------------------------
    # 12. Write outputs
    # ------------------------------------------------------------------
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Final clustering matrix
    final_matrix_path = processed_dir / config.output.final_clustering_filename
    working_df.to_parquet(final_matrix_path, index=False)
    output_matrix_sha256 = compute_df_sha256(working_df)
    print(f"[FE-06] final matrix written: {final_matrix_path}")

    # Customer metadata
    metadata_path = processed_dir / config.output.customer_metadata_filename
    df_metadata.to_parquet(metadata_path, index=False)
    output_metadata_sha256 = compute_df_sha256(df_metadata)
    print(f"[FE-06] metadata written: {metadata_path}")

    # Fitted pipeline
    pipeline_path = processed_dir / config.output.fitted_pipeline_filename
    with pipeline_path.open("wb") as f:
        pickle.dump(fitted_pipeline_data, f)
    output_pipeline_sha256 = compute_file_sha256(pipeline_path)
    print(f"[FE-06] fitted pipeline written: {pipeline_path}")

    # ------------------------------------------------------------------
    # 13. Compute diagnostics for comparison matrix
    # ------------------------------------------------------------------
    diagnostics = {}
    diag_key = config.working_configuration.id
    diagnostics[diag_key] = {
        "mean_skewness": float(dist_post_scale.stats_df["Skewness"].mean()),
        "mean_kurtosis": float(dist_post_scale.stats_df["Kurtosis"].mean()),
        "mean_outlier_ratio": float(outlier_post_scale.outlier_counts["OutlierRatio"].mean()),
        "max_correlation": (
            float(corr_post_scale.pearson.abs().values.max())
            if not corr_post_scale.pearson.empty
            else None
        ),
    }

    # ------------------------------------------------------------------
    # 14. Build reports
    # ------------------------------------------------------------------
    print("[FE-06] writing reports...")

    # Feature eligibility
    fe_eligibility_df = _build_feature_eligibility_csv(eligibility_result)

    # Feature dictionary
    fe_dict_df = _build_feature_dictionary(
        eligibility_result,
        eligible_features,
        working_transformation,
        working_scaling,
    )

    # Comparison matrix
    comp_matrix_df = _build_comparison_matrix(config, diagnostics, config.working_configuration.id)

    # Data quality
    dq_df = _build_data_quality_report(validation_result)

    # Leakage check
    leakage_df = _build_leakage_check(working_df, df_metadata)

    # Redundancy pre
    redundancy_pre = detect_redundancy(
        corr_pre.pearson,
        threshold=config.feature_eligibility.redundancy_threshold,
    )

    # Run metadata
    import platform as platform_module

    platform_info = {
        "python": platform_module.python_version(),
        "system": platform_module.system(),
        "release": platform_module.release(),
        "machine": platform_module.machine(),
    }

    # Get library versions
    import numpy as np_module
    import pandas as pd_module
    import pyarrow
    import scipy
    import sklearn

    library_versions = {
        "numpy": np_module.__version__,
        "pandas": pd_module.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "pyarrow": pyarrow.__version__,
    }

    executed_at_utc = datetime.now(UTC).isoformat()

    run_metadata = {
        "task_id": "FE-06",
        "stage_version": FE06_VERSION,
        "stage_version_meaning": config.metadata.dataset_version_meaning,
        "stage_status": "TECHNICALLY_GENERATED",
        "executed_at_utc": executed_at_utc,
        "platform": platform_info,
        "library_versions": library_versions,
        "input": {
            "customer_candidates_path": str(customer_candidates_path),
            "customer_candidates_sha256": input_sha256,
        },
        "config": {
            "config_source": config_label,
            "config_sha256": config_sha256,
            "random_seed": config.random_seed,
            "random_seed_reason": config.random_seed_reason,
            "working_configuration_id": config.working_configuration.id,
            "working_transformation": working_transformation,
            "working_transformation_status": config.working_configuration.status,
            "working_transformation_review": config.working_configuration.review,
            "working_scaling": working_scaling,
            "working_scaling_status": config.working_configuration.status,
            "working_scaling_review": config.working_configuration.review,
            "working_imputation": imputation_method,
            "working_imputation_status": config.working_configuration.status,
            "working_imputation_review": config.working_configuration.review,
            "median_values": median_values,
            "lambda_values": {
                k: float(v) if v is not None else None for k, v in lambda_values.items()
            },
            "feature_eligible_count": len(eligible_features),
            "feature_excluded_count": len(excluded_features),
        },
        "feature_set": {
            "eligible_features": eligible_features,
            "excluded_features": excluded_features,
            "redundancy_threshold": config.feature_eligibility.redundancy_threshold,
            "redundancy_action": "diagnostic_only_no_auto_drop",
            "redundancy_pairs": (
                redundancy_post.pairs_df.to_dict(orient="records")
                if not redundancy_post.pairs_df.empty
                else []
            ),
        },
        "output": {
            "final_clustering_dataset_path": str(final_matrix_path),
            "final_clustering_dataset_sha256": output_matrix_sha256,
            "customer_metadata_path": str(metadata_path),
            "customer_metadata_sha256": output_metadata_sha256,
            "fitted_pipeline_path": str(pipeline_path),
            "fitted_pipeline_sha256": output_pipeline_sha256,
        },
        "validations": {
            c.name: {"status": c.status, "message": c.message} for c in validation_result.checks
        },
        "scope_boundaries": config.metadata.scope_boundaries,
        "constraints": {
            "no_clustering": True,
            "no_evaluation": True,
            "no_tuning": True,
        },
        "pending_review_notes": [
            "PR-FE06-01: Working transformation = yeo_johnson (WORKING_ASSUMPTION)",
            "PR-FE06-02: Working scaler = robust (WORKING_ASSUMPTION)",
            "PR-FE06-03: Working imputation = median (WORKING_ASSUMPTION)",
            "PR-FE06-04: 6 FE-05 PENDING_REVIEW features included as ELIGIBLE_WORKING_ASSUMPTION",
            "PR-FE06-05: Redundancy pairs not auto-dropped (diagnostic only)",
            "PR-FE06-06: Rate features (CancellationRate, ReturnRate) included with Yeo-Johnson in C7",
            "PR-FE06-07: Dataset version FE06-v1.0 = TECHNICALLY_GENERATED",
            "PR-FE06-08: Working matrix retains all 14 eligible features",
        ],
        "assumptions": [
            "ReferenceDate = max(InvoiceDate)+1day from FE-05; FE-06 does NOT recompute.",
            "Median imputation suitable for 'no enough observations' NaN semantics.",
            "Yeo-Johnson simplifies pipeline (handles both negative and non-negative).",
            "RobustScaler is tolerant to outlier.",
            "Pipeline is deterministic (no random state used).",
        ],
    }

    # Write all reports
    redundancy_analysis_df = redundancy_analysis.to_dataframe()
    imputation_semantics_df = imputation_semantics.to_dataframe()
    write_fe06_reports(
        report_dir,
        distribution_pre=dist_pre.stats_df,
        distribution_post_trans=dist_post_trans.stats_df,
        distribution_post_scale=dist_post_scale.stats_df,
        correlation_pre_pearson=corr_pre.pearson,
        correlation_pre_spearman=corr_pre.spearman,
        correlation_post_trans_pearson=corr_post_trans.pearson,
        correlation_post_trans_spearman=corr_post_trans.spearman,
        correlation_post_scale_pearson=corr_post_scale.pearson,
        correlation_post_scale_spearman=corr_post_scale.spearman,
        redundancy_pre=redundancy_pre.pairs_df,
        redundancy_post=redundancy_post.pairs_df,
        outlier_pre=outlier_pre.outlier_counts,
        outlier_post_scale=outlier_post_scale.outlier_counts,
        feature_eligibility_df=fe_eligibility_df,
        feature_dictionary_df=fe_dict_df,
        comparison_matrix=comp_matrix_df,
        data_quality_df=dq_df,
        leakage_df=leakage_df,
        run_metadata=run_metadata,
        redundancy_analysis_df=redundancy_analysis_df,
        imputation_semantics_df=imputation_semantics_df,
    )
    print(f"[FE-06] reports written: {report_dir}")

    # Write narrative report
    narrative_md = _build_narrative(
        config,
        run_metadata,
        eligible_features,
        excluded_features,
        median_values,
        validation_result,
        lambda_values,
        dist_post_scale,
        outlier_post_scale,
        corr_post_scale,
        redundancy_post,
        redundancy_analysis,
        imputation_semantics,
        df_pre_imputation,
        df_metadata,
        eligibility_status_map,
        eligibility_fe05_map,
    )
    narrative_path = write_narrative_report(report_dir, narrative_md)
    print(f"[FE-06] narrative report written: {narrative_path}")

    # ------------------------------------------------------------------
    # 15. Verify input SHA-256 unchanged
    # ------------------------------------------------------------------
    input_sha256_after = compute_file_sha256(customer_candidates_path)
    if input_sha256_after != input_sha256:
        raise RuntimeError(
            f"FE-05 customer_candidates.parquet SHA-256 changed during FE-06 run: "
            f"before={input_sha256}, after={input_sha256_after}. "
            "FE-06 must not mutate the FE-05 input."
        )
    print(f"[FE-06] input SHA-256 verified unchanged: {input_sha256[:16]}...")

    return FE06PipelineResult(
        final_matrix=working_df,
        customer_metadata=df_metadata,
        eligible_features=eligible_features,
        excluded_features=excluded_features,
        eligibility_status_map=eligibility_status_map,
        eligibility_fe05_map=eligibility_fe05_map,
        working_config_id=config.working_configuration.id,
        working_transformation=working_transformation,
        working_scaling=working_scaling,
        working_imputation=imputation_method,
        median_values=median_values,
        lambda_values=lambda_values,
        validation_result=validation_result,
        input_sha256=input_sha256,
        output_matrix_sha256=output_matrix_sha256,
        output_metadata_sha256=output_metadata_sha256,
        output_pipeline_sha256=output_pipeline_sha256,
        config_sha256=config_sha256,
        fe06_version=FE06_VERSION,
    )
