# Research Questions

> **Trạng thái:** METHODOLOGY_LOCKED (theo ADR-0004)
> **Ngày:** 2026-09-22
> **Nguồn:** ADR-0004 — `docs/decisions/0004-research-questions.md`

Tài liệu này ghi lại ba Research Question chính thức cho dự án customer
segmentation. Mỗi RQ được định nghĩa với population, dataset, scope,
evidence base, và ranh giới diễn giải.

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho tên trường, identifier, SHA-256, RQ ID, ADR ID, code,
> status enum, và thuật ngữ kỹ thuật theo convention hiện có.

---

## RQ1 — Algorithm Comparison Under Controlled Conditions

> **Câu hỏi:** Các thuật toán clustering khác nhau hoạt động thế nào trên
> không gian feature behavioral cấp customer được rút ra từ dữ liệu
> transactional bán lẻ, dưới các điều kiện thí nghiệm controlled?

### Population và Unit of Analysis

- **Unit**: Customer (một row trên một customer, định danh bằng `CustomerID`).
- **Observation count**: 4,371 customers.
- **Feature space**: R¹⁴ (14 features per customer).

### Dataset

- **File**: `data/processed/final_clustering_dataset.parquet`
- **SHA-256**: `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`
- **Version**: FE06-v1.0
- **Source**: UCI Online Retail (primary dataset, theo ADR-0001)
- **Preprocessing**: FE-06 C7 (median imputation + Yeo-Johnson transformation
  + RobustScaler). Trạng thái: `WORKING_ASSUMPTION`.

### Feature Representation

RFM Extended — 14 features:

| # | Feature | FE-06 Status | Ghi chú |
|---|---|---|---|
| 1 | Recency | ELIGIBLE | Days from last purchase to ReferenceDate |
| 2 | Frequency | ELIGIBLE_WORKING_ASSUMPTION | nunique(InvoiceNo) |
| 3 | Monetary | ELIGIBLE | Sum of signed LineRevenue |
| 4 | TotalQuantity | ELIGIBLE | Sum of signed Quantity |
| 5 | AverageQuantity | ELIGIBLE_WORKING_ASSUMPTION | TotalQuantity / Frequency |
| 6 | BasketSize | ELIGIBLE_WORKING_ASSUMPTION | Alias for AverageQuantity |
| 7 | TenureDays | ELIGIBLE | Days from first to last purchase |
| 8 | PurchaseIntervalMean | ELIGIBLE | Mean inter-invoice days (NaN if <2 invoices) |
| 9 | PurchaseIntervalStd | ELIGIBLE | Std of inter-invoice days (NaN if <3 invoices) |
| 10 | ActiveDays | ELIGIBLE_WORKING_ASSUMPTION | nunique(calendar days) |
| 11 | AverageInvoiceValue | ELIGIBLE | Monetary / Frequency |
| 12 | ProductsPerInvoice | ELIGIBLE | DistinctProducts / DistinctInvoiceCount |
| 13 | CancellationRate | ELIGIBLE_WORKING_ASSUMPTION | CancellationInvoiceCount / Frequency |
| 14 | ReturnRate | ELIGIBLE_WORKING_ASSUMPTION | ReturnInvoiceCount / Frequency |

Sáu feature ở trạng thái `ELIGIBLE_WORKING_ASSUMPTION`. Xem tài liệu
FE-06 §13 để biết các pending review item.

### Algorithm Scope

Năm thuật toán (theo ADR-0003):

1. **K-Means** (`kmeans`) — sklearn implementation.
2. **Agglomerative Clustering** (`agglomerative`) — sklearn với Ward linkage.
3. **DBSCAN** (`dbscan`) — sklearn, density-based.
4. **Gaussian Mixture Model** (`gmm`) — sklearn, probabilistic.
5. **Fuzzy C-Means** (`fuzzy_cmeans`) — custom NumPy implementation.

K-Medoids là **OUT OF SCOPE** (theo ADR-0003).

### K Treatment

- EXP-02 swept K ∈ [2, 10] step=1, xác định 13 candidate qua deterministic
  heuristic.
- EXP-03 dùng K=3 làm controlled interaction point (từ EXP-02 candidates).
- K được xử lý per-experiment. KHÔNG có claim "best K" hoặc "optimal K".
- Per-algorithm K candidates được báo cáo dưới dạng evidence.

### Hyperparameter Treatment

- EXP-03 thực hiện sensitivity analysis per algorithm (Stage A: baseline;
  Stage B: single-parameter sweeps; Stage C: selected interactions).
- Per-algorithm working selection được sinh ra qua protocol:
  **silhouette primary → DBI → CH tiebreaker**.
- Selection status = `WORKING_SELECTED` (chưa final approved; đang chờ
  EPIC-08 validation).
- Protocol được document tại
  `docs/research/EXP03_HYPERPARAMETER_REVIEW.md`.

### Quality Metrics

Chỉ internal metrics (không có external validation):

| Metric | Mô tả | Status |
|---|---|---|
| Silhouette Score | Mean pairwise distance ratio | PRIMARY |
| Davies-Bouldin Index | Mean cluster similarity ratio | Tiebreaker 1 |
| Calinski-Harabasz Index | Cluster separation vs dispersion | Tiebreaker 2 |
| WCSS | Within-cluster sum of squares (arithmetic centroid) | Diagnostic only |

Metric status schema: `VALID_VALUE`, `NOT_APPLICABLE`, `COMPUTATION_ERROR`,
`MISSING`. Noise handling: DBSCAN noise points (label=-1) bị loại khỏi
internal metrics và WCSS.

### Runtime

- Đo bằng algorithm execution time (loại trừ metric computation và
  artifact writing).
