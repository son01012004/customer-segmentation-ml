# EXP-05 Reproducibility & Stability-Related Diagnostics Review

> **Tài liệu review EXP-05.**
> EXP-05 chỉ generate **raw evidence**, KHÔNG phải stability analysis.
> Phân biệt rõ: REPRODUCIBILITY vs STABILITY vs ROBUSTNESS.
> KHÔNG nói EXP-05 đã hoàn thành toàn bộ stability methodology của EPIC-08.
> Tất cả quyết định nghiên cứu ở trạng thái `PENDING_HUMAN_REVIEW`.

---

## 1. Mục tiêu

EXP-05 sinh ra **raw evidence** (không phải analysis) cho 3 khối thực nghiệm độc lập:

- **Block R — Reproducibility**: 5 thuật toán × n_repeat=5 × seed=42. Verify determinism.
- **Block S — Random Seed Stability**: K-Means + GMM + FCM × 5 seeds. Fixed hyperparameters.
- **Block N — Feature Perturbation**: in-memory Gaussian noise; sigma = [0, 0.01, 0.05] × std.

EXP-05 xuất raw labels artifact (`exp05_cluster_labels.parquet`) — **REQUIRED** cho EPIC-08 tính ARI/AMI / Hungarian matching / statistical tests / CI.

**Quan trọng:** EXP-05 KHÔNG phải stability analysis. ARI/AMI / Hungarian / statistical tests / confidence intervals thuộc **EPIC-08**.

---

## 2. Phân biệt rõ 3 khái niệm

| Concept | Định nghĩa | EXP-05 thực hiện? |
|---------|------------|---------------------|
| **REPRODUCIBILITY** | Cùng seed + cùng config + cùng input → cùng output | ✅ **Block R** verifies điều này (same seed → identical labels_hash) |
| **STABILITY** | Across different seeds → labels có ARI/AMI ≥ threshold | ⚠️ **Block S** generates raw evidence; EPIC-08 computes ARI/AMI |
| **ROBUSTNESS** | Input perturbed (noise) → labels có ổn định không | ⚠️ **Block N** generates raw evidence; EPIC-08 analyzes |

**EXP-05 chỉ generate evidence; KHÔNG tự compute ARI/AMI / statistical tests / confidence intervals.**

---

## 3. Inputs

| Field | Value |
|-------|-------|
| Dataset | `data/processed/final_clustering_dataset.parquet` |
| Input SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Dataset version | `FE06-v1.0` |
| Customer metadata | `data/processed/customer_metadata.parquet`, SHA `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` |
| Customer count | 4,371 |
| Feature count | 14 (RFM Extended) |
| Framework config SHA | `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79` |
| EXP-05 config SHA | `3dec62060a5a6d1c09443debc51802f6f321e91f7dbbd792962e9b519afcda9e` |

Pre/post SHA check: input SHA unchanged. FE-06 output KHÔNG bị mutate.

---

## 4. Block R — Reproducibility

### 4.1. Đặc tả

| Parameter | Value |
|-----------|-------|
| Algorithms | kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans |
| Hyperparameters | EXP-01 working defaults |
| Seed | 42 (fixed) |
| n_repeat | 5 |
| Total runs | 5 × 5 = **25** |

### 4.2. Kết quả

| Algorithm | n_repeat | n_successful | labels_hash_unique | n_clusters_unique | Decision |
|-----------|----------|--------------|--------------------|-------------------|----------|
| kmeans | 5 | 5 | 1 | 1 | `REPRODUCIBILITY_VERIFIED` |
| agglomerative | 5 | 5 | 1 | 1 | `REPRODUCIBILITY_VERIFIED` |
| dbscan | 5 | 5 | 1 | 1 | `REPRODUCIBILITY_VERIFIED` |
| gmm | 5 | 5 | 1 | 1 | `REPRODUCIBILITY_VERIFIED` |
| fuzzy_cmeans | 5 | 5 | 1 | 1 | `REPRODUCIBILITY_VERIFIED` |

