# EVA-03 — Đánh giá Stability & Reproducibility

> **Task ID:** EPIC-08 / EVA-03
> **Status:** IMPLEMENTED (source package tồn tại; không có direct test
> file; EXP-05 upstream có test coverage 1246 dòng)
> **Generated:** 2026-09-23

## 1. Mục tiêu

Tổng hợp evidence về stability / reproducibility từ EXP-05 (Block R:
reproducibility; Block S: seed stability; Block N: perturbation
robustness) và báo cáo các quan sát per-algorithm mà không promote bất
kỳ thuật toán nào thành "best / winner / optimal".

## 2. Scope

### 2.1. In scope

- Năm thuật toán (cả năm đều được đánh giá trong Block R và Block N; chỉ
  ba thuật toán stochastic — K-Means, GMM, Fuzzy C-Means — tham gia Block S
  vì Agglomerative + DBSCAN là deterministic).
- Ba sub-evaluation EXP-05: reproducibility (Block R), seed stability
  (Block S), perturbation robustness (Block N).
- Metric variation (silhouette / DBI / CH / WCSS) xuyên suốt repeats / seeds
  / perturbation seeds.
- Cluster-size variation (label-ID-independent partition min / max /
  range).
- Cluster-balance qualitative observation.
- Cluster-size consistency (`exp05_cluster_size_consistency.csv`).

### 2.2. Out of scope

- Pairwise ARI / AMI / NMI computation (underlying labels parquet có sẵn
  nhưng metric calculation được deferred — xem EPIC-08 pending decision
  `EPIC08-STAB-01`).
- Hungarian label alignment vượt quá một descriptive singleton row per
  algorithm.
- Hyperparameter stability (EXP-01 default vs EXP-03 working-selected
  cluster labels) — `EV03-HP-01`, không trong scope vì EXP-03 working-
  selected labels không được persist.
- Statistical tests / confidence intervals.
- Re-running bất kỳ thí nghiệm nào.
- Cross-algorithm ranking / overall stability score.

## 3. Input

Read-only:

| Nguồn | Rows | Vai trò |
|---|---|---|
| `reports/exp05/exp05_reproducibility_aggregate.csv` | 5 | Block R summary |
| `reports/exp05/exp05_seed_sweep_aggregate.csv` | 3 | Block S summary |
| `reports/exp05/exp05_noise_perturbation_aggregate.csv` | 15 | Block N summary |
| `reports/exp05/exp05_reproducibility_results.csv` | 25 | Per-run Block R records |
| `reports/exp05/exp05_seed_sweep_results.csv` | 15 | Per-run Block S records |
| `reports/exp05/exp05_noise_perturbation_results.csv` | 35 | Per-run Block N records |
| `reports/exp05/exp05_cluster_size_consistency.csv` | 440 | Per-run per-cluster sizes |
| `reports/exp05/exp05_analysis.md` | — | EXP-05 narrative evidence |
| `reports/exp05/exp05_cluster_labels.parquet` | 327 825 | KHÔNG được consume bởi run này (deferred sang đánh giá EPIC-08) |

## 4. Phương pháp / Implementation

### 4.1. Vị trí package

`src/customer_segmentation/evaluation/eva03/`:

- `types.py` — block enum và value types.
- `load.py` — đọc aggregate và per-run CSVs.
- `reproducibility.py` — phân tích Block R (labels_hash unique count, metric
  CV).
- `seed_stability.py` — phân tích Block S.
- `perturbation.py` — phân tích Block N (sigma = 0 sanity check, sigma =
  0.01 / 0.05 perturbation).
- `cluster_size.py` — per-(cluster, run) min/max/range; cả partition-level
  label-ID-independent summary.
- `label_compare.py` — ARI / AMI / NMI / Hungarian primitives (KHÔNG được
  apply trong run hiện tại).
- `hungarian.py` — descriptive Hungarian-alignment summary (một row per
  algorithm, KHÔNG phải stability metric).
- `hyperparameter_stability.py` — so sánh metadata-only EXP-01 default vs
  EXP-03 working-selected (metric values, không phải labels — vì labels
  không được persist).
- `report.py` — Markdown report builders.
- `runner.py` — top-level orchestration.

### 4.2. Script RUN

`scripts/run_eva03.py`.

### 4.3. Pre-flight audit

`reports/evaluation/eva03/eva03_preflight.md` document readiness của
evidence EXP-05 hiện có và xác định những gì KHÔNG THỂ compute từ
artifacts hiện có (ARI/AMI/NMI computation deferred sang EPIC-08;
hyperparameter-stability computation deferred do thiếu labels artifact —
`EV03-HP-01`).

## 5. Đánh giá / Phân tích

### 5.1. Block R (reproducibility — 5 thuật toán × 5 repeats × seed=42)

- `labels_hash_unique_count = 1` và metric CV = 0 cho tất cả 5 thuật toán.
- `REPRODUCIBILITY_VERIFIED` cho tất cả 5 thuật toán.

### 5.2. Block S (seed stability — K-Means / GMM / Fuzzy C-Means × 5 seeds)

- `labels_hash_unique_count = 5` cho mỗi stochastic algorithm.
- K-Means: partition_max_size constant tại 3021 xuyên suốt 5 seeds
  (label-permutation pattern).
- GMM: partition_max_size constant tại 2068 xuyên suốt 5 seeds.
- Fuzzy C-Means: partition_max_size = 1928 cho 4 seeds; = 2904 tại
  seed=2024 (single-seed partition shift).
