# EVA-02 — Đánh giá chất lượng Cluster

> **Task ID:** EPIC-08 / EVA-02
> **Status:** IMPLEMENTED (đã VERIFIED qua bộ test 1114 dòng)
> **Generated:** 2026-09-23

## 1. Mục tiêu

Tiêu thụ kho lưu trữ chuẩn hoá EVA-01 và sinh ra các đánh giá chất lượng
mô tả trên năm thuật toán theo bốn internal metric (Silhouette,
Davies-Bouldin, Calinski-Harabasz, WCSS), với xử lý boundary nghiêm ngặt
để các biến độc lập từ các thí nghiệm khác nhau KHÔNG bị gộp vào một
ranking chung.

## 2. Scope

### 2.1. In scope

- Đọc kho lưu trữ EVA-01 (read-only).
- Bốn internal metric: Silhouette (primary), DBI, CH, WCSS.
- Bảng so sánh per-(algorithm × K), per-preprocessing, per-hyperparameter
  (mỗi bảng có boundary group được document).
- Phát hiện cross-metric conflict ở mức conflict-group.
- DBSCAN-specific noise bucket reporting (semantics K realised).
- Hình algorithm × K.

### 2.2. Out of scope

- Cross-algorithm overall ranking.
- Label "best algorithm" / "winner" / "optimal algorithm" / "recommended".
- Composite scores xuyên suốt các metric.
- Pairwise ARI / AMI / NMI / Hungarian matching (deferred sang pipeline
  đánh giá EPIC-08).

## 3. Input

`reports/evaluation/eva01/eva01_experiment_repository.parquet` (185 rows).

## 4. Phương pháp / Implementation

### 4.1. Vị trí package

`src/customer_segmentation/evaluation/eva02/`:

- `load.py` — đọc parquet và coerce types.
- `metrics.py` — internal-metric vector extraction và per-metric summary.
- `comparison.py` — bảng so sánh per-algorithm, per-K, per-preprocessing,
  per-hyperparameter; `metric_ranking_per_metric` với boundary map
  `DEFAULT_RANK_WITHIN_BY_EXPERIMENT`.
- `quality.py` — phân tích phân phối metric và phát hiện cross-metric
  conflict (rank-tolerance threshold = 1, surface rows nơi primary
  (silhouette) rank không đồng ý với secondary / tertiary rank quá 1 vị
  trí trong cùng ranking group).
- `visualization.py` — hình matplotlib (single source of cluster colors /
  labels).
- `report.py` — narrative Markdown report builder.
- `runner.py` — top-level orchestration (`Eva02Runner.run_eva02()`).

### 4.2. Comparison-boundary policy

`DEFAULT_RANK_WITHIN_BY_EXPERIMENT` khoá ranking group theo
source-experiment để các dòng có biến độc lập khác nhau KHÔNG BAO GIỜ bị
gộp:

| Experiment | Ranking boundary |
|---|---|
| EXP-01 | `(source_experiment, algorithm)` |
| EXP-02 | `(source_experiment, algorithm, n_clusters)` |
| EXP-03 | `(source_experiment, algorithm, _exp03_stage, n_clusters)` |
| EXP-04 | `(source_experiment, algorithm, _exp04_scenario)` |
| EXP-05 | `(source_experiment, algorithm, _exp05_block)` |

Các block EXP-05 R / S / N mang các biến độc lập khác nhau — chúng
KHÔNG BAO GIỜ được xếp hạng cùng nhau.

### 4.3. Cross-metric conflict detection

Hai dòng được flag (`conflict_with_secondary=True` /
`conflict_with_tertiary=True`) khi silhouette rank không đồng ý với DBI
rank hoặc CH rank quá threshold `rank_tolerance=1`
(WORKING_ANALYTICAL_THRESHOLD — được document như vậy nên bất kỳ thay đổi
nào cũng yêu cầu một ADR).

### 4.4. Hyperparameter comparison

Chỉ các dòng EXP-03 được aggregate trong bảng hyperparameter-family.
Module comparison từ chối gộp các dòng EXP-01 / EXP-02 / EXP-04 / EXP-05
vì biến độc lập của chúng khác nhau.

### 4.5. DBSCAN K semantics

`n_clusters` là *requested* K cho K-Means / Agglomerative / GMM / FCM và
*realized* K cho DBSCAN. Report explicitly annotate điều này và sử dụng
marker `(realized K)` / `(requested K)` trong hình để người đọc không
thể suy ra rằng DBSCAN được fit với một giá trị K cụ thể.

### 4.6. Script RUN

`scripts/run_eva02.py` — gọi `Eva02Runner.run_eva02()`.

## 5. Đánh giá / Phân tích

- 185 rows được tách theo map `DEFAULT_RANK_WITHIN_BY_EXPERIMENT`.
- Per-algorithm summary: 5 thuật toán, tất cả 4 metric được populate,
  runtime được ghi.
- Per-K summary: 17 giá trị K riêng biệt xuyên suốt EXP-01–05.
- Per-preprocessing summary: chỉ EXP-04 có non-MISSING preprocessing
  combinations (K-Means only).
- Per-hyperparameter summary: giới hạn ở các dòng EXP-03
  (`include_non_exp03_aggregate` defaults to `False`; thiết lập thành
  `True` yêu cầu explicit opt-in).
- Cross-metric conflict flags: một non-zero subset của các dòng trong
  EXP-03 và EXP-05 flag `conflict_with_tertiary=True`, ghi lại sự bất
  đồng hợp lệ giữa silhouette ranking và CH ranking trong cùng conflict
  group.
- DBSCAN noise table: noise counts được báo cáo per source experiment
  (EXP-01 noise = 3177, EXP-02 noise = 3177, EXP-03 noise = 0 across
  all configurations; EXP-05 noise ranges từ 3177 đến 3897 xuyên suốt
  perturbation seeds).

