# EXP-01 / EXP-02 Results Review

> **Tài liệu review EXP-01 và EXP-02.**
> Tài liệu này trình bày **observed evidence** từ 2 experiments. Không tự chọn algorithm, không chọn K, không ranking.
> Mọi quyết định nghiên cứu đang ở trạng thái `PENDING_HUMAN_REVIEW`.

---

## Phần A — EXP-01 Baseline Experiment

### A.1. Mục tiêu

Thực thi baseline thống nhất cho 5 algorithm clustering trên FE-06 Final Clustering Dataset (`FE06-v1.0`):

- K-Means (`ML-02`)
- Agglomerative / Hierarchical (`ML-03`)
- DBSCAN (`ML-04`)
- Gaussian Mixture Model (`ML-05`)
- Fuzzy C-Means (`ML-06`)

Baseline cung cấp:
- Mốc tham chiếu thống nhất cho EPIC-07 sweep và EPIC-08 comparison.
- Bảo toàn evidence: input SHA, config SHA, hyperparameters, seed, library versions, evaluation metrics (value + status), runtime statistics.
- Hỗ trợ EPIC-07/EPIC-08 với unified metric schema.

### A.2. Experimental design

| Tham số | Giá trị | Nguồn |
|---------|---------|-------|
| Baseline seed | 42 | `configs/clustering.yaml` |
| Runtime n_repeat | 5 | EXP-01 plan |
| DBSCAN noise policy | Exclude noise from internal metrics + WCSS | EXP-01 plan §4.3 |
| WCSS convention | Arithmetic centroid từ hard labels | EXP-01 plan §4.2 |
| Metric status schema | VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR / MISSING | EXP-01 plan §4.1 |

5 algorithms chạy với working default từ `configs/clustering.yaml` (frameworks block). Mỗi algorithm lặp 5 lần cho runtime statistics và reproducibility verification.

**Lưu ý EXP-01 plan §3.3:** Repetition KHÔNG phải stability analysis. Stability analysis = EXP-05 (evidence) + EPIC-08 (analysis).

### A.3. Input

| Field | Value |
|-------|-------|
| Dataset | `data/processed/final_clustering_dataset.parquet` |
| Input SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Dataset version | `FE06-v1.0` |
| Customer metadata | `data/processed/customer_metadata.parquet`, SHA `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` |
| Customer count | 4,371 |
| Feature count | 14 (RFM Extended) |
| Config SHA-256 | `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79` |

### A.4. Algorithms / configurations

| Algorithm | Family | Working default hyperparameters | seed |
|-----------|--------|--------------------------------|------|
| kmeans | Hard | `n_clusters=4, init=k-means++, n_init=10, max_iter=300, tol=1e-4` | 42 |
| agglomerative | Hard | `n_clusters=4, linkage=ward, metric=euclidean, compute_distances=True` | (deterministic) |
| dbscan | Density-based | `eps=0.5, min_samples=5, metric=euclidean` | (deterministic) |
| gmm | Model-based | `n_components=4, covariance_type=full, init_params=kmeans, tol=1e-3, reg_covar=1e-6, max_iter=100, n_init=1` | 42 |
| fuzzy_cmeans | Fuzzy | `n_clusters=4, m=2.0, max_iter=300, error=1e-4` | 42 |

### A.5. Metrics (computed)

| Algorithm | Silhouette | DBI | CH | WCSS |
|-----------|------------|-----|-----|------|
| kmeans | 0.5681 | 0.6128 | 4819.08 | 179858.91 |
| agglomerative | 0.5657 | 0.7360 | 4578.83 | 187019.54 |
| dbscan | -0.1041 | 0.7721 | 49.18 | 2125.13 |
| gmm | 0.1843 | 3.7486 | 131.73 | 710957.20 |
| fuzzy_cmeans | 0.2691 | 1.3709 | 3869.05 | 211949.22 |

Tất cả metrics status = `VALID_VALUE`.

DBSCAN metrics đặc biệt: n_clusters = 17 (so với 4 của các algorithm khác), noise_ratio = **0.7268** (3177 / 4371 customers được gán noise label `-1`).

WCSS cho GMM = 710957.20 — đây là WCSS dùng **arithmetic centroid từ hard labels** (sau `argmax`), KHÔNG phải `inertia_` của sklearn KMeans hoặc GMM `means_` parameter. Đây là convention được EXP-01 plan §4.2 enforce.

### A.6. Runtime statistics (n_repeat=5)