- `STABILITY_EVIDENCE_GENERATED` cho mỗi stochastic algorithm.

### 5.3. Block N (perturbation — 5 thuật toán × (sigma=0, 0.01, 0.05) × 3 perturbation seeds)

- `SIGMA_ZERO_BASELINE_MATCH` cho mỗi thuật toán (sanity check pass).
- `labels_hash_unique_count = 3` per (algorithm, sigma > 0).
- DBSCAN: realised `n_clusters` biến thiên 11–14 (sigma=0.01) và 12–13
  (sigma=0.05).
- 4 thuật toán khác giữ realised `n_clusters` không đổi.
- Metric CV biến thiên per thuật toán (K-Means / GMM nhỏ; FCM tại
  sigma=0.05 có sil CV 0.317).

### 5.4. Output của module hyperparameter-stability

Module tồn tại và export metadata-only comparison. Kết quả được export
nhưng KHÔNG được diễn giải thành cross-algorithm judgement.

## 6. Artifacts

| File | Content |
|---|---|
| `reports/evaluation/eva03/eva03_preflight.md` | Pre-flight audit (readiness, gaps) |
| `reports/evaluation/eva03/eva03_report.md` | Narrative Markdown (per-block, per-algorithm) |
| `reports/evaluation/eva03/figures/` | Per-block figures |
| `reports/evaluation/eva03/tables/` | Per-block summary tables |

## 7. Validation

- **Direct tests**: KHÔNG có `tests/test_eva03.py`. Đây là một known
  coverage gap (xem §9 L1).
- **Upstream tests**: `tests/test_exp05_stability.py` (1246 dòng) validate
  producer (EXP-05) mà aggregate CSVs của nó feed EVA-03.
- Runner được gọi qua `python3 scripts/run_eva03.py`; report được dựng
  deterministic từ aggregate CSVs trên disk.

## 8. Kết quả / Findings

- Tất cả 5 thuật toán: REPRODUCIBILITY_VERIFIED tại seed=42 + EXP-01
  working defaults.
- Tất cả 3 stochastic algorithms: 5 phép gán label khác biệt xuyên suốt
  seeds; partition sizes ổn định cho K-Means / GMM, shifted tại một seed
  cho Fuzzy C-Means.
- Tất cả 5 thuật toán: 3 phép gán label khác biệt per (algorithm,
  sigma > 0) xuyên suốt 3 perturbation seeds.
- DBSCAN: realised `n_clusters` biến thiên theo sigma.
- Fuzzy C-Means: sil CV tại sigma=0.05 là lớn nhất có thể thấy trong
  aggregate (0.317).
- Labels_hash được ghi như evidence; ARI / AMI / NMI computation được
  DEFERRED (không áp dụng trong run này).

## 9. Limitations

| ID | Limitation | Source |
|---|---|---|
| L1 | Không có direct test cho các module source EVA-03; coverage dựa vào upstream EXP-05 tests. | absent `tests/test_eva03.py` |
| L2 | ARI / AMI / NMI KHÔNG ĐƯỢC COMPUTE — `labels_hash_unique_count` là một proxy yếu hơn pairwise label-overlap. | EPIC-08 pending decision `EPIC08-STAB-01`; `eva03_preflight.md` §3 |
| L3 | Hungarian cluster-label alignment — chỉ một descriptive row per algorithm được ghi; không phải stability metric. | `hungarian.py` docstring |
| L4 | Hyperparameter stability label-level comparison KHÔNG ĐƯỢC ĐÁNH GIÁ — EXP-03 working-selected cluster labels không được persist. | `eva03_preflight.md` §3 EV03-HP-01 |
| L5 | Statistical tests (paired t / Wilcoxon / CIs) KHÔNG ĐƯỢC ĐÁNH GIÁ — sample sizes (n=5 seeds, n=3 perturbation seeds) quá nhỏ. | AGENTS.md §2; `eva03_preflight.md` §3 |
| L6 | DBSCAN noise bucket interpretation — DBSCAN bị loại khỏi Block S theo design (deterministic), và Block N realised-K variability của nó được ghi nhưng không biến thành stability claim. | `seed_stability.py`, `perturbation.py` docstrings |
| L7 | Cross-algorithm ranking / overall stability score bị CẤM bởi methodology. | AGENTS.md §2 |

## 10. Research Status

- **Implemented**: per-block reproducibility / seed / perturbation
  descriptive tables; cluster-size variation analysis; report builders.
- **Verified**: upstream EXP-05 aggregates (n_total = 75); report được
  dựng deterministic từ aggregates trên disk.
- **Working assumption**: `labels_hash_unique_count` được coi là label-
  level uniqueness proxy (KHÔNG phải thay thế cho ARI/AMI).
- **Pending review**: xem EXP03-SEL-02, EXP03-KM-01, EPIC08-STAB-01,
  EPIC08-CROSS-ALG-01 từ
  `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md`.
- **Deferred**: ARI / AMI / NMI / Hungarian / statistical tests /
  hyperparameter label-level stability.

## 11. Traceability

- Package → `src/customer_segmentation/evaluation/eva03/`
- Runner → `scripts/run_eva03.py`
- Pre-flight → `reports/evaluation/eva03/eva03_preflight.md`
- Report → `reports/evaluation/eva03/eva03_report.md`
- Upstream test → `tests/test_exp05_stability.py`
- Pending decisions → `docs/research/review/EXP01_EXP05_PENDING_DECISIONS.md`