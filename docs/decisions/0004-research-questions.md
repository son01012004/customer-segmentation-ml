# ADR-0004 — Research Questions: Định nghĩa RQ1, RQ2, RQ3

> **Quy ước ngôn ngữ:** Tiếng Việt cho phần diễn giải; giữ nguyên
> tiếng Anh cho RQ ID, identifier, EPIC ID, status, file path, command
> theo convention hiện có.

## Status

Accepted

## Date

2026-09-22

## Task ID

EPIC-07 / EPIC-08

## Deciders

Researcher / Mentor

## Context

Repository trước đây thiếu định nghĩa Research Question chính thức. Thư
mục `docs/methodology/` chỉ chứa TODO placeholder. Research question
được suy ra từ tài liệu experiment, tạo ra sự mơ hồ về:

- RQ1, RQ2, và RQ3 thực sự đo gì.
- Evidence nào cần thiết để trả lời mỗi câu hỏi.
- Scope boundary nào được áp dụng.
- Mỗi RQ map sang experimental evidence thế nào.

Ngoài ra, RQ2 trước đây được frame là so sánh giữa "RFM-only" (3 feature)
và "RFM Extended" (14 feature). Tuy nhiên, RFM-only artifact không tồn tại
trong repository, nghĩa là framing RQ2 ban đầu không thể trả lời được
với evidence hiện tại. EXP-04 Family A (đáng lẽ evaluate RFM-only) đã
bị DEFERRED.

Có ba lựa chọn:

- **Option A**: Materialize RFM-only artifact và execute EXP-04 Family A
  để cho phép framing RQ2 ban đầu. Cost ước tính: ~30–60 run mới +
  ~1–2 tuần.
- **Option B**: Reformulate RQ2 để phản ánh evidence hiện có thực sự
  support. Không cần artifact mới hoặc rerun.
- **Option C**: Chấp nhận RQ2 là permanently incomplete (PARTIAL). Không
  phải research state sạch.

## Decision

### RQ1 — Algorithm Comparison Under Controlled Conditions

> **RQ1 question:** Các thuật toán clustering khác nhau hoạt động thế
> nào trên không gian feature behavioral cấp customer được rút ra từ
> dữ liệu transactional bán lẻ, dưới các điều kiện thí nghiệm controlled?

**Research scope:**

- **Population / Unit of Analysis**: Customer-level. Mỗi customer được
  biểu diễn bằng một feature vector trong R¹⁴ (14 feature). Unit =
  customer (định danh bằng CustomerID).
- **Dataset**: `data/processed/final_clustering_dataset.parquet`
  (FE06-v1.0), SHA-256
  `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`.
  4,371 customer × 14 feature.
- **Feature Representation**: RFM Extended = 14 feature. Sáu feature ở
  trạng thái `ELIGIBLE_WORKING_ASSUMPTION` (Frequency, AverageQuantity,
  BasketSize, ActiveDays, CancellationRate, ReturnRate). Feature set
  được chấp nhận as-is cho phase hiện tại.
- **Preprocessing**: FE-06 C7 configuration (median imputation +
  Yeo-Johnson transformation + RobustScaler). Status = `WORKING_ASSUMPTION`.
- **Algorithm Scope**: Năm thuật toán (theo ADR-0003): K-Means,
  Agglomerative, DBSCAN, GMM, Fuzzy C-Means. K-Medoids là OUT OF SCOPE.
- **K Treatment**: EXP-02 sweep K ∈ [2, 10] step=1 xác định 13 candidate.
  EXP-03 dùng K=3 từ EXP-02 làm controlled interaction point. K được
  xử lý per-experiment; không có claim "best K".
- **Hyperparameter Treatment**: EXP-03 sensitivity analysis tạo ra
  per-algorithm working selection qua protocol (silhouette primary → DBI
  → CH tiebreaker). Status = `WORKING_SELECTED` (chưa final approved).
- **Quality Metrics**: Chỉ internal metric: Silhouette Score,
  Davies-Bouldin Index, Calinski-Harabasz Index, Within-Cluster Sum of
  Squares (WCSS). External/business metric nằm ngoài scope.