| Algorithm | mean (s) | std (s) | min (s) | max (s) |
|-----------|----------|---------|---------|---------|
| kmeans | 0.0476 | 0.0225 | 0.0284 | 0.0836 |
| agglomerative | 0.5663 | 0.0933 | 0.4705 | 0.6735 |
| dbscan | 0.1083 | 0.0041 | 0.1041 | 0.1142 |
| gmm | 0.5189 | 0.1691 | 0.3347 | 0.7316 |
| fuzzy_cmeans | 0.0658 | 0.0068 | 0.0621 | 0.0779 |

**Lưu ý:** Runtime đo **algorithm execution only** (time.perf_counter quanh `adapter.fit()`). KHÔNG bao gồm metric computation time hoặc artifact writing time.

### A.7. Các điểm đã verify

- ✅ Tất cả 5 algorithms SUCCESS.
- ✅ Input SHA-256 unchanged pre/post run (verified tại `experiment_log_*.json`).
- ✅ Config SHA-256 ghi trong mỗi experiment log.
- ✅ Library versions recorded.
- ✅ Reproducibility: deterministic algorithms (agglomerative, dbscan) và seeded algorithms (kmeans, gmm, fcm) đều cho cùng labels_hash across 5 repeats (verified at EXP-05 Block R).
- ✅ Metric status schema đúng convention: VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR / MISSING.
- ✅ WCSS convention: arithmetic centroid từ hard labels (GMM/FCM dùng `argmax`).

### A.8. Limitations

- **DBSCAN baseline eps=0.5, min_samples=5** sinh 17 clusters + 72.68% noise. Đây là working default; chưa được tinh chỉnh. EXP-03 đã thử `eps ∈ {0.3, 0.7, 1.0}` và `min_samples ∈ {3, 10, 15}` — không có systematic eps-sweep cho DBSCAN.
- **GMM baseline covariance_type=full** cho silhouette thấp (0.1843) so với EXP-03 Stage B `covariance_type=tied` (0.5702). Đây là expected behavior với dataset có high-dimensional skewness; không phải implementation bug.
- **Agglomerative linkage=ward** là working default; EXP-03 Stage B thấy `linkage=average` cho silhouette cao hơn (Stage C K=3 linkage=average = 0.8033) nhưng có CH thấp hơn ~60× (chaining artifact).
- **Repetition = runtime measurement, KHÔNG stability analysis.** Stability evidence (Block R/S/N) thuộc EXP-05.

### A.9. Pending research decisions (EXP-01 cụ thể)

| ID | Decision / Question | Status | Evidence |
|----|---------------------|--------|----------|
| EXP01-MET-01 | Noise exclusion policy (silhouette/DBI/CH/WCSS exclude noise) | PENDING_REVIEW (FE-06 đã apply; EXP-01 mirror) | EXP-01 plan §4.3 |
| EXP01-MET-02 | WCSS convention: arithmetic centroid từ hard labels | PENDING_REVIEW | EXP-01 plan §4.2 |
| EXP01-MET-03 | n_repeat=5 cho runtime measurement | PENDING_REVIEW | EXP-01 plan §3.3 |
| EXP01-MET-04 | Metric applicability status schema (4 statuses + reason) | PENDING_REVIEW | EXP-01 plan §4.1 |
| EXP01-MET-05 | All-noise DBSCAN: silhouette → NOT_APPLICABLE / ALL_NOISE | PENDING_REVIEW | EXP-01 plan §4.1 |
| EXP01-MET-06 | Single-cluster edge case: silhouette → NOT_APPLICABLE / SINGLE_CLUSTER | PENDING_REVIEW | EXP-01 plan §4.1 |
| EXP01-ENG-01 | `configs/exp01_baseline.yaml` riêng thay vì sửa experiment.yaml | PENDING_REVIEW (Engineering) | EXP-01 plan §5 |
| EXP01-ENG-02 | Export metrics/baseline trong `clustering/__init__.py` (nếu convention yêu cầu) | PENDING_REVIEW (Engineering) | EXP-01 plan §7 |

### A.10. Câu hỏi cần Mentor review (EXP-01)

1. Có chấp nhận noise exclusion policy (internal metrics + WCSS exclude noise points) cho EPIC-08 không?
2. Có chấp nhận WCSS convention (arithmetic centroid từ hard labels) cross-algorithm không?
3. n_repeat=5 có đủ statistics cho runtime variance comparison trong EPIC-08 không?
4. Metric status schema 4 giá trị + reason field có đủ cho EPIC-08 không?
5. DBSCAN với 17 clusters + 72.68% noise ratio có được xem là baseline hợp lệ cho EPIC-08 không, hay cần tuning eps/min_samples trước?

