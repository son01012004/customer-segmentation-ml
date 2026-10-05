# EXP-01 → EXP-05 Review Overview

> **Tài liệu này dùng để gửi Mentor và các thành viên nghiên cứu review trước khi chuyển sang EPIC-08.**
> Ngôn ngữ: tiếng Việt. Code/identifier/file name: tiếng Anh theo convention hiện tại.
> Tài liệu **KHÔNG** tự kết luận methodology. Mọi quyết định nghiên cứu đang ở trạng thái `PENDING_HUMAN_REVIEW`.

---

## 1. Mục tiêu của giai đoạn EXP-01 → EXP-05

Giai đoạn này thuộc **EPIC-07 (Controlled Experiments)** trong pipeline nghiên cứu, xây dựng trên nền tảng:

- **FE-04**: customer-level aggregation.
- **FE-05**: customer feature engineering (RFM + extended behavioral features).
- **FE-06**: transformation + scaling → Final Clustering Dataset `FE06-v1.0`.
- **ML-01 → ML-06**: 5 algorithm adapters đã đăng ký vào `AlgorithmRegistry` (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means).

Mục tiêu **kỹ thuật** (TECHNICALLY_IMPLEMENTED) của giai đoạn này:

- EXP-01: chạy unified baseline cho 5 algorithm trên cùng input.
- EXP-02: khảo sát ảnh hưởng của cluster-count `K = 2..10` (step=1) với 4 K-bearing algorithm + DBSCAN diagnostic.
- EXP-03: khảo sát sensitivity theo hyperparameter per-algorithm (Stage A/B/C) để xác định working selection per-algorithm.
- EXP-04: đánh giá controlled preprocessing sensitivity (transformation × scaling) trên RFM Extended feature set.
- EXP-05: sinh **raw evidence** (Block R reproducibility, Block S seed sensitivity, Block N feature perturbation) — KHÔNG phải stability analysis.

Mục tiêu **nghiên cứu** (PENDING_HUMAN_REVIEW): cung cấp evidence base cho EPIC-08 (stability analysis với ARI/AMI/Hungarian/statistical tests/CI).

---

## 2. Research Questions liên quan

Tài liệu `docs/methodology/README.md` hiện ghi nhận rằng các file research questions (research questions, methodology overview, unit of analysis) **chưa được viết** (chỉ có placeholder `TODO_research_questions.md`, `TODO_methodology_overview.md`, `TODO_unit_of_analysis.md`).

Giai đoạn EXP-01 → EXP-05 đã được thiết kế để hỗ trợ các câu hỏi nghiên cứu thuộc 2 trục (xuất hiện trong các pending_review notes của từng experiment):

| Trục | Mô tả | Status |
|------|--------|--------|
| **RQ1** (algorithm × K × preprocessing × hyperparameter) | Ảnh hưởng của các yếu tố controlled đến internal metrics | Evidence đã có từ EXP-01/02/03/04 |
| **RQ2** (feature representation: RFM-only vs RFM Extended) | So sánh feature set | **RQ2 PARTIAL** — Family A của EXP-04 DEFERRED vì RFM-only artifact chưa tồn tại |
| **RQ3** (reproducibility / seed sensitivity / robustness) | Stability evidence | Evidence đã có từ EXP-05 (raw evidence; EPIC-08 sẽ phân tích) |

Đây là **inferred mapping** dựa trên pending_review notes; **chưa được xác nhận** trong methodology document chính thức.

---

## 3. Experimental progression

### 3.1. EXP-01 Baseline

- 5 algorithm × 1 working default configuration.
- 1 seed (42) × n_repeat=5 (reproducibility/runtime variance).
- Tổng: **5 runs** (mỗi algorithm = 1 record; n_repeat dùng cho runtime statistics, không tạo record mới).
- Inputs: `final_clustering_dataset.parquet` (FE-06 output, SHA `ba54033e4552...0f9c`).

### 3.2. EXP-02 Cluster-count exploration

- 4 K-bearing algorithms (K-Means, Agglomerative, GMM, Fuzzy C-Means) × K ∈ {2..10} (step=1).
- 1 DBSCAN diagnostic run (no K parameter).
- 1 seed (42) × n_repeat=5.
- Tổng: **37 runs** (4 × 9 + 1).

