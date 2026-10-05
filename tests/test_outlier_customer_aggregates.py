"""Unit tests for :mod:`customer_segmentation.outlier_analysis.customer_aggregates`.

Synthetic DataFrames only. No raw dataset, no FE-02 parquet.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.config.outlier_loader import (
    CustomerAggregationConfig,
    CustomerDiagnosticConfig,
)
from customer_segmentation.outlier_analysis.customer_aggregates import (
    LINE_REVENUE_COLUMN,
    compute_line_revenue,
    customer_diagnostic,
    filter_dataframe_for_mode,
    summarise_diagnostic,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cleaned_df() -> pd.DataFrame:
    """Small synthetic FE-02-style cleaned dataset.

    Three customers with different buying patterns and one cancellation.
    """
    return pd.DataFrame(
        {
            "InvoiceNo": ["A1", "A1", "A2", "A3", "C4", "A5"],
            "StockCode": ["P1", "P2", "P1", "P3", "P4", "P5"],
            "Description": ["x", "y", "x", "z", "w", "v"],
            "Quantity": [2, 1, 3, 1, 5, 2],
            "InvoiceDate": pd.to_datetime(
                [
                    "2011-01-01",
                    "2011-01-01",
                    "2011-01-02",
                    "2011-01-02",
                    "2011-01-03",
                    "2011-01-04",
                ]
            ),
            "UnitPrice": [10.0, 5.0, 10.0, 20.0, 100.0, 1.0],
            "CustomerID": pd.array([1, 1, 2, 3, 1, 2], dtype="Int64"),
            "Country": ["UK", "UK", "UK", "UK", "UK", "UK"],
            "IsCancellation": [False, False, False, False, True, False],
            "IsReturn": [False, False, False, False, False, False],
        }
    )


@pytest.fixture()
def default_diag_config() -> CustomerDiagnosticConfig:
    return CustomerDiagnosticConfig(
        enabled=True,
        customer_key="CustomerID",
        aggregations={
            "total_spend": CustomerAggregationConfig(source="LineRevenue", fn="sum"),
            "total_quantity": CustomerAggregationConfig(source="Quantity", fn="sum"),
            "distinct_invoices": CustomerAggregationConfig(source="InvoiceNo", fn="nunique"),
            "distinct_products": CustomerAggregationConfig(source="StockCode", fn="nunique"),
            "active_days": CustomerAggregationConfig(source="InvoiceDate", fn="nunique_date"),
        },
    )


# ---------------------------------------------------------------------------
# compute_line_revenue()
# ---------------------------------------------------------------------------


class TestLineRevenue:
    def test_basic(self) -> None:
        df = pd.DataFrame({"Quantity": [2, 3], "UnitPrice": [10.0, 5.0]})
        out = compute_line_revenue(df)
        assert LINE_REVENUE_COLUMN in out.columns
        assert list(out[LINE_REVENUE_COLUMN]) == [20.0, 15.0]

    def test_negative_quantity_preserved(self) -> None:
        # Sign flipping is forbidden.
        df = pd.DataFrame({"Quantity": [-2], "UnitPrice": [10.0]})
        out = compute_line_revenue(df)
        assert float(out[LINE_REVENUE_COLUMN].iloc[0]) == -20.0

    def test_missing_column_raises(self) -> None:
        df = pd.DataFrame({"Quantity": [1]})
        with pytest.raises(KeyError):
            compute_line_revenue(df)

    def test_input_not_mutated(self) -> None:
        df = pd.DataFrame({"Quantity": [1, 2], "UnitPrice": [3.0, 4.0]})
        snapshot = df.copy(deep=True)
        _ = compute_line_revenue(df)
        assert df.equals(snapshot)
        assert LINE_REVENUE_COLUMN not in df.columns


# ---------------------------------------------------------------------------
# filter_dataframe_for_mode()
# ---------------------------------------------------------------------------


class TestFilterModes:
    def test_all_rows_returns_copy(self, cleaned_df: pd.DataFrame) -> None:
        out = filter_dataframe_for_mode(cleaned_df, "all_rows")
        assert out.shape == cleaned_df.shape
        # Reset index so we can compare values.
        assert out.reset_index(drop=True).equals(cleaned_df.reset_index(drop=True))

    def test_clean_purchase_excludes_cancellations(self, cleaned_df: pd.DataFrame) -> None:
        out = filter_dataframe_for_mode(cleaned_df, "clean_purchase")
        # The fixture has one cancellation row (InvoiceNo=C4).
        assert out.shape[0] == cleaned_df.shape[0] - 1
        assert not bool(out["IsCancellation"].any())
        assert not bool(out["IsReturn"].any())

    def test_non_cancellation(self, cleaned_df: pd.DataFrame) -> None:
        out = filter_dataframe_for_mode(cleaned_df, "non_cancellation")
        assert out.shape[0] == cleaned_df.shape[0] - 1
        assert not bool(out["IsCancellation"].any())

    def test_non_return(self, cleaned_df: pd.DataFrame) -> None:
        out = filter_dataframe_for_mode(cleaned_df, "non_return")
        assert out.shape[0] == cleaned_df.shape[0]
        # Fixture has no return rows.
        assert not bool(out["IsReturn"].any())

    def test_unknown_mode_raises(self, cleaned_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="Unknown filter mode"):
            filter_dataframe_for_mode(cleaned_df, "magic")

    def test_missing_flag_raises(self) -> None:
        df = pd.DataFrame({"A": [1, 2]})
        with pytest.raises(ValueError, match="requires"):
            filter_dataframe_for_mode(df, "clean_purchase")

    def test_input_not_mutated(self, cleaned_df: pd.DataFrame) -> None:
        snapshot = cleaned_df.copy(deep=True)
        _ = filter_dataframe_for_mode(cleaned_df, "clean_purchase")
        assert cleaned_df.equals(snapshot)


# ---------------------------------------------------------------------------
# customer_diagnostic()
# ---------------------------------------------------------------------------


class TestCustomerDiagnostic:
    def test_basic_output_shape(
        self,
        cleaned_df: pd.DataFrame,
        default_diag_config: CustomerDiagnosticConfig,
    ) -> None:
        result = customer_diagnostic(cleaned_df, default_diag_config)
        assert result.is_diagnostic is True
        # Fixture has 3 distinct CustomerIDs.
        assert result.frame.shape[0] == 3
        assert set(result.frame.columns) >= {
            "CustomerID",
            "total_spend",
            "total_quantity",
            "distinct_invoices",
            "distinct_products",
            "active_days",
        }

    def test_total_spend_includes_line_revenue(
        self,
        cleaned_df: pd.DataFrame,
        default_diag_config: CustomerDiagnosticConfig,
    ) -> None:
        result = customer_diagnostic(cleaned_df, default_diag_config)
        # Customer 1: 2×10 + 1×5 + 5×100 (the cancellation row IS included
        # under all_rows because we only filter by flag; the cancellation
        # row has Quantity=5, UnitPrice=100).
        c1 = result.frame[result.frame["CustomerID"] == 1].iloc[0]
        assert float(c1["total_spend"]) == pytest.approx(2 * 10 + 1 * 5 + 5 * 100)
        # Customer 2: 3×10 + 2×1
        c2 = result.frame[result.frame["CustomerID"] == 2].iloc[0]
        assert float(c2["total_spend"]) == pytest.approx(3 * 10 + 2 * 1)
        # Customer 3: 1×20
        c3 = result.frame[result.frame["CustomerID"] == 3].iloc[0]
        assert float(c3["total_spend"]) == pytest.approx(20)

    def test_distinct_invoices(self, cleaned_df: pd.DataFrame) -> None:
        config = CustomerDiagnosticConfig(
            enabled=True,
            customer_key="CustomerID",
            aggregations={
                "distinct_invoices": CustomerAggregationConfig(source="InvoiceNo", fn="nunique")
            },
        )
        result = customer_diagnostic(cleaned_df, config)
        # Customer 1 has 3 invoices (A1, A1, C4) → 2 unique.
        c1 = result.frame[result.frame["CustomerID"] == 1].iloc[0]
        assert int(c1["distinct_invoices"]) == 2

    def test_active_days(self, cleaned_df: pd.DataFrame) -> None:
        config = CustomerDiagnosticConfig(
            enabled=True,
            customer_key="CustomerID",
            aggregations={
                "active_days": CustomerAggregationConfig(source="InvoiceDate", fn="nunique_date")
            },
        )
        result = customer_diagnostic(cleaned_df, config)
        # Customer 1 has rows on 2011-01-01 and 2011-01-03 → 2 days.
        c1 = result.frame[result.frame["CustomerID"] == 1].iloc[0]
        assert int(c1["active_days"]) == 2

    def test_clean_purchase_excludes_cancellation(
        self,
        cleaned_df: pd.DataFrame,
        default_diag_config: CustomerDiagnosticConfig,
    ) -> None:
        result = customer_diagnostic(cleaned_df, default_diag_config, filter_mode="clean_purchase")
        # Customer 1 under clean_purchase: only A1+A1 lines, no C4.
        c1 = result.frame[result.frame["CustomerID"] == 1].iloc[0]
        assert float(c1["total_spend"]) == pytest.approx(2 * 10 + 1 * 5)

    def test_disabled_returns_empty(self) -> None:
        config = CustomerDiagnosticConfig(enabled=False)
        df = pd.DataFrame({"CustomerID": [1, 2], "Quantity": [1, 2]})
        result = customer_diagnostic(df, config)
        assert result.frame.shape[0] == 0
        assert "CustomerID" in result.frame.columns

    def test_missing_customer_key_raises(self) -> None:
        config = CustomerDiagnosticConfig(enabled=True, customer_key="NotPresent")
        df = pd.DataFrame({"Quantity": [1, 2]})
        with pytest.raises(KeyError, match="Customer key"):
            customer_diagnostic(df, config)

    def test_input_not_mutated(
        self,
        cleaned_df: pd.DataFrame,
        default_diag_config: CustomerDiagnosticConfig,
    ) -> None:
        snapshot = cleaned_df.copy(deep=True)
        _ = customer_diagnostic(cleaned_df, default_diag_config)
        assert cleaned_df.equals(snapshot)
        assert LINE_REVENUE_COLUMN not in cleaned_df.columns

    def test_sort_order_total_spend_desc(
        self,
        cleaned_df: pd.DataFrame,
        default_diag_config: CustomerDiagnosticConfig,
    ) -> None:
        result = customer_diagnostic(cleaned_df, default_diag_config)
        spends = result.frame["total_spend"].tolist()
        # Non-increasing.
        assert all(spends[i] >= spends[i + 1] for i in range(len(spends) - 1))


# ---------------------------------------------------------------------------
# summarise_diagnostic()
# ---------------------------------------------------------------------------


class TestSummariseDiagnostic:
    def test_returns_one_row_per_diagnostic_column(
        self,
        cleaned_df: pd.DataFrame,
        default_diag_config: CustomerDiagnosticConfig,
    ) -> None:
        diag = customer_diagnostic(cleaned_df, default_diag_config)
        summary = summarise_diagnostic(diag)
        # Excludes the customer key column; should be 5 numeric columns.
        numeric_cols = [
            c
            for c in diag.frame.columns
            if c != diag.config.customer_key and pd.api.types.is_numeric_dtype(diag.frame[c])
        ]
        assert summary.shape[0] == len(numeric_cols)
        assert set(summary["column"]) == set(numeric_cols)