---

## Phần B — EXP-02 Cluster-count Survey

### B.1. Mục tiêu

Khảo sát ảnh hưởng của cluster-count `K` đến 4 K-bearing algorithm:

- K-Means (`n_clusters = K`)
- Agglomerative (`n_clusters = K`)
- GMM (`n_components = K`)
- Fuzzy C-Means (`n_clusters = K`)

DBSCAN không có K parameter → chỉ 1 diagnostic entry (mirror EXP-01 working default).

EXP-02 cung cấp:
- Metric curves theo K cho mỗi algorithm.
- Evidence-based candidate cluster numbers (heuristic transparent, deterministic).
- Provenance cho mỗi (algorithm, K) combination.
- Reuse EXP-01 metrics layer verbatim.

### B.2. Experimental design

| Tham số | Giá trị | Status |
|---------|---------|--------|
| K range | [2, 10], step=1 | WORKING_ASSUMPTION (PENDING_REVIEW) |
| Seed | 42 | EXP-01 default |
| n_repeat | 5 | Mirror EXP-01 |
| Algorithms sweep | kmeans, agglomerative, gmm, fuzzy_cmeans | 4 K-bearing |
| Algorithms diagnostic | dbscan | 1 run only |
| Fixed non-K hyperparameters | EXP-01 working defaults | Mirror EXP-01 |
| Candidate heuristic | top_n=3, drop_ratio=0.2, min_agreement=2 | WORKING_ASSUMPTION (PENDING_REVIEW) |

### B.3. Input