### 3.3. EXP-03 Hyperparameter sensitivity

- Stage A: baseline per algorithm (5 runs).
- Stage B: single-parameter sensitivity sweeps per algorithm.
- Stage C: selected interactions (K from EXP-02 × parameter).
- Tổng: **38 runs** (kmeans=10, agglomerative=7, dbscan=7, gmm=5, fuzzy_cmeans=9).

### 3.4. EXP-04 Preprocessing / feature-set sensitivity

- Family A (feature set sensitivity RFM vs RFM Extended): **DEFERRED**.
- Family B (preprocessing sensitivity): 6 full-matrix scenarios × n_repeat=5.
- Tổng Family B: **30 runs** = 6 × 5.
- Input: `customer_candidates.parquet` (FE-05 output, SHA `df5333fba95a...5649`) — pre-transform data, EXP-04 tự apply transformation + scaling riêng.

### 3.5. EXP-05 Reproducibility / stability-related diagnostics

- Block R: 5 algorithms × n_repeat=5 × seed=42 → **25 runs**.
- Block S: 3 algorithms (K-Means, GMM, FCM) × 5 seeds → **15 runs**.
- Block N: 5 algorithms × (1 sigma=0 sanity + 2 sigmas × 3 perturbation seeds) → **35 runs**.
- Tổng: **75 runs**.
- Labels artifact: `exp05_cluster_labels.parquet`, 327825 rows × 9 columns.

### 3.6. Tổng hợp runs

| Experiment | Runs | Methodology status |
|------------|------|---------------------|
| EXP-01 | 5 | TECHNICALLY_IMPLEMENTED |
| EXP-02 | 37 | TECHNICALLY_IMPLEMENTED |
| EXP-03 | 38 | TECHNICALLY_IMPLEMENTED |
| EXP-04 | 30 | TECHNICALLY_IMPLEMENTED (Family A DEFERRED) |
| EXP-05 | 75 | TECHNICALLY_IMPLEMENTED (raw evidence only) |
| **Tổng** | **185** | |

---

## 4. Technical verification summary

| Hạng mục | Kết quả | Nguồn |
|----------|---------|--------|
| `pytest tests/` | **1105/1105 pass** | Test session 2026-09-22 |
| `pytest tests/test_exp0X_*.py` (5 files) | **208/208 pass** | Test session 2026-09-22 |
| `ruff check .` | PASS | 0 errors |
| `black --check .` | PASS | 155 files unchanged |
| Input SHA unchanged across EXP-01/02/03/05 | Verified | Manifest `input_sha256` |
| Input SHA unchanged across EXP-04 | Verified | Manifest `input_sha256` (customer_candidates.parquet) |
| Customer metadata SHA unchanged across EXP-04/EXP-05 | Verified | Manifest `customer_metadata_sha256` |

**Lưu ý:** Số liệu kỹ thuật trên được lấy từ session verification 2026-09-22. Một số file `tests/test_fe04_pipeline.py` đã được sửa `# noqa: E402` để pass ruff (pre-existing import pattern).

---

## 5. Dataset / input provenance

| Artifact | SHA-256 | Used by |
|----------|---------|---------|
| `final_clustering_dataset.parquet` (FE-06 output) | `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c` | EXP-01, EXP-02, EXP-03, EXP-05 |
| `customer_candidates.parquet` (FE-05 output, pre-transform) | `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649` | EXP-04 |
| `customer_metadata.parquet` | `c2a42b3c8b035dcf6a5af8e4b6afb6a444099e6ad0e12a271ea59d95c7382ad2` | EXP-04, EXP-05 |
| `configs/clustering.yaml` | `d5172c4640d7bc2cbbaa0bc22b9de9353c4e851bbf21dec2e801bf06951abd79` | Tất cả 5 experiments |
| `configs/exp05_stability_reproducibility.yaml` | `3dec62060a5a6d1c09443debc51802f6f321e91f7dbbd792962e9b519afcda9e` | EXP-05 |

Dataset version (FE-06): `FE06-v1.0`. Status trong FE-06 doc: `TECHNICALLY_GENERATED` / `WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING` (chưa phải final approved clustering dataset).

