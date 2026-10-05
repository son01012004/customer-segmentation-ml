"""Tests for log1p transformation.

T1 — log1p transformation tests:
- positive values -> output > 0, deterministic
- zero -> log1p(0) = 0
- negative values must raise ValueError (not silently apply)
- deterministic output
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.transformation.skewness import (
    apply_log1p,
    apply_none,
    apply_transformation,
)


class TestLog1pPositive:
    """Tests for log1p on positive values."""

    def test_positive_values_positive_output(self) -> None:
        """log1p(x) > 0 for x >= 0."""
        series = pd.Series([0.0, 1.0, 10.0, 100.0])
        df = pd.DataFrame({"feat": series})
        result = apply_log1p(df, ["feat"])
        assert (
            result["feat"] >= 0
        ).all(), "log1p should produce non-negative output for non-negative input"

    def test_zero_becomes_zero(self) -> None:
        """log1p(0) = 0."""
        df = pd.DataFrame({"feat": [0.0, 0.0, 0.0]})
        result = apply_log1p(df, ["feat"])
        assert (result["feat"] == 0.0).all()

    def test_positive_decreases_skew(self) -> None:
        """log1p should reduce right skewness on heavily skewed data."""
        skewed = pd.Series([1.0, 2.0, 3.0, 10.0, 100.0, 1000.0, 10000.0])
        df = pd.DataFrame({"feat": skewed})
        result = apply_log1p(df, ["feat"])
        skew_before = float(skewed.skew())
        skew_after = float(result["feat"].skew())
        assert (
            skew_after < skew_before
        ), f"log1p should reduce skewness: {skew_before:.3f} -> {skew_after:.3f}"

    def test_deterministic(self) -> None:
        """Same input must produce same output."""
        df = pd.DataFrame({"feat": [1.0, 5.0, 10.0, 50.0]})
        result1 = apply_log1p(df, ["feat"])
        result2 = apply_log1p(df, ["feat"])
        pd.testing.assert_frame_equal(result1, result2)


class TestLog1pNegative:
    """Tests for log1p on negative values (must reject)."""

    def test_negative_raises_value_error(self) -> None:
        """log1p on negative values must raise ValueError."""
        df = pd.DataFrame({"feat": [1.0, -1.0, 5.0]})
        with pytest.raises(ValueError, match="negative"):
            apply_log1p(df, ["feat"])

    def test_single_negative_value_raises(self) -> None:
        """Single negative value must raise."""
        df = pd.DataFrame({"feat": [-0.5]})
        with pytest.raises(ValueError, match="negative"):
            apply_log1p(df, ["feat"])


class TestApplyNone:
    """Tests for identity transformation (T0)."""

    def test_identity_transform(self) -> None:
        """none returns same DataFrame."""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
        result = apply_none(df, ["a", "b"])
        pd.testing.assert_frame_equal(result, df)

    def test_none_does_not_modify(self) -> None:
        """none should not modify any values."""
        df = pd.DataFrame({"feat": [0.0, 100.0, 1000.0]})
        result = apply_none(df, ["feat"])
        assert result["feat"].tolist() == [0.0, 100.0, 1000.0]


class TestApplyTransformation:
    """Tests for apply_transformation dispatcher."""

    def test_none_method(self) -> None:
        """apply_transformation with 'none' calls apply_none."""
        df = pd.DataFrame({"feat": [1.0, 2.0]})
        result = apply_transformation(df, ["feat"], "none")
        assert result.method == "none"
        pd.testing.assert_frame_equal(result.df, df)

    def test_log1p_method(self) -> None:
        """apply_transformation with 'log1p' calls apply_log1p."""
        df = pd.DataFrame({"feat": [0.0, 1.0, 10.0]})
        result = apply_transformation(df, ["feat"], "log1p")
        assert result.method == "log1p"
        assert (result.df["feat"] >= 0).all()

    def test_unknown_method_raises(self) -> None:
        """Unknown method raises ValueError."""
        df = pd.DataFrame({"feat": [1.0]})
        with pytest.raises(ValueError, match="Unknown"):
            apply_transformation(df, ["feat"], "unknown")
