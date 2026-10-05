# Initial Data Profile — UCI Online Retail (Primary, FE-01)

This profile summarises the raw primary dataset at the level demanded by FE-01. Every number is computed live from the raw data by [`scripts/run_fe01_audit.py`](../../scripts/run_fe01_audit.py); no statistics are hard-coded here.

## 1. Dataset overview

| Field | Value |
| --- | --- |
| Dataset name | UCI Online Retail |
| Role | Primary |
| Local file | `data/raw/primary/Online Retail.xlsx` |
| Sheet name | `Online Retail` (of 1 sheet(s)) |
| Total rows | **541,909** |
| Total columns | **8** |
| In-memory size (deep) | 132,310,571 bytes |
| Source | UCI Machine Learning Repository — dataset ID 352 |
| License | CC BY 4.0 |

## 2. Dataset dimensions

- Rows: **541,909**
- Columns: **8**

Columns (in order):

- `InvoiceNo` — `object`
- `StockCode` — `object`
- `Description` — `object`
- `Quantity` — `int64`
- `InvoiceDate` — `datetime64[us]`
- `UnitPrice` — `float64`
- `CustomerID` — `float64`
- `Country` — `str`

## 3. Date coverage

```
InvoiceDate min: 2010-12-01T08:26:00
InvoiceDate max: 2011-12-09T12:50:00
Parsed: 541909/541909
Unparsed: 0
Duplicate timestamps: 537667
```

**Implication for FE-02 / RFM.** The dataset covers just over one year (December 2010 – December 2011). A reference date for the **Recency** computation must be chosen as part of the RFM stage (FE-02 / PR-XX). Per `configs/features.yaml` the default mode is `snapshot_max` (max InvoiceDate + 1 day); this is **not** modified by FE-01.

## 4. Column overview

| Column | dtype | Role |
| --- | --- | --- |
| `InvoiceNo` | `object` | Identifier (transaction) |
| `StockCode` | `object` | Identifier (product) |
| `Description` | `object` | Categorical Feature (text) |
| `Quantity` | `int64` | Numerical Feature (transaction-line) |
| `InvoiceDate` | `datetime64[us]` | Date Feature (transaction) |
| `UnitPrice` | `float64` | Numerical Feature (transaction-line) |
| `CustomerID` | `float64` | Identifier (customer) |
| `Country` | `str` | Categorical Feature |

## 5. Missing-data profile

| Column | Missing Count | Missing Rate (%) | Notes |
| --- | ---: | ---: | --- |
| `CustomerID` | 135,080 | 24.9267 | Large share (~24.93%). Decision required in preprocessing. |
| `Description` | 1,454 | 0.2683 | Small share (~0.27%). Decision required in preprocessing. |
| `Country` | 0 | 0.0000 | — |
| `InvoiceDate` | 0 | 0.0000 | — |
| `InvoiceNo` | 0 | 0.0000 | — |
| `Quantity` | 0 | 0.0000 | — |
| `StockCode` | 0 | 0.0000 | — |
| `UnitPrice` | 0 | 0.0000 | — |

## 6. Numerical profile

