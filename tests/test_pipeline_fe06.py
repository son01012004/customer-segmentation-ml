"""Integration tests for FE-06 pipeline.

IT-01: Load real config
IT-02: Pipeline run with real data
IT-03: Output shape = (4371, 14)
IT-04: CustomerID in metadata, NOT in matrix
IT-05: No NaN/Inf in final matrix
IT-06: SHA-256 reproducible
IT-07: Input SHA unchanged after pipeline
IT-08: All reports written
IT-09: No cluster labels in output
IT-10: Working config C7 applied
IT-11: FE06PipelineResult has eligibility maps
IT-12: AverageQuantity == BasketSize (DUPLICATE_INFORMATION)
IT-13: CancellationRate == ReturnRate (DUPLICATE_INFORMATION)
IT-14: Frequency != ActiveDays (HIGH_CORRELATION, not duplicate)
IT-15: Redundancy 3-category analysis in reports
IT-16: Imputation semantics report written
IT-17: FE06_Trace column in feature reports
IT-18: Imputation semantics: STRUCTURALLY_UNDEFINED
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.transformation.config_loader import (  # noqa: E402
    load_transformation_config,
    resolve_transformation_config_path,
)
from customer_segmentation.transformation.versioning import compute_file_sha256  # noqa: E402


class TestConfigLoad:
    """IT-01: Load real transformation config."""

    def test_load_real_config(self) -> None:
        """Load the actual configs/transformation.yaml."""
        config_path = resolve_transformation_config_path()
        assert config_path is not None, "configs/transformation.yaml not found"
        config = load_transformation_config(config_path)
        assert config.enabled is True
        assert config.working_configuration.id == "C7"
        assert config.working_configuration.transformation == "yeo_johnson"
        assert config.working_configuration.scaling == "robust"
        assert config.working_configuration.imputation == "median"


class TestPipelineOutput:
    """IT-02: Pipeline run with real data."""

    def test_pipeline_produces_output(self, tmp_path: Path) -> None:
        """Pipeline produces final_clustering_dataset.parquet."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert result.final_matrix.shape[0] == 4371
        assert result.working_config_id == "C7"
        assert result.working_transformation == "yeo_johnson"
        assert result.working_scaling == "robust"
        assert result.working_imputation == "median"
        assert result.fe06_version == "FE06-v1.0"


class TestOutputShape:
    """IT-03: Output shape = (4371, 14)."""

    def test_final_matrix_shape(self, tmp_path: Path) -> None:
        """Final matrix has 4371 rows and 14 numeric features."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert result.final_matrix.shape == (
            4371,
            14,
        ), f"Expected (4371, 14), got {result.final_matrix.shape}"


class TestCustomerIDHandling:
    """IT-04: CustomerID in metadata, NOT in matrix."""

    def test_customerid_not_in_matrix(self, tmp_path: Path) -> None:
        """CustomerID is NOT in the final clustering matrix."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert "CustomerID" not in result.final_matrix.columns
        assert "CustomerID" in result.customer_metadata.columns

    def test_metadata_row_count_matches_matrix(self, tmp_path: Path) -> None:
        """Metadata and matrix have matching row counts."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert len(result.customer_metadata) == len(result.final_matrix)


class TestNoNaNInf:
    """IT-05: No NaN/Inf in final matrix."""

    def test_no_nan_in_final_matrix(self, tmp_path: Path) -> None:
        """Final clustering matrix has no NaN values."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        nan_count = result.final_matrix.isna().sum().sum()
        assert nan_count == 0, f"Found {nan_count} NaN values in final matrix"

    def test_no_inf_in_final_matrix(self, tmp_path: Path) -> None:
        """Final clustering matrix has no Inf values."""
        import numpy as np

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        inf_count = np.isinf(result.final_matrix.values).sum()
        assert inf_count == 0, f"Found {inf_count} Inf values in final matrix"


class TestSHAUnchanged:
    """IT-07: Input SHA unchanged after pipeline."""

    def test_input_sha_unchanged(self, tmp_path: Path) -> None:
        """Input SHA-256 is the same before and after pipeline."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        sha_before = compute_file_sha256(candidates_path)

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        sha_after = compute_file_sha256(candidates_path)
        assert sha_before == sha_after, f"Input SHA changed: before={sha_before}, after={sha_after}"


class TestReportsWritten:
    """IT-08: All required reports are written."""

    def test_all_reports_exist(self, tmp_path: Path) -> None:
        """All required report files exist."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        required_reports = [
            "fe06_run.json",
            "feature_eligibility.csv",
            "feature_dictionary.csv",
            "distribution_pre_transformation.csv",
            "distribution_post_transformation.csv",
            "distribution_post_scaling.csv",
            "redundancy_report.csv",
            "redundancy_analysis.csv",
            "imputation_semantics.csv",
            "outlier_analysis.csv",
            "comparison_matrix.csv",
            "data_quality_report.csv",
            "leakage_check.csv",
            "narrative_report.md",
        ]

        for report in required_reports:
            path = report_dir / report
            assert path.exists(), f"Missing report: {report}"


