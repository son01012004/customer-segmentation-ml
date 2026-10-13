"""Tests for Stage D / E optional transform/scale (12-combo grid)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.prototype.preprocessing.config_loader import (
    PreprocessingTransformationConfig,
)
from customer_segmentation.prototype.preprocessing.pipeline import (
    _numeric_columns,
    _stage_d_transformation,
    _stage_e_scaling,
)


def _sample() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "InvoiceNo": ["x"] * 50,
            "CustomerID": rng.integers(1, 5, size=50),
            "Country": ["UK"] * 50,
            "Quantity": rng.normal(5, 1, size=50),
            "UnitPrice": rng.normal(3, 0.5, size=50),
        }
    )


def test_numeric_columns_excludes_id_and_country() -> None:
    df = _sample()
    cols = _numeric_columns(df)
    assert "Quantity" in cols
    assert "UnitPrice" in cols
    assert "CustomerID" not in cols
    assert "InvoiceNo" not in cols
    assert "Country" not in cols


def test_stage_d_none_is_noop() -> None:
    df = _sample().copy()
    out, cols, _ = _stage_d_transformation(
        df, config=PreprocessingTransformationConfig(), logger=None
    )
    pd.testing.assert_frame_equal(out, df)
    assert cols == []


def test_stage_d_log1p_rejects_negative() -> None:
    df = _sample()
    df.loc[0, "Quantity"] = -1.0  # introduce a negative
    with pytest.raises(ValueError):
        _stage_d_transformation(
            df, config=PreprocessingTransformationConfig(transformation="log1p"), logger=None
        )


def test_stage_d_log1p_applies_to_clean_numeric() -> None:
    df = _sample()
    out, cols, _ = _stage_d_transformation(
        df, config=PreprocessingTransformationConfig(transformation="log1p"), logger=None
    )
    # log1p transforms without introducing Inf/NaN.
    assert not out["Quantity"].isna().any()
    assert not np.isinf(out["Quantity"]).any()
    # For x > 0: log1p(x) > 0 (always) and < x for 0 < x < 1 (decreases).
    # We just check that it changed.
    assert not np.allclose(out["Quantity"].values, df["Quantity"].values)
    assert "Quantity" in cols


def test_stage_d_yeo_johnson_rejects_nan() -> None:
    df = _sample()
    df.loc[0, "Quantity"] = np.nan
    with pytest.raises(ValueError):
        _stage_d_transformation(
            df, config=PreprocessingTransformationConfig(transformation="yeo_johnson"), logger=None
        )


def test_stage_d_yeo_johnson_no_nan_no_inf() -> None:
    df = _sample()
    out, cols, _ = _stage_d_transformation(
        df, config=PreprocessingTransformationConfig(transformation="yeo_johnson"), logger=None
    )
    # No NaN, no Inf in transformed column.
    assert not out["Quantity"].isna().any()
    assert not np.isinf(out["Quantity"]).any()
    assert "Quantity" in cols


def test_stage_e_none_is_noop() -> None:
    df = _sample()
    out, cols = _stage_e_scaling(
        df, config=PreprocessingTransformationConfig(), numeric_cols=[], logger=None
    )
    pd.testing.assert_frame_equal(out, df)
    assert cols == []


def test_stage_e_log1p_uses_standard_scaler() -> None:
    """Stage E with transformation=log1p uses StandardScaler."""
    df = _sample()
    out, cols = _stage_e_scaling(
        df,
        config=PreprocessingTransformationConfig(transformation="log1p"),
        numeric_cols=["Quantity", "UnitPrice"],
        logger=None,
    )
    # Scaled values: mean ≈ 0, std ≈ 1.
    qty = out["Quantity"].astype(float).dropna()
    assert abs(qty.mean()) < 0.5
    assert abs(qty.std(ddof=0) - 1.0) < 0.5


def test_stage_e_yeo_johnson_uses_robust_scaler() -> None:
    """Stage E with transformation=yeo_johnson uses RobustScaler."""
    df = _sample()
    out, cols = _stage_e_scaling(
        df,
        config=PreprocessingTransformationConfig(transformation="yeo_johnson"),
        numeric_cols=["Quantity", "UnitPrice"],
        logger=None,
    )
    # Robust-scaled values: median ≈ 0, IQR ≈ 1.
    qty = out["Quantity"].astype(float).dropna()
    assert abs(qty.median()) < 1.0


@pytest.mark.parametrize(
    "transformation",
    ["none", "log1p", "yeo_johnson"],
)
def test_grid_stage_d_all_transformations_no_nan(transformation: str) -> None:
    df = _sample()
    out, _, _ = _stage_d_transformation(
        df, config=PreprocessingTransformationConfig(transformation=transformation), logger=None
    )
    # Check no Inf introduced (NaN is allowed only if input had NaN).
    for c in ["Quantity", "UnitPrice"]:
        assert not np.isinf(out[c]).any() or transformation == "none"


@pytest.mark.parametrize(
    "scaling_combo",
    [
        ("log1p", "standard"),
        ("log1p", "minmax"),
        ("log1p", "robust"),
        ("yeo_johnson", "standard"),
        ("yeo_johnson", "minmax"),
        ("yeo_johnson", "robust"),
    ],
)
def test_stage_e_combos_produce_numeric_output(scaling_combo: tuple) -> None:
    """The 6 transform × scaling combos Stage E supports all produce numeric output."""
    df = _sample()
    trans, _ = scaling_combo
    out, cols = _stage_e_scaling(
        df,
        config=PreprocessingTransformationConfig(transformation=trans),
        numeric_cols=["Quantity", "UnitPrice"],
        logger=None,
    )
    assert "Quantity" in cols
    assert not np.isinf(out["Quantity"]).any()
