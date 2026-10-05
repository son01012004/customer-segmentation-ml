"""Unit tests for :mod:`customer_segmentation.aggregation.base_dataset`.

Synthetic DataFrames only. No raw dataset, no FE-02 parquet.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.aggregation.base_dataset import (
    LINE_REVENUE_COLUMN,
    aggregate_customer_base,
    build_base_schema,
    compute_line_revenue,
)
from customer_segmentation.aggregation.config_loader import (
    AggregationConfig,
    AggregationSpec,
    LineRevenueColumns,
    MetadataConfig,
    OutputConfig,
    SourceConfig,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agg_config() -> AggregationConfig:
    """Default aggregation config for tests."""
    return AggregationConfig(
        enabled=True,
        random_seed=42,
        source=SourceConfig(
            role="primary",
            cleaned_dataset_path="./data/processed/transactions_clean.parquet",
            raw_dataset_path="./data/raw/primary/Online Retail.xlsx",
        ),
        aggregations=[
            AggregationSpec(
                name="TotalQuantity",
                source="Quantity",
                fn="sum",
                status="WORKING_ASSUMPTION",
                description="Tong so luong.",
            ),
            AggregationSpec(
                name="TotalMonetary",
                source="LineRevenue",
                fn="sum",
                status="WORKING_ASSUMPTION",
                description="Tong doanh thu (signed).",
            ),
            AggregationSpec(
                name="FirstPurchaseDate",
                source="InvoiceDate",
                fn="min",
                status="WORKING_ASSUMPTION",
                description="Ngay dau tien.",
            ),
            AggregationSpec(
                name="LastPurchaseDate",
                source="InvoiceDate",
                fn="max",
                status="WORKING_ASSUMPTION",
                description="Ngay cuoi cung.",
            ),
            AggregationSpec(
                name="PurchaseFrequency",
                source="InvoiceNo",
                fn="nunique",
                status="WORKING_ASSUMPTION",
                description="Working proxy.",
            ),
            AggregationSpec(
                name="AverageTransactionValue",
                source="LineRevenue",
                fn="avg_by_invoice",
                status="WORKING_ASSUMPTION",
                description="Trung binh.",
            ),
            AggregationSpec(
                name="TransactionLineCount",
                source="InvoiceNo",
                fn="count",
                status="WORKING_ASSUMPTION",
                description="So dong.",
            ),
            AggregationSpec(
                name="DistinctInvoiceCount",
                source="InvoiceNo",
                fn="nunique",
                status="WORKING_ASSUMPTION",
                description="So hoa don.",
            ),
            AggregationSpec(
                name="DistinctProducts",
                source="StockCode",
                fn="nunique",
                status="WORKING_ASSUMPTION",
                description="So san pham.",
            ),
            AggregationSpec(
                name="CancellationInvoiceCount",
                source="InvoiceNo",
                fn="conditional_nunique_cancellation",
                status="WORKING_ASSUMPTION",
                description="So hoa don cancellation.",
            ),
            AggregationSpec(
                name="ReturnInvoiceCount",
                source="InvoiceNo",
                fn="conditional_nunique_return",
                status="WORKING_ASSUMPTION",
                description="So hoa don return.",
            ),
        ],
        customer_key="CustomerID",
        line_revenue_columns=LineRevenueColumns(
            quantity="Quantity",
            unit_price="UnitPrice",
            output=LINE_REVENUE_COLUMN,
        ),
        output=OutputConfig(
            processed_dir="./data/processed",
            customer_base_filename="customer_base.parquet",
            report_dir="./reports/fe04",
        ),
        metadata=MetadataConfig(
            stage="FE-04",
            task_description="Test aggregation.",
            scope_boundaries=["Customer aggregation"],
            notes=[],
        ),
    )


@pytest.fixture()
def basic_df() -> pd.DataFrame:
    """Small FE-02-style dataset. 2 customers, no cancellations."""
    return pd.DataFrame(
        {
            "InvoiceNo": ["I1", "I1", "I2", "I3", "I3"],
            "StockCode": ["P1", "P2", "P1", "P3", "P4"],
            "Description": ["x", "y", "x", "z", "w"],
            "Quantity": [2, 1, 3, 4, 2],
            "InvoiceDate": pd.to_datetime(
                ["2011-01-01", "2011-01-01", "2011-01-02", "2011-01-03", "2011-01-03"]
            ),
            "UnitPrice": [10.0, 5.0, 10.0, 20.0, 15.0],
            "CustomerID": pd.array([1, 1, 2, 2, 2], dtype="Int64"),
            "Country": ["UK", "UK", "UK", "UK", "UK"],
            "IsCancellation": [False, False, False, False, False],
            "IsReturn": [False, False, False, False, False],
        }
    )


@pytest.fixture()
def cancellation_df() -> pd.DataFrame:
    """Dataset with cancellation and return rows."""
    return pd.DataFrame(
        {
            "InvoiceNo": ["I1", "I1", "C1", "C1", "I2"],
            "StockCode": ["P1", "P2", "P3", "P4", "P5"],
            "Description": ["x", "y", "z", "w", "v"],
            "Quantity": [2, 1, -5, -3, 4],
            "InvoiceDate": pd.to_datetime(
                ["2011-01-01", "2011-01-01", "2011-01-02", "2011-01-02", "2011-01-03"]
            ),
            "UnitPrice": [10.0, 5.0, 100.0, 50.0, 20.0],
            "CustomerID": pd.array([1, 1, 1, 1, 1], dtype="Int64"),
            "Country": ["UK", "UK", "UK", "UK", "UK"],
            "IsCancellation": [False, False, True, True, False],
            "IsReturn": [False, False, False, False, False],
        }
    )


# ---------------------------------------------------------------------------
# compute_line_revenue()
# ---------------------------------------------------------------------------


class TestComputeLineRevenue:
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
# aggregate_customer_base()
# ---------------------------------------------------------------------------


class TestAggregateCustomerBase:
    def test_one_customer_one_row(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        # Filter to only customer 2 (1 row in basic_df group).
        df_single = basic_df[basic_df["CustomerID"] == 2].reset_index(drop=True)
        result = aggregate_customer_base(df_single, agg_config)
        assert result.df.shape[0] == 1
        assert result.output_row_count == 1

    def test_multiple_transactions_aggregated(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        # 2 distinct customers.
        assert result.output_row_count == 2
        # CustomerID appears once each.
        assert result.df["CustomerID"].duplicated().sum() == 0

    def test_total_quantity(self, basic_df: pd.DataFrame, agg_config: AggregationConfig) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        # Customer 1: Quantity = 2 + 1 = 3.
        c1 = result.df[result.df["CustomerID"] == 1].iloc[0]
        assert float(c1["TotalQuantity"]) == pytest.approx(3.0)
        # Customer 2: Quantity = 3 + 4 + 2 = 9.
        c2 = result.df[result.df["CustomerID"] == 2].iloc[0]
        assert float(c2["TotalQuantity"]) == pytest.approx(9.0)

    def test_total_monetary_signed(
        self, cancellation_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(cancellation_df, agg_config)
        c1 = result.df.iloc[0]
        # I1+I1: 2*10 + 1*5 = 25
        # C1+C1: -5*100 + -3*50 = -650
        # I2: 4*20 = 80
        expected = 25.0 + (-650.0) + 80.0
        assert float(c1["TotalMonetary"]) == pytest.approx(expected)

    def test_first_purchase_date(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c1 = result.df[result.df["CustomerID"] == 1].iloc[0]
        assert c1["FirstPurchaseDate"] == pd.Timestamp("2011-01-01")

    def test_last_purchase_date(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c2 = result.df[result.df["CustomerID"] == 2].iloc[0]
        assert c2["LastPurchaseDate"] == pd.Timestamp("2011-01-03")

    def test_transaction_line_count(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c1 = result.df[result.df["CustomerID"] == 1].iloc[0]
        # Customer 1: 2 rows (I1 appears twice).
        assert int(c1["TransactionLineCount"]) == 2
        c2 = result.df[result.df["CustomerID"] == 2].iloc[0]
        # Customer 2: 3 rows (I2 + I3+I3).
        assert int(c2["TransactionLineCount"]) == 3

    def test_distinct_invoice_count(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c1 = result.df[result.df["CustomerID"] == 1].iloc[0]
        # Customer 1: I1, I1 → 1 unique.
        assert int(c1["DistinctInvoiceCount"]) == 1
        c2 = result.df[result.df["CustomerID"] == 2].iloc[0]
        # Customer 2: I2, I3, I3 → 2 unique.
        assert int(c2["DistinctInvoiceCount"]) == 2

    def test_distinct_products(self, basic_df: pd.DataFrame, agg_config: AggregationConfig) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c1 = result.df[result.df["CustomerID"] == 1].iloc[0]
        # Customer 1: P1, P2 → 2.
        assert int(c1["DistinctProducts"]) == 2
        c2 = result.df[result.df["CustomerID"] == 2].iloc[0]
        # Customer 2: P1, P3, P4 → 3.
        assert int(c2["DistinctProducts"]) == 3

    def test_average_transaction_value(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c2 = result.df[result.df["CustomerID"] == 2].iloc[0]
        # Customer 2: Monetary = 3*10 + 4*20 + 2*15 = 30 + 80 + 30 = 140
        # DistinctInvoiceCount = 2 (I2, I3)
        # Average = 140 / 2 = 70
        assert float(c2["AverageTransactionValue"]) == pytest.approx(70.0)

    def test_purchase_frequency_equals_distinct_invoice(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c2 = result.df[result.df["CustomerID"] == 2].iloc[0]
        assert int(c2["PurchaseFrequency"]) == int(c2["DistinctInvoiceCount"])

    def test_cancellation_invoice_count(
        self, cancellation_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(cancellation_df, agg_config)
        c1 = result.df.iloc[0]
        # Customer 1: cancellation invoices: C1 → 1 unique.
        assert int(c1["CancellationInvoiceCount"]) == 1

    def test_return_invoice_count_no_returns(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        c1 = result.df[result.df["CustomerID"] == 1].iloc[0]
        # No return rows in basic_df.
        assert int(c1["ReturnInvoiceCount"]) == 0

    def test_empty_input_returns_empty_dataframe(self, agg_config: AggregationConfig) -> None:
        empty_df = pd.DataFrame(
            {
                "InvoiceNo": pd.Series([], dtype="string"),
                "StockCode": pd.Series([], dtype="string"),
                "Description": pd.Series([], dtype="str"),
                "Quantity": pd.Series([], dtype="int64"),
                "InvoiceDate": pd.Series([], dtype="datetime64[ns]"),
                "UnitPrice": pd.Series([], dtype="float64"),
                "CustomerID": pd.Series([], dtype="Int64"),
                "Country": pd.Series([], dtype="str"),
                "IsCancellation": pd.Series([], dtype="bool"),
                "IsReturn": pd.Series([], dtype="bool"),
            }
        )
        result = aggregate_customer_base(empty_df, agg_config)
        assert result.df.shape[0] == 0
        # CustomerID column still present.
        assert "CustomerID" in result.df.columns

    def test_single_row_input(self, agg_config: AggregationConfig) -> None:
        single_df = pd.DataFrame(
            {
                "InvoiceNo": ["I1"],
                "StockCode": ["P1"],
                "Description": ["x"],
                "Quantity": [5],
                "InvoiceDate": pd.to_datetime(["2011-01-01"]),
                "UnitPrice": [10.0],
                "CustomerID": pd.array([1], dtype="Int64"),
                "Country": ["UK"],
                "IsCancellation": [False],
                "IsReturn": [False],
            }
        )
        result = aggregate_customer_base(single_df, agg_config)
        assert result.df.shape[0] == 1
        assert result.output_row_count == 1

    def test_output_schema(self, basic_df: pd.DataFrame, agg_config: AggregationConfig) -> None:
        result = aggregate_customer_base(basic_df, agg_config)
        expected_cols = {agg_config.customer_key} | {s.name for s in agg_config.aggregations}
        assert set(result.df.columns) == expected_cols

    def test_input_not_mutated(self, basic_df: pd.DataFrame, agg_config: AggregationConfig) -> None:
        snapshot = basic_df.copy(deep=True)
        _ = aggregate_customer_base(basic_df, agg_config)
        assert basic_df.equals(snapshot)
        assert LINE_REVENUE_COLUMN not in basic_df.columns

    def test_null_customer_id_raises(
        self, basic_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        df = basic_df.copy(deep=True)
        df.loc[0, "CustomerID"] = pd.NA
        with pytest.raises(ValueError, match="null.*CustomerID"):
            aggregate_customer_base(df, agg_config)

    def test_total_quantity_negative_warning(
        self, cancellation_df: pd.DataFrame, agg_config: AggregationConfig
    ) -> None:
        result = aggregate_customer_base(cancellation_df, agg_config)
        c1 = result.df.iloc[0]
        # TotalQuantity = 2 + 1 + (-5) + (-3) + 4 = -1 (negative due to cancellation).
        assert float(c1["TotalQuantity"]) == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# build_base_schema()
# ---------------------------------------------------------------------------


class TestBuildBaseSchema:
    def test_returns_dict(self, agg_config: AggregationConfig) -> None:
        schema = build_base_schema(agg_config)
        assert isinstance(schema, dict)
        assert "CustomerID" in schema
        assert len(schema) == 1 + len(agg_config.aggregations)