Library versions ghi nhận trong manifests:
`numpy 2.3.5`, `pandas 3.0.6`, `pyarrow 25.0.1`, `scikit-learn 1.9.1`, `scipy 1.18.1`.

Platform: Python 3.14.4, Linux 7.0.0-31-generic, x86_64.

---

## 6. Output / artifact overview

### 6.1. EXP-01 → EXP-05 reports directory

| Path | Loại | Nội dung chính |
|------|------|----------------|
| `reports/exp01/exp01_initial_baseline.md` | Markdown | Báo cáo baseline (algorithms, metrics, runtime) |
| `reports/exp01/exp01_baseline_summary.csv` | CSV | Flat summary 5 algorithms × metrics |
| `reports/exp01/exp01_baseline_manifest.json` | JSON | Full manifest với hyperparameters + metrics + status |
| `reports/exp01/exp01_run_summary.json` | JSON | Machine-readable summary |
| `reports/exp01/cluster_labels_EXP-01-{algo}_rep4.parquet` | Parquet (5 files) | Per-algorithm cluster labels |
| `reports/exp01/algorithm_output_EXP-01-{fuzzy,gmm}_rep4.parquet` | Parquet (2 files) | Soft memberships (GMM/FCM only) |
| `reports/exp01/experiment_log_EXP-01-{algo}_rep4.json` | JSON (5 files) | Full ExperimentResult.to_dict() |

| Path | Loại | Nội dung chính |
|------|------|----------------|
| `reports/exp02/exp02_cluster_number_analysis.md` | Markdown | Báo cáo K-sweep |
| `reports/exp02/exp02_cluster_number_summary.csv` | CSV | Per (algorithm, K) summary |
| `reports/exp02/exp02_metric_curves.csv` | CSV | Metric curves long-format |
| `reports/exp02/exp02_candidate_cluster_numbers.csv` | CSV | Evidence-based candidate K values |
| `reports/exp02/exp02_manifest.json` | JSON | Full manifest + candidates |
| `reports/exp02/exp02_run_summary.json` | JSON | Machine-readable summary |
| `reports/exp02/figures/exp02_<algo>_<metric>_vs_k.png` | PNG (16 files) | Diagnostic metric curves |

| Path | Loại | Nội dung chính |
|------|------|----------------|
| `reports/exp03/exp03_hyperparameter_analysis.md` | Markdown | Báo cáo sensitivity |
| `reports/exp03/exp03_hyperparameter_results.csv` | CSV | Per-run results |
| `reports/exp03/exp03_parameter_sensitivity.csv` | CSV | Per-parameter sensitivity table |
| `reports/exp03/exp03_selected_configurations.csv` | CSV | Per-algorithm working selection |
| `reports/exp03/exp03_manifest.json` | JSON | Full manifest + sensitivity table |
| `reports/exp03/exp03_run_summary.json` | JSON | Machine-readable summary |
| `reports/exp03/figures/*.png` | PNG | Diagnostic sensitivity plots |

| Path | Loại | Nội dung chính |
|------|------|----------------|
| `reports/exp04/exp04_analysis.md` | Markdown | Báo cáo preprocessing sensitivity |
| `reports/exp04/exp04_scenario_results.csv` | CSV | Per (scenario × repeat) results |
| `reports/exp04/exp04_preprocessing_sensitivity.csv` | CSV | Per-scenario aggregate |
| `reports/exp04/exp04_manifest.json` | JSON | Full manifest + scope boundaries |
| `reports/exp04/exp04_run_summary.json` | JSON | Machine-readable summary |
| `reports/exp04/exp04_deferred.json` | JSON | Family A deferred evidence |
| `reports/exp04/exp04_pending_review.json` | JSON | PENDING_REVIEW items (8 items) |

