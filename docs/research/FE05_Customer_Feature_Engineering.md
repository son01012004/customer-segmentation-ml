# FE-05 — Customer Feature Engineering & Selection: Lý thuyết và Kết quả thực hiện

> **Tài liệu cho mentor review.**
> Phiên bản: FE-05 (Feature Engineering & Feature Selection).
> Mọi số liệu trong tài liệu này được lấy trực tiếp từ `reports/fe05/` và `data/processed/customer_candidates.parquet` (sinh từ execution thực tế).
> Tài liệu KHÔNG mô tả cách cài đặt hay hướng dẫn sử dụng code; KHÔNG thay thế `reports/fe05/narrative_report.md` (báo cáo vận hành).

---

## 1. Tổng quan FE-05

### 1.1. Mục tiêu

FE-05 xây dựng **customer-level feature space** cho bài toán customer segmentation. Từ customer-level base dataset (`customer_base.parquet` của FE-04) và transaction-level cleaned data (`transactions_clean.parquet` của FE-02), FE-05:

1. Tính toán các **candidate features** thuộc nhiều nhóm: RFM (Recency, Frequency, Monetary), transaction behavior (TenureDays, PurchaseIntervalMean/Std, ActiveDays, AverageQuantity, BasketSize, AverageInvoiceValue), diversity (ProductsPerInvoice), và cancellation/return (CancellationRate, ReturnRate).
2. Thực hiện **analysis** (distribution, variance, correlation, redundancy, outlier) trên các candidate features.
3. Áp dụng **evidence-based feature selection gates** để phân loại mỗi feature vào một decision: `RETAIN_CANDIDATE`, `PENDING_REVIEW`, hoặc `UNSUPPORTED`.
4. Tạo **candidate dataset** (`customer_candidates.parquet`) phục vụ FE-06 transformation/scaling.

### 1.2. Input từ FE-04 và FE-02

| Input | Path | Vai trò |
|---|---|---|
| Customer-level base | `data/processed/customer_base.parquet` | CustomerID, base reference features (TotalQuantity, TotalMonetary, PurchaseFrequency, AverageTransactionValue, dates, counts) |
| Transaction-level cleaned | `data/processed/transactions_clean.parquet` | Nguồn tính PurchaseIntervalMean/Std (cần invoice-level ordering), diversity checks |

Input SHA-256 (`fe05_run.json`):
- `customer_base.parquet`: `ae5508624e3501b1252014e3187cfe20aedb53040761aaef2f7b99ae0d434d1a`
- `transactions_clean.parquet`: `08b8107573654fa2bd198904d00c6aeaa9f34d9ab3026bd4335f72d4b6903415`
- SHA-256 unchanged sau FE-05: `true`

### 1.3. Output của FE-05

| Output | Path | Mô tả |
|---|---|---|
| Candidate dataset | `data/processed/customer_candidates.parquet` | 4,371 customers × 14 candidate features + CustomerID |
| SHA-256 | `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649` | |
| Feature dictionary | `reports/fe05/feature_dictionary.csv` | Layer, role, status, mô tả từng feature |
| Feature selection | `reports/fe05/feature_selection_report.csv` | Decision `RETAIN_CANDIDATE` / `PENDING_REVIEW` / `UNSUPPORTED` + gate status |
| RFM report | `reports/fe05/rfm_report.md` | ReferenceDate, recency stats, monetary variants comparison |
| Frequency variants | `reports/fe05/frequency_variants_comparison.csv` | FREQ-01 vs FREQ-02 |
| Monetary variants | `reports/fe05/monetary_definition_comparison.csv` | 4 variants: Signed, Absolute, PurchaseOnly, CancellationOnly |
| Quantity variants | `reports/fe05/quantity_variants_comparison.csv` | Signed vs PurchaseOnly |
| Distribution analysis | `reports/fe05/distribution_analysis.csv` | Count, Mean, Std, Min, Q25, Q50, Q75, Max, Skewness, Kurtosis, Missing |
| Variance analysis | `reports/fe05/variance_analysis.csv` | Count, Mean, Std, Variance, CV |
| Correlation matrices | `reports/fe05/correlation_matrix_pearson.csv`, `correlation_matrix_spearman.csv` | Pearson + Spearman correlation |
| Redundancy report | `reports/fe05/redundancy_report.csv` | Cặp features có correlation cao |
| Outlier detection | `reports/fe05/outlier_detection.csv` | IQR-based outlier detection |
| Business interpretability | `reports/fe05/business_interpretability.csv` | Business meaning check |

### 1.4. Vai trò của feature engineering trong customer segmentation

Customer segmentation cần một **feature vector** cho mỗi khách hàng phản ánh hành vi mua hàng. Các feature "thô" từ FE-04 (TotalQuantity, TotalMonetary, PurchaseFrequency, ...) chỉ là baseline. Để phân cụm có ý nghĩa, cần bổ sung:

- **RFM** — ba trụ cột phổ biến nhất trong phân tích khách hàng (Recency, Frequency, Monetary).
- **Behavioral features** — phản ánh thói quen mua (khoảng cách giữa các giao dịch, số ngày hoạt động, số sản phẩm trung bình mỗi hóa đơn).
- **Diversity features** — phản ánh sự đa dạng sản phẩm khách hàng tương tác.
- **Cancellation/return features** — phản ánh hành vi hủy/trả hàng.

### 1.5. Vì sao customer-level base features (FE-04) chưa nhất thiết là clustering-ready features

Một số lý do:

1. **Chưa có Recency** — FE-04 chỉ cung cấp `LastPurchaseDate` (raw date); Recency (số ngày từ lần mua cuối đến thời điểm tham chiếu) là feature time-aware cần được tính riêng.
2. **Frequency chưa được quyết định** — FE-04 dùng `PurchaseFrequency = DistinctInvoiceCount` như working proxy; FE-05 phải so sánh với variants khác (e.g., transaction-line count).
3. **Monetary semantics chưa được quyết** — FE-04 giữ signed baseline; FE-05 phải đánh giá 4 variants (signed, absolute, purchase-only, cancellation-only).
4. **Chưa có behavioral features** — TenureDays, PurchaseIntervalMean/Std, ActiveDays, AverageInvoiceValue, Quantity per basket đều cần được derive từ customer-level data.
5. **Chưa có rate features** — CancellationRate, ReturnRate cần denominator (Frequency).
6. **Chưa có feature selection** — không phải feature nào cũng phù hợp làm clustering input.

FE-05 đóng vai trò cầu nối giữa "baseline aggregate" của FE-04 và "clustering input" của FE-06.

### 1.6. Sơ đồ pipeline FE-05

