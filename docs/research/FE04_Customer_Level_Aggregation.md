# FE-04 — Customer-level Aggregation: Lý thuyết và Kết quả thực hiện

> **Tài liệu cho mentor review.**
> Phiên bản: FE-04 (Aggregation — Customer-level Dataset).
> Mọi số liệu trong tài liệu này được lấy trực tiếp từ `reports/fe04/` và `data/processed/customer_base.parquet` (sinh từ execution thực tế).
> Tài liệu KHÔNG mô tả cách cài đặt hay hướng dẫn sử dụng code; KHÔNG thay thế `reports/fe04/aggregation_report.md` (báo cáo vận hành).

---

## 1. Tổng quan FE-04

### 1.1. Mục tiêu

FE-04 thực hiện **customer-level aggregation**: chuyển dữ liệu giao dịch đã được làm sạch bởi FE-02 sang một bảng customer-level mà trong đó **mỗi `CustomerID` tương ứng đúng một dòng quan sát (observation)**. Sản phẩm của FE-04 là file `data/processed/customer_base.parquet`, dùng làm đầu vào cho FE-05 (feature engineering & candidate selection).

### 1.2. Vấn đề cần giải quyết

Dữ liệu đầu vào từ FE-02 (`data/processed/transactions_clean.parquet`) là dữ liệu ở **transaction-line level**: mỗi dòng đại diện cho **một dòng (line item) của một hóa đơn**, ghi nhận một sản phẩm cụ thể trong một lần mua hàng của khách hàng. Một khách hàng có thể xuất hiện ở rất nhiều dòng (mua nhiều lần, mỗi lần mua nhiều sản phẩm). Các thuật toán phân cụm (clustering) yêu cầu mỗi khách hàng phải được biểu diễn bằng **một vector đặc trưng cố định chiều** (fixed-length feature vector). Do đó cần một bước chuyển đổi từ "nhiều dòng cho một khách hàng" sang "một dòng cho một khách hàng".

### 1.3. Vì sao cần chuyển từ transaction-level sang customer-level trong bài toán customer segmentation

Customer segmentation nhằm mục đích **nhóm các khách hàng có hành vi tương tự**. Về mặt phương pháp luận, đơn vị phân tích (unit of analysis) là **khách hàng**, không phải giao dịch. Việc giữ dữ liệu ở transaction-level sẽ khiến:

- Mỗi khách hàng có số dòng khác nhau (longitudinal, variable-length) — không thể đưa vào ma trận đặc trưng của clustering.
- Một giao dịch riêng lẻ không phản ánh "hồ sơ hành vi" tổng thể của khách hàng.
- Các thước đo như "tổng chi tiêu", "tần suất mua", "khoảng cách giữa các lần mua" chỉ có ý nghĩa khi aggregate trên toàn bộ lịch sử giao dịch của một khách hàng.

Do đó customer-level aggregation là **bước tiền xử lý bắt buộc**, biến lịch sử giao dịch thành **hồ sơ hành vi khách hàng** (customer behavioral profile).

### 1.4. Vai trò của FE-04 trong pipeline tổng thể

FE-04 nằm giữa FE-02 (cleaned transactions) và FE-05 (feature engineering & candidate selection). Trong chuỗi:

```
FE-02 (cleaned transactions)
   ↓
FE-04 (customer-level base dataset)            ← FE-04 ở đây
   ↓
FE-05 (RFM + behavioral features + selection)
   ↓
FE-06 (transformation, scaling, final matrix)
   ↓
Clustering, evaluation, profiling
```

FE-04 cung cấp **khung xương (scaffold)** cho FE-05: thay vì FE-05 phải aggregate thủ công trên transactions mỗi lần tính RFM, FE-04 đã aggregate sẵn các baseline features. Từ `customer_base.parquet`, FE-05 tiếp tục xây dựng các candidate features (RFM Recency/Frequency/Monetary, TenureDays, PurchaseInterval, ActiveDays, AverageInvoiceValue, ProductsPerInvoice, CancellationRate, ReturnRate, v.v.) và thực hiện feature selection.

### 1.5. Input và Output

**Input:**

| Mục | Giá trị |
|---|---|
| File | `data/processed/transactions_clean.parquet` (FE-02 output) |
| Số dòng | 401,564 |
| Số cột | 10 |
| Số CustomerID duy nhất | 4,371 |
| SHA-256 (trước khi chạy) | `08b8107573654fa2bd198904d00c6aeaa9f34d9ab3026bd4335f72d4b6903415` |
| SHA-256 (sau khi chạy) | `08b8107573654fa2bd198904d00c6aeaa9f34d9ab3026bd4335f72d4b6903415` |
| Kết luận SHA | Input không bị mutate |

