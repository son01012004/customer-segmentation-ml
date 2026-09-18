"""Smoke tests for the RFM feature placeholder."""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.features.rfm import build_rfm


class TestRFMPlaceholder:
    """Placeholder behavior checks for the RFM module."""

    def test_build_rfm_is_placeholder(self) -> None:
        """`build_rfm` should currently raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            build_rfm(pd.DataFrame())
