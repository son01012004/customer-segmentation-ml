"""Smoke tests for the feature-engineering module placeholders."""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.data.validator import ValidationResult
from customer_segmentation.features.behavioral import build_behavioral_features
from customer_segmentation.features.validation import validate_customer_features


class TestFeaturesPlaceholders:
    """Placeholder behavior checks for feature engineering helpers."""

    def test_build_behavioral_features_is_placeholder(self) -> None:
        with pytest.raises(NotImplementedError):
            build_behavioral_features(pd.DataFrame())

    def test_validate_customer_features_returns_result(self) -> None:
        result = validate_customer_features(pd.DataFrame())
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
