# Tổng quan Methodology

> **Trạng thái:** METHODOLOGY_LOCKED (theo ADR-0004)
> **Ngày:** 2026-09-22
> **Nguồn:** ADR-0004, ADR-0003, và các quyết định liên quan

Tài liệu này mô tả **methodology nghiên cứu tổng thể**: study design,
benchmarking protocol, và mối quan hệ giữa Research Questions và
Experimental Evidence.

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho tên trường, identifier, SHA-256, RQ ID, ADR ID, code,
> và thuật ngữ kỹ thuật theo convention hiện có của repository.

---

## 1. Research Questions

Ba Research Question hướng dẫn dự án này (theo
`docs/methodology/research_questions.md` và ADR-0004):

| RQ | Câu hỏi | Phase evidence |
|---|---|---|
| **RQ1** | So sánh thuật toán dưới điều kiện controlled | EXP-01, EXP-02, EXP-03 |
| **RQ2** | Độ nhạy preprocessing dưới feature representation cố định | EXP-04 |
| **RQ3** | Tính ổn định và khả năng tái lập | EXP-05 + EPIC-08 |

---

## 2. Study Design

### 2.1. Dataset

| Trường | Giá trị |
|---|---|
| Source | UCI Online Retail (primary, ADR-0001) |
| Backup | UCI Online Retail II (ADR-0002) |
| Raw file | `data/raw/primary/Online Retail.xlsx` |
| Raw SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Cleaning | FE-02 (loại bỏ record không hợp lệ, trùng lặp) |
| Customer aggregation | FE-04 (customer-level base) |
| Feature engineering | FE-05 (RFM + extended behavioral features) |
| Transformation | FE-06 (imputation, Yeo-Johnson, RobustScaler) |
| Final matrix | `data/processed/final_clustering_dataset.parquet` (4,371 × 14) |
| Final matrix SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Customer metadata | `data/processed/customer_metadata.parquet` (4,371 × 1, CustomerID) |

### 2.2. Feature Representation

RFM Extended — 14 features (theo RQ1 và tài liệu FE-06):

- **RFM core**: Recency, Frequency, Monetary
- **Quantity**: TotalQuantity, AverageQuantity, BasketSize
- **Temporal**: TenureDays, PurchaseIntervalMean, PurchaseIntervalStd, ActiveDays
- **Value**: AverageInvoiceValue
- **Diversity**: ProductsPerInvoice
- **Cancellation**: CancellationRate, ReturnRate

Sáu feature ở trạng thái `ELIGIBLE_WORKING_ASSUMPTION` (theo FE-06 §13).
Xem `docs/methodology/research_questions.md` §RQ1 để có danh sách đầy đủ.

### 2.3. Preprocessing Pipeline (FE-06 C7)

| Bước | Phương pháp | Chi tiết |
|---|---|---|
| Imputation | Median | PurchaseIntervalMean (41.0), PurchaseIntervalStd (32.585) |
| Transformation | Yeo-Johnson | Per-feature lambda, fit bằng sklearn |
| Scaling | RobustScaler | median=0, IQR=1 |

Trạng thái: `WORKING_ASSUMPTION`. Chưa được nâng lên
`RESEARCH_APPROVED_FINAL`.

---

## 3. Benchmarking Protocol

### 3.1. Phạm vi thuật toán

Năm thuật toán (theo ADR-0003):

| Thuật toán | Adapter | Hỗ trợ Random Seed | Ghi chú |
|---|---|---|---|
| K-Means | sklearn | Yes (init) | Hard centroid-based |
| Agglomerative | sklearn | No (deterministic) | Ward linkage |
| DBSCAN | sklearn | No (deterministic) | Density-based, noise label=-1 |
| GMM | sklearn | Yes (EM init) | Probabilistic, soft probabilities |
| Fuzzy C-Means | Custom NumPy | Yes (Dirichlet init) | Bezdek update, fuzzy membership |

K-Medoids: **OUT OF SCOPE** (theo ADR-0003).

### 3.2. Cluster Count (K)

- Range swept: K ∈ [2, 10], step=1 (EXP-02).
- 13 candidate K values được xác định bằng heuristic deterministic
  (top_n=3, drop_ratio=0.2, min_agreement=2).
- KHÔNG có "best K" claim. K treatment là per-experiment.

### 3.3. Hyperparameter Selection

Phân tích độ nhạy per-algorithm (EXP-03):

- **Stage A**: Baseline per algorithm (1 run mỗi cái).
- **Stage B**: Single-parameter sweeps (6–7 runs per algorithm).
- **Stage C**: Selected interactions (K=3 từ EXP-02 × parameter) — 3 runs per algorithm.

**Selection protocol**: Silhouette (primary) → Davies-Bouldin (tiebreaker 1) →
Calinski-Harabasz (tiebreaker 2).

Selection status = `WORKING_SELECTED` (chưa final approved). Cross-validation
qua EPIC-08.

### 3.4. Preprocessing Sensitivity (EXP-04)

Sáu scenario × 5 repeat = 30 run trên RFM Extended (14 features) dùng
K-Means (K=4).