**Output:**

| Mục | Giá trị |
|---|---|
| File | `data/processed/customer_base.parquet` |
| Số dòng | 4,371 (= số customer duy nhất) |
| Số cột | 12 (1 CustomerID + 11 aggregate features) |
| CustomerID uniqueness | 100% (4,371/4,371 unique) |

---

## 2. Cơ sở lý thuyết: Customer-level Aggregation

### 2.1. Khái niệm aggregation

Trong xử lý dữ liệu, **aggregation** là quá trình nhóm nhiều bản ghi theo một hoặc nhiều khóa chung (group key), sau đó tính toán một giá trị tóm tắt (summary statistic) cho mỗi nhóm. Các hàm tóm tắt phổ biến gồm `sum`, `mean`, `count`, `nunique`, `min`, `max`. Trong bối cảnh customer-level aggregation, group key là `CustomerID`, và mỗi nhóm là tập tất cả các dòng giao dịch thuộc về khách hàng đó.

### 2.2. Group-by theo CustomerID

Việc chọn `CustomerID` làm group key dựa trên giả định rằng `CustomerID` đã được FE-02 xác thực là duy nhất cho mỗi khách hàng thực (không null, không trùng lặp dòng sau cleaning). Mỗi group đại diện cho toàn bộ lịch sử giao dịch của một khách hàng trong tập dữ liệu.

### 2.3. Tại sao clustering cần một vector đặc trưng cho mỗi khách hàng

Các thuật toán clustering tiêu chuẩn (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means — năm thuật toán benchmark cố định trong methodology; K-Medoids OUT OF SCOPE per ADR-0003) hoạt động trên **ma trận đặc trưng hai chiều**: mỗi dòng là một quan sát (observation), mỗi cột là một đặc trưng (feature). Một ma trận có dạng `(n_samples, n_features)`. Customer-level aggregation chính là bước tạo ra ma trận này: `n_samples` = số khách hàng, `n_features` = số đặc trưng hành vi được tổng hợp.

### 2.4. Sự khác nhau giữa transaction-level và customer-level representation

| Đặc điểm | Transaction-level | Customer-level |
|---|---|---|
| Đơn vị quan sát | Một dòng sản phẩm trong hóa đơn | Một khách hàng |
| Số dòng mỗi đối tượng | Nhiều (variable) | Đúng 1 |
| Group key | Không (mỗi dòng độc lập) | `CustomerID` |
| Phù hợp với | Phân tích giỏ hàng, phân tích sản phẩm | Phân cụm khách hàng, RFM |
| Output schema | Cố định theo schema giao dịch | Mỗi cột là một aggregate |

### 2.5. Aggregation giúp chuyển lịch sử giao dịch thành hồ sơ hành vi khách hàng

Một khách hàng qua hàng trăm hoặc hàng nghìn dòng giao dịch. Aggregation gom toàn bộ lịch sử đó lại thành một số ít các con số tóm tắt: "tổng cộng khách hàng này đã mua bao nhiêu sản phẩm", "tổng doanh thu", "ngày mua đầu/cuối", "có bao nhiêu hóa đơn", v.v. Tập các con số này chính là **hồ sơ hành vi** (behavioral profile) của khách hàng, là đầu vào trực tiếp cho RFM và clustering.

---

## 3. Thiết kế dữ liệu Customer-level

### 3.1. Nguyên tắc thiết kế

**Nguyên tắc cốt lõi:** `CustomerID → 1 observation`. Mỗi khách hàng xuất hiện đúng một lần trong output. Không có dòng trùng CustomerID, không có CustomerID null, không có dòng tổng hợp "ALL".

FE-04 tạo ra **11 aggregate features** được định nghĩa trong `configs/aggregation.yaml`. Mỗi feature có:
- **name**: tên cột output
- **source**: cột nguồn trong transaction-level (hoặc `LineRevenue` nếu là derived)
- **fn**: hàm aggregation (`sum`, `nunique`, `min`, `max`, `count`, `avg_by_invoice`, hoặc conditional variants)
- **status**: `WORKING_ASSUMPTION` hoặc `PENDING_MENTOR_REVIEW`
- **description**: business meaning