## 6. Artifacts

| File | Content |
|---|---|
| `reports/evaluation/eva02/eva02_report.md` | Narrative Markdown |
| `reports/evaluation/eva02/eva02_run_manifest.json` | Run manifest (timestamps, table list, figure list) |
| `reports/evaluation/eva02/tables/eva02_dataset_overview.csv` | Dataset overview |
| `reports/evaluation/eva02/tables/eva02_by_algorithm.csv` | Per-algorithm summary |
| `reports/evaluation/eva02/tables/eva02_by_k.csv` | Per-K summary (xuyên suốt algorithms) |
| `reports/evaluation/eva02/tables/eva02_by_algorithm_and_k.csv` | Per-(algorithm, K) detail |
| `reports/evaluation/eva02/tables/eva02_by_preprocessing.csv` | Per-preprocessing (EXP-04 only) |
| `reports/evaluation/eva02/tables/eva02_by_hyperparameter.csv` | Per-hyperparameter (EXP-03 only by default) |
| `reports/evaluation/eva02/tables/eva02_quality_by_algorithm.csv` | Per-algorithm quality |
| `reports/evaluation/eva02/tables/eva02_quality_by_k.csv` | Per-K quality |
| `reports/evaluation/eva02/tables/eva02_quality_by_preprocessing.csv` | Per-preprocessing quality |
| `reports/evaluation/eva02/tables/eva02_cross_metric_conflicts.csv` | Tất cả conflict-group rows với per-metric rank của chúng |
| `reports/evaluation/eva02/tables/eva02_cross_metric_conflicts_flagged.csv` | Chỉ các dòng vượt rank_tolerance |
| `reports/evaluation/eva02/tables/eva02_dbscan_noise.csv` | DBSCAN noise bucket per source experiment |
| `reports/evaluation/eva02/tables/eva02_ranking_silhouette.csv` | Within-boundary ranks per metric |
| `reports/evaluation/eva02/tables/eva02_ranking_davies_bouldin.csv` | |
| `reports/evaluation/eva02/tables/eva02_ranking_calinski_harabasz.csv` | |
| `reports/evaluation/eva02/tables/eva02_ranking_wcss.csv` | |
| `reports/evaluation/eva02/figures/eva02_*_metric_*.png` | 20 hình trên 5 experiments × 4 metrics |

## 7. Validation

Tests dưới `tests/test_eva02.py` (1114 dòng, 8 test class): tất cả
pass. Test `TestIntegrationOnRealEva01` load kho lưu trữ EVA-01 trên disk
và xác minh rằng within-boundary ranking không tạo ra cross-experiment
mixing.

## 8. Kết quả / Findings

- Cả 5 thuật toán được đánh giá theo task brief.
- Cả 4 metric (Silhouette, DBI, CH, WCSS) được populate cho mọi thuật toán
  tại EXP-01 working defaults.
- 4 bảng ranking per-metric liệt kê các dòng trong mỗi conflict group;
  chúng KHÔNG phải cross-algorithm ranking.
- K ranges: 2–10 từ EXP-02 K-sweep; K=4 từ EXP-01 baseline và EXP-04
  preprocessing scenarios; realised K từ EXP-03 (extended K grid cho
  hyperparameter sweep); realised K từ EXP-05 blocks.
- DBSCAN được phân biệt chính xác: requested K vs realised K được
  annotate, và noise bucket được báo cáo riêng.

## 9. Limitations

| ID | Limitation | Source |
|---|---|---|
| L1 | Bảng ranking per-experiment (rows 1..N trong một group) có thể sinh rank=1 cho mọi dòng trong 1-row group; chúng KHÔNG phải cross-algorithm ranking. | `comparison.py` docstring |
| L2 | Cross-metric conflict detection nằm trong conflict-group, không cross-algorithm. Một dòng trong EXP-03 K=3 linkage=average flag `conflict_with_tertiary=True` (silhouette 1 vs CH 3 vs DBI 1) nhưng report KHÔNG biến điều này thành algorithm judgement. | `quality.py` rank_tolerance=1 |
| L3 | WCSS trong `eva02_by_k` khác nhau 7 bậc độ lớn xuyên suốt K; WCSS được báo cáo cho đầy đủ (diagnostic only) và KHÔNG là một phần của bất kỳ quality judgement nào. | `eva02_report.md` §4 |
| L4 | Hyperparameter comparison giới hạn ở EXP-03; các dòng hyperparameter cross-experiment không được gộp. | `comparison.py` `compare_by_hyperparameter` default |
| L5 | Không có pairwise label-level analysis (ARI / AMI / Hungarian); deferred. | AGENTS.md §2; EPIC-08 boundary |

## 10. Research Status

- **Implemented**: các bảng so sánh mô tả, conflict detection, ranking
  per-metric within-boundary, DBSCAN noise handling.
- **Verified**: bộ test 1114 dòng pass; on-disk integration test pass.
- **Working assumption**: `rank_tolerance=1` là
  WORKING_ANALYTICAL_THRESHOLD; được document trong source code nên bất
  kỳ thay đổi nào trong tương lai cũng yêu cầu một ADR.
- **Pending review**: không có pending cụ thể cho implementation này.
- **Deferred / out of scope**: cross-algorithm ranking, composite scores,
  ARI / AMI / Hungarian (pipeline đánh giá EPIC-08).

## 11. Traceability

- Package → `src/customer_segmentation/evaluation/eva02/`
- Runner → `scripts/run_eva02.py`
- Tests → `tests/test_eva02.py`
- Outputs → `reports/evaluation/eva02/`
- Methodology → `docs/methodology/research_questions.md`