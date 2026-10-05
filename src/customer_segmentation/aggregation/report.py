"""FE-04 report builders: CSV, JSON, and Markdown reports.

All reports are generated in tiếng Việt.

Output files:
- reports/fe04/aggregation_summary.csv
- reports/fe04/validation_report.csv
- reports/fe04/aggregation_report.md
- reports/fe04/fe04_run.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from customer_segmentation.aggregation.config_loader import (
    AggregationConfig,
    aggregation_config_to_dict,
)
from customer_segmentation.aggregation.validation import (
    ValidationResult,
    validation_result_to_dataframe,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute SHA-256 of a file by streaming chunks."""
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False, default=str))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Before / After summary
# ---------------------------------------------------------------------------


def build_aggregation_summary(
    *,
    input_df: pd.DataFrame,
    output_df: pd.DataFrame,
    config: AggregationConfig,
) -> pd.DataFrame:
    """Build before/after summary table (tiếng Việt).

    Parameters
    ----------
    input_df : pandas.DataFrame
        FE-02 transaction-level dataset.
    output_df : pandas.DataFrame
        FE-04 customer-level base dataset.
    config : AggregationConfig

    Returns
    -------
    pandas.DataFrame
        One row per metric.
    """
    rows = []

    def _add(
        metric: str,
        before_val: Any,
        after_val: Any,
        note: str = "",
    ) -> None:
        rows.append(
            {
                "metric": metric,
                "before": str(before_val),
                "after": str(after_val),
                "difference": "",
                "note": note,
            }
        )

    _add(
        "Tổng số dòng (transaction / customer)",
        input_df.shape[0],
        output_df.shape[0],
        note="Transaction-level → Customer-level",
    )
    _add(
        "Tổng số cột",
        input_df.shape[1],
        output_df.shape[1],
        note="Transaction-level → Customer-level",
    )

    # Unique CustomerID.
    before_cid = (
        input_df["CustomerID"].nunique(dropna=True) if "CustomerID" in input_df.columns else 0
    )
    after_cid = (
        output_df["CustomerID"].nunique(dropna=True) if "CustomerID" in output_df.columns else 0
    )
    _add("Số CustomerID riêng biệt", int(before_cid), int(after_cid))

    # Missing CustomerID.
    before_missing = (
        int(input_df["CustomerID"].isna().sum()) if "CustomerID" in input_df.columns else 0
    )
    after_missing = (
        int(output_df["CustomerID"].isna().sum()) if "CustomerID" in output_df.columns else 0
    )
    _add("Số dòng có CustomerID null", before_missing, after_missing)

    # Date range.
    if "InvoiceDate" in input_df.columns:
        min_date = input_df["InvoiceDate"].min()
        max_date = input_df["InvoiceDate"].max()
        _add("Ngày giao dịch nhỏ nhất", str(min_date), "", note="Input only")
        _add("Ngày giao dịch lớn nhất", str(max_date), "", note="Input only")

    if "FirstPurchaseDate" in output_df.columns:
        min_fpd = output_df["FirstPurchaseDate"].min()
        max_lpd = output_df["LastPurchaseDate"].max()
        _add("FirstPurchaseDate nhỏ nhất", "", str(min_fpd), note="Output only")
        _add("LastPurchaseDate lớn nhất", "", str(max_lpd), note="Output only")

    # Output features created.
    features = [c for c in output_df.columns if c != config.customer_key]
    for feat in features:
        if feat in output_df.columns:
            col = output_df[feat]
            if pd.api.types.is_numeric_dtype(col):
                vals = pd.to_numeric(col, errors="coerce").dropna()
                if len(vals) > 0:
                    _add(f"{feat} — min", "", f"{vals.min():.4f}", note="Output only")
                    _add(f"{feat} — max", "", f"{vals.max():.4f}", note="Output only")
                    _add(f"{feat} — mean", "", f"{vals.mean():.4f}", note="Output only")
                    _add(f"{feat} — median", "", f"{vals.median():.4f}", note="Output only")

    return pd.DataFrame.from_records(rows)


