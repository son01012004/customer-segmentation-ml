# FE-06 — Transformation, Scaling & Final Clustering Dataset: Lý thuyết và Kết quả thực hiện

> **Tài liệu cho mentor review.**
> Phiên bản: FE-06 (Transformation + Scaling + Working Final Dataset).
> Mọi số liệu trong tài liệu này được lấy trực tiếp từ `reports/fe06/` (sinh từ execution thực tế) và các file parquet đầu ra đã được kiểm tra trực tiếp.
> Tài liệu KHÔNG mô tả cách cài đặt hay hướng dẫn sử dụng code; KHÔNG thay thế `reports/fe06/narrative_report.md` (báo cáo vận hành).

**Trạng thái dataset:**
- Dataset version: `FE06-v1.0` (initial technically generated working dataset)
- Dataset status: `TECHNICALLY_GENERATED` (chưa được mentor approve)
- Working configuration: `C7` (yeo_johnson + robust + median) — `WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING`
- **Dataset này KHÔNG phải final approved clustering dataset.** Promotion sang final cần mentor review + ADR.

---

## 1. Tổng quan FE-06

### 1.1. Mục tiêu

FE-06 chuyển **customer-level candidate features** từ FE-05 thành **working clustering dataset** có pipeline transformation + scaling reproducible, sẵn sàng làm input cho phase Clustering tiếp theo.

Cụ thể, FE-06 thực hiện:

1. **Feature Eligibility Gate** — lọc các feature `CANDIDATE` từ FE-05 vào working matrix; `CustomerID` được tách riêng; `BASE_REFERENCE` / `SOURCE_ONLY` / `UNSUPPORTED` không bao gồm.
2. **Missing / Structural Undefined Analysis** — phân biệt NaN do data-quality và NaN do structurally undefined (chỉ áp dụng với `PurchaseIntervalMean` / `PurchaseIntervalStd`).
3. **Imputation** — median cho các feature có NaN còn lại (working default).
4. **Distribution Transformation** — Yeo-Johnson cho toàn bộ 14 eligible features (working default).
5. **Scaling** — RobustScaler cho toàn bộ 14 eligible features (working default).
6. **Validation** — data quality, leakage, alignment, reproducibility.
7. **Final Clustering Dataset** — output matrix 14 cột × 4,371 dòng, không chứa CustomerID, không NaN, không Inf.
8. **Customer Metadata** — CustomerID tách riêng để map cluster labels về customer sau clustering.

### 1.2. Input

| Input | Path | Vai trò |
|---|---|---|
| Customer candidate dataset | `data/processed/customer_candidates.parquet` | 4,371 customers × 14 candidate features + CustomerID |
| Input SHA-256 | `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649` | Verify input không bị mutate |
| ReferenceDate | `2011-12-10T12:50:00` (max(InvoiceDate)+1 day) | FE-05 sở hữu; FE-06 KHÔNG recompute |

`fe06_run.json` ghi `input.sha256 = df5333fba...` — input là READ-ONLY trong toàn bộ pipeline.

### 1.3. Output

| Output | Path | Mô tả |
|---|---|---|
| Final clustering dataset | `data/processed/final_clustering_dataset.parquet` | 4,371 × 14 numeric, không CustomerID, không NaN, không Inf |
| Output SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | |
| Customer metadata | `data/processed/customer_metadata.parquet` | 4,371 × 1 (CustomerID) |
| Metadata SHA-256 | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | |
| Fitted pipeline | `data/processed/fitted_preprocessing_pipeline.pkl` | Imputation + Yeo-Johnson + RobustScaler đã fit |
| Fitted pipeline SHA-256 | `71f97103d1e7f588d1554af01725afd333dbe48f08a2783c2914c5b57482a3ec` | (informational; KHÔNG dùng byte-level equality làm hard criterion) |
| Config SHA-256 | `70ae113272918c81232521ff36760e0e4abbf02b0ec436ac0c1420823c506dd2` | `configs/transformation.yaml` |

### 1.4. Vai trò của transformation / scaling

**Transformation** làm **giảm skewness** của distribution, giúp các thuật toán clustering (đặc biệt distance-based như K-Means) không bị ảnh hưởng quá mức bởi extreme values.

**Scaling** đưa features về cùng một **thang đo** (scale), đảm bảo feature có variance lớn không lấn át feature có variance nhỏ khi tính khoảng cách Euclidean / Manhattan.

**Imputation** thay thế NaN còn sót lại (sau FE-05) bằng một giá trị ước lượng — median ổn định với outlier, không bias như mean, không gây hiểu nhầm "zero = no observation" như fill 0 (xem Mục 3).

### 1.5. Vì sao feature engineering output chưa trực tiếp trở thành clustering matrix

Một số lý do:

1. **Skewed distribution** — `Monetary` có skewness 21.7, `TotalQuantity` 22.96, `Frequency` 11.39 (pre-transformation). Distance-based clustering bị dominated bởi extreme values.
2. **Khác đơn vị / khác scale** — `Recency` (days) có variance ~10,156; `CancellationRate` có variance 0.033; cần đồng nhất scale.
3. **NaN còn lại** — `PurchaseIntervalMean` (30.0% missing) và `PurchaseIntervalStd` (48.7% missing) vì structurally undefined (xem Mục 3).
4. **CustomerID phải tách riêng** — không được đưa vào clustering matrix (leakage risk nếu vô tình dùng để identify cluster).
5. **Redundancy cần được diagnose** — không auto-drop, nhưng cần báo cáo rõ để mentor xem xét.

FE-06 đóng vai trò **chuẩn hóa** working matrix trước khi clustering algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means — năm thuật toán benchmark cố định; K-Medoids OUT OF SCOPE per ADR-0003) được áp dụng.

### 1.6. Sơ đồ pipeline FE-06

```
customer_candidates.parquet  (FE-05 output, READ-ONLY)
        ↓
Feature Eligibility Gate
(include CANDIDATE only; exclude BASE_REFERENCE, IDENTIFIER_ONLY,
 SOURCE_ONLY, UNSUPPORTED; exclude CustomerID → metadata)
        ↓
Missing / Structural N/A Analysis
(distinguish STRUCTURALLY_UNDEFINED from data-quality NaN)
        ↓
Imputation
(median cho PurchaseIntervalMean, PurchaseIntervalStd)
        ↓
Distribution Transformation
(yeo_johnson cho toàn bộ 14 features)
        ↓
Scaling
(robust cho toàn bộ 14 features)
        ↓
Validation
(data quality, leakage, alignment, reproducibility)
        ↓
final_clustering_dataset.parquet  (14 features × 4,371 customers)
        +
customer_metadata.parquet        (CustomerID × 4,371)
        +
fitted_preprocessing_pipeline.pkl (cho reload / transform reproducibility)
```

