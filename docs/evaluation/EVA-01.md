# EVA-01 — Kho lưu trữ kết quả thí nghiệm (Experiment Result Repository)

> **Task ID:** EPIC-08 / EVA-01
> **Status:** IMPLEMENTED (đã VERIFIED qua bộ test 947 dòng)
> **Generated:** 2026-09-23

## 1. Mục tiêu

Tổng hợp toàn bộ output của các thí nghiệm EPIC-07 (EXP-01, EXP-02,
EXP-03, EXP-04, EXP-05) vào một kho lưu trữ được chuẩn hoá duy nhất.
Mỗi dòng của kho lưu trữ tương ứng với một lần chạy clustering (granularity
theo run), với schema cột cố định sao cho các bộ đánh giá EVA-02 / EVA-03 ở
phía downstream có thể đọc một bảng nhất quán thay vì năm CSV không đồng nhất.

## 2. Scope

### 2.1. In scope

- Năm thí nghiệm (EXP-01, EXP-02, EXP-03, EXP-04, EXP-05).
- Năm thuật toán (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means).
- Các dòng theo run (không phải per-experiment, không phải per-configuration).
- Một schema cột chuẩn canonical với annotation `missing_reason` đi kèm.
- Truy ngược source-fingerprint (SHA-256 của input dataset, customer
  metadata, configuration, run output).

### 2.2. Out of scope

- K-Medoids (per ADR-0003 — `OUT OF SCOPE`).
- Cross-algorithm ranking, composite score, claim "best / winner / optimal".
- Re-running bất kỳ thí nghiệm nào (kho lưu trữ được xây dựng từ các
  output EPIC-07 đã có sẵn).

## 3. Input

Read-only:

| Nguồn | Rows đóng góp |
|---|---|
| `reports/exp01/exp01_baseline_summary.csv` | 5 |
| `reports/exp02/exp02_cluster_number_summary.csv` (+ metric_curves) | 37 |
| `reports/exp03/exp03_hyperparameter_results.csv` (+ parameter_sensitivity + selected_configurations) | 38 |
| `reports/exp04/exp04_scenario_results.csv` | 30 |
| `reports/exp05/exp05_reproducibility_results.csv` (+ seed_sweep + noise_perturbation) | 75 |

Tổng cộng: **185 dòng**.

## 4. Phương pháp / Implementation

### 4.1. Vị trí package

`src/customer_segmentation/evaluation/experiment_results/`:

- `schema.py` — định nghĩa `STANDARD_COLUMNS`, `FIELD_TYPES`, sentinel
  `MISSING`, `MISSING_REASONS`, `ALLOWED_DECISION_STATUSES`,
  `FORBIDDEN_DECISION_LABELS`.
- `validation.py` — row-level validation bao gồm phát hiện
  `DUPLICATE_EXACT`, `DUPLICATE_BY_INTENT`, `INCONSISTENT_CONDITIONS`.
- `collectors.py` — collector theo từng experiment, đọc CSV nguồn EPIC-07
  và sinh các dòng canonical.
- `summary.py` — bộ summary builder per-experiment / per-algorithm /
  per-K.
- `repository.py` — top-level `ExperimentResultRepository` orchestrator.
- `summary_tables_to_markdown` → `eva01_summary.md`.

### 4.2. Required columns

Theo task brief:

| Required field | Present | Ghi chú |
|---|---|---|
| Algorithm | ✓ | `algorithm` |
| Dataset Version | ✓ | `dataset_version` |
| Feature Set | ✓ | `feature_set` (`rfm_extended` cho tất cả các dòng in-scope) |
| Preprocessing | ✓ | `transformation`, `scaling`, `imputation` (chỉ EXP-04 có non-MISSING combinations; với experiment khác field này là `MISSING` với lý do `not_applicable_for_this_experiment`) |
| Number of Clusters | ✓ | `n_clusters` (requested K; DBSCAN's realised `n_clusters_realized` được ghi riêng) |
| Hyperparameters | ✓ | `hyperparameters` (JSON-serialised) |
| Random Seed | ✓ | `random_seed` (nơi có mặt) |
| Silhouette Score | ✓ | `silhouette` |
| Davies-Bouldin Index | ✓ | `davies_bouldin` |
| Calinski-Harabasz Index | ✓ | `calinski_harabasz` |
| Execution Time | ✓ | `execution_time_seconds` |
| Cluster Size | ✓ | `cluster_size_largest`, `cluster_size_smallest`, `noise_count`, `noise_ratio` (cho DBSCAN) |

### 4.3. Script RUN

`scripts/run_eva01.py` — top-level orchestration; đọc từng CSV EPIC-07,
coerce, validate, ghi các artifact parquet/CSV/MD/JSON.

### 4.4. Missing reason taxonomy

Mỗi giá trị `MISSING` được gắn với một trong các missing-reason string đã
được document (ví dụ: `not_applicable_for_this_experiment`,
`feature_set_undefined_at_dataset_construction`,
`dbscan_does_not_have_requested_k`). Nhờ vậy người đọc có thể phân biệt
"not applicable by design" với "recording gap".

## 5. Đánh giá / Phân tích

### 5.1. Validation digest (từ `eva01_validation_report.json`)

- Tổng rows: **185**.
- OK rows: **185**.
- Rows với missing required fields: **0**.
- Rows với invalid metric values: **0**.
- `DUPLICATE_EXACT` groups: **0** (không có dòng trùng nhau ngoài ý muốn).
- `DUPLICATE_BY_INTENT` groups: **11** (5+5+5+5+5+5+6+5+5+6+5 dòng, chỉ
  khác nhau `execution_time_seconds`; đây là pattern mong đợi cho các run
  EXP-01–04 được re-execute cho runtime variance).
- `INCONSISTENT_CONDITIONS` groups: **6** (các perturbation set EXP-05 với
  `sigma` và `perturbation_seed` khác nhau; expected by design).

### 5.2. Cross-source row counts

Row counts trong repository khớp với các CSV nguồn:

| Nguồn | Reported rows |
|---|---|
| EXP-01 | 5 (khớp với `exp01_baseline_summary.csv`) |
| EXP-02 | 37 (khớp với `exp02_cluster_number_summary.csv` + `metric_curves.csv`) |
| EXP-03 | 38 (khớp với `exp03_hyperparameter_results.csv` + selected configs) |
| EXP-04 | 30 (khớp với `exp04_scenario_results.csv`, toàn bộ là K-Means) |
| EXP-05 | 75 (khớp với 25 + 15 + 35) |
| **Tổng** | **185** |

### 5.3. Provenance / SHA verification

- Hai giá trị SHA-256 feature-set khác nhau xuất hiện:
  - `ba54033e45525bf5123c2d9d3684b110676a84e81d4d505bb781a3be10980f9c`
    — FE-06 working dataset (khớp với `docs/methodology/research_questions.md`).
  - `df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649`
    — EXP-04 family B preprocessing scenarios (30 dòng).
- 5 dòng EXP-01 có `feature_set_sha256 = MISSING` vì EXP-01 chạy trên
  `final_clustering_dataset.parquet` đã được chuẩn bị sẵn mà không có per-record
  hash tracking — được annotate bằng `feature_set_sha256_missing_reason`.

## 6. Artifacts

| File | Content |
|---|---|
| `reports/evaluation/eva01/eva01_experiment_repository.parquet` | Kho lưu trữ per-run được chuẩn hoá (185 rows × 68 cols) |
| `reports/evaluation/eva01/eva01_experiment_repository.csv` | CSV mirror của parquet |
| `reports/evaluation/eva01/eva01_experiment_summary.csv` | Summary per-experiment |
| `reports/evaluation/eva01/eva01_algorithm_summary.csv` | Summary per-(experiment, algorithm) |
| `reports/evaluation/eva01/eva01_k_summary.csv` | Summary per-(experiment, algorithm, K) |
| `reports/evaluation/eva01/eva01_validation_report.json` | Validation outcomes per-row (n_total=185, n_ok=185) |
| `reports/evaluation/eva01/eva01_summary.md` | Narrative Markdown summary |

## 7. Validation

Các test dưới `tests/test_eva01_experiment_results.py` (947 dòng, 9 test
class): tất cả pass. Test `TestIntegrationOnRealEva01` load kho lưu trữ
thực trên disk và thực thi schema validation, duplicate detection và
summary builders trên dữ liệu thực.

## 8. Kết quả / Findings

- Cả năm thí nghiệm đều được đại diện.
- Cả năm thuật toán (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means)
  đều được đại diện. **K-Medoids absent** (per ADR-0003).
- Schema nhất quán trên tất cả 185 dòng.
- Không có duplicate thực sự.
- 11 `DUPLICATE_BY_INTENT` groups và 6 `INCONSISTENT_CONDITIONS` groups
  đã được giải thích (chỉ khác nhau runtime; perturbation variability là
  cố ý).
- Source-feature SHA values khớp với methodology doc reference.

## 9. Limitations

| ID | Limitation | Source |
|---|---|---|
| L1 | 5 dòng EXP-01 có `feature_set_sha256 = MISSING` vì EXP-01 chạy trước khi per-record feature-set hashing được giới thiệu; dòng được annotate qua `feature_set_sha256_missing_reason`. | `eva01_validation_report.json` + `schema.py` |
| L2 | 75 dòng EXP-05 có `decision_status` trống vì EXP-05 báo cáo `decision_status` theo block (R / S / N) trong `exp05_*_aggregate.csv` chứ không theo run. Status theo run được ghi là `run_status` (tất cả SUCCESS). | `eva01_validation_report.json` n_ok = 185 |
| L3 | Aggregate counts chỉ mang tính mô tả; không có claim "best algorithm" nào được tính. | AGENTS.md §2, schema forbidden-decision-labels |

## 10. Research Status

- **Algorithm scope**: K-Medoids OUT OF SCOPE per ADR-0003 — không có trong
  kho lưu trữ.
- **Decision status values** bị giới hạn ở enum
  `ALLOWED_DECISION_STATUSES` (`SUCCESS`, `CANDIDATE_SCENARIO`, và các
  status block-level EXP-05 `REPRODUCIBILITY_VERIFIED`,
  `STABILITY_EVIDENCE_GENERATED`, `PERTURBATION_EVIDENCE_GENERATED`,
  `SIGMA_ZERO_BASELINE_MATCH`). Danh sách `FORBIDDEN_DECISION_LABELS` loại
  trừ `BEST`, `WINNER`, `OPTIMAL`, `RECOMMENDED`, `FINAL`.

## 11. Traceability

- Source schema → `src/customer_segmentation/evaluation/experiment_results/schema.py`
- Source collectors → `src/customer_segmentation/evaluation/experiment_results/collectors.py`
- Runner → `scripts/run_eva01.py`
- Tests → `tests/test_eva01_experiment_results.py`
- Outputs → `reports/evaluation/eva01/`
- ADR → `docs/decisions/0003-algorithm-scope.md`