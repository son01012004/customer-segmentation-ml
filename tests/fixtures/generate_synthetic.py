"""Generate a synthetic DEV-02-importable CSV for E2E prototype pipeline test.

This is a TEST-ONLY utility (not part of the production codebase). It
generates a CSV with sufficient variation to exercise DEV-02 import +
DEV-03 preprocess + downstream clustering stages.

Constraints:
- seed = 42 (deterministic)
- ~200 unique customers
- ~2000 rows
- Multi-day InvoiceDate (so PurchaseIntervalMean/Std are not all NaN)
- Some cancellations (InvoiceNo starting with 'C')
- Some returns (C-prefixed invoice with positive Quantity, lower UnitPrice)
- Sufficient numeric variation in Quantity, UnitPrice, Monetary to
  avoid constant features in the ML dataset.
- Output is gitignored (written to /tmp only).

Schema (8 cols, matching data_dictionary/dataset_schema.csv):
    InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice,
    CustomerID, Country

Usage (from repo root)::

    python3 -m tests.fixtures.generate_synthetic /tmp/synthetic.csv
    PYTHONPATH=src python3 scripts/dev02_import_dataset.py --file /tmp/synthetic.csv \\
        --name synthetic_test --allow-external-source

Or import and use programmatically::

    from tests.fixtures.generate_synthetic import generate_synthetic_csv
    stats = generate_synthetic_csv(Path("/tmp/synthetic.csv"))
"""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
N_ROWS = 2000
N_CUSTOMERS = 200
N_DAYS = 90  # 90-day window to ensure multi-day InvoiceDate per customer
START_DATE = datetime(2010, 12, 1, 9, 0, 0)
COUNTRIES = [
    "United Kingdom",
    "Germany",
    "France",
    "Norway",
    "Australia",
    "Netherlands",
    "Japan",
    "USA",
    "Spain",
    "Belgium",
    "Switzerland",
    "Portugal",
    "Italy",
    "Cyprus",
    "Greece",
    "Poland",
    "Israel",
    "Hong Kong",
    "Singapore",
    "Iceland",
]
STOCK_CODES = [(f"{10000 + i:05d}", f"SYNTHETIC PRODUCT {i:03d}") for i in range(1, 51)]
CUSTOMER_IDS = [100000 + i for i in range(1, N_CUSTOMERS + 1)]


def generate_synthetic_csv(out_path: Path, seed: int = SEED) -> dict:
    """Generate the synthetic CSV. Returns a stats dict for logging."""
    rng = random.Random(seed)
    rows: list[list] = []
    n_cancellations = 0
    n_returns = 0

    # Per-customer invoice assignment: each customer gets 1..3 invoices
    # spread across N_DAYS, each invoice has 1..15 line items.
    for cid in CUSTOMER_IDS:
        n_invoices = rng.randint(1, 3)
        for _ in range(n_invoices):
            offset_minutes = rng.randint(0, N_DAYS * 24 * 60)
            invoice_dt = START_DATE + timedelta(minutes=offset_minutes)
            is_cancellation = rng.random() < 0.04  # ~4% cancellations
            invoice_no = (
                f"C{rng.randint(536000, 537000)}"
                if is_cancellation
                else f"{rng.randint(536000, 537000)}"
            )
            n_lines = rng.randint(1, 15)
            for _line in range(n_lines):
                stock_code, description = rng.choice(STOCK_CODES)
                # Quantity: 1..96 (positive; cancellations will override below)
                qty = rng.randint(1, 96)
                # UnitPrice: 0.29..18.0 (matching the on-disk data range)
                unit_price = round(rng.uniform(0.29, 18.0), 2)
                if is_cancellation:
                    # Cancellations have negative Quantity per FE-02 semantics
                    qty = -qty
                    n_cancellations += 1
                    # Some cancellations are also returns (lower price, positive qty)
                    if rng.random() < 0.5:
                        qty = abs(qty)
                        unit_price = round(unit_price * 0.5, 2)
                        n_returns += 1
                rows.append(
                    [
                        invoice_no,
                        stock_code,
                        description,
                        qty,
                        invoice_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        unit_price,
                        cid,
                        rng.choice(COUNTRIES),
                    ]
                )

    # Trim or pad to N_ROWS
    rng.shuffle(rows)
    if len(rows) > N_ROWS:
        rows = rows[:N_ROWS]
    while len(rows) < N_ROWS:
        # Pad with random rows if needed (rare path)
        stock_code, description = rng.choice(STOCK_CODES)
        rows.append(
            [
                f"{rng.randint(536000, 537000)}",
                stock_code,
                description,
                rng.randint(1, 96),
                (START_DATE + timedelta(minutes=rng.randint(0, N_DAYS * 24 * 60))).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                round(rng.uniform(0.29, 18.0), 2),
                rng.choice(CUSTOMER_IDS),
                rng.choice(COUNTRIES),
            ]
        )

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "InvoiceNo",
                "StockCode",
                "Description",
                "Quantity",
                "InvoiceDate",
                "UnitPrice",
                "CustomerID",
                "Country",
            ]
        )
        writer.writerows(rows)

    unique_customers = len({r[6] for r in rows})
    return {
        "rows": len(rows),
        "unique_customers": unique_customers,
        "cancellations": n_cancellations,
        "returns": n_returns,
        "n_days_span": N_DAYS,
        "first_invoice_date": min(r[4] for r in rows),
        "last_invoice_date": max(r[4] for r in rows),
    }


if __name__ == "__main__":
    import json
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/synthetic.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    stats = generate_synthetic_csv(out)
    print(json.dumps({"out": str(out), **stats}, indent=2))