---

## 2. Cơ sở lý thuyết

### 2.1. Feature Transformation — Tại sao cần transformation

Distribution của customer features thường bị **skewed** (lệch phải / lệch trái) do:
- Phần lớn khách hàng có hành vi "bình thường" (một vài giao dịch, giá trị nhỏ).
- Một số ít khách hàng có hành vi "extreme" (mua rất nhiều, giá trị rất lớn).

Các thuật toán clustering distance-based (đặc biệt K-Means với Euclidean) **nhạy cảm với extreme values** vì khoảng cách bị dominated bởi vài điểm outlier. Transformation nhằm **kéo distribution về gần đối xứng**, giảm ảnh hưởng của outliers.

### 2.2. Log Transformation

**Nguyên lý:** `x → log(x)` (với `log1p(x) = log(1 + x)` để xử lý x = 0).

**Ưu điểm:**
- Đơn giản, dễ hiểu.
- Hiệu quả với right-skewed data (giá trị lớn bị "kéo" xuống mạnh).

**Nhược điểm:**
- **Không áp dụng được cho giá trị âm** (log của số âm không xác định).
- `log1p` xử lý được `x = 0` nhưng vẫn không xử lý được `x < 0`.

**Điều kiện áp dụng trong FE-06:**
- 6/14 features có giá trị âm (`Monetary`, `TotalQuantity`, `AverageQuantity`, `BasketSize`, `AverageInvoiceValue`, `CancellationRate`/`ReturnRate` ở dạng signed baseline) → `log1p` không full-matrix applicable.
- Vì vậy log1p chỉ dùng diagnostic-only cho non-negative subset; **KHÔNG full-matrix comparable** trong C7.

### 2.3. Yeo-Johnson

**Nguyên lý:** extension của Box-Cox transformation, hỗ trợ cả giá trị âm, dương và zero. Đây là implementation `sklearn.preprocessing.PowerTransformer(method='yeo-johnson')`. Transformation tìm hệ số `λ` tối ưu cho mỗi feature bằng maximum likelihood để distribution kết quả gần Gaussian nhất.

**Ưu điểm:**
- Xử lý được **cả giá trị âm và không âm** → đơn giản hóa pipeline.
- Một transformation cho toàn bộ 14 features.
- Đã được triển khai sẵn trong sklearn (chuẩn công nghiệp).

**Vì sao có thể phù hợp với các feature hiện tại:**
- Nhiều feature có heavy-tail / right-skewed (Monetary, TotalQuantity, Frequency).
- Một số feature có giá trị âm (Monetary, TotalQuantity, AverageQuantity, BasketSize, AverageInvoiceValue — từ FE-04 signed baseline).
- CancellationRate / ReturnRate có range [0, 1] nhưng vẫn áp dụng được Yeo-Johnson (output range mở rộng).

**KHÔNG kết luận là "phương pháp tốt nhất":**
- Yeo-Johnson là **WORKING_ASSUMPTION** trong C7.
- Trong experimental matrix có C0–C7 (xem Mục 5) — chỉ C7 là working; các configuration khác không được đánh giá là tốt hơn / kém hơn.

### 2.4. Scaling

Scaling đưa features về cùng thang đo để distance-based clustering không bị dominated bởi feature có variance lớn. Ba scaler phổ biến:

#### 2.4.1. StandardScaler

**Công thức:** `z = (x - mean) / std` → mean = 0, std = 1.

**Vai trò:** Biến đổi về standard normal. Phù hợp với distribution đã gần Gaussian sau transformation.

**Sensitivity:** Mean và std bị ảnh hưởng bởi outliers.

#### 2.4.2. MinMaxScaler

**Công thức:** `x_scaled = (x - min) / (max - min)` → range [0, 1].

**Vai trò:** Đưa về range cố định. Phù hợp với neural networks hoặc khi cần bounded input.

**Sensitivity:** Min/max bị ảnh hưởng mạnh bởi outliers (một điểm extreme có thể nén toàn bộ distribution).

#### 2.4.3. RobustScaler

**Công thức:** `x_scaled = (x - median) / IQR` → median = 0, IQR = 1.

**Vai trò:** **Tolerant với outliers** vì dùng median và IQR (quartile-based), không bị dominated bởi extreme values.

**Phù hợp với FE-06:** Distribution sau Yeo-Johnson vẫn có một số features có outlier (xem `outlier_analysis.csv`). RobustScaler ổn định hơn StandardScaler / MinMaxScaler trong trường hợp này.

#### 2.4.4. Vai trò của scaling trong distance-based clustering

K-Means, Agglomerative, DBSCAN (với Ward / Euclidean / Manhattan linkage) đều dùng **khoảng cách** giữa các điểm. Nếu feature A có variance 10⁵ và feature B có variance 1, khoảng cách sẽ chủ yếu phản ánh sự khác biệt về feature A, bỏ qua feature B. Scaling đảm bảo **mỗi feature đóng góp công bằng** vào khoảng cách.

**KHÔNG nói scaler nào tốt nhất:** RobustScaler là WORKING_ASSUMPTION trong C7; các scaler khác là candidates trong experimental matrix.

---

## 3. Missing Values và Structural Undefined

### 3.1. Hai loại NaN

FE-06 phân biệt rõ hai loại NaN:

**Data-quality missing:** NaN do lỗi dữ liệu, sensor failure, hoặc missing trong input. Thường có thể impute bằng mean / median / mode.

**Structurally undefined:** NaN vì **khái niệm không xác định được** trong trường hợp cụ thể. Không phải lỗi dữ liệu.

### 3.2. PurchaseIntervalMean / PurchaseIntervalStd — Structural NaN

#### 3.2.1. PurchaseIntervalMean

Công thức: `diff(invoice_dates).mean()` trên chuỗi các ngày hóa đơn.

**Vấn đề:**
- Nếu khách hàng có **< 2 invoices** → `diff()` trên chuỗi 1 phần tử cho chuỗi rỗng → `mean()` của rỗng → `NaN`.
- Số khách hàng bị NaN: **1,312 / 4,371 = 30.0%**.

**Lý do không fill 0:** Fill 0 sẽ nói rằng "khách hàng này có interval trung bình = 0 ngày" — sai semantics. Khách hàng có 1 invoice không có khái niệm "interval trung bình" — NaN phản ánh "không tính được", không phải "interval = 0".

#### 3.2.2. PurchaseIntervalStd

Công thức: `diff(invoice_dates).std(ddof=1)` trên chuỗi các ngày hóa đơn.