- **Runtime**: Algorithm execution time, đo per repeat (n_repeat=5). Loại
  trừ metric computation và artifact writing.
- **Reproducibility**: Đã verify tại EXP-05 Block R (5/5 thuật toán
  reproducible với seed=42).
- **Stability**: EXP-05 Block S (seed sensitivity) và Block N (feature
  perturbation) tạo raw evidence; ARI/AMI computation deferred to
  EPIC-08.
- **Interpretation Boundary**: Không claim "best", "winner", "optimal",
  "recommended", hoặc "final" algorithm. Cross-algorithm comparison được
  trình bày dưới dạng evidence với caveat rõ ràng. Composite scores
  bị cấm.

**Evidence hỗ trợ RQ1:**

- EXP-01: 5 thuật toán × 1 configuration = baseline metrics.
- EXP-02: 37 run, K ∈ [2, 10], 13 candidate K value.
- EXP-03: 38 run, hyperparameter sensitivity per algorithm.
- EXP-05: Block R/S/N raw stability evidence.

---

### RQ2 — Preprocessing Sensitivity Under Fixed Feature Representation

> **RQ2 question:** Chiến lược preprocessing ảnh hưởng thế nào đến
> clustering quality dưới một feature representation cấp customer cố
> định?

**Rationale cho reformulation:**

Framing RQ2 ban đầu ("RFM-only vs RFM Extended") không thể được
evaluate vì RFM-only artifact không tồn tại và EXP-04 Family A đã bị
DEFERRED. Thay vì để RQ2 permanently incomplete hoặc delay research để
materialize RFM-only, RQ2 được reformulate để phản ánh evidence **thực
sự** có sẵn.

EXP-04 Family B đã evaluate sáu preprocessing configuration (C0:
none/none, C1: none/standard, C2: none/minmax, C3: none/robust, C6:
yeo_johnson/standard, C7: yeo_johnson/robust) trên cùng bộ 14-feature
RFM Extended dùng K-Means (K=4). Điều này trực tiếp hỗ trợ câu hỏi về
độ nhạy của preprocessing strategy.

**Research scope:**

- **Population / Unit of Analysis**: Giống RQ1 (customer-level, 4,371
  customer).
- **Dataset**: Giống RQ1.
- **Feature Representation**: RFM Extended (14 feature), cố định. Giống
  RQ1.
- **Independent Variable**: Preprocessing strategy (transformation ×
  scaling configuration).
- **Dependent Variables**: Internal quality metric (silhouette, DBI, CH,
  WCSS) và runtime.
- **Algorithm**: Chỉ K-Means (controlled reference theo EXP-04 design).
  Không phải so sánh giữa các thuật toán.
- **K**: K=4 (controlled reference theo EXP-04 design).
- **Evidence**: 30 run qua 6 scenario × 5 repeat từ EXP-04 Family B.

**Cái RQ2 KHÔNG hỏi:**

- Không so sánh RFM-only vs RFM Extended (điều này yêu cầu RFM-only
  artifact).
- Không xác định "best preprocessing configuration".
- Không đưa ra cross-algorithm preprocessing claim.

**Giới hạn của reformulated RQ2:**

- Single-algorithm (K-Means) — preprocessing sensitivity có thể khác
  nhau giữa các thuật toán.
- Single-K (K=4) — sensitivity có thể khác ở các cluster count khác.
- RFM-only comparison là **FUTURE WORK**. Xem
  `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`.

**Evidence hỗ trợ reformulated RQ2:**

- EXP-04 Family B: 6 preprocessing scenario × 5 repeat = 30 run, tất cả
  deterministic, tất cả thành công.

---

### RQ3 — Stability and Reproducibility

> **RQ3 question:** Clustering do mỗi thuật toán tạo ra reproducible và
> robust đến mức nào dưới các seed khác nhau và perturbation trên
> feature space?

**Research scope:**

