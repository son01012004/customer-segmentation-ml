"""Tests for FE-05 monetary comparison module.

T-MON-01 → T-MON-04
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

from customer_segmentation.features.monetary_comparison import (  # noqa: E402
    build_monetary_comparison_csv,
    compute_all_monetary_variants,
    detect_overlap,
    materialize_one_monetary_candidate,
)


@pytest.fixture()
def synthetic_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CustomerID": pd.array([1, 1, 1, 2, 2], dtype="Int64"),
            "LineRevenue": [100.0, -50.0, 30.0, 200.0, -20.0],
            "IsCancellation": [False, True, False, False, True],
        }
    )


@pytest.fixture()
def synthetic_base() -> pd.DataFrame:
    return pd.DataFrame({"CustomerID": pd.array([1, 2, 3], dtype="Int64")})


# ---------------------------------------------------------------------------
# T-MON-01: compute_all_monetary_variants returns 4 variants
# ---------------------------------------------------------------------------


class TestComputeAllVariants:
    def test_returns_four_variants(
        self, synthetic_transactions: pd.DataFrame, synthetic_base: pd.DataFrame
    ) -> None:
        """Should return MonetaryVariants with 4 distinct variants."""
        variants = compute_all_monetary_variants(synthetic_transactions, synthetic_base)
        assert variants.signed is not None
        assert variants.absolute is not None
        assert variants.purchase_only is not None
        assert variants.cancellation_only is not None
        assert variants.comparison_df is not None


# ---------------------------------------------------------------------------
# T-MON-02: detect_overlap
# ---------------------------------------------------------------------------


class TestDetectOverlap:
    def test_overlap_summary_has_all_variants(
        self, synthetic_transactions: pd.DataFrame, synthetic_base: pd.DataFrame
    ) -> None:
        """Overlap summary should have all 4 variants."""
        variants = compute_all_monetary_variants(synthetic_transactions, synthetic_base)
        overlap = detect_overlap(variants)
        assert len(overlap) == 4
        assert "MonetarySigned" in overlap["Variant"].values
        assert "MonetaryAbsolute" in overlap["Variant"].values
        assert "MonetaryPurchaseOnly" in overlap["Variant"].values
        assert "MonetaryCancellationOnly" in overlap["Variant"].values


# ---------------------------------------------------------------------------
# T-MON-03: build_monetary_comparison_csv
# ---------------------------------------------------------------------------


class TestBuildComparisonCSV:
    def test_writes_csv_file(
        self, synthetic_transactions: pd.DataFrame, synthetic_base: pd.DataFrame, tmp_path: Path
    ) -> None:
        """Should write CSV with all 4 monetary variants."""
        variants = compute_all_monetary_variants(synthetic_transactions, synthetic_base)
        output_path = tmp_path / "monetary_comparison.csv"
        result_path = build_monetary_comparison_csv(variants, output_path)
        assert result_path.exists()
        df = pd.read_csv(result_path)
        assert "MonetarySigned" in df.columns
        assert "MonetaryAbsolute" in df.columns
        assert "MonetaryPurchaseOnly" in df.columns
        assert "MonetaryCancellationOnly" in df.columns


# ---------------------------------------------------------------------------
# T-MON-04: materialize_one_monetary_candidate
# ---------------------------------------------------------------------------


class TestMaterializeOne:
    def test_materialize_signed_default(
        self, synthetic_transactions: pd.DataFrame, synthetic_base: pd.DataFrame
    ) -> None:
        """Default variant is signed."""
        variants = compute_all_monetary_variants(synthetic_transactions, synthetic_base)
        result = materialize_one_monetary_candidate(variants, synthetic_base)
        assert "Monetary" in result.columns

    def test_materialize_absolute(
        self, synthetic_transactions: pd.DataFrame, synthetic_base: pd.DataFrame
    ) -> None:
        variants = compute_all_monetary_variants(synthetic_transactions, synthetic_base)
        result = materialize_one_monetary_candidate(variants, synthetic_base, variant="absolute")
        assert "Monetary" in result.columns