```
FE-04 Customer Base (customer_base.parquet)
        ↓
        +
FE-02 Cleaned Transactions (transactions_clean.parquet)
        ↓
Feature Construction
        ↓
RFM (Recency, Frequency, Monetary + variants)
        ↓
Transaction Behavior (TenureDays, PurchaseInterval*, ActiveDays,
                      AverageQuantity, BasketSize, AverageInvoiceValue)
        ↓
Diversity (ProductsPerInvoice)
        ↓
Cancellation / Return (CancellationRate, ReturnRate)
        ↓
Candidate Feature Analysis
(distribution, variance, correlation, redundancy, outlier)
        ↓
Feature Selection / Decision
(RETAIN_CANDIDATE / PENDING_REVIEW / UNSUPPORTED)
        ↓
customer_candidates.parquet
```

---

## 2. Cơ sở lý thuyết về Customer Feature Engineering

### 2.1. Feature engineering

**Feature engineering** là quá trình biến dữ liệu thô thành các biến (features) phù hợp với mô hình phân tích. Trong machine learning nói chung và clustering nói riêng, chất lượng feature thường quan trọng hơn thuật toán. Một feature tốt cần:

- **Có business meaning**: phản ánh hành vi thực tế của khách hàng.
- **Có giá trị phân biệt**: phân tách được các nhóm khách hàng khác nhau.
- **Không leak target**: không dùng thông tin chưa có tại thời điểm dự đoán.

### 2.2. Behavioral representation

Mỗi khách hàng được biểu diễn bằng một **vector hành vi** (behavioral vector) gồm nhiều chiều, mỗi chiều là một khía cạnh hành vi (tần suất, giá trị, sản phẩm, thời gian, ...). Lịch sử giao dịch của khách hàng được "nén" thành vector cố định chiều này thông qua aggregation (FE-04) và feature construction (FE-05).

### 2.3. Customer-level feature vector

Trong toán học, customer-level feature space là một ma trận `X ∈ R^(n_customers × n_features)`. Mỗi dòng `x_i` là một vector đặc trưng của khách hàng `i`. Các thuật toán clustering (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means) sẽ dùng khoảng cách giữa các vector `x_i`, `x_j` để phân nhóm.

Điều này đặt ra hai yêu cầu:

1. **Số chiều phải cố định** cho mọi khách hàng → đã đảm bảo bởi customer-level aggregation.
2. **Các chiều phải so sánh được** → yêu cầu scaling/transformation (FE-06).

### 2.4. RFM framework

RFM là framework phổ biến nhất trong phân tích khách hàng:

- **Recency (R)**: Số ngày từ lần mua cuối đến thời điểm tham chiếu. Khách hàng mua gần đây thường có giá trị cao hơn.
- **Frequency (F)**: Số lần mua trong một khoảng thời gian. Phản ánh lòng trung thành.
- **Monetary (M)**: Tổng giá trị mua. Phản ánh quy mô đóng góp doanh thu.

FE-05 materialize RFM theo cách:

- **Recency**: tính từ `LastPurchaseDate` (FE-04) và `ReferenceDate` (FE-05 tự sở hữu).
- **Frequency**: so sánh 2 variants (`by_invoice` vs `by_transaction_line`), materialize ONE (default `by_invoice`).
- **Monetary**: so sánh 4 variants, materialize ONE (default `MonetarySigned`).

### 2.5. Transaction behavior

Là các feature phản ánh **nhịp độ và đặc điểm giao dịch** của khách hàng:

- **TenureDays**: số ngày từ lần mua đầu đến lần mua cuối (độ dài quan hệ).
- **PurchaseIntervalMean**: trung bình khoảng cách giữa các hóa đơn (NaN nếu < 2 invoices).
- **PurchaseIntervalStd**: độ biến động của khoảng cách (NaN nếu < 2 invoices, `ddof=1`).
- **ActiveDays**: số ngày lịch duy nhất có giao dịch (calendar day count, không phải raw datetime).
- **AverageQuantity / BasketSize**: trung bình số lượng mỗi hóa đơn (signed).
- **AverageInvoiceValue**: Monetary / Frequency (FE-05 candidate mới; **khác** với `AverageTransactionValue` của FE-04).

### 2.6. Purchase frequency

"Frequency" trong RFM không có định nghĩa duy nhất. Hai cách phổ biến:

- **`by_invoice` (FREQ-01)**: đếm số hóa đơn duy nhất — phản ánh "số lần khách hàng ghé mua".
- **`by_transaction_line` (FREQ-02)**: đếm số dòng transaction-line — phản ánh "số sản phẩm được mua tổng cộng".

Hai cách cho kết quả khác nhau: khách hàng mua 1 hóa đơn có 5 sản phẩm sẽ có `FREQ-01 = 1` và `FREQ-02 = 5`. FE-05 materialize FREQ-01 theo default nhưng ghi nhận cả hai để review.

### 2.7. Monetary value

"Monetary" trong RFM cũng có nhiều cách định nghĩa. FE-05 so sánh 4 variants:

| Variant | Định nghĩa | Ý nghĩa |
|---|---|---|
| `MonetarySigned` | `sum(LineRevenue)` với cả cancellation/return | Baseline trung thực: cancellation/return làm giảm tổng |
| `MonetaryAbsolute` | `sum(|LineRevenue|)` | Bỏ qua dấu: cancellation/return vẫn tính là giá trị dương |
| `MonetaryPurchaseOnly` | `sum(LineRevenue)` với `IsCancellation = False` | Chỉ tính giao dịch mua thật |
| `MonetaryCancellationOnly` | `sum(LineRevenue)` với `IsCancellation = True` | Tổng giá trị bị hủy (thường âm) |

FE-05 materialize `MonetarySigned` theo default.

### 2.8. Recency

Recency = `ReferenceDate - LastPurchaseDate` (tính theo ngày). FE-05 sở hữu ReferenceDate với công thức:

```
ReferenceDate = max(InvoiceDate) + 1 day
```

Đây là **strategy `snapshot_max`** — coi thời điểm "hiện tại" là ngày sau ngày giao dịch cuối cùng của toàn bộ dataset. Cách này deterministic (luôn cho ra cùng giá trị khi re-run) và thường dùng trong research với historical data.

FE-05 Recency **bao gồm** cả cancellation/return rows (vì LastPurchaseDate từ FE-04 tính trên tất cả rows). Variant "purchase-only Recency" được ghi nhận là PENDING_REVIEW.

### 2.9. Purchase interval

`PurchaseIntervalMean` và `PurchaseIntervalStd` đo **độ đều đặn** trong hành vi mua:

- Customer mua đều đặn hàng tuần → mean thấp, std thấp.
- Customer mua bất thường → mean có thể cao, std cao.

Cả hai đều **NaN nếu khách hàng có < 2 invoices** (vì cần ít nhất 2 invoices để có 1 interval). Giá trị NaN KHÔNG được fill bằng 0 — đây là quyết định có chủ đích trong implementation.

### 2.10. Product diversity

Diversity phản ánh khách hàng mua **nhiều loại sản phẩm khác nhau** hay **tập trung vào một vài sản phẩm**. Dataset này **không có official taxonomy cho category** (chỉ có `StockCode` ở mức sản phẩm), nên:

- `CategoryCount` được đánh dấu **UNSUPPORTED**, KHÔNG materialize.
- `ProductsPerInvoice` (DistinctProducts / DistinctInvoiceCount) là **ratio proxy**, không phải diversity metric chuẩn.

### 2.11. Cancellation/return behavior

`CancellationRate = CancellationInvoiceCount / Frequency` và `ReturnRate = ReturnInvoiceCount / Frequency`. Rate thay vì count để chuẩn hóa theo quy mô mua của từng khách hàng. Tuy nhiên, **denominator semantics** vẫn còn pending (Frequency đã chọn `by_invoice` nhưng nếu FE-05 đổi sang variant khác, các rate này sẽ thay đổi).

---

## 3. Thiết kế RFM

### 3.1. Recency

**Định nghĩa:** `Recency = (ReferenceDate - LastPurchaseDate).days`

**Cách tính trong implementation:**

1. FE-05 đọc `transactions_clean.parquet` để tính `ReferenceDate = max(InvoiceDate) + 1 day`.
2. FE-05 đọc `customer_base.parquet` lấy `LastPurchaseDate`.
3. `Recency` (in days) được tính cho từng customer.

**ReferenceDate (FE-05 sở hữu):**

- Công thức: `max(InvoiceDate) + 1 day`
- Computed: `2011-12-10T12:50:00`
- Strategy: `snapshot_max` (deterministic)
- Status: `WORKING_ASSUMPTION`, review: `MENTOR_REVIEW_PENDING`
- FE-06 KHÔNG được recompute ReferenceDate — FE-05 là single source of truth.

**Thống kê (rfm_report.md):**

- Count: 4,371
- Mean: 92.60 days
- Std: 100.78 days
- Min: 1 day
- Max: 374 days
- Bao gồm tất cả transactions (cancellation/return included).

**Limitations:**

- `Recency` hiện tại dùng `LastPurchaseDate` (FE-04) — đây là "ngày cuối cùng có transaction" của customer. Nếu lần cuối chỉ là cancellation/return, Recency có thể underestimate "thời gian kể từ lần mua thật". PENDING_REVIEW cho variant "purchase-only Recency".

### 3.2. Frequency

**Định nghĩa:** số lần khách hàng thực hiện giao dịch.

**Vì sao cần được định nghĩa rõ trong dữ liệu transaction:**

Trong data transaction-level, mỗi dòng là một **line item** (sản phẩm) thuộc một **invoice** (hóa đơn). Một khách hàng có thể có:
- 1 invoice chứa 5 line items (5 sản phẩm khác nhau).
- 5 invoices chứa 1 line item mỗi cái.

Vậy "số lần mua" có thể đếm theo invoice (5 vs 1) hoặc theo line item (5 vs 5). Hai cách cho ra câu trả lời khác nhau tùy dataset. Vì vậy Frequency cần một **định nghĩa rõ ràng** trước khi dùng làm clustering feature.

**Các candidate/definition thực tế đã xem xét trong FE-05:**

| Variant | Công thức | Ý nghĩa | Status |
|---|---|---|---|
| `FREQ-01: by_invoice` | `nunique(InvoiceNo)` | Số hóa đơn duy nhất | **Materialized (default)** |
| `FREQ-02: by_transaction_line` | `count(InvoiceNo)` (line count) | Số dòng transaction-line | Comparison only |

**Thống kê FE-05 (`frequency_variants_comparison.csv`):**

- `FREQ-01`: mean 5.08, max 248
- `FREQ-02`: phân phối rộng hơn nhiều (mean có thể lên tới hàng nghìn cho khách mua nhiều sản phẩm)
- Hai variants cho kết quả khác nhau rõ rệt.

### 3.3. Monetary

**Định nghĩa:** tổng giá trị giao dịch của khách hàng.

**Các monetary variants thực tế trong FE-05 (experimental candidates):**

| Variant | Công thức | Baseline | Status |
|---|---|---|---|
| `MonetarySigned` | `sum(LineRevenue)` bao gồm cancellation/return | Signed (cancellation/return làm giảm) | **Materialized (default)** |
| `MonetaryAbsolute` | `sum(\|LineRevenue\|)` | Absolute value (bỏ qua dấu) | Comparison |
| `MonetaryPurchaseOnly` | `sum(LineRevenue)` với `IsCancellation=False` | Chỉ mua thật | Comparison |
| `MonetaryCancellationOnly` | `sum(LineRevenue)` với `IsCancellation=True` | Chỉ hủy | Comparison |

**Thống kê FE-05 (rfm_report.md):**

- Count: 4,371
- Mean: 1,893.96
- Min: -4,287.63 (signed variant có giá trị âm)
- Max: 279,489.02

Đây là **experimental candidates**. FE-05 không tự chọn "best variant" mà để report đầy đủ cho mentor. Materialization chỉ là default cho downstream pipeline (FE-06).

---

## 4. Transaction Behavior Features

### 4.1. Tổng quan

Transaction behavior features phản ánh **cách khách hàng mua hàng** (frequency pattern, basket characteristics, value per transaction). Tất cả được định nghĩa trong `configs/feature_engineering.yaml`.

### 4.2. Bảng các feature

