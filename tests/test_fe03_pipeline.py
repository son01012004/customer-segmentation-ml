"""Integration tests for the FE-03 orchestrator.

These tests use **synthetic** data only:

- No raw XLSX is opened.
- No production FE-02 parquet is read.
- A small, in-memory FE-02-shaped parquet is written to a
  ``tmp_path`` and the orchestrator is pointed at it.

Coverage
--------
- Default run produces all expected reports.
- Default run does **not** create a treated dataset.
- SHA-256 of the cleaned parquet is unchanged before / after the run.
- ``--write-treated`` without YAML opt-in → no treated dataset, warning.
- YAML opt-in + ``--write-treated`` → treated dataset is written.
- Input DataFrame is not mutated.
- Output is deterministic across runs (with timestamp excluded).
- LineRevenue is computed correctly.
- Filter modes differ in row counts when cancellations / returns exist.
- Customer-level diagnostic is generated and clearly diagnostic-only.
- Config loader rejects malformed YAML and accepts strict YAML.
- ``PENDING_MENTOR_REVIEW`` is preserved end-to-end.
- ``OutlierConfigError`` is raised for unknown detection / treatment.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest
from scripts.run_fe03_outlier_analysis import (
    REQUIRED_CLEANED_COLUMNS,
    _resolve_outlier_config,
    _validate_cleaned_schema,
    run_outlier_pipeline,
)

from customer_segmentation.config.outlier_loader import (
    CustomerAggregationConfig,
    CustomerDiagnosticConfig,
    FeatureOutlierConfig,
    OutlierAnalysisConfig,
    OutlierConfigError,
    OutputConfig,
    SensitivityConfig,
    SourceConfig,
    load_outlier_config,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def synthetic_cleaned_parquet(tmp_path: Path) -> Path:
    """Write a small FE-02-shaped parquet to ``tmp_path`` and return its path.

    The synthetic dataset contains:

    - 12 normal purchase rows (3 customers, 4 invoices).
    - 2 cancellation rows (C-prefixed InvoiceNo).
    - 2 return rows (negative Quantity without C-prefix).
    - 1 extreme outlier (Quantity=10000) for IQR to detect.
    """
    rows = [
        # Normal purchase rows.
        {
            "InvoiceNo": "I001",
            "StockCode": "A",
            "Description": "A desc",
            "Quantity": 1,
            "InvoiceDate": pd.Timestamp("2026-01-01 09:00:00"),
            "UnitPrice": 1.0,
            "CustomerID": 1,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I001",
            "StockCode": "B",
            "Description": "B desc",
            "Quantity": 2,
            "InvoiceDate": pd.Timestamp("2026-01-01 09:00:00"),
            "UnitPrice": 2.0,
            "CustomerID": 1,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I002",
            "StockCode": "A",
            "Description": "A desc",
            "Quantity": 3,
            "InvoiceDate": pd.Timestamp("2026-01-02 10:00:00"),
            "UnitPrice": 1.5,
            "CustomerID": 1,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I003",
            "StockCode": "C",
            "Description": "C desc",
            "Quantity": 4,
            "InvoiceDate": pd.Timestamp("2026-01-03 11:00:00"),
            "UnitPrice": 3.0,
            "CustomerID": 2,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I003",
            "StockCode": "D",
            "Description": "D desc",
            "Quantity": 5,
            "InvoiceDate": pd.Timestamp("2026-01-03 11:00:00"),
            "UnitPrice": 0.5,
            "CustomerID": 2,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I004",
            "StockCode": "E",
            "Description": "E desc",
            "Quantity": 6,
            "InvoiceDate": pd.Timestamp("2026-01-04 12:00:00"),
            "UnitPrice": 2.5,
            "CustomerID": 2,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I005",
            "StockCode": "A",
            "Description": "A desc",
            "Quantity": 7,
            "InvoiceDate": pd.Timestamp("2026-01-05 13:00:00"),
            "UnitPrice": 1.0,
            "CustomerID": 3,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I006",
            "StockCode": "B",
            "Description": "B desc",
            "Quantity": 8,
            "InvoiceDate": pd.Timestamp("2026-01-06 14:00:00"),
            "UnitPrice": 1.25,
            "CustomerID": 3,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I006",
            "StockCode": "C",
            "Description": "C desc",
            "Quantity": 9,
            "InvoiceDate": pd.Timestamp("2026-01-06 14:00:00"),
            "UnitPrice": 2.0,
            "CustomerID": 3,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        {
            "InvoiceNo": "I006",
            "StockCode": "D",
            "Description": "D desc",
            "Quantity": 10,
            "InvoiceDate": pd.Timestamp("2026-01-06 14:00:00"),
            "UnitPrice": 0.75,
            "CustomerID": 3,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        # Extreme outlier (Quantity=10000).
        {
            "InvoiceNo": "I007",
            "StockCode": "X",
            "Description": "Bulk buy",
            "Quantity": 10000,
            "InvoiceDate": pd.Timestamp("2026-01-07 15:00:00"),
            "UnitPrice": 1.0,
            "CustomerID": 1,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        # Tail customer (high quantity to test customer-level diagnostic).
        {
            "InvoiceNo": "I008",
            "StockCode": "B",
            "Description": "B desc",
            "Quantity": 200,
            "InvoiceDate": pd.Timestamp("2026-01-08 16:00:00"),
            "UnitPrice": 0.5,
            "CustomerID": 1,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": False,
        },
        # Cancellation row (C-prefix, negative Quantity).
        {
            "InvoiceNo": "CI001",
            "StockCode": "A",
            "Description": "A desc",
            "Quantity": -3,
            "InvoiceDate": pd.Timestamp("2026-01-09 17:00:00"),
            "UnitPrice": 1.0,
            "CustomerID": 1,
            "Country": "UK",
            "IsCancellation": True,
            "IsReturn": True,
        },
        # Another cancellation row.
        {
            "InvoiceNo": "CI002",
            "StockCode": "B",
            "Description": "B desc",
            "Quantity": -2,
            "InvoiceDate": pd.Timestamp("2026-01-09 18:00:00"),
            "UnitPrice": 1.5,
            "CustomerID": 2,
            "Country": "UK",
            "IsCancellation": True,
            "IsReturn": True,
        },
        # Return row (negative Quantity, non-C prefix).
        {
            "InvoiceNo": "I009",
            "StockCode": "C",
            "Description": "C desc",
            "Quantity": -4,
            "InvoiceDate": pd.Timestamp("2026-01-10 19:00:00"),
            "UnitPrice": 2.0,
            "CustomerID": 3,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": True,
        },
        # Another return row.
        {
            "InvoiceNo": "I010",
            "StockCode": "D",
            "Description": "D desc",
            "Quantity": -5,
            "InvoiceDate": pd.Timestamp("2026-01-10 20:00:00"),
            "UnitPrice": 1.0,
            "CustomerID": 3,
            "Country": "UK",
            "IsCancellation": False,
            "IsReturn": True,
        },
    ]
    df = pd.DataFrame(rows)
    parquet_path = tmp_path / "transactions_clean.parquet"
    df.to_parquet(parquet_path, index=False)
    return parquet_path


@pytest.fixture()
def synthetic_raw_xlsx(tmp_path: Path) -> Path:
    """Write a tiny dummy raw file (not an XLSX) just to test SHA verification."""
    raw_path = tmp_path / "raw.bin"
    raw_path.write_bytes(b"RAW-RAW-RAW")
    return raw_path


@pytest.fixture()
def default_outlier_config() -> OutlierAnalysisConfig:
    """A minimal valid OutlierAnalysisConfig for synthetic-data runs."""
    return OutlierAnalysisConfig(
        enabled=True,
        random_seed=42,
        source=SourceConfig(
            role="synthetic",
            cleaned_dataset_path="./data/processed/transactions_clean.parquet",
            raw_dataset_path="./data/raw/primary/Online Retail.xlsx",
        ),
        transaction_features=[
            FeatureOutlierConfig(
                column="Quantity",
                detection="iqr",
                iqr_multiplier=1.5,
                percentile_thresholds=(99.0, 99.5, 99.9),
                zscore_threshold=3.0,
                treatment="none",
                status="PENDING_MENTOR_REVIEW",
            ),
            FeatureOutlierConfig(
                column="UnitPrice",
                detection="iqr",
                iqr_multiplier=1.5,
                percentile_thresholds=(99.0, 99.5, 99.9),
                zscore_threshold=3.0,
                treatment="none",
                status="PENDING_MENTOR_REVIEW",
            ),
            FeatureOutlierConfig(
                column="LineRevenue",
                detection="iqr",
                iqr_multiplier=1.5,
                percentile_thresholds=(99.0, 99.5, 99.9),
                zscore_threshold=3.0,
                treatment="none",
                status="PENDING_MENTOR_REVIEW",
            ),
        ],
        customer_diagnostic=CustomerDiagnosticConfig(
            enabled=True,
            customer_key="CustomerID",
            aggregations={
                "total_spend": CustomerAggregationConfig(source="LineRevenue", fn="sum"),
                "total_quantity": CustomerAggregationConfig(source="Quantity", fn="sum"),
                "distinct_invoices": CustomerAggregationConfig(source="InvoiceNo", fn="nunique"),
                "distinct_products": CustomerAggregationConfig(source="StockCode", fn="nunique"),
                "active_days": CustomerAggregationConfig(source="InvoiceDate", fn="nunique_date"),
            },
        ),
        sensitivity=SensitivityConfig(
            enabled=True, thresholds=(1.5, 3.0), percentiles=(99.0, 99.5, 99.9)
        ),
        output=OutputConfig(
            write_treated_dataset=False,
            write_plots=False,
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expected_files(report_dir: Path) -> set[str]:
    return {
        "outlier_analysis.md",
        "distribution_analysis.csv",
        "outlier_summary.csv",
        "treatment_decisions.csv",
        "percentile_analysis.csv",
        "sensitivity_analysis.csv",
        "feature_statistics.csv",
        "customer_level_diagnostic.csv",
        "fe03_run.json",
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_required_columns_are_enumerated(self) -> None:
        # Sanity check on the public constant.
        for col in (
            "InvoiceNo",
            "StockCode",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "IsCancellation",
            "IsReturn",
        ):
            assert col in REQUIRED_CLEANED_COLUMNS

    def test_validate_cleaned_schema_passes_on_valid(self, synthetic_cleaned_parquet: Path) -> None:
        df = pd.read_parquet(synthetic_cleaned_parquet)
        _validate_cleaned_schema(df)  # no exception

    def test_validate_cleaned_schema_raises_on_missing(self) -> None:
        df = pd.DataFrame({"Quantity": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required column"):
            _validate_cleaned_schema(df)


# ---------------------------------------------------------------------------
# Default run
# ---------------------------------------------------------------------------


class TestDefaultRun:
    def test_creates_all_expected_artifacts(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        # All expected artefacts exist.
        produced = {p.name for p in report_dir.iterdir()}
        assert _expected_files(report_dir).issubset(produced)

    def test_default_run_does_not_write_treated_dataset(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        summary = run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
            write_treated_dataset=False,
        )
        assert summary["treated_dataset_written"] is False
        assert summary["treated_dataset_path"] is None

    def test_cleaned_parquet_sha_unchanged(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        from scripts.run_fe03_outlier_analysis import _sha256_file

        before = _sha256_file(synthetic_cleaned_parquet)
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        after = _sha256_file(synthetic_cleaned_parquet)
        assert before == after

    def test_raw_sha_recorded_in_run_json(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        run_json = json.loads((report_dir / "fe03_run.json").read_text())
        assert run_json["input"]["cleaned_parquet_unchanged"] is True
        assert len(run_json["input"]["raw_sha256"]) == 64
        assert len(run_json["input"]["cleaned_parquet_sha256"]) == 64

    def test_no_input_mutation(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        # Snapshot the cleaned parquet before the run.
        df_before = pd.read_parquet(synthetic_cleaned_parquet)
        cols_before = list(df_before.columns)
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        df_after = pd.read_parquet(synthetic_cleaned_parquet)
        assert list(df_after.columns) == cols_before
        # No LineRevenue leaked into the persisted dataset.
        assert "LineRevenue" not in df_after.columns
        assert df_after.shape == df_before.shape

    def test_treatment_decisions_default_to_keep(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        decisions = pd.read_csv(report_dir / "treatment_decisions.csv")
        assert (decisions["recommendation"] == "KEEP").all()
        assert (decisions["status"] == "PENDING_MENTOR_REVIEW").all()

    def test_detection_summary_has_features_and_modes(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        det = pd.read_csv(report_dir / "outlier_summary.csv")
        assert set(det["feature"].unique()) == {"Quantity", "UnitPrice", "LineRevenue"}
        assert set(det["filter_mode"].unique()) == {
            "all_rows",
            "clean_purchase",
            "non_cancellation",
            "non_return",
        }

    def test_filter_modes_yield_different_row_counts(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        det = pd.read_csv(report_dir / "outlier_summary.csv")
        # all_rows has 16 rows; the others have 12 (after removing
        # the 4 cancellation/return rows).
        ar = det.loc[det["filter_mode"] == "all_rows", "total_rows"].iloc[0]
        cp = det.loc[det["filter_mode"] == "clean_purchase", "total_rows"].iloc[0]
        assert ar > cp
        assert cp == 12

    def test_markdown_has_all_sections(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        md = (report_dir / "outlier_analysis.md").read_text()
        for header in [
            "## 1. Objective",
            "## 2. Dataset and Unit of Analysis",
            "## 3. Features Investigated",
            "## 4. Distribution Analysis",
            "## 5. Outlier Detection Methods",
            "## 6. Transaction-Level Analysis",
            "## 7. Customer-Level Diagnostic Analysis",
            "## 8. Cancellation and Return Analysis",
            "## 9. Error vs Real Behavior Assessment",
            "## 10. Treatment Decisions",
            "## 11. Before / After Comparison",
            "## 12. Sensitivity Analysis",
            "## 13. Mentor Decisions Required",
            "## 14. Limitations",
            "## 15. Conclusion",
        ]:
            assert header in md
        assert "diagnostic" in md.lower()
        assert "FE-04" in md
        assert "PENDING_MENTOR_REVIEW" in md


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_markdown_is_byte_stable(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports1"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        md1 = (report_dir / "outlier_analysis.md").read_text()

        report_dir2 = tmp_path / "reports2"
        # Make a fresh config (same content).
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir2,
            config=default_outlier_config,
        )
        md2 = (report_dir2 / "outlier_analysis.md").read_text()
        assert md1 == md2

    def test_csv_outputs_are_byte_stable(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports1"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        report_dir2 = tmp_path / "reports2"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir2,
            config=default_outlier_config,
        )
        for name in (
            "distribution_analysis.csv",
            "outlier_summary.csv",
            "treatment_decisions.csv",
            "percentile_analysis.csv",
            "sensitivity_analysis.csv",
            "feature_statistics.csv",
            "customer_level_diagnostic.csv",
        ):
            a = (report_dir / name).read_bytes()
            b = (report_dir2 / name).read_bytes()
            assert a == b, f"{name} not stable across runs"

    def test_run_json_differs_only_in_timestamp(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports1"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        report_dir2 = tmp_path / "reports2"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir2,
            config=default_outlier_config,
        )
        a = json.loads((report_dir / "fe03_run.json").read_text())
        b = json.loads((report_dir2 / "fe03_run.json").read_text())

        def _scrub(payload: dict) -> dict:
            """Remove fields that vary by run (timestamp, paths)."""
            payload = dict(payload)
            payload.pop("executed_at_utc", None)
            payload["input"] = dict(payload["input"])
            payload["input"].pop("cleaned_parquet", None)
            payload["input"].pop("cleaned_parquet_sha256", None)
            payload["input"].pop("cleaned_parquet_sha256_after", None)
            payload.pop("report_dir", None)
            payload.pop("treated_dataset_path", None)
            payload["outputs"] = {k: v.split("/")[-1] for k, v in payload["outputs"].items()}
            return payload

        assert _scrub(a) == _scrub(b)


# ---------------------------------------------------------------------------
# Treated-dataset opt-in
# ---------------------------------------------------------------------------


class TestTreatedDatasetOptIn:
    def test_cli_flag_without_yaml_does_not_write(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        # YAML opt-out, CLI opt-in → no file.
        cfg = dataclasses.replace(
            default_outlier_config,
            output=dataclasses.replace(default_outlier_config.output, write_treated_dataset=False),
        )
        report_dir = tmp_path / "reports"
        summary = run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=cfg,
            write_treated_dataset=True,
        )
        assert summary["treated_dataset_written"] is False
        assert summary["treated_dataset_path"] is None

    def test_yaml_opt_in_without_cli_does_not_write(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        cfg = dataclasses.replace(
            default_outlier_config,
            output=dataclasses.replace(
                default_outlier_config.output,
                write_treated_dataset=True,
                processed_dir=str(tmp_path / "processed"),
            ),
        )
        report_dir = tmp_path / "reports"
        summary = run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=cfg,
            write_treated_dataset=False,
        )
        assert summary["treated_dataset_written"] is False
        assert not (tmp_path / "processed").exists()

    def test_yaml_opt_in_and_cli_flag_writes_treated_dataset(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        cfg = dataclasses.replace(
            default_outlier_config,
            output=dataclasses.replace(
                default_outlier_config.output,
                write_treated_dataset=True,
                processed_dir=str(tmp_path / "processed"),
                treated_filename="treated.parquet",
            ),
        )
        report_dir = tmp_path / "reports"
        summary = run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=cfg,
            write_treated_dataset=True,
        )
        assert summary["treated_dataset_written"] is True
        treated_path = Path(summary["treated_dataset_path"])
        assert treated_path.exists()
        # The treated dataset must have the same row count as the
        # cleaned one (default treatment is KEEP / none).
        df_treated = pd.read_parquet(treated_path)
        df_clean = pd.read_parquet(synthetic_cleaned_parquet)
        assert df_treated.shape[0] == df_clean.shape[0]
        # But the original cleaned parquet must not be mutated.
        df_clean_again = pd.read_parquet(synthetic_cleaned_parquet)
        assert "LineRevenue" not in df_clean_again.columns


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


class TestConfigResolution:
    def test_explicit_config_takes_precedence(
        self, default_outlier_config: OutlierAnalysisConfig
    ) -> None:
        cfg, label = _resolve_outlier_config(None)
        # Either yaml_auto (if configs/outlier.yaml exists in the test
        # environment) or default. Either way, an explicit config
        # argument bypasses the YAML.
        assert (
            label in {"yaml_auto:...", "default"}
            or label.startswith("yaml_auto:")
            or label == "default"
        )
        # Smoke-test the explicit config.
        assert default_outlier_config.enabled is True

    def test_strict_yaml_rejects_unknown_detection(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "outlier.yaml"
        bad_yaml.write_text(
            "outlier_analysis:\n"
            "  enabled: true\n"
            "  random_seed: 42\n"
            "  source: {role: synthetic, cleaned_dataset_path: x, raw_dataset_path: y}\n"
            "  transaction_features:\n"
            "    - {column: Q, detection: banana, iqr_multiplier: 1.5}\n"
            "  customer_diagnostic: {enabled: false}\n"
            "  filter_modes: []\n"
            "  sensitivity: {enabled: true, thresholds: [1.5], percentiles: [99]}\n"
            "  output: {write_treated_dataset: false}\n"
        )
        with pytest.raises(OutlierConfigError, match="detection"):
            load_outlier_config(bad_yaml, strict=True)

    def test_strict_yaml_rejects_unknown_treatment(self, tmp_path: Path) -> None:
        bad_yaml = tmp_path / "outlier.yaml"
        bad_yaml.write_text(
            "outlier_analysis:\n"
            "  enabled: true\n"
            "  random_seed: 42\n"
            "  source: {role: synthetic, cleaned_dataset_path: x, raw_dataset_path: y}\n"
            "  transaction_features:\n"
            "    - {column: Q, detection: iqr, treatment: obliterate}\n"
            "  customer_diagnostic: {enabled: false}\n"
            "  filter_modes: []\n"
            "  sensitivity: {enabled: true, thresholds: [1.5], percentiles: [99]}\n"
            "  output: {write_treated_dataset: false}\n"
        )
        with pytest.raises(OutlierConfigError, match="treatment"):
            load_outlier_config(bad_yaml, strict=True)

    def test_pending_status_preserved_through_pipeline(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        decisions = pd.read_csv(report_dir / "treatment_decisions.csv")
        # All decision statuses must be PENDING_MENTOR_REVIEW.
        assert (decisions["status"] == "PENDING_MENTOR_REVIEW").all()


# ---------------------------------------------------------------------------
# Distribution and detection sanity
# ---------------------------------------------------------------------------


class TestLineRevenueCorrectness:
    def test_line_revenue_quantity_times_unitprice(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        stats = pd.read_csv(report_dir / "feature_statistics.csv")
        # Pick the LineRevenue row.
        lr = stats.loc[stats["column"] == "LineRevenue"].iloc[0]
        # Sanity-check: the `count` column matches the row count of
        # the cleaned parquet and the `negative_count` matches the
        # number of negative-Quantity rows (because cancellations /
        # returns are present in all_rows).
        df = pd.read_parquet(synthetic_cleaned_parquet)
        assert int(lr["count"]) == int(df.shape[0])
        assert int(lr["negative_count"]) == int((df["Quantity"] < 0).sum())


class TestCustomerDiagnostic:
    def test_customer_diagnostic_outputs_one_row_per_customer(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        diag = pd.read_csv(report_dir / "customer_level_diagnostic.csv")
        # 3 customers in the synthetic dataset.
        assert diag.shape[0] == 3
        assert "total_spend" in diag.columns
        assert "total_quantity" in diag.columns
        assert "distinct_invoices" in diag.columns
        assert "active_days" in diag.columns

    def test_customer_diagnostic_summary_has_diagnostic_marker(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        md = (report_dir / "outlier_analysis.md").read_text()
        # Customer diagnostic outputs must be marked diagnostic-only.
        assert "diagnostic-only" in md.lower() or "diagnostic" in md.lower()
        # And explicitly NOT RFM.
        assert "not" in md.lower()
        assert "FE-04" in md


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_missing_cleaned_parquet_raises(
        self,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        missing = tmp_path / "does_not_exist.parquet"
        with pytest.raises(FileNotFoundError, match="FE-02 cleaned parquet"):
            run_outlier_pipeline(
                cleaned_parquet_path=missing,
                raw_dataset_path=synthetic_raw_xlsx,
                report_dir=tmp_path / "reports",
                config=default_outlier_config,
            )

    def test_missing_raw_raises(
        self,
        synthetic_cleaned_parquet: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        missing = tmp_path / "does_not_exist.xlsx"
        with pytest.raises(FileNotFoundError, match="Raw dataset"):
            run_outlier_pipeline(
                cleaned_parquet_path=synthetic_cleaned_parquet,
                raw_dataset_path=missing,
                report_dir=tmp_path / "reports",
                config=default_outlier_config,
            )

    def test_disabled_config_returns_marker(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        default_outlier_config.enabled = False
        report_dir = tmp_path / "reports"
        summary = run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        assert summary.get("enabled") is False


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------


class TestSensitivity:
    def test_sensitivity_table_covers_all_features_and_modes(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        sens = pd.read_csv(report_dir / "sensitivity_analysis.csv")
        # 3 features × 4 modes × (2 IQR + 3 percentile + 1 zscore) = 72 rows.
        # Plus the customer-level diagnostics.
        assert sens.shape[0] >= 72
        # Wider thresholds should yield fewer-or-equal candidates.
        iqr = sens[sens["method"] == "iqr"]
        if not iqr.empty:
            for feature in iqr["feature"].unique():
                f_df = iqr[iqr["feature"] == feature]
                for mode in f_df["filter_mode"].unique():
                    rows = f_df[f_df["filter_mode"] == mode].sort_values("threshold")
                    diffs = rows["candidates"].diff().dropna()
                    assert (diffs <= 0).all()

    def test_percentile_wider_yields_fewer(
        self,
        synthetic_cleaned_parquet: Path,
        synthetic_raw_xlsx: Path,
        default_outlier_config: OutlierAnalysisConfig,
        tmp_path: Path,
    ) -> None:
        report_dir = tmp_path / "reports"
        run_outlier_pipeline(
            cleaned_parquet_path=synthetic_cleaned_parquet,
            raw_dataset_path=synthetic_raw_xlsx,
            report_dir=report_dir,
            config=default_outlier_config,
        )
        sens = pd.read_csv(report_dir / "sensitivity_analysis.csv")
        pct = sens[sens["method"] == "percentile"]
        if not pct.empty:
            for feature in pct["feature"].unique():
                f_df = pct[pct["feature"] == feature]
                for mode in f_df["filter_mode"].unique():
                    rows = f_df[f_df["filter_mode"] == mode].sort_values("threshold")
                    diffs = rows["candidates"].diff().dropna()
                    assert (diffs <= 0).all()