class TestNoClusterLabels:
    """IT-09: No cluster labels in output."""

    def test_no_cluster_labels_in_matrix(self, tmp_path: Path) -> None:
        """Final matrix does not contain cluster labels."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        cluster_cols = [c for c in result.final_matrix.columns if "cluster" in c.lower()]
        assert len(cluster_cols) == 0, f"Cluster columns found: {cluster_cols}"


class TestWorkingConfigC7:
    """IT-10: Working config C7 is applied."""

    def test_working_config_c7_applied(self, tmp_path: Path) -> None:
        """Working configuration is C7 (yeo_johnson + robust + median)."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert result.working_config_id == "C7"
        assert result.working_transformation == "yeo_johnson"
        assert result.working_scaling == "robust"
        assert result.working_imputation == "median"
        assert result.validation_result.all_passed


class TestEligibilityMaps:
    """IT-11: FE06PipelineResult includes eligibility traceability maps."""

    def test_eligibility_status_map_present(self, tmp_path: Path) -> None:
        """FE06PipelineResult has eligibility_status_map."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert hasattr(result, "eligibility_status_map")
        assert len(result.eligibility_status_map) > 0
        # CANDIDATE features should have ELIGIBLE or ELIGIBLE_WORKING_ASSUMPTION
        assert "Recency" in result.eligibility_status_map
        assert result.eligibility_status_map["Recency"] in (
            "ELIGIBLE",
            "ELIGIBLE_WORKING_ASSUMPTION",
        )

    def test_eligibility_fe05_map_present(self, tmp_path: Path) -> None:
        """FE06PipelineResult has eligibility_fe05_map."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert hasattr(result, "eligibility_fe05_map")
        assert len(result.eligibility_fe05_map) > 0
        # PENDING_REVIEW features from FE-05 should be in the map
        assert "AverageQuantity" in result.eligibility_fe05_map
        assert result.eligibility_fe05_map["AverageQuantity"] == "PENDING_REVIEW"


class TestDuplicateInformation:
    """IT-12/13: True mathematical duplicates in source data."""

    def test_averagequantity_basketsize_equal(self, tmp_path: Path) -> None:
        """AverageQuantity and BasketSize are mathematically identical (duplicate).

        This is by FE-05 construction: BasketSize is an alias for AverageQuantity.
        Both are defined as: sum(Quantity) / nunique(InvoiceNo) per CustomerID.
        Equality rate must be 1.0 (all customers identical values).
        Category: DUPLICATE_INFORMATION (PENDING_REVIEW for drop decision).
        """
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        # Both features are in the final matrix
        assert "AverageQuantity" in result.final_matrix.columns
        assert "BasketSize" in result.final_matrix.columns

        # Values are equal across all rows
        diff = (result.final_matrix["AverageQuantity"] - result.final_matrix["BasketSize"]).abs()
        assert (
            float(diff.max()) < 1e-12
        ), f"AverageQuantity != BasketSize for some customers: max diff = {diff.max()}"

    def test_cancellationrate_returnrate_equal(self, tmp_path: Path) -> None:
        """CancellationRate and ReturnRate are empirically identical (duplicate).

        Although the formulas differ (CancellationInvoiceCount vs ReturnInvoiceCount
        divided by Frequency), the data shows equality rate = 1.0.
        Category: DUPLICATE_INFORMATION (PENDING_REVIEW for drop decision).
        """
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        # Both features are in the final matrix
        assert "CancellationRate" in result.final_matrix.columns
        assert "ReturnRate" in result.final_matrix.columns

        # Values are equal across all rows
        diff = (result.final_matrix["CancellationRate"] - result.final_matrix["ReturnRate"]).abs()
        assert (
            float(diff.max()) < 1e-12
        ), f"CancellationRate != ReturnRate for some customers: max diff = {diff.max()}"


class TestHighCorrelation:
    """IT-14: Frequency vs ActiveDays — HIGH_CORRELATION, not duplicate."""

    def test_frequency_active_days_not_equal(self, tmp_path: Path) -> None:
        """Frequency and ActiveDays are NOT identical (HIGH_CORRELATION).

        Definitions differ:
        - Frequency = nunique(InvoiceNo) per CustomerID
        - ActiveDays = nunique(date(InvoiceDate)) per CustomerID

        Multiple invoices on the same day -> Frequency > ActiveDays.
        Equality rate < 1.0. Category: HIGH_CORRELATION.
        """
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        result = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        assert "Frequency" in result.final_matrix.columns
        assert "ActiveDays" in result.final_matrix.columns

        # Not all values are equal (some customers have multi-invoice days)
        eq_count = (result.final_matrix["Frequency"] == result.final_matrix["ActiveDays"]).sum()
        total = len(result.final_matrix)
        eq_rate = eq_count / total
        # Some customers must have Frequency != ActiveDays
        assert eq_rate < 1.0, "Frequency and ActiveDays are identical for all customers"


