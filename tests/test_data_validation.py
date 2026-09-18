"""Smoke tests for data validation helpers.

These tests verify that the package imports and that the validation
helpers have the expected placeholder behavior. They do NOT require any
raw dataset to run.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.data.validator import (
    ValidationResult,
    assert_columns_exist,
    validate_customer_features,
    validate_raw_transactions,
)


class TestDataValidation:
    """Placeholder tests for data validation."""

    def test_validate_raw_transactions_returns_result(self) -> None:
        """Empty DataFrame should produce a valid placeholder result."""
        df = pd.DataFrame()
        result = validate_raw_transactions(df)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.errors == []

    def test_validate_customer_features_returns_result(self) -> None:
        """Empty DataFrame should produce a valid placeholder result."""
        df = pd.DataFrame()
        result = validate_customer_features(df)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True

    def test_assert_columns_exist_pass(self) -> None:
        """No exception when all required columns are present."""
        df = pd.DataFrame({"a": [1], "b": [2]})
        assert_columns_exist(df, ["a", "b"])

    def test_assert_columns_exist_missing(self) -> None:
        """KeyError is raised when a required column is missing."""
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(KeyError):
            assert_columns_exist(df, ["a", "b"])