| Path | Loại | Nội dung chính |
|------|------|----------------|
| `reports/exp05/exp05_analysis.md` | Markdown | Báo cáo reproducibility/stability evidence |
| `reports/exp05/exp05_reproducibility_results.csv` | CSV | Block R per-(algo, repeat) |
| `reports/exp05/exp05_reproducibility_aggregate.csv` | CSV | Block R per-algo aggregate |
| `reports/exp05/exp05_seed_sweep_results.csv` | CSV | Block S per-(algo, seed) |
| `reports/exp05/exp05_seed_sweep_aggregate.csv` | CSV | Block S per-algo aggregate |
| `reports/exp05/exp05_noise_perturbation_results.csv` | CSV | Block N per-(algo, sigma, pseed) |
| `reports/exp05/exp05_noise_perturbation_aggregate.csv` | CSV | Block N per-(algo, sigma) |
| `reports/exp05/exp05_cluster_size_consistency.csv` | CSV | Cross-block cluster size snapshot |
| `reports/exp05/exp05_cluster_labels.parquet` | Parquet | **REQUIRED for EPIC-08** — 327825 rows × 9 cols |
| `reports/exp05/exp05_manifest.json` | JSON | Full manifest + provenance |
| `reports/exp05/exp05_run_summary.json` | JSON | Machine-readable summary |
| `reports/exp05/exp05_pending_review.json` | JSON | PENDING_REVIEW items (9 items) |

### 6.2. Schema của labels artifact (EXP-05)

`exp05_cluster_labels.parquet` — 9 columns:

| Column | Type | Mô tả |
|--------|------|--------|
| `run_id` | str | Unique identifier per (block, algo, seed, sigma, pseed, repeat_index) |
| `block` | str | "R" / "S" / "N" |
| `algorithm` | str | algorithm name |
| `seed` | int64 | random seed for algorithm |
| `sigma` | float64 | None for R/S; float for N |
| `perturbation_seed` | float64 | None for R/S; int for N |
| `repeat_index` | int64 | 0..4 for R; 0 for S/N |
| `CustomerID` | int64 | From FE-06 customer_metadata |
| `cluster_label` | int64 | Hard label (argmax for GMM/FCM, raw for others) |

---

## 7. Các phát hiện chính đã VERIFIED

> Các phát hiện dưới đây là **observed evidence**, KHÔNG phải kết luận nghiên cứu.

### 7.1. Internal metrics observed (EXP-01)

| Algorithm | Silhouette | DBI | CH | WCSS | n_clusters | noise_ratio |
|-----------|------------|-----|-----|------|------------|-------------|
| kmeans | 0.5681 | 0.6128 | 4819.08 | 179858.91 | 4 | 0.0 |
| agglomerative (ward) | 0.5657 | 0.7360 | 4578.83 | 187019.54 | 4 | 0.0 |
| dbscan | -0.1041 | 0.7721 | 49.18 | 2125.13 | 17 | **0.7268** |
| gmm | 0.1843 | 3.7486 | 131.73 | 710957.20 | 4 | 0.0 |
| fuzzy_cmeans | 0.2691 | 1.3709 | 3869.05 | 211949.22 | 4 | 0.0 |

Tất cả metrics status = `VALID_VALUE`. Runtime mean (s): kmeans 0.0476, agglomerative 0.5663, dbscan 0.1083, gmm 0.5189, fcm 0.0658.

### 7.2. K-sweep candidates observed (EXP-02)

Có **13 candidates** được flag bởi evidence heuristics (transparent, deterministic):
- kmeans: K ∈ {2, 3, 4, 5}
- agglomerative: K ∈ {2, 3, 4}
- gmm: K ∈ {3, 4, 5}
- fuzzy_cmeans: K ∈ {2, 3, 5}
- dbscan: chỉ diagnostic, không có K-sweep candidates.

**KHÔNG có "best K" / "optimal K" / "final K" / "recommended K".**

### 7.3. EXP-03 working selections observed

| Algorithm | Status | Experiment ID | K | Silhouette | Note |
|-----------|--------|---------------|---|------------|------|
| kmeans | `TIED_WORKING_SELECTED` | EXP-03-kmeans-stageC-k3-n_init-1 | 3 | 0.6291 | Genuine 3-way tie (K-Means deterministic với fixed seed) |
| agglomerative | `WORKING_SELECTED` | EXP-03-agglomerative-stageC-k3-linkage-average | 3 | 0.8033 | CH=77.15, chênh lệch ~60× vs alternatives (chaining artifact) |
| dbscan | `WORKING_SELECTED` | EXP-03-dbscan-stageB-min_samples-10 | None | 0.1598 | |
| gmm | `WORKING_SELECTED` | EXP-03-gmm-stageB-covariance_type-tied | 4 | 0.5702 | |
| fuzzy_cmeans | `WORKING_SELECTED` | EXP-03-fuzzy_cmeans-stageC-k3-m-1_5 | 3 | 0.6296 | |