### 3.2. Bảng các aggregate features

| Feature | Định nghĩa | Cách tính | Ý nghĩa |
|---|---|---|---|
| `TotalQuantity` | Tổng số lượng sản phẩm đã mua của khách hàng (signed, bao gồm cancellation/return) | `sum(Quantity)` group theo `CustomerID` | Phản ánh "quy mô" tổng thể giao dịch của khách hàng. Signed: giá trị có thể âm do cancellation. |
| `TotalMonetary` | Tổng doanh thu theo signed baseline `Quantity × UnitPrice` | `sum(LineRevenue)` group theo `CustomerID`, với `LineRevenue` derive in-memory | Signed monetary baseline; cancellation/return rows tạo giá trị âm. **Chưa phải RFM Monetary cuối cùng** — FE-05 sẽ review sign convention. |
| `FirstPurchaseDate` | Ngày giao dịch đầu tiên của khách hàng | `min(InvoiceDate)` group theo `CustomerID` | Dùng để tính TenureDays và các chỉ số liên quan đến thời gian. |
| `LastPurchaseDate` | Ngày giao dịch cuối cùng của khách hàng | `max(InvoiceDate)` group theo `CustomerID` | Dùng để tính Recency (kết hợp với ReferenceDate của FE-05). |
| `PurchaseFrequency` | Working proxy cho tần suất mua = số hóa đơn duy nhất | `nunique(InvoiceNo)` group theo `CustomerID` | **WORKING PROXY**, chưa phải định nghĩa RFM Frequency cuối cùng. FE-05 sẽ review. Trong FE-04, giá trị này bằng `DistinctInvoiceCount` (theo implementation). |
| `TransactionLineCount` | Số dòng transaction-line (mỗi hóa đơn có thể có nhiều dòng) | `count(InvoiceNo)` group theo `CustomerID` | Khác với `DistinctInvoiceCount`. Cung cấp thêm thông tin để FE-05 chọn denominator cho Frequency. |
| `DistinctInvoiceCount` | Số hóa đơn duy nhất của khách hàng | `nunique(InvoiceNo)` group theo `CustomerID` | Đếm số hóa đơn (không trùng lặp). Làm denominator cho `AverageTransactionValue`. |
| `DistinctProducts` | Số sản phẩm khác nhau đã mua | `nunique(StockCode)` group theo `CustomerID` | Phản ánh mức độ đa dạng sản phẩm của khách hàng. |
| `CancellationInvoiceCount` | Số hóa đơn cancellation duy nhất | `nunique(InvoiceNo)` trên subset `IsCancellation == True`, group theo `CustomerID` | Phục vụ FE-05 xây dựng `CancellationRate`. **FE-05 sẽ review cancellation treatment**. |
| `ReturnInvoiceCount` | Số hóa đơn return duy nhất | `nunique(InvoiceNo)` trên subset `IsReturn == True`, group theo `CustomerID` | Phục vụ FE-05 xây dựng `ReturnRate`. **FE-05 sẽ review return treatment**. |
| `AverageTransactionValue` | Giá trị giao dịch trung bình | `TotalMonetary / DistinctInvoiceCount` | Working definition. **FE-05 có thể điều chỉnh denominator** (chú ý: không nhầm với `AverageInvoiceValue` của FE-05). |

### 3.3. Lưu ý về ba feature đặc biệt

1. **`PurchaseFrequency`** trong FE-04 là **WORKING PROXY** dựa trên `DistinctInvoiceCount`. Đây là giá trị "thử nghiệm" để FE-05 có baseline mà xem xét. Trong FE-05, RFM Frequency chính thức được tái định nghĩa qua 4 variants (`Frequency_ByInvoice`, `Frequency_ByTransactionLine`, v.v.) và so sánh trong `frequency_variants_comparison.csv` trước khi chọn một variant.

2. **`TotalMonetary`** là **SIGNED MONETARY BASELINE**. Không gọi đây là RFM Monetary cuối cùng. FE-05 xem xét 4 variants của Monetary (bao gồm signed, absolute, purchase-only, cancellation-only) trong `monetary_definition_comparison.csv`. FE-04 giữ giá trị signed vì đây là baseline trung thực nhất về "tổng giá trị giao dịch" theo quan điểm tài khoản (cancellation làm giảm doanh thu).

