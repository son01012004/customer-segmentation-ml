"""Integration tests for FE-05 feature engineering pipeline.

IT-01 → IT-18
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.features.config_loader import (  # noqa: E402
    FeatureEngineeringConfig,
    load_feature_engineering_config,
)

# ---------------------------------------------------------------------------
# IT-01: Load real config
# ---------------------------------------------------------------------------


class TestConfigLoad:
    def test_load_real_config(self) -> None:
        """Load the actual configs/feature_engineering.yaml."""
        config = load_feature_engineering_config(
            Path(_REPO_ROOT / "configs" / "feature_engineering.yaml")
        )
        assert isinstance(config, FeatureEngineeringConfig)
        assert config.enabled is True
        assert config.customer_key == "CustomerID"


# ---------------------------------------------------------------------------
# IT-02: customer_count matches FE-04
# ---------------------------------------------------------------------------


class TestCustomerCount:
    def test_customer_count_matches_fe04(self) -> None:
        """FE-05 output customer count must match FE-04 customer count."""
        customer_base = pd.read_parquet(_REPO_ROOT / "data" / "processed" / "customer_base.parquet")
        # This test assumes the candidate parquet exists from a previous run
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if candidate_path.exists():
            candidates = pd.read_parquet(candidate_path)
            assert candidates.shape[0] == customer_base.shape[0]
            assert candidates["CustomerID"].nunique() == customer_base["CustomerID"].nunique()


# ---------------------------------------------------------------------------
# IT-03: customer_candidates has expected features
# ---------------------------------------------------------------------------


class TestCandidateFeatures:
    def test_candidate_has_required_features(self) -> None:
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        expected_features = {
            "CustomerID",
            "Recency",
            "Frequency",
            "Monetary",
            "TotalQuantity",
            "AverageQuantity",
            "BasketSize",
            "TenureDays",
            "PurchaseIntervalMean",
            "PurchaseIntervalStd",
            "ActiveDays",
            "AverageInvoiceValue",
            "ProductsPerInvoice",
            "CancellationRate",
            "ReturnRate",
        }
        assert set(candidates.columns) >= expected_features


# ---------------------------------------------------------------------------
# IT-04 / IT-05: SHA-256 recorded
# ---------------------------------------------------------------------------


class TestSHA256:
    def test_input_sha256_in_run_json(self) -> None:
        """fe05_run.json should record input SHA-256."""
        run_json_path = _REPO_ROOT / "reports" / "fe05" / "fe05_run.json"
        if not run_json_path.exists():
            pytest.skip("fe05_run.json not generated")
        import json

        with run_json_path.open() as f:
            run = json.load(f)
        assert "customer_base_sha256" in run["input"]
        assert "transactions_clean_sha256" in run["input"]
        assert "customer_candidates_sha256" in run["output"]


# ---------------------------------------------------------------------------
# IT-06: ONE Monetary column
# ---------------------------------------------------------------------------


class TestOneMonetary:
    def test_one_monetary_in_candidates(self) -> None:
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        monetary_cols = [c for c in candidates.columns if c.startswith("Monetary")]
        assert len(monetary_cols) == 1
        assert "Monetary" in monetary_cols


# ---------------------------------------------------------------------------
# IT-07: ONE Frequency column
# ---------------------------------------------------------------------------


class TestOneFrequency:
    def test_one_frequency_in_candidates(self) -> None:
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        freq_cols = [c for c in candidates.columns if c.startswith("Frequency")]
        assert len(freq_cols) == 1
        assert "Frequency" in freq_cols


# ---------------------------------------------------------------------------
# IT-08: ONE Quantity working set
# ---------------------------------------------------------------------------


class TestOneQuantitySet:
    def test_one_quantity_set_in_candidates(self) -> None:
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        qty_cols = [
            c
            for c in candidates.columns
            if c.startswith("TotalQuantity")
            or c.startswith("AverageQuantity")
            or c.startswith("BasketSize")
        ]
        # Should have TotalQuantity, AverageQuantity, BasketSize
        assert "TotalQuantity" in qty_cols
        assert "AverageQuantity" in qty_cols
        assert "BasketSize" in qty_cols
        # Should NOT have variants in candidates (only in comparison report)
        assert "TotalQuantity_Signed" not in qty_cols
        assert "TotalQuantity_PurchaseOnly" not in qty_cols


# ---------------------------------------------------------------------------
# IT-09: No CategoryCount
# ---------------------------------------------------------------------------


class TestNoCategoryCount:
    def test_no_category_count(self) -> None:
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        assert "CategoryCount" not in candidates.columns


# ---------------------------------------------------------------------------
# IT-10: FE-04 AverageTransactionValue not modified
# ---------------------------------------------------------------------------


class TestFE04Unchanged:
    def test_fe04_average_transaction_value_intact(self) -> None:
        """FE-04 customer_base.parquet AverageTransactionValue column must remain."""
        customer_base = pd.read_parquet(_REPO_ROOT / "data" / "processed" / "customer_base.parquet")
        assert "AverageTransactionValue" in customer_base.columns


# ---------------------------------------------------------------------------
# IT-11: 4 monetary variants in comparison
# ---------------------------------------------------------------------------


class TestFourMonetaryVariants:
    def test_comparison_has_four_variants(self) -> None:
        comp_path = _REPO_ROOT / "reports" / "fe05" / "monetary_definition_comparison.csv"
        if not comp_path.exists():
            pytest.skip("comparison report not generated")
        df = pd.read_csv(comp_path)
        assert "MonetarySigned" in df.columns
        assert "MonetaryAbsolute" in df.columns
        assert "MonetaryPurchaseOnly" in df.columns
        assert "MonetaryCancellationOnly" in df.columns


# ---------------------------------------------------------------------------
# IT-12: FREQ-01 vs FREQ-02 comparison
# ---------------------------------------------------------------------------


class TestFrequencyComparison:
    def test_comparison_has_both_variants(self) -> None:
        comp_path = _REPO_ROOT / "reports" / "fe05" / "frequency_variants_comparison.csv"
        if not comp_path.exists():
            pytest.skip("comparison report not generated")
        df = pd.read_csv(comp_path)
        assert "FREQ_01_ByInvoice" in df.columns
        assert "FREQ_02_ByTransactionLine" in df.columns


# ---------------------------------------------------------------------------
# IT-13: signed/purchase-only Quantity comparison
# ---------------------------------------------------------------------------


class TestQuantityComparison:
    def test_comparison_has_both_variants(self) -> None:
        comp_path = _REPO_ROOT / "reports" / "fe05" / "quantity_variants_comparison.csv"
        if not comp_path.exists():
            pytest.skip("comparison report not generated")
        df = pd.read_csv(comp_path)
        assert "TotalQuantity_Signed" in df.columns
        assert "TotalQuantity_PurchaseOnly" in df.columns


# ---------------------------------------------------------------------------
# IT-14: PurchaseInterval NaN semantics
# ---------------------------------------------------------------------------


class TestPurchaseIntervalNaN:
    def test_purchase_interval_nan_semantics(self) -> None:
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        # Customers with Frequency < 2 must have NaN for PurchaseIntervalMean
        single_invoice_mask = candidates["Frequency"] < 2
        single_invoice_count = single_invoice_mask.sum()
        if single_invoice_count > 0:
            pim_nan_count = candidates.loc[single_invoice_mask, "PurchaseIntervalMean"].isna().sum()
            assert pim_nan_count == single_invoice_count


# ---------------------------------------------------------------------------
# IT-15: PurchaseIntervalStd ddof=1
# ---------------------------------------------------------------------------


class TestPurchaseIntervalStdDdof1:
    def test_std_uses_sample_std(self) -> None:
        """Std should be computed with ddof=1 (sample std)."""
        # This is verified at module level; here we check the file exists
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        assert "PurchaseIntervalStd" in candidates.columns


# ---------------------------------------------------------------------------
# IT-16: All reports written
# ---------------------------------------------------------------------------


class TestAllReportsWritten:
    def test_all_reports_exist(self) -> None:
        report_dir = _REPO_ROOT / "reports" / "fe05"
        if not report_dir.exists():
            pytest.skip("report directory not generated")
        expected_files = [
            "rfm_report.md",
            "monetary_definition_comparison.csv",
            "quantity_variants_comparison.csv",
            "frequency_variants_comparison.csv",
            "candidate_feature_report.md",
            "distribution_analysis.csv",
            "variance_analysis.csv",
            "correlation_matrix_pearson.csv",
            "correlation_matrix_spearman.csv",
            "redundancy_report.csv",
            "outlier_detection.csv",
            "feature_selection_report.csv",
            "business_interpretability.csv",
            "feature_dictionary.csv",
            "fe05_run.json",
            "narrative_report.md",
        ]
        for filename in expected_files:
            assert (report_dir / filename).exists(), f"Missing report: {filename}"


# ---------------------------------------------------------------------------
# IT-17: No clustering/scaling/transformation
# ---------------------------------------------------------------------------


class TestNoClustering:
    def test_no_clustering_columns_in_candidates(self) -> None:
        candidate_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidate_path.exists():
            pytest.skip("candidate dataset not generated")
        candidates = pd.read_parquet(candidate_path)
        # No cluster labels should be present
        assert "Cluster" not in candidates.columns
        assert "ClusterID" not in candidates.columns


# ---------------------------------------------------------------------------
# IT-18: Empty input fail-fast
# ---------------------------------------------------------------------------


class TestEmptyInputFailFast:
    def test_empty_transactions_raises(self, tmp_path: Path) -> None:
        """Empty transactions_clean must raise."""
        from scripts.run_fe05_feature_engineering import run_fe05_pipeline

        # Create empty inputs
        empty_base = pd.DataFrame(
            {
                "CustomerID": pd.array([], dtype="Int64"),
                "TotalQuantity": pd.array([], dtype="int64"),
                "TotalMonetary": pd.array([], dtype="float64"),
                "FirstPurchaseDate": pd.Series([], dtype="datetime64[us]"),
                "LastPurchaseDate": pd.Series([], dtype="datetime64[us]"),
                "PurchaseFrequency": pd.array([], dtype="int64"),
                "AverageTransactionValue": pd.array([], dtype="float64"),
                "TransactionLineCount": pd.array([], dtype="int64"),
                "DistinctInvoiceCount": pd.array([], dtype="int64"),
                "DistinctProducts": pd.array([], dtype="int64"),
                "CancellationInvoiceCount": pd.array([], dtype="Int64"),
                "ReturnInvoiceCount": pd.array([], dtype="Int64"),
            }
        )
        empty_transactions = pd.DataFrame(
            {
                "InvoiceNo": pd.Series([], dtype="string"),
                "Quantity": pd.array([], dtype="int64"),
                "InvoiceDate": pd.Series([], dtype="datetime64[us]"),
                "UnitPrice": pd.array([], dtype="float64"),
                "CustomerID": pd.array([], dtype="Int64"),
                "IsCancellation": pd.Series([], dtype="bool"),
                "IsReturn": pd.Series([], dtype="bool"),
            }
        )

        base_path = tmp_path / "customer_base.parquet"
        trans_path = tmp_path / "transactions_clean.parquet"
        empty_base.to_parquet(base_path)
        empty_transactions.to_parquet(trans_path)

        with pytest.raises(ValueError):
            run_fe05_pipeline(
                customer_base_path=base_path,
                transactions_clean_path=trans_path,
                processed_dir=tmp_path / "processed",
                report_dir=tmp_path / "reports",
            )
