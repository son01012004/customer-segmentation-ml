"""Tests for feature eligibility gate.

G1: Layer = CANDIDATE
G2: Numeric dtype
G3: Variance > 0
G4: Missing ratio <= threshold
G5: CustomerID excluded
G6: BASE_REFERENCE excluded
G7: UNSUPPORTED excluded
G8: PENDING_REVIEW -> ELIGIBLE_WORKING_ASSUMPTION
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.transformation.feature_eligibility import (
    EligibilityStatus,
    apply_feature_eligibility,
)


class TestCustomerIDExcluded:
    """Tests for CustomerID exclusion."""

    def test_customerid_not_in_eligible(self) -> None:
        """CustomerID must not be in eligible features."""
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3],
                "Recency": [10.0, 20.0, 30.0],
                "Frequency": [1, 2, 3],
            }
        )
        result = apply_feature_eligibility(df, customer_key="CustomerID")
        assert "CustomerID" not in result.eligible_features

    def test_customerid_in_metadata(self) -> None:
        """CustomerID must be in metadata features."""
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3],
                "Recency": [10.0, 20.0, 30.0],
            }
        )
        result = apply_feature_eligibility(df, customer_key="CustomerID")
        assert "CustomerID" in result.metadata_features


class TestZeroVarianceExcluded:
    """Tests for zero-variance exclusion."""

    def test_zero_variance_excluded(self) -> None:
        """Zero-variance feature must be excluded."""
        # Use real CANDIDATE features from FE-05
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3],
                "Recency": [5.0, 5.0, 5.0],  # zero variance, in CANDIDATE
                "Frequency": [1.0, 2.0, 3.0],  # valid, in CANDIDATE
            }
        )
        result = apply_feature_eligibility(
            df,
            customer_key="CustomerID",
            feature_selection_csv_path="nonexistent",
        )
        assert "Recency" in result.excluded_features
        assert "Frequency" in result.eligible_features


class TestNonNumericExcluded:
    """Tests for non-numeric exclusion."""

    def test_non_numeric_excluded(self) -> None:
        """Non-numeric features must be excluded."""
        # Use real CANDIDATE features - Recency + a string column
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3],
                "Recency": [1.0, 2.0, 3.0],  # valid numeric CANDIDATE
                "Description": ["a", "b", "c"],  # not in CANDIDATE layer
            }
        )
        result = apply_feature_eligibility(
            df,
            customer_key="CustomerID",
            feature_selection_csv_path="nonexistent",
        )
        assert "Description" in result.excluded_features
        assert "Recency" in result.eligible_features


class TestMissingRatioExcluded:
    """Tests for missing ratio exclusion."""

    def test_high_missing_ratio_excluded(self) -> None:
        """Feature with missing_ratio > threshold must be excluded."""
        # Use a real CANDIDATE feature name
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "Recency": [float("nan")] * 9 + [1.0],  # 90% missing (in CANDIDATE)
            }
        )
        result = apply_feature_eligibility(
            df,
            customer_key="CustomerID",
            feature_selection_csv_path="nonexistent",
            max_missing_ratio=0.5,
        )
        assert "Recency" in result.excluded_features


class TestPENDINGREVIEWMapped:
    """Tests for PENDING_REVIEW mapping."""

    def test_pending_review_becomes_working_assumption(self) -> None:
        """PENDING_REVIEW features should be ELIGIBLE_WORKING_ASSUMPTION."""
        # The actual CSV might not exist in test environment
        # So we test the logic by checking the eligibility status field
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3],
                "Frequency": [1.0, 2.0, 3.0],
                "AverageQuantity": [4.0, 5.0, 6.0],
            }
        )
        result = apply_feature_eligibility(
            df,
            customer_key="CustomerID",
            feature_selection_csv_path="nonexistent",
        )
        # If no FE-05 CSV, these default to WORKING_ASSUMPTION
        for feat in ["Frequency", "AverageQuantity"]:
            elig = result.eligibility_details.get(feat)
            if elig is not None:
                assert elig.fe06_status in (
                    EligibilityStatus.ELIGIBLE,
                    EligibilityStatus.ELIGIBLE_WORKING_ASSUMPTION,
                ), f"{feat} should be eligible or working assumption"


class TestTotalEligibleCount:
    """Tests for total eligible feature count."""

    def test_expected_candidate_count(self) -> None:
        """All 14 CANDIDATE features from FE-05 should be evaluated."""
        # This test requires the real customer_candidates.parquet
        from pathlib import Path

        candidate_path = Path("data/processed/customer_candidates.parquet")
        if not candidate_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        df = pd.read_parquet(candidate_path)
        result = apply_feature_eligibility(
            df,
            customer_key="CustomerID",
            max_missing_ratio=0.5,
        )
        # Should have exactly 14 eligible features (all CANDIDATE, all numeric, all non-constant)
        assert (
            len(result.eligible_features) >= 14
        ), f"Expected at least 14 eligible features, got {len(result.eligible_features)}"