| Scenario | Transformation | Scaling |
|---|---|---|
| C0 | none | none |
| C1 | none | standard |
| C2 | none | minmax |
| C3 | none | robust |
| C6 | yeo_johnson | standard |
| C7 | yeo_johnson | robust |

C7 mirror FE-06 working configuration.

### 3.5. Reproducibility và Stability (EXP-05)

Ba block evidence:

| Block | Nội dung | Run |
|---|---|---|
| Block R | Reproducibility verification (seed=42, n_repeat=5) | 25 |
| Block S | Seed sensitivity (5 seeds × 3 algorithms) | 15 |
| Block N | Feature perturbation (3 sigmas × 3 perturbation seeds × 5 algorithms) | 35 |

Toàn bộ evidence lưu tại
`reports/exp05/exp05_cluster_labels.parquet` (327,825 rows × 9 columns).

### 3.6. Evaluation Metrics

| Metric | Vai trò | Chiều tối ưu |
|---|---|---|
| Silhouette Score | Primary quality | Higher = better |
| Davies-Bouldin Index | Secondary quality | Lower = better |
| Calinski-Harabasz Index | Secondary quality | Higher = better |
| WCSS | Diagnostic only | Lower = more compact (diagnostic) |
| ARI / AMI | Stability (EPIC-08) | Higher = more similar |
| Runtime | Computational cost | Lower = faster |

**Bị cấm**: Composite scores, weighted rankings, claim "best"/"optimal"/
"winner" (`AGENTS.md` §2.5).

---

## 4. Experiment Pipeline

```
DS-05: Dataset selection (DONE)
  └─ ADR-0001, ADR-0002

FE-01: Raw data audit (DONE)
FE-02: Data cleaning (DONE)
FE-03: Outlier analysis (DONE, diagnostic only)
FE-04: Customer aggregation (DONE)
FE-05: Feature engineering (DONE)
FE-06: Transformation + Scaling (DONE)
  └─ Final matrix: SHA ba54033e...

EPIC-06: Clustering adapters (DONE)
  └─ 5 algorithms registered (ADR-0003)
  └─ ADR-0004 defines RQ1–RQ3

EPIC-07: Controlled experiments (DONE)
  ├─ EXP-01: Baseline (5 runs)
  ├─ EXP-02: K-sweep (37 runs)
  ├─ EXP-03: Hyperparameter sensitivity (38 runs)
  ├─ EXP-04: Preprocessing sensitivity (30 runs, Family B only)
  └─ EXP-05: Reproducibility + stability evidence (75 runs)
  Total: 185 runs

EPIC-08: Stability analysis + evaluation (PENDING)
  ├─ Phase A: ARI/AMI, statistical tests, CI, runtime
  └─ Phase B: Cross-algorithm analysis (conditional on mentor approval)

EPIC-09: Customer profiling (PENDING)
EPIC-10: Visualization (PENDING)
```

---

## 5. Ranh giới diễn giải

### 5.1. Methodology hỗ trợ những gì

- So sánh internal quality metric (silhouette, DBI, CH, WCSS) giữa các
  thuật toán, K values, và preprocessing configuration.
- Xác minh reproducibility (tính deterministic với fixed seed).
- Seed stability evidence (label thay đổi thế nào qua các seed).
- Perturbation robustness evidence (label thay đổi thế nào dưới feature
  noise).
- ARI/AMI tính trong EPIC-08 từ EXP-05 labels artifact.

### 5.2. Methodology KHÔNG hỗ trợ những gì

- Claim **"best algorithm" / "winner" / "optimal" / "recommended" /
  "final"** (`AGENTS.md` §2.5).
- Business interpretation của cluster (EPIC-09).
- Customer profiling hoặc segment naming (EPIC-09).
- So sánh RFM-only vs RFM Extended (RQ2 đã reformulate; RFM-only là
  future work).
- External validation với ground truth (unsupervised setting).
- Deployment hoặc production recommendation.
- Khái quát hoá ngoài phạm vi dataset (single retail dataset).

---

## 6. Yêu cầu Reproducibility

Mỗi thí nghiệm ghi lại:

- Input SHA-256 (dataset, config).
- Output SHA-256.
- Library versions (numpy, pandas, scipy, scikit-learn, pyarrow).
- Python version và platform.
- Random seed protocol.
- Execution metadata (timestamp, duration).

SHA chain: raw file → FE-05 candidates → FE-06 final matrix → EXP artifacts.

---

## 7. Chuỗi ADR

| ADR | Quyết định | Trạng thái |
|---|---|---|
| ADR-0001 | Primary dataset = UCI Online Retail | Accepted |
| ADR-0002 | Backup dataset = UCI Online Retail II | Accepted |
| ADR-0003 | Algorithm scope = 5 algorithms (K-Medoids deferred) | Accepted |
| ADR-0004 | Research Questions RQ1, RQ2, RQ3 | Accepted |

---

## 8. Tham chiếu

- `docs/methodology/research_questions.md` — RQ definitions
- `docs/decisions/0003-algorithm-scope.md` — ADR-0003
- `docs/decisions/0004-research-questions.md` — ADR-0004
- `docs/research/review/METHODOLOGY_LOCK_STATUS.md` — current status
- `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md` — future work