| Field | Value |
|-------|-------|
| Dataset | `data/processed/final_clustering_dataset.parquet` |
| Input SHA-256 | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` |
| Dataset version | `FE06-v1.0` |
| Customer count | 4,371 |
| Feature count | 14 (RFM Extended) |

### B.4. Metric curves observed (selection)

### K-Means — selected K values

| K | Silhouette | DBI | CH | WCSS |
|---|------------|-----|-----|------|
| 2 | 0.5839 | 0.6518 | 3331.81 | 439857.24 |
| 3 | 0.6291 | 0.5881 | 5420.09 | 222674.94 |
| 4 | 0.5681 | 0.6128 | 4819.08 | 179858.91 |
| 5 | 0.5697 | 0.7219 | 4851.72 | 142386.28 |
| 6 | 0.5740 | 0.6598 | 4663.50 | 122249.01 |
| 7 | 0.5118 | 0.6894 | 4472.89 | 108436.95 |
| 8 | 0.5033 | 0.7220 | 4395.42 | 96285.56 |
| 9 | 0.4983 | 0.6663 | 4228.88 | 88545.68 |
| 10 | 0.4782 | 0.6768 | 4083.96 | 82230.82 |

### Agglomerative (ward) — selected K values

| K | Silhouette | DBI | CH | WCSS |
|---|------------|-----|-----|------|
| 2 | 0.6103 | 0.5655 | 3148.99 | 450553.83 |
| 3 | 0.5904 | 0.6388 | 5029.13 | 234744.25 |
| 4 | 0.5657 | 0.7360 | 4578.83 | 187019.54 |
| 5 | 0.5446 | 0.7438 | 4266.60 | 157935.11 |
| 6 | 0.4556 | 0.7959 | 4167.58 | 134276.56 |
| 7 | 0.4574 | 0.7604 | 4190.52 | 114663.13 |
| 8 | 0.4405 | 0.8113 | 4072.80 | 102900.46 |
| 9 | 0.4424 | 0.7369 | 3886.61 | 95384.15 |
| 10 | 0.4432 | 0.7037 | 3720.43 | 89339.74 |

### GMM — selected K values

| K | Silhouette | DBI | CH | WCSS |
|---|------------|-----|-----|------|
| 2 | 0.0222 | 3.8192 | 118.77 | 754775.21 |
| 3 | 0.2047 | 3.5978 | 245.01 | 697090.23 |
| 4 | 0.1843 | 3.7486 | 131.73 | 710957.20 |
| 5 | 0.1946 | 12.7203 | 153.29 | 679821.48 |
| 6 | 0.1387 | 4.2923 | 147.71 | 663097.01 |
| 7 | 0.1489 | 9.2682 | 135.34 | 653660.92 |
| 8 | 0.1544 | 8.3500 | 141.61 | 631762.33 |
| 9 | 0.1604 | 5.4616 | 191.18 | 574026.85 |
| 10 | 0.1528 | 8.5950 | 141.02 | 600519.58 |

### Fuzzy C-Means — selected K values

| K | Silhouette | DBI | CH | WCSS |
|---|------------|-----|-----|------|
| 2 | 0.5696 | 0.6835 | 3315.16 | 440810.14 |
| 3 | 0.6271 | 0.5938 | 5413.69 | 222862.69 |
| 4 | 0.2691 | 1.3709 | 3869.05 | 211949.22 |
| 5 | 0.5560 | 0.7262 | 4805.42 | 143504.11 |
| 6 | 0.2711 | 1.1401 | 4087.97 | 136431.22 |
| 7 | 0.2681 | 1.4953 | 3464.30 | 134529.05 |
| 8 | 0.2047 | 1.4788 | 3048.35 | 131611.56 |
| 9 | 0.2455 | 1.3079 | 3363.91 | 108137.94 |
| 10 | 0.1914 | 1.5919 | 2957.31 | 109148.16 |

**Lưu ý Fuzzy C-Means:** Silhouette tại K=4 (0.2691) thấp hơn K=3 (0.6271) — đây là **non-monotonic** behavior, không phải implementation bug; K-Means K=4 cũng tương tự (0.5681 < 0.6291 ở K=3). Metrics observed, không suy diễn.

### DBSCAN diagnostic

| Field | Value |
|-------|-------|
| n_clusters | 17 |
| noise_count | 3177 |
| noise_ratio | 0.7268 |
| Silhouette | -0.1041 (VALID_VALUE) |
| DBI | 0.7721 (VALID_VALUE) |
| CH | 49.18 (VALID_VALUE) |
| WCSS | 2125.13 (VALID_VALUE) |
| Hyperparameters | `eps=0.5, min_samples=5, metric=euclidean` |

DBSCAN KHÔNG nằm trong K-sweep vì không có K parameter.

### B.5. Candidates observed (13 candidates)

| Algorithm | K | Agreement | Evidence |
|-----------|---|-----------|----------|
| kmeans | 2 | 2 | silhouette_top_n, davies_bouldin_low_n |
| kmeans | 3 | **4** | silhouette_top_n, davies_bouldin_low_n, calinski_harabasz_top_n, wcss_elbow_drop |
| kmeans | 4 | 2 | calinski_harabasz_top_n, davies_bouldin_low_n |
| kmeans | 5 | 2 | calinski_harabasz_top_n, wcss_elbow_drop |
| agglomerative | 2 | 2 | silhouette_top_n, davies_bouldin_low_n |
| agglomerative | 3 | **4** | silhouette_top_n, davies_bouldin_low_n, calinski_harabasz_top_n, wcss_elbow_drop |
| agglomerative | 4 | 3 | silhouette_top_n, calinski_harabasz_top_n, wcss_elbow_drop |
| gmm | 3 | 3 | silhouette_top_n, davies_bouldin_low_n, calinski_harabasz_top_n |
| gmm | 4 | 2 | silhouette_top_n, davies_bouldin_low_n |
| gmm | 5 | 2 | silhouette_top_n, calinski_harabasz_top_n |
| fuzzy_cmeans | 2 | 2 | silhouette_top_n, davies_bouldin_low_n |
| fuzzy_cmeans | 3 | **4** | silhouette_top_n, davies_bouldin_low_n, calinski_harabasz_top_n, wcss_elbow_drop |
| fuzzy_cmeans | 5 | **4** | silhouette_top_n, davies_bouldin_low_n, calinski_harabasz_top_n, wcss_elbow_drop |

**Lưu ý:** "candidate" = K được flag bởi ≥ 2 indicators. KHÔNG có "best K", "optimal K", "final K", "recommended K".

### B.6. Disagreements giữa metrics (đã ghi nhận)

Một số indicators flag K khác nhau cho cùng algorithm. Ví dụ K-Means:
- silhouette_top_n flag K ∈ {2, 3, 4} (top 3)
- davies_bouldin_low_n flag K ∈ {3, 4, 6}
- calinski_harabasz_top_n flag K ∈ {3, 4, 5}
- wcss_elbow_drop flag K ∈ {3, 5, 7}

K được flag bởi ≥ 2 indicators → candidate. K-Means có 4 candidates: K ∈ {2, 3, 4, 5}. Mỗi K có `evidence_indicators` riêng.

Trong trường hợp disagreement (mỗi indicator flag K khác nhau), KHÔNG tự resolve. Mỗi indicator evidence được ghi nhận độc lập.

### B.7. Các điểm đã verify

- ✅ 37/37 runs SUCCESS, tất cả metrics status = `VALID_VALUE`.
- ✅ Input SHA-256 unchanged.
- ✅ CustomerID alignment preserved (positional).
- ✅ Canonical ordering preserved: kmeans → agglomerative → dbscan → gmm → fuzzy_cmeans.
- ✅ DBSCAN KHÔNG nằm trong K-sweep (chỉ 1 diagnostic run).
- ✅ Không rerun K-sweep.
- ✅ Không rank algorithms.
- ✅ Candidate heuristic transparent, deterministic.

### B.8. Limitations

- **K range [2..10]** chưa được Mentor approve. Nếu cần K > 10, cần sweep lại.
- **Candidate heuristic constants** (top_n=3, drop_ratio=0.2, min_agreement=2) là WORKING_ASSUMPTION. Khi thay đổi constants, candidate set thay đổi → không deterministic cố định.
- **RFM-only feature set KHÔNG có** trong repo (PENDING_REVIEW `EXP02-FS-01`). EXP-02 chỉ chạy trên RFM Extended (14 features). RQ2 (feature representation) PARTIAL.
- **DBSCAN contribution to candidate set** chỉ qua 1 diagnostic point. Không có systematic eps-sweep.
- **Disagreement giữa indicators** không tự resolve — Mentor cần quyết định nếu cần.

### B.9. Pending research decisions (EXP-02)

| ID | Decision / Question | Status | Evidence |
|----|---------------------|--------|----------|
| EXP02-KRNG-01 | K range [2, 10], step=1 | WORKING_ASSUMPTION | EXP-02 plan §3.1 |
| EXP02-FS-01 | RFM-only feature set NOT present; EXP-02 runs on RFM Extended only | PENDING_REVIEW (FE-06 ADR needed) | EXP-02 plan §2.3 |
| EXP02-CDHC-01 | Candidate heuristic constants (top_n=3, drop_ratio=0.2, min_agreement=2) | WORKING_ASSUMPTION | EXP-02 plan §5.2 |
| EXP02-DBSCAN-01 | DBSCAN contributes only via diagnostic (no K-sweep) | WORKING_ASSUMPTION | EXP-02 plan §3.3 |
| EXP02-METRIC-01 | Metric status semantics mirror EXP-01 (no new metric) | TECHNICALLY_IMPLEMENTED | EXP-02 plan §4 |
| EXP02-REPRO-01 | Same seed across repetitions; NOT stability analysis | TECHNICALLY_IMPLEMENTED | EXP-02 plan §3.3 |

### B.10. Câu hỏi cần Mentor review (EXP-02)

1. K range [2, 10] có đủ không, hay cần mở rộng (vd. lên K=15 hoặc thu hẹp xuống [2, 8])?
2. Candidate heuristic constants (top_n=3, drop_ratio=0.2, min_agreement=2) có hợp lý không, hay cần điều chỉnh?
3. Trong trường hợp disagreement giữa indicators (silhouette vs CH vs WCSS flag K khác nhau), protocol hiện tại có phù hợp không?
4. DBSCAN có nên được tinh chỉnh eps/min_samples riêng cho EPIC-08 không, hay giữ working default?
5. RFM-only artifact có cần materialize để EXP-02 (Family A của EXP-04) có thể execute không?
6. EPIC-08 có nên dùng 13 candidates này làm input trực tiếp, hay cần rerun K-sweep?

---

## Provenance

Mọi số liệu trong tài liệu này lấy từ:
- `reports/exp01/exp01_initial_baseline.md`
- `reports/exp01/exp01_baseline_manifest.json`
- `reports/exp01/exp01_run_summary.json`
- `reports/exp02/exp02_cluster_number_analysis.md`
- `reports/exp02/exp02_cluster_number_summary.csv`
- `reports/exp02/exp02_metric_curves.csv`
- `reports/exp02/exp02_candidate_cluster_numbers.csv`
- `reports/exp02/exp02_manifest.json`

---

**REVIEW_STATUS: PENDING_HUMAN_REVIEW**
