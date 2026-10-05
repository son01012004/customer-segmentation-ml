"""Unit tests for :mod:`customer_segmentation.outlier_analysis.distribution`.

All tests use synthetic Series. No raw dataset, no FE-02 parquet.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.outlier_analysis.distribution import (
    DEFAULT_PERCENTILES,
    compute_iqr_bounds,
    compute_percentiles,
    distribution_profile,
    skewness,
    summarise_distribution_dataframe,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_series() -> pd.Series:
    """A small well-behaved series with known statistics."""
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], name="Quantity")


@pytest.fixture()
def skewed_series() -> pd.Series:
    """A strongly right-skewed series."""
    return pd.Series(
        [1.0, 1.0, 1.0, 2.0, 2.0, 3.0, 4.0, 5.0, 100.0, 1000.0],
        name="Monetary",
    )


@pytest.fixture()
def series_with_negatives() -> pd.Series:
    return pd.Series([-5.0, -1.0, 0.0, 0.0, 1.0, 5.0], name="Mixed")


@pytest.fixture()
def series_with_nan() -> pd.Series:
    return pd.Series([1.0, np.nan, 3.0, np.nan, 5.0], name="WithNaN")


# ---------------------------------------------------------------------------
# skewness()
# ---------------------------------------------------------------------------


class TestSkewness:
    def test_zero_for_symmetric(self) -> None:
        s = pd.Series([-2.0, -1.0, 0.0, 1.0, 2.0])
        assert abs(float(skewness(s))) < 1e-9

    def test_positive_for_right_skewed(self) -> None:
        s = pd.Series([1.0, 1.0, 1.0, 1.0, 100.0])
        assert float(skewness(s)) > 0

    def test_nan_for_empty(self) -> None:
        s = pd.Series([], dtype=float)
        assert math.isnan(float(skewness(s)))

    def test_nan_for_all_nan(self) -> None:
        s = pd.Series([np.nan, np.nan], dtype=float)
        assert math.isnan(float(skewness(s)))

    def test_ignores_nan(self) -> None:
        s = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0])
        out = float(skewness(s))
        assert not math.isnan(out)
        # Compare to non-NaN version.
        ref = float(skewness(pd.Series([1.0, 2.0, 4.0, 5.0])))
        assert abs(out - ref) < 1e-9


# ---------------------------------------------------------------------------
# compute_percentiles()
# ---------------------------------------------------------------------------


class TestComputePercentiles:
    def test_known_quantiles(self, simple_series: pd.Series) -> None:
        out = compute_percentiles(simple_series, [25, 50, 75])
        # 25th percentile of [1..10] is 3.25 (linear interp), 50th is 5.5, 75th is 7.75.
        assert abs(out["p25"] - 3.25) < 1e-9
        assert abs(out["p50"] - 5.5) < 1e-9
        assert abs(out["p75"] - 7.75) < 1e-9

    def test_default_set_contains_p99_9(self) -> None:
        assert 99.9 in DEFAULT_PERCENTILES

    def test_empty_returns_nan(self) -> None:
        s = pd.Series([], dtype=float)
        out = compute_percentiles(s, [25, 50])
        assert math.isnan(out["p25"])
        assert math.isnan(out["p50"])

    def test_label_formatting(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        out = compute_percentiles(s, [1, 99, 99.5, 99.9])
        assert "p1" in out
        assert "p99" in out
        assert "p99.5" in out
        assert "p99.9" in out

    def test_ignores_nan(self, series_with_nan: pd.Series) -> None:
        out = compute_percentiles(series_with_nan, [50])
        # Median of [1, 3, 5] = 3.
        assert abs(out["p50"] - 3.0) < 1e-9


# ---------------------------------------------------------------------------
# compute_iqr_bounds()
# ---------------------------------------------------------------------------


class TestComputeIQRBounds:
    def test_known_bounds(self, simple_series: pd.Series) -> None:
        lo, hi = compute_iqr_bounds(simple_series, multiplier=1.5)
        # Q1=3.25, Q3=7.75, IQR=4.5
        # lower = 3.25 − 1.5·4.5 = -3.5
        # upper = 7.75 + 1.5·4.5 = 14.5
        assert abs(lo - (-3.5)) < 1e-9
        assert abs(hi - 14.5) < 1e-9

    def test_multiplier_scaling(self, simple_series: pd.Series) -> None:
        lo15, hi15 = compute_iqr_bounds(simple_series, multiplier=1.5)
        lo30, hi30 = compute_iqr_bounds(simple_series, multiplier=3.0)
        # Wider multiplier → wider fences.
        assert lo30 < lo15
        assert hi30 > hi15

    def test_empty_returns_nan(self) -> None:
        lo, hi = compute_iqr_bounds(pd.Series([], dtype=float))
        assert math.isnan(lo)
        assert math.isnan(hi)


# ---------------------------------------------------------------------------
# distribution_profile()
# ---------------------------------------------------------------------------


class TestDistributionProfile:
    def test_basic_fields(self, simple_series: pd.Series) -> None:
        prof = distribution_profile(simple_series)
        assert prof.column == "Quantity"
        assert prof.count == 10
        assert prof.missing_count == 0
        assert prof.missing_rate == 0.0
        assert prof.total_rows == 10
        assert prof.min == 1.0
        assert prof.max == 10.0
        assert prof.mean == 5.5
        assert prof.median == 5.5
        assert prof.zero_count == 0
        assert prof.negative_count == 0

    def test_q1_q3_iqr(self, simple_series: pd.Series) -> None:
        prof = distribution_profile(simple_series)
        assert abs(prof.q1 - 3.25) < 1e-9
        assert abs(prof.q3 - 7.75) < 1e-9
        assert abs(prof.iqr - 4.5) < 1e-9

    def test_skewness_for_symmetric(self, simple_series: pd.Series) -> None:
        prof = distribution_profile(simple_series)
        assert abs(prof.skewness) < 0.5  # very small for symmetric

    def test_skewness_for_right_skewed(self, skewed_series: pd.Series) -> None:
        prof = distribution_profile(skewed_series)
        assert prof.skewness > 1.0

    def test_negative_and_zero_counts(self, series_with_negatives: pd.Series) -> None:
        prof = distribution_profile(series_with_negatives)
        assert prof.negative_count == 2
        assert prof.zero_count == 2

    def test_missing_count(self, series_with_nan: pd.Series) -> None:
        prof = distribution_profile(series_with_nan, total_rows=10)
        assert prof.missing_count == 2
        assert prof.missing_rate == pytest.approx(0.2, abs=1e-9)
        assert prof.count == 3

    def test_percentiles_default_set(self, simple_series: pd.Series) -> None:
        prof = distribution_profile(simple_series)
        # All default percentiles must be present.
        for label in ["p1", "p5", "p25", "p50", "p75", "p90", "p95", "p99", "p99.5", "p99.9"]:
            assert label in prof.percentiles

    def test_custom_percentiles(self, simple_series: pd.Series) -> None:
        prof = distribution_profile(simple_series, percentiles=[42.0])
        assert "p42" in prof.percentiles

    def test_empty_series(self) -> None:
        s = pd.Series([], dtype=float, name="Empty")
        prof = distribution_profile(s)
        assert prof.count == 0
        assert math.isnan(prof.mean)
        assert math.isnan(prof.median)
        assert prof.percentiles  # all-NaN percentiles

    def test_rejects_non_numeric(self) -> None:
        s = pd.Series(["a", "b", "c"], name="Text")
        with pytest.raises(TypeError, match="numeric"):
            distribution_profile(s)

    def test_to_dict_has_all_fields(self, simple_series: pd.Series) -> None:
        prof = distribution_profile(simple_series)
        d = prof.to_dict()
        for k in (
            "column",
            "count",
            "missing_count",
            "missing_rate",
            "total_rows",
            "min",
            "max",
            "mean",
            "median",
            "std",
            "q1",
            "q3",
            "iqr",
            "zero_count",
            "negative_count",
            "skewness",
            "p1",
            "p99.9",
        ):
            assert k in d

    def test_column_override(self) -> None:
        s = pd.Series([1.0, 2.0], name="orig")
        prof = distribution_profile(s, column="custom")
        assert prof.column == "custom"

    def test_input_not_mutated(self, simple_series: pd.Series) -> None:
        snapshot = simple_series.copy(deep=True)
        _ = distribution_profile(simple_series)
        assert simple_series.equals(snapshot)


# ---------------------------------------------------------------------------
# summarise_distribution_dataframe()
# ---------------------------------------------------------------------------


class TestSummarise:
    def test_one_row_per_input(self) -> None:
        s1 = pd.Series([1.0, 2.0, 3.0], name="A")
        s2 = pd.Series([4.0, 5.0, 6.0], name="B")
        df = summarise_distribution_dataframe({"A": s1, "B": s2})
        assert df.shape[0] == 2
        assert set(df["column"].tolist()) == {"A", "B"}

    def test_shared_total_rows(self) -> None:
        s1 = pd.Series([1.0, np.nan], name="A")
        s2 = pd.Series([5.0, 6.0], name="B")
        df = summarise_distribution_dataframe({"A": s1, "B": s2}, total_rows=10)
        row_a = df[df["column"] == "A"].iloc[0]
        row_b = df[df["column"] == "B"].iloc[0]
        assert row_a["missing_count"] == 1
        assert row_b["missing_count"] == 0
        # Both should report total_rows=10 (and rate computed against it).
        assert int(row_a["total_rows"]) == 10
        assert int(row_b["total_rows"]) == 10

    def test_columns_match_to_dict(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0], name="X")
        df = summarise_distribution_dataframe({"X": s})
        prof = distribution_profile(s)
        for k in prof.to_dict():
            assert k in df.columns
