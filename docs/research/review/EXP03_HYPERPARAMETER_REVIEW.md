# EXP-03 Hyperparameter Sensitivity Review

> **Tài liệu review EXP-03 Hyperparameter Search.**
> EXP-03 selection protocol hiện tại là **WORKING_ASSUMPTION**, KHÔNG phải methodology đã được phê duyệt cuối cùng.
> KHÔNG gọi configuration nào là "best", "winner", "optimal", "final", "recommended".
> Tất cả quyết định nghiên cứu ở trạng thái `PENDING_HUMAN_REVIEW`.

---

## 1. Mục tiêu

Xác định **search space có căn cứ** cho từng clustering algorithm, khảo sát ảnh hưởng của hyperparameters, và xác định **working selected configuration** trong phạm vi **từng algorithm** dựa trên multi-metric evidence.

**QUAN TRỌNG:** "Working Selected Configuration" trong EXP-03 KHÔNG có nghĩa:
- best algorithm
- final optimal model
- final research selection
- winner
- recommendation giữa các thuật toán

Nó chỉ có nghĩa: trong search space của từng algorithm, configuration được chọn theo protocol đa tiêu chí đã document, status = `WORKING_SELECTED` (per-algorithm), chưa được cross-algorithm ranking.

---

## 2. Experimental design

### 2.1. Stages

| Stage | Nội dung | Per-algorithm |
|-------|----------|---------------|
| **A** | Baseline với EXP-01 working defaults | 1 run each |
| **B** | Single-parameter sensitivity sweeps | 3-6 runs each |
| **C** | Selected interactions (K from EXP-02 × parameter) | 3 runs each (selected algorithms) |

### 2.2. Primary criterion / Tiebreakers

| Position | Metric | Convention |
|----------|--------|------------|
| Primary criterion | Silhouette | Cao hơn = clusters compact và tách biệt tốt hơn |
| Tiebreaker 1 | Davies-Bouldin | Thấp hơn = compact hơn |
| Tiebreaker 2 | Calinski-Harabasz | Cao hơn = compact và tách biệt tốt hơn |
| Diagnostic only | WCSS | Quan sát elbow, KHÔNG dùng để rank |
| Diagnostic only | Runtime | KHÔNG dùng để rank |

**KHÔNG có composite score với trọng số tùy ý.** (AGENTS.md §2.6)

### 2.3. K reuse

- K candidates reused from EXP-02 (CONTROLLED_REUSE_OF_EXP02_EVIDENCE).
- KHÔNG re-sweep K = 2..10.
- EXP-02 candidates used in Stage C: K=3 (highest agreement score).

### 2.4. Inputs

| Field | Value |
|-------|-------|
| Dataset | `data/processed/final_clustering_dataset.parquet` |
| Input SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Dataset version | `FE06-v1.0` |
| Customer count | 4,371 |
| Feature count | 14 (RFM Extended) |
| Config SHA-256 | `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79` |

---

## 3. Search space per algorithm

### 3.1. K-Means

| Stage | N_run | Sweep |
|-------|-------|-------|
| A | 1 | Baseline: `init=k-means++, n_init=10, max_iter=300, tol=1e-4` |
| B | 6 | `init=random`; `n_init ∈ {1, 5, 20}`; `max_iter ∈ {100, 500}` |
| C | 3 | K=3 (EXP-02 candidate) × `n_init ∈ {1, 10, 20}` |

### 3.2. Agglomerative

| Stage | N_run | Sweep |
|-------|-------|-------|
| A | 1 | Baseline: `linkage=ward, metric=euclidean` |
| B | 3 | `linkage ∈ {complete, average, single}` |
| C | 3 | K=3 (EXP-02) × `linkage ∈ {ward, complete, average}` |

### 3.3. DBSCAN

| Stage | N_run | Sweep |
|-------|-------|-------|
| A | 1 | Baseline: `eps=0.5, min_samples=5, metric=euclidean` |
| B | 6 | `eps ∈ {0.3, 0.7, 1.0}`; `min_samples ∈ {3, 10, 15}` |

### 3.4. GMM

| Stage | N_run | Sweep |
|-------|-------|-------|
| A | 1 | Baseline: `covariance_type=full, init_params=kmeans, n_init=1` |
| B | 4 | `covariance_type ∈ {tied, diag, spherical}`; `init_params=random` |