**Vấn đề (gấp đôi):**
1. Nếu khách hàng có **< 2 invoices** → NaN vì `diff()` trả về rỗng (giống `PurchaseIntervalMean`).
2. Nếu khách hàng có **đúng 2 invoices** → `diff()` trả về 1 phần tử; `std(ddof=1)` trên 1 phần tử **không xác định về mặt toán học** (sample std với `n = 1` và `ddof = 1` cho NaN).
- Số khách hàng bị NaN: **2,129 / 4,371 = 48.7%** (nhiều hơn Mean vì cả 2 cases).

**Lý do không fill 0:** Tương tự PurchaseIntervalMean — fill 0 sẽ nói "độ đều đặn của interval = 0", không có ý nghĩa.

### 3.3. Imputation strategy: Median (WORKING_ASSUMPTION)

`imputation_semantics.csv` ghi:

| Feature | NaN before | NaN after | Median used | Semantics |
|---|---|---|---|---|
| `PurchaseIntervalMean` | 1,312 | 0 | 41.0 | STRUCTURALLY_UNDEFINED |
| `PurchaseIntervalStd` | 2,129 | 0 | 32.58504379012092 | STRUCTURALLY_UNDEFINED |

**Median imputation rationale (working, từ `configs/transformation.yaml`):**
- "Median ổn định với outlier; không bias như mean; không gây hiểu nhầm 'zero = no interval' như fill 0."
- WORKING_ASSUMPTION — chưa được mentor approve.
- Status trong `fe06_run.json`: `working_imputation_status = "WORKING_ASSUMPTION"`, `working_imputation_review = "MENTOR_REVIEW_PENDING"`.

---

## 4. Feature Eligibility

### 4.1. Eligibility Gate

`feature_eligibility.csv` ghi nhận từng feature qua gate với các trường:

- `Feature`, `FE05_Layer`, `FE05_Decision`, `FE06_Status`, `FE06_Trace`
- `Eligibility_Reason`, `Variance`, `MissingRatio`, `Is_Numeric`

### 4.2. Eligible count

- **Eligible features: 14**
- **Excluded features: 0** (trong số CANDIDATE features)
- **CustomerID: METADATA_ONLY** — tách riêng vào `customer_metadata.parquet`, không bao gồm trong matrix.

### 4.3. FE-05 decision traceability

| Feature | FE-05 decision | FE-06 status | Included in C7? |
|---|---|---|---|
| `Recency` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `Frequency` | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Yes |
| `Monetary` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `TotalQuantity` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `AverageQuantity` | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Yes |
| `BasketSize` | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Yes |
| `TenureDays` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `PurchaseIntervalMean` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `PurchaseIntervalStd` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `ActiveDays` | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Yes |
| `AverageInvoiceValue` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `ProductsPerInvoice` | RETAIN_CANDIDATE | ELIGIBLE | Yes |
| `CancellationRate` | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Yes |
| `ReturnRate` | PENDING_REVIEW | ELIGIBLE_WORKING_ASSUMPTION | Yes |

### 4.4. `ELIGIBLE_WORKING_ASSUMPTION` ≠ `APPROVED`

Toàn bộ **6 features PENDING_REVIEW từ FE-05** được include trong C7 working dataset với status `ELIGIBLE_WORKING_ASSUMPTION`. Đây là **working default** cho phép pipeline chạy được, **KHÔNG đồng nghĩa với việc feature đã được mentor approve** để dùng trong clustering.

Workflow:
```
FE-05 PENDING_REVIEW
  → FE-06 ELIGIBLE_WORKING_ASSUMPTION
  → C7 working configuration
  → MENTOR_REVIEW_PENDING
```

Promotion từ `ELIGIBLE_WORKING_ASSUMPTION` → `APPROVED` (cho phase Clustering) cần mentor review + ADR.

---

## 5. Transformation/Scaling Experimental Design

### 5.1. Configuration matrix (`comparison_matrix.csv`)

| Config_ID | Transformation | Scaling | Is_Full_Matrix | Is_Working | Status |
|---|---|---|---|---|---|
| `C0` | none | none | True | False | CANDIDATE |
| `C1` | none | standard | True | False | CANDIDATE |
| `C2` | none | minmax | True | False | CANDIDATE |
| `C3` | none | robust | True | False | CANDIDATE |
| `C6` | yeo_johnson | standard | True | False | CANDIDATE |
| `C7` | yeo_johnson | robust | True | **True** | **WORKING_ASSUMPTION** |

**Note:** `C4` / `C5` không tồn tại trong matrix (đã loại bỏ trong Plan V2). Log1p-based configurations (T1 + Sx) không full-matrix comparable vì nhiều feature có giá trị âm.

### 5.2. Quy tắc

- **Full-matrix configurations:** 6 configs (C0, C1, C2, C3, C6, C7) — tất cả áp dụng cùng transformation/scaling cho toàn bộ 14 eligible features.
- **Chỉ C7 materialized:** `Is_Working = True` chỉ với C7; các config khác chỉ là **candidates**, không đánh giá.
- **KHÔNG ranking / scoring:** Các config không được xếp hạng theo metric nào. So sánh diagnostic only.
- **Working default = C7:** Implemented để có một working clustering matrix sẵn sàng cho clustering phase.

### 5.3. Per-feature applicability (`transformation_policy.per_feature_applicability`)

`configs/transformation.yaml` định nghĩa rõ per-feature applicability:

| Feature | Applicable transformations | Note |
|---|---|---|
| `Recency` | none, log1p, yeo_johnson | Tất cả |
| `Frequency` | none, log1p, yeo_johnson | Tất cả |
| `Monetary` | none, yeo_johnson | **Có âm → không log1p** |
| `TotalQuantity` | none, yeo_johnson | **Có âm → không log1p** |
| `AverageQuantity` | none, yeo_johnson | **Có âm → không log1p** |
| `BasketSize` | none, yeo_johnson | **Có âm → không log1p** |
| `TenureDays` | none, log1p, yeo_johnson | Tất cả |
| `PurchaseIntervalMean` | none, log1p, yeo_johnson | Tất cả (sau imputation) |
| `PurchaseIntervalStd` | none, log1p, yeo_johnson | Tất cả (sau imputation) |
| `ActiveDays` | none, log1p, yeo_johnson | Tất cả |
| `AverageInvoiceValue` | none, yeo_johnson | **Có âm → không log1p** |
| `ProductsPerInvoice` | none, log1p, yeo_johnson | Tất cả |
| `CancellationRate` | none, yeo_johnson | Rate [0,1]; yeo_johnson diagnostic |
| `ReturnRate` | none, yeo_johnson | Rate [0,1]; yeo_johnson diagnostic |

Trong C7: **toàn bộ 14 features** đều dùng `yeo_johnson` — KHÔNG có ngoại lệ per-feature.

---

## 6. C7 Working Configuration

### 6.1. Bảng cấu hình

