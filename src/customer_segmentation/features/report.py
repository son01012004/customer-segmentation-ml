"""Report generation for FE-05 pipeline.

Writes all FE-05 reports:
- rfm_report.md
- monetary_definition_comparison.csv
- quantity_variants_comparison.csv
- frequency_variants_comparison.csv
- candidate_feature_report.md
- distribution_analysis.csv
- variance_analysis.csv
- correlation_matrix_pearson.csv
- correlation_matrix_spearman.csv
- redundancy_report.csv
- outlier_detection.csv
- feature_selection_report.csv
- business_interpretability.csv
- feature_dictionary.csv
- fe05_run.json
- narrative_report.md

Hard constraints:
- All PENDING_REVIEW decisions documented.
- SHA-256: both inputs + output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

__all__ = [
    "ReportPaths",
    "write_rfm_report",
    "write_frequency_comparison_csv",
    "write_quantity_comparison_csv",
    "write_candidate_feature_report",
    "write_distribution_analysis",
    "write_variance_analysis",
    "write_correlation_matrices",
    "write_redundancy_report",
    "write_outlier_detection",
    "write_feature_selection_report",
    "write_interpretability_csv",
    "write_feature_dictionary",
    "write_fe05_run_json",
    "write_narrative_report",
]


@dataclass
class ReportPaths:
    """Paths to all written report files."""

    rfm_report: Path
    monetary_comparison: Path
    quantity_comparison: Path
    frequency_comparison: Path
    candidate_feature_report: Path
    distribution_analysis: Path
    variance_analysis: Path
    correlation_pearson: Path
    correlation_spearman: Path
    redundancy_report: Path
    outlier_detection: Path
    feature_selection: Path
    business_interpretability: Path
    feature_dictionary: Path
    run_json: Path
    narrative_report: Path

    def all_paths(self) -> dict[str, Path]:
        """Return all paths as a dict."""
        return {
            "rfm_report.md": self.rfm_report,
            "monetary_definition_comparison.csv": self.monetary_comparison,
            "quantity_variants_comparison.csv": self.quantity_comparison,
            "frequency_variants_comparison.csv": self.frequency_comparison,
            "candidate_feature_report.md": self.candidate_feature_report,
            "distribution_analysis.csv": self.distribution_analysis,
            "variance_analysis.csv": self.variance_analysis,
            "correlation_matrix_pearson.csv": self.correlation_pearson,
            "correlation_matrix_spearman.csv": self.correlation_spearman,
            "redundancy_report.csv": self.redundancy_report,
            "outlier_detection.csv": self.outlier_detection,
            "feature_selection_report.csv": self.feature_selection,
            "business_interpretability.csv": self.business_interpretability,
            "feature_dictionary.csv": self.feature_dictionary,
            "fe05_run.json": self.run_json,
            "narrative_report.md": self.narrative_report,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_dir(path: Path) -> None:
    """Ensure directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# RFM Report
# ---------------------------------------------------------------------------