| Feature | Định nghĩa | Cách tính | Business interpretation | Data limitations |
|---|---|---|---|---|
| `TotalQuantity` | Tổng số lượng sản phẩm đã mua (signed) | `sum(Quantity)` (từ FE-04) | Quy mô giao dịch tổng thể; signed baseline | Có thể âm với cancellation; default variant |
| `AverageQuantity` | Trung bình số lượng / invoice (signed) | `TotalQuantity / DistinctInvoiceCount` | Quy mô giỏ hàng trung bình | NaN/div nếu DistinctInvoiceCount = 0; signed |
| `BasketSize` | Alias cho `AverageQuantity` (signed) | Giống AverageQuantity | Cùng semantic; alias cho dễ đọc | Identical to AverageQuantity (correlation = 1.0) |
| `TenureDays` | Số ngày từ FirstPurchaseDate đến LastPurchaseDate | `LastPurchaseDate - FirstPurchaseDate` | Độ dài quan hệ khách hàng-cửa hàng | Inclusive cancellation/return; Min = 0 |
| `PurchaseIntervalMean` | Mean days giữa các invoice liên tiếp | `diff(invoice_dates).mean()` | Tần suất trung bình | NaN nếu < 2 invoices |
| `PurchaseIntervalStd` | Std (ddof=1) của days giữa các invoice | `diff(invoice_dates).std(ddof=1)` | Độ đều đặn | NaN nếu < 2 invoices; 1,312 missing values |
| `ActiveDays` | Số ngày lịch duy nhất có transaction | `dt.date.nunique()` | Mức độ "spread" của hoạt động | Calendar day (not raw datetime) |
| `AverageInvoiceValue` | Avg monetary / invoice | `Monetary / Frequency` | Giá trị trung bình mỗi lần mua | Denominator = Frequency variant đã chọn |

### 4.3. Lưu ý về `AverageTransactionValue` (FE-04) vs `AverageInvoiceValue` (FE-05)

Hai feature có semantic gần giống nhau nhưng **khác phase** và có thể khác giá trị:

| | FE-04 `AverageTransactionValue` | FE-05 `AverageInvoiceValue` |
|---|---|---|
| Numerator | `TotalMonetary` (FE-04, signed baseline) | `Monetary` (FE-05, MonetarySigned) |
| Denominator | `DistinctInvoiceCount` (FE-04 baseline) | `Frequency` (FE-05, FREQ-01 = `by_invoice`) |
| Giá trị | Nếu FE-05 giữa Monetary = TotalMonetary và Frequency = DistinctInvoiceCount | thì hai giá trị trùng nhau |

Trong implementation hiện tại của FE-05:
- `Monetary = MonetarySigned = TotalMonetary` (cùng giá trị, vì cùng dùng signed baseline).
- `Frequency = DistinctInvoiceCount` (vì `by_invoice` materialized).

→ Trong execution này, **`AverageTransactionValue (FE-04) == AverageInvoiceValue (FE-05)`** về giá trị. Tuy nhiên, chúng thuộc hai layer khác nhau:
- `AverageTransactionValue` là **BASE_REFERENCE** (giữ từ FE-04, không phải candidate mới).
- `AverageInvoiceValue` là **CANDIDATE** (FE-05 engineering mới).

Sự phân biệt này quan trọng vì nếu FE-05 sau này đổi Frequency variant, `AverageInvoiceValue` sẽ thay đổi còn `AverageTransactionValue` vẫn giữ giá trị FE-04.

---

## 5. Diversity Features

### 5.1. Tổng quan

Diversity features phản ánh **mức độ đa dạng sản phẩm** khách hàng tương tác. Dataset này có `StockCode` (mã sản phẩm) và `Description` (tên sản phẩm) nhưng **không có official taxonomy** (category hierarchy).

### 5.2. DistinctProducts (BASE_REFERENCE, từ FE-04)

- Số sản phẩm duy nhất khách hàng đã mua.
- Tính bằng `nunique(StockCode)`.
- Mean: 61.22, Median: 35 (từ FE-04 summary).

### 5.3. ProductsPerInvoice (CANDIDATE)

- Công thức: `DistinctProducts / DistinctInvoiceCount`
- Phân loại: **ratio proxy** (không phải diversity metric chuẩn).
- Đã được ghi rõ trong implementation (docstring): "Ratio proxy for product diversity. Not a standard diversity metric."
- Status: `WORKING_ASSUMPTION` (vì là ratio proxy).

### 5.4. CategoryCount (UNSUPPORTED, không materialize)

- **Không được materialize.**
- Lý do: dataset không có official taxonomy (chỉ có `StockCode` mức sản phẩm, không có category hierarchy).
- Nếu muốn diversity ở cấp category, cần taxonomy từ nguồn bên ngoài — chưa có.

---

## 6. Cancellation / Return Features

### 6.1. Cancellation

- `CancellationInvoiceCount` (FE-04, BASE_REFERENCE): số hóa đơn cancellation duy nhất (`nunique(InvoiceNo)` trên subset `IsCancellation = True`).
- `CancellationRate` (FE-05, CANDIDATE): `CancellationInvoiceCount / Frequency`.

### 6.2. Return

- `ReturnInvoiceCount` (FE-04, BASE_REFERENCE): số hóa đơn return duy nhất.
- `ReturnRate` (FE-05, CANDIDATE): `ReturnInvoiceCount / Frequency`.

### 6.3. Denominator

`Frequency` (FE-05 materialized variant `by_invoice`) làm denominator cho cả `CancellationRate` và `ReturnRate`. Vì Frequency là `nunique(InvoiceNo)` nên:

- CancellationRate = số hóa đơn hủy / tổng số hóa đơn (bao gồm cả hóa đơn hủy).
- ReturnRate tương tự.

### 6.4. Semantics trong implementation

Trong dataset hiện tại, `CancellationInvoiceCount == ReturnInvoiceCount` cho mọi customer (do flag `IsCancellation` và `IsReturn` có giá trị giống nhau trên data). Do đó:

- `CancellationRate == ReturnRate` distribution giống hệt nhau (correlation = 1.0, redundancy_report.csv).
- Mean 0.11, Median 0 (distribution_analysis.csv).

Đây là **observation của dataset hiện tại**, không phải universal rule. Nếu FE-02 flag thay đổi, hai rate có thể khác nhau.

### 6.5. Pending semantics

Các điểm sau vẫn **PENDING_REVIEW**:

- Cancellation/return treatment cho Monetary (signed, absolute, purchase-only).
- Denominator semantics (Frequency variant).
- Có nên giữ riêng CancellationRate/ReturnRate như candidate features, hay tính vào RFM?

---

## 7. Feature Analysis

FE-05 thực hiện analysis toàn diện trên các candidate features trước khi đưa vào selection. Mục đích: cung cấp evidence cho mentor quyết định, KHÔNG tự động drop hay rank.

### 7.1. Distribution analysis (`distribution_analysis.csv`)

Mỗi candidate feature được mô tả bằng: Count, Mean, Std, Min, Q25, Q50, Q75, Max, Skewness, Kurtosis, Missing, MissingRatio.

Ví dụ (`Recency`):

| Metric | Value |
|---|---|
| Count | 4,371 |
| Mean | 92.60 |
| Std | 100.78 |
| Min | 1 |
| Q25 | 17 |
| Median | 51 |
| Q75 | 144 |
| Max | 374 |
| Skewness | 1.249 |
| Missing | 0 |

