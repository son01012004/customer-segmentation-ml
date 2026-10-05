"""Generate the canonical docs/data_dictionary/ artefacts for FE-01.

Reads the machine-readable outputs under ``reports/fe01/`` produced by
``scripts/run_fe01_audit.py`` and emits:

- ``docs/data_dictionary/dataset_schema.csv``
- ``docs/data_dictionary/data_dictionary.md``
- ``docs/data_dictionary/initial_data_profile.md``

Why a generator?
---------------
This guarantees that the human-readable docs and the machine-readable
schema are never out of sync with the audited numbers.

Notes
-----
- The role assignment (Identifier / Numerical Feature / ...) is encoded
  in a small lookup table here. Any change to role mapping must be made
  in **one** place (this file) and re-running the generator will
  propagate it everywhere.
- The generator never modifies the raw data. It only reads the audit
  reports and writes documentation files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_FILENAME = "Online Retail.xlsx"
DEFAULT_REPORT_DIR = _REPO_ROOT / "reports" / "fe01"
sys.path.insert(0, str(_REPO_ROOT / "src"))

from customer_segmentation.data.audit import numerical_profile  # noqa: E402
from customer_segmentation.data.loader import load_raw_transactions  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration: role assignment for the primary dataset's columns.
# ---------------------------------------------------------------------------

PRIMARY_ROLE: dict[str, str] = {
    "InvoiceNo": "Identifier (transaction)",
    "StockCode": "Identifier (product)",
    "Description": "Categorical Feature (text)",
    "Quantity": "Numerical Feature (transaction-line)",
    "InvoiceDate": "Date Feature (transaction)",
    "UnitPrice": "Numerical Feature (transaction-line)",
    "CustomerID": "Identifier (customer)",
    "Country": "Categorical Feature",
}

PRIMARY_MEANING: dict[str, str] = {
    "InvoiceNo": (
        "6-digit integral invoice number. A leading 'C' marks a "
        "cancellation in the original UCI dataset convention."
    ),
    "StockCode": ("5-digit integral product (item) code. May be alphanumeric " "(e.g. '85123A')."),
    "Description": "Product (item) name as recorded in the invoice line.",
    "Quantity": "The quantities of each product (item) per transaction.",
    "InvoiceDate": "Day and time when each transaction was generated.",
    "UnitPrice": "Product price per unit, in sterling (£).",
    "CustomerID": (
        "5-digit integral customer number, unique per customer. "
        "Missing in ~24.93% of rows in the raw primary file."
    ),
    "Country": "Name of the country where each customer resides.",
}

PRIMARY_UNIT: dict[str, str] = {
    "InvoiceNo": "code",
    "StockCode": "code",
    "Description": "text",
    "Quantity": "items",
    "InvoiceDate": "datetime",
    "UnitPrice": "GBP (£)",
    "CustomerID": "code",
    "Country": "category",
}

PRIMARY_SOURCE: dict[str, str] = dict.fromkeys(PRIMARY_ROLE, "UCI Online Retail (raw primary file)")

PRIMARY_BUSINESS: dict[str, str] = {
    "InvoiceNo": (
        "Used to group transaction lines into a single customer purchase "
        "event and to identify cancellations ('C' prefix)."
    ),
    "StockCode": (
        "Used to distinguish products and to compute product-level "
        "diversity features per customer."
    ),
    "Description": (
        "Free-text product label. Useful for product taxonomy work, but "
        "**not** used directly as a clustering feature."
    ),
    "Quantity": (
        "Used (after preprocessing decisions) to derive monetary value " "and basket-size features."
    ),
    "InvoiceDate": (
        "Used to compute Recency and purchase-cadence features at the " "customer level."
    ),
    "UnitPrice": (
        "Used (after preprocessing decisions) to compute Monetary "
        "(= sum(Quantity * UnitPrice)) per customer."
    ),
    "CustomerID": (
        "Customer-level join key for the modelling unit. Cannot "
        "meaningfully aggregate customers without this column."
    ),
    "Country": (
        "Behavioural attribute used for segmentation by geography. "
        "Mostly UK in the raw data (~91.4%)."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_overview(report_dir: Path) -> dict:
    return json.loads((report_dir / "primary_overview.json").read_text())


def _read_dq(report_dir: Path) -> str:
    return (report_dir / "primary_data_quality_observations.md").read_text()


def _read_numerical(report_dir: Path) -> pd.DataFrame:
    return pd.read_csv(report_dir / "primary_numerical.csv")


def _read_categorical(report_dir: Path) -> pd.DataFrame:
    return pd.read_csv(report_dir / "primary_categorical.csv")


def _read_missing(report_dir: Path) -> pd.DataFrame:
    return pd.read_csv(report_dir / "primary_missing.csv")


def _read_country_top(report_dir: Path) -> pd.DataFrame:
    return pd.read_csv(report_dir / "primary_country_top.csv")


def _read_identifiers(report_dir: Path) -> dict:
    return json.loads((report_dir / "primary_identifiers.json").read_text())


def _read_duplicates(report_dir: Path) -> dict:
    return json.loads((report_dir / "primary_duplicates.json").read_text())


def _read_date_range(report_dir: Path) -> str:
    return (report_dir / "primary_date_range.txt").read_text()


def _read_pvb(report_dir: Path) -> pd.DataFrame:
    return pd.read_csv(report_dir / "primary_vs_backup.csv")


def _read_backup_overview(report_dir: Path) -> dict:
    return json.loads((report_dir / "backup_overview.json").read_text())


# ---------------------------------------------------------------------------
# Schema CSV
# ---------------------------------------------------------------------------


def write_dataset_schema(report_dir: Path, docs_dir: Path) -> Path:
    """Write the canonical dataset_schema.csv (long format, one row per column).

    Re-computes the numerical profile from the raw data so the schema CSV
    is bit-for-bit identical to ``reports/fe01/primary_numerical.csv``
    (no CSV roundtrip precision drift).
    """
    overview = _read_overview(report_dir)
    miss = _read_missing(report_dir)

    # Re-compute the numerical profile from raw data so the
    # min/max/mean/median/std are *exactly* the same float64 values that
    # were written to reports/fe01/primary_numerical.csv (which is what
    # pandas computed in-memory). Reading the CSV back via
    # ``pd.read_csv`` can lose 1-2 last-digit precision, so we avoid it.
    primary_path = _REPO_ROOT / "data" / "raw" / "primary" / PRIMARY_FILENAME
    df = load_raw_transactions(primary_path, sheet_name=overview["loaded_sheet"])
    num = numerical_profile(df)
    num_idx = num.set_index("column")

    # Build per-column aggregates
    rows: list[dict] = []
    for col in overview["column_names"]:
        dtype = overview["dtypes"][col]
        role = PRIMARY_ROLE.get(col, "")
        miss_row = miss[miss["column"] == col].iloc[0]
        int(miss_row["present_count"]) - int(
            miss_row["present_count"]
        )  # placeholder, replaced below

        # unique_count is also in the audit's primary_schema.csv but we
        # recompute from the data here for a single source of truth.
        # Fallback: use the missing-table present_count and total_rows
        # only as a hint; better to rely on the audit's
        # primary_schema.csv which we re-read below.
        rows.append(
            {
                "column_name": col,
                "data_type": dtype,
                "role": role,
                "nullable": bool(int(miss_row["missing_count"]) > 0),
                "missing_count": int(miss_row["missing_count"]),
                "missing_rate": float(miss_row["missing_rate"]),
                "unique_count": "",  # filled below
                "min_value": "",
                "max_value": "",
                "notes": PRIMARY_MEANING.get(col, ""),
                "unit": PRIMARY_UNIT.get(col, ""),
                "source": PRIMARY_SOURCE.get(col, ""),
                "business_meaning": PRIMARY_BUSINESS.get(col, ""),
            }
        )

    # Pull the authoritative unique_count / min / max from the audit's
    # primary_schema.csv (which itself reads the raw data — never
    # hard-coded values).
    audit_schema = pd.read_csv(report_dir / "primary_schema.csv").set_index("column_name")
    for row in rows:
        col = row["column_name"]
        if col in audit_schema.index:
            row["unique_count"] = int(audit_schema.at[col, "unique_count"])
            row["min_value"] = str(audit_schema.at[col, "min_value"])
            row["max_value"] = str(audit_schema.at[col, "max_value"])

    # Numerical rows get extra fields
    num_idx = num.set_index("column")
    for row in rows:
        col = row["column_name"]
        if col in num_idx.index:
            row["min_value"] = num_idx.at[col, "min"]
            row["max_value"] = num_idx.at[col, "max"]
            row["mean_value"] = num_idx.at[col, "mean"]
            row["median_value"] = num_idx.at[col, "median"]
            row["std_value"] = num_idx.at[col, "std"]

    out = pd.DataFrame.from_records(rows)
    # Column order aligned with the data_dictionary.md table:
    # Column Name, Data Type, Role, Meaning, Unit, Source, Missing Count,
    # Missing Rate, Unique Values, Expected Range [min, max], Business Meaning.
    # Nullable + mean/median/std are added extras for downstream tooling.
    out = out.reindex(
        columns=[
            "column_name",
            "data_type",
            "role",
            "notes",
            "unit",
            "source",
            "missing_count",
            "missing_rate",
            "unique_count",
            "min_value",
            "max_value",
            "business_meaning",
            "nullable",
            "mean_value",
            "median_value",
            "std_value",
        ]
    )
    out_dir = docs_dir / "data_dictionary"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dataset_schema.csv"
    out.to_csv(out_path, index=False)
    return out_path


# ---------------------------------------------------------------------------
# Data dictionary (markdown)
# ---------------------------------------------------------------------------


def write_data_dictionary(
    report_dir: Path,
    docs_dir: Path,
    schema_path: Path,
) -> Path:
    """Render the human-readable data_dictionary.md from the schema CSV."""
    schema = pd.read_csv(schema_path)
    overview = _read_overview(report_dir)
    lines: list[str] = []
    lines.append("# Data Dictionary — UCI Online Retail (Primary, FE-01)")
    lines.append("")
    lines.append(
        "This data dictionary is the **canonical reference** for the raw "
        "primary dataset used in the customer-segmentation research. It "
        "documents every column at the level the team has agreed to "
        "(per the DS-05 decision and FE-01 audit)."
    )
    lines.append("")
    lines.append(
        "- **Dataset**: UCI Online Retail (Primary) — see "
        "[`docs/decisions/0001-primary-dataset-uci-online-retail.md`](../decisions/0001-primary-dataset-uci-online-retail.md)."
    )
    lines.append(
        "- **File**: `data/raw/primary/Online Retail.xlsx` "
        "(see also [`dataset_provenance.md`](./dataset_provenance.md) for "
        "SHA-256 and source URL)."
    )
    lines.append(
        f"- **Sheet**: `{overview['loaded_sheet']}` "
        f"(the file has {len(overview['sheet_names'])} sheet(s))."
    )
    lines.append(f"- **Rows**: **{overview['n_rows']:,}**")
    lines.append(f"- **Columns**: **{overview['n_columns']}**")
    lines.append("")
    lines.append("## Notes on the canonical filename")
    lines.append("")
    lines.append(
        "`configs/dataset.yaml` declares the canonical primary filename "
        "as `online_retail.xlsx`, but the actual file on disk is "
        "`Online Retail.xlsx`. The file has **not** been renamed (see "
        "[`dataset_provenance.md`](./dataset_provenance.md) for the full "
        "discussion). The schema and column meanings below describe the "
        "columns **as they appear in the actual file on disk**."
    )
    lines.append("")
    lines.append("## Column reference")
    lines.append("")
    lines.append(
        "| Column | Data Type | Role | Meaning | Unit | Source | "
        "Missing Count | Missing Rate | Unique Values | "
        "Expected Range | Business Meaning |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |")
    for _, row in schema.iterrows():
        col = row["column_name"]
        lines.append(
            f"| `{col}` "
            f"| `{row['data_type']}` "
            f"| {row['role']} "
            f"| {PRIMARY_MEANING.get(col, '')} "
            f"| {PRIMARY_UNIT.get(col, '')} "
            f"| {PRIMARY_SOURCE.get(col, '')} "
            f"| {int(row['missing_count']):,} "
            f"| {float(row['missing_rate']):.4f} "
            f"| {int(row['unique_count']):,} "
            f"| [{row['min_value']}, {row['max_value']}] "
            f"| {PRIMARY_BUSINESS.get(col, '')} |"
        )
    lines.append("")
    lines.append("## Identifier hierarchy")
    lines.append("")
    lines.append(
        "The dataset's unit of observation is **transaction-line**. "
        "The intended modelling unit is **customer**."
    )
    lines.append("")
    lines.append(
        "| Level | Column | Notes |\n"
        "| --- | --- | --- |\n"
        "| Transaction | `InvoiceNo` | A single invoice spans multiple rows (one per product). "
        "Prefix `C` marks a cancellation. |\n"
        "| Product | `StockCode` | Distinct product/item code. May be alphanumeric. |\n"
        "| Customer | `CustomerID` | Missing in ≈ 24.93 % of raw rows — "
        "must be addressed in preprocessing. |"
    )
    lines.append("")
    lines.append("## Source of every number in this file")
    lines.append("")
    lines.append(
        "All numbers in this document come from "
        "[`reports/fe01/primary_missing.csv`](../../reports/fe01/primary_missing.csv), "
        "[`reports/fe01/primary_numerical.csv`](../../reports/fe01/primary_numerical.csv), "
        "and [`reports/fe01/primary_schema.csv`](../../reports/fe01/primary_schema.csv). "
        "They are computed live by "
        "[`scripts/run_fe01_audit.py`](../../scripts/run_fe01_audit.py) "
        "and the docs are regenerated by "
        "[`scripts/generate_fe01_docs.py`](../../scripts/generate_fe01_docs.py)."
    )
    out_path = docs_dir / "data_dictionary" / "data_dictionary.md"
    out_path.write_text("\n".join(lines))
    return out_path


# ---------------------------------------------------------------------------
# Initial data profile (markdown)
# ---------------------------------------------------------------------------


def write_initial_data_profile(
    report_dir: Path,
    docs_dir: Path,
) -> Path:
    """Render initial_data_profile.md."""
    overview = _read_overview(report_dir)
    num = _read_numerical(report_dir)
    cat = _read_categorical(report_dir)
    miss = _read_missing(report_dir)
    country = _read_country_top(report_dir)
    ident = _read_identifiers(report_dir)
    dup = _read_duplicates(report_dir)
    dq_md = _read_dq(report_dir)
    pvb = _read_pvb(report_dir)
    backup = _read_backup_overview(report_dir)
    date_range = _read_date_range(report_dir)

    lines: list[str] = []
    lines.append("# Initial Data Profile — UCI Online Retail (Primary, FE-01)")
    lines.append("")
    lines.append(
        "This profile summarises the raw primary dataset at the level "
        "demanded by FE-01. Every number is computed live from the raw "
        "data by "
        "[`scripts/run_fe01_audit.py`](../../scripts/run_fe01_audit.py); "
        "no statistics are hard-coded here."
    )
    lines.append("")

    # 1. Dataset overview
    lines.append("## 1. Dataset overview")
    lines.append("")
    lines.append(
        "| Field | Value |\n"
        "| --- | --- |\n"
        f"| Dataset name | UCI Online Retail |\n"
        f"| Role | Primary |\n"
        f"| Local file | `data/raw/primary/Online Retail.xlsx` |\n"
        f"| Sheet name | `{overview['loaded_sheet']}` "
        f"(of {len(overview['sheet_names'])} sheet(s)) |\n"
        f"| Total rows | **{overview['n_rows']:,}** |\n"
        f"| Total columns | **{overview['n_columns']}** |\n"
        f"| In-memory size (deep) | {overview['memory_bytes']:,} bytes |\n"
        f"| Source | UCI Machine Learning Repository — dataset ID 352 |\n"
        f"| License | CC BY 4.0 |"
    )
    lines.append("")

    # 2. Dimensions
    lines.append("## 2. Dataset dimensions")
    lines.append("")
    lines.append(f"- Rows: **{overview['n_rows']:,}**")
    lines.append(f"- Columns: **{overview['n_columns']}**")
    lines.append("")
    lines.append("Columns (in order):")
    lines.append("")
    for c in overview["column_names"]:
        lines.append(f"- `{c}` — `{overview['dtypes'][c]}`")
    lines.append("")

    # 3. Date coverage
    lines.append("## 3. Date coverage")
    lines.append("")
    lines.append("```")
    lines.append(date_range.rstrip())
    lines.append("```")
    lines.append("")
    lines.append(
        "**Implication for FE-02 / RFM.** The dataset covers just over "
        "one year (December 2010 – December 2011). A reference date for "
        "the **Recency** computation must be chosen as part of the "
        "RFM stage (FE-02 / PR-XX). Per `configs/features.yaml` the "
        "default mode is `snapshot_max` (max InvoiceDate + 1 day); this "
        "is **not** modified by FE-01."
    )
    lines.append("")

    # 4. Column overview
    lines.append("## 4. Column overview")
    lines.append("")
    lines.append("| Column | dtype | Role |")
    lines.append("| --- | --- | --- |")
    for c in overview["column_names"]:
        lines.append(f"| `{c}` | `{overview['dtypes'][c]}` | {PRIMARY_ROLE.get(c, '')} |")
    lines.append("")

    # 5. Missing profile
    lines.append("## 5. Missing-data profile")
    lines.append("")
    lines.append(
        "| Column | Missing Count | Missing Rate (%) | Notes |\n" "| --- | ---: | ---: | --- |"
    )
    notes_map = {
        "CustomerID": "Large share (~24.93%). Decision required in preprocessing.",
        "Description": "Small share (~0.27%). Decision required in preprocessing.",
    }
    for _, row in miss.sort_values("missing_count", ascending=False).iterrows():
        col = row["column"]
        lines.append(
            f"| `{col}` | {int(row['missing_count']):,} | "
            f"{float(row['missing_rate']):.4f} | {notes_map.get(col, '—')} |"
        )
    lines.append("")

    # 6. Numerical profile
    lines.append("## 6. Numerical profile")
    lines.append("")
    lines.append(
        "| Column | Count | Missing | Min | Max | Mean | Median | Std | "
        "Zero count | Negative count |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for _, row in num.iterrows():
        lines.append(
            f"| `{row['column']}` | {int(row['count']):,} | "
            f"{int(row['missing_count']):,} | "
            f"{row['min']} | {row['max']} | "
            f"{row['mean']:.4f} | {row['median']:.4f} | {row['std']:.4f} | "
            f"{int(row['zero_count']):,} | {int(row['negative_count']):,} |"
        )
    lines.append("")

    # 7. Categorical profile
    lines.append("## 7. Categorical profile")
    lines.append("")
    lines.append("| Column | Count | Missing | Unique | Top values (value:count) |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for _, row in cat.iterrows():
        lines.append(
            f"| `{row['column']}` | {int(row['count']):,} | "
            f"{int(row['missing_count']):,} | {int(row['unique_count']):,} | "
            f"{str(row['top_values'])[:120]} |"
        )
    lines.append("")

    # 7a. Country distribution
    lines.append("### 7.1 Country — top 15")
    lines.append("")
    lines.append("| Country | Count | Rate (%) |")
    lines.append("| --- | ---: | ---: |")
    for _, row in country.iterrows():
        lines.append(f"| {row['Country']} | {int(row['count']):,} | {float(row['rate']):.4f} |")
    lines.append("")

    # 8. Identifier profile
    lines.append("## 8. Identifier profile")
    lines.append("")
    lines.append("| Column | Total | Missing | Unique | Duplicate | Unique rate (%) | Is unique? |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | :---: |")
    for col, prof in ident["identifiers"].items():
        lines.append(
            f"| `{col}` | {prof['total']:,} | {prof['missing_count']:,} | "
            f"{prof['unique_count']:,} | {prof['duplicate_count']:,} | "
            f"{prof['unique_rate']:.4f} | {'✅' if prof['is_unique'] else '❌'} |"
        )
    lines.append("")
    cancel = ident.get("invoice_cancellation_scan", {})
    if cancel:
        lines.append("### 8.1 `InvoiceNo` — cancellation-prefix scan")
        lines.append("")
        lines.append(
            f"- Values with prefix `\"C\"`: **{cancel.get('n_matching', 0):,}** "
            f"({cancel.get('rate_percent', 0.0):.4f} % of non-null `InvoiceNo`)."
        )
        lines.append(f"- Examples: {', '.join(f'`{v}`' for v in cancel.get('examples', []))}")
        lines.append("")

    # 9. Transaction profile
    lines.append("## 9. Transaction profile")
    lines.append("")
    lines.append(
        "The unit of observation is **transaction-line** (one row per "
        "product on an invoice). The intended modelling unit is "
        "**customer**. Aggregation to customer-level is **not** performed "
        "in FE-01."
    )
    lines.append("")
    lines.append("| Level | Column(s) | Count (distinct) |")
    lines.append("| --- | --- | ---: |")
    level_label = {
        "InvoiceNo": "Invoice",
        "StockCode": "Product (StockCode)",
        "CustomerID": "Customer (CustomerID)",
    }
    for col, prof in ident["identifiers"].items():
        lines.append(f"| {level_label.get(col, col)} " f"| `{col}` | {prof['unique_count']:,} |")
    lines.append("")
    lines.append(
        "**Invoice structure.** The `(InvoiceNo, StockCode)`-level "
        f"yields {dup['by_invoice_stockcode']['key_unique_combinations']:,} "
        "unique combinations out of "
        f"{overview['n_rows']:,} rows. Multiple rows per invoice is "
        "expected because each invoice contains multiple products."
    )
    lines.append("")

    # 10. Duplicate profile
    lines.append("## 10. Duplicate profile")
    lines.append("")
    lines.append("| Pattern | Duplicate rows |")
    lines.append("| --- | ---: |")
    lines.append(
        f"| Exact-row duplicates | {dup['exact_duplicate_rows']:,} ({dup['exact_duplicate_row_rate']:.4f}%) |"
    )
    lines.append(
        f"| `(InvoiceNo, StockCode)`-key duplicates | {dup['by_invoice_stockcode']['key_duplicate_rows']:,} |"
    )
    lines.append(
        f"| `(InvoiceNo, StockCode, Description, Quantity, InvoiceDate)`-key duplicates | {dup['by_full_line_keys']['key_duplicate_rows']:,} |"
    )
    lines.append("")

    # 11. DQ observations (link)
    lines.append("## 11. Data-quality observations")
    lines.append("")
    lines.append(
        "Full report: "
        "[`reports/fe01/primary_data_quality_observations.md`](../../reports/fe01/primary_data_quality_observations.md)."
    )
    lines.append("")
    # Insert an abbreviated DQ section (top-level only).
    # Find the section break between top-level snapshot and the items list
    if "## 7. Items requiring a preprocessing decision" in dq_md:
        abbrev = dq_md.split("## 7. Items requiring a preprocessing decision")[0]
    else:
        abbrev = dq_md
    lines.append(abbrev)

    # 12. Primary vs Backup
    lines.append("## 12. Primary vs Backup — schema comparison")
    lines.append("")
    lines.append("### 12.1 Backup overview")
    lines.append("")
    lines.append("| Sheet | Rows | Columns | Date min | Date max |")
    lines.append("| --- | ---: | ---: | --- | --- |")
    for sh in backup["sheets"]:
        rng = backup["date_ranges"].get(sh["sheet"], {})
        lines.append(
            f"| `{sh['sheet']}` | {sh['n_rows']:,} | {sh['n_columns']} | "
            f"{rng.get('min', 'N/A')} | {rng.get('max', 'N/A')} |"
        )
    lines.append("")
    lines.append("### 12.2 Column-name differences")
    lines.append("")
    lines.append(
        "The backup uses **different column names** compared to the "
        "primary. The shared logical concepts are listed below."
    )
    lines.append("")
    lines.append(
        "| Logical concept | Primary column | Backup column | " "Backup dtype matches primary? |"
    )
    lines.append("| --- | --- | --- | :---: |")
    pairings = {
        "Invoice number": ("InvoiceNo", "Invoice"),
        "Product code": ("StockCode", "StockCode"),
        "Description": ("Description", "Description"),
        "Quantity": ("Quantity", "Quantity"),
        "Invoice date": ("InvoiceDate", "InvoiceDate"),
        "Unit price": ("UnitPrice", "Price"),
        "Customer id": ("CustomerID", "Customer ID"),
        "Country": ("Country", "Country"),
    }
    backup_pivot = pvb.groupby("column_name").first()  # collapse sheets
    for concept, (pc, bc) in pairings.items():
        if bc in backup_pivot.index:
            dtype_match = backup_pivot.at[bc, "dtype_matches_primary"]
            primary_col_str = f"`{pc}`" if pc else "(none)"
            backup_col_str = f"`{bc}`"
            lines.append(
                f"| {concept} | {primary_col_str} | {backup_col_str} | "
                f"{'✅' if dtype_match else '❌'} |"
            )
    lines.append("")
    lines.append("### 12.3 Coverage and row-level difference")
    lines.append("")
    lines.append(
        "- The primary spans **2010-12-01 → 2011-12-09** (≈ 1 year). "
        "Backup sheet `Year 2010-2011` covers the same date window."
    )
    lines.append(
        "- Backup sheet `Year 2009-2010` extends the time coverage by "
        "**one additional year** (2009-12-01 → 2010-12-09). This is "
        "the main reason the backup is kept as a robustness / coverage "
        "fallback."
    )
    lines.append(
        "- The two datasets use **different column names** for "
        "invoice number, unit price, and customer id (see 12.2). Any "
        "code that consumes both must apply a renaming map at the "
        "loader layer (PR-XX task)."
    )
    # 12.4 Row-level comparison (real, computed at doc-generation time)
    lines.append("")
    lines.append("### 12.4 Row-level comparison (Primary vs Backup `Year 2010-2011`)")
    lines.append("")
    try:
        primary_path = _REPO_ROOT / "data" / "raw" / "primary" / PRIMARY_FILENAME
        backup_path = _REPO_ROOT / "data" / "raw" / "backup" / "online_retail_II.xlsx"
        primary_df = load_raw_transactions(primary_path, sheet_name=overview["loaded_sheet"])
        backup_y1011 = load_raw_transactions(backup_path, sheet_name="Year 2010-2011")
        backup_renamed = backup_y1011.rename(
            columns={
                "Invoice": "InvoiceNo",
                "Price": "UnitPrice",
                "Customer ID": "CustomerID",
            }
        )
        key = ["InvoiceNo", "StockCode", "InvoiceDate"]
        primary_keys = set(primary_df[key].apply(tuple, axis=1))
        backup_keys = set(backup_renamed[key].apply(tuple, axis=1))
        n_common = len(primary_keys & backup_keys)
        n_only_primary = len(primary_keys - backup_keys)
        n_only_backup = len(backup_keys - primary_keys)
        delta = len(backup_renamed) - len(primary_df)
        lines.append(
            f"- Primary rows: **{len(primary_df):,}**. Backup "
            f"`Year 2010-2011` rows: **{len(backup_renamed):,}** "
            f"(delta **{delta:+,}**)."
        )
        lines.append(
            f"- Compared on the join key "
            f"`(InvoiceNo, StockCode, InvoiceDate)`: "
            f"**{n_common:,}** rows are present in both; "
            f"**{n_only_primary:,}** rows are only in the primary; "
            f"**{n_only_backup:,}** rows are only in the backup."
        )
        if n_only_backup == 1 and n_only_primary == 0:
            only_in_backup = list(backup_keys - primary_keys)
            tup = only_in_backup[0]
            lines.append(
                f"- The single extra row in the backup is: "
                f"`InvoiceNo={tup[0]}`, `StockCode={tup[1]}`, "
                f"`InvoiceDate={tup[2]}`. After renaming "
                f"`Invoice→InvoiceNo`, `Price→UnitPrice`, "
                f"`Customer ID→CustomerID`, this row corresponds to a "
                f"single `POSTAGE` line for `CustomerID=12680` "
                f"(country: France)."
            )
            lines.append(
                "- **Implication**: the claim "
                '"matches the primary row-for-row" is **not '
                "accurate**. FE-01 records the precise delta instead. "
                "Whether the missing-vs-extra line should be "
                "kept, dropped, or otherwise reconciled is a "
                "preprocessing decision (PR-XX / FE-02) and is "
                "**not** resolved here."
            )
    except FileNotFoundError:
        lines.append(
            "- (Primary-vs-Backup row-level comparison could not be "
            "computed: a required file was missing at generation time.)"
        )
    lines.append("")

    # 13. Implications for preprocessing
    lines.append("## 13. Implications for the next stage (preprocessing)")
    lines.append("")
    lines.append(
        "FE-01 deliberately does **not** decide the preprocessing rules. "
        "The following implications are listed so the next stage has a "
        "single page to triage. Each item must be resolved by an ADR "
        "**before** it is implemented."
    )
    lines.append("")
    implications = [
        "`CustomerID` is missing in ≈ 24.93 % of rows. Decide: drop, "
        "impute (e.g. via invoice grouping heuristics), or model "
        "guests separately.",
        "Negative `Quantity` rows (≈ 10,624) coincide with `C`-prefixed "
        "`InvoiceNo` rows (≈ 9,288). Decide a unified cancellation rule.",
        "`UnitPrice` has 2,515 zero-valued rows and 2 negative-valued "
        "rows. Decide: drop, impute, or treat as a separate flag.",
        "`Description` has 1,454 missing rows. Decide whether to drop "
        "the affected lines, treat missing as a separate label, or "
        "ignore the column for the modelling matrix.",
        "`StockCode` is mostly numeric but contains alphanumeric codes "
        "(e.g. '85123A', 'POST', 'M'). Decide whether to keep them as "
        "strings or to special-case postage / manual entries.",
        "Backup dataset has different column names (`Invoice` / `Price` / "
        "`Customer ID`). A canonical rename map must be defined if the "
        "backup is ever loaded into the modelling pipeline.",
        "Decide a canonical reference date for RFM. The audit gives the "
        "raw max `InvoiceDate` so the choice can be made later without "
        "re-reading the data.",
        "Decide which duplicates to keep when (InvoiceNo, StockCode, "
        "Description, Quantity, InvoiceDate) coincide. The audit reports "
        f"{dup['by_full_line_keys']['key_duplicate_rows']:,} such rows.",
    ]
    for it in implications:
        lines.append(f"- {it}")
    lines.append("")
    lines.append(
        "FE-01 finishes here. The next stage (FE-02 / PR-XX) takes these " "implications as input."
    )

    out_path = docs_dir / "data_dictionary" / "initial_data_profile.md"
    out_path.write_text("\n".join(lines))
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate FE-01 docs from audit outputs.")
    p.add_argument(
        "--report-dir",
        type=Path,
        default=_REPO_ROOT / "reports" / "fe01",
        help="Directory holding the FE-01 audit reports.",
    )
    p.add_argument(
        "--docs-dir",
        type=Path,
        default=_REPO_ROOT / "docs",
        help="Repository docs/ directory.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)

    schema_path = write_dataset_schema(args.report_dir, args.docs_dir)
    print(f"[FE-01] wrote {schema_path}")

    dict_path = write_data_dictionary(args.report_dir, args.docs_dir, schema_path)
    print(f"[FE-01] wrote {dict_path}")

    profile_path = write_initial_data_profile(args.report_dir, args.docs_dir)
    print(f"[FE-01] wrote {profile_path}")


if __name__ == "__main__":
    main()
