"""Unit tests for :mod:`customer_segmentation.outlier_analysis.sensitivity`.

Synthetic Series only.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.config.outlier_loader import SensitivityConfig
from customer_segmentation.outlier_analysis.sensitivity import (
    iqr_sensitivity,
    percentile_sensitivity,
    sensitivity_summary_table,
    sensitivity_table,
    zscore_sensitivity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def skewed_series() -> pd.Series:
    """A clearly heavy-tailed series with a few clear outliers."""
    return pd.Series(
        [1, 1, 1, 2, 2, 2, 3, 3, 4, 5, 100, 200, 500, 1000],
        name="Monetary",
        dtype=float,
    )


# ---------------------------------------------------------------------------
# iqr_sensitivity
# ---------------------------------------------------------------------------


class TestIQRSensitivity:
    def test_shape(self, skewed_series: pd.Series) -> None:
        df = iqr_sensitivity(skewed_series, multipliers=[1.5, 3.0])
        assert df.shape[0] == 2
        assert list(df.columns)[:3] == ["multiplier", "lower", "upper"]

    def test_wider_multiplier_flags_fewer(self, skewed_series: pd.Series) -> None:
        df = iqr_sensitivity(skewed_series, multipliers=[1.5, 3.0])
        n15 = int(df.iloc[0]["candidates"])
        n30 = int(df.iloc[1]["candidates"])
        # Mathematically: wider fences → fewer or equal flags.
        assert n30 <= n15


# ---------------------------------------------------------------------------
# percentile_sensitivity
# ---------------------------------------------------------------------------


class TestPercentileSensitivity:
    def test_higher_percentile_flags_fewer(self, skewed_series: pd.Series) -> None:
        df = percentile_sensitivity(skewed_series, percentiles=[99.0, 99.5, 99.9])
        n99 = int(df.iloc[0]["candidates"])
        n999 = int(df.iloc[-1]["candidates"])
        # Higher percentile → fewer flags (or equal).
        assert n999 <= n99

    def test_columns(self, skewed_series: pd.Series) -> None:
        df = percentile_sensitivity(skewed_series)
        assert "percentile" in df.columns
        assert "candidates" in df.columns
        assert "rate" in df.columns


# ---------------------------------------------------------------------------
# zscore_sensitivity
# ---------------------------------------------------------------------------


class TestZScoreSensitivity:
    def test_default_threshold(self, skewed_series: pd.Series) -> None:
        df = zscore_sensitivity(skewed_series)
        assert df.shape[0] == 1
        assert df.iloc[0]["zscore_threshold"] == 3.0

    def test_heavy_tailed_zscore_may_flag_nothing(self) -> None:
        # A series with std so large that no value is > 3σ away.
        s = pd.Series([0.0, 0.0, 0.0, 0.0, 100000.0])
        df = zscore_sensitivity(s, thresholds=[3.0])
        # It may or may not flag; just assert the function runs.
        assert df.shape[0] == 1


# ---------------------------------------------------------------------------
# sensitivity_table
# ---------------------------------------------------------------------------


class TestSensitivityTable:
    def test_default_config_includes_iqr_percentile_zscore(self, skewed_series: pd.Series) -> None:
        df = sensitivity_table(
            skewed_series,
            feature_name="Monetary",
            filter_mode="all_rows",
        )
        methods = set(df["method"].unique())
        assert "iqr" in methods
        assert "percentile" in methods
        assert "zscore" in methods

    def test_disabled_config_skips_zscore(self, skewed_series: pd.Series) -> None:
        cfg = SensitivityConfig(enabled=False, thresholds=(1.5,), percentiles=(99.0,))
        df = sensitivity_table(
            skewed_series,
            feature_name="Monetary",
            config=cfg,
        )
        methods = set(df["method"].unique())
        assert "zscore" not in methods

    def test_filter_mode_propagates(self, skewed_series: pd.Series) -> None:
        df = sensitivity_table(
            skewed_series,
            feature_name="Monetary",
            filter_mode="clean_purchase",
        )
        assert (df["filter_mode"] == "clean_purchase").all()

    def test_feature_name_propagates(self, skewed_series: pd.Series) -> None:
        df = sensitivity_table(
            skewed_series,
            feature_name="Quantity",
        )
        assert (df["feature"] == "Quantity").all()

    def test_required_columns(self, skewed_series: pd.Series) -> None:
        df = sensitivity_table(skewed_series, feature_name="X")
        for col in (
            "feature",
            "filter_mode",
            "method",
            "threshold",
            "lower",
            "upper",
            "candidates",
            "rate",
            "total_rows",
        ):
            assert col in df.columns

    def test_monotonicity_iqr(self, skewed_series: pd.Series) -> None:
        df = sensitivity_table(skewed_series, feature_name="X")
        iqr_rows = df[df["method"] == "iqr"].sort_values("threshold")
        # Candidates must be non-increasing as threshold grows.
        cands = iqr_rows["candidates"].tolist()
        assert all(cands[i] >= cands[i + 1] for i in range(len(cands) - 1))

    def test_monotonicity_percentile(self, skewed_series: pd.Series) -> None:
        df = sensitivity_table(skewed_series, feature_name="X")
        pct_rows = df[df["method"] == "percentile"].sort_values("threshold")
        cands = pct_rows["candidates"].tolist()
        assert all(cands[i] >= cands[i + 1] for i in range(len(cands) - 1))


# ---------------------------------------------------------------------------
# sensitivity_summary_table
# ---------------------------------------------------------------------------


class TestSensitivitySummaryTable:
    def test_concatenates(self, skewed_series: pd.Series) -> None:
        a = sensitivity_table(skewed_series, feature_name="A")
        b = sensitivity_table(skewed_series, feature_name="B", filter_mode="clean_purchase")
        out = sensitivity_summary_table([a, b])
        assert out.shape[0] == a.shape[0] + b.shape[0]
        assert set(out["feature"].unique()) == {"A", "B"}

    def test_empty_inputs(self) -> None:
        out = sensitivity_summary_table([])
        assert out.empty
        # The expected columns must be present even when empty.
        for col in (
            "feature",
            "filter_mode",
            "method",
            "threshold",
            "candidates",
        ):
            assert col in out.columns

    def test_skips_empty_tables(self, skewed_series: pd.Series) -> None:
        a = sensitivity_table(skewed_series, feature_name="A")
        empty = pd.DataFrame()
        out = sensitivity_summary_table([a, empty])
        assert out.shape[0] == a.shape[0]
