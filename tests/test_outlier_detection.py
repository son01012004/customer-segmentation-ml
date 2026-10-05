"""Unit tests for :mod:`customer_segmentation.outlier_analysis.detection`.

Uses synthetic Series/DataFrames. No raw dataset, no FE-02 parquet.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.outlier_analysis.detection import (
    DetectionRecord,
    build_detection_summary_table,
    detect_for_feature,
    detect_outliers_dataframe,
    iqr_bounds,
    iqr_mask,
    percentile_bounds,
    percentile_mask,
    summarise_detection_for_features,
    summarise_outliers_dataframe,
    zscore_bounds,
    zscore_mask,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def symmetric_series() -> pd.Series:
    """Series with the extreme values at index 0 and -1.

    Layout: ``[-50.0, 1.0, 2.0, ..., 9.0, 10.0, 100.0]`` so ``iloc[0]``
    and ``iloc[-1]`` are the obvious outliers.
    """
    return pd.Series(
        [-50.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 100.0],
        name="Quantity",
    )


@pytest.fixture()
def small_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Quantity": [1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 200.0],
            "UnitPrice": [0.5, 1.0, 1.5, 2.0, 2.5, 100.0, 200.0],
        }
    )


# ---------------------------------------------------------------------------
# IQR
# ---------------------------------------------------------------------------


class TestIQR:
    def test_bounds_known(self, symmetric_series: pd.Series) -> None:
        lo, hi = iqr_bounds(symmetric_series, multiplier=1.5)
        # Recompute Q1, Q3, IQR on the SAME series and compare.
        non_na = symmetric_series.dropna()
        q1 = float(non_na.quantile(0.25))
        q3 = float(non_na.quantile(0.75))
        iqr = q3 - q1
        assert abs(lo - (q1 - 1.5 * iqr)) < 1e-9
        assert abs(hi - (q3 + 1.5 * iqr)) < 1e-9

    def test_mask_flags_outliers(self, symmetric_series: pd.Series) -> None:
        mask, lo, hi = iqr_mask(symmetric_series, multiplier=1.5)
        # The extreme values -50 and 100 are outside the IQR fences.
        assert int(mask.sum()) >= 1
        # And the actual extreme values are flagged (both -50 and 100).
        assert bool(mask.iloc[0])  # -50
        assert bool(mask.iloc[-1])  # 100

    def test_multiplier_wider_fewer_flags(self, symmetric_series: pd.Series) -> None:
        m15, _, _ = iqr_mask(symmetric_series, multiplier=1.5)
        m30, _, _ = iqr_mask(symmetric_series, multiplier=3.0)
        # Wider multiplier → fewer flags (or equal).
        assert int(m30.sum()) <= int(m15.sum())

    def test_empty(self) -> None:
        lo, hi = iqr_bounds(pd.Series([], dtype=float))
        assert math.isnan(lo)
        assert math.isnan(hi)

    def test_input_not_mutated(self, symmetric_series: pd.Series) -> None:
        snapshot = symmetric_series.copy(deep=True)
        _ = iqr_mask(symmetric_series)
        assert symmetric_series.equals(snapshot)


# ---------------------------------------------------------------------------
# Z-score
# ---------------------------------------------------------------------------


class TestZScore:
    def test_bounds_around_mean(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        lo, hi = zscore_bounds(s, threshold=3.0)
        # Mean=3, std≈1.414. lo≈-1.24, hi≈7.24.
        assert 3 - 1e-9 < lo < 3 + 1e-9 or abs(lo - (3 - 3 * 1.41421356)) < 1e-3

    def test_mask_for_obvious_outlier(self) -> None:
        rng = np.random.default_rng(seed=0)
        s = pd.Series(np.concatenate([rng.normal(loc=5.0, scale=1.0, size=200), [1000.0]]))
        mask, lo, hi = zscore_mask(s, threshold=3.0)
        # The 1000 outlier is almost certainly above the upper fence.
        assert int(mask.sum()) >= 1

    def test_zero_std_returns_false_mask(self) -> None:
        s = pd.Series([5.0, 5.0, 5.0, 5.0])
        mask, lo, hi = zscore_mask(s, threshold=3.0)
        assert int(mask.sum()) == 0
        assert lo == hi

    def test_input_not_mutated(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 100.0])
        snapshot = s.copy(deep=True)
        _ = zscore_mask(s)
        assert s.equals(snapshot)


# ---------------------------------------------------------------------------
# Percentile
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_bounds_at_quantile(self) -> None:
        s = pd.Series(range(1, 101), dtype=float)  # 1..100
        lo, hi = percentile_bounds(s, upper_percentile=99.0)
        # 99th percentile of [1..100] ≈ 99.01; 1st percentile ≈ 1.99.
        assert 98 <= hi <= 100
        assert 1 <= lo <= 3

    def test_invalid_percentile(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="upper_percentile"):
            percentile_bounds(s, upper_percentile=0)
        with pytest.raises(ValueError, match="upper_percentile"):
            percentile_bounds(s, upper_percentile=100)

    def test_mask_strict_inequality(self) -> None:
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100], dtype=float)
        mask, lo, hi = percentile_mask(s, upper_percentile=90.0)
        # P90 of [1..9, 100] ≈ 18.1, P10 ≈ 1.9.
        # 1 is below 1.9 (flagged). 100 is above 18.1 (flagged).
        assert int(mask.sum()) == 2
        assert bool(mask.iloc[0])  # 1
        assert bool(mask.iloc[-1])  # 100

    def test_empty(self) -> None:
        lo, hi = percentile_bounds(pd.Series([], dtype=float))
        assert math.isnan(lo)
        assert math.isnan(hi)


# ---------------------------------------------------------------------------
# detect_for_feature / DetectionRecord
# ---------------------------------------------------------------------------


class TestDetectForFeature:
    def test_iqr_record_fields(self, symmetric_series: pd.Series) -> None:
        mask, rec = detect_for_feature(
            symmetric_series,
            feature_name="Quantity",
            method="iqr",
            iqr_multiplier=1.5,
            filter_mode="all_rows",
        )
        assert isinstance(rec, DetectionRecord)
        assert rec.feature == "Quantity"
        assert rec.method == "iqr"
        assert rec.threshold == 1.5
        assert rec.total_rows == len(symmetric_series)
        assert rec.candidates == int(mask.sum())
        assert rec.filter_mode == "all_rows"
        assert 0.0 <= rec.rate <= 1.0

    def test_zscore_record(self) -> None:
        # Use a larger, tighter sample so the std is small and the
        # outlier's z-score actually exceeds 3.
        rng = np.random.default_rng(seed=0)
        s = pd.Series(np.concatenate([rng.normal(loc=5.0, scale=1.0, size=200), [1000.0]]))
        _, rec = detect_for_feature(s, feature_name="X", method="zscore", zscore_threshold=3.0)
        assert rec.method == "zscore"
        assert rec.threshold == 3.0
        assert rec.candidates >= 1

    def test_percentile_record(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        _, rec = detect_for_feature(
            s, feature_name="X", method="percentile", percentile_threshold=95.0
        )
        assert rec.method == "percentile"
        assert rec.threshold == 95.0

    def test_unknown_method_raises(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="Unknown detection method"):
            detect_for_feature(s, feature_name="X", method="magic")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# summarise_detection_for_features
# ---------------------------------------------------------------------------


class TestSummariseDetection:
    def test_one_record_per_column(self, small_df: pd.DataFrame) -> None:
        recs = summarise_detection_for_features(
            small_df,
            ["Quantity", "UnitPrice"],
            method="iqr",
            iqr_multiplier=1.5,
            filter_mode="all_rows",
        )
        assert len(recs) == 2
        feats = {r.feature for r in recs}
        assert feats == {"Quantity", "UnitPrice"}

    def test_unknown_column_raises(self, small_df: pd.DataFrame) -> None:
        with pytest.raises(KeyError, match="not in DataFrame"):
            summarise_detection_for_features(small_df, ["NoSuchColumn"])

    def test_non_numeric_raises(self) -> None:
        df = pd.DataFrame({"A": ["x", "y"]})
        with pytest.raises(ValueError, match="numeric"):
            summarise_detection_for_features(df, ["A"])


# ---------------------------------------------------------------------------
# build_detection_summary_table
# ---------------------------------------------------------------------------


class TestBuildSummaryTable:
    def test_empty_input(self) -> None:
        df = build_detection_summary_table([])
        assert df.empty

    def test_one_record(self) -> None:
        rec = DetectionRecord(
            feature="Quantity",
            method="iqr",
            threshold=1.5,
            lower=0.0,
            upper=10.0,
            candidates=2,
            rate=0.1,
            total_rows=20,
            filter_mode="all_rows",
        )
        df = build_detection_summary_table([rec])
        assert df.shape[0] == 1
        assert df.iloc[0]["feature"] == "Quantity"
        assert df.iloc[0]["candidates"] == 2

    def test_sorted_for_determinism(self) -> None:
        records = [
            DetectionRecord("Z", "iqr", 1.5, 0.0, 1.0, 1, 0.5, 2, "all_rows"),
            DetectionRecord("A", "iqr", 1.5, 0.0, 1.0, 1, 0.5, 2, "all_rows"),
            DetectionRecord("A", "zscore", 3.0, 0.0, 1.0, 1, 0.5, 2, "all_rows"),
        ]
        df = build_detection_summary_table(records)
        assert df.iloc[0]["feature"] == "A"
        assert df.iloc[0]["method"] == "iqr"
        assert df.iloc[1]["feature"] == "A"
        assert df.iloc[1]["method"] == "zscore"
        assert df.iloc[2]["feature"] == "Z"


# ---------------------------------------------------------------------------
# Wrappers around preprocessing.outliers
# ---------------------------------------------------------------------------


class TestWrappers:
    def test_detect_outliers_dataframe(self, small_df: pd.DataFrame) -> None:
        out = detect_outliers_dataframe(small_df, ["Quantity"], method="iqr")
        assert "Quantity" in out
        assert isinstance(out["Quantity"], pd.Series)
        assert out["Quantity"].dtype == bool

    def test_summarise_outliers_dataframe(self, small_df: pd.DataFrame) -> None:
        out = summarise_outliers_dataframe(small_df, ["Quantity"], method="iqr")
        assert "column" in out.columns
        assert "outlier_count" in out.columns
        assert out.iloc[0]["column"] == "Quantity"
        assert int(out.iloc[0]["outlier_count"]) >= 0