`PurchaseIntervalMean` (3,059 count, 1,312 missing = 30.0% missing ratio): missing vì khách hàng có < 2 invoices không thể tính interval.

`PurchaseIntervalStd` (2,242 count, 2,129 missing = 48.7% missing ratio): tương tự.

`Monetary` có skewness 21.7, kurtosis 607 — heavily right-skewed (long-tail distribution, một số khách hàng chi tiêu rất lớn). Đây là expected cho retail data và là lý do cần transformation (FE-06).

### 7.2. Variance analysis (`variance_analysis.csv`)

Mỗi feature có Count, Mean, Std, Variance, CV (coefficient of variation). Tất cả 14 candidate features có `CV_Status = "valid"` (không feature nào có variance = 0).

### 7.3. Missing values

- `PurchaseIntervalMean`: 1,312 missing (30.0%) — vì < 2 invoices.
- `PurchaseIntervalStd`: 2,129 missing (48.7%) — vì < 2 invoices.
- Tất cả features khác: 0 missing.

Missing policy: NaN KHÔNG được fill bằng 0 (cố ý). NaN phản ánh "không tính được" — một customer chỉ mua 1 lần thực sự không có "interval trung bình". Đây là thông tin có giá trị phân biệt.

### 7.4. Correlation analysis

Hai ma trận: Pearson (`correlation_matrix_pearson.csv`) và Spearman (`correlation_matrix_spearman.csv`). Correlation chỉ tính trên **numeric Tầng 2 CANDIDATE features** (date features excluded, BASE_REFERENCE excluded).

### 7.5. Redundancy analysis (`redundancy_report.csv`)

Threshold Pearson ≥ 0.95. Các cặp redundant:

| Feature1 | Feature2 | Correlation |
|---|---|---|
| `AverageQuantity` | `BasketSize` | 1.0 |
| `CancellationRate` | `ReturnRate` | 1.0 |
| `Frequency` | `ActiveDays` | 0.974 |

**Phân biệt:**

- **Correlation ≠ duplicate**: hai feature có correlation = 1 chưa chắc là duplicate về ngữ nghĩa. `AverageQuantity` và `BasketSize` có cùng giá trị số (vì cùng công thức), có thể coi là **mathematical identity** — đây là định danh, không phải feature semantic trùng.
- **Redundancy ≠ mathematical identity**: `Frequency` và `ActiveDays` correlation 0.974 vì hai biến cùng tăng khi khách hàng mua nhiều, nhưng semantics khác nhau (Frequency = distinct invoices; ActiveDays = distinct calendar days). Đây là redundancy (cùng thông tin), không phải mathematical identity.

### 7.6. Outlier analysis (`outlier_detection.csv`)

IQR-based outlier detection cho mỗi candidate feature. Cung cấp evidence cho FE-06 về việc có nên winsorize/clip/transform không.

### 7.7. Interpretability & leakage

- `interpretability_gate`: tất cả features PASS — đều có business meaning rõ ràng.
- `leakage_gate`: tất cả features PASS — không leak target information (vì clustering không có target).

### 7.8. Stability & Shapiro-Wilk (diagnostic only)

- `stability_gate`: DIAGNOSTIC_ONLY (không ảnh hưởng quyết định).
- `shapiro_wilk_gate`: DIAGNOSTIC_ONLY (optional, không tự động KEEP/DROP).

Không feature nào được drop dựa trên normality test.

---

## 8. Feature Selection Framework

### 8.1. Triết lý

FE-05 **KHÔNG dùng một điểm số tổng hợp** (numerical score/rank/weight) để chọn feature. Việc tạo điểm số tổng hợp sẽ tự ý coi một số feature "quan trọng hơn" feature khác mà không có cơ sở methodology.

Thay vào đó, FE-05 dùng **evidence-based gates** (cổng dựa trên bằng chứng), mỗi gate trả lời một câu hỏi có/không cho feature:

| Gate | Câu hỏi | Status |
|---|---|---|
| Interpretability | Feature có business meaning rõ ràng? | Required |
| Data Quality | Missing ratio ≤ 50%? | Required (max_missing_ratio = 0.5) |
| Leakage | Feature có leak target? | Required |
| Zero Variance | Feature có variance > 0? | Required |
| Redundancy | Correlation với feature khác ≥ 0.95? | Diagnostic only |
| Stability | Feature ổn định qua bootstrap? | Diagnostic only |
| Shapiro-Wilk | Distribution normal? | Optional diagnostic only |

### 8.2. Các trạng thái decision

| Decision | Ý nghĩa |
|---|---|
| `RETAIN_CANDIDATE` | Qua tất cả required gates; eligible cho FE-06 |
| `EXCLUDE` | Không qua một required gate; không phù hợp |
| `ADJUST` | Cần điều chỉnh definition |
| `PENDING_REVIEW` | Decision phụ thuộc vào mentor (mentor review pending) |
| `UNSUPPORTED` | Không materialize vì dataset thiếu (e.g., CategoryCount) |

### 8.3. Kết quả selection (`feature_selection_report.csv`)

Tổng kết (`fe05_run.json`):

| Decision | Count |
|---|---|
| `RETAIN_CANDIDATE` | 8 |
| `EXCLUDE` | 0 |
| `ADJUST` | 0 |
| `PENDING_REVIEW` | 6 |
| `UNSUPPORTED` | 1 |

**RETAIN_CANDIDATE (8 features):**

- `Recency`
- `Monetary`
- `TotalQuantity`
- `TenureDays`
- `PurchaseIntervalMean`
- `PurchaseIntervalStd`
- `AverageInvoiceValue`
- `ProductsPerInvoice`

**PENDING_REVIEW (6 features):**

- `Frequency` (mentor review default variant)
- `ActiveDays` (correlation với Frequency = 0.974)
- `AverageQuantity` (correlation = 1.0 với BasketSize)
- `BasketSize` (correlation = 1.0 với AverageQuantity)
- `CancellationRate` (correlation = 1.0 với ReturnRate)
- `ReturnRate` (correlation = 1.0 với CancellationRate)

**UNSUPPORTED (1 feature):**

- `CategoryCount` (dataset lacks official taxonomy)

### 8.4. Lưu ý quan trọng

**`RETAIN_CANDIDATE` KHÔNG đồng nghĩa `FINAL`** (theo AGENTS.md §2.5). Một feature RETAIN_CANDIDATE chỉ có nghĩa:
- Qua tất cả required gates.
- Eligible cho FE-06 xem xét.

FE-06 (transformation/scaling/final matrix) sẽ quyết định feature nào thực sự được dùng cho clustering.

