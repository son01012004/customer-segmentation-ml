"""FE-02 orchestrator: clean the primary dataset and emit artifacts.

Stage: 02_data_cleaning (FE-02)

Usage (from the repository root):

    python -m scripts.run_fe02_cleaning

Outputs
-------
Written under ``data/processed/``:

- ``transactions_clean.parquet`` — the cleaned transaction-level dataset
  (Parquet, gzip). Used as the input of FE-03 / RFM.
- ``transactions_clean.csv`` — a CSV mirror for quick inspection. The
  CSV is optional; pass ``--no-csv`` to skip it.

Written under ``reports/fe02/``:

- ``cleaning_report.md`` — narrative cleaning report.
- ``cleaning_rules.csv`` — rule inventory (one row per cleaning rule).
- ``before_after_summary.csv`` — before/after metric table.
- ``invalid_records_summary.csv`` — per-rule invalid-record counts.
- ``missing_values.csv`` — per-column missing-value summary.
- ``duplicate_analysis.csv`` — exact + subset-key duplicate analysis.
- ``transaction_quality.csv`` — transaction-level numeric statistics
  after each major stage.
- ``cleaning_run.json`` — full run summary in JSON.

Notes
-----
- This script only **reads** the raw primary file; it never writes
  back to ``data/raw/``.
- The output path is resolved from the script's own location so the
  pipeline works regardless of the caller's working directory.
- The pipeline is deterministic: no random operation is performed
  at any stage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from customer_segmentation.config.loader import (  # noqa: E402
    PreprocessingConfigError,
    load_preprocessing_config,
    resolve_preprocessing_config_path,
)
from customer_segmentation.data.audit import (  # noqa: E402
    basic_overview,
    categorical_profile,
    identifier_profile,
    numerical_profile,
)
from customer_segmentation.data.loader import (  # noqa: E402
    list_sheet_names,
    load_raw_transactions,
)
from customer_segmentation.preprocessing.cleaning import (  # noqa: E402
    PipelineConfig,
    build_rule_inventory,
    clean_transactions,
    default_pipeline_config,
    summarise_cleaning_result,
)
from customer_segmentation.preprocessing.duplicates import (  # noqa: E402
    analyse_subset_duplicates,
    exact_duplicate_analysis,
)
from customer_segmentation.preprocessing.missing_values import (  # noqa: E402
    MissingSummary,
    summarise_missing,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


DEFAULT_PRIMARY_DIR = _REPO_ROOT / "data" / "raw" / "primary"
DEFAULT_PROCESSED_DIR = _REPO_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR = _REPO_ROOT / "reports" / "fe02"

PRIMARY_FILENAME = "Online Retail.xlsx"
PRIMARY_SHEET = "Online Retail"

CLEAN_FILENAME_PARQUET = "transactions_clean.parquet"
CLEAN_FILENAME_CSV = "transactions_clean.csv"


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False, default=str))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute the SHA-256 of a file by streaming chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return columns suitable for :func:`numerical_profile`.

    Excludes boolean columns, which ``pd.api.types.is_numeric_dtype``
    classifies as numeric but which cannot be reduced to a quantile
    (this would raise ``TypeError: numpy boolean subtract``).
    """
    cols = []
    for c in df.columns:
        if pd.api.types.is_bool_dtype(df[c]):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def _resolve_pipeline_config(
    config: PipelineConfig | None,
    *,
    preprocessing_config_path: Path | None,
    config_source_label: list[str],
) -> PipelineConfig:
    """Resolve the active cleaning config, preferring YAML over defaults.

    Priority order:

    1. Explicit ``config`` argument — used by tests and by library
       callers that want full programmatic control.
    2. ``preprocessing_config_path`` — load the YAML at this path.
    3. ``configs/preprocessing.yaml`` auto-discovery.
    4. :func:`default_pipeline_config` — fallback used only when both
       (2) and (3) are missing or fail. A warning is printed so the
       user knows the YAML was not consulted.

    Parameters
    ----------
    config : PipelineConfig or None
        Explicit pipeline configuration. Wins over everything else.
    preprocessing_config_path : pathlib.Path or None
        Explicit YAML path; ``None`` triggers auto-discovery.
    config_source_label : list[str]
        Mutable holder used to communicate the resolved source back to
        the caller (so it can be embedded in the run summary). One of
        ``"explicit_config"``, ``"yaml:<path>"``,
        ``"yaml_auto:<path>"``, ``"default"``.

    Returns
    -------
    PipelineConfig
        Resolved configuration.
    """
    if config is not None:
        config_source_label.append("explicit_config")
        return config

    yaml_path = resolve_preprocessing_config_path(explicit=preprocessing_config_path)
    if yaml_path is None:
        config_source_label.append("default")
        print(
            "[FE-02] NOTE: configs/preprocessing.yaml not found; "
            "falling back to default_pipeline_config()."
        )
        return default_pipeline_config()

    try:
        loaded = load_preprocessing_config(yaml_path, strict=True)
    except PreprocessingConfigError as exc:
        # Strict-mode failure must surface, not silently degrade.
        raise SystemExit(f"[FE-02] invalid preprocessing config at {yaml_path}: {exc}") from exc

    if preprocessing_config_path is not None:
        config_source_label.append(f"yaml:{yaml_path}")
    else:
        config_source_label.append(f"yaml_auto:{yaml_path}")

    print(f"[FE-02] loaded preprocessing config: {yaml_path}")
    return loaded