class TestRedundancyAnalysis:
    """IT-15: 3-category redundancy analysis in reports."""

    def test_redundancy_analysis_report_written(self, tmp_path: Path) -> None:
        """redundancy_analysis.csv (3-category) is written."""
        import pandas as pd

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        path = report_dir / "redundancy_analysis.csv"
        assert path.exists(), "redundancy_analysis.csv not written"
        df = pd.read_csv(path)
        assert not df.empty, "redundancy_analysis.csv is empty"
        assert "Category" in df.columns, "Category column missing"
        assert "EqualityRate" in df.columns, "EqualityRate column missing"

    def test_redundancy_categories_correct(self, tmp_path: Path) -> None:
        """3-category classification is correct for all canonical pairs."""
        import pandas as pd

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        path = report_dir / "redundancy_analysis.csv"
        df = pd.read_csv(path)

        # AverageQuantity <-> BasketSize: DUPLICATE_INFORMATION
        row = df[(df["Feature1"] == "AverageQuantity") & (df["Feature2"] == "BasketSize")]
        assert not row.empty, "Missing AverageQuantity/BasketSize pair"
        assert row.iloc[0]["Category"] == "DUPLICATE_INFORMATION"
        assert float(row.iloc[0]["EqualityRate"]) == 1.0

        # CancellationRate <-> ReturnRate: DUPLICATE_INFORMATION
        row = df[(df["Feature1"] == "CancellationRate") & (df["Feature2"] == "ReturnRate")]
        assert not row.empty, "Missing CancellationRate/ReturnRate pair"
        assert row.iloc[0]["Category"] == "DUPLICATE_INFORMATION"
        assert float(row.iloc[0]["EqualityRate"]) == 1.0

        # Frequency <-> ActiveDays: HIGH_CORRELATION
        row = df[(df["Feature1"] == "Frequency") & (df["Feature2"] == "ActiveDays")]
        assert not row.empty, "Missing Frequency/ActiveDays pair"
        assert row.iloc[0]["Category"] == "HIGH_CORRELATION"
        assert float(row.iloc[0]["EqualityRate"]) < 1.0


class TestImputationSemantics:
    """IT-16/18: Imputation semantics report and STRUCTURALLY_UNDEFINED."""

    def test_imputation_semantics_report_written(self, tmp_path: Path) -> None:
        """imputation_semantics.csv is written."""
        import pandas as pd

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        path = report_dir / "imputation_semantics.csv"
        assert path.exists(), "imputation_semantics.csv not written"
        df = pd.read_csv(path)
        assert not df.empty, "imputation_semantics.csv is empty"
        assert "Semantics" in df.columns

    def test_imputation_structurally_undefined(self, tmp_path: Path) -> None:
        """PurchaseIntervalMean/Std NaN are STRUCTURALLY_UNDEFINED."""
        import pandas as pd

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        path = report_dir / "imputation_semantics.csv"
        df = pd.read_csv(path)

        for feat in ["PurchaseIntervalMean", "PurchaseIntervalStd"]:
            row = df[df["Feature"] == feat]
            assert not row.empty, f"{feat} not in imputation semantics report"
            assert row.iloc[0]["Semantics"] == "STRUCTURALLY_UNDEFINED", (
                f"{feat} semantics should be STRUCTURALLY_UNDEFINED, "
                f"got {row.iloc[0]['Semantics']}"
            )
            assert int(row.iloc[0]["NaN_Before"]) > 0, f"{feat} should have NaN before imputation"
            assert int(row.iloc[0]["NaN_After"]) == 0, f"{feat} should have 0 NaN after imputation"


class TestFeatureReports:
    """IT-17: FE06_Trace column in feature reports."""

    def test_feature_eligibility_has_trace(self, tmp_path: Path) -> None:
        """feature_eligibility.csv has FE06_Trace column."""
        import pandas as pd

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        path = report_dir / "feature_eligibility.csv"
        df = pd.read_csv(path)
        assert "FE06_Trace" in df.columns, "FE06_Trace column missing from feature_eligibility.csv"
        # FE-05 PENDING_REVIEW features should have MENTOR_REVIEW_PENDING in trace
        pending = df[df["FE05_Decision"] == "PENDING_REVIEW"]
        for _, row in pending.iterrows():
            assert (
                "MENTOR_REVIEW_PENDING" in row["FE06_Trace"]
            ), f"Missing MENTOR_REVIEW_PENDING in trace for {row['Feature']}"

    def test_feature_dictionary_has_trace(self, tmp_path: Path) -> None:
        """feature_dictionary.csv has FE06_Trace column."""
        import pandas as pd

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        path = report_dir / "feature_dictionary.csv"
        df = pd.read_csv(path)
        assert "FE06_Trace" in df.columns, "FE06_Trace column missing from feature_dictionary.csv"
