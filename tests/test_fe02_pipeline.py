"""Integration tests for the FE-02 cleaning pipeline.

These tests verify the end-to-end behaviour of
``scripts.run_fe02_cleaning.run_pipeline`` against an in-memory
synthetic dataset. They do **not** touch the real raw xlsx file.

The pipeline is exercised through ``run_pipeline`` with a temporary
directory, and the outputs are inspected for:

- Parquet / CSV presence
- Schema stability (8 raw columns + 2 flag columns)
- Per-rule affected counts
- Raw file immutability (synthetic data, no file is modified)
- Determinism (running twice yields identical results)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest
from scripts.run_fe02_cleaning import (
    run_pipeline,
)


@pytest.fixture()
def synthetic_xlsx(tmp_path: Path) -> Path:
    """Write a small but realistic synthetic xlsx file under `tmp_path`."""
    df = pd.DataFrame(
        {
            "InvoiceNo": [
                "536365",
                "536365",  # exact-row duplicate
                "536366",
                "C536367",  # cancellation
                "C536368",  # cancellation, negative qty, negative price
                "536369",
                "536370",
                "",
            ],
            "StockCode": ["P1", "P1", "P2", "P3", "P4", "P5", "P6", "P7"],
            "Description": [
                "WHITE HANGING HEART T-LIGHT HOLDER",
                "WHITE HANGING HEART T-LIGHT HOLDER",
                "WHITE METAL LANTERN",
                "REGENCY CAKESTAND 3 TIER",
                None,
                "MISC",
                "POSTAGE",
                "BAG",
            ],
            "Quantity": [6, 6, 1, 1, -2, 0, 4, 5],
            "InvoiceDate": pd.to_datetime(
                [
                    "2011-05-31 11:22:00",
                    "2011-05-31 11:22:00",
                    "2011-05-31 11:25:00",
                    "2011-05-31 11:30:00",
                    "2011-05-31 11:35:00",
                    "2011-05-31 11:40:00",
                    "2011-05-31 11:45:00",
                    "2011-05-31 11:50:00",
                ]
            ),
            "UnitPrice": [2.55, 2.55, 3.39, 0.0, -1.0, 1.0, 1.25, 2.5],
            "CustomerID": [17850.0, 17850.0, 17850.0, 13085.0, 13085.0, None, 13086.0, 13087.0],
            "Country": ["UK", "UK", "UK", "France", "France", "UK", "Germany", "UK"],
        }
    )
    primary_dir = tmp_path / "raw" / "primary"
    primary_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = primary_dir / "Online Retail.xlsx"
    df.to_excel(xlsx_path, sheet_name="Online Retail", index=False)
    return xlsx_path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TestRunPipeline:
    def test_pipeline_runs_end_to_end(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        summary = run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        assert summary["rows_in"] == 8
        assert summary["rows_out"] < 8
        assert summary["rows_removed_total"] > 0
        # Two cancellations and one return flagged in the fixture.
        assert summary["flagged_cancellations"] == 2
        assert summary["flagged_returns"] == 1

    def test_parquet_and_csv_written(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        assert (processed_dir / "transactions_clean.parquet").exists()
        assert (processed_dir / "transactions_clean.csv").exists()

    def test_csv_disabled_skips_csv(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
            write_csv=False,
        )
        assert (processed_dir / "transactions_clean.parquet").exists()
        assert not (processed_dir / "transactions_clean.csv").exists()

    def test_cleaned_dataset_has_flag_columns(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        df_clean = pd.read_parquet(processed_dir / "transactions_clean.parquet")
        assert "IsCancellation" in df_clean.columns
        assert "IsReturn" in df_clean.columns
        assert df_clean["IsCancellation"].dtype == bool
        assert df_clean["IsReturn"].dtype == bool

    def test_cleaned_dataset_keeps_all_raw_columns(
        self, synthetic_xlsx: Path, tmp_path: Path
    ) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        df_clean = pd.read_parquet(processed_dir / "transactions_clean.parquet")
        for col in (
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
        ):
            assert col in df_clean.columns

    def test_reports_directory_contents(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        for required in (
            "cleaning_report.md",
            "cleaning_rules.csv",
            "before_after_summary.csv",
            "invalid_records_summary.csv",
            "missing_values.csv",
            "duplicate_analysis.csv",
            "transaction_quality.csv",
            "cleaning_run.json",
        ):
            assert (report_dir / required).exists(), f"missing {required}"

    def test_raw_file_not_modified(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        sha_before = _sha256(synthetic_xlsx)
        mtime_before = synthetic_xlsx.stat().st_mtime
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        sha_after = _sha256(synthetic_xlsx)
        mtime_after = synthetic_xlsx.stat().st_mtime
        assert sha_before == sha_after
        assert mtime_before == mtime_after

    def test_deterministic_outputs(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        processed_a = tmp_path / "proc_a"
        report_a = tmp_path / "rep_a"
        processed_b = tmp_path / "proc_b"
        report_b = tmp_path / "rep_b"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_a,
            report_dir=report_a,
        )
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_b,
            report_dir=report_b,
        )
        sha_a = _sha256(processed_a / "transactions_clean.parquet")
        sha_b = _sha256(processed_b / "transactions_clean.parquet")
        assert sha_a == sha_b
        # The cleaning-report MD and the CSV outputs must be byte-identical
        # across runs (no random elements anywhere in the pipeline).
        md_a = (report_a / "cleaning_report.md").read_text()
        md_b = (report_b / "cleaning_report.md").read_text()
        assert md_a == md_b
        # And the run-summary JSON, ignoring the timestamp + platform +
        # path fields, must be identical.
        import json

        a = json.loads((report_a / "cleaning_run.json").read_text())
        b = json.loads((report_b / "cleaning_run.json").read_text())
        assert a["input"] == b["input"]
        assert a["config"] == b["config"]
        assert a["summary"] == b["summary"]
        # Output paths differ by tmp_path; only structural fields are checked.
        assert (
            set(a["output"])
            == set(b["output"])
            == {
                "cleaned_parquet",
                "cleaned_csv",
                "report_dir",
            }
        )

    def test_cleaning_report_md_mentions_pipeline(
        self, synthetic_xlsx: Path, tmp_path: Path
    ) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        md = (report_dir / "cleaning_report.md").read_text()
        assert "FE-02" in md
        assert "Pipeline" in md or "pipeline" in md
        assert "PENDING_MENTOR_REVIEW" in md

    def test_cleaning_rules_have_pending_status(self, synthetic_xlsx: Path, tmp_path: Path) -> None:
        processed_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"
        run_pipeline(
            primary_path=synthetic_xlsx,
            processed_dir=processed_dir,
            report_dir=report_dir,
        )
        rules = pd.read_csv(report_dir / "cleaning_rules.csv")
        deferred = set(rules[rules["status"] == "PENDING_MENTOR_REVIEW"]["rule_id"])
        # CL-06 (return flag) and CL-08 (cancellation flag) must be
        # marked as deferred.
        assert "CL-06" in deferred
        assert "CL-08" in deferred

    def test_missing_primary_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            run_pipeline(
                primary_path=tmp_path / "no_such_file.xlsx",
                processed_dir=tmp_path / "proc",
                report_dir=tmp_path / "rep",
            )
