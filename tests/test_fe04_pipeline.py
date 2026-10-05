"""Integration tests for the FE-04 aggregation pipeline.

Tests verify the end-to-end behaviour of
``scripts.run_fe04_aggregation.run_aggregation_pipeline``
against synthetic in-memory data. They do **not** touch the real
FE-02 parquet.
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

from customer_segmentation.aggregation.base_dataset import (  # noqa: E402
    LINE_REVENUE_COLUMN,
)
from customer_segmentation.aggregation.config_loader import (  # noqa: E402
    AggregationConfig,
    AggregationSpec,
    LineRevenueColumns,
    MetadataConfig,
    OutputConfig,
    SourceConfig,
    load_aggregation_config,
)
from customer_segmentation.aggregation.validation import validate_base_dataset  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_config() -> AggregationConfig:
    return AggregationConfig(
        enabled=True,
        random_seed=42,
        source=SourceConfig(
            role="test",
            cleaned_dataset_path="./test.parquet",
            raw_dataset_path="./test_raw.xlsx",
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
                description="Tong doanh thu.",
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
                description="Hoa don cancellation.",
            ),
            AggregationSpec(
                name="ReturnInvoiceCount",
                source="InvoiceNo",
                fn="conditional_nunique_return",
                status="WORKING_ASSUMPTION",
                description="Hoa don return.",
            ),
        ],
        customer_key="CustomerID",
        line_revenue_columns=LineRevenueColumns(
            quantity="Quantity",
            unit_price="UnitPrice",
            output=LINE_REVENUE_COLUMN,
        ),
        output=OutputConfig(
            processed_dir="./test_out",
            customer_base_filename="test_customer_base.parquet",
            report_dir="./test_reports",
        ),
        metadata=MetadataConfig(
            stage="FE-04",
            task_description="Test.",
            scope_boundaries=["Customer aggregation"],
            notes=[],
        ),
    )


@pytest.fixture()
def clean_synthetic_df() -> pd.DataFrame:
    """3 customers, clean data (no cancellations/returns)."""
    return pd.DataFrame(
        {
            "InvoiceNo": ["I1", "I1", "I2", "I3", "I3", "I4", "I4", "I5", "I6"],
            "StockCode": ["P1", "P2", "P1", "P3", "P4", "P5", "P6", "P7", "P8"],
            "Description": ["a", "b", "a", "c", "d", "e", "f", "g", "h"],
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
            "Country": ["UK", "UK", "UK", "UK", "UK", "UK", "UK", "UK", "UK"],
            "IsCancellation": [False] * 9,
            "IsReturn": [False] * 9,
        }
    )


# ---------------------------------------------------------------------------
# IT-01: end-to-end aggregation with synthetic data
# ---------------------------------------------------------------------------


class TestEndToEndAggregation:
    def test_end_to_end_produces_correct_row_count(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        """3 distinct customers → 3 rows."""
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        assert result.output_row_count == 3
        assert result.df.shape[0] == 3

    def test_end_to_end_no_duplicate_customer(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        assert result.df["CustomerID"].duplicated().sum() == 0

    def test_end_to_end_all_features_created(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        expected_features = {s.name for s in synthetic_config.aggregations}
        assert set(result.features_created) == expected_features

    def test_end_to_end_input_row_count(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        assert result.input_row_count == clean_synthetic_df.shape[0]


# ---------------------------------------------------------------------------
# IT-02: config resolution
# ---------------------------------------------------------------------------


class TestConfigResolution:
    def test_load_config_from_yaml(self) -> None:
        """Load the real configs/aggregation.yaml."""
        config = load_aggregation_config(Path(_REPO_ROOT / "configs" / "aggregation.yaml"))
        assert isinstance(config, AggregationConfig)
        assert config.enabled is True
        assert config.customer_key == "CustomerID"
        assert len(config.aggregations) > 0

    def test_config_aggregations_have_valid_status(self) -> None:
        config = load_aggregation_config(Path(_REPO_ROOT / "configs" / "aggregation.yaml"))
        for spec in config.aggregations:
            assert spec.status in {"WORKING_ASSUMPTION", "PENDING_MENTOR_REVIEW"}


# ---------------------------------------------------------------------------
# IT-03: validation passes on clean synthetic input
# ---------------------------------------------------------------------------


class TestValidationChecks:
    def test_validation_all_pass_on_clean(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)
        assert val_result.is_valid is True
        failed = [c for c in val_result.checks if c.status == "FAIL"]
        assert len(failed) == 0

    def test_v01_row_count_equals_unique_customer(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)
        v01 = next(c for c in val_result.checks if c.check_id == "V-01")
        assert v01.status == "PASS"

    def test_v02_no_duplicate_customer(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)
        v02 = next(c for c in val_result.checks if c.check_id == "V-02")
        assert v02.status == "PASS"

    def test_v03_customer_id_not_null(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)
        v03 = next(c for c in val_result.checks if c.check_id == "V-03")
        assert v03.status == "PASS"

    def test_v07_distinct_invoice_ge_1(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)
        v07 = next(c for c in val_result.checks if c.check_id == "V-07")
        assert v07.status == "PASS"

    def test_v08_denominator_nonzero(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)
        v08 = next(c for c in val_result.checks if c.check_id == "V-08")
        assert v08.status == "PASS"


# ---------------------------------------------------------------------------
# IT-04: validation fails on corrupted input
# ---------------------------------------------------------------------------


class TestValidationCorrupted:
    def test_validation_fails_on_duplicates(self, synthetic_config: AggregationConfig) -> None:
        """If we manually create duplicate CustomerIDs, V-02 must fail."""

        df = pd.DataFrame(
            {
                "CustomerID": pd.array([1, 1], dtype="Int64"),  # duplicate
                "TotalQuantity": [10, 20],
                "TotalMonetary": [100.0, 200.0],
                "FirstPurchaseDate": pd.to_datetime(["2011-01-01", "2011-01-01"]),
                "LastPurchaseDate": pd.to_datetime(["2011-01-01", "2011-01-01"]),
                "PurchaseFrequency": [1, 1],
                "AverageTransactionValue": [100.0, 200.0],
                "TransactionLineCount": [1, 1],
                "DistinctInvoiceCount": [1, 1],
                "DistinctProducts": [1, 1],
                "CancellationInvoiceCount": [0, 0],
                "ReturnInvoiceCount": [0, 0],
            }
        )
        val_result = validate_base_dataset(df, synthetic_config)
        v02 = next(c for c in val_result.checks if c.check_id == "V-02")
        assert v02.status == "FAIL"


# ---------------------------------------------------------------------------
# IT-05: SHA-256 unchanged
# ---------------------------------------------------------------------------


class TestSHA256Unchanged:
    def test_sha256_helper_deterministic(self) -> None:
        """SHA-256 computed the same way twice must match."""
        from customer_segmentation.aggregation.report import _sha256_file

        test_content = b"hello world"
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(test_content)
            f.flush()
            path = Path(f.name)

        sha1 = _sha256_file(path)
        sha2 = _sha256_file(path)
        assert sha1 == sha2
        assert len(sha1) == 64  # SHA-256 hex length.

        path.unlink()


# ---------------------------------------------------------------------------
# IT-06: output path correctness
# ---------------------------------------------------------------------------


class TestOutputPaths:
    def test_write_reports_creates_files(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig, tmp_path: Path
    ) -> None:
        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base
        from customer_segmentation.aggregation.report import write_reports

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)

        report_dir = tmp_path / "reports"
        report_paths = write_reports(
            report_dir=report_dir,
            input_df=clean_synthetic_df,
            output_df=result.df,
            config=synthetic_config,
            validation_result=val_result,
            input_sha256="abc123",
            output_sha256="abc123",
            config_source="test",
            executed_at_utc="2026-01-01T00:00:00+00:00",
            platform_info={"python": "3.11", "system": "Linux"},
        )

        assert (report_dir / "aggregation_report.md").exists()
        assert (report_dir / "aggregation_summary.csv").exists()
        assert (report_dir / "validation_report.csv").exists()
        assert (report_dir / "fe04_run.json").exists()
        assert (report_dir / "feature_dictionary.csv").exists()
        assert len(report_paths) == 5


# ---------------------------------------------------------------------------
# IT-07: fe04_run.json contents
# ---------------------------------------------------------------------------


class TestRunJSON:
    def test_run_json_has_required_fields(
        self, clean_synthetic_df: pd.DataFrame, synthetic_config: AggregationConfig, tmp_path: Path
    ) -> None:
        import json

        from customer_segmentation.aggregation.base_dataset import aggregate_customer_base
        from customer_segmentation.aggregation.report import write_reports

        result = aggregate_customer_base(clean_synthetic_df, synthetic_config)
        val_result = validate_base_dataset(result.df, synthetic_config)

        report_dir = tmp_path / "reports"
        write_reports(
            report_dir=report_dir,
            input_df=clean_synthetic_df,
            output_df=result.df,
            config=synthetic_config,
            validation_result=val_result,
            input_sha256="abc123",
            output_sha256="abc123",
            config_source="test",
            executed_at_utc="2026-01-01T00:00:00+00:00",
            platform_info={"python": "3.11", "system": "Linux"},
        )

        run_json_path = report_dir / "fe04_run.json"
        with run_json_path.open() as f:
            run_json = json.load(f)

        required_keys = {
            "task_id",
            "executed_at_utc",
            "platform",
            "input",
            "output",
            "config",
            "config_source",
            "validation",
            "reports",
        }
        assert required_keys.issubset(run_json.keys())
        assert run_json["task_id"] == "FE-04"
        assert run_json["input"]["sha256_unchanged"] is True
        assert run_json["validation"]["is_valid"] is True
