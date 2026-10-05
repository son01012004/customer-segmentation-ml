"""FE-01 orchestrator: run raw dataset audit and emit CSV/MD outputs.

Stage: 01_dataset_audit (FE-01)

Usage (from the repository root):

    python -m scripts.run_fe01_audit

Outputs
-------
Written under ``reports/fe01/``:

- ``primary_overview.json``           — top-level structural summary
- ``primary_schema.csv``               — machine-readable schema
- ``primary_missing.csv``             — per-column missing-value profile
- ``primary_numerical.csv``           — per-numeric-column stats
- ``primary_categorical.csv``         — per-categorical-column stats
- ``primary_country_top.csv``         — top-N Country frequencies
- ``primary_date_range.txt``          — InvoiceDate min/max
- ``primary_identifiers.json``        — identifier uniqueness summary
- ``primary_duplicates.json``         — duplicate summary (exact + keys)
- ``primary_data_quality_observations.md``
- ``backup_overview.json``            — backup comparison summary
- ``backup_schema.csv``               — backup machine-readable schema
- ``primary_vs_backup.csv``           — schema comparison table

Notes
-----
- This script only **reads** the raw data; it never writes back to it.
- It never aggregates rows to customer level.
- All numbers are derived live from the raw files so they cannot drift
  from the underlying data.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

# Allow running as a plain script (``python scripts/run_fe01_audit.py``)
# without installing the package, while still importing ``customer_segmentation``.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from customer_segmentation.data.audit import (  # noqa: E402
    AuditSummary,
    basic_overview,
    categorical_profile,
    date_profile,
    duplicate_profile,
    frequency_table,
    identifier_profile,
    looks_like_cancellation_prefix,
    missing_profile,
    numerical_profile,
)
from customer_segmentation.data.loader import (  # noqa: E402
    list_sheet_names,
    load_raw_transactions,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


DEFAULT_PRIMARY_DIR = _REPO_ROOT / "data" / "raw" / "primary"
DEFAULT_BACKUP_DIR = _REPO_ROOT / "data" / "raw" / "backup"
DEFAULT_REPORT_DIR = _REPO_ROOT / "reports" / "fe01"

PRIMARY_FILENAME = "Online Retail.xlsx"
BACKUP_FILENAMES = ("online_retail_II.xlsx",)


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


# ---------------------------------------------------------------------------
# Per-dataset audit
# ---------------------------------------------------------------------------


def audit_primary(
    primary_path: Path,
    report_dir: Path,
    *,
    top_country_k: int = 15,
) -> dict:
    """Run the audit on the primary dataset and write outputs.

    Parameters
    ----------
    primary_path : pathlib.Path
        Path to the primary xlsx file.
    report_dir : pathlib.Path
        Output directory.
    top_country_k : int, default 15
        How many top countries to keep in the frequency CSV.

    Returns
    -------
    dict
        Structured summary suitable for further programmatic use.
    """
    if not primary_path.exists():
        raise FileNotFoundError(f"Primary dataset not found: {primary_path}")

    # 1. Discover sheets (informational; primary has only one)
    sheet_names = list_sheet_names(primary_path)

    # 2. Load full primary
    df = load_raw_transactions(primary_path, sheet_name=sheet_names[0])

    # 3. Top-level overview
    overview = basic_overview(df)
    _write_json(
        report_dir / "primary_overview.json",
        {
            "sheet_names": sheet_names,
            "loaded_sheet": sheet_names[0],
            "n_rows": overview.n_rows,
            "n_columns": overview.n_columns,
            "column_names": list(overview.column_names),
            "dtypes": overview.dtypes,
            "memory_bytes": overview.memory_bytes,
        },
    )

    # 4. Schema CSV (one row per column, machine-readable)
    schema_records = []
    for col in overview.column_names:
        s = df[col]
        schema_records.append(
            {
                "column_name": col,
                "data_type": str(s.dtype),
                "role": "",  # filled later by data_dictionary.md author
                "nullable": bool(s.isna().any()),
                "unique_count": int(s.nunique(dropna=True)),
                "missing_count": int(s.isna().sum()),
                "missing_rate": round(float(s.isna().sum()) / max(len(df), 1) * 100.0, 4),
                "min_value": _series_min(s),
                "max_value": _series_max(s),
                "notes": "",
            }
        )
    _write_csv(pd.DataFrame.from_records(schema_records), report_dir / "primary_schema.csv")

    # 5. Missing profile
    miss = missing_profile(df)
    _write_csv(miss, report_dir / "primary_missing.csv")

    # 6. Numerical profile
    num = numerical_profile(df)
    _write_csv(num, report_dir / "primary_numerical.csv")

    # 7. Categorical profile
    cat = categorical_profile(df)
    _write_csv(cat, report_dir / "primary_categorical.csv")

    # 8. Country top-K
    if "Country" in df.columns:
        country_freq = frequency_table(df["Country"], top_k=top_country_k)
        _write_csv(country_freq, report_dir / "primary_country_top.csv")

    # 9. Date profile
    if "InvoiceDate" in df.columns:
        p = date_profile(df, "InvoiceDate")
        _write_text(
            report_dir / "primary_date_range.txt",
            f"InvoiceDate min: {p.min.isoformat() if p.min else 'N/A'}\n"
            f"InvoiceDate max: {p.max.isoformat() if p.max else 'N/A'}\n"
            f"Parsed: {p.parsed_count}/{p.total}\n"
            f"Unparsed: {p.unparsed_count}\n"
            f"Duplicate timestamps: {p.duplicate_timestamps}\n",
        )

    # 10. Identifier profiles
    id_columns = [c for c in ("InvoiceNo", "StockCode", "CustomerID") if c in df.columns]
    id_profiles = {}
    for col in id_columns:
        prof = identifier_profile(df, col)
        id_profiles[col] = asdict(prof)
    # Cancellation-prefix scan for InvoiceNo
    cancel_scan = {}
    if "InvoiceNo" in df.columns:
        cancel_scan = looks_like_cancellation_prefix(df["InvoiceNo"], prefix="C")
    _write_json(
        report_dir / "primary_identifiers.json",
        {"identifiers": id_profiles, "invoice_cancellation_scan": cancel_scan},
    )

    # 11. Duplicate profile
    dup_exact = duplicate_profile(df)
    dup_invoice = duplicate_profile(df, subset=["InvoiceNo", "StockCode"])
    dup_full_keys = duplicate_profile(
        df, subset=["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate"]
    )
    _write_json(
        report_dir / "primary_duplicates.json",
        {
            "exact_duplicate_rows": dup_exact.exact_duplicate_rows,
            "exact_duplicate_row_rate": dup_exact.exact_duplicate_row_rate,
            "by_invoice_stockcode": {
                "key_subset": list(dup_invoice.key_subset) if dup_invoice.key_subset else None,
                "key_duplicate_rows": dup_invoice.key_duplicate_rows,
                "key_unique_combinations": dup_invoice.key_unique_combinations,
            },
            "by_full_line_keys": {
                "key_subset": list(dup_full_keys.key_subset) if dup_full_keys.key_subset else None,
                "key_duplicate_rows": dup_full_keys.key_duplicate_rows,
                "key_unique_combinations": dup_full_keys.key_unique_combinations,
            },
        },
    )

    # 12. Data-quality observations MD
    dq_md = _build_dq_md(
        df,
        overview,
        num,
        miss,
        id_profiles,
        cancel_scan,
        dup_exact,
        dup_invoice,
    )
    _write_text(report_dir / "primary_data_quality_observations.md", dq_md)

    return {
        "n_rows": overview.n_rows,
        "n_columns": overview.n_columns,
        "sheet_names": sheet_names,
        "report_dir": str(report_dir),
    }


def _series_min(s: pd.Series):
    return _series_extreme(s, which="min")


def _series_max(s: pd.Series):
    return _series_extreme(s, which="max")


def _series_extreme(s: pd.Series, *, which: str) -> str | None:
    """Return the string representation of `s.min()`/`s.max()` for the schema CSV.

    Object-dtype columns may mix numeric and string values (e.g. ``InvoiceNo``
    has both ``536365`` and ``"C536379"``). For those columns,
    ``Series.min()`` raises ``TypeError`` and we return a textual label
    instead so the CSV cell is informative rather than blank.
    """
    try:
        non_na = s.dropna()
    except TypeError:
        return None
    if non_na.empty:
        return None
    try:
        extreme = non_na.min() if which == "min" else non_na.max()
    except TypeError:
        return "N/A (mixed types)"
    try:
        return str(extreme)
    except Exception:  # noqa: BLE001
        return "N/A"


# ---------------------------------------------------------------------------
# Backup (schema comparison only)
# ---------------------------------------------------------------------------


def audit_backup(backup_dir: Path, report_dir: Path) -> dict:
    """Audit the backup dataset at the schema-comparison level only.

    Reads each sheet independently and writes one row per sheet to the
    backup schema CSV. Intentionally lighter than the primary audit.
    """
    backup_file: Path | None = None
    for cand in BACKUP_FILENAMES:
        p = backup_dir / cand
        if p.exists():
            backup_file = p
            break
    if backup_file is None:
        raise FileNotFoundError(
            f"No backup file found in {backup_dir}; expected one of {BACKUP_FILENAMES}."
        )
    sheet_names = list_sheet_names(backup_file)
    schema_records: list[dict] = []
    overview_records: list[dict] = []
    per_sheet_min_max: dict[str, dict] = {}
    for sheet in sheet_names:
        df = load_raw_transactions(backup_file, sheet_name=sheet)
        ov = basic_overview(df)
        overview_records.append(
            {
                "sheet": sheet,
                "n_rows": ov.n_rows,
                "n_columns": ov.n_columns,
                "column_names": list(ov.column_names),
            }
        )
        for col in ov.column_names:
            s = df[col]
            schema_records.append(
                {
                    "sheet": sheet,
                    "column_name": col,
                    "data_type": str(s.dtype),
                    "nullable": bool(s.isna().any()),
                    "unique_count": int(s.nunique(dropna=True)),
                    "missing_count": int(s.isna().sum()),
                    "missing_rate": round(float(s.isna().sum()) / max(len(df), 1) * 100.0, 4),
                }
            )
        # Date range per sheet
        date_col = _guess_date_column(df)
        if date_col is not None:
            p = date_profile(df, date_col)
            per_sheet_min_max[sheet] = {
                "date_column": date_col,
                "min": p.min.isoformat() if p.min else None,
                "max": p.max.isoformat() if p.max else None,
                "parsed": p.parsed_count,
                "unparsed": p.unparsed_count,
                "total": p.total,
            }
    _write_csv(pd.DataFrame.from_records(schema_records), report_dir / "backup_schema.csv")
    _write_json(
        report_dir / "backup_overview.json",
        {
            "backup_file": backup_file.name,
            "sheets": overview_records,
            "date_ranges": per_sheet_min_max,
        },
    )
    return {
        "backup_file": backup_file.name,
        "sheets": overview_records,
        "date_ranges": per_sheet_min_max,
    }


def _guess_date_column(df: pd.DataFrame) -> str | None:
    """Return the first datetime-like column name, or None."""
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    return None


# ---------------------------------------------------------------------------
# Primary vs Backup comparison
# ---------------------------------------------------------------------------


def compare_primary_vs_backup(primary_csv: Path, backup_csv: Path, out_csv: Path) -> dict:
    """Build a column-level primary-vs-backup comparison table.

    Reads ``reports/fe01/primary_schema.csv`` and
    ``reports/fe01/backup_schema.csv`` (both produced by this script)
    and emits a wide comparison CSV.
    """
    primary = pd.read_csv(primary_csv)
    backup = pd.read_csv(backup_csv)

    # Flatten backup so each (sheet, column) pair becomes one row.
    rows: list[dict] = []
    for _, b in backup.iterrows():
        match = primary[primary["column_name"] == b["column_name"]]
        match_dtype = match["data_type"].iloc[0] if not match.empty else "(not in primary)"
        match_missing_rate = float(match["missing_rate"].iloc[0]) if not match.empty else None
        rows.append(
            {
                "column_name": b["column_name"],
                "primary_dtype": match_dtype,
                "backup_dtype": b["data_type"],
                "backup_sheet": b["sheet"],
                "primary_missing_rate": match_missing_rate,
                "backup_missing_rate": b["missing_rate"],
                "name_matches_primary": bool(not match.empty),
                "dtype_matches_primary": bool(
                    not match.empty and str(match["data_type"].iloc[0]) == str(b["data_type"])
                ),
            }
        )
    pd.DataFrame.from_records(rows).to_csv(out_csv, index=False)
    return {"n_compared": len(rows)}


# ---------------------------------------------------------------------------
# DQ observations (markdown)
# ---------------------------------------------------------------------------


def _build_dq_md(
    df: pd.DataFrame,
    overview: AuditSummary,
    num: pd.DataFrame,
    miss: pd.DataFrame,
    id_profiles: dict,
    cancel_scan: dict,
    dup_exact,
    dup_invoice,
) -> str:
    """Render the data-quality observations as markdown."""
    lines: list[str] = []
    lines.append("# Primary Dataset — Data Quality Observations (FE-01)")
    lines.append("")
    lines.append(
        "All numbers below are computed live from "
        "`data/raw/primary/Online Retail.xlsx`. This document is a "
        "**read-only** observation report. No rows are modified, no "
        "values are imputed, no records are dropped."
    )
    lines.append("")

    # Top-level
    lines.append("## 1. Top-level snapshot")
    lines.append("")
    lines.append(f"- Rows: **{overview.n_rows:,}**")
    lines.append(f"- Columns: **{overview.n_columns}**")
    lines.append("- Columns: " + ", ".join(f"`{c}`" for c in overview.column_names))
    lines.append("")

    # Missing
    lines.append("## 2. Missing values")
    lines.append("")
    lines.append("| Column | Missing count | Missing rate (%) |")
    lines.append("| --- | ---: | ---: |")
    for _, row in miss.iterrows():
        lines.append(
            f"| `{row['column']}` | {int(row['missing_count']):,} | "
            f"{float(row['missing_rate']):.4f} |"
        )
    lines.append("")
    lines.append(
        "**Observation.** Negative/zero values are *not* handled here "
        "(see section 5); missing-value policy is owned by the "
        "preprocessing stage."
    )
    lines.append("")

    # Identifiers
    lines.append("## 3. Identifiers")
    lines.append("")
    lines.append("| Column | Unique count | Duplicate count | Missing count | Is unique? |")
    lines.append("| --- | ---: | ---: | ---: | :---: |")
    for col, prof in id_profiles.items():
        lines.append(
            f"| `{col}` | {prof['unique_count']:,} | {prof['duplicate_count']:,} | "
            f"{prof['missing_count']:,} | {'✅' if prof['is_unique'] else '❌'} |"
        )
    lines.append("")
    if cancel_scan:
        lines.append("### 3.1 InvoiceNo — cancellation-prefix scan")
        lines.append("")
        if cancel_scan["n_matching"] == 0:
            lines.append(
                "- Scanned all non-null `InvoiceNo` values for the prefix "
                '`"C"` (conventionally used by the original dataset for '
                "cancelled invoices)."
            )
            lines.append(
                f"- **Found {cancel_scan['n_matching']} matching values.** "
                f"In the raw primary file, `InvoiceNo` was parsed as "
                f"`int64`, which suggests there are **no `C`-prefixed "
                f"cancelled-invoice rows** in this copy of the dataset "
                f"(or they have been pre-filtered upstream)."
            )
            lines.append("- Examples: none.")
        else:
            lines.append(
                f"- Found **{cancel_scan['n_matching']:,}** values with prefix "
                f"`\"C\"` ({cancel_scan['rate_percent']:.4f}%)."
            )
            lines.append("- Examples: " + ", ".join(f"`{v}`" for v in cancel_scan["examples"]))
        lines.append("")

    # Duplicates
    lines.append("## 4. Duplicates")
    lines.append("")
    lines.append("| Pattern | Duplicate rows |")
    lines.append("| --- | ---: |")
    lines.append(f"| Exact-row duplicates | {dup_exact.exact_duplicate_rows:,} |")
    lines.append(
        f"| `(InvoiceNo, StockCode)`-level duplicates | {dup_invoice.key_duplicate_rows:,} |"
    )
    lines.append(
        f"| `(InvoiceNo, StockCode)`-level unique combinations | "
        f"{dup_invoice.key_unique_combinations:,} |"
    )
    lines.append("")
    lines.append(
        "**Observation.** A given `InvoiceNo` naturally appears on "
        "multiple rows because an invoice contains multiple products. "
        "Duplicate `InvoiceNo` values are therefore **not** data "
        "errors; they are the structure of invoice-line-level data."
    )
    lines.append("")

    # Numerical anomalies
    lines.append("## 5. Numerical anomalies (read-only)")
    lines.append("")
    lines.append("| Column | zero_count | negative_count | min | max |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for _, row in num.iterrows():
        lines.append(
            f"| `{row['column']}` | {int(row['zero_count']):,} | "
            f"{int(row['negative_count']):,} | {row['min']} | {row['max']} |"
        )
    lines.append("")
    lines.append(
        "**Observation.** Negative quantities / unit prices and zero "
        "values are recorded here **without any policy decision**. They "
        "are flagged for the preprocessing stage."
    )
    lines.append("")

    # Date coverage
    invoice_date = None
    if "InvoiceDate" in df.columns:
        from customer_segmentation.data.audit import date_profile as _dp

        invoice_date = _dp(df, "InvoiceDate")
    lines.append("## 6. Date coverage")
    lines.append("")
    if invoice_date is not None:
        lines.append(f"- Parsed rows: **{invoice_date.parsed_count:,} / {invoice_date.total:,}**")
        lines.append(f"- Unparseable rows: **{invoice_date.unparsed_count:,}**")
        lines.append(f"- Min: `{invoice_date.min.isoformat() if invoice_date.min else 'N/A'}`")
        lines.append(f"- Max: `{invoice_date.max.isoformat() if invoice_date.max else 'N/A'}`")
        lines.append(
            f"- Rows sharing a timestamp with another row: "
            f"**{invoice_date.duplicate_timestamps:,}** "
            "(expected — multiple products can be bought at the same instant)."
        )
    else:
        lines.append("- No `InvoiceDate` column found.")
    lines.append("")

    # Policy summary
    lines.append("## 7. Items requiring a preprocessing decision")
    lines.append("")
    items = [
        "Missing `CustomerID` rows: drop, impute, or keep as guest records?",
        "Negative `Quantity` rows: how to treat? (in the original UCI dataset, "
        "cancellations sometimes appear as negative quantities even when the "
        "`InvoiceNo` does not start with `C`.)",
        "Zero / negative `UnitPrice` rows: drop, flag, or impute?",
        f"Cancellation handling: the raw primary file contains "
        f"**{cancel_scan.get('n_matching', 0):,} `C`-prefixed `InvoiceNo` "
        f"rows** ({cancel_scan.get('rate_percent', 0.0):.4f}%); the "
        f"preprocessing policy for cancellations (drop, separate flag, "
        f"merge with negative-quantity logic, etc.) is undecided here.",
        "`Description` rows: drop missing, or treat as a separate signal?",
        "Per-customer aggregation rules: which columns are summed, which are "
        "counted unique, which become derived features? (FE-02+ territory.)",
    ]
    for it in items:
        lines.append(f"- {it}")
    lines.append("")
    lines.append(
        "FE-01 **does not** answer these questions. They are recorded here "
        "so the preprocessing stage (FE-02 or PR-XX, per the project lead's "
        "naming) has an explicit list to triage."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FE-01 raw dataset audit")
    p.add_argument(
        "--primary-dir",
        type=Path,
        default=DEFAULT_PRIMARY_DIR,
        help="Primary raw dataset directory.",
    )
    p.add_argument(
        "--backup-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help="Backup raw dataset directory.",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Output directory for FE-01 reports.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)
    args.report_dir.mkdir(parents=True, exist_ok=True)

    primary_path = args.primary_dir / PRIMARY_FILENAME
    print(f"[FE-01] auditing primary: {primary_path}")
    primary_summary = audit_primary(primary_path, args.report_dir)
    print(
        f"[FE-01] primary done: {primary_summary['n_rows']:,} rows, "
        f"{primary_summary['n_columns']} columns"
    )

    print(f"[FE-01] auditing backup: {args.backup_dir}")
    backup_summary = audit_backup(args.backup_dir, args.report_dir)
    print(f"[FE-01] backup done: {backup_summary['backup_file']}")

    compare = compare_primary_vs_backup(
        args.report_dir / "primary_schema.csv",
        args.report_dir / "backup_schema.csv",
        args.report_dir / "primary_vs_backup.csv",
    )
    print(f"[FE-01] primary-vs-backup comparison rows: {compare['n_compared']}")

    print(f"[FE-01] reports written to {args.report_dir}")


if __name__ == "__main__":
    main()