`PENDING_REVIEW` là vì decision cần mentor input — không phải vì feature "xấu". Ví dụ `BasketSize` PENDING_REVIEW vì identical to `AverageQuantity`, nhưng nếu mentor muốn giữ cả hai cho business readability thì cả hai được giữ.

---

## 9. Candidate Dataset

### 9.1. File output

- **Path:** `data/processed/customer_candidates.parquet`
- **SHA-256:** `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649`
- **Shape:** (4,371, 15) — 4,371 customers × (CustomerID + 14 candidate features)

### 9.2. Schema

| Column | Dtype | Layer | Role | Missing |
|---|---|---|---|---|
| `CustomerID` | `Int64` | IDENTIFIER_ONLY | identifier | 0 |
| `Recency` | `int64` | CANDIDATE | RFM | 0 |
| `Frequency` | `Int64` | CANDIDATE | RFM | 0 |
| `Monetary` | `float64` | CANDIDATE | RFM | 0 |
| `TotalQuantity` | `int64` | CANDIDATE | Quantity | 0 |
| `AverageQuantity` | `float64` | CANDIDATE | Quantity | 0 |
| `BasketSize` | `float64` | CANDIDATE | Quantity | 0 |
| `TenureDays` | `int64` | CANDIDATE | Behavior | 0 |
| `PurchaseIntervalMean` | `float64` | CANDIDATE | Behavior | 1,312 |
| `PurchaseIntervalStd` | `float64` | CANDIDATE | Behavior | 2,129 |
| `ActiveDays` | `Int64` | CANDIDATE | Behavior | 0 |
| `AverageInvoiceValue` | `float64` | CANDIDATE | Behavior | 0 |
| `ProductsPerInvoice` | `float64` | CANDIDATE | Diversity | 0 |
| `CancellationRate` | `float64` | CANDIDATE | Cancellation | 0 |
| `ReturnRate` | `float64` | CANDIDATE | Cancellation | 0 |

### 9.3. Uniqueness & integrity

- Customer count: 4,371
- Unique CustomerIDs: 4,371 (100% — không duplicate)
- CustomerID null: 0

### 9.4. Feature roles

| Role | Definition | Count |
|---|---|---|
| `IDENTIFIER_ONLY` | Chỉ dùng làm primary key (CustomerID) | 1 |
| `SOURCE_ONLY` | Dùng làm nguồn tính features khác (không trong output FE-05) | 7 (FE-02 columns) |
| `BASE_REFERENCE` | Reference từ FE-04, có thể dùng để derive candidates | 11 (giữ từ FE-04) |
| `CANDIDATE` | Engineered candidate feature; eligible cho FE-06 | 14 |
| `UNSUPPORTED` | Không materialize vì dataset thiếu | 1 |

### 9.5. Layer classification (từ `configs/feature_engineering.yaml`)

- `IDENTIFIER_ONLY`: CustomerID
- `SOURCE_ONLY`: InvoiceDate, InvoiceNo, StockCode, Quantity, LineRevenue, IsCancellation, IsReturn (FE-02 columns)
- `BASE_REFERENCE`: FirstPurchaseDate, LastPurchaseDate, TransactionLineCount, DistinctInvoiceCount, DistinctProducts, CancellationInvoiceCount, ReturnInvoiceCount, TotalQuantity, TotalMonetary, PurchaseFrequency, AverageTransactionValue (FE-04 outputs)
- `CANDIDATE`: Recency, Frequency, Monetary, TotalQuantity (Tầng 2), AverageQuantity, BasketSize, TenureDays, PurchaseIntervalMean, PurchaseIntervalStd, ActiveDays, AverageInvoiceValue, ProductsPerInvoice, CancellationRate, ReturnRate
- `UNSUPPORTED`: CategoryCount

---

## 10. Những kết quả quan trọng của FE-05

### 10.1. ReferenceDate

- Strategy: `snapshot_max` (`max(InvoiceDate) + 1 day`)
- Computed: `2011-12-10T12:50:00`
- **FE-05 sở hữu** ReferenceDate. FE-06 không được recompute.

### 10.2. RFM candidates

| Feature | Status | Default Materialized |
|---|---|---|
| `Recency` | RETAIN_CANDIDATE (purchase-only variant PENDING_REVIEW) | Days from `LastPurchaseDate` to ReferenceDate |
| `Frequency` | PENDING_REVIEW | `Frequency_ByInvoice` (FREQ-01) |
| `Monetary` | RETAIN_CANDIDATE | `MonetarySigned` |

### 10.3. Monetary comparison (4 variants)

| Variant | Mean | Min | Max |
|---|---|---|---|
| `MonetarySigned` | 1,893.96 | -4,287.63 | 279,489.02 |
| `MonetaryAbsolute` | (larger do lấy trị tuyệt đối) | (≥ 0) | (≥ MonetarySigned max) |
| `MonetaryPurchaseOnly` | (giữa Signed và Absolute) | (≥ 0) | (≥ MonetarySigned max) |
| `MonetaryCancellationOnly` | (typically < 0) | (≤ 0) | (≤ 0) |

FE-05 không chọn "best" — chỉ ghi nhận 4 variants đầy đủ trong `monetary_definition_comparison.csv` cho mentor xem xét.

### 10.4. Frequency comparison (2 variants)

| Variant | Mean | Max | Notes |
|---|---|---|---|
| `FREQ-01: by_invoice` | 5.08 | 248 | Materialized (default) |
| `FREQ-02: by_transaction_line` | (larger) | (≥ 5,000 cho big buyers) | Comparison only |

### 10.5. Quantity comparison (2 variants)

| Variant | Description |
|---|---|
| `signed` (default) | TotalQuantity nhận giá trị âm nếu cancellation > mua thật |
| `purchase_only` | Chỉ tính giao dịch mua thật (`IsCancellation = False`) |

### 10.6. Correlation / Redundancy

Các cặp feature có correlation ≥ 0.95:

| Feature1 | Feature2 | Correlation |
|---|---|---|
| `AverageQuantity` | `BasketSize` | 1.0 (mathematical identity) |
| `CancellationRate` | `ReturnRate` | 1.0 (data observation) |
| `Frequency` | `ActiveDays` | 0.974 (semantic redundancy) |

### 10.7. Selection decisions

| Decision | Count |
|---|---|
| RETAIN_CANDIDATE | 8 |
| EXCLUDE | 0 |
| ADJUST | 0 |
| PENDING_REVIEW | 6 |
| UNSUPPORTED | 1 |

### 10.8. Pending mentor decisions