**Tất cả 5 algorithms reproducible** với seed=42 + EXP-01 working defaults.

### 4.3. Mean metrics across n_repeat (selected)

| Algorithm | Silhouette mean | Silhouette std | Runtime mean (s) |
|-----------|-----------------|----------------|------------------|
| kmeans | 0.5681 | 0.0 | 0.2321 |
| agglomerative | 0.5657 | 0.0 | 0.7806 |
| dbscan | -0.1041 | 0.0 | 0.1110 |
| gmm | 0.1843 | 0.0 | 0.3908 |
| fuzzy_cmeans | 0.2691 | 0.0 | 0.0720 |

Silhouette std = 0.0 cho tất cả algorithms → cùng labels → cùng metrics.

---

## 5. Block S — Random Seed Stability (evidence only)

### 5.1. Đặc tả

| Parameter | Value |
|-----------|-------|
| Algorithms | kmeans, gmm, fuzzy_cmeans (3 algorithms có random axis) |
| Agglomerative | KHÔNG seed sweep (deterministic trong n_clusters mode) |
| DBSCAN | KHÔNG seed sweep (deterministic) |
| Hyperparameters | EXP-01 working defaults (fixed) |
| Seeds | [42, 7, 123, 2024, 1729] |
| n_repeat per seed | 1 |
| Total runs | 3 × 5 = **15** |

### 5.2. Kết quả

| Algorithm | n_seeds | labels_hash_unique | n_clusters_unique | Decision |
|-----------|---------|--------------------|-------------------|----------|
| kmeans | 5 | 5 | 1 | `STABILITY_EVIDENCE_GENERATED` |
| gmm | 5 | 5 | 1 | `STABILITY_EVIDENCE_GENERATED` |
| fuzzy_cmeans | 5 | 5 | 1 | `STABILITY_EVIDENCE_GENERATED` |

**Quan sát:** K-Means, GMM, FCM có **5 unique labels_hash** across 5 seeds → labels phụ thuộc vào seed. Đây là **expected evidence**, không phải failure.

**EPIC-08 sẽ tính ARI/AMI** across these seeds để quantify stability.

### 5.3. Phân biệt với EXP-01

- EXP-01 chạy 1 seed (42) × n_repeat=5 — runtime variance + determinism verification.
- EXP-05 Block S chạy 5 seeds × n_repeat=1 — seed-axis evidence cho EPIC-08.

---

## 6. Block N — Feature Perturbation (evidence only)

### 6.1. Đặc tả

| Parameter | Value |
|-----------|-------|
| Algorithms | kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans |
| Hyperparameters | EXP-01 working defaults |
| sigma_grid | [0.0, 0.01, 0.05] (× feature std) |
| sigma=0 | 1 sanity run per algorithm (đối chiếu EXP-01) |
| sigma=0.01, 0.05 | 3 perturbation seeds [42, 43, 44] |
| n_repeat per (sigma, perturbation_seed) | 1 |
| Total runs | 5 + 5 × 2 × 3 = 5 + 30 = **35** |

### 6.2. Perturbation semantics

```
rng = np.random.default_rng(seed=perturbation_seed)
noise = rng.normal(loc=0.0, scale=1.0, size=X.shape)
X_perturbed = X + sigma * noise * feature_std
```

Trong đó `feature_std` = column-wise std của `X` (FE-06 final clustering matrix). sigma=0.01 = 1% noise × std; sigma=0.05 = 5% noise × std.

### 6.3. Constraints

- Perturbation **in-memory only**. KHÔNG persist perturbed dataset ra disk.
- KHÔNG assert labels phải thay đổi với sigma=1% hoặc 5%. Việc labels thay đổi hay không là **kết quả thực nghiệm**.
- `sigma=0` là sanity check: phải reproduce EXP-01 baseline (cluster_labels identical ở library version hiện tại).
- Verify input FE-06 SHA unchanged (pre/post).

### 6.4. Kết quả

