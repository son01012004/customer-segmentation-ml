# EXP-04 Preprocessing & Feature Set Sensitivity Review

> **Tài liệu review EXP-04.**
> EXP-04 hiện đánh giá **preprocessing sensitivity** (Family B) trên RFM Extended feature set.
> Family A (Feature Set Sensitivity) bị **DEFERRED** vì RFM-only artifact chưa tồn tại.
> KHÔNG tự tạo RFM-only dataset. KHÔNG gọi scenario nào là "best/optimal/superior/winner/recommended/final".
> Tất cả quyết định nghiên cứu ở trạng thái `PENDING_HUMAN_REVIEW`.

---

## 1. Mục tiêu

EXP-04 đánh giá có kiểm soát ảnh hưởng của **preprocessing configuration** (transformation × scaling) đến clustering quality trên RFM Extended feature set.

EXP-04 gồm 2 family:

| Family | Nội dung | Status |
|--------|----------|--------|
| **Family A** | Feature Set Sensitivity (RFM only vs RFM Extended) | **DEFERRED** |
| **Family B** | Preprocessing Sensitivity (transformation × scaling) trên RFM Extended | EXECUTED |

**Quan trọng:** EXP-04-v1 hiện đánh giá preprocessing sensitivity, nhưng **chưa thể hoàn thành feature-set sensitivity** (vì RFM-only artifact chưa tồn tại).

---

## 2. Family A — Feature Set Sensitivity (DEFERRED)

| Field | Value |
|-------|-------|
| Status | **DEFERRED** |
| Deferred reason | RFM-only clustering-ready dataset does not exist in the repository. EXP-04 does NOT create an RFM-only ad-hoc dataset. |
| Owner | FE-06 |
| Scenarios blocked | EXP04-FA-RFM |
| RQ2 completeness | **PARTIAL** — preprocessing sensitivity completed; feature set sensitivity pending FE-06 |

**Lưu ý:** EXP-04 KHÔNG tạo RFM-only dataset ad-hoc. Việc materialize RFM-only thuộc FE-06 (cần ADR).

### RQ2 dimension

- Câu hỏi nghiên cứu RQ2 (feature representation: RFM-only vs RFM Extended) chỉ được trả lời PARTIAL.
- Cần materialize RFM-only artifact (FE-06 ADR) → EXP-04 Family A mới có thể execute.
- Cho đến khi đó, mọi evidence về feature representation chỉ giới hạn ở RFM Extended.

---

## 3. Family B — Preprocessing Sensitivity (EXECUTED)

### 3.1. Controls cố định (controlled references)

| Variable | Value | Tag |
|----------|-------|-----|
| Algorithm | `kmeans` | CONTROLLED_REFERENCE_ALGORITHM |
| K | `4` | CONTROLLED_REFERENCE_K |
| Imputation | `median` (FE-06 C7 fitted values) | CONTROLLED_REFERENCE_IMPUTATION |
| Seed | `42` | CONTROLLED_VARIABLE |
| n_repeat | `5` | REPRODUCIBILITY_VERIFICATION |

**Lưu ý quan trọng:**
- EXP-04 **KHÔNG** chạy stability analysis. Cùng seed → cùng labels_hash và cùng metric values; chỉ wall-clock runtime có thể thay đổi.
- `n_repeat=5` = REPRODUCIBILITY_VERIFICATION (cùng seed → identical labels), KHÔNG phải stability.
- EXP-04 KHÔNG dùng EXP-03 working / selected configurations (đã ghi trong scope_boundaries).

### 3.2. Scenario matrix

EXP-04 thực thi **6 full-matrix scenarios** (C0, C1, C2, C3, C6, C7; C4 và C5 không nằm trong scope).

| Scenario ID | Config ID | Transformation | Scaling | Role |
|-------------|-----------|----------------|---------|------|
| EXP04-S01 | C0 | `none` | `none` | NO_TRANSFORM_NO_SCALING_REFERENCE |
| EXP04-S02 | C1 | `none` | `standard` | PREPROCESSING_CANDIDATE_SCENARIO |
| EXP04-S03 | C2 | `none` | `minmax` | PREPROCESSING_CANDIDATE_SCENARIO |
| EXP04-S04 | C3 | `none` | `robust` | PREPROCESSING_CANDIDATE_SCENARIO |
| EXP04-S05 | C6 | `yeo_johnson` | `standard` | PREPROCESSING_CANDIDATE_SCENARIO |
| EXP04-S06 | C7 | `yeo_johnson` | `robust` | **FE06_WORKING_CONFIGURATION_REFERENCE** |

### 3.3. Runs count

- 6 scenarios × 5 repeats = **30 runs**.
- All runs SUCCESS, all deterministic.

### 3.4. Inputs