3. **`AverageTransactionValue`** giữ đúng định nghĩa implementation trong FE-04: `TotalMonetary / DistinctInvoiceCount`. **Không nhầm với `AverageInvoiceValue`** của FE-05 (là `Monetary / Frequency`, với Frequency là RFM Frequency chính thức của FE-05). Hai feature có cùng tên semantic "giá trị trung bình mỗi giao dịch" nhưng denominator và numerator có thể khác nhau giữa hai phase.

---

## 4. Quy trình aggregation

### 4.1. Sơ đồ pipeline

```
Input: data/processed/transactions_clean.parquet (FE-02 output)
   ├── Schema validation (REQUIRED_CLEANED_COLUMNS)
   ├── SHA-256 (before)
   │
   ↓
Derive LineRevenue = Quantity × UnitPrice (in-memory)
   │
   ↓
Group by CustomerID (groupby, dropna=False, sort=True)
   │
   ↓
Apply aggregations (per spec in configs/aggregation.yaml)
   ├── Standard: sum / nunique / min / max / count
   ├── Special: avg_by_invoice (TotalMonetary / DistinctInvoiceCount)
   └── Conditional: nunique trên IsCancellation / IsReturn subsets
   │
   ↓
Set PurchaseFrequency = DistinctInvoiceCount (working proxy)
   │
   ↓
Sort deterministic: TotalMonetary desc, CustomerID asc
   │
   ↓
Validate output (11 checks V-01 → V-11)
   │
   ↓
Write customer_base.parquet
   │
   ↓
SHA-256 (after); verify before == after
```

### 4.2. Mô tả từng bước

**Bước 1 — Input loading & schema validation.** Đọc `transactions_clean.parquet` từ FE-02 (read-only). Kiểm tra 8 cột bắt buộc tồn tại: `InvoiceNo`, `StockCode`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `IsCancellation`, `IsReturn`. Nếu thiếu → fail-fast với thông báo yêu cầu chạy lại FE-02. SHA-256 của file input được ghi nhận.

**Bước 2 — Derivation `LineRevenue`.** Tính `LineRevenue = Quantity × UnitPrice` trên bản copy của DataFrame (in-memory). Không ghi đè lên input file. Đây là bước chuẩn bị cho feature `TotalMonetary` và `AverageTransactionValue`.

**Bước 3 — Group by CustomerID.** `groupby(CustomerID, dropna=False, sort=True)`. Việc giữ `dropna=False` đảm bảo FE-04 phát hiện nếu FE-02 vô tình để CustomerID null (sẽ raise error, không silent).

**Bước 4 — Apply aggregations.** Với mỗi spec trong YAML:
- Standard aggregations (`sum`, `nunique`, `min`, `max`, `count`): áp dụng trực tiếp lên grouped series.
- `avg_by_invoice`: tính riêng `TotalMonetary` = `sum(LineRevenue)`, `DistinctInvoiceCount` = `nunique(InvoiceNo)`, sau đó `AverageTransactionValue = TotalMonetary / DistinctInvoiceCount`. Guard chống zero-denominator.
- Conditional aggregations: filter subset theo `IsCancellation == True` hoặc `IsReturn == True`, sau đó `nunique(InvoiceNo)` trên subset.

**Bước 5 — Working proxy assignment.** `PurchaseFrequency = DistinctInvoiceCount` (theo implementation trong `base_dataset.py`). Ghi rõ trong YAML rằng đây là working proxy, không phải RFM Frequency cuối cùng.

**Bước 6 — Deterministic sort.** Sort theo `TotalMonetary` desc, sau đó `CustomerID` asc. Đảm bảo output thứ tự cố định giữa các lần chạy (reproducibility).

**Bước 7 — Validation.** 11 checks (V-01 đến V-11) đảm bảo output đúng schema và không có anomaly dữ liệu. Nếu bất kỳ check nào FAIL → raise `RuntimeError`, pipeline dừng.

**Bước 8 — Write output.** Ghi `customer_base.parquet`. SHA-256 của input verify lần cuối (before == after) để chứng minh input không bị mutate.

---

## 5. Kiểm soát tính đúng đắn dữ liệu

### 5.1. Các validation check đã thực hiện

