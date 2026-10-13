# Initial Data Profile — UCI Online Retail (Primary, FE-01)

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho tên cột, identifier, dtype, status, command theo
> convention hiện có. Mọi con số (row count, missing count/rate, range)
> truy xuất được về `reports/fe01/primary_*.csv` (xem cuối file).

Profile này tóm tắt raw primary dataset ở mức FE-01 yêu cầu. Mọi con số
được tính live từ raw data bởi
[`scripts/run_fe01_audit.py`](../../scripts/run_fe01_audit.py); không có
statistic nào được hard-code ở đây.

## 1. Tổng quan dataset

| Trường | Giá trị |
| --- | --- |
| Dataset name | UCI Online Retail |
| Vai trò | Primary |
| Local file | `data/raw/primary/Online Retail.xlsx` |
| Sheet name | `Online Retail` (trong tổng 1 sheet) |
| Total rows | **541,909** |
| Total columns | **8** |
| In-memory size (deep) | 132,310,571 bytes |
| Source | UCI Machine Learning Repository — dataset ID 352 |
| License | CC BY 4.0 |

## 2. Kích thước dataset

- Rows: **541,909**
- Columns: **8**

Cột (theo thứ tự):

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

**Hệ quả cho FE-02 / RFM.** Dataset bao trùm hơn một năm (tháng 12 năm
2010 – tháng 12 năm 2011). Reference date cho việc tính **Recency** phải
được chọn như một phần của stage RFM (FE-02 / PR-XX). Theo
`configs/features.yaml`, mode mặc định là `snapshot_max` (max
`InvoiceDate` + 1 day); FE-01 **không** sửa giá trị này.

## 4. Tổng quan cột

| Cột | dtype | Vai trò |
| --- | --- | --- |
| `InvoiceNo` | `object` | Identifier (transaction) |
| `StockCode` | `object` | Identifier (product) |
| `Description` | `object` | Categorical Feature (text) |
| `Quantity` | `int64` | Numerical Feature (transaction-line) |
| `InvoiceDate` | `datetime64[us]` | Date Feature (transaction) |
| `UnitPrice` | `float64` | Numerical Feature (transaction-line) |
| `CustomerID` | `float64` | Identifier (customer) |
| `Country` | `str` | Categorical Feature |

## 5. Profile missing-data

| Cột | Missing Count | Missing Rate (%) | Ghi chú |
| --- | ---: | ---: | --- |
| `CustomerID` | 135,080 | 24.9267 | Tỷ lệ lớn (~24.93%). Cần quyết định trong preprocessing. |
| `Description` | 1,454 | 0.2683 | Tỷ lệ nhỏ (~0.27%). Cần quyết định trong preprocessing. |
| `Country` | 0 | 0.0000 | — |
| `InvoiceDate` | 0 | 0.0000 | — |
| `InvoiceNo` | 0 | 0.0000 | — |
| `Quantity` | 0 | 0.0000 | — |
| `StockCode` | 0 | 0.0000 | — |
| `UnitPrice` | 0 | 0.0000 | — |

## 6. Profile numerical