### 3.5. Fuzzy C-Means

| Stage | N_run | Sweep |
|-------|-------|-------|
| A | 1 | Baseline: `m=2.0, max_iter=300, error=1e-4` |
| B | 5 | `m ∈ {1.5, 2.5, 3.0}`; `max_iter ∈ {100, 500}` |
| C | 3 | K=3 (EXP-02) × `m ∈ {1.5, 2.0, 2.5}` |

### 3.6. Tổng hợp runs

| Algorithm | Successful | Total | Success Rate |
|-----------|-----------|-------|-------------|
| kmeans | 10 | 10 | 100% |
| agglomerative | 7 | 7 | 100% |
| dbscan | 7 | 7 | 100% |
| gmm | 5 | 5 | 100% |
| fuzzy_cmeans | 9 | 9 | 100% |
| **Tổng** | **38** | **38** | **100%** |

---

## 4. Kết quả verified

### 4.1. Selected configurations (per-algorithm)

| Algorithm | Decision Status | Experiment ID | K | Silhouette | DBI | CH | WCSS |
|-----------|----------------|---------------|---|------------|-----|-----|------|
| kmeans | `TIED_WORKING_SELECTED` | EXP-03-kmeans-stageC-k3-n_init-1 | 3 | 0.6291 | 0.5881 | 5420.09 | 222674.94 |
| agglomerative | `WORKING_SELECTED` | EXP-03-agglomerative-stageC-k3-linkage-average | 3 | 0.8033 | 0.2714 | **77.15** | 748840.46 |
| dbscan | `WORKING_SELECTED` | EXP-03-dbscan-stageB-min_samples-10 | None | 0.1598 | 0.7687 | 54.22 | 1739.80 |
| gmm | `WORKING_SELECTED` | EXP-03-gmm-stageB-covariance_type-tied | 4 | 0.5702 | 0.6167 | 4481.99 | 190069.74 |
| fuzzy_cmeans | `WORKING_SELECTED` | EXP-03-fuzzy_cmeans-stageC-k3-m-1_5 | 3 | 0.6296 | 0.5869 | 5419.61 | 222689.21 |

### 4.2. Sensitivity evidence (selection)

### Agglomerative — linkage sweep (K=4)

| Linkage | Silhouette | DBI | CH | WCSS | Runtime (s) |
|---------|------------|-----|-----|------|--------------|
| ward (baseline) | 0.5657 | 0.7360 | 4578.83 | 187019.54 | 0.5230 |
| average | 0.6586 | 0.2623 | 54.25 | 747437.29 | 0.7743 |
| complete | 0.6105 | 0.4634 | 1183.51 | 427622.30 | 0.6478 |
| single | **0.8007** | **0.2501** | **47.90** | 750594.22 | 0.1285 |

Note: `single` linkage có CH thấp nhất (47.90) trong khi silhouette cao nhất (0.8007). Đây là **chaining artifact** của single-linkage.

### Agglomerative — Stage C (K=3, linkage variants)

| Linkage | Silhouette | DBI | CH | WCSS |
|---------|------------|-----|-----|------|
| ward | 0.5904 | 0.6388 | 5029.13 | 234744.25 |
| complete | 0.5972 | 0.6362 | 5081.40 | 232200.79 |
| **average** (SELECTED) | **0.8033** | 0.2714 | **77.15** | 748840.46 |

**Agglomerative selected (Stage C K=3 linkage=average):** silhouette=0.8033 (cao nhất search space) nhưng CH=77.15. CH các alternatives (ward, complete): 5029.13, 5081.40 → chênh lệch **~60×**.

### DBSCAN — eps sweep

| eps | Silhouette | DBI | CH | WCSS |
|-----|------------|-----|-----|------|
| 0.3 | -0.0209 | 0.7608 | 50.80 | 405.50 |
| 0.5 (baseline) | -0.1041 | 0.7721 | 49.18 | 2125.13 |
| 0.7 | -0.0619 | 1.1493 | 131.46 | 4149.20 |
| 1.0 | 0.1404 | 0.9823 | 223.84 | 7821.43 |

### DBSCAN — min_samples sweep