| Check ID | Mô tả | Trạng thái | Thông báo |
|---|---|---|---|
| V-01 | Số dòng == số unique CustomerID | ✅ PASS | nrow=4,371, nunique=4,371 |
| V-02 | Không có duplicate CustomerID | ✅ PASS | duplicate_count=0 |
| V-03 | CustomerID không null | ✅ PASS | null_count=0 |
| V-04 | TotalQuantity là finite | ⚠️ WARNING | 40 customers có TotalQuantity âm (signed cancellation/return — kỳ vọng) |
| V-05 | TotalMonetary là finite | ✅ PASS | OK |
| V-06 | FirstPurchaseDate <= LastPurchaseDate | ✅ PASS | Tất cả ngày hợp lệ |
| V-07 | DistinctInvoiceCount >= 1 | ✅ PASS | OK |
| V-08 | DistinctInvoiceCount != 0 (denominator cho AverageTransactionValue) | ✅ PASS | OK |
| V-09 | AverageTransactionValue là finite | ✅ PASS | OK |
| V-10 | PurchaseFrequency là non-negative integer | ✅ PASS | OK |
| V-11 | Expected dtypes đúng cho từng cột | ✅ PASS | OK |

**Tổng kết:** 10 PASS, 1 WARNING, 0 FAIL. Pipeline vẫn thành công vì V-04 chỉ là WARNING (không phải FAIL).

### 5.2. Ý nghĩa của V-04 WARNING

V-04 ghi nhận **40 khách hàng có `TotalQuantity` âm**. Đây là kết quả kỳ vọng khi giữ chính sách **signed baseline**: nếu một khách hàng thực hiện cancellation (Quantity âm) tổng cộng lớn hơn tổng Quantity dương của các lần mua thực, `TotalQuantity` sẽ âm. V-04 xếp trạng thái WARNING (không phải FAIL) vì:
- Đây là baseline **có chủ đích**, không phải lỗi dữ liệu.
- FE-05 sẽ review sign convention cho Monetary tương tự.
- Báo cáo không gọi đây là lỗi.

### 5.3. Kiểm tra bổ sung đã thực hiện

Ngoài 11 check chính thức, FE-04 còn thực hiện:

- **Schema validation input:** đảm bảo 8 cột bắt buộc có trong `transactions_clean.parquet`.
- **CustomerID null check trước grouping:** phát hiện nếu FE-02 để null CustomerID.
- **DistinctInvoiceCount != 0 check trong pipeline:** guard chống zero-denominator khi tính AverageTransactionValue.
- **SHA-256 before/after comparison:** chứng minh input không bị mutate trong quá trình chạy.

### 5.4. Thống kê numeric output

| Feature | Min | Max | Mean | Median |
|---|---|---|---|---|
| `TotalQuantity` | -303 | 196,143 | 1,116.21 | 364 |
| `TotalMonetary` | -4,287.63 | 279,489.02 | 1,893.96 | 644.24 |
| `PurchaseFrequency` | 1 | 248 | 5.08 | 3 |
| `TransactionLineCount` | 1 | 7,812 | 91.87 | 41 |
| `DistinctInvoiceCount` | 1 | 248 | 5.08 | 3 |
| `DistinctProducts` | 1 | 1,794 | 61.22 | 35 |
| `CancellationInvoiceCount` | 0 | 47 | 0.84 | 0 |
| `ReturnInvoiceCount` | 0 | 47 | 0.84 | 0 |
| `AverageTransactionValue` | -4,287.63 | 6,207.67 | 314.59 | 235.18 |

`PurchaseFrequency` và `DistinctInvoiceCount` có cùng mean/median/min/max (vì implementation set `PurchaseFrequency = DistinctInvoiceCount`). Tương tự, `CancellationInvoiceCount` và `ReturnInvoiceCount` có cùng phân phối trong dataset này (do coincidence trong data, không phải vì công thức giống nhau — hai feature được tính từ hai flag khác nhau).

---

## 6. Kết quả FE-04

### 6.1. Số lượng

| Chỉ số | Trước (FE-02) | Sau (FE-04) |
|---|---|---|
| Tổng số dòng | 401,564 | 4,371 |
| Số cột | 10 | 12 |
| CustomerID duy nhất | 4,371 | 4,371 |
| CustomerID null | 0 | 0 |

### 6.2. Schema output

