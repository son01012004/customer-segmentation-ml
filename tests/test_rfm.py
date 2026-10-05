"""Tests for FE-05 RFM feature computation.

T-RFM-01 → T-RFM-07
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.features.rfm import (  # noqa: E402
    compute_frequency_variants,
    compute_monetary_variants,
    compute_recency,
    compute_reference_date,
    materialize_frequency,
    materialize_monetary,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_transactions() -> pd.DataFrame:
    """3 customers, 6 invoices, no cancellations."""
    return pd.DataFrame(
        {
            "InvoiceNo": ["I1", "I1", "I2", "I3", "I3", "I4", "I4", "I5", "I6"],
            "StockCode": ["P1", "P2", "P1", "P3", "P4", "P5", "P6", "P7", "P8"],
            "Quantity": [2, 1, 3, 4, 2, 1, 3, 5, 6],
            "InvoiceDate": pd.to_datetime(
                [
                    "2011-01-01",
                    "2011-01-01",
                    "2011-01-02",
                    "2011-01-03",
                    "2011-01-03",
                    "2011-02-01",
                    "2011-02-01",
                    "2011-03-01",
                    "2011-04-01",
                ]
            ),
            "UnitPrice": [10.0, 5.0, 10.0, 20.0, 15.0, 8.0, 12.0, 9.0, 7.0],
            "CustomerID": pd.array([1, 1, 2, 2, 2, 3, 3, 3, 3], dtype="Int64"),
            "IsCancellation": [False] * 9,
        }
    )


@pytest.fixture()
def synthetic_customer_base() -> pd.DataFrame:
    """Customer-level base dataset."""
    return pd.DataFrame(
        {
            "CustomerID": pd.array([1, 2, 3], dtype="Int64"),
            "FirstPurchaseDate": pd.to_datetime(["2011-01-01", "2011-01-02", "2011-02-01"]),
            "LastPurchaseDate": pd.to_datetime(["2011-01-01", "2011-01-03", "2011-04-01"]),
        }
    )


# ---------------------------------------------------------------------------
# T-RFM-01: Reference date deterministic
# ---------------------------------------------------------------------------


class TestReferenceDate:
    def test_reference_date_is_max_plus_one(self, synthetic_transactions: pd.DataFrame) -> None:
        """ReferenceDate = max(InvoiceDate) + 1 day."""
        ref_date = compute_reference_date(synthetic_transactions)
        expected = pd.Timestamp("2011-04-01") + timedelta(days=1)
        assert ref_date == expected

    def test_reference_date_deterministic(self, synthetic_transactions: pd.DataFrame) -> None:
        """Same input → same output (no random elements)."""
        ref1 = compute_reference_date(synthetic_transactions)
        ref2 = compute_reference_date(synthetic_transactions)
        assert ref1 == ref2


# ---------------------------------------------------------------------------
# T-RFM-02: Recency computation
# ---------------------------------------------------------------------------


class TestRecency:
    def test_recency_correct(self, synthetic_customer_base: pd.DataFrame) -> None:
        """Recency = ReferenceDate - LastPurchaseDate."""
        ref_date = datetime(2011, 12, 10)
        result = compute_recency(synthetic_customer_base, ref_date)
        # Customer 1: 2011-12-10 - 2011-01-01 = 343 days
        # Customer 2: 2011-12-10 - 2011-01-03 = 341 days
        # Customer 3: 2011-12-10 - 2011-04-01 = 253 days
        recencies = dict(zip(result["CustomerID"], result["Recency"], strict=False))
        assert recencies[1] == 343
        assert recencies[2] == 341
        assert recencies[3] == 253


# ---------------------------------------------------------------------------
# T-RFM-03: Frequency variants
# ---------------------------------------------------------------------------


class TestFrequencyVariants:
    def test_frequency_by_invoice_correct(
        self, synthetic_transactions: pd.DataFrame, synthetic_customer_base: pd.DataFrame
    ) -> None:
        """FREQ-01: nunique(InvoiceNo) per CustomerID."""
        variants = compute_frequency_variants(synthetic_transactions, synthetic_customer_base)
        result = dict(
            zip(
                variants.by_invoice["CustomerID"],
                variants.by_invoice["Frequency_ByInvoice"],
                strict=False,
            )
        )
        # Customer 1: invoices I1 (2 lines) → 1 invoice
        # Customer 2: invoices I2, I3 → 2 invoices
        # Customer 3: invoices I4, I5, I6 → 3 invoices
        assert result[1] == 1
        assert result[2] == 2
        assert result[3] == 3

    def test_frequency_by_transaction_line_correct(
        self, synthetic_transactions: pd.DataFrame, synthetic_customer_base: pd.DataFrame
    ) -> None:
        """FREQ-02: count of transaction lines per CustomerID."""
        variants = compute_frequency_variants(synthetic_transactions, synthetic_customer_base)
        result = dict(
            zip(
                variants.by_transaction_line["CustomerID"],
                variants.by_transaction_line["Frequency_ByTransactionLine"],
                strict=False,
            )
        )
        assert result[1] == 2  # I1 has 2 lines
        assert result[2] == 3  # I2 + I3 (I3 has 2 lines) = 3
        assert result[3] == 4  # I4 + I5 + I6 (I4 has 2 lines) = 4


# ---------------------------------------------------------------------------
# T-RFM-04: Frequency materialize ONE
# ---------------------------------------------------------------------------


class TestFrequencyMaterialize:
    def test_materialize_by_invoice(
        self, synthetic_transactions: pd.DataFrame, synthetic_customer_base: pd.DataFrame
    ) -> None:
        """Materialize Frequency = FREQ-01."""
        variants = compute_frequency_variants(synthetic_transactions, synthetic_customer_base)
        result = materialize_frequency(variants, synthetic_customer_base, mode="by_invoice")
        assert "Frequency" in result.columns
        assert result.shape[0] == 3

    def test_materialize_by_transaction_line(
        self, synthetic_transactions: pd.DataFrame, synthetic_customer_base: pd.DataFrame
    ) -> None:
        """Materialize Frequency = FREQ-02."""
        variants = compute_frequency_variants(synthetic_transactions, synthetic_customer_base)
        result = materialize_frequency(
            variants, synthetic_customer_base, mode="by_transaction_line"
        )
        assert "Frequency" in result.columns


# ---------------------------------------------------------------------------
# T-RFM-05: Monetary 4 variants
# ---------------------------------------------------------------------------


class TestMonetaryVariants:
    def test_monetary_signed_correct(self) -> None:
        """MonetarySigned = sum of signed LineRevenue."""
        df = pd.DataFrame(
            {
                "CustomerID": pd.array([1, 1, 2], dtype="Int64"),
                "LineRevenue": [100.0, -50.0, 200.0],
                "IsCancellation": [False, True, False],
            }
        )
        base = pd.DataFrame({"CustomerID": pd.array([1, 2], dtype="Int64")})
        variants = compute_monetary_variants(df, base)
        signed = dict(
            zip(variants.signed["CustomerID"], variants.signed["MonetarySigned"], strict=False)
        )
        assert signed[1] == 50.0  # 100 - 50
        assert signed[2] == 200.0

    def test_monetary_absolute_correct(self) -> None:
        """MonetaryAbsolute = sum of |LineRevenue|."""
        df = pd.DataFrame(
            {
                "CustomerID": pd.array([1, 1, 2], dtype="Int64"),
                "LineRevenue": [100.0, -50.0, 200.0],
                "IsCancellation": [False, True, False],
            }
        )
        base = pd.DataFrame({"CustomerID": pd.array([1, 2], dtype="Int64")})
        variants = compute_monetary_variants(df, base)
        absolute = dict(
            zip(
                variants.absolute["CustomerID"], variants.absolute["MonetaryAbsolute"], strict=False
            )
        )
        assert absolute[1] == 150.0
        assert absolute[2] == 200.0

    def test_monetary_purchase_only_correct(self) -> None:
        """MonetaryPurchaseOnly = sum where IsCancellation=False."""
        df = pd.DataFrame(
            {
                "CustomerID": pd.array([1, 1, 2], dtype="Int64"),
                "LineRevenue": [100.0, -50.0, 200.0],
                "IsCancellation": [False, True, False],
            }
        )
        base = pd.DataFrame({"CustomerID": pd.array([1, 2], dtype="Int64")})
        variants = compute_monetary_variants(df, base)
        purchase_only = dict(
            zip(
                variants.purchase_only["CustomerID"],
                variants.purchase_only["MonetaryPurchaseOnly"],
                strict=False,
            )
        )
        assert purchase_only[1] == 100.0  # Only the non-cancellation row
        assert purchase_only[2] == 200.0


# ---------------------------------------------------------------------------
# T-RFM-06: Monetary materialize ONE
# ---------------------------------------------------------------------------


class TestMonetaryMaterialize:
    def test_materialize_monetary_signed(self) -> None:
        df = pd.DataFrame(
            {
                "CustomerID": pd.array([1, 2], dtype="Int64"),
                "LineRevenue": [100.0, 200.0],
                "IsCancellation": [False, False],
            }
        )
        base = pd.DataFrame({"CustomerID": pd.array([1, 2], dtype="Int64")})
        variants = compute_monetary_variants(df, base)
        result = materialize_monetary(variants, base, variant="signed")
        assert "Monetary" in result.columns
        assert result.shape[0] == 2


# ---------------------------------------------------------------------------
# T-RFM-07: Comparison DataFrames
# ---------------------------------------------------------------------------


class TestComparisons:
    def test_frequency_comparison_has_both(self) -> None:
        df = pd.DataFrame(
            {
                "CustomerID": pd.array([1, 2], dtype="Int64"),
                "InvoiceNo": ["I1", "I1"],
            }
        )
        base = pd.DataFrame({"CustomerID": pd.array([1, 2], dtype="Int64")})
        variants = compute_frequency_variants(df, base)
        assert "Frequency_ByInvoice" in variants.comparison_df.columns
        assert "Frequency_ByTransactionLine" in variants.comparison_df.columns
