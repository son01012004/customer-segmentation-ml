"""Unit tests for :mod:`customer_segmentation.outlier_analysis.report`.

Synthetic artefacts only. No raw data, no FE-02 parquet.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.config.outlier_loader import (
    CustomerAggregationConfig,
    CustomerDiagnosticConfig,
    FeatureOutlierConfig,
    OutlierAnalysisConfig,
    OutputConfig,
    SensitivityConfig,
)
from customer_segmentation.outlier_analysis.detection import DetectionRecord
from customer_segmentation.outlier_analysis.distribution import distribution_profile
from customer_segmentation.outlier_analysis.interpretation import (
    InterpretationDecision,
)
from customer_segmentation.outlier_analysis.report import (
    ReportContext,
    build_customer_diagnostic_csv,
    build_distribution_csv,
    build_feature_statistics_csv,
    build_outlier_analysis_md,
    build_outlier_summary_csv,
    build_percentile_csv,
    build_sensitivity_csv,
    build_treatment_decisions_csv,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_quantity_series() -> pd.Series:
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 100.0, -10.0], name="Quantity")


@pytest.fixture()
def sample_unitprice_series() -> pd.Series:
    return pd.Series([0.5, 1.0, 2.0, 3.0, 5.0, 100.0, 1000.0], name="UnitPrice")


@pytest.fixture()
def sample_config() -> OutlierAnalysisConfig:
    return OutlierAnalysisConfig(
        enabled=True,
        random_seed=42,
        transaction_features=[
            FeatureOutlierConfig(column="Quantity", detection="iqr", iqr_multiplier=1.5),
            FeatureOutlierConfig(column="UnitPrice", detection="iqr", iqr_multiplier=1.5),
            FeatureOutlierConfig(column="LineRevenue", detection="iqr", iqr_multiplier=1.5),
        ],
        customer_diagnostic=CustomerDiagnosticConfig(
            enabled=True,
            customer_key="CustomerID",
            aggregations={
                "total_spend": CustomerAggregationConfig(source="LineRevenue", fn="sum"),
                "total_quantity": CustomerAggregationConfig(source="Quantity", fn="sum"),
                "distinct_invoices": CustomerAggregationConfig(source="InvoiceNo", fn="nunique"),
                "distinct_products": CustomerAggregationConfig(source="StockCode", fn="nunique"),
                "active_days": CustomerAggregationConfig(source="InvoiceDate", fn="nunique_date"),
            },
        ),
        sensitivity=SensitivityConfig(
            enabled=True, thresholds=(1.5, 3.0), percentiles=(99.0, 99.5, 99.9)
        ),
        output=OutputConfig(),
    )


@pytest.fixture()
def sample_ctx(
    sample_config: OutlierAnalysisConfig,
    sample_quantity_series: pd.Series,
    sample_unitprice_series: pd.Series,
) -> ReportContext:
    rev_series = sample_quantity_series * pd.Series([5.0, 2.0, 1.0, 3.0, 1.0, 1.0, 1.0, 5.0])
    rev_series.name = "LineRevenue"

    profiles = {
        "all_rows": {
            "Quantity": distribution_profile(sample_quantity_series),
            "UnitPrice": distribution_profile(sample_unitprice_series),
            "LineRevenue": distribution_profile(rev_series),
        }
    }
    det_records = [
        DetectionRecord(
            feature="Quantity",
            method="iqr",
            threshold=1.5,
            lower=-5.0,
            upper=15.0,
            candidates=2,
            rate=0.25,
            total_rows=8,
            filter_mode="all_rows",
        ),
        DetectionRecord(
            feature="UnitPrice",
            method="iqr",
            threshold=1.5,
            lower=-5.0,
            upper=10.0,
            candidates=2,
            rate=0.28,
            total_rows=7,
            filter_mode="all_rows",
        ),
    ]
    interp = [
        InterpretationDecision(
            feature="Quantity",
            verdict="AMBIGUOUS",
            recommendation="KEEP",
            status="PENDING_MENTOR_REVIEW",
            evidence=("Long tail", "Bulk buyer candidate"),
            filter_mode="all_rows",
            candidates=2,
            rate=0.25,
            notes="DD-02",
        ),
        InterpretationDecision(
            feature="UnitPrice",
            verdict="AMBIGUOUS",
            recommendation="KEEP",
            status="PENDING_MENTOR_REVIEW",
            evidence=("Max is high",),
            filter_mode="all_rows",
            candidates=2,
            rate=0.28,
            notes="DD-03",
        ),
    ]
    customer_diag_df = pd.DataFrame(
        {
            "CustomerID": [1, 2, 3],
            "total_spend": [100.0, 250.0, 1000.0],
            "total_quantity": [5, 10, 50],
            "distinct_invoices": [1, 2, 5],
            "distinct_products": [1, 2, 5],
            "active_days": [1, 2, 5],
        }
    )
    customer_summary = pd.DataFrame(
        {
            "column": ["total_spend", "total_quantity"],
            "count": [3, 3],
            "min": [100.0, 5.0],
            "max": [1000.0, 50.0],
            "mean": [450.0, 21.7],
            "median": [250.0, 10.0],
            "std": [400.0, 20.0],
            "q1": [100.0, 5.0],
            "q3": [1000.0, 50.0],
            "iqr": [900.0, 45.0],
        }
    )
    sens = pd.DataFrame(
        {
            "feature": ["Quantity", "Quantity"],
            "filter_mode": ["all_rows", "all_rows"],
            "method": ["iqr", "iqr"],
            "threshold": [1.5, 3.0],
            "lower": [-5.0, -15.0],
            "upper": [15.0, 25.0],
            "candidates": [2, 1],
            "rate": [0.25, 0.125],
            "total_rows": [8, 8],
        }
    )
    return ReportContext(
        config=sample_config,
        raw_sha256="abc123",
        cleaned_sha256_before="def456",
        cleaned_sha256_after="def456",
        distribution_profiles=profiles,
        detection_records=det_records,
        sensitivity_tables=[sens],
        interpretation_decisions=interp,
        customer_diagnostics={"all_rows": customer_diag_df},
        customer_diagnostic_summary=customer_summary,
        treated_dataset_path=None,
        config_source="yaml_auto:/tmp/outlier.yaml",
        run_id="2026-09-19T00:00:00Z",
        platform={"python": "3.11", "system": "Linux"},
    )


# ---------------------------------------------------------------------------
# CSV builders
# ---------------------------------------------------------------------------


class TestDistributionCSV:
    def test_one_row_per_feature_per_mode(self, sample_ctx: ReportContext) -> None:
        df = build_distribution_csv(sample_ctx)
        # 3 features × 1 mode = 3 rows.
        assert df.shape[0] == 3
        assert set(df["filter_mode"].unique()) == {"all_rows"}
        assert set(df["column"].unique()) == {"Quantity", "UnitPrice", "LineRevenue"}

    def test_percentile_columns_present(self, sample_ctx: ReportContext) -> None:
        df = build_distribution_csv(sample_ctx)
        for col in ["p1", "p50", "p99.9"]:
            assert col in df.columns


class TestOutlierSummaryCSV:
    def test_one_row_per_record(self, sample_ctx: ReportContext) -> None:
        df = build_outlier_summary_csv(sample_ctx)
        assert df.shape[0] == len(sample_ctx.detection_records)
        for c in ["feature", "method", "threshold", "candidates", "rate"]:
            assert c in df.columns

    def test_empty(self, sample_config: OutlierAnalysisConfig) -> None:
        ctx = ReportContext(
            config=sample_config,
            raw_sha256="x",
            cleaned_sha256_before="y",
            cleaned_sha256_after="y",
        )
        df = build_outlier_summary_csv(ctx)
        assert df.empty


class TestTreatmentDecisionsCSV:
    def test_one_row_per_decision(self, sample_ctx: ReportContext) -> None:
        df = build_treatment_decisions_csv(sample_ctx)
        assert df.shape[0] == len(sample_ctx.interpretation_decisions)
        assert "verdict" in df.columns
        assert "recommendation" in df.columns


class TestPercentileCSV:
    def test_columns(self, sample_ctx: ReportContext) -> None:
        df = build_percentile_csv(sample_ctx)
        assert "feature" in df.columns
        assert "filter_mode" in df.columns
        # One of the standard percentiles must appear.
        assert any(c.startswith("p") and c != "feature" for c in df.columns)


class TestSensitivityCSV:
    def test_concatenates(self, sample_ctx: ReportContext) -> None:
        df = build_sensitivity_csv(sample_ctx)
        assert df.shape[0] == 2  # the two rows from sample_ctx.sensitivity_tables[0]
        assert "method" in df.columns

    def test_empty(self, sample_config: OutlierAnalysisConfig) -> None:
        ctx = ReportContext(
            config=sample_config,
            raw_sha256="x",
            cleaned_sha256_before="y",
            cleaned_sha256_after="y",
        )
        df = build_sensitivity_csv(ctx)
        assert df.empty
        assert "feature" in df.columns  # schema columns preserved


class TestFeatureStatisticsCSV:
    def test_uses_all_rows_default(self, sample_ctx: ReportContext) -> None:
        df = build_feature_statistics_csv(sample_ctx)
        assert df.shape[0] == 3  # 3 features
        assert "filter_mode" in df.columns
        assert (df["filter_mode"] == "all_rows").all()


class TestCustomerDiagnosticCSV:
    def test_default_mode(self, sample_ctx: ReportContext) -> None:
        df = build_customer_diagnostic_csv(sample_ctx)
        assert df.shape[0] == 3
        assert (df["filter_mode"] == "all_rows").all()


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


class TestMarkdown:
    def test_has_15_sections(self, sample_ctx: ReportContext) -> None:
        md = build_outlier_analysis_md(sample_ctx)
        for header in [
            "## 1. Objective",
            "## 2. Dataset and Unit of Analysis",
            "## 3. Features Investigated",
            "## 4. Distribution Analysis",
            "## 5. Outlier Detection Methods",
            "## 6. Transaction-Level Analysis",
            "## 7. Customer-Level Diagnostic Analysis",
            "## 8. Cancellation and Return Analysis",
            "## 9. Error vs Real Behavior Assessment",
            "## 10. Treatment Decisions",
            "## 11. Before / After Comparison",
            "## 12. Sensitivity Analysis",
            "## 13. Mentor Decisions Required",
            "## 14. Limitations",
            "## 15. Conclusion",
        ]:
            assert header in md

    def test_mentions_pending_mentor_review(self, sample_ctx: ReportContext) -> None:
        md = build_outlier_analysis_md(sample_ctx)
        assert "PENDING_MENTOR_REVIEW" in md

    def test_mentions_diagnostic_only_boundary(self, sample_ctx: ReportContext) -> None:
        md = build_outlier_analysis_md(sample_ctx)
        assert "diagnostic" in md.lower()
        assert "not" in md.lower()
        assert "FE-04" in md

    def test_mentions_sha256(self, sample_ctx: ReportContext) -> None:
        md = build_outlier_analysis_md(sample_ctx)
        assert "abc123" in md  # raw
        assert "def456" in md  # cleaned

    def test_explains_default_keep(self, sample_ctx: ReportContext) -> None:
        md = build_outlier_analysis_md(sample_ctx)
        assert "KEEP" in md
        assert "no treated dataset is written" in md.lower()

    def test_deterministic(self, sample_ctx: ReportContext) -> None:
        md1 = build_outlier_analysis_md(sample_ctx)
        md2 = build_outlier_analysis_md(sample_ctx)
        assert md1 == md2