| Cột | dtype | Nguồn |
|---|---|---|
| `CustomerID` | `Int64` | Khóa chính |
| `TotalQuantity` | `int64` | `sum(Quantity)` |
| `TotalMonetary` | `float64` | `sum(LineRevenue)` |
| `FirstPurchaseDate` | `datetime64[us]` | `min(InvoiceDate)` |
| `LastPurchaseDate` | `datetime64[us]` | `max(InvoiceDate)` |
| `PurchaseFrequency` | `int64` | `nunique(InvoiceNo)` (working proxy) |
| `TransactionLineCount` | `int64` | `count(InvoiceNo)` |
| `DistinctInvoiceCount` | `int64` | `nunique(InvoiceNo)` |
| `DistinctProducts` | `int64` | `nunique(StockCode)` |
| `CancellationInvoiceCount` | `Int64` | conditional `nunique(InvoiceNo)` |
| `ReturnInvoiceCount` | `Int64` | conditional `nunique(InvoiceNo)` |
| `AverageTransactionValue` | `float64` | `TotalMonetary / DistinctInvoiceCount` |

### 6.3. Kết quả validation

- **10 PASS** trên 11 checks (xem mục 5.1).
- **1 WARNING (V-04):** 40 khách hàng có `TotalQuantity` âm do signed cancellation/return.
- **0 FAIL.**

### 6.4. Cảnh báo quan trọng

- **40 khách hàng có `TotalQuantity` âm.** Đây là hệ quả của việc giữ chính sách **signed baseline** cho Quantity (cancellation/return rows giữ Quantity âm). Báo cáo `validation_report.csv` xếp đây là WARNING, không phải lỗi. Lý do:
  - Đây là baseline có chủ đích (giống `TotalMonetary` cũng là signed).
  - FE-05 sẽ review sign convention và quyết định xem có giữ nguyên, đổi sang absolute, hay tách purchase-only.
  - Khi tính các chỉ số tổng hợp khác (như `AverageTransactionValue`), giá trị có thể âm, điều này phản ánh đúng nghĩa tài khoản.

- **Cancellation/return treatment defer cho FE-05.** Hai feature `CancellationInvoiceCount` và `ReturnInvoiceCount` được tính dựa trên flag từ FE-02. Việc xử lý cancellation/return (có tính vào Monetary, có loại bỏ khỏi Frequency, v.v.) thuộc về quyết định của FE-05.

---

## 7. Data integrity và Reproducibility

### 7.1. Input dataset

- **Path:** `data/processed/transactions_clean.parquet`
- **SHA-256 (before):** `08b8107573654fa2bd198904d00c6aeaa9f34d9ab3026bd4335f72d4b6903415`
- **SHA-256 (after):** `08b8107573654fa2bd198904d00c6aeaa9f34d9ab3026bd4335f72d4b6903415`
- **Kết luận:** Input không bị mutate. SHA-256 giữ nguyên trước và sau khi chạy FE-04.

### 7.2. Output dataset

- **Path:** `data/processed/customer_base.parquet`
- **Shape:** (4,371, 12)
- **CustomerID uniqueness:** 4,371/4,371 unique (100%)

### 7.3. Configuration

- **Source config:** `configs/aggregation.yaml`
- **11 aggregation specs** định nghĩa đầy đủ trong YAML với status (`WORKING_ASSUMPTION`) và description.
- **Customer key:** `CustomerID`
- **LineRevenue derivation:** `Quantity × UnitPrice`, in-memory, không persist.

### 7.4. Execution metadata

| Mục | Giá trị |
|---|---|
| Executed at (UTC) | `2026-09-20T09:04:13.148990+00:00` |
| Python | 3.14.4 |
| Platform | Linux 7.0.0-31-generic, x86_64 |
| Config source | `yaml:/home/hoangson301223/NCKH/EPU_CNS_SG_SV_2026_PHASE_2_PROJECT_13/customer-segmentation-ml/configs/aggregation.yaml` |
| Random seed | 42 (mặc dù FE-04 deterministic — không có random operation nào sử dụng seed) |

### 7.5. Khả năng tái lập pipeline

Pipeline FE-04 là **deterministic**:
- Không có random operation nào (random_seed trong config không được sử dụng nhưng được giữ cho tính khai báo).
- Output sort theo `TotalMonetary desc, CustomerID asc` đảm bảo thứ tự cố định.
- SHA-256 trước/sau khớp nhau → input được bảo toàn.
- Chạy lại pipeline với cùng input và config sẽ cho ra cùng output.

---

## 8. Quan hệ FE-04 → FE-05

### 8.1. FE-04 KHÔNG phải bước feature engineering cuối cùng

FE-04 tạo ra **customer-level base dataset** với các **working baseline features**. Đây là khung xương cho FE-05, không phải kết quả cuối cùng. Mọi feature trong FE-04 đều có status `WORKING_ASSUMPTION` và có thể được FE-05 review, điều chỉnh, hoặc thay thế.

