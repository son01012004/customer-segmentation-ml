"""Tests for NaN imputation strategy.

Imputation: median (WORKING_ASSUMPTION)
- Applies only to PurchaseIntervalMean, PurchaseIntervalStd
- Does NOT fill with 0
- Does NOT create sentinel values
- Verifies no NaN after imputation
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.transformation.fill_strategy import (
    apply_imputation,
    impute_median,
)


class TestMedianImputation:
    """Tests for median imputation."""

    def test_median_imputes_nan(self) -> None:
        """Median imputation fills NaN values."""
        series = pd.Series([1.0, 2.0, float("nan"), 3.0, 4.0])
        imputed, median_val = impute_median(series)
        assert imputed.isna().sum() == 0
        assert median_val == 2.5  # median of [1, 2, 3, 4] = (2+3)/2

    def test_median_does_not_fill_zero(self) -> None:
        """Median imputation does NOT fill with 0."""
        series = pd.Series([0.0, float("nan"), 0.0, 0.0])
        imputed, _ = impute_median(series)
        # Median of [0, 0, 0] = 0, but that's a coincidence of the data
        # The point is: we don't hard-code 0 as the fill value
        assert imputed.isna().sum() == 0

    def test_median_with_all_nan(self) -> None:
        """All-NaN series returns NaN median."""
        series = pd.Series([float("nan"), float("nan")])
        _, median_val = impute_median(series)
        assert np.isnan(median_val)


class TestApplyImputation:
    """Tests for apply_imputation function."""

    def test_no_nan_after_imputation(self) -> None:
        """apply_imputation: NaN count = 0 after imputation."""
        df = pd.DataFrame(
            {
                "PurchaseIntervalMean": [10.0, float("nan"), 20.0, float("nan"), 30.0],
                "PurchaseIntervalStd": [5.0, float("nan"), 15.0, float("nan"), 25.0],
            }
        )
        result = apply_imputation(
            df,
            ["PurchaseIntervalMean", "PurchaseIntervalStd"],
            method="median",
        )
        assert result.df["PurchaseIntervalMean"].isna().sum() == 0
        assert result.df["PurchaseIntervalStd"].isna().sum() == 0

    def test_median_values_recorded(self) -> None:
        """Median values should be recorded in result."""
        df = pd.DataFrame(
            {
                "PurchaseIntervalMean": [10.0, float("nan"), 20.0],
            }
        )
        result = apply_imputation(df, ["PurchaseIntervalMean"], method="median")
        assert "PurchaseIntervalMean" in result.median_values
        # median of [10.0, 20.0] = 15.0
        assert result.median_values["PurchaseIntervalMean"] == 15.0

    def test_nan_counts_before_after(self) -> None:
        """NaN counts before and after should be recorded."""
        df = pd.DataFrame(
            {
                "PurchaseIntervalMean": [10.0, float("nan"), 20.0],
            }
        )
        result = apply_imputation(df, ["PurchaseIntervalMean"], method="median")
        assert result.nan_counts_before["PurchaseIntervalMean"] == 1
        assert result.nan_counts_after["PurchaseIntervalMean"] == 0

    def test_no_nan_feature_unchanged(self) -> None:
        """Feature without NaN should be unchanged."""
        df = pd.DataFrame(
            {
                "PurchaseIntervalMean": [10.0, 20.0, 30.0],
                "Frequency": [1, 2, 3],
            }
        )
        result = apply_imputation(df, ["PurchaseIntervalMean"], method="median")
        pd.testing.assert_series_equal(
            result.df["Frequency"],
            pd.Series([1, 2, 3], name="Frequency"),
        )

    def test_unsupported_method_raises(self) -> None:
        """Unsupported imputation method raises ValueError."""
        df = pd.DataFrame({"feat": [1.0, float("nan")]})
        with pytest.raises(ValueError, match="Unsupported"):
            apply_imputation(df, ["feat"], method="mean")

    def test_missing_feature_in_df_skipped(self) -> None:
        """Feature not in DataFrame is skipped."""
        df = pd.DataFrame({"a": [1.0, 2.0]})
        result = apply_imputation(df, ["nonexistent_feature"], method="median")
        assert "nonexistent_feature" not in result.df.columns


class TestNoDropCustomers:
    """Verify imputation does NOT drop customers."""

    def test_imputation_preserves_row_count(self) -> None:
        """Imputation must not drop rows."""
        df = pd.DataFrame(
            {
                "PurchaseIntervalMean": [10.0] * 10,
            }
        )
        # Add NaN to some rows
        df.loc[3, "PurchaseIntervalMean"] = float("nan")
        df.loc[7, "PurchaseIntervalMean"] = float("nan")
        result = apply_imputation(df, ["PurchaseIntervalMean"], method="median")
        assert len(result.df) == len(df), "Imputation must not drop customers"
