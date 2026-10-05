"""Tests for FE-05 analysis module.

T-AN-01 → T-AN-07
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.features.analysis import (  # noqa: E402
    compute_correlation_matrices,
    compute_distribution_stats,
    compute_variance_stats,
    detect_outliers,
    detect_redundancy,
    select_numeric_candidate_columns,
    shapiro_wilk_diagnostic,
)


@pytest.fixture()
def synthetic_candidates() -> pd.DataFrame:
    np.random.seed(42)
    return pd.DataFrame(
        {
            "CustomerID": pd.array(list(range(1, 101)), dtype="Int64"),
            "Recency": np.random.randint(1, 365, 100),
            "Frequency": np.random.randint(1, 50, 100),
            "Monetary": np.random.uniform(100, 10000, 100),
            "TotalQuantity": np.random.randint(1, 1000, 100),
            "TenureDays": np.random.randint(1, 365, 100),
        }
    )


# ---------------------------------------------------------------------------
# T-AN-01: distribution stats
# ---------------------------------------------------------------------------


class TestDistributionStats:
    def test_distribution_stats_correct(self, synthetic_candidates: pd.DataFrame) -> None:
        result = compute_distribution_stats(synthetic_candidates, ["Recency", "Frequency"])
        assert "Recency" in result.stats_df["Feature"].values
        assert "Frequency" in result.stats_df["Feature"].values


# ---------------------------------------------------------------------------
# T-AN-02: only numeric CANDIDATE features
# ---------------------------------------------------------------------------


class TestNumericCandidateSelection:
    def test_excludes_date_features(self) -> None:
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2],
                "Recency": [10, 20],
                "SomeDate": pd.to_datetime(["2011-01-01", "2011-02-01"]),
            }
        )
        selected = select_numeric_candidate_columns(
            df,
            ["CustomerID", "Recency", "SomeDate"],
            include_date_features=False,
        )
        # CustomerID is not numeric, SomeDate is not included
        assert "Recency" in selected
        assert "SomeDate" not in selected

    def test_includes_only_candidate_features(self) -> None:
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2],
                "Recency": [10, 20],
                "Frequency": [5, 6],
            }
        )
        # Only pass Recency and Frequency as candidates
        selected = select_numeric_candidate_columns(
            df,
            ["Recency"],
        )
        assert "Recency" in selected
        assert "Frequency" not in selected


# ---------------------------------------------------------------------------
# T-AN-03: variance stats
# ---------------------------------------------------------------------------


class TestVarianceStats:
    def test_cv_nan_for_zero_mean(self) -> None:
        """CV = N/A when mean ≈ 0."""
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3],
                "Constant": [5.0, 5.0, 5.0],  # std = 0
                "Zero": [0.0, 0.0, 0.0],
            }
        )
        result = compute_variance_stats(df, ["Constant", "Zero"])
        # Both should have N/A CV
        zero_row = result.stats_df[result.stats_df["Feature"] == "Zero"]
        assert zero_row.iloc[0]["CV"] == "N/A"


# ---------------------------------------------------------------------------
# T-AN-04: correlation matrices
# ---------------------------------------------------------------------------


class TestCorrelationMatrices:
    def test_pearson_and_spearman(self, synthetic_candidates: pd.DataFrame) -> None:
        result = compute_correlation_matrices(
            synthetic_candidates, ["Recency", "Frequency", "Monetary"]
        )
        assert result.pearson.shape == (3, 3)
        assert result.spearman.shape == (3, 3)


# ---------------------------------------------------------------------------
# T-AN-05: redundancy detection
# ---------------------------------------------------------------------------


class TestRedundancyDetection:
    def test_detects_high_correlation(self) -> None:
        """Should detect pairs with |corr| >= threshold."""
        corr = pd.DataFrame(
            {
                "A": [1.0, 0.99, 0.5],
                "B": [0.99, 1.0, 0.3],
                "C": [0.5, 0.3, 1.0],
            },
            index=["A", "B", "C"],
        )
        result = detect_redundancy(corr, threshold=0.95)
        assert len(result.pairs_df) >= 1
        assert result.pairs_df.iloc[0]["AbsCorrelation"] >= 0.95


# ---------------------------------------------------------------------------
# T-AN-06: outlier detection
# ---------------------------------------------------------------------------


class TestOutlierDetection:
    def test_detects_outliers_iqr(self) -> None:
        """Should detect outliers using IQR method."""
        df = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3, 4, 5, 100],
                "Value": [10.0, 11.0, 12.0, 13.0, 14.0, 1000.0],  # 1000 is outlier
            }
        )
        result = detect_outliers(df, ["Value"])
        # Customer 100 should be flagged
        cust100_outlier = result.outliers_per_feature["Value"].loc[5]
        assert cust100_outlier


# ---------------------------------------------------------------------------
# T-AN-07: Shapiro-Wilk = optional diagnostic
# ---------------------------------------------------------------------------


class TestShapiroWilkDiagnostic:
    def test_returns_diagnostic_results(self, synthetic_candidates: pd.DataFrame) -> None:
        result = shapiro_wilk_diagnostic(
            synthetic_candidates, ["Recency", "Frequency"], alpha=0.05, random_seed=42
        )
        assert "Feature" in result.columns
        assert "PValue" in result.columns
        assert "IsNormal" in result.columns
        # Note column should mention "Optional diagnostic only"
        assert all("Optional diagnostic" in note for note in result["Note"].values)
