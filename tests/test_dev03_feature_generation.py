"""Tests for Stage F (feature generation) wrapping FE-04 + FE-05."""

from __future__ import annotations

import pandas as pd

from customer_segmentation.prototype.feature_generation import (
    FeatureGenerationOutcome,
    generate_features,
    run_feature_generation_pipeline,
)
from customer_segmentation.prototype.feature_generation.pipeline import (
    FeatureGenerationPipelineResult,
)
from customer_segmentation.prototype.preprocessing.config_loader import (
    FeatureGenerationBlockConfig,
)


def _sample_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "InvoiceNo": [
                "536365",
                "536365",
                "536366",
                "536367",
                "C536368",  # cancellation
            ],
            "StockCode": ["A", "A", "B", "C", "A"],
            "Description": ["x", "x", "y", "z", "x"],
            "Quantity": [6, 8, -2, 4, -6],  # cancellation: -6 (return)
            "InvoiceDate": pd.to_datetime(
                [
                    "2010-12-01 08:26:00",
                    "2010-12-01 08:26:00",
                    "2010-12-01 09:32:00",
                    "2010-12-01 10:15:00",
                    "2010-12-01 10:45:00",
                ]
            ),
            "UnitPrice": [2.55, 2.55, 3.39, 4.25, 2.55],
            "CustomerID": [12345, 12345, 12345, 12346, 12347],
            "Country": ["UK", "UK", "UK", "UK", "UK"],
            "IsCancellation": [False, False, False, False, True],
            "IsReturn": [False, False, True, False, False],
        }
    )


def test_generate_features_returns_dataframe() -> None:
    df = _sample_transactions()
    candidate = generate_features(df)
    assert isinstance(candidate, pd.DataFrame)
    # CustomerID must be present.
    assert "CustomerID" in candidate.columns
    # At least 1 row (FE-04 aggregates to customers).
    assert len(candidate) >= 1


def test_run_feature_generation_returns_result() -> None:
    df = _sample_transactions()
    result = run_feature_generation_pipeline(df)
    assert isinstance(result, FeatureGenerationPipelineResult)
    assert result.outcome in {o.value for o in FeatureGenerationOutcome}
    assert result.customer_count >= 1


def test_feature_generation_includes_rfm() -> None:
    df = _sample_transactions()
    result = run_feature_generation_pipeline(df)
    feats = list(result.candidate_df.columns)
    # RFM: Recency / Frequency / Monetary.
    assert "Recency" in feats
    assert "Frequency" in feats
    assert "Monetary" in feats


def test_feature_generation_includes_behavioral() -> None:
    df = _sample_transactions()
    result = run_feature_generation_pipeline(df)
    feats = list(result.candidate_df.columns)
    assert "TenureDays" in feats
    assert "ActiveDays" in feats
    assert "AverageInvoiceValue" in feats


def test_feature_generation_includes_cancellation_features() -> None:
    df = _sample_transactions()
    result = run_feature_generation_pipeline(df)
    feats = list(result.candidate_df.columns)
    assert "CancellationRate" in feats
    assert "ReturnRate" in feats


def test_feature_generation_category_count_not_materialized() -> None:
    """CategoryCount is FE-05 hard-constraint: NOT materialized."""
    df = _sample_transactions()
    result = run_feature_generation_pipeline(df)
    assert "CategoryCount" not in result.candidate_df.columns
    assert result.manifest_block.diversity.category_count_not_materialized is True


def test_feature_generation_default_ddof_1_in_behavior_block() -> None:
    """PurchaseInterval uses ddof=1 (FE-05 hard-constraint)."""
    df = _sample_transactions()
    result = run_feature_generation_pipeline(df)
    assert result.manifest_block.behavior.purchase_interval_ddof == 1


def test_feature_generation_signed_quantity_default() -> None:
    """Default quantity strategy = signed (FE-05 hard-constraint)."""
    _sample_transactions()
    cfg = FeatureGenerationBlockConfig()
    assert cfg.features.quantity_strategy == "signed"


def test_feature_generation_handles_empty_df() -> None:
    """An empty transaction-level DataFrame should FAIL Stage F1 (no customers).

    We bypass Stage F1's aggregation by passing an empty DataFrame.
    Empty DataFrame → Stage F1 errors → returns FAIL outcome.
    """
    empty = pd.DataFrame(
        {
            "InvoiceNo": pd.Series([], dtype=str),
            "StockCode": pd.Series([], dtype=str),
            "Description": pd.Series([], dtype=str),
            "Quantity": pd.Series([], dtype=float),
            "InvoiceDate": pd.Series([], dtype="datetime64[ns]"),
            "UnitPrice": pd.Series([], dtype=float),
            "CustomerID": pd.Series([], dtype=float),
            "Country": pd.Series([], dtype=str),
            "IsCancellation": pd.Series([], dtype=bool),
            "IsReturn": pd.Series([], dtype=bool),
        }
    )
    result = run_feature_generation_pipeline(empty)
    assert result.outcome == FeatureGenerationOutcome.FAIL.value
    assert result.customer_count == 0


def test_feature_generation_optional_transform_default_is_none() -> None:
    """Stage F3 default is no transform / no scaling."""
    _sample_transactions()
    cfg = FeatureGenerationBlockConfig()
    assert cfg.optional_transform.transformation == "none"
    assert cfg.optional_transform.scaling == "none"
    # Imputation default is "median" but only applied when NaN present.
    assert cfg.optional_transform.imputation == "median"


def test_feature_generation_manifest_block_categories() -> None:
    """Manifest block has the expected category structure."""
    df = _sample_transactions()
    result = run_feature_generation_pipeline(df)
    m = result.manifest_block
    assert hasattr(m, "rfm")
    assert hasattr(m, "quantity")
    assert hasattr(m, "behavior")
    assert hasattr(m, "diversity")
    assert hasattr(m, "cancellation")