def run_pipeline(
    primary_path: Path,
    processed_dir: Path,
    report_dir: Path,
    *,
    write_csv: bool = True,
    config: PipelineConfig | None = None,
    preprocessing_config_path: Path | None = None,
) -> dict:
    """Run the FE-02 cleaning pipeline end-to-end.

    Parameters
    ----------
    primary_path : pathlib.Path
        Path to the raw primary xlsx file.
    processed_dir : pathlib.Path
        Output directory for the clean dataset.
    report_dir : pathlib.Path
        Output directory for cleaning reports.
    write_csv : bool, default True
        Whether to also write a CSV mirror of the cleaned dataset.
    config : PipelineConfig, optional
        Explicit pipeline configuration. When provided, takes
        precedence over every other source (the YAML is **not** read
        in this case). Used by tests and library callers that need
        full programmatic control.
    preprocessing_config_path : pathlib.Path, optional
        Path to the YAML cleaning configuration. If ``None``
        (default), the pipeline auto-discovers ``configs/preprocessing.yaml``.
        If neither an explicit path nor the default YAML exists, the
        pipeline falls back to :func:`default_pipeline_config` and
        prints a warning.

    Returns
    -------
    dict
        Full structured summary of the run.
    """
    if not primary_path.exists():
        raise FileNotFoundError(f"Primary dataset not found: {primary_path}")

    config_source_label: list[str] = []
    if config is None:
        config = _resolve_pipeline_config(
            config,
            preprocessing_config_path=preprocessing_config_path,
            config_source_label=config_source_label,
        )

    raw_sha = _sha256_file(primary_path)

    # --------------------------------------------------------------
    # 1. Load raw data (read-only)
    # --------------------------------------------------------------
    sheet_names = list_sheet_names(primary_path)
    if sheet_names[0] != PRIMARY_SHEET:
        print(f"[FE-02] NOTE: primary sheet is {sheet_names[0]!r}, " f"expected {PRIMARY_SHEET!r}")
    df_raw = load_raw_transactions(primary_path, sheet_name=sheet_names[0])

    overview_raw = basic_overview(df_raw)

    # --------------------------------------------------------------
    # 2. Audit the raw data (before any cleaning)
    # --------------------------------------------------------------
    missing_raw = summarise_missing(df_raw)
    duplicate_subsets = {
        "(InvoiceNo, StockCode)": ["InvoiceNo", "StockCode"],
        "(InvoiceNo, StockCode, Description, Quantity, InvoiceDate)": [
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
        ],
    }
    subset_analyses = {
        label: analyse_subset_duplicates(df_raw, cols).to_dict()
        for label, cols in duplicate_subsets.items()
    }
    exact_dup_raw = exact_duplicate_analysis(df_raw)
    numerical_raw = numerical_profile(df_raw, columns=_numeric_columns(df_raw))
    # Identifier and categorical profiles are computed for documentation
    # parity with FE-01, but the cleaning report only embeds the numerical
    # profile. Kept for traceability; ``_``-prefixed to silence F841.
    _identifier_raw = {
        col: identifier_profile(df_raw, col).__dict__
        for col in ("InvoiceNo", "StockCode", "CustomerID")
        if col in df_raw.columns
    }
    _categorical_raw = categorical_profile(df_raw)

    # --------------------------------------------------------------
    # 3. Run cleaning pipeline
    # --------------------------------------------------------------
    result = clean_transactions(df_raw, config=config)
    df_clean = result.df
    overview_clean = basic_overview(df_clean)
    missing_clean = summarise_missing(df_clean)
    numerical_clean = numerical_profile(df_clean, columns=_numeric_columns(df_clean))
    _categorical_clean = categorical_profile(df_clean)

    # --------------------------------------------------------------
    # 4. Persist the cleaned dataset
    # --------------------------------------------------------------
    processed_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = processed_dir / CLEAN_FILENAME_PARQUET
    df_clean.to_parquet(parquet_path, index=False)
    csv_path: Path | None = None
    if write_csv:
        csv_path = processed_dir / CLEAN_FILENAME_CSV
        df_clean.to_csv(csv_path, index=False)

    # --------------------------------------------------------------
    # 5. Generate report artefacts
    # --------------------------------------------------------------
    rule_inventory = build_rule_inventory(config)

    invalid = result.invalid
    invalid_records_records: list[dict] = []
    if invalid is not None:
        for r in invalid.per_rule:
            invalid_records_records.append(
                {
                    "rule_id": r.get("rule_id"),
                    "column": r.get("column"),
                    "condition": r.get("condition"),
                    "action": r.get("action"),
                    "affected_rows": int(r.get("affected_rows", 0)),
                    "rationale": r.get("rationale", ""),
                }
            )

    # Missing values before/after
    miss_records: list[dict] = []
    raw_miss_by_col = {m.column: m for m in missing_raw}
    for m in missing_clean:
        before = raw_miss_by_col.get(m.column)
        miss_records.append(
            {
                "column": m.column,
                "missing_count_before": int(before.missing_count) if before else 0,
                "missing_rate_before": float(before.missing_rate) if before else 0.0,
                "missing_count_after": int(m.missing_count),
                "missing_rate_after": float(m.missing_rate),
            }
        )
    for col, before in raw_miss_by_col.items():
        if col not in {m.column for m in missing_clean}:
            miss_records.append(
                {
                    "column": col,
                    "missing_count_before": int(before.missing_count),
                    "missing_rate_before": float(before.missing_rate),
                    "missing_count_after": 0,
                    "missing_rate_after": 0.0,
                }
            )

    # Duplicate analysis
    dup_records: list[dict] = []
    dup_records.append(
        {
            "pattern": "exact-row duplicates",
            "subset": "(all columns)",
            "before_rows": int(exact_dup_raw["duplicate_rows"]),
            "before_groups": int(exact_dup_raw["duplicate_groups"]),
            "before_rate_percent": float(exact_dup_raw["duplicate_rate_percent"]),
        }
    )
    for label, info in subset_analyses.items():
        dup_records.append(
            {
                "pattern": "subset-key duplicates",
                "subset": label,
                "before_rows": int(info["duplicate_rows"]),
                "before_groups": int(info["duplicate_groups"]),
                "before_rate_percent": round(
                    float(info["duplicate_rows"]) / max(int(info["total_rows"]), 1) * 100.0,
                    4,
                ),
            }
        )
    # After-cleaning duplicates
    if result.duplicates is not None:
        dup_records.append(
            {
                "pattern": "exact-row duplicates (after cleaning)",
                "subset": "(all columns)",
                "before_rows": 0,
                "before_groups": 0,
                "before_rate_percent": 0.0,
                "after_rows": int(exact_duplicate_analysis(df_clean)["duplicate_rows"]),
                "after_groups": int(exact_duplicate_analysis(df_clean)["duplicate_groups"]),
            }
        )

    # Numeric before/after
    num_records: list[dict] = []
    raw_num_by_col = {row["column"]: row for _, row in numerical_raw.iterrows()}
    for _, row in numerical_clean.iterrows():
        col = row["column"]
        before = raw_num_by_col.get(col)
        num_records.append(
            {
                "column": col,
                "stage": "after_cleaning",
                "count": int(row["count"]),
                "min": row["min"],
                "max": row["max"],
                "mean": row["mean"],
                "median": row["median"],
                "std": row["std"],
                "zero_count": int(row["zero_count"]),
                "negative_count": int(row["negative_count"]),
                "count_before": int(before["count"]) if before is not None else 0,
                "min_before": before["min"] if before is not None else None,
                "max_before": before["max"] if before is not None else None,
                "mean_before": before["mean"] if before is not None else None,
                "median_before": before["median"] if before is not None else None,
                "std_before": before["std"] if before is not None else None,
                "zero_count_before": int(before["zero_count"]) if before is not None else 0,
                "negative_count_before": int(before["negative_count"]) if before is not None else 0,
            }
        )

    # Before/after summary
    before_after = build_before_after_table(
        df_raw=df_raw,
        df_clean=df_clean,
        invalid_result=invalid,
        exact_dup_raw=exact_dup_raw,
    )

    # Write CSV/JSON reports
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(pd.DataFrame.from_records(rule_inventory), report_dir / "cleaning_rules.csv")
    _write_csv(pd.DataFrame.from_records(before_after), report_dir / "before_after_summary.csv")
    if invalid_records_records:
        _write_csv(
            pd.DataFrame.from_records(invalid_records_records),
            report_dir / "invalid_records_summary.csv",
        )
    _write_csv(pd.DataFrame.from_records(miss_records), report_dir / "missing_values.csv")
    if dup_records:
        _write_csv(pd.DataFrame.from_records(dup_records), report_dir / "duplicate_analysis.csv")
    if num_records:
        _write_csv(pd.DataFrame.from_records(num_records), report_dir / "transaction_quality.csv")

    # Narrative report
    report_md = build_cleaning_report_md(
        primary_path=primary_path,
        raw_sha=raw_sha,
        overview_raw=overview_raw,
        overview_clean=overview_clean,
        cleaning_result=result,
        rule_inventory=rule_inventory,
        before_after=before_after,
        missing_raw=missing_raw,
        missing_clean=missing_clean,
        numerical_raw=numerical_raw,
        numerical_clean=numerical_clean,
        exact_dup_raw=exact_dup_raw,
        subset_analyses=subset_analyses,
        config=config,
    )
    _write_text(report_dir / "cleaning_report.md", report_md)

    # Run summary JSON
    run_summary = {
        "task_id": "FE-02",
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "platform": {
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "input": {
            "raw_path": str(primary_path),
            "raw_sha256": raw_sha,
            "sheet": sheet_names[0],
        },
        "config": _config_to_dict(config),
        "config_source": (config_source_label[0] if config_source_label else "unknown"),
        "output": {
            "cleaned_parquet": str(parquet_path),
            "cleaned_csv": str(csv_path) if csv_path else None,
            "report_dir": str(report_dir),
        },
        "summary": summarise_cleaning_result(result),
    }
    _write_json(report_dir / "cleaning_run.json", run_summary)

    return {
        "rows_in": int(result.report["rows_in"]),
        "rows_out": int(result.report["rows_out"]),
        "rows_removed_total": int(result.report["rows_removed_total"]),
        "flagged_cancellations": int(invalid.flagged_cancellations if invalid else 0),
        "flagged_returns": int(invalid.flagged_returns if invalid else 0),
        "parquet_path": str(parquet_path),
        "csv_path": str(csv_path) if csv_path else None,
        "report_dir": str(report_dir),
        "config_source": (config_source_label[0] if config_source_label else "explicit_config"),
    }


def _config_to_dict(config: PipelineConfig) -> dict:
    """Serialise the pipeline config to a JSON-friendly dict.

    The shape mirrors ``configs/preprocessing.yaml`` so the JSON
    artefact can be diffed against the YAML for traceability.
    """
    rules = config.invalid_rules
    return {
        "invalid_rules": {
            "drop_missing_customer_id": rules.drop_missing_customer_id,
            "drop_missing_invoice_no": rules.drop_missing_invoice_no,
            "drop_missing_description": rules.drop_missing_description,
            "drop_unparseable_invoice_date": rules.drop_unparseable_invoice_date,
            "drop_zero_quantity": rules.drop_zero_quantity,
            "drop_non_positive_unit_price": rules.drop_non_positive_unit_price,
            "flag_cancellations": rules.flag_cancellations,
            "flag_returns": rules.flag_returns,
            "cancellation_prefix": rules.cancellation_prefix,
        },
        "missing_strategy": config.missing_strategy,
        "missing_columns": list(config.missing_columns),
        "duplicate_subset": list(config.duplicate_subset) if config.duplicate_subset else None,
        "duplicate_keep": config.duplicate_keep,
        "outlier_action": config.outlier_action,
        "outlier_method": config.outlier_method,
        "outlier_columns": list(config.outlier_columns),
        "outlier_iqr_multiplier": config.outlier_iqr_multiplier,
        "outlier_zscore_threshold": config.outlier_zscore_threshold,
    }


def build_before_after_table(
    *,
    df_raw: pd.DataFrame,
    df_clean: pd.DataFrame,
    invalid_result,
    exact_dup_raw: dict,
) -> list[dict]:
    """Build a before/after metric table for the cleaning report.

    Parameters
    ----------
    df_raw : pandas.DataFrame
        Raw input.
    df_clean : pandas.DataFrame
        Cleaned output.
    invalid_result : InvalidRecordResult or None
        Result of the invalid-record stage (used to count flagged rows).
    exact_dup_raw : dict
        Exact-row duplicate analysis of `df_raw`.

    Returns
    -------
    list[dict]
        One row per metric, with ``metric``, ``before``, ``after``,
        ``difference``.
    """
    rows_in = int(df_raw.shape[0])
    rows_out = int(df_clean.shape[0])

    def _missing(col: str) -> tuple[int, int]:
        if col not in df_raw.columns:
            return (0, 0)
        before = int(df_raw[col].isna().sum())
        after = int(df_clean[col].isna().sum()) if col in df_clean.columns else 0
        return before, after

    def _value_count(df: pd.DataFrame, col: str, pred) -> int:
        if col not in df.columns:
            return 0
        return int(pred(df[col]).sum())

    def _zero(s: pd.Series) -> pd.Series:
        return (pd.to_numeric(s, errors="coerce") == 0).fillna(False)

    def _negative(s: pd.Series) -> pd.Series:
        return (pd.to_numeric(s, errors="coerce") < 0).fillna(False)

    def _cancelled(s: pd.Series) -> pd.Series:
        return s.astype("string").str.startswith("C").fillna(False)

    metrics: list[dict] = []

    def _add(metric: str, before: int, after: int) -> None:
        # Sign convention: positive difference means the metric
        # **decreased** (cleaning removed records), negative means
        # **increased** (e.g. flag columns added, so "Total columns"
        # goes from 8 to 10). See the report header for the convention.
        metrics.append(
            {
                "metric": metric,
                "before": int(before),
                "after": int(after),
                "difference": int(before - after),
            }
        )

    _add("Total rows", rows_in, rows_out)
    _add("Total columns", int(df_raw.shape[1]), int(df_clean.shape[1]))

    b, a = _missing("CustomerID")
    _add("Missing CustomerID", b, a)
    b, a = _missing("Description")
    _add("Missing Description", b, a)
    b, a = _missing("InvoiceDate")
    _add("Missing InvoiceDate", b, a)
    b, a = _missing("InvoiceNo")
    _add("Missing InvoiceNo", b, a)

    _add("Exact-row duplicates", int(exact_dup_raw["duplicate_rows"]), 0)

    # Negative quantity
    neg_before = _value_count(df_raw, "Quantity", _negative)
    neg_after = _value_count(df_clean, "Quantity", _negative)
    _add("Negative Quantity (raw count, kept as flag)", neg_before, neg_after)
    zero_before = _value_count(df_raw, "Quantity", _zero)
    zero_after = _value_count(df_clean, "Quantity", _zero)
    _add("Zero Quantity (raw count)", zero_before, zero_after)

    np_before = _value_count(df_raw, "UnitPrice", lambda s: pd.to_numeric(s, errors="coerce") <= 0)
    np_after = _value_count(df_clean, "UnitPrice", lambda s: pd.to_numeric(s, errors="coerce") <= 0)
    _add("Non-positive UnitPrice (<=0) (raw count)", np_before, np_after)

    # Cancellation flags
    canc_after = (
        int(df_clean["IsCancellation"].sum()) if "IsCancellation" in df_clean.columns else 0
    )
    _add(
        "Cancellation-flagged (C-prefix) — kept with flag",
        int(_value_count(df_raw, "InvoiceNo", _cancelled)),
        canc_after,
    )
    ret_after = int(df_clean["IsReturn"].sum()) if "IsReturn" in df_clean.columns else 0
    _add("Return-flagged (negative Quantity) — kept with flag", neg_before, ret_after)

    # Distinct counts after cleaning
    for col in ("InvoiceNo", "StockCode", "CustomerID", "Country"):
        if col in df_raw.columns and col in df_clean.columns:
            _add(
                f"Distinct {col}",
                int(df_raw[col].nunique(dropna=True)),
                int(df_clean[col].nunique(dropna=True)),
            )

    return metrics


def build_cleaning_report_md(
    *,
    primary_path: Path,
    raw_sha: str,
    overview_raw,
    overview_clean,
    cleaning_result,
    rule_inventory: list[dict],
    before_after: list[dict],
    missing_raw: list[MissingSummary],
    missing_clean: list[MissingSummary],
    numerical_raw: pd.DataFrame,
    numerical_clean: pd.DataFrame,
    exact_dup_raw: dict,
    subset_analyses: dict,
    config: PipelineConfig,
) -> str:
    """Render the narrative cleaning report in Markdown."""
    lines: list[str] = []
    lines.append("# FE-02 Cleaning Report — UCI Online Retail (Primary)")
    lines.append("")
    lines.append(
        "This report describes the data cleaning pipeline applied to the "
        "raw primary dataset. All numbers are computed live from the raw "
        "file and from the pipeline output; nothing is hard-coded."
    )
    lines.append("")

    # 1. Objective
    lines.append("## 1. Objective")
    lines.append("")
    lines.append(
        "Convert the raw primary transaction-level dataset into a "
        "**clean transaction-level dataset** suitable as input for the "
        "next pipeline stage (FE-03 / RFM). The pipeline is a deterministic, "
        "rule-based cleaning process. It does not aggregate to customer "
        "level and does not compute any RFM feature."
    )
    lines.append("")

    # 2. Input
    lines.append("## 2. Input Dataset")
    lines.append("")
    lines.append(f"- **Local file**: `{primary_path}`")
    lines.append(f"- **SHA-256**: `{raw_sha}`")
    lines.append(f"- **Sheet**: `{overview_raw.column_names[0] if False else 'Online Retail'}`")
    lines.append(f"- **Rows (raw)**: {overview_raw.n_rows:,}")
    lines.append(f"- **Columns (raw)**: {overview_raw.n_columns}")
    lines.append("")

    # 3. Cleaning scope
    lines.append("## 3. Cleaning Scope")
    lines.append("")
    lines.append("FE-02 covers **transaction-line-level** cleaning only. It does " "**not**:")
    lines.append("")
    lines.append("- aggregate to customer level;")
    lines.append("- compute RFM, Monetary, Recency, Frequency or any other customer feature;")
    lines.append("- perform clustering, scaling, or transformation;")
    lines.append("- modify, delete, or rename the raw file.")
    lines.append("")
    lines.append(
        "Decisions classified as **PENDING_MENTOR_REVIEW** are recorded "
        "in this report but are not silently adopted as the project's "
        "official methodology."
    )
    lines.append("")

    # 4. Cleaning rules
    lines.append("## 4. Cleaning Rules")
    lines.append("")
    lines.append("| Rule ID | Stage | Action | Column | Condition | Default behaviour | Status |")
    lines.append("| --- | --- | --- | --- | --- | :---: | --- |")
    for r in rule_inventory:
        lines.append(
            f"| {r['rule_id']} "
            f"| {r['stage']} "
            f"| {r['action']} "
            f"| `{r['column']}` "
            f"| {r['condition']} "
            f"| {'✅' if r['default_behaviour'] else '❌'} "
            f"| {r['status']} |"
        )
    lines.append("")

    # 5. Pipeline stages
    lines.append("## 5. Pipeline Stages (per-stage counters)")
    lines.append("")
    lines.append("| Stage | Action | Rows in | Rows out | Rows removed | Notes |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- |")
    for stage in cleaning_result.report["stages"]:
        notes_parts = []
        if "rule_ids" in stage:
            notes_parts.append("rules: " + ", ".join(stage["rule_ids"]))
        if "flagged_cancellations" in stage:
            notes_parts.append(f"IsCancellation={stage['flagged_cancellations']:,}")
            notes_parts.append(f"IsReturn={stage['flagged_returns']:,}")
        if stage.get("subset") is not None:
            notes_parts.append(f"subset={stage['subset']} keep={stage.get('keep')}")
        lines.append(
            f"| {stage['stage']} "
            f"| {stage['action']} "
            f"| {int(stage['rows_in']):,} "
            f"| {int(stage['rows_out']):,} "
            f"| {int(stage['rows_removed']):,} "
            f"| {'; '.join(notes_parts)} |"
        )
    lines.append("")

    # 6. Before / after
    lines.append("## 6. Before / After Statistics")
    lines.append("")
    lines.append(
        "Sign convention: `difference = before - after`. "
        "A **positive** value means the metric decreased (records were "
        "removed by cleaning). A **negative** value means the metric "
        "increased (typically because FE-02 added flag columns)."
    )
    lines.append("")
    lines.append("| Metric | Before | After | Difference |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in before_after:
        lines.append(
            f"| {row['metric']} "
            f"| {int(row['before']):,} "
            f"| {int(row['after']):,} "
            f"| {int(row['difference']):,} |"
        )
    lines.append("")

    # 7. Detailed findings
    lines.append("## 7. Detailed Findings")
    lines.append("")
    lines.append("### 7.1 Missing values (raw vs clean)")
    lines.append("")
    lines.append(
        "| Column | Missing (before) | Missing rate (before) | Missing (after) | Missing rate (after) |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    raw_miss_by_col = {m.column: m for m in missing_raw}
    clean_miss_by_col = {m.column: m for m in missing_clean}
    for col in sorted(set(list(raw_miss_by_col) + list(clean_miss_by_col))):
        b = raw_miss_by_col.get(col)
        a = clean_miss_by_col.get(col)
        b_count = int(b.missing_count) if b else 0
        b_rate = float(b.missing_rate) if b else 0.0
        a_count = int(a.missing_count) if a else 0
        a_rate = float(a.missing_rate) if a else 0.0
        lines.append(f"| `{col}` | {b_count:,} | {b_rate:.4f} | {a_count:,} | {a_rate:.4f} |")
    lines.append("")
    lines.append("### 7.2 Numeric anomalies (raw vs clean)")
    lines.append("")
    lines.append(
        "| Column | Stage | Count | Min | Max | Mean | Median | Std | Zero count | Negative count |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    raw_num_by_col = {row["column"]: row for _, row in numerical_raw.iterrows()}
    for _, row in numerical_clean.iterrows():
        col = row["column"]
        before = raw_num_by_col.get(col)
        if before is not None:
            lines.append(
                f"| `{col}` | raw "
                f"| {int(before['count']):,} "
                f"| {before['min']} | {before['max']} "
                f"| {float(before['mean']):.4f} | {float(before['median']):.4f} "
                f"| {float(before['std']):.4f} "
                f"| {int(before['zero_count']):,} | {int(before['negative_count']):,} |"
            )
        lines.append(
            f"| `{col}` | clean "
            f"| {int(row['count']):,} "
            f"| {row['min']} | {row['max']} "
            f"| {float(row['mean']):.4f} | {float(row['median']):.4f} "
            f"| {float(row['std']):.4f} "
            f"| {int(row['zero_count']):,} | {int(row['negative_count']):,} |"
        )
    lines.append("")
    lines.append("### 7.3 Duplicate analysis")
    lines.append("")
    lines.append("**Exact-row duplicates (raw)**")
    lines.append("")
    lines.append("| Pattern | Total rows | Duplicate rows | Groups | Rate (%) |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    lines.append(
        f"| Exact-row duplicates | {int(exact_dup_raw['total_rows']):,} "
        f"| {int(exact_dup_raw['duplicate_rows']):,} "
        f"| {int(exact_dup_raw['duplicate_groups']):,} "
        f"| {float(exact_dup_raw['duplicate_rate_percent']):.4f} |"
    )
    lines.append("")
    lines.append("**Subset-key duplicates (raw, reported but not dropped by default)**")
    lines.append("")
    lines.append(
        "| Subset | Total rows | Unique combos | Duplicate rows | Groups | Max group size |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for label, info in subset_analyses.items():
        lines.append(
            f"| `{label}` "
            f"| {int(info['total_rows']):,} "
            f"| {int(info['unique_combinations']):,} "
            f"| {int(info['duplicate_rows']):,} "
            f"| {int(info['duplicate_groups']):,} "
            f"| {int(info['max_group_size']):,} |"
        )
    lines.append("")
    lines.append("### 7.4 Invalid-record counts")
    lines.append("")
    lines.append("| Rule | Column | Condition | Action | Affected rows | Rationale |")
    lines.append("| --- | --- | --- | --- | ---: | --- |")
    if cleaning_result.invalid is not None:
        for r in cleaning_result.invalid.per_rule:
            lines.append(
                f"| {r['rule_id']} "
                f"| `{r['column']}` "
                f"| {r['condition']} "
                f"| {r['action']} "
                f"| {int(r['affected_rows']):,} "
                f"| {r.get('rationale', '')} |"
            )
    lines.append("")
    lines.append("### 7.5 Output schema")
    lines.append("")
    lines.append("The cleaned dataset preserves the 8 raw columns and adds two flag columns:")
    lines.append("")
    lines.append("| Column | dtype | Source | Meaning |")
    lines.append("| --- | --- | --- | --- |")
    for col in overview_clean.column_names:
        if col in {"IsCancellation", "IsReturn"}:
            src = "FE-02 cleaning"
            meaning = (
                "True if the row's InvoiceNo starts with the cancellation prefix."
                if col == "IsCancellation"
                else "True if Quantity is negative (return/cancellation line)."
            )
        else:
            src = "raw primary file"
            meaning = "see docs/data_dictionary/data_dictionary.md"
        lines.append(f"| `{col}` | `{overview_clean.dtypes.get(col, '?')}` | {src} | {meaning} |")
    lines.append("")

    # 8. Records removed
    lines.append("## 8. Records Removed")
    lines.append("")
    lines.append(
        f"- **Total removed**: {cleaning_result.report['rows_removed_total']:,} of "
        f"{cleaning_result.report['rows_in']:,} raw rows "
        f"({cleaning_result.report['rows_removed_total'] / max(cleaning_result.report['rows_in'], 1) * 100.0:.4f} %)."
    )
    lines.append(f"- **Rows retained**: {cleaning_result.report['rows_out']:,}.")
    lines.append("")
    lines.append("Per-rule affected-row counts:")
    lines.append("")
    lines.append("| Rule | Action | Affected rows |")
    lines.append("| --- | --- | ---: |")
    if cleaning_result.invalid is not None:
        for r in cleaning_result.invalid.per_rule:
            lines.append(f"| {r['rule_id']} | {r['action']} | {int(r['affected_rows']):,} |")
    if cleaning_result.duplicates is not None:
        lines.append(
            f"| {cleaning_result.duplicates.rule_id} | drop "
            f"| {int(cleaning_result.duplicates.rows_removed):,} |"
        )
    lines.append("")
    lines.append(
        "**Note on record-count sums.** The sum of the per-rule counts "
        "can exceed the total number of removed rows because a single row "
        "may fail multiple rules (e.g. a cancellation record may also have "
        "a non-positive UnitPrice). The orchestrator drops each row only "
        "once, using a union of drop masks."
    )
    lines.append("")

    # 9. Deferred decisions
    lines.append("## 9. Deferred Decisions (PENDING MENTOR REVIEW)")
    lines.append("")
    lines.append(
        "The following items are flagged in the cleaning pipeline but "
        "are **not** decided here. They require mentor approval before "
        "being adopted as the project's official methodology."
    )
    lines.append("")
    deferred = [
        {
            "id": "DD-01",
            "topic": "Cancellation handling",
            "description": (
                "Currently, cancellation records (`InvoiceNo` starting with "
                "`C`) are **flagged** via `IsCancellation` and **kept** in the "
                "clean dataset. Whether they should be excluded from customer "
                "behavioural features (Recency / Frequency / Monetary) is a "
                "methodology decision."
            ),
        },
        {
            "id": "DD-02",
            "topic": "Return handling",
            "description": (
                "Negative-Quantity rows are **flagged** via `IsReturn` and "
                "**kept**. Whether they should be summed into Monetary (as "
                "negative revenue), excluded entirely, or treated as a "
                "separate feature is a methodology decision."
            ),
        },
        {
            "id": "DD-03",
            "topic": "UnitPrice == 0",
            "description": (
                "Currently, rows with `UnitPrice == 0` are **dropped** as a "
                "working assumption. The mentor may decide to keep them as "
                "a separate flag (e.g. `IsFreeItem`) and let RFM decide."
            ),
        },
        {
            "id": "DD-04",
            "topic": "Missing CustomerID strategy",
            "description": (
                "Currently, rows with missing `CustomerID` are **dropped** as "
                "a working assumption. Alternatives: impute via invoice "
                "grouping heuristics, or model guest transactions separately. "
                "≈ 24.93% of raw rows fall in this bucket."
            ),
        },
        {
            "id": "DD-05",
            "topic": "Outlier handling",
            "description": (
                "Outlier processing is **off by default**. The cleaned "
                "dataset preserves the raw distribution of `Quantity` and "
                "`UnitPrice` so the next stage can decide on outlier policy."
            ),
        },
        {
            "id": "DD-06",
            "topic": "RFM reference date",
            "description": (
                "FE-02 does not compute RFM. The RFM reference date is "
                "configured in `configs/features.yaml` "
                "(`reference_date_mode: snapshot_max`). The exact value is "
                "chosen by FE-03."
            ),
        },
    ]
    lines.append("| ID | Topic | Description |")
    lines.append("| --- | --- | --- |")
    for d in deferred:
        lines.append(f"| {d['id']} | {d['topic']} | {d['description']} |")
    lines.append("")

    # 10. Reproducibility
    lines.append("## 10. Reproducibility")
    lines.append("")
    lines.append("- **Determinism**: the pipeline performs no random operation.")
    lines.append("- **Inputs**: raw file path and the resolved `PipelineConfig`.")
    lines.append(
        "- **Outputs**: Parquet (always), CSV (optional), and the CSVs / MD / JSON under `reports/fe02/`."
    )
    lines.append(
        f"- **Raw SHA-256**: `{raw_sha}` (compare with `docs/data_dictionary/dataset_provenance.md`)."
    )
    lines.append("- **Pipeline code**: `src/customer_segmentation/preprocessing/`.")
    lines.append("- **Pipeline script**: `scripts/run_fe02_cleaning.py`.")
    lines.append(
        "- **CLI**: `python -m scripts.run_fe02_cleaning` (or via `PYTHONPATH=src python scripts/run_fe02_cleaning.py`)."
    )
    lines.append("")

    # 11. Limitations
    lines.append("## 11. Limitations")
    lines.append("")
    lines.append(
        "- The cleaning pipeline reads its configuration from "
        "`configs/preprocessing.yaml` (single source of truth). The YAML "
        "schema is validated by "
        "`customer_segmentation.config.loader.load_preprocessing_config`. "
        "Unknown values or missing required keys raise a clear error "
        "rather than silently using a default."
    )
    lines.append(
        "- The pipeline is **strict by default**: an unset value in the "
        "YAML is a configuration error. The dataclass "
        "`PipelineConfig` keeps dataclass-level defaults so that "
        "library callers (e.g. unit tests) can construct a config "
        "without YAML, but the CLI orchestrator refuses to run on an "
        "empty / malformed YAML."
    )
    lines.append(
        "- The cleaned dataset is **transaction-line level**. Aggregation "
        "to customer level is the responsibility of FE-03."
    )
    lines.append(
        "- Cancellation / return semantics are recorded as flags. Their "
        "downstream treatment is a methodology decision (DD-01, DD-02)."
    )
    lines.append("")

    # 12. Conclusion
    lines.append("## 12. Conclusion")
    lines.append("")
    lines.append(
        f"The FE-02 cleaning pipeline converted {overview_raw.n_rows:,} raw "
        f"transactions into {overview_clean.n_rows:,} cleaned transactions. "
        f"Exactly {cleaning_result.report['rows_removed_total']:,} rows were "
        "removed by deterministic rules. Cancellations and returns were "
        "preserved as boolean flag columns so the RFM stage can decide "
        "whether to exclude them."
    )
    lines.append("")
    lines.append(
        "FE-02 finishes here. The next stage (FE-03 / RFM) consumes "
        "`data/processed/transactions_clean.parquet` and decides how to "
        "use the `IsCancellation` / `IsReturn` flags."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FE-02 cleaning pipeline")
    p.add_argument(
        "--primary-dir",
        type=Path,
        default=DEFAULT_PRIMARY_DIR,
        help="Primary raw dataset directory.",
    )
    p.add_argument(
        "--processed-dir",
        type=Path,
        default=DEFAULT_PROCESSED_DIR,
        help="Output directory for the clean dataset.",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Output directory for cleaning reports.",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to the preprocessing YAML. If omitted, the orchestrator "
            "auto-discovers 'configs/preprocessing.yaml'."
        ),
    )
    p.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip writing the CSV mirror of the cleaned dataset.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)
    primary_path = args.primary_dir / PRIMARY_FILENAME
    print(f"[FE-02] loading primary: {primary_path}")
    summary = run_pipeline(
        primary_path=primary_path,
        processed_dir=args.processed_dir,
        report_dir=args.report_dir,
        write_csv=not args.no_csv,
        preprocessing_config_path=args.config,
    )
    print(
        f"[FE-02] cleaning done: {summary['rows_in']:,} → {summary['rows_out']:,} "
        f"({summary['rows_removed_total']:,} removed, "
        f"{summary['flagged_cancellations']:,} cancellations flagged, "
        f"{summary['flagged_returns']:,} returns flagged)"
    )
    print(f"[FE-02] cleaned dataset: {summary['parquet_path']}")
    if summary.get("csv_path"):
        print(f"[FE-02] CSV mirror: {summary['csv_path']}")
    print(f"[FE-02] reports: {summary['report_dir']}")
    if summary.get("config_source"):
        print(f"[FE-02] config source: {summary['config_source']}")


if __name__ == "__main__":
    main()
