"""FE-04 orchestrator: aggregate transaction-level data to customer-level base dataset.

Stage: 04_customer_aggregation (FE-04)

Usage (from the repository root):

    python -m scripts.run_fe04_aggregation
    python -m scripts.run_fe04_aggregation --config PATH
    python -m scripts.run_fe04_aggregation --processed-dir ./data/processed

Outputs
-------
Written under ``data/processed/``:

- ``customer_base.parquet`` — the customer-level base dataset
  (1 row per CustomerID). Input cho FE-05.

Written under ``reports/fe04/``:

- ``aggregation_report.md`` — báo cáo narrative (tiếng Việt).
- ``aggregation_summary.csv`` — before/after table.
- ``feature_dictionary.csv`` — feature definitions.
- ``validation_report.csv`` — per-check validation results.
- ``fe04_run.json`` — full run metadata + SHA-256.

Hard constraints (AGENTS.md / Plan V3):
- Input FE-02 parquet is read-only.
- SHA-256 được ghi nhận trong fe04_run.json, không embed vào Parquet metadata.
- SHA-256 của input được verify trước và sau khi chạy; mismatch → RuntimeError.
- No clustering, no feature selection, no scaling, no transformation.
- Production pipeline fail-fast nếu input rỗng.
- PurchaseFrequency là working proxy, không phải RFM Frequency cuối cùng.
- TotalMonetary là signed monetary baseline, không phải RFM Monetary cuối cùng.
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from customer_segmentation.aggregation import (  # noqa: E402
    AggregationConfig,
    AggregationConfigError,
    aggregate_customer_base,
    load_aggregation_config,
    resolve_aggregation_config_path,
    validate_base_dataset,
    write_reports,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PROCESSED_DIR: Path = _REPO_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "fe04"
DEFAULT_CLEANED_PATH: Path = DEFAULT_PROCESSED_DIR / "transactions_clean.parquet"
DEFAULT_CUSTOMER_BASE_FILENAME: str = "customer_base.parquet"

# Columns that the FE-02 cleaned parquet MUST contain.
REQUIRED_CLEANED_COLUMNS: tuple[str, ...] = (
    "InvoiceNo",
    "StockCode",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "IsCancellation",
    "IsReturn",
)


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute SHA-256 of a file by streaming chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_aggregation_config(
    config_path: Path | None,
) -> tuple:
    """Resolve the aggregation config and report the source label."""
    yaml_path = resolve_aggregation_config_path(explicit=config_path)
    if yaml_path is None:
        raise SystemExit(
            "[FE-04] ERROR: configs/aggregation.yaml not found. "
            "Run from the repository root or pass --config."
        )
    try:
        loaded = load_aggregation_config(yaml_path, strict=True)
    except AggregationConfigError as exc:
        raise SystemExit(f"[FE-04] ERROR: invalid aggregation config: {exc}") from exc
    label = f"yaml:{yaml_path}"
    print(f"[FE-04] loaded aggregation config: {yaml_path}")
    return loaded, label


def _validate_cleaned_schema(df: pd.DataFrame) -> None:
    """Fail fast if the FE-02 cleaned parquet is missing required columns."""
    missing = [c for c in REQUIRED_CLEANED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"FE-02 cleaned parquet is missing required column(s): {missing}. "
            "Re-run FE-02 first (python -m scripts.run_fe02_cleaning)."
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_aggregation_pipeline(
    cleaned_parquet_path: Path,
    processed_dir: Path,
    report_dir: Path,
    *,
    config: AggregationConfig | None = None,
    config_path: Path | None = None,
) -> dict:
    """Run the FE-04 aggregation pipeline end-to-end.

    Parameters
    ----------
    cleaned_parquet_path : pathlib.Path
        Path to the FE-02 cleaned parquet.
    processed_dir : pathlib.Path
        Output directory for the customer base dataset.
    report_dir : pathlib.Path
        Output directory for FE-04 reports.
    config : AggregationConfig, optional
        Explicit config. When provided, YAML is not consulted.
    config_path : pathlib.Path, optional
        Explicit YAML path.

    Returns
    -------
    dict
        Run summary suitable for the fe04_run.json artefact.
    """
    # ------------------------------------------------------------------
    # 0. Resolve config
    # ------------------------------------------------------------------
    config_source_label = "explicit_config"
    if config is None:
        config, config_source_label = _resolve_aggregation_config(config_path)
    else:
        print("[FE-04] using explicit AggregationConfig")

    if not config.enabled:
        print("[FE-04] aggregation.enabled=false in config; nothing to do.")
        return {"enabled": False, "config_source": config_source_label}

    if not cleaned_parquet_path.exists():
        raise FileNotFoundError(
            f"FE-02 cleaned parquet not found: {cleaned_parquet_path}. "
            "Run FE-02 first (python -m scripts.run_fe02_cleaning)."
        )

    # ------------------------------------------------------------------
    # 1. SHA-256 before
    # ------------------------------------------------------------------
    input_sha_before = _sha256_file(cleaned_parquet_path)

    # ------------------------------------------------------------------
    # 2. Load input (read-only)
    # ------------------------------------------------------------------
    df_clean = pd.read_parquet(cleaned_parquet_path)
    _validate_cleaned_schema(df_clean)

    # Production: fail-fast nếu input rỗng.
    if df_clean.empty:
        raise ValueError(
            f"FE-02 cleaned parquet is empty ({cleaned_parquet_path}). "
            "Cannot aggregate empty dataset."
        )

    # ------------------------------------------------------------------
    # 3. Aggregate
    # ------------------------------------------------------------------
    print(f"[FE-04] aggregating {df_clean.shape[0]:,} rows → customer-level...")
    result = aggregate_customer_base(df_clean, config)
    print(
        f"[FE-04] aggregation done: {result.input_row_count:,} rows → "
        f"{result.output_row_count:,} customers, "
        f"{len(result.features_created)} features."
    )

    # ------------------------------------------------------------------
    # 4. Validate
    # ------------------------------------------------------------------
    print("[FE-04] running validation checks...")
    val_result = validate_base_dataset(result.df, config)
    passed = sum(1 for c in val_result.checks if c.status == "PASS")
    warnings = sum(1 for c in val_result.checks if c.status == "WARNING")
    failed = sum(1 for c in val_result.checks if c.status == "FAIL")
    print(f"[FE-04] validation: {passed} PASS, {warnings} WARNING, {failed} FAIL")
    if failed > 0:
        print("[FE-04] WARNING: some validation checks FAILED:")
        for check in val_result.checks:
            if check.status == "FAIL":
                print(f"  {check.check_id}: {check.message}")

    if not val_result.is_valid:
        raise RuntimeError(
            f"FE-04 validation failed ({failed} check(s)). " "Fix the issues before proceeding."
        )

    # ------------------------------------------------------------------
    # 5. Write output
    # ------------------------------------------------------------------
    processed_dir.mkdir(parents=True, exist_ok=True)
    customer_base_path = processed_dir / config.output.customer_base_filename
    result.df.to_parquet(customer_base_path, index=False)
    print(f"[FE-04] customer base dataset written: {customer_base_path}")

    # ------------------------------------------------------------------
    # 6. SHA-256 after
    # ------------------------------------------------------------------
    input_sha_after = _sha256_file(cleaned_parquet_path)
    if input_sha_after != input_sha_before:
        raise RuntimeError(
            f"FE-02 cleaned parquet SHA-256 changed during FE-04 run: "
            f"before={input_sha_before}, after={input_sha_after}. "
            "FE-04 must not mutate the input dataset."
        )
    print(f"[FE-04] FE-02 parquet SHA-256 verified unchanged " f"({input_sha_before[:16]}...).")

    # ------------------------------------------------------------------
    # 7. Write reports
    # ------------------------------------------------------------------
    executed_at_utc = datetime.now(UTC).isoformat()
    platform_info = {
        "python": platform.python_version(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }

    report_paths = write_reports(
        report_dir=report_dir,
        input_df=df_clean,
        output_df=result.df,
        config=config,
        validation_result=val_result,
        input_sha256=input_sha_before,
        output_sha256=input_sha_after,
        config_source=config_source_label,
        executed_at_utc=executed_at_utc,
        platform_info=platform_info,
    )
    print(f"[FE-04] reports written: {report_dir}")

    return {
        "task_id": "FE-04",
        "enabled": True,
        "config_source": config_source_label,
        "input_sha256_before": input_sha_before,
        "input_sha256_after": input_sha_after,
        "input_sha256_unchanged": input_sha_before == input_sha_after,
        "input_rows": result.input_row_count,
        "output_rows": result.output_row_count,
        "features_created": result.features_created,
        "customer_base_path": str(customer_base_path),
        "report_dir": str(report_dir),
        "validation": {
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "is_valid": val_result.is_valid,
        },
        "executed_at_utc": executed_at_utc,
        "platform": platform_info,
        "reports": {k: str(v) for k, v in report_paths.items()},
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "FE-04 customer-level aggregation pipeline. "
            "Reads the FE-02 cleaned parquet and writes customer_base.parquet "
            "under data/processed/ and reports under reports/fe04/."
        ),
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to the aggregation YAML. "
        "If omitted, auto-discovers 'configs/aggregation.yaml'.",
    )
    p.add_argument(
        "--cleaned-parquet",
        type=Path,
        default=DEFAULT_CLEANED_PATH,
        help="Path to the FE-02 cleaned parquet.",
    )
    p.add_argument(
        "--processed-dir",
        type=Path,
        default=DEFAULT_PROCESSED_DIR,
        help="Output directory for the customer base dataset.",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Output directory for FE-04 reports.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)
    print(f"[FE-04] cleaned parquet: {args.cleaned_parquet}")
    print(f"[FE-04] output dir:      {args.processed_dir}")
    print(f"[FE-04] report dir:      {args.report_dir}")

    summary = run_aggregation_pipeline(
        cleaned_parquet_path=args.cleaned_parquet,
        processed_dir=args.processed_dir,
        report_dir=args.report_dir,
        config_path=args.config,
    )

    if not summary.get("enabled", True):
        return

    print(
        f"[FE-04] aggregation done: "
        f"{summary['input_rows']:,} → {summary['output_rows']:,} customers, "
        f"{len(summary['features_created'])} features."
    )
    print(f"[FE-04] customer base:   {summary['customer_base_path']}")
    print(f"[FE-04] reports:         {summary['report_dir']}")
    val = summary.get("validation", {})
    print(
        f"[FE-04] validation:      "
        f"{val.get('passed', 0)} PASS / "
        f"{val.get('warnings', 0)} WARNING / "
        f"{val.get('failed', 0)} FAIL"
    )
    print(f"[FE-04] input SHA unchanged: {summary['input_sha256_unchanged']}")


if __name__ == "__main__":
    main()
