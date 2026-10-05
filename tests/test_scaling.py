"""Tests for scaling utilities.

S1 — StandardScaler
S2 — MinMaxScaler
S3 — RobustScaler
S0 — none (identity)
"""

from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.transformation.scaling import (
    apply_scaling,
    scale_features,
)


class TestStandardScaler:
    """Tests for StandardScaler (S1)."""

    def test_mean_zero(self) -> None:
        """StandardScaler: mean approximately 0."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = apply_scaling(df, ["feat"], "standard")
        mean_val = float(result.df["feat"].mean())
        assert abs(mean_val) < 1e-10, f"StandardScaler mean should be ~0, got {mean_val}"

    def test_std_one(self) -> None:
        """StandardScaler: std approximately 1 (population std)."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = apply_scaling(df, ["feat"], "standard")
        std_val = float(result.df["feat"].std(ddof=0))
        assert abs(std_val - 1.0) < 1e-10, f"StandardScaler std should be ~1, got {std_val}"

    def test_returns_fitted_scaler(self) -> None:
        """apply_scaling returns a scaler object."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        result = apply_scaling(df, ["feat"], "standard")
        assert result.scaler is not None
        assert hasattr(result.scaler, "mean_")
        assert hasattr(result.scaler, "scale_")

    def test_deterministic(self) -> None:
        """Same input produces same output."""
        df = pd.DataFrame({"feat": [1.0, 5.0, 10.0, 20.0]})
        r1 = apply_scaling(df, ["feat"], "standard")
        r2 = apply_scaling(df, ["feat"], "standard")
        pd.testing.assert_frame_equal(r1.df, r2.df)


class TestMinMaxScaler:
    """Tests for MinMaxScaler (S2)."""

    def test_range_zero_to_one(self) -> None:
        """MinMaxScaler: range approximately [0, 1]."""
        df = pd.DataFrame({"feat": [10.0, 20.0, 30.0, 40.0, 50.0]})
        result = apply_scaling(df, ["feat"], "minmax")
        assert float(result.df["feat"].min()) < 1e-10
        assert abs(float(result.df["feat"].max()) - 1.0) < 1e-10

    def test_returns_fitted_scaler(self) -> None:
        """MinMaxScaler returns scaler with data_min_/data_max_."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        result = apply_scaling(df, ["feat"], "minmax")
        assert result.scaler is not None
        assert hasattr(result.scaler, "data_min_")
        assert hasattr(result.scaler, "data_max_")

    def test_deterministic(self) -> None:
        """Same input produces same output."""
        df = pd.DataFrame({"feat": [0.0, 5.0, 10.0]})
        r1 = apply_scaling(df, ["feat"], "minmax")
        r2 = apply_scaling(df, ["feat"], "minmax")
        pd.testing.assert_frame_equal(r1.df, r2.df)


class TestRobustScaler:
    """Tests for RobustScaler (S3)."""

    def test_median_zero(self) -> None:
        """RobustScaler: median approximately 0."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = apply_scaling(df, ["feat"], "robust")
        median_val = float(result.df["feat"].median())
        assert abs(median_val) < 1e-10, f"RobustScaler median should be ~0, got {median_val}"

    def test_returns_fitted_scaler(self) -> None:
        """RobustScaler returns scaler with center_/scale_."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        result = apply_scaling(df, ["feat"], "robust")
        assert result.scaler is not None
        assert hasattr(result.scaler, "center_")
        assert hasattr(result.scaler, "scale_")

    def test_deterministic(self) -> None:
        """Same input produces same output."""
        df = pd.DataFrame({"feat": [1.0, 5.0, 10.0, 20.0]})
        r1 = apply_scaling(df, ["feat"], "robust")
        r2 = apply_scaling(df, ["feat"], "robust")
        pd.testing.assert_frame_equal(r1.df, r2.df)


class TestNoneScaling:
    """Tests for no scaling (S0)."""

    def test_identity(self) -> None:
        """Scaling 'none' returns same DataFrame."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        result = apply_scaling(df, ["feat"], "none")
        pd.testing.assert_frame_equal(result.df, df)

    def test_returns_none_scaler(self) -> None:
        """Scaling 'none' returns scaler=None."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        result = apply_scaling(df, ["feat"], "none")
        assert result.scaler is None


class TestScalerPickle:
    """Tests for scaler pickle round-trip."""

    def test_standard_pickle_roundtrip(self) -> None:
        """StandardScaler pickle can be unpickled."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        result = apply_scaling(df, ["feat"], "standard")
        scaler = result.scaler
        pickled = pickle.dumps(scaler)
        unpickled = pickle.loads(pickled)
        assert unpickled is not None
        # Verify unpickled scaler produces same result
        transformed = unpickled.transform(df[["feat"]])
        original = scaler.transform(df[["feat"]])
        np.testing.assert_array_almost_equal(transformed, original)


class TestScaleFeatures:
    """Backward-compatibility wrapper test."""

    def test_backward_compatible_signature(self) -> None:
        """scale_features returns (DataFrame, scaler) tuple."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        result_df, scaler = scale_features(df, "standard")
        assert isinstance(result_df, pd.DataFrame)
        assert scaler is not None


class TestUnknownScaler:
    """Tests for unknown scaler method."""

    def test_unknown_raises(self) -> None:
        """Unknown scaler raises ValueError."""
        df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
        with pytest.raises(ValueError, match="Unknown"):
            apply_scaling(df, ["feat"], "unknown_scaler")