- Protocol: n_repeat=5 per configuration cho variance estimation.
- Runtime data từ EXP-01 đến EXP-05.

### Reproducibility

- Đã verify tại EXP-05 Block R: 5/5 thuật toán tạo ra cluster labels
  giống hệt nhau qua 5 repeat với seed=42.
- Trạng thái: `REPRODUCIBILITY_VERIFIED`.

### Stability

- EXP-05 Block S: seed sensitivity (K-Means, GMM, Fuzzy C-Means × 5 seeds).
- EXP-05 Block N: feature perturbation (Gaussian noise,
  sigma ∈ {0, 0.01, 0.05} × column std).
- ARI/AMI computation: **deferred to EPIC-08** dùng
  `exp05_cluster_labels.parquet` (327,825 rows × 9 columns).

### Ranh giới diễn giải

> **Thuật ngữ bị cấm (theo `AGENTS.md` §2.5):** "best", "winner",
> "optimal", "recommended", "final", "superior".

Cross-algorithm comparison được trình bày dưới dạng evidence với caveat
rõ ràng. Composite scoring bị cấm.

---

## RQ2 — Preprocessing Sensitivity Under Fixed Feature Representation

> **Câu hỏi:** Chiến lược preprocessing ảnh hưởng thế nào đến clustering
> quality dưới một feature representation cấp customer cố định?

### Population và Unit of Analysis

Giống RQ1 (4,371 customers, R¹⁴).

### Dataset

Giống RQ1.

### Independent Variable

Preprocessing strategy — được định nghĩa là cấu hình transformation ×
scaling áp dụng lên bộ 14 feature cố định.

### Evidence

EXP-04 Family B: 6 preprocessing scenario × 5 repeat = 30 run. Tất cả
deterministic.

| Scenario | Transformation | Scaling | Vai trò |
|---|---|---|---|
| C0 | none | none | NO_TRANSFORM_NO_SCALING_REFERENCE |
| C1 | none | standard | Candidate |
| C2 | none | minmax | Candidate |
| C3 | none | robust | Candidate |
| C6 | yeo_johnson | standard | Candidate |
| C7 | yeo_johnson | robust | FE06_WORKING_CONFIGURATION_REFERENCE |

### Giới hạn

- Một thuật toán duy nhất (K-Means) — preprocessing sensitivity có thể
  khác nhau giữa các thuật toán.
- Một K duy nhất (K=4) — sensitivity có thể khác ở các cluster count khác.
- **So sánh RFM-only vs RFM Extended KHÔNG nằm trong scope của RQ2 đã
  reformulate.** Xem
  `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`.

---

## RQ3 — Stability and Reproducibility

> **Câu hỏi:** Clustering do mỗi thuật toán tạo ra reproducible và robust
> đến mức nào dưới các seed khác nhau và perturbation trên feature space?

### Population và Unit of Analysis

Giống RQ1 (4,371 customers, R¹⁴).

### Dataset

Giống RQ1.

### Reproducibility

- EXP-05 Block R: 5 thuật toán × n_repeat=5 × seed=42.
- Cả 5 thuật toán: `REPRODUCIBILITY_VERIFIED` (1 unique labels_hash qua
  5 repeat).
- Trạng thái: VERIFIED.

### Seed Stability

- EXP-05 Block S: K-Means, GMM, Fuzzy C-Means × 5 seeds
  (42, 7, 123, 2024, 1729).
- Agglomerative và DBSCAN bị loại (deterministic — không có random axis).
- Raw evidence: 15 run. ARI/AMI computation deferred to EPIC-08.

### Perturbation Robustness

- EXP-05 Block N: 5 thuật toán × (sigma=0, 0.01, 0.05) × 3 perturbation
  seeds.
- Tổng: 35 run.
- Sigma=0 sanity check: reproduce EXP-01 baseline (PASS).
- ARI/AMI computation deferred to EPIC-08.

### Stability Metrics (EPIC-08 owned)

| Metric | Mô tả | Trạng thái |
|---|---|---|
| ARI | Adjusted Rand Index | EPIC-08 |
| AMI | Adjusted Mutual Information | EPIC-08 |
| Hungarian matching | Cluster label alignment across runs | EPIC-08 |
| Statistical tests | Paired t-test / Wilcoxon | EPIC-08 plan |
| Confidence intervals | Bootstrap / percentile | EPIC-08 plan |

### Ranh giới diễn giải

RQ3 KHÔNG bao gồm:

- Business interpretation của cluster (EPIC-09).
- Customer profiling hoặc segment naming (EPIC-09).
- External validation với ground truth.

---

## Tóm tắt độ phủ RQ

| RQ | Evidence hiện có | Trả lời được? | Trạng thái |
|---|---|---|---|
| RQ1 | EXP-01 (baseline), EXP-02 (K-sweep), EXP-03 (hyperparameter) | PARTIAL — quality evidence đầy đủ; stability analysis ở EPIC-08 | METHODOLOGY_LOCKED |
| RQ2 | EXP-04 Family B (preprocessing sensitivity) | PARTIAL — preprocessing sensitivity trên RFM Extended; RFM-only comparison là future work | METHODOLOGY_LOCKED |
| RQ3 | EXP-05 Blocks R/S/N (raw evidence) | PARTIAL — evidence đầy đủ; ARI/AMI analysis ở EPIC-08 | METHODOLOGY_LOCKED |

---

## Tham chiếu

- ADR-0003: `docs/decisions/0003-algorithm-scope.md`
- ADR-0004: `docs/decisions/0004-research-questions.md`
- RFM-only future work: `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`
- Experiment reports: `reports/exp01/` qua `reports/exp05/`