| Algorithm | sigma | n_seeds | labels_hash_unique | n_clusters_unique | sigma_zero_match | Decision |
|-----------|-------|---------|--------------------|-------------------|------------------|----------|
| kmeans | 0.0 | 1 | 1 | 1 | True | `SIGMA_ZERO_BASELINE_MATCH` |
| kmeans | 0.01 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| kmeans | 0.05 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| agglomerative | 0.0 | 1 | 1 | 1 | True | `SIGMA_ZERO_BASELINE_MATCH` |
| agglomerative | 0.01 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| agglomerative | 0.05 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| **dbscan** | 0.0 | 1 | 1 | 1 | True | `SIGMA_ZERO_BASELINE_MATCH` |
| **dbscan** | **0.01** | 3 | **3** | **3** | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| **dbscan** | **0.05** | 3 | **3** | **2** | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| gmm | 0.0 | 1 | 1 | 1 | True | `SIGMA_ZERO_BASELINE_MATCH` |
| gmm | 0.01 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| gmm | 0.05 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| fuzzy_cmeans | 0.0 | 1 | 1 | 1 | True | `SIGMA_ZERO_BASELINE_MATCH` |
| fuzzy_cmeans | 0.01 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |
| fuzzy_cmeans | 0.05 | 3 | 3 | 1 | N/A | `PERTURBATION_EVIDENCE_GENERATED` |

**Quan sát DBSCAN:** `n_clusters_unique=3` (sigma=0.01) và `n_clusters_unique=2` (sigma=0.05) — DBSCAN có **số cluster thay đổi theo perturbation**. Đây là expected behavior của density-based clustering. EPIC-08 sẽ phân tích.

**Quan sát K-Means, Agglomerative, GMM, FCM:** n_clusters unique = 1 across perturbation seeds (nhưng labels_hash unique = 3) → labels **thay đổi** nhưng số cluster **giữ nguyên**. EPIC-08 sẽ phân tích ARI.

**Tất cả sigma=0 sanity check pass** (`sigma_zero_match=True`) → EXP-05 reproduce EXP-01 baseline correctly.

---

## 7. Labels Artifact — `exp05_cluster_labels.parquet`

### 7.1. Schema (REQUIRED)

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | str | Unique identifier per (block, algo, seed, sigma, pseed, repeat_index) |
| `block` | str | "R" / "S" / "N" |
| `algorithm` | str | algorithm name |
| `seed` | int64 | random seed for algorithm |
| `sigma` | float64 | None for R/S; float for N |
| `perturbation_seed` | float64 | None for R/S; int for N |
| `repeat_index` | int64 | 0..4 for R; 0 for S/N |
| `CustomerID` | int64 | From FE-06 customer_metadata |
| `cluster_label` | int64 | Hard label (argmax for GMM/FCM, raw for others) |

### 7.2. Kích thước

- Tổng rows: **327,825**
- = 4371 customers × 75 runs

### 7.3. CustomerID alignment

- CustomerID lấy từ FE-06 customer_metadata.
- Validate alignment qua `validate_customer_alignment` (EPIC-06 framework).

### 7.4. Why a separate label artifact?

EPIC-08 cần raw labels để:

- Tính ARI/AMI across seeds (Block S).
- Hungarian matching (Block N).
- Statistical tests (Block S vs Block N).
- Confidence intervals.

`labels_hash` chỉ cho biết labels identical hay khác, không cho biết cách chúng khác nhau thế nào. EPIC-08 cần label-level data.

---

## 8. Cluster size consistency

`exp05_cluster_size_consistency.csv` cung cấp cross-block cluster size distribution snapshot.

**Quan sát (từ CSV):**
- K-Means ở EXP-01 baseline (4 clusters): cluster sizes = {555, 3021, 571, 224}.
- Cùng cluster sizes across 5 repeats (Block R) → reproducibility verified.
- Cùng cluster sizes across EXP-01 baseline và EXP-05 Block R → consistency check.

Cluster size consistency cross-block (Block S vs Block N) chưa được phân tích sâu; thuộc EPIC-08.

---

