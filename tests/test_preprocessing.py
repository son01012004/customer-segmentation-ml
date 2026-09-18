"""Smoke tests for preprocessing module placeholders.

These tests verify that the preprocessing module imports correctly and
that the `clean_transactions` function is currently a `NotImplementedError`
placeholder. They do NOT require any raw dataset to run.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.preprocessing.cleaning import CleaningResult, clean_transactions
from customer_segmentation.preprocessing.duplicates import drop_duplicates
from customer_segmentation.preprocessing.invalid_records import drop_invalid
from customer_segmentation.preprocessing.missing_values import handle_missing
from customer_segmentation.preprocessing.outliers import treat_outliers


class TestPreprocessingPlaceholders:
    """Placeholder behavior checks for preprocessing helpers."""

    def test_clean_transactions_is_placeholder(self) -> None:
        """`clean_transactions` should currently raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            clean_transactions(pd.DataFrame())

    def test_handle_missing_is_placeholder(self) -> None:
        with pytest.raises(NotImplementedError):
            handle_missing(pd.DataFrame(), [], "drop")

    def test_drop_duplicates_is_placeholder(self) -> None:
        with pytest.raises(NotImplementedError):
            drop_duplicates(pd.DataFrame())

    def test_drop_invalid_is_placeholder(self) -> None:
        with pytest.raises(NotImplementedError):
            drop_invalid(pd.DataFrame(), {})  # type: ignore[arg-type]

    def test_treat_outliers_is_placeholder(self) -> None:
        with pytest.raises(NotImplementedError):
            treat_outliers(pd.DataFrame(), [])

    def test_cleaning_result_is_named_tuple(self) -> None:
        """Sanity check on the CleaningResult type."""
        assert CleaningResult._fields == ("df", "report")