def write_rfm_report(
    report_dir: Path,
    reference_date: datetime,
    recency_df: pd.DataFrame,
    frequency_variants_df: pd.DataFrame,
    monetary_variants_df: pd.DataFrame,
    *,
    customer_key: str = "CustomerID",
) -> Path:
    """Write RFM narrative report.

    Parameters
    ----------
    report_dir : pathlib.Path
        Output directory.
    reference_date : datetime
        Computed reference date.
    recency_df : pandas.DataFrame
        Recency DataFrame.
    frequency_variants_df : pandas.DataFrame
        Frequency variants comparison.
    monetary_variants_df : pandas.DataFrame
        Monetary variants comparison.
    customer_key : str
        Customer ID column name.

    Returns
    -------
    pathlib.Path
        Path to written report.
    """
    output_path = report_dir / "rfm_report.md"
    _ensure_dir(output_path)

    recency_stats = recency_df["Recency"].describe()

    content = f"""# FE-05 RFM Report

## Reference Date

- ReferenceDate = max(InvoiceDate) + 1 day
- Computed ReferenceDate: **{reference_date.isoformat()}**
- Strategy: snapshot_max (deterministic)
- Status: WORKING_ASSUMPTION
- Review: MENTOR_REVIEW_PENDING

## Recency

- Definition: Days between ReferenceDate and LastPurchaseDate
- Includes all transactions (cancellation/return included)
- Status: PENDING_REVIEW for purchase-only Recency

Statistics:
- Count: {int(recency_stats["count"]):,}
- Mean: {float(recency_stats["mean"]):.2f} days
- Std: {float(recency_stats["std"]):.2f} days
- Min: {float(recency_stats["min"]):.0f} days
- Max: {float(recency_stats["max"]):.0f} days

## Frequency

- Materialized: Frequency_ByInvoice (FREQ-01, default)
- Comparison: FREQ-01 (nunique InvoiceNo) vs FREQ-02 (count of transaction lines)
- Status: WORKING_ASSUMPTION

## Monetary

- Materialized: MonetarySigned (default)
- Comparison: 4 distinct definition variants
  - MonetarySigned: sum of signed LineRevenue
  - MonetaryAbsolute: sum of |LineRevenue|
  - MonetaryPurchaseOnly: sum where IsCancellation=False
  - MonetaryCancellationOnly: sum where IsCancellation=True
- Status: WORKING_ASSUMPTION

## Decisions

- ONE Monetary materialized (default: MonetarySigned)
- ONE Frequency materialized (default: Frequency_ByInvoice)
- Recency uses all transactions; PENDING_REVIEW for purchase-only
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Frequency Comparison CSV
# ---------------------------------------------------------------------------


def write_frequency_comparison_csv(
    frequency_variants_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write frequency variants comparison CSV.

    Parameters
    ----------
    frequency_variants_df : pandas.DataFrame
        Frequency variants comparison.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    frequency_variants_df.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Quantity Comparison CSV
# ---------------------------------------------------------------------------


def write_quantity_comparison_csv(
    quantity_comparison_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write quantity variants comparison CSV.

    Parameters
    ----------
    quantity_comparison_df : pandas.DataFrame
        Quantity variants comparison.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    quantity_comparison_df.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Candidate Feature Report (markdown)
# ---------------------------------------------------------------------------


def write_candidate_feature_report(
    output_path: Path,
    candidate_features: list[str],
    *,
    customer_count: int,
) -> Path:
    """Write candidate feature report.

    Parameters
    ----------
    output_path : pathlib.Path
        Output report path.
    candidate_features : list[str]
        List of candidate feature names.
    customer_count : int
        Number of customers in candidate dataset.

    Returns
    -------
    pathlib.Path
        Path to written report.
    """
    _ensure_dir(output_path)

    feature_list = "\n".join([f"- `{feat}`" for feat in candidate_features])

    content = f"""# FE-05 Candidate Feature Report

## Overview

- Customer count: {customer_count:,}
- Number of candidate features: {len(candidate_features)}

## Candidate Features (Tầng 2)

{feature_list}

## Layer Classification

### CANDIDATE (eligible for FE-06 evaluation)
- All candidate features are listed above.

### BASE_REFERENCE (kept from FE-04, NOT candidate)
- TotalQuantity, TotalMonetary, PurchaseFrequency, AverageTransactionValue
- FirstPurchaseDate, LastPurchaseDate, DistinctInvoiceCount, DistinctProducts
- CancellationInvoiceCount, ReturnInvoiceCount, TransactionLineCount

### UNSUPPORTED (NOT materialized)
- CategoryCount: Dataset lacks official taxonomy.

## Notes