### 7.4. EXP-04 preprocessing sensitivity observed

6 scenarios × 5 repeats = 30 records, all `CANDIDATE_SCENARIO`, all deterministic.
EXP-04 KHÔNG xác nhận scenario nào là "best scenario". C0 là NO_TRANSFORM_NO_SCALING_REFERENCE; C7 là FE06_WORKING_CONFIGURATION_REFERENCE.

### 7.5. EXP-05 evidence observed

- **Block R (Reproducibility)**: 25/25 runs SUCCESS, all 5 algorithms `REPRODUCIBILITY_VERIFIED` (1 unique labels_hash across 5 repeats × seed=42).
- **Block S (Seed sensitivity)**: 15/15 runs SUCCESS, K-Means/GMM/FCM có 5 unique labels_hash across 5 seeds — **đây là kết quả mong đợi**, không phải failure.
- **Block N (Feature perturbation)**: 35/35 runs SUCCESS; sigma=0 reproduce EXP-01 baseline (sanity check pass).

---

## 8. Các vấn đề chưa được quyết quyết

### 8.1. PENDING_REVIEW / DEFERRED / WORKING_ASSUMPTION

Đầy đủ trong `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md`. Tóm tắt nhóm:

- **Family A EXP-04 (feature set sensitivity)**: DEFERRED — RFM-only artifact chưa tồn tại.
- **EXP-03 selection protocol**: WORKING_ASSUMPTION (silhouette-primary → DBI → CH tiebreaker).
- **EXP-03 Agglomerative configuration disagreement**: K-Means và Agglomerative có known disagreement giữa metrics.
- **EXP-02 candidate heuristic constants**: WORKING_ASSUMPTION (top_n=3, drop_ratio=0.2, min_agreement=2).
- **EXP-02 K range [2..10]**: WORKING_ASSUMPTION.
- **EXP-04 controlled references**: WORKING_ASSUMPTION (kmeans, K=4, median imputation, seed=42).
- **EXP-05 Block S seeds / Block N sigmas / perturbation distribution**: WORKING_ASSUMPTION.
- **EXP-05 decision status taxonomy**: WORKING_ASSUMPTION.

### 8.2. Cross-experiment discrepancies

- **EXP-04 vs EXP-01/02/03/05 input SHA**: EXP-04 dùng `customer_candidates.parquet` (`df5333fba95a...`) — pre-transform; các EXP khác dùng `final_clustering_dataset.parquet` (`ba54033e4552...`). Đây là **by design** (EXP-04 kiểm soát preprocessing pipeline riêng) nhưng ghi nhận để tránh hiểu nhầm.

---

## 9. Các điểm cần Mentor review

### 9.1. Methodology decisions

1. Có nên materialize **RFM-only artifact** (FE-06 ADR) để EXP-04 Family A có thể execute?
2. Có nên finalize **EXP-03 selection protocol** (silhouette-primary → DBI → CH) thành methodology chính thức hay giữ WORKING_ASSUMPTION?
3. Có nên finalize **EXP-02 candidate heuristic constants** (top_n=3, drop_ratio=0.2, min_agreement=2) thành methodology chính thức?
4. Có nên finalize **EXP-02 K range [2..10]** thành methodology chính thức, hay cần mở rộng/thu hẹp?
5. Có nên finalize **EXP-04 controlled references** (kmeans, K=4, median imputation, seed=42) thành methodology chính thức?
6. Có nên finalize **EXP-05 Block S seeds [42, 7, 123, 2024, 1729]** và **sigma grid [0, 0.01, 0.05]** thành methodology chính thức?
7. **Agglomerative disagreement**: EXP-03 chọn Stage C K=3 linkage=average (silhouette=0.8033 nhưng CH=77.15, ~60× thấp hơn alternatives). Có chấp nhận WORKING_SELECTED theo protocol silhouette-primary, hay cần điều chỉnh protocol?