### 8.2. Những gì FE-05 tiếp tục thực hiện từ `customer_base.parquet`

FE-05 đọc `customer_base.parquet` và xây dựng:

- **RFM features:**
  - `Recency`: tính từ `LastPurchaseDate` và `ReferenceDate` = `max(InvoiceDate) + 1 day` (do FE-05 quản lý).
  - `Frequency`: so sánh 4 variants trong `frequency_variants_comparison.csv` rồi materialize ONE.
  - `Monetary`: so sánh 4 variants trong `monetary_definition_comparison.csv` rồi materialize ONE.

- **Behavioral features:**
  - `TenureDays`: từ `FirstPurchaseDate`, `LastPurchaseDate`.
  - `PurchaseIntervalMean`, `PurchaseIntervalStd`: từ invoice-level dates.
  - `ActiveDays`: distinct calendar days.
  - `AverageInvoiceValue`: từ `Monetary / Frequency` (FE-05 candidate, **khác** với `AverageTransactionValue` của FE-04).
  - `ProductsPerInvoice`: ratio proxy từ `DistinctProducts / DistinctInvoiceCount`.

- **Cancellation/return features:**
  - `CancellationRate = CancellationInvoiceCount / Frequency`.
  - `ReturnRate = ReturnInvoiceCount / Frequency`.

- **Distribution, correlation, redundancy analysis.**

- **Feature selection** để ra `customer_candidates.parquet` với 14 candidate features.

### 8.3. Working baseline features của FE-04 sẽ được FE-05 xem xét lại

| FE-04 feature | FE-05 xem xét |
|---|---|
| `PurchaseFrequency` | Review để quyết định đây có phải RFM Frequency chính thức hay không |
| `TotalMonetary` | Review sign convention cho RFM Monetary |
| `AverageTransactionValue` | Review denominator (FE-05 có thể chọn denominator khác) |
| `CancellationInvoiceCount` | Review cancellation treatment |
| `ReturnInvoiceCount` | Review return treatment |

---

## 9. Những gì FE-04 đã thực hiện được

| Requirement | Status | Evidence |
|---|---|---|
| Đọc transaction-level từ FE-02 output | ✅ DONE | `data/processed/transactions_clean.parquet` (401,564 rows) |
| Derive `LineRevenue` in-memory (không persist) | ✅ DONE | `base_dataset.py::compute_line_revenue()` |
| Group theo `CustomerID` | ✅ DONE | `aggregate_customer_base()` |
| Tạo 11 aggregate features | ✅ DONE | `customer_base.parquet` shape (4,371, 12) |
| Mỗi CustomerID = 1 observation | ✅ DONE | V-01 PASS (nrow=4,371, nunique=4,371) |
| Không duplicate CustomerID | ✅ DONE | V-02 PASS (duplicate_count=0) |
| CustomerID không null | ✅ DONE | V-03 PASS (null_count=0) |
| Validation đầy đủ | ✅ DONE | 11 checks, 10 PASS, 1 WARNING, 0 FAIL |
| SHA-256 verification input before/after | ✅ DONE | `fe04_run.json` SHA khớp nhau |
| Reports tự động | ✅ DONE | `aggregation_report.md`, `aggregation_summary.csv`, `feature_dictionary.csv`, `validation_report.csv`, `fe04_run.json` |
| Deterministic pipeline | ✅ DONE | Không random operation, sort cố định |
| Không cluster / scale / transform / feature selection | ✅ DONE | `configs/aggregation.yaml` scope_boundaries |

---

## 10. Những gì FE-04 chưa quyết định

FE-04 tạo working baselines. Các quyết định methodology sau **chưa được FE-04 thực hiện** và thuộc về các phase tiếp theo:

- **Final RFM Frequency:** Chưa chọn variant nào trong 4 variants. FE-05 sẽ so sánh trong `frequency_variants_comparison.csv`.
- **Final RFM Monetary semantics:** Chưa quyết định giữ signed / absolute / purchase-only / cancellation-only. FE-05 sẽ so sánh trong `monetary_definition_comparison.csv`.
- **Cancellation/return treatment:** Chưa quyết định có tính cancellation/return vào Monetary, có loại khỏi Frequency, hay giữ riêng. FE-05 chịu trách nhiệm.
- **Feature selection:** Chưa chọn feature nào là working candidate. FE-05 sẽ chọn 14 candidate features.
- **Transformation / scaling:** Chưa áp dụng. FE-06 (transformation + scaling) sẽ thực hiện trên `customer_candidates.parquet` (output của FE-05).
- **Clustering:** Chưa thực hiện. Thuộc phase sau FE-06.
- **Outlier removal / winsorize / clip:** Chưa thực hiện.