# ---------------------------------------------------------------------------
# Feature dictionary
# ---------------------------------------------------------------------------


def build_feature_dictionary(config: AggregationConfig) -> pd.DataFrame:
    """Build feature dictionary from aggregation config (tiếng Việt)."""
    rows = []
    for spec in config.aggregations:
        rows.append(
            {
                "feature_name": spec.name,
                "source_column": spec.source,
                "aggregation_fn": spec.fn,
                "status": spec.status,
                "description": spec.description,
            }
        )
    return pd.DataFrame.from_records(rows)


# ---------------------------------------------------------------------------
# Markdown narrative report
# ---------------------------------------------------------------------------


def build_aggregation_md(
    *,
    input_df: pd.DataFrame,
    output_df: pd.DataFrame,
    config: AggregationConfig,
    validation_result: ValidationResult,
    input_sha256: str,
    output_sha256: str,
    config_source: str,
    executed_at_utc: str,
    platform_info: dict[str, str],
) -> str:
    """Build the narrative aggregation report in tiếng Việt."""
    lines: list[str] = []

    lines.append("# FE-04 — Báo Cáo Tổng Hợp Dữ Liệu Cấp Customer-Level")
    lines.append("")
    lines.append(
        "Báo cáo này mô tả quy trình tổng hợp dữ liệu transaction-level "
        "(FE-02 output) thành customer-level base dataset. "
        "Tất cả các số liệu được tính toán trực tiếp từ dữ liệu thực tế, không hard-code."
    )
    lines.append("")

    # 1. Mục tiêu.
    lines.append("## 1. Mục Tiêu")
    lines.append("")
    lines.append(
        "FE-04 chuyển dữ liệu transaction-level đã được làm sạch bởi FE-02 "
        "thành customer-level dataset, trong đó **1 CustomerID = 1 observation**."
    )
    lines.append("")
    lines.append("FE-04 **thực hiện**:")
    for scope in config.metadata.scope_boundaries:
        lines.append(f"- {scope}")
    lines.append("")
    lines.append("FE-04 **KHÔNG thực hiện**:")
    lines.append("- Clustering (K-Means, K-Medoids, Agglomerative, DBSCAN)")
    lines.append("- Feature selection cuối cùng")
    lines.append("- RFM methodology chính thức")
    lines.append("- Scaling / transformation")
    lines.append("- Feature correlation analysis")
    lines.append("")

    # 2. Input dataset.
    lines.append("## 2. Input Dataset")
    lines.append("")
    lines.append("- **File**: `data/processed/transactions_clean.parquet`")
    lines.append(f"- **SHA-256 (trước khi chạy)**: `{input_sha256}`")
    lines.append(f"- **SHA-256 (sau khi chạy)**: `{output_sha256}`")
    lines.append(f"- **Số dòng (input)**: {input_df.shape[0]:,}")
    lines.append(f"- **Số cột (input)**: {input_df.shape[1]}")
    lines.append(
        f"- **CustomerID riêng biệt (input)**: {int(input_df['CustomerID'].nunique(dropna=True)):,}"
    )
    lines.append("")

    # 3. Schema input.
    lines.append("## 3. Schema Input (FE-02 output)")
    lines.append("")
    lines.append("| Cột | dtype | Ý nghĩa |")
    lines.append("| --- | --- | --- |")
    for col in input_df.columns:
        dtype = str(input_df[col].dtype)
        lines.append(f"| `{col}` | `{dtype}` | (FE-02 output) |")
    lines.append("")

    # 4. Aggregation methodology.
    lines.append("## 4. Aggregation Methodology")
    lines.append("")
    lines.append("Tổng hợp theo `CustomerID`. Các bước:")
    lines.append("")
    lines.append("1. Load FE-02 parquet (read-only).")
    lines.append("2. Derive `LineRevenue = Quantity × UnitPrice` (in-memory, không persist).")
    lines.append("3. Group by `CustomerID`.")
    lines.append("4. Tính các aggregate features theo `configs/aggregation.yaml`.")
    lines.append("5. Validate output dataset.")
    lines.append("6. Write `customer_base.parquet`.")
    lines.append("7. SHA-256 verification của input parquet.")
    lines.append("")

    # 5. Feature dictionary.
    lines.append("## 5. Feature Dictionary")
    lines.append("")
    lines.append("| Tên Feature | Cột nguồn | Aggregation | Trạng thái | Mô tả |")
    lines.append("| --- | --- | --- | --- | --- |")
    for spec in config.aggregations:
        desc_short = spec.description.split("\n")[0][:80]
        lines.append(
            f"| `{spec.name}` | `{spec.source}` | `{spec.fn}` | {spec.status} | " f"{desc_short} |"
        )
    lines.append("")

    # 6. Before / After statistics.
    lines.append("## 6. Before / After Statistics")
    lines.append("")
    lines.append("| Chỉ số | Trước (FE-02) | Sau (FE-04) | Ghi chú |")
    lines.append("| --- | ---: | ---: | --- |")
    before_rows = input_df.shape[0]
    after_rows = output_df.shape[0]
    lines.append(f"| Tổng số dòng | {before_rows:,} | {after_rows:,} | Transaction → Customer |")
    lines.append(
        f"| Số cột | {input_df.shape[1]} | {output_df.shape[1]} | Transaction → Customer |"
    )
    before_cid = int(input_df["CustomerID"].nunique(dropna=True))
    after_cid = int(output_df["CustomerID"].nunique(dropna=True))
    lines.append(f"| CustomerID riêng biệt | {before_cid:,} | {after_cid:,} | |")
    before_missing = int(input_df["CustomerID"].isna().sum())
    after_missing = int(output_df["CustomerID"].isna().sum())
    lines.append(f"| CustomerID null | {before_missing:,} | {after_missing:,} | |")
    if "InvoiceDate" in input_df.columns:
        lines.append(f"| Ngày nhỏ nhất | {input_df['InvoiceDate'].min()} | | Input |")
        lines.append(f"| Ngày lớn nhất | {input_df['InvoiceDate'].max()} | | Input |")
    if "FirstPurchaseDate" in output_df.columns:
        lines.append(f"| FirstPurchaseDate | | {output_df['FirstPurchaseDate'].min()} | Output |")
        lines.append(f"| LastPurchaseDate | | {output_df['LastPurchaseDate'].max()} | Output |")
    lines.append("")

    # 7. Numeric statistics (output).
    lines.append("## 7. Thống Kê Numeric (Output)")
    lines.append("")
    numeric_cols = [
        c
        for c in output_df.columns
        if c != config.customer_key and pd.api.types.is_numeric_dtype(output_df[c])
    ]
    if numeric_cols:
        lines.append("| Feature | Count | Min | Max | Mean | Median |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for col in numeric_cols:
            vals = pd.to_numeric(output_df[col], errors="coerce").dropna()
            if len(vals) > 0:
                lines.append(
                    f"| `{col}` | {len(vals):,} | {vals.min():.4f} | {vals.max():.4f} | "
                    f"{vals.mean():.4f} | {vals.median():.4f} |"
                )
    lines.append("")

    # 8. Validation results.
    lines.append("## 8. Kết Quả Validation")
    lines.append("")
    all_pass = validation_result.is_valid
    lines.append(f"**Tổng kết validation**: {'✅ Tất cả PASS' if all_pass else '❌ Có check FAIL'}")
    lines.append("")
    lines.append("| Check ID | Mô tả | Trạng thái | Thông báo |")
    lines.append("| --- | --- | ---: | --- |")
    for check in validation_result.checks:
        icon = "✅" if check.status == "PASS" else ("⚠️" if check.status == "WARNING" else "❌")
        lines.append(
            f"| {check.check_id} | {check.description} | {icon} {check.status} | {check.message} |"
        )
    lines.append("")

    # 9. Working assumptions.
    lines.append("## 9. Working Assumptions")
    lines.append("")
    lines.append("Các giả định sau là **baseline** và có thể được FE-05 review và điều chỉnh:")
    lines.append("")
    assumptions = [
        (
            "WA-01",
            "TotalMonetary là signed monetary baseline",
            "FE-05 sẽ review sign convention cho RFM Monetary",
        ),
        (
            "WA-02",
            "AverageTransactionValue = TotalMonetary / DistinctInvoiceCount",
            "FE-05 có thể điều chỉnh denominator",
        ),
        (
            "WA-03",
            "PurchaseFrequency = DistinctInvoiceCount (working proxy)",
            "FE-05 sẽ quyết định đây có phải RFM Frequency cuối cùng không",
        ),
        (
            "WA-04",
            "CancellationInvoiceCount dựa trên IsCancellation flag",
            "FE-05 sẽ review cancellation treatment",
        ),
        ("WA-05", "ReturnInvoiceCount dựa trên IsReturn flag", "FE-05 sẽ review return treatment"),
    ]
    lines.append("| ID | Giả định | FE-05 xử lý |")
    lines.append("| --- | --- | --- |")
    for wid, assumption, fe05 in assumptions:
        lines.append(f"| {wid} | {assumption} | {fe05} |")
    lines.append("")

    # 10. Limitations.
    lines.append("## 10. Hạn Chế")
    lines.append("")
    lines.append(
        "- **TotalMonetary**: giá trị signed baseline; FE-05 sẽ review sign convention. "
        "Cancellation/return rows tạo giá trị âm."
    )
    lines.append(
        "- **PurchaseFrequency**: working proxy, không phải RFM Frequency cuối cùng. "
        "FE-05 sẽ review và quyết định."
    )
    lines.append(
        "- **AverageTransactionValue**: denominator là DistinctInvoiceCount. "
        "FE-05 có thể điều chỉnh denominator."
    )
    lines.append(
        "- **CustomerID null**: FE-02 đã drop các dòng có null CustomerID. "
        "Nếu FE-02 policy thay đổi, FE-04 cần được cập nhật."
    )
    lines.append("")

    # 11. Reproducibility.
    lines.append("## 11. Reproducibility")
    lines.append("")
    lines.append(f"- **Thời gian chạy (UTC)**: `{executed_at_utc}`")
    lines.append(f"- **Python**: `{platform_info.get('python', 'N/A')}`")
    lines.append(f"- **Platform**: `{platform_info.get('system', 'N/A')}`")
    lines.append(f"- **Config source**: `{config_source}`")
    lines.append(f"- **Input SHA-256 (trước)**: `{input_sha256}`")
    lines.append(f"- **Input SHA-256 (sau)**: `{output_sha256}`")
    lines.append(
        "- **Kết luận SHA**: "
        f"{'✅ Input không thay đổi' if input_sha256 == output_sha256 else '❌ Input đã bị thay đổi!'}"
    )
    lines.append("")

    # 12. Conclusion.
    lines.append("## 12. Kết Luận")
    lines.append("")
    lines.append(
        f"FE-04 đã tổng hợp {before_rows:,} dòng transaction-level "
        f"(FE-02) thành {after_rows:,} dòng customer-level. "
        f"{len(config.aggregations)} aggregate features đã được tạo. "
        "Dataset được validate và ghi nhận reproducibility."
    )
    lines.append("")
    lines.append(
        "**Lưu ý quan trọng**: FE-04 tạo **base dataset** và các **working baseline features**. "
        "FE-05 mới chịu trách nhiệm: RFM methodology, feature selection, "
        "correlation analysis, và final clustering feature set."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Write all reports
# ---------------------------------------------------------------------------


def write_reports(
    *,
    report_dir: Path,
    input_df: pd.DataFrame,
    output_df: pd.DataFrame,
    config: AggregationConfig,
    validation_result: ValidationResult,
    input_sha256: str,
    output_sha256: str,
    config_source: str,
    executed_at_utc: str,
    platform_info: dict[str, str],
) -> dict[str, Path]:
    """Write all FE-04 reports to disk.

    Returns
    -------
    dict[str, Path]
        Map of report name → file path.
    """
    report_dir.mkdir(parents=True, exist_ok=True)

    # 1. aggregation_summary.csv
    summary_df = build_aggregation_summary(
        input_df=input_df,
        output_df=output_df,
        config=config,
    )
    summary_path = report_dir / "aggregation_summary.csv"
    _write_csv(summary_df, summary_path)

    # 2. feature_dictionary.csv
    feat_dict_df = build_feature_dictionary(config)
    feat_dict_path = report_dir / "feature_dictionary.csv"
    _write_csv(feat_dict_df, feat_dict_path)

    # 3. validation_report.csv
    val_df = validation_result_to_dataframe(validation_result)
    val_path = report_dir / "validation_report.csv"
    _write_csv(val_df, val_path)

    # 4. aggregation_report.md
    md_text = build_aggregation_md(
        input_df=input_df,
        output_df=output_df,
        config=config,
        validation_result=validation_result,
        input_sha256=input_sha256,
        output_sha256=output_sha256,
        config_source=config_source,
        executed_at_utc=executed_at_utc,
        platform_info=platform_info,
    )
    md_path = report_dir / "aggregation_report.md"
    _write_text(md_path, md_text)

    # 5. fe04_run.json
    run_json = {
        "task_id": "FE-04",
        "executed_at_utc": executed_at_utc,
        "platform": platform_info,
        "input": {
            "path": "data/processed/transactions_clean.parquet",
            "sha256_before": input_sha256,
            "sha256_after": output_sha256,
            "sha256_unchanged": input_sha256 == output_sha256,
            "rows_in": int(input_df.shape[0]),
            "unique_customers_in": int(input_df["CustomerID"].nunique(dropna=True)),
        },
        "output": {
            "path": f"data/processed/{config.output.customer_base_filename}",
            "rows_out": int(output_df.shape[0]),
            "unique_customers_out": int(output_df["CustomerID"].nunique(dropna=True)),
            "features_created": [c for c in output_df.columns if c != config.customer_key],
        },
        "config": aggregation_config_to_dict(config),
        "config_source": config_source,
        "validation": {
            "is_valid": validation_result.is_valid,
            "checks_passed": sum(1 for c in validation_result.checks if c.status == "PASS"),
            "checks_warning": sum(1 for c in validation_result.checks if c.status == "WARNING"),
            "checks_failed": sum(1 for c in validation_result.checks if c.status == "FAIL"),
        },
        "reports": {
            "summary_csv": str(summary_path),
            "feature_dictionary_csv": str(feat_dict_path),
            "validation_csv": str(val_path),
            "narrative_md": str(md_path),
        },
        "notes": [
            "FE-04 is deterministic: no random operation.",
            "Input parquet is read-only; SHA-256 verified before and after.",
            "LineRevenue is derived in-memory; never persisted back to input.",
            "PurchaseFrequency is a working proxy; not final RFM Frequency.",
            "TotalMonetary is a signed monetary baseline; not final RFM Monetary.",
            "Cancellation/return treatment deferred to FE-05.",
        ],
    }
    run_json_path = report_dir / "fe04_run.json"
    _write_json(run_json_path, run_json)

    return {
        "summary_csv": summary_path,
        "feature_dictionary_csv": feat_dict_path,
        "validation_csv": val_path,
        "narrative_md": md_path,
        "fe04_run_json": run_json_path,
    }
