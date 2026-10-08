# SYS-01 | Phân tích yêu cầu hệ thống thử nghiệm

> **Task ID:** EPIC-11 / SYS-01
> **Ngày:** 2026-10-07
> **Trạng thái:** `READY FOR USER REVIEW`
> **Phạm vi:** PHÂN TÍCH YÊU CẦU (requirements analysis) — KHÔNG code, KHÔNG
> architecture, KHÔNG API, KHÔNG database, KHÔNG frontend, KHÔNG triển khai
> ML service, KHÔNG thay đổi methodology/RQ/algorithm scope, KHÔNG Git
> operations.
> **Ngôn ngữ:** tài liệu bằng tiếng Việt. Code / identifier / file name
> giữ nguyên convention tiếng Anh hiện có của repository.
> **Source of truth cho mọi thuật ngữ methodology:** `AGENTS.md`,
> `docs/methodology/research_questions.md`, `docs/methodology/methodology_overview.md`,
> `docs/decisions/0003-algorithm-scope.md`, `docs/decisions/0004-research-questions.md`,
> `docs/research/review/METHODOLOGY_LOCK_STATUS.md`.

---

## 1. Objective

SYS-01 chuyển các kết quả, phạm vi và quy trình nghiên cứu hiện có trong
repository thành **bộ yêu cầu hệ thống thử nghiệm (prototype)** có cấu trúc,
có traceability và phù hợp với phạm vi NCKH.

Mục tiêu cụ thể:

1. Xác định **System Purpose** dựa trên research pipeline hiện đã được
   freeze (DS-05 → FE-01 → FE-06 → EPIC-06 → EPIC-07 → EPIC-08 → EPIC-09).
2. Phân tích **Functional Requirements** theo 8 nhóm chức năng
   (Data Management, Experiment Management, Clustering, Evaluation,
   Visualization, Customer Segment / Profiling, Marketing Recommendation,
   Report / Export).
3. Phân biệt rõ 4 loại requirement: **Functional / Non-functional /
   Research Constraint / Out of Scope**.
4. Thiết lập **Requirement Traceability** từ Research Source (RQ, ADR,
   research doc) → System Requirement → Future DEV / TEST.
5. Xác định **Open Questions** cần mentor / human researcher quyết định
   trước khi SYS-02 → SYS-06.

SYS-01 KHÔNG thực hiện bất kỳ hoạt động nào thuộc SYS-02 → SYS-06.

---

## 2. Research Context

### 2.1. Dataset

| Trường | Giá trị | Nguồn |
| --- | --- | --- |
| Source | UCI Online Retail (primary) | ADR-0001 |
| Backup | UCI Online Retail II | ADR-0002 |
| Raw file | `data/raw/primary/Online Retail.xlsx` | (git-ignored) |
| Raw SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` | FE-01 evidence |
| Cleaning | FE-02 (invalid records + duplicates) | FE-02 report |
| Customer-level base | FE-04 (4,371 customers) | FE-04 report |
| Feature set | RFM Extended (14 features) | FE-05, FE-06 |
| Transformation | FE-06 C7 (median imputation + Yeo-Johnson + RobustScaler) | FE-06 |
| Final matrix | `data/processed/final_clustering_dataset.parquet` (4,371 × 14) | FE-06 |
| Final matrix SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | FE-06 |
| Customer metadata | `data/processed/customer_metadata.parquet` (4,371 × 1, CustomerID) | FE-06 |

### 2.2. Feature Set (RFM Extended, 14 features)

| # | Feature | FE-06 Status |
| --- | --- | --- |
| 1 | Recency | ELIGIBLE |
| 2 | Frequency | ELIGIBLE_WORKING_ASSUMPTION |
| 3 | Monetary | ELIGIBLE |
| 4 | TotalQuantity | ELIGIBLE |
| 5 | AverageQuantity | ELIGIBLE_WORKING_ASSUMPTION |
| 6 | BasketSize | ELIGIBLE_WORKING_ASSUMPTION |
| 7 | TenureDays | ELIGIBLE |
| 8 | PurchaseIntervalMean | ELIGIBLE |
| 9 | PurchaseIntervalStd | ELIGIBLE |
| 10 | ActiveDays | ELIGIBLE_WORKING_ASSUMPTION |
| 11 | AverageInvoiceValue | ELIGIBLE |
| 12 | ProductsPerInvoice | ELIGIBLE |
| 13 | CancellationRate | ELIGIBLE_WORKING_ASSUMPTION |
| 14 | ReturnRate | ELIGIBLE_WORKING_ASSUMPTION |

Sáu features ở `ELIGIBLE_WORKING_ASSUMPTION` chưa được promote thành
`RESEARCH_APPROVED_FINAL`. Prototype phải hiển thị rõ status này cho từng
feature khi cần (xem `FR-VIZ-04`).

### 2.3. Research Questions (locked per ADR-0004)

| RQ | Câu hỏi | Evidence Phase |
| --- | --- | --- |
| **RQ1** | Algorithm comparison under controlled conditions | EXP-01, EXP-02, EXP-03 |
| **RQ2** | Preprocessing sensitivity under fixed feature representation | EXP-04 |
| **RQ3** | Stability and reproducibility | EXP-05 + EPIC-08 |

RQ2 đã được reformulated: RFM-only vs RFM Extended comparison là **future
work** (`docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`). Prototype chỉ
phản ánh scope đã freeze.

### 2.4. Algorithm Scope (locked per ADR-0003)

Năm thuật toán:

1. **K-Means** (`kmeans`) — hard centroid-based.
2. **Agglomerative** (`agglomerative`) — hierarchical, Ward linkage.
3. **DBSCAN** (`dbscan`) — density-based, noise label = -1.
4. **GMM** (`gmm`) — probabilistic, soft probabilities.
5. **Fuzzy C-Means** (`fuzzy_cmeans`) — soft membership, custom NumPy.

**K-Medoids: OUT OF SCOPE** (per ADR-0003). Prototype KHÔNG expose K-Medoids
dưới bất kỳ hình thức nào.

### 2.5. Evaluation Metrics (locked)

| Metric | Vai trò | Direction |
| --- | --- | --- |
| Silhouette Score | Primary quality | Higher = better |
| Davies-Bouldin Index | Secondary quality | Lower = better |
| Calinski-Harabasz Index | Secondary quality | Higher = better |
| WCSS | **Diagnostic only** | Lower = more compact |
| ARI / AMI | Stability (EPIC-08) | Higher = more similar |
| Runtime | Computational cost | Lower = faster |

Prototype phải hiển thị WCSS kèm nhãn `diagnostic_only`. KHÔNG dùng WCSS
như quality metric universal.

### 2.6. Pipeline đã thực hiện

```
DS-05: Dataset selection           ✅
FE-01: Raw data audit              ✅
FE-02: Data cleaning               ✅
FE-03: Outlier analysis            ✅ (diagnostic only)
FE-04: Customer aggregation        ✅
FE-05: Feature engineering         ✅
FE-06: Transformation + Scaling    ✅
EPIC-06: Clustering adapters       ✅ (5 algorithms)
EPIC-07: Controlled experiments    ✅ (185 runs across EXP-01..05)
EPIC-08: Stability analysis        🟡 Active (EVA-01 done, EVA-02..05 in progress)
EPIC-09: Customer profiling        ⏳ Pending (CP-01..04 done, CP-05 plan)
EPIC-10: Visualization + report    ⏳ Pending
EPIC-11: System design (SYS-01..06) 🟡 Starting (this document)
```

### 2.7. Customer Profiling (EPIC-09) context

CP-01 → CP-04 đã được implement. CP-05 đang ở trạng thái PLAN
(`docs/research/EPIC09_CP05_PLAN.md`). Customer Profiling trong prototype
phản ánh đúng phạm vi:

- Cluster size distribution (CP-01).
- Feature profile (CP-02).
- Distinguishing features (CP-03).
- Segment profile + naming (CP-04).
- Interpretability / Business Relevance (CP-05 — khi implement xong).

**Không hard-code segment name** ("Champions", "Loyal", "VIP"...) trong
prototype. Tất cả segment name phải đến từ CP-04/CP-05 evidence với status
`NAMED` / `COMPARATIVE` / `NOT_AVAILABLE` rõ ràng (xem `FR-SEG-04`).

### 2.8. Marketing Recommendation context

**HIỆN TRẠNG: CHƯA CÓ TÀI LIỆU MKT-01..MKT-05 trong repository.**

Đã xác nhận bằng `grep` toàn bộ docs/: không tồn tại tài liệu nào có
nhãn `MKT-01..MKT-05`. Các reference duy nhất đến "marketing" trong repo
là các **negation** trong CP-05 plan (CP-05 "KHÔNG marketing recommendation")
và CP-02 (cùng pattern). Điều này tạo ra một **open question quan trọng**
(xem §13) cho hệ thống prototype: marketing module cần kế thừa framework
nào, và khi nào?

Prototype do đó chỉ expose Marketing Recommendation ở mức **FR-MKT-01..05
với status `REVIEW_REQUIRED`** (xem §6.7). Không tự tạo framework mới.

---

## 3. System Purpose

### 3.1. Mục đích tổng quát

Prototype System minh họa workflow nghiên cứu đã freeze:

```
Dataset → Validation → Preprocessing → Feature Engineering
       → Clustering → Evaluation → Customer Segment / Profiling
       → Marketing Recommendation (REVIEW_REQUIRED)
       → Visualization / Report