---

## 11. Limitations / Points for Mentor Review

### 11.1. Signed monetary (TotalMonetary)

`TotalMonetary` được tính dưới dạng **signed baseline**: cancellation/return rows làm giảm tổng. Đây là baseline trung thực nhất theo quan điểm tài khoản, nhưng có thể gây khó khăn cho các thuật toán clustering giả định distribution dương. FE-05 và FE-06 sẽ review sign convention. **Cần mentor review để quyết định final semantics.**

### 11.2. Signed quantity (TotalQuantity)

Tương tự TotalMonetary: 40 khách hàng có TotalQuantity âm do cancellation/return rows vượt trội. **Cần mentor review để quyết định final policy.**

### 11.3. PurchaseFrequency = DistinctInvoiceCount (working proxy)

Trong FE-04, `PurchaseFrequency` được set bằng `DistinctInvoiceCount` theo working proxy. Đây chưa phải định nghĩa RFM Frequency cuối cùng. FE-05 sẽ so sánh với các variant khác (`Frequency_ByTransactionLine`, v.v.) trước khi quyết định. **Mentor review để xác nhận baseline này đủ để FE-05 reference.**

### 11.4. Cancellation/return treatment pending

Hai feature `CancellationInvoiceCount` và `ReturnInvoiceCount` được tính từ flag của FE-02 (`IsCancellation`, `IsReturn`). Tuy nhiên:

- `CancellationInvoiceCount == ReturnInvoiceCount` cho tất cả customers trong dataset này (cùng mean/median/min/max = 0.84/0/47).
- Trong dataset, hai flag này trùng giá trị; nếu chúng khác nhau trong tương lai, cần review.
- Quyết định có tính cancellation/return rows vào Monetary hay tách riêng thuộc FE-05.

**Cần mentor review để xác nhận baseline counting đúng.**

### 11.5. AverageTransactionValue vs AverageInvoiceValue

Hai feature có tên semantic gần giống nhưng thuộc hai phase khác nhau:
- `AverageTransactionValue` (FE-04): `TotalMonetary / DistinctInvoiceCount`.
- `AverageInvoiceValue` (FE-05 candidate): `Monetary / Frequency` (với Frequency là RFM Frequency chính thức).

Nếu FE-05 chọn Frequency = DistinctInvoiceCount, hai giá trị sẽ giống nhau. Nếu FE-05 chọn Frequency variant khác, hai giá trị sẽ khác. **Mentor review cần nhận thức sự phân biệt này khi đọc reports.**

### 11.6. Deterministic sort theo TotalMonetary desc

Output `customer_base.parquet` được sort theo `TotalMonetary desc, CustomerID asc`. Đây là implementation detail giúp reproducibility. **Không ảnh hưởng schema hay feature values**, chỉ ảnh hưởng thứ tự dòng.

---

## 12. Kết luận

FE-04 đã thực hiện thành công customer-level aggregation trên 401,564 dòng transaction-level, tạo ra `customer_base.parquet` với 4,371 khách hàng (mỗi khách hàng một dòng) và 11 aggregate features. Pipeline deterministic, validation 10/11 PASS (1 WARNING có chủ đích về signed baseline), SHA-256 verify toàn vẹn input.

Sản phẩm FE-04 là **base dataset** cho FE-05, **không phải final clustering dataset**. FE-05 sẽ tiếp tục xây dựng RFM, behavioral features, và candidate selection từ `customer_base.parquet`. Các working baseline features của FE-04 (PurchaseFrequency, TotalMonetary, AverageTransactionValue, cancellation/return counts) là **reversible**: chúng có thể được FE-05 review và điều chỉnh nếu cần.

Mọi aggregate feature đều được đánh dấu `WORKING_ASSUMPTION` trong `configs/aggregation.yaml` và `reports/fe04/feature_dictionary.csv`. Promotion sang final methodology yêu cầu mentor review và ADR.

---

*Tài liệu này được viết để mentor review. Số liệu trích từ execution thực tế, không tự tạo. Mọi PENDING_REVIEW decision được nêu rõ trong mục 11.*