| Decision | Mô tả |
|---|---|
| `ReferenceDate` strategy `snapshot_max` | Có dùng `max(InvoiceDate) + 1 day` làm ReferenceDate không, hay dùng ngày cố định khác? |
| Purchase-only Recency | Có materialize variant Recency chỉ tính trên purchase rows không? |
| `Frequency` variant | Có giữ `by_invoice` (default) hay chuyển sang `by_transaction_line`? |
| `Monetary` variant | Có giữ `MonetarySigned` (default) hay chuyển sang variant khác? |
| `Quantity` variant | Có giữ signed (default) hay chuyển sang purchase_only? |
| `BasketSize` vs `AverageQuantity` | Có giữ cả hai (alias) hay drop một? |
| `CancellationRate` vs `ReturnRate` | Có giữ cả hai hay gộp? |
| `Frequency` vs `ActiveDays` | Correlation 0.974 — có drop một không? |
| `ProductsPerInvoice` interpretation | Ghi nhận là "ratio proxy" trong report |

### 10.9. Missing values policy

- `PurchaseIntervalMean` và `PurchaseIntervalStd` có missing vì khách hàng có < 2 invoices.
- **Không fill bằng 0** (cố ý). NaN phản ánh "không tính được".

---

## 11. Quan hệ FE-05 → FE-06

### 11.1. Phân chia trách nhiệm

| Phase | Vai trò |
|---|---|
| **FE-05** | **Feature semantics và candidate construction.** Chọn feature nào có business meaning, tính giá trị, chạy analysis, ra decision `RETAIN_CANDIDATE` / `PENDING_REVIEW` / `UNSUPPORTED`. |
| **FE-06** | **Transformation, scaling và final working matrix.** Nhận `customer_candidates.parquet` bất biến, áp dụng Yeo-Johnson / log1p / RobustScaler, build final matrix cho clustering. |

### 11.2. FE-05 KHÔNG chịu trách nhiệm

- Scaling (RobustScaler, StandardScaler, MinMaxScaler).
- Transformation (Yeo-Johnson, log1p, Box-Cox).
- Winsorization / clipping.
- Final transformed dataset.

### 11.3. FE-06 đọc `customer_candidates.parquet` bất biến

- Input cho FE-06: `data/processed/customer_candidates.parquet`.
- FE-06 **không thay đổi** semantic của features; chỉ thay đổi scale/distribution.
- FE-06 output: final matrix sẵn sàng cho clustering algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means — 5 algorithms; K-Medoids OUT OF SCOPE per ADR-0003).

### 11.4. Pipeline sequence

```
FE-02 (cleaned transactions)
   ↓
FE-04 (customer_base.parquet) ← baseline aggregates
   ↓
FE-05 (customer_candidates.parquet) ← engineered candidates + analysis
   ↓
FE-06 (final transformed matrix) ← transformation/scaling
   ↓
Clustering, Evaluation, Profiling
```

---

## 12. Những gì FE-05 đã thực hiện được

| Requirement | Implementation / Result | Status | Evidence |
|---|---|---|---|
| Đọc customer_base.parquet + transactions_clean.parquet | Cả hai đọc với SHA-256 verified | ✅ DONE | `fe05_run.json.input.sha256_unchanged = true` |
| Tính ReferenceDate (FE-05 sở hữu) | `max(InvoiceDate) + 1 day` = `2011-12-10T12:50:00` | ✅ DONE | `rfm_report.md` |
| Tính Recency | `ReferenceDate - LastPurchaseDate` cho 4,371 customers | ✅ DONE | `customer_candidates.parquet` |
| Compute 2 Frequency variants | `by_invoice` (`FREQ-01`) + `by_transaction_line` (`FREQ-02`) | ✅ DONE | `frequency_variants_comparison.csv` |
| Materialize ONE Frequency | `Frequency` column = `by_invoice` (default) | ✅ DONE | `customer_candidates.parquet` |
| Compute 4 Monetary variants | `Signed` / `Absolute` / `PurchaseOnly` / `CancellationOnly` | ✅ DONE | `monetary_definition_comparison.csv` |
| Materialize ONE Monetary | `Monetary` column = `MonetarySigned` (default) | ✅ DONE | `customer_candidates.parquet` |
| Compute Quantity variants | `signed` (default) + `purchase_only` comparison | ✅ DONE | `quantity_variants_comparison.csv` |
| Materialize TenureDays | `LastPurchaseDate - FirstPurchaseDate` | ✅ DONE | `customer_candidates.parquet` |
| Compute PurchaseIntervalMean / Std | Invoice-level dates; NaN nếu < 2 invoices | ✅ DONE | `customer_candidates.parquet` (1,312 / 2,129 missing) |
| Compute ActiveDays | `dt.date.nunique()` (calendar days) | ✅ DONE | `customer_candidates.parquet` |
| Compute AverageQuantity / BasketSize | `TotalQuantity / DistinctInvoiceCount` (signed) | ✅ DONE | `customer_candidates.parquet` |
| Compute AverageInvoiceValue | `Monetary / Frequency` (FE-05 candidate mới) | ✅ DONE | `customer_candidates.parquet` |
| Compute ProductsPerInvoice | Ratio proxy (DistinctProducts / DistinctInvoiceCount) | ✅ DONE | `customer_candidates.parquet` |
| Compute CancellationRate / ReturnRate | CancellationInvoiceCount / Frequency (ReturnInvoiceCount / Frequency) | ✅ DONE | `customer_candidates.parquet` |
| CategoryCount NOT materialize | Dataset lacks official taxonomy | ✅ DONE (by design) | `feature_dictionary.csv` |
| Distribution analysis | Mean, Std, Min, Q25, Q50, Q75, Max, Skewness, Kurtosis, Missing | ✅ DONE | `distribution_analysis.csv` |
| Variance analysis | Count, Mean, Std, Variance, CV | ✅ DONE | `variance_analysis.csv` |
| Correlation matrices | Pearson + Spearman | ✅ DONE | `correlation_matrix_pearson.csv`, `correlation_matrix_spearman.csv` |
| Redundancy analysis | Cặp correlation ≥ 0.95 | ✅ DONE | `redundancy_report.csv` |
| Outlier detection | IQR-based | ✅ DONE | `outlier_detection.csv` |
| Business interpretability | Manual review | ✅ DONE | `business_interpretability.csv` |
| Feature selection gates | 4 required + 3 diagnostic | ✅ DONE | `feature_selection_report.csv` |
| Feature selection decisions | 8 RETAIN_CANDIDATE + 6 PENDING_REVIEW + 1 UNSUPPORTED | ✅ DONE | `feature_selection_report.csv` |
| Write customer_candidates.parquet | 4,371 × 15 (CustomerID + 14 candidates) | ✅ DONE | SHA-256: `df5333fba...` |
| Reproducibility metadata | SHA-256, executed_at, platform, config | ✅ DONE | `fe05_run.json` |
| Layer classification | IDENTIFIER_ONLY / SOURCE_ONLY / BASE_REFERENCE / CANDIDATE / UNSUPPORTED | ✅ DONE | `configs/feature_engineering.yaml` + `feature_dictionary.csv` |
| Feature dictionary | Layer, Role, Description, Status, ClusteringCandidate | ✅ DONE | `feature_dictionary.csv` |
| Candidate feature report | Summary, layer classification | ✅ DONE | `candidate_feature_report.md` |
| Narrative report | Tiếng Việt, báo cáo vận hành | ✅ DONE | `narrative_report.md` |