```

### 3.2. Đối tượng phục vụ

Prototype phục vụ:

- **Nghiên cứu:** cho phép researcher reproduce lại 185 runs EPIC-07,
  kiểm chứng ARI/AMI, chạy thêm cấu hình mới trên cùng schema.
- **Thực nghiệm:** cung cấp interface để chạy controlled experiment với
  cùng reproducibility contract (input SHA, config SHA, seed, library
  versions) mà ML-01 framework đã thiết lập.
- **Minh họa quy trình:** cho mentor / hội đồng / collaborator thấy
  workflow từ raw data → customer segment → marketing recommendation.
- **Kiểm chứng khả năng chuyển research workflow thành hệ thống:**
  prototype chứng minh rằng các quyết định methodology có thể được hiện
  thực thành giao diện chạy được, với traceability đầy đủ.

### 3.3. Prototype KHÔNG phải

- KHÔNG phải production SaaS.
- KHÔNG phải CRM.
- KHÔNG phải recommendation engine độc lập.
- KHÔNG phải campaign automation platform.
- KHÔNG phải business analytics dashboard cho stakeholder ngoài research.

### 3.4. Phân biệt TECHNICALLY_IMPLEMENTED vs RESEARCH_APPROVED_FINAL

Prototype chỉ cần phản ánh đúng **TECHNICALLY_IMPLEMENTED** state của
research pipeline (code chạy, tests pass, artifacts đầy đủ). Prototype
KHÔNG tự thăng cấp `WORKING_ASSUMPTION` lên `RESEARCH_APPROVED_FINAL`.
Mọi thay đổi status vẫn thuộc thẩm quyền mentor / human researcher
(`AGENTS.md` §2.10).

---

## 4. System Scope

### 4.1. In Scope

Prototype PHẢI hỗ trợ các chức năng sau (xem chi tiết §6):

| Nhóm | Chức năng |
| --- | --- |
| Data Management | Import dataset đã qua FE-06; validate; hiển thị thông tin; hiển thị feature info. |
| Experiment Management | Chọn algorithm (trong 5), feature set (RFM Extended only), preprocessing config (FE-06 C7), parameters, random seed; chạy experiment; lưu config; theo dõi status. |
| Clustering | Thực thi 5 algorithms qua `ExperimentRunner`; output cluster labels + soft output (GMM, FCM) + noise flag (DBSCAN). |
| Evaluation | Tính Silhouette, DBI, CH, WCSS (diagnostic), runtime. Tính ARI / AMI khi có evidence từ EPIC-08. |
| Visualization | Cluster distribution, cluster size, evaluation metrics, diagnostic plots theo đúng ownership split (EPIC-06 diagnostic / EPIC-08 research / EPIC-09 segment). |
| Customer Segment / Profiling | Xem segment list (CP-04), segment size, RFM profile, behavioural profile, distinguishing features. |
| Marketing Recommendation | Xem recommendation khi có MKT framework — hiện tại REVIEW_REQUIRED. |
| Report / Export | Tổng hợp experiment result, xem report từ `reports/`. |

### 4.2. Out of Scope (production-grade features)

| OOS ID | Item | Lý do |
| --- | --- | --- |
| OOS-01 | Campaign automation (email / SMS / push) | Nghiên cứu không yêu cầu; MKT framework chưa tồn tại. |
| OOS-02 | Real-time customer tracking / streaming | Dataset là batch; methodology không yêu cầu. |
| OOS-03 | Payment / billing integration | NGOÀI phạm vi NCKH. |
| OOS-04 | Production CRM (Salesforce, HubSpot, ...) | NGOÀI phạm vi NCKH. |
| OOS-05 | Production MLOps (model registry, CI/CD cho model, A/B test deployment) | Methodology không yêu cầu; chỉ có 185 runs batch. |
| OOS-06 | Multi-tenant authentication / authorization phức tạp (OAuth, RBAC đầy đủ) | Prototype nghiên cứu, single-user. |
| OOS-07 | Cloud infrastructure (Kubernetes, auto-scaling) | Prototype chạy local. |
| OOS-08 | Real-time recommendation engine | Methodology unsupervised + batch; không phục vụ real-time. |
| OOS-09 | Business analytics dashboard ngoài phạm vi nghiên cứu | Methodology chỉ nội bộ (silhouette, DBI, CH, ARI/AMI, runtime). |
| OOS-10 | Thay đổi research methodology, RQ, algorithm scope, dataset, feature definition | `AGENTS.md` §2.1, §2.9 cấm. |
| OOS-11 | K-Medoids adapter / K-Medoids trong UI | ADR-0003 OUT OF SCOPE. |
| OOS-12 | RFM-only feature set trong UI | RQ2 reformulated; RFM-only là future work. |
| OOS-13 | Marketing framework tự tạo (khi MKT-01..05 chưa tồn tại) | `FR-MKT-01..05` REVIEW_REQUIRED. |
| OOS-14 | Tự động promote WORKING_ASSUMPTION thành FINAL | `AGENTS.md` §2.10 cấm AI Agent. |

---

## 5. Actors

Phạm vi prototype giữ actor ở mức tối thiểu, đúng với nghiên cứu
NCKH (single-user, single-purpose):

| Actor | Mô tả | Quyền |
| --- | --- | --- |
| **Researcher / System User** | Người thực hiện nghiên cứu, chạy prototype, xem kết quả. | Toàn quyền trong prototype (single-user). |
| **Mentor / Human Reviewer** (implicit) | Người review methodology decisions, approve status changes. | KHÔNG tương tác trực tiếp với prototype; review qua PR / ADR ngoài prototype. |

**Không tạo** các actor phức tạp (Admin / Auditor / Data Engineer / Business
Stakeholder) vì research scope không yêu cầu.

---

## 6. Functional Requirements

Mỗi FR có ID có cấu trúc, source rõ ràng, priority, và verification method.

### 6.1. Data Management

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-DATA-01 | Import dataset đã qua FE-06 (`final_clustering_dataset.parquet` SHA-256 `ba54033e...`) ở chế độ read-only. | FE-06 evidence; `AGENTS.md` §2.3 | MUST | Input SHA-256 unchanged sau import; verification script đọc lại SHA-256 và so sánh. |
| FR-DATA-02 | Validate dataset schema: 4,371 rows × 14 numeric columns, không có identifier (CustomerID / InvoiceNo), không NaN, không Inf, không constant feature. | FE-06 contract; ML-01 §4.7 | MUST | Reuse `validate_clustering_matrix` từ `clustering/validation.py`; fail-fast với error rõ ràng. |
| FR-DATA-03 | Hiển thị thông tin dataset: n_samples, n_features, feature names, dataset version (`FE06-v1.0`), SHA-256. | FE-06 evidence | MUST | UI panel hiển thị các field; copy SHA-256. |
| FR-DATA-04 | Hiển thị feature information per feature: tên, FE-06 status (`ELIGIBLE` / `ELIGIBLE_WORKING_ASSUMPTION`), unit, mô tả ngắn. | `docs/data_dictionary/`; FE-06 §13 | MUST | Bảng feature info với status rõ ràng; highlight features chưa final-approved. |
| FR-DATA-05 | Không cho phép import dataset khác ngoài FE-06 final matrix. | `AGENTS.md` §2.3, §2.9; ADR-0001 | MUST | Validation chỉ chấp nhận path đã được config trong `configs/*.yaml`; reject alternative paths. |
| FR-DATA-06 | Không cho phép edit / mutate dataset trong prototype. | `AGENTS.md` §2.3 | MUST | UI không có edit action; mọi write phải fail. |

### 6.2. Experiment Management

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-EXP-01 | Chọn algorithm trong 5: K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means. **K-Medoids KHÔNG hiển thị.** | ADR-0003 | MUST | Dropdown chỉ list 5; K-Medoids absent. |
| FR-EXP-02 | Chọn feature set: **RFM Extended (14 features) only.** | ADR-0004; RQ2 reformulation | MUST | Dropdown chỉ có 1 option; KHÔNG có "RFM-only". |
| FR-EXP-03 | Chọn preprocessing configuration: **FE-06 C7 only** (median imputation + Yeo-Johnson + RobustScaler). | FE-06 C7 (WORKING_ASSUMPTION) | MUST | Dropdown hiển thị "FE-06 C7 (working assumption)" kèm status. |
| FR-EXP-04 | Cấu hình parameters per algorithm: `n_clusters` (fixed-K), `eps` + `min_samples` (DBSCAN), `n_components` (GMM), `c` + `m` (FCM), `linkage` (Agglomerative), `n_init`, `max_iter`, ... | `configs/clustering.yaml`; EXP-02/03 evidence | MUST | Form validate theo schema YAML; reject unknown keys. |
| FR-EXP-05 | Random seed input với default = 42 (`framework.random_seed.default`). | ML-01 §4.3 | MUST | Seed field có default; chỉ pass xuống algorithm nếu `supports_random_state() == True`. |
| FR-EXP-06 | Chạy experiment qua `ExperimentRunner` (reuse `src/customer_segmentation/clustering/runner.py`). | ML-01 framework | MUST | Reuse code; không duplicate logic; output schema đúng `ExperimentResult`. |
| FR-EXP-07 | Lưu experiment configuration: input SHA, config SHA, hyperparameters, seed used, library versions, platform. | `AGENTS.md` §2.7; ML-01 §3.9 | MUST | `experiment_log_*.json` đầy đủ fields. |
| FR-EXP-08 | Theo dõi experiment status: QUEUED / RUNNING / SUCCESS / FAILED. | ML-01 §4.7 | MUST | Status hiển thị real-time; trên FAILED hiển thị error. |
| FR-EXP-09 | Chạy lại (rerun) experiment: cùng seed + cùng config → cùng cluster labels (reproducibility). | EXP-05 Block R; ML-01 §3.2 | MUST | Verification: rerun → so sánh labels_hash; PASS nếu identical. |
| FR-EXP-10 | Hiển thị danh sách experiments đã chạy (history) với metadata. | EVA-01 evidence | SHOULD | Bảng list experiments với filter theo algorithm / K / date. |

### 6.3. Clustering

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-CLUSTER-01 | Thực thi 5 algorithms trên cùng input matrix với cùng schema output. | ML-01 §3.4; EPIC-06 contract | MUST | Reuse `AlgorithmRegistry`; `AlgorithmRegistry.list_registered()` = 5 names. |
| FR-CLUSTER-02 | Output `cluster_labels` (shape `(n_samples,)`, dtype `int64`) cho mỗi algorithm. | ML-01 §4.6 | MUST | Verify output dtype + shape. |
| FR-CLUSTER-03 | Output `soft_probabilities` (GMM, shape `(n_samples, n_components)`). | ML-01 §4.6 | MUST | Verify presence for GMM only. |
| FR-CLUSTER-04 | Output `soft_membership` (FCM, shape `(n_samples, c)`). | ML-01 §4.6 | MUST | Verify presence for FCM only. |
| FR-CLUSTER-05 | Output `noise_label = -1` cho DBSCAN noise points; KHÔNG gán noise vào cluster nào. | ML-01 §4.6; CP-01 §4.4 | MUST | Verify DBSCAN labels ∈ {0..K-1, -1}. |

### 6.4. Evaluation

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-EVAL-01 | Tính **Silhouette Score** (primary). | `methodology_overview.md` §3.6; EXP-01 plan | MUST | Value trong `[-1, 1]`; fail nếu all points cùng cluster. |
| FR-EVAL-02 | Tính **Davies-Bouldin Index** (secondary). | `methodology_overview.md` §3.6 | MUST | Value ≥ 0. |
| FR-EVAL-03 | Tính **Calinski-Harabasz Index** (secondary). | `methodology_overview.md` §3.6 | MUST | Value ≥ 0. |
| FR-EVAL-04 | Tính **WCSS** kèm nhãn `diagnostic_only` rõ ràng trong UI. | `methodology_overview.md` §3.6; `AGENTS.md` §2.5 | MUST | UI badge "diagnostic only" hiển thị cạnh WCSS value. |
| FR-EVAL-05 | Tính **runtime** (execution_time_seconds) per run, n_repeat=5 cho variance estimation. | EXP-01 plan; `methodology_overview.md` §3.6 | MUST | Mean ± std runtime hiển thị. |
| FR-EVAL-06 | Tính **ARI / AMI** khi EPIC-08 evidence có sẵn (`exp05_cluster_labels.parquet`). | `methodology_overview.md` §3.6; RQ3 | MUST | Reuse EPIC-08 outputs; KHÔNG tự compute trong SYS layer khi EPIC-08 chưa ready. |
| FR-EVAL-07 | Tính **cluster size distribution**: largest, smallest, ratio, range, deviation_from_equal_size. | CP-01 §4.3 | SHOULD | Reuse `cp01_*` evidence; hiển thị descriptive indicators. |
| FR-EVAL-08 | **KHÔNG** tạo composite score / weighted ranking / overall algorithm ranking. | `AGENTS.md` §2.5, §2.6 | MUST | Negative test: code review confirms no composite score. |
| FR-EVAL-09 | **KHÔNG** gọi thuật toán nào "best", "winner", "optimal", "recommended". | `AGENTS.md` §2.5; ADR-0004 | MUST | Negative test: methodology gate check. |
| FR-EVAL-10 | So sánh kết quả trong phạm vi methodology cho phép: descriptive comparison (e.g., "DBSCAN noise ratio = 72.68%"), KHÔNG ranking. | CP-01 §11; `AGENTS.md` §2.5 | MUST | UI hiển thị giá trị + status; KHÔNG hiển thị "best algo" highlight. |

### 6.5. Visualization

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-VIZ-01 | Hiển thị cluster distribution (count + percent) per algorithm. | CP-01 §7 | MUST | Bar chart; xem `cp01_*.png` references. |
| FR-VIZ-02 | Hiển thị cluster size distribution với noise (DBSCAN) riêng. | CP-01 §4.4 | MUST | DBSCAN noise bar dùng hatch riêng (`///`); legend riêng. |
| FR-VIZ-03 | Hiển thị evaluation metrics comparison (silhouette / DBI / CH / runtime) per algorithm. | `methodology_overview.md` §3.6; EVA-02 | MUST | Plot / table với WCSS kèm label `diagnostic_only`. |
| FR-VIZ-04 | Highlight feature status (`ELIGIBLE_WORKING_ASSUMPTION`) trong feature table. | FE-06 §13 | MUST | Badge / color-coding rõ ràng; tooltip giải thích. |
| FR-VIZ-05 | Hiển thị diagnostic plots per algorithm (per ML-02..06 ownership): elbow (K-Means), dendrogram (Agglomerative), k-distance (DBSCAN), BIC/AIC (GMM), membership distribution (FCM). | ML-01 §9.2 | SHOULD | Tất cả phải được gắn nhãn `diagnostic_only`; KHÔNG dùng để kết luận. |
| FR-VIZ-06 | KHÔNG hard-code cluster colors / labels ở nhiều nơi — dùng single source of truth. | `AGENTS.md` §3; CP-01 §7 (color source) | MUST | Code review: 1 file định nghĩa `ALGORITHM_COLORS`. |
| FR-VIZ-07 | KHÔNG tạo research comparison plot (silhouette comparison, comparison dashboard) ở SYS layer. | EPIC-06 contract §9.2; ownership: EPIC-08 | MUST | Negative test: SYS layer chỉ reference EPIC-08 outputs, KHÔNG tự compute. |

### 6.6. Customer Segment / Profiling

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-SEG-01 | Hiển thị segment list per analysis unit (algorithm × condition: EXP-01 working-default / EXP-03 working-selected). | CP-01 §3.2; CP-04 §11 | MUST | Bảng segments với `unit_id`, `algorithm`, `source_experiment`, `configuration_status`. |
| FR-SEG-02 | Hiển thị segment size: n_customers, pct_of_assigned, pct_of_total, relative_size_ratio. | CP-01 §4.2 | MUST | Bảng với 2 denominator rõ ràng. |
| FR-SEG-03 | Hiển thị segment characteristics: RFM tier (Recency/Frequency/Monetary), behavioural profile (Tenure, Cadence, ...). | CP-04 §11 | MUST | Bảng / heatmap per segment. |
| FR-SEG-04 | Hiển thị segment name với status rõ ràng: `NAMED` (CP-04) / `COMPARATIVE` / `NOT_AVAILABLE` / `NOISE` (DBSCAN). | CP-04 §4.3; CP-05 §6.3 | MUST | UI hiển thị status badge; KHÔNG hard-code name. |
| FR-SEG-05 | Hiển thị distinguishing features per segment (từ CP-03 evidence). | CP-03; CP-05 §5 | SHOULD | Bảng features × segments với classification. |
| FR-SEG-06 | Hiển thị segment size band (`DOMINANT` / `LARGE` / `MEDIUM` / `SMALL` / `VERY_SMALL`) với nhãn `WORKING_ANALYTICAL_SIZE_BAND`. | CP-05 §8.3 | SHOULD | Band label rõ ràng; tooltip giải thích `WORKING_*` semantics. |
| FR-SEG-07 | Hiển thị 6 evaluation axes từ CP-05: distinctiveness, interpretability, consistency, size, stability, business relevance — mỗi axis kèm status enum rõ ràng. | CP-05 §5-§10 | SHOULD | Hiển thị status taxonomy; KHÔNG tạo score / ranking. |
| FR-SEG-08 | KHÔNG tự đặt tên segment. Tất cả names đến từ CP-04 evidence. | `AGENTS.md` §3; CP-05 §6.4 | MUST | Negative test: code review. |
| FR-SEG-09 | KHÔNG coi DBSCAN noise (label = -1) là Customer Segment. | CP-01 §4.4; CP-04 §3.2; CP-05 §12 | MUST | Noise hiển thị riêng với status `NOISE`; KHÔNG gộp vào segment list. |
| FR-SEG-10 | KHÔNG xuất bản cross-algorithm segment mapping (e.g., "K-Means C2 = GMM C3"). | CP-05 §14 | MUST | Negative test: KHÔNG có mapping table. |
| FR-SEG-11 | KHÔNG tạo overall "best segment" claim hoặc "priority_band" với ngữ nghĩa "nên target". | CP-05 §11.5; `AGENTS.md` §2.5 | MUST | Negative test: methodology gate. |

### 6.7. Marketing Recommendation

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-MKT-01 | **REVIEW_REQUIRED**: chỉ hiển thị Marketing Recommendation khi MKT-01..MKT-05 đã được implement. | Hiện trạng: CHƯA CÓ MKT docs trong repo (verified by `grep`). | MUST (gate) | UI ẩn Marketing section cho đến khi MKT framework tồn tại; hiển thị "MKT framework pending" message. |
| FR-MKT-02 | Kế thừa Marketing Recommendation từ MKT-01..MKT-05, KHÔNG tự phát minh framework. | SYS-01 brief §6.7; `AGENTS.md` §2.1 | MUST (when applicable) | Negative test: SYS layer KHÔNG định nghĩa marketing strategy. |
| FR-MKT-03 | Nếu MKT framework tồn tại: mỗi recommendation phải có Marketing Objective, Strategy, Recommended Action, KPI, Evidence / Rationale, Limitation. | SYS-01 brief §6.7 | SHOULD (when applicable) | UI form đầy đủ fields; evidence link tới segment profile. |
| FR-MKT-04 | Recommendation KHÔNG biến thành campaign automation. | SYS-01 brief §4.2; `AGENTS.md` §2.4 | MUST | UI chỉ "view" / "export", KHÔNG có "send campaign", "schedule", "trigger". |
| FR-MKT-05 | Recommendation KHÔNG sử dụng internal clustering metric như business effectiveness. | `AGENTS.md` §2.5; SYS-01 brief §6.4 | MUST | Methodology gate: KHÔNG hiển thị "Silhouette = X → high-value campaign". |
| FR-MKT-06 | Recommendation KHÔNG dùng cluster ID DBSCAN noise (label = -1). | CP-05 §12; SYS-01 brief §6.6 | MUST | Negative test: filter noise khỏi MKT input. |

### 6.8. Report / Export

| ID | Requirement | Source/Evidence | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-REPORT-01 | Hiển thị danh sách report đã sinh từ `reports/` (FE-01..06, EXP-01..05, EVA-01..05, CP-01..05). | README §4; EVA-01 evidence | SHOULD | Tree view với metadata (timestamp, SHA, n_rows). |
| FR-REPORT-02 | Export report tổng hợp experiment result (CSV / Markdown) cho mỗi run. | `AGENTS.md` §2.7; ML-01 §3.7 | SHOULD | Export function ghi file theo schema ML-01. |
| FR-REPORT-03 | KHÔNG commit / push / tạo PR từ prototype. | `AGENTS.md` §2.11 | MUST | UI KHÔNG có action này; prototype chỉ export local. |

---

## 7. Non-functional Requirements

| ID | Requirement | Rationale | Verification |
| --- | --- | --- | --- |
| NFR-01 | **Reproducibility**: cùng input SHA + cùng config + cùng seed + cùng library versions → cùng cluster labels. | `AGENTS.md` §2.7; EXP-05 Block R | Test: rerun 5 lần với seed=42 → labels_hash identical. |
| NFR-02 | **Traceability**: mỗi output phải truy ngược về input SHA, config SHA, code version, library version, seed used. | `AGENTS.md` §2.7; ML-01 §3.9 | Test: `experiment_log_*.json` đầy đủ fields. |
| NFR-03 | **Data integrity**: dataset ở read-only; không mutate input. | `AGENTS.md` §2.3 | Test: SHA-256 input unchanged trước / sau run. |
| NFR-04 | **Validation**: mọi input phải qua validation (no NaN, no Inf, no constant feature, no identifier leakage). | ML-01 §4.7 | Test: invalid input → FAIL với error rõ ràng. |
| NFR-05 | **Error handling**: error phải được capture, surface rõ ràng, KHÔNG silent fail. | `AGENTS.md` §2.8; ML-01 §3.7 | Test: missing file / invalid config → UI hiển thị error. |
| NFR-06 | **Methodology gate**: KHÔNG hiển thị / tạo / tự động generate nội dung có forbidden tokens ("best", "winner", "optimal", "recommended", "final", "superior", "champion", "VIP", "at-risk", "loyal customer", ...). | `AGENTS.md` §2.5; CP-01 §8 (methodology gate); CP-05 §17.2 | Test: methodology gate check tự động. |
| NFR-07 | **Usability ở mức prototype**: giao diện đủ để researcher thao tác; KHÔNG yêu cầu UX / UI polish production-grade. | SYS-01 scope | Manual review. |
| NFR-08 | **Performance ở mức prototype**: dataset 4,371 × 14 — runtime đủ nhanh cho interactive use; không tối ưu cho dataset lớn hơn. | Dataset size thực tế | Test: full pipeline (5 algorithms × 1 K × 1 seed) < 5 phút trên máy local. |
| NFR-09 | **Single-language consistency**: tài liệu / UI / comments bằng tiếng Việt (ngoại trừ code / identifier). | `AGENTS.md` §7; repo convention | Review. |
| NFR-10 | **Config-driven**: tất cả paths, parameters, options phải resolve từ `configs/*.yaml` — KHÔNG hard-code. | `AGENTS.md` §5 | Code review: không có string literal paths trong code. |

---

## 8. Research Constraints

Các ràng buộc mà prototype KHÔNG ĐƯỢC vi phạm vì lý do methodology.

| ID | Constraint | Source | Impact |
| --- | --- | --- | --- |
| CON-01 | **5 algorithms only** (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means). K-Medoids OUT OF SCOPE. | ADR-0003 | UI KHÔNG hiển thị K-Medoids; registry chỉ có 5 names. |
| CON-02 | **RFM Extended (14 features) only**. KHÔNG có RFM-only option. | ADR-0004; RQ2 reformulated | UI chỉ cho phép RFM Extended; KHÔNG RFM-only. |
| CON-03 | **Preprocessing = FE-06 C7 only** (median imputation + Yeo-Johnson + RobustScaler) trong prototype. | FE-06 WORKING_ASSUMPTION | UI không cho phép chọn preprocessing khác; khi thay đổi cần ADR mới. |
| CON-04 | **No "best algorithm" / "winner" / "optimal" / "recommended" / "final" claim**. | `AGENTS.md` §2.5 | Methodology gate test; UI không highlight "best". |
| CON-05 | **WCSS chỉ là diagnostic**, KHÔNG phải quality metric universal. | `methodology_overview.md` §3.6 | UI gắn nhãn `diagnostic_only` cạnh WCSS. |
| CON-06 | **No composite score** / weighted ranking / overall algorithm ranking. | `AGENTS.md` §2.6 | Code review confirms no composite score. |
| CON-07 | **Internal metrics only** (silhouette, DBI, CH, ARI/AMI, runtime). KHÔNG external validation / business effectiveness metric. | `AGENTS.md` §2.5; ADR-0004 | Negative test: chỉ internal metrics. |
| CON-08 | **DBSCAN noise (label = -1) KHÔNG phải Customer Segment**. | CP-01 §4.4; CP-05 §12 | UI tách noise riêng; KHÔNG gộp vào segment. |
| CON-09 | **Cross-algorithm cluster ID mapping KHÔNG được phép** (e.g., "K-Means C2 = GMM C3"). | CP-05 §14 | UI KHÔNG có mapping table. |
| CON-10 | **6 features ở `ELIGIBLE_WORKING_ASSUMPTION`** (Frequency, AverageQuantity, BasketSize, ActiveDays, CancellationRate, ReturnRate) phải được highlight rõ. | FE-06 §13 | UI feature table phải show status; tooltip giải thích. |
| CON-11 | **EXP-03 working-selected segments = `NOT_AVAILABLE`** cho mọi analysis unit vì per-customer labels parquet không persist. | CP-01 §3.2; EV03-HP-01; CP-05 §13 | UI hiển thị `NOT_AVAILABLE` thay vì empty rows. |
| CON-12 | **Marketing Recommendation KHÔNG tự tạo framework** — kế thừa MKT-01..MKT-05. | SYS-01 brief §6.7; `AGENTS.md` §2.1 | Hiện tại: prototype ẩn Marketing section; chờ MKT framework. |
| CON-13 | **AI Agent KHÔNG commit / push / PR** trong prototype. | `AGENTS.md` §2.11 | UI KHÔNG có action này; chỉ export local. |
| CON-14 | **Raw datasets KHÔNG commit**; `data/**` git-ignored. | `AGENTS.md` §2.12 | Repo `.gitignore` đã cover. |
| CON-15 | **DBSCAN silhouette: noise excluded** (sklearn convention). | `methodology_overview.md` §3.6 | Test: silhouette cho DBSCAN = compute trên non-noise subset. |
| CON-16 | **EXP-01 working-default = `WORKING_DEFAULT`**; EXP-03 = `WORKING_SELECTED` / `TIED_WORKING_SELECTED`. KHÔNG promote thành FINAL. | CP-01 §3.3; `AGENTS.md` §2.10 | UI hiển thị status rõ ràng. |

---

## 9. Use Case List

| UC ID | Tên | Actor | Mô tả ngắn |
| --- | --- | --- | --- |
| UC-01 | Import Dataset | Researcher | Load FE-06 final matrix + customer metadata; validate SHA-256. |
| UC-02 | Validate Dataset | Researcher | Xem kết quả validation: schema, SHA, feature status. |
| UC-03 | View Dataset Information | Researcher | Xem n_samples, n_features, version, SHA-256, feature dictionary. |
| UC-04 | Configure Experiment | Researcher | Chọn algorithm (5 options), K, parameters, seed. |
| UC-05 | Run Clustering | Researcher | Chạy ExperimentRunner; theo dõi status; xem kết quả. |
| UC-06 | View Evaluation Metrics | Researcher | Xem silhouette / DBI / CH / runtime (WCSS = diagnostic only). |
| UC-07 | Compare Experiment Results | Researcher | So sánh kết quả giữa các runs trong cùng scope methodology (descriptive). |
| UC-08 | View Customer Segments | Researcher | Xem segment list, size, RFM profile, behavioural profile, distinguishing features. |
| UC-09 | View Marketing Recommendation | Researcher | Xem recommendation (chỉ khi MKT framework tồn tại — REVIEW_REQUIRED). |
| UC-10 | View / Export Report | Researcher | Xem report từ `reports/`; export CSV / Markdown local. |

Lưu ý: prototype KHÔNG có UC cho "Pick best algorithm" / "Pick best K" /
"Trigger campaign" / "Send notification" — các hành động này bị cấm bởi
methodology constraint và OOS items.

---

## 10. User Flow

```
┌────────────────────────────────────────────────────────────────────┐
│ Start                                                              │
└────────────────────────────────────────────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 1. Import Dataset            │
                │    - Load final matrix       │
                │    - Load customer metadata  │
                │    - Verify SHA-256          │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 2. Validate                  │
                │    - Schema check            │
                │    - no NaN / Inf / constant │
                │    - no identifier leakage   │
                │    - CustomerID alignment    │
                │                              │
                │    Decision:                 │
                │      PASS → continue         │
                │      FAIL → display error    │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 3. View Dataset Information  │
                │    - n_samples / n_features  │
                │    - Version + SHA           │
                │    - Feature dictionary      │
                │      (status highlighted)    │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 4. Configure Experiment      │
                │    - Algorithm (5 options)   │
                │    - K / parameters / seed   │
                │    - Preprocessing: FE-06 C7 │
                │    - Feature set: RFM Ext.   │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 5. Run Experiment            │
                │    - Status: QUEUED →        │
                │      RUNNING → SUCCESS/FAIL │
                │    - Save experiment log     │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 6. View Evaluation           │
                │    - Silhouette (primary)    │
                │    - DBI / CH                │
                │    - WCSS (diagnostic only)  │
                │    - Runtime                 │
                │    - ARI / AMI (if avail.)   │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 7. View Customer Segments    │
                │    - Segment list (CP-04)    │
                │    - Size / RFM / behaviour  │
                │    - Distinguishing features │
                │    - 6 evaluation axes       │
                │      (CP-05)                │
                │    - DBSCAN noise separate   │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 8. View Marketing Recommend. │
                │    - (REVIEW_REQUIRED)       │
                │    - Hidden until MKT        │
                │      framework exists        │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ 9. View / Export Report      │
                │    - Local export only       │
                │    - NO commit / push / PR   │
                └─────────────────────────────┘
                                ↓
                ┌─────────────────────────────┐
                │ End                          │
                └─────────────────────────────┘
```

Error paths:
- **Validation FAIL (UC-02)**: hiển thị lỗi chi tiết (check nào fail, vì
  sao). KHÔNG cho phép tiếp tục sang UC-04.
- **Run FAILED (UC-05)**: hiển thị `error` field từ `ExperimentResult`.
  Có thể quay lại UC-04 để chỉnh config.
- **Marketing unavailable (UC-09)**: hiển thị thông báo "MKT framework
  pending — kế thừa MKT-01..MKT-05".

UI design chi tiết thuộc SYS-06 (KHÔNG thuộc SYS-01).

---

## 11. Requirement Traceability

Mapping từ Research Source → System Requirement → Future DEV / TEST.
Mọi DEV-XX / TEST-XX hiện tại ở trạng thái **TBD** — sẽ được xác định
trong SYS-02 → SYS-06 sau khi SYS-01 được approve.

### 11.1. Functional Requirement Traceability

| Research Source | System Requirement | Future DEV | Future TEST |
| --- | --- | --- | --- |
| FE-06 evidence; `AGENTS.md` §2.3 | FR-DATA-01 | DEV-TBD | TEST-TBD |
| FE-06 contract; ML-01 §4.7 | FR-DATA-02 | DEV-TBD | TEST-TBD |
| FE-06 evidence | FR-DATA-03 | DEV-TBD | TEST-TBD |
| `docs/data_dictionary/`; FE-06 §13 | FR-DATA-04 | DEV-TBD | TEST-TBD |
| `AGENTS.md` §2.3, §2.9; ADR-0001 | FR-DATA-05, FR-DATA-06 | DEV-TBD | TEST-TBD |
| ADR-0003 | FR-EXP-01 | DEV-TBD | TEST-TBD |
| ADR-0004; RQ2 reformulation | FR-EXP-02 | DEV-TBD | TEST-TBD |
| FE-06 C7 (WORKING_ASSUMPTION) | FR-EXP-03 | DEV-TBD | TEST-TBD |
| `configs/clustering.yaml`; EXP-02/03 | FR-EXP-04 | DEV-TBD | TEST-TBD |
| ML-01 §4.3 | FR-EXP-05 | DEV-TBD | TEST-TBD |
| ML-01 framework | FR-EXP-06 | DEV-TBD | TEST-TBD |
| `AGENTS.md` §2.7; ML-01 §3.9 | FR-EXP-07 | DEV-TBD | TEST-TBD |
| ML-01 §4.7 | FR-EXP-08 | DEV-TBD | TEST-TBD |
| EXP-05 Block R; ML-01 §3.2 | FR-EXP-09 | DEV-TBD | TEST-TBD |
| EVA-01 evidence | FR-EXP-10 | DEV-TBD | TEST-TBD |
| ML-01 §3.4; EPIC-06 contract | FR-CLUSTER-01..05 | DEV-TBD | TEST-TBD |
| `methodology_overview.md` §3.6 | FR-EVAL-01..07 | DEV-TBD | TEST-TBD |
| `AGENTS.md` §2.5, §2.6 | FR-EVAL-08, FR-EVAL-09 | DEV-TBD | TEST-TBD |
| CP-01 §11; `AGENTS.md` §2.5 | FR-EVAL-10 | DEV-TBD | TEST-TBD |
| CP-01 §7; CP-01 §4.4; FE-06 §13 | FR-VIZ-01..04 | DEV-TBD | TEST-TBD |
| ML-01 §9.2; `AGENTS.md` §3 | FR-VIZ-05, FR-VIZ-06, FR-VIZ-07 | DEV-TBD | TEST-TBD |
| CP-01 §3.2; CP-04 §11; CP-01 §4.2 | FR-SEG-01..03 | DEV-TBD | TEST-TBD |
| CP-04 §4.3; CP-05 §6.3 | FR-SEG-04 | DEV-TBD | TEST-TBD |
| CP-03; CP-05 §5 | FR-SEG-05 | DEV-TBD | TEST-TBD |
| CP-05 §8.3 | FR-SEG-06 | DEV-TBD | TEST-TBD |
| CP-05 §5-§10 | FR-SEG-07 | DEV-TBD | TEST-TBD |
| `AGENTS.md` §3; CP-05 §6.4; §12; §14; §11.5 | FR-SEG-08..11 | DEV-TBD | TEST-TBD |
| Hiện trạng repo (MKT-01..05 absent) | FR-MKT-01..06 | DEV-TBD | TEST-TBD |
| README §4; EVA-01; `AGENTS.md` §2.7; ML-01 §3.7; §2.11 | FR-REPORT-01..03 | DEV-TBD | TEST-TBD |

### 11.2. Non-functional Requirement Traceability

| NFR | Source | Future TEST |
| --- | --- | --- |
| NFR-01 Reproducibility | `AGENTS.md` §2.7; EXP-05 Block R | TEST-TBD |
| NFR-02 Traceability | `AGENTS.md` §2.7; ML-01 §3.9 | TEST-TBD |
| NFR-03 Data integrity | `AGENTS.md` §2.3 | TEST-TBD |
| NFR-04 Validation | ML-01 §4.7 | TEST-TBD |
| NFR-05 Error handling | `AGENTS.md` §2.8; ML-01 §3.7 | TEST-TBD |
| NFR-06 Methodology gate | `AGENTS.md` §2.5; CP-01 §8; CP-05 §17.2 | TEST-TBD |
| NFR-07 Usability | SYS-01 scope | Manual review |
| NFR-08 Performance | Dataset size thực tế | TEST-TBD |
| NFR-09 Single-language | `AGENTS.md` §7; repo convention | Manual review |
| NFR-10 Config-driven | `AGENTS.md` §5 | Code review |

### 11.3. Research Constraint → Requirement Mapping

| Constraint | Ánh xạ vào |
| --- | --- |
| CON-01 (5 algorithms only) | FR-EXP-01; FR-CLUSTER-01; NFR-06 |
| CON-02 (RFM Extended only) | FR-EXP-02; FR-DATA-04 |
| CON-03 (FE-06 C7 only) | FR-EXP-03 |
| CON-04 (No "best" claim) | FR-EVAL-09, FR-EVAL-10; NFR-06 |
| CON-05 (WCSS diagnostic only) | FR-EVAL-04; FR-VIZ-03 |
| CON-06 (No composite score) | FR-EVAL-08; NFR-06 |
| CON-07 (Internal metrics only) | FR-EVAL-01..07; FR-MKT-05 |
| CON-08 (DBSCAN noise not segment) | FR-CLUSTER-05; FR-SEG-09; FR-MKT-06 |
| CON-09 (No cross-algorithm mapping) | FR-SEG-10 |
| CON-10 (Feature status highlight) | FR-DATA-04; FR-VIZ-04 |
| CON-11 (EXP-03 NOT_AVAILABLE) | FR-SEG-01 |
| CON-12 (Marketing inherits MKT) | FR-MKT-01, FR-MKT-02 |
| CON-13 (No commit / push / PR) | FR-REPORT-03 |
| CON-14 (No raw data commit) | (repo `.gitignore`) |
| CON-15 (DBSCAN noise excluded from silhouette) | FR-EVAL-01 (implementation note) |
| CON-16 (Status taxonomy) | FR-SEG-01 |

---

## 12. Dependencies

### 12.1. Phụ thuộc Repository (đã có)

- **Data:**
  - `data/processed/final_clustering_dataset.parquet` (FE-06 output, git-ignored).
  - `data/processed/customer_metadata.parquet` (FE-06 output, git-ignored).
  - `data/raw/primary/Online Retail.xlsx` (raw, git-ignored).
- **Configs:** `configs/clustering.yaml`, `configs/experiment.yaml`,
  `configs/dataset.yaml`, `configs/preprocessing.yaml`,
  `configs/transformation.yaml`, `configs/feature_engineering.yaml`,
  `configs/aggregation.yaml`, `configs/outlier.yaml`.
- **Source code:**
  - `src/customer_segmentation/clustering/` (ML-01 framework + 5 adapters).
  - `src/customer_segmentation/evaluation/` (EVA-01..03 evidence).
  - `src/customer_segmentation/profiling/cp01..05/` (CP evidence).
  - `src/customer_segmentation/preprocessing/`, `transformation/`,
    `features/`, `aggregation/`, `data/`, `outlier_analysis/`.
- **Reports (read-only references):**
  - `reports/fe01/..fe06/`
  - `reports/exp01/..exp05/`
  - `reports/evaluation/eva01/`
  - `reports/profiling/cp01/..cp05/`
  - `reports/evaluation_results/`
  - `reports/experiment_results/`
- **Tests:** `tests/test_ml01_*.py`, `tests/test_ml02..06_*.py`,
  `tests/test_eva*.py`, `tests/test_cp*.py`, `tests/test_*.py`.

### 12.2. Phụ thuộc Bên ngoài

- **Python ≥ 3.11** (per README §3; `pyproject.toml`).
- **Existing dependencies (đã khai báo trong `pyproject.toml`):**
  - numpy, pandas, scipy, scikit-learn, pyarrow.
  - pytest, ruff, black.
- **KHÔNG thêm dependency mới** trong SYS-01 (chỉ phân tích yêu cầu).

### 12.3. Phụ thuộc Documentation

- `AGENTS.md` (rules binding).
- `README.md`.
- `docs/methodology/research_questions.md`, `methodology_overview.md`.
- `docs/decisions/0001..0004-*.md`.
- `docs/research/review/METHODOLOGY_LOCK_STATUS.md`.
- `docs/data_dictionary/`.
- `docs/evaluation/EVA-01..05.md`, `CP-01..05.md`.
- `docs/research/FE-04..FE-06.md`, `ML-01..ML-06.md`, `EPIC06_DOCUMENTATION_CONTRACT.md`,
  `EPIC09_CP05_PLAN.md`, `EXP01..05_PLAN.md`, `RFM_ONLY_FUTURE_WORK_PLAN.md`.

### 12.4. Phụ thuộc Methodology (locked)

- Algorithm scope: 5 algorithms (ADR-0003).
- RQ definitions: RQ1, RQ2, RQ3 (ADR-0004).
- Dataset: UCI Online Retail (ADR-0001).
- Preprocessing: FE-06 C7 (WORKING_ASSUMPTION).
- Feature set: RFM Extended 14 features (FE-06).
- Final matrix: `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`.

### 12.5. Phụ thuộc MKT framework

- **HIỆN TẠI: KHÔNG CÓ.** MKT-01..MKT-05 chưa tồn tại.
- Đây là blocker cho FR-MKT-* (xem §13 Open Questions).

---

## 13. Limitations / Open Questions

Các điểm chưa rõ hoặc cần mentor / human researcher quyết định trước khi
SYS-02 → SYS-06. Mọi thay đổi methodology vẫn thuộc thẩm quyền
mentor (per `AGENTS.md` §2.10).

| ID | Open Question / Limitation | Impact | Trạng thái |
| --- | --- | --- | --- |
| OQ-01 | **MKT-01..MKT-05 chưa tồn tại trong repo.** Marketing Recommendation module phụ thuộc framework này. | FR-MKT-01..06 tạm thời ở trạng thái `REVIEW_REQUIRED`; UI phải ẩn cho đến khi có MKT framework. | REVIEW_REQUIRED — cần mentor / human researcher quyết định: (a) tạo MKT framework trước SYS-06, hoặc (b) đợi EPIC-09/10 xong rồi tạo. |
| OQ-02 | **MKT framework scope chưa rõ**: SYS-01 brief yêu cầu "Marketing Objective, Strategy, Recommended Action, KPI, Evidence, Limitation" — có khớp với cách MKT-01..05 dự kiến không? | FR-MKT-03 có thể cần điều chỉnh khi MKT framework được tạo. | REVIEW_REQUIRED |
| OQ-03 | **SYS layer nên re-implement cluster code, hay chỉ wrap (re-use) ML-01 framework?** | Ảnh hưởng SYS-02 architecture (re-implement vs re-use). | REVIEW_REQUIRED — recommend re-use `ExperimentRunner` (DRY, single source of truth). |
| OQ-04 | **Prototype có cần xử lý EXP-03 working-selected labels (`NOT_AVAILABLE`) trong UI không, hay chỉ reference config metadata?** | Ảnh hưởng FR-SEG-01, FR-EXP-10. | Hiện tại: reference config metadata only (CP-01 pattern). Có thể mở rộng nếu EXP-03 được rerun. |
| OQ-05 | **Prototype có cần hỗ trợ visualization trên data projection (PCA / UMAP / t-SNE) không?** | Ảnh hưởng FR-VIZ-05 ownership: PCA / UMAP nằm ở EPIC-08 hoặc SYS layer? | REVIEW_REQUIRED — CP-05 §2.2 OOS ghi rõ PCA / UMAP là OUT OF SCOPE cho CP-05. Nên tuân thủ. |
| OQ-06 | **Có cần expose tất cả 5 evaluation axes của CP-05 trong UI không, hay chỉ summary?** | Ảnh hưởng FR-SEG-07. | Có thể progress: lúc đầu chỉ summary; mở rộng khi CP-05 implement xong. |
| OQ-07 | **A/B testing cho prototype** có cần thiết không? | Ngoài scope NCKH; không nên thêm. | Đã ghi OOS-05. |
| OQ-08 | **Multi-user / concurrent access** có cần thiết không? | Ngoài scope; prototype single-user. | Đã ghi §5 Actors. |
| OQ-09 | **Prototype chạy trên Jupyter notebook (UI-less) hay standalone web app (Streamlit / Flask / Django)?** | Ảnh hưởng SYS-02 (architecture), SYS-06 (UI). | REVIEW_REQUIRED — chưa quyết định. `notebooks/` đã có sẵn cho exploration. |
| OQ-10 | **Có cần API layer (REST / GraphQL) cho SYS-01, hay prototype chỉ là CLI + notebook?** | Ảnh hưởng SYS-02 architecture. | REVIEW_REQUIRED — recommend CLI + notebook trước; API là future work. |
| OQ-11 | **Database có cần không** (PostgreSQL, SQLite, ...)? | Ảnh hưởng SYS-02 architecture; hiện tại repo dùng parquet files. | Recommend: KHÔNG cần database trong prototype. Parquet + filesystem đã đủ cho 185 runs + profiling evidence. |
| OQ-12 | **6 features `ELIGIBLE_WORKING_ASSUMPTION`** có nên được hiển thị kèm tooltip "chưa final-approved" trong UI không? | Ảnh hưởng FR-DATA-04, FR-VIZ-04. | Recommend: CÓ, để user hiểu status. |
| OQ-13 | **WCSS diagnostic label** nên được style như thế nào trong UI (badge / icon / tooltip)? | Ảnh hưởng FR-EVAL-04, FR-VIZ-03. | Decision thuộc UI design (SYS-06). |
| OQ-14 | **Có cần "experiment rerun" UI action (với cùng seed) để verify reproducibility không?** | Ảnh hưởng FR-EXP-09. | Recommend: CÓ — giúp user thấy EXP-05 Block R evidence trực tiếp. |
| OQ-15 | **DBSCAN noise ratio (72.68% at baseline)** nên được highlight như thế nào — chỉ số, hay có cảnh báo? | Ảnh hưởng FR-VIZ-02, FR-SEG-09. | Recommend: hiển thị như descriptive indicator, KHÔNG warning. |

### 13.1. Conflicts phát hiện trong quá trình phân tích

| ID | Conflict | Cách xử lý |
| --- | --- | --- |
| CF-01 | AGENTS.md §3 (trước ADR-0003) đã từng liệt kê K-Medoids trong "4 fixed algorithms". ADR-0003 đã resolve bằng "5 algorithms, K-Medoids OUT". | Tuân thủ ADR-0003 (mới hơn, đã được accept). Ghi rõ source-of-truth: ADR-0003 + METHODOLOGY_LOCK_STATUS.md. |
| CF-02 | README §2 ghi "EPIC-09: Customer profiling — PENDING" nhưng CP-01..04 đã IMPLEMENTED. | Prototype phản ánh implementation state: CP-01..04 done, CP-05 plan. |
| CF-03 | EPIC-10 (Visualization + report) được ghi "PENDING" trong README nhưng CP-01 đã có visualization (figures). | Prototype phản ánh: per-EPIC visualization đã có (CP-01 figures), nhưng cross-EPIC research viz (EPIC-08 owned) chưa có. Phân biệt ownership. |
| CF-04 | MKT-01..MKT-05 chưa tồn tại nhưng SYS-01 brief §6.7 yêu cầu "Marketing Recommendation kế thừa MKT-01..05". | Đã ghi OQ-01 + OQ-02. Prototype ẩn Marketing section cho đến khi MKT framework tồn tại. |
| CF-05 | SYS-01 brief §6.4 nói "WCSS nếu phù hợp với convention hiện tại và phải giữ đúng vai trò diagnostic". Methodology đã lock WCSS = diagnostic only. | Không conflict. Convention hiện tại = diagnostic only. |

### 13.2. Items NOT in scope của SYS-01

Để tránh scope creep, các item sau đã được verify là **NGOÀI** SYS-01
(per SYS-01 brief §17):

- ❌ Architecture diagram, component diagram.
- ❌ Database schema.
- ❌ API specification (REST / GraphQL endpoints).
- ❌ Frontend wireframe / mockup.
- ❌ Code implementation.
- ❌ ML service deployment.
- ❌ MLOps pipeline.
- ❌ Authentication / Authorization.
- ❌ Cloud infrastructure.
- ❌ Production SaaS features.
- ❌ Git operations (commit / push / PR / merge).

---

## 14. Acceptance Criteria

SYS-01 đạt `READY` khi tất cả items dưới đây PASS.

### 14.1. Structural

| Item | Tiêu chí | Status |
| --- | --- | --- |
| File location | `docs/system/SYS-01_requirements.md` tồn tại. | ✅ (file này) |
| 15 sections | Đủ 15 sections theo template (Objective → Review Status). | ✅ |
| Tables | Đủ 4 bảng tổng hợp (FR / NFR / CON / OOS) + Traceability table. | ✅ |
| Requirement IDs | Mỗi FR/NFR/CON/OOS có ID duy nhất. | ✅ |

### 14.2. Methodology

| Item | Tiêu chí | Status |
| --- | --- | --- |
| No "best algorithm" claim | KHÔNG có câu nào trong SYS-01 gọi algorithm / approach nào là "best", "winner", "optimal", "recommended", "final", "superior". | ✅ (verified by reading) |
| K-Medoids absent | KHÔNG có FR nào đề cập K-Medoids như supported option. CON-01 ghi rõ OUT OF SCOPE. | ✅ |
| RFM-only absent | KHÔNG có FR nào cho phép RFM-only feature set. CON-02 ghi rõ. | ✅ |
| WCSS = diagnostic only | FR-EVAL-04, FR-VIZ-03 gắn nhãn rõ. | ✅ |
| Internal metrics only | FR-EVAL-01..07 chỉ liệt kê internal metrics. CON-07 cấm business effectiveness. | ✅ |
| No hard-code segment name | FR-SEG-08, FR-SEG-09 cấm; CON-08, CON-09 cấm. | ✅ |
| Marketing inherits MKT | FR-MKT-01, FR-MKT-02 cấm tự tạo framework. CON-12 ghi rõ. | ✅ |
| 5 algorithms only | FR-EXP-01, FR-CLUSTER-01 chỉ 5. CON-01 cấm K-Medoids. | ✅ |
| Methodology gate | NFR-06 yêu cầu methodology gate test. | ✅ |
| Read-only | FR-DATA-05, FR-DATA-06, NFR-03, CON-13, CON-14. | ✅ |
| No silent policy change | Tuân thủ `AGENTS.md` §2.9; mọi constraint đều có source ADR / methodology doc. | ✅ |

### 14.3. Boundary

| Item | Tiêu chí | Status |
| --- | --- | --- |
| No code | SYS-01 chỉ tạo 1 file markdown; KHÔNG tạo / sửa source code. | ✅ |
| No architecture | KHÔNG tạo architecture diagram, component diagram, database schema. | ✅ |
| No API | KHÔNG tạo API spec. | ✅ |
| No frontend | KHÔNG tạo UI wireframe / mockup. | ✅ |
| No Git ops | KHÔNG commit / push / PR. | ✅ |

### 14.4. Traceability

| Item | Tiêu chí | Status |
| --- | --- | --- |
| Research source | Mỗi FR quan trọng có source từ research doc (RQ, ADR, methodology, FE-06, CP-0x, EVA-0x). | ✅ (§11) |
| Future DEV/TEST | Ghi rõ `DEV-TBD` / `TEST-TBD` (chưa tự ý đặt ID). | ✅ (§11) |
| Open questions | Tất cả ambiguity được liệt kê trong §13. | ✅ (15 items) |
| Conflicts | Tất cả conflict được liệt kê trong §13.1. | ✅ (5 items) |

---

## 15. Review Status

SYS-01 là tài liệu **PHÂN TÍCH YÊU CẦU** ở mức requirements. Tài liệu
này phản ánh research pipeline đã freeze (DS-05 → FE-06 → EPIC-06 →
EPIC-07 → EPIC-08 active → EPIC-09 partial) và đề xuất prototype
system minh họa workflow đó.

Tài liệu này:

- ✅ Tuân thủ `AGENTS.md` §2 (global principles) và §3 (stage guardrails).
- ✅ Không thay đổi methodology / RQ / algorithm scope.
- ✅ Không code, không architecture, không API, không database, không frontend.
- ✅ Không Git operations.
- ✅ Phân biệt rõ TECHNICALLY_IMPLEMENTED vs RESEARCH_APPROVED_FINAL.
- ✅ Có traceability từ Research Source → System Requirement.
- ✅ Ghi rõ Open Questions cho mentor / human researcher quyết định.

Sau khi SYS-01 được review, các task tiếp theo sẽ thuộc:

- **SYS-02**: System Architecture (component diagram, layer responsibilities, deployment view).
- **SYS-03**: Data Architecture (data flow, storage, integrity contract).
- **SYS-04**: Interface / API specification (nếu cần).
- **SYS-05**: Test Strategy.
- **SYS-06**: UI / UX Design.

Mỗi SYS-02..06 sẽ là task riêng với scope riêng, không tự ý thực hiện
trong SYS-01.

---

## Phụ lục A — Requirement ID Index

### Functional Requirements (51 IDs)

- **Data Management (6):** FR-DATA-01, FR-DATA-02, FR-DATA-03, FR-DATA-04, FR-DATA-05, FR-DATA-06
- **Experiment Management (10):** FR-EXP-01, FR-EXP-02, FR-EXP-03, FR-EXP-04, FR-EXP-05, FR-EXP-06, FR-EXP-07, FR-EXP-08, FR-EXP-09, FR-EXP-10
- **Clustering (5):** FR-CLUSTER-01, FR-CLUSTER-02, FR-CLUSTER-03, FR-CLUSTER-04, FR-CLUSTER-05
- **Evaluation (10):** FR-EVAL-01, FR-EVAL-02, FR-EVAL-03, FR-EVAL-04, FR-EVAL-05, FR-EVAL-06, FR-EVAL-07, FR-EVAL-08, FR-EVAL-09, FR-EVAL-10
- **Visualization (7):** FR-VIZ-01, FR-VIZ-02, FR-VIZ-03, FR-VIZ-04, FR-VIZ-05, FR-VIZ-06, FR-VIZ-07
- **Customer Segment / Profiling (11):** FR-SEG-01, FR-SEG-02, FR-SEG-03, FR-SEG-04, FR-SEG-05, FR-SEG-06, FR-SEG-07, FR-SEG-08, FR-SEG-09, FR-SEG-10, FR-SEG-11
- **Marketing Recommendation (6):** FR-MKT-01, FR-MKT-02, FR-MKT-03, FR-MKT-04, FR-MKT-05, FR-MKT-06
- **Report / Export (3):** FR-REPORT-01, FR-REPORT-02, FR-REPORT-03

### Non-functional Requirements (10 IDs)

NFR-01, NFR-02, NFR-03, NFR-04, NFR-05, NFR-06, NFR-07, NFR-08, NFR-09, NFR-10

### Research Constraints (16 IDs)

CON-01, CON-02, CON-03, CON-04, CON-05, CON-06, CON-07, CON-08, CON-09, CON-10, CON-11, CON-12, CON-13, CON-14, CON-15, CON-16

### Out of Scope (14 IDs)

OOS-01, OOS-02, OOS-03, OOS-04, OOS-05, OOS-06, OOS-07, OOS-08, OOS-09, OOS-10, OOS-11, OOS-12, OOS-13, OOS-14

### Use Cases (10 IDs)

UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10

### Open Questions (15 IDs)

OQ-01, OQ-02, OQ-03, OQ-04, OQ-05, OQ-06, OQ-07, OQ-08, OQ-09, OQ-10, OQ-11, OQ-12, OQ-13, OQ-14, OQ-15

### Conflicts (5 IDs)

CF-01, CF-02, CF-03, CF-04, CF-05

---

## Phụ lục B — Glossary

| Thuật ngữ | Ý nghĩa |
| --- | --- |
| **Adapter** | Class implement `BaseClusterAlgorithm` cho 1 thuật toán clustering. |
| **Algorithm family** | Phân loại: hard / density_based / model_based / fuzzy. |
| **CP-NN** | Customer Profiling EPIC-09 (CP-01..CP-05). |
| **EVA-NN** | Evaluation EPIC-08 (EVA-01..EVA-05). |
| **EXP-NN** | Controlled experiment EPIC-07 (EXP-01..EXP-05). |
| **FE-NN** | Feature engineering stage (FE-01..FE-06). |
| **ML-NN** | Clustering experiment framework / adapter (ML-01..ML-06). |
| **MKT-NN** | Marketing Recommendation framework (CHƯA TỒN TẠI trong repo). |
| **SYS-NN** | System Design EPIC-11 (SYS-01..SYS-06). |
| **Working assumption** | Default config chưa được mentor approve. |
| **Research-approved final** | Methodology đã được mentor / human researcher approve. |
| **REVIEW_REQUIRED** | Trạng thái yêu cầu mentor / human researcher quyết định. |
| **Diagnostic only** | Chỉ mang tính báo cáo; không ảnh hưởng quyết định. |

---

*Tài liệu này là SYS-01 (Phân tích yêu cầu hệ thống thử nghiệm) thuộc
EPIC-11. KHÔNG thay đổi methodology / RQ / algorithm scope. KHÔNG code.
KHÔNG Git operations. Sẵn sàng cho mentor / human researcher review.*