| Cột | Count | Missing | Min | Max | Mean | Median | Std | Zero count | Negative count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Quantity` | 541,909 | 0 | -80995.0 | 80995.0 | 9.5522 | 3.0000 | 218.0812 | 0 | 10,624 |
| `UnitPrice` | 541,909 | 0 | -11062.06 | 38970.0 | 4.6111 | 2.0800 | 96.7599 | 2,515 | 2 |
| `CustomerID` | 406,829 | 135,080 | 12346.0 | 18287.0 | 15287.6906 | 15152.0000 | 1713.6003 | 0 | 0 |

## 7. Profile categorical

| Cột | Count | Missing | Unique | Top values (value:count) |
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

## 8. Profile identifier

| Cột | Total | Missing | Unique | Duplicate | Unique rate (%) | Is unique? |
| --- | ---: | ---: | ---: | ---: | ---: | :---: |
| `InvoiceNo` | 541,909 | 0 | 25,900 | 516,009 | 4.7794 | ❌ |
| `StockCode` | 541,909 | 0 | 4,070 | 537,839 | 0.7510 | ❌ |
| `CustomerID` | 541,909 | 135,080 | 4,372 | 402,457 | 1.0747 | ❌ |

### 8.1 `InvoiceNo` — scan tiền tố cancellation

- Giá trị có tiền tố `"C"`: **9,288** (1.7139 % trên `InvoiceNo` non-null).
- Ví dụ: `C536379`, `C536383`, `C536391`, `C536391`, `C536391`.

## 9. Profile transaction

Unit of observation là **transaction-line** (một row trên một sản phẩm
trong invoice). Modelling unit dự kiến là **customer**. Aggregation lên
customer-level **không** được thực hiện trong FE-01.

| Cấp | Cột | Count (distinct) |
| --- | --- | ---: |
| Invoice | `InvoiceNo` | 25,900 |
| Product (StockCode) | `StockCode` | 4,070 |
| Customer (CustomerID) | `CustomerID` | 4,372 |

**Cấu trúc invoice.** Cấp `(InvoiceNo, StockCode)` cho ra 531,225 tổ
hợp duy nhất trên tổng 541,909 row. Một invoice có nhiều row là điều
bình thường vì mỗi invoice chứa nhiều sản phẩm.

## 10. Profile duplicate

| Pattern | Duplicate rows |
| --- | ---: |
| Exact-row duplicates | 5,268 (0.9721%) |
| `(InvoiceNo, StockCode)`-key duplicates | 10,684 |
| `(InvoiceNo, StockCode, Description, Quantity, InvoiceDate)`-key duplicates | 5,427 |

## 11. Quan sát data-quality

Báo cáo đầy đủ:
[`reports/fe01/primary_data_quality_observations.md`](../../reports/fe01/primary_data_quality_observations.md).

# Primary Dataset — Data Quality Observations (FE-01)

Mọi con số dưới đây được tính live từ `data/raw/primary/Online Retail.xlsx`.
Tài liệu này là **read-only** observation report. Không row nào bị sửa,
không value nào bị impute, không record nào bị drop.

## 1. Top-level snapshot

- Rows: **541,909**
- Columns: **8**
- Columns: `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`,
  `UnitPrice`, `CustomerID`, `Country`

## 2. Missing values

| Cột | Missing count | Missing rate (%) |
| --- | ---: | ---: |
| `CustomerID` | 135,080 | 24.9267 |
| `Description` | 1,454 | 0.2683 |
| `Country` | 0 | 0.0000 |
| `InvoiceDate` | 0 | 0.0000 |
| `InvoiceNo` | 0 | 0.0000 |
| `Quantity` | 0 | 0.0000 |
| `StockCode` | 0 | 0.0000 |
| `UnitPrice` | 0 | 0.0000 |

**Quan sát.** Negative/zero value *không* được xử lý ở đây (xem mục 5);
missing-value policy thuộc preprocessing stage.

## 3. Identifiers

| Cột | Unique count | Duplicate count | Missing count | Is unique? |
| --- | ---: | ---: | ---: | :---: |
| `InvoiceNo` | 25,900 | 516,009 | 0 | ❌ |
| `StockCode` | 4,070 | 537,839 | 0 | ❌ |
| `CustomerID` | 4,372 | 402,457 | 135,080 | ❌ |

### 3.1 InvoiceNo — scan tiền tố cancellation

- Phát hiện **9,288** giá trị có tiền tố `"C"` (1.7139%).
- Ví dụ: `C536379`, `C536383`, `C536391`, `C536391`, `C536391`.

## 4. Duplicates

| Pattern | Duplicate rows |
| --- | ---: |
| Exact-row duplicates | 5,268 |
| `(InvoiceNo, StockCode)`-level duplicates | 10,684 |
| `(InvoiceNo, StockCode)`-level unique combinations | 531,225 |

**Quan sát.** Một `InvoiceNo` nhất định tự nhiên xuất hiện trên nhiều
row vì một invoice chứa nhiều sản phẩm. `InvoiceNo` duplicate **không
phải** data error; đó là cấu trúc của dữ liệu invoice-line.

## 5. Numerical anomalies (read-only)

| Cột | zero_count | negative_count | min | max |
| --- | ---: | ---: | ---: | ---: |
| `Quantity` | 0 | 10,624 | -80995.0 | 80995.0 |
| `UnitPrice` | 2,515 | 2 | -11062.06 | 38970.0 |
| `CustomerID` | 0 | 0 | 12346.0 | 18287.0 |

**Quan sát.** Negative quantity / unit price và zero value được ghi ở
đây **mà không có bất kỳ policy decision nào**. Chúng được đánh dấu
cho preprocessing stage.

## 6. Date coverage

- Parsed rows: **541,909 / 541,909**
- Unparseable rows: **0**
- Min: `2010-12-01T08:26:00`
- Max: `2011-12-09T12:50:00`
- Row chia sẻ timestamp với row khác: **537,667** (expected — nhiều
  sản phẩm có thể được mua cùng một thời điểm).

## 12. So sánh schema Primary vs Backup

### 12.1 Tổng quan Backup

| Sheet | Rows | Columns | Date min | Date max |
| --- | ---: | ---: | --- | --- |
| `Year 2009-2010` | 525,461 | 8 | 2009-12-01T07:45:00 | 2010-12-09T20:01:00 |
| `Year 2010-2011` | 541,910 | 8 | 2010-12-01T08:26:00 | 2011-12-09T12:50:00 |

### 12.2 Khác biệt tên cột

Backup dùng **tên cột khác** so với primary. Các logical concept chung
được liệt kê dưới đây.

| Logical concept | Primary column | Backup column | Backup dtype khớp primary? |
| --- | --- | --- | :---: |
| Invoice number | `InvoiceNo` | `Invoice` | ❌ |
| Product code | `StockCode` | `StockCode` | ✅ |
| Description | `Description` | `Description` | ✅ |
| Quantity | `Quantity` | `Quantity` | ✅ |
| Invoice date | `InvoiceDate` | `InvoiceDate` | ✅ |
| Unit price | `UnitPrice` | `Price` | ❌ |
| Customer id | `CustomerID` | `Customer ID` | ❌ |
| Country | `Country` | `Country` | ✅ |

### 12.3 Coverage và khác biệt row-level

- Primary bao trùm **2010-12-01 → 2011-12-09** (≈ 1 năm). Sheet backup
  `Year 2010-2011` bao trùm cùng cửa sổ ngày.
- Sheet backup `Year 2009-2010` mở rộng time coverage thêm **một năm**
  (2009-12-01 → 2010-12-09). Đây là lý do chính backup được giữ làm
  robustness / coverage fallback.
- Hai dataset dùng **tên cột khác nhau** cho invoice number, unit price,
  và customer id (xem 12.2). Bất kỳ code nào consume cả hai phải áp
  dụng rename map ở loader layer (task PR-XX).

### 12.4 So sánh row-level (Primary vs Backup `Year 2010-2011`)

- Primary rows: **541,909**. Backup `Year 2010-2011` rows: **541,910**
  (delta **+1**).
- So sánh theo join key `(InvoiceNo, StockCode, InvoiceDate)`:
  **531,232** row hiện diện ở cả hai; **0** row chỉ ở primary; **1**
  row chỉ ở backup.
- Row thừa duy nhất ở backup là: `InvoiceNo=581587`, `StockCode=POST`,
  `InvoiceDate=2011-12-09 12:50:00`. Sau khi rename `Invoice→InvoiceNo`,
  `Price→UnitPrice`, `Customer ID→CustomerID`, row này tương ứng với
  một dòng `POSTAGE` duy nhất cho `CustomerID=12680` (country: France).
- **Hệ quả**: claim "khớp primary row-for-row" là **không chính xác**.
  FE-01 ghi lại delta chính xác thay vào đó. Việc missing-vs-extra line
  nên được keep, drop, hoặc reconcile là quyết định preprocessing
  (PR-XX / FE-02) và **không** được giải quyết ở đây.

## 13. Hệ quả cho stage tiếp theo (preprocessing)

FE-01 cố ý **không** quyết định preprocessing rule. Các hệ quả sau được
liệt kê để stage tiếp theo có một trang duy nhất để triage. Mỗi mục
phải được giải quyết bằng một ADR **trước khi** implement.

- `CustomerID` missing ở ≈ 24.93 % row. Quyết định: drop, impute (vd.
  qua invoice grouping heuristics), hoặc model guest riêng.
- Negative `Quantity` row (≈ 10,624) trùng với row `C`-prefixed
  `InvoiceNo` (≈ 9,288). Quyết định một cancellation rule thống nhất.
- `UnitPrice` có 2,515 row zero-value và 2 row negative-value. Quyết
  định: drop, impute, hoặc xem như một flag riêng.
- `Description` có 1,454 row missing. Quyết định drop các line bị ảnh
  hưởng, treat missing như một label riêng, hoặc bỏ qua cột cho
  modelling matrix.
- `StockCode` phần lớn là numeric nhưng chứa code alphanumeric (vd.
  '85123A', 'POST', 'M'). Quyết định giữ chúng dưới dạng string hay
  special-case postage / manual entry.
- Dataset backup có tên cột khác (`Invoice` / `Price` / `Customer ID`).
  Một canonical rename map phải được định nghĩa nếu backup từng được
  load vào modelling pipeline.
- Quyết định canonical reference date cho RFM. Audit đưa ra raw max
  `InvoiceDate` để choice có thể được đưa ra sau mà không cần đọc lại
  data.
- Quyết định duplicate nào được giữ khi `(InvoiceNo, StockCode,
  Description, Quantity, InvoiceDate)` trùng nhau. Audit báo cáo
  5,427 row như vậy.

FE-01 kết thúc tại đây. Stage tiếp theo (FE-02 / PR-XX) lấy các hệ quả
này làm input.