---

## 13. Những gì chưa được mentor phê duyệt

Các decision sau vẫn **PENDING_REVIEW** — mentor cần review trước khi các phase sau coi là final:

### 13.1. Methodology decisions

| Decision | Status | Note |
|---|---|---|
| `ReferenceDate` strategy `snapshot_max` | `MENTOR_REVIEW_PENDING` | Có nên dùng `max(InvoiceDate) + 1 day` không, hay dùng một ngày cố định khác? |
| Recency: all transactions vs purchase-only | `PENDING_REVIEW` | Recency hiện dùng LastPurchaseDate (bao gồm cancellation); có cần purchase-only variant không? |
| `Frequency` variant | `WORKING_ASSUMPTION` | Default `by_invoice` (FREQ-01); có chuyển sang `by_transaction_line` không? |
| `Monetary` variant | `WORKING_ASSUMPTION` | Default `MonetarySigned`; có chuyển sang absolute / purchase-only / cancellation-only không? |
| `Quantity` variant | `WORKING_ASSUMPTION` | Default signed; có chuyển sang purchase-only không? |
| Cancellation/return semantics | `WORKING_ASSUMPTION` | Hủy/trả có được tính vào Monetary, Frequency, hay tách riêng? |
| `BasketSize` vs `AverageQuantity` | `PENDING_REVIEW` | Có giữ cả hai (alias, mathematical identity) hay drop một? |
| `CancellationRate` vs `ReturnRate` | `PENDING_REVIEW` | Trong dataset hiện tại, hai rate identical (correlation = 1.0); có giữ cả hai không? |
| `Frequency` vs `ActiveDays` redundancy | `PENDING_REVIEW` | Correlation 0.974; có drop `ActiveDays` không? |
| `ProductsPerInvoice` ratio proxy | `WORKING_ASSUMPTION` | Ghi rõ là "ratio proxy", không phải standard diversity metric |

### 13.2. Không gọi là final

- `customer_candidates.parquet` **KHÔNG phải final clustering dataset**.
- Đây là **candidate dataset Tầng 2** — input cho FE-06 transformation.
- Sau FE-06 mới có **final matrix** cho clustering.

---

## 14. Limitations

### 14.1. Frequency variant comparison chỉ giữa 2 candidates

FE-05 so sánh `FREQ-01` (`by_invoice`) và `FREQ-02` (`by_transaction_line`) nhưng **KHÔNG** so sánh với các variant khác (e.g., `by_unique_date`). Chưa được xác định trong repo liệu có cần thêm variants khác không.

### 14.2. CancellationRate == ReturnRate (data observation)

Trong dataset hiện tại, `IsCancellation` và `IsReturn` cho cùng giá trị trên cùng rows (theo FE-02 audit). Nên `CancellationInvoiceCount == ReturnInvoiceCount` và `CancellationRate == ReturnRate`. **Nếu** hai flag khác nhau trong tương lai, hai rate có thể khác.

### 14.3. Missing values trong PurchaseInterval

`PurchaseIntervalMean` (30.0% missing) và `PurchaseIntervalStd` (48.7% missing) có missing vì khách hàng chỉ mua 1 lần. NaN KHÔNG được fill. Imputation policy sẽ do FE-06 quyết định.

### 14.4. Signed baseline

`Monetary`, `TotalQuantity`, `AverageQuantity`, `BasketSize` đều giữ signed baseline (cancellation/return làm giảm giá trị). Điều này có thể gây khó khăn cho các thuật toán clustering giả định distribution dương. FE-06 sẽ xử lý qua transformation.

### 14.5. CategoryCount unsupported

Dataset không có official taxonomy (category hierarchy) — chỉ có `StockCode` mức sản phẩm. Diversity ở cấp category không thể tính được. Nếu cần category-level diversity, cần taxonomy từ nguồn bên ngoài (chưa có).

### 14.6. RFM ReferenceDate là `snapshot_max`

FE-05 dùng `max(InvoiceDate) + 1 day` làm ReferenceDate. Đây là deterministic strategy nhưng giả định "thời điểm hiện tại" là sau dataset cuối cùng. Nếu dataset được cập nhật, ReferenceDate sẽ thay đổi.

### 14.7. PENDING_REVIEW không có ADR

Một số PENDING_REVIEW decisions (cancellation/return treatment, BasketSize alias, Frequency variant) — các decision này **chưa được ghi nhận trong ADR**. Cần mentor review trước khi final.

---

## 15. Kết luận

FE-05 đã xây dựng **customer feature space** gồm **14 candidate features** cho 4,371 customers, dựa trên customer-level base dataset của FE-04 và transaction-level cleaned data của FE-02.

Pipeline deterministic:
- Input SHA-256 của `customer_base.parquet` và `transactions_clean.parquet` được verify.
- Output `customer_candidates.parquet` với SHA-256: `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649`.
- Executed at: `2026-09-20T12:50:36.457405+00:00`, Python 3.14.4.

Evidence-based feature selection đã phân loại:
- 8 features `RETAIN_CANDIDATE` (eligible cho FE-06).
- 6 features `PENDING_REVIEW` (cần mentor input).
- 1 feature `UNSUPPORTED` (CategoryCount, dataset lacks taxonomy).

FE-05 KHÔNG gọi candidate dataset là "final clustering dataset". Đây là **candidate dataset Tầng 2** — input cho FE-06 (transformation, scaling, final matrix). Sau FE-06, mới có final transformed matrix cho clustering algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means — 5 algorithms; K-Medoids OUT OF SCOPE per ADR-0003).

Không algorithm/feature nào được gọi là "best", "recommended", hay "final" trong FE-05. Mọi decision methodology đều được đánh dấu `WORKING_ASSUMPTION` hoặc `PENDING_REVIEW` chờ mentor review.

---

*Tài liệu này được viết để mentor review. Số liệu trích từ execution thực tế, không tự tạo. Mọi PENDING_REVIEW decision được nêu rõ trong mục 13.*