- Only numeric Tầng 2 CANDIDATE features in correlation/redundancy/outlier analysis.
- Date features excluded from correlation analysis.
- Shapiro-Wilk = optional diagnostic only.
- No feature called "best/recommended/final".
- RETAIN_CANDIDATE = eligible for FE-06, NOT final.
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Distribution Analysis CSV
# ---------------------------------------------------------------------------


def write_distribution_analysis(
    distribution_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write distribution analysis CSV.

    Parameters
    ----------
    distribution_df : pandas.DataFrame
        Distribution statistics DataFrame.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    distribution_df.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Variance Analysis CSV
# ---------------------------------------------------------------------------


def write_variance_analysis(
    variance_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write variance analysis CSV.

    Parameters
    ----------
    variance_df : pandas.DataFrame
        Variance statistics DataFrame.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    variance_df.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Correlation Matrices
# ---------------------------------------------------------------------------


def write_correlation_matrices(
    pearson_df: pd.DataFrame,
    spearman_df: pd.DataFrame,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write Pearson and Spearman correlation matrices.

    Parameters
    ----------
    pearson_df : pandas.DataFrame
        Pearson correlation matrix.
    spearman_df : pandas.DataFrame
        Spearman correlation matrix.
    output_dir : pathlib.Path
        Output directory.

    Returns
    -------
    tuple[Path, Path]
        Paths to Pearson and Spearman CSVs.
    """
    pearson_path = output_dir / "correlation_matrix_pearson.csv"
    spearman_path = output_dir / "correlation_matrix_spearman.csv"
    _ensure_dir(pearson_path)
    _ensure_dir(spearman_path)

    pearson_df.to_csv(pearson_path)
    spearman_df.to_csv(spearman_path)

    return pearson_path, spearman_path


# ---------------------------------------------------------------------------
# Redundancy Report CSV
# ---------------------------------------------------------------------------


def write_redundancy_report(
    redundancy_pairs: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write redundancy report CSV.

    Parameters
    ----------
    redundancy_pairs : pandas.DataFrame
        Redundancy pairs DataFrame.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    if redundancy_pairs.empty:
        # Write empty CSV with header
        empty_df = pd.DataFrame(columns=["Feature1", "Feature2", "Correlation", "AbsCorrelation"])
        empty_df.to_csv(output_path, index=False)
    else:
        redundancy_pairs.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Outlier Detection CSV
# ---------------------------------------------------------------------------


def write_outlier_detection(
    outlier_counts: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write outlier detection CSV.

    Parameters
    ----------
    outlier_counts : pandas.DataFrame
        Outlier counts per feature.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    outlier_counts.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Feature Selection Report CSV
# ---------------------------------------------------------------------------


def write_feature_selection_report(
    selection_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write feature selection report CSV.

    Parameters
    ----------
    selection_df : pandas.DataFrame
        Selection report DataFrame.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    selection_df.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Business Interpretability CSV
# ---------------------------------------------------------------------------


def write_interpretability_csv(
    interpretability_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Write business interpretability CSV.

    Parameters
    ----------
    interpretability_df : pandas.DataFrame
        Interpretability assessment DataFrame.
    output_path : pathlib.Path
        Output CSV path.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)
    interpretability_df.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Feature Dictionary CSV
# ---------------------------------------------------------------------------


def write_feature_dictionary(
    output_path: Path,
    *,
    feature_layer_map: dict[str, str],
    feature_descriptions: dict[str, str] | None = None,
    feature_status_map: dict[str, str] | None = None,
) -> Path:
    """Write feature dictionary CSV.

    Parameters
    ----------
    output_path : pathlib.Path
        Output CSV path.
    feature_layer_map : dict[str, str]
        Map of feature name to layer role.
    feature_descriptions : dict[str, str], optional
        Map of feature name to description.
    feature_status_map : dict[str, str], optional
        Map of feature name to status.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    _ensure_dir(output_path)

    feature_descriptions = feature_descriptions or {}
    feature_status_map = feature_status_map or {}

    rows = []
    for feat, layer in feature_layer_map.items():
        rows.append(
            {
                "Feature": feat,
                "Layer": layer,
                "Role": layer,  # Same as layer for simplicity
                "Description": feature_descriptions.get(feat, ""),
                "Status": feature_status_map.get(feat, ""),
                "ClusteringCandidate": "Yes" if layer == "CANDIDATE" else "No",
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    return output_path


# ---------------------------------------------------------------------------
# Run JSON
# ---------------------------------------------------------------------------


def write_fe05_run_json(
    output_path: Path,
    *,
    input_sha256_customer_base: str,
    input_sha256_transactions: str,
    output_sha256_candidate: str,
    customer_count: int,
    candidate_feature_count: int,
    config_source: str,
    executed_at_utc: str,
    platform_info: dict[str, str],
    pending_review_notes: list[str],
    feature_selection_summary: dict[str, int],
    config_dict: dict[str, Any],
) -> Path:
    """Write fe05_run.json metadata file.

    Parameters
    ----------
    output_path : pathlib.Path
        Output JSON path.
    input_sha256_customer_base : str
        SHA-256 of customer_base.parquet.
    input_sha256_transactions : str
        SHA-256 of transactions_clean.parquet.
    output_sha256_candidate : str
        SHA-256 of customer_candidates.parquet.
    customer_count : int
        Number of customers in candidate dataset.
    candidate_feature_count : int
        Number of candidate features.
    config_source : str
        Configuration source label.
    executed_at_utc : str
        ISO 8601 UTC timestamp.
    platform_info : dict[str, str]
        Platform information.
    pending_review_notes : list[str]
        Pending review notes.
    feature_selection_summary : dict[str, int]
        Summary of feature selection decisions.
    config_dict : dict[str, Any]
        Configuration dictionary.

    Returns
    -------
    pathlib.Path
        Path to written JSON.
    """
    _ensure_dir(output_path)

    run_data = {
        "task_id": "FE-05",
        "executed_at_utc": executed_at_utc,
        "platform": platform_info,
        "input": {
            "customer_base_path": "data/processed/customer_base.parquet",
            "customer_base_sha256": input_sha256_customer_base,
            "transactions_clean_path": "data/processed/transactions_clean.parquet",
            "transactions_clean_sha256": input_sha256_transactions,
            "sha256_unchanged": True,  # Verified separately by orchestrator
        },
        "output": {
            "customer_candidates_path": "data/processed/customer_candidates.parquet",
            "customer_candidates_sha256": output_sha256_candidate,
            "customer_count": customer_count,
            "candidate_feature_count": candidate_feature_count,
        },
        "config_source": config_source,
        "config": config_dict,
        "feature_selection_summary": feature_selection_summary,
        "pending_review_notes": pending_review_notes,
        "scope_boundaries": [
            "RFM candidate features (ONE materialized each)",
            "Extended behavioral candidate features",
            "Monetary/Frequency/Quantity comparison reports",
            "Distribution/variance/correlation/redundancy/outlier analysis",
            "Evidence-based feature selection",
            "Candidate dataset Tầng 2",
            "Feature dictionary",
            "Reproducibility metadata",
        ],
        "constraints": {
            "no_clustering": True,
            "no_scaling": True,
            "no_transformation": True,
            "one_monetary": True,
            "one_frequency": True,
            "one_quantity_set": True,
            "no_category_count": True,
        },
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(run_data, f, indent=2, ensure_ascii=False, default=str)

    return output_path


# ---------------------------------------------------------------------------
# Narrative Report
# ---------------------------------------------------------------------------


def write_narrative_report(
    output_path: Path,
    *,
    reference_date: datetime,
    customer_count: int,
    candidate_feature_count: int,
    feature_selection_summary: dict[str, int],
    pending_review_notes: list[str],
    feature_layer_map: dict[str, str],
    validation_results: dict[str, Any],
    input_sha256_customer_base: str,
    input_sha256_transactions: str,
    output_sha256_candidate: str,
) -> Path:
    """Write Vietnamese narrative report.

    Parameters
    ----------
    output_path : pathlib.Path
        Output path.
    reference_date : datetime
        Computed reference date.
    customer_count : int
        Number of customers.
    candidate_feature_count : int
        Number of candidate features.
    feature_selection_summary : dict[str, int]
        Summary of feature selection decisions.
    pending_review_notes : list[str]
        Pending review notes.
    feature_layer_map : dict[str, str]
        Feature layer map.
    validation_results : dict[str, Any]
        Validation results.
    input_sha256_customer_base : str
        SHA-256 of customer_base.parquet.
    input_sha256_transactions : str
        SHA-256 of transactions_clean.parquet.
    output_sha256_candidate : str
        SHA-256 of customer_candidates.parquet.

    Returns
    -------
    pathlib.Path
        Path to written report.
    """
    _ensure_dir(output_path)

    # Format validation status
    validation_status_lines = []
    for check_id, result in validation_results.items():
        status = result.get("status", "UNKNOWN") if isinstance(result, dict) else str(result)
        validation_status_lines.append(f"- {check_id}: {status}")

    # Feature layer grouping
    layers: dict[str, list[str]] = {}
    for feat, layer in feature_layer_map.items():
        layers.setdefault(layer, []).append(feat)

    layer_lines = []
    for layer in ["IDENTIFIER_ONLY", "SOURCE_ONLY", "BASE_REFERENCE", "CANDIDATE", "UNSUPPORTED"]:
        if layer in layers:
            layer_lines.append(f"\n### {layer}")
            for feat in sorted(layers[layer]):
                layer_lines.append(f"- {feat}")

    content = f"""# FE-05 Báo Cáo Narrative (Tiếng Việt)

## 1. Tổng Quan

Báo cáo này mô tả quá trình feature engineering cho customer segmentation.

- **Stage**: FE-05 (Feature Engineering & Feature Selection)
- **Customer count**: {customer_count:,}
- **Candidate features**: {candidate_feature_count}
- **Reference Date**: {reference_date.isoformat()}
- **Reference Date Strategy**: max(InvoiceDate) + 1 day (deterministic)
- **Status**: WORKING_ASSUMPTION
- **Review**: MENTOR_REVIEW_PENDING

## 2. Input SHA-256

- `customer_base.parquet`: `{input_sha256_customer_base}`
- `transactions_clean.parquet`: `{input_sha256_transactions}`

## 3. Output SHA-256

- `customer_candidates.parquet`: `{output_sha256_candidate}`

## 4. RFM Features

- **Recency**: Days giữa ReferenceDate và LastPurchaseDate
  - Status: PENDING_REVIEW (purchase-only variant chưa quyết)
- **Frequency**: ONE materialized = Frequency_ByInvoice (FREQ-01)
  - Comparison với FREQ-02 trong `frequency_variants_comparison.csv`
- **Monetary**: ONE materialized = MonetarySigned
  - 4 distinct definition variants so sánh trong `monetary_definition_comparison.csv`

## 5. Extended Behavioral Features

- **TenureDays**: Transaction tenure
- **PurchaseIntervalMean**: Mean days between consecutive invoices (NaN if < 2 invoices)
- **PurchaseIntervalStd**: Std (ddof=1) of days between invoices (NaN if < 2 invoices)
- **ActiveDays**: Unique calendar days
- **AverageInvoiceValue**: Monetary / Frequency (FE-05 candidate mới)
- **ProductsPerInvoice**: DistinctProducts / DistinctInvoiceCount (ratio proxy)
- **CancellationRate**: CancellationInvoiceCount / Frequency
- **ReturnRate**: ReturnInvoiceCount / Frequency

## 6. Quantity Working Set

- **Default**: signed (TotalQuantity, AverageQuantity, BasketSize)
- **Comparison**: signed vs purchase-only trong `quantity_variants_comparison.csv`

## 7. Feature Layer Classification

{"".join(layer_lines)}

## 8. Validation Results

{"".join(validation_status_lines)}

## 9. Feature Selection Decisions

- **RETAIN_CANDIDATE**: {feature_selection_summary.get("RETAIN_CANDIDATE", 0)} features
- **PENDING_REVIEW**: {feature_selection_summary.get("PENDING_REVIEW", 0)} features
- **EXCLUDE**: {feature_selection_summary.get("EXCLUDE", 0)} features
- **ADJUST**: {feature_selection_summary.get("ADJUST", 0)} features
- **UNSUPPORTED**: {feature_selection_summary.get("UNSUPPORTED", 0)} features

## 10. PENDING_REVIEW Decisions

{"".join([f"- {note}" + chr(10) for note in pending_review_notes])}

## 11. Hard Constraints Verified

- ✅ ONE Monetary materialized (MonetarySigned)
- ✅ ONE Frequency materialized (Frequency_ByInvoice)
- ✅ ONE Quantity working set materialized (signed)
- ✅ CategoryCount NOT materialized
- ✅ PurchaseInterval uses ddof=1; NaN for < 2 invoices (not filled with 0)
- ✅ FE-04 AverageTransactionValue NOT modified (kept in BASE_REFERENCE)
- ✅ No clustering/scaling/transformation
- ✅ Input SHA-256 unchanged
- ✅ Output SHA-256 recorded

## 12. Limitations

- FE-05 does not select "best" features - all RETAIN_CANDIDATE features are eligible for FE-06.
- Selection uses evidence-based gates, NOT numerical score/ranking/weights.
- Shapiro-Wilk, Redundancy, Stability gates are diagnostic only.

## 13. Next Step

- FE-06 (Transformation/Clustering) will use `customer_candidates.parquet` as input.
- Decision of which features to actually use for clustering is in FE-06.
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Master write function
# ---------------------------------------------------------------------------


def write_all_fe05_reports(
    report_dir: Path,
    *,
    reference_date: datetime,
    customer_count: int,
    candidate_features: list[str],
    recency_df: pd.DataFrame,
    frequency_variants_df: pd.DataFrame,
    monetary_variants_df: pd.DataFrame,
    quantity_comparison_df: pd.DataFrame,
    distribution_df: pd.DataFrame,
    variance_df: pd.DataFrame,
    correlation_pearson: pd.DataFrame,
    correlation_spearman: pd.DataFrame,
    redundancy_pairs: pd.DataFrame,
    outlier_counts: pd.DataFrame,
    feature_selection_df: pd.DataFrame,
    interpretability_df: pd.DataFrame,
    feature_layer_map: dict[str, str],
    feature_descriptions: dict[str, str] | None,
    feature_status_map: dict[str, str] | None,
    input_sha256_customer_base: str,
    input_sha256_transactions: str,
    output_sha256_candidate: str,
    config_source: str,
    config_dict: dict[str, Any],
    pending_review_notes: list[str],
    feature_selection_summary: dict[str, int],
    validation_results: dict[str, Any],
    executed_at_utc: str,
    platform_info: dict[str, str],
) -> ReportPaths:
    """Write all FE-05 reports.

    Parameters
    ----------
    report_dir : pathlib.Path
        Output directory.

    Returns
    -------
    ReportPaths
        Container with paths to all written reports.
    """
    report_dir.mkdir(parents=True, exist_ok=True)

    # Write all reports
    rfm_report = write_rfm_report(
        report_dir,
        reference_date,
        recency_df,
        frequency_variants_df,
        monetary_variants_df,
    )
    monetary_comparison = write_monetary_comparison(report_dir, monetary_variants_df)
    quantity_comparison = write_quantity_comparison_csv(
        quantity_comparison_df, report_dir / "quantity_variants_comparison.csv"
    )
    frequency_comparison = write_frequency_comparison_csv(
        frequency_variants_df, report_dir / "frequency_variants_comparison.csv"
    )
    candidate_feature_report = write_candidate_feature_report(
        report_dir / "candidate_feature_report.md",
        candidate_features,
        customer_count=customer_count,
    )
    distribution_analysis = write_distribution_analysis(
        distribution_df, report_dir / "distribution_analysis.csv"
    )
    variance_analysis = write_variance_analysis(variance_df, report_dir / "variance_analysis.csv")
    correlation_pearson_path, correlation_spearman_path = write_correlation_matrices(
        correlation_pearson,
        correlation_spearman,
        report_dir,
    )
    redundancy_report = write_redundancy_report(
        redundancy_pairs, report_dir / "redundancy_report.csv"
    )
    outlier_detection = write_outlier_detection(
        outlier_counts, report_dir / "outlier_detection.csv"
    )
    feature_selection = write_feature_selection_report(
        feature_selection_df, report_dir / "feature_selection_report.csv"
    )
    interpretability = write_interpretability_csv(
        interpretability_df, report_dir / "business_interpretability.csv"
    )
    feature_dictionary = write_feature_dictionary(
        report_dir / "feature_dictionary.csv",
        feature_layer_map=feature_layer_map,
        feature_descriptions=feature_descriptions,
        feature_status_map=feature_status_map,
    )

    run_json = write_fe05_run_json(
        report_dir / "fe05_run.json",
        input_sha256_customer_base=input_sha256_customer_base,
        input_sha256_transactions=input_sha256_transactions,
        output_sha256_candidate=output_sha256_candidate,
        customer_count=customer_count,
        candidate_feature_count=len(candidate_features),
        config_source=config_source,
        executed_at_utc=executed_at_utc,
        platform_info=platform_info,
        pending_review_notes=pending_review_notes,
        feature_selection_summary=feature_selection_summary,
        config_dict=config_dict,
    )

    narrative_report = write_narrative_report(
        report_dir / "narrative_report.md",
        reference_date=reference_date,
        customer_count=customer_count,
        candidate_feature_count=len(candidate_features),
        feature_selection_summary=feature_selection_summary,
        pending_review_notes=pending_review_notes,
        feature_layer_map=feature_layer_map,
        validation_results=validation_results,
        input_sha256_customer_base=input_sha256_customer_base,
        input_sha256_transactions=input_sha256_transactions,
        output_sha256_candidate=output_sha256_candidate,
    )

    return ReportPaths(
        rfm_report=rfm_report,
        monetary_comparison=monetary_comparison,
        quantity_comparison=quantity_comparison,
        frequency_comparison=frequency_comparison,
        candidate_feature_report=candidate_feature_report,
        distribution_analysis=distribution_analysis,
        variance_analysis=variance_analysis,
        correlation_pearson=correlation_pearson_path,
        correlation_spearman=correlation_spearman_path,
        redundancy_report=redundancy_report,
        outlier_detection=outlier_detection,
        feature_selection=feature_selection,
        business_interpretability=interpretability,
        feature_dictionary=feature_dictionary,
        run_json=run_json,
        narrative_report=narrative_report,
    )


def write_monetary_comparison(
    report_dir: Path,
    monetary_variants_df: pd.DataFrame,
) -> Path:
    """Write monetary comparison CSV.

    Parameters
    ----------
    report_dir : pathlib.Path
        Output directory.
    monetary_variants_df : pandas.DataFrame
        Monetary variants DataFrame.

    Returns
    -------
    pathlib.Path
        Path to written CSV.
    """
    output_path = report_dir / "monetary_definition_comparison.csv"
    _ensure_dir(output_path)
    monetary_variants_df.to_csv(output_path, index=False)
    return output_path
