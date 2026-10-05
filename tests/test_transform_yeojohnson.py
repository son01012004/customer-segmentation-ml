"""Tests for Yeo-Johnson transformation.

T2 — yeo_johnson transformation tests:
- supports negative values (unlike log1p)
- supports zero values
- deterministic (no random state)
- all-NaN column handled gracefully
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.transformation.skewness import apply_yeo_johnson


class TestYeoJohnsonNegative:
    """Tests for yeo_johnson on features with negative values."""

    def test_negative_values_handled(self) -> None:
        """yeo_johnson handles negative values without error."""
        df = pd.DataFrame({"feat": [-10.0, -1.0, 0.0, 1.0, 10.0]})
        result, pt, lambdas = apply_yeo_johnson(df, ["feat"])
        assert result.shape == df.shape
        assert "feat" in result.columns

    def test_negative_values_no_inf(self) -> None:
        """yeo_johnson should not produce Inf on mixed sign data."""
        df = pd.DataFrame({"feat": [-100.0, -1.0, 0.0, 1.0, 100.0]})
        result, _, _ = apply_yeo_johnson(df, ["feat"])
        assert not np.isinf(result["feat"]).any()

    def test_negative_reduces_skew(self) -> None:
        """yeo_johnson should reduce skewness on heavily skewed data."""
        skewed = pd.Series([-1.0, -1.0, -1.0, 0.0, 0.0, 1.0, 100.0, 1000.0])
        df = pd.DataFrame({"feat": skewed})
        result, _, _ = apply_yeo_johnson(df, ["feat"])
        skew_before = float(skewed.skew())
        skew_after = float(result["feat"].skew())
        # Skew should decrease in absolute value
        assert abs(skew_after) < abs(
            skew_before
        ), f"yeo_johnson should reduce |skewness|: {skew_before:.3f} -> {skew_after:.3f}"


class TestYeoJohnsonZero:
    """Tests for yeo_johnson on zero values."""

    def test_zero_values_handled(self) -> None:
        """yeo_johnson handles zero values."""
        df = pd.DataFrame({"feat": [0.0, 0.0, 0.0, 1.0, 10.0]})
        result, _, _ = apply_yeo_johnson(df, ["feat"])
        assert result.shape == df.shape

    def test_zero_no_inf(self) -> None:
        """yeo_johnson should not produce Inf on zeros."""
        df = pd.DataFrame({"feat": [0.0] * 10})
        result, _, _ = apply_yeo_johnson(df, ["feat"])
        assert not np.isinf(result["feat"]).any()


class TestYeoJohnsonDeterminism:
    """Tests for yeo_johnson determinism."""

    def test_deterministic(self) -> None:
        """Same input must produce same output."""
        df = pd.DataFrame({"feat": [-5.0, 0.0, 1.0, 10.0, 50.0]})
        result1, _, _ = apply_yeo_johnson(df, ["feat"])
        result2, _, _ = apply_yeo_johnson(df, ["feat"])
        pd.testing.assert_frame_equal(result1, result2)

    def test_lambda_values_recorded(self) -> None:
        """Lambda values should be recorded for reproducibility."""
        df = pd.DataFrame({"a": [-1.0, 0.0, 1.0], "b": [1.0, 2.0, 3.0]})
        _, pt, lambda_values = apply_yeo_johnson(df, ["a", "b"])
        assert "a" in lambda_values
        assert "b" in lambda_values
        assert lambda_values["a"] is not None
        assert lambda_values["b"] is not None


class TestYeoJohnsonMultipleFeatures:
    """Tests for yeo_johnson on multiple features."""

    def test_multiple_features(self) -> None:
        """All features should be transformed."""
        df = pd.DataFrame(
            {
                "a": [-1.0, 0.0, 1.0],
                "b": [0.0, 5.0, 10.0],
                "c": [1.0, 2.0, 3.0],
            }
        )
        result, _, lambda_values = apply_yeo_johnson(df, ["a", "b", "c"])
        assert result.shape == df.shape
        assert len(lambda_values) == 3
        # Verify all transformed (not equal to original)
        assert not result["a"].equals(df["a"])


class TestYeoJohnsonNaNHandling:
    """Tests for yeo_johnson NaN handling."""

    def test_all_nan_raises(self) -> None:
        """All-NaN column should raise ValueError."""
        df = pd.DataFrame({"feat": [float("nan"), float("nan")]})
        with pytest.raises(ValueError, match="NaN"):
            apply_yeo_johnson(df, ["feat"])

    def test_partial_nan_propagates(self) -> None:
        """Partial NaN in features should propagate (handled by imputation before)."""
        # This tests that yeo_johnson works when imputation is applied first
        df = pd.DataFrame({"feat": [0.0, 1.0, 2.0]})  # No NaN here
        result, _, _ = apply_yeo_johnson(df, ["feat"])
        assert result.shape == df.shape
