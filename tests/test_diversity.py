"""Tests for FE-05 diversity module.

T-DIV-01 → T-DIV-03
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.features.diversity import (  # noqa: E402
    compute_diversity_features,
    compute_products_per_invoice,
)


@pytest.fixture()
def synthetic_base() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CustomerID": pd.array([1, 2, 3], dtype="Int64"),
            "DistinctProducts": [10, 20, 5],
            "DistinctInvoiceCount": [5, 10, 1],
        }
    )


# ---------------------------------------------------------------------------
# T-DIV-01: ProductsPerInvoice correct
# ---------------------------------------------------------------------------


class TestProductsPerInvoice:
    def test_ratio_correct(self, synthetic_base: pd.DataFrame) -> None:
        result = compute_products_per_invoice(synthetic_base)
        ratios = dict(zip(result["CustomerID"], result["ProductsPerInvoice"], strict=False))
        # Customer 1: 10/5 = 2.0
        # Customer 2: 20/10 = 2.0
        # Customer 3: 5/1 = 5.0
        assert ratios[1] == 2.0
        assert ratios[2] == 2.0
        assert ratios[3] == 5.0


# ---------------------------------------------------------------------------
# T-DIV-02: ProductsPerInvoice is ratio proxy
# ---------------------------------------------------------------------------


class TestRatioProxy:
    def test_column_name_correct(self, synthetic_base: pd.DataFrame) -> None:
        result = compute_products_per_invoice(synthetic_base)
        assert "ProductsPerInvoice" in result.columns


# ---------------------------------------------------------------------------
# T-DIV-03: CategoryCount NOT materialized
# ---------------------------------------------------------------------------


class TestCategoryCountNotMaterialized:
    def test_no_category_count_in_diversity_features(self, synthetic_base: pd.DataFrame) -> None:
        """CategoryCount must NOT be in diversity features."""
        result = compute_diversity_features(synthetic_base)
        assert "CategoryCount" not in result.columns