| Thành phần | Working configuration | Trạng thái |
|---|---|---|
| Features | 14 features (CANDIDATE only) | Working |
| Transformation | `yeo_johnson` (sklearn PowerTransformer) | Working assumption |
| Scaling | `robust` (sklearn RobustScaler, median=0, IQR=1) | Working assumption |
| Imputation | `median` (PurchaseIntervalMean, PurchaseIntervalStd) | Working assumption |
| Dataset version | `FE06-v1.0` | Technically generated |
| Dataset status | `TECHNICALLY_GENERATED` | Working |
| Random seed | `null` (deterministic pipeline) | Determinism |

### 6.2. Methodology rationale (trung lập)

**Imputation = median:**
- Median ổn định với outlier.
- Không bias như mean.
- Không gây hiểu nhầm "zero = no interval" như fill 0.
- Phù hợp với STRUCTURALLY_UNDEFINED semantics (median phản ánh "typical behavior").

**Transformation = Yeo-Johnson:**
- Xử lý được cả giá trị âm và không âm.
- Đơn giản hóa pipeline: 1 transformation cho toàn bộ 14 features.
- Đã được implement chuẩn trong sklearn (`PowerTransformer`).

**Scaling = RobustScaler:**
- Tolerant với outliers (median/IQR-based).
- Phù hợp với distribution vẫn có outliers sau Yeo-Johnson (xem `outlier_analysis.csv`: Monetary có 343 outliers, PurchaseIntervalStd có 2020 outliers).
- Mean = 0, IQR = 1 — tương đương StandardScaler về median-centered.

### 6.3. C7 KHÔNG phải final approved methodology

C7 là **working configuration**, KHÔNG phải final approved. Tài liệu này KHÔNG gọi C7 là:
- ❌ "final approved"
- ❌ "best"
- ❌ "recommended"
- ❌ "optimal"

C7 chỉ là **technically generated working default** để pipeline chạy được. Promotion sang final cần mentor review + ADR.

---

## 7. Redundancy Analysis

### 7.1. Ba cặp redundancy được phát hiện

`redundancy_analysis.csv` ghi nhận 3 cặp có `|Pearson| ≥ 0.95` (threshold = 0.95 từ `feature_eligibility.redundancy_threshold`).

| Feature1 | Feature2 | Pearson | Spearman | EqualityRate | MaxAbsDiff | Category |
|---|---|---|---|---|---|---|
| `AverageQuantity` | `BasketSize` | 1.0000 | 1.0000 | 1.0000 | 0.0000 | `DUPLICATE_INFORMATION` |
| `CancellationRate` | `ReturnRate` | 1.0000 | 1.0000 | 1.0000 | 0.0000 | `DUPLICATE_INFORMATION` |
| `Frequency` | `ActiveDays` | 0.9743 | 0.9834 | 0.7735 | 108.0 | `HIGH_CORRELATION` |

### 7.2. Phân loại redundancy (`redundancy_analysis.csv` categories)

Category có 4 loại:
- `DUPLICATE_INFORMATION` — empirical equality across all rows.
- `HIGH_CORRELATION` — `|Pearson| ≥ threshold` but not identical.
- `DISTINCT_BUT_RELATED` — both features documented but correlation below threshold.
- `PENDING_REVIEW` — insufficient evidence.

### 7.3. Chi tiết từng cặp

#### 7.3.1. `AverageQuantity` ↔ `BasketSize` (DUPLICATE_INFORMATION)

**Definitions:**
- `AverageQuantity = sum(Quantity) / nunique(InvoiceNo)` per CustomerID (signed; includes cancellations).
- `BasketSize = alias for AverageQuantity` per CustomerID (signed).

**Evidence:**
- Pearson = 1.0000
- Spearman = 1.0000
- EqualityRate = 1.0000
- MaxAbsDiff = 0.0000

**Phân tích:**
- Hai feature này bằng nhau cho **tất cả 4,371 customer** — `BasketSize` được FE-05 định nghĩa là alias cho `AverageQuantity`.
- Đây là **mathematical identity by construction** — cùng công thức, khác tên.
- `BasketSize` không mang thêm thông tin so với `AverageQuantity`.

**Quyết định:**
- ❌ KHÔNG auto-drop.
- ⏳ PENDING_REVIEW — promotion sang final cần mentor review.

#### 7.3.2. `CancellationRate` ↔ `ReturnRate` (DUPLICATE_INFORMATION)

**Definitions:**
- `CancellationRate = CancellationInvoiceCount / Frequency`
- `ReturnRate = ReturnInvoiceCount / Frequency`

**Evidence:**
- Pearson = 1.0000
- Spearman = 1.0000
- EqualityRate = 1.0000
- MaxAbsDiff = 0.0000

**Phân tích:**
- Hai feature này bằng nhau cho **tất cả 4,371 customer** — `CancellationInvoiceCount == ReturnInvoiceCount` trong dataset hiện tại.
- Hai flag `IsCancellation` và `IsReturn` (từ FE-02) có cùng giá trị trên cùng rows trong dataset này.
- Đây là **duplicate information by data coincidence**, KHÔNG phải mathematical identity — công thức khác nhau về khái niệm, nhưng giá trị giống nhau vì flag giống nhau.
- Nếu flag trong tương lai thay đổi, hai rate có thể khác nhau.

**Quyết định:**
- ❌ KHÔNG auto-drop.
- ⏳ PENDING_REVIEW — promotion sang final cần mentor review.

#### 7.3.3. `Frequency` ↔ `ActiveDays` (HIGH_CORRELATION)

**Definitions:**
- `Frequency = nunique(InvoiceNo)` per CustomerID.
- `ActiveDays = nunique(date(InvoiceDate))` per CustomerID.

**Evidence:**
- Pearson = 0.9743 (≥ threshold 0.95)
- Spearman = 0.9834
- EqualityRate = 0.7735 (< 1.0)
- MaxAbsDiff = 108.0

**Phân tích:**
- Hai feature **không identical** (EqualityRate chỉ 77.35%) — vẫn có 22.65% customer có `Frequency ≠ ActiveDays`.
- Lý do: một số khách hàng có **nhiều invoice trong cùng một ngày** (Frequency > ActiveDays trong những trường hợp đó).
- Cùng thông tin về "khách hàng mua nhiều lần", nhưng khác nhau về granularity (invoice-level vs calendar-day-level).
- Đây là **related but distinct** — high correlation nhưng KHÔNG duplicate.

**Quyết định:**
- ❌ KHÔNG auto-drop.
- ⏳ PENDING_REVIEW — promotion sang final cần mentor review.

### 7.4. Phân biệt các khái niệm

FE-06 redundancy gate phân biệt rõ:

| Concept | Definition | Example |
|---|---|---|
| **Duplicate information** | Empirical equality across all rows (1 carries same info as the other) | `AverageQuantity` ↔ `BasketSize` |
| **High correlation** | `\|Pearson\| ≥ threshold` but NOT identical | `Frequency` ↔ `ActiveDays` |
| **Related but distinct** | Both features documented but correlation < threshold | (n/a in current dataset) |
| **Mathematical identity** | Same formula by construction | `AverageQuantity` ↔ `BasketSize` |
| **Data coincidence** | Different formulas but same values due to data | `CancellationRate` ↔ `ReturnRate` |

**FE-06 KHÔNG ranking các feature.** Tất cả 14 eligible features đều có mặt trong C7 working matrix. Mentor sẽ quyết định promotion logic.

---

## 8. Final Clustering Dataset

### 8.1. File output

- **Path:** `data/processed/final_clustering_dataset.parquet`
- **SHA-256:** `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`
- **Shape:** (4,371, 14) — 4,371 customers × 14 features
- **Dataset version:** `FE06-v1.0`
- **Dataset status:** `TECHNICALLY_GENERATED`

### 8.2. Schema

| # | Feature | dtype (post-scaling) | Variance (pre-transform) | MissingRatio (pre-imputation) |
|---|---|---|---|---|
| 1 | `Recency` | float64 | 10,155.97 | 0.0 |
| 2 | `Frequency` | float64 | 87.10 | 0.0 |
| 3 | `Monetary` | float64 | 67,561,603.61 | 0.0 |
| 4 | `TotalQuantity` | float64 | 21,740,797.79 | 0.0 |
| 5 | `AverageQuantity` | float64 | 67,958.03 | 0.0 |
| 6 | `BasketSize` | float64 | 67,958.03 | 0.0 |
| 7 | `TenureDays` | float64 | 17,689.08 | 0.0 |
| 8 | `PurchaseIntervalMean` | float64 | 3,810.59 | 0.30 |
| 9 | `PurchaseIntervalStd` | float64 | 1,418.38 | 0.49 |
| 10 | `ActiveDays` | float64 | 44.55 | 0.0 |
| 11 | `AverageInvoiceValue` | float64 | 130,294.35 | 0.0 |
| 12 | `ProductsPerInvoice` | float64 | 256.91 | 0.0 |
| 13 | `CancellationRate` | float64 | 0.033 | 0.0 |
| 14 | `ReturnRate` | float64 | 0.033 | 0.0 |

### 8.3. Data quality checks (`data_quality_report.csv`)

| Check | Status | Message |
|---|---|---|
| `row_count` | PASS | Expected 4371 rows, got 4371. |
| `no_identifier_in_matrix` | PASS | No identifier columns in matrix. |
| `no_nan` | PASS | No NaN values in matrix. |
| `no_inf` | PASS | No Inf values in matrix. |
| `no_constant_feature` | PASS | No constant features. |
| `all_numeric` | PASS | All columns are numeric. |
| `customer_metadata_alignment` | PASS | Metadata and matrix aligned: 4371 rows, 4371 unique CustomerIDs, no NaN. |

### 8.4. Direct verification

Kiểm tra trực tiếp file parquet (sau khi execution):

- **Shape:** (4,371, 14) ✓
- **Unique customers (qua metadata):** 4,371 ✓
- **NaN per column:** tất cả 14 columns đều 0 ✓
- **Inf per column:** tất cả 14 columns đều 0 ✓
- **Constant features:** không có ✓
- **Tất cả columns numeric:** ✓

### 8.5. Post-scaling distribution snapshot

Một số đặc trưng phân phối sau scaling (`distribution_post_scaling.csv`):

| Feature | Mean | Std | Skewness | Outliers (IQR) |
|---|---|---|---|---|
| `Recency` | -0.009 | 0.621 | -0.052 | 0 |
| `Frequency` | -0.076 | 0.516 | 0.183 | 0 |
| `Monetary` | 0.529 | 3.008 | 5.092 | 343 (7.85%) |
| `TotalQuantity` | 0.364 | 1.737 | 2.705 | 274 (6.27%) |
| `AverageQuantity` | 0.221 | 1.254 | 2.584 | 214 (4.90%) |
| `BasketSize` | 0.221 | 1.254 | 2.584 | 214 (4.90%) |
| `TenureDays` | -0.158 | 0.447 | -0.294 | 0 |
| `PurchaseIntervalMean` | 0.032 | 1.290 | 0.114 | 566 (12.95%) |
| `PurchaseIntervalStd` | 0.243 | 12.471 | 0.149 | 2,020 (46.21%) |
| `ActiveDays` | 0.139 | 0.496 | 0.187 | 0 |
| `AverageInvoiceValue` | 0.348 | 1.662 | 3.634 | 291 (6.66%) |
| `ProductsPerInvoice` | 0.003 | 0.763 | -0.003 | 16 (0.37%) |
| `CancellationRate` | 0.390 | 0.532 | 0.717 | 0 |
| `ReturnRate` | 0.390 | 0.532 | 0.717 | 0 |

**Observations:**
- Sau Yeo-Johnson + RobustScaler, các features có median ≈ 0 và IQR ≈ 1 (theo RobustScaler).
- Outlier vẫn còn ở một số features (PurchaseIntervalStd: 46.21%, PurchaseIntervalMean: 12.95%) — chỉ mang tính diagnostic; **KHÔNG remove / winsorize / clip** trong FE-06.

---

## 9. Customer Metadata

### 9.1. Tại sao tách CustomerID

FE-06 tách `CustomerID` ra khỏi clustering matrix để:

1. **Tránh leakage:** Một identifier (CustomerID) trong clustering matrix có thể vô tình trở thành feature phân biệt cluster, gây leakage — cluster gắn với CustomerID thay vì hành vi.
2. **Map cluster labels sau clustering:** Sau khi clustering algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means) sinh ra cluster labels (mỗi customer được gán 1 cluster), cần map ngược label về CustomerID để profiling / reporting.

### 9.2. File output

- **Path:** `data/processed/customer_metadata.parquet`
- **Shape:** (4,371, 1) — 4,371 customers × 1 column
- **Columns:** `CustomerID` (Int64)
- **SHA-256:** `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2`

### 9.3. Alignment validation

`leakage_check.csv` và `data_quality_report.csv` xác nhận:

| Check | Status | Message |
|---|---|---|
| `Metadata_has_CustomerID` | PASS | CustomerID in metadata. |
| `Metadata_row_count_matches_matrix` | PASS | Row counts match: 4371. |
| `customer_metadata_alignment` | PASS | Metadata and matrix aligned: 4371 rows, 4371 unique CustomerIDs, no NaN. |
| `no_identifier_columns_in_matrix` | PASS | No identifier columns in matrix. |
| `CustomerID_absent_from_matrix` | PASS | CustomerID not in clustering matrix. |