| min_samples | Silhouette | DBI | CH | WCSS |
|-------------|------------|-----|-----|------|
| 3 | -0.1713 | 0.9677 | 37.84 | 2355.54 |
| 5 (baseline) | -0.1041 | 0.7721 | 49.18 | 2125.13 |
| **10** (SELECTED) | **0.1598** | 0.7687 | 54.22 | 1739.80 |
| 15 | 0.1340 | 0.9109 | 17.78 | 1355.41 |

### GMM — covariance_type sweep

| covariance_type | Silhouette | DBI | CH | WCSS |
|-----------------|------------|-----|-----|------|
| full (baseline) | 0.1843 | 3.7486 | 131.73 | 710957.20 |
| diag | 0.1808 | 4.3673 | 118.20 | 717068.23 |
| spherical | 0.4699 | 0.7547 | 3430.69 | 230963.17 |
| **tied** (SELECTED) | **0.5702** | 0.6167 | 4481.99 | 190069.74 |

### GMM — init_params sweep

| init_params | Silhouette | DBI | CH | WCSS |
|-------------|------------|-----|-----|------|
| kmeans (baseline) | 0.1843 | 3.7486 | 131.73 | 710957.20 |
| random | 0.1642 | 3.9700 | 121.91 | 715382.83 |

### Fuzzy C-Means — m sweep

| m | Silhouette | DBI | CH | WCSS |
|---|------------|-----|-----|------|
| **1.5** | 0.5599 | 0.7140 | 4697.84 | 183402.62 |
| 2.0 (baseline) | 0.2691 | 1.3709 | 3869.05 | 211949.22 |
| 2.5 | 0.2471 | 1.5176 | 3794.95 | 214940.34 |
| 3.0 | 0.2378 | 1.5086 | 3777.22 | 215668.49 |

### Fuzzy C-Means — max_iter sweep

| max_iter | Silhouette | DBI | CH | WCSS |
|----------|------------|-----|-----|------|
| 100 | 0.2691 | 1.3709 | 3869.05 | 211949.22 |
| 300 (baseline) | 0.2691 | 1.3709 | 3869.05 | 211949.22 |
| 500 | 0.2691 | 1.3709 | 3869.05 | 211949.22 |

(max_iter không ảnh hưởng — convergence trước max_iter.)

### K-Means — n_init sweep

| n_init | Silhouette | DBI | CH | WCSS |
|--------|------------|-----|-----|------|
| 1 | 0.5681 | 0.6128 | 4819.08 | 179858.91 |
| 5 | 0.5681 | 0.6128 | 4819.08 | 179858.91 |
| 10 (baseline) | 0.5681 | 0.6128 | 4819.08 | 179858.91 |
| 20 | 0.5681 | 0.6128 | 4819.08 | 179858.91 |

(n_init không ảnh hưởng — K-Means deterministic với fixed seed.)

### K-Means — Stage C (K=3, n_init variants)

| n_init | Silhouette | DBI | CH | WCSS |
|--------|------------|-----|-----|------|
| **1** (tied selected) | 0.6291 | 0.5881 | 5420.09 | 222674.94 |
| 10 | 0.6291 | 0.5881 | 5420.09 | 222674.94 |
| 20 | 0.6291 | 0.5881 | 5420.09 | 222674.94 |

**K-Means Stage C là genuine 3-way tie** — silhouette/DBI/CH/WCSS identical đến 17 chữ số thập phân (do K-Means deterministic với fixed seed).

### Fuzzy C-Means — Stage C (K=3, m variants)

| m | Silhouette | DBI | CH | WCSS |
|---|------------|-----|-----|------|
| **1.5** (SELECTED) | **0.6296** | 0.5869 | 5419.61 | 222689.21 |
| 2.0 | 0.6271 | 0.5938 | 5413.69 | 222862.69 |
| 2.5 | 0.6206 | 0.6054 | 5384.25 | 224503.50 |

---

## 5. K-Means tie (EXP03-KM-01)

K-Means Stage C (K=3, n_init ∈ {1, 10, 20}) là **genuine 3-way tie** — silhouette/DBI/CH/WCSS đều numerically identical đến 17 chữ số thập phân.

**Lý do:** K-Means với fixed `random_state=42` deterministic → labels giống nhau across n_init; metrics không phụ thuộc `n_init`.