- **Population / Unit of Analysis**: Giống RQ1 (customer-level).
- **Dataset**: Giống RQ1.
- **Reproducibility (Block R)**: Cùng seed + cùng config + cùng input →
  output giống hệt. Đã verify cho cả 5 thuật toán tại EXP-05.
- **Seed Stability (Block S)**: K-Means, GMM, Fuzzy C-Means × 5 seed.
  Agglomerative và DBSCAN là deterministic (không có seed axis). Raw
  evidence có sẵn; ARI/AMI computation deferred to EPIC-08.
- **Perturbation Robustness (Block N)**: Cả 5 thuật toán × Gaussian
  feature perturbation (sigma = 0, 0.01, 0.05 × column std). Raw evidence
  có sẵn; ARI/AMI computation deferred to EPIC-08.
- **Stability Metrics**: ARI (Adjusted Rand Index), AMI (Adjusted
  Mutual Information), Hungarian cluster matching. Tính trong EPIC-08
  dùng `exp05_cluster_labels.parquet`.
- **Statistical Tests**: Paired t-test / Wilcoxon qua các seed và
  perturbation level. Chọn trong EPIC-08 plan.
- **Confidence Intervals**: Bootstrap hoặc percentile. Chọn trong
  EPIC-08 plan.

**Cái RQ3 KHÔNG bao trùm:**

- Business interpretation của cluster (thuộc EPIC-09).
- Customer profiling hoặc segment naming (thuộc EPIC-09).
- External validation với ground truth (không áp dụng; unsupervised).

**Evidence hỗ trợ RQ3:**

- EXP-05: tổng 75 run (Block R: 25, Block S: 15, Block N: 35). Labels
  artifact: 327,825 rows × 9 columns.

---

## Consequences

### Dễ hơn

- Cả ba research question giờ có định nghĩa chính thức, bằng văn bản.
- Evidence-to-RQ mapping là tường minh và auditable.
- EPIC-08 có thể tiến hành với evaluation criteria rõ ràng.
- Không còn mơ hồ về cái gì cấu thành câu trả lời "đầy đủ" cho mỗi RQ.

### Khó hơn hoặc rủi ro hơn

- RQ2 reformulation nghĩa là câu hỏi "RFM-only vs RFM Extended" ban
  đầu không được trả lời. Điều này phải được phát biểu rõ trong bất
  kỳ thesis hoặc publication nào.
- RQ2 được scope về preprocessing sensitivity trên RFM Extended — một
  câu hỏi hẹp hơn ý ban đầu ngụ ý.

## Alternatives Considered

### Option A cho RQ2: Materialize RFM-only

- **Estimated impact**: ~30–60 run mới + ~1–2 tuần.
- **Decision**: Bị reject cho phase hiện tại. Reformulated RQ2 trả lời
  được với evidence hiện có. Materialization RFM-only là future work.

### Option B cho RQ2: Chấp nhận PARTIAL status vô thời hạn

- **Decision**: Bị reject. Một trạng thái PARTIAL vô thời hạn tạo ra
  sự mơ hồ cho EPIC-08 và cho người đọc thesis/paper.

### Option C cho RQ2: Reformulate RQ2 (ĐÃ CHỌN)

- **Estimated impact**: Zero run mới. Chỉ cập nhật tài liệu.
- **Decision**: Được chấp nhận. Câu hỏi được reformulate phản ánh
  chính xác evidence hiện có đồng thời methodologically honest.

## Future Work

- RFM-only materialization và RFM-only vs RFM Extended comparison: xem
  `docs/research/review/RFM_ONLY_FUTURE_WORK_PLAN.md`.
- K-Medoids implementation: xem ADR-0003.

## References

- `docs/methodology/research_questions.md` — official RQ definitions.
- `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md` — analysis
  dẫn đến các quyết định này.
- `docs/research/review/METHODOLOGY_LOCK_STATUS.md` — resolution status.
- `docs/decisions/0003-algorithm-scope.md` — ADR-0003 (algorithm scope).
- EXP-01 đến EXP-05 reports trong `reports/exp01/` qua `reports/exp05/`.