| Field | Value |
|-------|-------|
| Dataset | `data/processed/customer_candidates.parquet` (FE-05 output, pre-transform) |
| Input SHA-256 | `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649` |
| Customer metadata | `data/processed/customer_metadata.parquet`, SHA `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` |
| Dataset version | `FE06-v1.0` |
| Customer count | 4,371 |
| Config SHA-256 | `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79` |

**Lưu ý:** EXP-04 input SHA khác với EXP-01/02/03/05 (`ba54033e4552...`). Đây là **by design**:
- EXP-01/02/03/05 dùng `final_clustering_dataset.parquet` (FE-06 output, post-transform).
- EXP-04 dùng `customer_candidates.parquet` (FE-05 output, pre-transform) vì EXP-04 cần **kiểm soát** transformation + scaling trong scenario matrix.

EXP-04 tự áp dụng median imputation + transformation + scaling trên input pre-transform.

---

## 4. Kết quả aggregate

| Scenario | Silhouette | DBI | CH | WCSS | Runtime mean (s) | Runtime std (s) | Determinism | Decision |
|----------|------------|-----|-----|------|-------------------|-----------------|-------------|----------|
| EXP04-S01 (C0 none/none) | 0.9465 | 0.5279 | 9269.75 | 53,142,107,014.92 | 0.2258 | 0.2696 | True | CANDIDATE_SCENARIO |
| EXP04-S02 (C1 none/standard) | 0.2535 | 1.3655 | 793.39 | 39,606.94 | 0.5111 | 0.6995 | True | CANDIDATE_SCENARIO |
| EXP04-S03 (C2 none/minmax) | 0.3897 | 0.8738 | 2617.39 | 488.72 | 0.0280 | 0.0020 | True | CANDIDATE_SCENARIO |
| EXP04-S04 (C3 none/robust) | 0.6325 | 0.5586 | 3842.00 | 450,719.05 | 0.0321 | 0.0054 | True | CANDIDATE_SCENARIO |
| EXP04-S05 (C6 yeo_johnson/standard) | 0.2634 | 1.3678 | 1074.05 | 35,212.61 | 0.0625 | 0.0326 | True | CANDIDATE_SCENARIO |
| EXP04-S06 (C7 yeo_johnson/robust) | 0.5681 | 0.6128 | 4819.08 | 179,858.91 | 0.0469 | 0.0202 | True | CANDIDATE_SCENARIO |

**Quan sát:**
- EXP04-S06 (C7, FE06_WORKING_CONFIGURATION_REFERENCE) silhouette=0.5681, DBI=0.6128, CH=4819.08 — **giống hệt** EXP-01 K-Means baseline (vì C7 = FE-06 working configuration). Đây là expected cross-reference, không phải bug.
- EXP04-S01 (no transform, no scaling) có WCSS rất lớn (53 tỷ) — đây là pre-imputation/pre-scaling data nên WCSS ở raw scale, không so sánh được trực tiếp với các scenario khác.
- Silhouette C0 = 0.9465 rất cao — nhưng C0 dùng raw data (no scaling) → Euclidean distance bị dominated bởi feature có variance lớn, có thể không phản ánh cluster quality thực.

### 4.1. Determinism verification

| Field | Value |
|-------|-------|
| Deterministic scenarios | 6 / 6 |
| Non-deterministic scenarios | 0 / 6 |
| Deterministic per-repeat records | 30 / 30 |

Tất cả scenarios deterministic (cùng seed → cùng labels_hash). Đây là expected behavior — EXP-04 là **REPRODUCIBILITY_VERIFICATION**, không phải stability analysis.

---

## 5. Decision status taxonomy (EXP-04)

### Allowed labels (chỉ những label này):

| Label | Ý nghĩa |
|-------|---------|
| `CANDIDATE_SCENARIO` | Successful deterministic run |
| `TIED_SCENARIOS` | Nhiều scenarios có metric aligned (ghi evidence) |
| `PENDING_REVIEW` | Không đủ evidence / metrics disagreement / determinism fail |
| `DEFERRED` | Dành cho Family A (chưa execute) |

### Forbidden labels (AGENTS.md §2.5):

`BEST`, `OPTIMAL`, `WINNER`, `SUPERIOR`, `RECOMMENDED`, `FINAL`.

---

## 6. Các điểm đã verify

- ✅ 30/30 per-repeat records SUCCESS, 6/6 aggregates deterministic.
- ✅ Input SHA-256 unchanged pre/post run.
- ✅ Customer metadata SHA-256 unchanged.
- ✅ Framework config SHA-256 recorded.
- ✅ Library versions recorded.
- ✅ FE-05 / FE-06 outputs READ-ONLY (SHA verified).
- ✅ Family A ghi nhận DEFERRED với evidence + owner (FE-06).
- ✅ K-Means là CONTROLLED_REFERENCE_ALGORITHM (giống EXP-01 baseline).
- ✅ K=4 là CONTROLLED_REFERENCE_K (giống EXP-01 baseline).
- ✅ EXP-04 KHÔNG dùng EXP-03 working configurations.
- ✅ EXP-04 KHÔNG rerun K-sweep.