**Quyết định hiện tại (WORKING_ASSUMPTION):**
- Giữ status `TIED_WORKING_SELECTED` với 2 tied alternates (ghi trong `tied_alternates_count=2`).
- KHÔNG ép chọn một configuration duy nhất.
- Resolution thuộc EPIC-08.

---

## 6. Agglomerative average-linkage issue (EXP03-SEL-02)

Configuration được chọn cho Agglomerative (Stage C K=3 linkage=average):
- Silhouette = **0.8033** (cao nhất search space)
- CH = **77.15**
- Alternatives (ward, complete): CH = 5029.13, 5081.40 → chênh lệch **~60×**

**Phân tích:** Đây là **known chaining artifact** của average-linkage. Average-linkage với K=3 có thể merge các cluster "chuỗi" → CH giảm mạnh. Protocol silhouette-primary KHÔNG tự động surface disagreement này.

**Quyết định hiện tại (WORKING_ASSUMPTION):**
- Status **giữ là `WORKING_SELECTED`** theo EXP-03 protocol.
- **KHÔNG** được coi là "final validated configuration".
- EPIC-08 **PHẢI** thực hiện cross-metric evaluation và stability analysis trước khi bất kỳ kết luận nghiên cứu nào sử dụng configuration này.

---

## 7. Selection protocol hiện tại

### 7.1. Protocol hiện tại (silhouette-primary → DBI → CH)

| Position | Metric | Use case |
|----------|--------|----------|
| 1 | Silhouette | Primary criterion |
| 2 | DBI | Tiebreaker 1 |
| 3 | CH | Tiebreaker 2 |
| Diagnostic only | WCSS | Observe elbow |
| Diagnostic only | Runtime | No ranking |

### 7.2. Phân tích áp dụng protocol trên 5 algorithms

| Algorithm | Silhouette decision | Tiebreaker engage? | Outcome |
|-----------|---------------------|-------------------|---------|
| kmeans Stage C | 0.6291 (n_init=1) | Có, 3-way tie (tie-breaker không phân biệt được) | `TIED_WORKING_SELECTED` |
| agglomerative Stage C | 0.8033 (linkage=average) | Không (silhouette quyết định duy nhất) | `WORKING_SELECTED` (có CH disagreement) |
| dbscan Stage B | 0.1598 (min_samples=10) | Không | `WORKING_SELECTED` |
| gmm Stage B | 0.5702 (covariance_type=tied) | Không | `WORKING_SELECTED` |
| fuzzy_cmeans Stage C | 0.6296 (m=1.5) | Không | `WORKING_SELECTED` |

**Phát hiện:** 4/5 algorithms (agglomerative, dbscan, gmm, fuzzy_cmeans) silhouette quyết định duy nhất. 1/5 algorithms (K-Means Stage C) tiebreakers thực sự engage do genuine 3-way tie.

---

## 8. DBSCAN / GMM / FCM working selections

| Algorithm | Status | Note |
|-----------|--------|------|
| dbscan | `WORKING_SELECTED` | Stage B min_samples=10. eps=0.5 (không đổi). Noise ratio chưa được characterize rõ trong EXP-03. |
| gmm | `WORKING_SELECTED` | Stage B covariance_type=tied. K=4 (giữ EXP-01). |
| fuzzy_cmeans | `WORKING_SELECTED` | Stage C K=3 m=1.5. **CHÚ Ý:** m=1.5 tiệm cận hard K-Means (m=1 → K-Means) → fuzziness effect giảm. |

---

## 9. Các điểm đã verify

- ✅ 38/38 runs SUCCESS, tất cả metrics status = `VALID_VALUE`.
- ✅ Input SHA-256 unchanged.
- ✅ Per-algorithm selection theo protocol.
- ✅ Reuse EXP-02 K candidates (không re-sweep K).
- ✅ Agglomerative disagreement ghi nhận trong `pending_review_notes` (EXP03-SEL-02).
- ✅ K-Means tie ghi nhận trong `pending_review_notes` (EXP03-KM-01).
- ✅ 41/41 EXP-03 unit tests pass; 1004/1004 full regression pass (ghi trong analysis.md).

---

## 10. Limitations