### 9.2. EPIC-08 readiness

1. EPIC-08 có thể bắt đầu implement dựa trên EXP-05 labels artifact + EXP-01/02/03 metrics evidence không?
2. ARI/AMI / Hungarian matching / statistical tests / CI trong EPIC-08 có nên chạy trên toàn bộ 75 EXP-05 runs (75 × labels = heavy) hay subsample?
3. EXP-04 Family A có cần execute trước EPIC-08 để EPIC-08 mới đầy đủ không?

### 9.3. RQ completeness

1. RQ2 (feature representation) PARTIAL — có cần complete trước khi EPIC-08 đưa ra kết luận feature representation không?
2. EXP-05 chỉ chạy trên RFM Extended (14 features); nếu RFM-only được materialize, cần rerun EXP-05?

---

## 10. Boundary trước EPIC-08

| Trục | EXP-01 → EXP-05 (đã làm) | EPIC-08 (chưa làm) |
|------|---------------------------|---------------------|
| Internal metrics (silhouette/DBI/CH/WCSS) | ✅ Recorded per-run | Aggregate / statistical comparison |
| Stability analysis (ARI/AMI) | ❌ (chỉ evidence) | ✅ Computation |
| Hungarian matching | ❌ | ✅ Computation |
| Statistical tests | ❌ | ✅ Across seeds / perturbation |
| Confidence intervals | ❌ | ✅ |
| Cross-algorithm comparison / ranking | ❌ | ✅ (sau full evaluation) |
| "Most stable algorithm" claim | ❌ | ⚠️ (nếu methodology cho phép) |
| Visualization (research comparison) | ❌ (chỉ diagnostic plots) | ✅ |
| Re-sweep K / hyperparameters / preprocessing | ❌ | ❌ (EXP-02/03/04 owns) |
| Customer profiling / segment naming | ❌ | ❌ (EPIC-09 owns) |

---

## 11. Đề xuất câu hỏi review cho Mentor

1. **Cluster-count methodology**: EXP-02 đã sinh 13 candidates qua heuristic transparent. EPIC-08 có nên dùng candidates này làm input hay phải sweep lại?
2. **Hyperparameter selection methodology**: EXP-03 protocol silhouette-primary → DBI → CH có được accept như working methodology? Agglomerative disagreement (Stage C K=3 linkage=average vs CH=77.15) có cần protocol adjustment?
3. **Metric selection**: Bộ 4 metrics (silhouette / DBI / CH / WCSS) có đủ cho EPIC-08 không, hay cần thêm metric (vd. ARI/AMI)?
4. **DBSCAN noise handling**: noise_ratio = 0.7268 ở EXP-01 (eps=0.5, min_samples=5). Có chấp nhận DBSCAN contribute vào EPIC-08 evaluation với tỷ lệ noise này không, hay cần tuning eps/min_samples trước?
5. **Reproducibility vs stability vs robustness**: EXP-05 đã chứng minh reproducibility (Block R) và cung cấp seed-sensitivity evidence (Block S) và perturbation evidence (Block N). Đây có đủ evidence cho EPIC-08 không?
6. **RFM vs RFM Extended**: Trong khi RFM-only chưa được materialize, EPIC-08 có thể chạy trên RFM Extended only không?
7. **Runtime evaluation protocol**: 5 × n_repeat=5 có đủ statistics cho runtime variance comparison không?
8. **Business validation boundary**: Hiện tại KHÔNG có business validation. EPIC-08 có cần thêm bước business validation (vd. qua segment profile) hay để EPIC-09?

---

## 12. Provenance rule

Mọi con số trong tài liệu này **truy xuất được về**:

- `reports/exp0X/exp0X_*.{md,csv,json}` cho observed values.
- `configs/exp0X_*.yaml` cho configuration.
- `configs/clustering.yaml` cho framework defaults.
- Manifest SHA-256 fields cho dataset integrity.

KHÔNG có con số nào trong tài liệu này được invent. Tất cả số liệu đều lấy từ artifacts có sẵn trong repo tính đến 2026-09-22.

---

**REVIEW_STATUS: PENDING_HUMAN_REVIEW**