| Column | Count | Missing | Min | Max | Mean | Median | Std | Zero count | Negative count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Quantity` | 541,909 | 0 | -80995.0 | 80995.0 | 9.5522 | 3.0000 | 218.0812 | 0 | 10,624 |
| `UnitPrice` | 541,909 | 0 | -11062.06 | 38970.0 | 4.6111 | 2.0800 | 96.7599 | 2,515 | 2 |
| `CustomerID` | 406,829 | 135,080 | 12346.0 | 18287.0 | 15287.6906 | 15152.0000 | 1713.6003 | 0 | 0 |

## 7. Categorical profile

| Column | Count | Missing | Unique | Top values (value:count) |
| --- | ---: | ---: | ---: | --- |
| `InvoiceNo` | 541,909 | 0 | 25,900 | 573585:1114;581219:749;581492:731;580729:721;558475:705;579777:687;581217:676;537434:675;580730:662;538071:652 |
| `StockCode` | 541,909 | 0 | 4,070 | 85123A:2313;22423:2203;85099B:2159;47566:1727;20725:1639;84879:1502;22720:1477;22197:1476;21212:1385;20727:1350 |
| `Description` | 540,455 | 1,454 | 4,223 | WHITE HANGING HEART T-LIGHT HOLDER:2369;REGENCY CAKESTAND 3 TIER:2200;JUMBO BAG RED RETROSPOT:2159;PARTY BUNTING:1727;LU |
| `Country` | 541,909 | 0 | 38 | United Kingdom:495478;Germany:9495;France:8557;EIRE:8196;Spain:2533;Netherlands:2371;Belgium:2069;Switzerland:2002;Portu |

### 7.1 Country — top 15

| Country | Count | Rate (%) |
| --- | ---: | ---: |
| United Kingdom | 495,478 | 91.4320 |
| Germany | 9,495 | 1.7521 |
| France | 8,557 | 1.5790 |
| EIRE | 8,196 | 1.5124 |
| Spain | 2,533 | 0.4674 |
| Netherlands | 2,371 | 0.4375 |
| Belgium | 2,069 | 0.3818 |
| Switzerland | 2,002 | 0.3694 |
| Portugal | 1,519 | 0.2803 |
| Australia | 1,259 | 0.2323 |
| Norway | 1,086 | 0.2004 |
| Italy | 803 | 0.1482 |
| Channel Islands | 758 | 0.1399 |
| Finland | 695 | 0.1283 |
| Cyprus | 622 | 0.1148 |

## 8. Identifier profile

| Column | Total | Missing | Unique | Duplicate | Unique rate (%) | Is unique? |
| --- | ---: | ---: | ---: | ---: | ---: | :---: |
| `InvoiceNo` | 541,909 | 0 | 25,900 | 516,009 | 4.7794 | ❌ |
| `StockCode` | 541,909 | 0 | 4,070 | 537,839 | 0.7510 | ❌ |
| `CustomerID` | 541,909 | 135,080 | 4,372 | 402,457 | 1.0747 | ❌ |

### 8.1 `InvoiceNo` — cancellation-prefix scan

- Values with prefix `"C"`: **9,288** (1.7139 % of non-null `InvoiceNo`).
- Examples: `C536379`, `C536383`, `C536391`, `C536391`, `C536391`

## 9. Transaction profile

The unit of observation is **transaction-line** (one row per product on an invoice). The intended modelling unit is **customer**. Aggregation to customer-level is **not** performed in FE-01.

| Level | Column(s) | Count (distinct) |
| --- | --- | ---: |
| Invoice | `InvoiceNo` | 25,900 |
| Product (StockCode) | `StockCode` | 4,070 |
| Customer (CustomerID) | `CustomerID` | 4,372 |

**Invoice structure.** The `(InvoiceNo, StockCode)`-level yields 531,225 unique combinations out of 541,909 rows. Multiple rows per invoice is expected because each invoice contains multiple products.

## 10. Duplicate profile

| Pattern | Duplicate rows |
| --- | ---: |
| Exact-row duplicates | 5,268 (0.9721%) |
| `(InvoiceNo, StockCode)`-key duplicates | 10,684 |
| `(InvoiceNo, StockCode, Description, Quantity, InvoiceDate)`-key duplicates | 5,427 |

## 11. Data-quality observations

Full report: [`reports/fe01/primary_data_quality_observations.md`](../../reports/fe01/primary_data_quality_observations.md).

# Primary Dataset — Data Quality Observations (FE-01)

All numbers below are computed live from `data/raw/primary/Online Retail.xlsx`. This document is a **read-only** observation report. No rows are modified, no values are imputed, no records are dropped.

## 1. Top-level snapshot

- Rows: **541,909**
- Columns: **8**
- Columns: `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country`

## 2. Missing values

| Column | Missing count | Missing rate (%) |
| --- | ---: | ---: |
| `CustomerID` | 135,080 | 24.9267 |
| `Description` | 1,454 | 0.2683 |
| `Country` | 0 | 0.0000 |
| `InvoiceDate` | 0 | 0.0000 |
| `InvoiceNo` | 0 | 0.0000 |
| `Quantity` | 0 | 0.0000 |
| `StockCode` | 0 | 0.0000 |
| `UnitPrice` | 0 | 0.0000 |

**Observation.** Negative/zero values are *not* handled here (see section 5); missing-value policy is owned by the preprocessing stage.

## 3. Identifiers

| Column | Unique count | Duplicate count | Missing count | Is unique? |
| --- | ---: | ---: | ---: | :---: |
| `InvoiceNo` | 25,900 | 516,009 | 0 | ❌ |
| `StockCode` | 4,070 | 537,839 | 0 | ❌ |
| `CustomerID` | 4,372 | 402,457 | 135,080 | ❌ |

### 3.1 InvoiceNo — cancellation-prefix scan

- Found **9,288** values with prefix `"C"` (1.7139%).
- Examples: `C536379`, `C536383`, `C536391`, `C536391`, `C536391`

## 4. Duplicates

| Pattern | Duplicate rows |
| --- | ---: |
| Exact-row duplicates | 5,268 |
| `(InvoiceNo, StockCode)`-level duplicates | 10,684 |
| `(InvoiceNo, StockCode)`-level unique combinations | 531,225 |

**Observation.** A given `InvoiceNo` naturally appears on multiple rows because an invoice contains multiple products. Duplicate `InvoiceNo` values are therefore **not** data errors; they are the structure of invoice-line-level data.

## 5. Numerical anomalies (read-only)

| Column | zero_count | negative_count | min | max |
| --- | ---: | ---: | ---: | ---: |
| `Quantity` | 0 | 10,624 | -80995.0 | 80995.0 |
| `UnitPrice` | 2,515 | 2 | -11062.06 | 38970.0 |
| `CustomerID` | 0 | 0 | 12346.0 | 18287.0 |

**Observation.** Negative quantities / unit prices and zero values are recorded here **without any policy decision**. They are flagged for the preprocessing stage.

## 6. Date coverage

- Parsed rows: **541,909 / 541,909**
- Unparseable rows: **0**
- Min: `2010-12-01T08:26:00`
- Max: `2011-12-09T12:50:00`
- Rows sharing a timestamp with another row: **537,667** (expected — multiple products can be bought at the same instant).


## 12. Primary vs Backup — schema comparison

### 12.1 Backup overview

| Sheet | Rows | Columns | Date min | Date max |
| --- | ---: | ---: | --- | --- |
| `Year 2009-2010` | 525,461 | 8 | 2009-12-01T07:45:00 | 2010-12-09T20:01:00 |
| `Year 2010-2011` | 541,910 | 8 | 2010-12-01T08:26:00 | 2011-12-09T12:50:00 |

### 12.2 Column-name differences

The backup uses **different column names** compared to the primary. The shared logical concepts are listed below.

| Logical concept | Primary column | Backup column | Backup dtype matches primary? |
| --- | --- | --- | :---: |
| Invoice number | `InvoiceNo` | `Invoice` | ❌ |
| Product code | `StockCode` | `StockCode` | ✅ |
| Description | `Description` | `Description` | ✅ |
| Quantity | `Quantity` | `Quantity` | ✅ |
| Invoice date | `InvoiceDate` | `InvoiceDate` | ✅ |
| Unit price | `UnitPrice` | `Price` | ❌ |
| Customer id | `CustomerID` | `Customer ID` | ❌ |
| Country | `Country` | `Country` | ✅ |

### 12.3 Coverage and row-level difference

- The primary spans **2010-12-01 → 2011-12-09** (≈ 1 year). Backup sheet `Year 2010-2011` covers the same date window.
- Backup sheet `Year 2009-2010` extends the time coverage by **one additional year** (2009-12-01 → 2010-12-09). This is the main reason the backup is kept as a robustness / coverage fallback.
- The two datasets use **different column names** for invoice number, unit price, and customer id (see 12.2). Any code that consumes both must apply a renaming map at the loader layer (PR-XX task).

### 12.4 Row-level comparison (Primary vs Backup `Year 2010-2011`)

- Primary rows: **541,909**. Backup `Year 2010-2011` rows: **541,910** (delta **+1**).
- Compared on the join key `(InvoiceNo, StockCode, InvoiceDate)`: **531,232** rows are present in both; **0** rows are only in the primary; **1** rows are only in the backup.
- The single extra row in the backup is: `InvoiceNo=581587`, `StockCode=POST`, `InvoiceDate=2011-12-09 12:50:00`. After renaming `Invoice→InvoiceNo`, `Price→UnitPrice`, `Customer ID→CustomerID`, this row corresponds to a single `POSTAGE` line for `CustomerID=12680` (country: France).
- **Implication**: the claim "matches the primary row-for-row" is **not accurate**. FE-01 records the precise delta instead. Whether the missing-vs-extra line should be kept, dropped, or otherwise reconciled is a preprocessing decision (PR-XX / FE-02) and is **not** resolved here.

## 13. Implications for the next stage (preprocessing)

FE-01 deliberately does **not** decide the preprocessing rules. The following implications are listed so the next stage has a single page to triage. Each item must be resolved by an ADR **before** it is implemented.

- `CustomerID` is missing in ≈ 24.93 % of rows. Decide: drop, impute (e.g. via invoice grouping heuristics), or model guests separately.
- Negative `Quantity` rows (≈ 10,624) coincide with `C`-prefixed `InvoiceNo` rows (≈ 9,288). Decide a unified cancellation rule.
- `UnitPrice` has 2,515 zero-valued rows and 2 negative-valued rows. Decide: drop, impute, or treat as a separate flag.
- `Description` has 1,454 missing rows. Decide whether to drop the affected lines, treat missing as a separate label, or ignore the column for the modelling matrix.
- `StockCode` is mostly numeric but contains alphanumeric codes (e.g. '85123A', 'POST', 'M'). Decide whether to keep them as strings or to special-case postage / manual entries.
- Backup dataset has different column names (`Invoice` / `Price` / `Customer ID`). A canonical rename map must be defined if the backup is ever loaded into the modelling pipeline.
- Decide a canonical reference date for RFM. The audit gives the raw max `InvoiceDate` so the choice can be made later without re-reading the data.
- Decide which duplicates to keep when (InvoiceNo, StockCode, Description, Quantity, InvoiceDate) coincide. The audit reports 5,427 such rows.

FE-01 finishes here. The next stage (FE-02 / PR-XX) takes these implications as input.