- **Search space per-algorithm** là WORKING_ASSUMPTION (`EXP03-SP-01`). Chưa có căn cứ formal cho việc chọn các giá trị sweep.
- **Selection protocol** (silhouette-primary → DBI → CH) là WORKING_ASSUMPTION (`EXP03-SEL-01`). Chưa được validate cross-algorithm.
- **Agglomerative Stage C** có CH=77.15 ~60× thấp hơn alternatives → protocol silhouette-primary KHÔNG surface disagreement.
- **K-Means Stage C tie** không thể resolve bằng metrics → cần EPIC-08 stability evidence.
- **RFM-only feature set** chưa có → EXP-03 chỉ chạy trên RFM Extended.
- **Selected interactions** (Stage C) chỉ là small curated subset của K × parameter combinations — chưa phải full grid.
- **No composite scoring**, no cross-algorithm ranking, no rerun EXP-03 sau review.

---

## 11. Pending research decisions

| ID | Decision / Question | Status |
|----|---------------------|--------|
| EXP03-SP-01 | Per-algorithm search space (candidate values) | WORKING_ASSUMPTION |
| EXP03-FS-01 | RFM-only feature set NOT present; EXP-03 runs on RFM Extended only | PENDING_REVIEW (FE-06 ADR needed) |
| EXP03-K-01 | K candidates reused from EXP-02 (controlled reuse of EXP-02 evidence); NOT re-swept | TECHNICALLY_IMPLEMENTED |
| EXP03-INT-01 | Selected interactions là small curated subset | TECHNICALLY_IMPLEMENTED |
| EXP03-SEL-01 | Selection protocol: silhouette (primary) → DBI → CH | WORKING_ASSUMPTION |
| EXP03-SEL-02 | Agglomerative Stage C K=3 linkage=average — known chaining artifact; status `WORKING_SELECTED` per protocol nhưng KHÔNG final validated | TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING |
| EXP03-KM-01 | K-Means Stage C 3-way tie — status `TIED_WORKING_SELECTED`; KHÔNG ép chọn 1 config | TECHNICALLY_IMPLEMENTED_WITH_RESEARCH_DECISIONS_PENDING |
| EXP03-METRIC-01 | Metric status semantics mirror EXP-01 | TECHNICALLY_IMPLEMENTED |
| EXP03-REPRO-01 | Same seed across repetitions; NOT stability analysis | TECHNICALLY_IMPLEMENTED |

---

## 12. Các điểm methodology chưa được final hóa

1. **Selection protocol** (silhouette-primary → DBI → CH) chưa được finalize.
2. **Agglomerative disagreement** (silhouette vs CH) chưa được finalize cách xử lý.
3. **K-Means tie** resolution thuộc EPIC-08.
4. **Search space per-algorithm** chưa có căn cứ formal.
5. **Stage C selected interactions** chưa được mở rộng thành full grid.

---

## 13. Câu hỏi cần Mentor quyết định

1. Selection protocol (silhouette-primary → DBI → CH) có được accept như working methodology không?
2. Agglomerative disagreement (Stage C K=3 linkage=average, CH=77.15) có cần protocol adjustment để surface cross-metric disagreement không?
3. K-Means 3-way tie có cần thêm tiebreaker (vd. runtime, WCSS, stability) hay giữ status quo?
4. Search space per-algorithm có đủ không, hay cần mở rộng / thu hẹp?
5. Fuzzy C-Means m=1.5 (tiệm cận hard K-Means) có được chấp nhận như working selection, hay cần ràng buộc m ≥ 2.0?
6. DBSCAN selection (min_samples=10, eps=0.5) có cần kèm noise ratio characterization riêng không?
7. EXP-03 working selections có cần được cross-validate trong EPIC-08 stability analysis trước khi được coi là final không?

---

## Provenance

Mọi số liệu trong tài liệu này lấy từ:
- `reports/exp03/exp03_hyperparameter_analysis.md`
- `reports/exp03/exp03_hyperparameter_results.csv`
- `reports/exp03/exp03_parameter_sensitivity.csv`
- `reports/exp03/exp03_selected_configurations.csv`
- `reports/exp03/exp03_manifest.json`

---

**REVIEW_STATUS: PENDING_HUMAN_REVIEW**