## 9. Tổng hợp runs

| Block | Records | Successful | Failed | Aggregates |
|-------|---------|------------|--------|------------|
| R (Reproducibility) | 25 | 25 | 0 | 5 |
| S (Seed stability) | 15 | 15 | 0 | 3 |
| N (Perturbation) | 35 | 35 | 0 | 15 |
| **Tổng** | **75** | **75** | **0** | **23** |

---

## 10. Decision status taxonomy (EXP-05)

### Allowed labels:

- `REPRODUCIBILITY_VERIFIED` / `REPRODUCIBILITY_FAILED`
- `STABILITY_EVIDENCE_GENERATED`
- `PERTURBATION_EVIDENCE_GENERATED`
- `SIGMA_ZERO_BASELINE_MATCH` / `SIGMA_ZERO_BASELINE_MISMATCH`
- `PENDING_REVIEW`

### Forbidden (AGENTS.md §2.5):

`BEST`, `OPTIMAL`, `WINNER`, `SUPERIOR`, `RECOMMENDED`, `FINAL`.

---

## 11. EPIC-08 boundary (cumulative)

EXP-05 chỉ generate evidence. EPIC-08 owns:

- ARI / AMI computation (across Block S seeds; across Block N perturbation seeds).
- Hungarian matching.
- Statistical tests (across seeds / perturbation).
- Confidence intervals.
- Cross-algorithm stability analysis.
- "Most stable algorithm" / "best stability" claims (nếu có).

---

## 12. EXP-05 chứng minh được / CHƯA chứng minh được

### 12.1. EXP-05 CHỨNG MINH ĐƯỢC

1. ✅ **Reproducibility**: 5 algorithms reproducible với seed=42 + EXP-01 working defaults (Block R).
2. ✅ **Seed sensitivity exists**: K-Means, GMM, FCM cho labels khác nhau across 5 seeds (Block S — evidence, not analysis).
3. ✅ **Perturbation sensitivity exists**: labels_hash thay đổi với sigma=1% và 5% (Block N — evidence).
4. ✅ **Baseline reproduction**: sigma=0 reproduce EXP-01 baseline (sanity check pass).
5. ✅ **Input integrity**: FE-06 input SHA unchanged pre/post.
6. ✅ **DBSCAN n_clusters varies with perturbation** (evidence).

### 12.2. EXP-05 CHƯA chứng minh được

1. ❌ **Stability analysis ARI/AMI values**: chưa compute (EPIC-08 owns).
2. ❌ **Hungarian matching**: chưa compute (EPIC-08 owns).
3. ❌ **Statistical tests across seeds/perturbation**: chưa compute (EPIC-08 owns).
4. ❌ **Confidence intervals**: chưa compute (EPIC-08 owns).
5. ❌ **Cross-algorithm stability comparison**: chưa thực hiện (EPIC-08 owns).
6. ❌ **"Most stable algorithm" claim**: chưa thể đưa ra (cần EPIC-08 analysis).
7. ❌ **Robustness quantification**: chỉ có evidence về labels_hash uniqueness; cần ARI quantification.
8. ❌ **Stability across hyperparameters** (EXP-03 working selections): chưa test. EXP-05 dùng EXP-01 working defaults.

---

## 13. Limitations

1. **EXP-05 chỉ dùng EXP-01 working defaults** — chưa test EXP-03 working selections.
2. **Block S seeds [42, 7, 123, 2024, 1729]** — WORKING_ASSUMPTION. Chưa có căn cứ formal.
3. **Block N sigma_grid [0, 0.01, 0.05]** — WORKING_ASSUMPTION.
4. **Perturbation distribution = Gaussian** — WORKING_ASSUMPTION. Chưa test alternative distributions.
5. **5 seeds trong Block S** — có thể không đủ cho statistical power; EPIC-08 cần quyết định.
6. **3 perturbation seeds trong Block N** — có thể không đủ cho statistical power.
7. **Agglomerative + DBSCAN KHÔNG trong Block S** — dựa trên assumption rằng chúng deterministic với fixed hyperparameters; cần verify thêm.
8. **75 runs × 4371 customers = 327825 rows** — file size 663KB. Manageable.
9. **RFM-only chưa có** — Block R/S/N chỉ chạy trên RFM Extended. Nếu RFM-only materialized, cần rerun EXP-05.