### 9.4. Alignment properties

- **Row count:** 4,371 (matches final matrix exactly).
- **Unique CustomerIDs:** 4,371 (100% unique — không có duplicate).
- **NaN CustomerID:** 0.
- **Order/position:** Verified by position — `customer_metadata.CustomerID[i]` tương ứng với row `i` trong `final_clustering_dataset`. Verified by `alignment_status = "verified_by_position_and_unique_key"` (từ config A6).

**KHÔNG sort metadata độc lập với final matrix** — giữ nguyên thứ tự từ source candidate order.

---

## 10. Reproducibility và Dataset Version

### 10.1. Dataset version

- **Version:** `FE06-v1.0`
- **Meaning:** initial technically generated working dataset
- **Status:** `TECHNICALLY_GENERATED` (chưa được mentor approve)

Promotion sang `RESEARCH_APPROVED_FINAL` cần mentor review + ADR. FE-06 **KHÔNG tự động promote**.

### 10.2. SHA-256 chain

| Asset | SHA-256 |
|---|---|
| Input: `customer_candidates.parquet` | `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649` |
| Output: `final_clustering_dataset.parquet` | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Output: `customer_metadata.parquet` | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` |
| Fitted pipeline: `fitted_preprocessing_pipeline.pkl` | `71f97103d1e7f588d1554af01725afd333dbe48f08a2783c2914c5b57482a3ec` (informational) |
| Config: `configs/transformation.yaml` | `70ae113272918c81232521ff36760e0e4abbf02b0ec436ac0c1420823c506dd2` |

### 10.3. Pipeline parameters

**Imputation median values (per feature):**
- `PurchaseIntervalMean`: 41.0
- `PurchaseIntervalStd`: 32.58504379012092

**Yeo-Johnson lambda values (per feature, fitted by sklearn):**

| Feature | λ |
|---|---|
| `Recency` | 0.1202 |
| `Frequency` | -0.6393 |
| `Monetary` | 0.7743 |
| `TotalQuantity` | 0.6076 |
| `AverageQuantity` | 0.7445 |
| `BasketSize` | 0.7445 |
| `TenureDays` | 0.2023 |
| `PurchaseIntervalMean` | 0.2469 |
| `PurchaseIntervalStd` | 0.2268 |
| `ActiveDays` | -0.6856 |
| `AverageInvoiceValue` | 0.9693 |
| `ProductsPerInvoice` | 0.0908 |
| `CancellationRate` | -7.4568 |
| `ReturnRate` | -7.4568 |

### 10.4. Feature list

14 features trong C7:
`Recency, Frequency, Monetary, TotalQuantity, AverageQuantity, BasketSize, TenureDays, PurchaseIntervalMean, PurchaseIntervalStd, ActiveDays, AverageInvoiceValue, ProductsPerInvoice, CancellationRate, ReturnRate`.

### 10.5. Execution metadata

- **Executed at:** `2026-09-20T14:24:16.701083+00:00`
- **Python:** 3.14.4
- **System:** Linux 7.0.0-31-generic, x86_64
- **Library versions:**
  - numpy 2.3.5
  - pandas 3.0.6
  - scipy 1.18.1
  - scikit-learn 1.9.1
  - pyarrow 25.0.1
- **Random seed:** `null` (deterministic pipeline, no random state used)

### 10.6. Pickle determinism note

Config A5 ghi: "Pickle SHA ghi trong metadata nếu file tồn tại, NHƯNG: KHÔNG dùng byte-level SHA equality cross-environment làm hard acceptance criterion."

Lý do: pickle format có thể khác giữa các Python version / OS / library version nhỏ. Pickle SHA chỉ mang tính informational; final_clustering_dataset.parquet SHA là primary reproducibility check.

---

## 11. Validation Results

### 11.1. Data quality (`data_quality_report.csv`)

Tất cả 7 checks PASS:
- `row_count`: PASS
- `no_identifier_in_matrix`: PASS
- `no_nan`: PASS
- `no_inf`: PASS
- `no_constant_feature`: PASS
- `all_numeric`: PASS
- `customer_metadata_alignment`: PASS

### 11.2. Leakage check (`leakage_check.csv`)

Tất cả 8 checks PASS:

| Check | Status |
|---|---|
| `no_identifier_columns_in_matrix` | PASS |
| `CustomerID_absent_from_matrix` | PASS |
| `InvoiceNo_absent_from_matrix` | PASS |
| `StockCode_absent_from_matrix` | PASS |
| `InvoiceDate_absent_from_matrix` | PASS |
| `Cluster_labels_absent_from_matrix` | PASS |
| `Metadata_has_CustomerID` | PASS |
| `Metadata_row_count_matches_matrix` | PASS |

### 11.3. Input integrity (`tests/test_input_integrity.py`)

Các tests verify input `customer_candidates.parquet` không bị mutate:

- `test_input_file_sha_unchanged`: SHA-256 file trước và sau pipeline phải identical.
- `test_input_content_unchanged`: DataFrame content không thay đổi.

→ Pipeline KHÔNG sửa / overwrite FE-05 output.

### 11.4. Pipeline FE-06 tests (`tests/test_pipeline_fe06.py`)

22 tests covering:

- `test_load_real_config`: load `configs/transformation.yaml` thành công.
- `test_pipeline_produces_output`: pipeline chạy và sinh output files.
- `test_final_matrix_shape`: output matrix có shape đúng (4,371 × 14).
- `test_customerid_not_in_matrix`: CustomerID không có trong matrix.
- `test_metadata_row_count_matches_matrix`: metadata row count = matrix row count.
- `test_no_nan_in_final_matrix`: matrix không có NaN.
- `test_no_inf_in_final_matrix`: matrix không có Inf.
- `test_input_sha_unchanged`: input SHA không đổi.
- `test_all_reports_exist`: tất cả reports được sinh.
- `test_no_cluster_labels_in_matrix`: không có cluster labels trong matrix.
- `test_working_config_c7_applied`: C7 đúng là working configuration.
- `test_eligibility_status_map_present`: eligibility map có FE-06 status.
- `test_eligibility_fe05_map_present`: eligibility map có FE-05 decision.
- `test_averagequantity_basketsize_equal`: empirical equality của AverageQuantity/BasketSize.
- `test_cancellationrate_returnrate_equal`: empirical equality của CancellationRate/ReturnRate.
- `test_frequency_active_days_not_equal`: Frequency ≠ ActiveDays (empirical).
- `test_redundancy_analysis_report_written`: redundancy_analysis.csv được sinh.
- `test_redundancy_categories_correct`: category phân loại đúng.
- `test_imputation_semantics_report_written`: imputation_semantics.csv được sinh.
- `test_imputation_structurally_undefined`: STRUCTURALLY_UNDEFINED semantics đúng.
- `test_feature_eligibility_has_trace`: FE05→FE06 trace đúng.
- `test_feature_dictionary_has_trace`: feature dictionary có FE05→FE06 trace.

### 11.5. Deterministic behavior

- **Random seed:** `null` (từ config) — pipeline không dùng bất kỳ random state nào.
- **Yeo-Johnson:** deterministic fit (PowerTransformer với method='yeo-johnson' không có random state).
- **RobustScaler:** deterministic (median/IQR computation).
- **Imputation median:** deterministic từ dataset.
- → Cùng input + cùng config + cùng library version → cùng output.

### 11.6. Pipeline reload / transform reproducibility

Theo config A5:
- `final_clustering_dataset.parquet` reproducible từ customer_candidates.parquet.
- `customer_metadata.parquet` reproducible.
- `fitted_preprocessing_pipeline.pkl` load được (sklearn standard).
- Fitted pipeline giữ đúng feature/schema.
- Transform cùng input cho numerical output tương đương.

---

## 12. Những gì FE-06 đã thực hiện được

| Requirement | Kết quả | Evidence | Status |
|---|---|---|---|
| Đọc `customer_candidates.parquet` không mutate | Input SHA-256 unchanged | `fe06_run.json.input.sha256`; `tests/test_input_integrity.py` | ✅ DONE |
| Feature eligibility gate (CANDIDATE only) | 14 eligible, 0 excluded | `feature_eligibility.csv`; `fe06_run.json.config.feature_eligible_count = 14` | ✅ DONE |
| CustomerID tách riêng vào `customer_metadata.parquet` | CustomerID absent from matrix; metadata has CustomerID | `leakage_check.csv`; `data_quality_report.csv` | ✅ DONE |
| Phân biệt STRUCTURALLY_UNDEFINED vs data-quality | `imputation_semantics.csv` với semantics = STRUCTURALLY_UNDEFINED | `imputation_semantics.csv` | ✅ DONE |
| Median imputation cho PurchaseIntervalMean/Std | 1,312 / 2,129 NaN → 0 | `imputation_semantics.csv`; `fe06_run.json.config.median_values` | ✅ DONE |
| Yeo-Johnson transformation cho 14 features | Lambda values saved per feature | `fe06_run.json.config.lambda_values` | ✅ DONE |
| RobustScaler cho 14 features | Median=0, IQR=1 | `distribution_post_scaling.csv` | ✅ DONE |
| 14 features trong final matrix | Shape (4,371, 14) | Verified directly; `data_quality_report.csv` | ✅ DONE |
| No NaN, No Inf, No constants, all numeric | 7/7 PASS | `data_quality_report.csv` | ✅ DONE |
| Redundancy classification (3 categories) | 2 DUPLICATE_INFORMATION, 1 HIGH_CORRELATION | `redundancy_analysis.csv` | ✅ DONE |
| KHÔNG auto-drop redundancy | All 14 features retained | `feature_eligibility.csv` (no exclusions) | ✅ DONE |
| KHÔNG clustering / evaluation / tuning | `constraints.no_clustering = true`, etc. | `fe06_run.json.constraints`; `comparison_matrix.csv` Is_Working=True chỉ C7 | ✅ DONE |
| Reproducibility metadata + SHA-256 | Input/output/metadata/config SHA recorded | `fe06_run.json` | ✅ DONE |
| Library versions recorded | numpy, pandas, scipy, sklearn, pyarrow | `fe06_run.json.library_versions` | ✅ DONE |
| Dataset version `FE06-v1.0` | Marked TECHNICALLY_GENERATED | `fe06_run.json.stage_version`; `feature_dictionary.csv` | ✅ DONE |
| Fitted pipeline pickle saved | `fitted_preprocessing_pipeline.pkl` | `fe06_run.json.output.fitted_pipeline_path` | ✅ DONE |
| Documentation reports | feature_dictionary, eligibility, distribution, correlation, redundancy, outlier, leakage, narrative | `reports/fe06/*.csv`, `*.md` | ✅ DONE |

---

## 13. Những gì FE-06 KHÔNG quyết định

FE-06 **chưa quyết định** và **không có thẩm quyền quyết định** các vấn đề sau:

| Decision | Status | Lý do FE-06 chưa quyết |
|---|---|---|
| Clustering algorithm (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means — 5 algorithms; K-Medoids OUT OF SCOPE per ADR-0003) | Chưa chọn | FE-06 không chạy clustering. Methodology: 5 thuật toán benchmark cố định (per ADR-0003) — selection dựa trên evaluation phase sau. |
| Number of clusters (k) | Chưa quyết | FE-06 không chạy clustering. |
| Hyperparameters | Chưa tune | FE-06 không tuning. |
| "Best algorithm" | Không có | FE-06 không đánh giá thuật toán nào tốt hơn. |
| Feature ranking | Không có | FE-06 không xếp hạng feature. |
| Final feature elimination | Không có | FE-06 giữ đủ 14 features trong working matrix. |
| Final methodology approval | PENDING | FE-06 chỉ là TECHNICALLY_GENERATED, không phải RESEARCH_APPROVED_FINAL. |
| Working configuration C7 = "best" | Không có | C7 là WORKING_ASSUMPTION, không tự đánh giá. |
| Yeo-Johnson = "best transformation" | Không có | Working default, không so sánh với các transformation khác. |
| RobustScaler = "best scaler" | Không có | Working default, không so sánh với các scaler khác. |
| Median = "best imputation" | Không có | Working default, không so sánh với các imputation khác. |

**Clustering là phase tiếp theo** (sau FE-06), không nằm trong scope FE-06.

---

## 14. Pending Mentor Review

`fe06_run.json.pending_review_notes` ghi 8 PR-FE06 items:

| ID | Decision | Status |
|---|---|---|
| PR-FE06-01 | Working transformation = yeo_johnson | `WORKING_ASSUMPTION` |
| PR-FE06-02 | Working scaler = robust | `WORKING_ASSUMPTION` |
| PR-FE06-03 | Working imputation = median | `WORKING_ASSUMPTION` |
| PR-FE06-04 | 6 FE-05 PENDING_REVIEW features included as ELIGIBLE_WORKING_ASSUMPTION | `ELIGIBLE_WORKING_ASSUMPTION` |
| PR-FE06-05 | Redundancy pairs not auto-dropped | `DIAGNOSTIC_ONLY` |
| PR-FE06-06 | Rate features (CancellationRate, ReturnRate) included with Yeo-Johnson in C7 | `WORKING_ASSUMPTION` |
| PR-FE06-07 | Dataset version FE06-v1.0 = TECHNICALLY_GENERATED | `TECHNICALLY_GENERATED` |
| PR-FE06-08 | Working matrix retains all 14 eligible features | `TECHNICALLY_GENERATED` |

Phân loại status:
- **`WORKING_ASSUMPTION`** — working default; chưa được mentor approve methodology.
- **`ELIGIBLE_WORKING_ASSUMPTION`** — feature được include nhưng chưa được promote thành final approved.
- **`DIAGNOSTIC_ONLY`** — chỉ mang tính báo cáo; không tự động ảnh hưởng quyết định.
- **`TECHNICALLY_GENERATED`** — dataset đã được sinh ra từ pipeline, nhưng chưa được promote thành `RESEARCH_APPROVED_FINAL`.
- **`MENTOR_REVIEW_PENDING`** — chờ mentor review trước khi promote.

Các PR-FE06 liên quan đến FE-05 PENDING_REVIEW decisions (xem `docs/research/FE05_Customer_Feature_Engineering.md` §13):

| FE-05 PENDING_REVIEW | FE-06 status |
|---|---|
| `Frequency` variant (by_invoice default) | ELIGIBLE_WORKING_ASSUMPTION |
| `Monetary` variant (MonetarySigned default) | ELIGIBLE (RETAIN_CANDIDATE → ELIGIBLE) |
| `BasketSize` vs `AverageQuantity` (correlation 1.0) | ELIGIBLE_WORKING_ASSUMPTION; redundancy: DUPLICATE_INFORMATION |
| `CancellationRate` vs `ReturnRate` (correlation 1.0) | ELIGIBLE_WORKING_ASSUMPTION; redundancy: DUPLICATE_INFORMATION |
| `Frequency` vs `ActiveDays` (correlation 0.974) | ELIGIBLE_WORKING_ASSUMPTION; redundancy: HIGH_CORRELATION |
| Purchase-only Recency variant | FE-05 keeps Recency default; FE-06 giữ nguyên |

---

## 15. Limitations

Các limitations đã được ghi nhận trong `reports/fe06/`:

### 15.1. Working configuration chưa được approve

C7 (yeo_johnson + robust + median) là **WORKING_ASSUMPTION**, không phải final approved. Các configuration khác (C0, C1, C2, C3, C6) là candidates chưa được materialize. Không có comparison / ranking giữa các configurations.

### 15.2. Log1p không full-matrix comparable

Log1p-based configurations không được đưa vào experimental matrix vì 6/14 features có giá trị âm. Log1p chỉ diagnostic-only cho non-negative subset.

### 15.3. Redundancy chỉ ở mức phát hiện và phân loại

FE-06 redundancy gate **CHỈ detects + quantifies + classifies**. KHÔNG auto-drop. KHÔNG scoring. KHÔNG ranking. Quyết định drop feature là của mentor / future ADR.

### 15.4. Outliers không xử lý

Một số features vẫn có outliers post-scaling (`outlier_analysis.csv`):
- `PurchaseIntervalStd`: 46.21% outliers (2,020 / 4,371)
- `PurchaseIntervalMean`: 12.95% outliers (566 / 4,371)
- `Monetary`: 7.85% outliers
- `AverageInvoiceValue`: 6.66% outliers
- `TotalQuantity`: 6.27% outliers

FE-06 KHÔNG winsorize / clip / remove outliers. Outliers chỉ diagnostic.

### 15.5. Median imputation semantics

Median imputation cho STRUCTURALLY_UNDEFINED NaN là working default. Median "mất" thông tin "khách hàng này chỉ có 1 invoice" (vì sau imputation, ta không phân biệt được khách 1 invoice với khách 2+ invoice có interval = median). Đây là trade-off có chủ đích giữa tính khả thi (matrix không NaN) và tính trung thực (giữ NaN semantics).

### 15.6. CustomerID alignment

Alignment dựa trên **position** (row order), không phải dựa trên explicit join key. Cấu hình A6 ghi: `alignment: "verified_by_position_and_unique_key"` — position phải giữ nguyên từ source candidate order.

### 15.7. Pickle SHA không phải hard criterion

Theo config A5: "Pickle SHA ghi nhung KHONG dung byte-level SHA equality cross-environment lam hard acceptance criterion." Pickle format có thể khác nhau giữa Python/OS/library version; final_clustering_dataset.parquet SHA là primary check.

### 15.8. Dataset status chưa promote

`stage_status = "TECHNICALLY_GENERATED"` — chưa phải `RESEARCH_APPROVED_FINAL`. Promotion cần mentor review + ADR.

---

## 16. Kết luận

FE-06 đã tạo một **technically generated, reproducible working clustering matrix** từ customer candidate features:

- **Input:** `customer_candidates.parquet` (FE-05 output, 4,371 × 14 CANDIDATE features + CustomerID) với SHA-256 verified.
- **Pipeline:** feature eligibility gate → imputation (median) → Yeo-Johnson transformation → RobustScaler → validation.
- **Output 1:** `final_clustering_dataset.parquet` (4,371 × 14, numeric only, no NaN/Inf, no identifiers).
- **Output 2:** `customer_metadata.parquet` (4,371 × 1 CustomerID) for cluster label mapping.
- **Output 3:** `fitted_preprocessing_pipeline.pkl` cho reload / transform.
- **SHA-256 chain:** Tất cả inputs/outputs đều có SHA-256 recorded.
- **Validation:** 7/7 data quality checks PASS, 8/8 leakage checks PASS, 22 FE-06 tests + input integrity tests passing.

Dataset đã đáp ứng **điều kiện kỹ thuật** để làm input cho phase clustering tiếp theo (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means — năm thuật toán benchmark cố định; K-Medoids OUT OF SCOPE per ADR-0003).

**Tuy nhiên**, tất cả các lựa chọn methodology vẫn **PENDING mentor review**:
- Working transformation (yeo_johnson)
- Working scaler (robust)
- Working imputation (median)
- Inclusion của 6 FE-05 PENDING_REVIEW features vào working matrix
- Redundancy pairs chưa được auto-drop
- Dataset version `FE06-v1.0` là `TECHNICALLY_GENERATED`, KHÔNG phải `RESEARCH_APPROVED_FINAL`

Tài liệu này KHÔNG kết luận:
- ❌ "final optimal dataset"
- ❌ "best transformation"
- ❌ "best scaler"
- ❌ "best feature set"

Tài liệu này CHỈ mô tả **trạng thái kỹ thuật** của FE-06 output và các PENDING decisions cần mentor review trước khi promote sang final approved clustering dataset.

---

*Tài liệu này được viết để mentor review. Số liệu trích từ execution thực tế (`fe06_run.json`, `reports/fe06/*.csv|md`, kiểm tra trực tiếp các file parquet output). Mọi WORKING_ASSUMPTION và PENDING_REVIEW decision được nêu rõ.*