---

## 7. Limitations

1. **Family A DEFERRED** — RQ2 (feature representation) PARTIAL.
2. **EXP-04 chỉ dùng K-Means** — không có controlled comparison across algorithms.
3. **EXP-04 chỉ K=4** — không có K-sweep (đó là EXP-02).
4. **EXP-04 KHÔNG phải stability analysis** — chỉ reproducibility verification. Stability = EXP-05 / EPIC-08.
5. **log1p NOT included** — không full-matrix comparable (PENDING_REVIEW `EXP04-TR-01`).
6. **Median imputation** dùng FE-06 C7 fitted values — không có alternative imputation strategy tested.
7. **WCSS observed ở các scale khác nhau** (C0 raw scale vs C7 standardized) — không so sánh trực tiếp WCSS giữa scenarios.
8. **C0 (NO_TRANSFORM_NO_SCALING_REFERENCE)** silhouette rất cao (0.9465) nhưng có thể là artifact của un-standardized data dominating distance.

---

## 8. RQ2 completeness (PARTIAL)

| Dimension | Status |
|-----------|--------|
| Preprocessing sensitivity (Family B) | ✅ COMPLETED |
| Feature set sensitivity (Family A) | ❌ DEFERRED |

Cần Mentor review về:

1. Có nên materialize RFM-only artifact (FE-06 ADR) để EXP-04 Family A có thể execute?
2. Nếu RFM-only materialized, EXP-04 Family A nên dùng K nào (mirror K=4 CONTROLLED_REFERENCE_K hay dùng K candidates từ EXP-02)?
3. EXP-04 hiện tại có đủ evidence để EPIC-08 đánh giá preprocessing sensitivity không, hay cần execute Family A trước?

---

## 9. Pending research decisions (EXP-04)

| ID | Decision / Question | Status |
|----|---------------------|--------|
| EXP04-FS-01 | RFM-only dataset does not exist → Family A DEFERRED | DEFERRED / PENDING_FE06_MATERIALIZATION |
| EXP04-FS-02 | FE-06 ADR for RFM-only materialization | PENDING_REVIEW |
| EXP04-FS-03 | EXP-04-v1 does not claim RQ2 completeness for feature representation | PENDING_REVIEW |
| EXP04-ALG-01 | K-Means only as CONTROLLED_REFERENCE_ALGORITHM | PENDING_REVIEW |
| EXP04-K-01 | K=4 (CONTROLLED_REFERENCE_K); no K-sweep | PENDING_REVIEW |
| EXP04-IMP-01 | Median imputation with FE-06 C7 fitted values | PENDING_REVIEW |
| EXP04-TR-01 | log1p NOT included (not full-matrix comparable) | PENDING_REVIEW |
| EXP04-CONCL-01 | Decision status taxonomy: CANDIDATE_SCENARIO / TIED_SCENARIOS / PENDING_REVIEW / DEFERRED | PENDING_REVIEW |

---

## 10. Câu hỏi cần Mentor review

1. Family A có nên execute không? Nếu có, cần FE-06 ADR materialize RFM-only artifact trước.
2. K-Means only (CONTROLLED_REFERENCE_ALGORITHM) có phù hợp cho Family B không, hay cần thêm Agglomerative + GMM + FCM?
3. K=4 (CONTROLLED_REFERENCE_K) có phù hợp không, hay cần test thêm K ∈ {3, 5, 6}?
4. Median imputation với FE-06 C7 fitted values có đúng methodology không?
5. log1p có nên được thêm vào scenario matrix (vd. scenario C4/C5) để full-matrix comparable?
6. C0 silhouette=0.9465 có cần được giải thích rõ hơn (raw data artifact), hay giữ nguyên description hiện tại?
7. C7 (FE06_WORKING_CONFIGURATION_REFERENCE) có đang được dùng đúng cách như reference không?
8. Decision status taxonomy (CANDIDATE_SCENARIO / TIED_SCENARIOS / PENDING_REVIEW / DEFERRED) có phù hợp cho EPIC-08 không?
9. EXP-04 controlled references có nên được dùng cho EPIC-08 stability analysis không?

---

## Provenance

Mọi số liệu trong tài liệu này lấy từ:
- `reports/exp04/exp04_analysis.md`
- `reports/exp04/exp04_scenario_results.csv`
- `reports/exp04/exp04_preprocessing_sensitivity.csv`
- `reports/exp04/exp04_manifest.json`
- `reports/exp04/exp04_pending_review.json`
- `reports/exp04/exp04_deferred.json`
- `configs/exp04_preprocessing_feature_set.yaml`

---

**REVIEW_STATUS: PENDING_HUMAN_REVIEW**