---

## 14. Pending research decisions (EXP-05)

| ID | Decision / Question | Status |
|----|---------------------|--------|
| EXP05-BLK-01 | Block R = reproducibility verification, NOT stability analysis | WORKING_ASSUMPTION |
| EXP05-BLK-02 | Block S chỉ cho 3 algorithms có random axis (K-Means + GMM + FCM) | WORKING_ASSUMPTION |
| EXP05-BLK-03 | Block N = in-memory perturbation; sigma=[0, 0.01, 0.05]×std | WORKING_ASSUMPTION |
| EXP05-SEED-01 | Seeds for Block S = [42, 7, 123, 2024, 1729] | WORKING_ASSUMPTION |
| EXP05-PERT-01 | Perturbation distribution = Gaussian, column-wise std scaled | WORKING_ASSUMPTION |
| EXP05-PERT-02 | sigma=0 sanity run must reproduce EXP-01 baseline (cluster_labels identical) | WORKING_ASSUMPTION |
| EXP05-ART-01 | Labels artifact schema | WORKING_ASSUMPTION |
| EXP05-AGG-01 | Aggregate uses mean/std/min/max/CV; no composite scoring | TECHNICALLY_IMPLEMENTED |
| EXP05-DEC-01 | Decision status taxonomy | WORKING_ASSUMPTION |
| EXP05-EPIC-08 | ARI/AMI, Hungarian matching, statistical tests, CI thuộc EPIC-08 | TECHNICALLY_IMPLEMENTED |

---

## 15. Câu hỏi cần Mentor review

### 15.1. Về EXP-05 evidence

1. Block R reproducibility verification có đủ evidence không?
2. Block S với 5 seeds có đủ cho EPIC-08 ARI/AMI computation không?
3. Block N với 3 perturbation seeds có đủ không?
4. Sigma grid [0, 0.01, 0.05] có phù hợp không, hay cần thêm sigma = 0.1, 0.2?
5. Perturbation distribution = Gaussian có phù hợp không?

### 15.2. Về boundary

1. EXP-05 có nên được mở rộng để test EXP-03 working selections không?
2. Agglomerative + DBSCAN có nên được thêm vào Block S với random_state override không?
3. EXP-05 có cần rerun trên RFM-only nếu artifact materialized không?

### 15.3. Về EPIC-08 readiness

1. Labels artifact 327825 rows có đủ cho EPIC-08 ARI/AMI / Hungarian matching / statistical tests không?
2. EPIC-08 có cần sample / subsample, hay full computation?
3. EPIC-08 có cần thêm evidence (vd. EXP-05 + EXP-03 working selections) trước khi bắt đầu không?
4. EPIC-08 có cần 95% CI cho runtime / metric variance không?

---

## Provenance

Mọi số liệu trong tài liệu này lấy từ:
- `reports/exp05/exp05_analysis.md`
- `reports/exp05/exp05_manifest.json`
- `reports/exp05/exp05_run_summary.json`
- `reports/exp05/exp05_reproducibility_results.csv`
- `reports/exp05/exp05_reproducibility_aggregate.csv`
- `reports/exp05/exp05_seed_sweep_results.csv`
- `reports/exp05/exp05_seed_sweep_aggregate.csv`
- `reports/exp05/exp05_noise_perturbation_results.csv`
- `reports/exp05/exp05_noise_perturbation_aggregate.csv`
- `reports/exp05/exp05_cluster_size_consistency.csv`
- `reports/exp05/exp05_cluster_labels.parquet`
- `reports/exp05/exp05_pending_review.json`
- `configs/exp05_stability_reproducibility.yaml`

---

**REVIEW_STATUS: PENDING_HUMAN_REVIEW**
